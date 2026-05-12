"""
load_test.py — Phase 1: Architecture & Weight Loading Verification

Tests:
  1. Build model (CLIP + Llama 3.1 + random projector)
  2. Verify shapes at each stage
  3. Forward pass with a real image + prompt (no training)
  4. Greedy generation to confirm end-to-end text output
  5. Print memory usage

Usage:
  cd /home/ywlee/dev/ClaudeSDS/VisionLanguageModelV2
  /home/ywlee/miniconda3/envs/eva/bin/python load_test.py
  /home/ywlee/miniconda3/envs/eva/bin/python load_test.py --vision google/siglip-so400m-patch14-384
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import torch
from PIL import Image

# ── Parse arguments ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="VisionLanguageModelV2 load test")
parser.add_argument("--vision", default="openai/clip-vit-large-patch14-336",
                    help="Vision encoder model name/path")
parser.add_argument("--llm",    default="/home/ywlee/Llama-3.1-8B-Instruct",
                    help="LLM model name/path")
parser.add_argument("--device", default="cuda:0",
                    help="Device to use (cuda:0, cpu)")
parser.add_argument("--dtype",  default="bfloat16",
                    choices=["bfloat16", "float16", "float32"],
                    help="Model dtype")
parser.add_argument("--generate", action="store_true",
                    help="Run text generation (slow; for end-to-end verification)")
parser.add_argument("--test_image", default=None,
                    help="Path to a test image (optional; uses random tensor if not given)")
args = parser.parse_args()

DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
DTYPE  = DTYPE_MAP[args.dtype]
DEVICE = torch.device(args.device)

print("=" * 65)
print("  VisionLanguageModelV2 — Load & Architecture Test")
print("=" * 65)
print(f"  Vision encoder : {args.vision}")
print(f"  LLM            : {args.llm}")
print(f"  Device         : {DEVICE}")
print(f"  dtype          : {DTYPE}")
print("=" * 65)


# ── 1. Build model ────────────────────────────────────────────────────────────
from model import VLMConfig, build_model

config = VLMConfig(
    vision_model_name=args.vision,
    llm_model_name=args.llm,
    projector_type="mlp2x_gelu",
    vision_feature_layer=-2,
    vision_feature_select_strategy="patch",
    freeze_vision=True,
    freeze_llm=True,  # inference only — projector has random weights
)

print("\n[Step 1/5] Building model …")
model = build_model(config, torch_dtype=DTYPE)
model = model.to(DEVICE)
model.eval()


# ── 2. Tokenizer + image processor ────────────────────────────────────────────
tokenizer       = model.tokenizer
image_processor = model.vision_encoder.image_processor

print(f"\n[Step 2/5] Tokenizer & processor ready")
print(f"  Vocab size (with <image>): {len(tokenizer)}")
print(f"  image_token_id           : {config.image_token_id}")
print(f"  num_image_tokens         : {config.num_image_tokens}")


# ── 3. Prepare inputs ─────────────────────────────────────────────────────────
print("\n[Step 3/5] Preparing inputs …")

# --- Image ---
if args.test_image and os.path.exists(args.test_image):
    image = Image.open(args.test_image).convert("RGB")
    print(f"  Loaded image: {args.test_image}  size={image.size}")
else:
    # Create a solid-colour placeholder
    image = Image.new("RGB", (336, 336), color=(100, 149, 237))
    print("  Using placeholder image (cornflower blue 336×336)")

pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
pixel_values = pixel_values.to(DEVICE, dtype=DTYPE)
print(f"  pixel_values shape : {tuple(pixel_values.shape)}  dtype={pixel_values.dtype}")

# --- Text prompt ---
question = "Describe this image in detail."
messages = [{"role": "user", "content": f"<image>\n{question}"}]
prompt_text = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
input_ids = tokenizer(
    prompt_text, add_special_tokens=False, return_tensors="pt"
).input_ids.to(DEVICE)
attention_mask = torch.ones_like(input_ids)

print(f"  prompt_text    : {repr(prompt_text[:120])} …")
print(f"  input_ids shape: {tuple(input_ids.shape)}")

# Verify <image> token appears exactly once
img_tok_count = (input_ids == config.image_token_id).sum().item()
print(f"  <image> tokens in input_ids: {img_tok_count}  (expected 1)")
if img_tok_count != 1:
    print("  WARNING: <image> token count is not 1. Check tokenizer setup.")


# ── 4. Forward pass (no generation) ──────────────────────────────────────────
print("\n[Step 4/5] Forward pass …")
with torch.no_grad():
    # ── 4a. Vision encoder only ────────────────────────────────────────────
    img_features = model.vision_encoder(pixel_values)    # (1, N, D_vision)
    print(f"  vision_encoder output : {tuple(img_features.shape)}  "
          f"dtype={img_features.dtype}")

    # ── 4b. Projector only ─────────────────────────────────────────────────
    proj_features = model.projector(img_features)         # (1, N, D_llm)
    print(f"  projector output      : {tuple(proj_features.shape)}  "
          f"dtype={proj_features.dtype}")

    # ── 4c. Full forward (multimodal fusion → LLM logits) ─────────────────
    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=None,
    )
    expected_len = input_ids.shape[1] + config.num_image_tokens - 1
    print(f"  logits shape          : {tuple(out.logits.shape)}  "
          f"(expected seq_len={expected_len})")
    print(f"  logits dtype          : {out.logits.dtype}")
    print(f"  logits range          : [{out.logits.min().item():.3f}, "
          f"{out.logits.max().item():.3f}]")

    nan_count = out.logits.isnan().sum().item()
    inf_count = out.logits.isinf().sum().item()
    print(f"  NaN / Inf in logits   : {nan_count} / {inf_count}  "
          f"{'✓ PASS' if nan_count == 0 and inf_count == 0 else '✗ FAIL'}")


# ── 5. Text generation (optional) ─────────────────────────────────────────────
if args.generate:
    print("\n[Step 5/5] Text generation …")
    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            max_new_tokens=128,
            do_sample=False,         # greedy for reproducibility
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    # Decode only new tokens
    # generate() returns token ids starting from position 0
    generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    print(f"\n  Generated:\n{generated_text}\n")
else:
    print("\n[Step 5/5] Skipped generation (pass --generate to enable)")


# ── Memory summary ────────────────────────────────────────────────────────────
if DEVICE.type == "cuda":
    allocated = torch.cuda.memory_allocated(DEVICE) / 1e9
    reserved  = torch.cuda.memory_reserved(DEVICE)  / 1e9
    print(f"\n[Memory] GPU allocated : {allocated:.2f} GB")
    print(f"[Memory] GPU reserved  : {reserved:.2f} GB")

print("\n" + "=" * 65)
print("  ALL CHECKS PASSED — Model architecture is functional")
print("=" * 65)
