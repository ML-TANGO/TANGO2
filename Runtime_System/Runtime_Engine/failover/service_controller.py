#!/usr/bin/env python3

import argparse
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from common import JsonlWriter, monotonic_raw_ns, process_matches
from runtime import resolve_container
from scheduling import require_unmodified_scheduling
from service_chain import ServiceFailoverChain
from service_http import http_json_request


KUBE_CHAIN_RE = re.compile(r"\bKUBE-(?:SVC|SEP)-[A-Z0-9]+\b")
DESTINATION_RE = re.compile(r"--to-destination ([0-9.]+):([0-9]+)")
CONNTRACK_DELETE_RE = re.compile(r"([0-9]+) flow entries have been deleted")


class AgentLogBuffer:
    """Keep agent writes off the filesystem until the probe has finished."""

    def __init__(self):
        # No disk-backed fallback: an unsupported host must fail before arming.
        self.fd = os.memfd_create("tango2-tc2-agent-log", os.MFD_CLOEXEC)
        self.persist_attempted = False

    def persist(self, path):
        self.persist_attempted = True
        with Path(path).open("xb") as output:
            offset = 0
            while chunk := os.pread(self.fd, 65536, offset):
                output.write(chunk)
                offset += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        return offset

    def close(self):
        os.close(self.fd)


def collect_agent_logs(agent, log_buffer, evidence, expected_exit=0):
    """Call after RECOVERED or SOAK_COMPLETE; storage errors invalidate the run."""
    stdout, stderr = agent.communicate(timeout=5)
    storage_error = None
    try:
        persist_started_ns = monotonic_raw_ns()
        size = log_buffer.persist(evidence / "agent.jsonl")
        persist_finished_ns = monotonic_raw_ns()
        write_json(evidence / "agent-log-storage.json", {
            "backend": "memfd",
            "bytes": size,
            "persist_started_raw_ns": persist_started_ns,
            "persist_finished_raw_ns": persist_finished_ns,
            "agent_returncode": agent.returncode,
        })
    except OSError:
        storage_error = sys.exc_info()

    diagnostics_error = None
    for path, content in (
        (evidence / "agent.stdout.txt", stdout),
        (evidence / "agent.stderr.txt", stderr),
    ):
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            if diagnostics_error is None:
                diagnostics_error = sys.exc_info()

    if storage_error is not None:
        raise storage_error[1].with_traceback(storage_error[2])
    if diagnostics_error is not None:
        raise diagnostics_error[1].with_traceback(diagnostics_error[2])
    if agent.returncode != expected_exit:
        raise RuntimeError(f"service agent exited with {agent.returncode}")


def salvage_failed_agent_logs(agent, log_buffer, evidence):
    """Preserve available diagnostics without replacing an earlier failure."""
    if agent is not None:
        try:
            # Cleanup has stopped the agent. Read through the same text
            # streams as the handshake: communicate() bypasses readline's
            # prefetched text on POSIX and can silently discard that tail.
            agent.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            print(
                f"agent diagnostic stream save failed: {error}", file=sys.stderr
            )
        else:
            for path, stream in (
                (evidence / "agent.stdout.txt", agent.stdout),
                (evidence / "agent.stderr.txt", agent.stderr),
            ):
                try:
                    path.write_text(stream.read(), encoding="utf-8")
                except (OSError, ValueError) as error:
                    print(
                        f"agent diagnostic stream save failed: {error}",
                        file=sys.stderr,
                    )
    try:
        log_buffer.persist(evidence / "agent.jsonl")
    except OSError as error:
        print(f"agent diagnostic log save failed: {error}", file=sys.stderr)


def salvage_failed_probe_logs(probe, records, evidence):
    """Retain the baseline and any terminal/partial output after an abort."""
    for name, prefix, stream in (
        ("pod-probe.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n"
                                   for row in records), probe.stdout),
        ("pod-probe.stderr.txt", "", probe.stderr),
    ):
        path = evidence / name
        if path.exists():
            continue
        try:
            # Use the handshake's text stream so prefetched output is retained.
            content = prefix + stream.read()
            with path.open("x", encoding="utf-8") as output:
                output.write(content)
        except (OSError, ValueError) as error:
            print(f"probe diagnostic log save failed: {error}", file=sys.stderr)


def manual_steps_from_env():
    if not os.environ.get("TANGO2_STEP_CONTROL"):
        return None
    from manual_steps import ManualSteps

    steps = ManualSteps.from_env()
    if steps is not None:
        target = os.environ.get("TANGO2_STEP_TARGET")
        if not target:
            raise RuntimeError("manual TC2 event target is missing")
        steps.target(target)
    return steps


def live_children_guard(agent, probe=None):
    def guard():
        for name, process in (("agent", agent), ("probe", probe)):
            if process is not None and process.poll() is not None:
                raise RuntimeError(f"service {name} exited while awaiting manual action")
    return guard


def wait_for_manual_injection(steps, agent, probe, event_id):
    if steps is None:
        return
    deadline = time.monotonic() + 30
    children_alive = live_children_guard(agent, probe)

    def guard():
        if time.monotonic() >= deadline:
            raise RuntimeError("manual injection lease expired")
        children_alive()

    steps.wait("MONITOR_READY", ["inject"], timeout=30, guard=guard,
               details={"event_id": event_id, "injection_lease_seconds": 30})
    # Also reject a request accepted at the lease boundary or a dead child
    # before entering the original PID-checked injection sequence.
    guard()


def collect_agent_logs_after_probe_completion(
    completion_event,
    probe,
    agent,
    log_buffer,
    evidence,
    timeout_seconds,
    probe_records,
    expected_exit=0,
):
    if completion_event == "RECOVERED":
        completion = wait_for_recovery(
            probe, agent, timeout_seconds, probe_records
        )
    elif completion_event == "SOAK_COMPLETE":
        completion = read_until_event(
            probe, completion_event, timeout_seconds, probe_records
        )
    else:
        raise ValueError(f"unsupported probe completion event: {completion_event}")

    remaining_stdout, probe_stderr = probe.communicate(timeout=5)
    if remaining_stdout:
        probe_records.extend(
            json.loads(line) for line in remaining_stdout.splitlines() if line
        )
    (evidence / "pod-probe.jsonl").write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in probe_records
        ),
        encoding="utf-8",
    )
    (evidence / "pod-probe.stderr.txt").write_text(
        probe_stderr, encoding="utf-8"
    )
    if probe.returncode != 0:
        raise RuntimeError(f"Pod probe exited with {probe.returncode}")

    collect_agent_logs(agent, log_buffer, evidence, expected_exit)
    return completion


def run_json(command, input_value=None):
    completed = subprocess.run(
        command,
        input=input_value,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_service(args):
    service = run_json(
        [
            "kubectl",
            "--kubeconfig",
            args.kubeconfig,
            "-n",
            args.namespace,
            "get",
            "service",
            args.service,
            "-o",
            "json",
        ]
    )
    spec = service["spec"]
    ports = spec.get("ports", [])
    if spec.get("selector"):
        raise RuntimeError("integrated Service must be selectorless")
    if spec.get("type") != "NodePort" or spec.get("clusterIP") != args.service_ip:
        raise RuntimeError("integrated Service type or ClusterIP mismatch")
    if len(ports) != 1:
        raise RuntimeError("integrated Service must expose one port")
    expected_port = {
        "name": args.service_port_name,
        "nodePort": args.node_port,
        "port": args.service_port,
        "protocol": "TCP",
        "targetPort": args.backend_port,
    }
    actual_port = {key: ports[0].get(key) for key in expected_port}
    if actual_port != expected_port:
        raise RuntimeError(
            f"integrated Service port mismatch: {actual_port}"
        )
    return service


def endpoint_slice_manifest(args, target):
    return {
        "apiVersion": "discovery.k8s.io/v1",
        "kind": "EndpointSlice",
        "metadata": {
            "name": args.endpoint_slice,
            "namespace": args.namespace,
            "labels": {
                "endpointslice.kubernetes.io/managed-by": (
                    "tango2.rtst.co.kr-tc2-controller"
                ),
                "kubernetes.io/service-name": args.service,
            },
        },
        "addressType": "IPv4",
        "ports": [
            {
                "name": args.service_port_name,
                "port": args.backend_port,
                "protocol": "TCP",
            }
        ],
        "endpoints": [
            {
                "addresses": [target.pod_ip],
                "conditions": {
                    "ready": True,
                    "serving": True,
                    "terminating": False,
                },
                "nodeName": args.node_name,
                "targetRef": {
                    "kind": "Pod",
                    "name": target.pod_name,
                    "namespace": args.namespace,
                    "uid": target.pod_uid,
                },
            }
        ],
    }


def apply_endpoint_slice(args, target):
    manifest = endpoint_slice_manifest(args, target)
    command = [
        "kubectl",
        "--kubeconfig",
        args.kubeconfig,
        "apply",
        "-f",
        "-",
    ]
    completed = subprocess.run(
        command,
        input=json.dumps(manifest),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "EndpointSlice apply failed: " + completed.stderr.strip()
        )
    return manifest


def nat_rules():
    completed = subprocess.run(
        ["iptables", "-w", "1", "-t", "nat", "-S"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def kube_rules_snapshot(raw_rules):
    return "\n".join(
        line
        for line in raw_rules.splitlines()
        if line.startswith("-N KUBE-") or line.startswith("-A KUBE-")
    ) + "\n"


def service_backends(raw_rules, namespace, service, port_name):
    lines = raw_rules.splitlines()
    comment = f'{namespace}/{service}:{port_name} cluster IP'
    service_chains = set()
    for line in lines:
        if comment in line and "-j KUBE-SVC-" in line:
            matches = KUBE_CHAIN_RE.findall(line)
            service_chains.update(
                match for match in matches if match.startswith("KUBE-SVC-")
            )
    separator_chains = set()
    for line in lines:
        if any(line.startswith(f"-A {chain} ") for chain in service_chains):
            separator_chains.update(
                match
                for match in KUBE_CHAIN_RE.findall(line)
                if match.startswith("KUBE-SEP-")
            )
    backends = set()
    for line in lines:
        if any(line.startswith(f"-A {chain} ") for chain in separator_chains):
            match = DESTINATION_RE.search(line)
            if match:
                backends.add((match.group(1), int(match.group(2))))
    return backends


def wait_for_native_backend(args, target, timeout_seconds=10):
    deadline = time.monotonic() + timeout_seconds
    expected = {(target.pod_ip, args.backend_port)}
    observed = set()
    while time.monotonic() < deadline:
        observed = service_backends(
            nat_rules(),
            args.namespace,
            args.service,
            args.service_port_name,
        )
        if observed == expected:
            return
        time.sleep(0.05)
    raise RuntimeError(
        f"kube-proxy backend did not converge: observed={observed} "
        f"expected={expected}"
    )


def clear_service_conntrack(args, runner=subprocess.run):
    results = []
    for address, port, label in (
        (args.service_ip, args.service_port, "cluster_ip"),
        (args.node_ip, args.node_port, "node_port"),
    ):
        filters = [
            "-p",
            "tcp",
            "-d",
            address,
            "--dport",
            str(port),
        ]
        deleted = runner(
            ["conntrack", "-D", *filters],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        match = CONNTRACK_DELETE_RE.search(deleted.stderr)
        if deleted.returncode not in (0, 1) or not match:
            raise RuntimeError(
                f"conntrack delete failed for {label}: "
                f"rc={deleted.returncode} stderr={deleted.stderr!r}"
            )
        verified = runner(
            ["conntrack", "-L", *filters],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if verified.returncode != 0 or verified.stdout.strip():
            raise RuntimeError(
                f"conntrack entries remain for {label}: "
                f"rc={verified.returncode} stdout={verified.stdout!r} "
                f"stderr={verified.stderr!r}"
            )
        results.append(
            {
                "address": address,
                "deleted_entries": int(match.group(1)),
                "label": label,
                "port": port,
                "remaining_entries": 0,
            }
        )
    return {"flows": results, "valid": True}


def service_response(host, port, event_id, expected_instance, timeout_ms=50):
    status, payload = http_json_request(
        host,
        port,
        event_id,
        timeout_ms,
        path="/service",
    )
    expected = {
        "event_id": event_id,
        "instance_id": expected_instance,
    }
    actual = {key: payload.get(key) for key in expected}
    if status != 200 or actual != expected or not payload.get("boot_id"):
        raise RuntimeError(
            f"service response mismatch status={status} payload={payload}"
        )
    return payload


def wait_for_service_identity(
    host,
    port,
    event_id,
    expected_instance,
    timeout_ms=5000,
    consecutive_successes=20,
    request_timeout_ms=10,
    interval_us=2000,
):
    if timeout_ms <= 0 or consecutive_successes <= 0:
        raise ValueError("invalid convergence settings")
    started_ns = monotonic_raw_ns()
    deadline = time.monotonic() + timeout_ms / 1000
    consecutive = 0
    attempts = 0
    mismatches = 0
    last_error = None
    while time.monotonic() < deadline:
        attempts += 1
        try:
            service_response(
                host,
                port,
                event_id,
                expected_instance,
                timeout_ms=request_timeout_ms,
            )
            consecutive += 1
            if consecutive >= consecutive_successes:
                return {
                    "attempts": attempts,
                    "consecutive_successes": consecutive,
                    "duration_us": (monotonic_raw_ns() - started_ns) / 1000,
                    "event_id": event_id,
                    "instance_id": expected_instance,
                    "mismatches": mismatches,
                    "valid": True,
                }
        except (OSError, RuntimeError, TimeoutError) as error:
            consecutive = 0
            mismatches += 1
            last_error = str(error)
        time.sleep(interval_us / 1_000_000)
    raise RuntimeError(
        "service identity did not converge "
        f"attempts={attempts} mismatches={mismatches} "
        f"last_error={last_error}"
    )


def pod_probe_command(
    args,
    host,
    port,
    once=False,
    wait_active=False,
    expected_instance=None,
    stable_seconds=None,
):
    # Preserve the original names for direct callers and older fixtures.
    active_instance_id = getattr(args, "active_instance_id", "active")
    backup_instance_id = getattr(args, "backup_instance_id", "backup")
    command = [
        "kubectl",
        "--kubeconfig",
        args.kubeconfig,
        "-n",
        args.namespace,
        "exec",
        args.client_pod,
        "-c",
        args.client_container,
        "--",
        "python3",
        "/opt/tango2-tc2/service_probe.py",
        "--host",
        host,
        "--port",
        str(port),
        "--event-id",
        args.event_id,
        "--active-instance-id",
        active_instance_id,
        "--backup-instance-id",
        backup_instance_id,
    ]
    if wait_active:
        command.extend(
            [
                "--wait-active",
                "--expected-instance",
                expected_instance,
                "--probe-interval-us",
                str(args.probe_interval_us),
                "--baseline-timeout-ms",
                str(args.verification_timeout_ms),
                "--convergence-timeout-ms",
                str(args.pre_event_convergence_timeout_ms),
                "--convergence-successes",
                str(args.pre_event_convergence_successes),
            ]
        )
    elif stable_seconds is not None:
        command.extend(
            [
                "--stable-active-seconds",
                str(stable_seconds),
                "--probe-interval-us",
                str(args.probe_interval_us),
                "--request-timeout-ms",
                str(args.request_timeout_ms),
                "--baseline-timeout-ms",
                str(args.verification_timeout_ms),
                "--baseline-successes",
                str(args.baseline_successes),
            ]
        )
    elif once:
        command.extend(
            [
                "--once",
                "--expected-instance",
                expected_instance,
                "--request-timeout-ms",
                str(args.verification_timeout_ms),
            ]
        )
    else:
        command.extend(
            [
                "--baseline-successes",
                str(args.baseline_successes),
                "--probe-interval-us",
                str(args.probe_interval_us),
                "--request-timeout-ms",
                str(args.request_timeout_ms),
                "--baseline-timeout-ms",
                str(args.verification_timeout_ms),
            ]
        )
    return command


def run_pod_probe_once(args, host, port, expected_instance):
    completed = subprocess.run(
        pod_probe_command(
            args,
            host,
            port,
            once=True,
            expected_instance=expected_instance,
        ),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "one-shot Pod probe failed "
            f"rc={completed.returncode} stdout={completed.stdout!r} "
            f"stderr={completed.stderr!r}"
        )
    records = [
        json.loads(line) for line in completed.stdout.splitlines() if line
    ]
    if len(records) != 1 or records[0].get("event") != "ONCE_OK":
        raise RuntimeError(f"unexpected one-shot probe output: {records}")
    return records[0]


def run_pod_probe_convergence(args, host, port, expected_instance):
    completed = subprocess.run(
        pod_probe_command(
            args,
            host,
            port,
            wait_active=True,
            expected_instance=expected_instance,
        ),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "convergence Pod probe failed "
            f"rc={completed.returncode} stdout={completed.stdout!r} "
            f"stderr={completed.stderr!r}"
        )
    records = [
        json.loads(line) for line in completed.stdout.splitlines() if line
    ]
    if len(records) != 1 or records[0].get("event") != "CONVERGED":
        raise RuntimeError(f"unexpected convergence probe output: {records}")
    return records[0]


def read_until_event(process, expected_event, timeout_seconds, records):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select(
            [process.stdout], [], [], max(0, deadline - time.monotonic())
        )
        if not ready:
            break
        line = process.stdout.readline()
        if not line:
            break
        record = json.loads(line)
        records.append(record)
        if record.get("event") == "PROBE_FATAL":
            raise RuntimeError(f"Pod probe failed: {record}")
        if record.get("event") == expected_event:
            return record
    raise RuntimeError(f"Pod probe did not emit {expected_event}")


def wait_for_recovery(probe, agent, timeout_seconds, records):
    deadline = time.monotonic() + timeout_seconds
    monitored = {probe.stdout, agent.stdout}
    while monitored and time.monotonic() < deadline:
        ready, _, _ = select.select(
            list(monitored),
            [],
            [],
            max(0, deadline - time.monotonic()),
        )
        if not ready:
            break
        for stream in ready:
            line = stream.readline()
            if stream is agent.stdout:
                if line:
                    record = json.loads(line)
                    if record.get("event") == "AGENT_FATAL":
                        raise RuntimeError(f"service agent failed: {record}")
                else:
                    monitored.discard(stream)
                    if agent.poll() not in (None, 0):
                        raise RuntimeError(
                            f"service agent exited with {agent.returncode}"
                        )
                continue
            if not line:
                monitored.discard(stream)
                raise RuntimeError(
                    "Pod probe exited before reporting recovery "
                    f"with status {probe.poll()}"
                )
            record = json.loads(line)
            records.append(record)
            if record.get("event") == "PROBE_FATAL":
                raise RuntimeError(f"Pod probe failed: {record}")
            if record.get("event") == "RECOVERED":
                return record
    raise RuntimeError(
        f"service recovery timeout after {timeout_seconds:.3f}s "
        "from fault injection"
    )


def wait_for_agent_event(process, expected_event, timeout_seconds):
    ready, _, _ = select.select([process.stdout], [], [], timeout_seconds)
    if not ready:
        raise RuntimeError(f"service agent did not emit {expected_event}")
    record = json.loads(process.stdout.readline())
    if record.get("event") != expected_event:
        raise RuntimeError(f"unexpected service agent event: {record}")
    return record


def read_agent_event(path, event_name):
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]
    matches = [record for record in records if record.get("event") == event_name]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {event_name} record, found {len(matches)}"
        )
    return matches[0]


def read_agent_exit_state(path):
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]
    matches = [
        record
        for record in records
        if record.get("event")
        in {"ACTIVE_EXIT_CONFIRMED", "ACTIVE_EXIT_PENDING"}
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "expected one active exit terminal record, "
            f"found {len(matches)}"
        )
    return matches[0]


def application_recovery_valid(args, recovered, fenced, detected):
    return (
        recovered["instance_id"] == args.backup_instance_id
        and fenced["fence_execution_confirmed"] is True
        and (
            args.fault_mode != "hang"
            or detected["detection_source"] == "active_health_confirmed"
        )
    )


def first_post_injection_failure(recovered, injected_ns):
    observations = recovered.get("failure_observations")
    if not isinstance(observations, list):
        raise RuntimeError("probe did not report failure observations")

    candidates = []
    for observation in observations:
        started_ns = observation.get("started_raw_ns")
        observed_ns = observation.get("observed_raw_ns")
        if not isinstance(started_ns, int) or not isinstance(observed_ns, int):
            raise RuntimeError("probe failure timestamp is invalid")
        if started_ns > observed_ns:
            raise RuntimeError("probe failure timestamp order is invalid")
        if observed_ns >= injected_ns:
            candidates.append(observation)

    if not candidates:
        raise RuntimeError("probe observed no service failure after injection")
    first = min(candidates, key=lambda observation: observation["observed_raw_ns"])
    if first["observed_raw_ns"] > recovered["recovered_raw_ns"]:
        raise RuntimeError("probe failure was observed after recovery")
    return first


def health_confirmation_summary(records):
    cleared = [
        record
        for record in records
        if record.get("event") == "HEALTH_SUSPICION_CLEARED"
    ]
    durations = [record["confirmation_duration_us"] for record in cleared]
    return {
        "health_confirmation_cleared": len(cleared),
        "health_confirmation_final_stage_cleared": sum(
            record.get("confirmation_stage") == "final" for record in cleared
        ),
        "health_confirmation_max_us": max(durations, default=0),
    }


def result_exit_code(summary, accept_kpi_failure=False):
    if summary["integration_gate"] == "pass":
        return 0
    if accept_kpi_failure and summary["valid"]:
        return 0
    return 4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--namespace", default="tango2-tc2-service")
    parser.add_argument("--node-name", default="mic711-rt")
    parser.add_argument("--node-ip", default="10.2.58.155")
    parser.add_argument("--active-pod", default="tc2-service-active")
    parser.add_argument("--backup-pod", default="tc2-service-backup")
    parser.add_argument("--active-instance-id", default="active")
    parser.add_argument("--backup-instance-id", default="backup")
    parser.add_argument("--server-container", default="server")
    parser.add_argument("--client-pod", default="tc2-service-client")
    parser.add_argument("--client-container", default="client")
    parser.add_argument("--service", default="tc2-service")
    parser.add_argument("--service-ip", default="10.111.255.250")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument("--service-port-name", default="http")
    parser.add_argument("--node-port", type=int, default=30082)
    parser.add_argument("--backend-port", type=int, default=8080)
    parser.add_argument("--endpoint-slice", default="tc2-service-manual")
    parser.add_argument("--chain", default="TANGO2-TC2-SVC")
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--baseline-successes", type=int, default=100)
    parser.add_argument("--probe-interval-us", type=int, default=2000)
    parser.add_argument("--request-timeout-ms", type=int, default=2)
    parser.add_argument("--verification-timeout-ms", type=int, default=10)
    parser.add_argument(
        "--pre-event-convergence-timeout-ms", type=int, default=5000
    )
    parser.add_argument(
        "--pre-event-convergence-successes", type=int, default=20
    )
    parser.add_argument("--recovery-timeout-ms", type=int, default=1000)
    parser.add_argument("--max-probe-gap-us", type=int, default=5000)
    parser.add_argument(
        "--fault-mode", choices=("kill", "hang", "none"), default="hang"
    )
    parser.add_argument("--fence-timeout-ms", type=int, default=5)
    parser.add_argument("--exit-timeout-ms", type=int, default=100)
    parser.add_argument("--health-confirm-timeout-ms", type=int, default=10)
    parser.add_argument("--health-final-timeout-ms", type=int, default=5)
    parser.add_argument("--soak-seconds", type=float, default=1800)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--accept-kpi-failure", action="store_true")
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("service controller must run as root")
    if (
        args.pre_event_convergence_timeout_ms <= 0
        or args.pre_event_convergence_successes <= 0
    ):
        raise SystemExit("invalid pre-event convergence settings")
    if not hasattr(os, "pidfd_open") or not hasattr(
        signal, "pidfd_send_signal"
    ):
        raise SystemExit("pidfd APIs are unavailable")
    controller_scheduling = require_unmodified_scheduling(
        label="service controller"
    )

    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=False)
    controller_log = evidence / "controller.jsonl"
    agent_log = evidence / "agent.jsonl"
    agent = None
    agent_log_buffer = None
    pod_probe = None
    arm_write_fd = None
    probe_records = []
    chain_active = False
    chain = ServiceFailoverChain(
        args.chain,
        args.service_ip,
        args.service_port,
        args.node_ip,
        args.node_port,
    )

    with JsonlWriter(controller_log) as writer:
        try:
            steps = manual_steps_from_env()
            if steps is not None and args.fault_mode == "none":
                raise RuntimeError("manual TC2 steps require a fault event")
            service = verify_service(args)
            namespace = run_json(
                [
                    "kubectl",
                    "--kubeconfig",
                    args.kubeconfig,
                    "get",
                    "namespace",
                    args.namespace,
                    "-o",
                    "json",
                ]
            )
            active = resolve_container(
                args.namespace,
                args.active_pod,
                args.server_container,
                args.kubeconfig,
            )
            backup = resolve_container(
                args.namespace,
                args.backup_pod,
                args.server_container,
                args.kubeconfig,
            )
            client = resolve_container(
                args.namespace,
                args.client_pod,
                args.client_container,
                args.kubeconfig,
            )
            scheduling = {
                "controller": controller_scheduling,
                "active": require_unmodified_scheduling(
                    active.pid, "service active"
                ),
                "backup": require_unmodified_scheduling(
                    backup.pid, "service backup"
                ),
                "client_init": require_unmodified_scheduling(
                    client.pid, "service client init"
                ),
            }
            precheck = {
                "active": active.to_dict(),
                "backup": backup.to_dict(),
                "client": client.to_dict(),
                "namespace_uid": namespace["metadata"]["uid"],
                "scheduling": scheduling,
                "scheduling_mode": "none",
                "service": {
                    "cluster_ip": service["spec"]["clusterIP"],
                    "name": service["metadata"]["name"],
                    "node_port": args.node_port,
                    "selector": service["spec"].get("selector"),
                    "uid": service["metadata"]["uid"],
                },
            }
            write_json(evidence / "precheck.json", precheck)

            initial_slice = apply_endpoint_slice(args, active)
            write_json(evidence / "endpointslice.active.json", initial_slice)
            wait_for_native_backend(args, active)
            host_convergence = wait_for_service_identity(
                args.service_ip,
                args.service_port,
                args.event_id,
                args.active_instance_id,
                timeout_ms=args.pre_event_convergence_timeout_ms,
                consecutive_successes=(
                    args.pre_event_convergence_successes
                ),
                request_timeout_ms=args.verification_timeout_ms,
                interval_us=args.probe_interval_us,
            )
            cluster_convergence = run_pod_probe_convergence(
                args,
                args.service_ip,
                args.service_port,
                args.active_instance_id,
            )
            nodeport_convergence = run_pod_probe_convergence(
                args, args.node_ip, args.node_port, args.active_instance_id
            )
            pre_event_convergence = {
                "cluster_ip": cluster_convergence,
                "host": host_convergence,
                "node_port": nodeport_convergence,
                "valid": True,
            }
            write_json(
                evidence / "pre-event-convergence.json",
                pre_event_convergence,
            )
            writer.write(
                "PRE_EVENT_CONVERGED",
                event_id=args.event_id,
                convergence=pre_event_convergence,
            )
            if steps is not None:
                steps.wait("CREATED", ["agent"], details={
                    "event_id": args.event_id, "evidence_dir": str(evidence.resolve()),
                })

            kube_before = kube_rules_snapshot(nat_rules())
            (evidence / "kube.before-fast-path.txt").write_text(
                kube_before, encoding="utf-8"
            )
            chain.setup(active.pod_ip, args.backend_port)
            chain_active = True
            conntrack_before_fault = clear_service_conntrack(args)
            write_json(
                evidence / "conntrack.before-fault-reset.json",
                conntrack_before_fault,
            )
            (evidence / "chain.active.txt").write_text(
                chain.dump(), encoding="utf-8"
            )
            fast_path_host_convergence = wait_for_service_identity(
                args.service_ip,
                args.service_port,
                args.event_id,
                args.active_instance_id,
                timeout_ms=args.pre_event_convergence_timeout_ms,
                consecutive_successes=(
                    args.pre_event_convergence_successes
                ),
                request_timeout_ms=args.verification_timeout_ms,
                interval_us=args.probe_interval_us,
            )
            fast_path_cluster_convergence = run_pod_probe_convergence(
                args,
                args.service_ip,
                args.service_port,
                args.active_instance_id,
            )
            fast_path_nodeport_convergence = run_pod_probe_convergence(
                args, args.node_ip, args.node_port, args.active_instance_id
            )
            fast_path_baseline_convergence = {
                "cluster_ip": fast_path_cluster_convergence,
                "host": fast_path_host_convergence,
                "node_port": fast_path_nodeport_convergence,
                "valid": True,
            }
            write_json(
                evidence / "fast-path-baseline-convergence.json",
                fast_path_baseline_convergence,
            )

            agent_log_buffer = AgentLogBuffer()
            arm_read_fd, arm_write_fd = os.pipe()
            agent_command = [
                sys.executable,
                str(Path(__file__).with_name("service_agent.py")),
                "--event-id",
                args.event_id,
                "--container-id",
                active.container_id,
                "--pid",
                str(active.pid),
                "--start-ticks",
                str(active.start_ticks),
                "--active-ip",
                active.pod_ip,
                "--backup-ip",
                backup.pod_ip,
                "--active-instance-id",
                args.active_instance_id,
                "--backup-instance-id",
                args.backup_instance_id,
                "--backend-port",
                str(args.backend_port),
                "--chain",
                args.chain,
                "--service-ip",
                args.service_ip,
                "--service-port",
                str(args.service_port),
                "--node-ip",
                args.node_ip,
                "--node-port",
                str(args.node_port),
                "--arm-fd",
                str(arm_read_fd),
                "--fence-timeout-ms",
                str(args.fence_timeout_ms),
                "--exit-timeout-ms",
                str(args.exit_timeout_ms),
                "--health-confirm-timeout-ms",
                str(args.health_confirm_timeout_ms),
                "--health-final-timeout-ms",
                str(args.health_final_timeout_ms),
                "--timeout-ms",
                str(
                    int(args.soak_seconds * 1000 + 250)
                    if args.fault_mode == "none"
                    else 60000
                ),
                "--log",
                str(agent_log),
                "--log-fd",
                str(agent_log_buffer.fd),
            ]
            agent = subprocess.Popen(
                agent_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                pass_fds=(arm_read_fd, agent_log_buffer.fd),
            )
            os.close(arm_read_fd)
            # The agent independently proves 20 consecutive direct-backend
            # readiness responses for both replicas before becoming READY.
            agent_ready = wait_for_agent_event(agent, "READY", 12)
            writer.write(
                "AGENT_READY", event_id=args.event_id, agent=agent_ready
            )
            if steps is not None:
                steps.wait("AGENT_READY", ["monitor"],
                           guard=live_children_guard(agent),
                           details={"event_id": args.event_id})

            pod_probe = subprocess.Popen(
                pod_probe_command(
                    args,
                    args.service_ip,
                    args.service_port,
                    once=False,
                    stable_seconds=(
                        args.soak_seconds
                        if args.fault_mode == "none"
                        else None
                    ),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            probe_ready = read_until_event(
                pod_probe, "READY", 10, probe_records
            )
            writer.write(
                "POD_PROBE_READY",
                event_id=args.event_id,
                probe=probe_ready,
            )
            os.write(arm_write_fd, b"1")
            os.close(arm_write_fd)
            arm_write_fd = None
            watching = wait_for_agent_event(agent, "WATCHING", 12)
            writer.write(
                "AGENT_ARMED", event_id=args.event_id, agent=watching
            )

            if args.fault_mode == "none":
                soak_complete = collect_agent_logs_after_probe_completion(
                    "SOAK_COMPLETE",
                    pod_probe,
                    agent,
                    agent_log_buffer,
                    evidence,
                    args.soak_seconds + 10,
                    probe_records,
                    expected_exit=2,
                )
                agent_records = [
                    json.loads(line)
                    for line in agent_log.read_text(
                        encoding="utf-8"
                    ).splitlines()
                ]
                watch_timeouts = [
                    record
                    for record in agent_records
                    if record.get("event") == "WATCH_TIMEOUT"
                ]
                failovers = [
                    record
                    for record in agent_records
                    if record.get("event") == "FAILOVER_DETECTED"
                ]
                if agent.returncode != 2 or len(watch_timeouts) != 1:
                    raise RuntimeError(
                        "no-fault agent did not finish with WATCH_TIMEOUT"
                    )
                if failovers:
                    raise RuntimeError("false failover during no-fault soak")
                if not process_matches(
                    active.pid, active.start_ticks, active.container_id
                ):
                    raise RuntimeError(
                        "active identity changed during no-fault soak"
                    )
                chain.verify_entries()
                chain.verify_target(active.pod_ip, args.backend_port)
                kube_after_soak = kube_rules_snapshot(nat_rules())
                if kube_after_soak != kube_before:
                    raise RuntimeError(
                        "kube-proxy rules changed during no-fault soak"
                    )
                chain.cleanup()
                chain_active = False
                service_response(
                    args.service_ip,
                    args.service_port,
                    args.event_id,
                    args.active_instance_id,
                )
                native_cluster_probe = run_pod_probe_once(
                    args,
                    args.service_ip,
                    args.service_port,
                    args.active_instance_id,
                )
                native_nodeport_probe = run_pod_probe_once(
                    args, args.node_ip, args.node_port, args.active_instance_id
                )
                suspicion_count = sum(
                    record.get("event") == "ACTIVE_HEALTH_FAILURE"
                    for record in agent_records
                )
                summary = {
                    "active_probe_failures": soak_complete["failures"],
                    "active_probe_failure_rate": (
                        soak_complete["failures"]
                        / (
                            soak_complete["failures"]
                            + soak_complete["active_successes"]
                        )
                    ),
                    "active_probe_successes": soak_complete[
                        "active_successes"
                    ],
                    "event_id": args.event_id,
                    "false_failovers": len(failovers),
                    "health_suspicions": suspicion_count,
                    "health_confirm_timeout_ms": (
                        args.health_confirm_timeout_ms
                    ),
                    "health_final_timeout_ms": args.health_final_timeout_ms,
                    "integration_gate": "pass",
                    "kube_rules_unchanged": True,
                    "max_consecutive_probe_failures": soak_complete[
                        "max_consecutive_failures"
                    ],
                    "max_pod_probe_gap_us": soak_complete[
                        "max_probe_gap_us"
                    ],
                    "native_cluster_probe": native_cluster_probe,
                    "native_nodeport_probe": native_nodeport_probe,
                    "scheduling_mode": "none",
                    "soak_seconds": args.soak_seconds,
                    "test_mode": "no_fault_soak",
                    **health_confirmation_summary(agent_records),
                }
                write_json(evidence / "summary.json", summary)
                print(json.dumps(summary, sort_keys=True))
                return 0

            wait_for_manual_injection(steps, agent, pod_probe, args.event_id)
            if not process_matches(
                active.pid, active.start_ticks, active.container_id
            ):
                raise RuntimeError("active identity changed before injection")
            fault_pidfd = os.pidfd_open(active.pid, 0)
            injected_ns = monotonic_raw_ns()
            fault_signal = (
                signal.SIGKILL
                if args.fault_mode == "kill"
                else signal.SIGSTOP
            )
            signal.pidfd_send_signal(fault_pidfd, fault_signal)
            signal_returned_ns = monotonic_raw_ns()
            writer.write(
                "FAULT_INJECTED",
                event_id=args.event_id,
                fault_mode=args.fault_mode,
                fault_signal=signal.Signals(fault_signal).name,
                injected_raw_ns=injected_ns,
                signal_returned_raw_ns=signal_returned_ns,
                signal_syscall_us=(signal_returned_ns - injected_ns) / 1000,
                pid=active.pid,
                container_id=active.container_id,
            )
            os.close(fault_pidfd)

            recovered = collect_agent_logs_after_probe_completion(
                "RECOVERED",
                pod_probe,
                agent,
                agent_log_buffer,
                evidence,
                args.recovery_timeout_ms / 1000,
                probe_records,
            )
            chain.verify_entries()
            chain.verify_target(backup.pod_ip, args.backend_port)
            (evidence / "chain.backup.txt").write_text(
                chain.dump(), encoding="utf-8"
            )

            kube_after_fast = kube_rules_snapshot(nat_rules())
            (evidence / "kube.after-fast-switch.txt").write_text(
                kube_after_fast, encoding="utf-8"
            )
            if kube_after_fast != kube_before:
                raise RuntimeError(
                    "kube-proxy rules changed during the owned fast switch"
                )

            convergence_started_ns = monotonic_raw_ns()
            backup_slice = apply_endpoint_slice(args, backup)
            write_json(evidence / "endpointslice.backup.json", backup_slice)
            wait_for_native_backend(args, backup)
            convergence_returned_ns = monotonic_raw_ns()
            writer.write(
                "ENDPOINTSLICE_CONVERGED",
                event_id=args.event_id,
                convergence_returned_raw_ns=convergence_returned_ns,
                convergence_duration_us=(
                    convergence_returned_ns - convergence_started_ns
                )
                / 1000,
            )
            (evidence / "kube.after-convergence.txt").write_text(
                kube_rules_snapshot(nat_rules()), encoding="utf-8"
            )

            chain.cleanup()
            chain_active = False
            conntrack_after_fast_path = clear_service_conntrack(args)
            write_json(
                evidence / "conntrack.after-fast-path-reset.json",
                conntrack_after_fast_path,
            )
            native_host_convergence = wait_for_service_identity(
                args.service_ip,
                args.service_port,
                args.event_id,
                args.backup_instance_id,
                timeout_ms=args.pre_event_convergence_timeout_ms,
                consecutive_successes=(
                    args.pre_event_convergence_successes
                ),
                request_timeout_ms=args.verification_timeout_ms,
                interval_us=args.probe_interval_us,
            )
            native_cluster_probe = run_pod_probe_convergence(
                args,
                args.service_ip,
                args.service_port,
                args.backup_instance_id,
            )
            native_nodeport_probe = run_pod_probe_convergence(
                args, args.node_ip, args.node_port, args.backup_instance_id
            )
            native_path_convergence = {
                "cluster_ip": native_cluster_probe,
                "host": native_host_convergence,
                "node_port": native_nodeport_probe,
                "valid": True,
            }
            write_json(
                evidence / "native-path-convergence.json",
                native_path_convergence,
            )
            if steps is not None:
                steps.wait("CAPTURED", ["calculate"],
                           details={"event_id": args.event_id})

            detected = read_agent_event(agent_log, "FAILOVER_DETECTED")
            fenced = read_agent_event(agent_log, "ACTIVE_FENCED")
            exited = read_agent_exit_state(agent_log)
            switched = read_agent_event(agent_log, "RULE_SWITCH_RETURNED")
            first_failure = first_post_injection_failure(
                recovered, injected_ns
            )
            injection_to_recovery_us = (
                recovered["recovered_raw_ns"] - injected_ns
            ) / 1000
            service_outage_us = (
                recovered["recovered_raw_ns"]
                - first_failure["observed_raw_ns"]
            ) / 1000
            summary = {
                "active_baseline_successes": probe_ready["active_successes"],
                "detection_source": detected["detection_source"],
                "detection_us": (
                    detected["detected_raw_ns"] - injected_ns
                )
                / 1000,
                "endpoint_convergence_us": (
                    convergence_returned_ns - convergence_started_ns
                )
                / 1000,
                "event_id": args.event_id,
                "fault_mode": args.fault_mode,
                # Compatibility field for historical evidence. New KPI
                # decisions use service_outage_us below.
                "fast_path_latency_us": injection_to_recovery_us,
                "health_confirm_timeout_ms": args.health_confirm_timeout_ms,
                "health_final_timeout_ms": args.health_final_timeout_ms,
                "fence_execution_confirmed": fenced[
                    "fence_execution_confirmed"
                ],
                "fence_result": fenced["fence_result"],
                "fast_path_baseline_convergence_valid": (
                    fast_path_baseline_convergence["valid"]
                ),
                "kube_rules_unchanged_during_fast_switch": True,
                "native_cluster_probe": native_cluster_probe,
                "native_handoff_valid": True,
                "native_nodeport_probe": native_nodeport_probe,
                "pod_probe_failures": recovered["failures"],
                "post_injection_probe_failures": sum(
                    observation["observed_raw_ns"] >= injected_ns
                    for observation in recovered["failure_observations"]
                ),
                "pod_probe_max_gap_us": recovered["max_probe_gap_us"],
                "pod_probe_gap_target_us": args.max_probe_gap_us,
                "pod_probe_cadence_within_target": (
                    recovered["max_probe_gap_us"] <= args.max_probe_gap_us
                ),
                "pre_event_convergence_valid": pre_event_convergence[
                    "valid"
                ],
                "scoped_conntrack_reset_valid": (
                    conntrack_before_fault["valid"]
                    and conntrack_after_fast_path["valid"]
                ),
                "post_detection_recovery_us": (
                    recovered["recovered_raw_ns"]
                    - detected["detected_raw_ns"]
                )
                / 1000,
                "post_fence_recovery_us": (
                    recovered["recovered_raw_ns"]
                    - fenced["fence_returned_raw_ns"]
                )
                / 1000,
                "process_exit_confirmed_post_switch": (
                    exited["event"] == "ACTIVE_EXIT_CONFIRMED"
                ),
                "process_exit_cleanup_error": exited.get("cleanup_error"),
                "process_exit_state": exited["event"],
                "rule_switch_duration_us": switched["switch_duration_us"],
                "scheduling_mode": "none",
                "service_failure_observation_duration_us": (
                    first_failure["observed_raw_ns"]
                    - first_failure["started_raw_ns"]
                )
                / 1000,
                "injected_raw_ns": injected_ns,
                "recovered_raw_ns": recovered["recovered_raw_ns"],
                "service_failure_observed_raw_ns": first_failure[
                    "observed_raw_ns"
                ],
                "service_failure_started_raw_ns": first_failure[
                    "started_raw_ns"
                ],
                "service_outage_us": service_outage_us,
                "target_us": 30000,
                "injection_to_recovery_under_30ms": (
                    injection_to_recovery_us <= 30000
                ),
                "injection_to_recovery_us": injection_to_recovery_us,
                "under_30ms": service_outage_us <= 30000,
                "valid": application_recovery_valid(
                    args, recovered, fenced, detected
                ),
            }
            summary["integration_gate"] = (
                "pass"
                if summary["valid"] and summary["under_30ms"]
                else "fail"
            )
            write_json(evidence / "summary.json", summary)
            if steps is not None:
                steps.wait("CALCULATED", ["reset"], details={
                    "event_id": args.event_id,
                    "valid": summary["valid"],
                    "service_outage_us": summary["service_outage_us"],
                    "under_30ms": summary["under_30ms"],
                })
                # The next event's CREATED (or the outer worker's DONE) must
                # acknowledge reset only after shell cleanup and sealing.
            print(json.dumps(summary, sort_keys=True))
            return result_exit_code(summary, args.accept_kpi_failure)
        except Exception as error:
            writer.write(
                "CONTROLLER_FAILED", event_id=args.event_id, error=str(error)
            )
            write_json(
                evidence / "failure.json",
                {"error": str(error), "event_id": args.event_id},
            )
            raise
        finally:
            if arm_write_fd is not None:
                os.close(arm_write_fd)
            if pod_probe and pod_probe.poll() is None:
                pod_probe.terminate()
                try:
                    pod_probe.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pod_probe.kill()
                    pod_probe.wait(timeout=2)
            if pod_probe is not None:
                salvage_failed_probe_logs(pod_probe, probe_records, evidence)
            if agent and agent.poll() is None:
                agent.terminate()
                try:
                    agent.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    agent.kill()
                    agent.wait(timeout=2)
            if agent_log_buffer is not None:
                try:
                    if not agent_log_buffer.persist_attempted:
                        salvage_failed_agent_logs(
                            agent, agent_log_buffer, evidence
                        )
                finally:
                    agent_log_buffer.close()
            if chain_active:
                chain.cleanup()


if __name__ == "__main__":
    sys.exit(main())
