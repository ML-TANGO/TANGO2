"""
CT-JEPA v2 Phrase Grounding
=============================
Extract spatial heatmaps showing where the model grounds text phrases
in the CT volume. Text conditioning is via a single matryoshka-truncated
text token appended to the predictor's cross-attention context.

Three approaches, increasing in rigor:
1. Direct Attention Extraction — read cross-attention weights for the text token
2. Phrase-Level Aggregation — not applicable (single text token, not per-phrase tokens)
3. Causal Grounding (Perturbation) — measure prediction change when text is ablated

Usage:
    from ctjepa_v2.grounding import PhraseGrounder

    grounder = PhraseGrounder(model, device='cuda')
    heatmaps = grounder.ground_phrases(
        volume, window_id, texts=["..."],
        method="attention",  # or "causal"
    )
    # heatmaps: dict with 'global_heatmap' -> Tensor(D3, H3, W3)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Attention Capture via Hooks
# ---------------------------------------------------------------------------

class AttentionCapture:
    """
    Context manager that hooks into the cross-attention layers of PredictorP3
    and captures the attention weight matrices.

    Each captured map has shape (B, M, C) where:
        M = number of spatial query positions
        C = context length (visible tokens + 1 text token)
    """

    def __init__(self, predictor_p3: nn.Module):
        self.predictor = predictor_p3
        self.hooks = []
        self.attention_maps = []

    def _make_hook(self):
        """Create a hook function that captures MHA attention weights."""
        def hook_fn(module, args, kwargs, output):
            # nn.MultiheadAttention returns (attn_output, attn_output_weights)
            if isinstance(output, tuple) and len(output) >= 2:
                attn_weights = output[1]
                if attn_weights is not None:
                    self.attention_maps.append(attn_weights.detach())
        return hook_fn

    def __enter__(self):
        self.attention_maps = []
        self.hooks = []

        for block in self.predictor.blocks:
            # Hook into the cross-attention MHA (which now includes the text token)
            mha = block.cross_attn_ctx
            h = mha.register_forward_hook(self._make_hook(), with_kwargs=True)
            self.hooks.append(h)
        return self

    def __exit__(self, *args):
        for h in self.hooks:
            h.remove()
        self.hooks = []

    def get_text_token_attention(self) -> Optional[torch.Tensor]:
        """
        Extract attention weight to the text token (last position in context).

        Returns:
            (B, M) attention to the text token, averaged over layers and heads
        """
        if not self.attention_maps:
            return None

        processed = []
        for attn in self.attention_maps:
            if attn.ndim == 4:
                # (B, heads, M, C) -> average over heads -> (B, M, C)
                attn = attn.mean(dim=1)
            # Last position is the text token -> (B, M)
            processed.append(attn[:, :, -1])

        # Average over layers: (num_layers, B, M) -> (B, M)
        return torch.stack(processed).mean(dim=0)


# ---------------------------------------------------------------------------
# Core Heatmap Extraction
# ---------------------------------------------------------------------------

@torch.no_grad()
def extract_text_heatmap(model, volume: torch.Tensor, window_id: torch.Tensor,
                         texts: List[str],
                         region_masks_s2: Optional[torch.Tensor] = None,
                         grid_s3: Tuple[int, int, int] = (6, 8, 8),
                         ) -> Dict[str, torch.Tensor]:
    """
    Extract spatial heatmap showing where the model attends to the text token.

    Runs the full volume through the encoder (no masking), then queries ALL
    Stage-3 positions through the predictor with the given text.

    Args:
        model: CTJEPA model
        volume: (B, 1, D, H, W)
        window_id: (B,)
        texts: list of text strings
        region_masks_s2: optional (B, R, N_s2)
        grid_s3: Stage-3 spatial dimensions

    Returns:
        global_heatmap: (B, D3, H3, W3) — spatial attention to text token
    """
    model.eval()
    B = volume.shape[0]
    device = volume.device
    D3, H3, W3 = grid_s3
    N_s3 = D3 * H3 * W3

    # 1. Full encoder pass (no masking)
    enc_out = model.context_encoder.forward_full(volume, window_id, region_masks_s2)
    s3_features = enc_out['s3_features']  # (B, N_s3, dim_s3)

    # 2. Encode text -> get matryoshka-truncated embedding
    text_out = model.text_encoder(texts, target_device=device)
    raw_global = text_out['raw_global']  # (B, text_dim)
    z_txt_pred = raw_global[:, :model.matryoshka_pred_dim]  # (B, predictor_dim)

    # 3. Window conditioning
    cond = model.context_encoder.window_cond(window_id=window_id)

    # 4. Query ALL S3 positions through the predictor
    all_indices = torch.arange(N_s3, device=device).unsqueeze(0).expand(B, -1)
    visible_mask = torch.ones(B, N_s3, dtype=torch.bool, device=device)
    text_mask = torch.ones(B, dtype=torch.bool, device=device)

    region_tokens = enc_out.get('region_tokens')

    # 5. Forward through predictor with attention capture
    with AttentionCapture(model.predictor_p3) as cap:
        _ = model.predictor_p3(
            visible_embeddings=s3_features,
            visible_mask=visible_mask,
            masked_indices=all_indices,
            cond=cond,
            z_txt_pred=z_txt_pred,
            text_mask=text_mask,
            region_tokens=region_tokens,
        )
        text_attn = cap.get_text_token_attention()  # (B, N_s3)

    if text_attn is None:
        raise RuntimeError("No attention maps captured.")

    # 6. Reshape to spatial heatmap: (B, D3, H3, W3)
    global_heatmap = text_attn.reshape(B, D3, H3, W3)

    return {
        'global_heatmap': global_heatmap,  # (B, D3, H3, W3)
    }


# ---------------------------------------------------------------------------
# Causal Grounding (Perturbation-Based)
# ---------------------------------------------------------------------------

@torch.no_grad()
def causal_grounding(model, volume: torch.Tensor, window_id: torch.Tensor,
                     texts: List[str],
                     region_masks_s2: Optional[torch.Tensor] = None,
                     grid_s3: Tuple[int, int, int] = (6, 8, 8),
                     ) -> Dict[str, torch.Tensor]:
    """
    Measure the causal effect of text on each spatial prediction.

    Compares predictions with text vs without text (text token masked),
    then measures the L2 difference per spatial position.

    Args:
        model: CTJEPA model
        volume: (1, 1, D, H, W) — single sample
        window_id: (1,)
        texts: list of text strings
        region_masks_s2: optional
        grid_s3: Stage-3 spatial dimensions

    Returns:
        causal_heatmap: (D3, H3, W3) normalized causal effect
    """
    model.eval()
    device = volume.device
    D3, H3, W3 = grid_s3
    N_s3 = D3 * H3 * W3

    # Encode volume
    enc_out = model.context_encoder.forward_full(volume, window_id, region_masks_s2)
    s3_features = enc_out['s3_features']

    # Encode text
    text_out = model.text_encoder(texts, target_device=device)
    raw_global = text_out['raw_global']
    z_txt_pred = raw_global[:, :model.matryoshka_pred_dim]

    # Setup
    cond = model.context_encoder.window_cond(window_id=window_id)
    all_indices = torch.arange(N_s3, device=device).unsqueeze(0)
    visible_mask = torch.ones(1, N_s3, dtype=torch.bool, device=device)
    region_tokens = enc_out.get('region_tokens')

    # Prediction WITH text
    pred_with = model.predictor_p3(
        visible_embeddings=s3_features,
        visible_mask=visible_mask,
        masked_indices=all_indices,
        cond=cond,
        z_txt_pred=z_txt_pred,
        text_mask=torch.ones(1, dtype=torch.bool, device=device),
        region_tokens=region_tokens,
    )

    # Prediction WITHOUT text (text token masked out)
    pred_without = model.predictor_p3(
        visible_embeddings=s3_features,
        visible_mask=visible_mask,
        masked_indices=all_indices,
        cond=cond,
        z_txt_pred=z_txt_pred,
        text_mask=torch.zeros(1, dtype=torch.bool, device=device),
        region_tokens=region_tokens,
    )

    # L2 difference per position → causal effect
    effect = (pred_with - pred_without).pow(2).mean(dim=-1)  # (1, N_s3)
    heatmap = effect[0].reshape(D3, H3, W3)

    # Normalize
    vmin, vmax = heatmap.min(), heatmap.max()
    if vmax - vmin > 1e-8:
        heatmap = (heatmap - vmin) / (vmax - vmin)

    return {'causal_heatmap': heatmap}


# ---------------------------------------------------------------------------
# Heatmap Upsampling
# ---------------------------------------------------------------------------

def upsample_heatmap(heatmap: torch.Tensor,
                     target_size: Tuple[int, int, int],
                     mode: str = 'trilinear') -> torch.Tensor:
    """
    Upsample a Stage-3 resolution heatmap to a higher resolution.

    Args:
        heatmap: (D3, H3, W3) or (B, D3, H3, W3)
        target_size: (D, H, W) target dimensions
        mode: interpolation mode

    Returns:
        upsampled: same batch dims + target_size
    """
    squeeze = False
    if heatmap.ndim == 3:
        heatmap = heatmap.unsqueeze(0).unsqueeze(0)
        squeeze = True
    elif heatmap.ndim == 4:
        heatmap = heatmap.unsqueeze(1)

    upsampled = F.interpolate(heatmap.float(), size=target_size,
                               mode=mode, align_corners=False)

    if squeeze:
        return upsampled[0, 0]
    else:
        return upsampled[:, 0]


# ---------------------------------------------------------------------------
# High-Level Interface
# ---------------------------------------------------------------------------

class PhraseGrounder:
    """
    High-level interface for phrase grounding in CT-JEPA v2.

    Text conditioning is via a single matryoshka-truncated global embedding.
    Grounding produces a single spatial heatmap showing where the model
    attends to text, rather than per-phrase heatmaps.

    Usage:
        grounder = PhraseGrounder(model, device='cuda')
        results = grounder.ground(
            volume, window_id, texts=["bilateral pleural effusion"],
            method="attention",  # or "causal"
        )
        heatmap = results['global_heatmap']  # (D3, H3, W3)
    """

    def __init__(self, model, device: str = 'cuda',
                 grid_s3: Tuple[int, int, int] = (6, 8, 8)):
        self.model = model
        self.device = device
        self.grid_s3 = grid_s3
        self.model.eval()

    @torch.no_grad()
    def ground(self,
               volume: torch.Tensor,
               window_id: torch.Tensor,
               texts: List[str],
               region_masks_s2: Optional[torch.Tensor] = None,
               method: str = "attention",
               upsample_to: Optional[Tuple[int, int, int]] = None,
               ) -> Dict:
        """
        Ground text to spatial locations in the CT volume.

        Args:
            volume: (1, 1, D, H, W) single CT volume
            window_id: (1,) HU window ID
            texts: list of report text strings
            region_masks_s2: optional anatomy masks
            method: "attention" (fast) or "causal" (rigorous, 2 passes)
            upsample_to: optional target resolution

        Returns:
            dict with:
                global_heatmap: Tensor(D3, H3, W3) — spatial attention to text
                causal_heatmap: (causal method only)
        """
        assert volume.shape[0] == 1, "PhraseGrounder expects single sample (B=1)"

        volume = volume.to(self.device)
        window_id = window_id.to(self.device)
        if region_masks_s2 is not None:
            region_masks_s2 = region_masks_s2.to(self.device)

        if method == "attention":
            result = extract_text_heatmap(
                self.model, volume, window_id, texts,
                region_masks_s2=region_masks_s2,
                grid_s3=self.grid_s3,
            )
            result['global_heatmap'] = result['global_heatmap'][0]  # (D3, H3, W3)

        elif method == "causal":
            result = causal_grounding(
                self.model, volume, window_id, texts,
                region_masks_s2=region_masks_s2,
                grid_s3=self.grid_s3,
            )

        else:
            raise ValueError(f"Unknown method: {method}. Use 'attention' or 'causal'")

        # Optionally upsample
        if upsample_to is not None:
            for key in ['global_heatmap', 'causal_heatmap']:
                if key in result:
                    result[f'{key}_upsampled'] = upsample_heatmap(result[key], upsample_to)

        return result


# ---------------------------------------------------------------------------
# Visualization Utilities
# ---------------------------------------------------------------------------

def save_grounding_overlay(volume_slice: np.ndarray, heatmap_slice: np.ndarray,
                           phrase: str, save_path: str,
                           alpha: float = 0.5, cmap: str = 'jet'):
    """
    Save a CT slice with heatmap overlay.

    Args:
        volume_slice: (H, W) grayscale CT slice [0, 1]
        heatmap_slice: (H, W) heatmap [0, 1]
        phrase: text label
        save_path: output path
        alpha: overlay transparency
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        axes[0].imshow(volume_slice, cmap='gray', vmin=0, vmax=1)
        axes[0].set_title('CT Slice')
        axes[0].axis('off')

        im = axes[1].imshow(heatmap_slice, cmap=cmap, vmin=0, vmax=1)
        axes[1].set_title('Grounding Heatmap')
        axes[1].axis('off')
        plt.colorbar(im, ax=axes[1], fraction=0.046)

        axes[2].imshow(volume_slice, cmap='gray', vmin=0, vmax=1)
        axes[2].imshow(heatmap_slice, cmap=cmap, alpha=alpha, vmin=0, vmax=1)
        axes[2].set_title('Overlay')
        axes[2].axis('off')

        fig.suptitle(f'Phrase: "{phrase}"', fontsize=14, fontweight='bold')
        fig.tight_layout()
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return save_path
    except ImportError:
        return None
