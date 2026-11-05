"""외부 LLM 배포(deploy_type='remote_api')의 워커 — OpenAI/외부 엔드포인트 리레이.

왜 pod 인가. 이 배포는 GPU 도 모델 가중치도 쓰지 않지만, 플랫폼의 다른 배포와 **같은
모양**이어야 한다: 자기 서비스 URL 을 갖고, 상태가 파드로 관측되며, 시작/중지가 helm
릴리스의 생명주기와 같다. 그래야 추론·평가가 배포 유형을 몰라도 되고, 외부로 나가는
호출이 컨트롤 플레인(llm_playground)이 아니라 이 파드에서 일어난다.

두 계약을 동시에 말한다 — 그래서 호출자 어느 쪽도 분기하지 않는다:
  1) `POST /`            플랫폼 서빙 래퍼 계약. {test_type,test_question} → [{"output":...}]
                         (기존 vLLM/TGI 래퍼와 같은 모양 → _infer_question 이 그대로 동작)
  2) `POST /v1/chat/completions`, `GET /v1/models`
                         OpenAI 호환. 평가 채점 컨테이너가 generate_base_url/judge_base_url
                         로 직접 호출한다(컨트롤 플레인 우회).

구성은 전부 env 로 들어온다. **API 키는 helm values 가 아니라 K8s Secret →
valueFrom.secretKeyRef 로만 온다**(SP-3 하드닝과 같은 posture).
"""
import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from utils import remote_api

PROVIDER = os.environ.get("REMOTE_PROVIDER", "").strip()
MODEL = os.environ.get("REMOTE_MODEL", "").strip()
BASE_URL = os.environ.get("REMOTE_BASE_URL", "").strip() or None
API_KEY = os.environ.get("API_KEY", "").strip() or None

app = FastAPI(title="Remote API Proxy", version="0.1")


def _cfg():
    """env → 어댑터 config. 기동 시가 아니라 호출 시 만든다 — 잘못된 구성이라도 파드는
    떠서 /healthz 로 원인을 말할 수 있어야 한다(CrashLoop 은 원인을 감춘다)."""
    return remote_api.validate_config(provider=PROVIDER, model=MODEL, base_url=BASE_URL)


@app.get("/healthz")
async def healthz():
    try:
        _cfg()
        return {"status": "ok", "provider": PROVIDER, "model": MODEL}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "message": str(e)})


@app.post("/")
async def wrapper_infer(request: Request):
    """플랫폼 서빙 래퍼 계약 — 기존 배포 래퍼와 같은 요청/응답 모양.

    상태 코드도 래퍼 관행을 따른다: 구성 오류 401(_infer_question 이 "Setting up the
    playground" 로 읽는다), 모델/공급자 오류 402("Playground Model Error").
    """
    body = await request.json()
    question = (body or {}).get("test_question")
    if (body or {}).get("test_type") not in (None, "question"):
        return JSONResponse(status_code=400,
                            content={"message": "외부 LLM 배포는 단일 질문 추론만 지원합니다"})
    try:
        cfg = _cfg()
    except Exception as e:
        return JSONResponse(status_code=401, content={"message": str(e)})
    try:
        text = await remote_api.infer(cfg, API_KEY, question)
    except remote_api.RemoteApiError as e:
        return JSONResponse(status_code=402, content={"message": str(e)})
    return [{"output": text}]


@app.get("/v1/models")
async def openai_models():
    return {"object": "list",
            "data": [{"id": MODEL or PROVIDER, "object": "model", "owned_by": PROVIDER}]}


@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    """OpenAI 호환(비스트리밍). 평가 채점 컨테이너가 이 경로로 직접 온다."""
    body = await request.json()
    messages = (body or {}).get("messages")
    if not isinstance(messages, list) or not messages:
        return JSONResponse(status_code=400, content={"message": "messages must be a non-empty list"})
    prompt = "\n\n".join(
        m["content"].strip() for m in messages
        if isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].strip())
    if not prompt:
        return JSONResponse(status_code=400, content={"message": "no textual content in messages"})
    try:
        cfg = _cfg()
        # 상용 API 는 max_tokens 를 존중하므로 요청값을 그대로 넘긴다(플랫폼 shim 과 달리
        # 여기서는 버릴 이유가 없다 — 채점기가 길이를 통제할 수 있어야 한다).
        text = await remote_api.infer(
            cfg, API_KEY, prompt,
            max_tokens=int(body.get("max_tokens") or remote_api.DEFAULT_MAX_TOKENS))
    except remote_api.RemoteApiError as e:
        return JSONResponse(status_code=502, content={"message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL or PROVIDER,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": text or ""},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
