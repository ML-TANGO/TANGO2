import os
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling import scheduling_snapshot


class SchedulingTest(unittest.TestCase):
    @unittest.skipUnless(
        hasattr(os, "sched_getscheduler"),
        "Linux scheduling API is unavailable",
    )
    def test_snapshot_reports_observed_state(self):
        snapshot = scheduling_snapshot()
        self.assertEqual(snapshot["affinity"], sorted(os.sched_getaffinity(0)))
        self.assertIn("policy", snapshot)
        self.assertIn("priority", snapshot)


if __name__ == "__main__":
    unittest.main()
