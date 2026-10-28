#!/usr/bin/env python3

import argparse
import json
import sys
import time

from common import monotonic_raw_ns
from scheduling import require_unmodified_scheduling
from service_http import http_json_request


def announce(event, **fields):
    record = {"event": event, "ts_raw_ns": monotonic_raw_ns(), **fields}
    print(json.dumps(record, sort_keys=True), flush=True)
    return record


def valid_response(status, payload, event_id, instance_id):
    return (
        status == 200
        and payload.get("event_id") == event_id
        and payload.get("instance_id") == instance_id
        and bool(payload.get("boot_id"))
    )


def run_once(args, scheduling):
    started_ns = monotonic_raw_ns()
    status, payload = http_json_request(
        args.host,
        args.port,
        args.event_id,
        args.request_timeout_ms,
        path="/service",
    )
    ended_ns = monotonic_raw_ns()
    if not valid_response(
        status, payload, args.event_id, args.expected_instance
    ):
        raise RuntimeError(
            f"unexpected service response status={status} payload={payload}"
        )
    announce(
        "ONCE_OK",
        event_id=args.event_id,
        instance_id=args.expected_instance,
        duration_us=(ended_ns - started_ns) / 1000,
        scheduling=scheduling,
    )


def run_wait_active(args, scheduling):
    started_ns = monotonic_raw_ns()
    deadline_ns = started_ns + args.convergence_timeout_ms * 1_000_000
    consecutive_successes = 0
    attempts = 0
    mismatches = 0
    transport_failures = 0
    last_observation = None

    while monotonic_raw_ns() < deadline_ns:
        attempts += 1
        try:
            status, payload = http_json_request(
                args.host,
                args.port,
                args.event_id,
                args.baseline_timeout_ms,
                path="/service",
            )
            if valid_response(
                status, payload, args.event_id, args.expected_instance
            ):
                consecutive_successes += 1
                if consecutive_successes >= args.convergence_successes:
                    announce(
                        "CONVERGED",
                        attempts=attempts,
                        consecutive_successes=consecutive_successes,
                        duration_us=(monotonic_raw_ns() - started_ns) / 1000,
                        event_id=args.event_id,
                        instance_id=args.expected_instance,
                        mismatches=mismatches,
                        scheduling=scheduling,
                        transport_failures=transport_failures,
                    )
                    return
            else:
                mismatches += 1
                consecutive_successes = 0
                last_observation = {"payload": payload, "status": status}
        except (OSError, TimeoutError) as error:
            transport_failures += 1
            consecutive_successes = 0
            last_observation = {"error": str(error)}
        time.sleep(args.probe_interval_us / 1_000_000)

    raise RuntimeError(
        "service identity did not converge "
        f"attempts={attempts} mismatches={mismatches} "
        f"transport_failures={transport_failures} "
        f"last_observation={last_observation}"
    )


def wait_for_active_baseline(args):
    started_ns = monotonic_raw_ns()
    deadline_ns = started_ns + args.convergence_timeout_ms * 1_000_000
    consecutive_successes = 0
    attempts = 0
    transport_failures = 0
    last_transport_error = None

    while monotonic_raw_ns() < deadline_ns:
        attempts += 1
        try:
            status, payload = http_json_request(
                args.host,
                args.port,
                args.event_id,
                args.baseline_timeout_ms,
                path="/service",
            )
        except (OSError, TimeoutError) as error:
            consecutive_successes = 0
            transport_failures += 1
            last_transport_error = str(error)
        else:
            if not valid_response(
                status, payload, args.event_id, args.active_instance_id
            ):
                raise RuntimeError(
                    f"baseline identity mismatch status={status} "
                    f"payload={payload}"
                )
            consecutive_successes += 1
            if consecutive_successes >= args.baseline_successes:
                return {
                    "attempts": attempts,
                    "consecutive_successes": consecutive_successes,
                    "transport_failures": transport_failures,
                    "duration_us": (monotonic_raw_ns() - started_ns) / 1000,
                }
        time.sleep(args.probe_interval_us / 1_000_000)

    raise RuntimeError(
        "active baseline did not converge "
        f"attempts={attempts} "
        f"consecutive={consecutive_successes}/{args.baseline_successes} "
        f"transport_failures={transport_failures} "
        f"last_error={last_transport_error!r}"
    )


def run_continuous(args, scheduling):
    interval_ns = args.probe_interval_us * 1000
    deadline_ns = monotonic_raw_ns()
    active_successes = 0
    failures = 0
    failure_observations = []
    last_start_ns = None
    max_gap_ns = 0

    baseline = wait_for_active_baseline(args)
    active_successes = baseline["consecutive_successes"]

    announce(
        "READY",
        event_id=args.event_id,
        active_successes=active_successes,
        baseline_attempts=baseline["attempts"],
        baseline_duration_us=baseline["duration_us"],
        baseline_transport_failures=baseline["transport_failures"],
        scheduling=scheduling,
    )
    deadline_ns = monotonic_raw_ns()
    # The controller owns the recovery deadline and starts it at fault
    # injection. The probe only reports observations until recovered or killed.
    while True:
        started_ns = monotonic_raw_ns()
        if last_start_ns is not None:
            max_gap_ns = max(max_gap_ns, started_ns - last_start_ns)
        last_start_ns = started_ns
        try:
            status, payload = http_json_request(
                args.host,
                args.port,
                args.event_id,
                args.request_timeout_ms,
                path="/service",
            )
        except (OSError, TimeoutError, RuntimeError, ValueError) as error:
            observed_ns = monotonic_raw_ns()
            failures += 1
            failure_observations.append(
                {
                    "error": str(error),
                    "observed_raw_ns": observed_ns,
                    "started_raw_ns": started_ns,
                }
            )
        else:
            ended_ns = monotonic_raw_ns()
            if valid_response(
                status, payload, args.event_id, args.backup_instance_id
            ):
                announce(
                    "RECOVERED",
                    event_id=args.event_id,
                    instance_id=args.backup_instance_id,
                    recovered_raw_ns=ended_ns,
                    duration_us=(ended_ns - started_ns) / 1000,
                    failures=failures,
                    failure_observations=failure_observations,
                    max_probe_gap_us=max_gap_ns / 1000,
                    boot_id=payload["boot_id"],
                )
                return
            if valid_response(
                status, payload, args.event_id, args.active_instance_id
            ):
                pass
            elif (
                status == 200
                and payload.get("event_id") == args.event_id
                and bool(payload.get("boot_id"))
                and payload.get("instance_id")
                not in (args.active_instance_id, args.backup_instance_id)
            ):
                raise RuntimeError(
                    f"invalid recovery response status={status} "
                    f"payload={payload}"
                )
            else:
                observed_ns = monotonic_raw_ns()
                failures += 1
                failure_observations.append(
                    {
                        "error": (
                            f"invalid recovery response status={status} "
                            f"payload={payload}"
                        ),
                        "observed_raw_ns": observed_ns,
                        "started_raw_ns": started_ns,
                    }
                )

        deadline_ns += interval_ns
        remaining_ns = deadline_ns - monotonic_raw_ns()
        if remaining_ns > 0:
            time.sleep(remaining_ns / 1_000_000_000)
        else:
            deadline_ns = monotonic_raw_ns()


def run_stable_active(args, scheduling):
    baseline = wait_for_active_baseline(args)
    announce(
        "READY",
        event_id=args.event_id,
        active_successes=baseline["consecutive_successes"],
        baseline_attempts=baseline["attempts"],
        baseline_duration_us=baseline["duration_us"],
        baseline_transport_failures=baseline["transport_failures"],
        scheduling=scheduling,
    )

    interval_ns = args.probe_interval_us * 1000
    deadline_ns = monotonic_raw_ns()
    active_successes = 0
    failures = 0
    consecutive_failures = 0
    max_consecutive_failures = 0
    last_start_ns = None
    max_gap_ns = 0
    soak_deadline_ns = (
        deadline_ns + int(args.stable_active_seconds * 1_000_000_000)
    )
    while monotonic_raw_ns() < soak_deadline_ns:
        started_ns = monotonic_raw_ns()
        if last_start_ns is not None:
            max_gap_ns = max(max_gap_ns, started_ns - last_start_ns)
        last_start_ns = started_ns
        try:
            status, payload = http_json_request(
                args.host,
                args.port,
                args.event_id,
                args.request_timeout_ms,
                path="/service",
            )
            if not valid_response(status, payload, args.event_id, "active"):
                raise RuntimeError(
                    f"stable identity mismatch status={status} payload={payload}"
                )
            active_successes += 1
            consecutive_failures = 0
        except (OSError, TimeoutError):
            failures += 1
            consecutive_failures += 1
            max_consecutive_failures = max(
                max_consecutive_failures, consecutive_failures
            )

        deadline_ns += interval_ns
        remaining_ns = deadline_ns - monotonic_raw_ns()
        if remaining_ns > 0:
            time.sleep(remaining_ns / 1_000_000_000)
        else:
            deadline_ns = monotonic_raw_ns()
    announce(
        "SOAK_COMPLETE",
        event_id=args.event_id,
        active_successes=active_successes,
        failures=failures,
        max_consecutive_failures=max_consecutive_failures,
        max_probe_gap_us=max_gap_ns / 1000,
        scheduling=scheduling,
        stable_active_seconds=args.stable_active_seconds,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--active-instance-id", default="active")
    parser.add_argument("--backup-instance-id", default="backup")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--wait-active", action="store_true")
    parser.add_argument("--expected-instance", choices=("active", "backup"))
    parser.add_argument("--request-timeout-ms", type=int, default=2)
    parser.add_argument("--baseline-timeout-ms", type=int, default=10)
    parser.add_argument("--probe-interval-us", type=int, default=2000)
    parser.add_argument("--baseline-successes", type=int, default=100)
    parser.add_argument("--convergence-timeout-ms", type=int, default=5000)
    parser.add_argument("--convergence-successes", type=int, default=20)
    parser.add_argument("--stable-active-seconds", type=float)
    args = parser.parse_args()

    scheduling = require_unmodified_scheduling(label="service probe")
    if args.convergence_timeout_ms <= 0 or args.convergence_successes <= 0:
        raise SystemExit("invalid convergence probe settings")
    if args.stable_active_seconds is not None:
        if args.once or args.wait_active or args.stable_active_seconds <= 0:
            raise SystemExit("invalid stable-active probe mode")
        run_stable_active(args, scheduling)
    elif args.wait_active:
        if args.once or not args.expected_instance:
            raise SystemExit(
                "--expected-instance is required with --wait-active"
            )
        run_wait_active(args, scheduling)
    elif args.once:
        if not args.expected_instance:
            raise SystemExit("--expected-instance is required with --once")
        run_once(args, scheduling)
    else:
        run_continuous(args, scheduling)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        announce("PROBE_FATAL", error=str(error))
        raise
