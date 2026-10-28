import itertools
import json
import os
import signal
import unittest
from contextlib import ExitStack, contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_agent import (
    announce,
    cgroup_is_frozen,
    container_task_group_is_stopped,
    resolve_container_cgroup,
    wait_for_ready_convergence,
    wait_for_pidfd_exit,
    main as agent_main,
)


class FakePoller:
    def __init__(self, result):
        self.result = result
        self.timeouts = []

    def register(self, fd, events):
        pass

    def poll(self, timeout_ms):
        self.timeouts.append(timeout_ms)
        return self.result


class FakeWriter:
    def write(self, event, **fields):
        return {"event": event, **fields}


class ServiceAgentTest(unittest.TestCase):
    def test_readiness_convergence_tolerates_transport_jitter(self):
        responses = [
            TimeoutError("timed out"),
            (
                200,
                {
                    "event_id": "e1",
                    "instance_id": "active",
                    "boot_id": "boot-1",
                },
            ),
            (
                200,
                {
                    "event_id": "e1",
                    "instance_id": "active",
                    "boot_id": "boot-1",
                },
            ),
        ]

        def request(*args, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        result = wait_for_ready_convergence(
            "127.0.0.1",
            8080,
            "e1",
            "active",
            consecutive_successes=2,
            request_timeout_ms=10,
            convergence_timeout_ms=100,
            interval_us=0,
            request=request,
        )
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["transport_failures"], 1)
        self.assertEqual(result["consecutive_successes"], 2)

    def test_readiness_convergence_rejects_identity_mismatch(self):
        def request(*args, **kwargs):
            return (
                200,
                {
                    "event_id": "e1",
                    "instance_id": "wrong",
                    "boot_id": "boot-1",
                },
            )

        with self.assertRaisesRegex(RuntimeError, "readiness mismatch"):
            wait_for_ready_convergence(
                "127.0.0.1",
                8080,
                "e1",
                "active",
                consecutive_successes=2,
                request_timeout_ms=10,
                convergence_timeout_ms=100,
                interval_us=0,
                request=request,
            )

    def test_stdout_is_reserved_for_controller_handshake(self):
        output = StringIO()
        with redirect_stdout(output):
            announce(FakeWriter(), "ACTIVE_HEALTH_FAILURE", event_id="e1")
            announce(FakeWriter(), "READY", event_id="e1")
            announce(FakeWriter(), "HEALTH_SUSPICION_CLEARED", event_id="e1")
            announce(FakeWriter(), "WATCHING", event_id="e1")
        records = [
            json.loads(line) for line in output.getvalue().splitlines()
        ]
        self.assertEqual(
            [record["event"] for record in records], ["READY", "WATCHING"]
        )

    def test_fencing_requires_observed_pidfd_exit(self):
        poller = FakePoller([])
        self.assertFalse(wait_for_pidfd_exit(poller, 10))
        self.assertEqual(poller.timeouts, [10])

    def test_fencing_accepts_pidfd_exit_event(self):
        poller = FakePoller([(7, 1)])
        self.assertTrue(wait_for_pidfd_exit(poller, 10))
        self.assertEqual(poller.timeouts, [10])

    def test_negative_fence_timeout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            wait_for_pidfd_exit(FakePoller([]), -1)

    def test_resolves_exact_container_cgroup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            container_id = "a" * 64
            cgroup = root / f"cri-containerd-{container_id}.scope"
            cgroup.mkdir()
            for control in (
                "cgroup.events",
                "cgroup.freeze",
                "cgroup.kill",
                "cgroup.threads",
            ):
                (cgroup / control).touch()
            proc = root / "proc-cgroup"
            proc.write_text(f"0::/{cgroup.name}\n", encoding="utf-8")

            original_read_text = Path.read_text

            def read_text(path, *args, **kwargs):
                if str(path).startswith("/proc/"):
                    return original_read_text(proc, *args, **kwargs)
                return original_read_text(path, *args, **kwargs)

            from unittest.mock import patch

            with patch.object(Path, "read_text", read_text):
                self.assertEqual(
                    resolve_container_cgroup(123, container_id, root),
                    cgroup.resolve(),
                )

    def test_reads_frozen_state_from_cgroup_events(self):
        with TemporaryDirectory() as directory:
            cgroup = Path(directory)
            (cgroup / "cgroup.events").write_text(
                "populated 1\nfrozen 1\n", encoding="utf-8"
            )
            self.assertTrue(cgroup_is_frozen(cgroup))

    def test_stopped_fence_requires_every_exact_cgroup_thread(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cgroup = root / "cgroup"
            task_root = root / "proc" / "100" / "task"
            cgroup.mkdir()
            task_root.mkdir(parents=True)
            (cgroup / "cgroup.threads").write_text(
                "100\n101\n", encoding="ascii"
            )
            for task_id in (100, 101):
                task = task_root / str(task_id)
                task.mkdir()
                (task / "status").write_text(
                    f"Name:\tserver\nState:\tT (stopped)\nTgid:\t100\n",
                    encoding="utf-8",
                )
            self.assertTrue(
                container_task_group_is_stopped(
                    100, cgroup, proc_root=root / "proc"
                )
            )

            (task_root / "101" / "status").write_text(
                "Name:\tserver\nState:\tS (sleeping)\nTgid:\t100\n",
                encoding="utf-8",
            )
            self.assertFalse(
                container_task_group_is_stopped(
                    100, cgroup, proc_root=root / "proc"
                )
            )
            (task_root / "101" / "status").write_text(
                "Name:\tserver\nState:\tT (stopped)\nTgid:\t100\n",
                encoding="utf-8",
            )
            (cgroup / "cgroup.threads").write_text("100\n", encoding="ascii")
            self.assertFalse(
                container_task_group_is_stopped(
                    100, cgroup, proc_root=root / "proc"
                )
            )


class PreparedAgentFlowTest(unittest.TestCase):
    @contextmanager
    def agent(self, timeout_ms=1000, stopped=True, arm_action=None):
        """Run the real state machine with isolated process/HTTP boundaries."""
        with ExitStack() as stack:
            memory = stack.enter_context(TemporaryFile())
            arm_read, arm_write = os.pipe()
            os.write(arm_write, b"1")
            os.close(arm_write)
            pidfd = os.open(os.devnull, os.O_RDONLY)

            def close_if_open(fd):
                try:
                    os.close(fd)
                except OSError:
                    pass

            stack.callback(close_if_open, arm_read)
            stack.callback(close_if_open, pidfd)
            flow = []

            def records():
                memory.seek(0)
                return [json.loads(line) for line in memory.read().splitlines()]

            class Prepared:
                pid = 789
                version = "iptables-restore v1.8.10 (nf_tables)"

                def __enter__(self):
                    flow.append("prepare")
                    return self

                def __exit__(self, *exc):
                    flow.append("close")

                def check_alive(self):
                    flow.append("check_alive")

                def commit(self):
                    self.fence_at_commit = records()[-1]
                    flow.append("commit")

            prepared = Prepared()
            chain = stack.enter_context(patch("service_agent.ServiceFailoverChain")).return_value
            chain.prepare_target.return_value = prepared
            chain.apply_target.side_effect = AssertionError("restore must be prepared before fault handling")
            argv = ["service_agent.py", "--event-id", "e1", "--container-id", "c1",
                    "--pid", "123", "--start-ticks", "456", "--active-ip", "10.0.0.1",
                    "--backup-ip", "10.0.0.2", "--arm-fd", str(arm_read),
                    "--timeout-ms", str(timeout_ms), "--log", "/unused/agent.jsonl",
                    "--log-fd", str(memory.fileno())]
            stack.enter_context(patch.object(sys, "argv", argv))
            for target, value in (
                ("os.geteuid", 0), ("os.pidfd_open", pidfd),
                ("require_unmodified_scheduling", {}), ("process_matches", True),
                ("resolve_container_cgroup", Path("/fake")),
                ("wait_for_ready_convergence", {}),
                ("container_task_group_is_stopped", stopped),
            ):
                stack.enter_context(patch("service_agent." + target, return_value=value, create=True))
            stack.enter_context(patch("service_agent.signal.pidfd_send_signal", create=True))
            stack.enter_context(patch("service_agent.select.poll", return_value=FakePoller([])))
            stack.enter_context(patch("service_agent.monotonic_raw_ns", side_effect=itertools.count(0, 1000)))
            stack.enter_context(patch("service_agent.http_json_request", side_effect=TimeoutError("stopped")))
            stack.enter_context(patch("service_agent.freeze_cgroup", side_effect=RuntimeError("fence failed")))
            stack.enter_context(patch("service_agent.kill_cgroup"))
            if arm_action:
                stack.enter_context(patch("service_agent.wait_for_arm", side_effect=arm_action))
            stack.enter_context(redirect_stdout(StringIO()))
            yield flow, prepared, records, pidfd

    def assert_closed(self, pidfd):
        with self.assertRaises(OSError):
            os.fstat(pidfd)

    def test_prepared_restore_commits_only_after_confirmed_fence(self):
        with self.agent() as (flow, prepared, records, pidfd):
            self.assertEqual(agent_main(), 0)
            self.assertEqual(flow, ["prepare", "check_alive", "commit", "close"])
            self.assertEqual(prepared.fence_at_commit["event"], "ACTIVE_FENCED")
            self.assertTrue(prepared.fence_at_commit["fence_execution_confirmed"])
            ready = records()[0]
            self.assertEqual(ready["event"], "READY")
            self.assertEqual(ready["prepared_restore_pid"], prepared.pid)
            self.assertEqual(ready["prepared_restore_version"], prepared.version)
            self.assert_closed(pidfd)

    def test_failed_fence_aborts_prepared_restore_without_commit(self):
        with self.agent(stopped=False) as (flow, prepared, records, pidfd):
            with self.assertRaisesRegex(RuntimeError, "fence failed"):
                agent_main()
            self.assertNotIn("commit", flow)
            self.assertEqual(flow[-1], "close")
            self.assertEqual(records()[-1]["event"], "ACTIVE_FENCE_FAILED")
            self.assert_closed(pidfd)

    def test_no_fault_timeout_aborts_prepared_restore_without_commit(self):
        with self.agent(timeout_ms=0) as (flow, prepared, records, pidfd):
            self.assertEqual(agent_main(), 2)
            self.assertNotIn("commit", flow)
            self.assertEqual(flow[-1], "close")
            self.assertEqual(records()[-1]["event"], "WATCH_TIMEOUT")
            self.assert_closed(pidfd)

    def test_termination_unwinds_prepared_restore_and_restores_handlers(self):
        signals = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
        previous = {sig: signal.getsignal(sig) for sig in signals}

        def terminate(fd):
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler), "agent must handle termination while prepared")
            handler(signal.SIGTERM, None)

        with self.agent(arm_action=terminate) as (flow, prepared, records, pidfd):
            with self.assertRaises(SystemExit) as failure:
                agent_main()
            self.assertEqual(failure.exception.code, 128 + signal.SIGTERM)
            self.assertEqual(flow, ["prepare", "close"])
            self.assert_closed(pidfd)
        self.assertEqual({sig: signal.getsignal(sig) for sig in signals}, previous)


if __name__ == "__main__":
    unittest.main()
