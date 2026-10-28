import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_probe import (
    run_continuous,
    run_wait_active,
    wait_for_active_baseline,
)


class ServiceProbeTest(unittest.TestCase):
    @patch("service_probe.http_json_request")
    def test_continuous_preserves_failure_observation_times(self, request):
        active = (
            200,
            {
                "boot_id": "active-boot",
                "event_id": "event-0",
                "instance_id": "active",
            },
        )
        backup = (
            200,
            {
                "boot_id": "backup-boot",
                "event_id": "event-0",
                "instance_id": "backup",
            },
        )
        request.side_effect = [active, TimeoutError("down"), active, backup]
        args = SimpleNamespace(
            active_instance_id="active",
            backup_instance_id="backup",
            baseline_successes=1,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-0",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
            request_timeout_ms=2,
        )
        output = StringIO()
        with redirect_stdout(output):
            run_continuous(args, {"policy": "SCHED_OTHER"})
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        recovered = records[-1]
        self.assertEqual(recovered["event"], "RECOVERED")
        self.assertEqual(recovered["failures"], 1)
        self.assertEqual(len(recovered["failure_observations"]), 1)
        failure = recovered["failure_observations"][0]
        self.assertLessEqual(
            failure["started_raw_ns"], failure["observed_raw_ns"]
        )
        self.assertEqual(failure["error"], "down")

    @patch("service_probe.http_json_request")
    def test_continuous_records_non200_response_as_failure(self, request):
        active = (
            200,
            {
                "boot_id": "active-boot",
                "event_id": "event-0",
                "instance_id": "active",
            },
        )
        backup = (
            200,
            {
                "boot_id": "backup-boot",
                "event_id": "event-0",
                "instance_id": "backup",
            },
        )
        request.side_effect = [active, (503, {}), backup]
        args = SimpleNamespace(
            active_instance_id="active",
            backup_instance_id="backup",
            baseline_successes=1,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-0",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
            request_timeout_ms=2,
        )
        output = StringIO()
        with redirect_stdout(output):
            run_continuous(args, {"policy": "SCHED_OTHER"})
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        recovered = records[-1]
        self.assertEqual(recovered["event"], "RECOVERED")
        self.assertEqual(recovered["failures"], 1)
        self.assertEqual(len(recovered["failure_observations"]), 1)
        self.assertIn("status=503", recovered["failure_observations"][0]["error"])

    @patch("service_probe.http_json_request")
    def test_continuous_records_malformed_response_as_failure(self, request):
        active = (
            200,
            {
                "boot_id": "active-boot",
                "event_id": "event-0",
                "instance_id": "active",
            },
        )
        backup = (
            200,
            {
                "boot_id": "backup-boot",
                "event_id": "event-0",
                "instance_id": "backup",
            },
        )
        malformed = (200, {"event_id": "event-0", "instance_id": "backup"})
        request.side_effect = [active, malformed, backup]
        args = SimpleNamespace(
            active_instance_id="active",
            backup_instance_id="backup",
            baseline_successes=1,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-0",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
            request_timeout_ms=2,
        )
        output = StringIO()
        with redirect_stdout(output):
            run_continuous(args, {"policy": "SCHED_OTHER"})
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        recovered = records[-1]
        self.assertEqual(recovered["event"], "RECOVERED")
        self.assertEqual(recovered["failures"], 1)
        self.assertEqual(len(recovered["failure_observations"]), 1)

    @patch("service_probe.http_json_request")
    def test_continuous_fails_closed_on_identity_contamination(self, request):
        active = (
            200,
            {
                "boot_id": "active-boot",
                "event_id": "event-0",
                "instance_id": "active",
            },
        )
        contaminated = (
            200,
            {
                "boot_id": "rogue-boot",
                "event_id": "event-0",
                "instance_id": "rogue",
            },
        )
        request.side_effect = [active, contaminated]
        args = SimpleNamespace(
            active_instance_id="active",
            backup_instance_id="backup",
            baseline_successes=1,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-0",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
            request_timeout_ms=2,
        )
        with self.assertRaisesRegex(RuntimeError, "invalid recovery response"):
            run_continuous(args, {"policy": "SCHED_OTHER"})

    @patch("service_probe.http_json_request")
    def test_continuous_baseline_tolerates_transport_jitter(self, request):
        response = (
            200,
            {
                "boot_id": "boot",
                "event_id": "event-1",
                "instance_id": "active",
                "role": "active",
            },
        )
        request.side_effect = [TimeoutError("timed out"), response, response]
        args = SimpleNamespace(
            active_instance_id="active",
            baseline_successes=2,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-1",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
        )
        result = wait_for_active_baseline(args)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["transport_failures"], 1)
        self.assertEqual(result["consecutive_successes"], 2)

    @patch("service_probe.http_json_request")
    def test_continuous_baseline_rejects_wrong_identity(self, request):
        request.return_value = (
            200,
            {
                "boot_id": "boot",
                "event_id": "event-1",
                "instance_id": "backup",
                "role": "active",
            },
        )
        args = SimpleNamespace(
            active_instance_id="active",
            baseline_successes=2,
            baseline_timeout_ms=10,
            convergence_timeout_ms=100,
            event_id="event-1",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
        )
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            wait_for_active_baseline(args)

    @patch("service_probe.http_json_request")
    def test_wait_active_requires_consecutive_exact_responses(self, request):
        request.side_effect = [
            (
                503,
                {
                    "boot_id": "old",
                    "event_id": "event-2",
                    "instance_id": "active",
                    "role": "standby",
                },
            ),
            (
                200,
                {
                    "boot_id": "new",
                    "event_id": "event-2",
                    "instance_id": "backup",
                    "role": "active",
                },
            ),
            (
                200,
                {
                    "boot_id": "new",
                    "event_id": "event-2",
                    "instance_id": "backup",
                    "role": "active",
                },
            ),
        ]
        args = SimpleNamespace(
            baseline_timeout_ms=10,
            convergence_successes=2,
            convergence_timeout_ms=100,
            event_id="event-2",
            expected_instance="backup",
            host="10.111.255.250",
            port=18080,
            probe_interval_us=0,
        )
        output = StringIO()
        with redirect_stdout(output):
            run_wait_active(args, {"policy": "SCHED_OTHER"})
        record = json.loads(output.getvalue())
        self.assertEqual(record["event"], "CONVERGED")
        self.assertEqual(record["attempts"], 3)
        self.assertEqual(record["mismatches"], 1)
        self.assertEqual(record["consecutive_successes"], 2)


if __name__ == "__main__":
    unittest.main()
