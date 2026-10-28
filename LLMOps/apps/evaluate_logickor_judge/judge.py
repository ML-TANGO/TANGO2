"""LogicKor 심판 채점 — 미채점 생성물(jsonl) → 심판 점수가 박힌 evaluated jsonl.

ETRI `Evaluation/Logickor_web/logickor_eval/evaluator.py` 의 로직을 CLI 스크립트에서
함수로 재구성한 것이다. **프롬프트 구성과 점수 파싱은 원본과 글자 단위로 같게 유지한다** —
여기서 달라지면 우리 점수가 ETRI 재현값과 어긋나고, 그 차이를 사후에 추적할 방법이 없다.
심판 시스템 프롬프트(JUDGE_TEMPLATE)는 원본 templates.py 를 그대로 임포트해 쓴다(복제 금지).

vLLM 런타임 옵션은 import 전에 세팅해야 하므로 모듈 최상단에서 처리한다(원본 동일).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

# vLLM runtime options (must be set before importing vllm) — 원본 evaluator.py 동일.
os.environ.setdefault("VLLM_USE_V1", "0")
os.environ.setdefault("CUDA_MODULE_LOADING", "EAGER")
os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")

from templates import JUDGE_TEMPLATE  # noqa: E402  (원본 파일을 그대로 사용)

# 심판 프리셋 — 원본은 llama 를 개발자 개인 경로(/home/parkjb/...)로 박아뒀다. 컨테이너에서
# 존재하지 않는 경로라 제거하고, 공개 HF repo id 만 남긴다. 프리셋에 없는 값은 그대로
# 통과시키므로(원본 resolve 규약 유지) 임의 HF id·로컬 경로도 쓸 수 있다.
JUDGE_MODEL_PRESETS = {
    "gemma": "google/gemma-4-E4B-it",
}
DEFAULT_JUDGE_MODEL = "gemma"


def resolve_judge_model(judge_model: str) -> str:
    """프리셋 이름이면 매핑, 아니면 그대로 통과(원본 동일 규약)."""
    return JUDGE_MODEL_PRESETS.get(judge_model, judge_model)


def create_judge(judge_model: str, gpu_devices: str, model_len: int):
    """심판 모델을 vLLM 으로 로드. (llm, SamplingParams) 반환."""
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices
    gpu_counts = len([g for g in gpu_devices.split(",") if g.strip()]) or 1

    from vllm import LLM, SamplingParams

    llm = LLM(
        model=judge_model,
        tensor_parallel_size=gpu_counts,
        max_model_len=model_len,
        gpu_memory_utilization=0.8,
        trust_remote_code=True,
        enforce_eager=True,
    )
    return llm, SamplingParams


# ── 원격 심판(OpenAI 호환 엔드포인트) ────────────────────────────────────────
# judge_base_url 을 주면 vLLM 로드를 건너뛰고 **이미 떠 있는 배포**에 채점을 요청한다.
# 대상은 플랫폼의 OpenAI shim(llm_playground: /api/playgrounds/{id}/openai/v1)이다 —
# 서빙 pod 자체는 OpenAI HTTP API 를 노출하지 않으므로 shim 을 반드시 경유해야 한다
# (프롬프트 최적화 컨테이너가 같은 경로를 이미 소비한다).
#
# ⚠️ 재현성 경고 — shim 은 body 의 model·temperature·max_tokens 를 **무시한다**.
#    대상 모델은 playground_id 로 확정되고 생성 파라미터는 **배포 시점 설정**을 따른다.
#    즉 이 경로에서 temperature=0 을 실어 보내도 아무 효과가 없다. 심판 배포가
#    temperature 0 으로 떠 있지 않으면 같은 입력에 다른 점수가 나오고, 그 차이는
#    산출물만 봐서는 추적되지 않는다 → run_judge 가 로그로 경고하고 app.py 가
#    metrics.judge 에 mode/endpoint/note 를 새긴다.
#
# ⚠️ 프롬프트 병합 — shim 의 _messages_to_prompt 는 assistant 턴이 없으면 role 라벨 없이
#    content 만 "\n\n" 으로 이어 붙인다. 우리 대화는 system(JUDGE_TEMPLATE) + user 2턴이라
#    심판 모델은 system role 없이 "지침 + 평가대상" 한 덩어리를 받는다. 프롬프트 문자열
#    자체는 보존되지만 role 분리에 기대는 지시 준수는 약해질 수 있다 — vLLM 경로(chat
#    template 적용)와 점수를 직접 비교하지 마라.

# 동시성 상한. 근거:
#  - vLLM 경로는 84건(42문항 × 2턴)을 llm.chat 한 배치로 눌렀다. HTTP 로 쪼갠 뒤 순차
#    호출하면 1건당 수십 초 × 84 = 파일 하나에 수십 분이 된다.
#  - 반대로 무제한 fan-out 은 (a) 심판 배포 1개의 추론 큐를 넘겨 타임아웃을 만들고,
#    (b) shim 호출 1건이 플랫폼 BFF(llm_playground)의 요청을 최대 300초 점유하므로
#    화면과 다른 잡까지 굶긴다.
#  - 8 은 그 사이 — 단일 서빙 배포가 무리 없이 배치로 소화하는 수준이다.
REMOTE_JUDGE_CONCURRENCY = 8
# shim 내부 추론 타임아웃이 300초다(llm_playground `_SHIM_TIMEOUT`). 그보다 조금 길게 잡아야
# 우리 쪽 타임아웃이 shim 이 돌려주는 실제 에러 메시지를 덮어쓰지 않는다.
REMOTE_JUDGE_TIMEOUT = 330.0
# 순간 오류(연결 리셋·502·빈 응답)만 재시도한다. 점수 파싱 실패는 재시도 대상이 아니다 —
# 같은 프롬프트를 같은 배포에 다시 보내는 것이라 결과가 달라질 이유가 없다.
REMOTE_JUDGE_RETRIES = 2


class RemoteEndpoint(NamedTuple):
    """검증이 끝난 원격 엔드포인트. 연결은 **검증한 IP** 로만 하고 Host 는 되돌린다.

    app.py `_resolve_remote_base_url` 이 만들어 넘긴다(그쪽이 SSRF 게이트다). 여기 두는
    이유는 이 값을 실제로 소비하는 HTTP 클라이언트가 이 파일에 있기 때문이다 —
    generate.py 도 같은 클라이언트를 재사용한다.

      url         표시·기록용 원본 URL. 로그와 metrics.*.endpoint 는 이걸 쓴다 —
                  IP 만 남기면 어느 배포였는지 사후에 추적할 수 없다.
      connect_url host 를 검증한 IP 로 치환한 URL. 실제 요청은 이것으로만 나간다
                  (호스트명을 그대로 넘기면 httpx 가 연결 시점에 다시 resolve 해
                   DNS rebinding TOCTOU 창이 열린다).
      host_header 원본 host[:port]. IP 로 붙었으므로 Host 를 직접 세워야 shim 의
                  라우팅이 원래대로 동작한다.
      sni         https 일 때 TLS SNI·인증서 검증에 쓸 원본 hostname(http 면 None).

    ⚠️ evaluate_intent/remote.py 에 같은 타입이 있다(두 컨테이너는 공유 파일이 없다) —
       한쪽을 고치면 다른 쪽도 함께 봐야 한다.
    """
    url: str
    connect_url: str
    host_header: str
    sni: Optional[str]

    def request_kwargs(self) -> dict:
        """모든 요청에 그대로 펼쳐 넣는다 — Host 복원 + (https) SNI/인증서 대상 복원."""
        kwargs: dict = {"headers": {"Host": self.host_header}}
        if self.sni:
            # httpx → httpcore 확장. IP 로 연결하면서도 TLS 핸드셰이크의 SNI 와 인증서
            # hostname 검증은 **원래 이름**으로 한다(검증을 끄지 않는다). 이 확장을 모르는
            # httpcore 라면 무시되고 인증서가 IP 와 불일치해 연결이 실패한다 —
            # fail-open 이 아니라 fail-closed 라 뚫리는 경로가 생기지 않는다.
            kwargs["extensions"] = {"sni_hostname": self.sni}
        return kwargs


def _remote_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def detect_remote_model(endpoint: RemoteEndpoint, label: str = "심판") -> str:
    """GET {base}/models 의 data[0].id — 원격 엔드포인트가 서빙하는 모델 식별자.

    shim 은 이 playground 가 서빙하는 모델 1건만 돌려준다. 실패하면 예외 —
    엔드포인트가 죽었는데 84건을 쏘아 전량 실패로 끝나는 것보다 여기서 멈추는 게 낫다.
    label 은 오류 문구에만 쓴다(generate.py 가 같은 함수를 '생성' 라벨로 재사용한다) —
    엔드포인트 규약이 동일하므로 클라이언트를 두 벌 두지 않는다.
    """
    import httpx      # ETRI 스냅샷(etri-infer.txt)에 httpx==0.28.1 이 있다(추가 deps 없음).

    url = _remote_url(endpoint.connect_url, "/models")
    shown = _remote_url(endpoint.url, "/models")   # 오류 문구는 사용자가 준 주소로 말한다
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, **endpoint.request_kwargs())
    except Exception as exc:   # noqa: BLE001 — 연결/DNS/TLS 무엇이든 같은 진단이 필요하다
        # 원문 예외(ConnectError: All connection attempts failed)만으로는 어느 주소를
        # 못 잡았는지 알 수 없다. 잡 실패 메시지가 그대로 화면에 뜨므로 URL 을 붙인다.
        # 고정한 IP 도 같이 붙인다 — 이름은 풀렸는데 그 IP 가 안 열리는 경우가 갈린다.
        raise RuntimeError(f"{label} endpoint {shown}(→ {url}) 에 연결할 수 없다 "
                           f"({type(exc).__name__}: {exc}) — {label} 배포가 실행 중인지, "
                           f"잡 파드에서 도달 가능한 주소인지 확인하라") from exc
    if r.status_code != 200:
        raise RuntimeError(f"{label} endpoint {shown} → HTTP {r.status_code}: {r.text[:200]}")
    try:
        data = (r.json() or {}).get("data") or []
    except ValueError as exc:
        raise RuntimeError(f"{label} endpoint {shown} 응답이 JSON 이 아니다: "
                           f"{str(r.text)[:200]}") from exc
    if not data or not isinstance(data[0], dict) or not data[0].get("id"):
        raise RuntimeError(f"{label} endpoint {shown} 응답에 모델이 없다: {str(r.text)[:200]}")
    return str(data[0]["id"])


def _vllm_batch(llm, sampling_params) -> Callable[[List[List[Dict[str, str]]]],
                                                  List[Tuple[Optional[str], Optional[str]]]]:
    """기존 경로 — 대화 전체를 한 배치로 vLLM 에 넘긴다. 실패는 예외로 터진다(부분 실패 없음)."""
    def run(conversations):
        outputs = llm.chat(conversations, sampling_params, use_tqdm=False)
        return [(out.outputs[0].text, None) for out in outputs]
    return run


def _one_factory(client, url: str, model: str, max_output_tokens: int,
                 req_kwargs: dict):
    """단건 호출 클로저 — (text, None) 또는 (None, error) 를 돌려준다(예외를 올리지 않는다).

    req_kwargs 는 RemoteEndpoint.request_kwargs() 결과다(Host 복원 + https SNI). 읽기
    전용이라 워커 스레드가 공유해도 안전하다.
    """
    def one(messages):
        # temperature/max_tokens 는 플랫폼 shim 이 무시하지만 그대로 싣는다 — 이 컨테이너를
        # 일반 OpenAI 호환 엔드포인트(vLLM serve 등)에 붙였을 때는 실제로 먹기 때문이다.
        payload = {"model": model, "messages": messages,
                   "temperature": 0.0, "max_tokens": max_output_tokens,
                   "stream": False}
        last = "unknown error"
        for attempt in range(REMOTE_JUDGE_RETRIES + 1):
            try:
                r = client.post(url, json=payload, **req_kwargs)
                if r.status_code != 200:
                    last = f"HTTP {r.status_code}: {r.text[:200]}"
                else:
                    choices = (r.json() or {}).get("choices") or []
                    msg = (choices[0] or {}).get("message") if choices else None
                    text = (msg or {}).get("content")
                    if isinstance(text, str) and text.strip():
                        return text, None
                    last = "empty content in response"
            except Exception as exc:   # noqa: BLE001 — 네트워크/파싱 무엇이든 재시도 대상
                last = f"{type(exc).__name__}: {exc}"
            if attempt < REMOTE_JUDGE_RETRIES:
                time.sleep(2.0 * (attempt + 1))
        return None, last
    return one


def remote_batch(endpoint: RemoteEndpoint, model: str, max_output_tokens: int
                  ) -> Callable[[List[List[Dict[str, str]]]],
                                List[Tuple[Optional[str], Optional[str]]]]:
    """원격 경로 — 제한된 워커 풀로 /chat/completions 를 호출한다.

    반환은 vLLM 경로와 같은 (text, error) 리스트이며 **입력 순서를 보존한다**(호출부가
    meta 와 zip 으로 짝지으므로 순서가 어긋나면 점수가 다른 문항에 붙는다 — pool.map 이
    순서를 보장한다).
    개별 실패는 예외로 올리지 않고 error 문자열로 내려보낸다 — 1건 실패로 84건을 버리지
    않되, 실패 자체는 호출부가 세어 통계(errors)와 전량 실패 판정에 쓴다.
    """
    import httpx      # ETRI 스냅샷(etri-infer.txt)에 httpx==0.28.1 이 있다(추가 deps 없음).
    from concurrent.futures import ThreadPoolExecutor

    url = _remote_url(endpoint.connect_url, "/chat/completions")
    req_kwargs = endpoint.request_kwargs()

    def run(conversations):
        limits = httpx.Limits(max_connections=REMOTE_JUDGE_CONCURRENCY,
                              max_keepalive_connections=REMOTE_JUDGE_CONCURRENCY)
        # httpx.Client 는 스레드 세이프하고 커넥션 풀을 공유한다 — 워커마다 새로 만들면
        # 84건 동안 TCP 핸드셰이크를 84번 한다. 풀은 IP origin 에 키되므로 재resolve 없이
        # 고정한 주소로만 붙는다.
        with httpx.Client(timeout=REMOTE_JUDGE_TIMEOUT, limits=limits) as client:
            one = _one_factory(client, url, model, max_output_tokens, req_kwargs)
            with ThreadPoolExecutor(max_workers=REMOTE_JUDGE_CONCURRENCY) as pool:
                return list(pool.map(one, conversations))
    return run


def build_prompt(model_output: Dict[str, Any], is_multi_turn: bool) -> Tuple[str, str]:
    """(system, user) 메시지 구성 — 원본 evaluator.build_prompt 와 동일."""
    model_questions = model_output["questions"]
    model_outputs = model_output["outputs"]
    model_references = model_output["references"]

    prompt = (
        f"아래의 내용을 주어진 평가 기준들을 충실히 반영하여 평가해라. 특히 모델 답변이 언어 요구사항을 준수하는지 반드시 확인해야 한다.\n\n"
        f"**Question**\n{model_questions[0]}"
    )
    if model_references and model_references[0]:
        prompt += f"\n\n**Additional Reference**\n{model_references[0]}"
    prompt += f"\n\n**Model's Response**\n{model_outputs[0]}"

    if is_multi_turn:
        prompt += f"\n\n**Follow-up Question.**\n{model_questions[1]}"
        if model_references and model_references[1]:
            prompt += f"\n\n**Additional Reference**\n{model_references[1]}"
        prompt += f"\n\n**Model's Response**\n{model_outputs[1]}"

    prompt += "\n\n[[대화 종료. 평가 시작.]]"
    system_content = JUDGE_TEMPLATE["multi_turn" if is_multi_turn else "single_turn"]
    return system_content, prompt


def parse_judgement(content: Optional[str]) -> Dict[str, Any]:
    """심판 출력 텍스트 → {judge_message, judge_score} — 원본과 동일 정규식.

    점수를 못 찾으면 0 점 + 사유를 메시지에 남긴다(원본 동일). 0 점이 조용히 평균을
    끌어내리므로 호출부가 그 개수를 세어 로그로 노출한다.
    """
    if content is None:
        content = ""
    cleaned = content.replace("*", "")

    m = re.search(r"평가:(.*?)점수:", cleaned, re.DOTALL)
    judge_message = m.group(1).strip() if m else "No judge message found"

    sm = re.search(r"점수:\s*(\d+(\.\d+)?)", cleaned)
    if sm:
        judge_score = float(sm.group(1))
    else:
        judge_message = "Impossible to judge: no score found in response."
        judge_score = 0.0
    return {"judge_message": judge_message, "judge_score": judge_score}


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def list_inputs(input_root: str) -> List[Path]:
    """채점 대상 jsonl 목록(숨김 제외).

    ⚠️ 심볼릭 링크는 따라가지 않는다. 데이터셋 내용은 사용자가 올린 tar/zip 이라 신뢰할
    수 없고, 호출부의 루트 검증(_resolve_input_root)은 루트 자체만 본다. 링크가 남아 있으면
    마운트 밖 파일이 심판 프롬프트와 /output/evaluated 아티팩트로 흘러나갈 수 있다.
    scoring.resolve_paths 와 같은 규칙(os.walk followlinks=False + islink 거부 +
    realpath 재검증)을 쓴다 — 두 컨테이너의 입력 수집 규칙이 갈라지면 안 된다.
    """
    real_root = os.path.realpath(input_root)

    def within(path: str) -> bool:
        try:
            return os.path.commonpath([os.path.realpath(path), real_root]) == real_root
        except ValueError:
            return False

    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(input_root, followlinks=False):
        dirnames[:] = [d for d in dirnames
                       if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not within(full):
                continue
            p = Path(full)
            if not _is_hidden(p.relative_to(input_root)):
                found.append(p)
    return sorted(found)


def judge_file(batch_fn, in_path: Path, out_path: Path) -> Dict[str, int]:
    """파일 1개 채점 → out_path 에 query_single/query_multi 를 붙여 기록.

    한 파일의 전 문항 × 2턴을 **한 번에** batch_fn 에 넘긴다(원본 동일) — 문항별로 나눠
    호출하면 vLLM 배치 이득이 사라져 42문항이 수십분으로 늘어난다. batch_fn 은 대화
    리스트를 받아 같은 순서의 (text, error) 리스트를 돌려준다(_vllm_batch/remote_batch).
    """
    # 깨진 행은 스킵한다 — CPU 집계기(scoring.iter_records)와 같은 방어 수준. 한 줄
    # 파싱 실패로 42문항×2턴 배치와 수십 분짜리 GPU 잡 전체를 날리면 안 된다.
    rows: List[Dict[str, Any]] = []
    skipped = 0
    with open(in_path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            # build_prompt 가 요구하는 최소 shape 검증(없으면 IndexError 로 배치 전체 소실).
            q, o = rec.get("questions"), rec.get("outputs")
            if not (isinstance(q, list) and isinstance(o, list)
                    and len(q) >= 2 and len(o) >= 2):
                skipped += 1
                continue
            rec.setdefault("references", [None, None])
            rows.append(rec)

    if not rows:
        raise ValueError(
            f"{in_path.name}: 채점 가능한 행이 없다(스킵 {skipped}) — questions/outputs "
            "각 2턴을 가진 generator 산출물이 필요하다")

    conversations = []
    meta: List[Tuple[int, str]] = []
    for idx, row in enumerate(rows):
        for turn_key, is_multi in (("single", False), ("multi", True)):
            system_content, user_content = build_prompt(row, is_multi)
            conversations.append([
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ])
            meta.append((idx, turn_key))

    outputs = batch_fn(conversations)

    results: Dict[int, Dict[str, Dict]] = {}
    unscored = 0
    errors = 0
    last_error = ""
    for (idx, turn_key), (text, err) in zip(meta, outputs):
        if err:
            # 조용히 0 점 처리하지 않는다 — 사유를 평가문 자리에 남기고 별도로 센다.
            # errors ⊆ unscored(둘 다 0 점) 이며, errors 는 "심판이 답을 못 준 것",
            # unscored 는 "0 점으로 집계된 것" 이다.
            errors += 1
            last_error = err
            parsed = {"judge_message": f"Impossible to judge: {err}",
                      "judge_score": 0.0}
        else:
            parsed = parse_judgement(text)
        if parsed["judge_score"] == 0.0:
            unscored += 1
        results.setdefault(idx, {})[turn_key] = parsed

    # 전량 실패 = 엔드포인트가 죽었거나 계약이 어긋난 것이다. 0 점짜리 evaluated 파일을
    # 남기고 "성공" 으로 끝내면 화면에 종합 0.0 이 정상 점수처럼 박힌다 → 잡을 실패시킨다.
    if errors and errors == len(meta):
        raise RuntimeError(
            f"{in_path.name}: 심판 호출이 전량 실패했다({errors}/{len(meta)}) — 마지막 오류: {last_error}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig") as fh:
        for idx, row in enumerate(rows):
            row["query_single"] = results[idx]["single"]
            row["query_multi"] = results[idx]["multi"]
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"rows": len(rows), "judged": len(meta), "unscored": unscored,
            "skipped": skipped, "errors": errors}


def run_judge(input_root: str, output_root: str, judge_model: str = DEFAULT_JUDGE_MODEL,
              gpu_devices: str = "0", model_len: int = 8192,
              max_output_tokens: int = 1024,
              hf_token: Optional[str] = None,
              progress_cb: Optional[Callable[[float, str], None]] = None,
              judge_base_url: Optional[RemoteEndpoint] = None) -> Dict[str, Any]:
    """input_root 하위 jsonl 전부 채점 → output_root 에 같은 상대경로로 기록.

    judge_base_url 을 주면 **vLLM 로드를 건너뛰고** 그 OpenAI 호환 엔드포인트로 채점한다
    (심판 모델은 GET {base}/models 로 자동감지). 안 주면 종전대로 심판 모델을 직접 올린다 —
    심판 배포가 없는 환경이 있으므로 이 경로는 그대로 남는다.
    judge_base_url 은 app.py `_resolve_judge_base_url` 이 이미 검증한 RemoteEndpoint 다
    (SSRF 게이트 + 검증한 IP 고정).
    """
    inputs = list_inputs(input_root)
    if not inputs:
        raise FileNotFoundError(f"no *.jsonl under {input_root}")

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    if judge_base_url:
        # 1차 게이트는 app.py 다. 여기서도 스킴만은 다시 본다 — 이 함수는 그 게이트를
        # 거치지 않고도 호출될 수 있고, file:// 같은 스킴이 새어 들어오면 안 된다.
        if not judge_base_url.connect_url.startswith(("http://", "https://")):
            raise ValueError("judge_base_url must be http or https")
        if progress_cb:
            progress_cb(0.05, f"using remote judge at {judge_base_url.url}")
        resolved = detect_remote_model(judge_base_url)
        batch_fn = remote_batch(judge_base_url, resolved, max_output_tokens)
        mode = "remote"
        # 결정성 경고를 로그에 남긴다(app.py 가 stdout 을 /output/run.log 로 tee 한다).
        # 산출물의 metrics.judge.note 와 짝이며, 점수가 재현되지 않을 때 첫 단서다.
        print(f"[judge] 원격 심판 사용: {judge_base_url.url} (model={resolved}, "
              f"concurrency={REMOTE_JUDGE_CONCURRENCY}) — ⚠️ 이 엔드포인트(플랫폼 shim)는 "
              f"temperature·max_tokens 를 무시하고 **배포 시점 설정**을 따른다. 심판 배포가 "
              f"temperature 0 으로 떠 있지 않으면 점수가 재현되지 않는다.", flush=True)
    else:
        resolved = resolve_judge_model(judge_model)
        if progress_cb:
            progress_cb(0.05, f"loading judge model {resolved}")
        llm, SamplingParams = create_judge(resolved, gpu_devices, model_len)
        batch_fn = _vllm_batch(llm, SamplingParams(temperature=0.0,
                                                   max_tokens=max_output_tokens))
        mode = "vllm"

    in_root = Path(input_root)
    out_root = Path(output_root)
    stats = {"files": 0, "rows": 0, "judged": 0, "unscored": 0, "skipped": 0,
             "errors": 0, "judge_model": resolved, "judge_mode": mode,
             "judge_endpoint": judge_base_url.url if judge_base_url else None,
             "outputs": []}
    for i, path in enumerate(inputs, start=1):
        rel = path.relative_to(in_root)
        s = judge_file(batch_fn, path, out_root / rel)
        stats["files"] += 1
        stats["rows"] += s["rows"]
        stats["judged"] += s["judged"]
        stats["unscored"] += s["unscored"]
        stats["skipped"] += s["skipped"]
        stats["errors"] += s["errors"]
        stats["outputs"].append(str(rel))
        if progress_cb:
            progress_cb(0.05 + 0.85 * i / len(inputs), f"judged {rel} ({i}/{len(inputs)})")
    return stats
