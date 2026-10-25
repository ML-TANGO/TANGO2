"""
Tests for the projector guards in the export scripts.

`scripts/convert_to_llava_hf.py` and `scripts/convert_to_gguf.py` target formats
whose projector is a fixed two-layer MLP. Every other projector architecture
must be refused rather than exported with weights silently dropped.

The scripts are standalone and do not import the `model` package, so they are
loaded here by path.

Run with an interpreter that has torch and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_export_guards.py
"""
import importlib.util
import os
import sys

import pytest
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from model.config import PROJECTOR_MLP2, PROJECTOR_TYPES
from model.projector import VisionProjector


def load_script(filename: str):
    path = os.path.join(REPO_ROOT, "scripts", filename)
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gguf():
    return load_script("convert_to_gguf.py")


@pytest.fixture(scope="module")
def llava_hf():
    return load_script("convert_to_llava_hf.py")


def projector_state(projector_type: str) -> dict:
    return VisionProjector(
        vision_hidden_size=64,
        llm_hidden_size=96,
        projector_type=projector_type,
        num_query_tokens=4,
        num_heads=4,
        num_layers=2,
    ).state_dict()


# Each target format expresses a different subset, so the refused sets differ.
# clip.cpp's mlp graph always applies gelu after the first matmul and offers at
# most two matmuls, so only mlp2x_gelu fits. LlavaMultiModalProjector's
# activation is configurable and ACT2FN["linear"] is a true identity, so linear
# fits there as well.
GGUF_CONVERTIBLE = ["mlp2x_gelu"]
LLAVA_HF_CONVERTIBLE = ["mlp2x_gelu", "linear"]
GGUF_REFUSED = [t for t in PROJECTOR_TYPES if t not in GGUF_CONVERTIBLE]
LLAVA_HF_REFUSED = [t for t in PROJECTOR_TYPES if t not in LLAVA_HF_CONVERTIBLE]

LINEAR_2_IDENTITY_KEYS = {
    "multi_modal_projector.linear_2.weight",
    "multi_modal_projector.linear_2.bias",
}
LLAVA_HF_KEYS = {
    "multi_modal_projector.linear_1.weight",
    "multi_modal_projector.linear_1.bias",
} | LINEAR_2_IDENTITY_KEYS


# ── Type detection ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_type_is_detected_from_the_state_dict_alone(gguf, projector_type):
    """Checkpoints predating vlm_config.json must still be classified correctly."""
    detected = gguf.detect_projector_type({}, projector_state(projector_type))

    assert detected == projector_type


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_a_recorded_type_takes_precedence(gguf, projector_type):
    state = projector_state(PROJECTOR_MLP2)

    assert gguf.detect_projector_type({"projector_type": projector_type}, state) == projector_type


def test_an_unrecognizable_state_dict_is_reported_as_unknown(gguf):
    assert gguf.detect_projector_type({}, {"something.else": torch.zeros(1)}) == "unknown"


# ── GGUF guard ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", GGUF_CONVERTIBLE)
def test_gguf_accepts_what_the_mlp_graph_can_express(gguf, projector_type):
    state = projector_state(projector_type)

    assert gguf.ensure_convertible_projector({}, state) == projector_type


@pytest.mark.parametrize("projector_type", GGUF_REFUSED)
def test_gguf_refuses_what_the_mlp_graph_cannot_express(gguf, projector_type):
    with pytest.raises(ValueError) as excinfo:
        gguf.ensure_convertible_projector({}, projector_state(projector_type))

    assert projector_type in str(excinfo.value)


@pytest.mark.parametrize("projector_type", GGUF_REFUSED)
def test_the_gguf_refusal_blames_the_target_format_not_the_script(gguf, projector_type):
    """
    The reason must be a property of clip.cpp, so nobody reads it as a feature
    someone forgot to write.
    """
    with pytest.raises(ValueError) as excinfo:
        gguf.ensure_convertible_projector({}, projector_state(projector_type))

    message = str(excinfo.value)
    assert "llava.cpp" in message
    assert "미구현이 아닙니다" in message


def test_the_gguf_refusal_points_linear_at_the_llava_hf_script(gguf):
    """linear is inexpressible here but exact there, so say so."""
    with pytest.raises(ValueError) as excinfo:
        gguf.ensure_convertible_projector({}, projector_state("linear"))

    assert "convert_to_llava_hf.py" in str(excinfo.value)


# ── LLaVA HF guard ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", LLAVA_HF_CONVERTIBLE)
def test_llava_hf_converts_what_the_projector_can_express(llava_hf, projector_type):
    state = projector_state(projector_type)

    converted, hidden_act = llava_hf.convert_projector({}, state, torch.float16)

    assert set(converted) == LLAVA_HF_KEYS
    assert all(t.dtype == torch.float16 for t in converted.values())
    assert hidden_act in ("gelu", "linear")


def test_the_two_layer_mlp_keeps_gelu(llava_hf):
    _, hidden_act = llava_hf.convert_projector({}, projector_state("mlp2x_gelu"), torch.float32)

    assert hidden_act == "gelu"


def test_the_linear_projector_uses_the_identity_activation(llava_hf):
    """
    Wx+b is reproduced by act="linear" plus an identity linear_2, which is the
    only way a fixed two-layer projector can express one affine map.
    """
    converted, hidden_act = llava_hf.convert_projector(
        {}, projector_state("linear"), torch.float32
    )

    assert hidden_act == "linear"
    identity = converted["multi_modal_projector.linear_2.weight"]
    assert torch.equal(identity, torch.eye(identity.shape[0], dtype=torch.float32))
    assert torch.count_nonzero(converted["multi_modal_projector.linear_2.bias"]) == 0


@pytest.mark.parametrize("projector_type", LLAVA_HF_REFUSED)
def test_llava_hf_refuses_what_it_cannot_express(llava_hf, projector_type):
    with pytest.raises(ValueError) as excinfo:
        llava_hf.convert_projector({}, projector_state(projector_type), torch.float16)

    assert projector_type in str(excinfo.value)


@pytest.mark.parametrize("projector_type", LLAVA_HF_REFUSED)
def test_the_llava_hf_refusal_blames_the_target_format_not_the_script(llava_hf, projector_type):
    with pytest.raises(ValueError) as excinfo:
        llava_hf.convert_projector({}, projector_state(projector_type), torch.float16)

    message = str(excinfo.value)
    assert "LlavaMultiModalProjector" in message
    assert "미구현이 아닙니다" in message


def test_the_mlp3x_refusal_explains_the_extra_nonlinearity(llava_hf):
    """
    mlp3x_gelu shares its first two layers with mlp2x_gelu, so the reason has to
    be the second nonlinearity rather than a missing key.
    """
    with pytest.raises(ValueError) as excinfo:
        llava_hf.convert_projector({}, projector_state("mlp3x_gelu"), torch.float16)

    assert "비선형" in str(excinfo.value)


# ── No side effects when the guard fires ─────────────────────────────────────

def test_llava_hf_leaves_nothing_behind_when_it_refuses(llava_hf, tmp_path, monkeypatch):
    """
    The guard must run before the output directory is created, so a refused
    conversion does not leave an empty directory looking like a partial export.
    """
    import json

    import torch as torch_module

    checkpoint = tmp_path / "ckpt"
    checkpoint.mkdir()
    torch_module.save(projector_state("qformer"), checkpoint / "projector.bin")
    (checkpoint / "vlm_config.json").write_text(
        json.dumps(
            {
                "projector_type": "qformer",
                "image_token_id": 128256,
                "vision_feature_layer": -2,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "convert_to_llava_hf.py",
            "--ckpt_dir",
            str(checkpoint),
            "--llm_path",
            str(tmp_path / "no_such_llm"),
            "--clip_model",
            "openai/clip-vit-large-patch14-336",
            "--output_dir",
            str(output),
        ],
    )

    with pytest.raises(ValueError):
        llava_hf.main()

    assert not output.exists()


# ── Conversion fidelity ──────────────────────────────────────────────────────
# Copying tensors is not the property that matters. What matters is that the
# real LlavaMultiModalProjector, loaded with the converted tensors and the
# resolved activation, computes the same function as our VisionProjector.

def build_hf_projector(hidden_act: str, vision_hidden: int, llm_hidden: int):
    from transformers import CLIPVisionConfig, LlamaConfig, LlavaConfig
    from transformers.models.llava.modeling_llava import LlavaMultiModalProjector

    # LlavaMultiModalProjector reads only the two hidden sizes, but the configs
    # holding them validate that their own hidden size divides by their head
    # count. Their defaults (32 and 12) do not divide the small widths these
    # tests use, so the head counts are set here to keep the config buildable.
    heads = 8
    config = LlavaConfig(
        text_config=LlamaConfig(hidden_size=llm_hidden, num_attention_heads=heads,
                                num_key_value_heads=heads),
        vision_config=CLIPVisionConfig(hidden_size=vision_hidden,
                                       num_attention_heads=heads),
        projector_hidden_act=hidden_act,
        vision_feature_layer=-2,
    )
    return LlavaMultiModalProjector(config).eval()


@pytest.mark.parametrize("projector_type", LLAVA_HF_CONVERTIBLE)
def test_the_converted_projector_computes_the_same_function(llava_hf, projector_type):
    ours = VisionProjector(
        vision_hidden_size=64, llm_hidden_size=96, projector_type=projector_type
    ).eval()

    converted, hidden_act = llava_hf.convert_projector(
        {}, ours.state_dict(), torch.float32
    )
    theirs = build_hf_projector(hidden_act, 64, 96)
    theirs.load_state_dict(
        {k.removeprefix("multi_modal_projector."): v for k, v in converted.items()},
        strict=True,
    )

    features = torch.randn(2, 20, 64)
    with torch.no_grad():
        assert torch.equal(ours(features), theirs(features))


@pytest.mark.parametrize("projector_type", LLAVA_HF_CONVERTIBLE)
def test_the_converted_tensors_load_strictly_into_the_real_module(llava_hf, projector_type):
    """A key the HF module does not expect would silently go nowhere."""
    ours = VisionProjector(
        vision_hidden_size=64, llm_hidden_size=96, projector_type=projector_type
    )

    converted, hidden_act = llava_hf.convert_projector(
        {}, ours.state_dict(), torch.float32
    )
    theirs = build_hf_projector(hidden_act, 64, 96)

    # strict=True raises on any missing or unexpected key.
    theirs.load_state_dict(
        {k.removeprefix("multi_modal_projector."): v for k, v in converted.items()},
        strict=True,
    )


def test_the_two_layer_mlp_keeps_its_own_second_layer(llava_hf):
    """mlp2x_gelu must carry proj.2, not the identity used for linear."""
    state = projector_state(PROJECTOR_MLP2)

    converted, _ = llava_hf.convert_projector({}, state, torch.float32)

    assert torch.equal(
        converted["multi_modal_projector.linear_1.weight"], state["proj.0.weight"]
    )
    assert torch.equal(
        converted["multi_modal_projector.linear_2.weight"], state["proj.2.weight"]
    )
