"""
test_sds.py — VisionLanguageModelV2 Inference (SDS 샘플 디렉토리 입력)

두 가지 데이터셋 포맷을 자동 감지하여 지원한다.

[구 포맷 — 20260227]
  sample_dir/
  ├── input_image.png       단일 이미지
  ├── input_data.csv        AIS (file_name 컬럼 없음)
  ├── output_describe_en.txt
  ├── output_describe_kor.txt
  ├── output_advice_en.txt
  ├── output_advice_kor.txt
  └── output_advice_compact.txt

[신 포맷 — 20251031]
  sample_dir/
  ├── frame_1.png ~ frame_N.png   프레임별 이미지
  ├── input.csv                   AIS (file_name, ship_type 컬럼 포함)
  └── output.csv                  (file_name, text) — 한글 단일 출력

Usage:
  # 구 포맷
  python test_sds.py \\
      --projector_path CKPT/projector.bin --lora_path CKPT \\
      --sample_dir .../20260227/tango_sds-... --lang ko --show_reference

  # 신 포맷 (프레임 지정, 기본값: 첫 번째 프레임)
  python test_sds.py \\
      --projector_path CKPT/projector.bin --lora_path CKPT \\
      --sample_dir .../20251031/dataset1 --frame frame_3 --show_reference

언어/시나리오 (--lang):
  en          영문 AIS + 영문 묘사/조력 프롬프트  (구 포맷 reference: EN)
  ko          한글 AIS + 한글 묘사/조력 프롬프트  (구 포맷 reference: KO)
  ko_compact  한글 AIS + 간결 항해조력 프롬프트   (구 포맷 reference: 간결)
  신 포맷은 --lang 이 AIS/프롬프트 언어만 제어하며 reference 는 항상 한글.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import glob
import torch
import pandas as pd
from PIL import Image

from model import VLMConfig, build_model


# ── 프롬프트 ──────────────────────────────────────────────────────────────────
PROMPT_EN = (
    "Based on the camera image and AIS data provided, "
    "describe the current maritime situation and provide "
    "appropriate navigational advice in accordance with COLREG rules."
)
PROMPT_KO = (
    "사진과 AIS 데이터를 바탕으로 현재 해상상황을 묘사하고 "
    "COLREG 규칙에 따른 올바른 항해 조력 메시지를 생성해줘."
)
PROMPT_COMPACT = (
    "사진과 AIS 데이터를 바탕으로 간결한 항해 조력 메시지를 생성해줘. "
    "속도 조치, 방향 조치, 적용 근거(COLREG 조항)를 포함하시오."
)

PROMPT_MAP = {"en": PROMPT_EN, "ko": PROMPT_KO, "ko_compact": PROMPT_COMPACT}
AIS_LANG   = {"en": "en", "ko": "ko", "ko_compact": "ko"}

# 구 포맷 ground-truth 파일 목록
OLD_REFERENCE_FILES = {
    "en":         ["output_describe_en.txt", "output_advice_en.txt"],
    "ko":         ["output_describe_kor.txt", "output_advice_kor.txt"],
    "ko_compact": ["output_advice_compact.txt"],
}


# ── 포맷 감지 ─────────────────────────────────────────────────────────────────
def detect_format(sample_dir: str) -> str:
    """'new' (input.csv + output.csv) 또는 'old' (input_data.csv) 반환."""
    if os.path.exists(os.path.join(sample_dir, "input.csv")):
        return "new"
    return "old"


# ── AIS 포맷 ─────────────────────────────────────────────────────────────────
def format_ais(df: pd.DataFrame, lang: str) -> str:
    """df 컬럼은 소문자 정규화된 상태여야 함. ship_type 있으면 포함."""
    has_type = "ship_type" in df.columns

    if lang == "en":
        lines = ["[Vessel AIS Information]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m x {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            stype = f" Type:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- Own vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                        f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
                lines.append(
                    f"- Nearby vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft} | "
                    f"BoundingBox:[{bbox}]"
                )
    else:
        lines = ["[선박 AIS 정보]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m × {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            stype = f" 종류:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- 자선 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                        f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
                lines.append(
                    f"- 주변선박 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft} | "
                    f"바운딩박스:[{bbox}]"
                )
    return "\n".join(lines)


def _read_csv_normalized(path: str) -> pd.DataFrame:
    """CSV 읽고 컬럼명을 소문자로 정규화."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower()
    return df


def read_txt(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


# ── 신 포맷 헬퍼 ──────────────────────────────────────────────────────────────
def list_frames(sample_dir: str) -> list[str]:
    """frame_*.png 파일을 숫자 순으로 반환 (확장자 제외)."""
    pngs = glob.glob(os.path.join(sample_dir, "frame_*.png"))
    names = [os.path.splitext(os.path.basename(p))[0] for p in pngs]
    return sorted(names, key=lambda n: int(n.split("_")[-1]))


# ── question 빌더 ─────────────────────────────────────────────────────────────
def build_question_old(sample_dir: str, lang: str) -> str:
    csv_path = os.path.join(sample_dir, "input_data.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"AIS CSV not found: {csv_path}")
    df = _read_csv_normalized(csv_path)
    return f"{format_ais(df, AIS_LANG[lang])}\n\n{PROMPT_MAP[lang]}"


def build_question_new(sample_dir: str, frame: str, lang: str) -> str:
    csv_path = os.path.join(sample_dir, "input.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"AIS CSV not found: {csv_path}")
    df = _read_csv_normalized(csv_path)
    frame_df = df[df["file_name"] == frame]
    if frame_df.empty:
        raise ValueError(
            f"Frame '{frame}' not found in input.csv. "
            f"Available: {sorted(df['file_name'].unique().tolist())}"
        )
    return f"{format_ais(frame_df, AIS_LANG[lang])}\n\n{PROMPT_MAP[lang]}"


# ── reference 빌더 ────────────────────────────────────────────────────────────
def get_reference_old(sample_dir: str, lang: str) -> str:
    parts = [read_txt(os.path.join(sample_dir, f)) for f in OLD_REFERENCE_FILES[lang]]
    return "\n\n".join(p for p in parts if p) or "(기대값 파일 없음)"


def get_reference_new(sample_dir: str, frame: str) -> str:
    csv_path = os.path.join(sample_dir, "output.csv")
    if not os.path.exists(csv_path):
        return "(output.csv 없음)"
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.lower()
    row = df[df["file_name"] == frame]
    if row.empty:
        return f"('{frame}' 항목 없음)"
    return str(row.iloc[0]["text"]).strip()


# ── Argument parsing ──────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser("VisionLanguageModelV2 Inference (SDS sample dir)")

    # Model
    p.add_argument("--vision_model",    default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model",       default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--projector_type",  default="mlp2x_gelu")

    # Weights
    p.add_argument("--projector_path", required=True,
                   help="projector.bin 경로")
    p.add_argument("--lora_path", default=None,
                   help="LoRA 어댑터 디렉토리 (선택)")

    # Input
    p.add_argument("--sample_dir", required=True,
                   help="SDS 샘플 디렉토리")
    p.add_argument("--frame", default=None,
                   help="[신 포맷] 프레임 이름 (예: frame_3). 생략 시 첫 프레임 사용")
    p.add_argument("--lang", default="ko", choices=["en", "ko", "ko_compact"],
                   help="AIS/프롬프트 언어 시나리오 (기본: ko)")
    p.add_argument("--show_reference", action="store_true",
                   help="ground-truth 기대값 함께 출력")

    # Generation
    p.add_argument("--max_new_tokens",      type=int,   default=512)
    p.add_argument("--temperature",         type=float, default=0.2)
    p.add_argument("--top_p",               type=float, default=0.9)
    p.add_argument("--do_sample",           action="store_true", default=False)
    p.add_argument("--repetition_penalty",  type=float, default=1.0)

    # Hardware
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--dtype",  default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])

    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype  = DTYPE_MAP[args.dtype]
    device = torch.device(args.device)

    sample_dir = os.path.abspath(args.sample_dir.rstrip("/"))
    if not os.path.isdir(sample_dir):
        raise FileNotFoundError(f"sample_dir 가 존재하지 않습니다: {sample_dir}")
    fmt = detect_format(sample_dir)
    print(f"[Inference] Dataset format : {fmt}  ({sample_dir})")

    # ── 포맷별 이미지 경로 / question / reference ──────────────────────────────
    if fmt == "new":
        frames = list_frames(sample_dir)
        if not frames:
            raise FileNotFoundError(f"frame_*.png 파일을 찾을 수 없습니다: {sample_dir}")
        frame = args.frame if args.frame else frames[0]
        if frame not in frames:
            raise ValueError(f"'{frame}' 없음. 사용 가능: {frames}")
        image_path = os.path.join(sample_dir, f"{frame}.png")
        question   = build_question_new(sample_dir, frame, args.lang)
        reference  = get_reference_new(sample_dir, frame) if args.show_reference else None
        print(f"[Inference] Frame          : {frame}  ({len(frames)} available)")
    else:
        image_path = os.path.join(sample_dir, "input_image.png")
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        question  = build_question_old(sample_dir, args.lang)
        reference = get_reference_old(sample_dir, args.lang) if args.show_reference else None

    # ── Build model ────────────────────────────────────────────────────────────
    config = VLMConfig(
        vision_model_name=args.vision_model,
        llm_model_name=args.llm_model,
        projector_type=args.projector_type,
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=True,
        freeze_llm=True,
    )
    model = build_model(config, torch_dtype=dtype)

    print(f"[Inference] Loading projector: {args.projector_path}")
    proj_state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
    model.projector.load_weights(proj_state)

    if args.lora_path:
        print(f"[Inference] Loading LoRA: {args.lora_path}")
        from peft import PeftModel
        model.language_model = PeftModel.from_pretrained(
            model.language_model, args.lora_path
        )
        model.language_model = model.language_model.merge_and_unload()
        print("[Inference] LoRA merged.")

    model = model.to(device)
    model.eval()

    tokenizer       = model.tokenizer
    image_processor = model.vision_encoder.image_processor

    # ── Prepare image ──────────────────────────────────────────────────────────
    print(f"[Inference] Image: {image_path}")
    image = Image.open(image_path).convert("RGB")
    pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
    pixel_values = pixel_values.to(device, dtype=dtype)

    # ── Prepare prompt ─────────────────────────────────────────────────────────
    messages = [{"role": "user", "content": f"<image>\n{question}"}]
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt_text, add_special_tokens=False, return_tensors="pt")
    input_ids      = inputs.input_ids.to(device)
    attention_mask = inputs.attention_mask.to(device)

    img_count = (input_ids == config.image_token_id).sum().item()
    if img_count != 1:
        print(f"[WARNING] Expected 1 <image> token, found {img_count}.")

    # ── Generate ───────────────────────────────────────────────────────────────
    print(f"\n[Inference] Question ({args.lang}):")
    print(question)
    print("\n[Inference] Generating …\n")

    gen_kwargs = dict(
        max_new_tokens=args.max_new_tokens,
        do_sample=args.do_sample,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        repetition_penalty=args.repetition_penalty,
    )
    if args.do_sample:
        gen_kwargs["temperature"] = args.temperature
        gen_kwargs["top_p"]       = args.top_p

    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            **gen_kwargs,
        )

    generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # Qwen3 <think> 블록 제거
    if "</think>" in generated:
        generated = generated.split("</think>")[-1].strip()

    # 에코된 프롬프트 제거
    if question in generated:
        generated = generated.split(question)[-1].strip()

    print("=" * 60)
    print("[MODEL OUTPUT]")
    print("=" * 60)
    print(generated)
    print("=" * 60)

    if args.show_reference:
        print("\n" + "=" * 60)
        print("[REFERENCE / Ground Truth]")
        print("=" * 60)
        print(reference)
        print("=" * 60)


if __name__ == "__main__":
    main()
