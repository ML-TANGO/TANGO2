#!/usr/bin/env python
import torch
from dataclasses import dataclass, field
from typing import Optional, List
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, HfArgumentParser, TrainingArguments, set_seed
from trl import DPOTrainer

@dataclass
class ModelArguments:
    model_name_or_path: str = field(default="Qwen/Qwen3-8B")
    trust_remote_code: bool = field(default=False)
    lora_r: int = field(default=16)
    lora_alpha: int = field(default=32)
    lora_dropout: float = field(default=0.05)
    if_lora: int = field(default=1)
    beta: float = field(default=0.01)
    loss_type: str = field(default="sigmoid")

@dataclass
class DataArguments:
    dataset_name: str = field(default="Junrulu/Prompt_Preference_Dataset")
    dataset_split: str = field(default="train")
    raw_prompt_column: str = field(default="raw_prompt")
    chosen_column: str = field(default="gpt4_optimized_prompt")
    rejected_column: str = field(default="chatgpt_optimized_prompt")
    max_train_samples: Optional[int] = field(default=None)
    preprocessing_num_workers: int = field(default=4)
    use_chat_template: bool = field(default=True)

def build_messages(raw_prompt: str):
    system = (
        "You are a prompt optimizer. Rewrite the user's raw prompt into a clearer, "
        "more detailed, and more effective instruction prompt. Return only the rewritten optimized prompt."
    )
    user = f"Raw prompt:\n{raw_prompt}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

def build_optimizer_prompt(tokenizer, raw_prompt: str, use_chat_template: bool = True) -> str:
    messages = build_messages(raw_prompt)
    if use_chat_template and hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    return (
        "You are a prompt optimizer.\n"
        "Rewrite the user's raw prompt into a clearer, more detailed, and more effective instruction prompt.\n"
        "Return only the rewritten optimized prompt.\n\n"
        f"Raw prompt:\n{raw_prompt}\n\nOptimized prompt:\n"
    )

def find_lora_target_modules(model) -> List[str]:
    candidate_keywords = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "up_proj", "down_proj", "gate_proj",
        "wq", "wk", "wv", "wo"
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

def main():
    parser = HfArgumentParser((ModelArguments, DataArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()
    set_seed(training_args.seed)

    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path,
        use_fast=True,
        trust_remote_code=model_args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    tokenizer.truncation_side = "left"

    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        trust_remote_code=model_args.trust_remote_code,
        torch_dtype="auto",
    )
    model.config.use_cache = False

    if training_args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    ref_model = None
    if model_args.if_lora != 0:
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

    ds = load_dataset(data_args.dataset_name, split=data_args.dataset_split)
    if data_args.max_train_samples is not None:
        ds = ds.select(range(min(len(ds), data_args.max_train_samples)))

    def map_row(example):
        return {
            "prompt": build_optimizer_prompt(
                tokenizer,
                example[data_args.raw_prompt_column],
                use_chat_template=data_args.use_chat_template,
            ),
            "chosen": example[data_args.chosen_column],
            "rejected": example[data_args.rejected_column],
        }

    ds = ds.map(
        map_row,
        remove_columns=ds.column_names,
        num_proc=data_args.preprocessing_num_workers,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=training_args,
        beta=model_args.beta,
        loss_type=model_args.loss_type,
        train_dataset=ds,
        processing_class=tokenizer,
    )

    trainer.train(resume_from_checkpoint=training_args.resume_from_checkpoint)
    trainer.save_model(training_args.output_dir)
    tokenizer.save_pretrained(training_args.output_dir)

if __name__ == "__main__":
    main()