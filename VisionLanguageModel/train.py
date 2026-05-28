"""
train.py — VisionLanguageModelV2 Training Script

Two training phases:
  Phase 1 (--train_type projector):
    - Freeze CLIP + LLM, train only the projector
    - LR ~ 1e-3, 1 epoch on 595K CC3M images
    - Saves: checkpoints/<run>/projector.bin

  Phase 2 (--train_type lora):
    - Freeze CLIP, add LoRA to LLM, train projector + LoRA
    - LR ~ 2e-4, fine-tune on domain data
    - Loads projector from Phase 1 (--projector_path)
    - Saves: checkpoints/<run>/ (LoRA adapter + projector)

Usage (single GPU):
  /home/ywlee/miniconda3/envs/eva/bin/python train.py \\
      --train_type projector \\
      --data_path /home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json \\
      --image_dir /home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images \\
      --output_dir checkpoints/clip_llama_projector \\
      --wandb_project vlm-v2

Usage (multi-GPU with DeepSpeed):
  See scripts/train_projector.sh
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import torch
import torch.distributed as dist
from torch.utils.data import DataLoader
from transformers import (
    TrainingArguments, Trainer, AutoTokenizer, TrainerCallback
)
from transformers.trainer_utils import get_last_checkpoint
from peft import LoraConfig, get_peft_model

from model import VLMConfig, build_model, VisionLanguageModelV2
from data import LLaVADataset, DataCollatorForVLM


# ── Argument parsing ──────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser("VisionLanguageModelV2 Trainer")

    # Model
    p.add_argument("--vision_model", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model",    default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--projector_type", default="mlp2x_gelu",
                   choices=["linear", "mlp2x_gelu", "mlp3x_gelu"])

    # Training phase
    p.add_argument("--train_type", default="projector",
                   choices=["projector", "lora", "full"],
                   help="projector=freeze LLM; lora=LoRA on LLM; full=all params")

    # Phase 2: load pretrained projector
    p.add_argument("--projector_path", default=None,
                   help="Path to projector.bin from Phase 1 (required for lora/full)")

    # Data
    p.add_argument("--data_path",  required=True,  help="chat.json path")
    p.add_argument("--image_dir",  required=True,  help="Image folder")
    p.add_argument("--max_seq_len", type=int, default=2048)

    # Training
    p.add_argument("--output_dir", default="checkpoints/run")
    p.add_argument("--num_epochs", type=float, default=1.0)
    p.add_argument("--batch_size", type=int, default=4,
                   help="Per-device batch size")
    p.add_argument("--grad_accum", type=int, default=4)
    p.add_argument("--learning_rate", type=float, default=None,
                   help="Override LR (defaults: projector=1e-3, lora=2e-4)")
    p.add_argument("--warmup_ratio", type=float, default=0.03)
    p.add_argument("--lr_scheduler", default="cosine",
                   choices=["cosine", "linear", "constant"])
    p.add_argument("--save_steps",    type=int, default=500)
    p.add_argument("--logging_steps", type=int, default=10)
    p.add_argument("--max_steps", type=int, default=-1)

    # LoRA
    p.add_argument("--lora_r",       type=int,   default=128)
    p.add_argument("--lora_alpha",   type=int,   default=256)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--resume_lora_path", default=None,
                   help="Load existing LoRA adapter and continue training "
                        "(skips fresh LoRA init; adapter_config.json must exist)")

    # Hardware
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--gradient_checkpointing", action="store_true", default=True)
    p.add_argument("--dataloader_workers", type=int, default=4)

    # DeepSpeed
    p.add_argument("--deepspeed", default=None,
                   help="Path to DeepSpeed config JSON")

    # W&B
    p.add_argument("--wandb_project",  default=None,
                   help="wandb project name (omit to disable wandb)")
    p.add_argument("--wandb_run_name", default=None,
                   help="wandb run name (auto-generated if omitted)")
    p.add_argument("--wandb_watch",    default="gradients",
                   choices=["none", "gradients", "all", "parameters"],
                   help="wandb.watch mode for gradient/weight histograms")
    p.add_argument("--wandb_watch_freq", type=int, default=100,
                   help="Log histograms every N steps")

    return p.parse_args()


# ── W&B GPU memory callback ───────────────────────────────────────────────────

class WandbGPUCallback(TrainerCallback):
    """
    Logs per-step GPU memory (allocated / reserved) to wandb.
    Also logs gradient norm when available.
    """

    def __init__(self, log_freq: int = 10):
        self.log_freq = log_freq

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is None or not _is_main_process():
            return

        import wandb
        if not wandb.run:
            return

        extra = {}

        # GPU memory for each visible device
        for i in range(torch.cuda.device_count()):
            alloc = torch.cuda.memory_allocated(i) / 1e9
            resv  = torch.cuda.memory_reserved(i)  / 1e9
            extra[f"gpu/{i}/mem_allocated_GB"] = alloc
            extra[f"gpu/{i}/mem_reserved_GB"]  = resv

        wandb.log(extra, step=state.global_step)


def _is_main_process() -> bool:
    """True on rank-0 (or non-distributed)."""
    if dist.is_available() and dist.is_initialized():
        return dist.get_rank() == 0
    return True


# ── HF-Trainer compatible wrapper ────────────────────────────────────────────

class VLMTrainer(Trainer):
    """
    Thin wrapper over HF Trainer.
    - compute_loss: delegates to model.forward() which returns VLMOutput
    - _save_checkpoint: saves only trained components
    """

    def __init__(self, *args, train_type="projector", **kwargs):
        super().__init__(*args, **kwargs)
        self.train_type = train_type

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        outputs = model(**inputs)
        loss = outputs.loss
        return (loss, outputs) if return_outputs else loss

    def _save_checkpoint(self, model, trial):
        """Save only the components that were trained."""
        checkpoint_dir = self._get_output_dir(trial)
        os.makedirs(checkpoint_dir, exist_ok=True)

        if not _is_main_process():
            super()._save_checkpoint(model, trial)
            return

        # Always save tokenizer
        if hasattr(model, "tokenizer"):
            model.tokenizer.save_pretrained(checkpoint_dir)

        if self.train_type == "projector":
            proj_state = model.projector.state_dict()
            torch.save(proj_state, os.path.join(checkpoint_dir, "projector.bin"))
            print(f"[Trainer] Saved projector → {checkpoint_dir}/projector.bin")

        elif self.train_type in ("lora", "full"):
            proj_state = model.projector.state_dict()
            torch.save(proj_state, os.path.join(checkpoint_dir, "projector.bin"))

            if self.train_type == "lora":
                if hasattr(model.language_model, "save_pretrained"):
                    model.language_model.save_pretrained(checkpoint_dir)
                    print(f"[Trainer] Saved LoRA adapter → {checkpoint_dir}")
            else:
                model.language_model.save_pretrained(checkpoint_dir)
                print(f"[Trainer] Saved full LLM → {checkpoint_dir}")

        super()._save_checkpoint(model, trial)


# ── W&B initialization ────────────────────────────────────────────────────────

def init_wandb(args, config: VLMConfig):
    """Initialize wandb run (main process only)."""
    if not args.wandb_project or not _is_main_process():
        return

    import wandb

    # Auto run name: "<train_type>-<vision_short>-<llm_short>"
    if args.wandb_run_name is None:
        vision_short = args.vision_model.split("/")[-1]
        llm_short    = os.path.basename(args.llm_model)
        run_name = f"{args.train_type}-{vision_short}-{llm_short}"
    else:
        run_name = args.wandb_run_name

    wandb.init(
        project=args.wandb_project,
        name=run_name,
        config={
            # Model
            "vision_model":       config.vision_model_name,
            "llm_model":          config.llm_model_name,
            "projector_type":     config.projector_type,
            "vision_hidden_size": config.vision_hidden_size,
            "llm_hidden_size":    config.llm_hidden_size,
            "num_image_tokens":   config.num_image_tokens,
            # Training
            "train_type":         args.train_type,
            "batch_size":         args.batch_size,
            "grad_accum":         args.grad_accum,
            "effective_batch":    args.batch_size * args.grad_accum,
            "learning_rate":      args.learning_rate,
            "lr_scheduler":       args.lr_scheduler,
            "warmup_ratio":       args.warmup_ratio,
            "num_epochs":         args.num_epochs,
            "max_seq_len":        args.max_seq_len,
            "dtype":              args.dtype,
            # LoRA (if applicable)
            "lora_r":             args.lora_r if args.train_type == "lora" else None,
            "lora_alpha":         args.lora_alpha if args.train_type == "lora" else None,
        },
        resume="allow",
    )
    print(f"[W&B] Run: {wandb.run.get_url()}")
    return run_name


def watch_model_wandb(model, args):
    """Log model gradients / weights to wandb."""
    if not args.wandb_project or args.wandb_watch == "none" or not _is_main_process():
        return

    import wandb
    if not wandb.run:
        return

    # Only watch trainable parts to avoid logging frozen Llama weights (too large)
    wandb.watch(
        model.projector,
        log=args.wandb_watch,      # "gradients", "all", "parameters"
        log_freq=args.wandb_watch_freq,
        log_graph=False,
    )
    print(f"[W&B] Watching projector (log={args.wandb_watch}, freq={args.wandb_watch_freq})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype = DTYPE_MAP[args.dtype]

    # Default LR per phase
    if args.learning_rate is None:
        args.learning_rate = {"projector": 1e-3, "lora": 2e-4, "full": 2e-5}[args.train_type]

    # ── Build model ────────────────────────────────────────────────────────────
    config = VLMConfig(
        vision_model_name=args.vision_model,
        llm_model_name=args.llm_model,
        projector_type=args.projector_type,
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=True,
        freeze_llm=(args.train_type == "projector"),
        max_seq_len=args.max_seq_len,
    )

    model = build_model(config, torch_dtype=dtype)

    # ── Load pretrained projector (Phase 2) ───────────────────────────────────
    if args.projector_path:
        print(f"[Train] Loading projector weights from {args.projector_path}")
        state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
        model.projector.load_weights(state)

    # ── Apply LoRA (Phase 2) ──────────────────────────────────────────────────
    if args.train_type == "lora":
        for p in model.language_model.parameters():
            p.requires_grad = False

        if args.resume_lora_path:
            print(f"[Train] Resuming LoRA from {args.resume_lora_path} …")
            from peft import PeftModel as _PeftModel
            model.language_model = _PeftModel.from_pretrained(
                model.language_model, args.resume_lora_path, is_trainable=True
            )
        else:
            print("[Train] Applying fresh LoRA …")
            lora_config = LoraConfig(
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
            model.language_model = get_peft_model(model.language_model, lora_config)

        model.language_model.print_trainable_parameters()

    elif args.train_type == "full":
        for p in model.language_model.parameters():
            p.requires_grad = True

    # Always train the projector
    for p in model.projector.parameters():
        p.requires_grad = True

    model.print_trainable_parameters()

    # ── W&B init ───────────────────────────────────────────────────────────────
    init_wandb(args, config)
    watch_model_wandb(model, args)

    # ── Dataset ───────────────────────────────────────────────────────────────
    tokenizer       = model.tokenizer
    image_processor = model.vision_encoder.image_processor

    dataset = LLaVADataset(
        data_path=args.data_path,
        image_dir=args.image_dir,
        tokenizer=tokenizer,
        image_processor=image_processor,
        max_seq_len=args.max_seq_len,
    )

    collator = DataCollatorForVLM(pad_token_id=tokenizer.pad_token_id)

    # ── Training arguments ─────────────────────────────────────────────────────
    # TensorBoard는 항상 출력 (플랫폼 대시보드 자동 연동).
    # W&B는 --wandb_project 지정 시 추가로 활성화. 두 backend 공존 가능.
    report_to: list[str] = []
    if args.wandb_project:
        report_to.append("wandb")
    if not getattr(args, "no_tensorboard", False):
        report_to.append("tensorboard")
    if not report_to:
        report_to = "none"

    training_args = TrainingArguments(
        output_dir=args.output_dir,

        # Batch / accumulation
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,

        # Epochs / steps
        num_train_epochs=args.num_epochs,

        # Learning rate
        learning_rate=args.learning_rate,
        lr_scheduler_type=args.lr_scheduler,
        warmup_ratio=args.warmup_ratio,

        # Precision
        bf16=(args.dtype == "bfloat16"),
        fp16=(args.dtype == "float16"),
        tf32=True,

        # Saving / logging
        save_strategy="steps",
        save_steps=args.save_steps,
        max_steps=args.max_steps,
        logging_steps=args.logging_steps,
        report_to=report_to,

        # DataLoader
        dataloader_num_workers=args.dataloader_workers,
        dataloader_pin_memory=True,

        # Misc
        remove_unused_columns=False,
        gradient_checkpointing=args.gradient_checkpointing,

        # DeepSpeed
        deepspeed=args.deepspeed,
    )

    # ── Trainer ────────────────────────────────────────────────────────────────
    callbacks = [WandbGPUCallback(log_freq=args.logging_steps)] if args.wandb_project else []

    trainer = VLMTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        train_type=args.train_type,
        callbacks=callbacks,
    )

    # Resume from checkpoint if exists
    last_ckpt = get_last_checkpoint(args.output_dir) if os.path.isdir(args.output_dir) else None
    if last_ckpt:
        print(f"[Train] Resuming from checkpoint: {last_ckpt}")

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

        cfg_dict = {k: v for k, v in vars(config).items() if not k.startswith("_")}
        with open(os.path.join(args.output_dir, "vlm_config.json"), "w") as f:
            json.dump(cfg_dict, f, indent=2)

        print(f"\n[Train] Done. Outputs saved to {args.output_dir}")

    if args.wandb_project and _is_main_process():
        import wandb
        wandb.finish()


if __name__ == "__main__":
    main()
