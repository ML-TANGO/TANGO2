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
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
    TrainerCallback
)

from peft import (
    get_peft_model,
    LoraConfig
)
from peft.tuners.lora import LoraLayer
from dpo_trainer import DPOTrainer
from flash_attn_patch import replace_llama_attn_with_flash_attn

from deepspeed import zero
from deepspeed.runtime.zero.partition_parameters import ZeroParamStatus

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
    loss_type: Optional[str] = field(default="sigmoid", metadata={"help": "The loss type, either dpo or ipo."})
    if_lora: Optional[int] = field(default=1, metadata={"help": "Whether run lora or full training."})
    beta: Optional[float] = field(default=0.1, metadata={"help": "beta in DPO/IPO loss"})

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

def maybe_zero_3(param):
    if hasattr(param, "ds_id"):
        assert param.ds_status == ZeroParamStatus.NOT_AVAILABLE
        with zero.GatheredParameters([param]):
            param = param.data.cpu().clone().detach()
    return param

def get_peft_state_maybe_zero_3(state_dict, bias):
    if bias == "none":
        to_return = {
            k: state_dict[k].cpu().clone().detach() for k in state_dict if "lora_" in k
        }
    elif bias == "all":
        to_return = {
            k: state_dict[k] for k in state_dict if "lora_" in k or "bias" in k
        }
    elif bias == "lora_only":
        to_return = {}
        for k in state_dict:
            if "lora_" in k:
                to_return[k] = state_dict[k]
                bias_name = k.split("lora_")[0] + "bias"
                if bias_name in state_dict:
                    to_return[bias_name] = state_dict[bias_name]
    else:
        raise NotImplementedError
    to_return = {k: maybe_zero_3(v) for k, v in to_return.items()}
    return to_return

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

    def preprocess_function(examples):
        prepared_inputs = {"prompt": [], "chosen": [], "rejected": []}
        for p, g, r in zip(examples["prompt"], examples["chosen"], examples["rejected"]):
            prepared_inputs["prompt"].append(p)
            prepared_inputs["chosen"].append(g)
            prepared_inputs["rejected"].append(r)
        return prepared_inputs
    
    label_ignore_id = -100

    print("start data preprocess")
    data_files = {}
    data_files["train"] = data_args.train_data_path
    raw_datasets = load_dataset(
        "json",
        data_files=data_files
    )
    column_names = raw_datasets["train"].column_names
    prepared_dataset = raw_datasets.map(
        preprocess_function,
        batched=True,
        batch_size=len(raw_datasets["train"]),
        remove_columns=column_names,
        num_proc=data_args.preprocessing_num_workers,
        desc="Running tokenizer on train dataset"
    )
    if data_args.max_train_samples is not None:
        max_train_samples = min(len(prepared_dataset["train"]), data_args.max_train_samples)
        prepared_dataset["train"] = prepared_dataset["train"].select(range(max_train_samples))
    logger.info("load dataset finished")

    # load config and tokenziers
    config = LlamaConfig.from_pretrained(model_args.model_name_or_path)
    config.use_cache = False
    # use truncation_side='left' to preserve linking between end of prompt and target labels
    tokenizer = LlamaTokenizer.from_pretrained(model_args.model_name_or_path, truncation_side='left', padding_side='left')
    # initialize modules
    model = LlamaForCausalLM.from_pretrained(model_args.model_name_or_path, config=config)
    if model_args.if_lora == 0:
        ref_model = LlamaForCausalLM.from_pretrained(model_args.model_name_or_path, config=config)

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
        if model_args.if_lora == 0:
            ref_model.resize_token_embeddings(len(tokenizer))

    # Setup Trainer
    training_args = training_args.to_dict()
    training_args.update({'remove_unused_columns': False})
    training_args = TrainingArguments(**training_args)
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
        ref_model = None
    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        beta=model_args.beta, # DPO temprature
        train_dataset=prepared_dataset["train"],
        tokenizer=tokenizer,
        args=training_args,
        max_length=data_args.model_max_length,
        max_prompt_length=int(data_args.model_max_length) * 3 // 4,
        loss_type=model_args.loss_type
    )

    # Training
    train_result = trainer.train()
    trainer.save_state()
    
    # save fp16 model under deepspeed zero2 or zero3
    c_stage = json.load(open(training_args.deepspeed, "r"))["zero_optimization"]["stage"]
    if c_stage in [2, 3]:
        if c_stage == 2:
            w_state_dict = get_peft_state_maybe_zero_3(trainer.model.named_parameters(), "none")
        else:
            w_state_dict = trainer.model_wrapped._zero3_consolidated_16bit_state_dict()
        if trainer.is_world_process_zero():
            state_dict = {key: value.half().cpu() for key, value in w_state_dict.items()}
            trainer._save(training_args.output_dir, state_dict=state_dict)
    else:
        trainer.save_model()

if __name__ == "__main__":
    main()
