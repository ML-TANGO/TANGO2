"""LogicKor 답변 생성 — 대상 체크포인트로 42문항 × 2턴 생성 → 미채점 jsonl.

ETRI `Evaluation/Logickor/logickor_eval/generator.py` 를 함수로 재구성한 것이다.
**프롬프트 조립·토큰 예산·샘플링 파라미터를 원본과 같게 유지한다** — 이 셋 중 하나만
달라져도 나온 숫자는 LogicKor 점수가 아니게 되고, 차이를 사후에 추적할 방법이 없다.

원본과 의도적으로 다른 점 2가지
  1. **전략은 default 하나만** 돌린다(원본은 default/1-shot/cot-1-shot 3종 순회).
     한 런 = 한 점수라야 이력·비교표가 성립하고, 3종은 생성량이 3배(252건)라 잡 예산을
     넘긴다. 다른 전략이 필요하면 strategy 파라미터로 고르게 한다(정본은 default).
  2. pandas 를 쓰지 않고 표준 json 으로 읽는다(원본은 pd.read_json). 의존성을 줄이려는
     것이고, 문항 순서와 출력 shape 은 동일하다.

⚠️ 생성 후 심판 모델을 같은 GPU 에 올려야 하므로 release() 로 반드시 해제한다.

생성 경로는 둘이다
  1. **로컬 vLLM**(기본) — 체크포인트를 이 잡이 올린다. 위 설명 전부가 이 경로다.
  2. **원격 위임**(`generate_base_url`) — 이미 떠 있는 배포에 생성을 요청하고 vLLM 을
     아예 올리지 않는다. 대상은 플랫폼의 OpenAI shim
     (`/api/playgrounds/{id}/openai/v1`)이며 클라이언트는 judge.py 것을 그대로 쓴다.
     2턴 구조·전략 프리픽스·문항은 그대로 유지되고 **바뀌는 것은 "누가 토큰을 만드나"뿐**이다.
     차이는 아래 세 가지이며 전부 계약상 불가피하다 — `_generate_remote` 주석 참고.
       (a) chat template 을 이 컨테이너가 적용하지 않는다(적용할 tokenizer 자체가 없다).
       (b) enable_thinking=False 를 걸 수 없다.
       (c) 토큰 단위 예산 절삭 대신 문자 단위 캐리오버 상한을 쓴다.
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# vLLM runtime options (must be set before importing vllm) — 원본 generator.py 동일.
os.environ.setdefault("VLLM_USE_V1", "0")
os.environ.setdefault("CUDA_MODULE_LOADING", "EAGER")
os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")

from templates import PROMPT_STRATEGY  # noqa: E402  (ETRI 원본을 그대로 사용)

# 정본 전략. default 는 few-shot 접두가 없는 빈 리스트여서 프롬프트가
# apply_chat_template([user q1]) 그 자체다.
DEFAULT_STRATEGY = "default"

# 문항셋은 벤치마크 정의 자체라 이미지에 baked 한다(데이터셋 업로드 대상이 아니다).
QUESTIONS_PATH = os.environ.get(
    "LOGICKOR_QUESTIONS_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.jsonl"))

# ── 원본 generator.py 의 토큰 예산 상수(값·이름 그대로) ──
CONTEXT_MARGIN_TOKENS = 256
MAX_CARRYOVER_TOKENS = 896
PROMPT_TRIM_STEP_TOKENS = 128
MIN_QUESTION_TOKENS = 64
MIN_CARRYOVER_TOKENS = 64

STOP_TOKENS = ["<|endoftext|>", "[INST]", "[/INST]", "<|im_end|>", "<|end|>",
               "<|eot_id|>", "<end_of_turn>", "<eos>"]

# ── 원격 위임 경로 상수 ─────────────────────────────────────────────────────
# 캐리오버(1턴 답변)를 2턴 프롬프트에 넣기 전 잘라내는 상한. 로컬 경로는 tokenizer 로
# MAX_CARRYOVER_TOKENS(896) 토큰을 정확히 세지만, 원격 경로에는 대상 모델의 tokenizer 가
# 없다(가중치가 마운트되지 않는 것이 이 기능의 전제다). 그래서 문자 수로 근사한다.
# 계수 2 는 한국어 BPE 의 통상 범위(1.5~2.5 chars/token) 중간값이다 — 정확한 값이 아니라
# **폭주 방지 상한**이 목적이다(배포의 max_new_tokens 는 기본 4096 이라 1턴 답변이 로컬
# 경로의 512 토큰 상한보다 훨씬 길어질 수 있고, 그대로 2턴에 실으면 컨텍스트를 넘긴다).
REMOTE_CARRYOVER_CHARS = MAX_CARRYOVER_TOKENS * 2

# thinking 블록 마커. 원격 경로는 enable_thinking=False 를 걸 수 없어(템플릿을 우리가
# 적용하지 않는다) Qwen3 계열이 <think>…</think> 를 답변 앞에 붙여 보낼 수 있다. 그대로
# 두면 심판 루브릭의 "한국어 미준수" 에 걸려 점수가 반토막 난다(2026-08-25 실측, 42문항
# 중 30문항 0점 / overall 5.13) → 마커가 있을 때만 걷어낸다. 로컬 경로는 애초에 사고
# 블록이 생기지 않으므로 건드리지 않는다(프롬프트·출력을 원본과 한 글자도 다르게 두지 않는다).
THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


def strip_think_block(text: str) -> str:
    """<think>…</think> 를 걷어낸다 — **원격 경로 전용**.

    닫는 태그가 있으면 그 뒤만 남기고, 열기만 있고 닫히지 않았으면(생성 상한에 잘린 경우)
    답변이 존재하지 않는 것이므로 빈 문자열을 돌려준다 — 사고과정을 답변인 척 채점에
    넘기는 것보다 빈 출력(= empty_rows 로 계수)이 낫다.
    """
    t = text or ""
    if THINK_CLOSE in t:
        return t.split(THINK_CLOSE)[-1].strip()
    if THINK_OPEN in t:
        return ""
    return t


def build_messages_single(prefix: List[dict], questions: List[str]) -> List[dict]:
    """1턴 대화 — 전략 프리픽스 + 질문1. 로컬 format_single_turn 의 messages 판이다."""
    return list(prefix) + [{"role": "user", "content": questions[0]}]


def build_messages_double(prefix: List[dict], questions: List[str],
                          single_turn_output: str) -> List[dict]:
    """2턴 대화 — 1턴 답변을 assistant 턴으로 끼우고 후속 질문을 붙인다.

    이게 멀티턴의 정의라 원격이든 로컬이든 같다. 로컬(format_double_turn)과 다른 것은
    캐리오버를 토큰이 아니라 문자로 자르는 것뿐이다(REMOTE_CARRYOVER_CHARS 주석 참고).
    """
    carry = (single_turn_output or "")[:REMOTE_CARRYOVER_CHARS]
    return list(prefix) + [
        {"role": "user", "content": questions[0]},
        {"role": "assistant", "content": carry},
        {"role": "user", "content": questions[1]},
    ]


def _remote_texts(batch_fn, conversations: List[List[dict]], stage: str):
    """원격 배치 1회 → (출력 텍스트 리스트, 실패 건수). 순서는 입력과 같다.

    개별 실패는 빈 출력으로 떨어뜨린다(1건 실패로 42문항을 버리지 않는다). 전량 실패는
    엔드포인트가 죽은 것이므로 예외 — 빈 생성물을 채점해 종합 0.0 을 '정상 점수'로
    화면에 박는 것이 최악이다(judge_file 의 전량 실패 판정과 같은 취지).
    """
    outputs = batch_fn(conversations)
    texts: List[str] = []
    errors = 0
    last_error = ""
    for text, err in outputs:
        if err:
            errors += 1
            last_error = err
            texts.append("")
            continue
        texts.append(finalize_output_text(strip_think_block(text)))
    if errors and errors == len(conversations):
        raise RuntimeError(
            f"{stage}: 생성 호출이 전량 실패했다({errors}/{len(conversations)}) — "
            f"마지막 오류: {last_error}")
    return texts, errors


def max_generation_tokens(model_len: int) -> int:
    """원본 동일: min(512, max(64, model_len // 4))."""
    return min(512, max(64, model_len // 4))


def prompt_token_budget(model_len: int) -> int:
    """원본 동일: model_len − 생성분 − 여유. 이 예산을 넘으면 tail 을 깎는다."""
    return max(1, model_len - max_generation_tokens(model_len) - CONTEXT_MARGIN_TOKENS)


def load_questions(path: str = QUESTIONS_PATH) -> List[Dict[str, Any]]:
    """questions.jsonl → 레코드 목록. utf-8-sig(BOM) — 원본과 같은 인코딩."""
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            q = rec.get("questions")
            if not (isinstance(q, list) and len(q) >= 2):
                raise ValueError(f"문항 {rec.get('id')}: questions 2턴이 필요하다")
            rows.append(rec)
    if not rows:
        raise ValueError(f"문항이 없다: {path}")
    return rows


def create_generator(model_path: str, gpu_devices: str, model_len: int):
    """대상 모델을 vLLM 으로 로드. (llm, SamplingParams) — judge.create_judge 와 동형.

    LLM(...) 인자는 원본 generator.py 와 같게 둔다(attention_config 는 vLLM 버전에 따라
    거부될 수 있어 실패 시 빼고 재시도 — 원본은 고정 환경 전제라 폴백이 없다).
    """
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices
    gpu_counts = len([g for g in gpu_devices.split(",") if g.strip()]) or 1

    from vllm import LLM, SamplingParams

    kwargs = dict(
        model=model_path,
        tensor_parallel_size=gpu_counts,
        max_model_len=model_len,
        gpu_memory_utilization=0.8,
        trust_remote_code=True,
        enforce_eager=True,
    )
    try:
        llm = LLM(attention_config={"backend": "triton_attn"},
                  compilation_config={"mode": 0}, **kwargs)
    except TypeError:
        # 이 빌드의 vLLM 이 해당 인자를 모르면 환경변수(VLLM_ATTENTION_BACKEND)로 이미
        # 같은 백엔드가 지정돼 있으므로 인자만 빼고 로드한다.
        llm = LLM(**kwargs)
    return llm, SamplingParams


def resolve_chat_tokenizer(llm_instance):
    """apply_chat_template 을 가진 tokenizer 를 찾는다 — 원본 동일(래핑 4단까지 탐색).

    이게 실패하면 생성 자체를 하지 않는다: chat template 없이 만든 프롬프트는 LogicKor
    프롬프트가 아니므로 조용히 다른 것을 재는 것보다 실패가 낫다.
    """
    tokenizer = None
    if hasattr(llm_instance, "get_tokenizer"):
        try:
            tokenizer = llm_instance.get_tokenizer()
        except Exception:  # noqa: BLE001
            tokenizer = None
    if tokenizer is None:
        tokenizer = getattr(getattr(llm_instance, "llm_engine", None), "tokenizer", None)

    current = tokenizer
    for _ in range(4):
        if current is None:
            break
        if hasattr(current, "apply_chat_template"):
            return current
        current = getattr(current, "tokenizer", None)
    raise RuntimeError("apply_chat_template 을 가진 tokenizer 를 찾지 못했다")


def supports_thinking_toggle(tok) -> bool:
    """chat template 이 enable_thinking 변수를 실제로 읽는지 본다(Qwen3 계열).

    템플릿 문자열에 그 이름이 없으면 인자를 넘겨봐야 무시되므로 넘기지 않는다 —
    Gemma/EXAONE 같은 비thinking 모델의 프롬프트를 원본과 한 글자도 다르지 않게 유지한다.
    """
    tpl = getattr(tok, "chat_template", None)
    return isinstance(tpl, str) and "enable_thinking" in tpl


def apply_chat(tok, messages: List[dict]) -> str:
    """LogicKor 프롬프트 조립. thinking 모델이면 사고 블록을 끈다.

    ⚠️ 이게 없으면 Qwen3 계열에서 답변이 통째로 날아간다(2026-08-25 클러스터 e2e 실측):
    답변이 <think> 로 시작하는데 생성 상한(min(512, model_len//4))에 사고과정 도중 잘려
    실제 답변이 0글자가 되고, 심판 루브릭의 "한국어 미준수 0점" 에 걸려 42문항 중 30문항이
    0점으로 집계됐다(overall 5.13). ETRI 원본 generator.py 에는 이 처리가 없는데,
    그들은 LogicKor 를 Gemma/EXAONE 으로만 돌렸기 때문이다 — Qwen3 를 쓰는 그들의
    Intent_web/evaluate_qwen3_mixatis.py 에는 enable_thinking=False 가 들어 있다.
    """
    kwargs = {"tokenize": False, "add_generation_prompt": True}
    if supports_thinking_toggle(tok):
        kwargs["enable_thinking"] = False
    return tok.apply_chat_template(messages, **kwargs)


# ── 토큰 유틸 (원본 동일) ──

def _encode(tok, text: str) -> List[int]:
    try:
        return tok.encode(text, add_special_tokens=False)
    except TypeError:
        return tok.encode(text)


def _decode(tok, ids) -> str:
    try:
        return tok.decode(ids, skip_special_tokens=True)
    except TypeError:
        return tok.decode(ids)


def token_len(tok, text: str) -> int:
    return len(_encode(tok, text))


def truncate_to_tokens(tok, text: str, max_tokens: int) -> str:
    ids = _encode(tok, text)
    if len(ids) <= max_tokens:
        return text
    return _decode(tok, ids[:max_tokens]).strip()


def trim_tail_tokens(tok, text: str, trim_step_tokens: int, min_tokens: int) -> str:
    ids = _encode(tok, text)
    if len(ids) <= min_tokens:
        return text
    cut_to = max(min_tokens, len(ids) - trim_step_tokens)
    return _decode(tok, ids[:cut_to]).strip()


def finalize_output_text(text: str) -> str:
    """문장 끝에서 잘린 출력을 마지막 완결 문장까지 되돌린다 — 원본 동일."""
    text = (text or "").strip()
    if not text:
        return text
    if text[-1] in ".!?。！？":
        return text
    last_end = max(text.rfind("."), text.rfind("!"), text.rfind("?"),
                   text.rfind("。"), text.rfind("！"), text.rfind("？"))
    if last_end >= int(len(text) * 0.6):
        return text[: last_end + 1].rstrip()
    return text


# ── 프롬프트 조립 (원본 동일) ──

def format_single_turn(tok, prefix: List[dict], questions: List[str], budget: int) -> str:
    question_1 = questions[0]

    def build(q1: str) -> str:
        return apply_chat(tok, prefix + [{"role": "user", "content": q1}])

    prompt = build(question_1)
    while token_len(tok, prompt) > budget:
        nxt = trim_tail_tokens(tok, question_1, PROMPT_TRIM_STEP_TOKENS, MIN_QUESTION_TOKENS)
        if nxt == question_1:
            break
        question_1 = nxt
        prompt = build(question_1)
    return prompt


def format_double_turn(tok, prefix: List[dict], questions: List[str],
                       single_turn_output: str, budget: int) -> str:
    """1턴 답변을 assistant 턴으로 넣고 후속 질문을 붙인다 — 이게 멀티턴의 정의다.

    예산 초과 시 깎는 순서도 원본과 같다: carry(1턴 답변) → q1 → q2, 그래도 안 되면
    1턴 문맥을 버리고 q2 단독 프롬프트로 폴백한다.
    """
    question_1, question_2 = questions[0], questions[1]
    carry = truncate_to_tokens(tok, single_turn_output, MAX_CARRYOVER_TOKENS)

    def build(q1: str, c: str, q2: str) -> str:
        return apply_chat(tok, prefix + [{"role": "user", "content": q1},
                                        {"role": "assistant", "content": c},
                                        {"role": "user", "content": q2}])

    prompt = build(question_1, carry, question_2)
    while token_len(tok, prompt) > budget:
        nxt = trim_tail_tokens(tok, carry, PROMPT_TRIM_STEP_TOKENS, MIN_CARRYOVER_TOKENS)
        if nxt == carry:
            break
        carry = nxt
        prompt = build(question_1, carry, question_2)
    while token_len(tok, prompt) > budget:
        nxt = trim_tail_tokens(tok, question_1, PROMPT_TRIM_STEP_TOKENS, MIN_QUESTION_TOKENS)
        if nxt == question_1:
            break
        question_1 = nxt
        prompt = build(question_1, carry, question_2)
    while token_len(tok, prompt) > budget:
        nxt = trim_tail_tokens(tok, question_2, PROMPT_TRIM_STEP_TOKENS, MIN_QUESTION_TOKENS)
        if nxt == question_2:
            break
        question_2 = nxt
        prompt = build(question_1, carry, question_2)

    if token_len(tok, prompt) > budget:
        fallback_q2 = question_2

        def build_single(q2: str) -> str:
            return apply_chat(tok, prefix + [{"role": "user", "content": q2}])

        fb = build_single(fallback_q2)
        while token_len(tok, fb) > budget:
            nxt = trim_tail_tokens(tok, fallback_q2, PROMPT_TRIM_STEP_TOKENS,
                                   MIN_QUESTION_TOKENS)
            if nxt == fallback_q2:
                break
            fallback_q2 = nxt
            fb = build_single(fallback_q2)
        return fb
    return prompt


def _generate_remote(base_url, prefix: List[dict], rows: List[Dict[str, Any]],
                     model_len: int,
                     progress_cb: Optional[Callable[[float, str], None]] = None):
    """이미 떠 있는 배포에 42문항 × 2턴 생성을 위임한다 → (1턴, 2턴, meta).

    OpenAI 호환 클라이언트는 judge.py 것을 그대로 쓴다 — 같은 shim, 같은 규약이라
    두 벌을 두면 재시도·동시성·타임아웃이 갈라진다(동시성 8 / 타임아웃 330s /
    재시도 2회는 judge.REMOTE_JUDGE_* 가 정본이다).

    ⚠️ chat template — 이 경로는 apply_chat_template 을 **하지 않는다**. 두 가지 이유다.
      1. 못 한다: 대상 모델의 tokenizer 가 없다. 원격 위임의 전제가 "가중치를 이 잡에
         마운트하지 않는다" 이므로 템플릿 문자열을 얻을 방법 자체가 없다.
      2. 하면 안 된다: 템플릿 적용 주체가 **배포의 서빙 엔진마다 다르다**.
         - 임베드 vLLM(deployment_llm/src/llm/playground.py): test_question 을 그대로
           LLM_ENGINE.generate() 에 넣는다 → 템플릿을 아무도 안 붙인다.
         - llama.cpp / TGI / TensorRT-LLM(playground_llamacpp.py, serving_adapter.py):
           test_question 을 user 메시지로 감싸 /v1/chat/completions 에 넘긴다 →
           엔진이 템플릿을 붙인다.
         컨테이너는 어느 엔진인지 알 수 없다. 여기서 템플릿을 적용하면 후자에서
         **이중 적용**(특수토큰이 user content 안에 박힘)이 된다. 그래서 템플릿은
         전적으로 배포 쪽에 맡기고 이 컨테이너는 대화 내용만 소유한다 — judge.py 의
         원격 심판 경로와 같은 규약이다.
      결과적으로 임베드 vLLM 배포에서는 템플릿이 0회 적용된다(플랫폼의 배포 추론 화면이
      늘 그렇게 동작한다). 로컬 vLLM 경로의 점수와 직접 비교하지 마라.

    ⚠️ enable_thinking — 템플릿을 우리가 안 붙이므로 이 제어가 **사라진다**. Qwen3 계열
      배포는 사고 블록을 답변 앞에 붙일 수 있다 → strip_think_block 으로 걷어내는 것이
      우리가 할 수 있는 전부다. 근본 대책은 배포 쪽에서 thinking 을 끄는 것이다.

    ⚠️ shim 은 body 의 temperature·max_tokens·model 을 무시하고 **배포 시점 설정**을
      따른다. 즉 이 경로의 생성은 greedy 가 아닐 수 있고, 그러면 같은 체크포인트라도
      런마다 점수가 달라진다. 로그와 metrics.generate 에 남겨 추적 가능하게 한다.
    """
    import judge  # 같은 이미지의 OpenAI 호환 클라이언트(재구현 금지)

    # 1차 게이트는 app.py `_resolve_generate_base_url` 이다(judge.RemoteEndpoint 로
    # 넘어온다 — 검증한 IP 고정 포함). 여기서도 스킴만은 다시 본다 — 이 함수는 그 게이트를
    # 거치지 않고도 호출될 수 있고 file:// 같은 스킴이 새면 안 된다.
    if not base_url.connect_url.startswith(("http://", "https://")):
        raise ValueError("generate_base_url must be http or https")

    if progress_cb:
        progress_cb(0.02, f"using remote generator at {base_url.url}")
    resolved = judge.detect_remote_model(base_url, label="생성")
    # max_tokens 는 플랫폼 shim 이 무시하지만 그대로 싣는다 — 일반 OpenAI 호환
    # 엔드포인트(vLLM serve 등)에 붙였을 때는 실제로 먹기 때문이다(judge.py 동일 관행).
    batch_fn = judge.remote_batch(base_url, resolved, max_generation_tokens(model_len))
    print(f"[generate] 원격 생성 위임: {base_url.url} (model={resolved}) — ⚠️ chat template 과 "
          f"생성 파라미터(temperature/max_tokens)는 이 컨테이너가 아니라 **배포**가 정한다. "
          f"enable_thinking=False 를 걸 수 없으므로 thinking 모델은 배포 쪽에서 꺼야 한다.",
          flush=True)

    if progress_cb:
        progress_cb(0.12, f"generating single-turn via deployment ({len(rows)} questions)")
    single_outputs, err_single = _remote_texts(
        batch_fn, [build_messages_single(prefix, r["questions"]) for r in rows], "1턴")

    if progress_cb:
        progress_cb(0.55, "generating multi-turn via deployment")
    multi_outputs, err_multi = _remote_texts(
        batch_fn,
        [build_messages_double(prefix, r["questions"], out)
         for r, out in zip(rows, single_outputs)], "2턴")

    return single_outputs, multi_outputs, {
        "mode": "remote", "endpoint": base_url.url, "model": resolved,
        "errors": err_single + err_multi,
    }


def release(llm) -> None:
    """vLLM 인스턴스를 해제해 GPU 를 비운다 — 심판 모델을 같은 카드에 올리기 위한 전제.

    해제 단계마다 개별로 감싼다: 생성이 성공한 뒤 teardown 예외로 잡 전체를 잃는 것이
    최악이고, vLLM 버전에 따라 없는 심볼이 있다. 실패해도 진행하되 무엇이 실패했는지는
    남긴다(해제가 덜 되면 다음 로드가 OOM 으로 죽으므로 진단 단서가 필요하다).
    """
    problems: List[str] = []
    try:
        from vllm.distributed.parallel_state import (  # type: ignore
            destroy_distributed_environment, destroy_model_parallel)
        try:
            destroy_model_parallel()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"destroy_model_parallel: {exc}")
        try:
            destroy_distributed_environment()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"destroy_distributed_environment: {exc}")
    except ImportError as exc:
        problems.append(f"parallel_state import: {exc}")

    try:
        if hasattr(llm, "llm_engine"):
            del llm.llm_engine
    except Exception as exc:  # noqa: BLE001
        problems.append(f"del llm_engine: {exc}")
    try:
        del llm
    except Exception:  # noqa: BLE001
        pass

    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"cuda empty_cache: {exc}")

    if problems:
        print(json.dumps({"event": "log", "level": "warn",
                          "message": "vLLM 해제 일부 실패(다음 로드 OOM 가능)",
                          "problems": problems}, ensure_ascii=False), flush=True)


def run_generate(model_path: str, output_dir: str, gpu_devices: str = "0",
                 model_len: int = 4096, strategy: str = DEFAULT_STRATEGY,
                 questions_path: str = QUESTIONS_PATH,
                 progress_cb: Optional[Callable[[float, str], None]] = None,
                 generate_base_url=None) -> Dict[str, Any]:
    """전 문항 1턴→2턴 생성 → output_dir/<strategy>.jsonl.

    1턴 전량을 한 배치로 돌린 뒤 그 출력을 2턴 프롬프트에 넣고 다시 전량 배치한다
    (원본 동일). 문항별로 나눠 호출하면 vLLM 배치 이득이 사라진다.

    generate_base_url(judge.RemoteEndpoint, app.py 가 검증해 넘긴다)을 주면 **vLLM 로드를
    건너뛰고** 이미 떠 있는 배포에 생성을 위임한다(_generate_remote 주석에 계약·한계 전부).
    안 주면 종전대로 model_path 체크포인트를 직접 올린다 — 배포가 없는 환경이 있으므로
    이 경로는 그대로 남는다.
    """
    if strategy not in PROMPT_STRATEGY:
        raise ValueError(f"알 수 없는 전략: {strategy} (가능: {list(PROMPT_STRATEGY)})")
    prefix = PROMPT_STRATEGY[strategy]

    rows = load_questions(questions_path)

    if generate_base_url:
        single_outputs, multi_outputs, gen_meta = _generate_remote(
            generate_base_url, prefix, rows, model_len, progress_cb)
    else:
        if not model_path:
            raise ValueError("model_path 가 필요하다 — 체크포인트 없이 로컬 생성은 불가하다 "
                             "(배포에 위임하려면 generate_base_url 을 주어라)")
        budget = prompt_token_budget(model_len)
        if progress_cb:
            progress_cb(0.02, f"loading target model {model_path}")
        llm, SamplingParams = create_generator(model_path, gpu_devices, model_len)
        try:
            tok = resolve_chat_tokenizer(llm)
            sampling_params = SamplingParams(
                temperature=0, skip_special_tokens=True,
                max_tokens=max_generation_tokens(model_len), stop=STOP_TOKENS)

            if progress_cb:
                progress_cb(0.12, f"generating single-turn ({len(rows)} questions)")
            single_prompts = [format_single_turn(tok, prefix, r["questions"], budget)
                              for r in rows]
            single_outputs = [finalize_output_text(o.outputs[0].text)
                              for o in llm.generate(single_prompts, sampling_params)]

            if progress_cb:
                progress_cb(0.55, "generating multi-turn")
            # 1턴 출력과 문항을 **파일 순서로** 짝짓는다. 원본은 id-1 로 인덱싱하는데 그건
            # id 가 1..N 연속일 때만 맞고, 여기선 순서 짝이 그 조건 없이 같은 결과를 준다.
            multi_prompts = [format_double_turn(tok, prefix, r["questions"], out, budget)
                             for r, out in zip(rows, single_outputs)]
            multi_outputs = [finalize_output_text(o.outputs[0].text)
                             for o in llm.generate(multi_prompts, sampling_params)]
        finally:
            # 성공이든 실패든 GPU 를 비운다 — 심판 로드가 이 뒤에 온다.
            release(llm)
        gen_meta = {"mode": "vllm", "endpoint": None, "model": model_path, "errors": 0}

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{strategy}.jsonl"
    # judge/scoring 이 utf-8-sig 로 읽으므로 같은 인코딩으로 쓴다(원본 산출물 규약).
    with out_path.open("w", encoding="utf-8-sig") as fh:
        for r, s_out, m_out in zip(rows, single_outputs, multi_outputs):
            fh.write(json.dumps({
                "id": r.get("id"),
                "category": r.get("category"),
                "questions": r["questions"],
                "outputs": [s_out, m_out],
                "references": r.get("references") or [None, None],
            }, ensure_ascii=False) + "\n")

    empty = sum(1 for s, m in zip(single_outputs, multi_outputs) if not s and not m)
    if empty == len(rows):
        raise ValueError(
            "생성 결과가 전부 비었다 — 체크포인트/템플릿을 확인하라"
            if gen_meta["mode"] == "vllm" else
            "생성 결과가 전부 비었다 — 배포가 답을 돌려주지 않았거나 thinking 블록만 "
            "돌려주고 있다(배포 쪽에서 thinking 을 끄고 다시 실행하라)")

    if progress_cb:
        progress_cb(0.95, f"generated {len(rows)} rows → {out_path.name}")
    return {
        "model_path": model_path, "strategy": strategy, "rows": len(rows),
        "model_len": model_len, "max_output_tokens": max_generation_tokens(model_len),
        "empty_rows": empty, "output": str(out_path.relative_to(out_dir.parent))
        if out_dir.parent in out_path.parents else out_path.name,
        # vllm(이 잡이 가중치를 올림) | remote(이미 떠 있는 배포에 위임).
        "mode": gen_meta["mode"], "endpoint": gen_meta["endpoint"],
        "model": gen_meta["model"],
        # 원격 호출 자체가 실패한 건수 — empty_rows 의 부분집합이다.
        "errors": gen_meta["errors"],
    }
