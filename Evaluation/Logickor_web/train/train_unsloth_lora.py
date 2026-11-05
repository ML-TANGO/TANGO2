import argparse
import inspect
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dataloader import read_jsonl, split_by_question_id, validate_rows
from prompt import ensure_training_chat_template
from util import load_config, make_sft_args, restore_kv_shared_norm_weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a LoRA SFT model with Unsloth.")
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    parser.add_argument("--output-dir", required=True, help="Directory to write run outputs.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--resume-from-checkpoint", default=None, help="Checkpoint path to resume from.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config/data/splits only and exit.")
    parser.add_argument("--save-merged", action="store_true", help="Also save a merged 16-bit model.")
    return parser.parse_args()


def _load_unsloth_model(model_name: str, max_seq_length: int, load_in_4bit: bool) -> Any:
    try:
        from unsloth import FastModel

        return FastModel, *FastModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype="bfloat16",
            load_in_4bit=load_in_4bit,
            trust_remote_code=True,
        )
    except Exception as fast_model_exc:
        try:
            from unsloth import FastLanguageModel

            return FastLanguageModel, *FastLanguageModel.from_pretrained(
                model_name=model_name,
                max_seq_length=max_seq_length,
                dtype="bfloat16",
                load_in_4bit=load_in_4bit,
                trust_remote_code=True,
            )
        except Exception as fast_lm_exc:
            raise RuntimeError(
                "Failed to load model with Unsloth FastModel and FastLanguageModel."
            ) from fast_lm_exc


def _language_model_lora_targets(model: Any, lora_cfg: Dict[str, Any]) -> List[str]:
    suffixes = tuple(
        lora_cfg.get(
            "target_modules",
            ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
    )
    targets = []
    for name, module in model.named_modules():
        if ".language_model." not in name:
            continue
        if not name.endswith(suffixes):
            continue
        if not hasattr(module, "weight"):
            continue
        targets.append(name)
    if not targets:
        raise RuntimeError("No language_model LoRA target modules were found.")
    return sorted(set(targets))


def _apply_unsloth_lora(fast_cls: Any, model: Any, lora_cfg: Dict[str, Any], seed: int) -> Any:
    common_kwargs = {
        "r": int(lora_cfg["r"]),
        "lora_alpha": int(lora_cfg["alpha"]),
        "lora_dropout": float(lora_cfg["dropout"]),
        "bias": "none",
        "use_gradient_checkpointing": lora_cfg.get("use_gradient_checkpointing", True),
        "random_state": seed,
    }

    target_modules = _language_model_lora_targets(model, lora_cfg)
    print(json.dumps({"language_model_lora_target_count": len(target_modules), "language_model_lora_target_preview": target_modules[:30]}, ensure_ascii=False, indent=2))
    return fast_cls.get_peft_model(model, target_modules=target_modules, **common_kwargs)


def _assert_lora_scope(model: Any, require_language_model_only: bool) -> Dict[str, Any]:
    trainable_lora = [
        name
        for name, param in model.named_parameters()
        if param.requires_grad and "lora_" in name
    ]
    if not trainable_lora:
        raise RuntimeError("No trainable LoRA parameters were found.")

    bad = []
    if require_language_model_only:
        bad = [name for name in trainable_lora if ".language_model." not in name]
        if bad:
            preview = "\n".join(bad[:30])
            raise RuntimeError(f"LoRA attached outside language_model:\n{preview}")

    return {
        "trainable_lora_tensors": len(trainable_lora),
        "trainable_lora_preview": trainable_lora[:30],
        "language_model_only": require_language_model_only,
    }


def _tokenize_chat_rows(rows: List[Dict[str, Any]], tokenizer: Any, max_seq_length: int) -> List[Dict[str, Any]]:
    tokenized_rows: List[Dict[str, Any]] = []
    for row in rows:
        text = tokenizer.apply_chat_template(
            row["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        encoded = tokenizer(
            text=text,
            truncation=True,
            max_length=max_seq_length,
            add_special_tokens=False,
        )
        input_ids = encoded["input_ids"]
        if input_ids and isinstance(input_ids[0], list):
            input_ids = input_ids[0]
        attention_mask = encoded.get("attention_mask")
        if attention_mask and isinstance(attention_mask[0], list):
            attention_mask = attention_mask[0]
        if attention_mask is None:
            attention_mask = [1] * len(input_ids)
        tokenized_rows.append(
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
        )
    return tokenized_rows


def _checkpoints_enabled(training_cfg: Dict[str, Any]) -> bool:
    save_steps = int(training_cfg.get("save_steps", 0))
    save_total_limit = int(training_cfg.get("save_total_limit", 0))
    default = save_steps > 0 and save_total_limit != 0
    enabled = bool(training_cfg.get("save_checkpoints", default))
    if enabled and save_steps <= 0:
        raise ValueError("save_checkpoints is enabled, but training.save_steps must be greater than 0.")
    return enabled


def _early_stopping_config(config: Dict[str, Any], checkpoints_enabled: bool) -> Dict[str, Any] | None:
    early_cfg = config.get("early_stopping")
    if not early_cfg or not bool(early_cfg.get("enabled", True)):
        return None
    if not checkpoints_enabled:
        print("early_stopping is disabled because checkpoint saving is disabled.")
        return None
    return early_cfg


def train(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    model_name = config["model"]
    data_path = config["data_path"]
    max_seq_length = int(config["max_seq_length"])
    train_ratio = float(config["split"]["train_ratio"])
    training_cfg = config["training"]
    lora_cfg = config["lora"]

    rows = read_jsonl(data_path)
    dataset_stats = validate_rows(rows)
    train_rows, eval_rows, split_stats = split_by_question_id(rows, train_ratio=train_ratio, seed=args.seed)
    save_checkpoints = _checkpoints_enabled(training_cfg)
    early_cfg = _early_stopping_config(config, save_checkpoints)

    output_dir = Path(args.output_dir)
    adapter_dir = output_dir / "adapter"
    merged_dir = output_dir / "merged"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        dry_run_meta = {
            "mode": "dry_run",
            "seed": args.seed,
            "model": model_name,
            "data_path": data_path,
            "dataset_stats": dataset_stats,
            "split_stats": split_stats,
        }
        with (output_dir / "dry_run_meta.json").open("w", encoding="utf-8") as f:
            json.dump(dry_run_meta, f, ensure_ascii=False, indent=2)
        print(json.dumps(dry_run_meta, ensure_ascii=False, indent=2))
        return

    cuda_visible_devices = training_cfg.get("cuda_visible_devices")
    if cuda_visible_devices is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_visible_devices)
    os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

    import unsloth  # noqa: F401 - must be imported before TRL/Transformers for Unsloth patching.
    from datasets import Dataset
    from transformers import EarlyStoppingCallback, set_seed
    from trl import SFTConfig, SFTTrainer

    set_seed(args.seed)

    load_in_4bit = bool(config.get("load_in_4bit", lora_cfg.get("load_in_4bit", False)))
    fast_cls, model, tokenizer = _load_unsloth_model(model_name, max_seq_length, load_in_4bit)
    ensure_training_chat_template(tokenizer, model_name)
    model = _apply_unsloth_lora(fast_cls, model, lora_cfg, args.seed)
    lora_scope = _assert_lora_scope(
        model,
        require_language_model_only=bool(lora_cfg.get("require_language_model_only", True)),
    )
    print(json.dumps(lora_scope, ensure_ascii=False, indent=2))

    train_ds = Dataset.from_list(_tokenize_chat_rows(train_rows, tokenizer, max_seq_length))
    eval_ds = Dataset.from_list(_tokenize_chat_rows(eval_rows, tokenizer, max_seq_length))

    run_kwargs: Dict[str, Any] = {
        "output_dir": str(output_dir),
        "num_train_epochs": int(training_cfg["num_train_epochs"]),
        "per_device_train_batch_size": int(training_cfg["per_device_train_batch_size"]),
        "per_device_eval_batch_size": int(training_cfg["per_device_eval_batch_size"]),
        "gradient_accumulation_steps": int(training_cfg["gradient_accumulation_steps"]),
        "gradient_checkpointing": bool(training_cfg["gradient_checkpointing"]),
        "learning_rate": float(training_cfg["learning_rate"]),
        "lr_scheduler_type": str(training_cfg["lr_scheduler_type"]),
        "optim": str(training_cfg.get("optim", "adamw_torch")),
        "weight_decay": float(training_cfg["weight_decay"]),
        "logging_steps": int(training_cfg["logging_steps"]),
        "eval_steps": int(training_cfg["eval_steps"]),
        "eval_strategy": "steps",
        "evaluation_strategy": "steps",
        "save_strategy": "steps" if save_checkpoints else "no",
        "load_best_model_at_end": bool(training_cfg.get("load_best_model_at_end", save_checkpoints)) if save_checkpoints else False,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "bf16": bool(training_cfg.get("bf16", True)),
        "fp16": bool(training_cfg.get("fp16", False)),
        "seed": args.seed,
        "max_seq_length": max_seq_length,
        "assistant_only_loss": bool(training_cfg.get("assistant_only_loss", False)),
        "dataset_kwargs": {"skip_prepare_dataset": False},
        "report_to": "none",
    }
    dataset_num_proc = training_cfg.get("dataset_num_proc")
    if dataset_num_proc is not None:
        run_kwargs["dataset_num_proc"] = int(dataset_num_proc)
    if "max_steps" in training_cfg:
        run_kwargs["max_steps"] = int(training_cfg["max_steps"])

    if save_checkpoints:
        run_kwargs["save_steps"] = int(training_cfg["save_steps"])
        save_total_limit = int(training_cfg.get("save_total_limit", 0))
        if save_total_limit > 0:
            run_kwargs["save_total_limit"] = save_total_limit

    warmup_ratio = float(training_cfg["warmup_ratio"])
    est_steps = max(1, int(len(train_rows) / int(training_cfg["per_device_train_batch_size"])))
    est_steps = max(1, int(est_steps / int(training_cfg["gradient_accumulation_steps"])))
    est_steps *= int(training_cfg["num_train_epochs"])
    run_kwargs["warmup_steps"] = max(1, int(est_steps * warmup_ratio))

    sft_args = make_sft_args(SFTConfig, run_kwargs)
    callbacks = []
    if early_cfg is not None:
        callbacks.append(
            EarlyStoppingCallback(
                early_stopping_patience=int(early_cfg["patience"]),
                early_stopping_threshold=float(early_cfg.get("threshold", 0.0)),
            )
        )

    trainer_kwargs = {
        "model": model,
        "args": sft_args,
        "train_dataset": train_ds,
        "eval_dataset": eval_ds,
        "callbacks": callbacks,
    }
    trainer_init_params = set(inspect.signature(SFTTrainer.__init__).parameters.keys())
    if "max_seq_length" in trainer_init_params:
        trainer_kwargs["max_seq_length"] = max_seq_length
    if "processing_class" in trainer_init_params:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_init_params:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = SFTTrainer(**trainer_kwargs)
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)

    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    if args.save_merged:
        merged_dir.mkdir(parents=True, exist_ok=True)
        if not hasattr(trainer.model, "save_pretrained_merged"):
            raise RuntimeError("This Unsloth model does not expose save_pretrained_merged().")
        trainer.model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")
        restore_kv_shared_norm_weights(merged_dir, model_name)

    run_meta = {
        "seed": args.seed,
        "model": model_name,
        "data_path": data_path,
        "dataset_stats": dataset_stats,
        "split_stats": split_stats,
        "lora_scope": lora_scope,
        "train_args": run_kwargs,
        "load_in_4bit": load_in_4bit,
        "save_checkpoints": save_checkpoints,
        "early_stopping_enabled": early_cfg is not None,
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_eval_loss": trainer.state.best_metric,
        "global_step": trainer.state.global_step,
        "adapter_dir": str(adapter_dir),
        "merged_dir": str(merged_dir) if args.save_merged else None,
    }
    with (output_dir / "run_meta.json").open("w", encoding="utf-8") as f:
        json.dump(run_meta, f, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    train(args, config)


if __name__ == "__main__":
    main()
