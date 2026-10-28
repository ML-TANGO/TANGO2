import json
import pathlib
import tarfile
import tempfile
import unittest
from unittest import mock

from exporter import Store
from test_metrics import example
from test_cpu_metrics import cpu_example
from verify_collection import verify


class VerificationContract(unittest.TestCase):
    def record(self):
        record = example()
        record["completed_utc_ns"] = 100_000_000_000
        return record

    def verify(self, root, payload):
        response = mock.Mock()
        response.read.return_value = payload.encode()
        with mock.patch("verify_collection.urllib.request.urlopen", return_value=response):
            return verify(root, "http://collector.invalid/metrics")

    def payload(self, store, now=105):
        with mock.patch("exporter.time.time", return_value=now):
            return store.render(dict(up=1, age=0, active=0))+"tango2_llm_pending_records 0\n"

    def test_matching_raw_and_exported_observations_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            record = self.record()
            (requests/"1.json").write_text(json.dumps(record))
            store = Store(epoch_ns=1)
            store.ingest(record)
            self.assertTrue(self.verify(root, self.payload(store))["pass_gate"])

    def test_exported_observation_without_raw_evidence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            record = self.record()
            store = Store(epoch_ns=1)
            store.ingest(record)
            result = self.verify(root, self.payload(store))
            self.assertFalse(result["pass_gate"])
            self.assertTrue(any(error.startswith("count mismatch") for error in result["errors"]))

    def test_missing_required_endpoint_metric_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            record = self.record()
            (requests/"1.json").write_text(json.dumps(record))
            store = Store(epoch_ns=1)
            store.ingest(record)
            payload = "\n".join(line for line in self.payload(store).splitlines()
                                if not line.startswith("tango2_llm_records_invalid_total"))+"\n"
            result = self.verify(root, payload)
            self.assertFalse(result["pass_gate"])
            self.assertIn("missing metric: records_invalid_total", result["errors"])

    def test_wrong_window_percentile_is_rejected_even_when_histograms_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            record = self.record()
            (requests/"1.json").write_text(json.dumps(record))
            store = Store(epoch_ns=1)
            store.ingest(record)
            payload = "\n".join(line.rsplit(" ", 1)[0]+" 0.015"
                                if line.startswith("tango2_llm_window_duration_seconds")
                                and 'stage="ttft"' in line and 'statistic="p50"' in line else line
                                for line in self.payload(store).splitlines())+"\n"
            result = self.verify(root, payload)
            self.assertFalse(result["pass_gate"])
            self.assertTrue(any(error.startswith("window value mismatch") for error in result["errors"]))

    def test_expired_or_failure_only_window_cannot_export_performance_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            expired = self.record()
            expired["completed_utc_ns"] = 1_000_000_000
            failure = self.record()
            failure.update(request_id="failure", status="error", completed_utc_ns=400_000_000_000)
            (requests/"expired.json").write_text(json.dumps(expired))
            (requests/"failure.json").write_text(json.dumps(failure))
            store = Store(epoch_ns=1)
            store.ingest(expired)
            store.ingest(failure)
            payload = self.payload(store, now=405)
            source = Store(epoch_ns=1)
            source_record = self.record()
            source_record["completed_utc_ns"] = 400_000_000_000
            source.ingest(source_record)
            stale = next(line for line in self.payload(source, now=405).splitlines()
                         if line.startswith("tango2_llm_window_duration_seconds")
                         and 'stage="ttft"' in line and 'statistic="p50"' in line)
            result = self.verify(root, payload+stale+"\n")
            self.assertFalse(result["pass_gate"])
            self.assertTrue(any(error.startswith("unexpected window statistic")
                                for error in result["errors"]))

    def test_records_completed_after_endpoint_snapshot_do_not_change_cumulative_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            captured = self.record()
            later = self.record()
            later.update(request_id="later", completed_utc_ns=106_000_000_000)
            (requests/"captured.json").write_text(json.dumps(captured))
            (requests/"later.json").write_text(json.dumps(later))
            store = Store(epoch_ns=1)
            store.ingest(captured)
            result = self.verify(root, self.payload(store))
            self.assertTrue(result["pass_gate"], result["errors"])

            mismatched = self.payload(store).replace(
                'tango2_llm_duration_seconds_count{case="i64_o64",mode="live",stage="e2e"} 1',
                'tango2_llm_duration_seconds_count{case="i64_o64",mode="live",stage="e2e"} 2')
            result = self.verify(root, mismatched)
            self.assertFalse(result["pass_gate"])
            self.assertTrue(any(error.startswith("count mismatch") for error in result["errors"]))

    def test_rotated_raw_records_remain_available_to_the_independent_check(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root = base/"runs"
            root.mkdir()
            archives = base/"continuous-archives"
            archives.mkdir()
            raw = base/"raw.json"
            record = self.record()
            raw.write_text(json.dumps(record))
            with tarfile.open(archives/"continuous-example.tar.gz", "w:gz") as archive:
                archive.add(raw, arcname="runs/run-a/requests/1.json")
            store = Store(epoch_ns=1)
            store.ingest(record)
            result = self.verify(root, self.payload(store))
            self.assertTrue(result["pass_gate"], result["errors"])
            self.assertGreater(result["compared_window_statistics"], 0)

    def test_cpu_counter_deltas_are_independently_checked_against_scrape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            record = cpu_example()
            record["completed_utc_ns"] = 100_000_000_000
            (requests/"1.json").write_text(json.dumps(record))
            store = Store(epoch_ns=1)
            store.ingest(record)
            payload = self.payload(store)
            good = self.verify(root, payload)
            self.assertTrue(good["pass_gate"], good["errors"])
            self.assertTrue(good["cpu_observation_complete"])
            self.assertEqual(good["compared_cpu_statistics"], 24)
            corrupted = "\n".join(line.rsplit(" ", 1)[0]+" 0.9"
                if line.startswith("tango2_llm_cpu_window_seconds") and 'scope="input"' in line
                and 'kind="on_cpu"' in line else line for line in payload.splitlines())+"\n"
            bad = self.verify(root, corrupted)
            self.assertFalse(bad["pass_gate"])
            self.assertTrue(any(error.startswith("CPU window value mismatch") for error in bad["errors"]))


if __name__ == "__main__":
    unittest.main()
