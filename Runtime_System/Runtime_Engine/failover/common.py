#!/usr/bin/env python3

import json
import os
import time
from pathlib import Path


def monotonic_raw_ns():
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)


def parse_proc_start_ticks(stat_line):
    close_paren = stat_line.rfind(")")
    if close_paren < 0:
        raise ValueError("invalid /proc/PID/stat line")
    fields_after_comm = stat_line[close_paren + 2 :].split()
    if len(fields_after_comm) <= 19:
        raise ValueError("short /proc/PID/stat line")
    return int(fields_after_comm[19])


def read_proc_start_ticks(pid):
    stat_line = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return parse_proc_start_ticks(stat_line)


def process_matches(pid, start_ticks, container_id=None):
    try:
        if read_proc_start_ticks(pid) != start_ticks:
            return False
        if container_id:
            cgroup = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8")
            if container_id not in cgroup:
                return False
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False
    return True


class JsonlWriter:
    def __init__(self, path=None, *, fd=None, max_bytes=None):
        if (path is None) == (fd is None):
            raise ValueError("provide exactly one log path or descriptor")
        self.path = Path(path) if path is not None else None
        self.max_bytes = max_bytes
        self.bytes_written = 0
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fd = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o644,
            )
        else:
            self.fd = os.dup(fd)

    def write(self, event, **fields):
        record = {
            "event": event,
            "ts_raw_ns": monotonic_raw_ns(),
            **fields,
        }
        encoded = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        if (
            self.max_bytes is not None
            and self.bytes_written + len(encoded) > self.max_bytes
        ):
            raise BufferError("agent log buffer limit exceeded")
        remaining = memoryview(encoded)
        while remaining:
            written = os.write(self.fd, remaining)
            if written <= 0:
                raise OSError("log write made no progress")
            self.bytes_written += written
            remaining = remaining[written:]
        return record

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
