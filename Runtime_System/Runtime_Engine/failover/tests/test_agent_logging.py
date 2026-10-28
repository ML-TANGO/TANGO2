import json
import os
import select
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_agent import main as agent_main
from service_controller import (
    AgentLogBuffer,
    collect_agent_logs,
    collect_agent_logs_after_probe_completion,
    salvage_failed_agent_logs,
    wait_for_recovery,
)


@unittest.skipUnless(hasattr(os, "memfd_create"), "requires Linux memfd")
class AgentLoggingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.evidence = Path(self.directory.name)
        self.buffer = AgentLogBuffer()
        self.addCleanup(self.buffer.close)

    def start_agent(self, event="ACTIVE_FENCED", diagnostic_output=False):
        exit_action = (
            "code = int(input()); print('agent stdout', flush=True); "
            "print('agent stderr', file=sys.stderr, flush=True); sys.exit(code)"
            if diagnostic_output
            else "sys.exit(int(input()))"
        )
        source = (
            "import sys; from common import JsonlWriter; "
            f"writer = JsonlWriter(fd={self.buffer.fd}); "
            f"writer.write({event!r}, event_id='e1'); "
            "writer.close(); print('buffered', flush=True); "
            + exit_action
        )
        agent = subprocess.Popen(
            [sys.executable, "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            pass_fds=(self.buffer.fd,),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_process, agent)
        ready, _, _ = select.select([agent.stdout], [], [], 5)
        self.assertTrue(ready, "agent did not write its memory log")
        self.assertEqual(agent.stdout.readline().strip(), "buffered")
        return agent

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)

    @staticmethod
    def finish_agent(agent, code):
        agent.stdin.write(f"{code}\n")
        agent.stdin.flush()

    def test_agent_can_finish_before_recovery_without_disk_logging(self):
        agent = self.start_agent()
        self.finish_agent(agent, 0)
        agent.wait(timeout=5)
        self.assertEqual(list(self.evidence.iterdir()), [])
        captured = os.pread(self.buffer.fd, 65536, 0)

        probe = subprocess.Popen(
            [sys.executable, "-c", "print('{\"event\":\"RECOVERED\"}', flush=True)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_process, probe)
        recovered = wait_for_recovery(probe, agent, 5, [])
        self.assertEqual(recovered["event"], "RECOVERED")
        self.assertFalse((self.evidence / "agent.jsonl").exists())
        collect_agent_logs(agent, self.buffer, self.evidence)
        self.assertEqual((self.evidence / "agent.jsonl").read_bytes(), captured)

    def test_killed_agent_leaves_diagnostic_log_but_is_rejected(self):
        agent = self.start_agent()
        agent.kill()
        with self.assertRaisesRegex(RuntimeError, "service agent exited"):
            collect_agent_logs(agent, self.buffer, self.evidence)
        record = json.loads((self.evidence / "agent.jsonl").read_text())
        self.assertEqual(record["event"], "ACTIVE_FENCED")

    def test_pre_recovery_abort_salvages_agent_diagnostics(self):
        source = (
            "import sys; from common import JsonlWriter; "
            f"writer = JsonlWriter(fd={self.buffer.fd}); "
            "writer.write('WATCHING', event_id='e1'); writer.close(); "
            "print('{\"event\": \"AGENT_FATAL\"}', flush=True); "
            "print('agent stdout', flush=True); "
            "print('agent stderr', file=sys.stderr, flush=True); sys.exit(1)"
        )
        agent = subprocess.Popen(
            [sys.executable, "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            pass_fds=(self.buffer.fd,),
        )
        self.addCleanup(self.stop_process, agent)
        probe = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_process, probe)

        with self.assertRaisesRegex(RuntimeError, "service agent failed"):
            try:
                wait_for_recovery(probe, agent, 5, [])
            finally:
                salvage_failed_agent_logs(agent, self.buffer, self.evidence)

        self.assertEqual(
            (self.evidence / "agent.stdout.txt").read_text(), "agent stdout\n"
        )
        self.assertEqual(
            (self.evidence / "agent.stderr.txt").read_text(), "agent stderr\n"
        )
        record = json.loads((self.evidence / "agent.jsonl").read_text())
        self.assertEqual(record["event"], "WATCHING")

    def test_no_fault_timeout_log_is_saved_with_expected_exit(self):
        agent = self.start_agent("WATCH_TIMEOUT")
        self.finish_agent(agent, 2)
        collect_agent_logs(agent, self.buffer, self.evidence, expected_exit=2)
        record = json.loads((self.evidence / "agent.jsonl").read_text())
        self.assertEqual(record["event"], "WATCH_TIMEOUT")

    def test_storage_failure_rejects_an_otherwise_successful_agent(self):
        agent = self.start_agent(diagnostic_output=True)
        self.finish_agent(agent, 0)
        with patch("service_controller.os.fsync", side_effect=OSError("storage failed")):
            with self.assertRaisesRegex(OSError, "storage failed"):
                collect_agent_logs(agent, self.buffer, self.evidence)
        self.assertEqual(
            (self.evidence / "agent.stdout.txt").read_text(), "agent stdout\n"
        )
        self.assertEqual(
            (self.evidence / "agent.stderr.txt").read_text(), "agent stderr\n"
        )

    def start_gated_process(self, output, exit_code):
        read_fd, write_fd = os.pipe()
        source = (
            "import os, sys; os.read(int(sys.argv[1]), 1); "
            "print(sys.argv[2], flush=True); sys.exit(int(sys.argv[3]))"
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                source,
                str(read_fd),
                output,
                str(exit_code),
            ],
            pass_fds=(read_fd,),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        os.close(read_fd)
        self.addCleanup(self.stop_process, process)
        self.addCleanup(self.close_fd, write_fd)
        return process, write_fd

    @staticmethod
    def close_fd(fd):
        try:
            os.close(fd)
        except OSError:
            pass

    def collect_after_probe_completion(
        self, completion_event, probe, agent, timeout_seconds, expected_exit
    ):
        persisted = threading.Event()
        persisted_after = []
        persist = self.buffer.persist

        def record_persist(path):
            persisted_after.append((probe.poll(), agent.poll()))
            persisted.set()
            return persist(path)

        self.buffer.persist = record_persist
        result = {}

        def collect():
            try:
                result["completion"] = collect_agent_logs_after_probe_completion(
                    completion_event,
                    probe,
                    agent,
                    self.buffer,
                    self.evidence,
                    timeout_seconds,
                    [],
                    expected_exit,
                )
            except BaseException as error:
                result["error"] = error

        thread = threading.Thread(target=collect)
        thread.start()
        return thread, result, persisted, persisted_after

    def assert_collection_completed(
        self, thread, result, persisted_after, expected_agent_exit
    ):
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "controller collection did not finish")
        if "error" in result:
            raise result["error"]
        self.assertEqual(persisted_after, [(0, expected_agent_exit)])

    def test_fault_collection_waits_for_recovery_and_agent_exit(self):
        agent, agent_gate = self.start_gated_process(
            '{"event":"AGENT_DONE"}', 0
        )
        probe, probe_gate = self.start_gated_process(
            '{"event":"RECOVERED"}', 0
        )
        thread, result, persisted, persisted_after = (
            self.collect_after_probe_completion(
                "RECOVERED", probe, agent, 5, 0
            )
        )

        os.write(agent_gate, b"1")
        self.close_fd(agent_gate)
        agent.wait(timeout=5)
        self.assertFalse(persisted.wait(0.1))
        os.write(probe_gate, b"1")
        self.close_fd(probe_gate)
        probe.wait(timeout=5)

        self.assert_collection_completed(thread, result, persisted_after, 0)
        self.assertEqual(result["completion"]["event"], "RECOVERED")

    def test_soak_collection_waits_for_completion_and_agent_exit(self):
        agent, agent_gate = self.start_gated_process(
            '{"event":"AGENT_DONE"}', 2
        )
        probe, probe_gate = self.start_gated_process(
            '{"event":"SOAK_COMPLETE"}', 0
        )
        thread, result, persisted, persisted_after = (
            self.collect_after_probe_completion(
                "SOAK_COMPLETE", probe, agent, 5, 2
            )
        )

        os.write(probe_gate, b"1")
        self.close_fd(probe_gate)
        probe.wait(timeout=5)
        self.assertFalse(persisted.wait(0.1))
        os.write(agent_gate, b"1")
        self.close_fd(agent_gate)
        agent.wait(timeout=5)

        self.assert_collection_completed(thread, result, persisted_after, 2)
        self.assertEqual(result["completion"]["event"], "SOAK_COMPLETE")

    def test_real_agent_path_logs_only_to_inherited_memory(self):
        arm_read, arm_write = os.pipe()
        os.write(arm_write, b"1")
        os.close(arm_write)
        pidfd = os.open(os.devnull, os.O_RDONLY)
        destination = self.evidence / "agent.jsonl"
        argv = [
            "service_agent.py", "--event-id", "e1", "--container-id", "c1",
            "--pid", "123", "--start-ticks", "456", "--active-ip", "10.0.0.1",
            "--backup-ip", "10.0.0.2", "--arm-fd", str(arm_read),
            "--log", str(destination), "--log-fd", str(self.buffer.fd),
        ]
        with (
            patch.object(sys, "argv", argv),
            patch("service_agent.os.geteuid", return_value=0),
            patch("service_agent.os.pidfd_open", return_value=pidfd),
            patch("service_agent.select.poll") as poll,
            patch("service_agent.require_unmodified_scheduling", return_value={}),
            patch("service_agent.process_matches", return_value=True),
            patch("service_agent.resolve_container_cgroup", return_value=Path("/fake")),
            patch("service_agent.ServiceFailoverChain") as chain,
            patch("service_agent.wait_for_ready_convergence", return_value={}),
            patch("service_agent.http_json_request", side_effect=TimeoutError("stopped")),
            patch("service_agent.container_task_group_is_stopped", return_value=True),
            patch("service_agent.kill_cgroup"),
            redirect_stdout(StringIO()),
        ):
            poll.return_value.poll.return_value = []
            prepared = chain.return_value.prepare_target.return_value.__enter__.return_value
            prepared.pid = 789
            prepared.version = "iptables-restore v1.8.10 (nf_tables)"
            self.assertEqual(agent_main(), 0)
            chain.return_value.prepare_target.assert_called_once_with("10.0.0.2", 8080)
            prepared.commit.assert_called_once_with()
            chain.return_value.apply_target.assert_not_called()
        self.assertFalse(destination.exists())
        records = [json.loads(line) for line in os.pread(self.buffer.fd, 65536, 0).splitlines()]
        self.assertEqual(
            [record["event"] for record in records],
            ["READY", "WATCHING", "ACTIVE_HEALTH_FAILURE",
             "HEALTH_CONFIRMATION_FAILED", "FAILOVER_DETECTED", "ACTIVE_FENCED",
             "RULE_SWITCH_RETURNED", "RULE_SWITCH_VERIFIED", "ACTIVE_EXIT_PENDING"],
        )
        self.buffer.persist(destination)
        self.assertEqual([json.loads(line) for line in destination.read_text().splitlines()], records)


if __name__ == "__main__":
    unittest.main()
