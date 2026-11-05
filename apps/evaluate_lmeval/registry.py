"""플랫폼 벤치마크 id → lm-evaluation-harness 태스크 레지스트리.

id 는 llm_evaluation `constants.BENCHMARK_IDS` · FE `benchmarks.js` 와 **같은 집합**이어야
한다(패리티 테스트: llm_evaluation/tests/test_benchmark_catalog.py). 기존 id(arc·kobest…)는
mock 시절 이력·비교표가 averages 의 키로 쓰므로 이름을 바꾸지 않는다.

few-shot 은 ETRI 레지스트리(`Evaluation/lmeval/eval_tasks.py`, 리더보드 관례)를 따른다.
`metric` 은 결과 화면의 대표 스칼라 축(플랫폼 메트릭 id)이고, `lm_metric`·`lm_filter` 는
lm-eval 결과 dict 의 `"<metric>,<filter>"` 키에서 그 값을 고르는 좌표다.

스케일 — 화면은 accuracy 류를 0~100 으로 그린다(FE benchmarkMetrics.js). lm-eval 은
태스크마다 스케일이 다르므로(squadv2 는 0~100, 대부분 0~1) **태스크별 명시표**로 환산한다.
"값이 1 을 넘으면 이미 백분율" 같은 휴리스틱은 쓰지 않는다 — ETRI 원본이 그 규칙과 잘못된
지정 때문에 DROP 을 100 배 작게 그렸다. 표에 없는 지표는 환산하지 않고 경고로 남긴다.
원시값 범위는 P0 스파이크(lm_eval 0.4.12, 18종 limit=20)에서 실측했다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

FRACTION = "fraction"   # 0~1 → ×100
PERCENT = "percent"     # 이미 0~100

# 객관식 태스크가 내는 지표는 전부 0~1 이다.
_MC_SCALE = {"acc": FRACTION, "acc_norm": FRACTION}


@dataclass(frozen=True)
class Benchmark:
    id: str
    tasks: Tuple[str, ...]           # lm-eval 태스크(또는 그룹) 이름
    num_fewshot: int
    metric: str                      # 플랫폼 대표 메트릭 id
    lm_metric: str                   # lm-eval 지표 이름
    lm_filter: str = "none"
    scale: Dict[str, str] = field(default_factory=dict)
    kind: str = "lmeval"             # lmeval | custom
    # 여러 태스크의 대표값을 산술평균으로 합친다(kobest 5종). 그룹 태스크(mmlu 등)는
    # lm-eval 이 이미 가중 평균을 내므로 여기서 다시 합치지 않는다.
    mean_of_tasks: bool = False
    # 모델이 생성한 코드를 실행해 채점한다(HumanEval). 컨테이너 env 가 허용할 때만 돈다.
    unsafe_code: bool = False


BENCHMARKS: Dict[str, Benchmark] = {b.id: b for b in (
    Benchmark("arc", ("arc_challenge",), 25, "accuracy", "acc", scale=_MC_SCALE),
    Benchmark("arc_easy", ("arc_easy",), 0, "acc_norm", "acc_norm", scale=_MC_SCALE),
    Benchmark("kobest", ("kobest_boolq", "kobest_copa", "kobest_hellaswag",
                         "kobest_sentineg", "kobest_wic"), 5, "f1", "f1",
              scale={**_MC_SCALE, "f1": FRACTION}, mean_of_tasks=True),
    Benchmark("mmlu", ("mmlu",), 5, "accuracy", "acc", scale=_MC_SCALE),
    Benchmark("kmmlu", ("kmmlu",), 5, "accuracy", "acc", scale=_MC_SCALE),
    Benchmark("kmmlu_direct", ("kmmlu_direct",), 5, "exact_match", "exact_match",
              scale={"exact_match": FRACTION}),
    Benchmark("haerae", ("haerae",), 0, "acc_norm", "acc_norm", scale=_MC_SCALE),
    Benchmark("hellaswag", ("hellaswag",), 10, "acc_norm", "acc_norm", scale=_MC_SCALE),
    Benchmark("winogrande", ("winogrande",), 5, "accuracy", "acc", scale=_MC_SCALE),
    Benchmark("piqa", ("piqa",), 0, "acc_norm", "acc_norm", scale=_MC_SCALE),
    Benchmark("openbookqa", ("openbookqa",), 0, "acc_norm", "acc_norm", scale=_MC_SCALE),
    # strict-match = 리더보드 관례(#### 뒤 숫자만 정답으로 인정). flexible 은 상세에만.
    Benchmark("gsm8k", ("gsm8k",), 5, "accuracy", "exact_match", lm_filter="strict-match",
              scale={"exact_match": FRACTION}),
    Benchmark("truthfulqa", ("truthfulqa_mc2",), 0, "accuracy", "acc", scale=_MC_SCALE),
    Benchmark("truthfulqa_gen", ("truthfulqa_gen",), 0, "bleu", "bleu_max",
              scale={"bleu_max": PERCENT, "bleu_diff": PERCENT, "bleu_acc": FRACTION,
                     "rouge1_max": PERCENT, "rouge1_diff": PERCENT, "rouge1_acc": FRACTION,
                     "rouge2_max": PERCENT, "rouge2_diff": PERCENT, "rouge2_acc": FRACTION,
                     "rougeL_max": PERCENT, "rougeL_diff": PERCENT, "rougeL_acc": FRACTION}),
    Benchmark("boolq", ("boolq",), 0, "accuracy", "acc", scale={"acc": FRACTION}),
    # HF `squad_v2` 지표가 이미 0~100 으로 낸다.
    Benchmark("squadv2", ("squadv2",), 0, "f1", "f1",
              scale={k: PERCENT for k in ("exact", "f1", "HasAns_exact", "HasAns_f1",
                                          "NoAns_exact", "NoAns_f1", "best_exact",
                                          "best_f1")}),
    # drop_tango = upstream drop 의 정답 템플릿 버그 수정본(prepare_tasks.py). 원본은
    # few-shot 정답이 필드 이름 목록('number,date,spans,...')으로 렌더돼 모델이 그걸 베낀다.
    Benchmark("drop", ("drop_tango",), 3, "f1", "f1",
              scale={"em": FRACTION, "f1": FRACTION}),
    Benchmark("humaneval", ("humaneval",), 0, "pass_at_1", "pass@1",
              lm_filter="create_test", scale={"pass@1": FRACTION}, unsafe_code=True),
    # 런 데이터셋(입력-정답 쌍)으로 생성 후 F1/EM/BLEU/ROUGE — lm-eval 태스크가 아니다.
    Benchmark("custom", (), 0, "f1", "f1", kind="custom"),
)}

CODE_BENCHMARK_IDS = tuple(b.id for b in BENCHMARKS.values() if b.unsafe_code)


def resolve(ids) -> list:
    """요청 벤치마크 목록(문자열 또는 {"benchmark": id}) → Benchmark 목록(중복 제거·순서 유지).

    모르는 id 는 **거절한다** — 조용히 버리면 "고른 벤치마크가 채점됐다"고 믿는 런이 된다
    (mock 이 모르는 id 를 필터링해 9 개 해시 점수를 내던 것과 같은 함정).
    """
    out, seen = [], set()
    for item in ids or []:
        bid = item if isinstance(item, str) else str((item or {}).get("benchmark", ""))
        bid = bid.strip()
        if not bid or bid in seen:
            continue
        if bid not in BENCHMARKS:
            raise ValueError(f"unknown benchmark: {bid!r} (지원: {', '.join(BENCHMARKS)})")
        seen.add(bid)
        out.append(BENCHMARKS[bid])
    if not out:
        raise ValueError("benchmarks 가 비었다 — 채점할 벤치마크를 1 개 이상 지정하라")
    return out
