"""
Tests for recovering projector settings from a trained checkpoint.

The inference entry points rebuild the projector from `vlm_config.json` next to
`projector.bin`, so a resampler checkpoint loads without the caller repeating
every hyperparameter flag. These tests pin the precedence rules.

Run with an interpreter that has torch and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_checkpoint.py
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.checkpoint import (
    CONFIG_FILENAME,
    PROJECTOR_CONFIG_KEYS,
    SOURCE_CHECKPOINT,
    SOURCE_CLI,
    SOURCE_DEFAULT,
    find_projector_config,
    load_projector_config,
    resolve_projector_settings,
)
from model.config import VLMConfig


QFORMER_CONFIG = {
    "vision_model_name": "openai/clip-vit-large-patch14-336",
    "llm_model_name": "/models/Llama-3.1-8B-Instruct",
    "projector_type": "qformer",
    "projector_num_query_tokens": 64,
    "projector_num_heads": 16,
    "projector_num_layers": 4,
    "projector_ffn_ratio": 2.0,
    "projector_dropout": 0.1,
    "projector_hidden_size": 1024,
    "num_image_tokens": 64,
    "vision_num_patches": 576,
}


def make_checkpoint(tmp_path, config: dict = None, weights_name="projector.bin"):
    """Write a checkpoint directory and return the path to its weights file."""
    weights = tmp_path / weights_name
    weights.write_bytes(b"")
    if config is not None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps(config), encoding="utf-8")
    return str(weights)


def no_cli_overrides() -> dict:
    return {key: None for key in PROJECTOR_CONFIG_KEYS}


# ── Locating the config ──────────────────────────────────────────────────────

def test_find_config_from_the_weights_file(tmp_path):
    weights = make_checkpoint(tmp_path, QFORMER_CONFIG)

    assert find_projector_config(weights) == str(tmp_path / CONFIG_FILENAME)


def test_find_config_from_the_checkpoint_directory(tmp_path):
    make_checkpoint(tmp_path, QFORMER_CONFIG)

    assert find_projector_config(str(tmp_path)) == str(tmp_path / CONFIG_FILENAME)


def test_find_config_returns_none_when_absent(tmp_path):
    weights = make_checkpoint(tmp_path, config=None)

    assert find_projector_config(weights) is None


@pytest.mark.parametrize("empty", [None, ""])
def test_find_config_tolerates_a_missing_path(empty):
    assert find_projector_config(empty) is None


# ── Reading the config ───────────────────────────────────────────────────────

def test_load_returns_only_the_projector_keys(tmp_path):
    weights = make_checkpoint(tmp_path, QFORMER_CONFIG)

    settings = load_projector_config(weights)

    assert set(settings) == set(PROJECTOR_CONFIG_KEYS)
    assert settings["projector_type"] == "qformer"
    assert settings["projector_num_query_tokens"] == 64
    assert "vision_model_name" not in settings
    assert "num_image_tokens" not in settings


def test_load_returns_none_without_a_config(tmp_path):
    weights = make_checkpoint(tmp_path, config=None)

    assert load_projector_config(weights) is None


def test_load_returns_none_for_unreadable_json(tmp_path):
    weights = make_checkpoint(tmp_path, config=None)
    (tmp_path / CONFIG_FILENAME).write_text("{not json", encoding="utf-8")

    assert load_projector_config(weights) is None


def test_load_returns_none_for_a_json_scalar(tmp_path):
    weights = make_checkpoint(tmp_path, config=None)
    (tmp_path / CONFIG_FILENAME).write_text('"mlp2x_gelu"', encoding="utf-8")

    assert load_projector_config(weights) is None


def test_load_drops_an_unrecognized_projector_type(tmp_path):
    config = dict(QFORMER_CONFIG, projector_type="perceiver_io")
    weights = make_checkpoint(tmp_path, config)

    settings = load_projector_config(weights)

    assert "projector_type" not in settings
    assert settings["projector_num_query_tokens"] == 64


def test_load_keeps_a_partial_config(tmp_path):
    weights = make_checkpoint(tmp_path, {"projector_type": "cross_attn"})

    settings = load_projector_config(weights)

    assert settings == {"projector_type": "cross_attn"}


# ── Precedence ───────────────────────────────────────────────────────────────

def test_defaults_apply_with_no_cli_flags_and_no_checkpoint():
    settings, sources = resolve_projector_settings(no_cli_overrides(), None)

    defaults = VLMConfig()
    for key in PROJECTOR_CONFIG_KEYS:
        assert settings[key] == getattr(defaults, key)
        assert sources[key] == SOURCE_DEFAULT


def test_checkpoint_wins_over_the_defaults():
    settings, sources = resolve_projector_settings(
        no_cli_overrides(),
        {"projector_type": "qformer", "projector_num_query_tokens": 64},
    )

    assert settings["projector_type"] == "qformer"
    assert sources["projector_type"] == SOURCE_CHECKPOINT
    assert settings["projector_num_query_tokens"] == 64
    assert sources["projector_num_query_tokens"] == SOURCE_CHECKPOINT
    assert sources["projector_num_heads"] == SOURCE_DEFAULT


def test_cli_wins_over_the_checkpoint():
    overrides = dict(no_cli_overrides(), projector_num_query_tokens=16)

    settings, sources = resolve_projector_settings(
        overrides,
        {"projector_type": "qformer", "projector_num_query_tokens": 64},
    )

    assert settings["projector_num_query_tokens"] == 16
    assert sources["projector_num_query_tokens"] == SOURCE_CLI
    assert settings["projector_type"] == "qformer"
    assert sources["projector_type"] == SOURCE_CHECKPOINT


def test_a_cli_value_equal_to_the_default_still_overrides_the_checkpoint():
    """The None sentinel is what distinguishes "not passed" from "passed 32"."""
    defaults = VLMConfig()
    overrides = dict(
        no_cli_overrides(),
        projector_num_query_tokens=defaults.projector_num_query_tokens,
    )

    settings, sources = resolve_projector_settings(
        overrides, {"projector_num_query_tokens": 64}
    )

    assert settings["projector_num_query_tokens"] == defaults.projector_num_query_tokens
    assert sources["projector_num_query_tokens"] == SOURCE_CLI


# Falsy-but-valid values are the classic trap in a precedence chain. A recorded
# dropout of 0.0 must not be mistaken for "unset", and a CLI 0.0 must still win.

def test_a_recorded_falsy_value_is_not_mistaken_for_unset():
    settings, sources = resolve_projector_settings(
        no_cli_overrides(), {"projector_dropout": 0.0, "projector_num_layers": 6}
    )

    assert settings["projector_dropout"] == 0.0
    assert sources["projector_dropout"] == SOURCE_CHECKPOINT
    assert settings["projector_num_layers"] == 6
    assert sources["projector_num_layers"] == SOURCE_CHECKPOINT


def test_a_cli_falsy_value_still_beats_the_checkpoint():
    overrides = dict(no_cli_overrides(), projector_dropout=0.0)

    settings, sources = resolve_projector_settings(overrides, {"projector_dropout": 0.5})

    assert settings["projector_dropout"] == 0.0
    assert sources["projector_dropout"] == SOURCE_CLI


def test_a_recorded_hidden_size_survives():
    """projector_hidden_size's own default is None, so this is the risky key."""
    settings, sources = resolve_projector_settings(
        no_cli_overrides(), {"projector_hidden_size": 256}
    )

    assert settings["projector_hidden_size"] == 256
    assert sources["projector_hidden_size"] == SOURCE_CHECKPOINT


def test_a_recorded_null_hidden_size_falls_through_to_the_default():
    settings, sources = resolve_projector_settings(
        no_cli_overrides(), {"projector_hidden_size": None}
    )

    assert settings["projector_hidden_size"] is None
    assert sources["projector_hidden_size"] == SOURCE_DEFAULT


def test_a_cli_hidden_size_beats_a_recorded_one():
    overrides = dict(no_cli_overrides(), projector_hidden_size=512)

    settings, sources = resolve_projector_settings(overrides, {"projector_hidden_size": 256})

    assert settings["projector_hidden_size"] == 512
    assert sources["projector_hidden_size"] == SOURCE_CLI


def test_resolved_settings_are_accepted_by_vlmconfig(tmp_path):
    weights = make_checkpoint(tmp_path, QFORMER_CONFIG)

    settings, _ = resolve_projector_settings(
        no_cli_overrides(), load_projector_config(weights)
    )
    config = VLMConfig(llm_model_name="/models/Llama-3.1-8B-Instruct", **settings)

    assert config.projector_type == "qformer"
    assert config.is_resampler_projector
    assert config.projector_output_tokens == 64
    assert config.projector_num_layers == 4


# The scenario this whole mechanism exists for: Phase 1 trains with non-default
# resampler settings, Phase 2 is launched with only --projector_type. train.py
# deliberately does not auto-read the checkpoint, so the load must catch it.

def test_phase_two_forgetting_the_resampler_flags_fails_loudly(tmp_path):
    import torch

    from model.projector import VisionProjector

    phase_one = VisionProjector(
        vision_hidden_size=1024,
        llm_hidden_size=4096,
        projector_type="qformer",
        num_query_tokens=32,
        num_heads=16,
    )
    weights = tmp_path / "projector.bin"
    torch.save(phase_one.state_dict(), weights)

    # Phase 2 passes the type but leaves num_heads at the default 8.
    phase_two_config = VLMConfig(projector_type="qformer", projector_num_query_tokens=32)
    phase_two = VisionProjector(
        vision_hidden_size=1024,
        llm_hidden_size=4096,
        projector_type=phase_two_config.projector_type,
        **phase_two_config.projector_kwargs(),
    )

    with pytest.raises(ValueError) as excinfo:
        phase_two.load_weights(torch.load(weights, map_location="cpu", weights_only=True))

    message = str(excinfo.value)
    assert "num_heads checkpoint=16 vs projector=8" in message
    assert "vlm_config.json" in message


def test_the_same_handoff_succeeds_when_the_checkpoint_config_is_consulted(tmp_path):
    """Which is what test.py, test_sds.py, demo/app.py and api/ all do."""
    import torch

    from model.projector import VisionProjector

    recorded = VLMConfig(
        projector_type="qformer", projector_num_query_tokens=32, projector_num_heads=16
    )
    recorded.vision_hidden_size = 1024
    recorded.llm_hidden_size = 4096
    phase_one = VisionProjector(
        vision_hidden_size=1024,
        llm_hidden_size=4096,
        projector_type="qformer",
        **recorded.projector_kwargs(),
    ).eval()

    weights = tmp_path / "projector.bin"
    torch.save(phase_one.state_dict(), weights)
    (tmp_path / CONFIG_FILENAME).write_text(
        json.dumps({k: v for k, v in vars(recorded).items() if not k.startswith("_")}),
        encoding="utf-8",
    )

    settings, _ = resolve_projector_settings(
        no_cli_overrides(), load_projector_config(str(weights))
    )
    resolved = VLMConfig(**settings)
    phase_two = VisionProjector(
        vision_hidden_size=1024,
        llm_hidden_size=4096,
        projector_type=resolved.projector_type,
        **resolved.projector_kwargs(),
    ).eval()

    missing, unexpected = phase_two.load_weights(
        torch.load(weights, map_location="cpu", weights_only=True)
    )

    assert list(missing) == [] and list(unexpected) == []
    assert resolved.projector_num_heads == 16
    features = torch.randn(1, 576, 1024)
    with torch.no_grad():
        assert torch.equal(phase_one(features), phase_two(features))


def test_a_per_patch_checkpoint_reports_no_fixed_token_count(tmp_path):
    weights = make_checkpoint(tmp_path, {"projector_type": "mlp3x_gelu"})

    settings, _ = resolve_projector_settings(
        no_cli_overrides(), load_projector_config(weights)
    )
    config = VLMConfig(**settings)

    assert not config.is_resampler_projector
    assert config.projector_output_tokens is None

    config.vision_num_patches = 576
    assert config.projector_output_tokens == 576
