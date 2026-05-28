"""
Unified Vision Encoder Wrapper
Supports: CLIP, SigLIP, Video-LanguageBind
All encoders expose a common interface: forward(pixel_values) -> (B, N, D)
"""
import torch
import torch.nn as nn
from typing import Optional

from .config import VISION_CLIP, VISION_SIGLIP, VISION_LANGUAGEBIND


class VisionEncoderWrapper(nn.Module):
    """
    Wraps different vision encoders behind a unified interface.

    Output of forward():
        (B, num_image_tokens, hidden_size)

    For CLIP:   (B, 576, 1024)  - 336px / patch14, drops CLS
    For SigLIP: (B, 729, 1152)  - 384px / patch14, no CLS
    For Video-LanguageBind: (B, T*N, D) where T=frames
    """

    def __init__(
        self,
        model_name: str,
        feature_layer: int = -2,
        feature_select_strategy: str = "patch",
        torch_dtype: torch.dtype = torch.bfloat16,
    ):
        super().__init__()
        self.model_name = model_name
        self.feature_layer = feature_layer
        self.feature_select_strategy = feature_select_strategy
        self.encoder_type = self._detect_type(model_name)

        if self.encoder_type == VISION_CLIP:
            self._init_clip(model_name, torch_dtype)
        elif self.encoder_type == VISION_SIGLIP:
            self._init_siglip(model_name, torch_dtype)
        elif self.encoder_type == VISION_LANGUAGEBIND:
            self._init_languagebind(model_name, torch_dtype)

    # ── Init helpers ─────────────────────────────────────────────────────────

    def _init_clip(self, model_name: str, torch_dtype: torch.dtype):
        import logging
        # Suppress the CLIP text-encoder "UNEXPECTED keys" load report
        # (expected: CLIPVisionModel doesn't load text_model.* weights)
        logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
        from transformers import CLIPVisionModel, CLIPImageProcessor
        self.model = CLIPVisionModel.from_pretrained(model_name, torch_dtype=torch_dtype)
        logging.getLogger("transformers.modeling_utils").setLevel(logging.WARNING)
        self.image_processor = CLIPImageProcessor.from_pretrained(model_name)
        cfg = self.model.config
        self._hidden_size = cfg.hidden_size          # 1024
        patches_per_side = cfg.image_size // cfg.patch_size  # 336 // 14 = 24
        self._num_image_tokens = patches_per_side ** 2        # 576

    def _init_siglip(self, model_name: str, torch_dtype: torch.dtype):
        from transformers import SiglipVisionModel, SiglipImageProcessor
        self.model = SiglipVisionModel.from_pretrained(model_name, torch_dtype=torch_dtype)
        self.image_processor = SiglipImageProcessor.from_pretrained(model_name)
        cfg = self.model.config
        self._hidden_size = cfg.hidden_size           # 1152
        patches_per_side = cfg.image_size // cfg.patch_size  # 384 // 14 = 27
        self._num_image_tokens = patches_per_side ** 2        # 729

    def _init_languagebind(self, model_name: str, torch_dtype: torch.dtype):
        from transformers import AutoModel, AutoProcessor
        self.model = AutoModel.from_pretrained(model_name, torch_dtype=torch_dtype, trust_remote_code=True)
        self.image_processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        # LanguageBind: use vision component
        vision_cfg = self.model.config.vision_config
        self._hidden_size = vision_cfg.hidden_size
        patches_per_side = vision_cfg.image_size // vision_cfg.patch_size
        self._num_image_tokens = patches_per_side ** 2

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def hidden_size(self) -> int:
        return self._hidden_size

    @property
    def num_image_tokens(self) -> int:
        return self._num_image_tokens

    @property
    def dtype(self) -> torch.dtype:
        return next(self.model.parameters()).dtype

    @property
    def device(self) -> torch.device:
        return next(self.model.parameters()).device

    # ── Forward ──────────────────────────────────────────────────────────────

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        """
        Args:
            pixel_values: (B, C, H, W)  [or (B, T, C, H, W) for video]
        Returns:
            features: (B, num_image_tokens, hidden_size)
        """
        if self.encoder_type == VISION_CLIP:
            return self._forward_clip(pixel_values)
        elif self.encoder_type == VISION_SIGLIP:
            return self._forward_siglip(pixel_values)
        elif self.encoder_type == VISION_LANGUAGEBIND:
            return self._forward_languagebind(pixel_values)
        else:
            raise ValueError(f"Unknown encoder type: {self.encoder_type}")

    def _forward_clip(self, pixel_values: torch.Tensor) -> torch.Tensor:
        outputs = self.model(
            pixel_values=pixel_values,
            output_hidden_states=True,
        )
        # Select the specified layer
        if self.feature_layer == -1:
            features = outputs.last_hidden_state
        else:
            features = outputs.hidden_states[self.feature_layer]

        # Drop CLS token (position 0) for "patch" strategy
        if self.feature_select_strategy == "patch":
            features = features[:, 1:]   # (B, 576, 1024)

        return features

    def _forward_siglip(self, pixel_values: torch.Tensor) -> torch.Tensor:
        outputs = self.model(
            pixel_values=pixel_values,
            output_hidden_states=True,
        )
        # SigLIP has no CLS token
        if self.feature_layer == -1:
            features = outputs.last_hidden_state
        else:
            features = outputs.hidden_states[self.feature_layer]

        return features  # (B, 729, 1152)

    def _forward_languagebind(self, pixel_values: torch.Tensor) -> torch.Tensor:
        # pixel_values: (B, T, C, H, W) - T frames
        B, T, C, H, W = pixel_values.shape
        # Reshape to (B*T, C, H, W) for batch processing
        flat = pixel_values.view(B * T, C, H, W)
        outputs = self.model.vision_model(
            pixel_values=flat,
            output_hidden_states=True,
        )
        features = outputs.last_hidden_state  # (B*T, N, D)
        # Drop CLS if present
        if self.feature_select_strategy == "patch":
            features = features[:, 1:]
        # Reshape back to (B, T*N, D)
        N = features.shape[1]
        features = features.view(B, T * N, self._hidden_size)
        return features

    # ── Utility ──────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_type(model_name: str) -> str:
        name = model_name.lower()
        if "siglip" in name:
            return VISION_SIGLIP
        elif "languagebind" in name:
            return VISION_LANGUAGEBIND
        else:
            return VISION_CLIP
