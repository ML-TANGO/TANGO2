"""
CT-JEPA v2 Grounding Head (Protocol B)
========================================
Text-conditioned segmentation head for fine-tuning on ReXGroundingCT.

Architecture:
    1. Frozen/fine-tuned encoder produces S3 features (6×8×8)
    2. Text encoder produces global text embedding + token embeddings
    3. FiLM-style text modulation selects WHICH finding to segment
    4. Predictor cross-attention injects learned text-spatial alignment
    5. ConvTranspose3d decoder produces full-resolution binary mask

Fine-tuning recipe:
    Phase 1 (epochs 0-20):  Freeze encoder + predictor, train decoder + FiLM only
    Phase 2 (epochs 20-50): Unfreeze predictor (cross-attention adapts to findings)
    Phase 3 (epochs 50-80): Optionally unfreeze encoder Stage 3
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict, Tuple


class GroundingHead(nn.Module):
    """
    Text-conditioned segmentation head on top of CT-JEPA v2.
    Combines encoder features + predictor cross-attention features → dense mask.
    """

    def __init__(self, ctjepa_model, freeze_encoder: bool = True,
                 freeze_predictor: bool = True,
                 output_size: Tuple[int, int, int] = (192, 256, 256)):
        super().__init__()
        self.output_size = output_size

        # Backbone components (shared weights)
        self.encoder = ctjepa_model.context_encoder
        self.predictor = ctjepa_model.predictor_p3
        self.text_encoder = ctjepa_model.text_encoder

        # Get dims from model
        config = ctjepa_model.config
        self.dim_s3 = config.model.dim_s3
        self.dim_s2 = config.model.dim_s2
        self.dim_s1 = config.model.dim_s1
        self.text_dim = config.text.text_embed_dim
        self.grid_s3 = config.patch.grid_size_s3   # (10, 12, 12)

        # Apply freezing
        if freeze_encoder:
            for p in self.encoder.parameters():
                p.requires_grad = False
        if freeze_predictor:
            for p in self.predictor.parameters():
                p.requires_grad = False
        # Text encoder always frozen
        for p in self.text_encoder.parameters():
            p.requires_grad = False

        # Matryoshka dims from config
        self.matryoshka_pred_dim = config.text.matryoshka_pred_dim

        # ---- Trainable components ----

        # FiLM-style text conditioning: text → spatial modulation
        # Uses matryoshka-truncated global embedding (text_dim → dim_s3)
        self.text_to_spatial = nn.Sequential(
            nn.Linear(self.text_dim, self.dim_s3),
            nn.GELU(),
            nn.Linear(self.dim_s3, self.dim_s3),
        )

        # Feature fusion: encoder S3 + predictor output → combined
        self.feature_fusion = nn.Sequential(
            nn.LayerNorm(self.dim_s3 * 2),
            nn.Linear(self.dim_s3 * 2, self.dim_s3),
            nn.GELU(),
        )

        # Dense decoder: S3 (6,8,8) → full resolution
        D3, H3, W3 = self.grid_s3
        self.seg_decoder = nn.Sequential(
            # (dim_s3, 6, 8, 8) → (256, 12, 16, 16)
            nn.ConvTranspose3d(self.dim_s3, 256, kernel_size=2, stride=2),
            nn.GroupNorm(16, 256),
            nn.GELU(),

            # (256, 12, 16, 16) → (128, 24, 32, 32)
            nn.ConvTranspose3d(256, 128, kernel_size=2, stride=2),
            nn.GroupNorm(8, 128),
            nn.GELU(),

            # (128, 24, 32, 32) → (64, 48, 64, 64)
            nn.ConvTranspose3d(128, 64, kernel_size=2, stride=2),
            nn.GroupNorm(4, 64),
            nn.GELU(),

            # 1x1 conv for logits
            nn.Conv3d(64, 1, kernel_size=1),
        )

    def set_phase(self, phase: int):
        """
        Set training phase for progressive unfreezing.

        Phase 1: Only decoder + FiLM (freeze encoder + predictor)
        Phase 2: Unfreeze predictor
        Phase 3: Unfreeze encoder Stage 3
        """
        if phase >= 2:
            for p in self.predictor.parameters():
                p.requires_grad = True

        if phase >= 3:
            for p in self.encoder.stage3.parameters():
                p.requires_grad = True
            for p in self.encoder.readout.parameters():
                p.requires_grad = True

    def forward(self, volume: torch.Tensor, window_id: torch.Tensor,
                texts: list,
                region_masks_s2: Optional[torch.Tensor] = None,
                ) -> torch.Tensor:
        """
        Forward pass: volume + finding text → segmentation logits.

        Args:
            volume: (B, 1, D, H, W)
            window_id: (B,)
            texts: list of text strings
            region_masks_s2: optional (B, R, N_s2)

        Returns:
            logits: (B, 1, D, H, W) — apply sigmoid for probability
        """
        B = volume.shape[0]
        device = volume.device
        N_s3 = self.grid_s3[0] * self.grid_s3[1] * self.grid_s3[2]

        # 1. Encode volume (full pass, no masking)
        enc_out = self.encoder.forward_full(volume, window_id, region_masks_s2)
        s3_features = enc_out['s3_features']  # (B, N_s3, dim_s3)

        # 2. Encode text (frozen, returns raw_global only)
        text_out = self.text_encoder(texts, target_device=device)
        text_global = text_out['raw_global']  # (B, text_dim=1024)

        # 3. FiLM modulation: text tells model WHICH finding to segment
        text_cond = self.text_to_spatial(text_global)  # (B, dim_s3)
        s3_modulated = s3_features * text_cond.unsqueeze(1).sigmoid()

        # 4. Predictor features with text context token
        cond = self.encoder.window_cond(window_id=window_id)
        all_indices = torch.arange(N_s3, device=device).unsqueeze(0).expand(B, -1)
        visible_mask = torch.ones(B, N_s3, dtype=torch.bool, device=device)

        # Matryoshka truncation for predictor context token
        z_txt_pred = text_global[:, :self.matryoshka_pred_dim]
        text_mask = text_out['has_text']

        pred_features = self.predictor(
            visible_embeddings=s3_features,
            visible_mask=visible_mask,
            masked_indices=all_indices,
            cond=cond,
            z_txt_pred=z_txt_pred,
            text_mask=text_mask,
            region_tokens=enc_out.get('region_tokens'),
        )  # (B, N_s3, dim_s3)

        # 5. Fuse encoder + predictor features
        combined = self.feature_fusion(
            torch.cat([s3_modulated, pred_features], dim=-1)
        )  # (B, N_s3, dim_s3)

        # 6. Reshape to 3D and decode
        D3, H3, W3 = self.grid_s3
        combined_3d = combined.view(B, D3, H3, W3, self.dim_s3).permute(0, 4, 1, 2, 3)

        logits = self.seg_decoder(combined_3d)

        # 7. Upsample to full resolution
        logits = F.interpolate(logits, size=self.output_size,
                               mode='trilinear', align_corners=False)

        return logits


class GroundingLoss(nn.Module):
    """Dice + BCE loss for grounding segmentation."""

    def __init__(self, dice_weight: float = 1.0, bce_weight: float = 1.0):
        super().__init__()
        self.dice_weight = dice_weight
        self.bce_weight = bce_weight

    def dice_loss(self, pred: torch.Tensor, target: torch.Tensor,
                  smooth: float = 1.0) -> torch.Tensor:
        pred_flat = pred.flatten(1)
        target_flat = target.flatten(1)
        intersection = (pred_flat * target_flat).sum(dim=1)
        union = pred_flat.sum(dim=1) + target_flat.sum(dim=1)
        dice = (2.0 * intersection + smooth) / (union + smooth)
        return 1.0 - dice.mean()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            logits: (B, 1, D, H, W)
            targets: (B, D, H, W) binary
        """
        pred_probs = torch.sigmoid(logits.squeeze(1))  # (B, D, H, W)
        targets = targets.float()

        l_dice = self.dice_loss(pred_probs, targets)
        l_bce = F.binary_cross_entropy_with_logits(logits.squeeze(1), targets)

        total = self.dice_weight * l_dice + self.bce_weight * l_bce

        return {
            'total': total,
            'dice_loss': l_dice,
            'bce_loss': l_bce,
        }
