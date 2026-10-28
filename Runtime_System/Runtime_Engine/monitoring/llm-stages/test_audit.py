import json
import pathlib
import tempfile
import unittest

from audit import audit, compare
from test_metrics import example
from test_cpu_metrics import cpu_example


class AuditContract(unittest.TestCase):
    def write_run(self, root, run_id, mode="live", count=1, acknowledged=True):
        run = pathlib.Path(root)/run_id
        requests = run/"requests"
        requests.mkdir(parents=True)
        (run/"manifest.json").write_text(json.dumps({"run_id": run_id, "mode": mode,
            "started_utc_ns": 1}))
        for index in range(1, count+1):
            record = example()
            record.update(run_id=run_id, request_id=str(index), mode=mode, block=0,
                          completed_utc_ns=100+index)
            (requests/(str(index)+".json")).write_text(json.dumps(record))
        (run/"completion.json").write_text(json.dumps({"run_id": run_id, "mode": mode,
            "requests": count, "failures": 0, "cancelled": False, "heartbeat_failed": False,
            "blocks": [{"case": "i64_o64", "block": 0, "first_request": 1,
                        "last_request": count, "begin_ns": 1_000_000_000,
                        "end_ns": 2_100_000_100, "tail_processing_ns": 100,
                        "inter_request_gaps_ns": [], "residual_acknowledged": acknowledged}]}))
        return run

    def test_foreign_and_out_of_block_records_are_integrity_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.write_run(directory, "run-a")
            foreign = example()
            foreign.update(run_id="run-b", request_id="2", block=1, completed_utc_ns=102)
            (run/"requests"/"2.json").write_text(json.dumps(foreign))
            summary = audit(run)
            self.assertFalse(summary["complete"])
            self.assertTrue(any("foreign run" in error for error in summary["errors"]))

    def test_missing_residual_acknowledgement_is_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = audit(self.write_run(directory, "run-a", acknowledged=False))
            self.assertFalse(summary["complete"])
            self.assertTrue(any("residual" in error for error in summary["errors"]))

    def test_repeated_comparison_input_cannot_make_samples_sufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = audit(self.write_run(directory, "baseline", "baseline", count=10))
            live = audit(self.write_run(directory, "live", "live", count=10))
            baseline["path"] = str(pathlib.Path(directory)/"baseline")
            live["path"] = str(pathlib.Path(directory)/"live")
            result = compare([baseline, live, baseline, live])
            self.assertTrue(result["_comparison"]["errors"])
            self.assertFalse(result["i64_o64"]["live"]["sample_complete"])

    def test_cpu_completeness_is_separate_from_valid_latency_records(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.write_run(directory, "run-a", mode="detail")
            manifest = json.loads((run/"manifest.json").read_text())
            manifest["cpu_observation_enabled"] = True
            (run/"manifest.json").write_text(json.dumps(manifest))
            record = cpu_example()
            record.update(request_id="1", block=0, completed_utc_ns=101)
            (run/"requests/1.json").write_text(json.dumps(record))
            complete = audit(run)
            self.assertTrue(complete["complete"])
            self.assertTrue(complete["cpu_observation"]["complete"])
            self.assertAlmostEqual(complete["cpu_observation"]["cases"]["i64_o64"]
                ["input"]["on_cpu"]["median"], .001)
            for thread in record["cpu_observation"]["threads"].values():
                for snapshot in thread["snapshots"].values():
                    snapshot.update(runqueue_wait_ns=None, wait_error="unavailable")
            (run/"requests/1.json").write_text(json.dumps(record))
            partial = audit(run)
            self.assertTrue(partial["complete"])
            self.assertFalse(partial["cpu_observation"]["complete"])
            self.assertTrue(partial["cpu_observation"]["errors"])
            self.assertNotIn("runqueue_wait", partial["cpu_observation"]["cases"]
                             ["i64_o64"]["input"])


if __name__ == "__main__":
    unittest.main()
