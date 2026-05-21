"""
CT-JEPA v2 Loss Functions
==========================
7-component loss stack with epoch-based scheduling:
L_JEPA3:  Main latent prediction loss at Stage 3
L_JEPA2:  Detail latent prediction loss at Stage 2
L_align:  Report-Image contrastive alignment (SigLIP)
L_SIGReg: Isotropic Gaussian regularization (collapse prevention)
L_cross:  Cross-stage prediction loss (fine->coarse)
L_decoder: Feature pyramid reconstruction loss
L_local:  Local contrastive loss at Stage 1
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from typing import Optional


class GatherWithGrad(torch.autograd.Function):
    """All-gather tensors across GPUs while preserving gradients."""

    @staticmethod
    def forward(ctx, x):
        world_size = dist.get_world_size()
        gathered = [torch.zeros_like(x) for _ in range(world_size)]
        dist.all_gather(gathered, x)
        # Replace our own shard with the original (gradient-bearing) tensor
        gathered[dist.get_rank()] = x
        return torch.cat(gathered, dim=0)

    @staticmethod
    def backward(ctx, grad_output):
        world_size = dist.get_world_size()
        rank = dist.get_rank()
        chunk_size = grad_output.shape[0] // world_size
        return grad_output[rank * chunk_size:(rank + 1) * chunk_size]


def gather_with_grad(x: torch.Tensor) -> torch.Tensor:
    """Gather tensors across GPUs if distributed, preserving gradients."""
    if not dist.is_initialized() or dist.get_world_size() == 1:
        return x
    return GatherWithGrad.apply(x)


class JEPALoss(nn.Module):
    """Latent prediction loss: L2 between LayerNorm'd embeddings."""

    def __init__(self, dim: int):
        super().__init__()
        self.norm_pred = nn.LayerNorm(dim, elementwise_affine=False)
        self.norm_tgt = nn.LayerNorm(dim, elementwise_affine=False)

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor,
                valid_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        pred_norm = self.norm_pred(predictions)
        tgt_norm = self.norm_tgt(targets.detach())
        loss = (pred_norm - tgt_norm).pow(2).mean(dim=-1)

        if valid_mask is not None:
            loss = (loss * valid_mask.float()).sum() / valid_mask.float().sum().clamp(min=1)
        else:
            loss = loss.mean()
        return loss


class SigLIPLoss(nn.Module):
    """SigLIP-style sigmoid contrastive loss for image-text alignment.

    Per-pair BCE instead of softmax — robust to noisy/missing text and does not
    require large batch sizes.  Learnable logit_scale (log-space) and logit_bias.

    Uses cross-GPU gathering in DDP to maximize contrastive batch size.
    Accepts a validity mask so each GPU can pass a full uniform-sized batch,
    then filter to valid pairs after gathering.
    """

    def __init__(self, init_logit_bias: float = -10.0):
        super().__init__()
        # log(1/0.07) ≈ 2.659 — standard CLIP-scale init
        self.logit_scale = nn.Parameter(torch.tensor(2.659, dtype=torch.float32))
        self.logit_bias = nn.Parameter(torch.tensor(init_logit_bias, dtype=torch.float32))

    def forward(self, z_img: torch.Tensor, z_txt: torch.Tensor,
                valid_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            z_img: (B, D) image embeddings (full batch; zeros for invalid samples)
            z_txt: (B, D) text embeddings (full batch; zeros for invalid samples)
            valid_mask: (B,) bool — True = sample participates in alignment.
                        If None, all samples are valid.
        """
        # Gather full uniform-sized batches across GPUs first
        z_img_all = gather_with_grad(z_img)
        z_txt_all = gather_with_grad(z_txt)

        # Gather validity mask and filter to valid pairs
        if valid_mask is not None:
            if dist.is_initialized() and dist.get_world_size() > 1:
                mask_int = valid_mask.int()
                mask_gathered = [torch.zeros_like(mask_int) for _ in range(dist.get_world_size())]
                dist.all_gather(mask_gathered, mask_int)
                valid_all = torch.cat(mask_gathered, dim=0).bool()
            else:
                valid_all = valid_mask
            z_img_all = z_img_all[valid_all]
            z_txt_all = z_txt_all[valid_all]

        if z_img_all.shape[0] < 2:
            return z_img.sum() * 0.0

        z_img_all = F.normalize(z_img_all, dim=-1)
        z_txt_all = F.normalize(z_txt_all, dim=-1)

        # Learnable temperature (clamped for stability)
        scale = self.logit_scale.clamp(max=4.6052).exp()  # max exp ≈ 100

        logits_i2t = scale * (z_img_all @ z_txt_all.T) + self.logit_bias
        logits_t2i = scale * (z_txt_all @ z_img_all.T) + self.logit_bias
        logits_i2t = logits_i2t.clamp(min=-100.0, max=100.0)
        logits_t2i = logits_t2i.clamp(min=-100.0, max=100.0)

        # Diagonal = positive pairs
        N = z_img_all.shape[0]
        labels = torch.eye(N, device=z_img_all.device, dtype=torch.float32)

        loss_i2t = F.binary_cross_entropy_with_logits(logits_i2t, labels, reduction="mean")
        loss_t2i = F.binary_cross_entropy_with_logits(logits_t2i, labels, reduction="mean")
        return 0.5 * (loss_i2t + loss_t2i)


class SIGRegLoss(nn.Module):
    """SIGReg: pushes embedding distribution toward isotropic Gaussian."""

    def __init__(self, dim: int, num_projections: int = 128,
                 num_test_points: int = 64):
        super().__init__()
        self.num_projections = num_projections
        self.num_test_points = num_test_points
        # Cap at 3.0: at t=5.0, exp(-12.5) ~ 3.7e-6 is near float32 precision limits
        self.register_buffer('test_points', torch.linspace(0.1, 3.0, num_test_points))

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        if embeddings.ndim == 3:
            B, N, D = embeddings.shape
            embeddings = embeddings.reshape(-1, D)
        else:
            D = embeddings.shape[-1]

        embeddings = embeddings - embeddings.mean(dim=0, keepdim=True)
        std = embeddings.std(dim=0, keepdim=True).clamp(min=1e-6)
        embeddings = embeddings / std

        proj_dirs = torch.randn(D, self.num_projections, device=embeddings.device)
        proj_dirs = F.normalize(proj_dirs, dim=0)
        projections = embeddings @ proj_dirs

        t = self.test_points.unsqueeze(0).unsqueeze(-1)
        proj_expanded = projections.unsqueeze(1)

        cos_term = torch.cos(t * proj_expanded).mean(dim=0)
        sin_term = torch.sin(t * proj_expanded).mean(dim=0)

        gaussian_cf_real = torch.exp(-0.5 * self.test_points.unsqueeze(-1) ** 2)

        loss_real = (cos_term - gaussian_cf_real).pow(2).mean()
        loss_imag = sin_term.pow(2).mean()
        return loss_real + loss_imag


class LocalContrastiveLoss(nn.Module):
    """Local InfoNCE at Stage 1."""

    def __init__(self, temperature: float = 0.1):
        super().__init__()
        self.temperature = temperature

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        B, K, D = predictions.shape
        pred_norm = F.normalize(predictions, dim=-1)
        tgt_norm = F.normalize(targets.detach(), dim=-1)
        logits = torch.bmm(pred_norm, tgt_norm.transpose(1, 2)) / self.temperature
        labels = torch.arange(K, device=predictions.device).unsqueeze(0).expand(B, -1)
        loss = F.cross_entropy(logits.reshape(-1, K), labels.reshape(-1))
        return loss


class DecoderLoss(nn.Module):
    """L2 loss between decoded features and EMA target features at Stage 1."""

    def __init__(self, dim: int):
        super().__init__()
        self.norm_pred = nn.LayerNorm(dim, elementwise_affine=False)
        self.norm_tgt = nn.LayerNorm(dim, elementwise_affine=False)

    def forward(self, decoded: torch.Tensor, target: torch.Tensor,
                masked_positions: Optional[torch.Tensor] = None) -> torch.Tensor:
        pred_norm = self.norm_pred(decoded)
        tgt_norm = self.norm_tgt(target.detach())
        loss = (pred_norm - tgt_norm).pow(2).mean(dim=-1)

        if masked_positions is not None:
            loss = (loss * masked_positions.float()).sum() / masked_positions.float().sum().clamp(min=1)
        else:
            loss = loss.mean()
        return loss


class CTJEPALoss(nn.Module):
    """Full loss computation with per-component weights and epoch-based scheduling."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        lc = config.loss
        mc = config.model

        self.jepa3_loss = JEPALoss(mc.dim_s3)
        self.jepa2_loss = JEPALoss(mc.dim_s2) if mc.use_detail_predictor else None
        self.align_loss = SigLIPLoss() if config.text.use_text else None
        self.sigreg_loss = SIGRegLoss(mc.dim_s3, lc.sigreg_num_projections, lc.sigreg_num_test_points)
        self.cross_stage_loss = JEPALoss(mc.dim_s3)
        self.decoder_loss = DecoderLoss(mc.dim_s1) if mc.use_decoder_head else None
        self.local_contrast_loss = LocalContrastiveLoss()

        self.lambda_jepa3 = lc.lambda_jepa3
        self.lambda_jepa2 = lc.lambda_jepa2
        self.lambda_align = lc.lambda_align
        self.lambda_sigreg = lc.lambda_sigreg
        self.lambda_cross = lc.lambda_cross_stage
        self.lambda_decoder = lc.lambda_decoder
        self.lambda_local = lc.lambda_local_contrast

    def forward(self, outputs: dict, epoch: int) -> dict:
        lc = self.config.loss
        losses = {}
        total = 0.0

        # 1) Main JEPA at Stage 3
        if 'pred_s3' in outputs and 'target_s3' in outputs:
            l_jepa3 = self.jepa3_loss(outputs['pred_s3'], outputs['target_s3'],
                                       outputs.get('valid_mask_s3'))
            losses['jepa3'] = l_jepa3
            total = total + self.lambda_jepa3 * l_jepa3

        # 2) Detail JEPA at Stage 2
        if self.jepa2_loss is not None and 'pred_s2' in outputs and 'target_s2' in outputs:
            l_jepa2 = self.jepa2_loss(outputs['pred_s2'], outputs['target_s2'],
                                       outputs.get('valid_mask_s2'))
            losses['jepa2'] = l_jepa2
            total = total + self.lambda_jepa2 * l_jepa2

        # 3) Text alignment (after align introduction epoch — delayed to epoch 60
        #    so the predictor has time to learn text conditioning first)
        if (self.align_loss is not None
                and epoch >= lc.align_introduction_epoch
                and 'z_img' in outputs and 'z_txt' in outputs):
            l_align = self.align_loss(outputs['z_img'], outputs['z_txt'],
                                       valid_mask=outputs.get('has_text'))
            losses['align'] = l_align
            total = total + self.lambda_align * l_align

        # 4) SIGReg (always)
        if 's3_embeddings' in outputs:
            l_sigreg = self.sigreg_loss(outputs['s3_embeddings'])
            losses['sigreg'] = l_sigreg
            total = total + self.lambda_sigreg * l_sigreg

        # 5) Cross-stage (always computed for DDP grad sync; weight is 0 before introduction)
        if 'pred_cross' in outputs and 'target_cross' in outputs:
            l_cross = self.cross_stage_loss(outputs['pred_cross'], outputs['target_cross'])
            losses['cross_stage'] = l_cross
            cross_weight = self.lambda_cross if epoch >= lc.cross_stage_introduction_epoch else 0.0
            total = total + cross_weight * l_cross

        # 6) Decoder
        if (self.decoder_loss is not None
                and 'decoded_s1' in outputs and 'target_s1' in outputs):
            l_dec = self.decoder_loss(
                outputs['decoded_s1'], outputs['target_s1'],
                outputs.get('masked_positions_s1'),
            )
            losses['decoder'] = l_dec
            total = total + self.lambda_decoder * l_dec

        # 7) Local contrastive
        if 'local_pred' in outputs and 'local_target' in outputs:
            l_local = self.local_contrast_loss(outputs['local_pred'], outputs['local_target'])
            losses['local_contrast'] = l_local
            total = total + self.lambda_local * l_local

        # DDP dummy: zero-weight term that ensures all params have gradients
        if '_ddp_dummy' in outputs:
            total = total + outputs['_ddp_dummy']

        losses['total'] = total
        return losses
