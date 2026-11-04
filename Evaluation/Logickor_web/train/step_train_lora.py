import argparse
import inspect
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from dataloader import read_jsonl, split_by_question_id, validate_rows
from prompt import ensure_training_chat_template
from util import (
    ensure_embedding_accessors,
    load_causal_lm_model,
    load_config,
    load_peft_model_for_merge,
    make_sft_args,
    restore_kv_shared_norm_weights,
)


DEFAULT_STAGE_SAVE_ADAPTER = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a multi-stage curriculum LoRA SFT model.")
    parser.add_argument("--config", required=True, help="Path to curriculum YAML config.")
    parser.add_argument("--output-dir", required=True, help="Directory to write run outputs.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config/data/splits only and exit without loading a model.",
    )
    parser.add_argument(
        "--skip-merge",
        action="store_true",
        help="Skip final adapter merge even when config enables it.",
    )
    return parser.parse_args()


def require_mapping(value: Any, name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping.")
    return value


def require_non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def validate_curriculum_config(config: Dict[str, Any]) -> None:
    require_non_empty_string(config.get("model"), "model")
    if int(config.get("max_seq_length", 0)) <= 0:
        raise ValueError("max_seq_length must be a positive integer.")

    require_mapping(config.get("lora"), "lora")
    require_mapping(config.get("training"), "training")
    require_mapping(config.get("split"), "split")

    stages = config.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("stages must be a non-empty list.")

    seen_names = set()
    for index, stage in enumerate(stages):
        stage_name = f"stages[{index}]"
        require_mapping(stage, stage_name)
        name = require_non_empty_string(stage.get("name"), f"{stage_name}.name")
        if name in seen_names:
            raise ValueError(f"Duplicate stage name: {name}")
        seen_names.add(name)
        require_non_empty_string(stage.get("data_path"), f"{stage_name}.data_path")
        if float(stage.get("num_train_epochs", 0)) <= 0:
            raise ValueError(f"{stage_name}.num_train_epochs must be positive.")


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


def cleanup_merged_only(output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if path.name not in {"merged", "run_meta.json"}:
            shutil.rmtree(path) if path.is_dir() else path.unlink()



def logic_kor_rows_to_sft_rows(rows: Sequence[Dict[str, Any]], source_path: str) -> List[Dict[str, Any]]:
    converted: List[Dict[str, Any]] = []
    seen_ids = set()

    for row_index, row in enumerate(rows):
        qid = row.get("id")
        category = row.get("category")
        questions = row.get("questions")
        references = row.get("references")

        if not isinstance(qid, int):
            raise ValueError(f"Row {row_index}: id must be an integer.")
        if qid in seen_ids:
            raise ValueError(f"Duplicate question id in {source_path}: {qid}")
        seen_ids.add(qid)

        if not isinstance(questions, list) or len(questions) < 2:
            raise ValueError(f"Row {row_index}: questions must contain at least two items.")
        if not isinstance(references, list) or len(references) < 2:
            raise ValueError(f"Row {row_index}: references must contain at least two items.")

        q1, q2 = questions[0], questions[1]
        a1, a2 = references[0], references[1]
        required_text_fields = (
            ("questions[0]", q1),
            ("questions[1]", q2),
            ("references[0]", a1),
            ("references[1]", a2),
        )
        for field_name, value in required_text_fields:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Row {row_index}: {field_name} must be a non-empty string.")

        meta = {
            "question_id": qid,
            "category": category,
            "source_model": "logic_kor_raw",
            "source_path": source_path,
        }
        converted.append(
            {
                "messages": [
                    {"role": "user", "content": q1},
                    {"role": "assistant", "content": a1},
                ],
                "meta": {**meta, "turn": 1},
            }
        )
        converted.append(
            {
                "messages": [
                    {"role": "user", "content": q1},
                    {"role": "assistant", "content": a1},
                    {"role": "user", "content": q2},
                    {"role": "assistant", "content": a2},
                ],
                "meta": {**meta, "turn": 2},
            }
        )

    return converted


def load_stage_rows(data_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows = read_jsonl(data_path)
    if not rows:
        raise ValueError(f"Dataset is empty: {data_path}")

    first_row = rows[0]
    if "messages" in first_row and "meta" in first_row:
        normalized_rows = rows
        source_format = "sft_messages"
    elif {"id", "questions", "references"}.issubset(first_row.keys()):
        normalized_rows = logic_kor_rows_to_sft_rows(rows, data_path)
        source_format = "logic_kor_raw"
    else:
        raise ValueError(
            f"Unsupported dataset format: {data_path}. "
            "Expected SFT messages/meta rows or LogicKor id/questions/references rows."
        )

    stats = validate_rows(normalized_rows)
    stats["source_format"] = source_format
    return normalized_rows, stats


def merge_training_config(base_training: Dict[str, Any], stage: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base_training)
    for key, value in stage.items():
        if key in {"name", "data_path", "save_adapter"}:
            continue
        merged[key] = value
    return merged


def build_sft_config_kwargs(
    output_dir: Path,
    max_seq_length: int,
    training_cfg: Dict[str, Any],
    seed: int,
    train_row_count: int,
) -> Dict[str, Any]:
    warmup_ratio = float(training_cfg.get("warmup_ratio", 0.0))
    per_device_train_batch_size = int(training_cfg["per_device_train_batch_size"])
    gradient_accumulation_steps = int(training_cfg["gradient_accumulation_steps"])
    save_checkpoints = _checkpoints_enabled(training_cfg)

    kwargs: Dict[str, Any] = {
        "output_dir": str(output_dir),
        "num_train_epochs": float(training_cfg["num_train_epochs"]),
        "per_device_train_batch_size": per_device_train_batch_size,
        "per_device_eval_batch_size": int(training_cfg["per_device_eval_batch_size"]),
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "gradient_checkpointing": bool(training_cfg.get("gradient_checkpointing", False)),
        "learning_rate": float(training_cfg["learning_rate"]),
        "lr_scheduler_type": str(training_cfg["lr_scheduler_type"]),
        "optim": str(training_cfg["optim"]),
        "weight_decay": float(training_cfg.get("weight_decay", 0.0)),
        "logging_steps": int(training_cfg["logging_steps"]),
        "eval_steps": int(training_cfg["eval_steps"]),
        "eval_strategy": "steps",
        "evaluation_strategy": "steps",
        "save_strategy": "steps" if save_checkpoints else "no",
        "load_best_model_at_end": bool(training_cfg.get("load_best_model_at_end", save_checkpoints)) if save_checkpoints else False,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "bf16": bool(training_cfg["bf16"]),
        "fp16": bool(training_cfg.get("fp16", False)),
        "seed": seed,
        "max_length": max_seq_length,
        "max_seq_length": max_seq_length,
        "assistant_only_loss": bool(training_cfg.get("assistant_only_loss", True)),
        "completion_only_loss": bool(training_cfg.get("completion_only_loss", False)),
        "dataset_kwargs": {"skip_prepare_dataset": False},
        "report_to": "none",
    }
    dataset_num_proc = training_cfg.get("dataset_num_proc")
    if dataset_num_proc is not None:
        kwargs["dataset_num_proc"] = int(dataset_num_proc)
    if "max_steps" in training_cfg:
        kwargs["max_steps"] = int(training_cfg["max_steps"])
    if save_checkpoints:
        kwargs["save_steps"] = int(training_cfg["save_steps"])
        save_total_limit = int(training_cfg.get("save_total_limit", 0))
        if save_total_limit > 0:
            kwargs["save_total_limit"] = save_total_limit

    estimated_steps = max(1, train_row_count // max(1, per_device_train_batch_size))
    estimated_steps = max(1, estimated_steps // max(1, gradient_accumulation_steps))
    estimated_steps = max(1, int(estimated_steps * float(training_cfg["num_train_epochs"])))
    kwargs["warmup_ratio"] = warmup_ratio
    kwargs["warmup_steps"] = max(0, int(estimated_steps * warmup_ratio))
    return kwargs


def prepare_stage_datasets(
    stage: Dict[str, Any],
    train_ratio: float,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    rows, dataset_stats = load_stage_rows(stage["data_path"])
    train_rows, eval_rows, split_stats = split_by_question_id(rows, train_ratio=train_ratio, seed=seed)
    return train_rows, eval_rows, {"dataset_stats": dataset_stats, "split_stats": split_stats}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def dry_run(config: Dict[str, Any], output_dir: Path, seed: int) -> None:
    train_ratio = float(config["split"]["train_ratio"])
    stages_meta = []
    for stage in config["stages"]:
        train_rows, eval_rows, stats = prepare_stage_datasets(stage, train_ratio=train_ratio, seed=seed)
        stages_meta.append(
            {
                "name": stage["name"],
                "data_path": stage["data_path"],
                "num_train_epochs": float(stage["num_train_epochs"]),
                **stats,
                "train_rows": len(train_rows),
                "eval_rows": len(eval_rows),
            }
        )

    payload = {
        "mode": "dry_run",
        "seed": seed,
        "model": config["model"],
        "stage_count": len(stages_meta),
        "stages": stages_meta,
    }
    write_json(output_dir / "dry_run_meta.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def train_curriculum(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    validate_curriculum_config(config)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        dry_run(config, output_dir=output_dir, seed=args.seed)
        return

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoProcessor, AutoTokenizer
        from transformers import EarlyStoppingCallback, set_seed
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

    training_defaults = require_mapping(config["training"], "training")
    cuda_visible_devices = training_defaults.get("cuda_visible_devices")
    if cuda_visible_devices is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_visible_devices)
    os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

    has_cuda = bool(torch.cuda.is_available())
    bf16_requested = bool(training_defaults.get("bf16", True))
    fp16_requested = bool(training_defaults.get("fp16", False))
    bf16 = bool(has_cuda and torch.cuda.is_bf16_supported() and bf16_requested)
    fp16 = bool(has_cuda and (not bf16) and fp16_requested)
    model_dtype = torch.bfloat16 if has_cuda and bf16 else torch.float16 if has_cuda else torch.float32

    model_name = config["model"]
    max_seq_length = int(config["max_seq_length"])
    train_ratio = float(config["split"]["train_ratio"])
    lora_cfg = require_mapping(config["lora"], "lora")
    save_checkpoints = _checkpoints_enabled(training_defaults)
    early_cfg = _early_stopping_config(config, save_checkpoints)

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

    run_meta: Dict[str, Any] = {
        "seed": args.seed,
        "model": model_name,
        "max_seq_length": max_seq_length,
        "output_dir": str(output_dir),
        "stages": [],
    }

    trainer = None
    for stage_index, stage in enumerate(config["stages"], start=1):
        stage_name = stage["name"]
        stage_dir = output_dir / f"{stage_index:02d}_{stage_name}"
        stage_training = merge_training_config(training_defaults, stage)
        stage_training["num_train_epochs"] = float(stage["num_train_epochs"])
        stage_training["bf16"] = bf16
        stage_training["fp16"] = fp16

        train_rows, eval_rows, stats = prepare_stage_datasets(stage, train_ratio=train_ratio, seed=args.seed)
        train_ds = Dataset.from_list(train_rows)
        eval_ds = Dataset.from_list(eval_rows)

        sft_kwargs = build_sft_config_kwargs(
            output_dir=stage_dir,
            max_seq_length=max_seq_length,
            training_cfg=stage_training,
            seed=args.seed,
            train_row_count=len(train_rows),
        )
        sft_args = make_sft_args(SFTConfig, sft_kwargs)
        callbacks = []
        best_checkpoint_callback = make_best_checkpoint_callback(
            bool(stage_training.get("best_checkpoint_only", False))
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
            "callbacks": callbacks,
        }
        if stage_index == 1:
            trainer_kwargs["peft_config"] = peft_config

        trainer_init_params = set(inspect.signature(SFTTrainer.__init__).parameters.keys())
        if "max_seq_length" in trainer_init_params:
            trainer_kwargs["max_seq_length"] = max_seq_length
        if "processing_class" in trainer_init_params:
            trainer_kwargs["processing_class"] = tokenizer
        elif "tokenizer" in trainer_init_params:
            trainer_kwargs["tokenizer"] = tokenizer

        print(f"\n=== Stage {stage_index}/{len(config['stages'])}: {stage_name} ===")
        print(json.dumps({"data_path": stage["data_path"], **stats}, ensure_ascii=False, indent=2))

        trainer = SFTTrainer(**trainer_kwargs)
        trainer.train()
        model = trainer.model

        stage_adapter_dir = stage_dir / "adapter"
        if bool(stage.get("save_adapter", DEFAULT_STAGE_SAVE_ADAPTER)):
            stage_adapter_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(stage_adapter_dir)
            if processor is not None:
                processor.save_pretrained(stage_adapter_dir)
            else:
                tokenizer.save_pretrained(stage_adapter_dir)

        stage_meta = {
            "name": stage_name,
            "data_path": stage["data_path"],
            "stage_dir": str(stage_dir),
            "adapter_dir": str(stage_adapter_dir) if stage_adapter_dir.exists() else None,
            "dataset_stats": stats["dataset_stats"],
            "split_stats": stats["split_stats"],
            "train_args": sft_kwargs,
            "best_checkpoint_only": bool(stage_training.get("best_checkpoint_only", False)),
            "best_model_checkpoint": trainer.state.best_model_checkpoint,
            "best_eval_loss": trainer.state.best_metric,
            "global_step": trainer.state.global_step,
        }
        write_json(stage_dir / "stage_meta.json", stage_meta)
        run_meta["stages"].append(stage_meta)
        write_json(output_dir / "run_meta.json", run_meta)

    if trainer is None:
        raise RuntimeError("No curriculum stages were trained.")

    final_adapter_dir = output_dir / "adapter"
    final_adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(final_adapter_dir)
    if processor is not None:
        processor.save_pretrained(final_adapter_dir)
    else:
        tokenizer.save_pretrained(final_adapter_dir)
    run_meta["final_adapter_dir"] = str(final_adapter_dir)

    save_merged_only = bool(config.get("save_merged_only", False))
    if save_merged_only and args.skip_merge:
        raise ValueError("save_merged_only requires final merge; remove --skip-merge.")

    final_merge_enabled = bool(config.get("final_merge", True)) and not args.skip_merge
    if final_merge_enabled:
        from peft import AutoPeftModelForCausalLM

        merged_dir = output_dir / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        merged_model = load_peft_model_for_merge(AutoPeftModelForCausalLM, str(final_adapter_dir), model_dtype)
        merged_model = merged_model.merge_and_unload()
        merged_model.save_pretrained(merged_dir, safe_serialization=True)
        restore_kv_shared_norm_weights(merged_dir, model_name)
        if processor is not None:
            processor.save_pretrained(merged_dir)
        else:
            tokenizer.save_pretrained(merged_dir)
        run_meta["merged_dir"] = str(merged_dir)
    else:
        run_meta["merged_dir"] = None

    run_meta["save_merged_only"] = save_merged_only
    write_json(output_dir / "run_meta.json", run_meta)
    if save_merged_only:
        cleanup_merged_only(output_dir)
    print(json.dumps(run_meta, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    train_curriculum(args, config)


if __name__ == "__main__":
    main()
