import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepared_restore import PreparedRestore


PAYLOAD = (
    "*nat\n"
    "-F TANGO2-TC2-SVC\n"
    "-A TANGO2-TC2-SVC -p tcp -j DNAT --to-destination 172.20.1.3:8080\n"
    "COMMIT\n"
)

# This fixture models the restore parser's pipe protocol, not kernel nftables.
# The separate AGX network-namespace oracle owns the actual no-COMMIT guarantee.
RESTORE_FIXTURE = r'''
import json
import os
import re
import signal
import sys
from pathlib import Path

state_path, mode = Path(sys.argv[1]), sys.argv[2]
if sys.argv[-1] == "--version":
    backend = "legacy" if mode == "legacy" else "nf_tables"
    print("iptables-restore v1.8.10 (" + backend + ")")
    sys.exit(0)

state = json.loads(state_path.read_text())
state["pid"] = os.getpid()
state["starts"] += 1

def save():
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.replace(state_path)

save()
if mode == "startup_error":
    print("restore startup failed", file=sys.stderr, flush=True)
    sys.exit(17)

buffered = []
for line in sys.stdin:
    if line == "COMMIT\n":
        if not state["prepared"]:
            print("unprepared COMMIT", file=sys.stderr, flush=True)
            sys.exit(18)
        state["owned_target"] = "172.20.1.3:8080"
        state["commits"] += 1
        if "--noflush" not in sys.argv:
            state["unrelated_rules"] = []
        save()
        if mode == "commit_error":
            print("failure after transaction submission", file=sys.stderr, flush=True)
            sys.exit(17)
        if mode == "commit_hang":
            while True:
                signal.pause()
        sys.exit(0)
    if re.fullmatch(r"#TC2_PREPARED_[0-9a-f]{32}\n", line):
        if buffered != [
            "*nat\n",
            "-F TANGO2-TC2-SVC\n",
            "-A TANGO2-TC2-SVC -p tcp -j DNAT --to-destination 172.20.1.3:8080\n",
        ]:
            print("invalid restore input", file=sys.stderr, flush=True)
            sys.exit(19)
        state["prepared"] = True
        save()
        if mode == "overflow":
            sys.stderr.write("x" * 65537 + "\n")
            sys.stderr.flush()
        elif mode == "lookalike_marker":
            print("echo: " + line.rstrip(), flush=True)
        elif mode != "silent" and "--verbose" in sys.argv:
            print(line, end="", flush=True)
    else:
        buffered.append(line)
state["eof_without_commit"] = True
save()
if mode == "interrupt_abort":
    os.kill(os.getppid(), signal.SIGUSR1)
    while True:
        signal.pause()
'''


class PreparedRestoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.fixture = self.directory / "restore_fixture.py"
        self.fixture.write_text(RESTORE_FIXTURE)
        self.next_state = 0

    def restore(self, mode="normal", payload=PAYLOAD, timeout=1.0):
        self.next_state += 1
        state_path = self.directory / f"state-{self.next_state}.json"
        state_path.write_text(json.dumps({
            "owned_target": "172.20.1.2:8080",
            "unrelated_rules": ["KUBE-sentinel", "cali-sentinel"],
            "starts": 0,
            "commits": 0,
            "prepared": False,
        }))
        command = (sys.executable, str(self.fixture), str(state_path), mode)
        restore = PreparedRestore(payload, command=command, timeout=timeout)
        self.addCleanup(self.reap_fixture, state_path)
        self.addCleanup(restore.close)
        return restore, state_path

    @staticmethod
    def state(path):
        return json.loads(path.read_text())

    @staticmethod
    def reap_fixture(path):
        # A failing lifecycle assertion must not leave its real fixture alive.
        pid = json.loads(path.read_text()).get("pid")
        if pid is None:
            return
        try:
            child, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if child == 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)

    def assert_reaped(self, path):
        pid = self.state(path)["pid"]
        with self.assertRaises(ChildProcessError, msg="restore child was not reaped"):
            os.waitpid(pid, os.WNOHANG)

    def assert_unchanged(self, path):
        state = self.state(path)
        self.assertEqual(state["owned_target"], "172.20.1.2:8080")
        self.assertEqual(state["commits"], 0)
        self.assertEqual(state["unrelated_rules"], ["KUBE-sentinel", "cali-sentinel"])

    def test_preparation_is_inert_and_commit_changes_only_owned_target_once(self):
        restore, state_path = self.restore()
        with restore:
            self.assertEqual(restore.pid, self.state(state_path)["pid"])
            self.assertIn("(nf_tables)", restore.version)
            restore.check_alive()
            self.assertTrue(self.state(state_path)["prepared"])
            self.assert_unchanged(state_path)

            restore.commit()
            state = self.state(state_path)
            self.assertEqual(state["owned_target"], "172.20.1.3:8080")
            self.assertEqual(state["unrelated_rules"], ["KUBE-sentinel", "cali-sentinel"])
            self.assertEqual(state["commits"], 1)
            self.assert_reaped(state_path)
            with self.assertRaises(RuntimeError):
                restore.commit()
            self.assertEqual(self.state(state_path)["commits"], 1)
            self.assertEqual(self.state(state_path)["starts"], 1)

    def test_context_abort_closes_input_without_committing_and_reaps_child(self):
        restore, state_path = self.restore()
        with self.assertRaisesRegex(RuntimeError, "controller aborted"):
            with restore:
                raise RuntimeError("controller aborted")
        self.assert_unchanged(state_path)
        self.assertTrue(self.state(state_path)["eof_without_commit"])
        self.assert_reaped(state_path)
        restore.close()
        with self.assertRaises(RuntimeError):
            restore.check_alive()
        with self.assertRaises(RuntimeError):
            restore.commit()

    def test_non_nft_backend_and_embedded_commit_are_rejected_before_launch(self):
        restore, state_path = self.restore("legacy")
        with self.assertRaises(RuntimeError):
            restore.__enter__()
        self.assertEqual(self.state(state_path)["starts"], 0)
        self.assert_unchanged(state_path)

        # Merely removing the final COMMIT would apply this batch too early.
        with self.assertRaises(ValueError):
            self.restore(payload=PAYLOAD + PAYLOAD)

    def test_signal_during_normal_close_propagates_after_reaping_child(self):
        restore, state_path = self.restore("interrupt_abort")

        def terminate(signum, _frame):
            raise SystemExit(128 + signum)

        previous_handler = signal.signal(signal.SIGUSR1, terminate)
        try:
            with self.assertRaises(SystemExit) as raised:
                with restore:
                    self.assert_unchanged(state_path)
            self.assertEqual(raised.exception.code, 128 + signal.SIGUSR1)
            self.assertTrue(self.state(state_path)["eof_without_commit"])
            self.assert_unchanged(state_path)
            self.assert_reaped(state_path)
        finally:
            signal.signal(signal.SIGUSR1, previous_handler)

    def test_parser_or_startup_failure_aborts_without_modifying_rules(self):
        for mode, payload in (
            ("startup_error", PAYLOAD),
            ("normal", PAYLOAD.replace("-F TANGO2-TC2-SVC", "INVALID")),
        ):
            with self.subTest(mode=mode):
                restore, state_path = self.restore(mode, payload)
                with self.assertRaises(RuntimeError):
                    restore.__enter__()
                self.assert_unchanged(state_path)
                self.assert_reaped(state_path)

    def test_missing_or_inexact_marker_times_out_and_aborts(self):
        for mode in ("silent", "lookalike_marker"):
            with self.subTest(mode=mode):
                restore, state_path = self.restore(mode, timeout=0.25)
                with self.assertRaises(TimeoutError):
                    restore.__enter__()
                self.assert_unchanged(state_path)
                self.assert_reaped(state_path)

    def test_excessive_parser_output_fails_and_reaps_child(self):
        restore, state_path = self.restore("overflow")
        with self.assertRaisesRegex(RuntimeError, "output"):
            restore.__enter__()
        self.assert_unchanged(state_path)
        self.assert_reaped(state_path)

    def test_commit_failure_or_timeout_is_terminal_even_if_already_applied(self):
        for mode, error in (
            ("commit_error", subprocess.CalledProcessError),
            ("commit_hang", TimeoutError),
        ):
            with self.subTest(mode=mode):
                restore, state_path = self.restore(mode, timeout=0.25)
                with restore:
                    with self.assertRaises(error):
                        restore.commit()
                    self.assert_reaped(state_path)
                    with self.assertRaises(RuntimeError):
                        restore.commit()
                state = self.state(state_path)
                self.assertEqual(state["owned_target"], "172.20.1.3:8080")
                self.assertEqual(state["commits"], 1)
                self.assertEqual(state["starts"], 1)
                self.assertEqual(state["unrelated_rules"], ["KUBE-sentinel", "cali-sentinel"])


if __name__ == "__main__":
    unittest.main()
