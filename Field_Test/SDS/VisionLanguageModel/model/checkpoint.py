"""
Checkpoint helpers — recovering projector settings from a trained run.

train.py and gaa/train_gaa.py write `vlm_config.json` next to `projector.bin`
in every checkpoint directory. The inference entry points read it back so a
checkpoint trained with a resampler projector is rebuilt with the same
architecture, without the caller having to repeat every hyperparameter flag.
"""
import json
import os
from typing import Optional, Tuple

from .config import VLMConfig, PROJECTOR_TYPES


CONFIG_FILENAME = "vlm_config.json"

# Keys read back out of vlm_config.json. Everything else in that file describes
# the vision encoder, the LLM, or the training run, none of which the projector
# architecture depends on.
PROJECTOR_CONFIG_KEYS = (
    "projector_type",
    "projector_num_query_tokens",
    "projector_num_heads",
    "projector_num_layers",
    "projector_ffn_ratio",
    "projector_dropout",
    "projector_hidden_size",
)

# Where a resolved setting came from, in precedence order.
SOURCE_CLI = "cli"
SOURCE_CHECKPOINT = "checkpoint"
SOURCE_DEFAULT = "default"


def find_projector_config(projector_path_or_dir: Optional[str]) -> Optional[str]:
    """
    Locate `vlm_config.json` for a projector checkpoint.

    Accepts either the projector weights file (the config is looked up in its
    directory) or a checkpoint directory. Returns None when there is no config
    file to read.
    """
    if not projector_path_or_dir:
        return None

    path = os.path.abspath(os.path.expanduser(projector_path_or_dir))
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    config_path = os.path.join(directory, CONFIG_FILENAME)

    return config_path if os.path.isfile(config_path) else None


def load_projector_config(projector_path_or_dir: Optional[str]) -> Optional[dict]:
    """
    Read the projector settings recorded alongside a projector checkpoint.

    Args:
        projector_path_or_dir: path to projector.bin, or the directory holding it.

    Returns:
        A dict containing only the keys in PROJECTOR_CONFIG_KEYS that the file
        actually records, or None when no readable config was found.
    """
    config_path = find_projector_config(projector_path_or_dir)
    if config_path is None:
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as err:
        print(f"[Checkpoint] Could not read {config_path}: {err}")
        return None

    if not isinstance(raw, dict):
        print(f"[Checkpoint] Ignoring {config_path}: expected a JSON object.")
        return None

    settings = {key: raw[key] for key in PROJECTOR_CONFIG_KEYS if key in raw}

    recorded_type = settings.get("projector_type")
    if recorded_type is not None and recorded_type not in PROJECTOR_TYPES:
        print(f"[Checkpoint] Ignoring unknown projector_type {recorded_type!r} "
              f"in {config_path}.")
        settings.pop("projector_type")

    if not settings:
        return None

    print(f"[Checkpoint] Projector settings read from {config_path}")
    return settings


def resolve_projector_settings(
    cli_overrides: dict,
    checkpoint_config: Optional[dict] = None,
) -> Tuple[dict, dict]:
    """
    Resolve projector settings by precedence: CLI flag, then the checkpoint
    config, then the VLMConfig dataclass default.

    Args:
        cli_overrides: maps a key in PROJECTOR_CONFIG_KEYS to the value passed
            on the command line. None means the flag was not passed, which is
            why the inference entry points default these arguments to None.
        checkpoint_config: result of load_projector_config(), or None.

    Returns:
        (settings, sources). `settings` is a complete kwargs dict for VLMConfig.
        `sources` maps each key to SOURCE_CLI, SOURCE_CHECKPOINT or SOURCE_DEFAULT.
    """
    defaults = VLMConfig()
    recorded = checkpoint_config or {}

    settings: dict = {}
    sources: dict = {}

    for key in PROJECTOR_CONFIG_KEYS:
        if cli_overrides.get(key) is not None:
            settings[key] = cli_overrides[key]
            sources[key] = SOURCE_CLI
        elif recorded.get(key) is not None:
            settings[key] = recorded[key]
            sources[key] = SOURCE_CHECKPOINT
        else:
            settings[key] = getattr(defaults, key)
            sources[key] = SOURCE_DEFAULT

    return settings, sources
