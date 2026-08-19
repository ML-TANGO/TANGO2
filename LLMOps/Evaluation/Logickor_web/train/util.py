import json
import inspect
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


def patch_exaone_causal_mask_compat(model_name: str) -> None:
    if "EXAONE" not in str(model_name).upper():
        return

    import transformers.masking_utils as masking_utils

    original = masking_utils.create_causal_mask
    if getattr(original, "_logickor_exaone_compat", False):
        return

    params = inspect.signature(original).parameters

    def create_causal_mask_compat(*args, **kwargs):
        if "input_embeds" in kwargs and "inputs_embeds" in params and "inputs_embeds" not in kwargs:
            kwargs["inputs_embeds"] = kwargs.pop("input_embeds")
        if "cache_position" in kwargs and "cache_position" not in params:
            kwargs.pop("cache_position")
        return original(*args, **kwargs)

    create_causal_mask_compat._logickor_exaone_compat = True
    masking_utils.create_causal_mask = create_causal_mask_compat


def load_causal_lm_model(auto_model_cls: Any, model_name: str, model_dtype: Any) -> Any:
    patch_exaone_causal_mask_compat(model_name)
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


def _safetensors_files(model_dir: Path) -> list:
    index_path = model_dir / "model.safetensors.index.json"
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            index = json.load(f)
        names = sorted(set(index.get("weight_map", {}).values()))
        return [model_dir / name for name in names]
    return sorted(model_dir.glob("*.safetensors"))


def _resolve_base_model_dir(base_model_name_or_path: str) -> Path:
    local_dir = Path(base_model_name_or_path)
    if local_dir.is_dir():
        return local_dir

    from huggingface_hub import snapshot_download

    # Weights are already cached from the merge itself; this resolves the cache path.
    return Path(
        snapshot_download(
            base_model_name_or_path,
            allow_patterns=["*.safetensors", "*.safetensors.index.json"],
        )
    )


def restore_kv_shared_norm_weights(merged_dir: Any, base_model_name_or_path: str) -> list:
    """Copy k_norm weights of KV-sharing layers back into a merged checkpoint.

    Gemma 3n/4-style models share KV across the last `num_kv_shared_layers` layers, and
    transformers skips creating k_proj/v_proj/k_norm for those layers entirely. So
    save_pretrained() drops the keys, while vLLM's loader allocates self_attn.k_norm for
    every layer and aborts startup with "Following weights were not initialized from
    checkpoint". The weights are never used at inference (and LoRA never trains them), so
    restoring them from the base checkpoint only satisfies the strict check.

    Returns the list of restored key names (empty when nothing was missing).
    """
    from safetensors import safe_open
    from safetensors.torch import save_file

    merged_dir = Path(merged_dir)
    merged_files = _safetensors_files(merged_dir)
    if not merged_files:
        return []

    merged_keys = set()
    for path in merged_files:
        with safe_open(str(path), framework="pt") as f:
            merged_keys.update(f.keys())

    try:
        base_dir = _resolve_base_model_dir(base_model_name_or_path)
    except Exception as exc:  # network/cache miss: leave the checkpoint untouched
        print(f"[warn] Skipping k_norm restore, base weights unavailable: {exc}")
        return []

    base_files = _safetensors_files(base_dir)
    missing = {}
    for path in base_files:
        with safe_open(str(path), framework="pt") as f:
            for key in f.keys():
                if key.endswith(".self_attn.k_norm.weight") and key not in merged_keys:
                    missing[key] = f.get_tensor(key).clone()

    if not missing:
        return []

    # Append to the smallest shard to keep the rewrite cheap.
    target = min(merged_files, key=lambda p: p.stat().st_size)
    with safe_open(str(target), framework="pt") as f:
        metadata = f.metadata()
        tensors = {key: f.get_tensor(key) for key in f.keys()}
    tensors.update(missing)

    tmp_path = target.with_suffix(target.suffix + ".tmp")
    save_file(tensors, str(tmp_path), metadata=metadata or {"format": "pt"})
    tmp_path.replace(target)

    index_path = merged_dir / "model.safetensors.index.json"
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            index = json.load(f)
        weight_map = index.setdefault("weight_map", {})
        for key, tensor in missing.items():
            weight_map[key] = target.name
        metadata_block = index.setdefault("metadata", {})
        if "total_size" in metadata_block:
            metadata_block["total_size"] += sum(t.numel() * t.element_size() for t in missing.values())
        with index_path.open("w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    restored = sorted(missing)
    print(f"[info] Restored {len(restored)} KV-shared k_norm weights into {target.name}")
    return restored


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
