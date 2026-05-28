"""
test.py — VisionLanguageModelV2 Inference

Loads a trained model (projector + optional LoRA) and generates responses.

Usage (single image):
  /home/ywlee/miniconda3/envs/eva/bin/python test.py \\
      --projector_path checkpoints/clip_llama_projector/projector.bin \\
      --image /path/to/image.jpg \\
      --question "What is in this image?"

Usage (with LoRA):
  /home/ywlee/miniconda3/envs/eva/bin/python test.py \\
      --projector_path checkpoints/lora_run/projector.bin \\
      --lora_path checkpoints/lora_run \\
      --image /path/to/image.jpg

Multi-GPU (via torchrun):
  torchrun --nproc_per_node=2 test.py --projector_path ... --image ...
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import torch
from PIL import Image

from model import VLMConfig, build_model


# ── Argument parsing ──────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser("VisionLanguageModelV2 Inference")

    # Model
    p.add_argument("--vision_model", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model",    default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--projector_type", default="mlp2x_gelu")

    # Weights
    p.add_argument("--projector_path", required=True,
                   help="Path to projector.bin (from training)")
    p.add_argument("--lora_path", default=None,
                   help="Path to saved LoRA adapter directory (optional)")

    # Input
    p.add_argument("--image",    required=True, help="Path to input image")
    p.add_argument("--question", default="Describe this image in detail.",
                   help="Question / prompt for the model")

    # Generation
    p.add_argument("--max_new_tokens", type=int,   default=512)
    p.add_argument("--temperature",    type=float, default=0.2)
    p.add_argument("--top_p",          type=float, default=0.9)
    p.add_argument("--do_sample",      action="store_true", default=False)
    p.add_argument("--repetition_penalty", type=float, default=1.0)

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

    # ── Build base model ──────────────────────────────────────────────────────
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

    # ── Load projector weights ─────────────────────────────────────────────────
    print(f"[Inference] Loading projector: {args.projector_path}")
    proj_state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
    model.projector.load_weights(proj_state)

    # ── Load LoRA adapter (optional) ──────────────────────────────────────────
    if args.lora_path:
        print(f"[Inference] Loading LoRA adapter: {args.lora_path}")
        from peft import PeftModel
        model.language_model = PeftModel.from_pretrained(
            model.language_model, args.lora_path
        )
        model.language_model = model.language_model.merge_and_unload()
        print("[Inference] LoRA merged into base model.")

    model = model.to(device)
    model.eval()

    tokenizer       = model.tokenizer
    image_processor = model.vision_encoder.image_processor

    # ── Prepare image ──────────────────────────────────────────────────────────
    print(f"[Inference] Image: {args.image}")
    image = Image.open(args.image).convert("RGB")
    pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
    pixel_values = pixel_values.to(device, dtype=dtype)

    # ── Prepare prompt ─────────────────────────────────────────────────────────
    messages = [{"role": "user", "content": f"<image>\n{args.question}"}]
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(
        prompt_text, add_special_tokens=False, return_tensors="pt"
    )
    input_ids      = inputs.input_ids.to(device)
    attention_mask = inputs.attention_mask.to(device)

    # Verify <image> token is present
    img_count = (input_ids == config.image_token_id).sum().item()
    if img_count != 1:
        print(f"[WARNING] Expected 1 <image> token, found {img_count}. "
              "Check tokenizer and prompt format.")

    # ── Generate ───────────────────────────────────────────────────────────────
    print(f"\n[Inference] Question: {args.question}")
    print("[Inference] Generating …\n")

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

    # Decode
    generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # Strip echoed prompt if present
    if args.question in generated:
        generated = generated.split(args.question)[-1].strip()

    print("=" * 60)
    print(generated)
    print("=" * 60)


if __name__ == "__main__":
    main()
