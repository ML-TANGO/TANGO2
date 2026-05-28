"""
train_text_lora.py — Text-only LoRA fine-tuning

Loads an existing LoRA checkpoint (from VLM Phase 2) and continues training
on text-only instruction data (no images).  Only the LLM + LoRA adapters are
involved — the vision encoder and projector are not loaded.

Usage:
  python train_text_lora.py \\
      --llm_model  /path/to/Llama-3.1-8B-Instruct \\
      --lora_path  checkpoints/clip_llama31_lora \\
      --data_path  /path/to/data.parquet \\
      --output_dir checkpoints/clip_llama31_lora_marine

Supported data formats:
  - .parquet  with columns  'instruction' / 'output'
  - .json     list of {"instruction": ..., "output": ...}
"""
import os
import sys
import json
import shutil
import argparse
from dataclasses import dataclass
from typing import Dict, List

import torch
import pandas as pd
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
)
from peft import PeftModel


# ── Dataset ───────────────────────────────────────────────────────────────────

class MarineTextDataset(Dataset):
    """Instruction-output dataset loaded from .parquet or .json."""

    def __init__(self, data_path: str, tokenizer, max_seq_len: int = 2048):
        if data_path.endswith(".parquet"):
            df = pd.read_parquet(data_path)
            self.records = df.to_dict("records")
        else:
            with open(data_path, encoding="utf-8") as f:
                self.records = json.load(f)

        self.tokenizer   = tokenizer
        self.max_seq_len = max_seq_len

        print(f"[Dataset] {len(self.records):,} samples from {data_path}")
        print(f"[Dataset] max_seq_len : {max_seq_len}")

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict:
        item = self.records[idx]
        instruction = item.get("instruction") or item.get("input") or ""
        output      = item.get("output")      or item.get("response") or ""

        # Build full conversation and prompt-only text using chat template
        full_msgs   = [
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": output},
        ]
        prompt_msgs = [{"role": "user", "content": instruction}]

        full_text   = self.tokenizer.apply_chat_template(
            full_msgs,   tokenize=False, add_generation_prompt=False
        )
        prompt_text = self.tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )

        full_ids = self.tokenizer(
            full_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids[0]
        prompt_ids = self.tokenizer(
            prompt_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids[0]

        if len(full_ids) > self.max_seq_len:
            full_ids = full_ids[: self.max_seq_len]

        prompt_len = min(len(prompt_ids), len(full_ids))

        labels = full_ids.clone()
        labels[:prompt_len] = -100   # mask instruction; only response contributes to loss

        return {"input_ids": full_ids, "labels": labels}


# ── Collator ──────────────────────────────────────────────────────────────────

@dataclass
class TextCollator:
    pad_token_id: int

    def __call__(self, batch: List[Dict]) -> Dict[str, torch.Tensor]:
        max_len = max(b["input_ids"].shape[0] for b in batch)

        padded_ids, padded_labels, attn_masks = [], [], []
        for b in batch:
            ids = b["input_ids"]
            lbl = b["labels"]
            pad = max_len - ids.shape[0]
            if pad > 0:
                ids = torch.cat([ids, torch.full((pad,), self.pad_token_id, dtype=ids.dtype)])
                lbl = torch.cat([lbl, torch.full((pad,), -100,             dtype=lbl.dtype)])
            padded_ids.append(ids)
            padded_labels.append(lbl)
            attn_masks.append((ids != self.pad_token_id).long())

        return {
            "input_ids":      torch.stack(padded_ids),
            "attention_mask": torch.stack(attn_masks),
            "labels":         torch.stack(padded_labels),
        }


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser("Text-only LoRA continued fine-tuning")

    p.add_argument("--llm_model",   required=True,
                   help="Base LLM model path (same one used in Phase 2)")
    p.add_argument("--lora_path",   required=True,
                   help="Existing LoRA checkpoint dir to continue from")
    p.add_argument("--data_path",   required=True,
                   help="Training data path (.parquet or .json)")
    p.add_argument("--output_dir",  required=True,
                   help="Output directory for updated LoRA adapter")

    p.add_argument("--max_seq_len",    type=int,   default=2048)
    p.add_argument("--batch_size",     type=int,   default=2)
    p.add_argument("--grad_accum",     type=int,   default=8)
    p.add_argument("--learning_rate",  type=float, default=5e-5)
    p.add_argument("--num_epochs",     type=int,   default=1)
    p.add_argument("--save_steps",     type=int,   default=500)
    p.add_argument("--logging_steps",  type=int,   default=10)
    p.add_argument("--warmup_ratio",   type=float, default=0.03)
    p.add_argument("--max_steps",      type=int,   default=-1,
                   help="Override epoch-based training with a fixed step count")
    p.add_argument("--dtype",    default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--gradient_checkpointing", action="store_true")
    p.add_argument("--dataloader_workers", type=int, default=4)
    p.add_argument("--wandb_project", default=None)
    p.add_argument("--deepspeed", default=None)

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

    os.makedirs(args.output_dir, exist_ok=True)

    if args.wandb_project:
        os.environ.setdefault("WANDB_PROJECT", args.wandb_project)

    # ── Tokenizer ─────────────────────────────────────────────────────────────
    print(f"[Train] Tokenizer : {args.llm_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.llm_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token    = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # ── Base LLM ──────────────────────────────────────────────────────────────
    print(f"[Train] Base model: {args.llm_model}")
    base_model = AutoModelForCausalLM.from_pretrained(
        args.llm_model,
        torch_dtype=dtype,
        attn_implementation="flash_attention_2",
    )

    # Resize embeddings if the tokenizer has extra tokens (e.g. <image>)
    # The saved adapter_config knows the original vocab size; we must match.
    import json as _json
    _adapter_cfg_path = os.path.join(args.lora_path, "adapter_config.json")
    if os.path.exists(_adapter_cfg_path):
        with open(_adapter_cfg_path) as _f:
            _acfg = _json.load(_f)
        # Check tokenizer_config for vocab size mismatch and resize if needed
        _tok_cfg_path = os.path.join(args.lora_path, "tokenizer_config.json")
        if os.path.exists(_tok_cfg_path):
            _saved_tok = AutoTokenizer.from_pretrained(args.lora_path)
            if len(_saved_tok) != len(tokenizer):
                print(f"[Train] Resizing embeddings: {len(base_model.get_input_embeddings().weight)} → {len(_saved_tok)}")
                base_model.resize_token_embeddings(len(_saved_tok))
            del _saved_tok

    # ── Load existing LoRA and enable continued training ──────────────────────
    print(f"[Train] Loading LoRA: {args.lora_path}")
    model = PeftModel.from_pretrained(base_model, args.lora_path, is_trainable=True)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"[Train] Parameters : {trainable:,} trainable / {total:,} total "
          f"({100 * trainable / total:.2f}%)")

    if args.gradient_checkpointing:
        model.enable_input_require_grads()
        model.gradient_checkpointing_enable()

    # ── Dataset ───────────────────────────────────────────────────────────────
    dataset  = MarineTextDataset(args.data_path, tokenizer, args.max_seq_len)
    collator = TextCollator(pad_token_id=tokenizer.pad_token_id)

    # ── Training arguments ────────────────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_epochs,
        max_steps=args.max_steps,
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        bf16=(dtype == torch.bfloat16),
        fp16=(dtype == torch.float16),
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        dataloader_num_workers=args.dataloader_workers,
        remove_unused_columns=False,
        report_to="wandb" if args.wandb_project else "none",
        deepspeed=args.deepspeed,
        gradient_checkpointing=args.gradient_checkpointing,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    print("[Train] Starting ...")
    trainer.train()

    # ── Save LoRA adapter ─────────────────────────────────────────────────────
    print(f"[Train] Saving LoRA adapter → {args.output_dir}")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # Copy projector.bin from the source LoRA checkpoint so the output dir
    # is self-contained and can be used directly with the VLM demo / service.
    proj_src = os.path.join(args.lora_path, "projector.bin")
    proj_dst = os.path.join(args.output_dir, "projector.bin")
    if os.path.exists(proj_src) and not os.path.exists(proj_dst):
        shutil.copy2(proj_src, proj_dst)
        print(f"[Train] Copied projector.bin → {proj_dst}")

    print("[Train] Done.")


if __name__ == "__main__":
    main()
