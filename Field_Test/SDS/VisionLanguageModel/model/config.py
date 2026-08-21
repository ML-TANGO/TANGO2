"""
VisionLanguageModelV2 Configuration
Supports: CLIP, SigLIP, Video-LanguageBind (vision) + Llama 3.1, Qwen3 (LLM)
"""
from dataclasses import dataclass
from typing import Optional


# Supported vision encoders
VISION_CLIP = "clip"
VISION_SIGLIP = "siglip"
VISION_LANGUAGEBIND = "languagebind"

# Supported LLMs
LLM_LLAMA = "llama"
LLM_QWEN = "qwen"

# Supported vision projectors
PROJECTOR_LINEAR = "linear"
PROJECTOR_MLP2 = "mlp2x_gelu"
PROJECTOR_MLP3 = "mlp3x_gelu"
PROJECTOR_CROSS_ATTN = "cross_attn"
PROJECTOR_QFORMER = "qformer"

PROJECTOR_TYPES = (
    PROJECTOR_LINEAR,
    PROJECTOR_MLP2,
    PROJECTOR_MLP3,
    PROJECTOR_CROSS_ATTN,
    PROJECTOR_QFORMER,
)

# Projectors that compress the patch sequence into a fixed number of learned
# query tokens instead of projecting each patch independently.
RESAMPLER_PROJECTOR_TYPES = (PROJECTOR_CROSS_ATTN, PROJECTOR_QFORMER)

# Vision model → expected output dimensions
VISION_MODEL_SPECS = {
    # model_name_pattern: (hidden_size, image_size, patch_size)
    "clip-vit-large-patch14-336": (1024, 336, 14),   # 576 patches
    "siglip-so400m-patch14-384": (1152, 384, 14),     # 729 patches
    "video-languagebind": (1024, 224, 14),             # 256 patches per frame
}


@dataclass
class VLMConfig:
    # ── Vision encoder ────────────────────────────────────────────────────────
    vision_model_name: str = "openai/clip-vit-large-patch14-336"
    # Which hidden layer to extract features from (-1 = last, -2 = second-to-last)
    vision_feature_layer: int = -2
    # "patch": drop CLS token  |  "full": keep CLS token
    vision_feature_select_strategy: str = "patch"

    # ── Language model ────────────────────────────────────────────────────────
    llm_model_name: str = "/home/ywlee/Llama-3.1-8B-Instruct"

    # ── Projector ─────────────────────────────────────────────────────────────
    # "linear" | "mlp2x_gelu" | "mlp3x_gelu" | "cross_attn" | "qformer"
    projector_type: str = PROJECTOR_MLP2

    # Resampler hyperparameters. Used only by "cross_attn" and "qformer";
    # ignored by the linear and MLP projectors.
    # Number of image tokens the resampler emits, independent of patch count.
    projector_num_query_tokens: int = 32
    # Attention heads per resampler block.
    projector_num_heads: int = 8
    # Number of stacked resampler blocks.
    projector_num_layers: int = 2
    # Feed-forward width as a multiple of the resampler hidden size.
    projector_ffn_ratio: float = 4.0
    # Dropout inside the resampler blocks.
    projector_dropout: float = 0.0
    # Resampler working width. None falls back to vision_hidden_size, which
    # keeps the resampler far cheaper than running it at the LLM width.
    projector_hidden_size: Optional[int] = None

    # ── Special tokens ────────────────────────────────────────────────────────
    image_token: str = "<image>"

    # ── Freeze flags (for staged training) ───────────────────────────────────
    freeze_vision: bool = True
    freeze_llm: bool = True     # False for full fine-tuning; use LoRA for fine-tuning

    # ── Computed at build time (do not set manually) ─────────────────────────
    vision_hidden_size: Optional[int] = None
    llm_hidden_size: Optional[int] = None
    # Patch tokens produced by the vision encoder.
    vision_num_patches: Optional[int] = None
    # Image tokens the projector emits, i.e. how many positions are spliced
    # into the LLM sequence at the <image> token.
    num_image_tokens: Optional[int] = None
    image_token_id: Optional[int] = None

    # ── Training ──────────────────────────────────────────────────────────────
    max_seq_len: int = 2048

    def to_dict(self) -> dict:
        """HF Trainer / wandb integration calls model.config.to_dict()."""
        import dataclasses
        return dataclasses.asdict(self)

    def to_json_string(self) -> str:
        """
        HF Trainer's TensorBoardCallback.on_train_begin calls
        model.config.to_json_string() (transformers
        integrations/integration_utils.py). train.py always adds "tensorboard"
        to report_to, so without this every training run aborts on the callback
        before the first step. default=str keeps a value that is not JSON
        serializable from taking a training run down with it.
        """
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str)

    @property
    def vision_model_type(self) -> str:
        name = self.vision_model_name.lower()
        if "siglip" in name:
            return VISION_SIGLIP
        elif "languagebind" in name:
            return VISION_LANGUAGEBIND
        else:
            return VISION_CLIP

    @property
    def llm_model_type(self) -> str:
        name = self.llm_model_name.lower()
        if "qwen" in name:
            return LLM_QWEN
        else:
            return LLM_LLAMA

    @property
    def is_resampler_projector(self) -> bool:
        """True when the projector emits a fixed token count instead of one per patch."""
        return self.projector_type in RESAMPLER_PROJECTOR_TYPES

    @property
    def projector_output_tokens(self) -> Optional[int]:
        """
        Image tokens the configured projector emits. Returns None before
        build time for the per-patch projectors, since the patch count is only
        known once the vision encoder is loaded.
        """
        if self.is_resampler_projector:
            return self.projector_num_query_tokens
        return self.vision_num_patches

    def projector_kwargs(self) -> dict:
        """Resampler hyperparameters, in the argument names VisionProjector expects."""
        return {
            "hidden_size": self.projector_hidden_size,
            "num_query_tokens": self.projector_num_query_tokens,
            "num_heads": self.projector_num_heads,
            "num_layers": self.projector_num_layers,
            "ffn_ratio": self.projector_ffn_ratio,
            "dropout": self.projector_dropout,
        }
