import logging
import sys
from dataclasses import dataclass, field
from typing import Optional
import torch
import copy
import json

import datasets
from datasets import load_dataset

import transformers
from transformers import (
    HfArgumentParser,
    LlamaForCausalLM, 
    LlamaTokenizer,
    LlamaConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)

from peft import (
    get_peft_model,
    LoraConfig
)

from flash_attn_patch import replace_llama_attn_with_flash_attn

logger = logging.getLogger(__name__)

@dataclass
class ModelArguments:
    model_name_or_path: str = field(
        metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    lora_r: int = field(
        default=8,
        metadata={"help": "Lora attention dimension"}
    )
    lora_alpha: int = field(
        default=16,
        metadata={"help": "The alpha parameter for Lora scaling"}
    )
    lora_dropout: float = field(
        default=0.05,
        metadata={"help": "The dropout probability for Lora layers."}
    )
    if_lora: Optional[int] = field(default=1, metadata={"help": "Whether run lora or full training."})

@dataclass
class DataTrainingArguments:
    model_max_length: int = field(
        default=4096,
        metadata={
            "help": "Maximum sequence length. Sequences will be right padded (and possibly truncated)."
        },
    )
    max_train_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "For debugging purposes or quicker training, truncate the number of training examples to this "
                "value if set."
            )
        },
    )
    preprocessed_path: str = field(
        default=None, metadata={"help": "Path to the preprocessed training data."}
    )
    train_data_path: Optional[str] = field(default=None, metadata={"help": "The input training data file (a jsonlines)."})
    eval_data_path: Optional[str] = field(default=None, metadata={"help": "The input evaluation data file (a jsonlines)."})
    preprocessing_num_workers: Optional[int] = field(
        default=None,
        metadata={"help": "The number of processes to use for the preprocessing."},
    )

def main():
    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    replace_llama_attn_with_flash_attn()
    
    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if training_args.should_log:
        # The default of training_args.log_level is passive, so we set log level at info here to have that default.
        transformers.utils.logging.set_verbosity_info()
    
    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()
    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16 or training_args.bf16}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")

    # load config and tokenziers
    config = LlamaConfig.from_pretrained(model_args.model_name_or_path)
    config.use_cache = False
    # use truncation_side='left' to preserve linking between end of prompt and target labels
    tokenizer = LlamaTokenizer.from_pretrained(model_args.model_name_or_path, truncation_side='left')
    # initialize modules
    model = LlamaForCausalLM.from_pretrained(model_args.model_name_or_path, config=config)

    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    else:
        def make_inputs_require_grad(module, input, output):
            output.requires_grad_(True)
        model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
    model.gradient_checkpointing_enable()

    # add pad token in tokenizer if needed
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({"pad_token": tokenizer.eos_token})
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Setup seed
    set_seed(training_args.seed)
    if len(tokenizer) > tokenizer.vocab_size:
        model.resize_token_embeddings(len(tokenizer))

    # load dataset
    logger.info("start data preprocess")
    label_ignore_id = -100
    bos_token = tokenizer.bos_token
    eos_token = tokenizer.eos_token

    def preprocess_function(examples):
        inputs = [bos_token + example[0]["value"] + example[1]["value"] + eos_token for example in examples["conversations"]]
        model_inputs = tokenizer(inputs, max_length=data_args.model_max_length, padding="longest", truncation=True, add_special_tokens=False)
        model_inputs["labels"] = copy.deepcopy(model_inputs["input_ids"])
        for e_i, example in enumerate(examples["conversations"]):
            source_text = bos_token + example[0]["value"]
            target_text = example[1]["value"] + eos_token
            source_ids = tokenizer.encode(source_text, add_special_tokens=False)
            target_ids = tokenizer.encode(target_text, add_special_tokens=False)
            if len(source_ids) >= data_args.model_max_length:
                model_inputs["labels"][e_i] = [label_ignore_id] * data_args.model_max_length
                continue
            else:
                model_inputs["labels"][e_i][:len(source_ids)] = [label_ignore_id] * len(source_ids)
                if len(target_ids) + len(source_ids) >= len(model_inputs["input_ids"][e_i]):
                    continue
                else:
                    model_inputs["labels"][e_i][(len(target_ids) + len(source_ids)):] = [label_ignore_id] * (len(model_inputs["input_ids"][e_i]) - len(target_ids) - len(source_ids))
        model_inputs["input_ids"] = torch.tensor(model_inputs["input_ids"])
        model_inputs["labels"] = torch.tensor(model_inputs["labels"])
        model_inputs["attention_mask"] = model_inputs["input_ids"].ne(tokenizer.pad_token_id)
        return model_inputs

    data_files = {}
    data_files["train"] = data_args.train_data_path
    raw_datasets = load_dataset(
        "json",
        data_files=data_files
    )
    column_names = raw_datasets["train"].column_names
    train_dataset = raw_datasets["train"].map(
        preprocess_function,
        batched=True,
        batch_size=len(raw_datasets["train"]),
        remove_columns=column_names,
        num_proc=data_args.preprocessing_num_workers,
        load_from_cache_file=False,
        desc="Running tokenizer on train dataset"
    )
    if data_args.max_train_samples is not None:
        max_train_samples = min(len(train_dataset), data_args.max_train_samples)
        train_dataset = train_dataset.select(range(max_train_samples))
    logger.info("load dataset finished")

    # lora
    peft_config = LoraConfig(
        r=model_args.lora_r,
        lora_alpha=model_args.lora_alpha,
        lora_dropout=model_args.lora_dropout,
        target_modules=[
            "q_proj",
            "v_proj"
        ],
        bias="none",
        task_type="CAUSAL_LM",
    )
    if model_args.if_lora != 0:
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()

    # Setup Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        tokenizer=tokenizer
    )

    # Training
    train_result = trainer.train()
    trainer.save_state()

    # save fp16 model under deepspeed zero2 or zero3
    c_stage = json.load(open(training_args.deepspeed, "r"))["zero_optimization"]["stage"]
    if c_stage in [2, 3]:
        if c_stage == 2:
            w_state_dict = trainer.model.state_dict()
        else:
            w_state_dict = trainer.model_wrapped._zero3_consolidated_16bit_state_dict()
        if trainer.is_world_process_zero():
            state_dict = {key: value.half().cpu() for key, value in w_state_dict.items()}
            trainer._save(training_args.output_dir, state_dict=state_dict)
    else:
        trainer.save_model()

if __name__ == "__main__":
    main()
