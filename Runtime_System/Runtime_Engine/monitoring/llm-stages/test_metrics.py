"""Contract examples; all timestamps below are AGX monotonic nanoseconds."""

import copy
import unittest

from metrics import aggregate_request


def example():
    # Three tokens in 50ms: two intervals, hence 40 tok/s and 25ms TPOT.
    return dict(schema_version=1, run_id="run-a", request_id="r1", mode="live",
                case="i64_o64", warmup=False, status="length", valid=True,
                a_ns=1_000_000_000, b_ns=1_001_000_000,
                g1_ns=2_000_000_000, gN_ns=2_050_000_000,
                e_ns=2_100_000_000, v1_ns=2_010_000_000,
                token_ns=[2_000_000_000, 2_020_000_000, 2_050_000_000],
                output_tokens=3, input_tokens=64, stages_ns={
                    "input": 2_000_000, "prefill_prepare": 3_000_000,
                    "prefill_host": 900_000_000, "detokenize": 1_000_000,
                    "deliver": 2_000_000}, gpu_ms={})


class RequestContract(unittest.TestCase):
    def test_token_intervals_and_host_boundaries(self):
        result = aggregate_request(example())
        self.assertAlmostEqual(result["ttft"], 1.0)
        self.assertAlmostEqual(result["first_text"], 1.01)
        self.assertAlmostEqual(result["e2e"], 1.1)
        self.assertAlmostEqual(result["tpot"], .025)
        self.assertAlmostEqual(result["decode_tokens_per_second"], 40)
        self.assertEqual(result["itl"], [.02, .03])

    def test_zero_and_one_token_do_not_invent_generation_speed(self):
        for count in (0, 1):
            record = example()
            record.update(output_tokens=count, token_ns=record["token_ns"][:count],
                          g1_ns=2_000_000_000 if count else None,
                          gN_ns=2_000_000_000 if count else None, v1_ns=None)
            values = aggregate_request(record)
            self.assertNotIn("tpot", values)
            self.assertNotIn("decode_tokens_per_second", values)
            self.assertNotIn("first_text", values)

    def test_diagnostic_and_warmup_requests_do_not_enter_distributions(self):
        for changes in ({"warmup": True}, {"status": "timeout"},
                        {"status": "cancelled"}, {"status": "error"},
                        {"valid": False}):
            record = example()
            record.update(changes)
            self.assertIsNone(aggregate_request(record))

    def test_bad_clock_count_and_gpu_mode_are_rejected(self):
        for changes in ({"token_ns": [2_000_000_000]},
                        {"gN_ns": 2_040_000_000},
                        {"e_ns": 1_000_000_000},
                        {"token_ns": [2_000_000_000, 1, 2_050_000_000]},
                        {"gpu_ms": {"prefill": 1.0}},
                        {"stages_ns": {"input": -1}},
                        {"case": "arbitrary-label"}):
            record = copy.deepcopy(example())
            record.update(changes)
            with self.assertRaises(ValueError, msg=str(changes)):
                aggregate_request(record)

    def test_detail_gpu_values_are_independent_of_host_stage_sums(self):
        record = example()
        record.update(mode="detail", gpu_ms={"prefill": 800.0, "decode": 30.0})
        values = aggregate_request(record)
        self.assertEqual(values["gpu_prefill"], .8)
        self.assertEqual(values["gpu_decode"], .03)
        self.assertAlmostEqual(values["e2e"], 1.1)


if __name__ == "__main__":
    unittest.main()
