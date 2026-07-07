import argparse
import inspect
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from dataloader import read_jsonl, split_by_question_id, validate_rows
from prompt import ensure_training_chat_template
from util import (
    ensure_embedding_accessors,
    load_causal_lm_model,
    load_config,
    load_peft_model_for_merge,
    make_sft_args,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a LoRA SFT pilot model for LogicKor data.")
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    parser.add_argument("--output-dir", required=True, help="Directory to write run outputs.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--resume-from-checkpoint",
        default=None,
        help="Checkpoint path to resume from.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config/data/splits only and exit without training.",
    )
    return parser.parse_args()


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


def cleanup_best_checkpoints(output_dir: str, best_model_checkpoint: str | None) -> None:
    if not best_model_checkpoint:
        return

    best_path = Path(best_model_checkpoint).resolve()
    for checkpoint_dir in Path(output_dir).glob("checkpoint-*"):
        try:
            if checkpoint_dir.resolve() != best_path:
                shutil.rmtree(checkpoint_dir)
        except FileNotFoundError:
            pass


def make_best_checkpoint_callback(enabled: bool) -> Any | None:
    if not enabled:
        return None

    from transformers import TrainerCallback

    class BestCheckpointOnlyCallback(TrainerCallback):
        def on_save(self, args, state, control, **kwargs):
            cleanup_best_checkpoints(args.output_dir, state.best_model_checkpoint)
            return control

        def on_train_end(self, args, state, control, **kwargs):
            cleanup_best_checkpoints(args.output_dir, state.best_model_checkpoint)
            return control

    return BestCheckpointOnlyCallback()



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
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = output_dir / "adapter"
    merged_dir = output_dir / "merged"

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

    # Avoid pulling vision backends in a text-only SFT pipeline.
    os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoProcessor, AutoTokenizer, EarlyStoppingCallback, set_seed
        from trl import SFTConfig, SFTTrainer
    except Exception as exc:
        msg = str(exc)
        if "torchvision::nms does not exist" in msg or "BloomPreTrainedModel" in msg:
            raise RuntimeError(
                "Detected a torch/torchvision/transformers compatibility issue.\n"
                "For this text-only LoRA training, remove torchvision or reinstall matching torch/torchvision versions.\n"
                "Recommended quick fix:\n"
                "  pip uninstall -y torchvision\n"
                "Then re-run training."
            ) from exc
        raise

    set_seed(args.seed)

    has_cuda = bool(torch.cuda.is_available())
    bf16_requested = bool(training_cfg.get("bf16", True))
    fp16_requested = bool(training_cfg.get("fp16", False))
    bf16 = bool(has_cuda and torch.cuda.is_bf16_supported() and bf16_requested)
    fp16 = bool(has_cuda and (not bf16) and fp16_requested)
    if has_cuda:
        model_dtype = torch.bfloat16 if bf16 else torch.float16
    else:
        model_dtype = torch.float32

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    processor = None
    try:
        processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    except Exception:
        processor = None
    ensure_training_chat_template(tokenizer, model_name)

    model = load_causal_lm_model(AutoModelForCausalLM, model_name, model_dtype)
    model.config.use_cache = False
    ensure_embedding_accessors(model)

    train_ds = Dataset.from_list(train_rows)
    eval_ds = Dataset.from_list(eval_rows)

    target_modules = lora_cfg.get("target_modules_regex")
    if target_modules is None:
        target_modules = list(lora_cfg["target_modules"])

    peft_config = LoraConfig(
        r=int(lora_cfg["r"]),
        lora_alpha=int(lora_cfg["alpha"]),
        lora_dropout=float(lora_cfg["dropout"]),
        target_modules=target_modules,
        bias="none",
        task_type="CAUSAL_LM",
    )

    run_kwargs: Dict[str, Any] = {
        "output_dir": str(output_dir),
        "num_train_epochs": int(training_cfg["num_train_epochs"]),
        "per_device_train_batch_size": int(training_cfg["per_device_train_batch_size"]),
        "per_device_eval_batch_size": int(training_cfg["per_device_eval_batch_size"]),
        "gradient_accumulation_steps": int(training_cfg["gradient_accumulation_steps"]),
        "gradient_checkpointing": bool(training_cfg["gradient_checkpointing"]),
        "learning_rate": float(training_cfg["learning_rate"]),
        "lr_scheduler_type": str(training_cfg["lr_scheduler_type"]),
        "optim": str(training_cfg["optim"]),
        "weight_decay": float(training_cfg["weight_decay"]),
        "logging_steps": int(training_cfg["logging_steps"]),
        "eval_steps": int(training_cfg["eval_steps"]),
        "eval_strategy": "steps",
        "evaluation_strategy": "steps",
        "save_strategy": "steps" if save_checkpoints else "no",
        "load_best_model_at_end": bool(training_cfg.get("load_best_model_at_end", save_checkpoints)) if save_checkpoints else False,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "bf16": bf16,
        "fp16": fp16,
        "seed": args.seed,
        "max_length": max_seq_length,
        "max_seq_length": max_seq_length,
        "assistant_only_loss": bool(training_cfg.get("assistant_only_loss", True)),
        "completion_only_loss": bool(training_cfg.get("completion_only_loss", False)),
        "dataset_kwargs": {"skip_prepare_dataset": False},
        "report_to": "none",
    }
    # Keep backward compatibility across transformer versions.
    sft_config_params = set(SFTConfig.__init__.__code__.co_varnames)
    if save_checkpoints:
        run_kwargs["save_steps"] = int(training_cfg["save_steps"])
        save_total_limit = int(training_cfg.get("save_total_limit", 0))
        if save_total_limit > 0:
            run_kwargs["save_total_limit"] = save_total_limit

    warmup_ratio = float(training_cfg["warmup_ratio"])
    if "warmup_ratio" in sft_config_params:
        run_kwargs["warmup_ratio"] = warmup_ratio
    else:
        # Fallback when warmup_ratio is removed/deprecated.
        est_steps = max(1, int(len(train_rows) / int(training_cfg["per_device_train_batch_size"])))
        est_steps = max(1, int(est_steps / int(training_cfg["gradient_accumulation_steps"])))
        est_steps *= int(training_cfg["num_train_epochs"])
        run_kwargs["warmup_steps"] = max(1, int(est_steps * warmup_ratio))

    sft_args = make_sft_args(SFTConfig, run_kwargs)

    callbacks = []
    best_checkpoint_callback = make_best_checkpoint_callback(
        bool(training_cfg.get("best_checkpoint_only", False))
    )
    if best_checkpoint_callback is not None:
        callbacks.append(best_checkpoint_callback)
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
        "peft_config": peft_config,
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
    if processor is not None:
        processor.save_pretrained(adapter_dir)
    else:
        tokenizer.save_pretrained(adapter_dir)

    # Merge adapter into base for direct inference with LogicKor generator.
    from peft import AutoPeftModelForCausalLM

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged_model = load_peft_model_for_merge(AutoPeftModelForCausalLM, str(adapter_dir), model_dtype)
    merged_model = merged_model.merge_and_unload()
    merged_model.save_pretrained(merged_dir, safe_serialization=True)
    if processor is not None:
        processor.save_pretrained(merged_dir)
    else:
        tokenizer.save_pretrained(merged_dir)

    run_meta = {
        "seed": args.seed,
        "model": model_name,
        "data_path": data_path,
        "dataset_stats": dataset_stats,
        "split_stats": split_stats,
        "train_args": run_kwargs,
        "save_checkpoints": save_checkpoints,
        "best_checkpoint_only": bool(training_cfg.get("best_checkpoint_only", False)),
        "early_stopping_enabled": early_cfg is not None,
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_eval_loss": trainer.state.best_metric,
        "global_step": trainer.state.global_step,
        "adapter_dir": str(adapter_dir),
        "merged_dir": str(merged_dir),
    }
    with (output_dir / "run_meta.json").open("w", encoding="utf-8") as f:
        json.dump(run_meta, f, ensure_ascii=False, indent=2)

    print(json.dumps(run_meta, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    train(args, config)


if __name__ == "__main__":
    main()
