#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
codegen.py — 배포 대상에서 모델을 실행할 서비스 코드 생성기

pipeline.py 의 codegen 단계가 호출한다. 변환이 끝난 모델 폴더와 deploy.yaml 설정을
받아 그대로 실행 가능한 서비스 한 벌을 만든다.

생성물:
    <out_dir>/
      runtime.json       생성 시점에 확정된 설정 (코드는 전부 여기서 값을 읽는다)
      engine.py          선택된 target_engine 1종의 추론 래퍼
      app.py             invoke_time 에 맞는 구동 방식 (HTTP 서버 / 워커 루프)
      prompt.py          use_prompt_engineering=yes 일 때만
      requirements.txt
      README.md

설계 의도:
    코드 템플릿은 '정적'이고, 달라지는 값은 전부 runtime.json 으로 뺐다.
    덕분에 생성된 코드는 문자열 치환 흔적 없이 읽히고, 모델 경로·포트만 바꿔
    다시 쓰는 것도 파일 하나 수정으로 끝난다.

엔진별 매핑:
    vllm       → vllm.LLM
    llama.cpp  → llama_cpp.Llama (GGUF 단일 파일)
    pytorch    → transformers AutoModelForCausalLM
    tensorrt   → onnxruntime / optimum ORTModel (현재는 ONNX 런타임까지)

구동 방식(invoke_time):
    user   → FastAPI HTTP 서버 (/health, /generate, /v1/chat/completions)
    period → 고정 주기로 공유 폴더를 훑는 워커
    event  → 공유 폴더에 새 입력이 생기면 처리하는 워커
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 저장소 루트를 검색 경로에 추가 — 이 파일을 개별 CLI 로 실행할 때
# 루트의 yaml_parser 를 찾기 위함이다.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# 엔진 래퍼 템플릿 — 공통 인터페이스: Engine(cfg).generate(prompt, **kw) -> str
# ---------------------------------------------------------------------------

_ENGINE_HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""engine.py — 추론 엔진 래퍼 (codegen 자동 생성)

공통 인터페이스:
    eng = Engine(load_runtime())
    text = eng.generate("안녕", max_tokens=128, temperature=0.7)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_runtime() -> dict:
    """runtime.json 을 읽는다. MODEL_DIR 환경변수가 있으면 모델 경로를 덮어쓴다."""
    cfg = json.loads((HERE / "runtime.json").read_text(encoding="utf-8"))
    override = os.environ.get("MODEL_DIR")
    if override:
        cfg["model_dir"] = override
    if not Path(cfg["model_dir"]).is_absolute():
        cfg["model_dir"] = str((HERE / cfg["model_dir"]).resolve())
    return cfg

'''

_ENGINE_VLLM = _ENGINE_HEADER + '''

class Engine:
    """vLLM 백엔드. AWQ/GPTQ 체크포인트는 quantization 값을 그대로 넘기면 된다."""

    def __init__(self, cfg: dict):
        from vllm import LLM, SamplingParams
        self._SamplingParams = SamplingParams

        kwargs = {"model": cfg["model_dir"]}
        if cfg.get("quantization"):
            kwargs["quantization"] = cfg["quantization"]
        if cfg.get("dtype"):
            kwargs["dtype"] = cfg["dtype"]
        if cfg.get("max_model_len"):
            kwargs["max_model_len"] = cfg["max_model_len"]

        print(f"[engine] vLLM 로드: {kwargs}", flush=True)
        self.llm = LLM(**kwargs)
        self.defaults = cfg.get("generation", {})

    def generate(self, prompt: str, **kw) -> str:
        params = self._SamplingParams(
            max_tokens=kw.get("max_tokens", self.defaults.get("max_tokens", 256)),
            temperature=kw.get("temperature", self.defaults.get("temperature", 0.7)),
            top_p=kw.get("top_p", self.defaults.get("top_p", 0.95)),
        )
        out = self.llm.generate([prompt], params)
        return out[0].outputs[0].text

    def close(self):
        pass
'''

_ENGINE_LLAMACPP = _ENGINE_HEADER + '''

class Engine:
    """llama.cpp 백엔드. 변환 산출물의 단일 .gguf 파일을 로드한다."""

    def __init__(self, cfg: dict):
        from llama_cpp import Llama

        model_dir = Path(cfg["model_dir"])
        gguf = model_dir if model_dir.suffix == ".gguf" else None
        if gguf is None:
            candidates = sorted(model_dir.glob("*.gguf"))
            if not candidates:
                raise FileNotFoundError(f"{model_dir} 에서 .gguf 파일을 찾지 못했습니다.")
            gguf = candidates[0]

        print(f"[engine] llama.cpp 로드: {gguf}", flush=True)
        self.llm = Llama(
            model_path=str(gguf),
            n_ctx=cfg.get("max_model_len") or 4096,
            n_threads=cfg.get("n_threads") or os.cpu_count(),
            verbose=False,
        )
        self.defaults = cfg.get("generation", {})

    def generate(self, prompt: str, **kw) -> str:
        out = self.llm(
            prompt,
            max_tokens=kw.get("max_tokens", self.defaults.get("max_tokens", 256)),
            temperature=kw.get("temperature", self.defaults.get("temperature", 0.7)),
            top_p=kw.get("top_p", self.defaults.get("top_p", 0.95)),
        )
        return out["choices"][0]["text"]

    def close(self):
        pass
'''

_ENGINE_PYTORCH = _ENGINE_HEADER + '''

class Engine:
    """transformers 직접 실행 백엔드."""

    def __init__(self, cfg: dict):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        dtype_name = cfg.get("dtype") or "auto"
        dtype = {"f16": torch.float16, "bf16": torch.bfloat16,
                 "f32": torch.float32}.get(dtype_name, "auto")
        device = cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")

        print(f"[engine] transformers 로드: {cfg['model_dir']} "
              f"(dtype={dtype_name}, device={device})", flush=True)
        self.tok = AutoTokenizer.from_pretrained(cfg["model_dir"])
        self.model = AutoModelForCausalLM.from_pretrained(
            cfg["model_dir"], torch_dtype=dtype).to(device).eval()
        self.device = device
        self.defaults = cfg.get("generation", {})

    def generate(self, prompt: str, **kw) -> str:
        inputs = self.tok(prompt, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=kw.get("max_tokens", self.defaults.get("max_tokens", 256)),
                temperature=kw.get("temperature", self.defaults.get("temperature", 0.7)),
                top_p=kw.get("top_p", self.defaults.get("top_p", 0.95)),
                do_sample=True,
                pad_token_id=self.tok.eos_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[-1]:]
        return self.tok.decode(gen, skip_special_tokens=True)

    def close(self):
        pass
'''

_ENGINE_ONNX = _ENGINE_HEADER + '''

class Engine:
    """ONNX Runtime 백엔드.

    주의: 파이프라인은 현재 ONNX export 까지만 수행한다. TensorRT .plan(engine)
    빌드는 아직 없으므로 여기서는 onnxruntime 으로 실행한다. TensorRT 로 붙이려면
    TensorrtExecutionProvider 를 providers 앞에 두거나 trtexec 로 engine 을
    따로 빌드해야 한다."""

    def __init__(self, cfg: dict):
        from transformers import AutoTokenizer
        from optimum.onnxruntime import ORTModelForCausalLM

        providers = cfg.get("onnx_providers") or ["CPUExecutionProvider"]
        print(f"[engine] ONNX Runtime 로드: {cfg['model_dir']} "
              f"(providers={providers})", flush=True)
        self.tok = AutoTokenizer.from_pretrained(cfg["model_dir"])
        self.model = ORTModelForCausalLM.from_pretrained(
            cfg["model_dir"], provider=providers[0])
        self.defaults = cfg.get("generation", {})

    def generate(self, prompt: str, **kw) -> str:
        inputs = self.tok(prompt, return_tensors="pt")
        out = self.model.generate(
            **inputs,
            max_new_tokens=kw.get("max_tokens", self.defaults.get("max_tokens", 256)),
            temperature=kw.get("temperature", self.defaults.get("temperature", 0.7)),
            do_sample=True,
            pad_token_id=self.tok.eos_token_id,
        )
        gen = out[0][inputs["input_ids"].shape[-1]:]
        return self.tok.decode(gen, skip_special_tokens=True)

    def close(self):
        pass
'''

_ENGINE_TRTLLM = _ENGINE_HEADER + '''

class Engine:
    """TensorRT-LLM 백엔드.

    TRT 엔진 백엔드가 제거되어 PyTorch 백엔드만 남았다. 엔진 빌드 단계가 없고
    HF 체크포인트를 그대로 로드한다. ModelOpt 로 양자화한 체크포인트도 같은
    경로로 들어간다(config.json 의 quantization_config 로 식별된다)."""

    def __init__(self, cfg: dict):
        from tensorrt_llm import LLM, SamplingParams
        self._SamplingParams = SamplingParams

        kwargs = {"model": cfg["model_dir"]}
        if cfg.get("max_model_len"):
            kwargs["max_seq_len"] = cfg["max_model_len"]
        if cfg.get("tensor_parallel_size"):
            kwargs["tensor_parallel_size"] = cfg["tensor_parallel_size"]

        print(f"[engine] TensorRT-LLM 로드: {kwargs}", flush=True)
        self.llm = LLM(**kwargs)
        self.defaults = cfg.get("generation", {})

    def generate(self, prompt: str, **kw) -> str:
        params = self._SamplingParams(
            max_tokens=kw.get("max_tokens", self.defaults.get("max_tokens", 256)),
            temperature=kw.get("temperature", self.defaults.get("temperature", 0.7)),
            top_p=kw.get("top_p", self.defaults.get("top_p", 0.95)),
        )
        out = self.llm.generate([prompt], params)
        return out[0].outputs[0].text

    def close(self):
        try:
            self.llm.shutdown()
        except Exception:
            pass
'''


ENGINE_TEMPLATES = {
    "vllm": _ENGINE_VLLM,
    "trtllm": _ENGINE_TRTLLM,
    "llama.cpp": _ENGINE_LLAMACPP,
    "pytorch": _ENGINE_PYTORCH,
    "tensorrt": _ENGINE_ONNX,
}

ENGINE_REQUIREMENTS = {
    "vllm": ["vllm"],
    "trtllm": ["tensorrt-llm>=1.2.0"],
    "llama.cpp": ["llama-cpp-python"],
    "pytorch": ["torch", "transformers", "safetensors"],
    "tensorrt": ["transformers", "optimum-onnx[onnxruntime]", "onnxruntime"],
}


# ---------------------------------------------------------------------------
# 프롬프트 적용 모듈
# ---------------------------------------------------------------------------
_PROMPT_PY = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt.py — 시스템 프롬프트 적용 (codegen 자동 생성)

prompt_method:
    once        서버 기동 시 한 번 읽어 모든 요청 앞에 붙인다
    every query 요청마다 파일을 다시 읽는다(운영 중 수정 반영)
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent


class PromptBuilder:
    def __init__(self, cfg: dict):
        p = (cfg.get("prompt") or {})
        self.method = (p.get("method") or "once").lower()
        self.path = p.get("file")
        if self.path and not Path(self.path).is_absolute():
            self.path = str((HERE / self.path).resolve())
        self._cached = self._read() if self.method == "once" else None

    def _read(self) -> str:
        if not self.path:
            return ""
        try:
            return Path(self.path).read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"[prompt] 프롬프트 파일을 읽지 못했습니다({e}) — 빈 값으로 진행",
                  flush=True)
            return ""

    def build(self, user_text: str) -> str:
        system = self._cached if self.method == "once" else self._read()
        if not system:
            return user_text
        return f"{system}\\n\\n{user_text}"
'''


# ---------------------------------------------------------------------------
# app.py — invoke_time=user (HTTP 서버)
# ---------------------------------------------------------------------------
_APP_SERVER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py — HTTP 추론 서비스 (codegen 자동 생성, invoke_time=user)

엔드포인트:
    GET  /health                 상태 확인
    POST /generate               {"prompt": "...", "max_tokens": 128}
    POST /v1/chat/completions    OpenAI 호환 최소 구현

실행:
    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from engine import Engine, load_runtime

CFG = load_runtime()

engine = None
prompt_builder = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 모델을 한 번 로드한다(요청마다 로드하면 안 된다)."""
    global engine, prompt_builder
    engine = Engine(CFG)
    if CFG.get("prompt"):
        from prompt import PromptBuilder
        prompt_builder = PromptBuilder(CFG)
    print("[app] 준비 완료", flush=True)
    yield
    if engine:
        engine.close()
    print("[app] 종료", flush=True)


app = FastAPI(title=CFG.get("app_name") or "model-service", lifespan=lifespan)


def _apply_prompt(text: str) -> str:
    return prompt_builder.build(text) if prompt_builder else text


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None


@app.get("/health")
def health():
    return {"status": "ok" if engine else "loading",
            "engine": CFG.get("target_engine"),
            "model_dir": CFG.get("model_dir")}


@app.post("/generate")
def generate(req: GenerateRequest):
    if engine is None:
        raise HTTPException(503, "엔진이 아직 준비되지 않았습니다.")
    kw = {k: v for k, v in
          {"max_tokens": req.max_tokens, "temperature": req.temperature}.items()
          if v is not None}
    return {"text": engine.generate(_apply_prompt(req.prompt), **kw)}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    if engine is None:
        raise HTTPException(503, "엔진이 아직 준비되지 않았습니다.")
    # 최소 구현: 메시지를 role 표기와 함께 이어붙인다.
    # 모델별 chat template 을 쓰려면 이 부분을 tokenizer.apply_chat_template 로 교체.
    parts = [f"{m.role}: {m.content}" for m in req.messages]
    prompt = _apply_prompt("\\n".join(parts) + "\\nassistant:")
    kw = {k: v for k, v in
          {"max_tokens": req.max_tokens, "temperature": req.temperature}.items()
          if v is not None}
    text = engine.generate(prompt, **kw)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or CFG.get("app_name") or "local",
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
    }


if __name__ == "__main__":
    svc = CFG.get("service", {})
    uvicorn.run(app, host=svc.get("ip") or "0.0.0.0",
                port=int(svc.get("port") or 8000))
'''


# ---------------------------------------------------------------------------
# app.py — invoke_time=period / event (워커 루프)
# ---------------------------------------------------------------------------
_APP_WORKER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py — 공유 폴더 기반 추론 워커 (codegen 자동 생성)

invoke_time:
    period  고정 주기로 inbox 를 훑는다
    event   새 파일이 생기는 즉시 처리한다(짧은 주기 폴링)

폴더 구조 (service_shared_folder 아래):
    inbox/    처리할 입력 (.txt 또는 {"prompt": "..."} 형태의 .json)
    outbox/   결과 .json
    done/     처리 완료된 입력 원본

sdf_action 이 설정돼 있으면 결과를 그 함수로 넘긴다:
    entry_point(result: dict, cfg: dict) -> None
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import signal
import sys
import time
from pathlib import Path

from engine import Engine, load_runtime

CFG = load_runtime()
_running = True


def _stop(signum, frame):
    global _running
    print(f"[worker] 종료 신호({signum}) 수신 — 진행 중인 작업까지만 마칩니다.", flush=True)
    _running = False


def load_action(cfg: dict):
    """sdf_action.lib_path 의 entry_point 함수를 로드한다. 없으면 None."""
    action = cfg.get("sdf_action") or {}
    lib, entry = action.get("lib_path"), action.get("entry_point")
    if not lib or not entry:
        return None
    path = Path(lib)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parent / path).resolve()
    if not path.exists():
        print(f"[worker] sdf_action 모듈이 없습니다: {path} — 후처리를 건너뜁니다.",
              flush=True)
        return None
    spec = importlib.util.spec_from_file_location("sdf_action", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, entry, None)
    if fn is None:
        print(f"[worker] {path} 에 '{entry}' 가 없습니다 — 후처리를 건너뜁니다.",
              flush=True)
        return None
    print(f"[worker] sdf_action 로드: {path}::{entry}", flush=True)
    return fn


def read_prompt(path: Path) -> str | None:
    try:
        if path.suffix == ".json":
            return (json.loads(path.read_text(encoding="utf-8"))
                    .get("prompt"))
        return path.read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"[worker] 입력을 읽지 못했습니다 {path.name}: {e}", flush=True)
        return None


def main() -> int:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    svc = CFG.get("service", {})
    shared = svc.get("shared_folder")
    if not shared:
        print("[worker] service_shared_folder 가 설정되지 않았습니다.", file=sys.stderr)
        return 2

    root = Path(shared)
    inbox, outbox, done = root / "inbox", root / "outbox", root / "done"
    for d in (inbox, outbox, done):
        d.mkdir(parents=True, exist_ok=True)

    interval = float(svc.get("period_seconds") or
                     (1.0 if svc.get("invoke_time") == "event" else 60.0))
    print(f"[worker] invoke_time={svc.get('invoke_time')} / 주기 {interval}s / "
          f"감시 폴더 {inbox}", flush=True)

    engine = Engine(CFG)
    prompt_builder = None
    if CFG.get("prompt"):
        from prompt import PromptBuilder
        prompt_builder = PromptBuilder(CFG)
    action = load_action(CFG)

    while _running:
        items = sorted(p for p in inbox.iterdir()
                       if p.is_file() and p.suffix in (".txt", ".json"))
        for path in items:
            if not _running:
                break
            text = read_prompt(path)
            if not text:
                continue
            prompt = prompt_builder.build(text) if prompt_builder else text
            t0 = time.time()
            try:
                output = engine.generate(prompt)
                result = {"input": path.name, "output": output,
                          "elapsed_sec": round(time.time() - t0, 3)}
            except Exception as e:
                result = {"input": path.name, "error": f"{type(e).__name__}: {e}"}
                print(f"[worker] 추론 실패 {path.name}: {e}", flush=True)

            (outbox / f"{path.stem}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            shutil.move(str(path), str(done / path.name))
            print(f"[worker] 처리 완료: {path.name} "
                  f"({result.get('elapsed_sec', '-')}s)", flush=True)

            if action:
                try:
                    action(result, CFG)
                except Exception as e:
                    print(f"[worker] sdf_action 실패: {e}", flush=True)

        time.sleep(interval)

    engine.close()
    print("[worker] 종료", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ---------------------------------------------------------------------------
# 생성 로직
# ---------------------------------------------------------------------------
def _build_runtime(plan, cfg, model_dir: str) -> dict:
    """생성된 코드가 읽을 runtime.json 내용을 만든다."""
    cg = cfg.code_generation
    svc = cg.service_info
    spec = svc.spec
    bi = cfg.image_build.build_info
    opt = cfg.optimization

    # vLLM 은 AWQ/GPTQ 체크포인트를 quantization 인자로 알려줘야 한다.
    quantization = None
    if plan.quant and plan.quant.method in ("awq", "gptq"):
        quantization = plan.quant.method

    runtime = {
        "app_name": bi.app_name or "model-service",
        "target_engine": plan.target_engine,
        "model_dir": model_dir,
        "model_format": plan.output_format,
        "quantization": quantization,
        "dtype": plan.save_precision,
        "service": {
            "type": svc.service_type,
            "invoke_time": spec.invoke_time,
            "ip": spec.service_ip,
            "port": spec.service_port,
            "shared_folder": spec.service_shared_folder,
            "period_seconds": spec.extra.get("period_seconds"),
        },
        "generation": {"max_tokens": 256, "temperature": 0.7, "top_p": 0.95},
    }

    sdf = cg.coding_info.sdf_action
    if sdf.lib_path and sdf.entry_point:
        runtime["sdf_action"] = {"lib_path": sdf.lib_path,
                                 "entry_point": sdf.entry_point}

    pe = cfg.prompt_engineering
    if _truthy(cg.use_prompt_engineering) and (pe.prompt_file or pe.prompt_method):
        runtime["prompt"] = {"method": pe.prompt_method or "once",
                             "file": pe.prompt_file}

    if plan.target_engine == "tensorrt":
        runtime["onnx_providers"] = ["CPUExecutionProvider"]

    return runtime


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"yes", "true", "y", "1"}


def _requirements(engine: str, invoke_time: str) -> str:
    lines = [f"# {engine} 서비스 실행 의존성 (codegen 자동 생성)"]
    lines += ENGINE_REQUIREMENTS[engine]
    if invoke_time == "user":
        lines += ["", "# HTTP 서비스", "fastapi", "uvicorn[standard]", "pydantic"]
    return "\n".join(lines) + "\n"


def _readme(runtime: dict, invoke_time: str, files: list[str]) -> str:
    svc = runtime["service"]
    lines = [
        f"# {runtime['app_name']}",
        "",
        "`codegen` 이 자동 생성한 서비스입니다. 설정값은 모두 `runtime.json` 에 있으므로,",
        "모델 경로나 포트를 바꾸려면 그 파일만 고치면 됩니다",
        "(`MODEL_DIR` 환경변수로 모델 경로만 덮어쓸 수도 있습니다).",
        "",
        "## 구성",
        "",
        f"- 엔진: `{runtime['target_engine']}` (모델 포맷 `{runtime['model_format']}`)",
        f"- 서비스 타입: `{svc['type']}` / 구동 방식: `{invoke_time}`",
    ]
    if runtime.get("quantization"):
        lines.append(f"- 양자화 체크포인트: `{runtime['quantization']}`")
    lines += ["", "## 실행", "", "```bash", "pip install -r requirements.txt"]
    lines += ["python app.py", "```", ""]

    if invoke_time == "user":
        port = svc.get("port") or 8000
        lines += [
            "## 호출 예",
            "",
            "```bash",
            f"curl localhost:{port}/health",
            f"curl -X POST localhost:{port}/generate \\",
            "  -H 'Content-Type: application/json' \\",
            "  -d '{\"prompt\": \"안녕하세요\", \"max_tokens\": 64}'",
            "```",
            "",
            "`/v1/chat/completions` 는 OpenAI 호환 최소 구현입니다. 모델별 chat template",
            "을 쓰려면 `app.py` 의 메시지 조립 부분을 `tokenizer.apply_chat_template` 로",
            "바꾸세요.",
            "",
        ]
    else:
        shared = svc.get("shared_folder") or "(미설정)"
        lines += [
            "## 입출력",
            "",
            f"공유 폴더 `{shared}` 아래에서 동작합니다.",
            "",
            "- `inbox/` 에 `.txt` 또는 `{\"prompt\": \"...\"}` 형태의 `.json` 을 넣으면 처리합니다",
            "- 결과는 `outbox/` 에 `.json` 으로 떨어집니다",
            "- 처리된 입력은 `done/` 으로 옮겨집니다",
            "",
        ]
        if runtime.get("sdf_action"):
            a = runtime["sdf_action"]
            lines += [
                f"결과는 `{a['lib_path']}` 의 `{a['entry_point']}(result, cfg)` 로도 전달됩니다.",
                "",
            ]

    lines += ["## 생성된 파일", ""]
    lines += [f"- `{f}`" for f in files]
    lines += ["", "> 이 코드는 생성물입니다. 파이프라인을 다시 돌리면 덮어쓰이므로,",
              "> 손으로 고친 내용은 별도 파일로 분리해 두세요.", ""]
    return "\n".join(lines)


def generate_service(plan, cfg, out_dir, model_dir=None):
    """서비스 코드를 생성한다.

    인자:
        plan      : yaml_parser.Plan
        cfg       : yaml_parser.DeployConfig
        out_dir   : 생성 위치
        model_dir : 변환된 모델 폴더. 미지정 시 plan 기준 상대경로를 쓴다.

    반환값:
        (0, "success") 또는 (-1, "<오류 메시지>")
    """
    try:
        engine = plan.target_engine
        if engine not in ENGINE_TEMPLATES:
            return (-1, f"코드 생성을 지원하지 않는 엔진입니다: {engine}")

        invoke_time = (cfg.code_generation.service_info.spec.invoke_time
                       or "user").lower()
        if invoke_time not in ("user", "period", "event"):
            return (-1, f"알 수 없는 invoke_time 입니다: {invoke_time}")
        if invoke_time in ("period", "event"):
            if not cfg.code_generation.service_info.spec.service_shared_folder:
                return (-1, f"invoke_time={invoke_time} 에는 "
                            f"service_info.spec.service_shared_folder 가 필요합니다.")

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        runtime = _build_runtime(plan, cfg, model_dir or "../30_converted")

        written = []

        def write(name: str, content: str, executable: bool = False):
            p = out / name
            p.write_text(content, encoding="utf-8")
            if executable:
                p.chmod(0o755)
            written.append(name)

        write("runtime.json",
              json.dumps(runtime, ensure_ascii=False, indent=2) + "\n")
        write("engine.py", ENGINE_TEMPLATES[engine])
        write("app.py",
              _APP_SERVER if invoke_time == "user" else _APP_WORKER,
              executable=True)
        if runtime.get("prompt"):
            write("prompt.py", _PROMPT_PY)
        write("requirements.txt", _requirements(engine, invoke_time))
        write("README.md", _readme(runtime, invoke_time, written + ["README.md"]))

        return (0, f"{engine} / invoke_time={invoke_time} 서비스 생성 "
                   f"({len(written)}개 파일)")

    except Exception as e:
        return (-1, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# CLI — deploy.yaml 만으로 코드 생성만 따로 돌릴 때
# ---------------------------------------------------------------------------
def main() -> int:
    import argparse
    from yaml_parser import DeployConfig

    ap = argparse.ArgumentParser(description="배포 서비스 코드 생성기")
    ap.add_argument("config", help="deploy.yaml 경로")
    ap.add_argument("-o", "--output", default="./service", help="생성 위치")
    ap.add_argument("--model-dir", default=None,
                    help="변환된 모델 폴더 (기본: ../30_converted)")
    args = ap.parse_args()

    cfg = DeployConfig.from_yaml(args.config)
    errors, warnings = cfg.validate()
    for w in warnings:
        print(f"[WARN ] {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    code, msg = generate_service(cfg.resolve_plan(), cfg, args.output,
                                 args.model_dir)
    if code == 0:
        print(f"[done] {args.output} — {msg}")
        return 0
    print(f"오류: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
