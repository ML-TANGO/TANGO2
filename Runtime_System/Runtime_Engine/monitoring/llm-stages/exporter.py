#!/usr/bin/env python3
"""Expose validated immutable AGX request records using classic text metrics."""

import argparse
import collections
import http.server
import json
import math
import os
import pathlib
import threading
import time

from metrics import (CASES, MODES, STAGES, STATUSES, CPU_KINDS, CPU_SCOPES, CPU_STATUSES,
                     aggregate_cpu_observation, aggregate_request, diagnostic_dimensions)

BOUNDS = (.0001, .0005, .001, .002, .005, .01, .02, .05, .1, .2,
          .5, 1., 2., 5., 10., 20., 60., math.inf)
OUTPUT_BOUNDS = (0, 1, 2, 4, 8, 16, 32, 64, 128, math.inf)
RUN_METADATA_LIMIT = 64
LATEST_MAX_AGE_SECONDS = 10
WINDOW_SECONDS = 300
HISTOGRAM_STAGES = ("queue", "e2e", "ttft", "first_text", "generation", "tpot", "itl",
                    *STAGES, "gpu_prefill", "gpu_decode")
HISTOGRAM_DIMENSIONS = tuple((case, mode, stage)
    for case in CASES for mode in ("live", "detail") for stage in HISTOGRAM_STAGES
    if mode == "detail" or not stage.startswith("gpu_"))
PREFIX = "tango2_llm_"


def labels(values):
    return "{" + ",".join(f"{key}={json.dumps(str(value))}"
                          for key, value in sorted(values.items())) + "}"


class Store:
    """A collector restart starts a new epoch, never replays old completions."""

    def __init__(self, epoch_ns=None):
        self.epoch_ns = time.time_ns() if epoch_ns is None else epoch_ns
        self.seen = set()
        self.histograms = {key: ([0]*len(BOUNDS), 0., 0) for key in HISTOGRAM_DIMENSIONS}
        self.latest = {}
        self.maximum = {}
        self.current_run = None
        self.current_run_start = -1
        self.run_starts = {}
        self.run_metadata = {}
        self.statuses = collections.Counter({(case, mode, status): 0
                                             for case in CASES for mode in MODES
                                             for status in STATUSES})
        self.tokens = collections.Counter({(case, mode, kind): 0
                                           for case in CASES for mode in MODES
                                           for kind in ("input", "output")})
        self.output_lengths = {(case, mode): ([0]*len(OUTPUT_BOUNDS), 0., 0)
                               for case in CASES for mode in MODES if mode != "baseline"}
        self.invalid = self.duplicates = self.parse_errors = 0
        self.latest_completed = {}
        self.window_records = collections.defaultdict(list)
        self.cpu_statuses = collections.Counter({status: 0 for status in CPU_STATUSES})
        self.cpu_unavailable = collections.Counter({(scope, kind): 0
            for scope in CPU_SCOPES for kind in CPU_KINDS})
        self.cpu_window_records = collections.defaultdict(list)

    def begin_run(self, run_id, started_utc_ns, metadata=None):
        if not isinstance(run_id, str) or not isinstance(started_utc_ns, int):
            return
        self.run_starts[run_id] = started_utc_ns
        if metadata is not None:
            self.run_metadata[run_id] = metadata
        if started_utc_ns >= self.current_run_start:
            if run_id != self.current_run:
                self.latest.clear()
                self.maximum.clear()
                self.latest_completed.clear()
            self.current_run, self.current_run_start = run_id, started_utc_ns

    def _histogram(self, key):
        return self.histograms.setdefault(key, ([0]*len(BOUNDS), 0., 0))

    def ingest(self, record):
        if not isinstance(record, dict):
            self.parse_errors += 1
            return
        completed = record.get("completed_utc_ns")
        if not isinstance(completed, int):
            self.parse_errors += 1
            return
        if completed < self.epoch_ns:
            return
        if not isinstance(record.get("run_id"), str) or not isinstance(record.get("request_id"), str):
            self.parse_errors += 1
            return
        key = record["run_id"], record["request_id"]
        if key in self.seen:
            self.duplicates += 1
            return
        self.seen.add(key)
        try:
            case, mode, status = diagnostic_dimensions(record)
            if not record["valid"]:
                self.invalid += 1
            if mode == "baseline":
                return
            self.begin_run(record["run_id"], self.run_starts.get(record["run_id"], completed))
            self.statuses[case, mode, status] += 1
            for kind in ("input", "output"):
                self.tokens[case, mode, kind] += record[kind+"_tokens"]
            values = aggregate_request(record)
        except (KeyError, TypeError, ValueError):
            self.invalid += 1
            return
        cpu = aggregate_cpu_observation(record)
        self.cpu_statuses[cpu["status"]] += 1
        self.cpu_unavailable.update(cpu["issues"].keys())
        if record["warmup"]:
            return
        if values is None:
            return
        self.window_records[case, mode].append((completed, dict(values, output_tokens=record["output_tokens"])))
        if mode == "detail" and cpu["values"]:
            self.cpu_window_records[case].append((completed, cpu["values"]))
        buckets, total, count = self.output_lengths[case, mode]
        output = record["output_tokens"]
        for index, bound in enumerate(OUTPUT_BOUNDS):
            buckets[index] += output <= bound
        self.output_lengths[case, mode] = buckets, total+output, count+1
        is_current = record["run_id"] == self.current_run
        if is_current:
            self.latest = {key: value for key, value in self.latest.items()
                           if key[:2] != (case, mode)}
            self.latest_completed[case, mode] = completed/1e9
        for stage, value in values.items():
            if stage in ("decode_tokens_per_second", "prefill_input_tokens_per_second"):
                if is_current:
                    self.latest[case, mode, stage] = value
                continue
            samples = value if stage == "itl" else [value]
            key = case, mode, stage
            buckets, total, count = self._histogram(key)
            for sample in samples:
                for index, bound in enumerate(BOUNDS):
                    buckets[index] += sample <= bound
                total += sample
                count += 1
                if is_current:
                    self.latest[key] = sample
                    self.maximum[key] = max(sample, self.maximum.get(key, 0))
            if samples:
                self.histograms[key] = buckets, total, count

    def render(self, heartbeat):
        now = time.time()
        lines = ["# TYPE "+PREFIX+name+" "+kind for name, kind in (
            ("duration_seconds", "histogram"), ("output_tokens", "histogram"),
            ("requests_completed_total", "counter"), ("tokens_total", "counter"),
            ("records_invalid_total", "counter"), ("records_duplicate_total", "counter"),
            ("records_parse_errors_total", "counter"),
            ("window_duration_seconds", "gauge"), ("window_requests", "gauge"),
            ("window_samples", "gauge"),
            ("window_output_tokens", "gauge"), ("window_rate", "gauge"),
            ("cpu_observations_total", "counter"), ("cpu_samples_unavailable_total", "counter"),
            ("cpu_window_seconds", "gauge"), ("cpu_window_samples", "gauge"))]

        def emit(name, value, **tags):
            if isinstance(value, float) and math.isinf(value):
                value = "+Inf" if value > 0 else "-Inf"
            lines.append(PREFIX+name+labels(tags)+" "+str(value))

        emit("collector_epoch_seconds", self.epoch_ns/1e9)
        emit("records_invalid_total", self.invalid)
        emit("records_duplicate_total", self.duplicates)
        emit("records_parse_errors_total", self.parse_errors)
        emit("producer_up", heartbeat["up"])
        emit("producer_heartbeat_age_seconds", heartbeat["age"])
        emit("inflight", heartbeat["active"] if heartbeat["up"] else 0)
        for status, count in sorted(self.cpu_statuses.items()):
            emit("cpu_observations_total", count, status=status)
        for (scope, kind), count in sorted(self.cpu_unavailable.items()):
            emit("cpu_samples_unavailable_total", count, scope=scope, kind=kind)
        for (case, mode, status), count in sorted(self.statuses.items()):
            emit("requests_completed_total", count, case=case, mode=mode, status=status)
        for (case, mode, kind), count in sorted(self.tokens.items()):
            emit("tokens_total", count, case=case, mode=mode, kind=kind)
        for (case, mode), (buckets, total, count) in sorted(self.output_lengths.items()):
            for bound, value in zip(OUTPUT_BOUNDS, buckets):
                emit("output_tokens_bucket", value, case=case, mode=mode,
                     le="+Inf" if math.isinf(bound) else str(bound))
            emit("output_tokens_sum", total, case=case, mode=mode)
            emit("output_tokens_count", count, case=case, mode=mode)
        for (case, mode, stage), (buckets, total, count) in sorted(self.histograms.items()):
            tags = dict(case=case, mode=mode, stage=stage)
            for bound, value in zip(BOUNDS, buckets):
                emit("duration_seconds_bucket", value, le="+Inf" if math.isinf(bound) else str(bound), **tags)
            emit("duration_seconds_sum", total, **tags)
            emit("duration_seconds_count", count, **tags)
        self.render_window(now, emit)
        self.render_cpu_window(now, emit)
        fresh_latest = {
            (case, mode) for (case, mode), completed in self.latest_completed.items()
            if 0 <= now-completed <= LATEST_MAX_AGE_SECONDS
        }
        for case, mode in sorted(fresh_latest):
            emit("last_completed_timestamp_seconds", self.latest_completed[case, mode],
                 case=case, mode=mode)
        if heartbeat["up"]:
            # Run gauges are cleared together at every explicit new run boundary.
            for (case, mode, stage), value in sorted(self.latest.items()):
                if (case, mode) not in fresh_latest:
                    continue
                if stage == "decode_tokens_per_second":
                    name = "latest_decode_tokens_per_second"
                elif stage == "prefill_input_tokens_per_second":
                    name = "latest_prefill_input_tokens_per_second"
                else:
                    name = "latest_duration_seconds"
                emit(name, value, case=case, mode=mode, stage=stage)
        for (case, mode, stage), value in sorted(self.maximum.items()):
            emit("run_max_duration_seconds", value, case=case, mode=mode, stage=stage)
        recent = sorted(self.run_metadata.items(), key=lambda item: item[1].get("started_utc_ns", 0))[-RUN_METADATA_LIMIT:]
        for run_id, metadata in recent:
            tags = dict(run_id=run_id, mode=metadata.get("mode", "unknown"),
                        evidence_path=metadata.get("evidence_path", ""))
            for name in ("engine_path", "runtime_commit", "binary_sha256", "workload_sha256"):
                if metadata.get(name):
                    tags[name] = metadata[name]
            if isinstance(metadata.get("model_hashes"), dict):
                tags["model_identity"] = json.dumps(metadata["model_hashes"], sort_keys=True,
                                                    separators=(",", ":"))
            emit("run_info", 1, **tags)
            for event, timestamp in (("start", metadata.get("started_utc_ns")),
                                     ("complete", metadata.get("completed_utc_ns"))):
                if isinstance(timestamp, int):
                    emit("run_boundary_timestamp_seconds", timestamp/1e9, event=event, **tags)
        return "\n".join(lines)+"\n"

    def render_window(self, now, emit):
        """Exact inclusive-rank interpolation over eligible completions in (now-300s, now]."""
        self.expire_window(now)
        now_ns = int(now*1e9)
        emit("window_end_timestamp_seconds", now)
        for case in CASES:
            for mode in MODES:
                if mode == "baseline":
                    continue
                key = case, mode
                records = [values for stamp, values in self.window_records[key] if stamp <= now_ns]
                emit("window_requests", len(records), case=case, mode=mode)
                stages = collections.defaultdict(list)
                for values in records:
                    for stage, value in values.items():
                        stages[stage].extend(value if stage == "itl" else [value])
                for stage, values in sorted(stages.items()):
                    if not values:
                        continue
                    emit("window_samples", len(values), case=case, mode=mode, stage=stage)
                    ordered = sorted(values)
                    statistics = {}
                    for name, quantile in (("p50", .5), ("p95", .95)):
                        rank = (len(ordered)-1)*quantile
                        lower, upper = math.floor(rank), math.ceil(rank)
                        statistics[name] = ordered[lower]+(ordered[upper]-ordered[lower])*(rank-lower)
                    if stage in ("ttft", "e2e"):
                        statistics.update(min=ordered[0], max=ordered[-1])
                    tags = dict(case=case, mode=mode, stage=stage)
                    if stage == "output_tokens":
                        metric = "window_output_tokens"
                        tags.pop("stage")
                    elif stage.endswith("_tokens_per_second"):
                        metric = "window_rate"
                    else:
                        metric = "window_duration_seconds"
                    for name, value in statistics.items():
                        emit(metric, value, statistic=name, **tags)

    def expire_window(self, now):
        cutoff = int((now-WINDOW_SECONDS)*1e9)
        for key, records in self.window_records.items():
            self.window_records[key] = [(stamp, values) for stamp, values in records if stamp > cutoff]
        for key, records in self.cpu_window_records.items():
            self.cpu_window_records[key] = [(stamp, values) for stamp, values in records if stamp > cutoff]

    def render_cpu_window(self, now, emit):
        """CPU scope distributions use bounded gauges, never per-TID histograms."""
        now_ns = int(now*1e9)
        for case in CASES:
            samples = collections.defaultdict(list)
            for completed, values in self.cpu_window_records[case]:
                if completed <= now_ns:
                    for key, value in values.items():
                        samples[key].append(value)
            for scope in CPU_SCOPES:
                for kind in CPU_KINDS:
                    values = sorted(samples[scope, kind])
                    tags = dict(case=case, mode="detail", scope=scope, kind=kind)
                    emit("cpu_window_samples", len(values), **tags)
                    for name, quantile in (("p50", .5), ("p95", .95)):
                        if values:
                            rank = (len(values)-1)*quantile
                            lower, upper = math.floor(rank), math.ceil(rank)
                            value = values[lower]+(values[upper]-values[lower])*(rank-lower)
                            emit("cpu_window_seconds", value, statistic=name, **tags)


def heartbeat_state(path):
    try:
        record = json.loads(path.read_text())
        age = max(0., (time.monotonic_ns()-record["monotonic_ns"])/1e9)
        os.kill(record["pid"], 0)
        return dict(up=int(age < 5), age=age, active=int(record["active"]))
    except (OSError, ValueError, KeyError):
        return dict(up=0, age=math.inf, active=0)


class Collector:
    def __init__(self, root, heartbeat):
        self.root, self.heartbeat = root, heartbeat
        self.store, self.processed = Store(), set()
        self.lock = threading.Lock()
        self.sensors = Sensors()
        self.worker_failed = 0
        self.manifest_versions = {}

    def register_runs(self):
        for path in self.root.glob("*/manifest.json"):
            try:
                completion = path.with_name("completion.json")
                version = (path.stat().st_mtime_ns,
                           completion.stat().st_mtime_ns if completion.exists() else 0)
                if self.manifest_versions.get(path) == version:
                    continue
                manifest = json.loads(path.read_text())
                if not isinstance(manifest, dict):
                    raise ValueError("manifest is not an object")
                run_id, mode = manifest["run_id"], manifest["mode"]
                started = manifest["started_utc_ns"]
                if mode not in MODES:
                    raise ValueError("invalid mode")
                metadata = dict(manifest, evidence_path=str(path.parent))
                if completion.exists():
                    finished = json.loads(completion.read_text())
                    if isinstance(finished, dict) and finished.get("run_id") == run_id:
                        metadata["completed_utc_ns"] = finished.get("completed_utc_ns")
                self.store.begin_run(run_id, started, metadata)
                self.manifest_versions[path] = version
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self.store.parse_errors += 1

    @staticmethod
    def acknowledge(path):
        acknowledgment = path.parents[1]/"acknowledged"/path.name
        acknowledgment.parent.mkdir(exist_ok=True)
        temporary = acknowledgment.with_suffix(".json.tmp")
        try:
            with temporary.open("w") as stream:
                json.dump({"request": path.name, "acknowledged_utc_ns": time.time_ns()}, stream)
                stream.write("\n")
            os.link(temporary, acknowledgment)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)

    def scan(self):
        with self.lock:
            self.sensors.sample()
            self.register_runs()
            # Sort by completion time so current-run gauges cannot move backwards.
            pending = []
            for path in self.root.glob("*/requests/*.json"):
                if path in self.processed:
                    continue
                try:
                    record = json.loads(path.read_text())
                    if not isinstance(record, dict) or not isinstance(record.get("completed_utc_ns"), int):
                        raise ValueError("invalid record shape or completion timestamp")
                    pending.append((path, record))
                except (OSError, ValueError):
                    self.store.parse_errors += 1
                    self.processed.add(path)
            for path, record in sorted(pending, key=lambda item: item[1]["completed_utc_ns"]):
                try:
                    self.store.ingest(record)
                except (KeyError, TypeError, ValueError):
                    self.store.parse_errors += 1
                finally:
                    self.processed.add(path)
                    self.acknowledge(path)
            self.store.expire_window(time.time())

    def render(self):
        with self.lock:
            text = self.store.render(heartbeat_state(self.heartbeat))
            pending = sum(1 for path in self.root.glob("*/requests/*.json") if path not in self.processed)
            sensor_text = "".join(PREFIX+"device_"+name+" "+str(value)+"\n"
                                  for name, value in sorted(self.sensors.values.items()))
            return (text+PREFIX+"pending_records "+str(pending)+"\n"
                    +PREFIX+"collector_worker_failed "+str(self.worker_failed)+"\n"+sensor_text)


class Sensors:
    """Read existing sysfs sensors; unavailable sensors remain absent (N/A)."""

    def __init__(self):
        self.last_sample = 0
        self.previous_cpu = None
        self.values = {}
        self.paths = {}
        root = pathlib.Path("/sys/devices/platform/bus@0/17000000.gpu")
        self.paths["gpu_utilization_ratio"] = (root/"load", .001)
        self.paths["gpu_clock_hertz"] = (root/"devfreq/17000000.gpu/cur_freq", 1)
        self.paths["emc_clock_hertz"] = (pathlib.Path("/sys/devices/platform/bwmgr/devfreq/bwmgr/cur_freq"), 1)
        self.paths["cpu_clock_hertz"] = (pathlib.Path("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq"), 1000)
        for directory in pathlib.Path("/sys/class/thermal").glob("thermal_zone*"):
            try:
                kind = (directory/"type").read_text().strip().lower()
            except OSError:
                continue
            if kind in ("cpu-thermal", "gpu-thermal", "soc0-thermal"):
                self.paths[kind.split("-")[0]+"_temperature_celsius"] = (directory/"temp", .001)
        # AGX exposes separate rails; VDD_IN is the NX/Nano input measurement.
        # DDR/1V8AO is downstream of system 5V, so do not sum all AGX rails.
        power_names = {"VDD_IN": "input_power_watts",
                       "VDD_GPU_SOC": "gpu_soc_power_watts",
                       "VDD_CPU_CV": "cpu_cv_power_watts",
                       "VIN_SYS_5V0": "system_5v_power_watts",
                       "VDDQ_VDD2_1V8AO": "ddr_1v8ao_power_watts"}
        self.power = {}
        for label in pathlib.Path("/sys/class/hwmon").glob("hwmon*/in*_label"):
            try:
                rail = label.read_text().strip()
                if rail in power_names and (label.parent/"name").read_text().strip() == "ina3221":
                    index = label.name[2:].split("_")[0]
                    self.power[power_names[rail]] = (label.with_name("in"+index+"_input"),
                                                    label.with_name("curr"+index+"_input"))
            except OSError:
                continue

    def sample(self):
        now = time.monotonic()
        if now-self.last_sample < 1:
            return
        self.last_sample = now
        self.values.clear()
        for name, (path, factor) in self.paths.items():
            try:
                self.values[name] = float(path.read_text().strip())*factor
            except (OSError, ValueError):
                pass
        for name, (voltage, current) in self.power.items():
            try:
                # hwmon voltage is mV and current is mA; their product is uW.
                watts = float(voltage.read_text())*float(current.read_text())/1e6
                if math.isfinite(watts):
                    self.values[name] = watts
            except (OSError, ValueError):
                pass
        try:
            fields = pathlib.Path("/proc/stat").read_text().splitlines()[0].split()[1:9]
            ticks = list(map(int, fields))
            total, idle = sum(ticks), ticks[3]+ticks[4]
            if self.previous_cpu:
                dt = total-self.previous_cpu[0]
                if dt > 0:
                    self.values["cpu_utilization_ratio"] = 1-(idle-self.previous_cpu[1])/dt
            self.previous_cpu = total, idle
            memory = {line.split(":")[0]: int(line.split()[1])*1024
                      for line in pathlib.Path("/proc/meminfo").read_text().splitlines()}
            self.values["memory_used_bytes"] = memory["MemTotal"]-memory["MemAvailable"]
        except (OSError, ValueError, KeyError):
            pass


def serve(root, heartbeat, bind, port):
    collector = Collector(root, heartbeat)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/metrics":
                self.send_error(404)
                return
            payload = collector.render().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer((bind, port), Handler)
    stopped = threading.Event()

    def poll():
        while not stopped.is_set():
            try:
                collector.scan()
            except BaseException:
                collector.worker_failed = 1
            stopped.wait(.05)

    worker = threading.Thread(target=poll, daemon=True)
    worker.start()
    try:
        server.serve_forever()
    finally:
        stopped.set()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--heartbeat", type=pathlib.Path, default=pathlib.Path("/dev/shm/tango2-llm-heartbeat.json"))
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9464)
    args = parser.parse_args()
    serve(args.root, args.heartbeat, args.bind, args.port)
