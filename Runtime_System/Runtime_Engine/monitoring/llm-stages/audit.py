"""Recalculate run summaries and instrumentation overhead from AGX raw records."""

import argparse
import collections
import json
import math
import pathlib
import statistics

from metrics import aggregate_cpu_observation, aggregate_request


def percentile(values, p):
    values = sorted(values)
    index = (len(values)-1)*p
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo]+(values[hi]-values[lo])*(index-lo)


def read_records(run, errors):
    records = []
    requests = run/"requests"
    if not requests.is_dir():
        errors.append("missing requests directory")
        return records
    for path in sorted(requests.glob("*.json")):
        try:
            record = json.loads(path.read_text())
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            records.append(record)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{path.name}: {error}")
    return records


def audit(run):
    run = pathlib.Path(run)
    errors = []
    try:
        manifest = json.loads((run/"manifest.json").read_text())
        run_id, mode = manifest["run_id"], manifest["mode"]
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        manifest, run_id, mode = {}, None, None
        errors.append(f"invalid run manifest: {error}")
    completion_path = run/"completion.json"
    completion = None
    if completion_path.exists():
        try:
            completion = json.loads(completion_path.read_text())
            if not isinstance(completion, dict):
                raise ValueError("completion is not an object")
            if completion.get("run_id") != run_id or completion.get("mode") != mode:
                errors.append("completion does not match run manifest")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"invalid completion: {error}")
            completion = None
    else:
        errors.append("missing completion")
    records = read_records(run, errors)
    groups = collections.defaultdict(list)
    cpu_groups = collections.defaultdict(lambda: collections.defaultdict(list))
    cpu_statuses, cpu_errors = collections.Counter(), []
    cpu_requested = manifest.get("cpu_observation_enabled") is True
    identities = set()
    blocks = {(block.get("case"), block.get("block")): block
              for block in completion.get("blocks", [])} if completion else {}
    for r in records:
        identity = r.get("run_id"), r.get("request_id")
        if identity in identities:
            errors.append("duplicate request identity")
        identities.add(identity)
        if r.get("run_id") != run_id or r.get("mode") != mode:
            errors.append(f'{r.get("request_id", "?")}: foreign run or mode')
            continue
        if not r.get("warmup", False):
            block = blocks.get((r.get("case"), r.get("block")))
            request_id = r.get("request_id")
            if not block or not isinstance(request_id, str) or not request_id.isdecimal():
                errors.append(f'{request_id}: outside declared block')
                continue
            if not block.get("first_request", 1) <= int(request_id) <= block.get("last_request", 0):
                errors.append(f'{request_id}: outside declared block')
                continue
        try:
            values = aggregate_request(r)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f'{r.get("request_id", "?")}: {error}')
            continue
        if not r["valid"]:
            errors.append(f'{r["request_id"]}: invalid record')
        cpu = aggregate_cpu_observation(r)
        cpu_statuses[cpu["status"]] += 1
        cpu_requested = cpu_requested or cpu["enabled"] is True
        if ((manifest.get("cpu_observation_enabled") is True or cpu["enabled"] is True)
                and cpu["status"] != "complete"):
            cpu_errors.append(f'{r["request_id"]}: {cpu["status"]}: '
                              + "; ".join(cpu["errors"] or ["requested CPU observation is absent"]))
        if not r["warmup"] and values is not None:
            groups[r["case"]].append((r, values))
            for dimension, value in cpu["values"].items():
                cpu_groups[r["case"]][dimension].append(value)
    cases = {}
    for case, items in groups.items():
        stages = collections.defaultdict(list)
        for _, values in items:
            for key, value in values.items():
                stages[key].extend(value if isinstance(value, list) else [value])
        cases[case] = dict(valid_requests=len(items), metrics={
            stage: dict(count=len(values), sum=sum(values), median=statistics.median(values),
                        p95=percentile(values, .95), maximum=max(values))
            for stage, values in stages.items() if values})
    block_summaries = []
    for block in blocks.values():
        selected = [r for r in records if not r.get("warmup") and r.get("case") == block["case"]
                    and r.get("block") == block["block"]]
        admissions = [r.get("a_ns") for r in selected if isinstance(r.get("a_ns"), int)]
        if admissions and block.get("begin_ns") != min(admissions):
            errors.append(f'block {block["case"]}/{block["block"]}: begin is not first admission')
        if not block.get("residual_acknowledged", False):
            errors.append(f'block {block["case"]}/{block["block"]}: residual processing unacknowledged')
        end = block.get("end_ns")
        if not isinstance(end, int) or not isinstance(block.get("begin_ns"), int) or end <= block["begin_ns"]:
            errors.append(f'block {block["case"]}/{block["block"]}: invalid interval')
            continue
        tokens = sum(r.get("output_tokens", 0) for r in selected if isinstance(r.get("output_tokens"), int))
        duration = (end-block["begin_ns"])/1e9
        block_summaries.append(dict(**block, output_tokens=tokens, elapsed_seconds=duration,
                                    tokens_per_second=tokens/duration))
    incomplete = (completion is None or completion.get("cancelled")
                  or completion.get("incomplete_reason") or completion.get("failures")
                  or completion.get("heartbeat_failed"))
    expected = completion.get("requests") if completion else None
    for case in manifest.get("expected_cases", []):
        measured = [r for r in records if r.get("case") == case and not r.get("warmup")]
        warmed = [r for r in records if r.get("case") == case and r.get("warmup")]
        if len(measured) != manifest.get("expected_attempts_per_case"):
            errors.append(f"{case}: incomplete scheduled measurement attempts")
        if len(warmed) != manifest.get("warmups_per_case"):
            errors.append(f"{case}: incomplete scheduled warmup attempts")
    result = dict(run_id=run_id, mode=mode, cases=cases, blocks=block_summaries,
                  requests=len(records), errors=errors,
                  complete=not incomplete and not errors and len(records) == expected)
    cpu_cases = {}
    for case, dimensions in cpu_groups.items():
        scopes = collections.defaultdict(dict)
        for (scope, kind), values in dimensions.items():
            scopes[scope][kind] = dict(count=len(values), sum=sum(values),
                median=statistics.median(values), p95=percentile(values, .95), maximum=max(values))
        cpu_cases[case] = dict(scopes)
    result["cpu_observation"] = dict(requested=cpu_requested, status_counts=dict(cpu_statuses),
        complete=(result["complete"] and not cpu_errors
                  and cpu_statuses["complete"] == len(records)) if cpu_requested else None,
        cases=cpu_cases, errors=cpu_errors)
    (run/"summary.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def comparison_inputs(summaries):
    errors, runs, identities, unique = [], set(), set(), []
    for summary in summaries:
        run_id = summary.get("run_id")
        if run_id in runs:
            errors.append(f"duplicate run {run_id}")
            continue
        runs.add(run_id)
        unique.append(summary)
        for path in pathlib.Path(summary["path"]).glob("requests/*.json"):
            try:
                record = json.loads(path.read_text())
                identity = record["run_id"], record["request_id"]
                if identity in identities:
                    errors.append("duplicate request identity")
                identities.add(identity)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                errors.append(f"invalid comparison record {path}: {error}")
    return unique, errors


def compare(summaries):
    summaries, integrity_errors = comparison_inputs(summaries)
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for summary in summaries:
        for case, values in summary["cases"].items():
            grouped[case][summary["mode"]].append((summary, values))
    result = {"_comparison": {"errors": integrity_errors}}
    for case, modes in grouped.items():
        entry = {}
        for mode in ("live", "detail"):
            if "baseline" not in modes or mode not in modes:
                continue
            values = {}
            complete = not integrity_errors and all(s["complete"] for m in ("baseline", mode)
                                                    for s, _ in modes[m])
            for metric, statistic, threshold, decrease in (
                ("ttft", "median", .03, False), ("e2e", "median", .03, False),
                ("ttft", "p95", .05, False), ("e2e", "p95", .05, False),
                ("decode_tokens_per_second", "median", .03, True)):
                measurements = {}
                for selected in ("baseline", mode):
                    samples = []
                    for summary, _ in modes[selected]:
                        for path in pathlib.Path(summary["path"]).glob("requests/*.json"):
                            r = json.loads(path.read_text())
                            v = aggregate_request(r)
                            if r["case"] == case and v is not None and metric in v:
                                samples.append(v[metric])
                    complete = complete and len(samples) >= 30
                    measurements[selected] = (statistics.median(samples) if statistic == "median"
                                              else percentile(samples, .95)) if samples else None
                base, observed = measurements["baseline"], measurements[mode]
                change = (observed/base-1)*(-1 if decrease else 1) if base and observed else None
                values[metric+"_"+statistic] = dict(relative_regression=change,
                    target=threshold, pass_target=change is not None and change <= threshold)
            rates = {}
            for selected in ("baseline", mode):
                blocks = [b for s, _ in modes[selected] for b in s["blocks"] if b["case"] == case]
                elapsed = sum(b["elapsed_seconds"] for b in blocks)
                rates[selected] = sum(b["output_tokens"] for b in blocks)/elapsed if elapsed else None
            change = 1-rates[mode]/rates["baseline"] if rates[mode] and rates["baseline"] else None
            values["block_throughput"] = dict(relative_regression=change, target=.03,
                                               pass_target=change is not None and change <= .03)
            entry[mode] = dict(metrics=values, sample_complete=complete,
                               pass_target=complete and all(v["pass_target"] for v in values.values()))
        result[case] = entry
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=pathlib.Path)
    parser.add_argument("--overhead-output", type=pathlib.Path)
    args = parser.parse_args()
    summaries = []
    for run in args.runs:
        summary = audit(run)
        summary["path"] = str(run.resolve())
        summaries.append(summary)
        print(json.dumps({k: summary[k] for k in ("run_id", "mode", "requests", "complete", "errors")}))
    if args.overhead_output:
        comparison = compare(summaries)
        args.overhead_output.write_text(json.dumps(comparison, indent=2)+"\n")
        comparable = [value for case, value in comparison.items() if case != "_comparison"]
        comparison_pass = (not comparison["_comparison"]["errors"] and len(comparable) == 3
                           and all(value.get("live", {}).get("pass_target", False) for value in comparable))
    else:
        comparison_pass = True
    raise SystemExit(0 if summaries and all(s["complete"] and (
        not s["cpu_observation"]["requested"] or s["cpu_observation"]["complete"])
        for s in summaries) and comparison_pass else 1)
