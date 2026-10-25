#!/usr/bin/env python

'''
python /scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/prompt_optimization_FIPO/codes/train_dpo_fipo.py \
    --base_model_name_or_path Qwen/Qwen3-8B \
    --sft_adapter_path /scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/model/FIPO_sft/checkpoint-5625 \
    --output_dir /scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/model/dpo
'''

'''
read_prompts_json : prompts.json 파일 읽음
DPO의 학습 입력 프롬프트는 prompts.json 파일의 template 기반으로 생성됨

input : prompts["optimizer"] template에 raw_prompt 넣은 text
    silver_response_column : silver_response 넣은 text
    golden_response_column : golden_response 넣은 text
    둘다 None : raw prompt만 생성
    
chosen label = gpt4_optimized_prompt
rejected label = chatgpt_optimized_prompt

output : DPO LoRA adapter
'''

import json
import os
import random
from dataclasses import dataclass, field
from typing import List, Optional

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    HfArgumentParser,
    set_seed,
)
from trl import DPOConfig, DPOTrainer


@dataclass
class ModelArguments:
    model_name_or_path: str = field(
        default="/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/model/FIPO_sft/checkpoint-5625"
    )
    base_model_name_or_path: str = field(default="Qwen/Qwen3-8B")
    sft_adapter_path: Optional[str] = field(default = "/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/model/FIPO_sft/checkpoint-5625")
    trust_remote_code: bool = field(default=False)
    lora_r: int = field(default=16)
    lora_alpha: int = field(default=32)
    lora_dropout: float = field(default=0.05)
    if_lora: int = field(default=1)


@dataclass
class DataArguments:
    dataset_name: str = field(default="Junrulu/Prompt_Preference_Dataset")
    dataset_split: str = field(default="train")
    raw_prompt_column: str = field(default="raw_prompt")
    chosen_column: str = field(default="gpt4_optimized_prompt")
    rejected_column: str = field(default="chatgpt_optimized_prompt")
    silver_response_column: Optional[str] = field(default="text003_response_based_raw")
    golden_response_column: Optional[str] = field(default="gpt4_response_based_raw")
    max_train_samples: Optional[int] = field(default=None)
    preprocessing_num_workers: int = field(default=4)
    use_chat_template: bool = field(default=True)
    prompt_template_path: str = field(default="/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/prompt_optimization_FIPO/data/prompts.json")
    fallback_max_words: int = field(default=256)
    context_mix_mode: str = field(
        default="mixed",
        metadata={"help": "none|silver|golden|both|mixed (FIPO dataset diversification)"},
    )
    p_none: float = field(default=0.25)
    p_silver: float = field(default=0.25)
    p_golden: float = field(default=0.25)
    p_both: float = field(default=0.25)
    context_mix_seed: int = field(default=42)


def read_prompts_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    required = ["optimizer", "s_r", "g_r"]
    missing = [k for k in required if k not in obj]
    if missing:
        raise ValueError(f"Missing keys in prompts.json: {missing}")
    return obj


def build_fipo_optimizer_text(
    raw_prompt: str,
    prompts: dict,
    silver_response: Optional[str] = None,
    golden_response: Optional[str] = None,
    max_words: int = 256,
) -> str:
    optional_context = ""
    if silver_response:
        optional_context += prompts["s_r"].replace("S_R", silver_response)
    if golden_response:
        optional_context += prompts["g_r"].replace("G_R", golden_response)

    text = prompts["optimizer"]
    text = text.replace("S_P", raw_prompt)
    text = text.replace("O_C", optional_context)
    text = text.replace("G_N", str(max_words))
    return text


def build_chat_messages(optimizer_text: str):
    return [{"role": "user", "content": optimizer_text}]


def build_optimizer_prompt(tokenizer, optimizer_text: str, use_chat_template: bool = True) -> str:
    messages = build_chat_messages(optimizer_text)
    if use_chat_template and hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    return optimizer_text + "\n"


def find_lora_target_modules(model) -> List[str]:
    candidate_keywords = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "up_proj",
        "down_proj",
        "gate_proj",
        "wq",
        "wk",
        "wv",
        "wo",
    ]
    found = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            short = name.split(".")[-1]
            if short in candidate_keywords:
                found.add(short)
    if not found:
        found.update(["q_proj", "v_proj"])
    return sorted(found)


def get_optional_value(example: dict, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    value = example.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def choose_context_flags(data_args: DataArguments, rng: random.Random):
    mode = data_args.context_mix_mode.lower()
    if mode == "none":
        return False, False
    if mode == "silver":
        return True, False
    if mode == "golden":
        return False, True
    if mode == "both":
        return True, True
    if mode != "mixed":
        raise ValueError(
            f"Invalid context_mix_mode={data_args.context_mix_mode}. "
            "Expected one of: none|silver|golden|both|mixed"
        )

    probs = [data_args.p_none, data_args.p_silver, data_args.p_golden, data_args.p_both]
    if any(p < 0 for p in probs):
        raise ValueError("p_none/p_silver/p_golden/p_both must be >= 0")
    total = sum(probs)
    if total <= 0:
        raise ValueError("At least one of p_none/p_silver/p_golden/p_both must be > 0")

    x = rng.random() * total
    bounds = [probs[0], probs[0] + probs[1], probs[0] + probs[1] + probs[2], total]
    if x < bounds[0]:
        return False, False
    if x < bounds[1]:
        return True, False
    if x < bounds[2]:
        return False, True
    return True, True


def main():
    parser = HfArgumentParser((ModelArguments, DataArguments, DPOConfig))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()
    set_seed(training_args.seed)

    tokenizer_load_path = model_args.model_name_or_path
    if model_args.sft_adapter_path:
        tokenizer_load_path = model_args.sft_adapter_path

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_load_path,
        use_fast=True,
        trust_remote_code=model_args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    tokenizer.truncation_side = "left"

    # SFT 결과가 LoRA adapter만 저장된 경우, base + adapter 조합으로 로드
    if model_args.sft_adapter_path:
        base_for_adapter = AutoModelForCausalLM.from_pretrained(
            model_args.base_model_name_or_path,
            trust_remote_code=model_args.trust_remote_code,
            torch_dtype="auto",
        )
        model = PeftModel.from_pretrained(
            base_for_adapter,
            model_args.sft_adapter_path,
            is_trainable=True,
        )
    else:
        # 기본: SFT로 저장된 모델(merged/full)을 직접 로드
        model = AutoModelForCausalLM.from_pretrained(
            model_args.model_name_or_path,
            trust_remote_code=model_args.trust_remote_code,
            torch_dtype="auto",
        )
    model.config.use_cache = False

    if training_args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    ref_model = None
    # 이미 SFT adapter를 로드한 경우에는 새 LoRA를 덧씌우지 않음
    if model_args.sft_adapter_path:
        model.print_trainable_parameters()
    elif model_args.if_lora != 0:
        target_modules = find_lora_target_modules(model)
        peft_config = LoraConfig(
            r=model_args.lora_r,
            lora_alpha=model_args.lora_alpha,
            lora_dropout=model_args.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=target_modules,
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
    else:
        ref_model = AutoModelForCausalLM.from_pretrained(
            model_args.model_name_or_path,
            trust_remote_code=model_args.trust_remote_code,
            torch_dtype="auto",
        )

    template_path = data_args.prompt_template_path
    if not os.path.isabs(template_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.normpath(os.path.join(base_dir, template_path))
    prompts = read_prompts_json(template_path)

    ds = load_dataset(data_args.dataset_name, split=data_args.dataset_split)
    if data_args.max_train_samples is not None:
        ds = ds.select(range(min(len(ds), data_args.max_train_samples)))

    def map_row(example, idx):
        chosen_text = str(example[data_args.chosen_column]).strip()
        max_words = max(1, len(chosen_text.split())) if chosen_text else data_args.fallback_max_words
        rng = random.Random(data_args.context_mix_seed + idx)
        use_silver, use_golden = choose_context_flags(data_args, rng)
        silver_text = (
            get_optional_value(example, data_args.silver_response_column)
            if use_silver
            else None
        )
        golden_text = (
            get_optional_value(example, data_args.golden_response_column)
            if use_golden
            else None
        )
        optimizer_text = build_fipo_optimizer_text(
            raw_prompt=str(example[data_args.raw_prompt_column]),
            prompts=prompts,
            silver_response=silver_text,
            golden_response=golden_text,
            max_words=max_words,
        )
        return {
            "prompt": build_optimizer_prompt(
                tokenizer,
                optimizer_text=optimizer_text,
                use_chat_template=data_args.use_chat_template,
            ),
            "chosen": chosen_text,
            "rejected": str(example[data_args.rejected_column]).strip(),
        }

    ds = ds.map(
        map_row,
        with_indices=True,
        remove_columns=ds.column_names,
        num_proc=data_args.preprocessing_num_workers,
    )

    # trl>=0.24: beta/loss_type는 DPOConfig(args)에서 읽음
    print(f"[DPO 설정] beta={training_args.beta}, loss_type={training_args.loss_type}")
    print(
        f"[DPO context] mode={data_args.context_mix_mode}, "
        f"silver={data_args.silver_response_column}, golden={data_args.golden_response_column}"
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=training_args,
        train_dataset=ds,
        processing_class=tokenizer,
    )

    trainer.train(resume_from_checkpoint=training_args.resume_from_checkpoint)
    trainer.save_model(training_args.output_dir)
    tokenizer.save_pretrained(training_args.output_dir)


if __name__ == "__main__":
    main()
