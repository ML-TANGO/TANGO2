# -*- coding: utf-8 -*-
"""
train_qwen3_mixatis.py
----------------------
UGEN QA 패러다임으로 변환한 MixATIS 데이터로 Qwen3-8B 를 LoRA SFT 한다.

핵심 설계
- decoder-only(Qwen3) 이므로 seq2seq 가 아니라 causal LM SFT.
- completion-only loss: 프롬프트(system+user) 토큰은 라벨을 -100 으로 마스킹하고
  assistant 정답 토큰에만 loss 를 건다.
- Qwen3 thinking 모드 충돌 방지: apply_chat_template(enable_thinking=False).
- 8B 단일 GPU 학습을 위해 LoRA + (선택)4bit 양자화 + gradient checkpointing.
- OOM 회피: --optim paged_adamw_8bit (bitsandbytes) 기본 사용.

사용 예:
  python train_qwen3_mixatis.py \
      --model_name Qwen/Qwen3-8B \
      --data_dir ./UGEN/data/MixATIS_clean \
      --output_dir ./out/qwen3-8b-mixatis-lora \
      --epochs 3 --batch_size 2 --grad_accum 8 --use_4bit

학습 후 LoRA 어댑터가 output_dir 에 저장된다. (평가는 evaluate_qwen3_mixatis.py)
"""

import os
import argparse
from dataclasses import dataclass
from typing import List, Dict

import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

from ugen_data import build_training_examples

IGNORE_INDEX = -100


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model_name", default="Qwen/Qwen3-8B")
    p.add_argument("--data_dir", default="./UGEN/data/MixATIS_clean")
    p.add_argument("--output_dir", default="./out/qwen3-8b-mixatis-lora")
    p.add_argument("--train_split", default="train")
    p.add_argument("--max_len", type=int, default=768,
                   help="MixATIS 는 옵션 텍스트가 길어 768 권장(slot options 포함)")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch_size", type=int, default=2)
    p.add_argument("--grad_accum", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--warmup_ratio", type=float, default=0.03)
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--use_4bit", action="store_true",
                   help="bitsandbytes 4bit(QLoRA) 로딩. 80GB 미만 GPU 권장.")
    p.add_argument("--optim", default="paged_adamw_8bit",
                   help="OOM 회피용 8bit 옵티마이저. 메모리 여유 시 adamw_torch.")
    p.add_argument("--save_steps", type=int, default=500)
    p.add_argument("--logging_steps", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--debug", action="store_true", help="앞 200개 예제만 사용")
    return p.parse_args()


def build_tokenized_dataset(examples: List[Dict], tokenizer, max_len: int) -> Dataset:
    """
    chat 메시지를 토크나이즈하고 completion-only 라벨 마스크를 만든다.
    - 전체(system+user+assistant) 시퀀스를 input_ids 로,
    - 프롬프트(system+user, add_generation_prompt=True) 길이만큼 라벨을 -100 으로.
    """
    def encode(ex):
        messages = ex["messages"]
        # 1) chat 템플릿을 "문자열"로 렌더링한다.
        #    tokenize=True 경로는 일부 tokenizers 버전에서 List[int] 가 아니라
        #    tokenizers.Encoding 객체를 돌려주어 Arrow 직렬화가 실패한다.
        #    (OverflowError / "Could not convert Encoding ... type tokenizers.Encoding")
        #    문자열로 받은 뒤 직접 토크나이즈하면 항상 순수 List[int] 가 보장된다.
        full_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,   # Qwen3 thinking 토큰 비활성
        )
        # 프롬프트 부분만 (assistant 직전까지)
        prompt_text = tokenizer.apply_chat_template(
            messages[:-1],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        # 2) 렌더링된 문자열을 토크나이즈. 템플릿이 이미 special token 을
        #    포함하므로 add_special_tokens=False.
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        full_ids = full_ids[:max_len]
        labels = list(full_ids)
        prompt_len = min(len(prompt_ids), len(full_ids))
        for i in range(prompt_len):
            labels[i] = IGNORE_INDEX
        return {"input_ids": full_ids, "labels": labels,
                "attention_mask": [1] * len(full_ids)}

    ds = Dataset.from_list(examples)
    ds = ds.map(encode, remove_columns=ds.column_names,
                desc="tokenizing")
    return ds


@dataclass
class CausalCollator:
    """가변 길이 배치를 오른쪽 패딩(학습용)으로 묶는다."""
    tokenizer: any

    def __call__(self, features):
        max_len = max(len(f["input_ids"]) for f in features)
        pad_id = self.tokenizer.pad_token_id
        input_ids, labels, attn = [], [], []
        for f in features:
            diff = max_len - len(f["input_ids"])
            input_ids.append(f["input_ids"] + [pad_id] * diff)
            labels.append(f["labels"] + [IGNORE_INDEX] * diff)
            attn.append(f["attention_mask"] + [0] * diff)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attn, dtype=torch.long),
        }


def main():
    args = parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    torch.manual_seed(args.seed)

    # --- 토크나이저 ---
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"   # 학습 시 right padding + 라벨 마스킹

    # --- 데이터 ---
    examples = build_training_examples(args.data_dir, args.train_split)
    if args.debug:
        examples = examples[:200]
    print(f"[data] SFT 예제 {len(examples)}개 (발화 {len(examples)//2})")
    train_ds = build_tokenized_dataset(examples, tokenizer, args.max_len)

    # --- 모델 로딩 ---
    quant_config = None
    if args.use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=quant_config,
        dtype=torch.bfloat16,          # torch_dtype 은 최신 transformers 에서 deprecated
        device_map={"": 0},
        trust_remote_code=True,
    )
    model.config.use_cache = False           # gradient checkpointing 과 충돌 방지
    if args.use_4bit:
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=True)
    else:
        model.gradient_checkpointing_enable()

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # --- 학습 설정 ---
    targs = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type="cosine",
        bf16=True,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        optim=args.optim,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        data_collator=CausalCollator(tokenizer),
    )
    trainer.train()

    # --- 저장(LoRA 어댑터 + 토크나이저) ---
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"[done] LoRA 어댑터 저장 완료 -> {args.output_dir}")


if __name__ == "__main__":
    main()
