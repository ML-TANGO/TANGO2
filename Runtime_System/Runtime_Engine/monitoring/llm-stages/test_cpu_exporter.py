import pathlib
import unittest
from unittest.mock import patch

from exporter import Collector, Store, RUN_METADATA_LIMIT
from metrics import CASES
from test_cpu_metrics import cpu_example
from test_window import metric, samples


class CpuCollectionContract(unittest.TestCase):
    def record(self, identifier="1", completed=100):
        record = cpu_example()
        record.update(request_id=identifier, completed_utc_ns=round(completed*1e9))
        return record

    def test_cpu_values_reach_exact_window_without_creating_histograms(self):
        store = Store(epoch_ns=1)
        record = self.record()
        store.ingest(record)
        store.ingest(record)
        values = samples(store, 105)
        tags = dict(case="i64_o64", mode="detail", scope="input", kind="on_cpu")
        self.assertEqual(metric(values, "cpu_window_samples", **tags), 1)
        self.assertAlmostEqual(metric(values, "cpu_window_seconds", **tags, statistic="p50"), .001)
        self.assertEqual(metric(values, "cpu_observations_total", status="complete"), 1)
        self.assertEqual(metric(values, "window_samples", case="i64_o64", mode="detail", stage="e2e"), 1)
        self.assertFalse(any("cpu" in dict(tags).get("stage", "")
                             for name, tags in values if name.startswith("tango2_llm_duration_seconds")))
        self.assertFalse(any("tid" in dict(tags) or "request_id" in dict(tags) for _, tags in values))

    def test_unavailable_wait_keeps_host_and_cpu_runtime_and_expires_together(self):
        store = Store(epoch_ns=1)
        record = self.record()
        for thread in record["cpu_observation"]["threads"].values():
            for snapshot in thread["snapshots"].values():
                snapshot.update(runqueue_wait_ns=None, wait_error="unavailable")
        store.ingest(record)
        values = samples(store, 105)
        tags = dict(case="i64_o64", mode="detail", scope="worker_request")
        self.assertEqual(metric(values, "cpu_window_samples", **tags, kind="on_cpu"), 1)
        self.assertEqual(metric(values, "cpu_window_samples", **tags, kind="runqueue_wait"), 0)
        self.assertIsNone(metric(values, "cpu_window_seconds", **tags, kind="runqueue_wait", statistic="p50"))
        self.assertEqual(metric(values, "cpu_samples_unavailable_total", scope="worker_request", kind="runqueue_wait"), 1)
        self.assertEqual(metric(values, "cpu_observations_total", status="partial"), 1)
        self.assertEqual(metric(values, "window_samples", case="i64_o64", mode="detail", stage="e2e"), 1)
        expired = samples(store, 401)
        self.assertEqual(metric(expired, "cpu_window_samples", **tags, kind="on_cpu"), 0)
        self.assertIsNone(metric(expired, "cpu_window_seconds", **tags, kind="on_cpu", statistic="p50"))

    def test_full_supported_collection_remains_under_series_budget(self):
        collector = Collector(pathlib.Path("/not-a-run-directory"), pathlib.Path("/no-heartbeat"))
        collector.store = store = Store(epoch_ns=1)
        for index in range(RUN_METADATA_LIMIT):
            store.begin_run(f"old-{index}", index, dict(started_utc_ns=index,
                completed_utc_ns=index+1, mode="detail"))
        for index, mode in enumerate(("live", "detail")):
            run_id = f"run-{mode}"
            store.begin_run(run_id, (90+index)*10**9, dict(started_utc_ns=(90+index)*10**9,
                completed_utc_ns=100*10**9, mode=mode))
            for case in CASES:
                record = self.record(case)
                record.update(run_id=run_id, case=case, mode=mode)
                record["stages_ns"]["host_remainder"] = 1
                if mode == "live":
                    record["gpu_ms"] = {}
                    del record["cpu_observation"]
                store.ingest(record)
        # All currently supported device dimensions, including both board rail sets.
        collector.sensors.values = {name: 1 for name in (
            "gpu_utilization_ratio", "gpu_clock_hertz", "emc_clock_hertz", "cpu_clock_hertz",
            "cpu_temperature_celsius", "gpu_temperature_celsius", "soc0_temperature_celsius",
            "input_power_watts", "gpu_soc_power_watts", "cpu_cv_power_watts",
            "system_5v_power_watts", "ddr_1v8ao_power_watts", "cpu_utilization_ratio", "memory_used_bytes")}
        with patch("exporter.time.time", return_value=105), patch("exporter.heartbeat_state",
                return_value=dict(up=1, age=0, active=0)):
            rendered = collector.render()
        active = [line for line in rendered.splitlines() if not line.startswith("#")]
        self.assertLessEqual(len(active), 5000)
        self.assertFalse(any('mode="live"' in line and 'stage="gpu_' in line for line in active))

    def test_warmup_failed_and_future_requests_do_not_enter_cpu_distributions(self):
        store = Store(epoch_ns=1)
        for identifier, changes in (("warm", {"warmup": True}),
                                    ("error", {"status": "error"}),
                                    ("future", {"completed_utc_ns": 110_000_000_000})):
            record = self.record(identifier)
            record.update(changes)
            store.ingest(record)
        values = samples(store, 105)
        self.assertEqual(metric(values, "cpu_window_samples", case="i64_o64", mode="detail",
                                scope="worker_request", kind="on_cpu"), 0)


if __name__ == "__main__":
    unittest.main()
