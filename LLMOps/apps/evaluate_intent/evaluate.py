"""MixATIS 평가 드라이버 — ETRI 원본 함수를 그대로 호출한다.

원본 `evaluate_qwen3_mixatis.py:main()` 은 argparse 로 인자를 받아 stdout 에 지표를
인쇄하고 끝난다. 플랫폼은 진행률 콜백과 `/output/metrics.json` 이 필요하므로 main() 을
쓰지 않고 **같은 함수들을 같은 순서로** 부르는 드라이버를 둔다. 모델 로드·프롬프트·생성·
파싱은 전부 원본 함수라 점수 정의가 갈라지지 않는다.

원본과 다른 점은 셋이다.
  1) `adapter_dir` 는 선택이다. 플랫폼 체크포인트는 merged 라 그것만으로 평가가 되지만
     (원본의 zero-shot 경로), 같은 잡의 학습 단계가 LoRA 를 붙였으면 그 어댑터를 얹는다.
     비우면 종전과 완전히 같은 동작이다.
  2) 4bit 가 기본이 아니다. 원본은 A100 40G 급을 상정해 QLoRA 4bit 를 기본으로 켰지만
     우리 잡은 80GB 한 장을 통째로 받으므로 bf16 이 더 빠르고 bitsandbytes 의존도 없앤다.
     `use_4bit` 파라미터로 원본 동작을 복원할 수 있다.
  3) `generate_base_url` 을 주면 모델을 이 잡이 올리지 않고 **이미 떠 있는 배포**에 생성을
     위임한다(remote.py). 프롬프트(ugen_data 가 만든 messages)·파싱·지표는 그대로이고
     바뀌는 것은 "누가 토큰을 만드나"뿐이다. ⚠️ 원본 `generate_batch` 가 걸던
     `apply_chat_template(..., enable_thinking=False)` 는 이 경로에서 **사라진다** —
     템플릿 적용은 배포 쪽 서빙 엔진의 몫이라 컨테이너가 개입할 수 없다. 자세한 계약·한계는
     `_generate_remote_factory` 주석 참고.
"""
from __future__ import annotations

import csv
import os
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Tuple

import remote
import ugen_data
from evaluate_qwen3_mixatis import generate_batch, load_model_and_tokenizer

# 원본 run_experiment.sh 의 평가 기본값.
DEFAULT_BATCH_SIZE = 16
DEFAULT_MAX_NEW_TOKENS = 128
# 이미지에 baked 된 MixATIS(build.sh 가 seq.out 을 복원해 스테이징한다).
DATA_DIR = os.environ.get(
    "MIXATIS_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "MixATIS_clean"))

CSV_FIELDS = ("sentence", "gold_intents", "pred_intents",
              "gold_slots", "pred_slots", "intent_raw", "slot_raw")


def _generate_remote_factory(endpoint, max_new_tokens: int):
    """messages 배치 → 출력 문자열 배치. 원본 generate_batch 의 원격 판이다.

    반환 시그니처를 `generate_batch(model, tokenizer, msgs, max_new_tokens)` 와 같은
    "messages 리스트 → 문자열 리스트" 로 맞춰 호출부(run_evaluate 의 배치 루프)가
    로컬/원격을 구분하지 않게 한다. 실패 건수는 클로저 밖 카운터로 누적한다.

    ⚠️ chat template — 이 경로는 apply_chat_template 을 **하지 않는다**. 두 가지 이유다.
      1. 못 한다: 대상 모델의 tokenizer 가 없다. 원격 위임의 전제가 "가중치를 이 잡에
         마운트하지 않는다" 이므로 템플릿 문자열을 얻을 방법 자체가 없다.
      2. 하면 안 된다: 템플릿 적용 주체가 **배포의 서빙 엔진마다 다르다**.
         - 임베드 vLLM(deployment_llm/src/llm/playground.py): test_question 을 그대로
           LLM_ENGINE.generate() 에 넣는다 → 템플릿을 아무도 안 붙인다.
         - llama.cpp / TGI / TensorRT-LLM(playground_llamacpp.py, serving_adapter.py):
           test_question 을 user 메시지로 감싸 OpenAI 라우트에 넘긴다 → 엔진이 붙인다.
         컨테이너는 어느 엔진인지 알 수 없다. 여기서 적용하면 후자에서 **이중 적용**
         (특수토큰이 user content 안에 박힘)이 된다. 그래서 템플릿은 배포에 맡기고 이
         컨테이너는 대화 내용(UGEN 지침 + 질문)만 소유한다.
      결과적으로 임베드 vLLM 배포에서는 템플릿이 0회 적용되고, shim 이 system+user 를
      role 라벨 없이 이어 붙인다 → 로컬 경로 점수와 직접 비교하지 마라.

    ⚠️ enable_thinking — 위와 같은 이유로 이 제어가 사라진다. Qwen3 계열 배포가 사고
      블록을 붙이면 UGEN 형식 파싱이 전부 빈 예측이 되므로 strip_think_block 으로
      걷어내는 것이 우리가 할 수 있는 전부다. 근본 대책은 배포 쪽에서 thinking 을 끄는 것.
    """
    # endpoint 는 remote.validate_base_url 이 돌려준 RemoteEndpoint 다 — 검증한 IP 로
    # 연결하고 Host 를 되돌리는 책임은 전부 remote.py 안에 있다(여기서 URL 을 만들지 않는다).
    resolved = remote.detect_model(endpoint)
    batch_fn = remote.batch_chat(endpoint, resolved, max_new_tokens)
    stat = {"model": resolved, "calls": 0, "errors": 0, "last_error": ""}

    def gen(list_of_messages: List[List[Dict[str, str]]]) -> List[str]:
        outs = batch_fn(list_of_messages)
        texts: List[str] = []
        for text, err in outs:
            stat["calls"] += 1
            if err:
                stat["errors"] += 1
                stat["last_error"] = err
                texts.append("")
                continue
            texts.append(remote.strip_think_block(text).strip())
        return texts

    return gen, stat


def run_evaluate(model_path: str, output_dir: str, gpu_devices: str = "0",
                 split: str = "test", limit: int = 0,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
                 use_4bit: bool = False, data_dir: str = DATA_DIR,
                 progress: Callable[[float, str], None] | None = None,
                 adapter_dir: str = "",
                 generate_base_url=None) -> Dict[str, Any]:
    """체크포인트(또는 배포)로 MixATIS test 를 평가하고 예측 4종 리스트 + 통계를 돌려준다.

    generate_base_url(remote.RemoteEndpoint, app.py 가 검증해 넘긴다)을 주면 모델을
    로드하지 않고 그 OpenAI 호환 엔드포인트에 생성을 위임한다. 안 주면 종전대로
    model_path 를 직접 올린다 — 배포가 없는 환경이 있으므로 이 경로는 그대로 남는다.
    """
    def tick(p: float, msg: str) -> None:
        if progress:
            progress(p, msg)

    # 플랫폼이 device 를 격리해 주므로 컨테이너 안에서는 0..n-1 이다.
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices

    examples = ugen_data.build_eval_examples(data_dir, split)
    if limit:
        examples = examples[:limit]
    if not examples:
        raise ValueError(f"평가할 발화가 없다: {data_dir}/{split}")
    tick(0.02, f"{len(examples)} 발화 로드")

    remote_stat = None
    if generate_base_url:
        # 배포 위임 — 가중치·tokenizer 를 올리지 않는다(GPU 점유 0).
        generate_fn, remote_stat = _generate_remote_factory(generate_base_url,
                                                            max_new_tokens)
        print(f"[evaluate] 원격 생성 위임: {generate_base_url.url} "
              f"(model={remote_stat['model']}) — ⚠️ chat template 과 생성 파라미터는 이 "
              f"컨테이너가 아니라 **배포**가 정한다. enable_thinking=False 를 걸 수 "
              f"없으므로 thinking 모델은 배포 쪽에서 꺼야 한다.", flush=True)
        tick(0.10, f"원격 생성 준비 완료({remote_stat['model']})")
    else:
        if not model_path:
            raise ValueError("model_path 가 필요하다 — 체크포인트 없이 로컬 평가는 불가하다 "
                             "(배포에 위임하려면 generate_base_url 을 주어라)")
        # 원본 loader 는 argparse Namespace 를 받는다 — 같은 필드만 채워 넘긴다.
        args = SimpleNamespace(model_name=model_path, adapter_dir=adapter_dir,
                               use_4bit=use_4bit)
        model, tokenizer = load_model_and_tokenizer(args)

        def generate_fn(list_of_messages):
            return generate_batch(model, tokenizer, list_of_messages, max_new_tokens)

        tick(0.10, "모델 로드 완료")

    pred_intents: List[List[str]] = []
    pred_slots: List[List[Tuple[str, str]]] = []
    gold_intents = [e["gold_intents"] for e in examples]
    gold_slots = [[tuple(s) for s in e["gold_slots"]] for e in examples]
    rows: List[Dict[str, str]] = []
    # 형식을 어긴 출력은 파싱에서 조용히 빈 예측이 된다 — 점수가 왜 낮은지 추적하려면
    # 개수를 세어 결과에 실어야 한다(LogicKor 의 unscored 와 같은 이유).
    empty_intent = empty_slot = 0

    for i in range(0, len(examples), batch_size):
        chunk = examples[i:i + batch_size]
        intent_out = generate_fn([c["intent_messages"] for c in chunk])
        slot_out = generate_fn([c["slot_messages"] for c in chunk])
        if remote_stat and remote_stat["errors"] == remote_stat["calls"]:
            # 여기까지 **한 건도** 성공하지 못했다 = 엔드포인트가 죽었거나 계약이 어긋난 것.
            # 남은 배치를 끝까지 쏘지 않고 즉시 멈춘다 — 828 발화 × 2문항 × 재시도(2회,
            # 2·4초 백오프)를 완주하면 실패 하나에 몇 시간이 든다. (detect_model 이 시작
            # 시점에 GET /models 로 한 번 걸러내지만, 서빙 파드가 아직 준비 안 됐을 때처럼
            # /models 는 되고 /chat/completions 만 실패하는 조합이 실제로 있다.)
            # 전부 0.0 인 metrics 를 남기고 '성공' 으로 끝내면 화면에 0 이 정상 점수처럼
            # 박힌다 → 잡을 실패시킨다.
            raise RuntimeError(
                f"원격 생성이 전량 실패했다({remote_stat['errors']}/{remote_stat['calls']}) — "
                f"마지막 오류: {remote_stat['last_error']}")
        for c, io, so in zip(chunk, intent_out, slot_out):
            pi = ugen_data.parse_intent_answer(io)
            ps = ugen_data.parse_slot_answer(so)
            if not pi:
                empty_intent += 1
            if not ps:
                empty_slot += 1
            pred_intents.append(pi)
            pred_slots.append(ps)
            rows.append({
                "sentence": c["sentence"],
                "gold_intents": ";".join(c["gold_intents"]),
                "pred_intents": ";".join(pi),
                "gold_slots": ";".join(f"{v}={n}" for v, n in
                                       [tuple(x) for x in c["gold_slots"]]),
                "pred_slots": ";".join(f"{v}={n}" for v, n in ps),
                "intent_raw": io,
                "slot_raw": so,
            })
        done = min(i + batch_size, len(examples))
        tick(0.10 + 0.85 * done / len(examples), f"{done}/{len(examples)} 발화")

    # 발화별 예측 CSV — 형식 이탈을 사후에 눈으로 진단하는 유일한 수단이라 항상 남긴다.
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "mixatis_eval.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    tick(0.97, "예측 CSV 저장")

    return {
        "pred_intents": pred_intents, "gold_intents": gold_intents,
        "pred_slots": pred_slots, "gold_slots": gold_slots,
        "stats": {
            "utterances": len(examples),
            "split": split,
            "batch_size": batch_size,
            "max_new_tokens": max_new_tokens,
            "use_4bit": bool(use_4bit),
            "adapter": bool(adapter_dir),
            "empty_intent_predictions": empty_intent,
            "empty_slot_predictions": empty_slot,
            "csv": os.path.basename(csv_path),
            # local(이 잡이 가중치 로드) | remote(이미 떠 있는 배포에 위임).
            "mode": "remote" if generate_base_url else "local",
            "endpoint": generate_base_url.url if generate_base_url else None,
            "model": (remote_stat or {}).get("model"),
            # 원격 호출 자체가 실패한 건수 — empty_* 예측의 부분집합이다.
            "generate_errors": (remote_stat or {}).get("errors", 0),
        },
    }
