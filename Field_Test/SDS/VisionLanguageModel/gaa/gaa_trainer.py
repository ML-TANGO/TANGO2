"""
GAATrainer — HF Trainer with Geometric Attention Alignment

Adds L_geo (background-suppression loss) to the standard SFT loss:

    L_total = L_SFT + λ · L_geo   (Eq. 6)

L_geo is computed from the last-layer CLIP ViT CLS-token attention maps
using ground-truth bounding boxes as privileged information (training only).

The CLIP encoder is called a second time with output_attentions=True so that
gradients from L_geo flow back through the vision encoder.  This requires
the vision encoder to be unfrozen (freeze_vision=False in VLMConfig), which
train_gaa.py enforces automatically.
"""
import torch

from .geometric_loss import compute_geometric_loss
from train import VLMTrainer, _is_main_process


def _get_clip_attentions(vision_encoder, pixel_values: torch.Tensor) -> torch.Tensor:
    """
    Forward the CLIP vision encoder with attention output enabled.

    Returns the last-layer attention map: (B, num_heads, N+1, N+1)
    where index 0 in the sequence dimension is the CLS token.
    """
    from model.config import VISION_CLIP
    if vision_encoder.encoder_type != VISION_CLIP:
        raise RuntimeError(
            "GAA requires a CLIP-based vision encoder (needs CLS-token attention). "
            f"Got encoder type: {vision_encoder.encoder_type}"
        )
    pixel_values = pixel_values.to(dtype=vision_encoder.dtype)
    outputs = vision_encoder.model(
        pixel_values=pixel_values,
        output_attentions=True,
    )
    return outputs.attentions[-1]  # (B, H, N+1, N+1)


class GAATrainer(VLMTrainer):
    """
    VLMTrainer subclass that adds the GAA geometric attention loss.

    Additional constructor arguments (all keyword-only):
        geo_loss_weight : λ in Eq. 6  (paper optimal = 0.5)
        geo_tau         : IoU threshold τ for mask generation (paper default = 0.5)
        feature_size    : ViT patch grid side length
                          (24 for CLIP-ViT-L/14-336, 27 for SigLIP-384)
    """

    def __init__(
        self,
        *args,
        geo_loss_weight: float = 0.5,
        geo_tau: float = 0.5,
        feature_size: int = 24,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.geo_loss_weight = geo_loss_weight
        self.geo_tau = geo_tau
        self.feature_size = feature_size

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # Remove bboxes before model.forward() — the base model doesn't accept them
        bboxes = inputs.pop("bboxes", None)

        # --- Standard supervised fine-tuning loss ---
        outputs = model(**inputs)
        sft_loss = outputs.loss

        # --- Geometric attention loss (training phase, bboxes present) ---
        use_geo = (
            self.geo_loss_weight > 0
            and bboxes
            and any(b for b in bboxes)   # at least one sample has boxes
            and model.training
        )

        if use_geo:
            # Second CLIP forward pass — gradients flow back through vision encoder
            attentions = _get_clip_attentions(model.vision_encoder, inputs["pixel_values"])
            geo_loss = compute_geometric_loss(
                attentions, bboxes, self.feature_size, self.geo_tau
            )
            total_loss = sft_loss + self.geo_loss_weight * geo_loss

            if self.state.global_step % self.args.logging_steps == 0 and _is_main_process():
                self.log({
                    "loss/sft":   sft_loss.detach().item(),
                    "loss/geo":   geo_loss.detach().item(),
                    "loss/total": total_loss.detach().item(),
                })
        else:
            total_loss = sft_loss

        return (total_loss, outputs) if return_outputs else total_loss
