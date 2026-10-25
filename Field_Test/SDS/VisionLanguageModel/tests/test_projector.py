"""
Unit tests for the selectable vision projector architectures.

Covers all five values of VLMConfig.projector_type: shape contract,
state_dict round-trip, gradient flow, dtype handling and error reporting.

Run with an interpreter that has torch and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_projector.py
"""
import os
import sys

import pytest
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from model.config import (
    PROJECTOR_TYPES,
    PROJECTOR_CROSS_ATTN,
    PROJECTOR_QFORMER,
    RESAMPLER_PROJECTOR_TYPES,
    VLMConfig,
)
from model.projector import VisionProjector


# Small dimensions keep the tests CPU-fast while staying divisible by the
# head count used below.
VISION_DIM = 64
LLM_DIM = 96
NUM_HEADS = 4
NUM_LAYERS = 2
NUM_QUERY_TOKENS = 8
BATCH = 2
NUM_PATCHES = 12


def build(projector_type: str, **overrides) -> VisionProjector:
    kwargs = dict(
        vision_hidden_size=VISION_DIM,
        llm_hidden_size=LLM_DIM,
        projector_type=projector_type,
        hidden_size=VISION_DIM,
        num_query_tokens=NUM_QUERY_TOKENS,
        num_heads=NUM_HEADS,
        num_layers=NUM_LAYERS,
    )
    kwargs.update(overrides)
    return VisionProjector(**kwargs)


def expected_tokens(projector_type: str, num_patches: int) -> int:
    if projector_type in RESAMPLER_PROJECTOR_TYPES:
        return NUM_QUERY_TOKENS
    return num_patches


# ── Registry ─────────────────────────────────────────────────────────────────

def test_registry_lists_exactly_the_five_supported_types():
    assert PROJECTOR_TYPES == (
        "linear",
        "mlp2x_gelu",
        "mlp3x_gelu",
        "cross_attn",
        "qformer",
    )


def test_unknown_projector_type_raises_and_names_every_option():
    with pytest.raises(ValueError) as excinfo:
        build("bogus")
    message = str(excinfo.value)
    for name in PROJECTOR_TYPES:
        assert name in message


# ── Shape contract ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_forward_output_shape(projector_type):
    projector = build(projector_type)
    features = torch.randn(BATCH, NUM_PATCHES, VISION_DIM)

    out = projector(features)

    assert out.shape == (
        BATCH,
        expected_tokens(projector_type, NUM_PATCHES),
        LLM_DIM,
    )


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_output_num_tokens_matches_forward(projector_type):
    projector = build(projector_type)
    features = torch.randn(BATCH, NUM_PATCHES, VISION_DIM)

    out = projector(features)

    assert projector.output_num_tokens(NUM_PATCHES) == out.shape[1]


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_resampler_output_is_independent_of_patch_count(projector_type):
    projector = build(projector_type)

    short = projector(torch.randn(BATCH, 5, VISION_DIM))
    long = projector(torch.randn(BATCH, 577, VISION_DIM))

    assert short.shape == long.shape == (BATCH, NUM_QUERY_TOKENS, LLM_DIM)


# ── Learned queries ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_the_output_depends_on_the_vision_features(projector_type):
    """
    A resampler that ignored its context would still pass every shape test
    while learning nothing from the image, so pin that the vision features
    actually reach the output.
    """
    torch.manual_seed(0)
    projector = build(projector_type).eval()

    with torch.no_grad():
        first = projector(torch.randn(1, NUM_PATCHES, VISION_DIM))
        second = projector(torch.randn(1, NUM_PATCHES, VISION_DIM))

    assert not torch.allclose(first, second, atol=1e-6)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_gradients_reach_the_vision_features(projector_type):
    """The vision encoder must be trainable through the projector."""
    projector = build(projector_type)
    features = torch.randn(1, NUM_PATCHES, VISION_DIM, requires_grad=True)

    projector(features).sum().backward()

    assert features.grad is not None
    assert features.grad.abs().sum() > 0


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_cross_attention_takes_the_queries_as_query_and_context_as_key_value(projector_type):
    """
    Swapping the roles would make the output length follow the patch count
    instead of the query count, so the token count is the observable proof.
    """
    projector = build(projector_type).eval()

    with torch.no_grad():
        out = projector(torch.randn(1, 137, VISION_DIM))

    assert out.shape[1] == NUM_QUERY_TOKENS
    assert out.shape[1] != 137


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_every_batch_element_sees_its_own_features(projector_type):
    """The shared query parameter is expanded, so rows must not be identical."""
    projector = build(projector_type).eval()
    features = torch.randn(3, NUM_PATCHES, VISION_DIM)

    with torch.no_grad():
        out = projector(features)

    assert not torch.allclose(out[0], out[1], atol=1e-6)
    assert not torch.allclose(out[1], out[2], atol=1e-6)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_shared_query_accumulates_gradient_over_the_whole_batch(projector_type):
    """
    forward() expands one query parameter across the batch, so its gradient must
    be the SUM over batch elements, not just the last one's. Run in float64:
    in float32 the two accumulation orders differ by rounding alone.
    """
    def query_grad(features):
        torch.manual_seed(7)
        projector = build(projector_type, num_layers=1).to(torch.float64)
        projector(features.to(torch.float64)).sum().backward()
        return projector.proj.query.grad.clone()

    torch.manual_seed(11)
    features = torch.randn(3, NUM_PATCHES, VISION_DIM)

    batched = query_grad(features)
    summed = sum(query_grad(features[i : i + 1]) for i in range(3))

    assert batched.abs().max() > 0
    assert torch.allclose(batched, summed, rtol=1e-10)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_query_parameter_is_not_mutated_by_a_forward_pass(projector_type):
    """expand() returns a view, so an in-place write would corrupt the parameter."""
    projector = build(projector_type)
    before = projector.proj.query.detach().clone()

    projector(torch.randn(3, NUM_PATCHES, VISION_DIM)).sum().backward()

    assert torch.equal(before, projector.proj.query.detach())


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_batching_matches_single_sample_forwarding(projector_type):
    """No cross-talk between batch elements."""
    projector = build(projector_type).eval()
    features = torch.randn(3, NUM_PATCHES, VISION_DIM)

    with torch.no_grad():
        batched = projector(features)
        singles = torch.cat([projector(features[i : i + 1]) for i in range(3)])

    assert torch.allclose(batched, singles, atol=1e-5)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_resampler_query_parameter_is_saved(projector_type):
    projector = build(projector_type)

    assert "proj.query" in projector.state_dict()
    assert projector.state_dict()["proj.query"].shape == (NUM_QUERY_TOKENS, VISION_DIM)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_query_init_survives_the_xavier_pass(projector_type):
    """
    VisionProjector._init_weights runs after QueryResampler.__init__ and xavier-
    inits every nn.Linear. It must not reach the query parameter, whose
    trunc_normal_(std=0.02) init is deliberately narrower than xavier's.
    """
    projector = build(projector_type, hidden_size=1024, num_query_tokens=32)

    query = projector.proj.query
    assert 0.01 < query.std().item() < 0.03
    assert abs(query.mean().item()) < 0.01


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_each_block_normalizes_before_its_sublayer(projector_type):
    """Pre-layernorm residual structure, one norm per sublayer, no double norm."""
    projector = build(projector_type)

    for block in projector.proj.blocks:
        assert isinstance(block.cross_attn_norm, torch.nn.LayerNorm)
        assert isinstance(block.context_norm, torch.nn.LayerNorm)
        assert isinstance(block.ffn_norm, torch.nn.LayerNorm)
        assert hasattr(block, "self_attn_norm") == block.self_attention


@pytest.mark.parametrize("self_attention", [False, True])
def test_the_norms_are_applied_before_the_sublayers_not_after(self_attention):
    """
    The test above only pins that the LayerNorms exist under those names. A
    post-layernorm block, normalizing the residual sum instead of the input,
    would carry the same module names and pass it.

    What separates the two is measurable. In a pre-LN block the residual path is
    untouched, so zeroing every sublayer's output projection makes the block the
    exact identity. A post-LN block would return LayerNorm(input) instead.
    """
    from model.projector import ResamplerBlock

    torch.manual_seed(0)
    block = ResamplerBlock(
        hidden_size=VISION_DIM, num_heads=NUM_HEADS, ffn_ratio=4.0,
        dropout=0.0, self_attention=self_attention,
    ).eval()

    with torch.no_grad():
        block.cross_attn.out_proj.weight.zero_()
        block.cross_attn.out_proj.bias.zero_()
        block.ffn[-1].weight.zero_()
        block.ffn[-1].bias.zero_()
        if self_attention:
            block.self_attn.out_proj.weight.zero_()
            block.self_attn.out_proj.bias.zero_()

    queries = torch.randn(3, NUM_QUERY_TOKENS, VISION_DIM)
    context = torch.randn(3, NUM_PATCHES, VISION_DIM)

    with torch.no_grad():
        out = block(queries, context)

    assert torch.equal(out, queries)


def test_qformer_block_has_query_self_attention_and_cross_attn_does_not():
    qformer = build(PROJECTOR_QFORMER)
    cross_attn = build(PROJECTOR_CROSS_ATTN)

    assert all(block.self_attention for block in qformer.proj.blocks)
    assert not any(block.self_attention for block in cross_attn.proj.blocks)
    assert sum(p.numel() for p in qformer.parameters()) > sum(
        p.numel() for p in cross_attn.parameters()
    )


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_num_layers_is_honored(projector_type):
    shallow = build(projector_type, num_layers=2)
    deep = build(projector_type, num_layers=4)

    assert len(shallow.proj.blocks) == 2
    assert len(deep.proj.blocks) == 4
    assert sum(p.numel() for p in deep.parameters()) > sum(
        p.numel() for p in shallow.parameters()
    )


# ── Weight persistence ───────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_state_dict_round_trip_reports_no_missing_or_unexpected_keys(projector_type):
    source = build(projector_type)
    target = build(projector_type)

    missing, unexpected = target.load_weights(source.state_dict())

    assert list(missing) == []
    assert list(unexpected) == []


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_load_weights_accepts_a_whole_model_state_dict(projector_type):
    """
    A whole-model dict carries the projector under a `projector.` prefix
    alongside its siblings. The prefix is stripped and the siblings dropped.
    """
    source = build(projector_type)
    target = build(projector_type)
    whole_model = {f"projector.{k}": v for k, v in source.state_dict().items()}
    whole_model["vision_encoder.model.embeddings.patch_embedding.weight"] = torch.zeros(3, 3)
    whole_model["language_model.model.layers.0.mlp.gate_proj.weight"] = torch.zeros(4, 4)

    missing, unexpected = target.load_weights(whole_model)

    assert list(missing) == []
    assert list(unexpected) == []


@pytest.mark.parametrize("foreign_key", [
    "multi_modal_projector.linear_1.weight",   # LLaVA-HF
    "model.mm_projector.0.weight",             # upstream LLaVA
])
def test_a_foreign_projector_layout_is_rejected_on_its_leaf_names(foreign_key):
    """
    Only the `projector.` prefix is translated, never the leaf names, so these
    layouts cannot be imported. Rejecting them beats appearing to accept them.
    """
    target = build("mlp2x_gelu")

    with pytest.raises(ValueError):
        target.load_weights({foreign_key: torch.zeros(96, 64)})


def test_a_missing_projector_key_inside_a_whole_model_dict_is_still_reported():
    """Dropping siblings must not swallow a genuine gap in the projector."""
    source = build("mlp2x_gelu")
    whole_model = {f"projector.{k}": v for k, v in source.state_dict().items()}
    del whole_model["projector.proj.0.weight"]
    whole_model["vision_encoder.anything"] = torch.zeros(2, 2)

    with pytest.raises(ValueError) as excinfo:
        build("mlp2x_gelu").load_weights(whole_model)

    assert "proj.0.weight" in str(excinfo.value)


def test_a_dict_with_no_projector_keys_at_all_is_rejected():
    with pytest.raises(ValueError):
        build("mlp2x_gelu").load_weights({"vision_encoder.anything": torch.zeros(2, 2)})


def test_a_sibling_named_key_is_a_stray_when_no_prefix_was_stripped():
    """
    The gate runs both ways: siblings are only dropped when a `projector.`
    prefix was actually seen, so in a projector-only dict such a key is a
    mistake rather than a sibling.
    """
    source = build("mlp2x_gelu")
    projector_only = dict(source.state_dict())
    projector_only["vision_encoder.anything"] = torch.zeros(2, 2)

    with pytest.raises(ValueError) as excinfo:
        build("mlp2x_gelu").load_weights(projector_only)

    assert "vision_encoder.anything" in str(excinfo.value)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_strict_false_really_loads_the_weights_that_do_match(projector_type):
    """A tolerated mismatch must not mean nothing was loaded."""
    source = build(projector_type, num_heads=8)
    target = build(projector_type, num_heads=4)

    target.load_weights(source.state_dict(), strict=False)

    assert torch.equal(target.proj.query.detach(), source.proj.query.detach())


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_load_weights_does_not_mutate_the_callers_dict(projector_type):
    """Callers reuse a loaded checkpoint; the internal drops must be local."""
    source = build(projector_type)
    state = source.state_dict()
    keys_before = set(state)

    build(projector_type).load_weights(state)

    assert set(state) == keys_before


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_a_stray_projector_key_is_still_rejected(projector_type):
    """Dropping sibling-module keys must not also swallow genuine mistakes."""
    source = build(projector_type)
    corrupted = dict(source.state_dict())
    corrupted["proj.bogus_layer.weight"] = torch.zeros(2, 2)

    with pytest.raises(ValueError) as excinfo:
        build(projector_type).load_weights(corrupted)

    assert "proj.bogus_layer.weight" in str(excinfo.value)


def test_loading_a_mismatched_architecture_raises():
    """Selectable projectors make this mismatch possible; it must not pass silently."""
    qformer = build(PROJECTOR_QFORMER)
    mlp = build("mlp2x_gelu")

    with pytest.raises(ValueError) as excinfo:
        mlp.load_weights(qformer.state_dict())

    message = str(excinfo.value)
    assert "mlp2x_gelu" in message
    assert "vlm_config.json" in message


def test_a_differing_layer_count_raises():
    """More blocks in the checkpoint means extra key names."""
    source = build(PROJECTOR_QFORMER, num_layers=4)
    target = build(PROJECTOR_QFORMER, num_layers=2)

    with pytest.raises(ValueError):
        target.load_weights(source.state_dict())


# The key names are IDENTICAL when only a shape changes, so load_state_dict
# reports nothing missing or unexpected and raises its own RuntimeError
# instead. These are the likeliest real mistakes: Phase 1 trained at one query
# count or width, Phase 2 launched at the default.

def test_a_differing_query_count_raises_with_actionable_detail():
    source = build(PROJECTOR_QFORMER, num_query_tokens=48)
    target = build(PROJECTOR_QFORMER, num_query_tokens=32)

    with pytest.raises(ValueError) as excinfo:
        target.load_weights(source.state_dict())

    message = str(excinfo.value)
    assert "proj.query" in message
    assert "(48," in message and "(32," in message
    assert "vlm_config.json" in message


def test_a_differing_resampler_width_raises():
    source = build(PROJECTOR_CROSS_ATTN, hidden_size=64, num_heads=4)
    target = build(PROJECTOR_CROSS_ATTN, hidden_size=128, num_heads=4)

    with pytest.raises(ValueError) as excinfo:
        target.load_weights(source.state_dict())

    assert "vlm_config.json" in str(excinfo.value)


MISMATCH_CASES = [
    ("wrong architecture", dict(projector_type=PROJECTOR_QFORMER), dict(projector_type="mlp2x_gelu")),
    ("wrong query count", dict(projector_type=PROJECTOR_QFORMER, num_query_tokens=48),
     dict(projector_type=PROJECTOR_QFORMER, num_query_tokens=32)),
    ("wrong width", dict(projector_type=PROJECTOR_CROSS_ATTN, hidden_size=64, num_heads=4),
     dict(projector_type=PROJECTOR_CROSS_ATTN, hidden_size=128, num_heads=4)),
    ("wrong layer count", dict(projector_type=PROJECTOR_QFORMER, num_layers=4),
     dict(projector_type=PROJECTOR_QFORMER, num_layers=2)),
    ("wrong head count", dict(projector_type=PROJECTOR_QFORMER, num_heads=8),
     dict(projector_type=PROJECTOR_QFORMER, num_heads=4)),
]


# num_heads is the one architecture scalar nn.MultiheadAttention keeps as a
# plain int: it changes no key name and no tensor shape. Without the recorded
# signature, a 16-head checkpoint loads into an 8-head projector reporting zero
# missing and zero unexpected keys, with every head boundary silently wrong.

@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_head_count_is_recorded_in_the_state_dict(projector_type):
    state = build(projector_type, num_heads=4).state_dict()

    assert "proj.arch_signature" in state
    assert state["proj.arch_signature"].tolist()[1] == 4


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_head_count_mismatch_is_caught_and_named(projector_type):
    source = build(projector_type, num_heads=8)

    with pytest.raises(ValueError) as excinfo:
        build(projector_type, num_heads=4).load_weights(source.state_dict())

    message = str(excinfo.value)
    assert "num_heads" in message
    assert "checkpoint=8" in message and "projector=4" in message


def test_the_per_patch_projectors_carry_no_signature():
    """Only the resamplers have resampler scalars to record."""
    for projector_type in ("linear", "mlp2x_gelu", "mlp3x_gelu"):
        assert "proj.arch_signature" not in build(projector_type).state_dict()


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_signatureless_checkpoint_still_loads_its_weights(projector_type):
    """
    A resampler checkpoint saved before the signature existed must load. An
    absent signature is an unknown, not a missing weight, so it is not counted.
    """
    source = build(projector_type)
    legacy = {k: v for k, v in source.state_dict().items() if k != "proj.arch_signature"}

    missing, unexpected = build(projector_type).load_weights(legacy)

    assert list(missing) == []
    assert list(unexpected) == []


# The signature records how THIS module was constructed. Loading a checkpoint's
# values over it would leave the buffer describing an architecture the module
# does not have, and the field that exists to detect a mismatch would then be
# corrupted by the very mismatch it is meant to catch.

@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_signature_is_never_overwritten_by_a_checkpoint(projector_type):
    target = build(projector_type, num_heads=4)
    before = target.proj.arch_signature.tolist()

    target.load_weights(build(projector_type, num_heads=8).state_dict(), strict=False)

    assert target.proj.arch_signature.tolist() == before
    assert target.proj.blocks[0].cross_attn.num_heads == before[1]


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_tolerated_mismatch_does_not_poison_the_next_save(projector_type):
    """Re-saving after strict=False must not reject its own correct weights."""
    target = build(projector_type, num_heads=4)
    target.load_weights(build(projector_type, num_heads=8).state_dict(), strict=False)

    missing, unexpected = build(projector_type, num_heads=4).load_weights(
        target.state_dict()
    )

    assert list(missing) == []
    assert list(unexpected) == []


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_signature_of_the_wrong_length_is_reported_as_a_shape_mismatch(projector_type):
    source = build(projector_type)
    corrupted = dict(source.state_dict())
    corrupted["proj.arch_signature"] = torch.tensor([1, 2, 3], dtype=torch.int64)

    with pytest.raises(ValueError) as excinfo:
        build(projector_type).load_weights(corrupted)

    assert "proj.arch_signature" in str(excinfo.value)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_the_signature_survives_a_dtype_cast(projector_type):
    """build_model casts the projector to bfloat16; an int64 buffer must not follow."""
    projector = build(projector_type, num_heads=4).to(dtype=torch.bfloat16)

    assert projector.proj.arch_signature.dtype == torch.int64
    assert projector.proj.arch_signature.tolist()[1] == 4


@pytest.mark.parametrize("label, source_kwargs, target_kwargs", MISMATCH_CASES)
def test_every_kind_of_mismatch_raises_the_same_actionable_error(label, source_kwargs, target_kwargs):
    source = build(**source_kwargs)
    target = build(**target_kwargs)

    with pytest.raises(ValueError) as excinfo:
        target.load_weights(source.state_dict())

    assert "vlm_config.json" in str(excinfo.value)


@pytest.mark.parametrize("victim", [
    "proj.query",
    "proj.context_proj.weight",
    "proj.out_proj.weight",
    "proj.blocks.0.cross_attn.in_proj_weight",
    "proj.blocks.1.ffn.0.weight",
])
def test_a_single_wrong_shape_anywhere_is_caught_and_named(victim):
    """
    Every key name still matches, so load_state_dict reports nothing missing or
    unexpected. Only the shape comparison catches these.
    """
    source = build(PROJECTOR_QFORMER, num_layers=2)
    corrupted = {k: v.clone() for k, v in source.state_dict().items()}
    corrupted[victim] = torch.zeros(1, 1)

    with pytest.raises(ValueError) as excinfo:
        build(PROJECTOR_QFORMER, num_layers=2).load_weights(corrupted)

    assert victim in str(excinfo.value)


@pytest.mark.parametrize("label, source_kwargs, target_kwargs", MISMATCH_CASES)
def test_strict_false_downgrades_every_kind_of_mismatch(label, source_kwargs, target_kwargs, capsys):
    """The escape hatch must work for shape mismatches too, not just key mismatches."""
    source = build(**source_kwargs)
    target = build(**target_kwargs)

    target.load_weights(source.state_dict(), strict=False)

    assert "do not match" in capsys.readouterr().out


def test_the_mismatch_report_truncates_long_key_lists():
    qformer = build(PROJECTOR_QFORMER)
    mlp = build("mlp2x_gelu")

    with pytest.raises(ValueError) as excinfo:
        mlp.load_weights(qformer.state_dict())

    assert "more)" in str(excinfo.value)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_loaded_weights_reproduce_the_source_output(projector_type):
    source = build(projector_type).eval()
    target = build(projector_type).eval()
    target.load_weights(source.state_dict())
    features = torch.randn(BATCH, NUM_PATCHES, VISION_DIM)

    with torch.no_grad():
        assert torch.allclose(source(features), target(features), atol=1e-6)


# ── Gradient flow ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_every_trainable_parameter_receives_a_gradient(projector_type):
    projector = build(projector_type)
    features = torch.randn(BATCH, NUM_PATCHES, VISION_DIM)

    projector(features).sum().backward()

    ungrad = [
        name
        for name, param in projector.named_parameters()
        if param.requires_grad and param.grad is None
    ]
    assert ungrad == []


# ── dtype handling ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_bfloat16_forward(projector_type):
    projector = build(projector_type).to(dtype=torch.bfloat16)
    features = torch.randn(BATCH, NUM_PATCHES, VISION_DIM, dtype=torch.bfloat16)

    out = projector(features)

    assert out.dtype == torch.bfloat16
    assert projector.dtype == torch.bfloat16


# ── Validation ───────────────────────────────────────────────────────────────

def test_head_count_must_divide_the_resampler_hidden_size():
    with pytest.raises(ValueError, match="divisible"):
        build(PROJECTOR_QFORMER, hidden_size=65, num_heads=4)


@pytest.mark.parametrize("bad_layers", [0, -1])
def test_resampler_rejects_a_non_positive_layer_count(bad_layers):
    with pytest.raises(ValueError, match="at least one layer"):
        build(PROJECTOR_CROSS_ATTN, num_layers=bad_layers)


@pytest.mark.parametrize("bad_queries", [0, -3])
def test_resampler_rejects_a_non_positive_query_count(bad_queries):
    with pytest.raises(ValueError, match="at least one query token"):
        build(PROJECTOR_CROSS_ATTN, num_query_tokens=bad_queries)


# ── The builder's warning about that ─────────────────────────────────────────

def test_the_config_can_tell_the_resampler_video_combination_apart():
    """
    The condition build_model warns on. Checked through VLMConfig because
    build_model itself loads a real CLIP and a real 8B LLM.
    """
    from model.config import VISION_LANGUAGEBIND

    video = "LanguageBind/Video-LanguageBind"
    image = "openai/clip-vit-large-patch14-336"

    for projector_type in RESAMPLER_PROJECTOR_TYPES:
        config = VLMConfig(vision_model_name=video, projector_type=projector_type)
        assert config.is_resampler_projector
        assert config.vision_model_type == VISION_LANGUAGEBIND

        # Same projector, image encoder: nothing to warn about.
        assert VLMConfig(vision_model_name=image,
                         projector_type=projector_type).vision_model_type != VISION_LANGUAGEBIND

    for projector_type in [t for t in PROJECTOR_TYPES if t not in RESAMPLER_PROJECTOR_TYPES]:
        # Video encoder, per-patch projector: also nothing to warn about.
        assert not VLMConfig(vision_model_name=video,
                             projector_type=projector_type).is_resampler_projector


def test_the_builder_warns_on_the_resampler_video_combination():
    """
    Nothing downstream can detect this: the run trains and the loss looks
    ordinary. The warning at build time is the only notice the operator gets.
    """
    import ast

    source = open(os.path.join(REPO_ROOT, "model", "vlm_v2.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    builder = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_model"
    )

    # Both names have to appear in the SAME condition, and that branch has to
    # print. Searching the whole function for the two names would pass on an
    # inverted condition, or on a leftover mention after the warning was
    # deleted.
    guards = [
        node for node in ast.walk(builder)
        if isinstance(node, ast.If)
        and "is_resampler_projector" in ast.unparse(node.test)
        and "VISION_LANGUAGEBIND" in ast.unparse(node.test)
    ]
    assert len(guards) == 1, f"expected one guard, found {len(guards)}"
    assert "print" in ast.unparse(guards[0].body), "the guard branch says nothing"

    # And the name it compares against must be imported, or the check raises
    # NameError at build time instead of warning.
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "VISION_LANGUAGEBIND" in imported


# ── Sequence order ───────────────────────────────────────────────────────────
# The resamplers add no positional embedding to the context, on the grounds that
# the ViT already put position inside each feature vector. The measurable
# consequence is invariance to permutations of the sequence axis. Pinned here
# because it is what makes a resampler unusable with the LanguageBind path,
# which concatenates independently encoded frames so that frame identity lives
# only in the index.

@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_resampler_ignores_the_order_of_its_input_sequence(projector_type):
    projector = build(projector_type).eval()
    features = torch.randn(1, NUM_PATCHES, VISION_DIM)
    shuffled = features[:, torch.randperm(NUM_PATCHES)]

    with torch.no_grad():
        assert torch.allclose(projector(features), projector(shuffled), atol=1e-5)


@pytest.mark.parametrize(
    "projector_type",
    [t for t in PROJECTOR_TYPES if t not in RESAMPLER_PROJECTOR_TYPES],
)
def test_a_per_patch_projector_keeps_the_order_of_its_input_sequence(projector_type):
    """The contrast: these carry the index through, so the LLM can recover it."""
    projector = build(projector_type).eval()
    features = torch.randn(1, NUM_PATCHES, VISION_DIM)
    permutation = torch.randperm(NUM_PATCHES)

    with torch.no_grad():
        out = projector(features)
        shuffled_out = projector(features[:, permutation])

    # Same multiset of rows, different order.
    assert torch.allclose(out[:, permutation], shuffled_out, atol=1e-5)
    assert not torch.allclose(out, shuffled_out, atol=1e-3)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_resampler_still_reads_its_input(projector_type):
    """
    Order-invariance must not be confused with ignoring the input. A projector
    that returned a constant would pass the permutation test above.
    """
    projector = build(projector_type).eval()
    features = torch.randn(1, NUM_PATCHES, VISION_DIM)
    perturbed = features.clone()
    perturbed[0, NUM_PATCHES // 2] += 5.0

    with torch.no_grad():
        assert not torch.allclose(projector(features), projector(perturbed), atol=1e-3)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
@pytest.mark.parametrize("bad_ratio", [0.0, 1.0 / (VISION_DIM + 1)])
def test_resampler_rejects_an_ffn_ratio_that_rounds_the_width_to_zero(
    projector_type, bad_ratio
):
    """nn.Linear accepts out_features=0, so this would otherwise build silently."""
    with pytest.raises(ValueError, match="feed-forward width"):
        build(projector_type, ffn_ratio=bad_ratio)


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_a_narrow_but_usable_ffn_ratio_is_still_accepted(projector_type):
    """The guard must not reject a deliberately small feed-forward width."""
    projector = build(projector_type, ffn_ratio=1.0 / VISION_DIM)

    out = projector(torch.randn(2, NUM_PATCHES, VISION_DIM))

    assert out.shape == (2, NUM_QUERY_TOKENS, LLM_DIM)
    ffn_widths = {block.ffn[0].out_features for block in projector.proj.blocks}
    assert ffn_widths == {1}


@pytest.mark.parametrize(
    "projector_type",
    [t for t in PROJECTOR_TYPES if t not in RESAMPLER_PROJECTOR_TYPES],
)
def test_the_ffn_guard_does_not_reach_the_per_patch_projectors(projector_type):
    """These types have no feed-forward network, so the ratio is theirs to ignore."""
    projector = build(projector_type, ffn_ratio=0.0)

    out = projector(torch.randn(2, NUM_PATCHES, VISION_DIM))

    assert out.shape == (2, NUM_PATCHES, LLM_DIM)


# ── Config integration ───────────────────────────────────────────────────────

@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_config_round_trips_through_json(projector_type):
    import json

    config = VLMConfig(projector_type=projector_type, projector_num_query_tokens=64)

    restored = json.loads(json.dumps(config.to_dict()))

    assert restored["projector_type"] == projector_type
    assert restored["projector_num_query_tokens"] == 64
    assert restored["projector_num_heads"] == config.projector_num_heads
    assert restored["projector_num_layers"] == config.projector_num_layers
    assert restored["projector_ffn_ratio"] == config.projector_ffn_ratio
    assert restored["projector_dropout"] == config.projector_dropout
    assert "projector_hidden_size" in restored


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_config_provides_what_the_hf_trainer_callbacks_call(projector_type):
    """
    TensorBoardCallback.on_train_begin calls model.config.to_json_string() and
    WandbCallback calls to_dict(). train.py always enables tensorboard, so a
    missing to_json_string aborts training before the first step.
    """
    import json

    config = VLMConfig(projector_type=projector_type, projector_num_query_tokens=48)

    rendered = config.to_json_string()

    assert isinstance(rendered, str)
    restored = json.loads(rendered)
    assert restored["projector_type"] == projector_type
    assert restored["projector_num_query_tokens"] == 48
    assert restored == config.to_dict()


def test_config_json_survives_a_value_json_cannot_serialize():
    """A config that cannot serialize must not take a training run down."""
    import json

    config = VLMConfig(projector_type="qformer")
    config.vision_hidden_size = object()   # deliberately unserializable

    restored = json.loads(config.to_json_string())

    assert isinstance(restored["vision_hidden_size"], str)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_config_projector_output_tokens_matches_the_built_projector(projector_type):
    config = VLMConfig(
        projector_type=projector_type,
        projector_num_query_tokens=NUM_QUERY_TOKENS,
        projector_num_heads=NUM_HEADS,
        projector_num_layers=NUM_LAYERS,
        projector_hidden_size=VISION_DIM,
    )
    config.vision_hidden_size = VISION_DIM
    config.vision_num_patches = NUM_PATCHES
    config.llm_hidden_size = LLM_DIM

    projector = VisionProjector(
        vision_hidden_size=config.vision_hidden_size,
        llm_hidden_size=config.llm_hidden_size,
        projector_type=config.projector_type,
        **config.projector_kwargs(),
    )

    assert config.projector_output_tokens == projector.output_num_tokens(NUM_PATCHES)
    assert config.is_resampler_projector == (projector_type in RESAMPLER_PROJECTOR_TYPES)


def test_resampler_hidden_size_defaults_to_the_vision_width():
    projector = VisionProjector(
        vision_hidden_size=VISION_DIM,
        llm_hidden_size=LLM_DIM,
        projector_type=PROJECTOR_QFORMER,
        hidden_size=None,
        num_query_tokens=NUM_QUERY_TOKENS,
        num_heads=NUM_HEADS,
        num_layers=1,
    )

    assert projector.proj.query.shape == (NUM_QUERY_TOKENS, VISION_DIM)
