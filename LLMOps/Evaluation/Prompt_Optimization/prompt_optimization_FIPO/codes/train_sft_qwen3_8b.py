#!/usr/bin/env python
import torch
from dataclasses import dataclass, field
from typing import Dict, Sequence, Optional, List
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, HfArgumentParser, Trainer, TrainingArguments, set_seed

IGNORE_INDEX = -100

@dataclass
class MyTrainingArguments(TrainingArguments):
    output_dir: str = field(default="/scratch/x3397a11/minkyu/workspace/ETRI/promptopti/model")
    num_train_epochs: float = field(default=3)
    per_device_train_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=16)
    learning_rate: float = field(default=2e-5)
    weight_decay: float = field(default=0.0)
    warmup_ratio: float = field(default=0.04)
    lr_scheduler_type: str = field(default="cosine")
    logging_steps: int = field(default=10)
    save_steps: int = field(default=500)
    save_total_limit: int = field(default=2)
    bf16: bool = field(default=True)
    tf32: bool = field(default=False)
    gradient_checkpointing: bool = field(default=True)
    report_to: str = field(default="none")

@dataclass
class ModelArguments:
    model_name_or_path: str = field(default="Qwen/Qwen3-8B")
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
    target_column: str = field(default="gpt4_optimized_prompt")
    model_max_length: int = field(default=2048)
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


def build_source_text(tokenizer, raw_prompt: str, use_chat_template: bool = True) -> str:
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



class SupervisedDataset(torch.utils.data.Dataset):
    def __init__(
        self,
        raw_texts: Sequence[str],
        targets: Sequence[str],
        tokenizer,
        model_max_length: int,
        use_chat_template: bool
    ):
        self.input_ids = []
        self.labels = []
        eos = tokenizer.eos_token or ""

        for src, tgt in zip(raw_texts, targets):
            source = build_source_text(tokenizer, src, use_chat_template=use_chat_template)
            full_text = source + tgt + eos

            tokenized_full = tokenizer(
                full_text,
                max_length=model_max_length,
                truncation=True,
                add_special_tokens=False,
            )
            tokenized_source = tokenizer(
                source,
                max_length=model_max_length,
                truncation=True,
                add_special_tokens=False,
            )

            input_ids = tokenized_full["input_ids"]
            source_len = min(len(tokenized_source["input_ids"]), len(input_ids))
            labels = input_ids.copy()
            labels[:source_len] = [IGNORE_INDEX] * source_len

            self.input_ids.append(torch.tensor(input_ids, dtype=torch.long))
            self.labels.append(torch.tensor(labels, dtype=torch.long))

    def __len__(self):
        return len(self.input_ids)

    def __getitem__(self, i) -> Dict[str, torch.Tensor]:
        return {"input_ids": self.input_ids[i], "labels": self.labels[i]}

class DataCollatorForSupervisedDataset:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, instances: Sequence[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
        input_ids = [instance["input_ids"] for instance in instances]
        labels = [instance["labels"] for instance in instances]

        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids,
            batch_first=True,
            padding_value=self.tokenizer.pad_token_id,
        )
        labels = torch.nn.utils.rnn.pad_sequence(
            labels,
            batch_first=True,
            padding_value=IGNORE_INDEX,
        )
        attention_mask = input_ids.ne(self.tokenizer.pad_token_id)

        return {
            "input_ids": input_ids,
            "labels": labels,
            "attention_mask": attention_mask,
        }

def main():
    parser = HfArgumentParser((ModelArguments, DataArguments, MyTrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()
    set_seed(training_args.seed)

    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path,
        use_fast=True,
        trust_remote_code=model_args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    tokenizer.truncation_side = "left"
    tokenizer.model_max_length = data_args.model_max_length

    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        trust_remote_code=model_args.trust_remote_code,
        torch_dtype="auto",
    )
    model.config.use_cache = False

    if training_args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

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

    ds = load_dataset(data_args.dataset_name, split=data_args.dataset_split)
    if data_args.max_train_samples is not None:
        ds = ds.select(range(min(len(ds), data_args.max_train_samples)))

    raw_prompts = ds[data_args.raw_prompt_column]
    targets = ds[data_args.target_column]

    train_dataset = SupervisedDataset(
        raw_prompts,
        targets,
        tokenizer,
        data_args.model_max_length,
        data_args.use_chat_template,
    )
    data_collator = DataCollatorForSupervisedDataset(tokenizer)

    trainer = Trainer(
        model=model,
        processing_class=tokenizer,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )

    trainer.train(resume_from_checkpoint=training_args.resume_from_checkpoint)
    trainer.save_state()
    trainer.save_model(training_args.output_dir)
    tokenizer.save_pretrained(training_args.output_dir)

if __name__ == "__main__":
    main()