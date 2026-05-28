"""
Linear probing for multi-label CT finding classification.

Uses pre-extracted CT-JEPA embeddings (train.pt / val.pt).
Label columns are auto-detected from the CSV (any column with values in {-1, 0, 1}),
or specified explicitly with --label_cols. Values of -1 (uncertain) and NaN
are both treated as negative (0).

Usage:
    python linear_probe.py --emb_dir ./ct/cepa_embs --csv ./final_ct2.csv
    python linear_probe.py --emb_dir ./ct/cepa_embs --csv ./final_ct2.csv --loss asl
    python linear_probe.py --label_cols "Emphysema" "Consolidation" "Pleural effusion"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm


# ============================================================
# Known metadata columns — never treated as labels
# ============================================================
_META_COLS = {
    "object_id", "VolumeName", "split", "base_name", "img_path",
    "findings", "refined_findings", "impression", "indication",
    "Lungs", "Airways & Trachea", "Pleura", "Mediastinum & Hila",
    "Cardiovascular", "Chest Wall", "Bones / Spine", "Upper abdomen",
    "Lower neck", "Breast & Axilla", "Others", "Lungs + Pleura",
    "Thoracic MSK", "Unnamed: 0",
}


def resolve_label_cols(csv_path: str, label_cols_arg: Optional[List[str]]) -> List[str]:
    if label_cols_arg:
        return label_cols_arg

    df = pd.read_csv(csv_path, nrows=100)
    detected = []
    for c in df.columns:
        if c in _META_COLS:
            continue
        if df[c].dtype in ["int64", "float64"]:
            unique = set(df[c].dropna().unique())
            if unique and unique.issubset({-1, 0, 1, -1.0, 0.0, 1.0}):
                detected.append(c)
    if not detected:
        raise ValueError(
            f"No label columns detected in {csv_path}. "
            "Use --label_cols to specify them explicitly."
        )
    return detected


# ============================================================
# Data loading
# ============================================================

def load_embeddings(pt_path: str) -> Tuple[List[str], torch.Tensor]:
    """Load a split .pt file -> (ids, embeddings [N, D])."""
    data = torch.load(pt_path, map_location="cpu", weights_only=False)
    ids: List[str] = data["ids"]
    embs: torch.Tensor = data["embeddings"].float()
    return ids, embs


def build_label_map(csv_path: str, label_cols: List[str]) -> Dict[str, np.ndarray]:
    """Read CSV and return {object_id: label_array (num_classes,)}."""
    df = pd.read_csv(csv_path)

    # Normalize IDs: strip .npz / .nii.gz extensions
    df["_id"] = df["object_id"].apply(
        lambda x: str(x).replace(".npz", "").replace(".nii.gz", "")
    )

    missing = [c for c in label_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing label columns in CSV: {missing}")

    def _to_label(v) -> float:
        if pd.isna(v):
            return 0.0
        return max(float(v), 0.0)

    label_map: Dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        labels = np.array([_to_label(row[c]) for c in label_cols], dtype=np.float32)
        # Store under both raw and normalized ID
        label_map[str(row["object_id"])] = labels
        label_map[row["_id"]] = labels

    return label_map


class EmbeddingDataset(Dataset):
    def __init__(self, ids: List[str], embeddings: torch.Tensor,
                 label_map: Dict[str, np.ndarray]):
        # Try matching by raw ID, then by stripping extensions
        valid_idx = []
        for i, id_ in enumerate(ids):
            key = id_
            if key not in label_map:
                key = str(id_).replace(".npz", "").replace(".nii.gz", "")
            if key in label_map:
                valid_idx.append((i, key))

        missing = len(ids) - len(valid_idx)
        if missing:
            print(f"  [WARNING] {missing}/{len(ids)} IDs not found in label_map; skipping.")

        self.ids = [ids[i] for i, _ in valid_idx]
        self.embeddings = embeddings[[i for i, _ in valid_idx]]
        self.labels = torch.tensor(
            np.stack([label_map[key] for _, key in valid_idx]),
            dtype=torch.float32,
        )

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.embeddings[idx], self.labels[idx]


# ============================================================
# Losses
# ============================================================

class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, alpha: float = 0.25, reduction: str = "mean"):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probs = torch.sigmoid(logits)
        p_t = probs * targets + (1 - probs) * (1 - targets)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        focal_weight = alpha_t * (1 - p_t) ** self.gamma
        loss = focal_weight * bce
        return loss.mean() if self.reduction == "mean" else loss.sum()


class AsymmetricLoss(nn.Module):
    def __init__(self, gamma_pos: float = 0.0, gamma_neg: float = 4.0,
                 clip: float = 0.05, reduction: str = "mean"):
        super().__init__()
        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.clip = clip
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        probs_neg = probs
        if self.clip > 0:
            probs_neg = (probs - self.clip).clamp(min=1e-8)

        log_pos = torch.log(probs.clamp(min=1e-8))
        log_neg = torch.log((1 - probs_neg).clamp(min=1e-8))

        loss_pos = -targets * log_pos
        loss_neg = -(1 - targets) * log_neg

        if self.gamma_pos > 0:
            loss_pos = loss_pos * ((1 - probs) ** self.gamma_pos)
        if self.gamma_neg > 0:
            pt_neg = 1 - probs_neg
            loss_neg = loss_neg * ((1 - pt_neg) ** self.gamma_neg)

        loss = loss_pos + loss_neg
        return loss.mean() if self.reduction == "mean" else loss.sum()


# ============================================================
# Model
# ============================================================

class LinearProbe(nn.Module):
    def __init__(self, emb_dim: int, num_classes: int, dropout: float = 0.0):
        super().__init__()
        layers: List[nn.Module] = []
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        layers.append(nn.Linear(emb_dim, num_classes))
        self.head = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(x)


# ============================================================
# Evaluation
# ============================================================

@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module,
             device: torch.device, num_classes: int,
             threshold: float = 0.5) -> Tuple[float, dict]:
    model.eval()
    all_logits, all_targets = [], []
    total_loss = 0.0
    n_batches = 0

    for embs, targets in loader:
        embs, targets = embs.to(device), targets.to(device)
        logits = model(embs)
        loss = criterion(logits, targets)
        total_loss += loss.item()
        n_batches += 1
        all_logits.append(logits.cpu().float().numpy())
        all_targets.append(targets.cpu().float().numpy())

    all_logits = np.concatenate(all_logits, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    all_probs = 1 / (1 + np.exp(-all_logits))
    all_preds = (all_probs >= threshold).astype(np.float32)

    aucs = np.full(num_classes, np.nan)
    f1s = np.full(num_classes, np.nan)
    precs = np.full(num_classes, np.nan)
    recs = np.full(num_classes, np.nan)

    for c in range(num_classes):
        y_true = all_targets[:, c]
        y_prob = all_probs[:, c]
        y_pred = all_preds[:, c]
        pos = y_true.sum()
        if pos == 0 or pos == len(y_true):
            continue
        aucs[c] = roc_auc_score(y_true, y_prob)
        f1s[c] = f1_score(y_true, y_pred, zero_division=0)
        precs[c] = precision_score(y_true, y_pred, zero_division=0)
        recs[c] = recall_score(y_true, y_pred, zero_division=0)

    prevalence = all_targets.mean(axis=0)
    mean_loss = total_loss / max(n_batches, 1)

    def _macro(arr):
        valid = arr[~np.isnan(arr)]
        return float(valid.mean()) if len(valid) else float("nan")

    return mean_loss, {
        "auc": aucs, "f1": f1s, "precision": precs, "recall": recs,
        "prevalence": prevalence,
        "macro_auc": _macro(aucs), "macro_f1": _macro(f1s),
        "macro_precision": _macro(precs), "macro_recall": _macro(recs),
    }


def print_best_metrics(metrics: dict, label_cols: List[str]) -> None:
    header = (
        f"\n{'Idx':>3}  {'AUC':>6}  {'F1':>6}  {'Prec':>6}  {'Rec':>6}  "
        f"{'Prev':>5}  Label"
    )
    print(header)
    print("-" * len(header))
    for i, name in enumerate(label_cols):
        def fmt(v):
            return f"{v:.4f}" if not np.isnan(v) else "  N/A"
        print(
            f"{i:3d}  {fmt(metrics['auc'][i])}  {fmt(metrics['f1'][i])}  "
            f"{fmt(metrics['precision'][i])}  {fmt(metrics['recall'][i])}  "
            f"{metrics['prevalence'][i]:5.3f}  {name}"
        )
    print(
        f"\n  Macro AUC={metrics['macro_auc']:.4f}  "
        f"F1={metrics['macro_f1']:.4f}  "
        f"Prec={metrics['macro_precision']:.4f}  "
        f"Rec={metrics['macro_recall']:.4f}"
    )


# ============================================================
# Training
# ============================================================

def train(args: argparse.Namespace) -> None:
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    label_cols = resolve_label_cols(args.csv, args.label_cols)
    num_classes = len(label_cols)
    print(f"\nLabel columns ({num_classes}):")
    for i, c in enumerate(label_cols):
        print(f"  [{i:02d}] {c}")

    # Load embeddings
    train_pt = os.path.join(args.emb_dir, "train.pt")
    val_pt = os.path.join(args.emb_dir, "val.pt")
    for p in (train_pt, val_pt):
        if not os.path.exists(p):
            sys.exit(f"[ERROR] Embedding file not found: {p}")

    print(f"\nLoading train embeddings from {train_pt} ...")
    train_ids, train_embs = load_embeddings(train_pt)
    print(f"  -> {len(train_ids)} samples, dim={train_embs.shape[1]}")

    print(f"Loading val embeddings from {val_pt} ...")
    val_ids, val_embs = load_embeddings(val_pt)
    print(f"  -> {len(val_ids)} samples, dim={val_embs.shape[1]}")

    emb_dim = train_embs.shape[1]

    # Load labels
    print(f"Loading labels from {args.csv} ...")
    label_map = build_label_map(args.csv, label_cols)
    print(f"  -> {len(label_map)} label entries")

    # Datasets
    train_ds = EmbeddingDataset(train_ids, train_embs, label_map)
    val_ds = EmbeddingDataset(val_ids, val_embs, label_map)
    print(f"  Train samples: {len(train_ds)}, Val samples: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=args.num_workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size * 4, shuffle=False,
                            num_workers=args.num_workers, pin_memory=True)

    # Model
    model = LinearProbe(emb_dim, num_classes, dropout=args.dropout).to(device)
    print(f"\nModel: LinearProbe(emb_dim={emb_dim}, num_classes={num_classes}, dropout={args.dropout})")

    # Loss
    if args.loss == "asl":
        criterion = AsymmetricLoss(gamma_pos=args.gamma_pos, gamma_neg=args.gamma_neg, clip=args.clip)
        print(f"Loss: ASL(gamma_pos={args.gamma_pos}, gamma_neg={args.gamma_neg}, clip={args.clip})")
    else:
        criterion = FocalLoss(gamma=args.gamma, alpha=args.alpha)
        print(f"Loss: FocalLoss(gamma={args.gamma}, alpha={args.alpha})")

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    # Training loop
    best_val_auc = -1.0
    best_epoch = 0
    best_metrics = None
    save_path = os.path.join(args.out_dir, "best_linear_probe.pt")
    os.makedirs(args.out_dir, exist_ok=True)

    print(f"\nStarting training for {args.epochs} epochs ...")
    print(f"  LR={args.lr}, WD={args.weight_decay}, batch_size={args.batch_size}")
    print(f"  Checkpoints -> {args.out_dir}\n")

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0

        for embs, targets in tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}", leave=False):
            embs, targets = embs.to(device), targets.to(device)
            optimizer.zero_grad()
            logits = model(embs)
            loss = criterion(logits, targets)
            loss.backward()
            if args.grad_clip > 0:
                nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            total_loss += loss.item()

        scheduler.step()

        train_loss = total_loss / max(len(train_loader), 1)
        val_loss, val_metrics = evaluate(model, val_loader, criterion, device,
                                          num_classes=num_classes, threshold=args.threshold)
        mean_val_auc = val_metrics["macro_auc"]
        lr_now = scheduler.get_last_lr()[0]

        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} | "
            f"val_loss={val_loss:.4f} | "
            f"macro_auc={mean_val_auc:.4f} | "
            f"macro_f1={val_metrics['macro_f1']:.4f} | "
            f"lr={lr_now:.2e}"
        )

        if mean_val_auc > best_val_auc:
            best_val_auc = mean_val_auc
            best_epoch = epoch
            best_metrics = val_metrics
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "label_cols": label_cols,
                "macro_auc": mean_val_auc,
                "macro_f1": val_metrics["macro_f1"],
                "args": vars(args),
            }, save_path)

    # Final report
    print(f"\n{'='*70}")
    print(f"  BEST EPOCH: {best_epoch}  |  macro AUC = {best_val_auc:.4f}")
    print(f"{'='*70}")
    if best_metrics:
        print_best_metrics(best_metrics, label_cols)

    # Save per-class results
    if best_metrics:
        results_df = pd.DataFrame({
            "class": label_cols,
            "auc": best_metrics["auc"],
            "f1": best_metrics["f1"],
            "precision": best_metrics["precision"],
            "recall": best_metrics["recall"],
            "prevalence": best_metrics["prevalence"],
        })
        results_path = os.path.join(args.out_dir, "best_val_results.csv")
        results_df.to_csv(results_path, index=False)
        print(f"\nPer-class results saved to {results_path}")
    print(f"Best checkpoint saved to    {save_path}")


# ============================================================
# Argparse
# ============================================================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Linear probing on CT-JEPA v2 embeddings for multi-label CT finding classification."
    )
    ap.add_argument("--emb_dir", type=str, default="./ct/cepa_embs")
    ap.add_argument("--csv", type=str, default="./final_ct2.csv")
    ap.add_argument("--out_dir", type=str, default="./linear_probe_output")
    ap.add_argument("--label_cols", nargs="+", default=None)
    # Training
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch_size", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight_decay", type=float, default=1e-4)
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--grad_clip", type=float, default=1.0)
    ap.add_argument("--num_workers", type=int, default=4)
    ap.add_argument("--device", type=str, default="cuda:0")
    # Loss
    ap.add_argument("--loss", type=str, default="focal", choices=["focal", "asl"])
    ap.add_argument("--gamma", type=float, default=2.0)
    ap.add_argument("--alpha", type=float, default=0.25)
    ap.add_argument("--gamma_pos", type=float, default=0.0)
    ap.add_argument("--gamma_neg", type=float, default=4.0)
    ap.add_argument("--clip", type=float, default=0.05)
    ap.add_argument("--threshold", type=float, default=0.5)
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
