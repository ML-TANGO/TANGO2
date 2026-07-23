"""[멀티엔진 서빙 Phase 3 / Tier B] 외부 HTTP 추론서버 공용 어댑터 (LLM/model 역할 전용).

playground_llamacpp.py(llama.cpp) 와 **동일한 플랫폼 서빙 계약**을 그대로 유지하고,
엔진만 "외부 HTTP 서버를 subprocess 로 띄우는" 방식으로 일반화한다:
  - FastAPI 앱, port 8555, `POST /`(`{test_question,session_id,test_type}` → `[{input,output,time}]`),
    `GET /` 헬스, `api_monitor` 데코, `db.insert/update_playground_test`, RAG DNS 호출.
    → command.sh/nginx/proxy/모니터링/stop 스캐폴딩 무변경(playground_llamacpp.py L1-13 계약과 동일).

Tier B 엔진 추상화(ServingRuntime 레지스트리):
  - 앱/envelope/lifespan 오케스트레이션은 엔진 무관.
  - 엔진별 차이(런처 argv·health path·내부 포트·generate 호출)만 ServingRuntime 이 캡슐화.
  - 첫 엔트리 = TGI(HuggingFace text-generation-inference). Ollama/Triton/TensorRT 는 SERVING_RUNTIMES 에
    엔트리만 추가하면 됨(lifespan/POST/GET 재작성 불요).
  - 어떤 런타임을 쓸지는 pod-side `settings.LLM_SERVING_SYSTEM` 이 선택(defense-in-depth).

TGI 는 HF/safetensors 를 직접 서빙(GGUF 변환 없음) → `_resolve_model_dir()` 이 해석한 디렉토리가
곧 `--model-id`. 임베딩/리랭커 역할은 이 파일을 쓰지 않는다(엔진 무관, HF 유지 — 설계 §10).
"""
import sys, os, time, subprocess, asyncio, traceback, hashlib
from dataclasses import dataclass
from typing import Callable, Optional
import uvicorn, aiofiles, httpx
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
sys.path.append('/addlib')
from deployment_api_deco import api_monitor

import settings, db

file_name = os.path.splitext(os.path.basename(__file__))[0]

# ===== Tier B 공용 서빙 상수 =====
ENGINE_HOST = "127.0.0.1"                 # 엔진은 localhost 만 바인딩(외부 노출은 8555 FastAPI/nginx).
MODEL_CACHE_DIR = "/jf-deployment-home/serving"  # jf-ws(NFS) 백업 → LoRA merge 결과 캐시(재기동 재사용).

LIFESPAN_STATUS = False
ENGINE_PROC = None
RUNTIME = None       # 선택된 ServingRuntime
MODEL_DIR = None     # 엔진에 넘긴 model-id(로깅/모델 태그용)
MODEL_TAG = None     # payload(/api/chat 등)에 넣을 모델 태그. Ollama 는 prepare 가 등록 후 반환, 그 외는 MODEL_DIR.


# =======================================================================
# 모델 해석 (playground_llamacpp.py L53-111 미러 — GGUF 변환 단계만 제거)
# =======================================================================
def _model_identity():
    """모델 식별 slug(merge 캐시 keying용, H2). 모델 바뀌면 캐시 디렉토리명도 바뀜."""
    mt = settings.LLM_MODEL_TYPE
    if mt == "commit":
        raw = f"commit:{settings.LLM_MODEL_ALLM_NAME}:{settings.LLM_MODEL_ALLM_COMMIT_NAME}"
    else:
        raw = f"hf:{settings.LLM_MODEL_HUGGINGFACE_ID}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _subprocess_env():
    """엔진 런처에 넘길 env. TGI 등 Tier B 런처는 자체 venv(/usr/src/.venv)·CUDA·PATH 로
    자식 shard 프로세스를 spawn 하므로 **정상 환경을 상속**해야 한다(allow-list 로 좁히면
    launcher/shard 가 실행파일·라이브러리를 못 찾음 — FileNotFoundError). 대신 **시크릿만 제거**(S-B):
    DB 비번·*PASSWORD*·*SECRET*·*TOKEN*. 모델은 부모가 이미 로컬에 받아둠 → 토큰 불요.
    폐쇄망 전제라 HF offline 을 강제(setdefault) — 로컬 서빙이므로 hub 접근 시도 원천 차단."""
    env = dict(os.environ)
    for k in list(env.keys()):
        ku = k.upper()
        # 이 파드의 DB 크레덴셜은 JF_LLM_DB_*(비번=JF_LLM_DB_PW) 네이밍 —
        #   JF_DB 접두/'PASSWORD' 로는 안 잡히므로 JF_LLM_DB 접두 + _PW/_PWD 접미도 제거(S-B).
        if (k.startswith("JF_DB") or k.startswith("JF_LLM_DB")
                or "PASSWORD" in ku or "SECRET" in ku or "TOKEN" in ku
                or ku.endswith("_PW") or ku.endswith("_PWD")):
            env.pop(k, None)
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    return env


def _merge_lora_commit():
    """LoRA 커밋(/model=adapter, /model/source_model=base) → merge 후 서빙 대상 디렉토리 반환(H1).
    playground_llamacpp.py L74-96 / playground.py 의 PeftModel.merge_and_unload() 경로와 파리티.
    TGI 는 safetensors 를 직접 서빙하므로 merged 디렉토리가 그대로 --model-id 가 된다(GGUF 변환 없음)."""
    merged = os.path.join(MODEL_CACHE_DIR, f"merged.{_model_identity()}")
    if os.path.isdir(merged) and any(f.endswith(".safetensors") for f in os.listdir(merged)):
        print(f"[serving_adapter] LoRA merge 캐시 재사용: {merged}")
        return merged
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    print("[serving_adapter] LoRA 커밋 감지 → base(/model/source_model)+adapter(/model) merge")
    base = AutoModelForCausalLM.from_pretrained(
        "/model/source_model", torch_dtype=torch.float16, trust_remote_code=True)
    model = PeftModel.from_pretrained(base, "/model")
    model = model.merge_and_unload()
    os.makedirs(merged, exist_ok=True)
    model.save_pretrained(merged, safe_serialization=True)  # safetensors → TGI 직접 서빙 호환
    try:
        tok = AutoTokenizer.from_pretrained("/tokenizer")
    except Exception:
        tok = AutoTokenizer.from_pretrained("/model/source_model")
    tok.save_pretrained(merged)  # chat_template 포함 → TGI /v1/chat/completions 필수
    return merged


def _resolve_model_dir():
    """모델 위치 해석. commit → /model(LoRA 면 merge), huggingface → 스냅샷 다운로드.
    반환 디렉토리가 곧 엔진의 model-id (playground_llamacpp.py L99-111 미러, _ensure_gguf 만 제거)."""
    model_type = settings.LLM_MODEL_TYPE
    if model_type == "commit":
        # LoRA 파인튜닝 커밋: /model=adapter, /model/source_model=base (playground.py 선례).
        if os.path.exists("/model/source_model"):
            return _merge_lora_commit()
        return "/model"
    # huggingface: 로컬 캐시/nexus 우선(HF offline 가능). 토큰 optional. (parent 프로세스 env 사용)
    repo_id = settings.LLM_MODEL_HUGGINGFACE_ID
    token = settings.LLM_HUGGINGFACE_API_TOKEN or None
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id=repo_id, token=token)


# =======================================================================
# ServingRuntime 레지스트리 (Tier B 엔진 추상화)
# =======================================================================
def _openai_chat_payload(messages, params, model_tag):
    """OpenAI 호환 chat body — llama.cpp `/v1/chat/completions` 사용부(L265-272)와 동형.
    TGI 는 단일 모델 서빙이라 model_tag 는 불필요 → 시그니처만 통일(엔진 무관 호출부)."""
    payload = {
        "messages": messages,
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "max_tokens": params["max_tokens"],
    }
    # repetition_penalty 는 OpenAI 라우트에 없어 frequency_penalty 로 근사(의미 상이 — VERIFY 참고).
    if params.get("frequency_penalty"):
        payload["frequency_penalty"] = params["frequency_penalty"]
    return payload


def _openai_chat_parse(data):
    """llama.cpp 와 동일한 응답 매핑: choices[0].message.content (L278)."""
    return data["choices"][0]["message"]["content"].strip()


def _tgi_build_args(model_dir, port, bin_path):
    """TGI 런처 argv. --model-id 는 로컬 디렉토리 경로 허용. 단일노드(A100) — shard 플래그 미지정.
    --trust-remote-code 는 기본 off(보안). offline 은 _subprocess_env 가 강제."""
    return [
        bin_path,
        "--model-id", model_dir,
        "--port", str(port),
        "--hostname", ENGINE_HOST,
    ]


# ----- Ollama 엔진 델타 (TGI 와 달리 런처가 모델을 로드하지 않음 → prepare 훅으로 등록) -----
def _ollama_build_args(model_dir, port, bin_path):
    """Ollama 런처 argv. `ollama serve` 는 HTTP 서버만 띄우고 모델은 로드하지 않는다
    (모델은 ready 후 _ollama_prepare 가 `ollama create` 로 스토어에 등록). 포트/바인딩은
    extra_env 의 OLLAMA_HOST(127.0.0.1:11434)로 지정 → argv 엔 모델/포트 인자 없음."""
    return [bin_path, "serve"]


def _ollama_build_payload(messages, params, model_tag):
    """Ollama `/api/chat` body. OpenAI 와 달리 (1) model 이름 필수, (2) 샘플링은 options 중첩,
    (3) max_tokens 는 num_predict. Ollama 는 top_k/repeat_penalty 를 네이티브 지원 → 플랫폼 설정 반영
    (llama.cpp 파리티; TGI OpenAI 라우트는 미지원이라 거기선 생략). stream=False 로 단발 응답."""
    options = {
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "num_predict": params["max_tokens"],
    }
    if settings.LLM_PARAM_TOP_K and settings.LLM_PARAM_TOP_K > 0:
        options["top_k"] = settings.LLM_PARAM_TOP_K
    if settings.LLM_PARAM_REPETITION_PENALTY and settings.LLM_PARAM_REPETITION_PENALTY > 0:
        options["repeat_penalty"] = settings.LLM_PARAM_REPETITION_PENALTY
    return {
        "model": model_tag,
        "messages": messages,
        "stream": False,
        "options": options,
    }


def _ollama_chat_parse(data):
    """Ollama /api/chat 응답 매핑: message.content (OpenAI choices[0].message 와 상이)."""
    return data["message"]["content"].strip()


def _resolved_cache_key(model_dir):
    """resolved model_dir 기반 캐시 키(ollama materialize/tag · triton 모델명 공용). hf 는 스냅샷 경로에
    revision 해시 포함, commit 은 /model 또는 merged.<id> → 동일 HF ID 라도 revision 이 바뀌면 키가
    바뀌어 stale 재사용 방지(_model_identity 는 hf revision 을 담지 않음 — codex HIGH)."""
    return hashlib.sha1((model_dir or "").encode("utf-8")).hexdigest()[:16]


def _ollama_materialize(model_dir, key):
    """Ollama `create` 는 HF 캐시 스냅샷의 상대 심링크(../../blobs/..)를 'insecure path' 로 거부한다.
    최상위 '일반 파일'만 basename 으로 평면 복사(심링크는 최종 대상의 실제 내용) → 상대 traversal 제거.
    디렉토리/디렉토리 심링크는 복사하지 않는다(무한/예상외 트리·중첩 경로 배제, 보안 하드닝).
    marker 로 캐시(재기동 재사용). 표준 causal-LM 스냅샷(safetensors/config/tokenizer)은 평면 구조."""
    import shutil
    flat = os.path.join(MODEL_CACHE_DIR, f"ollama-src.{key}")
    marker = os.path.join(flat, ".materialized")
    if os.path.exists(marker):
        return flat
    if os.path.isdir(flat):
        shutil.rmtree(flat, ignore_errors=True)
    os.makedirs(flat, exist_ok=True)
    for entry in os.scandir(model_dir):
        # 심링크 따라간 최종 대상이 '일반 파일' 인 것만 basename 으로 복사(디렉토리/특수파일 제외).
        if entry.is_file(follow_symlinks=True):
            shutil.copyfile(entry.path, os.path.join(flat, entry.name))  # follow_symlinks 기본 True → 실제 내용
    open(marker, "w").close()
    return flat


def _ollama_prepare(model_dir, base_url):
    """[Ollama 특수성] 런처가 모델을 로드하지 않으므로, 서버 ready 후 모델을 스토어에 등록하고
    /api/chat 에서 쓸 tag 를 반환한다. HF safetensors 디렉토리를
    `ollama create <tag> -f Modelfile(FROM <model_dir>)` 로 임포트(지원 아키텍처면 내부 포맷 변환).

    - serve/create 가 **동일 OLLAMA_MODELS/OLLAMA_HOST** 를 써야 함(불일치 시 서버가 모델을 못 찾음)
      → runtime.extra_env 를 serve(lifespan)·create(여기) 양쪽에 동일 적용.
    - OLLAMA_MODELS 는 NFS 캐시(extra_env)라 재기동 시 이미 등록된 tag 면 create 생략(변환비용 절감).
    """
    rt = RUNTIME or SERVING_RUNTIMES["ollama"]   # lifespan 에서 선택된 런타임 재사용(레지스트리 키 하드코딩 회피)
    bin_path = rt.bin_path()
    env = _subprocess_env()
    if rt.extra_env:
        env.update(rt.extra_env)
    key = _resolved_cache_key(model_dir)         # resolved model_dir 기반(hf revision 반영 — stale 방지)
    tag = f"jf-{key}"
    # 이미 등록된 태그면 재사용(NFS 스토어 캐시).
    try:
        listed = subprocess.run([bin_path, "list"], env=env,
                                capture_output=True, text=True, timeout=60)
        if tag in (listed.stdout or ""):
            print(f"[ollama] 모델 태그 캐시 재사용: {tag}")
            return tag
    except Exception:
        pass
    # HF 캐시 스냅샷은 ../../blobs 상대 심링크 → Ollama create 가 'insecure path' 로 거부.
    #   심링크 없는 실제 파일 dir 로 1회 materialize(캐시) 후 그 경로를 FROM 으로.
    src_dir = _ollama_materialize(model_dir, key)
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    modelfile = os.path.join(MODEL_CACHE_DIR, f"Modelfile.{key}")
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(f"FROM {src_dir}\n")
    print(f"[ollama] create {tag} <- {src_dir}")
    proc = subprocess.run([bin_path, "create", tag, "-f", modelfile], env=env,
                          capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"ollama create 실패(rc={proc.returncode}): {(proc.stderr or '')[-500:]}")
    return tag


# ----- Triton 엔진 델타 (NVIDIA Triton + vLLM backend; model repository + KServe generate) -----
TRITON_REPO_DIR = os.path.join(MODEL_CACHE_DIR, "triton-repo")  # explicit model-control repo(기동 전 존재 필요)
_TRITON_TOKENIZER = None   # chat_template 평탄화용(prepare 에서 로드·캐시)


def _triton_build_args(model_dir, port, bin_path):
    """Triton 런처 argv. explicit model-control 로 기동(모델 없이 ready) → prepare 가 repo 작성 후 load.
    repo 디렉토리는 기동 전 존재해야 하므로 여기서 빈 디렉토리를 만든다(부수효과)."""
    os.makedirs(TRITON_REPO_DIR, exist_ok=True)
    return [
        bin_path,
        f"--model-repository={TRITON_REPO_DIR}",
        "--model-control-mode=explicit",
        f"--http-port={port}",
        f"--http-address={ENGINE_HOST}",
        "--allow-grpc=false",
        "--allow-metrics=false",
    ]


def _triton_build_payload(messages, params, model_tag):
    """Triton vLLM backend KServe generate body. generate 는 text_input(단일 프롬프트)만 받으므로
    메시지를 tokenizer.chat_template 로 평탄화. 샘플링은 sampling_parameters(JSON 문자열)."""
    import json
    if _TRITON_TOKENIZER is not None:
        prompt = _TRITON_TOKENIZER.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
    else:  # 토크나이저 미로드 폴백(chat_template 없이 원문 이어붙임)
        prompt = "\n".join(m.get("content", "") for m in messages)
    sampling = {
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "max_tokens": params["max_tokens"],
    }
    if settings.LLM_PARAM_TOP_K and settings.LLM_PARAM_TOP_K > 0:
        sampling["top_k"] = settings.LLM_PARAM_TOP_K
    if settings.LLM_PARAM_REPETITION_PENALTY and settings.LLM_PARAM_REPETITION_PENALTY > 0:
        sampling["repetition_penalty"] = settings.LLM_PARAM_REPETITION_PENALTY
    return {
        "text_input": prompt,
        "sampling_parameters": json.dumps(sampling),
        "exclude_input_in_output": True,
    }


def _triton_parse(data):
    """Triton vLLM backend generate 응답: text_output (누락 시 KeyError → 상위서 오류 표면화, TGI/ollama 파서와 동형)."""
    return data["text_output"].strip()


def _triton_prepare(model_dir, base_url):
    """[Triton 특수성] explicit model-control → server ready 후 vLLM backend 모델 repo 를 작성하고
    load API 로 올린다. repo/<tag>/{config.pbtxt, 1/model.json}. tag=모델명(resolved model_dir 기반).
    chat_template 평탄화용 tokenizer 도 여기서 로드·캐시."""
    global _TRITON_TOKENIZER
    import json
    tag = f"jf-{_resolved_cache_key(model_dir)}"
    model_dir_abs = os.path.abspath(model_dir)
    ver_dir = os.path.join(TRITON_REPO_DIR, tag, "1")
    os.makedirs(ver_dir, exist_ok=True)
    with open(os.path.join(TRITON_REPO_DIR, tag, "config.pbtxt"), "w", encoding="utf-8") as f:
        f.write('backend: "vllm"\ninstance_group [ { count: 1, kind: KIND_MODEL } ]\n')
    # vLLM 엔진 args. tensor_parallel_size=파드당 GPU 수(playground.py:141 관례) → 멀티GPU 단일노드 활용
    #   (누락 시 vLLM 기본 1 GPU만 써 OOM/유휴 — codex HIGH). gpu_mem_util 은 vLLM 기본과 동일.
    _model_json = {"model": model_dir_abs, "disable_log_requests": True, "gpu_memory_utilization": 0.9}
    if settings.LLM_GPU_COUNT and settings.LLM_GPU_COUNT > 1:
        _model_json["tensor_parallel_size"] = settings.LLM_GPU_COUNT
    with open(os.path.join(ver_dir, "model.json"), "w", encoding="utf-8") as f:
        json.dump(_model_json, f)
    # chat_template 평탄화용 tokenizer 로드. 실패/무-template 시 loud-fail(무음 degrade 방지 — 기능∩codex).
    #   trust_remote_code=False 명시(보안: 상위 transformers 기본값 의존 배제).
    from transformers import AutoTokenizer
    _TRITON_TOKENIZER = AutoTokenizer.from_pretrained(model_dir_abs, trust_remote_code=False)
    if getattr(_TRITON_TOKENIZER, "chat_template", None) is None:
        raise RuntimeError(f"triton: tokenizer 에 chat_template 없음({model_dir_abs}) — /generate 프롬프트 평탄화 불가")
    r = httpx.post(f"{base_url}/v2/repository/models/{tag}/load", timeout=1800)
    if r.status_code != 200:
        raise RuntimeError(f"triton load 실패(status={r.status_code}): {r.text[:500]}")
    print(f"[triton] loaded {tag} <- {model_dir_abs}")
    return tag


# ----- TensorRT-LLM 엔진 델타 (trtllm-serve OpenAI 호환 서버; PyTorch 백엔드 = HF 직접, AOT 컴파일 불요) -----
def _tensorrt_build_args(model_dir, port, bin_path):
    """TensorRT-LLM 런처 argv. `trtllm-serve serve <model_dir> --backend pytorch` 는 OpenAI 호환
    /v1/chat/completions + /health 를 노출하고, PyTorch 백엔드로 HF 체크포인트를 직접 로드한다
    (별도 AOT `trtllm-build` 엔진 컴파일 불요 — vLLM/TGI 와 동형). model 인자는 로컬 디렉토리 허용.
    멀티GPU 단일노드는 --tp_size(파드당 GPU 수 = triton 관례, LLM_GPU_COUNT). --trust_remote_code 는
    기본 off(보안, TGI 와 동일). offline 은 _subprocess_env 가 강제. payload/parse 는 OpenAI 기본값 재사용."""
    args = [
        bin_path, "serve", model_dir,
        "--host", ENGINE_HOST,
        "--port", str(port),
        "--backend", "pytorch",
    ]
    if settings.LLM_GPU_COUNT and settings.LLM_GPU_COUNT > 1:
        args += ["--tp_size", str(settings.LLM_GPU_COUNT)]
    return args


def _tensorrt_build_payload(messages, params, model_tag):
    """trtllm-serve OpenAI 서버(TRT-LLM 0.20 `openai_protocol.py`)는 ChatCompletionRequest.model 이
    **필수** — 누락 시 매 요청 422(기능∩codex HIGH). TGI 는 model optional 이라 _openai_chat_payload
    (model 미포함)로 충분했지만 trtllm-serve 는 필수라 여기서 명시한다. 서버는 `trtllm-serve serve <dir>`
    의 <dir>(=MODEL_TAG, prepare 없음 → MODEL_DIR)로 모델을 등록하므로 요청 model 도 그 경로로 일치.
    나머지 필드는 OpenAI 기본과 동일 → _openai_chat_payload 재사용(DRY)."""
    payload = _openai_chat_payload(messages, params, model_tag)
    payload["model"] = model_tag
    return payload


@dataclass
class ServingRuntime:
    """엔진별 차이만 캡슐화. 앱/lifespan 은 이 인터페이스에만 의존(엔진 무관)."""
    name: str                                   # 로깅/모델 태그 라벨
    port: int                                   # 엔진 내부 포트(8555/18555 과 충돌 없음)
    bin_env: str                                # 런처 바이너리 경로 env 키
    default_bin: str                            # env 미설정 시 PATH 상 기본 바이너리
    build_args: Callable[[str, int, str], list]  # (model_dir, port, bin_path) → argv 리스트
    health_path: str = "/health"                # 200 → ready
    generate_path: str = "/v1/chat/completions"
    build_payload: Callable[[list, dict, str], dict] = _openai_chat_payload
    parse_response: Callable[[dict], str] = _openai_chat_parse
    prepare: Optional[Callable[[str, str], str]] = None   # ready 후 모델 등록 훅(Ollama). None → MODEL_TAG=MODEL_DIR
    extra_env: Optional[dict] = None                       # 엔진 subprocess 추가 env(Ollama 스토어/바인딩)

    def bin_path(self):
        # bare name 을 절대경로로 해석 — Popen 이 제한 env 로 실행파일 탐색에 실패하는 것 방지.
        # 벤더 이미지 런처는 PATH(/usr/local/bin 등) 상에 있음 → shutil.which 로 절대경로화.
        import shutil
        name = os.environ.get(self.bin_env) or self.default_bin
        return shutil.which(name) or name

    @property
    def base_url(self):
        return f"http://{ENGINE_HOST}:{self.port}"

    @property
    def health_url(self):
        return f"{self.base_url}{self.health_path}"

    def generate_url_for(self, model_tag):
        # Triton 처럼 URL 에 모델명이 들어가는 엔진 지원 — generate_path 의 {tag} 치환.
        #   TGI/ollama generate_path 엔 {} 가 없어 no-op.
        return f"{self.base_url}{self.generate_path.format(tag=model_tag)}"


SERVING_RUNTIMES = {
    # TGI: HF/safetensors 직접 서빙, OpenAI 호환 /v1/chat/completions, /health 200 → ready.
    "tgi": ServingRuntime(
        name="tgi",
        port=8080,
        bin_env="TGI_LAUNCHER_BIN",
        default_bin="text-generation-launcher",
        build_args=_tgi_build_args,
    ),
    # Ollama: `ollama serve`(모델 미로드) → ready 후 prepare 가 `ollama create` 로 등록. /api/chat.
    #   serve/create 가 공유할 스토어(OLLAMA_MODELS=NFS)·바인딩(OLLAMA_HOST)은 extra_env 로 주입.
    "ollama": ServingRuntime(
        name="ollama",
        port=11434,
        bin_env="OLLAMA_BIN",
        default_bin="ollama",
        build_args=_ollama_build_args,
        health_path="/",                 # GET / → 200 "Ollama is running"
        generate_path="/api/chat",
        build_payload=_ollama_build_payload,
        parse_response=_ollama_chat_parse,
        prepare=_ollama_prepare,
        extra_env={
            "OLLAMA_HOST": f"{ENGINE_HOST}:11434",
            "OLLAMA_MODELS": os.path.join(MODEL_CACHE_DIR, "ollama"),
        },
    ),
    # Triton(NVIDIA) + vLLM backend: explicit model-control → ready 후 prepare 가 repo 작성 + load.
    #   KServe generate 는 URL 에 모델명 포함(generate_path 의 {tag}) → generate_url_for 가 치환.
    "triton": ServingRuntime(
        name="triton",
        port=8000,
        bin_env="TRITON_BIN",
        default_bin="tritonserver",
        build_args=_triton_build_args,
        health_path="/v2/health/ready",
        generate_path="/v2/models/{tag}/generate",
        build_payload=_triton_build_payload,
        parse_response=_triton_parse,
        prepare=_triton_prepare,
    ),
    # TensorRT-LLM: `trtllm-serve serve <model> --backend pytorch` → OpenAI 호환 /v1/chat/completions,
    #   /health 200 → ready. PyTorch 백엔드로 HF 직접 로드(AOT 컴파일 불요). parse 는 OpenAI 기본값
    #   재사용(TGI 동형)이나 payload 는 model 필수(TRT-LLM 0.20 스키마) → _tensorrt_build_payload.
    "tensorrt": ServingRuntime(
        name="tensorrt",
        port=8000,                       # trtllm-serve 기본 포트(triton 과 동일값이나 파드당 1엔진이라 무충돌)
        bin_env="TRTLLM_SERVE_BIN",
        default_bin="trtllm-serve",
        build_args=_tensorrt_build_args,
        health_path="/health",
        build_payload=_tensorrt_build_payload,
    ),
}


def _select_runtime():
    key = (settings.LLM_SERVING_SYSTEM or "").lower()
    rt = SERVING_RUNTIMES.get(key)
    if rt is None:
        raise RuntimeError(
            f"serving_adapter: 미지원 serving_system={key!r} (지원: {list(SERVING_RUNTIMES)})")
    return rt


# =======================================================================
# lifespan — 엔진 subprocess 기동 + health 폴링 (playground_llamacpp.py L141-186 미러)
# =======================================================================
async def _wait_ready(health_url, timeout_s=1800):
    deadline = time.time() + timeout_s
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                r = await client.get(health_url, timeout=5)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global LIFESPAN_STATUS, ENGINE_PROC, RUNTIME, MODEL_DIR, MODEL_TAG
    try:
        RUNTIME = _select_runtime()
        MODEL_DIR = _resolve_model_dir()  # commit→/model(LoRA merge), hf→snapshot. TGI 는 그대로 model-id.
        args = RUNTIME.build_args(MODEL_DIR, RUNTIME.port, RUNTIME.bin_path())
        print(f"[{RUNTIME.name}] start: {' '.join(args)}")
        # 시크릿 미상속 env(S-B) — native 런처에 DB비번/HF토큰 노출 차단. argv 리스트, shell 미사용.
        # extra_env(엔진별, 예: Ollama 스토어/바인딩)는 serve 와 이후 prepare 가 동일하게 써야 함.
        engine_env = _subprocess_env()
        if RUNTIME.extra_env:
            engine_env.update(RUNTIME.extra_env)
        ENGINE_PROC = subprocess.Popen(args, env=engine_env)  # nosec

        if not await _wait_ready(RUNTIME.health_url):
            raise RuntimeError(f"{RUNTIME.name} 준비 실패(health timeout)")
        # 서버 ready 후 모델 준비. TGI 는 prepare=None → MODEL_TAG=MODEL_DIR. Ollama 는 create 후 tag 반환.
        #   prepare 는 blocking subprocess(ollama create, 최대 1h) → to_thread 로 오프로드(이벤트루프 비점유).
        if RUNTIME.prepare:
            MODEL_TAG = await asyncio.to_thread(RUNTIME.prepare, MODEL_DIR, RUNTIME.base_url)
        else:
            MODEL_TAG = MODEL_DIR
        LIFESPAN_STATUS = True
        yield
    except Exception:
        traceback.print_exc()
        LIFESPAN_STATUS = "error"  # POST/GET 이 402(Model Error) 반환
        yield
    finally:
        if ENGINE_PROC is not None:
            try:
                ENGINE_PROC.terminate()
            except Exception:
                pass


# =======================================================================
# dataset (playground_llamacpp.py L192-209 와 동일)
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
    """RAG(embedding/reranker 파드) 결과 → context 문자열. embedding/reranker 는 엔진 무관(HF).
    playground_llamacpp.py L212-241 과 동일."""
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
        try:
            from langchain_core.load import loads
            docs = loads(payload)
            return "".join(getattr(d, "page_content", "") for d in docs)
        except Exception:
            print("[serving_adapter] RAG 결과 파싱 스킵(langchain 미탑재) — context 없이 진행")
            return ""
    except Exception:
        print("[serving_adapter] RAG 대기/실패 — context 없이 진행")
        return ""


# =======================================================================
# playground (playground_llamacpp.py L247-288 미러 — RUNTIME.generate 로 위임)
# =======================================================================
async def run_playground(test_input, session_id, db_id):
    result = None
    try:
        rag = await _fetch_rag_context(test_input)

        # 프롬프트 구성 (playground.py/llama.cpp 의 chat 메시지 형태 유지)
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
        # repetition_penalty(곱셈, ~1.0-1.3)를 OpenAI frequency_penalty(가산, 범위 [-2,2])로 그대로
        #   넘기면 의미 상이·값 거부 위험 → TGI 엔 미전달(엔진 기본값). 엔진별 정확 매핑은 후속.
        params = {
            "temperature": settings.LLM_PARAM_TEMPERATURE,
            "top_p": settings.LLM_PARAM_TOP_P,
            "max_tokens": max_tokens,
        }
        payload = RUNTIME.build_payload(messages, params, MODEL_TAG)

        async with httpx.AsyncClient() as client:
            resp = await client.post(RUNTIME.generate_url_for(MODEL_TAG), json=payload, timeout=1800)
            resp.raise_for_status()
            data = resp.json()
        result = RUNTIME.parse_response(data)

        try:
            await db.update_playground_test(
                db_id=db_id, **{"model": f"{RUNTIME.name}:{os.path.basename(MODEL_DIR or '')}"})
        except Exception:
            pass
        return result
    except Exception as e:
        traceback.print_exc()
        result = str(e)
    return result


app = FastAPI(lifespan=lifespan)
print("FASTAPI APP START (serving_adapter)")


@app.post("/", description="종합테스트")
@api_monitor()
async def post_llm(request: Request):
    global LIFESPAN_STATUS
    if LIFESPAN_STATUS is False:
        raise HTTPException(status_code=401, detail="Installing")
    elif LIFESPAN_STATUS == "error":
        raise HTTPException(status_code=402, detail="Model Error")

    print("playground(serving_adapter) test start")
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
    return "JF DEPLOYMENT RUNNING - playground (serving_adapter)"


if __name__ == "__main__":
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0')
