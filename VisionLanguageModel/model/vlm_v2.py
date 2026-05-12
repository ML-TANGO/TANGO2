"""
VisionLanguageModelV2 — Main Model Class

Architecture:
    pixel_values  →  VisionEncoder  →  VisionProjector  ─┐
    input_ids     →  LLM.embed_tokens                    ├→ LLM → logits / loss
                                                          │
    (image features are inserted at <image> token positions)

Supports:
    Vision : CLIP, SigLIP, Video-LanguageBind
    LLM    : Llama 3.1, Qwen3
"""
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .config import VLMConfig, LLM_LLAMA, LLM_QWEN
from .vision_encoder import VisionEncoderWrapper
from .projector import VisionProjector


# ── Output dataclass ─────────────────────────────────────────────────────────

@dataclass
class VLMOutput:
    loss: Optional[torch.Tensor] = None
    logits: Optional[torch.Tensor] = None


# ── Main Model ────────────────────────────────────────────────────────────────

class VisionLanguageModelV2(nn.Module):
    """
    HF-Trainer compatible multimodal model.

    forward() accepts the batch dict directly from DataLoader:
        input_ids, attention_mask, pixel_values, labels (optional)

    Returns a VLMOutput with .loss and .logits.
    """

    def __init__(
        self,
        config: VLMConfig,
        vision_encoder: VisionEncoderWrapper,
        projector: VisionProjector,
        language_model: nn.Module,
    ):
        super().__init__()
        self.config = config
        self.vision_encoder = vision_encoder
        self.projector = projector
        self.language_model = language_model

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_embed_layer(self) -> nn.Embedding:
        """Get the token embedding layer from the underlying LLM.

        Walks .model attributes to handle PEFT wrappers (PeftModel wraps
        LlamaForCausalLM, adding one extra level before embed_tokens).
        """
        lm = self.language_model
        for _ in range(4):
            if hasattr(lm, "embed_tokens"):
                return lm.embed_tokens
            if hasattr(lm, "model"):
                lm = lm.model
            else:
                break
        raise AttributeError("Cannot locate embed_tokens in the language model.")

    def encode_images(self, pixel_values: torch.Tensor) -> torch.Tensor:
        """
        Vision encoder + projector pass.
        Returns: (B, num_image_tokens, llm_hidden_size)
        """
        # Cast to vision encoder dtype to avoid precision mismatch
        pixel_values = pixel_values.to(dtype=self.vision_encoder.dtype)
        features = self.vision_encoder(pixel_values)   # (B, N, vision_D)
        features = features.to(dtype=self.projector.proj[0].weight.dtype
                               if hasattr(self.projector.proj, '__getitem__')
                               else self.projector.proj.weight.dtype)
        return self.projector(features)                # (B, N, llm_D)

    # ── Multimodal fusion ────────────────────────────────────────────────────

    def prepare_inputs_labels_for_multimodal(
        self,
        input_ids: torch.Tensor,          # (B, L)
        attention_mask: torch.Tensor,     # (B, L)
        pixel_values: Optional[torch.Tensor],  # (B, C, H, W)
        labels: Optional[torch.Tensor],   # (B, L)
    ):
        """
        Replace each <image> token in input_ids with N image feature vectors.

        Assumes exactly one <image> token per sample.
        After replacement, every sample in the batch has length L + N - 1,
        so no re-padding is needed (all samples share the same pre-padded L).

        Returns:
            inputs_embeds : (B, L+N-1, D)
            attention_mask: (B, L+N-1)
            labels        : (B, L+N-1) or None
        """
        B, L = input_ids.shape
        embed_layer = self._get_embed_layer()
        image_token_id = self.config.image_token_id

        # ── No image in batch ──────────────────────────────────────────────
        if pixel_values is None:
            inputs_embeds = embed_layer(input_ids)   # (B, L, D)
            return inputs_embeds, attention_mask, labels

        # ── Encode all images ──────────────────────────────────────────────
        image_features = self.encode_images(pixel_values)  # (B, N, D)
        N = image_features.shape[1]
        new_L = L + N - 1  # sequence length after expanding one <image> → N tokens

        embed_dtype = embed_layer.weight.dtype
        embed_device = embed_layer.weight.device

        new_embeds_list = []
        new_attn_list = []
        new_labels_list = []

        for i in range(B):
            ids_i   = input_ids[i]      # (L,)
            attn_i  = attention_mask[i] # (L,)
            img_i   = image_features[i] # (N, D)
            lbl_i   = labels[i] if labels is not None else None

            # Find <image> position
            img_positions = (ids_i == image_token_id).nonzero(as_tuple=True)[0]

            if len(img_positions) == 0:
                # No image token — embed and pad out to new_L
                embeds = embed_layer(ids_i).to(dtype=embed_dtype)  # (L, D)
                pad_e = torch.zeros(N - 1, embeds.shape[-1], dtype=embed_dtype, device=embed_device)
                embeds = torch.cat([embeds, pad_e], dim=0)          # (new_L, D)

                attn = torch.cat([attn_i,
                                  torch.zeros(N - 1, dtype=attn_i.dtype, device=attn_i.device)], dim=0)

                if lbl_i is not None:
                    lbl = torch.cat([lbl_i,
                                     torch.full((N - 1,), -100, dtype=lbl_i.dtype, device=lbl_i.device)], dim=0)
            else:
                p = img_positions[0].item()  # position of <image> token

                # Left segment: tokens before <image>
                if p > 0:
                    left_e = embed_layer(ids_i[:p]).to(dtype=embed_dtype)  # (p, D)
                    left_a = attn_i[:p]
                    left_l = lbl_i[:p] if lbl_i is not None else None
                else:
                    D = embed_layer.weight.shape[1]
                    left_e = torch.zeros(0, D, dtype=embed_dtype, device=embed_device)
                    left_a = torch.zeros(0, dtype=attn_i.dtype, device=attn_i.device)
                    left_l = torch.zeros(0, dtype=lbl_i.dtype, device=lbl_i.device) if lbl_i is not None else None

                # Image segment
                img_a = torch.ones(N, dtype=attn_i.dtype, device=attn_i.device)
                img_l = torch.full((N,), -100, dtype=lbl_i.dtype, device=lbl_i.device) if lbl_i is not None else None

                # Right segment: tokens after <image>
                if p + 1 < L:
                    right_e = embed_layer(ids_i[p + 1:]).to(dtype=embed_dtype)  # (L-p-1, D)
                    right_a = attn_i[p + 1:]
                    right_l = lbl_i[p + 1:] if lbl_i is not None else None
                else:
                    D = embed_layer.weight.shape[1]
                    right_e = torch.zeros(0, D, dtype=embed_dtype, device=embed_device)
                    right_a = torch.zeros(0, dtype=attn_i.dtype, device=attn_i.device)
                    right_l = torch.zeros(0, dtype=lbl_i.dtype, device=lbl_i.device) if lbl_i is not None else None

                embeds = torch.cat([left_e, img_i.to(dtype=embed_dtype), right_e], dim=0)  # (new_L, D)
                attn   = torch.cat([left_a, img_a, right_a], dim=0)                        # (new_L,)

                if lbl_i is not None:
                    lbl = torch.cat([left_l, img_l, right_l], dim=0)   # (new_L,)
                else:
                    lbl = None

            assert embeds.shape[0] == new_L, (
                f"[VLM] Sample {i}: expected length {new_L}, got {embeds.shape[0]}. "
                f"input_ids.shape={input_ids.shape}, N={N}"
            )

            new_embeds_list.append(embeds)
            new_attn_list.append(attn)
            if lbl is not None:
                new_labels_list.append(lbl)

        inputs_embeds  = torch.stack(new_embeds_list, dim=0)   # (B, new_L, D)
        attention_mask = torch.stack(new_attn_list,   dim=0)   # (B, new_L)
        labels_out = torch.stack(new_labels_list, dim=0) if new_labels_list else None

        return inputs_embeds, attention_mask, labels_out

    # ── Forward ──────────────────────────────────────────────────────────────

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        pixel_values: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        **kwargs,
    ) -> VLMOutput:

        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids)

        inputs_embeds, attention_mask, labels = self.prepare_inputs_labels_for_multimodal(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            labels=labels,
        )

        out = self.language_model(
            inputs_embeds=inputs_embeds,
            attention_mask=attention_mask,
            labels=labels,
            return_dict=True,
        )

        return VLMOutput(loss=out.loss, logits=out.logits)

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        pixel_values: Optional[torch.Tensor] = None,
        **generate_kwargs,
    ) -> torch.Tensor:

        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids)

        inputs_embeds, attention_mask, _ = self.prepare_inputs_labels_for_multimodal(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            labels=None,
        )

        return self.language_model.generate(
            inputs_embeds=inputs_embeds,
            attention_mask=attention_mask,
            **generate_kwargs,
        )

    # ── HF Trainer compatibility ──────────────────────────────────────────────

    def gradient_checkpointing_enable(self, gradient_checkpointing_kwargs=None):
        """Delegate to LLM — required by HF Trainer."""
        if hasattr(self.language_model, "enable_input_require_grads"):
            self.language_model.enable_input_require_grads()
        if hasattr(self.language_model, "gradient_checkpointing_enable"):
            kwargs = gradient_checkpointing_kwargs or {}
            self.language_model.gradient_checkpointing_enable(**kwargs)

    def gradient_checkpointing_disable(self):
        """Delegate to LLM — required by HF Trainer."""
        if hasattr(self.language_model, "gradient_checkpointing_disable"):
            self.language_model.gradient_checkpointing_disable()

    # ── Parameter helpers ─────────────────────────────────────────────────────

    def trainable_parameters(self):
        """Iterate over parameters that require gradients."""
        return (p for p in self.parameters() if p.requires_grad)

    def print_trainable_parameters(self):
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"Trainable parameters: {trainable:,} / {total:,} "
              f"({100 * trainable / total:.2f}%)")


# ── Builder ───────────────────────────────────────────────────────────────────

def build_model(
    config: VLMConfig,
    torch_dtype: torch.dtype = torch.bfloat16,
) -> VisionLanguageModelV2:
    """
    Build VisionLanguageModelV2 from config.
    Loads pretrained vision encoder and LLM; initializes projector randomly.
    """
    import os
    from transformers import AutoTokenizer

    print(f"[Builder] Vision encoder : {config.vision_model_name}")
    print(f"[Builder] LLM            : {config.llm_model_name}")
    print(f"[Builder] Projector      : {config.projector_type}")
    print(f"[Builder] dtype          : {torch_dtype}")

    # ── Vision encoder ────────────────────────────────────────────────────────
    vision_encoder = VisionEncoderWrapper(
        model_name=config.vision_model_name,
        feature_layer=config.vision_feature_layer,
        feature_select_strategy=config.vision_feature_select_strategy,
        torch_dtype=torch_dtype,
    )
    config.vision_hidden_size = vision_encoder.hidden_size
    config.num_image_tokens    = vision_encoder.num_image_tokens
    print(f"[Builder] Vision hidden_size   : {config.vision_hidden_size}")
    print(f"[Builder] Num image tokens     : {config.num_image_tokens}")

    # ── LLM ───────────────────────────────────────────────────────────────────
    if config.llm_model_type == LLM_LLAMA:
        from transformers import LlamaForCausalLM
        language_model = LlamaForCausalLM.from_pretrained(
            config.llm_model_name,
            torch_dtype=torch_dtype,
            attn_implementation="flash_attention_2",
        )
    elif config.llm_model_type == LLM_QWEN:
        from transformers import AutoModelForCausalLM
        language_model = AutoModelForCausalLM.from_pretrained(
            config.llm_model_name,
            torch_dtype=torch_dtype,
            attn_implementation="flash_attention_2",
        )
    else:
        raise ValueError(f"Unknown LLM type: {config.llm_model_type}")

    config.llm_hidden_size = language_model.config.hidden_size
    print(f"[Builder] LLM hidden_size      : {config.llm_hidden_size}")

    # ── Tokenizer + special tokens ────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(config.llm_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Add <image> as a special token if not already present
    if config.image_token not in tokenizer.get_vocab():
        tokenizer.add_special_tokens({"additional_special_tokens": [config.image_token]})
        language_model.resize_token_embeddings(len(tokenizer))
        print(f"[Builder] Added '{config.image_token}' token → id {len(tokenizer) - 1}")

    config.image_token_id = tokenizer.convert_tokens_to_ids(config.image_token)
    print(f"[Builder] image_token_id       : {config.image_token_id}")

    # ── Projector (randomly initialized) ─────────────────────────────────────
    projector = VisionProjector(
        vision_hidden_size=config.vision_hidden_size,
        llm_hidden_size=config.llm_hidden_size,
        projector_type=config.projector_type,
    ).to(dtype=torch_dtype)

    # ── Freeze ────────────────────────────────────────────────────────────────
    if config.freeze_vision:
        for p in vision_encoder.parameters():
            p.requires_grad = False
        print("[Builder] Vision encoder frozen.")

    if config.freeze_llm:
        for p in language_model.parameters():
            p.requires_grad = False
        print("[Builder] LLM frozen.")

    # ── Assemble ──────────────────────────────────────────────────────────────
    model = VisionLanguageModelV2(
        config=config,
        vision_encoder=vision_encoder,
        projector=projector,
        language_model=language_model,
    )

    # Attach tokenizer for convenience
    model.tokenizer = tokenizer

    print("\n[Builder] Parameter summary:")
    _print_param_count("  Vision encoder", vision_encoder)
    _print_param_count("  Projector     ", projector)
    _print_param_count("  LLM           ", language_model)
    model.print_trainable_parameters()

    return model


def _print_param_count(name: str, module: nn.Module):
    total = sum(p.numel() for p in module.parameters())
    trainable = sum(p.numel() for p in module.parameters() if p.requires_grad)
    print(f"{name} : {total:>12,} total, {trainable:>12,} trainable")
