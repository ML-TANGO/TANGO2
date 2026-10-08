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
VERSION = "1.1.2"

# SDS(eva-vlm) 커밋 마운트(플랫폼 차트가 commit_models 를 RO 로 붙인다).
CHECKPOINTS_ROOT = os.environ.get("CHECKPOINTS_ROOT", "/models/checkpoints")

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


# SDS(eva-vlm) 패키지 — llama.cpp 멀티모달(llama-mtmd-cli) 추론. eva 컨테이너와 같은 입력
# (이미지 + AIS 행 + 출력 유형) 을 같은 프롬프트로 조립한다(eva api/model_manager.py 대조).
_VLM_INFERENCE_PY = '''\
# 포팅 패키지 — SDS(eva-vlm) llama.cpp 멀티모달 추론 예시 (자동 생성, 코드 수정 UI 없음 / ⑬)
# 사용: python inference.py <이미지> <AIS csv|json> [출력유형] [--server http://<디바이스>:<포트>]
#   --server 없음: 이 장비에서 llama.cpp 의 llama-mtmd-cli 로 실행 (PATH 또는 LLAMA_MTMD_CLI 환경변수)
#   --server 있음: 엣지 배포된 llama-server(--mmproj 로 띄운 OpenAI 호환 서버)에 같은 프롬프트로 요청
#   공통: pip install pillow
import base64, csv, json, os, subprocess, sys, tempfile, urllib.request
from PIL import Image, ImageOps

MODEL = {model_path}
MMPROJ = {mmproj_path}
PROMPTS = {prompts}
DEFAULT_TYPE = {default_type}


def load_rows(path):
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def ais_text(rows, lang):
    ko = lang == "ko"
    lines = ["[선박 AIS 정보]" if ko else "[Vessel AIS Information]"]
    for r in rows:
        spd, hdg = f"{{float(r['knot']):.1f}}kt", f"{{float(r['heading']):.1f}}°"
        lat, lon = f"{{float(r['latitude']):.6f}}", f"{{float(r['longitude']):.6f}}"
        size = f"{{int(float(r['length']))}}m {{'×' if ko else 'x'}} {{int(float(r['width']))}}m"
        draft = f"{{int(float(r['draft']))}}m"
        if int(float(r["my_ship"])) == 1:
            lines.append(f"- 자선 (ID:{{r['ship_id']}}) | 위도:{{lat}} 경도:{{lon}} | 속도:{{spd}} 방향:{{hdg}} | 선체:{{size}} 흘수:{{draft}}" if ko else
                         f"- Own vessel (ID:{{r['ship_id']}}) | Lat:{{lat}} Lon:{{lon}} | Speed:{{spd}} Heading:{{hdg}} | Size:{{size}} Draft:{{draft}}")
            continue
        bbox = ""
        if str(r.get("bbox_x", "")).strip() not in ("", "None"):
            box = (f"x={{float(r['bbox_x']):.0f}} y={{float(r['bbox_y']):.0f}} "
                   f"w={{float(r['bbox_width']):.0f}} h={{float(r['bbox_height']):.0f}}")
            bbox = f" | 바운딩박스:[{{box}}]" if ko else f" | BoundingBox:[{{box}}]"
        lines.append(f"- 주변선박 (ID:{{r['ship_id']}}) | 위도:{{lat}} 경도:{{lon}} | 속도:{{spd}} 방향:{{hdg}} | 선체:{{size}} 흘수:{{draft}}{{bbox}}" if ko else
                     f"- Nearby vessel (ID:{{r['ship_id']}}) | Lat:{{lat}} Lon:{{lon}} | Speed:{{spd}} Heading:{{hdg}} | Size:{{size}} Draft:{{draft}}{{bbox}}")
    return "\\n".join(lines)


def square_crop(src, dst):
    # 학습 전처리(짧은 변 맞춤 + 중앙 크롭) 와 같은 시야 — llama.cpp 는 정사각형 패딩을 하므로 미리 자른다.
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")  # eva 와 같은 EXIF 회전 보정
    w, h = im.size
    s = min(w, h)
    im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).save(dst)


def ask_server(url, image, prompt):
    # CLI 와 같은 프롬프트("<__media__>\\n" + 프롬프트, 학습 형식 <image>\\n)가 되도록 텍스트 앞에
    # 개행을 둔다 — llama-server 는 이미지 마커 뒤에 텍스트를 개행 없이 붙인다(그러면 출력이 달라진다).
    with open(image, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    body = {{"messages": [{{"role": "user", "content": [
                {{"type": "image_url", "image_url": {{"url": "data:image/png;base64," + data}}}},
                {{"type": "text", "text": "\\n" + prompt}}]}}],
            "temperature": 0, "repeat_penalty": 1.1, "max_tokens": 512}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={{"Content-Type": "application/json"}})
    with urllib.request.urlopen(req, timeout=900) as r:
        print(json.load(r)["choices"][0]["message"]["content"])


def main():
    usage = "사용: python inference.py <이미지> <AIS csv|json> [출력유형] [--server http://<디바이스>:<포트>]"
    args, server, rest = [], None, iter(sys.argv[1:])
    for a in rest:
        if a == "--server":
            server = next(rest, None) or sys.exit(usage)
        elif a.startswith("--server="):
            server = a.split("=", 1)[1] or sys.exit(usage)
        else:
            args.append(a)
    if len(args) < 2:
        sys.exit(usage)
    output_type = args[2] if len(args) > 2 else DEFAULT_TYPE
    lang = "en" if "영문" in output_type else "ko"
    question = PROMPTS.get(output_type) or sys.exit(f"알 수 없는 출력유형: {{output_type}} ({{', '.join(PROMPTS)}})")
    prompt = ais_text(load_rows(args[1]), lang) + "\\n\\n" + question
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, "image.png")
        square_crop(args[0], image)
        if server:
            ask_server(server, image, prompt)
            return
        cli = os.environ.get("LLAMA_MTMD_CLI", "llama-mtmd-cli")
        subprocess.run([cli, "-m", MODEL, "--mmproj", MMPROJ, "--image", image,
                        "-p", "<__media__>\\n" + prompt, "--jinja", "--temp", "0",
                        "--repeat-penalty", "1.1", "-n", "512", "-c", "4096"], check=True)


if __name__ == "__main__":
    main()
'''

_VLM_RUN_SH = '''\
#!/usr/bin/env bash
# 타겟 디바이스에서 실행: llama.cpp(llama-mtmd-cli) 설치 + pip install pillow
#   ./run.sh <이미지> <AIS csv|json> [출력유형]
# 엣지 배포된 서버로 보낼 때: ./run.sh <이미지> <AIS csv|json> [출력유형] --server http://<디바이스>:<포트>
set -e
python3 inference.py "$@"
'''

# eva-vlm 출력 유형 → 지시문 (eva api/model_manager.py PROMPT_MAP 과 동일).
_EVA_PROMPTS = {
    "영문 해상상황묘사":
        "Based on the camera image and AIS data provided, describe the current maritime situation in detail.",
    "한글 해상상황묘사":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 현재 해상 상황을 상세히 묘사하시오.",
    "영문 항해조력메시지":
        "Based on the camera image and AIS data provided, provide navigational advice "
        "for the own vessel in accordance with COLREG rules.",
    "한글 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 COLREG 규칙에 따른 "
        "자선의 항해 조력 메시지를 제공하시오.",
    "간결 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 간결한 항해 조력 메시지를 제공하시오. "
        "속도 조치, 방향 조치, 적용 근거(COLREG 조항)를 포함하시오.",
}


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
        # SDS(eva-vlm): /model 이 아니라 커밋(LoRA 어댑터 + projector)에서 merge·mmproj 를 만든다.
        checkpoint_name = params.get("checkpoint_name")
        is_eva = bool(checkpoint_name)
        if is_eva and do_prune:
            raise RuntimeError("SDS(eva-vlm) 양자화는 프루닝을 지원하지 않습니다")

        if not is_eva and not _has_hf_weights(JF_MODEL_PATH):
            raise RuntimeError(
                f"no HF weights at {JF_MODEL_PATH} (merged 모델 필요 — LoRA 어댑터만 있으면 merge 후 재시도)")

        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        # 예측가능 /tmp 경로 대신 mkdtemp (심링크 레이스 방지).
        workdir = tempfile.mkdtemp(prefix=f"convert-{job_id}-")

        steps = ["convert-to-gguf", "quantize", "package"]
        if do_prune:
            steps = ["prune"] + steps
        if is_eva:
            steps = ["materialize"] + steps
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

        # 1') SDS(eva-vlm): base 에 LoRA merge → HF LLM, CLIP + projector → mmproj GGUF
        eva_meta = None
        if is_eva:
            if _check_cancel("materialize"):
                return
            import eva_vlm

            eva_meta = await asyncio.to_thread(
                eva_vlm.prepare, CHECKPOINTS_ROOT, checkpoint_name, workdir)
            model_src = eva_meta["llm_dir"]
            _progress("materialize (LoRA merge + mmproj)")

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
        # SDS: merged HF(≈15GB)는 f16 GGUF 로 옮겨졌다 — 양자화 전에 지워 scratch(/tmp) 피크를 낮춘다.
        if eva_meta:
            shutil.rmtree(eva_meta["llm_dir"], ignore_errors=True)

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
        # SDS(eva-vlm): 비전 인코더(mmproj)는 양자화하지 않고 f16 그대로 싣는다(용량 작고 정확도 민감).
        # 파일명 'mmproj-' 접두는 llama.cpp 관례 — 플랫폼은 metadata.model_file 로 본체를 고른다.
        mmproj_name = None
        if is_eva:
            mmproj_name = f"mmproj-{model_name}.f16.gguf"
            mmproj_out = os.path.join(JF_OUTPUT_PATH, mmproj_name)
            if os.path.commonpath([os.path.realpath(mmproj_out), out_real]) != out_real:
                raise RuntimeError(f"mmproj path escapes output dir: {mmproj_name!r}")
            shutil.copy2(eva_meta["mmproj_path"], mmproj_out)
            with open(os.path.join(JF_OUTPUT_PATH, "inference.py"), "w", encoding="utf-8") as f:
                f.write(_VLM_INFERENCE_PY.format(
                    model_path=json.dumps(gguf_name), mmproj_path=json.dumps(mmproj_name),
                    prompts=json.dumps(_EVA_PROMPTS, ensure_ascii=False, indent=4),
                    default_type=json.dumps("한글 항해조력메시지", ensure_ascii=False)))
            with open(os.path.join(JF_OUTPUT_PATH, "run.sh"), "w", encoding="utf-8") as f:
                f.write(_VLM_RUN_SH)
        else:
            with open(os.path.join(JF_OUTPUT_PATH, "inference.py"), "w", encoding="utf-8") as f:
                f.write(_INFERENCE_PY.format(model_path=json.dumps(gguf_name)))
            with open(os.path.join(JF_OUTPUT_PATH, "run.sh"), "w", encoding="utf-8") as f:
                f.write(_RUN_SH)
        config = {"model_file": gguf_name, "quantization": qtype, "n_ctx": 2048,
                  "source_model": model_name, "pruned": do_prune}
        if is_eva:
            config.update({"mmproj_file": mmproj_name, "n_ctx": 4096,
                           "image_preprocess": "center-crop to square",
                           "generation": {"temperature": 0, "repeat_penalty": 1.1, "max_new_tokens": 512}})
        with open(os.path.join(JF_OUTPUT_PATH, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        files = [gguf_name] + ([mmproj_name] if mmproj_name else []) + \
            ["inference.py", "run.sh", "config.json", "metadata.json"]
        metadata = {
            "name": NAME, "version": VERSION, "job_id": job_id, "item_id": JF_ITEM_ID,
            "target_quant": target_quant, "quantize_type": qtype, "gguf_bytes": gguf_bytes,
            "pruned": do_prune, "prune_sparsity": sparsity if do_prune else None,
            "model_file": gguf_name, "files": files,
        }
        if is_eva:
            metadata.update({
                "source_format": "eva-vlm", "mmproj_file": mmproj_name,
                "checkpoint": eva_meta["checkpoint"], "lora_merged": eva_meta["lora_merged"],
                "base_llm": eva_meta["llm_repo"], "vision_model": eva_meta["vision_repo"],
            })
        with open(os.path.join(JF_OUTPUT_PATH, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        _progress("write package")

        j["result"] = {
            "gguf_file": gguf_name,
            "gguf_bytes": gguf_bytes,
            "target_quant": target_quant,
            "quantize_type": qtype,
            "pruned": do_prune,
            "mmproj_file": mmproj_name,
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
