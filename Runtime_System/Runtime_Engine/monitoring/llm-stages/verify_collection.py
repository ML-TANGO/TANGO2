"""Independently compare the live collector with raw AGX timestamps and counts."""

import argparse
import collections
import json
import math
import pathlib
import re
import statistics
import tarfile
import urllib.request

from exporter import HISTOGRAM_DIMENSIONS, WINDOW_SECONDS
from metrics import CASES, MODES, STATUSES, CPU_KINDS, CPU_SCOPES, CPU_STATUSES


def cpu_reference(record):
    """Recompute raw counter differences without using the collector's parser."""
    cpu = record.get("cpu_observation")
    if "cpu_observation" not in record:
        return "legacy", {}, set()
    if (not isinstance(cpu, dict) or type(cpu.get("schema_version")) is not int
            or cpu.get("schema_version") != 1
            or cpu.get("method") != "thread_clock_schedstat"
            or cpu.get("scope") != "instrumented_threads"
            or type(cpu.get("enabled")) is not bool):
        return "invalid", {}, set()
    if not cpu["enabled"]:
        return "disabled", {}, set()
    b, e, threads = record.get("b_ns"), record.get("e_ns"), cpu.get("threads")
    if (record.get("mode") != "detail" or not isinstance(threads, dict)
            or type(b) is not int or type(e) is not int or not 0 < b <= e):
        return "invalid", {}, set()
    values, missing, invalid = {}, set(), False
    valid_threads = {name: value for name, value in threads.items()
        if isinstance(value, dict) and value.get("identity_error") == ""
        and all(type(value.get(key)) is int and value[key] > 0
                for key in ("pid", "tid", "starttime_ticks"))}
    same_process_distinct_threads = True
    if "worker" in valid_threads and "consumer" in valid_threads:
        same_process_distinct_threads = (valid_threads["worker"]["pid"] == valid_threads["consumer"]["pid"]
            and valid_threads["worker"]["tid"] != valid_threads["consumer"]["tid"])
    chain = []
    worker_points = threads.get("worker", {}).get("snapshots", {}) if isinstance(threads.get("worker"), dict) else {}
    if isinstance(worker_points, dict):
        for name in ("request_begin", "input_begin", "input_end", "prefill_begin", "prefill_end", "request_end"):
            point = worker_points.get(name)
            if isinstance(point, dict) and type(point.get("boundary_ns")) is int:
                chain.append(point["boundary_ns"])
    ordered_worker = len(chain) == 6 and chain == sorted(chain) and b <= chain[0] <= chain[-1] <= e
    for scope, (role, begin_name, end_name) in CPU_SCOPES.items():
        thread = threads.get(role, {})
        identity_error = thread.get("identity_error") if isinstance(thread, dict) else None
        valid_identity = (isinstance(thread, dict) and identity_error == ""
            and all(type(thread.get(key)) is int and thread[key] > 0
                    for key in ("pid", "tid", "starttime_ticks")))
        if not valid_identity:
            missing.update((scope, kind) for kind in CPU_KINDS)
            invalid = invalid or not (isinstance(identity_error, str) and identity_error)
            continue
        if not same_process_distinct_threads or (role == "worker" and not ordered_worker):
            missing.update((scope, kind) for kind in CPU_KINDS)
            invalid = True
            continue
        snapshots = thread.get("snapshots")
        endpoints = [snapshots.get(name) for name in (begin_name, end_name)] \
            if isinstance(snapshots, dict) else [None, None]
        clock_ok = all(isinstance(point, dict) and all(type(point.get(key)) is int
                       for key in ("boundary_ns", "read_begin_ns", "read_end_ns"))
                       for point in endpoints)
        if clock_ok:
            start, end = endpoints
            clock_ok = (all(b <= point["boundary_ns"] <= e
                            and point["boundary_ns"] <= point["read_begin_ns"] <= point["read_end_ns"]
                            for point in endpoints)
                        and start["boundary_ns"] <= end["boundary_ns"]
                        and start["read_end_ns"] <= end["read_begin_ns"])
            if scope == "consumer_request":
                clock_ok = clock_ok and [point["boundary_ns"] for point in endpoints] == [b, e]
            if scope in ("input", "prefill_prepare", "prefill_host"):
                host = record["stages_ns"].get(scope) if isinstance(record.get("stages_ns"), dict) else None
                clock_ok = clock_ok and type(host) is int and host == end["boundary_ns"]-start["boundary_ns"]
        if not clock_ok:
            missing.update((scope, kind) for kind in CPU_KINDS)
            invalid = True
            continue
        for kind, error_key in (("on_cpu", "runtime_error"), ("runqueue_wait", "wait_error")):
            counters = []
            for point in endpoints:
                number, error = point.get(kind+"_ns"), point.get(error_key)
                if number is None and isinstance(error, str) and error:
                    missing.add((scope, kind))
                    break
                if type(number) is not int or number < 0 or error != "":
                    missing.add((scope, kind))
                    invalid = True
                    break
                counters.append(number)
            if len(counters) == 2:
                elapsed = endpoints[1]["read_end_ns"]-endpoints[0]["read_begin_ns"]
                difference = counters[1]-counters[0]
                if not 0 <= difference <= elapsed:
                    missing.add((scope, kind))
                    invalid = True
                else:
                    values[scope, kind] = difference/1_000_000_000
    return ("invalid" if invalid else "complete" if not missing else
            "partial" if values else "unavailable"), values, missing


def records(root):
    """Read loose records and rotated continuous observations without extraction."""
    for path in root.glob("*/requests/*.json"):
        yield json.loads(path.read_text())
    for path in (root.parent/"continuous-archives").glob("continuous-*.tar.gz"):
        with tarfile.open(path) as archive:
            for member in archive:
                if member.isfile() and "/requests/" in member.name and member.name.endswith(".json"):
                    yield json.load(archive.extractfile(member))


def verify(root, endpoint):
    text = urllib.request.urlopen(endpoint, timeout=5).read().decode()
    samples = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        metric, value = line.rsplit(" ", 1)
        name, _, tail = metric.partition("{")
        tags = dict(re.findall(r'(\w+)="([^"]*)"', tail))
        samples[name, tuple(sorted(tags.items()))] = float(value)

    errors = []

    def actual(name, **tags):
        return samples.get(("tango2_llm_"+name, tuple(sorted(tags.items()))))

    def required(name, **tags):
        value = actual(name, **tags)
        if value is None:
            errors.append(f"missing metric: {name} {tags}" if tags else f"missing metric: {name}")
        return value

    epoch = required("collector_epoch_seconds")
    if epoch is None:
        epoch = 0
    expected = collections.defaultdict(list)
    window = collections.defaultdict(list)
    window_requests = collections.Counter()
    cpu_statuses, cpu_missing = collections.Counter(), collections.Counter()
    cpu_window = collections.defaultdict(list)
    window_end = required("window_end_timestamp_seconds")
    statuses, tokens = collections.Counter(), collections.Counter()
    invalid = 0
    requests = 0
    seen = {}
    for r in records(root):
        identity = r["run_id"], r["request_id"]
        if identity in seen:
            if seen[identity] != r:
                errors.append(f"conflicting raw record: {identity}")
            continue
        seen[identity] = r
        if (r["completed_utc_ns"]/1e9 < epoch
                or (window_end is not None and r["completed_utc_ns"] > window_end*1e9)):
            continue
        case, mode = r["case"], r["mode"]
        if not r["valid"]:
            invalid += 1
        if mode != "baseline":
            statuses[case, mode, r["status"]] += 1
            tokens[case, mode, "input"] += r["input_tokens"]
            tokens[case, mode, "output"] += r["output_tokens"]
            cpu_status, cpu_values, missing = cpu_reference(r)
            cpu_statuses[cpu_status] += 1
            cpu_missing.update(missing)
        if not r["valid"] or r["status"] not in ("eos", "length") or r["warmup"] or mode == "baseline":
            continue
        requests += 1
        values = {"queue": (r["b_ns"]-r["a_ns"])/1e9,
                  "e2e": (r["e_ns"]-r["a_ns"])/1e9}
        if r["g1_ns"] is not None:
            values["ttft"] = (r["g1_ns"]-r["a_ns"])/1e9
        if r["v1_ns"] is not None:
            values["first_text"] = (r["v1_ns"]-r["a_ns"])/1e9
        if r["output_tokens"] >= 2:
            values["generation"] = (r["gN_ns"]-r["g1_ns"])/1e9
            values["tpot"] = values["generation"]/(r["output_tokens"]-1)
        values.update({k: v/1e9 for k, v in r["stages_ns"].items()})
        values.update({"gpu_"+k: v/1000 for k, v in r["gpu_ms"].items()})
        for stage, value in values.items():
            expected[case, mode, stage].append(value)
        intervals = [(b-a)/1e9 for a, b in zip(r["token_ns"], r["token_ns"][1:])]
        expected[case, mode, "itl"].extend(intervals)
        if window_end is not None and (window_end-WINDOW_SECONDS)*1e9 < r["completed_utc_ns"] <= window_end*1e9:
            window_requests[case, mode] += 1
            for stage, value in values.items():
                window[case, mode, stage].append(value)
            window[case, mode, "itl"].extend(intervals)
            window[case, mode, "output_tokens"].append(r["output_tokens"])
            if r["output_tokens"] >= 2:
                window[case, mode, "decode_tokens_per_second"].append(
                    (r["output_tokens"]-1)*1e9/(r["gN_ns"]-r["g1_ns"]))
            if r["gpu_ms"].get("prefill", 0) > 0:
                window[case, mode, "prefill_input_tokens_per_second"].append(
                    r["input_tokens"]*1000/r["gpu_ms"]["prefill"])
            if mode == "detail":
                for (scope, kind), value in cpu_values.items():
                    cpu_window[case, scope, kind].append(value)

    compared_window = 0
    for case in CASES:
        for mode in MODES:
            if mode != "baseline" and required("window_requests", case=case, mode=mode) != window_requests[case, mode]:
                errors.append(f"window request mismatch: {case} {mode}")
    expected_window_statistics = {}
    expected_window_samples = {}
    for (case, mode, stage), values in window.items():
        if not values:
            continue
        # The independent check uses the standard library's inclusive quantiles.
        p95 = statistics.quantiles(values, n=100, method="inclusive")[94] if len(values) > 1 else values[0]
        expected_statistics = dict(p50=statistics.median(values), p95=p95)
        if stage in ("ttft", "e2e"):
            expected_statistics.update(min=min(values), max=max(values))
        tags = dict(case=case, mode=mode, stage=stage)
        sample_tags = tuple(sorted(tags.items()))
        name = "window_duration_seconds"
        if stage == "output_tokens":
            name = "window_output_tokens"
            tags.pop("stage")
        elif stage.endswith("_tokens_per_second"):
            name = "window_rate"
        expected_window_samples[sample_tags] = len(values)
        for statistic, expected_value in expected_statistics.items():
            statistic_tags = tuple(sorted(dict(tags, statistic=statistic).items()))
            expected_window_statistics[name, statistic_tags] = expected_value
            observed = required(name, **dict(statistic_tags))
            if observed is not None and not math.isclose(observed, expected_value, rel_tol=1e-9, abs_tol=1e-12):
                errors.append(f"window value mismatch: {name} {tags} {statistic}")
            compared_window += 1
    observed_window_statistics = {
        (name.removeprefix("tango2_llm_"), tags)
        for name, tags in samples
        if name in ("tango2_llm_window_duration_seconds", "tango2_llm_window_output_tokens",
                    "tango2_llm_window_rate")
    }
    for name, tags in observed_window_statistics - set(expected_window_statistics):
        errors.append(f"unexpected window statistic: {name} {dict(tags)}")
    observed_window_samples = {
        tags for name, tags in samples if name == "tango2_llm_window_samples"
    }
    for tags in observed_window_samples - set(expected_window_samples):
        errors.append(f"unexpected window samples: {dict(tags)}")
    for tags, expected_count in expected_window_samples.items():
        observed = required("window_samples", **dict(tags))
        if observed is not None and observed != expected_count:
            errors.append(f"window sample mismatch: {dict(tags)}")
    duration_dimensions = {
        tags for name, tags in samples
        if name in ("tango2_llm_duration_seconds_count", "tango2_llm_duration_seconds_sum")
    }
    required_duration_dimensions = {
        tuple(sorted(dict(case=case, mode=mode, stage=stage).items()))
        for case, mode, stage in HISTOGRAM_DIMENSIONS
    }
    expected_duration_dimensions = {
        tuple(sorted(dict(case=case, mode=mode, stage=stage).items()))
        for case, mode, stage in expected
    }
    for dimension in duration_dimensions | required_duration_dimensions | expected_duration_dimensions:
        tags = dict(dimension)
        if dimension not in required_duration_dimensions:
            errors.append(f"unexpected duration dimension: {tags}")
        values = expected.get((tags["case"], tags["mode"], tags["stage"]), []) \
            if set(tags) == {"case", "mode", "stage"} else []
        count = required("duration_seconds_count", **tags)
        if count is not None and count != len(values):
            errors.append(f"count mismatch: {tags}")
        total = sum(values)
        exported_total = required("duration_seconds_sum", **tags)
        if exported_total is not None and abs(exported_total-total) > max(total*.001, .0001):
            errors.append(f"sum mismatch: {tags}")
    for case in CASES:
        for mode in MODES:
            for status in STATUSES:
                count = statuses[case, mode, status]
                exported = required("requests_completed_total", case=case, mode=mode, status=status)
                if exported is not None and exported != count:
                    errors.append(f"status mismatch: {case} {mode} {status}")
            for kind in ("input", "output"):
                count = tokens[case, mode, kind]
                exported = required("tokens_total", case=case, mode=mode, kind=kind)
                if exported is not None and exported != count:
                    errors.append(f"token mismatch: {case} {mode} {kind}")
    invalid_records = required("records_invalid_total")
    if invalid_records is not None and invalid_records != invalid:
        errors.append("invalid count mismatch")
    pending = required("pending_records")
    parse_errors = required("records_parse_errors_total")
    duplicates = required("records_duplicate_total")
    if pending or parse_errors or duplicates:
        errors.append("pending, parsing, or duplicate records")
    expected_cpu_statistics = set()
    expected_cpu_samples = set()
    compared_cpu = 0
    for status in CPU_STATUSES:
        if required("cpu_observations_total", status=status) != cpu_statuses[status]:
            errors.append(f"CPU observation status mismatch: {status}")
    for scope in CPU_SCOPES:
        for kind in CPU_KINDS:
            if required("cpu_samples_unavailable_total", scope=scope, kind=kind) != cpu_missing[scope, kind]:
                errors.append(f"CPU unavailable count mismatch: {scope} {kind}")
            for case in CASES:
                values = cpu_window[case, scope, kind]
                tags = dict(case=case, mode="detail", scope=scope, kind=kind)
                expected_cpu_samples.add(tuple(sorted(tags.items())))
                if required("cpu_window_samples", **tags) != len(values):
                    errors.append(f"CPU window sample mismatch: {tags}")
                if not values:
                    continue
                statistics_by_name = dict(p50=statistics.median(values),
                    p95=statistics.quantiles(values, n=100, method="inclusive")[94]
                    if len(values) > 1 else values[0])
                for name, expected_value in statistics_by_name.items():
                    dimension = tuple(sorted(dict(tags, statistic=name).items()))
                    expected_cpu_statistics.add(dimension)
                    observed = required("cpu_window_seconds", **dict(dimension))
                    if observed is not None and not math.isclose(observed, expected_value,
                                                                rel_tol=1e-9, abs_tol=1e-12):
                        errors.append(f"CPU window value mismatch: {dict(dimension)}")
                    compared_cpu += 1
    actual_cpu_statistics = {tags for name, tags in samples if name == "tango2_llm_cpu_window_seconds"}
    for tags in actual_cpu_statistics-expected_cpu_statistics:
        errors.append(f"unexpected CPU window statistic: {dict(tags)}")
    for name, tags in samples:
        if name == "tango2_llm_cpu_window_samples" and tags not in expected_cpu_samples:
            errors.append(f"unexpected CPU window sample dimension: {dict(tags)}")
    if len(samples) > 5000:
        errors.append("active series exceeds 5000")
    return dict(pass_gate=not errors, epoch_seconds=epoch, normal_requests=requests,
                compared_window_statistics=compared_window,
                compared_histograms=len(duration_dimensions | required_duration_dimensions
                                        | expected_duration_dimensions),
                compared_cpu_statistics=compared_cpu, cpu_status_counts=dict(cpu_statuses),
                cpu_observation_complete=cpu_statuses["complete"] > 0 and not any(
                    cpu_statuses[status] for status in ("partial", "unavailable", "invalid")),
                active_series=len(samples), errors=errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:9464/metrics")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.endpoint)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))
    raise SystemExit(not result["pass_gate"])
