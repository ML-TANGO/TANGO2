import re
import unittest
from unittest.mock import patch

from exporter import Store
from test_metrics import example


def samples(store, now):
    with patch("exporter.time.time", return_value=now):
        text = store.render(dict(up=0, age=6, active=0))
    result = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        metric, value = line.rsplit(" ", 1)
        name, _, labels = metric.partition("{")
        tags = tuple(sorted(re.findall(r'(\w+)="([^"]*)"', labels)))
        result[name, tags] = float(value)
    return result


def metric(values, suffix, **tags):
    return values.get(("tango2_llm_"+suffix, tuple(sorted(tags.items()))))


class ExactWindowContract(unittest.TestCase):
    def record(self, identifier, completed, ttft=.0186, **changes):
        record = example()
        first = 1_000_000_000+round(ttft*1e9)
        record.update(request_id=identifier, completed_utc_ns=round(completed*1e9),
                      g1_ns=first, gN_ns=first+50_000_000,
                      token_ns=[first, first+20_000_000, first+50_000_000],
                      e_ns=1_100_000_000, v1_ns=first+1_000_000,
                      stages_ns={})
        record.update(changes)
        return record

    def test_values_in_one_bucket_still_have_exact_percentiles_and_bounds(self):
        store = Store(epoch_ns=1)
        for index, value in enumerate((.0182, .0186, .0190)):
            store.ingest(self.record(str(index), 990+index, value))
        values = samples(store, 1000)
        tags = dict(case="i64_o64", mode="live", stage="ttft")
        expected = {"p50": .0186, "p95": .01896, "min": .0182, "max": .0190}
        for statistic, value in expected.items():
            self.assertAlmostEqual(metric(values, "window_duration_seconds",
                                          **tags, statistic=statistic), value)
        self.assertEqual(metric(values, "window_requests", case="i64_o64", mode="live"), 3)
        self.assertAlmostEqual(metric(values, "window_duration_seconds", case="i64_o64",
                                      mode="live", stage="itl", statistic="p50"), .025)

    def test_window_excludes_expired_future_and_ineligible_requests_without_pooling(self):
        store = Store(epoch_ns=1)
        for identifier, completed, changes in (
                ("boundary", 700, {}), ("old", 699, {}), ("future", 1001, {}),
                ("warmup", 990, {"warmup": True}), ("invalid", 991, {"valid": False}),
                ("error", 992, {"status": "error"}),
                ("other-case", 993, {"case": "i256_o128"}),
                ("detail", 994, {"mode": "detail", "gpu_ms": {"prefill": 10, "decode": 40}}),
                ("eligible", 995, {})):
            store.ingest(self.record(identifier, completed, **changes))
        values = samples(store, 1000)
        self.assertEqual(metric(values, "window_requests", case="i64_o64", mode="live"), 1)
        self.assertEqual(metric(values, "window_requests", case="i64_o64", mode="detail"), 1)
        values = samples(store, 1302)
        self.assertEqual(metric(values, "window_requests", case="i64_o64", mode="live"), 0)
        self.assertIsNone(metric(values, "window_duration_seconds", case="i64_o64",
                                 mode="live", stage="ttft", statistic="p50"))

    def test_new_run_does_not_clear_the_window_or_recount_duplicate_records(self):
        store = Store(epoch_ns=1)
        first = self.record("1", 990, .0182)
        store.ingest(first)
        store.ingest(first)
        store.ingest(self.record("2", 995, .0190, run_id="run-b"))
        values = samples(store, 1000)
        self.assertEqual(metric(values, "window_requests", case="i64_o64", mode="live"), 2)
        self.assertAlmostEqual(metric(values, "window_duration_seconds", case="i64_o64",
                                      mode="live", stage="ttft", statistic="p50"), .0186)

    def test_window_reports_metric_specific_eligible_sample_counts(self):
        store = Store(epoch_ns=1)
        for index in range(29):
            record = self.record(str(index), 990-index)
            record.update(output_tokens=1, token_ns=[record["token_ns"][0]],
                          gN_ns=record["g1_ns"], v1_ns=None)
            store.ingest(record)
        store.ingest(self.record("multi-token", 995))
        values = samples(store, 1000)
        base = dict(case="i64_o64", mode="live")
        self.assertEqual(metric(values, "window_requests", **base), 30)
        self.assertEqual(metric(values, "window_samples", **base, stage="ttft"), 30)
        self.assertEqual(metric(values, "window_samples", **base, stage="tpot"), 1)
        self.assertEqual(metric(values, "window_samples", **base,
                                stage="decode_tokens_per_second"), 1)
        self.assertLess(len(values), 5000)
