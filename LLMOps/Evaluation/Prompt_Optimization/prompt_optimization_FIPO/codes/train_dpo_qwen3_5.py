import logging
import sys
from dataclasses import dataclass, field
from typing import Optional, List

import datasets
from datasets import load_dataset
import torch
import transformers
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    HfArgumentParser,
    TrainingArguments,
    set_seed,
)
from peft import LoraConfig, get_peft_model
from dpo_trainer import DPOTrainer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a prompt optimizer. Rewrite a raw user prompt into a clearer, more detailed, "
    "and more effective instruction prompt while preserving the original task intent."
)


@dataclass
class ModelArguments:
    model_name_or_path: str = field(metadata={"help": "HF model id or local path."})
    trust_remote_code: bool = field(default=True)
    lora_r: int = field(default=16)
    lora_alpha: int = field(default=32)
    lora_dropout: float = field(default=0.05)
    loss_type: str = field(default="sigmoid", metadata={"help": "sigmoid for DPO, ipo for IPO."})
    if_lora: int = field(default=1)
    beta: float = field(default=0.1)


@dataclass
class DataTrainingArguments:
    dataset_name: str = field(default="Junrulu/Prompt_Preference_Dataset")
    dataset_split: str = field(default="train")
    raw_prompt_column: str = field(default="raw_prompt")
    chosen_column: str = field(default="gpt4_optimized_prompt")
    rejected_column: str = field(default="chatgpt_optimized_prompt")
    model_max_length: int = field(default=2048)
    max_train_samples: Optional[int] = field(default=None)
    preprocessing_num_workers: Optional[int] = field(default=4)


def find_lora_targets(model) -> List[str]:
    preferred_suffixes = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ]
    found = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            suffix = name.split(".")[-1]
            if suffix in preferred_suffixes:
                found.add(suffix)
    if found:
        return sorted(found)
    fallback = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            suffix = name.split(".")[-1]
            if suffix != "lm_head":
                fallback.add(suffix)
    return sorted(fallback)


def build_prompt(raw_prompt: str) -> str:
    return (
        f"System: {SYSTEM_PROMPT}\n\n"
        f"User: Rewrite the following raw prompt into an optimized instruction prompt.\n\n"
        f"Raw prompt:\n{raw_prompt}\n\n"
        f"Optimized prompt:\n"
    )


def main():
    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if training_args.should_log:
        transformers.utils.logging.set_verbosity_info()

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f" distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16 or training_args.bf16}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")

    set_seed(training_args.seed)

    raw_dataset = load_dataset(data_args.dataset_name, split=data_args.dataset_split)
    if data_args.max_train_samples is not None:
        raw_dataset = raw_dataset.select(range(min(len(raw_dataset), data_args.max_train_samples)))

    def preprocess_function(examples):
        return {
            "prompt": [build_prompt(x) for x in examples[data_args.raw_prompt_column]],
            "chosen": examples[data_args.chosen_column],
            "rejected": examples[data_args.rejected_column],
        }

    prepared_dataset = raw_dataset.map(
        preprocess_function,
        batched=True,
        remove_columns=raw_dataset.column_names,
        num_proc=data_args.preprocessing_num_workers,
        load_from_cache_file=False,
        desc="Preparing DPO dataset",
    )

    config = AutoConfig.from_pretrained(model_args.model_name_or_path, trust_remote_code=model_args.trust_remote_code)
    config.use_cache = False
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path,
        trust_remote_code=model_args.trust_remote_code,
        use_fast=False,
        truncation_side="left",
        padding_side="left",
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        config=config,
        trust_remote_code=model_args.trust_remote_code,
    )
    ref_model = None
    if model_args.if_lora == 0:
        ref_model = AutoModelForCausalLM.from_pretrained(
            model_args.model_name_or_path,
            config=config,
            trust_remote_code=model_args.trust_remote_code,
        )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
    model.config.pad_token_id = tokenizer.pad_token_id
    if ref_model is not None:
        ref_model.config.pad_token_id = tokenizer.pad_token_id

    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    else:
        def make_inputs_require_grad(module, _input, output):
            output.requires_grad_(True)
        model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
    model.gradient_checkpointing_enable()

    if len(tokenizer) > model.get_input_embeddings().weight.shape[0]:
        model.resize_token_embeddings(len(tokenizer))
        if ref_model is not None:
            ref_model.resize_token_embeddings(len(tokenizer))

    target_modules = find_lora_targets(model)
    logger.info(f"Detected LoRA target modules: {target_modules}")
    if model_args.if_lora != 0:
        peft_config = LoraConfig(
            r=model_args.lora_r,
            lora_alpha=model_args.lora_alpha,
            lora_dropout=model_args.lora_dropout,
            target_modules=target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
        ref_model = None

    args_dict = training_args.to_dict()
    args_dict.update({"remove_unused_columns": False})
    training_args = TrainingArguments(**args_dict)

    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        beta=model_args.beta,
        train_dataset=prepared_dataset,
        tokenizer=tokenizer,
        args=training_args,
        max_length=data_args.model_max_length,
        max_prompt_length=int(data_args.model_max_length) * 3 // 4,
        loss_type=model_args.loss_type,
    )

    trainer.train()
    trainer.save_state()
    trainer.save_model(training_args.output_dir)
    tokenizer.save_pretrained(training_args.output_dir)


if __name__ == "__main__":
    main()
