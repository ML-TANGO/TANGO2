"""
GAA Training Entry Point

Trains VisionLanguageModelV2 with Geometric Attention Alignment (GAA).
Bounding boxes stored in the training JSON are used as privileged information
to suppress background texture attention in the CLIP vision encoder.

Key difference from train.py:
  - freeze_vision=False   (vision encoder must receive L_geo gradients)
  - GAADataset / GAADataCollator  (loads and batches bbox annotations)
  - GAATrainer            (adds L_geo = λ · geometric_loss to L_SFT)

Usage (single GPU):
  python gaa/train_gaa.py \\
      --data_path /path/to/sds_gaa_train.json \\
      --image_dir /path/to/images \\
      --projector_path checkpoints/projector/projector.bin \\
      --output_dir checkpoints/gaa_lora

Usage (multi-GPU with DeepSpeed):
  See scripts/train_lora_gaa.sh
"""
import sys
import os
# Ensure VisionLanguageModel/ is importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import math
import torch
from transformers import TrainingArguments
from transformers.trainer_utils import get_last_checkpoint
from peft import LoraConfig, get_peft_model

from model import VLMConfig, build_model
from gaa.gaa_dataset import GAADataset, GAADataCollator
from gaa.gaa_trainer import GAATrainer
from train import init_wandb, watch_model_wandb, WandbGPUCallback, _is_main_process


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser("GAA VLM Trainer")

    # Model
    p.add_argument("--vision_model", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model",    default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--projector_type", default="mlp2x_gelu",
                   choices=["linear", "mlp2x_gelu", "mlp3x_gelu"])

    # Training phase
    p.add_argument("--train_type", default="lora",
                   choices=["lora", "full"],
                   help="lora=LoRA on LLM; full=all params. "
                        "Vision encoder is always unfrozen for GAA gradient flow.")

    # Pretrained components
    p.add_argument("--projector_path", default=None,
                   help="Path to projector.bin from Phase 1 projector pre-training.")
    p.add_argument("--resume_lora_path", default=None,
                   help="Resume existing LoRA adapter instead of initializing fresh.")

    # Data
    p.add_argument("--data_path",   required=True, help="chat.json with bboxes field")
    p.add_argument("--image_dir",   required=True, help="Image directory")
    p.add_argument("--max_seq_len", type=int, default=2048)

    # GAA hyperparameters (paper Table 2 optimal values)
    p.add_argument("--geo_loss_weight", type=float, default=0.5,
                   help="λ: geometric loss weight (Eq. 6). Paper optimum = 0.5.")
    p.add_argument("--geo_tau", type=float, default=0.5,
                   help="IoU threshold τ for foreground mask (Eq. 4). Default = 0.5.")
    p.add_argument("--feature_size", type=int, default=-1,
                   help="ViT patch grid side. -1 = auto-detect from vision encoder "
                        "(24 for CLIP-ViT-L/14-336).")

    # Training schedule
    p.add_argument("--output_dir",    default="checkpoints/gaa_run")
    p.add_argument("--num_epochs",    type=float, default=3.0)
    p.add_argument("--batch_size",    type=int,   default=4,
                   help="Per-device train batch size")
    p.add_argument("--grad_accum",    type=int,   default=4)
    p.add_argument("--learning_rate", type=float, default=2e-4)
    p.add_argument("--warmup_ratio",  type=float, default=0.03)
    p.add_argument("--lr_scheduler",  default="cosine",
                   choices=["cosine", "linear", "constant"])
    p.add_argument("--save_steps",    type=int, default=500)
    p.add_argument("--logging_steps", type=int, default=10)
    p.add_argument("--max_steps",     type=int, default=-1)

    # LoRA
    p.add_argument("--lora_r",       type=int,   default=128)
    p.add_argument("--lora_alpha",   type=int,   default=256)
    p.add_argument("--lora_dropout", type=float, default=0.05)

    # Hardware
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--gradient_checkpointing", action="store_true", default=True)
    p.add_argument("--dataloader_workers", type=int, default=4)

    # DeepSpeed
    p.add_argument("--deepspeed", default=None,
                   help="Path to DeepSpeed config JSON (e.g. scripts/zero2.json)")

    # W&B
    p.add_argument("--wandb_project",    default=None)
    p.add_argument("--wandb_run_name",   default=None)
    p.add_argument("--wandb_watch",      default="gradients",
                   choices=["none", "gradients", "all", "parameters"])
    p.add_argument("--wandb_watch_freq", type=int, default=100)

    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    DTYPE_MAP = {
        "bfloat16": torch.bfloat16,
        "float16":  torch.float16,
        "float32":  torch.float32,
    }
    dtype = DTYPE_MAP[args.dtype]

    # ── Build model ───────────────────────────────────────────────────────────
    # GAA requires the vision encoder to be unfrozen so that L_geo gradients
    # can propagate back and suppress background attention weights.
    config = VLMConfig(
        vision_model_name=args.vision_model,
        llm_model_name=args.llm_model,
        projector_type=args.projector_type,
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=False,
        freeze_llm=(args.train_type == "lora"),
        max_seq_len=args.max_seq_len,
    )
    model = build_model(config, torch_dtype=dtype)

    # GAA requires output_attentions from CLIP, which is only supported with
    # eager (non-SDPA) attention.  Reload the vision model with eager attention
    # so _get_clip_attentions() can extract per-layer attention maps.
    if args.train_type in ("lora", "full"):
        from transformers import CLIPVisionModel
        print("[GAA] Reloading CLIP with eager attention (required for output_attentions) ...")
        clip_eager = CLIPVisionModel.from_pretrained(
            args.vision_model,
            torch_dtype=dtype,
            attn_implementation="eager",
        )
        clip_device = next(model.vision_encoder.model.parameters()).device
        model.vision_encoder.model = clip_eager.to(clip_device)
        print("[GAA] CLIP reloaded with eager attention.")

    # Auto-detect feature_size from vision encoder if not specified
    if args.feature_size == -1:
        args.feature_size = int(math.isqrt(model.vision_encoder.num_image_tokens))
        print(f"[GAA] Auto-detected feature_size = {args.feature_size} "
              f"(from {model.vision_encoder.num_image_tokens} image tokens)")

    # ── Load pretrained projector ─────────────────────────────────────────────
    if args.projector_path:
        print(f"[GAA] Loading projector from {args.projector_path}")
        state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
        model.projector.load_weights(state)

    # ── Apply LoRA to LLM ─────────────────────────────────────────────────────
    if args.train_type == "lora":
        for p in model.language_model.parameters():
            p.requires_grad = False

        if args.resume_lora_path:
            print(f"[GAA] Resuming LoRA from {args.resume_lora_path}")
            from peft import PeftModel
            model.language_model = PeftModel.from_pretrained(
                model.language_model, args.resume_lora_path, is_trainable=True
            )
        else:
            print("[GAA] Applying fresh LoRA ...")
            lora_cfg = LoraConfig(
                r=args.lora_r,
                lora_alpha=args.lora_alpha,
                lora_dropout=args.lora_dropout,
                target_modules=[
                    "q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj",
                ],
                bias="none",
                task_type="CAUSAL_LM",
            )
            model.language_model = get_peft_model(model.language_model, lora_cfg)
        model.language_model.print_trainable_parameters()

    elif args.train_type == "full":
        for p in model.language_model.parameters():
            p.requires_grad = True

    # Projector and vision encoder always trainable for GAA
    for p in model.projector.parameters():
        p.requires_grad = True
    for p in model.vision_encoder.parameters():
        p.requires_grad = True

    model.print_trainable_parameters()

    # ── W&B ──────────────────────────────────────────────────────────────────
    init_wandb(args, config)
    watch_model_wandb(model, args)

    # ── Dataset & collator ────────────────────────────────────────────────────
    tokenizer       = model.tokenizer
    image_processor = model.vision_encoder.image_processor

    dataset = GAADataset(
        data_path=args.data_path,
        image_dir=args.image_dir,
        tokenizer=tokenizer,
        image_processor=image_processor,
        max_seq_len=args.max_seq_len,
    )
    collator = GAADataCollator(pad_token_id=tokenizer.pad_token_id)

    # ── Training arguments ────────────────────────────────────────────────────
    report_to = []
    try:
        import tensorboard  # noqa: F401
        report_to.append("tensorboard")
    except ImportError:
        pass
    if args.wandb_project:
        report_to.append("wandb")
    if not report_to:
        report_to = ["none"]

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.num_epochs,
        learning_rate=args.learning_rate,
        lr_scheduler_type=args.lr_scheduler,
        warmup_ratio=args.warmup_ratio,
        bf16=(args.dtype == "bfloat16"),
        fp16=(args.dtype == "float16"),
        tf32=True,
        save_strategy="steps",
        save_steps=args.save_steps,
        max_steps=args.max_steps,
        logging_steps=args.logging_steps,
        report_to=report_to,
        dataloader_num_workers=args.dataloader_workers,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
        gradient_checkpointing=args.gradient_checkpointing,
        deepspeed=args.deepspeed,
    )

    # ── Trainer ───────────────────────────────────────────────────────────────
    callbacks = (
        [WandbGPUCallback(log_freq=args.logging_steps)]
        if args.wandb_project else []
    )

    trainer = GAATrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        train_type=args.train_type,
        geo_loss_weight=args.geo_loss_weight,
        geo_tau=args.geo_tau,
        feature_size=args.feature_size,
        callbacks=callbacks,
    )

    last_ckpt = (
        get_last_checkpoint(args.output_dir)
        if os.path.isdir(args.output_dir) else None
    )
    if last_ckpt:
        print(f"[GAA] Resuming from checkpoint: {last_ckpt}")

    trainer.train(resume_from_checkpoint=last_ckpt)

    # ── Final save ────────────────────────────────────────────────────────────
    if _is_main_process():
        os.makedirs(args.output_dir, exist_ok=True)

        torch.save(
            model.projector.state_dict(),
            os.path.join(args.output_dir, "projector.bin"),
        )
        tokenizer.save_pretrained(args.output_dir)

        if args.train_type in ("lora", "full"):
            model.language_model.save_pretrained(args.output_dir)

        cfg_path = os.path.join(args.output_dir, "vlm_config.json")
        with open(cfg_path, "w") as f:
            json.dump(
                {k: v for k, v in vars(config).items() if not k.startswith("_")},
                f, indent=2,
            )

        print(f"\n[GAA] Training complete. Outputs saved to: {args.output_dir}")

    if args.wandb_project and _is_main_process():
        import wandb
        wandb.finish()


if __name__ == "__main__":
    main()
