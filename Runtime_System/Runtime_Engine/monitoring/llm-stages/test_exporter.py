import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from exporter import Collector, Store
from test_metrics import example


class CollectionContract(unittest.TestCase):
    def record(self, **changes):
        r = example()
        r["completed_utc_ns"] = 100
        r.update(changes)
        return r

    def test_duplicate_reprocessing_cannot_change_counts(self):
        store = Store(epoch_ns=1)
        record = self.record()
        store.ingest(record)
        before = copy.deepcopy(store.histograms)
        store.ingest(record)
        self.assertEqual(store.histograms, before)
        self.assertEqual(store.statuses["i64_o64", "live", "length"], 1)
        self.assertEqual(store.duplicates, 1)

    def test_restart_does_not_replay_historical_completions(self):
        store = Store(epoch_ns=101)
        store.ingest(self.record())
        self.assertEqual(store.histograms["i64_o64", "live", "e2e"][2], 0)
        store.ingest(self.record(request_id="new", completed_utc_ns=102))
        self.assertEqual(store.statuses["i64_o64", "live", "length"], 1)

    def test_new_run_clears_gauges_but_preserves_counters(self):
        store = Store(epoch_ns=1)
        store.ingest(self.record())
        store.ingest(self.record(run_id="run-b", case="i256_o128", warmup=True,
                                 completed_utc_ns=101))
        self.assertFalse(any(key[0] == "i64_o64" for key in store.latest))
        self.assertEqual(store.histograms["i64_o64", "live", "ttft"][2], 1)
        store.ingest(self.record(run_id="run-c", status="error", completed_utc_ns=102))
        self.assertFalse(store.latest)
        store.ingest(self.record(completed_utc_ns=103))
        self.assertEqual(store.current_run, "run-c")

    def test_latest_gauges_require_a_live_producer_and_fresh_completion(self):
        store = Store(epoch_ns=1)
        store.ingest(self.record(completed_utc_ns=100_000_000_000))
        with patch("exporter.time.time", return_value=105):
            active = store.render(dict(up=1, age=0, active=0))
            stopped = store.render(dict(up=0, age=6, active=0))
        with patch("exporter.time.time", return_value=111):
            idle = store.render(dict(up=1, age=0, active=0))
        self.assertIn("tango2_llm_latest_decode_tokens_per_second", active)
        self.assertNotIn("tango2_llm_latest_decode_tokens_per_second", stopped)
        self.assertNotIn("tango2_llm_latest_decode_tokens_per_second", idle)

    def test_latest_gauges_expire_per_case_and_mode(self):
        store = Store(epoch_ns=1)
        store.ingest(self.record(completed_utc_ns=100_000_000_000))
        store.ingest(self.record(case="i256_o128", mode="detail", request_id="new",
                                 gpu_ms={"prefill": 800.0, "decode": 30.0},
                                 completed_utc_ns=200_000_000_000))
        store.ingest(self.record(request_id="diagnostic", status="timeout", output_tokens=2,
                                 token_ns=[2_000_000_000, 2_050_000_000],
                                 completed_utc_ns=200_000_000_000))
        with patch("exporter.time.time", return_value=201):
            rendered = store.render(dict(up=1, age=0, active=0))
        old = 'case="i64_o64",mode="live"'
        fresh = 'case="i256_o128",mode="detail"'
        self.assertNotIn("tango2_llm_latest_decode_tokens_per_second{"+old, rendered)
        self.assertNotIn("tango2_llm_last_completed_timestamp_seconds{"+old, rendered)
        self.assertIn("tango2_llm_latest_decode_tokens_per_second{"+fresh, rendered)
        self.assertIn("tango2_llm_last_completed_timestamp_seconds{"+fresh, rendered)

    def test_failures_are_counted_without_entering_performance_histograms(self):
        store = Store(epoch_ns=1)
        store.ingest(self.record())
        store.ingest(self.record(request_id="timeout", status="timeout", output_tokens=2,
                                 token_ns=[2_000_000_000, 2_050_000_000]))
        store.ingest(self.record(request_id="error", status="error", output_tokens=1,
                                 token_ns=[2_000_000_000], gN_ns=2_000_000_000))
        store.ingest(self.record(request_id="bad", valid=False, output_tokens=1,
                                 token_ns=[2_000_000_000], gN_ns=2_000_000_000))
        self.assertEqual(store.histograms["i64_o64", "live", "e2e"][2], 1)
        self.assertEqual(sum(store.statuses.values()), 4)
        self.assertEqual(store.invalid, 1)
        self.assertEqual(store.tokens["i64_o64", "live", "input"], 256)
        self.assertEqual(store.tokens["i64_o64", "live", "output"], 7)

    def test_baseline_is_acknowledged_without_exported_aggregation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            (requests/"baseline.json").write_text(json.dumps(self.record(mode="baseline")))
            collector = Collector(root, root/"heartbeat.json")
            collector.store.epoch_ns = 1
            collector.scan()
            self.assertTrue((root/"run-a"/"acknowledged"/"baseline.json").exists())
            self.assertEqual(sum(collector.store.statuses.values()), 0)
            self.assertEqual(sum(collector.store.tokens.values()), 0)
            self.assertTrue(all(count == 0 for _, _, count in collector.store.histograms.values()))

    def test_invalid_warmups_are_diagnostic_only(self):
        store = Store(epoch_ns=1)
        for mode in ("live", "detail"):
            store.ingest(self.record(mode=mode, request_id=mode, warmup=True, valid=False))
        self.assertEqual(store.invalid, 2)
        self.assertEqual(store.statuses["i64_o64", "live", "length"], 1)
        self.assertEqual(store.statuses["i64_o64", "detail", "length"], 1)
        self.assertTrue(all(count == 0 for _, _, count in store.histograms.values()))
        self.assertTrue(all(count == 0 for _, _, count in store.output_lengths.values()))

    def test_zero_baseline_and_first_event_are_visible_to_range_queries(self):
        store = Store(epoch_ns=1)
        before = store.render(dict(up=0, age=0, active=0))
        self.assertIn('tango2_llm_duration_seconds_count{case="i64_o64",mode="live",stage="e2e"} 0', before)
        self.assertIn('tango2_llm_output_tokens_count{case="i64_o64",mode="live"} 0', before)
        store.ingest(self.record())
        after = store.render(dict(up=0, age=0, active=0))
        self.assertIn('tango2_llm_duration_seconds_count{case="i64_o64",mode="live",stage="e2e"} 1', after)
        self.assertIn('tango2_llm_output_tokens_count{case="i64_o64",mode="live"} 1', after)

    def test_collector_counts_bad_shapes_and_keeps_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            requests = root/"run-a"/"requests"
            requests.mkdir(parents=True)
            (requests/"bad.json").write_text("[]")
            (requests/"mixed.json").write_text(json.dumps({"completed_utc_ns": "later"}))
            (requests/"good.json").write_text(json.dumps(self.record()))
            collector = Collector(root, root/"heartbeat.json")
            collector.store.epoch_ns = 1
            collector.scan()
            self.assertEqual(collector.store.statuses["i64_o64", "live", "length"], 1)
            self.assertEqual(collector.store.parse_errors, 2)
            self.assertTrue((root/"run-a"/"acknowledged"/"good.json").exists())

    def test_buckets_are_cumulative_and_nan_never_reaches_scrape(self):
        store = Store(epoch_ns=1)
        store.ingest(self.record())
        buckets, total, count = store.histograms["i64_o64", "live", "itl"]
        self.assertEqual(count, 2)
        self.assertAlmostEqual(total, .05)
        self.assertEqual(buckets[-1], 2)
        self.assertTrue(all(y >= x for x, y in zip(buckets, buckets[1:])))


class PowerSensing(unittest.TestCase):
    def power_metrics(self, collector):
        return {name: float(value) for name, value in
                (line.split() for line in collector.render().splitlines()
                 if line.startswith("tango2_llm_device_") and "_power_watts " in line)}

    def rail(self, root, hwmon, channel, name, millivolts, milliamps):
        directory = root/"sys/class/hwmon"/f"hwmon{hwmon}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory/"name").write_text("ina3221")
        (directory/f"in{channel}_label").write_text(name)
        (directory/f"in{channel}_input").write_text(str(millivolts))
        (directory/f"curr{channel}_input").write_text(str(milliamps))
        return directory

    def test_agx_rails_reach_metrics_without_inventing_total_input_power(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self.rail(root, 12, 1, "VDD_GPU_SOC", 20000, 200)
            self.rail(root, 12, 2, "VDD_CPU_CV", 20000, 100)
            self.rail(root, 12, 3, "VIN_SYS_5V0", 5000, 600)
            self.rail(root, 18, 2, "VDDQ_VDD2_1V8AO", 5000, 100)
            self.rail(root, 12, 7, "sum of shunt voltages", 600, 300)
            with patch("exporter.pathlib.Path", side_effect=lambda p: root/str(p).lstrip("/")), \
                    patch("exporter.time.monotonic", return_value=10):
                collector = Collector(root/"runs", root/"heartbeat.json")
                collector.scan()
                metrics = self.power_metrics(collector)
            # DDR is downstream of the 5V rail; these four values cannot be summed.
            self.assertEqual(metrics, {
                "tango2_llm_device_gpu_soc_power_watts": 4.0,
                "tango2_llm_device_cpu_cv_power_watts": 2.0,
                "tango2_llm_device_system_5v_power_watts": 3.0,
                "tango2_llm_device_ddr_1v8ao_power_watts": 0.5})

    def test_nx_vdd_in_remains_a_direct_input_power_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self.rail(root, 27, 1, "VDD_IN", 12000, 500)
            with patch("exporter.pathlib.Path", side_effect=lambda p: root/str(p).lstrip("/")), \
                    patch("exporter.time.monotonic", return_value=10):
                collector = Collector(root/"runs", root/"heartbeat.json")
                collector.scan()
                self.assertEqual(self.power_metrics(collector),
                                 {"tango2_llm_device_input_power_watts": 6.0})

    def test_unreadable_or_nonfinite_rail_drops_stale_value_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            hwmon = self.rail(root, 12, 1, "VDD_GPU_SOC", 20000, 200)
            self.rail(root, 12, 2, "VDD_CPU_CV", 20000, 100)
            with patch("exporter.pathlib.Path", side_effect=lambda p: root/str(p).lstrip("/")), \
                    patch("exporter.time.monotonic", return_value=10):
                collector = Collector(root/"runs", root/"heartbeat.json")
                collector.scan()
                self.assertEqual(len(self.power_metrics(collector)), 2)
                for broken in ("nan", "unreadable", None):
                    if broken is None:
                        (hwmon/"curr1_input").unlink()
                    else:
                        (hwmon/"curr1_input").write_text(broken)
                    with patch("exporter.time.monotonic", return_value=collector.sensors.last_sample+2):
                        collector.scan()
                    self.assertEqual(self.power_metrics(collector),
                                     {"tango2_llm_device_cpu_cv_power_watts": 2.0})


if __name__ == "__main__":
    unittest.main()
