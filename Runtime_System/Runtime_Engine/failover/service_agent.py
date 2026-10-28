#!/usr/bin/env python3

import argparse
import json
import os
import select
import signal
import sys
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

from common import JsonlWriter, monotonic_raw_ns, process_matches
from scheduling import require_unmodified_scheduling
from service_chain import ServiceFailoverChain
from service_http import http_json_request


CONTROL_EVENTS = {"READY", "WATCHING"}


@contextmanager
def cleanup_on_termination():
    signals = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
    previous = {}

    def terminate(signum, frame):
        # Let the owned restore child finish bounded cleanup during unwinding.
        for handled in signals:
            signal.signal(handled, signal.SIG_IGN)
        raise SystemExit(128 + signum)

    try:
        for handled in signals:
            previous[handled] = signal.signal(handled, terminate)
        yield
    finally:
        for handled, handler in previous.items():
            signal.signal(handled, handler)


def announce(writer, event, **fields):
    record = writer.write(event, **fields)
    if event in CONTROL_EVENTS:
        print(json.dumps(record, sort_keys=True), flush=True)
    return record


def validate_ready(status, payload, event_id, instance_id):
    expected = {
        "event_id": event_id,
        "instance_id": instance_id,
    }
    actual = {key: payload.get(key) for key in expected}
    if status != 200 or actual != expected or not payload.get("boot_id"):
        raise RuntimeError(
            f"{instance_id} readiness mismatch status={status} "
            f"payload={payload}"
        )


def wait_for_ready_convergence(
    host,
    port,
    event_id,
    instance_id,
    consecutive_successes,
    request_timeout_ms,
    convergence_timeout_ms,
    interval_us,
    request=http_json_request,
):
    if consecutive_successes <= 0 or convergence_timeout_ms <= 0:
        raise ValueError("readiness convergence limits must be positive")
    deadline = time.monotonic() + convergence_timeout_ms / 1000
    consecutive = 0
    attempts = 0
    transport_failures = 0
    last_transport_error = None
    started_ns = monotonic_raw_ns()
    while time.monotonic() < deadline:
        attempts += 1
        try:
            status, payload = request(
                host,
                port,
                event_id,
                request_timeout_ms,
                path="/readyz",
            )
        except Exception as error:
            consecutive = 0
            transport_failures += 1
            last_transport_error = str(error)
        else:
            # A response from the wrong instance is an identity
            # violation, not a transient transport failure to retry.
            validate_ready(status, payload, event_id, instance_id)
            consecutive += 1
            if consecutive >= consecutive_successes:
                return {
                    "attempts": attempts,
                    "consecutive_successes": consecutive,
                    "transport_failures": transport_failures,
                    "duration_us": (monotonic_raw_ns() - started_ns) / 1000,
                }
        if interval_us > 0:
            time.sleep(interval_us / 1_000_000)
    raise RuntimeError(
        f"{instance_id} readiness did not converge: attempts={attempts} "
        f"consecutive={consecutive}/{consecutive_successes} "
        f"transport_failures={transport_failures} "
        f"last_error={last_transport_error!r}"
    )


def wait_for_arm(fd):
    try:
        value = os.read(fd, 2)
    finally:
        os.close(fd)
    if value != b"1":
        raise RuntimeError("invalid or missing arm signal")


def wait_for_pidfd_exit(poller, timeout_ms):
    if timeout_ms < 0:
        raise ValueError("fence timeout must be non-negative")
    return bool(poller.poll(timeout_ms))


def resolve_container_cgroup(pid, container_id, cgroup_root="/sys/fs/cgroup"):
    lines = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8").splitlines()
    unified = []
    for line in lines:
        fields = line.split(":", 2)
        if len(fields) == 3 and fields[0] == "0" and fields[1] == "":
            unified.append(fields[2])
    if len(unified) != 1:
        raise RuntimeError("active process has no exact cgroup v2 identity")

    root = Path(cgroup_root).resolve()
    cgroup = (root / unified[0].lstrip("/")).resolve()
    if Path(os.path.commonpath((root, cgroup))) != root:
        raise RuntimeError(f"active cgroup escapes root: {cgroup}")
    if container_id not in cgroup.name:
        raise RuntimeError(
            f"active cgroup does not match container identity: {cgroup}"
        )
    for control in (
        "cgroup.events",
        "cgroup.freeze",
        "cgroup.kill",
        "cgroup.threads",
    ):
        if not (cgroup / control).is_file():
            raise RuntimeError(f"missing cgroup v2 control {control}: {cgroup}")
    return cgroup


def cgroup_is_frozen(cgroup):
    events = {}
    content = (cgroup / "cgroup.events").read_text(encoding="utf-8")
    for line in content.splitlines():
        key, value = line.split(None, 1)
        events[key] = value
    return events.get("frozen") == "1"


def container_task_group_is_stopped(pid, cgroup, proc_root="/proc"):
    try:
        task_root = Path(proc_root) / str(pid) / "task"
        task_ids = {
            int(path.name)
            for path in task_root.iterdir()
            if path.name.isdigit()
        }
        cgroup_threads = {
            int(line)
            for line in (cgroup / "cgroup.threads").read_text(
                encoding="ascii"
            ).splitlines()
        }
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        return False
    if not task_ids or task_ids != cgroup_threads:
        return False
    for task_id in task_ids:
        fields = {}
        try:
            status = (task_root / str(task_id) / "status").read_text(
                encoding="utf-8"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return False
        for line in status.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key] = value.strip()
        if fields.get("Tgid") != str(pid):
            return False
        if fields.get("State", "")[:1] not in {"T", "t"}:
            return False
    return True


def freeze_cgroup(cgroup, timeout_ms):
    if timeout_ms <= 0:
        raise ValueError("fence timeout must be positive")
    started_ns = monotonic_raw_ns()
    deadline_ns = started_ns + timeout_ms * 1_000_000
    (cgroup / "cgroup.freeze").write_text("1", encoding="ascii")
    while monotonic_raw_ns() < deadline_ns:
        if cgroup_is_frozen(cgroup):
            return (monotonic_raw_ns() - started_ns) / 1000
        time.sleep(0.00005)
    raise RuntimeError("active cgroup did not freeze before fencing deadline")


def kill_cgroup(cgroup):
    (cgroup / "cgroup.kill").write_text("1", encoding="ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--start-ticks", type=int, required=True)
    parser.add_argument("--active-ip", required=True)
    parser.add_argument("--backup-ip", required=True)
    parser.add_argument("--active-instance-id", default="active")
    parser.add_argument("--backup-instance-id", default="backup")
    parser.add_argument("--backend-port", type=int, default=8080)
    parser.add_argument("--chain", default="TANGO2-TC2-SVC")
    parser.add_argument("--service-ip", default="10.111.255.250")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument("--node-ip", default="10.2.58.155")
    parser.add_argument("--node-port", type=int, default=30082)
    parser.add_argument("--arm-fd", type=int, required=True)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--health-interval-us", type=int, default=2000)
    parser.add_argument("--health-timeout-ms", type=int, default=2)
    parser.add_argument("--health-baseline-timeout-ms", type=int, default=10)
    parser.add_argument("--health-confirm-timeout-ms", type=int, default=10)
    parser.add_argument("--health-final-timeout-ms", type=int, default=5)
    parser.add_argument("--health-failure-threshold", type=int, default=1)
    parser.add_argument("--health-baseline-successes", type=int, default=20)
    parser.add_argument(
        "--readiness-convergence-timeout-ms", type=int, default=5000
    )
    parser.add_argument("--fence-timeout-ms", type=int, default=5)
    parser.add_argument("--exit-timeout-ms", type=int, default=100)
    parser.add_argument("--log", required=True, help="controller-owned evidence path")
    parser.add_argument("--log-fd", type=int, required=True)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("service agent must run as root")
    if not hasattr(os, "pidfd_open") or not hasattr(
        signal, "pidfd_send_signal"
    ):
        raise SystemExit("pidfd APIs are unavailable")
    scheduling = require_unmodified_scheduling(label="service agent")
    if not process_matches(args.pid, args.start_ticks, args.container_id):
        raise SystemExit("active PID identity validation failed")
    active_cgroup = resolve_container_cgroup(
        args.pid, args.container_id
    )

    chain = ServiceFailoverChain(
        args.chain,
        args.service_ip,
        args.service_port,
        args.node_ip,
        args.node_port,
    )
    pidfd = os.pidfd_open(args.pid, 0)

    # The controller retains this memfd across agent failure and persists it
    # only after recovery, or as invalid diagnostic evidence after an abort.
    with ExitStack() as resources:
        resources.callback(os.close, pidfd)
        resources.enter_context(cleanup_on_termination())
        poller = select.poll()
        poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        writer = resources.enter_context(
            JsonlWriter(fd=args.log_fd, max_bytes=16 * 1024 * 1024)
        )
        prepared = resources.enter_context(
            chain.prepare_target(args.backup_ip, args.backend_port)
        )
        active_startup = wait_for_ready_convergence(
            args.active_ip,
            args.backend_port,
            args.event_id,
            args.active_instance_id,
            args.health_baseline_successes,
            args.health_baseline_timeout_ms,
            args.readiness_convergence_timeout_ms,
            args.health_interval_us,
        )
        backup_startup = wait_for_ready_convergence(
            args.backup_ip,
            args.backend_port,
            args.event_id,
            args.backup_instance_id,
            args.health_baseline_successes,
            args.health_baseline_timeout_ms,
            args.readiness_convergence_timeout_ms,
            args.health_interval_us,
        )
        announce(
            writer,
            "READY",
            event_id=args.event_id,
            container_id=args.container_id,
            pid=args.pid,
            start_ticks=args.start_ticks,
            scheduling_mode="none",
            scheduling=scheduling,
            health_failure_threshold=args.health_failure_threshold,
            health_interval_us=args.health_interval_us,
            health_baseline_timeout_ms=args.health_baseline_timeout_ms,
            health_timeout_ms=args.health_timeout_ms,
            active_startup=active_startup,
            backup_startup=backup_startup,
            prepared_restore_pid=prepared.pid,
            prepared_restore_version=prepared.version,
        )
        wait_for_arm(args.arm_fd)
        if not process_matches(args.pid, args.start_ticks, args.container_id):
            raise RuntimeError("active identity changed before arm")
        active_armed = wait_for_ready_convergence(
            args.active_ip,
            args.backend_port,
            args.event_id,
            args.active_instance_id,
            args.health_baseline_successes,
            args.health_baseline_timeout_ms,
            args.readiness_convergence_timeout_ms,
            args.health_interval_us,
        )
        backup_armed = wait_for_ready_convergence(
            args.backup_ip,
            args.backend_port,
            args.event_id,
            args.backup_instance_id,
            args.health_baseline_successes,
            args.health_baseline_timeout_ms,
            args.readiness_convergence_timeout_ms,
            args.health_interval_us,
        )
        prepared.check_alive()
        announce(
            writer,
            "WATCHING",
            event_id=args.event_id,
            health_confirm_timeout_ms=args.health_confirm_timeout_ms,
            health_final_timeout_ms=args.health_final_timeout_ms,
            active_armed=active_armed,
            backup_armed=backup_armed,
        )

        deadline_ns = monotonic_raw_ns() + args.timeout_ms * 1_000_000
        consecutive_failures = 0
        detection_source = None
        while monotonic_raw_ns() < deadline_ns:
            if poller.poll(0):
                detection_source = "pidfd"
                break
            try:
                status, payload = http_json_request(
                    args.active_ip,
                    args.backend_port,
                    args.event_id,
                    args.health_timeout_ms,
                    path="/readyz",
                )
                validate_ready(
                    status,
                    payload,
                    args.event_id,
                    args.active_instance_id,
                )
                consecutive_failures = 0
            except Exception as error:
                consecutive_failures += 1
                announce(
                    writer,
                    "ACTIVE_HEALTH_FAILURE",
                    event_id=args.event_id,
                    consecutive_failures=consecutive_failures,
                    error=str(error),
                )
                if consecutive_failures >= args.health_failure_threshold:
                    confirmation_started_ns = monotonic_raw_ns()
                    confirmation_errors = []
                    confirmation_stages = (
                        ("primary", args.health_confirm_timeout_ms),
                        ("final", args.health_final_timeout_ms),
                    )
                    confirmation_cleared = False
                    for confirmation_stage, confirmation_timeout_ms in (
                        confirmation_stages
                    ):
                        stage_started_ns = monotonic_raw_ns()
                        try:
                            confirm_status, confirm_payload = http_json_request(
                                args.active_ip,
                                args.backend_port,
                                args.event_id,
                                confirmation_timeout_ms,
                                path="/readyz",
                            )
                            validate_ready(
                                confirm_status,
                                confirm_payload,
                                args.event_id,
                                args.active_instance_id,
                            )
                        except Exception as confirm_error:
                            confirmation_errors.append(
                                {
                                    "error": str(confirm_error),
                                    "stage": confirmation_stage,
                                    "stage_duration_us": (
                                        monotonic_raw_ns() - stage_started_ns
                                    )
                                    / 1000,
                                    "timeout_ms": confirmation_timeout_ms,
                                }
                            )
                            continue
                        confirmation_returned_ns = monotonic_raw_ns()
                        announce(
                            writer,
                            "HEALTH_SUSPICION_CLEARED",
                            event_id=args.event_id,
                            confirmation_duration_us=(
                                confirmation_returned_ns
                                - confirmation_started_ns
                            )
                            / 1000,
                            confirmation_stage=confirmation_stage,
                            preceding_errors=confirmation_errors,
                            consecutive_failures=consecutive_failures,
                        )
                        consecutive_failures = 0
                        confirmation_cleared = True
                        break
                    if not confirmation_cleared:
                        confirmation_returned_ns = monotonic_raw_ns()
                        announce(
                            writer,
                            "HEALTH_CONFIRMATION_FAILED",
                            event_id=args.event_id,
                            confirmation_duration_us=(
                                confirmation_returned_ns
                                - confirmation_started_ns
                            )
                            / 1000,
                            confirmation_errors=confirmation_errors,
                        )
                        detection_source = "active_health_confirmed"
                        break
            if poller.poll(0):
                detection_source = "pidfd"
                break
            time.sleep(args.health_interval_us / 1_000_000)
        if detection_source is None:
            announce(writer, "WATCH_TIMEOUT", event_id=args.event_id)
            return 2

        detected_ns = monotonic_raw_ns()
        announce(
            writer,
            "FAILOVER_DETECTED",
            event_id=args.event_id,
            detected_raw_ns=detected_ns,
            detection_source=detection_source,
            consecutive_health_failures=consecutive_failures,
        )

        fence_started_ns = monotonic_raw_ns()
        process_exit_confirmed_at_fence = wait_for_pidfd_exit(poller, 0)
        cgroup_freeze_error = None
        cgroup_freeze_us = None
        if process_exit_confirmed_at_fence:
            fence_result = "pidfd_exit_confirmed"
        elif container_task_group_is_stopped(args.pid, active_cgroup):
            fence_result = "task_group_stop_confirmed"
        else:
            try:
                cgroup_freeze_us = freeze_cgroup(
                    active_cgroup, args.fence_timeout_ms
                )
            except Exception as error:
                cgroup_freeze_error = str(error)
                process_exit_confirmed_at_fence = wait_for_pidfd_exit(
                    poller, args.exit_timeout_ms
                )
                if not process_exit_confirmed_at_fence:
                    fence_returned_ns = monotonic_raw_ns()
                    announce(
                        writer,
                        "ACTIVE_FENCE_FAILED",
                        event_id=args.event_id,
                        error=cgroup_freeze_error,
                        fence_execution_confirmed=False,
                        fence_returned_raw_ns=fence_returned_ns,
                        fence_duration_us=(
                            fence_returned_ns - fence_started_ns
                        )
                        / 1000,
                        fence_timeout_ms=args.fence_timeout_ms,
                    )
                    raise
                fence_result = "pidfd_exit_after_freeze_timeout"
            else:
                fence_result = "cgroup_freeze_confirmed"
        fence_returned_ns = monotonic_raw_ns()
        announce(
            writer,
            "ACTIVE_FENCED",
            event_id=args.event_id,
            cgroup=str(active_cgroup),
            cgroup_freeze_error=cgroup_freeze_error,
            cgroup_freeze_us=cgroup_freeze_us,
            fence_result=fence_result,
            fence_execution_confirmed=True,
            fence_returned_raw_ns=fence_returned_ns,
            fence_duration_us=(fence_returned_ns - fence_started_ns) / 1000,
            fence_timeout_ms=args.fence_timeout_ms,
            process_exit_confirmed_at_fence=(
                process_exit_confirmed_at_fence
            ),
        )

        switch_started_ns = monotonic_raw_ns()
        prepared.commit()
        switch_returned_ns = monotonic_raw_ns()
        announce(
            writer,
            "RULE_SWITCH_RETURNED",
            event_id=args.event_id,
            switch_returned_raw_ns=switch_returned_ns,
            switch_duration_us=(switch_returned_ns - switch_started_ns) / 1000,
        )
        chain.verify_entries()
        chain.verify_target(args.backup_ip, args.backend_port)
        announce(
            writer,
            "RULE_SWITCH_VERIFIED",
            event_id=args.event_id,
            verified_raw_ns=monotonic_raw_ns(),
        )
        cleanup_error = None
        if (
            not process_exit_confirmed_at_fence
            and not wait_for_pidfd_exit(poller, 0)
        ):
            try:
                kill_cgroup(active_cgroup)
            except Exception as error:
                if not wait_for_pidfd_exit(poller, 0):
                    cleanup_error = str(error)
        exit_wait_started_ns = monotonic_raw_ns()
        if not wait_for_pidfd_exit(poller, args.exit_timeout_ms):
            announce(
                writer,
                "ACTIVE_EXIT_PENDING",
                event_id=args.event_id,
                cleanup_error=cleanup_error,
                exit_timeout_ms=args.exit_timeout_ms,
                execution_fence_retained=True,
            )
        else:
            exit_confirmed_ns = monotonic_raw_ns()
            announce(
                writer,
                "ACTIVE_EXIT_CONFIRMED",
                event_id=args.event_id,
                cleanup_error=cleanup_error,
                exit_confirmed_raw_ns=exit_confirmed_ns,
                exit_wait_duration_us=(
                    exit_confirmed_ns - exit_wait_started_ns
                )
                / 1000,
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"event": "AGENT_FATAL", "error": str(error)}))
        raise
