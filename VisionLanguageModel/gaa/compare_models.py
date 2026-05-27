"""
GAA vs Baseline 모델 비교 스크립트

두 체크포인트에 동일한 SDS 입력을 넣고 출력을 나란히 비교합니다.

Usage:
  python gaa/compare_models.py \
      --baseline  /home/ywlee/SSD/checkpoints/clip_llama31_lora_marine_sds_lora_en \
      --gaa_model /home/ywlee/SSD/checkpoints/gaa_marine_sds_lora_en \
      --data_path data/sds_gaa_en.json \
      --image_dir /home/ywlee/dev/TANGO2/SDS/dataset/20260227 \
      --num_samples 10
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import textwrap
import torch
from PIL import Image
from transformers import AutoTokenizer, CLIPImageProcessor
from peft import PeftModel

from model import VLMConfig, build_model


def parse_args():
    p = argparse.ArgumentParser("GAA vs Baseline comparison")
    p.add_argument("--baseline",    required=True,  help="기준 모델 체크포인트 경로")
    p.add_argument("--gaa_model",   required=True,  help="GAA 학습 모델 체크포인트 경로")
    p.add_argument("--data_path",   required=True,  help="평가용 chat.json")
    p.add_argument("--image_dir",   required=True,  help="이미지 디렉토리")
    p.add_argument("--num_samples", type=int, default=5,   help="비교할 샘플 수")
    p.add_argument("--max_new_tokens", type=int, default=300)
    p.add_argument("--llm_model",   default="/home/ywlee/SSD/Llama-3.1-8B-Instruct")
    p.add_argument("--vision_model",default="openai/clip-vit-large-patch14-336")
    p.add_argument("--dtype",       default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    return p.parse_args()


def load_model(ckpt_path: str, llm_model: str, vision_model: str, dtype: torch.dtype):
    config = VLMConfig(
        vision_model_name=vision_model,
        llm_model_name=llm_model,
        projector_type="mlp2x_gelu",
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=True,
        freeze_llm=True,
    )
    model = build_model(config, torch_dtype=dtype)

    # Load projector
    proj_path = os.path.join(ckpt_path, "projector.bin")
    if os.path.exists(proj_path):
        state = torch.load(proj_path, map_location="cpu", weights_only=True)
        model.projector.load_weights(state)

    # Load LoRA adapter
    model.language_model = PeftModel.from_pretrained(
        model.language_model, ckpt_path, is_trainable=False
    )
    model.eval()
    return model


@torch.no_grad()
def generate_response(model, tokenizer, image_processor, human_msg: str,
                      image_path: str, max_new_tokens: int, device: torch.device) -> str:
    # Tokenize prompt
    prompt_msgs = [{"role": "user", "content": human_msg}]
    prompt_text = tokenizer.apply_chat_template(
        prompt_msgs, tokenize=False, add_generation_prompt=True
    )
    input_ids = tokenizer(
        prompt_text, add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)

    # Load image
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        image = Image.new("RGB", (336, 336), 0)
    pixel_values = image_processor(
        images=image, return_tensors="pt"
    ).pixel_values.to(device=device, dtype=model.vision_encoder.dtype)

    output_ids = model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=None,
        top_p=None,
    )

    # model.generate() internally uses inputs_embeds, so the returned tensor
    # contains only the newly generated token IDs (no input prefix to strip).
    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()


def wrap(text: str, width: int = 80, indent: str = "  ") -> str:
    return "\n".join(
        textwrap.fill(line, width=width, initial_indent=indent,
                      subsequent_indent=indent)
        for line in text.splitlines()
    )


def main():
    args = parse_args()

    DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype = DTYPE_MAP[args.dtype]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    with open(args.data_path) as f:
        data = json.load(f)
    samples = data[:args.num_samples]

    # ── 모델별 순차 추론 (GPU 메모리 절약) ────────────────────────────────────
    results = {s["id"]: {} for s in samples}

    for label, ckpt_path in [("baseline", args.baseline), ("gaa", args.gaa_model)]:
        print(f"\nLoading {label} model: {os.path.basename(ckpt_path)} ...")
        model = load_model(ckpt_path, args.llm_model, args.vision_model, dtype)
        model.to(device)
        tokenizer       = model.tokenizer
        image_processor = model.vision_encoder.image_processor

        for sample in samples:
            human_msg  = sample["conversations"][0]["value"]
            image_path = os.path.join(args.image_dir, sample["image"])
            out = generate_response(
                model, tokenizer, image_processor,
                human_msg, image_path, args.max_new_tokens, device
            )
            results[sample["id"]][label] = out

        # GPU 메모리 해제
        del model
        torch.cuda.empty_cache()

    # ── 결과 출력 ─────────────────────────────────────────────────────────────
    print(f"\n{'='*100}")
    print(f"  비교: Baseline ({os.path.basename(args.baseline)})  vs  GAA ({os.path.basename(args.gaa_model)})")
    print(f"{'='*100}\n")

    for idx, sample in enumerate(samples, 1):
        sid = sample["id"]
        ground_truth = sample["conversations"][1]["value"]

        print(f"[Sample {idx}/{len(samples)}] {sid}")
        print(f"  Bboxes : {sample.get('bboxes', [])}")
        print()
        print("  [Ground Truth]")
        print(wrap(ground_truth))
        print()
        print(f"  [Baseline — {os.path.basename(args.baseline)}]")
        print(wrap(results[sid]["baseline"]))
        print()
        print(f"  [GAA — {os.path.basename(args.gaa_model)}]")
        print(wrap(results[sid]["gaa"]))
        print()
        print("-" * 100)
        print()


if __name__ == "__main__":
    main()
