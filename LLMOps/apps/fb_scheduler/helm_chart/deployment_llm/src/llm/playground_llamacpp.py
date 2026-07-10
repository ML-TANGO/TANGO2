"""[멀티엔진 서빙 Phase 2] llama.cpp 서빙 엔트리 (LLM/model 역할 전용).

playground.py(vLLM) 와 **동일한 플랫폼 서빙 계약**을 유지하고 엔진만 교체한다:
  - FastAPI 앱, port 8555, `POST /`(`{test_question,session_id,test_type}` → `[{input,output,time}]`),
    `GET /` 헬스, `api_monitor` 데코, `db.insert/update_playground_test`, RAG DNS 호출.
엔진: 베이스 이미지(llama.cpp:full)의 `llama-server` 바이너리를 subprocess 로 띄우고
      OpenAI 호환 HTTP(`/v1/chat/completions`)로 추론. 프록시/헬스/모니터링/stop 은 무변경.

모델 소스(둘 다 지원):
  - GGUF 직접: `/model`(commit) 또는 HF 스냅샷 안에 `*.gguf` 존재 → 그대로 서빙.
  - HF/commit(safetensors): 기동 시 `convert_hf_to_gguf.py` 로 온더플라이 GGUF 변환(캐시) → 서빙.
임베딩/리랭커 역할은 이 파일을 쓰지 않는다(엔진 무관, HF 유지 — 설계 §10).
"""
import sys, os, glob, time, shutil, subprocess, asyncio, traceback, hashlib
import uvicorn, aiofiles, httpx
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
sys.path.append('/addlib')
from deployment_api_deco import api_monitor

import settings, db

file_name = os.path.splitext(os.path.basename(__file__))[0]

# ===== llama.cpp 서빙 상수 =====
LLAMA_SERVER_BIN = os.environ.get("LLAMA_SERVER_BIN", "/app/llama-server")
CONVERT_HF_TO_GGUF = os.environ.get("CONVERT_HF_TO_GGUF", "/app/convert_hf_to_gguf.py")
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080  # llama-server 내부 포트(외부 노출은 8555 FastAPI). 8555/18555 과 충돌 없음.
LLAMA_URL = f"http://{LLAMA_HOST}:{LLAMA_PORT}"
GGUF_CACHE_DIR = "/jf-deployment-home/gguf"  # jf-ws(NFS) 백업 → 재기동 시 변환 캐시 재사용
CONVERT_TIMEOUT_S = 7200  # HF→GGUF 변환 백스톱(S-A). 초과 시 fail-fast → LIFESPAN_STATUS=error.

LIFESPAN_STATUS = False
LLAMA_PROC = None
GGUF_PATH = None


def _has_gpu():
    return shutil.which("nvidia-smi") is not None and os.path.exists("/dev/nvidiactl")


def _find_gguf(path):
    """path(파일/디렉토리)에서 GGUF 를 찾는다. 없으면 None."""
    if os.path.isfile(path) and path.endswith(".gguf"):
        return path
    if os.path.isdir(path):
        hits = sorted(glob.glob(os.path.join(path, "*.gguf")))
        return hits[0] if hits else None
    return None


def _model_identity():
    """모델 식별 slug(캐시 keying용, H2). 모델 바뀌면 캐시 파일명도 바뀜."""
    mt = settings.LLM_MODEL_TYPE
    if mt == "commit":
        raw = f"commit:{settings.LLM_MODEL_ALLM_NAME}:{settings.LLM_MODEL_ALLM_COMMIT_NAME}"
    else:
        raw = f"hf:{settings.LLM_MODEL_HUGGINGFACE_ID}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _subprocess_env():
    """native llama-server/converter 로 넘길 env — DB비번·HF토큰 등 시크릿 상속 차단(S-B).
    변환/서빙은 로컬 모델만 다루므로 시크릿 불요."""
    allow = ("PATH", "HOME", "LANG", "LC_ALL", "HF_HOME", "HF_HUB_OFFLINE",
             "TRANSFORMERS_OFFLINE", "NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES",
             "LLAMA_SERVER_BIN", "CONVERT_HF_TO_GGUF", "PYTORCH_CUDA_ALLOC_CONF")
    env = {k: v for k, v in os.environ.items() if k in allow}
    env["LD_LIBRARY_PATH"] = (os.environ.get("LD_LIBRARY_PATH", "") + ":/app").lstrip(":")
    return env


def _merge_lora_commit():
    """LoRA 커밋(/model=adapter, /model/source_model=base) → merge 후 변환 대상 디렉토리 반환(H1).
    playground.py 의 PeftModel.merge_and_unload() 경로와 파리티(vLLM 과 동일 결과)."""
    merged = os.path.join(GGUF_CACHE_DIR, f"merged.{_model_identity()}")
    if os.path.isdir(merged) and any(f.endswith(".safetensors") for f in os.listdir(merged)):
        print(f"[llama.cpp] LoRA merge 캐시 재사용: {merged}")
        return merged
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    print("[llama.cpp] LoRA 커밋 감지 → base(/model/source_model)+adapter(/model) merge")
    base = AutoModelForCausalLM.from_pretrained(
        "/model/source_model", torch_dtype=torch.float16, trust_remote_code=True)
    model = PeftModel.from_pretrained(base, "/model")
    model = model.merge_and_unload()
    os.makedirs(merged, exist_ok=True)
    model.save_pretrained(merged, safe_serialization=True)  # safetensors → convert 호환
    try:
        tok = AutoTokenizer.from_pretrained("/tokenizer")
    except Exception:
        tok = AutoTokenizer.from_pretrained("/model/source_model")
    tok.save_pretrained(merged)
    return merged


def _resolve_model_dir():
    """모델 위치 해석. commit → /model(LoRA 면 merge), huggingface → 스냅샷 다운로드."""
    model_type = settings.LLM_MODEL_TYPE
    if model_type == "commit":
        # LoRA 파인튜닝 커밋: /model=adapter, /model/source_model=base (playground.py 선례).
        if os.path.exists("/model/source_model"):
            return _merge_lora_commit()
        return "/model"
    # huggingface: 로컬 캐시/nexus 우선(HF offline 가능). 토큰 optional.
    repo_id = settings.LLM_MODEL_HUGGINGFACE_ID
    token = settings.LLM_HUGGINGFACE_API_TOKEN or None
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id=repo_id, token=token)


def _ensure_gguf(model_dir):
    """GGUF 직접 사용, 없으면 convert_hf_to_gguf 로 변환(모델별 캐시). 실패/타임아웃 시 fail-fast."""
    direct = _find_gguf(model_dir)
    if direct:
        print(f"[llama.cpp] GGUF 직접 서빙: {direct}")
        return direct
    os.makedirs(GGUF_CACHE_DIR, exist_ok=True)
    # H2: 모델 식별자로 캐시 keying → 모델 교체 시 stale GGUF 재사용 방지.
    out_gguf = os.path.join(GGUF_CACHE_DIR, f"model.{_model_identity()}.f16.gguf")
    if os.path.isfile(out_gguf):
        print(f"[llama.cpp] 변환 캐시 재사용: {out_gguf}")
        return out_gguf
    print(f"[llama.cpp] HF→GGUF 온더플라이 변환: {model_dir} → {out_gguf}")
    # argv 리스트 호출(shell=False) — 경로 인젝션 무해(R4). 시크릿 미상속 env(S-B). timeout 백스톱(S-A).
    try:
        cp = subprocess.run(
            ["python3", CONVERT_HF_TO_GGUF, model_dir, "--outfile", out_gguf, "--outtype", "f16"],
            env=_subprocess_env(), capture_output=True, text=True, timeout=CONVERT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"convert_hf_to_gguf timeout({CONVERT_TIMEOUT_S}s) — 모델이 너무 크거나 hang")
    if cp.returncode != 0 or not os.path.isfile(out_gguf):
        # 지원 안 하는 아키텍처 등 → 명확 에러(R3).
        raise RuntimeError(f"convert_hf_to_gguf 실패(rc={cp.returncode}): {(cp.stderr or '')[-2000:]}")
    return out_gguf


async def _wait_llama_ready(timeout_s=1800):
    deadline = time.time() + timeout_s
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                r = await client.get(f"{LLAMA_URL}/health", timeout=5)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global LIFESPAN_STATUS, LLAMA_PROC, GGUF_PATH
    try:
        model_dir = _resolve_model_dir()
        GGUF_PATH = _ensure_gguf(model_dir)

        # 컨텍스트 길이: max_new_tokens 기반(여유 2배), 최소 4096.
        mnt = settings.LLM_PARAM_MAX_NEW_TOKENS if settings.LLM_PARAM_MAX_NEW_TOKENS and settings.LLM_PARAM_MAX_NEW_TOKENS > 0 else 4096
        ctx = max(mnt * 2, 4096)
        args = [LLAMA_SERVER_BIN, "-m", GGUF_PATH,
                "--host", LLAMA_HOST, "--port", str(LLAMA_PORT), "-c", str(ctx)]
        if _has_gpu():
            args += ["-ngl", "999"]  # 전 레이어 GPU 오프로드
        print(f"[llama.cpp] start: {' '.join(args)}")
        # 시크릿 미상속 env(S-B) — native llama-server 에 DB비번/HF토큰 노출 차단.
        LLAMA_PROC = subprocess.Popen(args, env=_subprocess_env())  # nosec - argv 리스트, shell 미사용

        if not await _wait_llama_ready():
            raise RuntimeError("llama-server 준비 실패(health timeout)")
        LIFESPAN_STATUS = True
        yield
    except Exception:
        traceback.print_exc()
        LIFESPAN_STATUS = "error"  # POST/GET 이 402(Model Error) 반환
        yield
    finally:
        if LLAMA_PROC is not None:
            try:
                LLAMA_PROC.terminate()
            except Exception:
                pass


# =======================================================================
# dataset (playground.py 와 동일)
# =======================================================================
async def get_dataset_input(dataset_id, filename):
    result = []
    try:
        dataset_info = await db.get_dataset(dataset_id=dataset_id)
        dataset_name = dataset_info.get("name")
        dataset_access = "datasets_rw" if dataset_info.get("access") == 1 else "datasets_ro"
        dataset_path = f"/jf-data/dataset/{dataset_access}/{dataset_name}/{filename}"
        try:
            async with aiofiles.open(dataset_path, mode='r', encoding='utf-8') as f:
                lines = await f.readlines()
                for line in lines:
                    result.append(line.strip())
        except Exception:
            traceback.print_exc()
            print("파일 내용 읽기 실패")
    except Exception:
        traceback.print_exc()
    return result


async def _fetch_rag_context(test_input):
    """RAG(embedding/reranker 파드) 결과 → context 문자열. embedding/reranker 는 엔진 무관(HF)."""
    if not settings.LLM_RUN_RAG:
        return ""
    if settings.LLM_RUN_RAG_RERANKER:
        rag_dns = f"http://deployment-llm-playground-rag-reranker-{settings.LLM_RAG_ID}--service:18555"
    else:
        rag_dns = f"http://deployment-llm-playground-rag-embedding-{settings.LLM_RAG_ID}--service:18555"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{rag_dns}/playground",
                json={"chunk_size": settings.LLM_PLAYGROUND_RAG_CHUNK_MAX, "prompt": test_input},
                timeout=1800,
            )
        if response.status_code != 200:
            return ""
        payload = response.json().get("data")
        # langchain 직렬화 파싱은 지연 import(이미지에 langchain 하드의존 회피 — 설계 §10).
        # 실패 시 RAG context 없이 진행(그레이스풀). 완전한 RAG 파리티는 RAG 트랙에서.
        try:
            from langchain_core.load import loads
            docs = loads(payload)
            return "".join(getattr(d, "page_content", "") for d in docs)
        except Exception:
            print("[llama.cpp] RAG 결과 파싱 스킵(langchain 미탑재) — context 없이 진행")
            return ""
    except Exception:
        print("[llama.cpp] RAG 대기/실패 — context 없이 진행")
        return ""


# =======================================================================
# playground
# =======================================================================
async def run_playground(test_input, session_id, db_id):
    result = None
    try:
        rag = await _fetch_rag_context(test_input)

        # 프롬프트 구성 (playground.py 의 chat 메시지 형태 유지)
        if settings.LLM_RUN_PROMPT:
            system_message = settings.LLM_PROMPT_SYSTEM_MESSAGE or ""
            user_message = settings.LLM_PROMPT_USER_MESSAGE or test_input
            messages = [
                {"role": "system", "content": rag + system_message},
                {"role": "user", "content": user_message},
            ]
        else:
            content = (rag + "\n" + test_input) if rag else test_input
            messages = [{"role": "user", "content": content}]

        max_tokens = settings.LLM_PARAM_MAX_NEW_TOKENS if settings.LLM_PARAM_MAX_NEW_TOKENS > 0 else 4096
        payload = {
            "messages": messages,
            "temperature": settings.LLM_PARAM_TEMPERATURE,
            "top_p": settings.LLM_PARAM_TOP_P,
            "max_tokens": max_tokens,
        }
        if settings.LLM_PARAM_REPETITION_PENALTY and settings.LLM_PARAM_REPETITION_PENALTY > 0:
            payload["repeat_penalty"] = settings.LLM_PARAM_REPETITION_PENALTY

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{LLAMA_URL}/v1/chat/completions", json=payload, timeout=1800)
            resp.raise_for_status()
            data = resp.json()
        result = data["choices"][0]["message"]["content"].strip()

        try:
            await db.update_playground_test(db_id=db_id, **{"model": f"llama.cpp:{os.path.basename(GGUF_PATH or '')}"})
        except Exception:
            pass
        return result
    except Exception as e:
        traceback.print_exc()
        result = str(e)
    return result


app = FastAPI(lifespan=lifespan)
print("FASTAPI APP START (llama.cpp)")


@app.post("/", description="종합테스트")
@api_monitor()
async def post_llm(request: Request):
    global LIFESPAN_STATUS
    if LIFESPAN_STATUS is False:
        raise HTTPException(status_code=401, detail="Installing")
    elif LIFESPAN_STATUS == "error":
        raise HTTPException(status_code=402, detail="Model Error")

    print("playground(llama.cpp) test start")
    data = await request.json()
    test_type = data.get("test_type") if data.get("test_type") is not None else "question"
    test_dataset_id = data.get("test_dataset_id")
    test_dataset_filename = data.get("test_dataset_filename")
    test_question = data.get("test_question")
    session_id = data.get("session_id")
    result = []
    try:
        if test_type == "dataset":
            test_input = await get_dataset_input(dataset_id=test_dataset_id, filename=test_dataset_filename)
        else:
            test_input = [test_question]
        for _input in test_input:
            _, db_id = await db.insert_playground_test(playground_id=settings.LLM_PLAYGROUND_ID, type=test_type)
            start_time = time.time()
            output = await run_playground(test_input=_input, session_id=session_id, db_id=db_id)
            end_time = time.time()
            item = {"input": _input, "output": output, "time": end_time - start_time}
            result.append(item)
            await db.update_playground_test(db_id=db_id, **{"input": _input, "output": output})
        return result
    except Exception:
        traceback.print_exc()
    return result


@app.get("/")
@api_monitor()
async def health():
    global LIFESPAN_STATUS
    if LIFESPAN_STATUS is False:
        raise HTTPException(status_code=401, detail="Installing")
    elif LIFESPAN_STATUS == "error":
        raise HTTPException(status_code=402, detail="Model Error")
    return "JF DEPLOYMENT RUNNING - playground (llama.cpp)"


if __name__ == "__main__":
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0')
