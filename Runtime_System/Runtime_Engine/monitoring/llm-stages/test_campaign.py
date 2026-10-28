import fcntl
import json
import os
import pathlib
import signal
import sys
import tempfile
import unittest

from run_campaign import (create_runs_root, field_control_lock,
                          install_cancellation_handlers, run_runner,
                          runner_command, write_campaign_evidence)


class CampaignCancellationContract(unittest.TestCase):
    def test_cpu_option_preserves_the_empty_case_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/"bin").mkdir()
            runner = root/"bin/runner"
            runner.write_text("#!"+sys.executable+"\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
            runner.chmod(0o755)
            command = runner_command(root, root/"engine", root/"run", "detail", "run",
                                     1, 0, "", "off")
            with (root/"log").open("w") as log:
                code, reason = run_runner(command, dict(os.environ), log, [False])
            received = json.loads((root/"log").read_text())
            self.assertEqual((code, reason), (0, ""))
            self.assertEqual(received[-2:], ["", "off"])
            self.assertEqual(received[3], "detail")

    def test_documented_fresh_root_creates_runs_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = create_runs_root(pathlib.Path(directory)/"fresh")
            self.assertTrue(runs.is_dir())
            run = runs/"new-run"
            run.mkdir()
            with self.assertRaises(FileExistsError):
                run.mkdir()

    def test_existing_field_session_prevents_campaign_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            active = root/"active"
            active.write_text("prepared-tc2")
            with self.assertRaisesRegex(RuntimeError, "official field session"):
                field_control_lock(root/"field.lock", active)

    def test_field_control_lock_rejects_a_concurrent_campaign_or_test_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            lock = field_control_lock(root/"field.lock", root/"active")
            second = (root/"field.lock").open("a+")
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                second.close()
                lock.close()

    def test_timeout_reaps_runner_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory)/"runner.log"
            with log_path.open("w") as log:
                code, reason = run_runner([sys.executable, "-c", "import time; time.sleep(60)"],
                                          dict(os.environ), log, [False], timeout=.01)
        self.assertEqual(reason, "runner_timeout")
        self.assertNotEqual(code, 0)

    def test_sighup_reaps_runner_before_evidence_and_field_lock_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            field_lock = field_control_lock(root/"field.lock", root/"active")
            cancelled = [False]
            previous = install_cancellation_handlers(cancelled)
            runner_pid = root/"runner.pid"
            campaign = root/"campaign"
            campaign.mkdir()
            try:
                program = ("import os, pathlib, signal, time; "
                           f"pathlib.Path({str(runner_pid)!r}).write_text(str(os.getpid())); "
                           "os.kill(os.getppid(), signal.SIGHUP); time.sleep(60)")
                with (root/"runner.log").open("w") as log:
                    code, reason = run_runner([sys.executable, "-c", program], dict(os.environ), log,
                                              cancelled)
                write_campaign_evidence(campaign, [root/"run"],
                                        [dict(run_id="run", exit_code=code, incomplete_reason=reason)],
                                        cancelled)
                self.assertEqual(reason, "campaign_cancelled")
                self.assertNotEqual(code, 0)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(runner_pid.read_text()), 0)
                self.assertTrue(json.loads((campaign/"outcome.json").read_text())["cancelled"])
                contender = (root/"field.lock").open("a+")
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    contender.close()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                field_lock.close()


if __name__ == "__main__":
    unittest.main()
