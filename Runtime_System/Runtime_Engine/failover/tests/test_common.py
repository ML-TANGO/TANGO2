import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import JsonlWriter, parse_proc_start_ticks


class CommonTest(unittest.TestCase):
    def test_parse_start_ticks_with_spaces_in_comm(self):
        fields = ["S"] + [str(value) for value in range(4, 53)]
        fields[19] = "424242"
        stat_line = "123 (name with spaces) " + " ".join(fields)
        self.assertEqual(parse_proc_start_ticks(stat_line), 424242)

    def test_jsonl_writer_emits_one_record(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "events.jsonl"
            with JsonlWriter(output) as writer:
                record = writer.write("READY", value=7)
            self.assertEqual(record["event"], "READY")
            self.assertIn('"value": 7', output.read_text(encoding="utf-8"))

    def test_inherited_log_keeps_event_times_order_and_parent_ownership(self):
        with tempfile.TemporaryFile() as output:
            with patch("common.monotonic_raw_ns", side_effect=[100, 200]):
                with JsonlWriter(fd=output.fileno()) as writer:
                    first = writer.write("HEALTH_CONFIRMATION_FAILED")
                    second = writer.write("FAILOVER_DETECTED", detected_raw_ns=190)
            output.seek(0)
            self.assertEqual(
                [json.loads(line) for line in output], [first, second]
            )
            self.assertEqual([first["ts_raw_ns"], second["ts_raw_ns"]], [100, 200])

    def test_inherited_log_handles_short_writes_without_losing_bytes(self):
        write = os.write
        with tempfile.TemporaryFile() as output:
            with patch("common.os.write", side_effect=lambda fd, data: write(fd, data[:7])):
                with JsonlWriter(fd=output.fileno()) as writer:
                    record = writer.write("ACTIVE_FENCED", event_id="e1")
            output.seek(0)
            self.assertEqual(json.loads(output.read()), record)

    def test_memory_log_limit_rejects_overflow_without_partial_record(self):
        with tempfile.TemporaryFile() as output:
            with JsonlWriter(fd=output.fileno(), max_bytes=128) as writer:
                first = writer.write("READY")
                with self.assertRaisesRegex(BufferError, "log buffer"):
                    writer.write("TOO_LARGE", value="x" * 128)
            output.seek(0)
            self.assertEqual([json.loads(line) for line in output], [first])

    def test_inherited_log_propagates_write_failure(self):
        with tempfile.TemporaryFile() as output:
            with JsonlWriter(fd=output.fileno()) as writer:
                with patch("common.os.write", side_effect=OSError("write failed")):
                    with self.assertRaisesRegex(OSError, "write failed"):
                        writer.write("ACTIVE_FENCED")


if __name__ == "__main__":
    unittest.main()
