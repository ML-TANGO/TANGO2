"""
CT-JEPA v2 Building Blocks
===========================
Core building blocks from ThoraxJEPA plus Swin3D/ConvNeXt from ctjepa.

ThoraxJEPA blocks:
- AdaLN-Zero conditioning
- 3D Window Attention with relative position bias
- Depthwise Conv3D bridge for cross-window communication
- Patch embedding and patch merging
- Factorized 3D positional embeddings
- Region tokens

ctjepa blocks (ported):
- ConvNeXtBlock3D (depthwise conv k=7 + MLP)
- SwinBlock3D (windowed self-attention with shifted windows)
- Adapter stages to match the Stage interface
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import math


# ===========================================================================
# AdaLN-Zero: Adaptive Layer Normalization with zero-initialized conditioning
# ===========================================================================

class AdaLNZero(nn.Module):
    """Adaptive LayerNorm-Zero from DiT. Generates (scale, shift, gate) from conditioning."""

    def __init__(self, dim: int, cond_dim: int):
        super().__init__()
        self.norm = nn.LayerNorm(dim, elementwise_affine=False)
        self.proj = nn.Sequential(
            nn.SiLU(),
            nn.Linear(cond_dim, 3 * dim),
        )
        nn.init.zeros_(self.proj[-1].weight)
        nn.init.zeros_(self.proj[-1].bias)

    def forward(self, x: torch.Tensor, cond: torch.Tensor):
        gamma, beta, alpha = self.proj(cond).chunk(3, dim=-1)
        gamma = gamma.unsqueeze(1)
        beta = beta.unsqueeze(1)
        alpha = alpha.unsqueeze(1)
        normed = self.norm(x)
        modulated = (1 + gamma) * normed + beta
        return modulated, alpha


# ===========================================================================
# Window Conditioning Encoder
# ===========================================================================

class WindowConditioner(nn.Module):
    """Encodes window ID (discrete) or (WL, WW) continuous into conditioning vector."""

    def __init__(self, cond_dim: int, num_windows: int = 3, use_continuous: bool = False):
        super().__init__()
        self.use_continuous = use_continuous
        if use_continuous:
            self.mlp = nn.Sequential(
                nn.Linear(2, cond_dim),
                nn.SiLU(),
                nn.Linear(cond_dim, cond_dim),
            )
        else:
            self.embed = nn.Embedding(num_windows, cond_dim)
            self.mlp = nn.Sequential(
                nn.SiLU(),
                nn.Linear(cond_dim, cond_dim),
            )

    def forward(self, window_id: torch.Tensor = None,
                window_params: torch.Tensor = None) -> torch.Tensor:
        if self.use_continuous and window_params is not None:
            return self.mlp(window_params)
        else:
            return self.mlp(self.embed(window_id))


# ===========================================================================
# 3D Window Partition / Reverse
# ===========================================================================

def window_partition_3d(x: torch.Tensor, window_size: Tuple[int, int, int]):
    """
    Partition 3D token grid into non-overlapping windows.
    Args: x: (B, D, H, W, C), window_size: (wd, wh, ww)
    Returns: windows: (B*nW, wd*wh*ww, C), num_per_dim: (nd, nh, nw)
    """
    B, D, H, W, C = x.shape
    wd, wh, ww = window_size
    nd, nh, nw = D // wd, H // wh, W // ww
    x = x.view(B, nd, wd, nh, wh, nw, ww, C)
    x = x.permute(0, 1, 3, 5, 2, 4, 6, 7).contiguous()
    windows = x.view(B * nd * nh * nw, wd * wh * ww, C)
    return windows, (nd, nh, nw)


def window_reverse_3d(windows: torch.Tensor, window_size: Tuple[int, int, int],
                       grid_size: Tuple[int, int, int], batch_size: int):
    """Reverse window partition: (B*nW, N, C) -> (B, D, H, W, C)."""
    D, H, W = grid_size
    wd, wh, ww = window_size
    nd, nh, nw = D // wd, H // wh, W // ww
    C = windows.shape[-1]
    x = windows.view(batch_size, nd, nh, nw, wd, wh, ww, C)
    x = x.permute(0, 1, 4, 2, 5, 3, 6, 7).contiguous()
    x = x.view(batch_size, D, H, W, C)
    return x


# ===========================================================================
# Multi-Head Self-Attention with optional relative position bias
# ===========================================================================

class Attention3D(nn.Module):
    """Standard multi-head attention with optional 3D relative position bias."""

    def __init__(self, dim: int, num_heads: int, qkv_bias: bool = True,
                 attn_drop: float = 0.0, proj_drop: float = 0.0,
                 use_rel_pos_bias: bool = False,
                 window_size: Optional[Tuple[int, int, int]] = None):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5

        self.qkv = nn.Linear(dim, 3 * dim, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)

        self.use_rel_pos_bias = use_rel_pos_bias
        if use_rel_pos_bias and window_size is not None:
            wd, wh, ww = window_size
            self.rel_pos_bias_table = nn.Parameter(
                torch.zeros((2 * wd - 1) * (2 * wh - 1) * (2 * ww - 1), num_heads)
            )
            nn.init.trunc_normal_(self.rel_pos_bias_table, std=0.02)

            coords_d = torch.arange(wd)
            coords_h = torch.arange(wh)
            coords_w = torch.arange(ww)
            coords = torch.stack(torch.meshgrid(coords_d, coords_h, coords_w, indexing='ij'))
            coords_flat = coords.reshape(3, -1)
            relative_coords = coords_flat[:, :, None] - coords_flat[:, None, :]
            relative_coords = relative_coords.permute(1, 2, 0).contiguous()
            relative_coords[:, :, 0] += wd - 1
            relative_coords[:, :, 1] += wh - 1
            relative_coords[:, :, 2] += ww - 1
            relative_coords[:, :, 0] *= (2 * wh - 1) * (2 * ww - 1)
            relative_coords[:, :, 1] *= (2 * ww - 1)
            relative_position_index = relative_coords.sum(-1)
            self.register_buffer("relative_position_index", relative_position_index)

    def forward(self, x: torch.Tensor, extra_kv: Optional[torch.Tensor] = None,
                key_padding_mask: Optional[torch.Tensor] = None):
        B, N, C = x.shape
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv.unbind(0)

        if extra_kv is not None:
            M = extra_kv.shape[1]
            kv_extra = self.qkv(extra_kv).reshape(B, M, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
            _, k_extra, v_extra = kv_extra.unbind(0)
            k = torch.cat([k, k_extra], dim=2)
            v = torch.cat([v, v_extra], dim=2)

        attn = (q @ k.transpose(-2, -1)) * self.scale

        if self.use_rel_pos_bias:
            bias = self.rel_pos_bias_table[self.relative_position_index.view(-1)].view(
                N, N, -1).permute(2, 0, 1)
            if extra_kv is not None:
                bias = F.pad(bias, (0, extra_kv.shape[1]), value=0)
            attn = attn + bias.unsqueeze(0)

        # Apply key padding mask: True = padded position to ignore
        if key_padding_mask is not None:
            # key_padding_mask: (B, K) where K = total key length
            # Expand for extra_kv: pad mask with False (not padded) for extra_kv positions
            if extra_kv is not None:
                extra_mask = torch.zeros(B, extra_kv.shape[1], dtype=torch.bool, device=x.device)
                kpm = torch.cat([key_padding_mask, extra_mask], dim=1)
            else:
                kpm = key_padding_mask
            # (B, 1, 1, K) -> broadcast over heads and query positions
            attn = attn.masked_fill(kpm.unsqueeze(1).unsqueeze(2), float('-inf'))

        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        out = (attn @ v).transpose(1, 2).reshape(B, N, C)
        out = self.proj(out)
        out = self.proj_drop(out)
        return out


# ===========================================================================
# Feed-Forward Network
# ===========================================================================

class FFN(nn.Module):
    def __init__(self, dim: int, mlp_ratio: float = 4.0, drop: float = 0.0):
        super().__init__()
        hidden = int(dim * mlp_ratio)
        self.fc1 = nn.Linear(dim, hidden)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden, dim)
        self.drop = nn.Dropout(drop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.drop(self.fc2(self.act(self.fc1(x))))


# ===========================================================================
# Depthwise Conv3D Bridge (cross-window communication)
# ===========================================================================

class DepthwiseConvBridge3D(nn.Module):
    """Depthwise 3x3x3 convolution for cross-window communication. Replaces shifted windows."""

    def __init__(self, dim: int):
        super().__init__()
        self.conv = nn.Conv3d(dim, dim, kernel_size=3, padding=1, groups=dim, bias=True)
        self.norm = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor, grid_size: Tuple[int, int, int]) -> torch.Tensor:
        B, N, C = x.shape
        D, H, W = grid_size
        x_3d = x.view(B, D, H, W, C).permute(0, 4, 1, 2, 3)
        x_3d = self.conv(x_3d)
        x_3d = x_3d.permute(0, 2, 3, 4, 1).reshape(B, N, C)
        return self.norm(x_3d)


# ===========================================================================
# Drop Path (Stochastic Depth)
# ===========================================================================

class DropPath(nn.Module):
    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = drop_prob

    def forward(self, x):
        if not self.training or self.drop_prob == 0.0:
            return x
        keep_prob = 1.0 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        mask = torch.rand(shape, device=x.device, dtype=x.dtype) < keep_prob
        return x * mask / keep_prob


# ===========================================================================
# AdaLN Transformer Block (ThoraxJEPA's main block for S1-S2-S3)
# ===========================================================================

class AdaLNTransformerBlock(nn.Module):
    """Transformer block with AdaLN-Zero. Supports windowed and global attention."""

    def __init__(self, dim: int, num_heads: int, cond_dim: int,
                 mlp_ratio: float = 4.0, drop_path: float = 0.0,
                 use_window: bool = True,
                 window_size: Optional[Tuple[int, int, int]] = None,
                 use_conv_bridge: bool = True,
                 use_rel_pos_bias: bool = True):
        super().__init__()
        self.use_window = use_window
        self.window_size = window_size

        self.adaln_attn = AdaLNZero(dim, cond_dim)
        self.attn = Attention3D(
            dim, num_heads,
            use_rel_pos_bias=use_rel_pos_bias and window_size is not None,
            window_size=window_size if use_window else None,
        )

        self.adaln_ffn = AdaLNZero(dim, cond_dim)
        self.ffn = FFN(dim, mlp_ratio)

        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

        self.use_conv_bridge = use_conv_bridge and use_window
        if self.use_conv_bridge:
            self.conv_bridge = DepthwiseConvBridge3D(dim)

    def forward(self, x: torch.Tensor, cond: torch.Tensor,
                grid_size: Tuple[int, int, int],
                extra_kv: Optional[torch.Tensor] = None,
                key_padding_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        B = x.shape[0]

        x_mod, gate_attn = self.adaln_attn(x, cond)

        if self.use_window and self.window_size is not None:
            D, H, W = grid_size
            x_3d = x_mod.view(B, D, H, W, -1)
            windows, (nd, nh, nw) = window_partition_3d(x_3d, self.window_size)

            if extra_kv is not None:
                num_win = nd * nh * nw
                extra_kv_win = extra_kv.unsqueeze(1).expand(
                    -1, num_win, -1, -1
                ).reshape(B * num_win, extra_kv.shape[1], extra_kv.shape[2])
            else:
                extra_kv_win = None

            attn_out = self.attn(windows, extra_kv=extra_kv_win)
            attn_out = window_reverse_3d(attn_out, self.window_size, grid_size, B)
            attn_out = attn_out.view(B, -1, x.shape[-1])
        else:
            attn_out = self.attn(x_mod, extra_kv=extra_kv,
                                 key_padding_mask=key_padding_mask)

        x = x + self.drop_path(gate_attn * attn_out)

        if self.use_conv_bridge:
            x = x + self.conv_bridge(x, grid_size)

        x_mod2, gate_ffn = self.adaln_ffn(x, cond)
        x = x + self.drop_path(gate_ffn * self.ffn(x_mod2))

        return x


# ===========================================================================
# Patch Embedding (3D)
# ===========================================================================

class PatchEmbed3D(nn.Module):
    """Convert 3D volume to patch tokens via 3D convolution."""

    def __init__(self, in_channels: int = 1, embed_dim: int = 128,
                 patch_size: Tuple[int, int, int] = (8, 8, 8)):
        super().__init__()
        self.patch_size = patch_size
        self.proj = nn.Conv3d(in_channels, embed_dim,
                              kernel_size=patch_size, stride=patch_size)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """(B, C, D, H, W) -> (B, N, embed_dim)"""
        x = self.proj(x)
        B, C, D, H, W = x.shape
        x = x.flatten(2).transpose(1, 2)
        x = self.norm(x)
        return x


# ===========================================================================
# Patch Merging (3D) — 2x2x2 downsample
# ===========================================================================

class PatchMerge3D(nn.Module):
    """Merge 2x2x2 neighboring tokens into one. Halves spatial resolution."""

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.reduction = nn.Linear(8 * in_dim, out_dim, bias=False)
        self.norm = nn.LayerNorm(8 * in_dim)

    def forward(self, x: torch.Tensor, grid_size: Tuple[int, int, int]) -> torch.Tensor:
        """(B, N, C) -> (B, N/8, out_dim)"""
        B, N, C = x.shape
        D, H, W = grid_size
        x = x.view(B, D, H, W, C)
        x0 = x[:, 0::2, 0::2, 0::2, :]
        x1 = x[:, 0::2, 0::2, 1::2, :]
        x2 = x[:, 0::2, 1::2, 0::2, :]
        x3 = x[:, 0::2, 1::2, 1::2, :]
        x4 = x[:, 1::2, 0::2, 0::2, :]
        x5 = x[:, 1::2, 0::2, 1::2, :]
        x6 = x[:, 1::2, 1::2, 0::2, :]
        x7 = x[:, 1::2, 1::2, 1::2, :]
        x = torch.cat([x0, x1, x2, x3, x4, x5, x6, x7], dim=-1)
        x = x.view(B, -1, 8 * C)
        x = self.norm(x)
        x = self.reduction(x)
        return x


# ===========================================================================
# Factorized 3D Positional Embedding (memory-efficient for large grids)
# ===========================================================================

class FactorizedPosEmbed3D(nn.Module):
    """Factorized pos = pos_D + pos_H + pos_W. Memory-efficient for S1 (24x32x32)."""

    def __init__(self, grid_size: Tuple[int, int, int], dim: int):
        super().__init__()
        D, H, W = grid_size
        self.grid_size = grid_size
        self.pos_d = nn.Parameter(torch.zeros(1, D, 1, 1, dim))
        self.pos_h = nn.Parameter(torch.zeros(1, 1, H, 1, dim))
        self.pos_w = nn.Parameter(torch.zeros(1, 1, 1, W, dim))
        nn.init.trunc_normal_(self.pos_d, std=0.02)
        nn.init.trunc_normal_(self.pos_h, std=0.02)
        nn.init.trunc_normal_(self.pos_w, std=0.02)

    def forward(self, B: int) -> torch.Tensor:
        """Returns (B, D*H*W, dim)"""
        D, H, W = self.grid_size
        pos = self.pos_d + self.pos_h + self.pos_w
        pos = pos.expand(B, -1, -1, -1, -1)
        return pos.reshape(B, D * H * W, -1)


# ===========================================================================
# Full 3D Positional Embedding (for Stage 3 — 384 tokens)
# ===========================================================================

class FullPosEmbed3D(nn.Module):
    """Learned absolute positional embedding for small grids."""

    def __init__(self, grid_size: Tuple[int, int, int], dim: int):
        super().__init__()
        self.grid_size = grid_size
        num_tokens = math.prod(grid_size)
        self.pos_embed = nn.Parameter(torch.zeros(1, num_tokens, dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

    def forward(self, B: int) -> torch.Tensor:
        return self.pos_embed.expand(B, -1, -1)

    def get_embed_at_indices(self, indices: torch.Tensor) -> torch.Tensor:
        return self.pos_embed[:, indices, :]


# ===========================================================================
# Region Token Module
# ===========================================================================

class RegionTokens(nn.Module):
    """Converts TotalSegmentator masks into learnable region tokens."""

    def __init__(self, num_regions: int, dim: int):
        super().__init__()
        self.num_regions = num_regions
        self.region_embeds = nn.Parameter(torch.zeros(1, num_regions, dim))
        nn.init.trunc_normal_(self.region_embeds, std=0.02)
        self.proj = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, dim),
        )

    def forward(self, tokens: torch.Tensor,
                region_masks: torch.Tensor) -> torch.Tensor:
        """
        Args:
            tokens: (B, N, D), region_masks: (B, R, N) soft masks
        Returns:
            region_tokens: (B, R, D)
        """
        B, N, D = tokens.shape
        mask_sum = region_masks.sum(dim=-1, keepdim=True).clamp(min=1e-6)
        weights = region_masks / mask_sum
        pooled = torch.bmm(weights, tokens)
        region_tokens = pooled + self.region_embeds.expand(B, -1, -1)
        return self.proj(region_tokens)


# ===========================================================================
# ConvNeXtBlock3D (from ctjepa — depthwise conv k=7 + MLP)
# ===========================================================================

class ConvNeXtBlock3D(nn.Module):
    """Lightweight local mixing block using depthwise 3D conv."""

    def __init__(self, dim: int, drop_path: float = 0.0):
        super().__init__()
        self.dwconv = nn.Conv3d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.norm = nn.LayerNorm(dim, eps=1e-6)
        self.pw1 = nn.Linear(dim, 4 * dim)
        self.act = nn.GELU()
        self.pw2 = nn.Linear(4 * dim, dim)
        self.gamma = nn.Parameter(1e-6 * torch.ones(dim))
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B,C,D,H,W] -> [B,C,D,H,W]"""
        residual = x
        x = self.dwconv(x)
        x = x.permute(0, 2, 3, 4, 1).contiguous()
        x = self.norm(x)
        x = self.pw1(x)
        x = self.act(x)
        x = self.pw2(x)
        x = self.gamma * x
        x = x.permute(0, 4, 1, 2, 3).contiguous()
        x = residual + self.drop_path(x)
        return x


# ===========================================================================
# Swin3D Blocks (from ctjepa — windowed self-attention with shifted windows)
# ===========================================================================

class RelativePositionBias3D(nn.Module):
    """Learnable 3D relative position bias for windowed attention."""

    def __init__(self, window_size: Tuple[int, int, int], num_heads: int):
        super().__init__()
        self.window_size = window_size
        self.num_heads = num_heads
        wD, wH, wW = window_size
        table_size = (2 * wD - 1) * (2 * wH - 1) * (2 * wW - 1)
        self.relative_position_bias_table = nn.Parameter(torch.zeros(table_size, num_heads))
        nn.init.trunc_normal_(self.relative_position_bias_table, std=0.02)

        coords_d = torch.arange(wD)
        coords_h = torch.arange(wH)
        coords_w = torch.arange(wW)
        coords = torch.stack(torch.meshgrid(coords_d, coords_h, coords_w, indexing="ij"))
        coords_flat = coords.reshape(3, -1)
        relative_coords = coords_flat[:, :, None] - coords_flat[:, None, :]
        relative_coords[0] += wD - 1
        relative_coords[1] += wH - 1
        relative_coords[2] += wW - 1
        relative_coords[0] *= (2 * wH - 1) * (2 * wW - 1)
        relative_coords[1] *= (2 * wW - 1)
        relative_position_index = relative_coords.sum(0)
        self.register_buffer("relative_position_index", relative_position_index)

    def forward(self) -> torch.Tensor:
        """Returns [num_heads, N, N]."""
        N = math.prod(self.window_size)
        bias = self.relative_position_bias_table[self.relative_position_index.view(-1)].view(
            N, N, self.num_heads)
        return bias.permute(2, 0, 1).contiguous()


class WindowAttention3D(nn.Module):
    """Multi-head self-attention within a 3D window with relative position bias."""

    def __init__(self, dim: int, num_heads: int, window_size: Tuple[int, int, int],
                 qkv_bias: bool = True, attn_drop: float = 0.0, proj_drop: float = 0.0):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.qkv = nn.Linear(dim, 3 * dim, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)
        self.rpb = RelativePositionBias3D(window_size, num_heads)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        BW, N, C = x.shape
        qkv = self.qkv(x).reshape(BW, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv.unbind(0)
        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn + self.rpb().unsqueeze(0)
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)
        x = (attn @ v).transpose(1, 2).reshape(BW, N, C)
        x = self.proj(x)
        x = self.proj_drop(x)
        return x


class SwinBlock3D(nn.Module):
    """Swin Transformer block for 3D data. Interface: [B,C,D,H,W] in/out."""

    def __init__(self, dim: int, num_heads: int, window_size: Tuple[int, int, int] = (4, 4, 4),
                 shift: bool = False, mlp_ratio: float = 4.0, drop: float = 0.0,
                 attn_drop: float = 0.0, drop_path: float = 0.0):
        super().__init__()
        self.window_size = window_size
        self.shift_size = tuple(s // 2 for s in window_size) if shift else (0, 0, 0)
        self.norm1 = nn.LayerNorm(dim)
        self.attn = WindowAttention3D(dim=dim, num_heads=num_heads, window_size=window_size,
                                      attn_drop=attn_drop, proj_drop=drop)
        self.norm2 = nn.LayerNorm(dim)
        hidden = int(dim * mlp_ratio)
        self.mlp = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Dropout(drop),
                                 nn.Linear(hidden, dim), nn.Dropout(drop))
        self.gamma1 = nn.Parameter(1e-6 * torch.ones(dim))
        self.gamma2 = nn.Parameter(1e-6 * torch.ones(dim))
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, D, H, W = x.shape
        wD, wH, wW = self.window_size
        xl = x.permute(0, 2, 3, 4, 1).contiguous()
        if any(s > 0 for s in self.shift_size):
            xl = torch.roll(xl, shifts=(-self.shift_size[0], -self.shift_size[1], -self.shift_size[2]),
                           dims=(1, 2, 3))
        xn = self.norm1(xl)
        nD, nH, nW = D // wD, H // wH, W // wW
        xn = xn.view(B, nD, wD, nH, wH, nW, wW, C).permute(0, 1, 3, 5, 2, 4, 6, 7).contiguous()
        xn = xn.view(B * nD * nH * nW, wD * wH * wW, C)
        xn = self.attn(xn)
        xn = xn.view(B, nD, nH, nW, wD, wH, wW, C).permute(0, 1, 4, 2, 5, 3, 6, 7).contiguous()
        xn = xn.view(B, D, H, W, C)
        if any(s > 0 for s in self.shift_size):
            xn = torch.roll(xn, shifts=(self.shift_size[0], self.shift_size[1], self.shift_size[2]),
                           dims=(1, 2, 3))
        xl = xl + self.drop_path(self.gamma1 * xn)
        xl = xl + self.drop_path(self.gamma2 * self.mlp(self.norm2(xl)))
        return xl.permute(0, 4, 1, 2, 3).contiguous()


class SwinStage3D(nn.Module):
    """Stage of alternating regular/shifted SwinBlock3D blocks. Interface: [B,C,D,H,W]."""

    def __init__(self, dim: int, depth: int, num_heads: int,
                 window_size: Tuple[int, int, int] = (4, 4, 4),
                 mlp_ratio: float = 4.0, drop: float = 0.0, attn_drop: float = 0.0,
                 drop_path_rates: list = None):
        super().__init__()
        if drop_path_rates is None:
            drop_path_rates = [0.0] * depth
        self.blocks = nn.ModuleList([
            SwinBlock3D(dim=dim, num_heads=num_heads, window_size=window_size,
                        shift=(i % 2 == 1), mlp_ratio=mlp_ratio, drop=drop,
                        attn_drop=attn_drop, drop_path=drop_path_rates[i])
            for i in range(depth)
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for blk in self.blocks:
            x = blk(x)
        return x


# ===========================================================================
# Adapter Stages — match Stage.forward(x, cond, extra_kv) interface
# ===========================================================================

class ConvNeXtStage3D(nn.Module):
    """Adapter: wraps ConvNeXtBlock3D blocks to match Stage interface (B,N,C) tokens."""

    def __init__(self, dim: int, depth: int, grid_size: Tuple[int, int, int] = None,
                 drop_path_rates: list = None):
        super().__init__()
        if drop_path_rates is None:
            drop_path_rates = [0.0] * depth
        self.blocks = nn.ModuleList([
            ConvNeXtBlock3D(dim, drop_path=drop_path_rates[i])
            for i in range(depth)
        ])
        self.grid_size = grid_size

    def forward(self, x: torch.Tensor, cond: torch.Tensor,
                extra_kv: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: (B, N, C) tokens
            cond: (B, cond_dim) — ignored for ConvNeXt
            extra_kv: ignored
        Returns:
            x: (B, N, C) tokens
        """
        B, N, C = x.shape
        D, H, W = self.grid_size
        x = x.view(B, D, H, W, C).permute(0, 4, 1, 2, 3).contiguous()  # (B, C, D, H, W)
        for blk in self.blocks:
            x = blk(x)
        x = x.permute(0, 2, 3, 4, 1).reshape(B, N, C)  # back to (B, N, C)
        return x


class SwinStageAdapter(nn.Module):
    """Adapter: wraps SwinStage3D to match Stage interface (B,N,C) tokens."""

    def __init__(self, dim: int, depth: int, num_heads: int,
                 grid_size: Tuple[int, int, int] = None,
                 window_size: Tuple[int, int, int] = (4, 4, 4),
                 mlp_ratio: float = 4.0, drop_path_rates: list = None):
        super().__init__()
        self.grid_size = grid_size
        self.stage = SwinStage3D(
            dim=dim, depth=depth, num_heads=num_heads,
            window_size=window_size, mlp_ratio=mlp_ratio,
            drop_path_rates=drop_path_rates,
        )

    def forward(self, x: torch.Tensor, cond: torch.Tensor,
                extra_kv: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: (B, N, C) tokens
            cond: (B, cond_dim) — ignored for Swin
            extra_kv: ignored
        Returns:
            x: (B, N, C) tokens
        """
        B, N, C = x.shape
        D, H, W = self.grid_size
        x = x.view(B, D, H, W, C).permute(0, 4, 1, 2, 3).contiguous()  # (B, C, D, H, W)
        x = self.stage(x)
        x = x.permute(0, 2, 3, 4, 1).reshape(B, N, C)  # back to (B, N, C)
        return x
