import subprocess
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_controller import (
    application_recovery_valid,
    clear_service_conntrack,
    endpoint_slice_manifest,
    first_post_injection_failure,
    health_confirmation_summary,
    pod_probe_command,
    read_agent_exit_state,
    result_exit_code,
    service_backends,
    wait_for_recovery,
    wait_for_service_identity,
)


class ServiceControllerTest(unittest.TestCase):
    def test_official_outage_starts_at_first_post_injection_failure(self):
        recovered = {
            "failure_observations": [
                {
                    "started_raw_ns": 800,
                    "observed_raw_ns": 900,
                },
                {
                    "started_raw_ns": 1050,
                    "observed_raw_ns": 1200,
                },
                {
                    "started_raw_ns": 1250,
                    "observed_raw_ns": 1300,
                },
            ],
            "recovered_raw_ns": 2000,
        }
        self.assertEqual(
            first_post_injection_failure(recovered, 1000)["observed_raw_ns"],
            1200,
        )

    def test_official_outage_requires_post_injection_failure(self):
        recovered = {
            "failure_observations": [
                {
                    "started_raw_ns": 800,
                    "observed_raw_ns": 900,
                }
            ],
            "recovered_raw_ns": 2000,
        }
        with self.assertRaisesRegex(RuntimeError, "no service failure"):
            first_post_injection_failure(recovered, 1000)

    def test_collection_mode_accepts_only_valid_kpi_failure(self):
        kpi_failure = {
            "integration_gate": "fail",
            "under_30ms": False,
            "valid": True,
        }
        invalid = {
            "integration_gate": "fail",
            "under_30ms": False,
            "valid": False,
        }
        self.assertEqual(result_exit_code(kpi_failure), 4)
        self.assertEqual(result_exit_code(kpi_failure, True), 0)
        self.assertEqual(result_exit_code(invalid, True), 4)

    def start_process(self, source):
        return subprocess.Popen(
            [sys.executable, "-u", "-c", source],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def stop_process(self, process):
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=1)

    def test_recovery_wait_starts_at_controller_deadline(self):
        probe = self.start_process(
            'import json; print(json.dumps({"event":"RECOVERED",'
            '"instance_id":"backup"}), flush=True)'
        )
        agent = self.start_process("import time; time.sleep(1)")
        try:
            records = []
            recovered = wait_for_recovery(probe, agent, 0.2, records)
            self.assertEqual(recovered["instance_id"], "backup")
            self.assertEqual(records, [recovered])
        finally:
            self.stop_process(probe)
            self.stop_process(agent)

    def test_recovery_wait_reports_agent_fatal_immediately(self):
        probe = self.start_process("import time; time.sleep(1)")
        agent = self.start_process(
            'import json; print(json.dumps({"event":"AGENT_FATAL",'
            '"error":"switch failed"}), flush=True)'
        )
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(RuntimeError, "switch failed"):
                wait_for_recovery(probe, agent, 0.5, [])
            self.assertLess(time.monotonic() - started, 0.2)
        finally:
            self.stop_process(probe)
            self.stop_process(agent)

    def test_conntrack_reset_is_scoped_to_test_service_tuples(self):
        commands = []

        def runner(command, **_kwargs):
            commands.append(command)
            if command[1] == "-D":
                return SimpleNamespace(
                    returncode=0,
                    stderr="conntrack: 2 flow entries have been deleted.\n",
                    stdout="",
                )
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        args = SimpleNamespace(
            node_ip="10.2.58.155",
            node_port=30082,
            service_ip="10.111.255.250",
            service_port=18080,
        )
        result = clear_service_conntrack(args, runner=runner)
        self.assertTrue(result["valid"])
        self.assertEqual(
            [flow["deleted_entries"] for flow in result["flows"]], [2, 2]
        )
        self.assertEqual(
            commands,
            [
                [
                    "conntrack",
                    "-D",
                    "-p",
                    "tcp",
                    "-d",
                    "10.111.255.250",
                    "--dport",
                    "18080",
                ],
                [
                    "conntrack",
                    "-L",
                    "-p",
                    "tcp",
                    "-d",
                    "10.111.255.250",
                    "--dport",
                    "18080",
                ],
                [
                    "conntrack",
                    "-D",
                    "-p",
                    "tcp",
                    "-d",
                    "10.2.58.155",
                    "--dport",
                    "30082",
                ],
                [
                    "conntrack",
                    "-L",
                    "-p",
                    "tcp",
                    "-d",
                    "10.2.58.155",
                    "--dport",
                    "30082",
                ],
            ],
        )

    def test_health_confirmation_summary_exposes_final_stage_tail(self):
        records = [
            {
                "event": "HEALTH_SUSPICION_CLEARED",
                "confirmation_duration_us": 4000,
                "confirmation_stage": "primary",
            },
            {
                "event": "HEALTH_SUSPICION_CLEARED",
                "confirmation_duration_us": 13000,
                "confirmation_stage": "final",
            },
        ]
        self.assertEqual(
            health_confirmation_summary(records),
            {
                "health_confirmation_cleared": 2,
                "health_confirmation_final_stage_cleared": 1,
                "health_confirmation_max_us": 13000,
            },
        )

    def test_application_recovery_gate_does_not_require_process_exit(self):
        args = SimpleNamespace(
            backup_instance_id="backup",
            event_id="failover-1",
            fault_mode="hang",
            max_probe_gap_us=5000,
        )
        recovered = {
            "instance_id": "backup",
            "max_probe_gap_us": 3000,
        }
        fenced = {"fence_execution_confirmed": True}
        detected = {"detection_source": "active_health_confirmed"}
        self.assertTrue(
            application_recovery_valid(args, recovered, fenced, detected)
        )

    def test_probe_gap_is_conservative_diagnostic_not_validity_failure(self):
        args = SimpleNamespace(
            backup_instance_id="backup",
            event_id="failover-1",
            fault_mode="hang",
            max_probe_gap_us=5000,
        )
        recovered = {
            "instance_id": "backup",
            "max_probe_gap_us": 5409,
        }
        fenced = {"fence_execution_confirmed": True}
        detected = {"detection_source": "active_health_confirmed"}
        self.assertTrue(
            application_recovery_valid(args, recovered, fenced, detected)
        )

    def test_post_switch_process_exit_pending_is_a_valid_terminal_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "agent.jsonl"
            path.write_text(
                '{"event":"ACTIVE_EXIT_PENDING","execution_fence_retained":true}\n',
                encoding="utf-8",
            )
            record = read_agent_exit_state(path)
            self.assertEqual(record["event"], "ACTIVE_EXIT_PENDING")
            self.assertTrue(record["execution_fence_retained"])

    def test_post_switch_process_exit_confirmed_is_recorded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "agent.jsonl"
            path.write_text(
                '{"event":"ACTIVE_EXIT_CONFIRMED"}\n', encoding="utf-8"
            )
            self.assertEqual(
                read_agent_exit_state(path)["event"],
                "ACTIVE_EXIT_CONFIRMED",
            )

    def test_one_shot_probe_uses_verification_timeout(self):
        args = SimpleNamespace(
            client_container="client",
            client_pod="probe",
            event_id="verify-1",
            kubeconfig="/tmp/kubeconfig",
            namespace="tc2",
            verification_timeout_ms=10,
        )
        command = pod_probe_command(
            args,
            "10.111.255.250",
            18080,
            once=True,
            expected_instance="active",
        )
        timeout_index = command.index("--request-timeout-ms")
        self.assertEqual(command[timeout_index + 1], "10")

    def test_stable_probe_command_preserves_measurement_parameters(self):
        args = SimpleNamespace(
            baseline_successes=100,
            client_container="client",
            client_pod="probe",
            event_id="soak-1",
            kubeconfig="/tmp/kubeconfig",
            namespace="tc2",
            probe_interval_us=2000,
            request_timeout_ms=2,
            verification_timeout_ms=10,
        )
        command = pod_probe_command(
            args,
            "10.111.255.250",
            18080,
            stable_seconds=60,
        )
        self.assertIn("--stable-active-seconds", command)
        self.assertIn("--baseline-successes", command)
        self.assertIn("--baseline-timeout-ms", command)
        baseline_timeout_index = command.index("--baseline-timeout-ms")
        self.assertEqual(command[baseline_timeout_index + 1], "10")
        self.assertIn("2000", command)

    def test_convergence_probe_preserves_exact_identity_contract(self):
        args = SimpleNamespace(
            client_container="client",
            client_pod="probe",
            event_id="converge-1",
            kubeconfig="/tmp/kubeconfig",
            namespace="tc2",
            pre_event_convergence_successes=20,
            pre_event_convergence_timeout_ms=5000,
            probe_interval_us=2000,
            verification_timeout_ms=10,
        )
        command = pod_probe_command(
            args,
            "10.111.255.250",
            18080,
            wait_active=True,
            expected_instance="backup",
        )
        self.assertIn("--wait-active", command)
        self.assertEqual(
            command[command.index("--expected-instance") + 1], "backup"
        )
        self.assertEqual(
            command[command.index("--convergence-successes") + 1], "20"
        )

    @patch("service_controller.service_response")
    def test_host_convergence_resets_after_stale_backend(self, response):
        response.side_effect = [
            RuntimeError("stale"),
            {},
            {},
            {},
        ]
        result = wait_for_service_identity(
            "10.111.255.250",
            18080,
            "converge-1",
            "backup",
            timeout_ms=100,
            consecutive_successes=3,
            interval_us=0,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["attempts"], 4)
        self.assertEqual(result["mismatches"], 1)

    def test_endpoint_slice_binds_exact_pod_identity(self):
        args = SimpleNamespace(
            backend_port=8080,
            endpoint_slice="tc2-service-manual",
            namespace="tango2-tc2-service",
            node_name="mic711-rt",
            service="tc2-service",
            service_port_name="http",
        )
        target = SimpleNamespace(
            pod_ip="172.20.1.2",
            pod_name="tc2-service-active",
            pod_uid="pod-uid-1",
        )
        manifest = endpoint_slice_manifest(args, target)
        endpoint = manifest["endpoints"][0]
        self.assertEqual(endpoint["addresses"], ["172.20.1.2"])
        self.assertEqual(endpoint["targetRef"]["uid"], "pod-uid-1")
        self.assertEqual(
            manifest["metadata"]["labels"]["kubernetes.io/service-name"],
            "tc2-service",
        )

    def test_service_backend_parser_traverses_owned_kube_chains(self):
        rules = "\n".join(
            [
                '-A KUBE-SERVICES -d 10.111.255.250/32 -p tcp '
                '-m comment --comment "tango2-tc2-service/'
                'tc2-service:http cluster IP" -j KUBE-SVC-AAAA',
                '-A KUBE-SVC-AAAA -m comment --comment "endpoint" '
                '-j KUBE-SEP-BBBB',
                '-A KUBE-SEP-BBBB -p tcp -j DNAT '
                '--to-destination 172.20.1.3:8080',
            ]
        )
        self.assertEqual(
            service_backends(
                rules,
                "tango2-tc2-service",
                "tc2-service",
                "http",
            ),
            {("172.20.1.3", 8080)},
        )


if __name__ == "__main__":
    unittest.main()
