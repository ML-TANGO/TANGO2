"""
CT-JEPA v2 Validation & Monitoring
====================================
Comprehensive validation suite for self-supervised pretraining:

1. Feature extraction from target encoder
2. Linear probe evaluation (classification)
3. Image-text retrieval metrics
4. Feature quality metrics (uniformity, alignment, SIGReg on val)
5. Per-window analysis
6. Visualization (t-SNE, attention maps, masking examples)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import os
import math
from typing import Dict, Optional, List, Tuple
from collections import defaultdict


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------

@torch.no_grad()
def extract_features(model, dataloader, device, max_samples: int = 1000,
                     mask_sampler=None, config=None) -> Dict[str, torch.Tensor]:
    """
    Extract target encoder features for a set of samples.

    Returns dict with:
        g_img: (N, D) global image embeddings
        s3_features: (N, N_s3, D) stage-3 token features
        window_ids: (N,) which window was used
        text_ids: (N, T) text token IDs (if available)
        z_txt: (N, D) text embeddings (if text encoder available)
    """
    model.eval()
    all_g_img = []
    all_z_img = []
    all_s3 = []
    all_window_ids = []
    all_z_txt = []
    all_has_text = []
    collected = 0

    has_window_proj = hasattr(model, 'context_encoder') and hasattr(model.context_encoder, 'window_proj')

    for batch in dataloader:
        if collected >= max_samples:
            break

        volume = batch['volume'].to(device)
        window_id = batch['window_id'].to(device)
        region_masks_s2 = batch['region_masks_s2'].to(device) if batch['region_masks_s2'] is not None else None

        # Target encoder (full pass, no masking)
        target_out = model.target_encoder.forward_full(volume, window_id, region_masks_s2)

        all_g_img.append(target_out['g_img'].cpu())
        all_s3.append(target_out['s3_features'].cpu())
        all_window_ids.append(window_id.cpu())

        # Projected image embeddings for retrieval (same space as alignment training)
        if has_window_proj:
            z_img_proj = model.context_encoder.window_proj(target_out['g_img'], window_id)
            all_z_img.append(z_img_proj.cpu())

        # Text embeddings (via Chest2Vec)
        # Track per-sample text availability to maintain alignment with z_img
        texts = batch.get('texts')
        if texts is not None and model.use_text and any(t is not None for t in texts):
            text_out = model.text_encoder(texts, target_device=device)
            if text_out is not None:
                # text_out['raw_global'] is (B, text_dim) with zeros for no-text samples
                # Project through align_proj for retrieval evaluation
                # text_out['has_text'] is (B,) bool
                raw_global = text_out['raw_global']
                z_txt = model.align_proj(raw_global[:, :model.matryoshka_align_dim])
                all_z_txt.append(z_txt.cpu())
                all_has_text.append(text_out['has_text'].cpu())
            else:
                # All samples in this batch lack text
                all_has_text.append(torch.zeros(volume.shape[0], dtype=torch.bool))
        elif has_window_proj and model.use_text:
            # No texts key at all — mark entire batch as no-text
            all_has_text.append(torch.zeros(volume.shape[0], dtype=torch.bool))

        collected += volume.shape[0]

    result = {
        'g_img': torch.cat(all_g_img)[:max_samples],
        's3_features': torch.cat(all_s3)[:max_samples],
        'window_ids': torch.cat(all_window_ids)[:max_samples],
    }
    if all_z_img:
        result['z_img'] = torch.cat(all_z_img)[:max_samples]
    if all_z_txt and all_has_text:
        z_txt_full = torch.cat(all_z_txt)[:max_samples]
        has_text_full = torch.cat(all_has_text)[:max_samples]
        # Filter to only samples with valid text, keeping alignment with z_img
        result['z_txt'] = z_txt_full[has_text_full]
        if all_z_img:
            result['z_img_for_retrieval'] = torch.cat(all_z_img)[:max_samples][has_text_full]

    return result


# ---------------------------------------------------------------------------
# Linear Probe
# ---------------------------------------------------------------------------

class LinearProbe:
    """
    Fast linear probe: trains a single linear layer on frozen features.
    Supports both single-label (cross-entropy) and multi-label (BCE) classification.
    """

    def __init__(self, feature_dim: int, num_classes: int, lr: float = 0.01,
                 epochs: int = 50, device: str = 'cuda',
                 multi_label: bool = False, label_names: Optional[List[str]] = None):
        self.device = device
        self.epochs = epochs
        self.lr = lr
        self.num_classes = num_classes
        self.multi_label = multi_label
        self.label_names = label_names
        self.classifier = nn.Linear(feature_dim, num_classes).to(device)

    @torch.no_grad()
    def extract_labeled_features(self, model, dataset, device,
                                 max_samples: int = 500,
                                 collate_fn=None) -> Tuple[torch.Tensor, torch.Tensor]:
        """Extract features for a labeled dataset. Expects dataset items to have 'label' key."""
        model.eval()
        features = []
        labels = []

        loader = torch.utils.data.DataLoader(
            dataset, batch_size=2, shuffle=False,
            num_workers=2, drop_last=False,
            collate_fn=collate_fn,
        )
        collected = 0
        for batch in loader:
            if collected >= max_samples:
                break
            volume = batch['volume'].to(device)
            window_id = batch['window_id'].to(device)
            region_masks = batch.get('region_masks_s2')
            if region_masks is not None:
                region_masks = region_masks.to(device)

            out = model.target_encoder.forward_full(volume, window_id, region_masks)
            features.append(out['g_img'].cpu())
            labels.append(batch['label'])
            collected += volume.shape[0]

        return torch.cat(features)[:max_samples], torch.cat(labels)[:max_samples]

    def train_and_eval(self, train_features: torch.Tensor, train_labels: torch.Tensor,
                       val_features: torch.Tensor, val_labels: torch.Tensor) -> Dict[str, float]:
        """Train linear probe and evaluate."""
        X_train = F.normalize(train_features, dim=-1).to(self.device)
        y_train = train_labels.to(self.device)
        X_val = F.normalize(val_features, dim=-1).to(self.device)
        y_val = val_labels.to(self.device)

        optimizer = torch.optim.SGD(self.classifier.parameters(), lr=self.lr,
                                     momentum=0.9, weight_decay=1e-4)

        # Train
        self.classifier.train()
        for _ in range(self.epochs):
            logits = self.classifier(X_train)
            if self.multi_label:
                loss = F.binary_cross_entropy_with_logits(logits, y_train.float())
            elif self.num_classes == 1:
                loss = F.binary_cross_entropy_with_logits(logits.squeeze(-1), y_train.float())
            else:
                loss = F.cross_entropy(logits, y_train)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Eval
        self.classifier.eval()
        with torch.no_grad():
            logits = self.classifier(X_val)

            if self.multi_label:
                return self._eval_multi_label(logits, y_val)
            elif self.num_classes == 1:
                probs = torch.sigmoid(logits.squeeze(-1))
                auc = _compute_auc(y_val.cpu().numpy(), probs.cpu().numpy())
                return {'val/linear_probe_auc': auc}
            else:
                preds = logits.argmax(dim=-1)
                acc = (preds == y_val).float().mean().item()
                return {'val/linear_probe_auc': acc}

    def _eval_multi_label(self, logits: torch.Tensor, labels: torch.Tensor) -> Dict[str, float]:
        """Per-class AUC and macro AUC for multi-label classification."""
        probs = torch.sigmoid(logits).cpu().numpy()
        y_true = labels.cpu().numpy()

        per_class_auc = []
        metrics = {}

        for i in range(self.num_classes):
            y_i = y_true[:, i]
            p_i = probs[:, i]

            # Skip classes with no positive or no negative samples
            if y_i.sum() == 0 or y_i.sum() == len(y_i):
                continue

            auc_i = _compute_auc(y_i, p_i)
            per_class_auc.append(auc_i)

            # Log top findings by name
            if self.label_names and i < len(self.label_names):
                name = self.label_names[i][:40]
                metrics[f'val/probe_auc_{name}'] = auc_i

        macro_auc = np.mean(per_class_auc) if per_class_auc else 0.5
        metrics['val/linear_probe_macro_auc'] = macro_auc
        metrics['val/linear_probe_num_evaluated'] = len(per_class_auc)

        return metrics


def _compute_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Simple AUC computation without sklearn dependency."""
    try:
        from sklearn.metrics import roc_auc_score
        return roc_auc_score(y_true, y_score)
    except ImportError:
        # Manual AUC: sort by score, compute area under ROC
        order = np.argsort(-y_score)
        y_sorted = y_true[order]
        npos = y_sorted.sum()
        nneg = len(y_sorted) - npos
        if npos == 0 or nneg == 0:
            return 0.5
        tp = 0.0
        fp = 0.0
        auc = 0.0
        for label in y_sorted:
            if label == 1:
                tp += 1
            else:
                fp += 1
                auc += tp
        return auc / (npos * nneg)


# ---------------------------------------------------------------------------
# Image-Text Retrieval
# ---------------------------------------------------------------------------

@torch.no_grad()
def compute_retrieval_metrics(z_img: torch.Tensor, z_txt: torch.Tensor,
                               ks: List[int] = [1, 5, 10]) -> Dict[str, float]:
    """
    Compute Recall@K for image->text and text->image retrieval.
    Assumes z_img[i] matches z_txt[i].
    """
    z_img = F.normalize(z_img, dim=-1)
    z_txt = F.normalize(z_txt, dim=-1)

    # Similarity matrix
    sims = z_img @ z_txt.T  # (N, N)
    N = sims.shape[0]

    metrics = {}
    for k in ks:
        # Image -> Text
        _, i2t_topk = sims.topk(k, dim=1)
        i2t_correct = (i2t_topk == torch.arange(N).unsqueeze(1)).any(dim=1).float().mean().item()
        metrics[f'val/retrieval_i2t_R@{k}'] = i2t_correct

        # Text -> Image
        _, t2i_topk = sims.T.topk(k, dim=1)
        t2i_correct = (t2i_topk == torch.arange(N).unsqueeze(1)).any(dim=1).float().mean().item()
        metrics[f'val/retrieval_t2i_R@{k}'] = t2i_correct

    return metrics


# ---------------------------------------------------------------------------
# Feature Quality Metrics
# ---------------------------------------------------------------------------

@torch.no_grad()
def compute_feature_quality(embeddings: torch.Tensor) -> Dict[str, float]:
    """
    Compute alignment-uniformity framework metrics and general feature quality.

    Args:
        embeddings: (N, D) feature vectors
    """
    # Center before normalizing to remove DC bias that hides collapse
    embeddings_centered = embeddings - embeddings.mean(dim=0, keepdim=True)
    z = F.normalize(embeddings_centered, dim=-1)
    N = z.shape[0]

    # Uniformity: log of average pairwise Gaussian potential
    # Lower is more uniform (better spread on hypersphere)
    if N > 2000:
        idx = torch.randperm(N)[:2000]
        z_sub = z[idx]
    else:
        z_sub = z

    sq_pdist = torch.cdist(z_sub, z_sub, p=2).pow(2)
    # Mask diagonal
    mask = ~torch.eye(z_sub.shape[0], dtype=torch.bool, device=z_sub.device)
    uniformity = torch.logsumexp(-2.0 * sq_pdist[mask].reshape(-1), dim=0).item() - math.log(mask.sum().item())

    # Mean pairwise cosine similarity (should be low for diverse features)
    cos_sim_matrix = z_sub @ z_sub.T
    cos_sim_matrix.fill_diagonal_(0)
    mean_cosine = cos_sim_matrix.sum().item() / (z_sub.shape[0] * (z_sub.shape[0] - 1))

    # Isotropy: ratio of min to max singular value
    try:
        z_centered = z_sub - z_sub.mean(dim=0, keepdim=True)
        S = torch.linalg.svdvals(z_centered)
        isotropy = (S[-1] / S[0]).item() if S[0] > 0 else 0.0
    except Exception:
        isotropy = 0.0

    # Also report raw (un-centered) mean cosine as a DC bias diagnostic
    z_raw = F.normalize(embeddings, dim=-1)
    if N > 2000:
        z_raw_sub = z_raw[idx]
    else:
        z_raw_sub = z_raw
    raw_cos = z_raw_sub @ z_raw_sub.T
    raw_cos.fill_diagonal_(0)
    mean_cosine_raw = raw_cos.sum().item() / (z_raw_sub.shape[0] * (z_raw_sub.shape[0] - 1))

    return {
        'val/feature_uniformity': uniformity,
        'val/feature_mean_cosine': mean_cosine,
        'val/feature_mean_cosine_raw': mean_cosine_raw,
        'val/feature_isotropy': isotropy,
    }


@torch.no_grad()
def compute_per_window_features(model, dataloader, device,
                                 max_per_window: int = 200) -> Dict[str, torch.Tensor]:
    """Extract features grouped by window ID."""
    model.eval()
    window_features = defaultdict(list)
    window_counts = defaultdict(int)

    for batch in dataloader:
        volume = batch['volume'].to(device)
        window_id = batch['window_id'].to(device)
        region_masks = batch.get('region_masks_s2')
        if region_masks is not None:
            region_masks = region_masks.to(device)

        out = model.target_encoder.forward_full(volume, window_id, region_masks)

        for i in range(volume.shape[0]):
            wid = window_id[i].item()
            if window_counts[wid] < max_per_window:
                window_features[wid].append(out['g_img'][i].cpu())
                window_counts[wid] += 1

        if all(c >= max_per_window for c in window_counts.values()) and len(window_counts) >= 3:
            break

    return {wid: torch.stack(feats) for wid, feats in window_features.items()}


@torch.no_grad()
def compute_sigreg_on_val(model, val_loader, device, config, max_batches: int = 20) -> float:
    """Compute SIGReg loss on validation set — the best proxy for model selection."""
    from .losses import SIGRegLoss
    sigreg = SIGRegLoss(
        dim=config.model.dim_s3,
        num_projections=config.loss.sigreg_num_projections,
        num_test_points=config.loss.sigreg_num_test_points,
    ).to(device)

    model.eval()
    losses = []
    for i, batch in enumerate(val_loader):
        if i >= max_batches:
            break
        volume = batch['volume'].to(device)
        window_id = batch['window_id'].to(device)
        region_masks = batch.get('region_masks_s2')
        if region_masks is not None:
            region_masks = region_masks.to(device)

        out = model.target_encoder.forward_full(volume, window_id, region_masks)
        loss = sigreg(out['s3_features'])
        losses.append(loss.item())

    return np.mean(losses) if losses else 0.0


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def compute_tsne_embeddings(features: torch.Tensor, labels: Optional[torch.Tensor] = None,
                            perplexity: float = 30.0, n_iter: int = 1000) -> Optional[np.ndarray]:
    """Compute 2D t-SNE embedding. Returns (N, 2) numpy array or None if sklearn unavailable."""
    try:
        from sklearn.manifold import TSNE
        feats_np = features.cpu().numpy()
        tsne = TSNE(n_components=2, perplexity=min(perplexity, feats_np.shape[0] - 1),
                     max_iter=n_iter, random_state=42)
        return tsne.fit_transform(feats_np)
    except ImportError:
        print("  sklearn not available, skipping t-SNE")
        return None


def save_tsne_plot(coords_2d: np.ndarray, labels: np.ndarray, save_path: str,
                   title: str = "t-SNE", label_names: Optional[dict] = None):
    """Save a t-SNE scatter plot as PNG."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        unique_labels = np.unique(labels)

        for lbl in unique_labels:
            mask = labels == lbl
            name = label_names.get(lbl, str(lbl)) if label_names else str(lbl)
            ax.scatter(coords_2d[mask, 0], coords_2d[mask, 1], s=8, alpha=0.6, label=name)

        ax.set_title(title)
        ax.legend(markerscale=3, fontsize=8, loc='best')
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return save_path
    except ImportError:
        print("  matplotlib not available, skipping plot")
        return None


def visualize_mask_example(visible_mask_s3: torch.Tensor, grid_s3: Tuple[int, int, int],
                           save_path: str, family: str = "", mask_ratio: float = 0.0):
    """Save a 2D slice visualization of a masking pattern."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        D, H, W = grid_s3
        mask_3d = visible_mask_s3.reshape(D, H, W).float().cpu().numpy()

        # Show 3 axial slices
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        slice_indices = [D // 4, D // 2, 3 * D // 4]
        for ax, si in zip(axes, slice_indices):
            ax.imshow(mask_3d[si], cmap='RdYlGn', vmin=0, vmax=1, interpolation='nearest')
            ax.set_title(f'Slice {si}')
            ax.axis('off')

        fig.suptitle(f'Mask: {family} | Ratio: {mask_ratio:.2f} (green=visible)', fontsize=12)
        fig.tight_layout()
        fig.savefig(save_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        return save_path
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Full Validation Runner
# ---------------------------------------------------------------------------

@torch.no_grad()
def run_validation(model, val_loader, config, device, epoch: int, global_step: int,
                   logger, output_dir: str,
                   mask_sampler=None,
                   labeled_dataset=None) -> Dict[str, float]:
    """
    Run the full validation suite. Called every config.validation.eval_interval epochs.

    Returns all validation metrics as a flat dict.
    """
    vc = config.validation
    metrics = {}
    model.eval()

    print(f"\n  Running validation at epoch {epoch}...")

    # ---- 1. Feature extraction ----
    feats = extract_features(model, val_loader, device, max_samples=vc.num_retrieval_samples)

    # ---- 2. Feature quality ----
    quality = compute_feature_quality(feats['g_img'])
    metrics.update(quality)

    # ---- 3. SIGReg on validation (THE proxy metric) ----
    sigreg_val = compute_sigreg_on_val(model, val_loader, device, config)
    metrics['val/sigreg_loss_on_val'] = sigreg_val

    # ---- 4. Retrieval metrics (if text available) ----
    if 'z_txt' in feats and feats['z_txt'].shape[0] > 10:
        # Use pre-aligned image/text pairs (filtered to samples with text)
        img_feats = feats.get('z_img_for_retrieval', feats['z_txt'])  # fallback shouldn't happen
        if img_feats.shape[0] != feats['z_txt'].shape[0]:
            # Shouldn't happen after fix, but guard anyway
            n = min(img_feats.shape[0], feats['z_txt'].shape[0])
            img_feats = img_feats[:n]
            feats['z_txt'] = feats['z_txt'][:n]
        retrieval = compute_retrieval_metrics(img_feats, feats['z_txt'])
        metrics.update(retrieval)

    # ---- 6. Linear probe (if labeled data available) ----
    if labeled_dataset is not None and epoch % vc.linear_probe_interval == 0:
        try:
            from .data import probe_collate_fn
            num_classes = getattr(labeled_dataset, 'num_classes', 1)
            label_names = getattr(labeled_dataset, 'label_columns', None)
            is_multi_label = num_classes > 1 and hasattr(labeled_dataset, 'label_columns')

            probe = LinearProbe(
                feature_dim=config.model.dim_s3,
                num_classes=num_classes,
                epochs=vc.probe_epochs,
                device=str(device),
                multi_label=is_multi_label,
                label_names=label_names,
            )
            # Split labeled data 70/30
            n = len(labeled_dataset)
            n_train = int(0.7 * n)
            train_ds = torch.utils.data.Subset(labeled_dataset, range(n_train))
            val_ds = torch.utils.data.Subset(labeled_dataset, range(n_train, n))

            max_samples = vc.probe_num_samples
            train_feats, train_labels = probe.extract_labeled_features(
                model, train_ds, device, max_samples=max_samples,
                collate_fn=probe_collate_fn,
            )
            val_feats, val_labels = probe.extract_labeled_features(
                model, val_ds, device, max_samples=max_samples // 2,
                collate_fn=probe_collate_fn,
            )
            probe_metrics = probe.train_and_eval(train_feats, train_labels, val_feats, val_labels)
            metrics.update(probe_metrics)

            if is_multi_label:
                macro = probe_metrics.get('val/linear_probe_macro_auc', 0)
                n_eval = probe_metrics.get('val/linear_probe_num_evaluated', 0)
                print(f"    Linear probe: macro AUC = {macro:.4f} ({n_eval}/{num_classes} classes)")
        except Exception as e:
            print(f"  Linear probe failed: {e}")
            import traceback
            traceback.print_exc()

    # ---- 7. Visualizations ----
    vis_dir = os.path.join(output_dir, 'visualizations')
    os.makedirs(vis_dir, exist_ok=True)

    if epoch % vc.visualization_interval == 0:
        # t-SNE of S3 features colored by window ID
        tsne_data = feats['g_img'][:vc.num_tsne_samples]
        tsne_labels = feats['window_ids'][:vc.num_tsne_samples].numpy()
        coords = compute_tsne_embeddings(tsne_data)
        if coords is not None:
            path = save_tsne_plot(
                coords, tsne_labels,
                save_path=os.path.join(vis_dir, f'tsne_windows_epoch{epoch:04d}.png'),
                title=f'S3 Embeddings by Window (Epoch {epoch})',
                label_names={0: 'mediastinal', 1: 'lung', 2: 'all-range'},
            )
            if path:
                logger.log_image('viz/tsne_by_window', path, global_step,
                                 caption=f'Epoch {epoch}')

        # Masking example
        if mask_sampler is not None:
            visible_masks, _, mask_results = mask_sampler.sample_batch(
                batch_size=4, epoch=epoch, total_epochs=config.training.total_epochs)
            for i in range(min(4, len(mask_results))):
                mask_path = visualize_mask_example(
                    visible_masks[i], config.patch.grid_size_s3,
                    save_path=os.path.join(vis_dir, f'mask_epoch{epoch:04d}_sample{i}.png'),
                    family=mask_results[i].family,
                    mask_ratio=mask_results[i].mask_ratio,
                )
                if mask_path and i == 0:
                    logger.log_image('viz/mask_example', mask_path, global_step,
                                     caption=f'{mask_results[i].family} ratio={mask_results[i].mask_ratio:.2f}')

    # ---- Log all metrics ----
    logger.log(metrics, global_step, epoch)

    # Print summary
    print(f"  Validation results (epoch {epoch}):")
    print(f"    SIGReg (val): {metrics.get('val/sigreg_loss_on_val', 0):.6f}")
    print(f"    Feature uniformity: {metrics.get('val/feature_uniformity', 0):.4f}")
    print(f"    Feature isotropy: {metrics.get('val/feature_isotropy', 0):.4f}")
    if 'val/retrieval_i2t_R@1' in metrics:
        print(f"    Retrieval I2T R@1: {metrics['val/retrieval_i2t_R@1']:.4f}")
        print(f"    Retrieval I2T R@5: {metrics.get('val/retrieval_i2t_R@5', 0):.4f}")
    if 'val/linear_probe_macro_auc' in metrics:
        print(f"    Linear probe macro AUC: {metrics['val/linear_probe_macro_auc']:.4f}")
    elif 'val/linear_probe_auc' in metrics:
        print(f"    Linear probe AUC: {metrics['val/linear_probe_auc']:.4f}")

    return metrics


# ---------------------------------------------------------------------------
# Phase Transition Evaluation
# ---------------------------------------------------------------------------

@torch.no_grad()
def run_phase_evaluation(model, val_loader, config, device, epoch: int,
                         global_step: int, logger, ckpt_manager,
                         mask_sampler) -> Dict[str, float]:
    """
    Comprehensive evaluation at phase transition points.
    Saves a permanent checkpoint and runs full validation.
    """
    progress = epoch / config.training.total_epochs
    if progress < 0.3:
        phase_name = "phase1_foundation"
    elif progress < 0.65:
        phase_name = "phase2_expansion"
    else:
        phase_name = "phase3_refinement"

    print(f"\n{'='*60}")
    print(f"  PHASE TRANSITION: {phase_name} at epoch {epoch}")
    print(f"{'='*60}")

    # Save permanent checkpoint
    ckpt_path = ckpt_manager.save_phase(model, epoch, global_step, phase_name)
    print(f"  Phase checkpoint saved: {ckpt_path}")

    # Verify curriculum
    if mask_sampler is not None:
        family_counts = defaultdict(int)
        for _ in range(100):
            _, _, results = mask_sampler.sample_batch(
                batch_size=1, epoch=epoch, total_epochs=config.training.total_epochs)
            family_counts[results[0].family] += 1

        metrics = {}
        for family, count in family_counts.items():
            metrics[f'phase/mask_distribution_{family}'] = count / 100.0

        logger.log(metrics, global_step, epoch)

        print(f"  Mask family distribution at epoch {epoch}:")
        for family, count in sorted(family_counts.items()):
            print(f"    {family}: {count}%")

    # Run full validation
    val_metrics = run_validation(
        model, val_loader, config, device, epoch, global_step, logger,
        output_dir=os.path.dirname(ckpt_path),
        mask_sampler=mask_sampler,
    )

    val_metrics['phase/checkpoint_path'] = ckpt_path
    val_metrics['phase/name'] = phase_name

    return val_metrics
