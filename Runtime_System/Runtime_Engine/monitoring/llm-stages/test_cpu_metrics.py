"""CPU counters are independent of wall-clock latency and GPU timing."""

import unittest

from metrics import aggregate_cpu_observation, aggregate_request
from test_metrics import example


def cpu_example():
    record = example()
    record.update(mode="detail", gpu_ms={"prefill": 800.0, "decode": 30.0})

    def snapshot(boundary, cpu, wait):
        return dict(boundary_ns=boundary, read_begin_ns=boundary+1,
                    read_end_ns=boundary+10, on_cpu_ns=cpu,
                    runqueue_wait_ns=wait, runtime_error="", wait_error="")

    record["cpu_observation"] = dict(
        schema_version=1, method="thread_clock_schedstat", scope="instrumented_threads",
        enabled=True, threads={
            "worker": dict(pid=100, tid=101, starttime_ticks=123, identity_error="",
                snapshots={
                    "request_begin": snapshot(1_002_000_000, 1_000, 100),
                    "input_begin": snapshot(1_010_000_000, 2_000, 200),
                    "input_end": snapshot(1_012_000_000, 1_002_000, 2_200),
                    "prefill_begin": snapshot(1_015_000_000, 2_002_000, 3_200),
                    "prefill_end": snapshot(1_915_000_000, 10_000_000, 1_000_000),
                    "request_end": snapshot(2_090_000_000, 20_000_000, 2_000_000)}),
            "consumer": dict(pid=100, tid=100, starttime_ticks=120, identity_error="",
                snapshots={
                    "request_begin": snapshot(record["b_ns"], 10_000_000, 1_000),
                    "request_end": snapshot(record["e_ns"], 12_000_000, 2_000)})})
    return record


class CpuMeasurementContract(unittest.TestCase):
    def test_counter_deltas_are_seconds_without_replacing_host_or_gpu_time(self):
        record = cpu_example()
        result = aggregate_cpu_observation(record)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["values"]), 12)
        self.assertAlmostEqual(result["values"]["input", "on_cpu"], .001)
        self.assertAlmostEqual(result["values"]["input", "runqueue_wait"], .000002)
        self.assertAlmostEqual(result["values"]["worker_request", "on_cpu"], .019999)
        self.assertAlmostEqual(result["values"]["decode_and_finalize", "on_cpu"], .010)
        self.assertAlmostEqual(result["values"]["consumer_request", "on_cpu"], .002)
        self.assertAlmostEqual(aggregate_request(record)["prefill_host"], .9)
        self.assertAlmostEqual(aggregate_request(record)["gpu_prefill"], .8)
        self.assertNotIn(("generation", "on_cpu"), result["values"])

    def test_unsupported_wait_does_not_hide_runtime_or_invent_zero_wait(self):
        record = cpu_example()
        for thread in record["cpu_observation"]["threads"].values():
            for snapshot in thread["snapshots"].values():
                snapshot.update(runqueue_wait_ns=None, wait_error="schedstat_unavailable")
        result = aggregate_cpu_observation(record)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["values"]), 6)
        self.assertTrue(all(kind == "on_cpu" for _, kind in result["values"]))
        self.assertEqual(len(result["issues"]), 6)
        self.assertIsNotNone(aggregate_request(record))

    def test_measured_zero_wait_is_an_eligible_sample(self):
        record = cpu_example()
        for thread in record["cpu_observation"]["threads"].values():
            for snapshot in thread["snapshots"].values():
                snapshot["runqueue_wait_ns"] = 0
        result = aggregate_cpu_observation(record)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["values"]["worker_request", "runqueue_wait"], 0)

    def test_legacy_disabled_and_missing_enabled_data_remain_distinct(self):
        self.assertEqual(aggregate_cpu_observation(example())["status"], "legacy")
        record = cpu_example()
        record["cpu_observation"].update(enabled=False, threads={})
        self.assertEqual(aggregate_cpu_observation(record)["status"], "disabled")
        record["cpu_observation"]["enabled"] = True
        result = aggregate_cpu_observation(record)
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["values"])
        self.assertIsNotNone(aggregate_request(record))

    def test_bad_identity_counter_reversal_and_marker_mismatch_are_not_zero(self):
        for mutation in ("identity", "counter", "marker", "error", "read_window"):
            record = cpu_example()
            worker = record["cpu_observation"]["threads"]["worker"]
            if mutation == "identity":
                worker["tid"] = 0
            elif mutation == "counter":
                worker["snapshots"]["input_end"]["on_cpu_ns"] = 1
            elif mutation == "marker":
                worker["snapshots"]["input_end"]["boundary_ns"] += 1
            elif mutation == "error":
                worker["snapshots"]["input_end"]["runtime_error"] = "unavailable"
            else:
                worker["snapshots"]["input_end"]["read_end_ns"] = 1
            result = aggregate_cpu_observation(record)
            self.assertEqual(result["status"], "invalid", mutation)
            self.assertNotIn(("input", "on_cpu"), result["values"], mutation)
            self.assertIn(("consumer_request", "on_cpu"), result["values"], mutation)
            self.assertIsNotNone(aggregate_request(record))

    def test_cross_thread_identity_and_complete_worker_chain_are_required(self):
        for mutation in ("different_process", "same_thread", "outer_boundary", "reordered", "bad_error", "bad_stages"):
            with self.subTest(mutation=mutation):
                record = cpu_example()
                worker = record["cpu_observation"]["threads"]["worker"]
                if mutation == "different_process":
                    worker["pid"] += 1
                elif mutation == "same_thread":
                    worker["tid"] = 100
                elif mutation == "outer_boundary":
                    worker["snapshots"]["request_begin"]["boundary_ns"] = 1_011_000_000
                elif mutation == "reordered":
                    worker["snapshots"]["prefill_begin"]["boundary_ns"] = 1_011_000_000
                elif mutation == "bad_error":
                    worker["identity_error"] = 42
                else:
                    record["stages_ns"] = []
                result = aggregate_cpu_observation(record)
                self.assertEqual(result["status"], "invalid")
                self.assertNotIn(("input", "on_cpu"), result["values"])

    def test_consumer_end_read_may_follow_response_boundary(self):
        record = cpu_example()
        end = record["cpu_observation"]["threads"]["consumer"]["snapshots"]["request_end"]
        end.update(read_begin_ns=record["e_ns"]+10_000, read_end_ns=record["e_ns"]+20_000)
        self.assertEqual(aggregate_cpu_observation(record)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
