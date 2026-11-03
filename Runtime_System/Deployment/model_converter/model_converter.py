#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
model_converter.py — HuggingFace LLM 가중치 포맷 변환기

지원 모델: Qwen, Llama, SmolLM, Gemma 등 (HF 포맷 기준)

입력 포맷:
  - "pytorch"     : HF 포맷 디렉토리, 가중치가 .pth / .bin
  - "safetensors" : HF 포맷 디렉토리, 가중치가 .safetensors

출력 포맷:
  - "pytorch"     : .bin(state_dict) 으로 변환
  - "safetensors" : .safetensors 로 변환
  - "gguf"        : llama.cpp 의 convert_hf_to_gguf.py 로 변환 (단일 .gguf)
  - "onnx"        : optimum 으로 변환(LLM 등). CLIP 은 비전 인코더(vision tower)만 torch.onnx 로 export.

변환 규칙:
  - 입력 == 출력           : 해당 포맷 실행에 필요한 파일만 선택 복사
                             (다른 프레임워크 가중치·문서/메타 파일 제외, 샤딩 인덱스는 유지)
  - pytorch 입력           : safetensors / onnx 출력 지원, gguf 는 미지원 안내
  - safetensors 입력       : pytorch / gguf / onnx 모두 지원
  - 가중치 외 동반 파일(config, generation_config, 토크나이저, vocab,
    preprocessor_config 등)은 복사. 단, 다른 프레임워크 가중치(.h5/.msgpack)와
    샤딩 인덱스(*.index.json)는 복사 대상에서 제외.

사용 예:
  python model_converter.py -if safetensors -i ./qwen-hf -of pytorch    -o ./qwen-pt
  python model_converter.py -if pytorch     -i ./llama-bin -of safetensors -o ./llama-st
  python model_converter.py -if safetensors -i ./smollm  -of gguf   -o ./smollm-gguf --llama-cpp-dir ~/llama.cpp
  python model_converter.py -if safetensors -i ./gemma   -of onnx   -o ./gemma-onnx
  # onnx task 기본값은 auto — config.json 의 architectures 로 자동 추론(LLM=text-generation 등)
  python model_converter.py -if pytorch -i ./clip-vit-base-patch32 -of onnx -o ./clip-onnx
  #   ↑ CLIP 자동 감지 → 비전 인코더(vision tower)만 ONNX export + 이미지 기반 수치 검증
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

VALID_FORMATS = ("pytorch", "safetensors", "gguf", "onnx")
INPUT_FORMATS = ("pytorch", "safetensors")   # 입력으로 받을 수 있는 포맷

# 복사에서 제외할 파일 패턴
WEIGHT_PATTERNS = ("*.safetensors", "*.bin", "*.pth", "*.pt", "*.h5", "*.msgpack")
INDEX_PATTERNS = ("*.index.json",)  # model.safetensors.index.json, pytorch_model.bin.index.json

# 입력==출력(동일 포맷 복사) 시, 해당 포맷 '실행'에 꼭 필요한 동반 파일 화이트리스트.
# 모델 패밀리(Qwen/Llama/SmolLM/Gemma 등)별 토크나이저 구성 차이를 폭넓게 커버한다.
ESSENTIAL_COMPANION_PATTERNS = (
    "config.json",                 # 모델 구조 (필수)
    "generation_config.json",      # 생성 기본값(eos 등)
    "tokenizer.json",              # fast 토크나이저 본체
    "tokenizer_config.json",       # 토크나이저 로드 설정 + chat template
    "special_tokens_map.json",     # 특수 토큰 매핑
    "added_tokens.json",           # 추가 토큰(일부 모델)
    "vocab.json", "vocab.txt",     # BPE/WordPiece 어휘
    "merges.txt",                  # BPE 병합 규칙
    "*.model",                     # SentencePiece (tokenizer.model, spiece.model 등)
    "preprocessor_config.json",    # 이미지/오디오 전처리 (CLIP 등 멀티모달)
    "processor_config.json",       # 멀티모달 프로세서
    "image_processor_config.json", # 이미지 프로세서(분리형)
    "video_preprocessor_config.json",  # 비디오 전처리 (Qwen-VL 등)
    "chat_template.json",          # 분리 저장된 chat template(최신 모델)
    "chat_template.jinja",
    # ── 양자화 메타데이터 ────────────────────────────────────────────
    #   이게 빠지면 런타임이 '양자화된 체크포인트'임을 알지 못해
    #   로드에 실패하거나 조용히 잘못된 값으로 읽는다.
    "quantize_config.json",        # GPTQ(gptqmodel) / 본 파이프라인 RTN
    "quantization_config.json",    # 일부 도구가 쓰는 변형 이름
    "quant_config.json",           # AWQ 계열 변형
    "hf_quant_config.json",        # NVIDIA ModelOpt (fp8 / nvfp4)
    # ── 파이프라인 자체 기록 ─────────────────────────────────────────
    #   실행에 필수는 아니지만, 산출물만 보고 어떤 처리를 거쳤는지
    #   추적할 수 있어야 하므로 함께 옮긴다.
    "pruning_config.json",
    "pruning_report.json",
)

# 동일 포맷 복사 시 유지할 가중치/인덱스 패턴 (해당 포맷 그대로 보존, 샤딩 인덱스 포함)
FORMAT_WEIGHT_KEEP = {
    "safetensors": ("*.safetensors",),
    "pytorch": ("*.bin", "*.pth", "*.pt"),
}
FORMAT_INDEX_KEEP = {
    "safetensors": ("model.safetensors.index.json",),
    "pytorch": ("pytorch_model.bin.index.json",),
}


# --------------------------------------------------------------------------- #
# 동반 파일 처리
# --------------------------------------------------------------------------- #
def _matches(name: str, patterns) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(name, p) for p in patterns)


def copy_companion_files(src_dir: Path, dst_dir: Path) -> list[str]:
    """가중치 파일과 샤딩 인덱스를 제외한 모든 동반 파일을 복사(변환 경로용).
    config.json, generation_config.json, tokenizer*.json, vocab.json,
    merges.txt, special_tokens_map.json, preprocessor_config.json,
    tokenizer.model 등이 자동으로 따라온다."""
    copied = []
    for entry in sorted(src_dir.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if _matches(name, WEIGHT_PATTERNS):
            continue  # 가중치는 변환 경로로만 산출 폴더에 들어간다
        if _matches(name, INDEX_PATTERNS):
            continue  # 샤딩 인덱스는 변환 후 무의미하므로 제외
        shutil.copy2(entry, dst_dir / name)
        copied.append(name)
    return copied


# --------------------------------------------------------------------------- #
# 가중치 로드 / 저장
# --------------------------------------------------------------------------- #
def _unwrap_state_dict(sd):
    """{"state_dict": {...}} / {"model": {...}} 래핑을 벗긴다."""
    if isinstance(sd, dict):
        if "state_dict" in sd and isinstance(sd["state_dict"], dict):
            return sd["state_dict"]
        if "model" in sd and isinstance(sd["model"], dict):
            return sd["model"]
    return sd


def load_pytorch_weights(src_dir: Path) -> dict:
    """src 폴더의 .bin / .pth 가중치를 모두 읽어 하나의 state_dict 로 병합."""
    import torch
    files = sorted(glob.glob(str(src_dir / "*.bin")) + glob.glob(str(src_dir / "*.pth")))
    if not files:
        raise FileNotFoundError(f"{src_dir} 에서 .bin / .pth 가중치를 찾지 못했습니다.")
    sd = {}
    for f in files:
        part = torch.load(f, map_location="cpu", weights_only=True)
        part = _unwrap_state_dict(part)
        sd.update(part)
    print(f"  로드: {len(files)}개 파일, 텐서 {len(sd)}개", file=sys.stderr)
    return sd


def load_safetensors_weights(src_dir: Path) -> dict:
    """src 폴더의 .safetensors 가중치를 모두 읽어 하나의 state_dict 로 병합."""
    from safetensors.torch import load_file
    files = sorted(glob.glob(str(src_dir / "*.safetensors")))
    if not files:
        raise FileNotFoundError(f"{src_dir} 에서 .safetensors 가중치를 찾지 못했습니다.")
    sd = {}
    for f in files:
        sd.update(load_file(f))
    print(f"  로드: {len(files)}개 파일, 텐서 {len(sd)}개", file=sys.stderr)
    return sd


def save_pytorch_weights(sd: dict, dst_dir: Path):
    """state_dict 를 pytorch_model.bin 으로 저장 (.bin 과 .pth 는 내용 동일).
    safetensors → pytorch 는 텐서 공유 제약이 없어 그대로 저장하면 된다."""
    import torch
    out = dst_dir / "pytorch_model.bin"
    torch.save(sd, out)
    print(f"  저장: {out.name} ({out.stat().st_size/1e6:.0f} MB)", file=sys.stderr)


def save_safetensors_weights(sd: dict, dst_dir: Path):
    """state_dict 를 model.safetensors 로 저장.
    safetensors 는 스토리지 공유(tied weights)·비연속 텐서를 허용하지 않으므로
    clone + contiguous 로 분리한다(추론 시 동등, config 로 재-tie 됨)."""
    from safetensors.torch import save_file
    clean = {k: v.detach().cpu().clone().contiguous() for k, v in sd.items()}
    out = dst_dir / "model.safetensors"
    save_file(clean, str(out), metadata={"format": "pt"})
    print(f"  저장: {out.name} ({out.stat().st_size/1e6:.0f} MB)", file=sys.stderr)


# --------------------------------------------------------------------------- #
# 변환 경로
# --------------------------------------------------------------------------- #
def convert_weights(src_dir, dst_dir, in_fmt, out_fmt):
    """pytorch ↔ safetensors 가중치 변환 + 동반 파일 복사."""
    print(f"[변환] {in_fmt} → {out_fmt} (가중치 재직렬화)", file=sys.stderr)

    if in_fmt == "pytorch":
        sd = load_pytorch_weights(src_dir)
    else:
        sd = load_safetensors_weights(src_dir)

    if out_fmt == "safetensors":
        save_safetensors_weights(sd, dst_dir)
    else:  # pytorch
        save_pytorch_weights(sd, dst_dir)

    copied = copy_companion_files(src_dir, dst_dir)
    print(f"[복사] 동반 파일 {len(copied)}개: {', '.join(copied)}", file=sys.stderr)


def _find_gguf_script(llama_cpp_dir):
    """convert_hf_to_gguf.py 를 탐색한다.
    우선순위:
      ① --llama-cpp-dir(인자)
      ② 환경변수 LLAMA_CPP_DIR
      ③ (기본값) 이 프로그램과 같은 위치의 'llama.cpp' 폴더  ← 인자가 없으면 여기를 본다
      ④ 이 프로그램과 같은 폴더(스크립트를 직접 복사해 둔 경우)
    못 찾으면 None."""
    here = Path(__file__).resolve().parent
    candidates = []
    if llama_cpp_dir:
        candidates.append(Path(llama_cpp_dir))
    env_dir = os.environ.get("LLAMA_CPP_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(here / "llama.cpp")  # 기본값: 코드 옆 'llama.cpp' 폴더
    candidates.append(here)                # 폴백: 스크립트를 직접 옆에 둔 경우

    for d in candidates:
        cand = d / "convert_hf_to_gguf.py"
        if cand.exists():
            print(f"[gguf] 변환 스크립트: {cand}", file=sys.stderr)
            return cand
    return None


def convert_to_gguf(src_dir, dst_dir, llama_cpp_dir, outtype):
    """safetensors HF 디렉토리 → 단일 .gguf (llama.cpp convert_hf_to_gguf.py 사용).
    GGUF 는 토크나이저·메타데이터를 내부에 담으므로 동반 파일 복사가 필요 없다."""
    print(f"[변환] safetensors → gguf (outtype={outtype})", file=sys.stderr)

    # llama.cpp convert_hf_to_gguf.py 는 생성형 LLM(ModelType.TEXT)과 일부 멀티모달
    # 프로젝터(mmproj)만 지원한다. 단독 CLIP(CLIPModel)은 지원 아키텍처가 아니므로 미리 막는다.
    if _is_clip(src_dir):
        raise RuntimeError(
            "CLIP(CLIPModel)은 llama.cpp GGUF 변환 대상이 아닙니다.\n"
            "  convert_hf_to_gguf.py 는 생성형 LLM 과 일부 멀티모달 프로젝터(mmproj)만 지원합니다.\n"
            "  - 단독 비전 인코더는 GGUF 대신 ONNX/safetensors 로 두세요 (이 스크립트의 -of onnx).\n"
            "  - LLaVA 류 멀티모달의 비전 타워를 GGUF(mmproj)로 만들려면, 지원되는 VLM 전체를 대상으로\n"
            "    'python convert_hf_to_gguf.py <vlm_dir> --mmproj' 또는 tools/mtmd 의 llava 도구를 쓰세요."
        )

    script = _find_gguf_script(llama_cpp_dir)
    if script is None:
        raise RuntimeError(
            "convert_hf_to_gguf.py 를 찾지 못했습니다.\n"
            "  탐색 위치: --llama-cpp-dir 인자 → 환경변수 LLAMA_CPP_DIR → "
            "코드 옆 'llama.cpp' 폴더(기본값) → 코드와 같은 폴더\n"
            "  방법1) llama.cpp 저장소를 통째로 두고 경로 지정(권장):\n"
            "      git clone https://github.com/ggml-org/llama.cpp\n"
            "      pip install -r llama.cpp/requirements.txt\n"
            "      ... --llama-cpp-dir ./llama.cpp\n"
            "  방법2) 스크립트를 이 프로그램과 같은 폴더에 복사 + gguf 모듈 설치:\n"
            "      pip install gguf"
        )

    out_file = dst_dir / "model.gguf"
    cmd = [sys.executable, str(script), str(src_dir),
           "--outfile", str(out_file), "--outtype", outtype]
    print(f"[실행] {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_file.exists():
        sys.stderr.write((result.stdout or "") + "\n" + (result.stderr or "") + "\n")
        combined = (result.stdout or "") + (result.stderr or "")
        hint = ""
        if "No module named 'gguf'" in (result.stderr or ""):
            hint = ("\n  원인: convert_hf_to_gguf.py 가 의존하는 'gguf' 모듈이 없습니다.\n"
                    "  파일만 복사해 쓰는 경우 'pip install gguf' 로 설치하거나,\n"
                    "  llama.cpp 저장소를 통째로 두고 --llama-cpp-dir 로 지정하세요.")
        elif "is not supported" in combined:
            hint = ("\n  원인: 이 모델 아키텍처는 llama.cpp(convert_hf_to_gguf.py)가 지원하지 않습니다.\n"
                    "  지원 목록 확인: python convert_hf_to_gguf.py --print-supported-models\n"
                    "  비전/멀티모달이면 --mmproj 경로가 필요할 수 있습니다(단독 CLIP 은 미지원).")
        raise RuntimeError("GGUF 변환에 실패했습니다. 위 로그를 확인하세요." + hint)
    print(f"[완료] {out_file}", file=sys.stderr)


def verify_onnx(src_dir: Path, dst_dir: Path, atol: float, prompt: str):
    """변환된 ONNX 와 PyTorch 원본의 출력을 비교해 수치 동등성을 검증.
    오차가 허용치(atol)를 넘으면 RuntimeError 로 실패시킨다.
    검증 의존성이 없으면 경고만 남기고 건너뛴다(변환 자체는 성공)."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from optimum.onnxruntime import ORTModelForCausalLM
    except Exception as e:
        print(f"[onnx-검증] 건너뜀: 검증 의존성 부족 ({e})", file=sys.stderr)
        print("  검증하려면: pip install 'optimum-onnx[onnxruntime]'", file=sys.stderr)
        return None

    print(f"[onnx-검증] PyTorch vs ONNX 출력 비교 (prompt={prompt!r}, atol={atol:.1e})",
          file=sys.stderr)

    tok = AutoTokenizer.from_pretrained(str(src_dir))
    inputs = tok(prompt, return_tensors="pt")

    # 원본(PyTorch) logits — fp32 로 비교해 dtype 차이를 배제
    ref = AutoModelForCausalLM.from_pretrained(str(src_dir), torch_dtype=torch.float32).eval()
    with torch.no_grad():
        ref_logits = ref(**inputs).logits.float()

    # 변환된 ONNX logits.
    # text-generation(no-past) 로 export 한 그래프는 KV 캐시(past_key_values)가 없다.
    # config.json 의 use_cache=True 를 그대로 따르면 'pkv 캐시' 를 요구하다가 ValueError 가 나므로,
    # use_cache=False 로 명시해 로드한다(검증은 단일 forward 의 logits 비교만 하므로 캐시 불필요).
    ort_model = ORTModelForCausalLM.from_pretrained(str(dst_dir), use_cache=False)
    ort_logits = torch.as_tensor(ort_model(**inputs).logits).float()

    if ort_logits.shape != ref_logits.shape:
        raise RuntimeError(
            f"ONNX 검증 실패: logits shape 불일치 "
            f"(ONNX {tuple(ort_logits.shape)} vs PyTorch {tuple(ref_logits.shape)}). "
            "동적 축이 잘못 잡혔거나 그래프가 고정 형태로 박제됐을 수 있습니다."
        )

    max_err = (ort_logits - ref_logits).abs().max().item()
    same_argmax = bool((ort_logits[:, -1].argmax(-1) == ref_logits[:, -1].argmax(-1)).all())
    print(f"[onnx-검증] max_abs_err={max_err:.3e}, next-token argmax 일치={same_argmax}",
          file=sys.stderr)

    if max_err > atol or not same_argmax:
        raise RuntimeError(
            f"ONNX 검증 실패: 최대 오차 {max_err:.3e} (허용치 {atol:.1e}), "
            f"next-token 일치={same_argmax}.\n"
            "  변환 그래프가 원본과 수치적으로 다릅니다 "
            "(dtype 캐스팅 / 연산 순서 / 동적 흐름 박제 / 미지원 op 근사 등).\n"
            "  --onnx-atol 로 허용치를 조정하거나 export 설정(opset, dtype)을 점검하세요."
        )
    print("[onnx-검증] PASS — 원본과 수치적으로 동등", file=sys.stderr)
    return max_err


# --------------------------------------------------------------------------- #
# ONNX: task 자동 추론 (config.json 기반)
# --------------------------------------------------------------------------- #
def _read_config(src_dir) -> dict:
    """src 폴더의 config.json 을 읽어 dict 로 반환(없거나 깨지면 {})."""
    import json
    p = Path(src_dir) / "config.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _weights_total_bytes(src_dir) -> int:
    """src 폴더의 가중치 파일 총 바이트 수(대형 모델 판별용)."""
    total = 0
    for pat in ("*.safetensors", "*.bin", "*.pth", "*.pt"):
        for f in glob.glob(str(Path(src_dir) / pat)):
            try:
                total += os.path.getsize(f)
            except OSError:
                pass
    return total


def _is_clip(src_dir) -> bool:
    """config.json 으로 CLIP 계열인지 판별."""
    cfg = _read_config(src_dir)
    model_type = (cfg.get("model_type") or "").lower()
    archs = " ".join(cfg.get("architectures") or [])
    return model_type == "clip" or "CLIP" in archs


# 아키텍처 접미사 → optimum onnx task 매핑(대표 패밀리)
_ARCH_SUFFIX_TASK = (
    ("ForCausalLM", "text-generation"),
    ("ForConditionalGeneration", "text2text-generation"),
    ("ForSequenceClassification", "text-classification"),
    ("ForTokenClassification", "token-classification"),
    ("ForQuestionAnswering", "question-answering"),
    ("ForMaskedLM", "fill-mask"),
    ("ForImageClassification", "image-classification"),
)


def infer_onnx_task(src_dir) -> str:
    """config.json 의 architectures 로 optimum ONNX task 를 자동 추론.
    추론 실패 시 RuntimeError 로 --onnx-task 직접 지정을 유도한다."""
    cfg = _read_config(src_dir)
    archs = cfg.get("architectures") or []
    for arch in archs:
        for suffix, task in _ARCH_SUFFIX_TASK:
            if arch.endswith(suffix):
                print(f"[onnx-task] 자동 추론: architectures={archs} → task={task}",
                      file=sys.stderr)
                return task
    model_type = cfg.get("model_type")
    raise RuntimeError(
        f"config.json 에서 ONNX task 를 자동 추론하지 못했습니다 "
        f"(architectures={archs}, model_type={model_type!r}).\n"
        "  --onnx-task 로 직접 지정하세요 (예: text-generation, text2text-generation, "
        "feature-extraction, image-classification 등)."
    )


# --------------------------------------------------------------------------- #
# ONNX: CLIP 비전 인코더(vision tower) 전용 export + 이미지 기반 검증
# --------------------------------------------------------------------------- #
def verify_clip_vision_onnx(model, image_processor, onnx_path, image_size, atol):
    """합성 이미지를 image processor 로 전처리해 PyTorch vs ONNX(onnxruntime) 의
    image_embeds 출력을 비교한다. 의존성이 없으면 경고만 남기고 건너뛴다."""
    try:
        import numpy as np
        import torch
        from PIL import Image
        import onnxruntime as ort
    except Exception as e:
        print(f"[onnx-검증] 건너뜀: 검증 의존성 부족 ({e})", file=sys.stderr)
        print("  검증하려면: pip install onnxruntime pillow", file=sys.stderr)
        return None

    print(f"[onnx-검증] CLIP vision: PyTorch vs ONNX 비교 (atol={atol:.1e})", file=sys.stderr)

    # 합성 RGB 이미지 → image processor → pixel_values (모델 입력 크기로 리사이즈됨)
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 256, (image_size, image_size, 3), dtype=np.uint8))
    pixel_values = image_processor(images=img, return_tensors="pt")["pixel_values"].float()

    with torch.no_grad():
        ref_embeds = model(pixel_values=pixel_values).image_embeds.float().cpu().numpy()

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_embeds = sess.run(["image_embeds"],
                           {"pixel_values": pixel_values.cpu().numpy()})[0]

    if onnx_embeds.shape != ref_embeds.shape:
        raise RuntimeError(
            f"ONNX 검증 실패: image_embeds shape 불일치 "
            f"(ONNX {onnx_embeds.shape} vs PyTorch {ref_embeds.shape})."
        )

    max_err = float(np.abs(onnx_embeds - ref_embeds).max())
    print(f"[onnx-검증] image_embeds max_abs_err={max_err:.3e} (허용치 {atol:.1e})",
          file=sys.stderr)
    if max_err > atol:
        raise RuntimeError(
            f"ONNX 검증 실패: 최대 오차 {max_err:.3e} > 허용치 {atol:.1e}.\n"
            "  --onnx-atol 로 허용치를 조정하거나 opset/dtype 을 점검하세요."
        )
    print("[onnx-검증] PASS — 원본과 수치적으로 동등", file=sys.stderr)
    return max_err


def convert_clip_vision_to_onnx(src_dir, dst_dir, verify=True, atol=1e-3, opset=17):
    """CLIP 비전 인코더(vision tower)만 ONNX 로 export + 이미지 기반 수치 검증.
    LLaVA 류 파이프라인이 필요로 하는 건 비전 타워 출력(image_embeds / last_hidden_state)이므로
    전체 CLIP(텍스트 타워 포함) 대신 CLIPVisionModelWithProjection 만 떼어 export 한다.
    SDPA 추적 이슈를 피하려고 eager attention 으로 로드한다."""
    import torch
    from transformers import CLIPVisionModelWithProjection, AutoImageProcessor

    print("[변환] → onnx (CLIP vision tower, torch.onnx)", file=sys.stderr)

    model = CLIPVisionModelWithProjection.from_pretrained(
        str(src_dir), attn_implementation="eager", torch_dtype=torch.float32
    ).eval()
    image_processor = AutoImageProcessor.from_pretrained(str(src_dir))
    image_size = int(getattr(model.config, "image_size", 224))

    # torch.onnx.export 출력 순서를 (image_embeds, last_hidden_state) 로 고정하는 래퍼
    class VisionWrap(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            o = self.m(pixel_values=pixel_values)
            return o.image_embeds, o.last_hidden_state

    wrapped = VisionWrap(model).eval()
    dummy = torch.randn(1, 3, image_size, image_size, dtype=torch.float32)

    out_file = dst_dir / "model.onnx"
    export_kwargs = dict(
        input_names=["pixel_values"],
        output_names=["image_embeds", "last_hidden_state"],
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "image_embeds": {0: "batch"},
            "last_hidden_state": {0: "batch"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )
    # 최신 torch(2.9+)는 dynamo 익스포터가 기본이고 'onnxscript' 의존성이 필요하다.
    # 추가 설치 없이 동작하도록 레거시 TorchScript 익스포터(dynamo=False)를 명시한다.
    # (구버전 torch 는 dynamo 인자를 모르므로 TypeError 시 인자 없이 폴백)
    try:
        torch.onnx.export(wrapped, (dummy,), str(out_file), dynamo=False, **export_kwargs)
    except TypeError:
        torch.onnx.export(wrapped, (dummy,), str(out_file), **export_kwargs)
    print(f"[완료] {out_file}", file=sys.stderr)

    # 전처리기/config 등 동반 파일 복사(가중치·인덱스 제외)
    copied = copy_companion_files(src_dir, dst_dir)
    print(f"[복사] 동반 파일 {len(copied)}개: {', '.join(copied)}", file=sys.stderr)

    if verify:
        verify_clip_vision_onnx(model, image_processor, out_file, image_size, atol)
    else:
        print("[onnx-검증] --no-verify-onnx 로 검증 생략", file=sys.stderr)


# --------------------------------------------------------------------------- #
# ONNX: 입력 모델에 따라 적절한 export 경로로 라우팅
# --------------------------------------------------------------------------- #
def run_onnx_export(src_dir, dst_dir, onnx_task="auto", verify=True,
                    atol=1e-3, prompt="Hello, world!", opset=17,
                    no_post_process=False):
    """ONNX export 디스패처.
      - CLIP + task=auto         → 비전 인코더 전용 torch.onnx 경로(+이미지 검증)
      - 그 외 task=auto           → config.json 으로 task 자동 추론 후 optimum-cli
      - task 명시(예: feature-extraction) → optimum-cli 로 그대로 export
        (CLIP 전체를 optimum 으로 뽑고 싶으면 --onnx-task feature-extraction 사용)"""
    if onnx_task == "auto" and _is_clip(src_dir):
        convert_clip_vision_to_onnx(src_dir, dst_dir, verify=verify, atol=atol, opset=opset)
        return
    task = infer_onnx_task(src_dir) if onnx_task == "auto" else onnx_task
    convert_to_onnx(src_dir, dst_dir, task=task, verify=verify, atol=atol,
                    prompt=prompt, no_post_process=no_post_process)


def convert_to_onnx(src_dir, dst_dir, task="text-generation",
                    verify=True, atol=1e-3, prompt="Hello, world!",
                    no_post_process=False):
    """safetensors/pytorch HF 디렉토리 → ONNX (optimum-cli 사용) + 수치 검증.
    optimum 이 토크나이저·config 복사와 dynamic axes 설정을 함께 처리한다.

    주의:
      - optimum 2.x 부터 ONNX export 는 별도 패키지 'optimum-onnx' 로 분리되었다.
        백엔드가 없으면 'optimum-cli export onnx' 서브커맨드 자체가 등록되지 않아
        'unrecognized arguments: onnx ...' 로 실패한다.
      - 로컬 디렉토리는 task 자동 추론이 안 되므로 --task 를 반드시 넘긴다.
        LLM 은 text-generation(검증 용이) / text-generation-with-past(배포 효율)."""
    print("[변환] → onnx (optimum)", file=sys.stderr)

    exe = shutil.which("optimum-cli")
    if exe is None:
        raise RuntimeError(
            "optimum-cli 를 찾지 못했습니다.\n"
            "  설치: pip install 'optimum-onnx[onnxruntime]'"
        )

    # onnx 익스포터 백엔드(optimum-onnx)가 등록됐는지 실제로 확인한다.
    # optimum-cli 바이너리는 기본 optimum 만 깔려도 존재하므로 which() 만으로는 부족하다.
    probe = subprocess.run([exe, "export", "onnx", "--help"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        raise RuntimeError(
            "optimum 의 ONNX 익스포터 백엔드를 찾지 못했습니다.\n"
            "  optimum 2.x 부터 ONNX export 는 별도 패키지로 분리되었습니다.\n"
            "  설치: pip install 'optimum-onnx[onnxruntime]'  (GPU 는 [onnxruntime-gpu])"
        )

    cmd = [exe, "export", "onnx", "--task", task,
           "--model", str(src_dir), str(dst_dir)]

    # ONNX(protobuf)는 단일 메시지 2GB 한계가 있다. 대형 모델은 optimum 후처리
    # (tied-weight 중복 제거)의 직렬화에서 'Failed to serialize proto' 로 실패한다.
    # 가중치 합이 임계치를 넘거나 옵션 지정 시 --no-post-process 로 후처리를 생략한다
    # (중복 제거 최적화만 빠질 뿐 추론 정확도와는 무관).
    effective_npp = no_post_process or (_weights_total_bytes(src_dir) > 1_700_000_000)
    if effective_npp:
        cmd.append("--no-post-process")
        print("[onnx] 대형 모델 감지 또는 옵션 지정 → --no-post-process 적용 "
              "(tied-weight 중복 제거 생략, 2GB proto 한계 회피)", file=sys.stderr)

    print(f"[실행] {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        extra = "" if effective_npp else (
            "\n  대형 모델(>2GB)의 후처리(proto 2GB 한계)에서 막혔을 수 있습니다 — "
            "--onnx-no-post-process 로 다시 시도하세요.")
        raise RuntimeError("ONNX 변환에 실패했습니다. 위 로그를 확인하세요." + extra)
    print(f"[완료] {dst_dir}", file=sys.stderr)

    # 변환 성공만으로는 '조용히 틀어진' 케이스를 못 잡으므로 수치 검증 수행.
    # 단, 이 스크립트의 검증은 causal-LM 전용(AutoModelForCausalLM/ORTModelForCausalLM)이므로
    # text-generation 계열 task 에만 적용한다. CLIP(feature-extraction) 등 비-LLM 은
    # export 중 optimum 이 수행한 자체 수치 검증으로 갈음한다.
    if not verify:
        print("[onnx-검증] --no-verify-onnx 로 검증 생략", file=sys.stderr)
    elif task.startswith("text-generation"):
        verify_onnx(src_dir, dst_dir, atol=atol, prompt=prompt)
    else:
        print(f"[onnx-검증] task={task} 는 causal-LM 검증 대상이 아니라 건너뜁니다.\n"
              "  (export 중 optimum 이 자체 수치 검증을 이미 수행했습니다 — "
              "위 'Validating ONNX model' 로그 참고)", file=sys.stderr)


def copy_same_format(src_dir, dst_dir, fmt):
    """입력 == 출력 : 해당 포맷 실행에 꼭 필요한 파일만 선택 복사.

    유지: 해당 포맷 가중치(+ 샤딩 인덱스) + 필수 동반 파일(config/토크나이저/생성설정/전처리기 등)
    제외: 다른 프레임워크 가중치(.bin/.h5/.msgpack 등)와 그 인덱스,
          README/.gitattributes/LICENSE 등 실행에 불필요한 파일, 하위 폴더."""
    print(f"[복사] 입력==출력({fmt}) — 실행 필수 파일만 선택 복사", file=sys.stderr)

    keep_weights = FORMAT_WEIGHT_KEEP.get(fmt, ())
    keep_index = FORMAT_INDEX_KEEP.get(fmt, ())

    copied, skipped = [], []
    for entry in sorted(src_dir.iterdir()):
        if not entry.is_file():
            skipped.append(entry.name + "/")  # 하위 폴더는 복사하지 않음
            continue
        name = entry.name
        keep = (_matches(name, keep_weights)
                or _matches(name, keep_index)
                or _matches(name, ESSENTIAL_COMPANION_PATTERNS))
        if keep:
            shutil.copy2(entry, dst_dir / name)
            copied.append(name)
        else:
            skipped.append(name)

    print(f"[복사] 유지 {len(copied)}개: {', '.join(copied)}", file=sys.stderr)
    if skipped:
        print(f"[복사] 제외 {len(skipped)}개: {', '.join(skipped)}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# 공개 API — 다른 프로그램에서 import 해서 호출
# --------------------------------------------------------------------------- #
def convert_model(input_format, input_dir, output_format, output_dir,
                  llama_cpp_dir=None, gguf_outtype="f16",
                  verify_onnx_flag=True, onnx_atol=1e-3,
                  verify_prompt="Hello, world!", onnx_task="auto", onnx_opset=17,
                  onnx_no_post_process=False):
    """모델 포맷을 변환하는 공개 함수.

    필수 인자:
        input_format  : 입력 포맷 ("pytorch" | "safetensors")
        input_dir     : 입력 모델 폴더 경로
        output_format : 출력 포맷 ("pytorch" | "safetensors" | "gguf" | "onnx")
        output_dir    : 출력 모델 폴더 경로

    선택 인자(gguf/onnx 용, 미지정 시 기본값):
        llama_cpp_dir, gguf_outtype, verify_onnx_flag, onnx_atol, verify_prompt,
        onnx_task(기본 "auto"=config.json 기반 자동 추론, CLIP 은 비전 인코더 전용 export),
        onnx_opset(CLIP 비전 export 시 torch.onnx opset),
        onnx_no_post_process(대형 모델의 optimum 후처리 2GB proto 한계 회피; 대형이면 자동 적용)

    반환값:
        (a, b) 튜플.
          a = 0  / b = "success"      성공
          a = -1 / b = "<오류 메시지>"  실패
    """
    try:
        # ── 포맷 유효성 ──────────────────────────────────────────────
        if input_format not in ("pytorch", "safetensors"):
            return (-1, f"입력 포맷은 pytorch 또는 safetensors 여야 합니다 (받은 값: {input_format})")
        if output_format not in VALID_FORMATS:
            return (-1, f"알 수 없는 출력 포맷입니다: {output_format} "
                        f"(가능: {', '.join(VALID_FORMATS)})")

        src_dir = Path(input_dir)
        dst_dir = Path(output_dir)

        if not src_dir.is_dir():
            return (-1, f"모델 폴더를 찾을 수 없습니다: {src_dir}")

        # 입력과 출력이 같은 폴더면 복사가 자기 자신을 덮어쓰게 된다(SameFileError).
        if src_dir.resolve() == dst_dir.resolve():
            return (-1, f"입력과 출력 폴더가 같습니다: {src_dir.resolve()}. "
                        "다른 출력 폴더를 지정하세요.")

        dst_dir.mkdir(parents=True, exist_ok=True)

        # ── 입력 구성 점검(경고만) ──────────────────────────────────
        if input_format == "safetensors" and not glob.glob(str(src_dir / "*.safetensors")):
            print("경고: 입력 포맷이 safetensors 인데 .safetensors 파일이 없습니다.", file=sys.stderr)
        if input_format == "pytorch" and not (glob.glob(str(src_dir / "*.bin")) or
                                              glob.glob(str(src_dir / "*.pth"))):
            print("경고: 입력 포맷이 pytorch 인데 .bin/.pth 파일이 없습니다.", file=sys.stderr)

        # ── 1) 입력 == 출력 → 복사만 ────────────────────────────────
        if input_format == output_format:
            copy_same_format(src_dir, dst_dir, input_format)
            return (0, "success")

        # ── 2) pytorch 입력 → safetensors / onnx (gguf 미지원) ──────
        if input_format == "pytorch":
            if output_format == "safetensors":
                convert_weights(src_dir, dst_dir, input_format, output_format)
            elif output_format == "onnx":
                # CLIP 은 비전 인코더 전용 경로, 그 외는 optimum-cli.
                # from_pretrained / optimum 모두 .bin·.safetensors 를 직접 로드한다.
                run_onnx_export(src_dir, dst_dir, onnx_task=onnx_task,
                                verify=verify_onnx_flag, atol=onnx_atol,
                                prompt=verify_prompt, opset=onnx_opset,
                                no_post_process=onnx_no_post_process)
            else:  # gguf
                return (-1, "지원하지 않는 변환입니다: pytorch 입력은 'gguf' 출력을 지원하지 않습니다. "
                            "safetensors 또는 onnx 출력만 지원하며, gguf 가 필요하면 "
                            "먼저 safetensors 로 변환한 뒤 진행하세요.")
            return (0, "success")

        # ── 3) safetensors 입력 → pytorch / gguf / onnx ─────────────
        if input_format == "safetensors":
            if output_format == "pytorch":
                convert_weights(src_dir, dst_dir, input_format, output_format)
            elif output_format == "gguf":
                convert_to_gguf(src_dir, dst_dir, llama_cpp_dir, gguf_outtype)
            elif output_format == "onnx":
                run_onnx_export(src_dir, dst_dir, onnx_task=onnx_task,
                                verify=verify_onnx_flag, atol=onnx_atol,
                                prompt=verify_prompt, opset=onnx_opset,
                                no_post_process=onnx_no_post_process)
            return (0, "success")

        return (-1, f"처리할 수 없는 조합입니다: {input_format} → {output_format}")

    except Exception as e:
        # 변환 함수들이 던지는 예외(파일 없음, 변환 실패, ONNX 검증 실패 등)를
        # 모두 잡아 (-1, 메시지) 형태로 반환한다.
        return (-1, f"{type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="HuggingFace LLM 가중치 포맷 변환기 (pytorch/safetensors/gguf/onnx)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-if", "--input-format", required=True, choices=INPUT_FORMATS,
                        help="입력 포맷 (pytorch | safetensors)")
    parser.add_argument("-i", "--model-dir", required=True,
                        help="모델이 저장된 폴더")
    parser.add_argument("-of", "--output-format", required=True, choices=VALID_FORMATS,
                        help="출력 포맷 (pytorch | safetensors | gguf | onnx)")
    parser.add_argument("-o", "--output-dir", required=True,
                        help="출력 폴더")

    # gguf / onnx 보조 옵션
    parser.add_argument("--llama-cpp-dir", default=None,
                        help="(gguf) llama.cpp 저장소 경로. 미지정 시 환경변수 LLAMA_CPP_DIR → "
                             "코드 옆 'llama.cpp' 폴더(기본값) → 코드와 같은 폴더 순으로 "
                             "convert_hf_to_gguf.py 를 찾는다")
    parser.add_argument("--gguf-outtype", default="f16",
                        choices=["f32", "f16", "bf16", "q8_0", "auto"],
                        help="(gguf) 출력 dtype")

    # onnx 옵션
    parser.add_argument("--onnx-task", default="auto",
                        help="(onnx) export task. 기본 'auto' = config.json 의 architectures 로 "
                             "자동 추론(LLM=text-generation 등). CLIP 은 자동 감지되어 비전 인코더만 "
                             "export. 필요 시 직접 지정(text-generation-with-past, feature-extraction 등)")
    parser.add_argument("--onnx-opset", type=int, default=17,
                        help="(onnx) CLIP 비전 인코더 torch.onnx export 시 opset 버전")
    parser.add_argument("--onnx-no-post-process", action="store_true",
                        help="(onnx) optimum 후처리(tied-weight 중복 제거)를 생략. 대형 모델(>2GB)의 "
                             "proto 직렬화 실패 회피용. 가중치가 크면 자동으로도 적용됨")
    parser.add_argument("--no-verify-onnx", action="store_true",
                        help="(onnx) 변환 후 PyTorch 대비 수치 검증을 생략")
    parser.add_argument("--onnx-atol", type=float, default=1e-3,
                        help="(onnx) 검증 허용 최대 오차")
    parser.add_argument("--verify-prompt", default="Hello, world!",
                        help="(onnx) LLM 검증에 사용할 입력 텍스트")

    args = parser.parse_args()

    code, message = convert_model(
        input_format=args.input_format,
        input_dir=args.model_dir,
        output_format=args.output_format,
        output_dir=args.output_dir,
        llama_cpp_dir=args.llama_cpp_dir,
        gguf_outtype=args.gguf_outtype,
        verify_onnx_flag=not args.no_verify_onnx,
        onnx_atol=args.onnx_atol,
        verify_prompt=args.verify_prompt,
        onnx_task=args.onnx_task,
        onnx_opset=args.onnx_opset,
        onnx_no_post_process=args.onnx_no_post_process,
    )

    if code == 0:
        print(message)            # "success"
        sys.exit(0)
    else:
        print(f"오류: {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
