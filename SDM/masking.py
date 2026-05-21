"""
CT-JEPA v2 Masking Strategies
===============================
All masking is defined on the Stage-3 grid (6x8x8 = 384 tokens).
Families: cuboid, axial/coronal/sagittal slabs, skip-slabs, frequency masking.
Supports anatomy-guided placement bias and curriculum scheduling.
"""

import torch
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass


@dataclass
class MaskResult:
    """Output of a masking operation."""
    visible_mask: torch.Tensor   # (N_s3,) bool — True = visible
    masked_indices: torch.Tensor  # (M,) long — indices of masked positions
    visible_indices: torch.Tensor # (V,) long — indices of visible positions
    mask_ratio: float
    family: str


GRID_S3 = (6, 8, 8)
N_S3 = 6 * 8 * 8  # 384


def _idx_3d_to_flat(d: int, h: int, w: int,
                     grid: Tuple[int, int, int] = GRID_S3) -> int:
    return d * grid[1] * grid[2] + h * grid[2] + w


def _flat_to_3d(idx: int, grid: Tuple[int, int, int] = GRID_S3) -> Tuple[int, int, int]:
    d = idx // (grid[1] * grid[2])
    remainder = idx % (grid[1] * grid[2])
    h = remainder // grid[2]
    w = remainder % grid[2]
    return (d, h, w)


# ---------------------------------------------------------------------------
# Cuboid Masking
# ---------------------------------------------------------------------------

def sample_cuboid_mask(num_targets: int = 5,
                       min_size: Tuple[int, int, int] = (2, 2, 2),
                       max_size: Tuple[int, int, int] = (3, 4, 4),
                       anatomy_weights: Optional[np.ndarray] = None,
                       grid: Tuple[int, int, int] = GRID_S3) -> MaskResult:
    D, H, W = grid
    N = D * H * W
    mask = np.zeros(N, dtype=bool)

    for _ in range(num_targets):
        sd = np.random.randint(min_size[0], max_size[0] + 1)
        sh = np.random.randint(min_size[1], max_size[1] + 1)
        sw = np.random.randint(min_size[2], max_size[2] + 1)

        if anatomy_weights is not None:
            probs = anatomy_weights / anatomy_weights.sum()
            center_flat = np.random.choice(N, p=probs)
            cd, ch, cw = _flat_to_3d(center_flat, grid)
        else:
            cd = np.random.randint(0, D)
            ch = np.random.randint(0, H)
            cw = np.random.randint(0, W)

        d_start = max(0, cd - sd // 2)
        d_end = min(D, d_start + sd)
        h_start = max(0, ch - sh // 2)
        h_end = min(H, h_start + sh)
        w_start = max(0, cw - sw // 2)
        w_end = min(W, w_start + sw)

        mask_3d = mask.reshape(D, H, W)
        mask_3d[d_start:d_end, h_start:h_end, w_start:w_end] = True
        mask = mask_3d.reshape(-1)

    visible_mask = torch.tensor(~mask)
    masked_indices = torch.where(~visible_mask)[0]
    visible_indices = torch.where(visible_mask)[0]

    return MaskResult(
        visible_mask=visible_mask,
        masked_indices=masked_indices,
        visible_indices=visible_indices,
        mask_ratio=mask.sum() / N,
        family="cuboid",
    )


# ---------------------------------------------------------------------------
# Slab Masking
# ---------------------------------------------------------------------------

def sample_slab_mask(plane: str = "axial",
                     slab_width: int = 2,
                     num_slabs: int = 3,
                     anatomy_weights: Optional[np.ndarray] = None,
                     grid: Tuple[int, int, int] = GRID_S3) -> MaskResult:
    D, H, W = grid
    N = D * H * W
    mask = np.zeros(N, dtype=bool)

    if plane == "axial":
        axis_len = D
    elif plane == "coronal":
        axis_len = H
    elif plane == "sagittal":
        axis_len = W
    else:
        raise ValueError(f"Unknown plane: {plane}")

    if anatomy_weights is not None:
        weights_3d = anatomy_weights.reshape(D, H, W)
        if plane == "axial":
            slice_weights = weights_3d.sum(axis=(1, 2))
        elif plane == "coronal":
            slice_weights = weights_3d.sum(axis=(0, 2))
        else:
            slice_weights = weights_3d.sum(axis=(0, 1))
        slice_weights = slice_weights / slice_weights.sum()
        centers = np.random.choice(axis_len, size=num_slabs, replace=False, p=slice_weights)
    else:
        centers = np.random.choice(axis_len, size=min(num_slabs, axis_len), replace=False)

    mask_3d = mask.reshape(D, H, W)
    for center in centers:
        start = max(0, center - slab_width // 2)
        end = min(axis_len, start + slab_width)

        for s in range(start, end):
            if plane == "axial":
                mask_3d[s, :, :] = True
            elif plane == "coronal":
                mask_3d[:, s, :] = True
            elif plane == "sagittal":
                mask_3d[:, :, s] = True
    mask = mask_3d.reshape(-1)

    visible_mask = torch.tensor(~mask)
    masked_indices = torch.where(~visible_mask)[0]
    visible_indices = torch.where(visible_mask)[0]

    return MaskResult(
        visible_mask=visible_mask,
        masked_indices=masked_indices,
        visible_indices=visible_indices,
        mask_ratio=mask.sum() / N,
        family=f"{plane}_slab",
    )


# ---------------------------------------------------------------------------
# Skip-Slab Masking
# ---------------------------------------------------------------------------

def sample_skip_slab_mask(plane: str = "axial",
                          center_width: int = 2,
                          gap: int = 1,
                          num_slabs: int = 2,
                          anatomy_weights: Optional[np.ndarray] = None,
                          grid: Tuple[int, int, int] = GRID_S3) -> MaskResult:
    D, H, W = grid
    N = D * H * W
    full_mask = np.zeros(N, dtype=bool)
    center_mask = np.zeros(N, dtype=bool)

    if plane == "axial":
        axis_len = D
    elif plane == "coronal":
        axis_len = H
    elif plane == "sagittal":
        axis_len = W
    else:
        raise ValueError(f"Unknown plane: {plane}")

    valid_positions = list(range(gap, axis_len - gap - center_width + 1))

    if len(valid_positions) < num_slabs:
        centers = valid_positions
    else:
        if anatomy_weights is not None:
            weights_3d = anatomy_weights.reshape(D, H, W)
            if plane == "axial":
                slice_weights = weights_3d.sum(axis=(1, 2))
            elif plane == "coronal":
                slice_weights = weights_3d.sum(axis=(0, 2))
            else:
                slice_weights = weights_3d.sum(axis=(0, 1))
            valid_weights = slice_weights[valid_positions]
            valid_weights = valid_weights / valid_weights.sum()
            centers = np.random.choice(valid_positions, size=num_slabs,
                                        replace=False, p=valid_weights)
        else:
            centers = np.random.choice(valid_positions, size=num_slabs, replace=False)

    def _mask_slice(s, axis, target_mask_3d):
        if axis == "axial":
            target_mask_3d[s, :, :] = True
        elif axis == "coronal":
            target_mask_3d[:, s, :] = True
        elif axis == "sagittal":
            target_mask_3d[:, :, s] = True

    full_mask_3d = full_mask.reshape(D, H, W)
    center_mask_3d = center_mask.reshape(D, H, W)

    for center in centers:
        for s in range(center - gap, center):
            if 0 <= s < axis_len:
                _mask_slice(s, plane, full_mask_3d)
        for s in range(center, center + center_width):
            if 0 <= s < axis_len:
                _mask_slice(s, plane, full_mask_3d)
                _mask_slice(s, plane, center_mask_3d)
        for s in range(center + center_width, center + center_width + gap):
            if 0 <= s < axis_len:
                _mask_slice(s, plane, full_mask_3d)

    full_mask = full_mask_3d.reshape(-1)
    center_mask = center_mask_3d.reshape(-1)

    visible_mask = torch.tensor(~full_mask)
    masked_indices = torch.where(torch.tensor(center_mask))[0]
    visible_indices = torch.where(visible_mask)[0]

    return MaskResult(
        visible_mask=visible_mask,
        masked_indices=masked_indices,
        visible_indices=visible_indices,
        mask_ratio=full_mask.sum() / N,
        family=f"{plane}_skip_slab",
    )


# ---------------------------------------------------------------------------
# Frequency Masking
# ---------------------------------------------------------------------------

def sample_frequency_mask(mode: str = "random",
                          mask_ratio: float = 0.5,
                          grid: Tuple[int, int, int] = GRID_S3) -> MaskResult:
    D, H, W = grid
    N = D * H * W

    freq_d = torch.fft.fftfreq(D)
    freq_h = torch.fft.fftfreq(H)
    freq_w = torch.fft.fftfreq(W)
    fd, fh, fw = torch.meshgrid(freq_d, freq_h, freq_w, indexing='ij')
    freq_magnitude = (fd**2 + fh**2 + fw**2).sqrt()

    if mode == "random":
        mode = np.random.choice(["low", "high"])

    freq_flat = freq_magnitude.reshape(-1)

    if mode == "low":
        threshold = torch.quantile(freq_flat, mask_ratio)
        mask = freq_magnitude <= threshold
    else:
        threshold = torch.quantile(freq_flat, 1.0 - mask_ratio)
        mask = freq_magnitude >= threshold

    mask_flat = mask.reshape(-1)
    visible_mask = ~mask_flat
    masked_indices = torch.where(mask_flat)[0]
    visible_indices = torch.where(~mask_flat)[0]

    return MaskResult(
        visible_mask=visible_mask,
        masked_indices=masked_indices,
        visible_indices=visible_indices,
        mask_ratio=mask_flat.float().mean().item(),
        family=f"frequency_{mode}",
    )


# ---------------------------------------------------------------------------
# Anatomy-Guided Sampling Weights
# ---------------------------------------------------------------------------

def compute_anatomy_weights(totalseg_mask: torch.Tensor,
                            grid: Tuple[int, int, int] = GRID_S3,
                            bias_strength: float = 2.0,
                            target_groups: Optional[Dict[str, List[int]]] = None,
                            ) -> np.ndarray:
    D, H, W = grid
    N = D * H * W

    if target_groups is None:
        target_groups = {"any_structure": list(range(1, 118))}

    pool_kernel = (
        totalseg_mask.shape[0] // D,
        totalseg_mask.shape[1] // H,
        totalseg_mask.shape[2] // W,
    )

    weights = np.zeros(N, dtype=np.float32)

    for group_name, label_ids in target_groups.items():
        binary_mask = torch.zeros_like(totalseg_mask, dtype=torch.float32)
        for lid in label_ids:
            binary_mask += (totalseg_mask == lid).float()
        binary_mask = binary_mask.clamp(0, 1)

        pooled = F.avg_pool3d(
            binary_mask.unsqueeze(0).unsqueeze(0),
            kernel_size=pool_kernel,
        ).squeeze().numpy()

        weights += pooled.reshape(-1)

    weights = weights * bias_strength
    weights = np.exp(weights) / np.exp(weights).sum()
    return weights


# ---------------------------------------------------------------------------
# Masked S2 Index Sampling
# ---------------------------------------------------------------------------

def sample_masked_s2_indices(visible_mask_s3: torch.Tensor,
                             grid_s2: Tuple[int, int, int] = (12, 16, 16),
                             grid_s3: Tuple[int, int, int] = (6, 8, 8),
                             num_samples: int = 512,
                             ) -> torch.Tensor:
    D3, H3, W3 = grid_s3
    D2, H2, W2 = grid_s2

    masked_s3 = (~visible_mask_s3).nonzero(as_tuple=True)[0]

    s2_candidates = []
    for idx_s3 in masked_s3:
        idx_s3 = idx_s3.item()
        d3 = idx_s3 // (H3 * W3)
        rem = idx_s3 % (H3 * W3)
        h3 = rem // W3
        w3 = rem % W3

        for dd in range(2):
            for dh in range(2):
                for dw in range(2):
                    d2 = d3 * 2 + dd
                    h2 = h3 * 2 + dh
                    w2 = w3 * 2 + dw
                    if d2 < D2 and h2 < H2 and w2 < W2:
                        s2_candidates.append(int(d2 * H2 * W2 + h2 * W2 + w2))

    s2_candidates = list(set(s2_candidates))

    if len(s2_candidates) <= num_samples:
        indices = torch.tensor(s2_candidates, dtype=torch.long)
        pad = torch.full((num_samples - len(s2_candidates),), -1, dtype=torch.long)
        indices = torch.cat([indices, pad])
    else:
        chosen = np.random.choice(s2_candidates, size=num_samples, replace=False)
        indices = torch.tensor(chosen, dtype=torch.long)

    return indices


# ---------------------------------------------------------------------------
# Main Mask Sampler with Curriculum
# ---------------------------------------------------------------------------

class MaskSampler:
    """Samples masks from mixture of families with curriculum support.

    Mask ratio schedule (aligned with training milestones):
        Phase 1 (Foundation):       epoch < text_intro    → mask_ratio_foundation (0.65)
        Phase 2 (Text conditioning): text_intro ≤ epoch < align_intro → mask_ratio_text (0.55)
        Phase 3 (Alignment):        epoch ≥ align_intro   → mask_ratio_alignment (0.45)

    Family probabilities also shift at the same boundaries:
        Phase 1: 60% cuboid, easy masks
        Phase 2: 30% cuboid, balanced rest
        Phase 3: 20% cuboid, 15% each slab, 15% skip-slab, 15% frequency
    """

    def __init__(self, config):
        self.config = config
        self.mc = config.masking
        self.text_intro = config.text.text_introduction_epoch
        self.align_intro = config.loss.align_introduction_epoch

    def get_target_mask_ratio(self, epoch: int) -> float:
        if epoch < self.text_intro:
            return self.mc.mask_ratio_foundation
        elif epoch < self.align_intro:
            return self.mc.mask_ratio_text
        else:
            return self.mc.mask_ratio_alignment

    def get_family_probs(self, epoch: int) -> Dict[str, float]:
        if epoch < self.text_intro:
            return {
                "cuboid": 0.60, "axial": 0.10, "coronal": 0.10,
                "sagittal": 0.10, "skip_slab": 0.05, "frequency": 0.05,
            }
        elif epoch < self.align_intro:
            return {
                "cuboid": 0.30, "axial": 0.14, "coronal": 0.14,
                "sagittal": 0.14, "skip_slab": 0.14, "frequency": 0.14,
            }
        else:
            return {
                "cuboid": 0.20, "axial": 0.15, "coronal": 0.15,
                "sagittal": 0.15, "skip_slab": 0.15, "frequency": 0.20,
            }

    def _enforce_mask_ratio(self, result: MaskResult, target_ratio: float,
                            tolerance: float = 0.10) -> MaskResult:
        """Adjust mask to be within tolerance of target ratio by flipping tokens."""
        N = result.visible_mask.shape[0]
        current_masked = (~result.visible_mask).sum().item()
        target_masked = int(round(target_ratio * N))

        if abs(current_masked - target_masked) <= int(tolerance * N):
            return result

        mask = ~result.visible_mask.numpy()

        if current_masked < target_masked:
            # Need to mask more tokens — randomly mask some visible ones
            visible_idx = np.where(~mask)[0]
            num_to_mask = min(target_masked - current_masked, len(visible_idx))
            flip = np.random.choice(visible_idx, size=num_to_mask, replace=False)
            mask[flip] = True
        else:
            # Need to unmask tokens — randomly reveal some masked ones
            masked_idx = np.where(mask)[0]
            num_to_unmask = min(current_masked - target_masked, len(masked_idx))
            flip = np.random.choice(masked_idx, size=num_to_unmask, replace=False)
            mask[flip] = False

        visible_mask = torch.tensor(~mask)
        return MaskResult(
            visible_mask=visible_mask,
            masked_indices=torch.where(~visible_mask)[0],
            visible_indices=torch.where(visible_mask)[0],
            mask_ratio=mask.sum() / N,
            family=result.family,
        )

    def sample(self, epoch: int, total_epochs: int,
               anatomy_weights: Optional[np.ndarray] = None) -> MaskResult:
        probs = self.get_family_probs(epoch)
        families = list(probs.keys())
        weights = list(probs.values())

        family = np.random.choice(families, p=weights)

        if family == "cuboid":
            result = sample_cuboid_mask(
                num_targets=self.mc.num_cuboid_targets,
                min_size=self.mc.cuboid_min_size,
                max_size=self.mc.cuboid_max_size,
                anatomy_weights=anatomy_weights,
            )
        elif family in ("axial", "coronal", "sagittal"):
            result = sample_slab_mask(
                plane=family,
                slab_width=self.mc.slab_width,
                num_slabs=self.mc.num_slabs,
                anatomy_weights=anatomy_weights,
            )
        elif family == "skip_slab":
            plane = np.random.choice(["axial", "coronal", "sagittal"])
            result = sample_skip_slab_mask(
                plane=plane,
                center_width=self.mc.skip_slab_center_width,
                gap=self.mc.skip_slab_gap,
                num_slabs=2,
                anatomy_weights=anatomy_weights,
            )
        elif family == "frequency":
            result = sample_frequency_mask(
                mode=self.mc.freq_mask_mode,
                mask_ratio=self.mc.freq_mask_ratio,
            )
        else:
            raise ValueError(f"Unknown masking family: {family}")

        target_ratio = self.get_target_mask_ratio(epoch)
        return self._enforce_mask_ratio(result, target_ratio)

    def sample_batch(self, batch_size: int, epoch: int, total_epochs: int,
                     anatomy_weights_batch: Optional[List[np.ndarray]] = None,
                     ) -> Tuple[torch.Tensor, torch.Tensor, List[MaskResult]]:
        results = []
        for b in range(batch_size):
            aw = anatomy_weights_batch[b] if anatomy_weights_batch is not None else None
            results.append(self.sample(epoch, total_epochs, anatomy_weights=aw))

        visible_masks = torch.stack([r.visible_mask for r in results])

        max_masked = max(r.masked_indices.shape[0] for r in results)
        masked_indices = torch.full((batch_size, max_masked), -1, dtype=torch.long)
        for b, r in enumerate(results):
            m = r.masked_indices.shape[0]
            masked_indices[b, :m] = r.masked_indices

        return visible_masks, masked_indices, results
