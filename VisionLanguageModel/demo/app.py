"""
demo/app.py — VisionLanguageModelV2 SDS 데모 웹 애플리케이션

레이아웃:
  [상단 좌] 이미지 / CSV 테이블     [상단 우] 데이터셋 탐색기
  ─────────────────────────────────────────────────────────
  [하단 좌] 기대값 (5종 라디오)     [하단 우] 모델 설정 + 채팅

실행:
  /home/ywlee/miniconda3/envs/eva/bin/python demo/app.py
  → http://localhost:7860
"""
import gc
import os
import re
import sys
import traceback
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import torch

# ── Path setup ────────────────────────────────────────────────────────────────
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
VLM_DIR  = os.path.dirname(DEMO_DIR)
sys.path.insert(0, VLM_DIR)

import gradio as gr

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_DATASET_PATH = "/home/ywlee/dev/TANGO2_main/SDS/dataset/20260227"
CHECKPOINTS_ROOT     = os.path.join(VLM_DIR, "checkpoints")
DEFAULT_VISION_MODEL = "openai/clip-vit-large-patch14-336"
DEFAULT_LLM_MODEL    = "/home/ywlee/Llama-3.1-8B-Instruct"

# 출력 유형 ↔ 파일명 ↔ 프롬프트
OUTPUT_TYPES = [
    "영문 해상상황묘사",
    "한글 해상상황묘사",
    "영문 항해조력메시지",
    "한글 항해조력메시지",
    "간결 항해조력메시지",
]

FILE_MAP = {
    "영문 해상상황묘사":    "output_describe_en.txt",
    "한글 해상상황묘사":   "output_describe_kor.txt",
    "영문 항해조력메시지":  "output_advice_en.txt",
    "한글 항해조력메시지": "output_advice_kor.txt",
    "간결 항해조력메시지": "output_advice_compact.txt",
}

PROMPT_MAP = {
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

CSV_KO_COLUMNS = {
    "timestamp": "시간",
    "my_ship":   "자선여부",
    "ship_id":   "선박ID",
    "length":    "길이(m)",
    "width":     "너비(m)",
    "draft":     "흘수(m)",
    "latitude":  "위도",
    "longitude": "경도",
    "knot":      "속도(kt)",
    "heading":   "방향(°)",
    "bbox_x":    "BBox_X",
    "bbox_y":    "BBox_Y",
    "bbox_width":"BBox_W",
    "bbox_height":"BBox_H",
}

# ── Global model state ────────────────────────────────────────────────────────
_model = None
_model_device = None


# ── Dataset helpers ───────────────────────────────────────────────────────────

def scan_dataset(path: str):
    """데이터셋 경로를 스캔하여 샘플 디렉토리 목록을 반환."""
    path = path.strip()
    if not os.path.isdir(path):
        return gr.update(choices=[], value=None), f"❌ 경로를 찾을 수 없습니다: `{path}`"

    samples = sorted([
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ])

    if not samples:
        return gr.update(choices=[], value=None), "⚠️ 샘플 디렉토리가 없습니다."

    return (
        gr.update(choices=samples, value=samples[0]),
        f"✅ **{len(samples)}개** 샘플 발견",
    )


def _draw_bboxes(image: Image.Image, df_raw: pd.DataFrame) -> Image.Image:
    """타선 바운딩 박스를 초록색으로 그리고 선박ID 이름표를 추가."""
    img = image.copy()
    draw = ImageDraw.Draw(img)

    # 폰트 로드 (없으면 기본 폰트 사용)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15
        )
    except OSError:
        font = ImageFont.load_default()

    BOX_COLOR   = "#00FF00"   # 초록
    TEXT_BG     = "#00CC00"
    TEXT_FG     = "#000000"
    LINE_WIDTH  = 2

    for _, row in df_raw.iterrows():
        if int(row["my_ship"]) == 1:
            continue  # 자선은 bbox 없음

        x = float(row["bbox_x"])
        y = float(row["bbox_y"])
        w = float(row["bbox_width"])
        h = float(row["bbox_height"])

        if w <= 0 or h <= 0:
            continue

        ship_id = int(row["ship_id"])
        label   = f" ID:{ship_id} "

        # 바운딩 박스
        draw.rectangle([x, y, x + w, y + h], outline=BOX_COLOR, width=LINE_WIDTH)

        # 이름표 위치 (박스 위; 화면 밖이면 박스 안쪽 상단)
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        label_y = y - th - 4 if y - th - 4 >= 0 else y + 2

        draw.rectangle(
            [x, label_y, x + tw, label_y + th + 2],
            fill=TEXT_BG,
        )
        draw.text((x, label_y + 1), label, fill=TEXT_FG, font=font)

    return img


def load_sample(dataset_path: str, sample_name: str):
    """선택된 샘플의 이미지(bbox 포함)와 CSV를 반환."""
    if not sample_name:
        return None, pd.DataFrame()

    sample_dir = os.path.join(dataset_path.strip(), sample_name)

    # CSV (원본 컬럼으로 먼저 읽기)
    csv_path = os.path.join(sample_dir, "input_data.csv")
    df_raw = pd.read_csv(csv_path) if os.path.exists(csv_path) else None

    # Image + 바운딩 박스 오버레이
    img_path = os.path.join(sample_dir, "input_image.png")
    if os.path.exists(img_path):
        image = Image.open(img_path).convert("RGB")
        if df_raw is not None:
            image = _draw_bboxes(image, df_raw)
    else:
        image = None

    # CSV 표시용 (한글 컬럼)
    if df_raw is not None:
        df = df_raw.rename(columns=CSV_KO_COLUMNS)
        df["자선여부"] = df["자선여부"].map({1: "✅ 자선", 0: "타선"})
    else:
        df = pd.DataFrame({"오류": ["input_data.csv 없음"]})

    return image, df


def load_expected(dataset_path: str, sample_name: str, output_type: str) -> str:
    """선택된 출력 유형의 기대값 텍스트를 반환."""
    if not sample_name or not output_type:
        return ""

    filename = FILE_MAP.get(output_type, "")
    path = os.path.join(dataset_path.strip(), sample_name, filename)

    if not os.path.exists(path):
        return f"(파일 없음: {filename})"

    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def format_ais_text(dataset_path: str, sample_name: str, lang: str = "ko") -> str:
    """CSV를 자연어 형태로 포맷하여 모델 프롬프트에 포함할 텍스트 생성.

    lang: "en" → English labels, "ko" → Korean labels
    """
    csv_path = os.path.join(dataset_path.strip(), sample_name, "input_data.csv")
    if not os.path.exists(csv_path):
        return ""

    df = pd.read_csv(csv_path)

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

            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- Own vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                bbox = (
                    f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                    f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}"
                )
                lines.append(
                    f"- Nearby vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
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

            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- 자선 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                bbox = (
                    f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                    f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}"
                )
                lines.append(
                    f"- 주변선박 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft} | 바운딩박스:[{bbox}]"
                )

    return "\n".join(lines)


# ── Model helpers ─────────────────────────────────────────────────────────────

def get_checkpoint_choices():
    """체크포인트 디렉토리 목록을 반환. projector.bin이 있는 디렉토리만 포함."""
    result = []
    if os.path.isdir(CHECKPOINTS_ROOT):
        for root, dirs, files in os.walk(CHECKPOINTS_ROOT):
            if "projector.bin" in files:
                rel = os.path.relpath(root, VLM_DIR)
                has_lora = os.path.exists(os.path.join(root, "adapter_config.json"))
                label = f"{rel}  [LoRA]" if has_lora else rel
                result.append(label)
    return sorted(result) or ["(체크포인트 없음)"]


def _unload_model():
    """기존 로드된 모델을 GPU 메모리에서 해제."""
    global _model, _model_device
    if _model is not None:
        _model.cpu()
        del _model
        _model = None
        _model_device = None
        gc.collect()
        torch.cuda.empty_cache()


def load_model(checkpoint_label: str, vision_model: str, llm_model: str) -> str:
    """VLM 모델을 로드하고 상태 메시지를 반환. 기존 모델은 먼저 해제."""
    global _model, _model_device

    if not checkpoint_label or checkpoint_label == "(체크포인트 없음)":
        return "❌ 유효한 체크포인트를 선택하세요."

    # 레이블에서 " [LoRA]" 접미사 제거하여 실제 경로 추출
    checkpoint_dir_rel = checkpoint_label.replace("  [LoRA]", "").strip()
    checkpoint_dir = os.path.join(VLM_DIR, checkpoint_dir_rel)

    projector_path = os.path.join(checkpoint_dir, "projector.bin")
    if not os.path.exists(projector_path):
        return f"❌ projector.bin을 찾을 수 없습니다:\n`{checkpoint_dir}`"

    has_lora = os.path.exists(os.path.join(checkpoint_dir, "adapter_config.json"))

    # 기존 모델 해제
    _unload_model()

    try:
        from model import VLMConfig, build_model as _build

        config = VLMConfig(
            vision_model_name=vision_model.strip(),
            llm_model_name=llm_model.strip(),
            projector_type="mlp2x_gelu",
            freeze_vision=True,
            freeze_llm=not has_lora,  # LoRA 적용 시 LLM 파라미터 필요
        )

        m = _build(config, torch_dtype=torch.bfloat16)

        # 프로젝터 가중치 로드
        proj_state = torch.load(projector_path, map_location="cpu", weights_only=True)
        m.projector.load_weights(proj_state)

        # LoRA 가중치 로드 (있는 경우)
        if has_lora:
            from peft import PeftModel
            m.language_model = PeftModel.from_pretrained(
                m.language_model,
                checkpoint_dir,
                torch_dtype=torch.bfloat16,
            )
            m.language_model = m.language_model.merge_and_unload()
            print("[Demo] LoRA weights merged.")

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        m = m.to(device)
        m.eval()

        _model        = m
        _model_device = device

        mem_gb = torch.cuda.memory_allocated(device) / 1e9 if device.type == "cuda" else 0
        mode_str = "프로젝터 + LoRA" if has_lora else "프로젝터 전용"
        return (
            f"✅ **모델 로드 완료** ({mode_str})\n"
            f"- 체크포인트: `{checkpoint_dir_rel}`\n"
            f"- 디바이스: `{device}` (VRAM {mem_gb:.1f} GB 사용)\n"
            f"- 이미지 토큰: `{config.num_image_tokens}개`\n"
            f"- 어휘 크기: `{len(m.tokenizer)}`"
        )

    except Exception:
        _unload_model()  # 실패 시 정리
        return f"❌ 모델 로드 실패:\n```\n{traceback.format_exc()}\n```"


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(
    dataset_path: str,
    sample_name: str,
    output_type: str,
    user_prompt: str,
    history: list,
):
    """모델 추론을 실행하고 채팅 히스토리를 업데이트."""
    history = list(history or [])

    if _model is None:
        history.append({"role": "assistant", "content": "⚠️ 먼저 모델을 로드해주세요."})
        return history

    if not sample_name:
        history.append({"role": "assistant", "content": "⚠️ 샘플을 선택해주세요."})
        return history

    # AIS 텍스트 + 프롬프트 합성
    lang = "en" if "영문" in output_type else "ko"
    ais_text = format_ais_text(dataset_path, sample_name, lang=lang)
    # 사용자 입력 프롬프트 우선, 없으면 출력 유형 기본값 사용
    question = user_prompt.strip() if user_prompt.strip() else PROMPT_MAP.get(output_type, "")
    full_question = f"{ais_text}\n\n{question}" if ais_text else question

    # 사용자 메시지를 채팅에 추가
    user_msg = (
        f"**[샘플]** `{sample_name}`\n"
        f"**[출력유형]** {output_type}\n\n"
        f"```\n{ais_text}\n```\n\n"
        f"**{question}**"
    )
    history.append({"role": "user", "content": user_msg})

    try:
        img_path = os.path.join(dataset_path.strip(), sample_name, "input_image.png")
        image = Image.open(img_path).convert("RGB")

        tokenizer       = _model.tokenizer
        image_processor = _model.vision_encoder.image_processor

        messages = [{"role": "user", "content": f"<image>\n{full_question}"}]
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

        pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(_model_device, dtype=torch.bfloat16)

        input_ids = tokenizer(
            prompt_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids.to(_model_device)
        attention_mask = torch.ones_like(input_ids)

        with torch.no_grad():
            output_ids = _model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pixel_values=pixel_values,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1,
            )

        response = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        # Qwen3: </think> 이후 실제 답변만 추출
        if "</think>" in response:
            response = response.split("</think>")[-1].strip()
        # 프롬프트가 echo 되는 경우 제거
        elif full_question in response:
            response = response.split(full_question)[-1].strip()

        history.append({"role": "assistant", "content": response})

    except Exception:
        history.append({
            "role": "assistant",
            "content": f"❌ 추론 실패:\n```\n{traceback.format_exc()}\n```",
        })

    return history


# ── Gradio UI ─────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
    .section-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; }
    .csv-table { font-size: 0.82rem; }
    #expected-box textarea { font-size: 0.85rem; line-height: 1.6; }
    #chat-col { border-left: 1px solid #e2e8f0; padding-left: 12px; }
"""

def build_ui():
    with gr.Blocks(title="VLM SDS Demo") as demo:

        gr.Markdown("# 🚢 VisionLanguageModel SDS 데모")
        gr.Markdown(
            "선박 자율항행 지원을 위한 Vision-Language Model 추론 데모입니다. "
            "우측 탐색기에서 샘플을 선택하고 하단에서 모델 출력을 확인하세요."
        )

        # ── 상단: 이미지/CSV + 탐색기 ──────────────────────────────────────────
        with gr.Row(equal_height=False):

            # 상단 좌: 이미지 + CSV
            with gr.Column(scale=3):
                gr.Markdown("### 📸 입력 이미지", elem_classes="section-title")
                img_display = gr.Image(
                    label="input_image.png",
                    height=320,
                )
                gr.Markdown("### 📊 AIS 데이터", elem_classes="section-title")
                csv_display = gr.Dataframe(
                    label="input_data.csv",
                    interactive=False,
                    wrap=False,
                    elem_classes="csv-table",
                )

            # 상단 우: 탐색기
            with gr.Column(scale=1, min_width=280):
                gr.Markdown("### 📁 데이터셋 탐색기", elem_classes="section-title")

                with gr.Row():
                    path_input = gr.Textbox(
                        value=DEFAULT_DATASET_PATH,
                        label="데이터셋 경로",
                        placeholder="/path/to/dataset",
                        scale=4,
                    )
                    path_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                with gr.Row(visible=False) as path_explorer_row:
                    with gr.Column():
                        path_file_explorer = gr.FileExplorer(
                            root_dir="/home",
                            glob="**",
                            file_count="single",
                            label="데이터셋 디렉토리 선택",
                            height=240,
                        )
                        path_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")
                scan_btn    = gr.Button("📂 스캔", variant="secondary", size="sm")
                scan_status = gr.Markdown("")

                sample_list = gr.Dropdown(
                    choices=[],
                    value=None,
                    label="샘플 목록",
                )

        gr.Markdown("---")

        # ── 하단: 기대값 + 채팅 ────────────────────────────────────────────────
        with gr.Row(equal_height=False):

            # 하단 좌: 기대값
            with gr.Column(scale=2):
                gr.Markdown("### 📋 기대값 (Ground Truth)", elem_classes="section-title")

                output_type_radio = gr.Radio(
                    choices=OUTPUT_TYPES,
                    value=OUTPUT_TYPES[0],
                    label="출력 유형",
                )
                expected_box = gr.Textbox(
                    label="기대값 텍스트",
                    lines=14,
                    max_lines=20,
                    interactive=False,
                    elem_id="expected-box",
                )

            # 하단 우: 모델 + 채팅
            with gr.Column(scale=3, elem_id="chat-col"):
                gr.Markdown("### 💬 모델 추론", elem_classes="section-title")

                # 모델 설정 아코디언
                with gr.Accordion("⚙️ 모델 설정", open=True):
                    with gr.Row():
                        checkpoint_dd = gr.Dropdown(
                            choices=get_checkpoint_choices(),
                            value=None,
                            label="체크포인트 디렉토리 (projector.bin / LoRA 자동 감지)",
                            scale=4,
                        )
                        refresh_btn    = gr.Button("🔄", scale=0, min_width=44, size="sm")
                        ckpt_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as ckpt_explorer_row:
                        with gr.Column():
                            ckpt_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                file_count="single",
                                label="체크포인트 디렉토리 선택",
                                height=240,
                            )
                            ckpt_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        vision_input = gr.Textbox(
                            value=DEFAULT_VISION_MODEL,
                            label="비전 모델 경로",
                            scale=4,
                        )
                        vision_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as vision_explorer_row:
                        with gr.Column():
                            vision_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                file_count="single",
                                label="비전 모델 디렉토리 선택",
                                height=240,
                            )
                            vision_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        llm_input = gr.Textbox(
                            value=DEFAULT_LLM_MODEL,
                            label="언어 모델 경로",
                            scale=4,
                        )
                        llm_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as llm_explorer_row:
                        with gr.Column():
                            llm_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                file_count="single",
                                label="언어 모델 디렉토리 선택",
                                height=240,
                            )
                            llm_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        load_btn = gr.Button("모델 로드", variant="primary", scale=2)
                        with gr.Column(scale=3):
                            model_status = gr.Markdown("⚪ 모델 미로드")

                # 채팅 출력 유형 (기대값 라디오와 연동)
                chat_type = gr.Radio(
                    choices=OUTPUT_TYPES,
                    value=OUTPUT_TYPES[0],
                    label="채팅 출력 유형 (기대값과 연동됨)",
                )

                chatbot = gr.Chatbot(
                    label="대화",
                    height=300,
                    avatar_images=(None, "🤖"),
                )

                prompt_input = gr.Textbox(
                    value=PROMPT_MAP[OUTPUT_TYPES[0]],
                    label="프롬프트 (편집 가능 — 비우면 출력 유형 기본값 사용)",
                    lines=3,
                )

                with gr.Row():
                    infer_btn = gr.Button("🚀 추론 실행", variant="primary", scale=3)
                    clear_btn = gr.Button("🗑️ 초기화", variant="secondary", scale=1)

        # ── Event bindings ─────────────────────────────────────────────────────

        # 스캔
        scan_btn.click(
            fn=scan_dataset,
            inputs=[path_input],
            outputs=[sample_list, scan_status],
        )
        path_input.submit(
            fn=scan_dataset,
            inputs=[path_input],
            outputs=[sample_list, scan_status],
        )

        # 샘플 선택 → 이미지 + CSV 업데이트
        sample_list.change(
            fn=load_sample,
            inputs=[path_input, sample_list],
            outputs=[img_display, csv_display],
        )

        # 샘플 또는 출력유형 변경 → 기대값 업데이트
        def _update_expected(dp, sn, ot):
            return load_expected(dp, sn, ot)

        sample_list.change(
            fn=_update_expected,
            inputs=[path_input, sample_list, output_type_radio],
            outputs=[expected_box],
        )
        output_type_radio.change(
            fn=_update_expected,
            inputs=[path_input, sample_list, output_type_radio],
            outputs=[expected_box],
        )

        # 기대값 라디오 ↔ 채팅 출력유형 양방향 연동 + 프롬프트 기본값 갱신
        output_type_radio.change(
            fn=lambda ot: (ot, PROMPT_MAP.get(ot, "")),
            inputs=[output_type_radio],
            outputs=[chat_type, prompt_input],
        )
        chat_type.change(
            fn=lambda ot: (ot, PROMPT_MAP.get(ot, "")),
            inputs=[chat_type],
            outputs=[output_type_radio, prompt_input],
        )

        # ── 파일 탐색기 이벤트 ────────────────────────────────────────────────

        # 데이터셋 경로 탐색기
        path_browse_btn.click(
            fn=lambda: gr.update(visible=True), outputs=[path_explorer_row],
        )
        path_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[path_file_explorer],
            outputs=[path_input, path_explorer_row],
        )
        path_explorer_close.click(
            fn=lambda: gr.update(visible=False), outputs=[path_explorer_row],
        )

        # 체크포인트 탐색기
        def _select_ckpt_from_path(p):
            if not p:
                return gr.update(), gr.update(visible=False)
            has_proj = os.path.exists(os.path.join(p, "projector.bin"))
            has_lora = os.path.exists(os.path.join(p, "adapter_config.json"))
            try:
                rel = os.path.relpath(p, VLM_DIR)
            except ValueError:
                rel = p  # Windows cross-drive edge case 방어
            label = (f"{rel}  [LoRA]" if has_lora else rel) if has_proj else p
            choices = get_checkpoint_choices()
            if label not in choices:
                choices = sorted(choices + [label])
            return gr.update(choices=choices, value=label), gr.update(visible=False)

        ckpt_browse_btn.click(
            fn=lambda: gr.update(visible=True), outputs=[ckpt_explorer_row],
        )
        ckpt_file_explorer.change(
            fn=_select_ckpt_from_path,
            inputs=[ckpt_file_explorer],
            outputs=[checkpoint_dd, ckpt_explorer_row],
        )
        ckpt_explorer_close.click(
            fn=lambda: gr.update(visible=False), outputs=[ckpt_explorer_row],
        )

        # 비전 모델 경로 탐색기
        vision_browse_btn.click(
            fn=lambda: gr.update(visible=True), outputs=[vision_explorer_row],
        )
        vision_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[vision_file_explorer],
            outputs=[vision_input, vision_explorer_row],
        )
        vision_explorer_close.click(
            fn=lambda: gr.update(visible=False), outputs=[vision_explorer_row],
        )

        # 언어 모델 경로 탐색기
        llm_browse_btn.click(
            fn=lambda: gr.update(visible=True), outputs=[llm_explorer_row],
        )
        llm_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[llm_file_explorer],
            outputs=[llm_input, llm_explorer_row],
        )
        llm_explorer_close.click(
            fn=lambda: gr.update(visible=False), outputs=[llm_explorer_row],
        )

        # 체크포인트 목록 새로고침
        refresh_btn.click(
            fn=lambda: gr.update(choices=get_checkpoint_choices()),
            outputs=[checkpoint_dd],
        )

        # 모델 로드 — 버튼 비활성화 → 로드 → 버튼 복원
        load_btn.click(
            fn=lambda: (gr.update(interactive=False, value="로딩 중..."), "🔄 모델 로드 중..."),
            outputs=[load_btn, model_status],
            queue=False,
        ).then(
            fn=load_model,
            inputs=[checkpoint_dd, vision_input, llm_input],
            outputs=[model_status],
        ).then(
            fn=lambda: gr.update(interactive=True, value="모델 로드"),
            outputs=[load_btn],
        )

        # 추론 실행
        infer_btn.click(
            fn=run_inference,
            inputs=[path_input, sample_list, chat_type, prompt_input, chatbot],
            outputs=[chatbot],
        )

        # 채팅 초기화
        clear_btn.click(fn=lambda: [], outputs=[chatbot])

        # 앱 시작 시 자동 스캔
        demo.load(
            fn=scan_dataset,
            inputs=[path_input],
            outputs=[sample_list, scan_status],
        )
        # 첫 샘플 자동 로드
        demo.load(
            fn=lambda dp, samples: load_sample(dp, samples[0]) if samples else (None, pd.DataFrame()),
            inputs=[path_input, sample_list],
            outputs=[img_display, csv_display],
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser("VLM SDS Demo")
    p.add_argument("--host",  default="0.0.0.0")
    p.add_argument("--port",  type=int, default=7860)
    p.add_argument("--share", action="store_true", help="Gradio public URL")
    args = p.parse_args()

    demo = build_ui()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="blue", 
            secondary_hue="slate",
            font=[gr.themes.GoogleFont("Noto Sans KR"), "sans-serif"],
            font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
        ),
        css=CUSTOM_CSS,
    )
