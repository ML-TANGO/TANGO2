"""
Guards the hand-copied projector type lists against drift.

`model/config.py` is the single source of truth for the projector types, but
three places restate it because they cannot import it:

  - `api/schemas.py` is imported before EVA_VLM_ROOT joins sys.path.
  - `scripts/convert_to_gguf.py` and `scripts/convert_to_llava_hf.py` operate on
    state dicts alone so they stay runnable without the training dependencies.

These tests fail when any copy falls out of step with model/config.py.

Run with an interpreter that has torch, pydantic and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_projector_type_consistency.py
"""
import importlib.util
import os
import sys
import typing

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "api"))

from model.config import PROJECTOR_TYPES, RESAMPLER_PROJECTOR_TYPES


def load_script(filename: str):
    path = os.path.join(REPO_ROOT, "scripts", filename)
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPORT_SCRIPTS = ["convert_to_gguf.py", "convert_to_llava_hf.py"]

# TrainParams requires these regardless of projector settings.
REQUIRED_TRAIN_PARAMS = {
    "phase": "projector",
    "llm_model_path": "/models/llm/Llama-3.1-8B-Instruct",
    "output_checkpoint_name": "projector_run",
}


def train_params(**overrides):
    import schemas

    return schemas.TrainParams(**{**REQUIRED_TRAIN_PARAMS, **overrides})


@pytest.mark.parametrize("filename", EXPORT_SCRIPTS)
def test_export_scripts_restate_the_resampler_list_correctly(filename):
    module = load_script(filename)

    assert tuple(module.RESAMPLER_PROJECTOR_TYPES) == RESAMPLER_PROJECTOR_TYPES


def test_api_schema_restates_the_projector_type_list_correctly():
    import schemas

    assert typing.get_args(schemas.ProjectorType) == PROJECTOR_TYPES


def test_api_schema_restates_the_resampler_list_correctly():
    import schemas

    assert tuple(schemas.RESAMPLER_PROJECTOR_TYPES) == RESAMPLER_PROJECTOR_TYPES


def test_train_params_defaults_match_the_dataclass_defaults():
    """A request that omits the projector fields must build what train.py would."""
    from model.config import VLMConfig

    params = train_params()
    defaults = VLMConfig()

    for field in (
        "projector_type",
        "projector_num_query_tokens",
        "projector_num_heads",
        "projector_num_layers",
        "projector_ffn_ratio",
        "projector_dropout",
        "projector_hidden_size",
    ):
        assert getattr(params, field) == getattr(defaults, field), field


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_train_params_accepts_every_supported_type(projector_type):
    assert train_params(projector_type=projector_type).projector_type == projector_type


def test_train_params_rejects_an_unknown_type():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        train_params(projector_type="perceiver_io")


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("projector_num_query_tokens", 0),
        ("projector_num_heads", 0),
        ("projector_num_layers", 0),
        ("projector_ffn_ratio", 0.0),
        ("projector_dropout", 1.5),
        ("projector_hidden_size", 0),
    ],
)
def test_train_params_rejects_out_of_range_resampler_settings(field, bad_value):
    """The API must reject values the projector constructor would raise on."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        train_params(**{field: bad_value})


# ── API to train.py command line ─────────────────────────────────────────────
# api/train_manager.py builds a train.py argv. The flags it emits must be flags
# train.py actually declares, and lora_marine runs train_text_lora.py which has
# no projector at all.

def train_command(**overrides):
    from train_manager import TrainManager

    params = train_params(
        data_path="/data/chat.json", image_dir="/data/images", **overrides
    )
    return TrainManager()._build_command("python", "/repo", params, "/out")


def train_py_argument_names() -> set:
    """Flags train.py declares, read from its source so no heavy imports are needed."""
    import ast

    tree = ast.parse(
        open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read()
    )
    names = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_every_emitted_flag_is_declared_by_train_py(projector_type):
    cmd = train_command(projector_type=projector_type)
    declared = train_py_argument_names()

    emitted = [token for token in cmd if token.startswith("--")]
    assert emitted, "no flags were emitted"
    assert [flag for flag in emitted if flag not in declared] == []


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_resampler_requests_pass_the_hyperparameters_through(projector_type):
    cmd = train_command(
        projector_type=projector_type,
        projector_num_query_tokens=48,
        projector_num_heads=16,
        projector_num_layers=3,
    )

    assert cmd[cmd.index("--projector_type") + 1] == projector_type
    assert cmd[cmd.index("--projector_num_query_tokens") + 1] == "48"
    assert cmd[cmd.index("--projector_num_heads") + 1] == "16"
    assert cmd[cmd.index("--projector_num_layers") + 1] == "3"


def test_per_patch_requests_omit_the_resampler_hyperparameters():
    """Passing them would be harmless but misleading in the job log."""
    cmd = train_command(projector_type="mlp2x_gelu")

    assert "--projector_type" in cmd
    assert "--projector_num_query_tokens" not in cmd
    assert "--projector_num_layers" not in cmd


def test_the_text_only_phase_gets_no_projector_flags():
    """lora_marine runs train_text_lora.py, which has no projector."""
    from train_manager import TrainManager

    params = train_params(
        phase="lora_marine",
        projector_type="qformer",
        marine_data_path="/data/marine.json",
        resume_lora_path="/ckpt",
    )
    cmd = TrainManager()._build_command("python", "/repo", params, "/out")

    assert os.path.basename(cmd[1]) == "train_text_lora.py"
    assert not [token for token in cmd if token.startswith("--projector_")]
