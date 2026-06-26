"""convert — 플랫폼 소유 llama.cpp 양자화·포팅 컨테이너 (SP-4 / v0.4 3.9).

mock-convert(examples/) 를 대체하는 **실제 변환** 컨테이너. 플랫폼이 소유·구현하며
(협력기관 제공물 아님), 배포는 external_container launch 메커니즘을 재사용한다
(SP-4 J-1: fb_porting 신규 서비스 회피). SP-1 외부 컨테이너 계약을 그대로 따르므로
플랫폼/FE/lineage/다운로드 와이어링은 변경 없이 동작한다.

실로직:
  1. (옵션) 매그니튜드 프루닝 — transformers 로 모델 로드 → Linear 가중치 희소화 → 재저장
  2. HF merged 모델(/model) → f16 GGUF (convert_hf_to_gguf.py)
  3. f16 GGUF → 타겟 양자화 GGUF (llama-quantize, Q4_K_M/Q5_K_M/Q6_K)
  4. 포팅 패키지(/output): model.gguf + inference.py + run.sh + config.json + metadata.json

베이스 이미지(ghcr.io/ggml-org/llama.cpp:full)가 convert_hf_to_gguf.py + llama-quantize
+ torch/transformers/gguf 를 제공한다. 이 앱은 그 위에 SP-1 계약 FastAPI 래퍼만 얹는다.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

# ── 플랫폼 주입 env (spec §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "convert")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_MODEL_PATH     = os.environ.get("JF_MODEL_PATH", "/model")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

# 베이스 이미지가 제공하는 도구 경로 (env override 가능).
LLAMA_QUANTIZE_BIN = os.environ.get("LLAMA_QUANTIZE_BIN", "/app/llama-quantize")
CONVERT_HF_TO_GGUF = os.environ.get("CONVERT_HF_TO_GGUF", "/app/convert_hf_to_gguf.py")

NAME    = "convert-llamacpp"
VERSION = "1.0.0"

# target_quant(q4/q5/q6) → llama-quantize 타입.
_QUANT_TYPE = {"q4": "Q4_K_M", "q5": "Q5_K_M", "q6": "Q6_K", "q8": "Q8_0"}

# model_name 은 산출 파일명(gguf)·inference.py 에 들어가므로 경로조작/코드주입 방지용
# 화이트리스트로 정제(영숫자/._- 만). 빈 값은 'model'.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_model_name(raw: Any) -> str:
    name = _SAFE_NAME_RE.sub("_", str(raw or "model")).strip("._-")
    return name[:64] or "model"

CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,   # llama.cpp 변환·양자화는 CPU 중심.
    "estimated_startup_seconds": 15,
    "estimated_duration_seconds": 300,
    "timeout_seconds": 3600,
}

app = FastAPI(title=NAME, version=VERSION)

_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    line = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    print(json.dumps(line, ensure_ascii=False), flush=True)


def _load_params(body_params: Optional[dict]) -> dict:
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"malformed or unreadable {JF_PARAMS_PATH}: {exc}") from exc


# ── 표준 endpoint (SP-1 규약) ──

@app.get("/health", tags=["표준"])
async def health():
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/live", tags=["표준"])
async def live():
    return JSONResponse(status_code=200, content={"status": "alive"})


@app.get("/info", tags=["표준"])
async def info():
    return {
        "name": NAME,
        "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE,
        "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        **CAPABILITIES,
    }


@app.post("/run", tags=["표준"])
async def run(body: Optional[dict] = Body(default=None)):
    body = body or {}
    raw = body["params"] if isinstance(body.get("params"), dict) else body
    try:
        params = _load_params(raw)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "E_PARAMS_INVALID", "message": str(exc)})

    if any(j["status"] == "running" for j in _jobs.values()):
        return JSONResponse(status_code=429, content={
            "status": "error", "code": "E_BUSY", "message": "a job is already running"})

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "progress": 0.0, "result": None,
                     "error": None, "cancel": False, "task": None}
    _jobs[job_id]["task"] = asyncio.create_task(_run_job(job_id, params))
    _emit("log", level="info", message="convert job started", job_id=job_id,
          item_id=JF_ITEM_ID, target_quant=params.get("target_quant", "q5"),
          prune=bool(params.get("prune", False)))
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "result": j["result"],
        "error": j["error"],
    }


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── 포팅 패키지 템플릿 (⑬ 코드 수정 UI 없음 / 다운로드만) ──

_INFERENCE_PY = '''\
# 포팅 패키지 — llama.cpp GGUF 추론 예시 (자동 생성, 코드 수정 UI 없음 / ⑬)
import sys
from llama_cpp import Llama
llm = Llama(model_path={model_path}, n_ctx=2048)
print(llm(sys.argv[1] if len(sys.argv) > 1 else "Hello", max_tokens=128)["choices"][0]["text"])
'''

_RUN_SH = '''\
#!/usr/bin/env bash
# 타겟 디바이스에서 실행: pip install llama-cpp-python && python inference.py "프롬프트"
set -e
pip install --quiet llama-cpp-python
python inference.py "$@"
'''


def _run(cmd: list, step: str) -> None:
    """blocking subprocess. 실패 시 stderr tail 을 담아 예외.

    llama-quantize 등 native 바이너리는 같은 디렉토리의 .so(libllama-*, libggml-*)에
    의존하는데 베이스 이미지가 LD_LIBRARY_PATH 를 안 박아둔다 → 바이너리 dir 을
    LD_LIBRARY_PATH 에 주입해 dynamic linking 보장.
    """
    env = dict(os.environ)
    bin_dir = os.path.dirname(LLAMA_QUANTIZE_BIN) or "/app"
    env["LD_LIBRARY_PATH"] = bin_dir + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1200:]
        raise RuntimeError(f"{step} failed (rc={proc.returncode}): {tail}")


def _has_hf_weights(model_dir: str) -> bool:
    try:
        for fn in os.listdir(model_dir):
            if fn.endswith((".safetensors", ".bin")) or fn == "model.safetensors.index.json":
                return True
    except OSError:
        return False
    return False


def _prune_model_sync(src_dir: str, dst_dir: str, sparsity: float) -> None:
    """매그니튜드(unstructured) 프루닝 — Linear 가중치 |w| 하위 sparsity 비율을 0 으로.

    주의: unstructured 희소화라 GGUF(dense) 용량은 줄지 않는다(spec RT-Optimization §9
    "실이득 작음"). 실로직은 존재하되 효과는 제한적 — 추후 structured/2:4 로 교체 가능.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(src_dir, torch_dtype=torch.float16)
    with torch.no_grad():
        for _, module in model.named_modules():
            if isinstance(module, torch.nn.Linear):
                w = module.weight.data
                n = w.numel()
                k = int(n * sparsity)
                if k > 0:
                    thresh = w.abs().flatten().kthvalue(k).values
                    w[w.abs() <= thresh] = 0.0
    os.makedirs(dst_dir, exist_ok=True)
    model.save_pretrained(dst_dir)
    try:
        AutoTokenizer.from_pretrained(src_dir).save_pretrained(dst_dir)
    except Exception:
        # 토크나이저가 별도 파일로만 있는 경우 원본에서 복사 (convert 가 요구).
        # ⚠ config.json 은 복사 X — save_pretrained 가 이미 (프루닝 반영) 작성했으므로
        # 덮어쓰면 안 됨. 토크나이저 파일만.
        _TOK_FILES = {"tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                      "vocab.json", "merges.txt", "tokenizer.model"}
        for fn in os.listdir(src_dir):
            if fn in _TOK_FILES or "token" in fn.lower():
                shutil.copy2(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))


async def _run_job(job_id: str, params: dict) -> None:
    """HF merged 모델 → (옵션 프루닝) → f16 GGUF → 타겟 양자화 → 포팅 패키지."""
    j = _jobs[job_id]
    workdir = None
    try:
        target_quant = str(params.get("target_quant", "q5")).lower()
        model_name = _safe_model_name(params.get("model_name", "model"))
        do_prune = bool(params.get("prune", False))
        # prune_sparsity 범위 가드 — 1.0 이상이면 kthvalue 가 터지거나 전체 0.
        try:
            sparsity = float(params.get("prune_sparsity", 0.5))
        except (TypeError, ValueError):
            sparsity = 0.5
        sparsity = max(0.0, min(0.99, sparsity))
        qtype = _QUANT_TYPE.get(target_quant, "Q5_K_M")

        if not _has_hf_weights(JF_MODEL_PATH):
            raise RuntimeError(
                f"no HF weights at {JF_MODEL_PATH} (merged 모델 필요 — LoRA 어댑터만 있으면 merge 후 재시도)")

        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        # 예측가능 /tmp 경로 대신 mkdtemp (심링크 레이스 방지).
        workdir = tempfile.mkdtemp(prefix=f"convert-{job_id}-")

        steps = ["prune", "convert-to-gguf", "quantize", "package"] if do_prune \
            else ["convert-to-gguf", "quantize", "package"]
        total = len(steps)
        done = 0

        def _progress(step: str) -> None:
            nonlocal done
            done += 1
            _emit("progress", job_id=job_id, step=done, total=total,
                  percent=round(done / total * 100, 1), message=step)
            j["progress"] = round(done / total, 4)

        def _check_cancel(step: str) -> bool:
            if j["cancel"]:
                j["status"] = "cancelled"
                _emit("log", level="info", message="convert cancelled", job_id=job_id, step=step)
                return True
            return False

        # 1) (옵션) 프루닝
        model_src = JF_MODEL_PATH
        if do_prune:
            if _check_cancel("prune"):
                return
            pruned_dir = os.path.join(workdir, "pruned")
            await asyncio.to_thread(_prune_model_sync, JF_MODEL_PATH, pruned_dir, sparsity)
            model_src = pruned_dir
            _progress(f"prune (sparsity={sparsity})")

        # 2) HF → f16 GGUF
        if _check_cancel("convert-to-gguf"):
            return
        f16_path = os.path.join(workdir, "f16.gguf")
        await asyncio.to_thread(
            _run,
            ["python3", CONVERT_HF_TO_GGUF, model_src, "--outfile", f16_path, "--outtype", "f16"],
            "convert_hf_to_gguf",
        )
        _progress("convert to f16 GGUF")

        # 3) 타겟 양자화
        if _check_cancel("quantize"):
            return
        gguf_name = f"{model_name}.{target_quant}.gguf"
        gguf_path = os.path.join(JF_OUTPUT_PATH, gguf_name)
        # model_name 은 정제됐지만 방어적으로 /output 이탈 재확인.
        out_real = os.path.realpath(JF_OUTPUT_PATH)
        if os.path.commonpath([os.path.realpath(gguf_path), out_real]) != out_real:
            raise RuntimeError(f"gguf path escapes output dir: {gguf_name!r}")
        await asyncio.to_thread(
            _run, [LLAMA_QUANTIZE_BIN, f16_path, gguf_path, qtype], "llama-quantize",
        )
        _progress(f"quantize → {qtype}")

        # 4) 포팅 패키지 — blocking subprocess(llama-quantize)는 취소 못 받으니
        # 패키징 직전 한 번 더 취소 확인(취소된 job 이 completed 로 publish 되는 것 방지).
        if _check_cancel("package"):
            return
        gguf_bytes = os.path.getsize(gguf_path)
        with open(os.path.join(JF_OUTPUT_PATH, "inference.py"), "w", encoding="utf-8") as f:
            f.write(_INFERENCE_PY.format(model_path=json.dumps(gguf_name)))
        with open(os.path.join(JF_OUTPUT_PATH, "run.sh"), "w", encoding="utf-8") as f:
            f.write(_RUN_SH)
        config = {"model_file": gguf_name, "quantization": qtype, "n_ctx": 2048,
                  "source_model": model_name, "pruned": do_prune}
        with open(os.path.join(JF_OUTPUT_PATH, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        metadata = {
            "name": NAME, "version": VERSION, "job_id": job_id, "item_id": JF_ITEM_ID,
            "target_quant": target_quant, "quantize_type": qtype, "gguf_bytes": gguf_bytes,
            "pruned": do_prune, "prune_sparsity": sparsity if do_prune else None,
            "files": [gguf_name, "inference.py", "run.sh", "config.json", "metadata.json"],
        }
        with open(os.path.join(JF_OUTPUT_PATH, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        _progress("write package")

        j["result"] = {
            "gguf_file": gguf_name,
            "gguf_bytes": gguf_bytes,
            "target_quant": target_quant,
            "quantize_type": qtype,
            "pruned": do_prune,
            "package_files": metadata["files"],
            "output_dir": JF_OUTPUT_PATH,
        }
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="convert completed", job_id=job_id,
              gguf_file=gguf_name, gguf_bytes=gguf_bytes, quantize_type=qtype)

    except Exception as exc:
        j["status"] = "failed"
        j["error"] = {"code": "E_CONVERT_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_CONVERT_FAILED", message=str(exc), fatal=True)
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        # 실패/취소 시 부분 산출물 정리 — /output(=jobs/<id>/output)은 이 job 전용이라
        # 안전. 안 지우면 플랫폼 list_quantize_package 가 ready 로 오인 + lineage 오마감.
        if j["status"] != "completed":
            try:
                for fn in os.listdir(JF_OUTPUT_PATH):
                    fp = os.path.join(JF_OUTPUT_PATH, fn)
                    if os.path.isfile(fp):
                        os.remove(fp)
            except OSError:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
