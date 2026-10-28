"""Separate user-visible latency trends, phase comparisons, and runtime diagnostics."""

import itertools
import json
import pathlib

DS = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}
HEALTH_FILTER = 'job="tango2",component="llm",host="10.2.250.15"'
ALL_CASES = HEALTH_FILTER+',mode="detail"'
FILTER = ALL_CASES+',case="$case"'
ids = itertools.count(1)


def statistic(stage, name="p50", selected=True):
    filters = FILTER if selected else ALL_CASES
    return f'tango2_llm_window_duration_seconds{{{filters},stage="{stage}",statistic="{name}"}}'


def rate(stage):
    return f'tango2_llm_window_rate{{{FILTER},stage="{stage}",statistic="p50"}}'


def sample_count(stage):
    return f'tango2_llm_window_samples{{{FILTER},stage="{stage}"}}'


def cpu_statistic(scope, kind, name="p50"):
    return (f'tango2_llm_cpu_window_seconds{{{FILTER},scope="{scope}",'
            f'kind="{kind}",statistic="{name}"}}')


def ms(expression):
    return f'1000 * ({expression})'


def panel(title, expressions, x, y, w=12, h=8, kind="timeseries", unit="suffix: ms",
          description="", decimals=3):
    instant = kind in ("stat", "bargauge", "table")
    item = dict(id=next(ids), title=title, type=kind, datasource=DS,
                gridPos=dict(x=x, y=y, w=w, h=h), description=description,
                targets=[dict(refId=chr(65+i), expr=expression, legendFormat=legend,
                              datasource=DS, instant=instant, range=not instant,
                              format="time_series")
                         for i, (legend, expression) in enumerate(expressions)],
                fieldConfig=dict(defaults=dict(unit=unit, decimals=decimals, noValue="—",
                                               color=dict(mode="palette-classic")), overrides=[]))
    if kind == "timeseries":
        item["fieldConfig"]["defaults"]["custom"] = dict(
            drawStyle="line", lineInterpolation="linear", lineWidth=2, fillOpacity=0,
            showPoints="never", spanNulls=False, axisCenteredZero=False,
            stacking=dict(mode="none", group="A"))
        item["options"] = dict(tooltip=dict(mode="multi", sort="none"),
                               legend=dict(displayMode="table", placement="bottom", calcs=["lastNotNull"]))
    elif kind == "bargauge":
        item["fieldConfig"]["defaults"]["min"] = 0
        item["options"] = dict(orientation="horizontal", displayMode="basic", showUnfilled=False,
                               valueMode="color", namePlacement="left",
                               text=dict(titleSize=14, valueSize=18),
                               reduceOptions=dict(calcs=["lastNotNull"], fields="", values=False))
    elif kind == "stat":
        item["options"] = dict(graphMode="none", colorMode="none", textMode="value",
                               reduceOptions=dict(calcs=["lastNotNull"], fields="", values=False))
    elif kind == "table":
        item["options"] = dict(showHeader=True, cellHeight="sm", footer=dict(show=False))
        item["transformations"] = [
            dict(id="reduce", options=dict(reducers=["lastNotNull"], mode="seriesToRows")),
            dict(id="organize", options=dict(renameByName={"Field": "Metric", "Last *": "Samples",
                                                            "Last": "Samples", "lastNotNull": "Samples"})),
        ]
    return item


def trend(title, stage, x, y):
    item = panel(title, [(name, ms(statistic(stage, name))) for name in ("min", "max", "p50", "p95")],
                 x, y, h=9, description="Exact statistics of completed requests in the last 5m. Shading is the observed min–max range; lines are p50/p95. This is an aggregate trend, not individual requests. Hover shows 0.001ms digits. Empty intervals remain gaps.")
    for name in ("min", "max"):
        properties = [dict(id="custom.lineWidth", value=0),
                      dict(id="custom.hideFrom", value=dict(legend=True, tooltip=False, viz=False))]
        if name == "max":
            properties += [dict(id="custom.fillBelowTo", value="min"),
                           dict(id="custom.fillOpacity", value=12),
                           dict(id="color", value=dict(mode="fixed", fixedColor="blue"))]
        item["fieldConfig"]["overrides"].append(dict(matcher=dict(id="byName", options=name), properties=properties))
    return item


def row(title, y, children):
    return dict(id=next(ids), title=title, type="row", collapsed=True, panels=children,
                gridPos=dict(x=0, y=y, w=24, h=1))


panels = [dict(id=next(ids), type="text", title="Qwen3-1.7B · controlled single-request benchmark",
    gridPos=dict(x=0, y=0, w=24, h=4), options=dict(mode="markdown", content=(
        "Fixed input lengths / output limits · greedy decoding · one active request. "
        "**Trends:** exact last-5-minute statistics, not per-request samples. "
        "**Bars:** current phase/case comparisons. Each case receives 10 requests per cycle (~75–80s). "
        "See eligible counts below; fewer than 30 samples is exploratory.")))]

for index, (title, expression, unit, decimals, description) in enumerate((
    ("TTFT p50", ms(statistic("ttft")), "suffix: ms", 3,
     "Request acceptance to first generated non-EOS token. Includes input preparation and prefill. Internal AGX consumer boundary."),
    ("E2E p50", ms(statistic("e2e")), "suffix: ms", 3,
     "Request acceptance to completed internal response delivery. Model load and raw-record publication are outside this interval."),
    ("TPOT p50", ms(statistic("tpot")), "suffix: ms", 3,
     "Per-request (last token − first token)/(N−1). Undefined for N<2. This is not a GPU-only timer."),
    ("Decode tok/s", rate("decode_tokens_per_second"), "suffix: tok/s", 2,
     "Median per-request (N−1)/(last token − first token). Board-wide output throughput is shown separately."),
)):
    panels.append(panel(title, [("p50", expression)], index*6, 3, w=6, h=4,
                        kind="stat", unit=unit, decimals=decimals, description=description))

panels += [trend("First-token latency · 5m distribution", "ttft", 0, 7),
           trend("Request latency · 5m distribution", "e2e", 12, 7)]

panels.append(panel("Prefill · host and GPU", [
    ("Host p50", ms(statistic("prefill_host"))),
    ("GPU p50", ms(statistic("gpu_prefill"))),
    ("GPU p95", ms(statistic("gpu_prefill", "p95")))], 0, 16, h=7, kind="bargauge",
    description="Current last-5-minute phase statistics. The host call includes GPU execution and its existing wait; these bars overlap and must not be added. Prefill processes the prompt and produces the first token."))
panels.append(panel("Decode · generation and GPU", [
    ("Elapsed p50", ms(statistic("generation"))),
    ("GPU p50", ms(statistic("gpu_decode"))),
    ("GPU p95", ms(statistic("gpu_decode", "p95")))], 12, 16, h=7, kind="bargauge",
    description="Generation is first-to-last token elapsed time; GPU is the sum of subsequent decode stream intervals. Overlapping measurements, not additive stages. Bars are snapshot comparisons, not a continuous execution trace."))

for index, stage in enumerate(("gpu_prefill", "gpu_decode")):
    label = "prefill" if index == 0 else "decode"
    panels.append(panel("GPU "+label+" · compare all cases", [
        ("{{case}}", ms(statistic(stage, selected=False)))], index*12, 23, h=8, kind="bargauge",
        description="All six cases, exact last-5-minute p50. Compare input-length sensitivity for prefill and output-length sensitivity for decode. These panels intentionally ignore the case dropdown."))

throughput = panel("Board throughput · all cases", [
    ("output tok/s", f'sum(rate(tango2_llm_output_tokens_sum{{{ALL_CASES}}}[5m]))'),
    ("requests/s", f'sum(rate(tango2_llm_duration_seconds_count{{{ALL_CASES},stage="e2e"}}[5m]))')],
    0, 31, unit="suffix: tok/s", decimals=2,
    description="Board-wide successful, non-warmup output tokens and requests per elapsed second, including idle/reload gaps. Prometheus rate is extrapolated over 5m. This differs from per-request decode speed.")
throughput["fieldConfig"]["overrides"].append(dict(matcher=dict(id="byName", options="requests/s"),
    properties=[dict(id="unit", value="suffix: req/s"), dict(id="decimals", value=3),
                dict(id="custom.axisPlacement", value="right")]))
panels.append(throughput)

sample_stages = (("TTFT", "ttft"), ("Request E2E", "e2e"), ("TPOT", "tpot"),
                 ("Token intervals (ITL)", "itl"), ("GPU prefill", "gpu_prefill"),
                 ("GPU decode", "gpu_decode"), ("Decode rate", "decode_tokens_per_second"),
                 ("Prefill rate", "prefill_input_tokens_per_second"))
samples = panel("Eligible samples · last 5m", [(name, sample_count(stage)) for name, stage in sample_stages],
                12, 31, kind="table", unit="none", decimals=0,
                description="Fewer than 30 samples for a metric means that metric is insufficient. ITL counts individual token intervals; the other rows count eligible requests. Empty metrics have no samples.")
samples["fieldConfig"]["defaults"].update(thresholds=dict(mode="absolute", steps=[
    dict(color="orange", value=None), dict(color="green", value=30)]))
samples["fieldConfig"]["overrides"].append(dict(matcher=dict(id="byType", options="number"),
    properties=[dict(id="color", value=dict(mode="thresholds")),
                dict(id="custom.cellOptions", value=dict(type="color-text"))]))
panels.append(samples)

runtime = [
    panel("Input and prefill preparation", [(name, f'1000000 * ({statistic(stage)})') for name, stage in (
        ("Template + tokenizer", "input"), ("KV/buffer preparation", "prefill_prepare"))],
        0, 40, kind="bargauge", unit="suffix: µs",
        description="CPU-side preparation before the prefill call. Separates text/tokenizer work from runtime context/buffer setup."),
    panel("Text conversion and publication", [(name, f'1000000 * ({statistic(stage)})') for name, stage in (
        ("Incremental detokenization", "detokenize"), ("Stream publication", "deliver"))],
        12, 40, kind="bargauge", unit="suffix: µs",
        description="Cumulative host costs inside generation. They overlap generation elapsed time and do not measure external network delivery."),
    panel("Token pacing · TPOT and ITL", [(f"{stage} {name}", ms(statistic(stage, name)))
        for stage in ("tpot", "itl") for name in ("p50", "p95")], 0, 48,
        description="TPOT gives one average per request; ITL gives individual token gaps and weights longer responses more. Both exclude N<2 and are not GPU-only timings."),
    panel("First token and first nonempty text", [(f"{stage} {name}", ms(statistic(stage, name)))
        for stage in ("ttft", "first_text") for name in ("p50", "p95")], 12, 48,
        description="Generated token availability and the internal consumer's first visible text can differ because a token may yield empty text or wait for publication."),
    panel("Unattributed host interval", [("internal queue", f'1000000 * ({statistic("queue")})'),
                                        ("remainder", f'1000000 * ({statistic("host_remainder")})')],
        0, 56, kind="bargauge", unit="suffix: µs",
        description="Queue is this serial runner's admission-to-start gap, not a production server queue. Remainder closes E2E accounting and is not an independently attributed runtime stage."),
    panel("Output length · actual tokens", [(name, f'tango2_llm_window_output_tokens{{{FILTER},statistic="{name}"}}')
        for name in ("p50", "p95")], 12, 56, kind="bargauge", unit="short", decimals=0,
        description="Actual generated tokens expose early EOS; the selected case specifies an output limit."),
]
panels.append(row("Runtime diagnostics", 39, runtime))

device = []
for index, (title, names, unit) in enumerate((
    ("Utilization", ("cpu_utilization_ratio", "gpu_utilization_ratio"), "percentunit"),
    ("Clocks", ("cpu_clock_hertz", "gpu_clock_hertz", "emc_clock_hertz"), "hertz"),
    ("Temperature", ("cpu_temperature_celsius", "gpu_temperature_celsius", "soc0_temperature_celsius"), "celsius"),
    ("Power by rail", ("gpu_soc_power_watts", "cpu_cv_power_watts", "system_5v_power_watts", "ddr_1v8ao_power_watts"), "watt"),
    ("Memory", ("memory_used_bytes",), "bytes"),
)):
    device.append(panel(title, [(name, f'tango2_llm_device_{name}{{{HEALTH_FILTER}}}') for name in names],
                        index%2*12, 41+index//2*8, unit=unit, decimals=2,
                        description=("AGX INA3221 rails. DDR/1V8AO is included in system 5V; do not add or stack rails."
                                     if unit == "watt" else "Platform context for latency changes; time correlation alone does not establish cause.")))
panels.append(row("Device telemetry", 40, device))

quality = [
    panel("Collection and producer health", [("scrape up", f'up{{{HEALTH_FILTER}}}'),
        ("producer heartbeat", f'tango2_llm_producer_up{{{HEALTH_FILTER}}}'),
        ("pending records", f'tango2_llm_pending_records{{{HEALTH_FILTER}}}')], 0, 42, unit="short", decimals=0,
        description="Endpoint and producer are separate. The runner reloads between cycles; producer heartbeat can be briefly absent. A heartbeat older than 5s means stopped/stale."),
    panel("Record integrity", [(name, f'tango2_llm_records_{name}_total{{{HEALTH_FILTER}}}')
        for name in ("invalid", "duplicate", "parse_errors")], 12, 42, unit="short", decimals=0),
    panel("Completion reasons", [("{{status}}", f'sum by(status)(increase(tango2_llm_requests_completed_total{{{FILTER}}}[5m]))')],
        0, 50, unit="short", decimals=1, description="Diagnostic counters include warmups. Normal performance statistics exclude warmups, errors and invalid records."),
    panel("Preparation sample counts", [(stage, sample_count(stage)) for stage in (
        "input", "prefill_prepare", "prefill_host", "generation", "host_remainder", "detokenize", "deliver", "first_text", "queue", "output_tokens")],
        12, 50, kind="table", unit="none", decimals=0),
    panel("CPU observation availability", [("{{status}}",
        f'tango2_llm_cpu_observations_total{{{HEALTH_FILTER}}}')],
        0, 58, kind="table", unit="none", decimals=0,
        description="All cases since the collector restarted. Complete/partial/unavailable/invalid concern CPU observation only; legacy and disabled runs have no CPU measurement. Host/GPU latency remains independently eligible."),
    panel("CPU eligible samples · last 5m", [("{{scope}} / {{kind}}",
        f'tango2_llm_cpu_window_samples{{{FILTER}}}')],
        12, 58, kind="table", unit="none", decimals=0,
        description="Each CPU scope and counter has its own eligible request count. Zero samples means unavailable or absent observation, not zero CPU work or zero wait. Fewer than 30 samples is exploratory."),
]
evidence = panel("Run identity and evidence", [("run", f'tango2_llm_run_info{{{HEALTH_FILTER}}}')],
                 0, 66, w=24, kind="table", unit="short", decimals=0)
evidence.pop("transformations")
for target in evidence["targets"]:
    target["format"] = "table"
quality.append(evidence)
panels.append(row("Collection quality and evidence", 41, quality))

# CPU counters are shown beside the existing latency view, without treating
# overlapping thread/stage scopes as an additive wall-time decomposition.
for item in panels:
    if item["gridPos"]["y"] >= 39:
        item["gridPos"]["y"] += 8
        for child in item.get("panels", []):
            child["gridPos"]["y"] += 8
cpu_scopes = (("Worker request", "worker_request"), ("Consumer request", "consumer_request"),
              ("Input", "input"), ("Prefill preparation", "prefill_prepare"),
              ("Prefill host", "prefill_host"), ("Decode + finalize", "decode_and_finalize"))
for index, (title, kind) in enumerate((("CPU execution · instrumented threads", "on_cpu"),
                                     ("Runnable CPU wait · instrumented threads", "runqueue_wait"))):
    panels.append(panel(title, [(label, ms(cpu_statistic(scope, kind)))
                               for label, scope in cpu_scopes], index*12, 39, kind="bargauge",
        description=("Exact last-5-minute p50 in detail mode. Only the request worker and consumer are measured; "
                     "runtime helper threads are outside scope. Stage scopes overlap the worker request and are not additive. "
                     "Decode + finalize runs from prefill end to worker completion, not first-to-last token generation. "
                     "Runnable wait is scheduler queue delay, not GPU/I/O blocking or runner admission queue. "
                     "Missing measurements stay absent; see per-counter eligible counts in Collection quality.")))
panels.sort(key=lambda item: (item["gridPos"]["y"], item["gridPos"]["x"]))

# Leave enough height for the benchmark assumptions before the metric cards.
for item in panels[1:]:
    item["gridPos"]["y"] += 1
    for child in item.get("panels", []):
        child["gridPos"]["y"] += 1

dashboard = dict(uid="tango2-agx-llm-stages", title="TANGO2 AGX — LLM Stage Performance",
    tags=["tango2", "orin-agx", "llm", "engineering"], schemaVersion=39, version=4,
    refresh="5s", timezone="browser", editable=False,
    description="Fixed-shape greedy benchmark. Latency trends, phase/case snapshots, and collapsed diagnostics. Exact 5m sample statistics. Internal AGX observation, not an external serving or official TC5 verdict.",
    time={"from": "now-30m", "to": "now"},
    templating=dict(list=[dict(name="case", label="Workload", type="custom", query=",".join(
        f"i{i}_o{o}" for i in (64, 256, 1024) for o in (64, 128)),
        current=dict(text="i64_o64", value="i64_o64"))]),
    annotations=dict(list=[dict(name="Run boundaries", datasource=DS, enable=False, hide=False,
        iconColor="rgba(0,211,255,1)", useValueForTime=True, target=dict(refId="A",
        expr=f'1000 * tango2_llm_run_boundary_timestamp_seconds{{{HEALTH_FILTER}}}'),
        titleFormat="{{run_id}} {{event}}", textFormat="{{evidence_path}}")]), panels=panels)

if __name__ == "__main__":
    pathlib.Path(__file__).with_name("grafana-dashboard.json").write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2)+"\n")
