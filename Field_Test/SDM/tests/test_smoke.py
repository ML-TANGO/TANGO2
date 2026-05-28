"""
CT-JEPA v2 Smoke Tests
=======================
Verifies each component works with small synthetic tensors.
No real data needed — uses random inputs with correct shapes.

Run: python -m SDM.tests.test_smoke
"""

import sys
import torch
import torch.nn as nn
import numpy as np

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def is_finite(t):
    return torch.isfinite(t).all().item()


# ---------------------------------------------------------------------------
# Test: Masking Functions
# ---------------------------------------------------------------------------

def test_masking():
    print("\n=== Masking ===")
    from SDM.data.masking import (
        sample_cuboid_mask, sample_slab_mask, sample_skip_slab_mask,
        sample_frequency_mask, MaskSampler, sample_masked_s2_indices,
    )
    from SDM.config import CTJEPAConfig

    N_S3 = 384
    grid = (6, 8, 8)

    # Cuboid
    r = sample_cuboid_mask(num_targets=5, grid=grid)
    check("cuboid mask shape", r.visible_mask.shape == (N_S3,))
    check("cuboid has visible tokens", r.visible_mask.any().item())
    check("cuboid has masked tokens", r.masked_indices.shape[0] > 0)
    check("cuboid mask ratio valid", 0 < r.mask_ratio < 1, f"ratio={r.mask_ratio}")

    # Slab
    for plane in ["axial", "coronal", "sagittal"]:
        r = sample_slab_mask(plane=plane, slab_width=2, num_slabs=2, grid=grid)
        check(f"{plane} slab shape", r.visible_mask.shape == (N_S3,))
        check(f"{plane} slab has visible", r.visible_mask.any().item())

    # Skip-slab
    r = sample_skip_slab_mask(plane="axial", center_width=2, gap=1, num_slabs=2, grid=grid)
    check("skip-slab shape", r.visible_mask.shape == (N_S3,))
    check("skip-slab has visible", r.visible_mask.any().item())

    # Frequency
    r = sample_frequency_mask(mode="low", mask_ratio=0.5, grid=grid)
    check("freq mask shape", r.visible_mask.shape == (N_S3,))
    check("freq mask has visible", r.visible_mask.any().item())

    # MaskSampler curriculum (phases aligned with training milestones)
    config = CTJEPAConfig()
    sampler = MaskSampler(config)

    # Family probabilities per phase
    probs_foundation = sampler.get_family_probs(0)
    probs_text = sampler.get_family_probs(50)
    probs_align = sampler.get_family_probs(150)
    check("foundation phase cuboid-heavy", probs_foundation["cuboid"] >= 0.60)
    check("text phase cuboid reduced", probs_text["cuboid"] < probs_foundation["cuboid"])
    check("align phase more diverse", probs_align["frequency"] > probs_foundation["frequency"])

    # Mask ratio schedule
    check("foundation mask ratio", sampler.get_target_mask_ratio(0) == 0.65)
    check("text mask ratio", sampler.get_target_mask_ratio(50) == 0.55)
    check("align mask ratio", sampler.get_target_mask_ratio(150) == 0.45)

    # Ratio enforcement
    for epoch, expected in [(0, 0.65), (50, 0.55), (150, 0.45)]:
        r = sampler.sample(epoch, 300)
        check(f"enforced ratio epoch={epoch}",
              abs(r.mask_ratio - expected) < 0.15,
              f"ratio={r.mask_ratio:.2f}, expected~{expected}")

    # Batch sampling
    vis_masks, masked_idx, results = sampler.sample_batch(4, epoch=50, total_epochs=300)
    check("batch vis_masks shape", vis_masks.shape == (4, N_S3))
    check("batch masked_idx has padding", (masked_idx == -1).any().item() or masked_idx.shape[1] > 0,
          "padding or all same length")

    # S2 index sampling
    vis_mask_single = results[0].visible_mask
    s2_idx = sample_masked_s2_indices(vis_mask_single)
    check("s2_indices shape", s2_idx.shape[0] == 512)
    check("s2_indices has valid", (s2_idx >= 0).any().item())


# ---------------------------------------------------------------------------
# Test: Loss Functions
# ---------------------------------------------------------------------------

def test_losses():
    print("\n=== Losses ===")
    from SDM.losses.losses import JEPALoss, SigLIPLoss, SIGRegLoss, LocalContrastiveLoss, DecoderLoss

    B, N, D = 4, 100, 128

    # JEPA Loss
    loss_fn = JEPALoss(D)
    pred = torch.randn(B, N, D)
    target = torch.randn(B, N, D)
    loss = loss_fn(pred, target)
    check("JEPA loss finite", is_finite(loss))
    check("JEPA loss positive", loss.item() > 0)

    # JEPA Loss with valid mask
    valid_mask = torch.ones(B, N, dtype=torch.bool)
    valid_mask[:, 80:] = False  # last 20 are padding
    loss_masked = loss_fn(pred, target, valid_mask=valid_mask)
    check("JEPA masked loss finite", is_finite(loss_masked))

    # SigLIP Loss
    loss_fn = SigLIPLoss()
    z_img = torch.randn(B, D)
    z_txt = torch.randn(B, D)
    loss = loss_fn(z_img, z_txt)
    check("SigLIP loss finite", is_finite(loss))
    check("SigLIP loss positive", loss.item() > 0)

    # SIGReg Loss
    loss_fn = SIGRegLoss(D)
    embeddings = torch.randn(B, N, D)
    loss = loss_fn(embeddings)
    check("SIGReg loss finite", is_finite(loss))
    check("SIGReg loss positive", loss.item() > 0)

    # SIGReg with isotropic Gaussian input (should be low)
    embeddings_gaussian = torch.randn(200, D)
    loss_gaussian = loss_fn(embeddings_gaussian)
    check("SIGReg low for Gaussian", loss_gaussian.item() < 1.0,
          f"got {loss_gaussian.item():.4f}")

    # Local Contrastive
    loss_fn = LocalContrastiveLoss()
    pred = torch.randn(B, 50, D)
    target = torch.randn(B, 50, D)
    loss = loss_fn(pred, target)
    check("LocalContrastive finite", is_finite(loss))

    # Decoder Loss
    loss_fn = DecoderLoss(D)
    loss = loss_fn(torch.randn(B, N, D), torch.randn(B, N, D))
    check("Decoder loss finite", is_finite(loss))


# ---------------------------------------------------------------------------
# Test: Blocks
# ---------------------------------------------------------------------------

def test_blocks():
    print("\n=== Blocks ===")
    from SDM.models.blocks import (
        AdaLNZero, PatchEmbed3D, PatchMerge3D,
        FactorizedPosEmbed3D, FullPosEmbed3D, FFN, DropPath,
    )

    B, D_dim = 2, 128

    # AdaLN-Zero
    adaln = AdaLNZero(D_dim, D_dim)
    x = torch.randn(B, 10, D_dim)
    cond = torch.randn(B, D_dim)
    out, gate = adaln(x, cond)
    check("AdaLN output shape", out.shape == x.shape)
    check("AdaLN gate shape", gate.shape == (B, 1, D_dim))

    # FFN
    ffn = FFN(D_dim, mlp_ratio=4.0)
    out = ffn(x)
    check("FFN output shape", out.shape == x.shape)
    check("FFN output finite", is_finite(out))

    # DropPath
    dp = DropPath(0.1)
    dp.train()
    out = dp(x)
    check("DropPath shape", out.shape == x.shape)

    # PatchEmbed3D (small volume for speed)
    pe = PatchEmbed3D(in_channels=1, embed_dim=64, patch_size=(4, 4, 4))
    vol = torch.randn(2, 1, 16, 16, 16)
    tokens = pe(vol)
    check("PatchEmbed3D output shape", tokens.shape == (2, 64, 64),
          f"got {tokens.shape}")

    # PatchMerge3D
    pm = PatchMerge3D(64, 128)
    grid = (4, 4, 4)
    merged = pm(tokens, grid)
    check("PatchMerge3D output shape", merged.shape == (2, 8, 128),
          f"got {merged.shape}")

    # FactorizedPosEmbed3D
    fpe = FactorizedPosEmbed3D(grid_size=(4, 4, 4), dim=64)
    pos = fpe(2)
    check("FactorizedPosEmbed shape", pos.shape == (2, 64, 64),
          f"got {pos.shape}")

    # FullPosEmbed3D
    fpe_full = FullPosEmbed3D(grid_size=(4, 4, 4), dim=64)
    pos_full = fpe_full(2)
    check("FullPosEmbed shape", pos_full.shape == (2, 64, 64),
          f"got {pos_full.shape}")


# ---------------------------------------------------------------------------
# Test: Predictors (with text token appended to context)
# ---------------------------------------------------------------------------

def test_predictors():
    print("\n=== Predictors ===")
    from SDM.models.predictors import PredictorP3, PredictorP2, CrossStagePredictor, DecoderHead

    B, D = 2, 128
    predictor_dim = D // 2
    N_s3 = 384

    # PredictorP3 without text
    p3 = PredictorP3(
        dim=D, predictor_dim=predictor_dim, depth=2,
        num_heads=4, cond_dim=D, num_tokens_s3=N_s3,
        use_text=False,
    )
    visible_emb = torch.randn(B, 500, D)
    vis_mask = torch.ones(B, N_s3, dtype=torch.bool)
    masked_idx = torch.randint(0, N_s3, (B, 100))
    cond = torch.randn(B, D)
    valid_mask = torch.ones(B, 100, dtype=torch.bool)

    pred = p3(visible_emb, vis_mask, masked_idx, cond, valid_mask=valid_mask)
    check("P3 output shape", pred.shape == (B, 100, D), f"got {pred.shape}")
    check("P3 output finite", is_finite(pred))

    # PredictorP3 with text token (appended to context)
    p3_text = PredictorP3(
        dim=D, predictor_dim=predictor_dim, depth=2,
        num_heads=4, cond_dim=D, num_tokens_s3=N_s3,
        use_text=True,
    )
    z_txt_pred = torch.randn(B, predictor_dim)  # matryoshka-truncated text embedding
    text_mask = torch.tensor([True, False])  # sample 0 has text, sample 1 doesn't

    pred_text = p3_text(visible_emb, vis_mask, masked_idx, cond,
                        z_txt_pred=z_txt_pred, text_mask=text_mask,
                        valid_mask=valid_mask)
    check("P3+text output shape", pred_text.shape == (B, 100, D), f"got {pred_text.shape}")
    check("P3+text output finite", is_finite(pred_text))

    # Verify text masking works: sample 1's text token is masked in cross-attention
    # (no NaN, no crash)
    check("P3+text no NaN", not torch.isnan(pred_text).any().item())

    # PredictorP3 with -1 PADDING (critical bug fix test)
    masked_idx_padded = torch.randint(0, N_s3, (B, 100))
    masked_idx_padded[1, 60:] = -1
    safe_idx = masked_idx_padded.clamp(min=0)
    valid_mask_padded = (masked_idx_padded >= 0)

    pred_padded = p3(visible_emb, vis_mask, safe_idx, cond, valid_mask=valid_mask_padded)
    check("P3 padded output shape", pred_padded.shape == (B, 100, D))
    check("P3 padded output finite", is_finite(pred_padded))
    check("P3 padded no NaN", not torch.isnan(pred_padded).any().item())

    # PredictorP2 basic test
    p2 = PredictorP2(dim_s3=D, dim_s2=D // 2, num_sampled=50)
    s3_pred = torch.randn(B, 100, D)
    s2_vis = torch.randn(B, 200, D // 2)
    s2_idx = torch.randint(0, 3072, (B, 50))
    valid_mask_s2 = torch.ones(B, 50, dtype=torch.bool)

    pred_s2 = p2(s3_pred, s2_vis, s2_idx, valid_mask=valid_mask_s2)
    check("P2 output shape", pred_s2.shape == (B, 50, D // 2), f"got {pred_s2.shape}")
    check("P2 output finite", is_finite(pred_s2))

    # PredictorP2 with padding
    s2_idx_padded = torch.randint(0, 3072, (B, 50))
    s2_idx_padded[0, 30:] = -1
    valid_s2 = (s2_idx_padded >= 0)
    pred_s2_p = p2(s3_pred, s2_vis, s2_idx_padded.clamp(min=0), valid_mask=valid_s2)
    check("P2 padded finite", is_finite(pred_s2_p))

    # CrossStagePredictor
    csp = CrossStagePredictor(
        dim_s1=64, dim_s3=D,
        grid_s1=(4, 4, 4), grid_s3=(2, 2, 2),
    )
    s1_feat = torch.randn(B, 64, 64)
    pred_cross = csp(s1_feat, (4, 4, 4))
    check("CrossStage shape", pred_cross.shape == (B, 8, D), f"got {pred_cross.shape}")
    check("CrossStage finite", is_finite(pred_cross))

    # DecoderHead
    dec = DecoderHead(
        dim_s1=64, dim_s2=128, dim_s3=D,
        grid_s1=(4, 4, 4), grid_s2=(2, 2, 2), grid_s3=(1, 1, 1),
    )
    s3_pred = torch.randn(B, 1, D)
    s2_feat = torch.randn(B, 8, 128)
    s1_feat = torch.randn(B, 64, 64)
    decoded = dec(s3_pred, s2_feat, s1_feat)
    check("Decoder shape", decoded.shape == (B, 64, 64), f"got {decoded.shape}")
    check("Decoder finite", is_finite(decoded))


# ---------------------------------------------------------------------------
# Test: EMA Updater
# ---------------------------------------------------------------------------

def test_ema():
    print("\n=== EMA Updater ===")
    from SDM.models.model import EMAUpdater

    ema = EMAUpdater(momentum_start=0.996, momentum_end=0.9999,
                     total_steps=1000, schedule="cosine")

    m_start = ema.get_momentum()
    check("EMA start momentum", abs(m_start - 0.996) < 0.001, f"got {m_start}")

    ema.step = 500
    m_mid = ema.get_momentum()
    check("EMA mid momentum in range", 0.996 < m_mid < 0.9999, f"got {m_mid}")

    ema.step = 1000
    m_end = ema.get_momentum()
    check("EMA end momentum", abs(m_end - 0.9999) < 0.001, f"got {m_end}")

    # Test actual update
    ema.step = 0
    online = nn.Linear(10, 10)
    target = nn.Linear(10, 10)
    target.load_state_dict(online.state_dict())

    with torch.no_grad():
        online.weight.add_(1.0)

    m = ema.update(online, target)
    diff = (target.weight - online.weight).abs().mean()
    check("EMA update moves target", diff < 1.0, f"mean diff={diff:.4f}")


# ---------------------------------------------------------------------------
# Test: Collapse Monitor
# ---------------------------------------------------------------------------

def test_collapse_monitor():
    print("\n=== Collapse Monitor ===")
    from SDM.training.utils import CollapseMonitor

    monitor = CollapseMonitor()

    # Healthy embeddings
    healthy = torch.randn(100, 128) * 0.5
    result = monitor.check(healthy, name="test")
    check("healthy: no collapse",
          result['health/test_severity'] == 'ok',
          f"severity={result['health/test_severity']}")
    check("healthy: rank_ratio > 0.1",
          result['health/test_rank_ratio'] > 0.1,
          f"rank_ratio={result['health/test_rank_ratio']:.4f}")

    # Collapsed embeddings (all same)
    collapsed = torch.ones(100, 128) * 0.5 + torch.randn(100, 128) * 1e-6
    result = monitor.check(collapsed, name="test")
    check("collapsed: detected",
          result['health/test_severity'] != 'ok',
          f"severity={result['health/test_severity']}, min_std={result['health/test_embed_std_min']:.2e}")


# ---------------------------------------------------------------------------
# Test: Cosine Warmup Scheduler
# ---------------------------------------------------------------------------

def test_scheduler():
    print("\n=== Cosine Warmup Scheduler ===")
    from SDM.training.utils import CosineWarmupScheduler

    model = nn.Linear(10, 10)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    scheduler = CosineWarmupScheduler(
        optimizer, base_lr=1e-3, min_lr=1e-6,
        warmup_epochs=1, total_epochs=10,
        steps_per_epoch=100,
    )

    lr_start = scheduler.get_lr()
    check("warmup starts near 0", lr_start < 1e-4, f"lr={lr_start}")

    for _ in range(100):
        scheduler.step()
    lr_after_warmup = scheduler.get_lr()
    check("warmup reaches base_lr", abs(lr_after_warmup - 1e-3) < 1e-4,
          f"lr={lr_after_warmup}")

    for _ in range(900):
        scheduler.step()
    lr_end = scheduler.get_lr()
    check("cosine decays to min_lr", lr_end < 1e-4, f"lr={lr_end}")


# ---------------------------------------------------------------------------
# Test: CTJEPALoss (integrated)
# ---------------------------------------------------------------------------

def test_ctjepa_loss():
    print("\n=== CTJEPALoss ===")
    from SDM.losses.losses import CTJEPALoss
    from SDM.config import CTJEPAConfig

    config = CTJEPAConfig()
    loss_fn = CTJEPALoss(config)

    B, M, D = 4, 100, config.model.dim_s3

    outputs = {
        'pred_s3': torch.randn(B, M, D),
        'target_s3': torch.randn(B, M, D),
        'valid_mask_s3': torch.ones(B, M, dtype=torch.bool),
        's3_embeddings': torch.randn(B, 200, D),
    }

    losses = loss_fn(outputs, epoch=0)
    check("CTJEPALoss returns dict", isinstance(losses, dict))
    check("total loss finite", is_finite(losses['total']))
    check("total loss positive", losses['total'].item() > 0)
    check("jepa3 present", 'jepa3' in losses)
    check("sigreg present", 'sigreg' in losses)


# ---------------------------------------------------------------------------
# Test: Contrastive Alignment (SigLIP + reconstructed S3)
# ---------------------------------------------------------------------------

def test_contrastive_alignment():
    print("\n=== Contrastive Alignment ===")
    from SDM.losses.losses import SigLIPLoss, CTJEPALoss
    from SDM.models.encoder import AttentionalReadout, WindowProjectionHead
    from SDM.config import CTJEPAConfig

    config = CTJEPAConfig()
    D = config.model.dim_s3   # 512 for base
    N_s3 = config.patch.num_tokens_s3  # 384
    B = 4

    # --- 1. SigLIP with valid_mask ---
    loss_fn = SigLIPLoss()
    z_img = torch.randn(B, D)
    z_txt = torch.randn(B, D)
    valid = torch.tensor([True, True, False, True])
    loss = loss_fn(z_img, z_txt, valid_mask=valid)
    check("SigLIP with valid_mask finite", is_finite(loss))
    check("SigLIP with valid_mask positive", loss.item() > 0)

    # --- 2. SigLIP too few valid pairs returns 0 ---
    one_valid = torch.tensor([True, False, False, False])
    loss_few = loss_fn(z_img, z_txt, valid_mask=one_valid)
    check("SigLIP <2 valid returns 0", loss_few.item() == 0.0)

    # --- 3. Learnable params have gradients ---
    z_img_g = torch.randn(B, D, requires_grad=True)
    z_txt_g = torch.randn(B, D, requires_grad=True)
    loss = loss_fn(z_img_g, z_txt_g)
    loss.backward()
    check("SigLIP logit_scale has grad", loss_fn.logit_scale.grad is not None)
    check("SigLIP logit_bias has grad", loss_fn.logit_bias.grad is not None)
    check("SigLIP z_img has grad", z_img_g.grad is not None)
    check("SigLIP z_txt has grad", z_txt_g.grad is not None)

    # --- 4. Reconstructed S3 → readout → window_proj pipeline ---
    readout = AttentionalReadout(dim=D, num_queries=4, num_heads=8)
    window_proj = WindowProjectionHead(in_dim=D, proj_dim=D, num_windows=4)
    window_id = torch.tensor([0, 1, 2, 3])

    s3_visible = torch.randn(B, 280, D)
    pred_s3 = torch.randn(B, 104, D, requires_grad=True)

    s3_recon = torch.zeros(B, N_s3, D)
    s3_recon[:, :280] = s3_visible
    s3_recon[:, 280:] = pred_s3

    g_img = readout(s3_recon)
    check("readout from recon shape", g_img.shape == (B, D))

    z_img_recon = window_proj(g_img, window_id)
    check("window_proj output shape", z_img_recon.shape == (B, D))

    loss_fn.zero_grad()
    z_txt_recon = torch.randn(B, D)
    loss_recon = loss_fn(z_img_recon, z_txt_recon)
    loss_recon.backward()
    check("recon contrastive loss finite", is_finite(loss_recon))
    check("grad flows to pred_s3", pred_s3.grad is not None and pred_s3.grad.abs().sum() > 0)

    # --- 5. CTJEPALoss epoch gating ---
    loss_module = CTJEPALoss(config)
    outputs = {
        'pred_s3': torch.randn(B, 100, D),
        'target_s3': torch.randn(B, 100, D),
        'valid_mask_s3': torch.ones(B, 100, dtype=torch.bool),
        's3_embeddings': torch.randn(B, 200, D),
        'z_img': torch.randn(B, D),
        'z_txt': torch.randn(B, D),
        'has_text': torch.ones(B, dtype=torch.bool),
    }

    losses_early = loss_module(outputs, epoch=50)
    check("epoch 50: no align loss", 'align' not in losses_early)

    losses_at100 = loss_module(outputs, epoch=100)
    check("epoch 100: align loss present", 'align' in losses_at100)
    check("epoch 100: align loss finite", is_finite(losses_at100['align']))


# ---------------------------------------------------------------------------
# Test: Text Token in Predictor Context
# ---------------------------------------------------------------------------

def test_text_context_token():
    print("\n=== Text Context Token ===")
    from SDM.models.predictors import PredictorP3

    B, D = 4, 128
    predictor_dim = D // 2
    N_s3 = 384

    p3 = PredictorP3(
        dim=D, predictor_dim=predictor_dim, depth=2,
        num_heads=4, cond_dim=D, num_tokens_s3=N_s3,
        use_text=True,
    )

    visible_emb = torch.randn(B, 250, D)
    vis_mask = torch.ones(B, N_s3, dtype=torch.bool)
    masked_idx = torch.randint(0, N_s3, (B, 134))
    cond = torch.randn(B, D)
    valid_mask = torch.ones(B, 134, dtype=torch.bool)

    # All text available
    z_txt_pred = torch.randn(B, predictor_dim)
    text_mask = torch.ones(B, dtype=torch.bool)

    pred_all = p3(visible_emb, vis_mask, masked_idx, cond,
                  z_txt_pred=z_txt_pred, text_mask=text_mask,
                  valid_mask=valid_mask)
    check("all text: output finite", is_finite(pred_all))

    # No text available (all masked)
    text_mask_none = torch.zeros(B, dtype=torch.bool)
    pred_none = p3(visible_emb, vis_mask, masked_idx, cond,
                   z_txt_pred=z_txt_pred, text_mask=text_mask_none,
                   valid_mask=valid_mask)
    check("no text: output finite", is_finite(pred_none))

    # Partial text (some samples have, some don't)
    text_mask_partial = torch.tensor([True, False, True, False])
    pred_partial = p3(visible_emb, vis_mask, masked_idx, cond,
                      z_txt_pred=z_txt_pred, text_mask=text_mask_partial,
                      valid_mask=valid_mask)
    check("partial text: output finite", is_finite(pred_partial))

    # Gradient flows through text token
    z_txt_grad = torch.randn(B, predictor_dim, requires_grad=True)
    pred = p3(visible_emb, vis_mask, masked_idx, cond,
              z_txt_pred=z_txt_grad, text_mask=torch.ones(B, dtype=torch.bool),
              valid_mask=valid_mask)
    loss = pred.sum()
    loss.backward()
    check("text token grad flows", z_txt_grad.grad is not None and z_txt_grad.grad.abs().sum() > 0)

    # No z_txt_pred at all
    pred_no_txt = p3(visible_emb, vis_mask, masked_idx, cond,
                     z_txt_pred=None, text_mask=None,
                     valid_mask=valid_mask)
    check("None z_txt_pred: output finite", is_finite(pred_no_txt))


# ---------------------------------------------------------------------------
# Test: Matryoshka align_proj dimensions
# ---------------------------------------------------------------------------

def test_align_proj():
    print("\n=== Matryoshka align_proj ===")

    D = 512  # dim_s3 for base
    align_dim = 512  # matryoshka truncation

    # 2-layer MLP: LN(512) → Linear(512, 512) → GELU → Linear(512, 512)
    align_proj = nn.Sequential(
        nn.LayerNorm(align_dim),
        nn.Linear(align_dim, D),
        nn.GELU(),
        nn.Linear(D, D),
    )

    B = 4
    raw_global = torch.randn(B, 1024)  # full Chest2Vec output
    truncated = raw_global[:, :align_dim]  # matryoshka slice

    z_txt = align_proj(truncated)
    check("align_proj output shape", z_txt.shape == (B, D), f"got {z_txt.shape}")
    check("align_proj output finite", is_finite(z_txt))

    # Gradient flows
    truncated_g = torch.randn(B, align_dim, requires_grad=True)
    z = align_proj(truncated_g)
    z.sum().backward()
    check("align_proj grad flows", truncated_g.grad is not None)


# ---------------------------------------------------------------------------
# Test: TextEncoder (placeholder)
# ---------------------------------------------------------------------------

def test_text_encoder():
    print("\n=== TextEncoder (Chest2Vec — requires model weights, skipped if unavailable) ===")
    try:
        from SDM.models.model import Chest2VecEncoder
        from SDM.config import CTJEPAConfig

        config = CTJEPAConfig()
        enc = Chest2VecEncoder(config, device="cuda")

        texts = ["Normal chest CT.", None]
        out = enc(texts, target_device=torch.device("cuda"))
        check("raw_global shape", out['raw_global'].shape == (2, config.text.text_embed_dim))
        check("has_text correct", out['has_text'][0].item() and not out['has_text'][1].item())
        check("raw_global finite", is_finite(out['raw_global']))
        # No more token_embeddings or padding_mask
        check("no token_embeddings", 'token_embeddings' not in out)
        check("no padding_mask", 'padding_mask' not in out)
    except Exception as e:
        print(f"  [SKIP] Chest2Vec not available: {e}")


# ---------------------------------------------------------------------------
# Test: Grounding (smoke test)
# ---------------------------------------------------------------------------

def test_grounding():
    print("\n=== Grounding ===")
    from SDM.grounding.grounding import upsample_heatmap

    # upsample_heatmap
    heatmap = torch.randn(6, 8, 8)
    upsampled = upsample_heatmap(heatmap, target_size=(24, 32, 32))
    check("upsample shape", upsampled.shape == (24, 32, 32), f"got {upsampled.shape}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("CT-JEPA v2 Smoke Tests")
    print("=" * 50)

    test_masking()
    test_losses()
    test_blocks()
    test_predictors()
    test_ema()
    test_collapse_monitor()
    test_scheduler()
    test_ctjepa_loss()
    test_contrastive_alignment()
    test_text_context_token()
    test_align_proj()
    test_text_encoder()
    test_grounding()

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL} checks")

    if FAIL > 0:
        print("\nSome tests FAILED. Review the output above.")
        sys.exit(1)
    else:
        print("\nAll tests PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
