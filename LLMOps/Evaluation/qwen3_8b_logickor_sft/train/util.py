import json
from pathlib import Path
from types import MethodType
from typing import Any, Dict

import yaml


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError("Config must be a mapping.")
    return config


def make_sft_args(sft_config_cls: Any, kwargs: Dict[str, Any]) -> Any:
    accepted = set(sft_config_cls.__init__.__code__.co_varnames)
    normalized = dict(kwargs)

    # Handle naming differences across transformers/trl versions.
    if "eval_strategy" in accepted and "evaluation_strategy" in normalized:
        normalized["eval_strategy"] = normalized["evaluation_strategy"]
    if "evaluation_strategy" in accepted and "eval_strategy" in normalized:
        normalized["evaluation_strategy"] = normalized["eval_strategy"]

    filtered = {k: v for k, v in normalized.items() if k in accepted}
    return sft_config_cls(**filtered)


def _get_module_by_path(root: Any, path: str) -> Any:
    current = root
    for name in path.split("."):
        if not hasattr(current, name):
            return None
        current = getattr(current, name)
    return current


def _infer_input_embedding_module(model: Any) -> Any:
    candidates = [
        "model.embed_tokens",
        "embed_tokens",
        "transformer.wte",
        "wte",
        "embeddings.word_embeddings",
    ]
    for path in candidates:
        module = _get_module_by_path(model, path)
        if module is not None:
            return module
    base = getattr(model, "base_model", None)
    if base is not None:
        for path in candidates:
            module = _get_module_by_path(base, path)
            if module is not None:
                return module
    return None


def ensure_embedding_accessors(model: Any) -> None:
    try:
        emb = model.get_input_embeddings()
    except Exception:
        emb = _infer_input_embedding_module(model)
        if emb is None:
            raise RuntimeError(
                "Could not resolve input embedding module for this model. "
                "Please update transformers/peft or provide model-specific embedding accessors."
            )

        def _get_input_embeddings(self):
            return emb

        def _set_input_embeddings(self, value):
            nonlocal emb
            emb = value

        model.get_input_embeddings = MethodType(_get_input_embeddings, model)
        model.set_input_embeddings = MethodType(_set_input_embeddings, model)

    # Ensure output embeddings accessor exists for merge/save compatibility.
    try:
        _ = model.get_output_embeddings()
    except Exception:
        if hasattr(model, "lm_head"):
            lm_head = model.lm_head

            def _get_output_embeddings(self):
                return lm_head

            model.get_output_embeddings = MethodType(_get_output_embeddings, model)


def load_causal_lm_model(auto_model_cls: Any, model_name: str, model_dtype: Any) -> Any:
    load_kwargs = {
        "trust_remote_code": True,
        "dtype": model_dtype,
    }
    try:
        return auto_model_cls.from_pretrained(model_name, **load_kwargs)
    except TypeError:
        load_kwargs.pop("dtype")
        load_kwargs["torch_dtype"] = model_dtype
        return auto_model_cls.from_pretrained(model_name, **load_kwargs)


def load_peft_model_for_merge(auto_peft_cls: Any, adapter_path: str, model_dtype: Any) -> Any:
    load_kwargs = {
        "dtype": model_dtype,
        "trust_remote_code": True,
    }
    try:
        return auto_peft_cls.from_pretrained(adapter_path, **load_kwargs)
    except TypeError:
        load_kwargs.pop("dtype")
        load_kwargs["torch_dtype"] = model_dtype
        return auto_peft_cls.from_pretrained(adapter_path, **load_kwargs)
    except Exception as exc:
        if "get_input_embeddings" not in str(exc):
            raise

        # Fallback path for custom models (e.g., EXAONE) where AutoPeftModel loading
        # calls base_model.get_input_embeddings() before accessors are model-patched.
        from peft import PeftModel
        from transformers import AutoModelForCausalLM

        adapter_config_path = Path(adapter_path) / "adapter_config.json"
        if not adapter_config_path.exists():
            raise RuntimeError(f"Missing adapter config: {adapter_config_path}") from exc

        with adapter_config_path.open("r", encoding="utf-8") as f:
            adapter_cfg = json.load(f)

        base_model_name = adapter_cfg.get("base_model_name_or_path")
        if not base_model_name:
            raise RuntimeError("adapter_config.json missing base_model_name_or_path.") from exc

        base_model = load_causal_lm_model(AutoModelForCausalLM, base_model_name, model_dtype)
        ensure_embedding_accessors(base_model)
        return PeftModel.from_pretrained(base_model, adapter_path, trust_remote_code=True)
