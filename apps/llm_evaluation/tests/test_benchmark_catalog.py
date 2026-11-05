"""벤치마크 카탈로그 교차 정합 — BE constants ↔ 채점 컨테이너 ↔ FE ↔ 매니페스트 ↔ settings.

id 가 한 곳에서만 늘면 "화면에서 고를 수는 있는데 서버·컨테이너가 모르는" 벤치마크가
생긴다. 전에는 이 대조를 사람이 주석으로만 약속했다(constants.py "⚠️ FE 와 같아야 한다").
DB·네트워크 없이 파일만 읽는다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

APPS = Path(__file__).resolve().parents[2]
LLMOPS = APPS.parent
sys.path.insert(0, str(APPS / "llm_evaluation" / "src"))
sys.path.insert(0, str(APPS / "evaluate_lmeval"))

from evaluation import constants as C  # noqa: E402
import registry as REG  # noqa: E402  (evaluate_lmeval)

FE_DIR = LLMOPS / "front" / "src" / "pages" / "llm" / "Evaluation" / "BenchmarkEvaluation"
MANIFEST_DIR = APPS / "fb_external_container" / "manifests"
SCORER_MANIFESTS = ("evaluate-lmeval", "evaluate-lmeval-code", "evaluate-intent",
                    "evaluate-logickor-judge", "evaluate-benchmark-mock")


def _fe_benchmarks():
    """benchmarks.js 의 BENCHMARKS 배열 → {id: recommended}."""
    text = (FE_DIR / "benchmarks.js").read_text(encoding="utf-8")
    body = text.split("export const BENCHMARKS = [", 1)[1].split("\n];", 1)[0]
    ids = re.findall(r"^\s{4}id: '([a-z0-9_]+)'", body, re.M)
    recs = re.findall(r"^\s{4}recommended: '([a-z0-9_]+)'", body, re.M)
    assert len(ids) == len(recs)
    return dict(zip(ids, recs))


def _manifest(name: str) -> dict:
    return yaml.safe_load((MANIFEST_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


# ── BE ↔ 컨테이너 ──────────────────────────────────────────────────────────────

def test_lmeval_scorer_ids_match_container_registry():
    routed_to_lmeval = set(C.LMEVAL_BENCHMARK_IDS) | {
        b for b, key in C.REAL_BENCHMARK_MANIFEST_KEY.items() if key in C.LOCAL_WEIGHTS_MANIFEST_KEYS}
    assert routed_to_lmeval == set(REG.BENCHMARKS)


def test_recommended_metric_matches_container():
    for bid, bench in REG.BENCHMARKS.items():
        assert C.BENCHMARK_RECOMMENDED_METRIC[bid] == bench.metric, bid
        assert bench.metric in C.METRIC_IDS
        assert bench.metric in C.BENCHMARK_ALLOWED_METRICS[bid]


def test_code_benchmarks_route_to_code_scorer_only():
    for bid in REG.CODE_BENCHMARK_IDS:
        assert C.REAL_BENCHMARK_MANIFEST_KEY.get(bid) == "BENCHMARK_CODE"
    assert not set(REG.CODE_BENCHMARK_IDS) & set(C.LMEVAL_BENCHMARK_IDS)


def test_default_set_is_single_scorer_and_scoreable():
    keys = {C.REAL_BENCHMARK_MANIFEST_KEY.get(b, "BENCHMARK") for b in C.DEFAULT_BENCHMARK_IDS}
    assert keys == {"BENCHMARK"}           # 혼재 거부에 걸리지 않는다
    assert "humaneval" not in C.DEFAULT_BENCHMARK_IDS and "custom" not in C.DEFAULT_BENCHMARK_IDS
    assert len(C.DEFAULT_BENCHMARK_IDS) <= C.MAX_BENCHMARK_ITEMS


# ── BE ↔ FE ────────────────────────────────────────────────────────────────────

def _fe_entries():
    """benchmarks.js 의 BENCHMARKS 항목별 원문 → {id: 항목 텍스트}(플래그 대조용)."""
    text = (FE_DIR / "benchmarks.js").read_text(encoding="utf-8")
    body = text.split("export const BENCHMARKS = [", 1)[1].split("\n];", 1)[0]
    out = {}
    for chunk in re.split(r"^\s{2}\{", body, flags=re.M):
        m = re.search(r"^\s{4}id: '([a-z0-9_]+)'", chunk, re.M)
        if m:
            out[m.group(1)] = chunk
    return out


def test_dataset_free_set_matches_fe_and_container():
    # 데이터셋 없이 시작해도 되는 벤치마크 — 화면이 데이터셋 칸을 선택으로 두는 조건과
    # 서버가 거절하지 않는 조건, 컨테이너가 데이터셋을 읽지 않는 조건이 같아야 한다.
    fe_free = {bid for bid, chunk in _fe_entries().items()
               if "scorer: 'lmeval'" in chunk and "usesDataset: true" not in chunk}
    assert fe_free == set(C.DATASET_FREE_BENCHMARK_IDS)
    container_free = {bid for bid, bench in REG.BENCHMARKS.items() if bench.kind != "custom"}
    assert container_free == set(C.DATASET_FREE_BENCHMARK_IDS)


def test_fe_catalog_matches_be():
    fe = _fe_benchmarks()
    assert set(fe) == set(C.BENCHMARK_IDS)
    for bid, rec in fe.items():
        assert rec == C.BENCHMARK_RECOMMENDED_METRIC[bid], bid


def test_fe_eval_type_matches_be():
    # 벤치마크의 평가 유형 = 어느 프로젝트의 실행 화면에 뜨나(FE) = 어느 프로젝트에서 서버가 받나(BE).
    # 갈리면 화면에서 고를 수 있는데 실행하면 유형 게이트에 거절된다.
    fe = {bid: re.search(r"^\s{4}evalType: '([a-z]+)'", chunk, re.M).group(1)
          for bid, chunk in _fe_entries().items()}
    assert fe == C.BENCHMARK_EVAL_TYPE


def test_fe_metric_catalog_covers_be_metrics():
    text = (FE_DIR / "benchmarkMetrics.js").read_text(encoding="utf-8")
    fe_ids = set(re.findall(r"^\s{4}id: '([a-z0-9_]+)'", text, re.M))
    assert set(C.METRIC_IDS) <= fe_ids


# ── 매니페스트 ↔ settings ↔ 시간 상한 ───────────────────────────────────────────

@pytest.mark.parametrize("name, canonical", [
    ("evaluate-lmeval", "manifest.yaml"), ("evaluate-lmeval-code", "manifest-code.yaml")])
def test_seed_copy_matches_canonical(name, canonical):
    seed = (MANIFEST_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    assert seed == (APPS / "evaluate_lmeval" / canonical).read_text(encoding="utf-8")


def test_mixatis_seed_copy_carries_canonical_body():
    # MixATIS 시드 사본은 lm-eval 과 달리 머리에 안내 주석이 붙는다 — 본문은 정본 그대로여야 한다
    # (한쪽만 버전·timeout 을 올리면 시드가 옛 값을 등록한다).
    seed = (MANIFEST_DIR / "evaluate-intent.yaml").read_text(encoding="utf-8")
    assert seed.endswith((APPS / "evaluate_intent" / "manifest.yaml").read_text(encoding="utf-8"))


def test_settings_defaults_point_at_registered_manifests():
    text = (APPS / "fb_utils" / "settings.py").read_text(encoding="utf-8")
    for key, manifest in (("BENCHMARK", "evaluate-lmeval"), ("BENCHMARK_CODE", "evaluate-lmeval-code"),
                          ("MIXATIS", "evaluate-intent")):
        name = re.search(rf"^{key}_MANIFEST_NAME = os.getenv\('{key}_MANIFEST_NAME', '([^']+)'\)", text, re.M)
        ver = re.search(rf"^{key}_MANIFEST_VERSION = os.getenv\('{key}_MANIFEST_VERSION', '([^']+)'\)", text, re.M)
        m = _manifest(manifest)["metadata"]
        assert (name.group(1), ver.group(1)) == (m["name"], m["version"])


def test_stale_sweep_outlives_every_scorer_timeout():
    # 스윕은 컨테이너에 묻지 않고 나이만으로 failed(복구 불가)로 만든다 — 정상 런을 죽이면 안 된다.
    budget = C.STALE_RUNNING_MAX_HOURS * 3600
    for name in SCORER_MANIFESTS:
        caps = _manifest(name)["spec"]["capabilities"]
        worst = int(caps.get("timeout_seconds") or 0) + int(caps.get("estimated_startup_seconds") or 0)
        assert worst < budget, name


def test_lmeval_manifests_are_isolated_and_only_code_one_runs_code():
    main, code = _manifest("evaluate-lmeval")["spec"], _manifest("evaluate-lmeval-code")["spec"]
    assert main["network"]["isolate"] is True and code["network"]["isolate"] is True
    assert "LMEVAL_ALLOW_CODE_EXEC" not in main["env"] and "HF_ALLOW_CODE_EVAL" not in main["env"]
    assert code["env"]["LMEVAL_ALLOW_CODE_EXEC"] == "1"
    assert main["image"] == code["image"]


def test_batch_split_constants_match_the_lmeval_manifest():
    # 분배의 타임아웃 가드(plan_benchmark_runs)는 파드가 실제로 죽는 시각과 같아야 의미가 있다.
    caps = _manifest("evaluate-lmeval")["spec"]["capabilities"]
    assert C.LMEVAL_RUN_TIMEOUT_SECONDS == int(caps["timeout_seconds"])
    assert C.LMEVAL_STARTUP_SECONDS == int(caps["estimated_startup_seconds"])
    # 추정표는 lm-eval 채점기 벤치마크만 — 오타 id 는 조용히 기본값(80초)으로 떨어진다.
    assert set(C.LMEVAL_EST_SECONDS) <= set(C.LMEVAL_BENCHMARK_IDS)
