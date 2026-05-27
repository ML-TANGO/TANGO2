"""
CT-JEPA v2 Hierarchical Encoder
=================================
Stage 1 (24x32x32): Configurable local blocks (transformer/swin/convnext)
Stage 2 (12x16x16): Configurable local blocks + region tokens
Stage 3 (6x8x8): Global self-attention with AdaLN-Zero (always)
Global Readout: Attentional pooling -> g_img
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional, Dict

from .blocks import (
    PatchEmbed3D, PatchMerge3D,
    AdaLNTransformerBlock, WindowConditioner,
    FactorizedPosEmbed3D, FullPosEmbed3D,
    RegionTokens,
    ConvNeXtStage3D, SwinStageAdapter,
)


class Stage(nn.Module):
    """A single encoder stage with N AdaLN transformer blocks."""

    def __init__(self, dim: int, num_blocks: int, num_heads: int,
                 cond_dim: int, grid_size: Tuple[int, int, int],
                 mlp_ratio: float = 4.0,
                 use_window: bool = True,
                 window_size: Optional[Tuple[int, int, int]] = None,
                 use_conv_bridge: bool = True,
                 drop_path_rates: list = None):
        super().__init__()
        self.grid_size = grid_size
        self.use_window = use_window

        if drop_path_rates is None:
            drop_path_rates = [0.0] * num_blocks

        self.blocks = nn.ModuleList([
            AdaLNTransformerBlock(
                dim=dim,
                num_heads=num_heads,
                cond_dim=cond_dim,
                mlp_ratio=mlp_ratio,
                drop_path=drop_path_rates[i],
                use_window=use_window,
                window_size=window_size,
                use_conv_bridge=use_conv_bridge,
                use_rel_pos_bias=use_window,
            )
            for i in range(num_blocks)
        ])

    def forward(self, x: torch.Tensor, cond: torch.Tensor,
                extra_kv: Optional[torch.Tensor] = None,
                key_padding_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        for blk in self.blocks:
            x = blk(x, cond, self.grid_size, extra_kv=extra_kv,
                     key_padding_mask=key_padding_mask)
        return x


class AttentionalReadout(nn.Module):
    """Global readout via learnable CLS queries + cross-attention. Replaces Stage 4."""

    def __init__(self, dim: int, num_queries: int = 4, num_heads: int = 8):
        super().__init__()
        self.queries = nn.Parameter(torch.zeros(1, num_queries, dim))
        nn.init.trunc_normal_(self.queries, std=0.02)
        self.cross_attn = nn.MultiheadAttention(dim, num_heads, batch_first=True)
        self.norm_q = nn.LayerNorm(dim)
        self.norm_kv = nn.LayerNorm(dim)
        self.ffn = nn.Sequential(
            nn.Linear(dim, dim * 4),
            nn.GELU(),
            nn.Linear(dim * 4, dim),
        )
        self.norm_ffn = nn.LayerNorm(dim)
        self.pool_proj = nn.Linear(dim, dim) if num_queries > 1 else nn.Identity()

    def forward(self, tokens: torch.Tensor,
                key_padding_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """(B, N, D) -> (B, D) global embedding.

        Args:
            tokens: (B, N, D) input tokens
            key_padding_mask: (B, N) bool, True = padded (ignored in attention)
        """
        B = tokens.shape[0]
        q = self.queries.expand(B, -1, -1)
        q = self.norm_q(q)
        kv = self.norm_kv(tokens)
        attn_out, _ = self.cross_attn(q, kv, kv, key_padding_mask=key_padding_mask)
        q = q + attn_out
        q = q + self.ffn(self.norm_ffn(q))
        g_img = q.mean(dim=1)
        g_img = self.pool_proj(g_img)
        return g_img


class WindowProjectionHead(nn.Module):
    """Per-window projection head for text alignment."""

    def __init__(self, in_dim: int, proj_dim: int, num_windows: int = 3):
        super().__init__()
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.LayerNorm(in_dim),
                nn.Linear(in_dim, proj_dim),
                nn.GELU(),
                nn.Linear(proj_dim, proj_dim),
            )
            for _ in range(num_windows)
        ])

    def forward(self, g_img: torch.Tensor, window_id: torch.Tensor) -> torch.Tensor:
        """(B, D) + (B,) -> (B, proj_dim)"""
        B = g_img.shape[0]
        outputs = torch.stack([head(g_img) for head in self.heads], dim=1)
        idx = window_id.unsqueeze(1).unsqueeze(2).expand(-1, 1, outputs.shape[-1])
        z_img = outputs.gather(1, idx).squeeze(1)
        return z_img


def _build_local_stage(local_block_type: str, dim: int, num_blocks: int,
                       num_heads: int, cond_dim: int,
                       grid_size: Tuple[int, int, int],
                       mlp_ratio: float,
                       window_size_transformer: Tuple[int, int, int],
                       swin_window_size: Tuple[int, int, int],
                       drop_path_rates: list) -> nn.Module:
    """Build a local stage (S1 or S2) based on block type."""
    if local_block_type == "transformer":
        return Stage(
            dim=dim, num_blocks=num_blocks,
            num_heads=num_heads, cond_dim=cond_dim,
            grid_size=grid_size,
            mlp_ratio=mlp_ratio,
            use_window=True, window_size=window_size_transformer,
            drop_path_rates=drop_path_rates,
        )
    elif local_block_type == "swin":
        return SwinStageAdapter(
            dim=dim, depth=num_blocks, num_heads=num_heads,
            grid_size=grid_size,
            window_size=swin_window_size,
            mlp_ratio=mlp_ratio,
            drop_path_rates=drop_path_rates,
        )
    elif local_block_type == "convnext":
        return ConvNeXtStage3D(
            dim=dim, depth=num_blocks,
            grid_size=grid_size,
            drop_path_rates=drop_path_rates,
        )
    else:
        raise ValueError(f"Unknown local_block_type: {local_block_type}")


class HierarchicalEncoder(nn.Module):
    """
    Full CT-JEPA encoder: Patch Embed -> Stage 1 -> Merge -> Stage 2 -> Merge -> Stage 3 -> Readout.

    Supports two modes:
      - Full pass (target encoder): processes all tokens through all stages
      - Masked pass (context encoder): all tokens at S1-S2, only visible tokens at S3
    """

    def __init__(self, config):
        super().__init__()
        self.config = config
        mc = config.model
        pc = config.patch

        cond_dim = mc.dim_s3
        local_block_type = mc.local_block_type

        # Window conditioner
        self.window_cond = WindowConditioner(cond_dim, config.window.num_windows)

        # Patch embedding
        self.patch_embed = PatchEmbed3D(
            in_channels=config.volume.channels,
            embed_dim=mc.dim_s1,
            patch_size=pc.patch_size,
        )

        # Positional embeddings
        self.pos_embed_s1 = FactorizedPosEmbed3D(pc.grid_size_s1, mc.dim_s1)
        self.pos_embed_s2 = FactorizedPosEmbed3D(pc.grid_size_s2, mc.dim_s2)
        self.pos_embed_s3 = FullPosEmbed3D(pc.grid_size_s3, mc.dim_s3)

        # Drop path rates (linearly increasing across all stages)
        total_blocks = mc.num_blocks_s1 + mc.num_blocks_s2 + mc.num_blocks_s3
        dpr = [x.item() for x in torch.linspace(0, mc.drop_path_rate, total_blocks)]
        dpr_s1 = dpr[:mc.num_blocks_s1]
        dpr_s2 = dpr[mc.num_blocks_s1:mc.num_blocks_s1 + mc.num_blocks_s2]
        dpr_s3 = dpr[mc.num_blocks_s1 + mc.num_blocks_s2:]

        # Stage 1: configurable local blocks
        self.stage1 = _build_local_stage(
            local_block_type=local_block_type,
            dim=mc.dim_s1, num_blocks=mc.num_blocks_s1,
            num_heads=mc.num_heads_s1, cond_dim=cond_dim,
            grid_size=pc.grid_size_s1,
            mlp_ratio=mc.mlp_ratio,
            window_size_transformer=mc.window_size_s1,
            swin_window_size=mc.swin_window_size,
            drop_path_rates=dpr_s1,
        )

        # Patch merge 1->2
        self.merge_1to2 = PatchMerge3D(mc.dim_s1, mc.dim_s2)

        # Region tokens (introduced at Stage 2)
        self.use_region_tokens = mc.use_region_tokens
        if self.use_region_tokens:
            self.region_tokens = RegionTokens(mc.num_region_tokens, mc.dim_s2)

        # Stage 2: configurable local blocks
        self.stage2 = _build_local_stage(
            local_block_type=local_block_type,
            dim=mc.dim_s2, num_blocks=mc.num_blocks_s2,
            num_heads=mc.num_heads_s2, cond_dim=cond_dim,
            grid_size=pc.grid_size_s2,
            mlp_ratio=mc.mlp_ratio,
            window_size_transformer=mc.window_size_s2,
            swin_window_size=mc.swin_window_size,
            drop_path_rates=dpr_s2,
        )

        # Patch merge 2->3
        self.merge_2to3 = PatchMerge3D(mc.dim_s2, mc.dim_s3)

        # Project region tokens from S2 dim to S3 dim
        if self.use_region_tokens:
            self.region_proj_s2to3 = nn.Linear(mc.dim_s2, mc.dim_s3)

        # Stage 3: ALWAYS global self-attention with AdaLN
        self.stage3 = Stage(
            dim=mc.dim_s3, num_blocks=mc.num_blocks_s3,
            num_heads=mc.num_heads_s3, cond_dim=cond_dim,
            grid_size=pc.grid_size_s3,
            mlp_ratio=mc.mlp_ratio,
            use_window=False,
            window_size=None,
            use_conv_bridge=False,
            drop_path_rates=dpr_s3,
        )

        # Global readout (replaces Stage 4)
        self.readout = AttentionalReadout(
            dim=mc.dim_s3,
            num_queries=mc.num_readout_queries,
            num_heads=mc.num_heads_s3,
        )

        # Window-specific projection heads for text alignment
        self.window_proj = WindowProjectionHead(
            in_dim=mc.dim_s3, proj_dim=mc.dim_s3,
            num_windows=config.window.num_windows,
        )

        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.LayerNorm):
            if m.elementwise_affine:
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward_full(self, x: torch.Tensor, window_id: torch.Tensor,
                     region_masks_s2: Optional[torch.Tensor] = None,
                     ) -> Dict[str, torch.Tensor]:
        """
        Full forward pass (no masking) — used by the EMA target encoder.

        Args:
            x: (B, 1, D, H, W), window_id: (B,), region_masks_s2: (B, R, N_s2)
        Returns:
            dict with s1_features, s2_features, s3_features, g_img
        """
        B = x.shape[0]
        pc = self.config.patch

        cond = self.window_cond(window_id=window_id)

        tokens = self.patch_embed(x)
        tokens = tokens + self.pos_embed_s1(B)

        s1_out = self.stage1(tokens, cond)

        tokens_s2 = self.merge_1to2(s1_out, pc.grid_size_s1)
        tokens_s2 = tokens_s2 + self.pos_embed_s2(B)

        extra_kv = None
        if self.use_region_tokens and region_masks_s2 is not None:
            extra_kv = self.region_tokens(tokens_s2, region_masks_s2)

        s2_out = self.stage2(tokens_s2, cond, extra_kv=extra_kv)

        tokens_s3 = self.merge_2to3(s2_out, pc.grid_size_s2)
        tokens_s3 = tokens_s3 + self.pos_embed_s3(B)

        extra_kv_s3 = self.region_proj_s2to3(extra_kv) if extra_kv is not None else None
        s3_out = self.stage3(tokens_s3, cond, extra_kv=extra_kv_s3)

        g_img = self.readout(s3_out)

        return {
            "s1_features": s1_out,
            "s2_features": s2_out,
            "s3_features": s3_out,
            "g_img": g_img,
        }

    def forward_masked(self, x: torch.Tensor, window_id: torch.Tensor,
                       visible_mask_s3: torch.Tensor,
                       region_masks_s2: Optional[torch.Tensor] = None,
                       ) -> Dict[str, torch.Tensor]:
        """
        Masked forward pass — used by the context encoder.
        Full processing at S1-S2, masking at S2->S3 boundary.

        Args:
            x: (B, 1, D, H, W), window_id: (B,),
            visible_mask_s3: (B, N_s3) bool True=visible,
            region_masks_s2: (B, R, N_s2)
        Returns:
            dict with s1_features, s2_features, s3_visible, g_img, region_tokens
        """
        B = x.shape[0]
        pc = self.config.patch

        cond = self.window_cond(window_id=window_id)

        # Patch embed -> Stage 1 (full)
        tokens = self.patch_embed(x)
        tokens = tokens + self.pos_embed_s1(B)
        s1_out = self.stage1(tokens, cond)

        # Merge -> Stage 2 (full)
        tokens_s2 = self.merge_1to2(s1_out, pc.grid_size_s1)
        tokens_s2 = tokens_s2 + self.pos_embed_s2(B)

        extra_kv = None
        if self.use_region_tokens and region_masks_s2 is not None:
            extra_kv = self.region_tokens(tokens_s2, region_masks_s2)

        s2_out = self.stage2(tokens_s2, cond, extra_kv=extra_kv)

        # Merge to S3 resolution
        tokens_s3_all = self.merge_2to3(s2_out, pc.grid_size_s2)
        pos_s3_all = self.pos_embed_s3(B)

        # Apply masking: keep only visible tokens
        vis_tokens_list = []
        vis_pos_list = []
        for b in range(B):
            vis_idx = visible_mask_s3[b].nonzero(as_tuple=True)[0]
            if vis_idx.shape[0] == 0:
                # Guard: keep at least 1 token to prevent empty sequence crash
                vis_idx = torch.tensor([0], device=x.device)
            vis_tokens_list.append(tokens_s3_all[b, vis_idx])
            vis_pos_list.append(pos_s3_all[b, vis_idx])

        max_vis = max(t.shape[0] for t in vis_tokens_list)
        D3 = tokens_s3_all.shape[-1]

        vis_tokens = torch.zeros(B, max_vis, D3, device=x.device, dtype=x.dtype)
        vis_pos = torch.zeros(B, max_vis, D3, device=x.device, dtype=x.dtype)

        for b in range(B):
            n = vis_tokens_list[b].shape[0]
            vis_tokens[b, :n] = vis_tokens_list[b]
            vis_pos[b, :n] = vis_pos_list[b]

        vis_tokens = vis_tokens + vis_pos

        # Build padding mask for variable-length visible tokens: True = padded
        vis_padding_mask = torch.ones(B, max_vis, dtype=torch.bool, device=x.device)
        for b in range(B):
            n = vis_tokens_list[b].shape[0]
            vis_padding_mask[b, :n] = False

        extra_kv_s3 = self.region_proj_s2to3(extra_kv) if extra_kv is not None else None
        s3_out = self.stage3(vis_tokens, cond, extra_kv=extra_kv_s3,
                             key_padding_mask=vis_padding_mask)

        g_img = self.readout(s3_out, key_padding_mask=vis_padding_mask)

        return {
            "s1_features": s1_out,
            "s2_features": s2_out,
            "s3_visible": s3_out,
            "s3_visible_mask": visible_mask_s3,
            "s3_vis_padding_mask": vis_padding_mask,  # (B, max_vis) True=padded
            "g_img": g_img,
            "region_tokens": extra_kv_s3,
        }
