"""
Model-level tests for projector selection.

VisionLanguageModelV2 splices the projector output into the LLM sequence at the
<image> token, so the sequence length depends on how many tokens the projector
emits. These tests drive that path with stand-in vision and language modules so
no pretrained weights are needed.

Run with an interpreter that has torch and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_vlm_projector_integration.py
"""
import os
import sys

import pytest
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.config import PROJECTOR_TYPES, RESAMPLER_PROJECTOR_TYPES, VLMConfig
from model.projector import VisionProjector
from model.vlm_v2 import VisionLanguageModelV2


VISION_DIM = 64
LLM_DIM = 96
VOCAB = 50
NUM_PATCHES = 12
NUM_QUERY_TOKENS = 5
IMAGE_TOKEN_ID = 49


class StubVisionEncoder(nn.Module):
    """Mimics VisionEncoderWrapper's interface with a single linear layer."""

    def __init__(self):
        super().__init__()
        self.embed = nn.Linear(3, VISION_DIM)

    @property
    def dtype(self):
        return self.embed.weight.dtype

    @property
    def hidden_size(self):
        return VISION_DIM

    @property
    def num_image_tokens(self):
        return NUM_PATCHES

    def forward(self, pixel_values):
        batch = pixel_values.shape[0]
        flat = pixel_values.reshape(batch, -1, 3)[:, :NUM_PATCHES]
        return self.embed(flat)


class StubLanguageModelOutput:
    def __init__(self, loss, logits):
        self.loss = loss
        self.logits = logits


class StubLanguageModel(nn.Module):
    """Consumes inputs_embeds and reports the sequence length it received."""

    def __init__(self):
        super().__init__()
        self.embed_tokens = nn.Embedding(VOCAB, LLM_DIM)
        self.head = nn.Linear(LLM_DIM, VOCAB)
        self.last_seen_length = None

    def forward(self, inputs_embeds, attention_mask=None, labels=None, return_dict=True):
        self.last_seen_length = inputs_embeds.shape[1]
        logits = self.head(inputs_embeds)
        loss = None
        if labels is not None:
            loss = nn.functional.cross_entropy(
                logits.reshape(-1, VOCAB), labels.reshape(-1), ignore_index=-100
            )
        return StubLanguageModelOutput(loss=loss, logits=logits)


def build_model(projector_type: str) -> VisionLanguageModelV2:
    config = VLMConfig(
        projector_type=projector_type,
        projector_num_query_tokens=NUM_QUERY_TOKENS,
        projector_num_heads=4,
        projector_num_layers=2,
        projector_hidden_size=VISION_DIM,
    )
    config.vision_hidden_size = VISION_DIM
    config.vision_num_patches = NUM_PATCHES
    config.llm_hidden_size = LLM_DIM
    config.image_token_id = IMAGE_TOKEN_ID

    projector = VisionProjector(
        vision_hidden_size=VISION_DIM,
        llm_hidden_size=LLM_DIM,
        projector_type=projector_type,
        **config.projector_kwargs(),
    )
    config.num_image_tokens = projector.output_num_tokens(config.vision_num_patches)

    return VisionLanguageModelV2(
        config=config,
        vision_encoder=StubVisionEncoder(),
        projector=projector,
        language_model=StubLanguageModel(),
    )


def make_batch(batch: int = 2, text_len: int = 7):
    input_ids = torch.randint(0, VOCAB - 1, (batch, text_len))
    input_ids[:, 2] = IMAGE_TOKEN_ID
    attention_mask = torch.ones_like(input_ids)
    labels = input_ids.clone()
    pixel_values = torch.randn(batch, 3, 8, 8)
    return input_ids, attention_mask, pixel_values, labels


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_encode_images_emits_the_configured_token_count(projector_type):
    model = build_model(projector_type)
    _, _, pixel_values, _ = make_batch()

    features = model.encode_images(pixel_values)

    assert features.shape == (2, model.config.num_image_tokens, LLM_DIM)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_sequence_length_accounting(projector_type):
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)

    embeds, mask, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    expected_len = input_ids.shape[1] + model.config.num_image_tokens - 1
    assert embeds.shape == (2, expected_len, LLM_DIM)
    assert mask.shape == (2, expected_len)
    assert out_labels.shape == (2, expected_len)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_image_positions_are_masked_out_of_the_loss(projector_type):
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)

    _, _, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    image_span = out_labels[:, 2 : 2 + model.config.num_image_tokens]
    assert torch.all(image_span == -100)


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_forward_backward_reaches_the_projector(projector_type):
    model = build_model(projector_type)
    for param in model.language_model.parameters():
        param.requires_grad = False
    input_ids, attention_mask, pixel_values, labels = make_batch()

    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )
    out.loss.backward()

    ungrad = [
        name
        for name, param in model.projector.named_parameters()
        if param.grad is None
    ]
    assert ungrad == []
    assert model.language_model.last_seen_length == (
        input_ids.shape[1] + model.config.num_image_tokens - 1
    )


@pytest.mark.parametrize("projector_type", RESAMPLER_PROJECTOR_TYPES)
def test_resampler_shortens_the_sequence_relative_to_per_patch_projection(projector_type):
    resampler = build_model(projector_type)
    per_patch = build_model("mlp2x_gelu")

    assert resampler.config.num_image_tokens == NUM_QUERY_TOKENS
    assert per_patch.config.num_image_tokens == NUM_PATCHES
    assert resampler.config.num_image_tokens < per_patch.config.num_image_tokens


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_bfloat16_vision_features_are_cast_to_the_projector_dtype(projector_type):
    model = build_model(projector_type)
    model.projector = model.projector.to(dtype=torch.bfloat16)
    _, _, pixel_values, _ = make_batch()

    features = model.encode_images(pixel_values)

    assert features.dtype == torch.bfloat16


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_a_second_image_token_raises_instead_of_dropping_the_image(projector_type):
    """
    Only the first placeholder is replaced, so extra images were silently
    dropped. Nothing in the repo emits two today, so this guard is inert and
    exists to catch whoever adds multi-image packing.
    """
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)
    input_ids[0, 4] = IMAGE_TOKEN_ID   # sample 0 now has one at 2 and at 4

    with pytest.raises(ValueError) as excinfo:
        model.prepare_inputs_labels_for_multimodal(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            labels=labels,
        )

    assert "Sample 0 has 2" in str(excinfo.value)


@pytest.mark.parametrize("offending_sample", [0, 1])
def test_the_guard_names_the_sample_that_actually_offends(offending_sample):
    """A wrong index would send whoever hits this to the wrong row."""
    model = build_model("qformer")
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)
    input_ids[offending_sample, 4] = IMAGE_TOKEN_ID

    with pytest.raises(ValueError) as excinfo:
        model.prepare_inputs_labels_for_multimodal(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            labels=labels,
        )

    assert f"Sample {offending_sample} has 2" in str(excinfo.value)


def test_the_guard_does_not_weaken_the_zero_image_path():
    """
    A new guard must be shown not to soften a different check, not only to
    fire. The zero-image arm pads to new_L with the pad positions masked out.
    """
    model = build_model("qformer")
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)
    input_ids[:, 2] = 5

    embeds, mask, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    n = model.config.num_image_tokens
    assert embeds.shape[1] == input_ids.shape[1] + n - 1
    # The original tokens stay attended; only the N-1 pad is masked off.
    assert int(mask[0].sum()) == input_ids.shape[1]


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_exactly_one_image_token_is_still_accepted(projector_type):
    """The guard must not fire on the only shape the repo actually produces."""
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)

    embeds, _, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    assert embeds.shape[1] == input_ids.shape[1] + model.config.num_image_tokens - 1


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_an_imageless_sample_with_no_labels_does_not_raise(projector_type):
    """
    The no-<image> branch only bound `lbl` when labels were supplied, so the
    check after the branch hit UnboundLocalError on the first imageless sample.
    Every generate() call passes labels=None, which is exactly this path.
    """
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, _ = make_batch(text_len=7)
    input_ids[:, 2] = 5   # no sample has an <image> token

    embeds, mask, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=None,
    )

    expected_len = input_ids.shape[1] + model.config.num_image_tokens - 1
    assert embeds.shape == (2, expected_len, LLM_DIM)
    assert mask.shape == (2, expected_len)
    assert out_labels is None


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_a_labelless_mixed_batch_does_not_leak_labels_between_samples(projector_type):
    """
    With labels=None, a stale `lbl` from an earlier sample would have been
    appended and produced a labels tensor out of nothing.
    """
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, _ = make_batch(text_len=7)
    input_ids[1, 2] = 5   # sample 0 keeps <image>, sample 1 does not

    _, _, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=None,
    )

    assert out_labels is None


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_generate_runs_on_a_batch_whose_first_sample_has_no_image(projector_type):
    """End-to-end through the same path generate() takes."""
    model = build_model(projector_type)
    input_ids, attention_mask, pixel_values, _ = make_batch(text_len=7)
    input_ids[0, 2] = 5

    embeds, mask, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=None,
    )
    out = model.language_model(inputs_embeds=embeds, attention_mask=mask)

    assert out.logits.shape[1] == embeds.shape[1]


@pytest.mark.parametrize("projector_type", PROJECTOR_TYPES)
def test_text_only_batch_bypasses_the_projector(projector_type):
    model = build_model(projector_type)
    input_ids, attention_mask, _, labels = make_batch()

    embeds, mask, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=None,
        labels=labels,
    )

    assert embeds.shape == (2, input_ids.shape[1], LLM_DIM)
    assert mask.shape == attention_mask.shape
    assert torch.equal(out_labels, labels)


# ── Query-count boundaries ───────────────────────────────────────────────────
# A resampler can emit fewer tokens than the one <image> placeholder it
# replaces, which the per-patch projectors never could. new_L = L + N - 1, so
# N == 1 means the sequence length does not change at all.

def build_resampler_model(num_query_tokens: int) -> VisionLanguageModelV2:
    config = VLMConfig(
        projector_type="qformer",
        projector_num_query_tokens=num_query_tokens,
        projector_num_heads=4,
        projector_num_layers=1,
        projector_hidden_size=VISION_DIM,
    )
    config.vision_hidden_size = VISION_DIM
    config.vision_num_patches = NUM_PATCHES
    config.llm_hidden_size = LLM_DIM
    config.image_token_id = IMAGE_TOKEN_ID

    projector = VisionProjector(
        vision_hidden_size=VISION_DIM,
        llm_hidden_size=LLM_DIM,
        projector_type="qformer",
        **config.projector_kwargs(),
    )
    config.num_image_tokens = projector.output_num_tokens(config.vision_num_patches)

    return VisionLanguageModelV2(
        config=config,
        vision_encoder=StubVisionEncoder(),
        projector=projector,
        language_model=StubLanguageModel(),
    )


@pytest.mark.parametrize("num_query_tokens", [1, 2, 7])
def test_small_query_counts_keep_the_three_outputs_aligned(num_query_tokens):
    model = build_resampler_model(num_query_tokens)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)

    embeds, mask, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    expected_len = input_ids.shape[1] + num_query_tokens - 1
    assert embeds.shape[1] == expected_len
    assert mask.shape[1] == expected_len
    assert out_labels.shape[1] == expected_len
    assert torch.all(out_labels[:, 2 : 2 + num_query_tokens] == -100)


def test_a_single_query_token_leaves_the_sequence_length_unchanged():
    model = build_resampler_model(1)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)

    embeds, _, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    assert embeds.shape[1] == input_ids.shape[1]


def test_a_sample_without_an_image_token_is_padded_to_the_batch_length():
    model = build_resampler_model(4)
    input_ids, attention_mask, pixel_values, labels = make_batch(text_len=7)
    input_ids[1, 2] = 5   # sample 1 loses its <image> placeholder

    embeds, mask, out_labels = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    expected_len = input_ids.shape[1] + 4 - 1
    assert embeds.shape == (2, expected_len, LLM_DIM)
    assert mask.shape == (2, expected_len)
    assert out_labels.shape == (2, expected_len)
    # The padding added for the imageless sample must not be attended to.
    assert torch.all(mask[1, input_ids.shape[1]:] == 0)
