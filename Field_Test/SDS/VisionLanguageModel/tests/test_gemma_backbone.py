"""
Tests for the Gemma 4 language backbone.

Gemma 4 feeds every decoder layer a Per-Layer Embedding (PLE) looked up from the
token ids. This VLM hands the language model inputs_embeds, not ids, because the
projector output is spliced in at the <image> token, so the ids for the spliced
sequence have to be rebuilt and the lookup done here. These tests drive that path
with a randomly initialized Gemma 4 text model small enough to run on CPU.

Run with an interpreter that has torch, transformers >= 5.5 and pytest:
    /home/ywlee/miniforge3/envs/eva/bin/python -m pytest tests/test_gemma_backbone.py
"""
import inspect
import os
import sys

import pytest
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.config import LLM_GEMMA, LLM_LLAMA, LLM_QWEN, VLMConfig
from model.projector import VisionProjector
from model.vlm_v2 import (
    VisionLanguageModelV2,
    _drop_per_layer_inputs_after_prefill,
)

Gemma4ForCausalLM = pytest.importorskip(
    "transformers", reason="transformers is required"
).Gemma4ForCausalLM
from transformers.models.gemma4.configuration_gemma4 import Gemma4TextConfig


VISION_DIM = 16
LLM_DIM = 32
VOCAB = 64
NUM_PATCHES = 6
NUM_LAYERS = 2
PLE_DIM = 8
PAD_TOKEN_ID = 0
IMAGE_TOKEN_ID = 63
GEMMA_MODEL_NAME = "/models/gemma-4-E4B-it"


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
    """A language model that has no per-layer embeddings, like Llama or Qwen."""

    def __init__(self):
        super().__init__()
        self.embed_tokens = nn.Embedding(VOCAB, LLM_DIM)
        self.head = nn.Linear(LLM_DIM, VOCAB)

    def forward(self, inputs_embeds, attention_mask=None, labels=None, return_dict=True):
        return StubLanguageModelOutput(loss=None, logits=self.head(inputs_embeds))


def tiny_gemma_text_config() -> Gemma4TextConfig:
    """The smallest Gemma 4 text config that still exercises the PLE path."""
    return Gemma4TextConfig(
        vocab_size=VOCAB,
        hidden_size=LLM_DIM,
        intermediate_size=64,
        num_hidden_layers=NUM_LAYERS,
        num_attention_heads=2,
        num_key_value_heads=1,
        head_dim=16,
        global_head_dim=16,
        sliding_window=8,
        layer_types=["sliding_attention", "full_attention"],
        num_kv_shared_layers=0,
        vocab_size_per_layer_input=VOCAB,
        hidden_size_per_layer_input=PLE_DIM,
        max_position_embeddings=128,
        pad_token_id=PAD_TOKEN_ID,
    )


def build_vlm(language_model: nn.Module, llm_model_name: str) -> VisionLanguageModelV2:
    config = VLMConfig(llm_model_name=llm_model_name, projector_type="linear")
    config.vision_hidden_size = VISION_DIM
    config.vision_num_patches = NUM_PATCHES
    config.llm_hidden_size = LLM_DIM
    config.image_token_id = IMAGE_TOKEN_ID

    projector = VisionProjector(
        vision_hidden_size=VISION_DIM,
        llm_hidden_size=LLM_DIM,
        projector_type="linear",
        **config.projector_kwargs(),
    )
    config.num_image_tokens = projector.output_num_tokens(NUM_PATCHES)

    return VisionLanguageModelV2(
        config=config,
        vision_encoder=StubVisionEncoder(),
        projector=projector,
        language_model=language_model,
    )


def build_gemma_vlm() -> VisionLanguageModelV2:
    torch.manual_seed(0)
    language_model = Gemma4ForCausalLM(tiny_gemma_text_config())
    language_model.eval()
    _drop_per_layer_inputs_after_prefill(language_model)
    return build_vlm(language_model, GEMMA_MODEL_NAME)


def make_batch(batch: int = 2, text_len: int = 7, with_image_token: bool = True):
    input_ids = torch.randint(1, VOCAB - 2, (batch, text_len))
    if with_image_token:
        input_ids[:, 2] = IMAGE_TOKEN_ID
    attention_mask = torch.ones_like(input_ids)
    labels = input_ids.clone()
    pixel_values = torch.randn(batch, 3, 8, 8)
    return input_ids, attention_mask, pixel_values, labels


# ── Config ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "llm_model_name, expected",
    [
        ("/models/gemma-4-E4B-it", LLM_GEMMA),
        ("google/gemma-4-E4B-it", LLM_GEMMA),
        ("/models/Qwen3-8B", LLM_QWEN),
        ("/models/Llama-3.1-8B-Instruct", LLM_LLAMA),
        ("/models/some-other-model", LLM_LLAMA),
    ],
)
def test_llm_model_type_detection(llm_model_name, expected):
    assert VLMConfig(llm_model_name=llm_model_name).llm_model_type == expected


# ── Id realignment ───────────────────────────────────────────────────────────

def test_expanded_ids_fill_the_image_slots_with_pad():
    model = build_gemma_vlm()
    input_ids, _, _, _ = make_batch(batch=1, text_len=7)
    num_image_tokens = model.config.num_image_tokens
    seq_len = input_ids.shape[1] + num_image_tokens - 1

    expanded = model._expand_input_ids(input_ids, seq_len, has_image=True, pad_id=PAD_TOKEN_ID)

    assert expanded.shape == (1, seq_len)
    # Text on both sides of the placeholder is preserved …
    assert torch.equal(expanded[0, :2], input_ids[0, :2])
    assert torch.equal(expanded[0, 2 + num_image_tokens:], input_ids[0, 3:])
    # … and every position the projector filled carries pad_token_id.
    image_slots = expanded[0, 2:2 + num_image_tokens]
    assert torch.equal(image_slots, torch.full_like(image_slots, PAD_TOKEN_ID))


def test_expanded_ids_pad_a_sample_without_an_image_token():
    model = build_gemma_vlm()
    input_ids, _, _, _ = make_batch(batch=1, text_len=7, with_image_token=False)
    num_image_tokens = model.config.num_image_tokens
    seq_len = input_ids.shape[1] + num_image_tokens - 1

    expanded = model._expand_input_ids(input_ids, seq_len, has_image=True, pad_id=PAD_TOKEN_ID)

    assert torch.equal(expanded[0, :7], input_ids[0])
    tail = expanded[0, 7:]
    assert torch.equal(tail, torch.full_like(tail, PAD_TOKEN_ID))


@pytest.mark.parametrize("image_position", [0, 3, 6])
def test_expanded_ids_line_up_with_the_spliced_embeddings(image_position):
    """
    Every text position in the realigned ids must embed to exactly the vector
    the splice put at that position. This is the property the per-layer lookup
    depends on, and it is the one that breaks if the two ever drift apart.
    """
    model = build_gemma_vlm()
    text_len = 7
    input_ids = torch.randint(1, VOCAB - 2, (1, text_len))
    input_ids[0, image_position] = IMAGE_TOKEN_ID
    pixel_values = torch.randn(1, 3, 8, 8)
    num_image_tokens = model.config.num_image_tokens

    embeds, _, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=torch.ones_like(input_ids),
        pixel_values=pixel_values,
        labels=None,
    )
    expanded = model._expand_input_ids(input_ids, embeds.shape[1], has_image=True, pad_id=PAD_TOKEN_ID)

    assert expanded.shape[1] == embeds.shape[1]
    embed_layer = model._get_embed_layer()
    image_slots = range(image_position, image_position + num_image_tokens)
    for position in range(embeds.shape[1]):
        if position in image_slots:
            continue
        expected = embed_layer(expanded[0, position])
        assert torch.allclose(expected, embeds[0, position], atol=1e-5)


def test_expanded_ids_line_up_for_a_batch_mixing_image_and_text_only():
    model = build_gemma_vlm()
    input_ids = torch.randint(1, VOCAB - 2, (2, 7))
    input_ids[0, 2] = IMAGE_TOKEN_ID          # first sample has an image token
    pixel_values = torch.randn(2, 3, 8, 8)

    embeds, mask, _ = model.prepare_inputs_labels_for_multimodal(
        input_ids=input_ids,
        attention_mask=torch.ones_like(input_ids),
        pixel_values=pixel_values,
        labels=None,
    )
    expanded = model._expand_input_ids(input_ids, embeds.shape[1], has_image=True, pad_id=PAD_TOKEN_ID)

    assert expanded.shape == mask.shape
    # The second sample is padded on the right, and those positions are masked
    # out, so only the real text positions have to agree.
    embed_layer = model._get_embed_layer()
    for position in range(7):
        expected = embed_layer(expanded[1, position])
        assert torch.allclose(expected, embeds[1, position], atol=1e-5)
    assert mask[1, 7:].sum() == 0


def test_expanded_ids_are_unchanged_without_an_image():
    model = build_gemma_vlm()
    input_ids, _, _, _ = make_batch(batch=2, text_len=7)

    expanded = model._expand_input_ids(input_ids, input_ids.shape[1], has_image=False, pad_id=PAD_TOKEN_ID)

    assert torch.equal(expanded, input_ids)


# ── Per-layer embeddings ─────────────────────────────────────────────────────

def test_per_layer_inputs_cover_the_spliced_sequence():
    model = build_gemma_vlm()
    input_ids, _, _, _ = make_batch(batch=2, text_len=7)
    seq_len = input_ids.shape[1] + model.config.num_image_tokens - 1

    per_layer_inputs = model._llm_kwargs(input_ids, seq_len, has_image=True)["per_layer_inputs"]

    assert per_layer_inputs.shape == (2, seq_len, NUM_LAYERS, PLE_DIM)


def test_only_gemma_receives_per_layer_inputs():
    gemma = build_gemma_vlm()
    llama = build_vlm(StubLanguageModel(), "/models/Llama-3.1-8B-Instruct")
    input_ids, _, _, _ = make_batch()
    seq_len = input_ids.shape[1] + gemma.config.num_image_tokens - 1

    assert "per_layer_inputs" in gemma._llm_kwargs(input_ids, seq_len, has_image=True)
    assert llama._llm_kwargs(input_ids, seq_len, has_image=True) == {}


def test_a_model_without_per_layer_embeddings_is_reported():
    model = build_vlm(StubLanguageModel(), GEMMA_MODEL_NAME)

    with pytest.raises(AttributeError, match="get_per_layer_inputs"):
        model._get_text_model()


# ── Forward and generate ─────────────────────────────────────────────────────

def test_forward_returns_logits_for_the_spliced_sequence():
    model = build_gemma_vlm()
    input_ids, attention_mask, pixel_values, labels = make_batch()
    expected_len = input_ids.shape[1] + model.config.num_image_tokens - 1

    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    assert out.logits.shape == (2, expected_len, VOCAB)
    assert torch.isfinite(out.loss)


def test_forward_without_an_image_keeps_the_text_length():
    model = build_gemma_vlm()
    input_ids, attention_mask, _, labels = make_batch()

    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=None,
        labels=labels,
    )

    assert out.logits.shape == (2, input_ids.shape[1], VOCAB)


def test_generate_runs_past_the_prefill_step():
    model = build_gemma_vlm()
    input_ids, attention_mask, pixel_values, _ = make_batch()

    generated = model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        max_new_tokens=4,
        do_sample=False,
    )

    # Decoding steps after the prefill feed input_ids, which the text model
    # refuses to accept alongside per_layer_inputs, so reaching four new tokens
    # is what shows the argument was dropped in time.
    assert generated.shape == (2, 4)


# ── Generation kwarg handling ────────────────────────────────────────────────

def test_prefill_keeps_per_layer_inputs_and_decoding_drops_it():
    language_model = Gemma4ForCausalLM(tiny_gemma_text_config())
    _drop_per_layer_inputs_after_prefill(language_model)
    per_layer_inputs = torch.zeros(1, 3, NUM_LAYERS, PLE_DIM)
    ids = torch.ones(1, 3, dtype=torch.long)

    prefill = language_model.prepare_inputs_for_generation(
        ids, per_layer_inputs=per_layer_inputs, is_first_iteration=True
    )
    decode = language_model.prepare_inputs_for_generation(
        ids, per_layer_inputs=per_layer_inputs, is_first_iteration=False
    )

    assert prefill["per_layer_inputs"] is per_layer_inputs
    assert "per_layer_inputs" not in decode


def test_the_per_layer_lookup_survives_a_lora_wrapper():
    # train.py --train_type lora replaces model.language_model with a PEFT
    # wrapper, which puts two more levels between the VLM and the text model.
    peft = pytest.importorskip("peft")
    model = build_gemma_vlm()
    lora_config = peft.LoraConfig(
        r=4,
        lora_alpha=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model.language_model = peft.get_peft_model(model.language_model, lora_config)
    input_ids, attention_mask, pixel_values, labels = make_batch()
    expected_len = input_ids.shape[1] + model.config.num_image_tokens - 1

    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        labels=labels,
    )

    assert out.logits.shape == (2, expected_len, VOCAB)
    assert any(p.requires_grad for p in model.language_model.parameters())


def test_generate_still_works_through_a_lora_wrapper():
    # The prefill-only handling is installed on the causal LM instance, and the
    # inference entry points wrap that instance with PEFT after build_model
    # returns. If the wrapper hid it, generation would stop after one token.
    peft = pytest.importorskip("peft")
    model = build_gemma_vlm()
    model.language_model = peft.get_peft_model(
        model.language_model,
        peft.LoraConfig(r=4, lora_alpha=8, target_modules=["q_proj", "v_proj"],
                        bias="none", task_type="CAUSAL_LM"),
    )
    input_ids, attention_mask, pixel_values, _ = make_batch()

    generated = model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        pixel_values=pixel_values,
        max_new_tokens=4,
        do_sample=False,
    )

    assert generated.shape == (2, 4)


def test_lora_skips_the_layers_that_share_key_and_value_projections():
    """
    Gemma 4 omits k_proj and v_proj on its KV-sharing layers, and PEFT passes
    over the missing names without a word. train.py's target list therefore
    reaches fewer modules than the layer count suggests, and this pins how many.
    """
    peft = pytest.importorskip("peft")
    shared_layers = 1
    config = tiny_gemma_text_config()
    config.num_kv_shared_layers = shared_layers
    language_model = peft.get_peft_model(
        Gemma4ForCausalLM(config),
        peft.LoraConfig(
            r=4,
            lora_alpha=8,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )

    adapted = {name.rsplit(".lora_A", 1)[0]
               for name, _ in language_model.named_parameters() if ".lora_A." in name}

    always_present = 5 * NUM_LAYERS                                  # q, o, gate, up, down
    key_value = 2 * (NUM_LAYERS - shared_layers)                     # k, v
    assert len(adapted) == always_present + key_value
    assert not any(f"layers.{NUM_LAYERS - 1}.self_attn.k_proj" in name for name in adapted)


def test_resizing_for_the_image_token_keeps_the_gemma_embedding_scale():
    # Gemma multiplies its token embeddings by sqrt(hidden_size). build_model
    # adds <image> and resizes, and a resize that returned a plain nn.Embedding
    # would drop that factor, leaving text embeddings ~sqrt(hidden_size) times
    # smaller than the model expects with nothing raising.
    from transformers.models.gemma4.modeling_gemma4 import Gemma4TextScaledWordEmbedding

    language_model = Gemma4ForCausalLM(tiny_gemma_text_config())
    ids = torch.tensor([[1, 2, 3]])
    before = language_model.model.embed_tokens(ids).clone()

    language_model.resize_token_embeddings(VOCAB + 1)

    embed_tokens = language_model.get_input_embeddings()
    per_layer = language_model.get_per_layer_input_embeddings()
    assert isinstance(embed_tokens, Gemma4TextScaledWordEmbedding)
    assert isinstance(per_layer, Gemma4TextScaledWordEmbedding)
    assert embed_tokens.weight.shape[0] == VOCAB + 1
    assert torch.equal(language_model.model.embed_tokens(ids), before)


def test_the_patched_method_still_reports_that_it_forwards_inputs_embeds():
    # generate() reads this signature to decide whether inputs_embeds may be
    # passed at all, so losing it would break generation outright.
    language_model = Gemma4ForCausalLM(tiny_gemma_text_config())
    _drop_per_layer_inputs_after_prefill(language_model)

    parameters = inspect.signature(language_model.prepare_inputs_for_generation).parameters

    assert "inputs_embeds" in parameters
