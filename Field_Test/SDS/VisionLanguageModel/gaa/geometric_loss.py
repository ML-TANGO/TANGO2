"""
Geometric Attention Alignment (GAA) Loss

Implements Eq. 4 & 5 from:
  "Geometric Attention Alignment via Privileged Information:
   Bridging the Sim-to-Real Gap in Maritime VLMs"

Eq. 4 — Geometric mask:
  M_i = 1[ IoU(patch_i, b^s) > τ ]

Eq. 5 — Geometry-Consistency Loss:
  L_geo = (1/N_B) Σ_k  (1/||1-M^(k)||_1) * Σ_h ||A_h^(k) ⊙ (1-M^(k))||_2^2

  where A_h^(k) is the CLS-token attention map for head h of sample k,
  and (1-M) is the background mask (1=background, 0=foreground).
"""
import torch


def compute_geometric_mask(
    bboxes: list,
    feature_size: int,
    device: torch.device,
    tau: float = 0.5,
) -> torch.Tensor:
    """
    Project normalized bounding boxes onto the ViT patch grid via IoU threshold.

    Args:
        bboxes      : list (batch) of list of [x1, y1, x2, y2] in [0, 1] coords
        feature_size: grid side length (e.g. 24 for CLIP-ViT-L/14-336)
        device      : target device
        tau         : IoU threshold (paper default = 0.5)

    Returns:
        mask: (B, F, F) float tensor; 1 = foreground, 0 = background
    """
    B = len(bboxes)
    mask = torch.zeros(B, feature_size, feature_size, device=device)
    cell = 1.0 / feature_size

    # Patch boundary grids [F, F]
    y_idx = torch.arange(feature_size, device=device).float()
    x_idx = torch.arange(feature_size, device=device).float()
    cy1 = (y_idx * cell).view(feature_size, 1).expand(feature_size, feature_size)
    cx1 = (x_idx * cell).view(1, feature_size).expand(feature_size, feature_size)
    cy2 = cy1 + cell
    cx2 = cx1 + cell
    cell_area = cell * cell

    for i, box_list in enumerate(bboxes):
        if not box_list:
            continue
        for box in box_list:
            x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
            if x2 <= x1 or y2 <= y1:
                continue

            inter_x1 = torch.clamp(cx1, min=x1)
            inter_y1 = torch.clamp(cy1, min=y1)
            inter_x2 = torch.clamp(cx2, max=x2)
            inter_y2 = torch.clamp(cy2, max=y2)

            inter_w = torch.clamp(inter_x2 - inter_x1, min=0.0)
            inter_h = torch.clamp(inter_y2 - inter_y1, min=0.0)
            inter_area = inter_w * inter_h

            # Coverage = fraction of cell area covered by the bbox.
            # Standard IoU (inter/union) is impractical here because patches are
            # tiny relative to a large bbox, making IoU always << τ for interior
            # cells.  Coverage (inter/cell) is what the paper τ threshold intends:
            # a patch is foreground when more than τ of its area falls inside the box.
            coverage = inter_area / (cell_area + 1e-8)

            # Union of all foreground regions (multiple boxes per sample)
            mask[i] = torch.clamp(mask[i] + (coverage > tau).float(), max=1.0)

    return mask  # (B, F, F)


def compute_geometric_loss(
    attentions: torch.Tensor,
    bboxes: list,
    feature_size: int = 24,
    tau: float = 0.5,
) -> torch.Tensor:
    """
    Geometry-Consistency Loss (Eq. 5).

    Forces the CLS-token attention to stay off background patches by
    penalizing attention weight allocated outside foreground bounding boxes.

    Args:
        attentions  : last-layer ViT attention, shape (B, H, N+1, N+1)
                      index 0 in the sequence dimension = CLS token
        bboxes      : list of list of [x1, y1, x2, y2] normalized coords
        feature_size: ViT patch grid side (24 for CLIP-ViT-L/14-336)
        tau         : IoU threshold for foreground mask (paper default = 0.5)

    Returns:
        scalar loss (differentiable w.r.t. attentions)
    """
    B, num_heads, _, _ = attentions.shape

    # CLS token attending to each spatial patch: (B, H, F, F)
    cls_attn = attentions[:, :, 0, 1:]  # (B, H, N)
    cls_attn = cls_attn.reshape(B, num_heads, feature_size, feature_size)

    # Background mask: 1=background, 0=foreground; shape (B, 1, F, F)
    fg_mask = compute_geometric_mask(bboxes, feature_size, attentions.device, tau)
    bg_mask = (1.0 - fg_mask).unsqueeze(1)  # (B, 1, F, F)

    # Attention on background regions: (B, H, F, F)
    bg_attn = cls_attn * bg_mask

    # Σ_h ||A_h^(k) ⊙ (1-M^(k))||_2^2  →  (B,)
    head_loss_sum = bg_attn.pow(2).sum(dim=(1, 2, 3))

    # Normalize by background area per sample to remove object-size bias (Eq. 5)
    bg_size = bg_mask.sum(dim=(1, 2, 3)).clamp(min=1.0)  # (B,)

    loss = (head_loss_sum / bg_size).mean()
    return loss
