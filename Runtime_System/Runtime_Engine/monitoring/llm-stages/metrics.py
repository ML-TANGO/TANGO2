"""Validated request summaries shared by the exporter and offline audit."""

import math

CASES = tuple(f"i{i}_o{o}" for i in (64, 256, 1024) for o in (64, 128))
MODES = ("baseline", "live", "detail")
STATUSES = ("eos", "length", "cancelled", "timeout", "error")
STAGES = ("input", "prefill_prepare", "prefill_host", "detokenize", "deliver", "host_remainder")
CPU_SCOPES = {
    "worker_request": ("worker", "request_begin", "request_end"),
    "consumer_request": ("consumer", "request_begin", "request_end"),
    "input": ("worker", "input_begin", "input_end"),
    "prefill_prepare": ("worker", "input_end", "prefill_begin"),
    "prefill_host": ("worker", "prefill_begin", "prefill_end"),
    "decode_and_finalize": ("worker", "prefill_end", "request_end"),
}
CPU_KINDS = ("on_cpu", "runqueue_wait")
CPU_STATUSES = ("legacy", "disabled", "complete", "partial", "unavailable", "invalid")


def aggregate_cpu_observation(record):
    """Validate optional thread counters independently of latency eligibility."""
    result = dict(enabled=None, status="legacy", values={}, issues={}, errors=[])
    if "cpu_observation" not in record:
        return result
    cpu = record["cpu_observation"]
    malformed = False

    def issue(scope, kind, reason, invalid=False):
        nonlocal malformed
        malformed = malformed or invalid
        result["issues"][scope, kind] = reason
        result["errors"].append(f"{scope}/{kind}: {reason}")

    if (not isinstance(cpu, dict) or type(cpu.get("schema_version")) is not int
            or cpu.get("schema_version") != 1
            or cpu.get("method") != "thread_clock_schedstat"
            or cpu.get("scope") != "instrumented_threads"
            or type(cpu.get("enabled")) is not bool):
        result.update(status="invalid", errors=["invalid CPU observation contract"])
        return result
    result["enabled"] = cpu["enabled"]
    if not cpu["enabled"]:
        result["status"] = "disabled"
        return result
    threads = cpu.get("threads")
    b, e = record.get("b_ns"), record.get("e_ns")
    if (record.get("mode") != "detail" or not isinstance(threads, dict)
            or type(b) is not int or type(e) is not int or not 0 < b <= e):
        result.update(status="invalid", errors=["invalid CPU mode, threads, or request boundaries"])
        return result

    def identity_ok(thread):
        return (isinstance(thread, dict) and thread.get("identity_error") == ""
                and all(type(thread.get(key)) is int and thread[key] > 0
                        for key in ("pid", "tid", "starttime_ticks")))

    worker, consumer = threads.get("worker"), threads.get("consumer")
    conflicting_identity = (identity_ok(worker) and identity_ok(consumer)
        and (worker["pid"] != consumer["pid"] or worker["tid"] == consumer["tid"]))
    worker_chain_valid = False
    if isinstance(worker, dict) and isinstance(worker.get("snapshots"), dict):
        ordered = [worker["snapshots"].get(name) for name in
                   ("request_begin", "input_begin", "input_end", "prefill_begin",
                    "prefill_end", "request_end")]
        if all(isinstance(point, dict) and type(point.get("boundary_ns")) is int for point in ordered):
            boundaries = [point["boundary_ns"] for point in ordered]
            worker_chain_valid = b <= boundaries[0] and boundaries[-1] <= e and all(
                first <= last for first, last in zip(boundaries, boundaries[1:]))
    stages = record.get("stages_ns")
    for scope, (role, first, last) in CPU_SCOPES.items():
        thread = threads.get(role)
        identity_error = thread.get("identity_error") if isinstance(thread, dict) else None
        identity_valid = identity_ok(thread)
        if not identity_valid:
            reason = identity_error if isinstance(identity_error, str) and identity_error else "invalid thread identity"
            for kind in CPU_KINDS:
                issue(scope, kind, reason, not (isinstance(identity_error, str) and identity_error))
            continue
        if conflicting_identity or (role == "worker" and not worker_chain_valid):
            reason = "conflicting thread identities" if conflicting_identity else "invalid worker boundary chain"
            for kind in CPU_KINDS:
                issue(scope, kind, reason, True)
            continue
        snapshots = thread.get("snapshots", {})
        start, end = ((snapshots.get(first), snapshots.get(last))
                      if isinstance(snapshots, dict) else (None, None))
        # Reject mismatched stage attribution before considering either counter.
        valid_clock = True
        for sample in (start, end):
            if (not isinstance(sample, dict)
                    or any(type(sample.get(key)) is not int for key in
                           ("boundary_ns", "read_begin_ns", "read_end_ns"))):
                valid_clock = False
                break
            valid_clock = valid_clock and (b <= sample["boundary_ns"] <= e
                and sample["boundary_ns"] <= sample["read_begin_ns"] <= sample["read_end_ns"])
        if valid_clock:
            valid_clock = (start["boundary_ns"] <= end["boundary_ns"]
                           and start["read_end_ns"] <= end["read_begin_ns"])
            if scope == "consumer_request":
                valid_clock = valid_clock and (start["boundary_ns"] == b and end["boundary_ns"] == e)
            if scope in ("input", "prefill_prepare", "prefill_host"):
                duration = stages.get(scope) if isinstance(stages, dict) else None
                valid_clock = valid_clock and (type(duration) is int
                    and duration == end["boundary_ns"]-start["boundary_ns"])
        if not valid_clock:
            for kind in CPU_KINDS:
                issue(scope, kind, "invalid CPU snapshot boundaries or stage alignment", True)
            continue
        for kind, error_key in (("on_cpu", "runtime_error"), ("runqueue_wait", "wait_error")):
            counters = []
            for sample in (start, end):
                counter, error = sample.get(kind+"_ns"), sample.get(error_key)
                if counter is None and isinstance(error, str) and error:
                    issue(scope, kind, error)
                    break
                if type(counter) is not int or counter < 0 or error != "":
                    issue(scope, kind, "invalid CPU counter or availability", True)
                    break
                counters.append(counter)
            if len(counters) == 2:
                delta = counters[1]-counters[0]
                if delta < 0 or delta > end["read_end_ns"]-start["read_begin_ns"]:
                    issue(scope, kind, "CPU counter reversal or delta outside read interval", True)
                else:
                    result["values"][scope, kind] = delta/1e9
    result["status"] = ("invalid" if malformed else "complete" if not result["issues"]
                        else "partial" if result["values"] else "unavailable")
    return result


def diagnostic_dimensions(record):
    """Return trustworthy accounting dimensions, independent of eligibility."""
    if not isinstance(record, dict):
        raise ValueError("record is not an object")
    if (record.get("schema_version") != 1 or record.get("case") not in CASES
            or record.get("mode") not in MODES or record.get("status") not in STATUSES):
        raise ValueError("unknown schema, case, mode, or status")
    for name in ("input_tokens", "output_tokens"):
        if not isinstance(record.get(name), int) or record[name] < 0:
            raise ValueError("invalid token count")
    if not isinstance(record.get("warmup"), bool) or not isinstance(record.get("valid"), bool):
        raise ValueError("invalid request flags")
    return record["case"], record["mode"], record["status"]


def aggregate_request(record):
    """Return seconds/rates for eligible requests; reject corrupt measurements."""
    r = record
    diagnostic_dimensions(r)
    if not r["valid"] or r["warmup"] or r["status"] not in ("eos", "length"):
        return None
    a, b, e = (r[k] for k in ("a_ns", "b_ns", "e_ns"))
    n, times = r["output_tokens"], r["token_ns"]
    if (not isinstance(n, int) or n < 0 or r["input_tokens"] <= 0
            or not 0 < a <= b <= e):
        raise ValueError("invalid count or request boundary")
    if r["mode"] != "baseline" and len(times) != n:
        raise ValueError("token timestamp count mismatch")
    if any(not isinstance(t, int) or not b <= t <= e for t in times):
        raise ValueError("token timestamp outside request")
    if any(y <= x for x, y in zip(times, times[1:])):
        raise ValueError("non-increasing token timestamps")
    g1, gn = r["g1_ns"], r["gN_ns"]
    if n:
        if not (g1 is not None and gn is not None and b <= g1 <= gn <= e):
            raise ValueError("invalid generation boundaries")
        if times and (g1 != times[0] or gn != times[-1]):
            raise ValueError("generation boundaries do not match token set")
        if (n > 1 and gn <= g1) or (n == 1 and gn != g1):
            raise ValueError("invalid token interval")
    elif g1 is not None or gn is not None:
        raise ValueError("generation boundaries without tokens")
    result = {"queue": (b-a)/1e9, "e2e": (e-a)/1e9, "itl": []}
    if n:
        result["ttft"] = (g1-a)/1e9
    if r.get("v1_ns") is not None:
        if not b <= r["v1_ns"] <= e:
            raise ValueError("first text outside request")
        result["first_text"] = (r["v1_ns"]-a)/1e9
    if n >= 2:
        result.update(generation=(gn-g1)/1e9, tpot=(gn-g1)/(n-1)/1e9,
                      decode_tokens_per_second=(n-1)*1e9/(gn-g1))
        result["itl"] = [(y-x)/1e9 for x, y in zip(times, times[1:])]
    for stage, duration in r["stages_ns"].items():
        if stage not in STAGES or not math.isfinite(duration) or duration < 0:
            raise ValueError("invalid host stage")
        result[stage] = duration/1e9
    if r["gpu_ms"] and r["mode"] != "detail":
        raise ValueError("GPU timing outside detail mode")
    for stage, duration in r["gpu_ms"].items():
        if stage not in ("prefill", "decode") or not math.isfinite(duration) or duration < 0:
            raise ValueError("invalid GPU stage")
        result["gpu_"+stage] = duration/1000
    if "gpu_prefill" in result and result["gpu_prefill"] > 0:
        result["prefill_input_tokens_per_second"] = r["input_tokens"]/result["gpu_prefill"]
    if r["mode"] == "detail" and set(r["gpu_ms"]) != {"prefill", "decode"}:
        raise ValueError("missing mandatory GPU timing")
    return result
