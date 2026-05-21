"""
CT-JEPA v2 Grounding Evaluation
==================================
Evaluate phrase grounding on ReXGroundingCT using three protocols:

Protocol A: Zero-shot predictive grounding (attention + multi-window fusion)
Protocol B: Fine-tuned GroundingHead (with progressive unfreezing)
Protocol C: Causal perturbation grounding (zero-shot, interpretable)

Usage:
    # Protocol A: Zero-shot attention grounding
    python -m ctjepa_v2.grounding_eval --protocol A \
        --checkpoint runs/ctjepa_v2/ctjepa_v2_final.pt \
        --dataset_json cepa/ctjepa_v2/rexgrounding/dataset.json

    # Protocol B: Fine-tune grounding head
    python -m ctjepa_v2.grounding_eval --protocol B \
        --checkpoint runs/ctjepa_v2/ctjepa_v2_final.pt \
        --dataset_json cepa/ctjepa_v2/rexgrounding/dataset.json \
        --finetune_epochs 80

    # Protocol C: Causal grounding
    python -m ctjepa_v2.grounding_eval --protocol C \
        --checkpoint runs/ctjepa_v2/ctjepa_v2_final.pt \
        --dataset_json cepa/ctjepa_v2/rexgrounding/dataset.json
"""

import os
import sys
import argparse
import json
import time
import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from scipy.ndimage import label, generate_binary_structure

from ..config import CTJEPAConfig
from ..models.model import CTJEPA
from .grounding import PhraseGrounder, extract_text_heatmap, causal_grounding, upsample_heatmap
from .grounding_data import ReXGroundingDataset, create_grounding_dataloader
from .grounding_head import GroundingHead, GroundingLoss
from ..data.dataset import apply_window


# ---------------------------------------------------------------------------
# Evaluation Metrics (matching rexrank_eval.py)
# ---------------------------------------------------------------------------

GLOBAL_HIT_THR = 0.1
MATCH_DICE_THR = 0.2
MIN_SIZE_DEFAULT = 50
CC_CONNECTIVITY = 2
MAX_COMPONENTS = 50


def dice_score(mask1: np.ndarray, mask2: np.ndarray, eps: float = 1e-6) -> float:
    m1 = mask1 > 0
    m2 = mask2 > 0
    inter = (m1 & m2).sum()
    total = m1.sum() + m2.sum()
    if total == 0:
        return 1.0
    return float((2 * inter + eps) / (total + eps))


def cc_filter(binary_mask: np.ndarray, min_size: int = MIN_SIZE_DEFAULT) -> np.ndarray:
    """Connected component filtering: remove small components, relabel."""
    structure = generate_binary_structure(3, CC_CONNECTIVITY)
    lbl, n = label(binary_mask, structure=structure)
    if n == 0:
        return lbl
    sizes = np.bincount(lbl.ravel())
    remove = np.where(sizes < min_size)[0]
    if len(remove) > 0:
        lbl[np.isin(lbl, remove)] = 0
    relabeled, _ = label(lbl > 0, structure=structure)

    # Cap at MAX_COMPONENTS
    comp_ids = np.unique(relabeled)
    comp_ids = comp_ids[comp_ids > 0]
    if len(comp_ids) > MAX_COMPONENTS:
        sizes = np.bincount(relabeled.ravel())
        id_sizes = [(int(c), int(sizes[c])) for c in comp_ids]
        id_sizes.sort(key=lambda x: x[1], reverse=True)
        keep = set(c for c, _ in id_sizes[:MAX_COMPONENTS])
        relabeled[(relabeled > 0) & (~np.isin(relabeled, list(keep)))] = 0

    return relabeled


def match_instances(gt_cc: np.ndarray, pred_cc: np.ndarray) -> Tuple[list, set, set]:
    """Greedy one-to-one matching of GT and predicted components."""
    gt_ids = set(np.unique(gt_cc).tolist()) - {0}
    pred_ids = set(np.unique(pred_cc).tolist()) - {0}
    if not gt_ids or not pred_ids:
        return [], gt_ids, pred_ids

    gt_masks = {i: (gt_cc == i) for i in gt_ids}
    pred_masks = {j: (pred_cc == j) for j in pred_ids}
    remaining_gt = set(gt_ids)
    remaining_pred = set(pred_ids)
    matches = []

    while remaining_gt and remaining_pred:
        best = (0.0, None, None)
        for gi in remaining_gt:
            for pj in remaining_pred:
                d = dice_score(gt_masks[gi], pred_masks[pj])
                if d > best[0]:
                    best = (d, gi, pj)
        if best[1] is None or best[0] < MATCH_DICE_THR:
            break
        matches.append((best[1], best[2], best[0]))
        remaining_gt.remove(best[1])
        remaining_pred.remove(best[2])

    return matches, remaining_gt, remaining_pred


def evaluate_finding(gt_mask: np.ndarray, pred_mask: np.ndarray,
                     instance_eval: bool = True) -> Dict:
    """Evaluate a single finding: global dice, hit, and instance metrics."""
    gt_bin = gt_mask > 0
    pred_bin = pred_mask > 0

    global_d = dice_score(gt_bin, pred_bin)
    result = {
        'global_dice': global_d,
        'global_hit': global_d >= GLOBAL_HIT_THR,
    }

    if instance_eval:
        pred_cc = cc_filter(pred_bin.astype(np.uint8))
        gt_cc = gt_mask.astype(np.uint8)  # already instance-labeled

        matches, unmatched_gt, unmatched_pred = match_instances(gt_cc, pred_cc)
        tp = len(matches)
        fn = len(unmatched_gt)
        fp = len(unmatched_pred)

        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if tp == 0 and fp == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if tp == 0 and fn == 0 else 0.0)
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        result.update({
            'tp': tp, 'fp': fp, 'fn': fn,
            'instance_precision': prec,
            'instance_recall': rec,
            'instance_f1': f1,
            'mean_matched_dice': float(np.mean([m[2] for m in matches])) if matches else 0.0,
        })

    return result


# ---------------------------------------------------------------------------
# Protocol A: Zero-Shot Attention Grounding (multi-window fusion)
# ---------------------------------------------------------------------------

@torch.no_grad()
def protocol_a_predict(model, volume_hu: np.ndarray, finding_text: str,
                       device: str = 'cuda',
                       grid_s3: Tuple[int, int, int] = (6, 8, 8),
                       threshold_quantile: float = 0.85,
                       window_ids: List[int] = [0, 1, 2, 3],
                       max_text_len: int = 256,
                       ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Protocol A: Zero-shot grounding via predictor cross-attention + multi-window fusion.

    Returns:
        pred_mask: (D, H, W) binary uint8
        heatmap: (D, H, W) float32 [0, 1]
    """
    model.eval()
    D, H, W = volume_hu.shape
    all_heatmaps = []

    for w_id in window_ids:
        volume = apply_window(volume_hu, w_id)
        volume_t = torch.from_numpy(volume).float().unsqueeze(0).unsqueeze(0).to(device)
        window_id_t = torch.tensor([w_id], dtype=torch.long, device=device)

        result = extract_text_heatmap(
            model, volume_t, window_id_t,
            texts=[finding_text],
            grid_s3=grid_s3,
        )

        heatmap_s3 = result['global_heatmap'][0]  # (D3, H3, W3)
        all_heatmaps.append(heatmap_s3)

    # Multi-window fusion: max across windows
    fused_s3 = torch.stack(all_heatmaps).max(dim=0).values

    # Upsample to full resolution
    fused_full = upsample_heatmap(fused_s3, (D, H, W)).cpu().numpy()

    # Normalize to [0, 1]
    vmin, vmax = fused_full.min(), fused_full.max()
    if vmax - vmin > 1e-8:
        fused_full = (fused_full - vmin) / (vmax - vmin)

    # Threshold
    threshold = np.quantile(fused_full, threshold_quantile)
    pred_mask = (fused_full >= threshold).astype(np.uint8)

    return pred_mask, fused_full


# ---------------------------------------------------------------------------
# Protocol C: Causal Perturbation Grounding
# ---------------------------------------------------------------------------

@torch.no_grad()
def protocol_c_predict(model, volume_hu: np.ndarray, finding_text: str,
                       device: str = 'cuda',
                       grid_s3: Tuple[int, int, int] = (6, 8, 8),
                       threshold_quantile: float = 0.85,
                       window_ids: List[int] = [0, 1, 2, 3],
                       max_text_len: int = 256,
                       ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Protocol C: Causal grounding via prediction perturbation + multi-window fusion.
    """
    model.eval()
    D, H, W = volume_hu.shape

    all_heatmaps = []

    for w_id in window_ids:
        volume = apply_window(volume_hu, w_id)
        volume_t = torch.from_numpy(volume).float().unsqueeze(0).unsqueeze(0).to(device)
        window_id_t = torch.tensor([w_id], dtype=torch.long, device=device)

        result = causal_grounding(
            model, volume_t, window_id_t,
            texts=[finding_text],
            grid_s3=grid_s3,
        )

        all_heatmaps.append(result['causal_heatmap'])

    fused_s3 = torch.stack(all_heatmaps).max(dim=0).values
    fused_full = upsample_heatmap(fused_s3, (D, H, W)).cpu().numpy()

    vmin, vmax = fused_full.min(), fused_full.max()
    if vmax - vmin > 1e-8:
        fused_full = (fused_full - vmin) / (vmax - vmin)

    threshold = np.quantile(fused_full, threshold_quantile)
    pred_mask = (fused_full >= threshold).astype(np.uint8)

    return pred_mask, fused_full


# ---------------------------------------------------------------------------
# Protocol B: Fine-Tuned Grounding
# ---------------------------------------------------------------------------

def train_grounding_head(model, config, dataset_json_path: str, data_root: str,
                         output_dir: str, device: str = 'cuda',
                         total_epochs: int = 80, lr: float = 1e-4,
                         batch_size: int = 2):
    """
    Protocol B: Fine-tune GroundingHead on ReXGroundingCT training set.
    Progressive unfreezing: Phase 1 (0-20), Phase 2 (20-50), Phase 3 (50-80).
    """
    os.makedirs(output_dir, exist_ok=True)

    # Create head
    head = GroundingHead(model, freeze_encoder=True, freeze_predictor=True).to(device)
    loss_fn = GroundingLoss(dice_weight=1.0, bce_weight=1.0)

    # Data
    train_loader = create_grounding_dataloader(
        dataset_json_path, data_root, split="train",
        batch_size=batch_size, num_workers=4,
    )
    val_loader = create_grounding_dataloader(
        dataset_json_path, data_root, split="val",
        batch_size=1, num_workers=2,
    )

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, head.parameters()),
        lr=lr, weight_decay=0.01,
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_epochs)

    best_dice = 0.0
    print(f"\nFine-tuning GroundingHead for {total_epochs} epochs...")

    for epoch in range(total_epochs):
        # Progressive unfreezing
        if epoch == 20:
            print("  Phase 2: Unfreezing predictor...")
            head.set_phase(2)
            optimizer.add_param_group({
                'params': list(head.predictor.parameters()),
                'lr': lr * 0.1,
            })
        elif epoch == 50:
            print("  Phase 3: Unfreezing encoder Stage 3...")
            head.set_phase(3)
            optimizer.add_param_group({
                'params': list(head.encoder.stage3.parameters()) +
                          list(head.encoder.readout.parameters()),
                'lr': lr * 0.01,
            })

        # Train
        head.train()
        epoch_losses = []
        for batch in train_loader:
            volume = batch['volume'].to(device)
            window_id = batch['window_id'].to(device)
            texts = batch['finding_text']
            gt_mask = batch['gt_mask'].to(device)
            region_masks = batch['region_masks_s2']
            if region_masks is not None:
                region_masks = region_masks.to(device)

            logits = head(volume, window_id, texts, region_masks)
            losses = loss_fn(logits, gt_mask)

            optimizer.zero_grad()
            losses['total'].backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()

            epoch_losses.append(losses['total'].item())

        scheduler.step()
        avg_loss = np.mean(epoch_losses)

        # Validate every 5 epochs
        if (epoch + 1) % 5 == 0:
            val_metrics = evaluate_grounding_head(head, val_loader, device)
            print(f"  Epoch {epoch+1}/{total_epochs} | Loss: {avg_loss:.4f} | "
                  f"Val Dice: {val_metrics['mean_global_dice']:.4f} | "
                  f"Val HIT: {val_metrics['hit_rate']:.4f}")

            if val_metrics['mean_global_dice'] > best_dice:
                best_dice = val_metrics['mean_global_dice']
                torch.save({
                    'epoch': epoch,
                    'head_state_dict': head.state_dict(),
                    'best_dice': best_dice,
                }, os.path.join(output_dir, 'grounding_head_best.pt'))
        else:
            print(f"  Epoch {epoch+1}/{total_epochs} | Loss: {avg_loss:.4f}")

    print(f"\nFine-tuning complete. Best val Dice: {best_dice:.4f}")
    return head


@torch.no_grad()
def evaluate_grounding_head(head, dataloader, device) -> Dict:
    """Evaluate a fine-tuned GroundingHead on a dataloader."""
    head.eval()
    all_results = []

    for batch in dataloader:
        volume = batch['volume'].to(device)
        window_id = batch['window_id'].to(device)
        texts = batch['finding_text']
        gt_mask = batch['gt_mask'].cpu().numpy()
        region_masks = batch['region_masks_s2']
        if region_masks is not None:
            region_masks = region_masks.to(device)

        logits = head(volume, window_id, texts, region_masks)
        pred_probs = torch.sigmoid(logits).squeeze(1).cpu().numpy()

        for i in range(volume.shape[0]):
            pred_bin = (pred_probs[i] >= 0.5).astype(np.uint8)
            result = evaluate_finding(gt_mask[i], pred_bin, instance_eval=True)
            result['category'] = batch['category'][i]
            result['finding_text'] = batch['finding_text'][i]
            all_results.append(result)

    return _aggregate_results(all_results)


# ---------------------------------------------------------------------------
# Full Evaluation Pipeline
# ---------------------------------------------------------------------------

@torch.no_grad()
def evaluate_protocol(model, protocol: str, dataset_json_path: str, data_root: str,
                      device: str = 'cuda', split: str = "test",
                      output_dir: str = './grounding_results',
                      threshold_quantile: float = 0.85,
                      ) -> Dict:
    """
    Run a full evaluation protocol on ReXGroundingCT.

    Args:
        protocol: "A" (attention), "C" (causal), or "B" (fine-tuned, requires separate training)
        split: "test" or "val"
    """
    model.eval()
    os.makedirs(output_dir, exist_ok=True)

    dataset = ReXGroundingDataset(
        dataset_json_path=dataset_json_path,
        data_root=data_root,
        split=split,
    )

    config = model.config
    grid_s3 = config.patch.grid_size_s3

    predict_fn = protocol_a_predict if protocol == "A" else protocol_c_predict

    all_results = []
    per_category = defaultdict(list)
    per_window = defaultdict(list)

    print(f"\nEvaluating Protocol {protocol} on {split} set ({len(dataset)} findings)...")
    start_time = time.time()

    for idx in range(len(dataset)):
        sample = dataset[idx]
        ct_hu_path = dataset.samples[idx]['npz_path']
        data = np.load(ct_hu_path)
        ct_hu = data['ct']
        if ct_hu.ndim == 4:
            ct_hu = ct_hu[0]

        gt_mask = sample['gt_mask'].numpy()  # (D, H, W), instance-labeled
        finding_text = sample['finding_text']
        category = sample['category']

        pred_mask, heatmap = predict_fn(
            model, ct_hu, finding_text,
            device=device, grid_s3=grid_s3,
            threshold_quantile=threshold_quantile,
        )

        result = evaluate_finding(gt_mask, pred_mask, instance_eval=True)
        result['category'] = category
        result['case_name'] = sample['case_name']
        result['finding_text'] = finding_text[:100]

        all_results.append(result)
        per_category[category].append(result)

        if (idx + 1) % 50 == 0 or idx == len(dataset) - 1:
            agg = _aggregate_results(all_results)
            elapsed = time.time() - start_time
            print(f"  [{idx+1}/{len(dataset)}] "
                  f"Dice: {agg['mean_global_dice']:.4f} | "
                  f"HIT: {agg['hit_rate']:.4f} | "
                  f"F1: {agg.get('instance_f1', 0):.4f} | "
                  f"{elapsed:.0f}s")

    # Final aggregation
    overall = _aggregate_results(all_results)

    # Per-category breakdown
    category_results = {}
    for cat, results in per_category.items():
        category_results[cat] = _aggregate_results(results)

    # Per-window analysis (Protocol A only — run each window separately)
    window_results = {}
    if protocol == "A":
        print("\n  Per-window analysis...")
        for wid in range(4):
            wname = {0: 'lung', 1: 'med', 2: 'general', 3: 'full'}[wid]
            w_results = []
            for idx in range(min(len(dataset), 100)):  # Subset for speed
                sample = dataset[idx]
                ct_hu_path = dataset.samples[idx]['npz_path']
                data = np.load(ct_hu_path)
                ct_hu = data['ct']
                if ct_hu.ndim == 4:
                    ct_hu = ct_hu[0]
                gt_mask = sample['gt_mask'].numpy()

                pred, hm = protocol_a_predict(
                    model, ct_hu, dataset.samples[idx]['finding_text'],
                    device=device, grid_s3=grid_s3,
                    window_ids=[wid],
                    threshold_quantile=threshold_quantile,
                )
                r = evaluate_finding(gt_mask, pred, instance_eval=False)
                w_results.append(r)

            window_results[wname] = _aggregate_results(w_results)
            print(f"    {wname}: Dice={window_results[wname]['mean_global_dice']:.4f} "
                  f"HIT={window_results[wname]['hit_rate']:.4f}")

    # Save results
    output = {
        'protocol': protocol,
        'split': split,
        'threshold_quantile': threshold_quantile,
        'overall': overall,
        'per_category': category_results,
        'per_window': window_results,
        'num_findings': len(all_results),
        'elapsed_seconds': time.time() - start_time,
    }

    output_path = os.path.join(output_dir, f'protocol_{protocol}_{split}_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Protocol {protocol} Results ({split})")
    print(f"{'='*60}")
    print(f"  Global Dice:      {overall['mean_global_dice']:.4f}")
    print(f"  HIT Rate:         {overall['hit_rate']:.4f}")
    if 'instance_f1' in overall:
        print(f"  Instance F1:      {overall['instance_f1']:.4f}")
        print(f"  Instance Prec:    {overall['instance_precision']:.4f}")
        print(f"  Instance Recall:  {overall['instance_recall']:.4f}")
    print(f"\n  Per-category:")
    for cat, res in sorted(category_results.items()):
        n = res.get('num_findings', 0)
        print(f"    {cat}: Dice={res['mean_global_dice']:.4f} "
              f"HIT={res['hit_rate']:.4f} (n={n})")
    print(f"\n  Results saved to: {output_path}")

    return output


def _aggregate_results(results: List[Dict]) -> Dict:
    """Aggregate per-finding results into summary metrics."""
    if not results:
        return {'mean_global_dice': 0, 'hit_rate': 0, 'num_findings': 0}

    global_dices = [r['global_dice'] for r in results]
    hits = sum(1 for r in results if r.get('global_hit', False))

    agg = {
        'mean_global_dice': float(np.mean(global_dices)),
        'hit_rate': hits / len(results),
        'num_findings': len(results),
    }

    # Instance metrics
    if 'tp' in results[0]:
        total_tp = sum(r.get('tp', 0) for r in results)
        total_fp = sum(r.get('fp', 0) for r in results)
        total_fn = sum(r.get('fn', 0) for r in results)

        prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        agg.update({
            'instance_precision': prec,
            'instance_recall': rec,
            'instance_f1': f1,
            'total_tp': total_tp,
            'total_fp': total_fp,
            'total_fn': total_fn,
        })

    return agg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="CT-JEPA v2 Grounding Evaluation")
    parser.add_argument('--protocol', type=str, required=True, choices=['A', 'B', 'C'],
                        help='A=attention, B=fine-tuned, C=causal')
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to ctjepa_v2_final.pt or full checkpoint')
    parser.add_argument('--dataset_json', type=str,
                        default='cepa/ctjepa_v2/rexgrounding/dataset.json')
    parser.add_argument('--data_root', type=str, default='/data/preprocessed')
    parser.add_argument('--split', type=str, default='test', choices=['train', 'val', 'test'])
    parser.add_argument('--output_dir', type=str, default='./grounding_results')
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--threshold', type=float, default=0.85,
                        help='Quantile threshold for zero-shot protocols')

    # Protocol B specific
    parser.add_argument('--finetune_epochs', type=int, default=80)
    parser.add_argument('--finetune_lr', type=float, default=1e-4)
    parser.add_argument('--finetune_batch_size', type=int, default=2)
    parser.add_argument('--grounding_head_ckpt', type=str, default=None,
                        help='Load pre-trained grounding head instead of fine-tuning')

    return parser.parse_args()


def load_model(checkpoint_path: str, device: str = 'cuda') -> CTJEPA:
    """Load CTJEPA model from checkpoint."""
    state = torch.load(checkpoint_path, map_location='cpu', weights_only=False)

    if 'config' in state:
        config = state['config']
    else:
        config = CTJEPAConfig()

    model = CTJEPA(config)

    if 'context_encoder' in state:
        model.context_encoder.load_state_dict(state['context_encoder'])
        model.target_encoder.load_state_dict(state['target_encoder'])
    elif 'model_state_dict' in state:
        model.load_state_dict(state['model_state_dict'])

    return model.to(device).eval()


def main():
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() else 'cpu')

    print("Loading model...")
    model = load_model(args.checkpoint, device)
    print(f"Model loaded. Variant: {model.config.model.variant}, "
          f"Block type: {model.config.model.local_block_type}")

    if args.protocol == 'B':
        if args.grounding_head_ckpt:
            # Load existing grounding head
            head = GroundingHead(model).to(device)
            state = torch.load(args.grounding_head_ckpt, map_location=device, weights_only=False)
            head.load_state_dict(state['head_state_dict'])
            print(f"Loaded grounding head from {args.grounding_head_ckpt}")
        else:
            # Fine-tune
            head = train_grounding_head(
                model, model.config,
                dataset_json_path=args.dataset_json,
                data_root=args.data_root,
                output_dir=os.path.join(args.output_dir, 'finetune'),
                device=str(device),
                total_epochs=args.finetune_epochs,
                lr=args.finetune_lr,
                batch_size=args.finetune_batch_size,
            )

        # Evaluate the head
        test_loader = create_grounding_dataloader(
            args.dataset_json, args.data_root,
            split=args.split, batch_size=1, num_workers=2,
        )
        results = evaluate_grounding_head(head, test_loader, device)

        print(f"\nProtocol B Results ({args.split}):")
        print(f"  Global Dice: {results['mean_global_dice']:.4f}")
        print(f"  HIT Rate:    {results['hit_rate']:.4f}")
        if 'instance_f1' in results:
            print(f"  Instance F1: {results['instance_f1']:.4f}")

        output_path = os.path.join(args.output_dir, f'protocol_B_{args.split}_results.json')
        os.makedirs(args.output_dir, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

    else:
        # Protocol A or C
        evaluate_protocol(
            model, args.protocol,
            dataset_json_path=args.dataset_json,
            data_root=args.data_root,
            device=str(device),
            split=args.split,
            output_dir=args.output_dir,
            threshold_quantile=args.threshold,
        )


if __name__ == '__main__':
    main()
