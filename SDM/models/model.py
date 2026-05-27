"""
CT-JEPA v2: Full Model Wrapper
================================
Combines context encoder, EMA target encoder, all predictors,
text conditioning, and produces all outputs needed for the loss.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from copy import deepcopy
from typing import Optional, Dict
import math

from typing import List

from .encoder import HierarchicalEncoder
from .predictors import PredictorP3, PredictorP2, CrossStagePredictor, DecoderHead
from ..chest2vec.chest2vec import (
    Chest2Vec, encode_with_eos_ids, get_last_hidden_state,
    last_token_pool, build_qwen_query,
)


class EMAUpdater:
    """Exponential Moving Average updater for target encoder."""

    def __init__(self, momentum_start: float = 0.996, momentum_end: float = 0.9999,
                 total_steps: int = 100000, schedule: str = "cosine"):
        self.momentum_start = momentum_start
        self.momentum_end = momentum_end
        self.total_steps = total_steps
        self.schedule = schedule
        self.step = 0

    def get_momentum(self) -> float:
        if self.schedule == "cosine":
            progress = min(self.step / max(self.total_steps, 1), 1.0)
            return self.momentum_end - (self.momentum_end - self.momentum_start) * (
                1 + math.cos(math.pi * progress)) / 2
        else:
            progress = min(self.step / max(self.total_steps, 1), 1.0)
            return self.momentum_start + (self.momentum_end - self.momentum_start) * progress

    @torch.no_grad()
    def update(self, online: nn.Module, target: nn.Module):
        m = self.get_momentum()
        for p_online, p_target in zip(online.parameters(), target.parameters()):
            p_target.data.mul_(m).add_(p_online.data, alpha=1.0 - m)
        self.step += 1
        return m


class Chest2VecEncoder(nn.Module):
    """Frozen Chest2Vec (Qwen3-Embedding + LoRA) text encoder for CT-JEPA.

    Pure frozen feature extractor — zero trainable parameters.
    Returns only the global (EOS-pooled) embedding; callers handle
    matryoshka truncation and projection.
    """

    def __init__(self, config, device: str = "cuda"):
        super().__init__()
        self.config = config
        self.max_tokens = config.text.text_max_tokens
        self.instruction = config.text.chest2vec_instruction

        # Load Chest2Vec model
        self._wrapper = Chest2Vec.from_pretrained(
            config.text.text_encoder_name,
            device=device,
            force_flash_attention_2=True,
        )
        self.tokenizer = self._wrapper.tokenizer
        self.qwen_model = self._wrapper.model
        self.text_device = self._wrapper.device

        # Probe actual hidden dim
        with torch.no_grad():
            probe = encode_with_eos_ids(self.tokenizer, ["test"], max_len=8)
            h = get_last_hidden_state(
                self.qwen_model,
                probe["input_ids"].to(self.text_device),
                probe["attention_mask"].to(self.text_device),
            )
            self.text_dim = h.shape[-1]

        # Update config if probed dim differs
        config.text.text_embed_dim = self.text_dim

        # Freeze Chest2Vec entirely
        self.qwen_model.eval()
        for p in self.qwen_model.parameters():
            p.requires_grad = False

    def forward(self, texts: List[Optional[str]],
                target_device: torch.device,
                ) -> Optional[Dict[str, torch.Tensor]]:
        """Encode raw text strings with frozen Chest2Vec.

        Args:
            texts: List of text strings (None entries = no text for that sample).
            target_device: Device for output tensors (e.g. cuda:0).

        Returns dict with:
            raw_global: [B, text_dim] L2-normalized global embedding
            has_text: [B] bool mask of which samples had text
        """
        B = len(texts)
        valid_indices = [i for i, t in enumerate(texts) if t is not None]

        if not valid_indices:
            return None

        valid_texts = [texts[i] for i in valid_indices]

        # Format as instruction-query pairs for Chest2Vec
        q_texts = [build_qwen_query(self.instruction, str(t)) for t in valid_texts]

        # Tokenize
        enc = encode_with_eos_ids(self.tokenizer, q_texts, self.max_tokens)
        input_ids = enc["input_ids"].to(self.text_device, non_blocking=True)
        attention_mask = enc["attention_mask"].to(self.text_device, non_blocking=True)

        # Frozen forward pass — global (EOS) embedding only
        with torch.no_grad():
            with torch.autocast(
                device_type="cuda", dtype=torch.bfloat16,
                enabled=self.text_device.type == "cuda",
            ):
                hidden_states = get_last_hidden_state(
                    self.qwen_model, input_ids, attention_mask
                )
                global_emb = last_token_pool(hidden_states, attention_mask)
                global_emb = F.normalize(global_emb.float(), p=2, dim=-1)

        global_emb = global_emb.to(target_device)

        # Expand to full batch size if only a subset has text
        if len(valid_indices) < B:
            full_global = torch.zeros(B, self.text_dim, device=target_device)
            has_text = torch.zeros(B, dtype=torch.bool, device=target_device)
            for j, idx in enumerate(valid_indices):
                full_global[idx] = global_emb[j]
                has_text[idx] = True
            global_emb = full_global
        else:
            has_text = torch.ones(B, dtype=torch.bool, device=target_device)

        return {
            'raw_global': global_emb,          # (B, text_dim)
            'has_text': has_text,
        }


class CTJEPA(nn.Module):
    """
    Full CT-JEPA v2 model.

    Forward pass:
    1. Target encoder (EMA): process full volume (no masking)
    2. Context encoder: process with masking (visible tokens only at S3)
    3. Text encoding (optional)
    4. Predictor P3: predict masked S3 embeddings
    5. Predictor P2: predict sparse S2 embeddings (optional)
    6. Cross-stage predictor (optional, phased)
    7. Decoder head (optional)
    8. Text alignment (optional, phased)
    9. Collect all outputs for loss computation
    """

    def __init__(self, config):
        super().__init__()
        self.config = config
        mc = config.model
        pc = config.patch

        # Context encoder (trainable)
        self.context_encoder = HierarchicalEncoder(config)

        # Target encoder (EMA copy — frozen)
        self.target_encoder = deepcopy(self.context_encoder)
        for p in self.target_encoder.parameters():
            p.requires_grad = False

        # EMA updater
        self.ema = EMAUpdater(
            momentum_start=config.ema.momentum_start,
            momentum_end=config.ema.momentum_end,
            schedule=config.ema.momentum_schedule,
        )

        # Text encoder (Chest2Vec, frozen) — init before predictor to probe text_dim
        self.use_text = config.text.use_text
        self.text_introduction_epoch = config.text.text_introduction_epoch
        self.text_dropout_rate = config.text.text_dropout_rate
        self.matryoshka_align_dim = config.text.matryoshka_align_dim
        self.matryoshka_pred_dim = config.text.matryoshka_pred_dim
        if self.use_text:
            self.text_encoder = Chest2VecEncoder(config, device="cuda")

            # Contrastive alignment projection: 2-layer MLP on matryoshka-truncated input
            # Only receives SigLIP gradients — completely separate from predictor path
            align_dim = config.text.matryoshka_align_dim  # 512
            self.align_proj = nn.Sequential(
                nn.LayerNorm(align_dim),
                nn.Linear(align_dim, mc.dim_s3),
                nn.GELU(),
                nn.Linear(mc.dim_s3, mc.dim_s3),
            )

        # Main predictor P3
        predictor_dim = mc.dim_s3 // 2
        self.predictor_p3 = PredictorP3(
            dim=mc.dim_s3,
            predictor_dim=predictor_dim,
            depth=mc.predictor_depth,
            num_heads=mc.predictor_num_heads,
            cond_dim=mc.dim_s3,
            num_tokens_s3=pc.num_tokens_s3,
            use_text=config.text.use_text,
        )

        # Detail predictor P2 (optional)
        self.use_p2 = mc.use_detail_predictor
        if self.use_p2:
            self.predictor_p2 = PredictorP2(
                dim_s3=mc.dim_s3,
                dim_s2=mc.dim_s2,
                num_sampled=mc.detail_num_sampled,
            )

        # Cross-stage predictor
        self.cross_stage_predictor = CrossStagePredictor(
            dim_s1=mc.dim_s1, dim_s3=mc.dim_s3,
            grid_s1=pc.grid_size_s1, grid_s3=pc.grid_size_s3,
        )

        # Decoder head (optional)
        self.use_decoder = mc.use_decoder_head
        if self.use_decoder:
            self.decoder_head = DecoderHead(
                dim_s1=mc.dim_s1, dim_s2=mc.dim_s2, dim_s3=mc.dim_s3,
                grid_s1=pc.grid_size_s1, grid_s2=pc.grid_size_s2, grid_s3=pc.grid_size_s3,
            )

    @torch.no_grad()
    def update_target_encoder(self):
        """Update EMA target encoder. Call after each optimizer step."""
        return self.ema.update(self.context_encoder, self.target_encoder)

    def forward(self, volume: torch.Tensor, window_id: torch.Tensor,
                visible_mask_s3: torch.Tensor,
                masked_indices_s3: torch.Tensor,
                region_masks_s2: Optional[torch.Tensor] = None,
                texts: Optional[List[Optional[str]]] = None,
                masked_s2_indices: Optional[torch.Tensor] = None,
                epoch: int = 0,
                ) -> Dict[str, torch.Tensor]:
        B = volume.shape[0]
        pc = self.config.patch
        device = volume.device
        outputs = {}

        # 1. Target encoder (full pass, no masking, no gradients)
        with torch.no_grad():
            target_out = self.target_encoder.forward_full(
                volume, window_id, region_masks_s2
            )
            target_s3_all = target_out['s3_features']

        # 2. Context encoder (masked pass)
        context_out = self.context_encoder.forward_masked(
            volume, window_id, visible_mask_s3, region_masks_s2
        )

        # 3. Text encoding + dropout
        # Matryoshka truncation: [:512] for SigLIP, [:256] for predictor context token
        z_txt_pred = None  # (B, predictor_dim) for predictor context token
        text_available = torch.zeros(B, dtype=torch.bool, device=device)

        if self.use_text and texts is not None and any(t is not None for t in texts):
            text_out = self.text_encoder(texts, target_device=device)
            if text_out is not None:
                raw_global = text_out['raw_global']  # (B, text_dim=1024)
                has_text = text_out['has_text']       # (B,) bool

                # Determine which samples have text available
                text_available = has_text.clone()
                if epoch < self.text_introduction_epoch:
                    text_available[:] = False
                elif self.training:
                    drop = torch.rand(B, device=device) < self.text_dropout_rate
                    text_available = text_available & ~drop

                # Zero out raw_global for dropped/unavailable samples
                raw_global_masked = raw_global.clone()
                raw_global_masked[~text_available] = 0

                # For SigLIP: matryoshka truncate to 512, project through align_proj
                if text_available.any():
                    z_txt = self.align_proj(raw_global_masked[:, :self.matryoshka_align_dim])
                    outputs['z_txt'] = z_txt
                    outputs['has_text'] = text_available

                # For predictor: matryoshka truncate to predictor_dim (256)
                z_txt_pred = raw_global_masked[:, :self.matryoshka_pred_dim]  # (B, 256)

        # 4. Window conditioning vector
        cond = self.context_encoder.window_cond(window_id=window_id)

        # 5. Main Predictor P3
        valid_mask_s3 = (masked_indices_s3 >= 0)
        safe_indices = masked_indices_s3.clamp(min=0)

        pred_s3 = self.predictor_p3(
            visible_embeddings=context_out['s3_visible'],
            visible_mask=visible_mask_s3,
            masked_indices=safe_indices,
            cond=cond,
            z_txt_pred=z_txt_pred,
            text_mask=text_available,
            region_tokens=context_out.get('region_tokens'),
            valid_mask=valid_mask_s3,
        )

        target_s3 = torch.zeros_like(pred_s3)
        for b in range(B):
            valid_idx = safe_indices[b][valid_mask_s3[b]]
            target_s3[b, :valid_idx.shape[0]] = target_s3_all[b, valid_idx]

        outputs['pred_s3'] = pred_s3
        outputs['target_s3'] = target_s3
        outputs['valid_mask_s3'] = valid_mask_s3

        # For SIGReg: only include valid (non-padded) S3 tokens
        s3_vis = context_out['s3_visible']
        s3_pad_mask = context_out.get('s3_vis_padding_mask')
        if s3_pad_mask is not None:
            valid_tokens = s3_vis[~s3_pad_mask]
            outputs['s3_embeddings'] = valid_tokens
        else:
            outputs['s3_embeddings'] = s3_vis

        # 6. Detail Predictor P2 (optional)
        if self.use_p2 and masked_s2_indices is not None:
            with torch.no_grad():
                target_s2_all = target_out['s2_features']

            valid_mask_s2 = (masked_s2_indices >= 0)
            pred_s2 = self.predictor_p2(
                s3_predictions=pred_s3,
                s2_visible=context_out['s2_features'],
                masked_s2_indices=masked_s2_indices.clamp(min=0),
                valid_mask=valid_mask_s2,
            )

            target_s2 = torch.zeros_like(pred_s2)
            for b in range(B):
                valid_idx = masked_s2_indices[b][valid_mask_s2[b]].clamp(min=0)
                target_s2[b, :valid_idx.shape[0]] = target_s2_all[b, valid_idx]

            outputs['pred_s2'] = pred_s2
            outputs['target_s2'] = target_s2
            outputs['valid_mask_s2'] = valid_mask_s2

        # 7. Cross-stage predictor (always run so DDP sees all params used)
        pred_cross = self.cross_stage_predictor(
            context_out['s1_features'], pc.grid_size_s1
        )
        with torch.no_grad():
            target_cross = target_s3_all

        outputs['pred_cross'] = pred_cross
        outputs['target_cross'] = target_cross

        # 8. Decoder head (optional)
        if self.use_decoder:
            s3_full = target_s3_all.clone()
            for b in range(B):
                valid_idx = safe_indices[b][valid_mask_s3[b]]
                s3_full[b, valid_idx] = pred_s3[b, :valid_idx.shape[0]].to(s3_full.dtype)

            decoded_s1 = self.decoder_head(
                s3_pred=s3_full,
                s2_features=context_out['s2_features'],
                s1_features=context_out['s1_features'],
            )

            with torch.no_grad():
                target_s1 = target_out['s1_features']

            outputs['decoded_s1'] = decoded_s1
            outputs['target_s1'] = target_s1

        # 9. Text alignment: build z_img from reconstructed S3 (visible + predicted)
        if self.use_text and 'z_txt' in outputs:
            s3_recon = torch.zeros(B, pc.num_tokens_s3, self.config.model.dim_s3,
                                   device=device, dtype=pred_s3.dtype)
            for b in range(B):
                vis_idx = visible_mask_s3[b].nonzero(as_tuple=True)[0]
                n_vis = vis_idx.shape[0]
                s3_recon[b, vis_idx] = context_out['s3_visible'][b, :n_vis]
            for b in range(B):
                valid_idx = safe_indices[b][valid_mask_s3[b]]
                s3_recon[b, valid_idx] = pred_s3[b, :valid_idx.shape[0]]
            g_img_full = self.context_encoder.readout(s3_recon)
            z_img = self.context_encoder.window_proj(g_img_full, window_id)
            outputs['z_img'] = z_img

        # 10. DDP dummy
        if self.training:
            outputs['_ddp_dummy'] = sum(
                p.reshape(-1)[0] * 0.0
                for p in self.parameters() if p.requires_grad
            )

        # 11. Monitoring outputs
        outputs['g_img'] = context_out['g_img']

        return outputs

    def get_param_groups(self, base_lr: float, weight_decay: float) -> list:
        """Get parameter groups with no decay for biases, norms, embeddings."""
        no_decay = {'bias', 'norm', 'pos_embed', 'region_embeds', 'queries', 'mask_pos_embed'}

        params_decay = []
        params_no_decay = []

        for name, param in self.named_parameters():
            if not param.requires_grad:
                continue
            if any(nd in name for nd in no_decay):
                params_no_decay.append(param)
            else:
                params_decay.append(param)

        return [
            {'params': params_decay, 'lr': base_lr, 'weight_decay': weight_decay},
            {'params': params_no_decay, 'lr': base_lr, 'weight_decay': 0.0},
        ]
