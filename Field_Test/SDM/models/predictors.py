"""
CT-JEPA v2 Predictors
======================
P3: Main query-based predictor at Stage 3 (text token appended to context)
P2: Detail predictor at Stage 2 (sparse)
CrossStagePredictor: Fine->Coarse prediction for cross-scale learning
DecoderHead: Lightweight feature pyramid for segmentation readiness
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple
import math

from .blocks import AdaLNZero, FFN


# ---------------------------------------------------------------------------
# Predictor Block
# ---------------------------------------------------------------------------

class PredictorBlock(nn.Module):
    """Single predictor transformer block.

    Three operations:
    1. Self-attention over queries (AdaLN-Zero conditioned on window_id)
    2. Cross-attention from queries to context (may include appended text token)
    3. FFN with AdaLN-Zero
    """

    def __init__(self, dim: int, num_heads: int, cond_dim: int,
                 mlp_ratio: float = 4.0):
        super().__init__()
        self.adaln_self = AdaLNZero(dim, cond_dim)
        self.self_attn = nn.MultiheadAttention(dim, num_heads, batch_first=True)

        self.norm_cross_q = nn.LayerNorm(dim)
        self.norm_cross_kv = nn.LayerNorm(dim)
        self.cross_attn_ctx = nn.MultiheadAttention(dim, num_heads, batch_first=True)

        self.adaln_ffn = AdaLNZero(dim, cond_dim)
        self.ffn = FFN(dim, mlp_ratio)

    def forward(self, queries: torch.Tensor, context: torch.Tensor,
                cond: torch.Tensor,
                cross_attn_key_padding_mask: Optional[torch.Tensor] = None,
                region_tokens: Optional[torch.Tensor] = None,
                query_padding_mask: Optional[torch.Tensor] = None,
                ) -> torch.Tensor:
        # Self-attention with AdaLN
        q_mod, gate_self = self.adaln_self(queries, cond)
        self_out, _ = self.self_attn(q_mod, q_mod, q_mod,
                                     key_padding_mask=query_padding_mask)
        queries = queries + gate_self * self_out

        # Cross-attention to context (which may include text token at the end)
        q_cross = self.norm_cross_q(queries)
        kv = self.norm_cross_kv(context)
        if region_tokens is not None:
            kv = torch.cat([kv, self.norm_cross_kv(region_tokens)], dim=1)
            # Extend key_padding_mask for region tokens (never masked)
            if cross_attn_key_padding_mask is not None:
                R = region_tokens.shape[1]
                region_pad = torch.zeros(queries.shape[0], R, dtype=torch.bool,
                                         device=queries.device)
                cross_attn_key_padding_mask = torch.cat(
                    [cross_attn_key_padding_mask, region_pad], dim=1)
        cross_out, _ = self.cross_attn_ctx(q_cross, kv, kv,
                                            key_padding_mask=cross_attn_key_padding_mask)
        queries = queries + cross_out

        # FFN with AdaLN
        q_mod2, gate_ffn = self.adaln_ffn(queries, cond)
        queries = queries + gate_ffn * self.ffn(q_mod2)

        return queries


# ---------------------------------------------------------------------------
# Main Predictor P3 (Stage 3)
# ---------------------------------------------------------------------------

class PredictorP3(nn.Module):
    """Main JEPA predictor at Stage 3 with bottleneck and text conditioning.

    Text conditioning is simplified: a single matryoshka-truncated text
    embedding (predictor_dim=256) is appended to the cross-attention context.
    When text is dropped, the text token position is masked out via the
    cross-attention key_padding_mask so it receives zero attention weight.
    """

    def __init__(self, dim: int, predictor_dim: int, depth: int,
                 num_heads: int, cond_dim: int,
                 num_tokens_s3: int = 384,
                 use_text: bool = True):
        super().__init__()
        self.dim = dim
        self.predictor_dim = predictor_dim
        self.use_text = use_text

        self.input_proj = nn.Linear(dim, predictor_dim)
        self.context_proj = nn.Linear(dim, predictor_dim)

        self.mask_pos_embed = nn.Parameter(torch.zeros(1, num_tokens_s3, predictor_dim))
        nn.init.trunc_normal_(self.mask_pos_embed, std=0.02)

        self.cond_proj = nn.Linear(cond_dim, predictor_dim) if cond_dim != predictor_dim else nn.Identity()

        self.blocks = nn.ModuleList([
            PredictorBlock(
                dim=predictor_dim,
                num_heads=num_heads,
                cond_dim=predictor_dim,
            )
            for _ in range(depth)
        ])

        self.output_proj = nn.Sequential(
            nn.LayerNorm(predictor_dim),
            nn.Linear(predictor_dim, dim),
        )

    def forward(self, visible_embeddings: torch.Tensor,
                visible_mask: torch.Tensor,
                masked_indices: torch.Tensor,
                cond: torch.Tensor,
                z_txt_pred: Optional[torch.Tensor] = None,
                text_mask: Optional[torch.Tensor] = None,
                region_tokens: Optional[torch.Tensor] = None,
                valid_mask: Optional[torch.Tensor] = None,
                ) -> torch.Tensor:
        """
        Args:
            visible_embeddings: (B, V, dim) — visible S3 features
            visible_mask: (B, N_s3) bool
            masked_indices: (B, M) long
            cond: (B, cond_dim) — window conditioning
            z_txt_pred: (B, predictor_dim) — matryoshka-truncated text embedding
            text_mask: (B,) bool — True = text available for this sample
            region_tokens: optional (B, R, dim)
            valid_mask: (B, M) bool — valid masked positions
        """
        B, M = masked_indices.shape
        device = visible_embeddings.device

        context = self.context_proj(visible_embeddings)  # (B, V, predictor_dim)

        queries = torch.zeros(B, M, self.predictor_dim, device=device)
        for b in range(B):
            queries[b] = self.mask_pos_embed[0, masked_indices[b]]

        if valid_mask is not None:
            queries = queries * valid_mask.unsqueeze(-1).float()

        cond_p = self.cond_proj(cond)

        if region_tokens is not None:
            region_tokens = self.context_proj(region_tokens)

        # Append text token to context and build key_padding_mask
        cross_attn_key_padding_mask = None
        if self.use_text and z_txt_pred is not None:
            text_token = z_txt_pred.unsqueeze(1)  # (B, 1, predictor_dim)
            context = torch.cat([context, text_token], dim=1)  # (B, V+1, predictor_dim)

            # Build mask: last position (text token) is masked when text unavailable
            ctx_len = context.shape[1]
            cross_attn_key_padding_mask = torch.zeros(B, ctx_len, dtype=torch.bool, device=device)
            if text_mask is not None:
                # Mask the text token position for samples without text
                cross_attn_key_padding_mask[:, -1] = ~text_mask  # True = ignore

        query_padding_mask = ~valid_mask if valid_mask is not None else None

        for blk in self.blocks:
            queries = blk(queries, context, cond_p,
                         cross_attn_key_padding_mask=cross_attn_key_padding_mask,
                         region_tokens=region_tokens,
                         query_padding_mask=query_padding_mask)

        predictions = self.output_proj(queries)
        return predictions


# ---------------------------------------------------------------------------
# Detail Predictor P2 (Stage 2, Sparse)
# ---------------------------------------------------------------------------

class PredictorP2(nn.Module):
    """Detail predictor: coarse-to-fine from S3 predictions to S2 targets."""

    def __init__(self, dim_s3: int, dim_s2: int, num_sampled: int = 512,
                 num_heads: int = 8, depth: int = 2):
        super().__init__()
        self.num_sampled = num_sampled
        self.dim_s2 = dim_s2

        self.upsample = nn.Sequential(
            nn.Linear(dim_s3, dim_s2 * 4),
            nn.GELU(),
            nn.Linear(dim_s2 * 4, dim_s2),
        )

        self.cross_attn = nn.MultiheadAttention(dim_s2, num_heads, batch_first=True)
        self.norm_q = nn.LayerNorm(dim_s2)
        self.norm_kv = nn.LayerNorm(dim_s2)

        self.refine = nn.Sequential(
            nn.LayerNorm(dim_s2),
            nn.Linear(dim_s2, dim_s2 * 2),
            nn.GELU(),
            nn.Linear(dim_s2 * 2, dim_s2),
        )

        self.pos_embed_s2 = nn.Parameter(torch.zeros(1, 3072, dim_s2))
        nn.init.trunc_normal_(self.pos_embed_s2, std=0.02)

    def forward(self, s3_predictions: torch.Tensor,
                s2_visible: torch.Tensor,
                masked_s2_indices: torch.Tensor,
                valid_mask: Optional[torch.Tensor] = None,
                ) -> torch.Tensor:
        B, K = masked_s2_indices.shape

        s3_up = self.upsample(s3_predictions)

        queries = torch.zeros(B, K, self.dim_s2, device=s3_predictions.device)
        for b in range(B):
            queries[b] = self.pos_embed_s2[0, masked_s2_indices[b]]

        # Zero out padded positions so they don't contaminate cross-attention
        if valid_mask is not None:
            queries = queries * valid_mask.unsqueeze(-1).float()

        kv = torch.cat([s3_up, self.norm_kv(s2_visible)], dim=1)
        q = self.norm_q(queries)
        cross_out, _ = self.cross_attn(q, kv, kv)
        queries = queries + cross_out

        predictions = queries + self.refine(queries)
        return predictions


# ---------------------------------------------------------------------------
# Cross-Stage Predictor (Fine -> Coarse)
# ---------------------------------------------------------------------------

class CrossStagePredictor(nn.Module):
    """Predicts S3 semantics from S1 features (pooled to S3 grid)."""

    def __init__(self, dim_s1: int, dim_s3: int, grid_s1: Tuple[int, int, int],
                 grid_s3: Tuple[int, int, int]):
        super().__init__()
        self.pool_kernel = tuple(s1 // s3 for s1, s3 in zip(grid_s1, grid_s3))

        self.predictor = nn.Sequential(
            nn.LayerNorm(dim_s1),
            nn.Linear(dim_s1, dim_s3),
            nn.GELU(),
            nn.Linear(dim_s3, dim_s3),
            nn.LayerNorm(dim_s3),
        )

    def forward(self, s1_features: torch.Tensor,
                grid_size_s1: Tuple[int, int, int]) -> torch.Tensor:
        B, N, D = s1_features.shape
        Ds, Hs, Ws = grid_size_s1

        x = s1_features.view(B, Ds, Hs, Ws, D).permute(0, 4, 1, 2, 3)
        x = F.avg_pool3d(x, kernel_size=self.pool_kernel)
        x = x.flatten(2).transpose(1, 2)

        return self.predictor(x)


# ---------------------------------------------------------------------------
# Lightweight Decoder Head
# ---------------------------------------------------------------------------

class DecoderHead(nn.Module):
    """S3->S2->S1 decoder with skip connections for segmentation readiness."""

    def __init__(self, dim_s1: int, dim_s2: int, dim_s3: int,
                 grid_s1: Tuple[int, int, int],
                 grid_s2: Tuple[int, int, int],
                 grid_s3: Tuple[int, int, int]):
        super().__init__()
        self.grid_s1 = grid_s1
        self.grid_s2 = grid_s2
        self.grid_s3 = grid_s3

        self.up_s3_to_s2 = nn.Sequential(
            nn.Linear(dim_s3, dim_s2 * 4),
            nn.GELU(),
            nn.Linear(dim_s2 * 4, dim_s2),
        )
        self.fuse_s2 = nn.Sequential(
            nn.LayerNorm(dim_s2 * 2),
            nn.Linear(dim_s2 * 2, dim_s2),
            nn.GELU(),
        )

        self.up_s2_to_s1 = nn.Sequential(
            nn.Linear(dim_s2, dim_s1 * 4),
            nn.GELU(),
            nn.Linear(dim_s1 * 4, dim_s1),
        )
        self.fuse_s1 = nn.Sequential(
            nn.LayerNorm(dim_s1 * 2),
            nn.Linear(dim_s1 * 2, dim_s1),
            nn.GELU(),
        )

        self.output_proj = nn.Sequential(
            nn.LayerNorm(dim_s1),
            nn.Linear(dim_s1, dim_s1),
        )

    def _spatial_upsample(self, x: torch.Tensor,
                          from_grid: Tuple[int, int, int],
                          to_grid: Tuple[int, int, int]) -> torch.Tensor:
        B, N, D = x.shape
        Df, Hf, Wf = from_grid
        Dt, Ht, Wt = to_grid
        x = x.view(B, Df, Hf, Wf, D).permute(0, 4, 1, 2, 3)
        x = F.interpolate(x, size=(Dt, Ht, Wt), mode='trilinear', align_corners=False)
        x = x.flatten(2).transpose(1, 2)
        return x

    def forward(self, s3_pred: torch.Tensor,
                s2_features: torch.Tensor,
                s1_features: torch.Tensor) -> torch.Tensor:
        # S3 -> S2
        up_s2 = self.up_s3_to_s2(s3_pred)
        up_s2 = self._spatial_upsample(up_s2, self.grid_s3, self.grid_s2)
        fused_s2 = self.fuse_s2(torch.cat([up_s2, s2_features], dim=-1))

        # S2 -> S1
        up_s1 = self.up_s2_to_s1(fused_s2)
        up_s1 = self._spatial_upsample(up_s1, self.grid_s2, self.grid_s1)
        fused_s1 = self.fuse_s1(torch.cat([up_s1, s1_features], dim=-1))

        return self.output_proj(fused_s1)
