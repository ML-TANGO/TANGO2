"""
VisionLanguageModelV2 Configuration
Supports: CLIP, SigLIP, Video-LanguageBind (vision) + Llama 3.1, Qwen3 (LLM)
"""
from dataclasses import dataclass, field
from typing import Optional


# Supported vision encoders
VISION_CLIP = "clip"
VISION_SIGLIP = "siglip"
VISION_LANGUAGEBIND = "languagebind"

# Supported LLMs
LLM_LLAMA = "llama"
LLM_QWEN = "qwen"

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
    # "linear" | "mlp2x_gelu" | "mlp3x_gelu"
    projector_type: str = "mlp2x_gelu"

    # ── Special tokens ────────────────────────────────────────────────────────
    image_token: str = "<image>"

    # ── Freeze flags (for staged training) ───────────────────────────────────
    freeze_vision: bool = True
    freeze_llm: bool = True     # False for full fine-tuning; use LoRA for fine-tuning

    # ── Computed at build time (do not set manually) ─────────────────────────
    vision_hidden_size: Optional[int] = None
    llm_hidden_size: Optional[int] = None
    num_image_tokens: Optional[int] = None
    image_token_id: Optional[int] = None

    # ── Training ──────────────────────────────────────────────────────────────
    max_seq_len: int = 2048

    def to_dict(self) -> dict:
        """HF Trainer / wandb integration calls model.config.to_dict()."""
        import dataclasses
        return dataclasses.asdict(self)

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
