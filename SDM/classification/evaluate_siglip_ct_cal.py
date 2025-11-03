#!/usr/bin/env python3
# coding: utf-8
"""
Evaluate trained SigLIP model on chest-CT validation set
"""

from __future__ import annotations
import argparse, logging, os, sys, json, warnings
import numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F
from sklearn.metrics import f1_score, precision_recall_fscore_support, roc_auc_score
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from tqdm import tqdm  # Added for progress bar

# Local imports
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "training"))
from training.ct_transform import get_val_transform
from merlin import Merlin

# ───────────────────────────────────────────────────────
def _hu_window_to_unit(volume: np.ndarray, center: float, width: float) -> np.ndarray:
    """Clip a HU volume to the given window and scale to [0,1]."""
    lower, upper = center - width / 2.0, center + width / 2.0
    vol = np.clip(volume, lower, upper)
    return (vol - lower) / (upper - lower)

class CTDataset(Dataset):
    """Loads npz volumes and on-the-fly window mixing."""
    def __init__(self, csv: str, labels: List[str], split: str, transform=None, three_ch: bool = False):
        self.df = pd.read_csv(csv).query("split==@split").reset_index(drop=True)
        self.labels, self.transform, self.three_ch = labels, transform, three_ch
        logging.info(f"{split.capitalize():5s}: {len(self.df):,} vols")

    def __len__(self): return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        try:
            with np.load(row.img_path) as npz:
                arr = npz["image"]
        except Exception as e:
            logging.warning(f"Corrupt sample {row.img_path}: {e}")
            return self.__getitem__(0)  # fallback to first sample

        if self.three_ch:
            if arr.max() <= 1.0:
                arr = arr * 2500.0 - 1000.0

            if arr.ndim == 4:
                arr = arr[0]
            
            lung  = _hu_window_to_unit(arr,  -600, 1000)
            medi  = _hu_window_to_unit(arr,    40,  400)
            bone  = _hu_window_to_unit(arr,   700, 1500)
            arr = np.stack([lung, medi, bone], 0)

        img = torch.from_numpy(arr).float()
        if self.transform is not None: 
            img = self.transform(img)
        tgt = torch.from_numpy(row[self.labels].values.astype(np.float32))
        return img, tgt


# ───────────────────────────────────────────────────────
class SigLIPClassifier(nn.Module):
    def __init__(self, backbone: nn.Module, n_classes: int, drop: float = .1):
        super().__init__()
        self.backbone = backbone
        dim = getattr(backbone, "output_dim", 2048)
        self.head = nn.Sequential(
            nn.Dropout(drop), nn.Linear(dim, dim // 2), nn.GELU(),
            nn.Dropout(drop), nn.Linear(dim // 2, n_classes)
        )

    def forward(self, x):
        feat = self.backbone(x).flatten(1)
        return self.head(feat)

# ───────────────────────────────────────────────────────
def _worker_init_fn(worker_id):
    """Worker initialization function to set single-threaded NumPy/BLAS."""
    np.random.seed()
    torch.set_num_threads(1)

# ----------------------------------------------------------------------
#  Tiny calibration layer (must match the one saved during training)
# ----------------------------------------------------------------------
class _AffineCalibrator(nn.Module):
    """Per‑class temperature and bias: z' = (z + b) / T"""
    def __init__(self, n_cls: int):
        super().__init__()
        self.log_T = nn.Parameter(torch.zeros(n_cls))   # T_i = exp(log_T_i) ≥ 0
        self.bias  = nn.Parameter(torch.zeros(n_cls))   # b_i

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return (z + self.bias) / torch.exp(self.log_T)


class CalibratedSigLIP(nn.Module):
    """
    Wraps the original SigLIPClassifier (“base”) with the fitted calibrator.
    Forward returns *calibrated* logits.
    """
    def __init__(self, base: nn.Module, calib: _AffineCalibrator):
        super().__init__()
        self.base = base
        self.calib = calib

    def forward(self, x):
        z = self.base(x)
        return self.calib(z)


# ───────────────────────────────────────────────────────
class FocalBalancedLoss(nn.Module):
    """Focal loss + BCE pos‑weight (works better for extreme imbalance)."""
    def __init__(self, pos_weight: torch.Tensor, gamma: float = 2.0):
        super().__init__(); self.w = pos_weight; self.g = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor):
        bce = F.binary_cross_entropy_with_logits(logits, targets,
                                                 reduction="none", pos_weight=self.w)
        p_t = torch.exp(-bce)
        loss = (1 - p_t) ** self.g * bce
        return loss.mean()

# ───────────────────────────────────────────────────────
def calculate_crg_score(y_true: np.ndarray, y_pred: np.ndarray, labels: List[str]) -> Dict[str, float]:
    """Calculate CRG (Clinically Relevant Grade) score."""
    if y_true.shape[0] == 0:
        return {"CRG": 0.0, "TP": 0, "FN": 0, "FP": 0, "X": 0, "A": 0, "r": 0.0, "U": 0.0, "score_s": 0.0}
    
    TP = int(((y_pred == 1) & (y_true == 1)).sum())
    FN = int(((y_pred == 0) & (y_true == 1)).sum())
    FP = int(((y_pred == 1) & (y_true == 0)).sum())
    
    num_images = y_true.shape[0]
    num_labels = len(labels)
    X = num_labels * num_images
    A = int(y_true.sum())
    
    if A == 0:
        return {"CRG": 0.0, "TP": TP, "FN": FN, "FP": FP, "X": X, "A": A, "r": 0.0, "U": 0.0, "score_s": 0.0}
    
    r = (X - A) / (2 * A)
    U = (X - A) / 2
    s = r * TP - r * FN - FP
    
    denominator = 2 * U - s
    crg = U / denominator if abs(denominator) > 1e-10 else 0.0
    crg = max(0.0, min(1.0, crg))
    
    return {
        "CRG": float(crg),
        "TP": TP,
        "FN": FN, 
        "FP": FP,
        "X": X,
        "A": A,
        "r": float(r),
        "U": float(U),
        "score_s": float(s)
    }

# ───────────────────────────────────────────────────────
def search_thresholds(logits: np.ndarray, gts: np.ndarray, step: float = 0.005) -> Tuple[np.ndarray, float]:
    """Search for optimal per-class thresholds."""
    best = np.zeros(logits.shape[1])
    for c in range(logits.shape[1]):
        t_candidates = np.arange(0.05, 0.95, step)
        f1s = [f1_score(gts[:, c], (logits[:, c] > t).astype(int), zero_division=0) for t in t_candidates]
        idx = int(np.argmax(f1s))
        best[c] = t_candidates[idx]
    macro = f1_score(gts, logits > best, average="macro", zero_division=0)
    return best, macro

# ───────────────────────────────────────────────────────
@torch.inference_mode()
def evaluate(model, loader, device, labels, thresholds):
    """Evaluate model on validation set."""
    model.eval()
    logits, gts = [], []
    
    for x, y in tqdm(loader, desc="Evaluating"):
        x, y = x.to(device, non_blocking=True), y.to(device)
        out = model(x)
        logits.append(torch.sigmoid(out).cpu())
        gts.append(y.cpu())
    
    if logits:
        logits = torch.cat(logits, dim=0).numpy()
        gts = torch.cat(gts, dim=0).numpy()
    else:
        logits = np.array([]).reshape(0, len(labels))
        gts = np.array([]).reshape(0, len(labels))

    # Apply thresholds
    if isinstance(thresholds, float):
        preds = (logits > thresholds).astype(int)
    else:
        preds = (logits > thresholds[None, :]).astype(int)

    # Calculate CRG score
    crg_metrics = calculate_crg_score(gts, preds, labels)

    # Calculate macro AUC
    macro_auc = 0.0
    if gts.shape[0] > 0:
        try:
            macro_auc = roc_auc_score(gts, logits, average="macro")
        except ValueError as e:
            logging.warning(f"Could not calculate macro AUC: {e}")
            macro_auc = 0.5

    metrics = {
        "macro_f1": f1_score(gts, preds, average="macro", zero_division=0),
        "micro_f1": f1_score(gts, preds, average="micro", zero_division=0),
        "macro_auc": macro_auc,
        "CRG": crg_metrics["CRG"]
    }
    
    # Per-class metrics
    pr, rc, f1, _ = precision_recall_fscore_support(
        gts, preds, average=None, zero_division=0, labels=range(len(labels)))
    
    auc = []
    for i in range(len(labels)):
        if gts.shape[0] > 0:
            try:
                unique_vals = np.unique(gts[:, i])
                if len(unique_vals) > 1:
                    auc_score = roc_auc_score(gts[:, i], logits[:, i])
                else:
                    auc_score = 0.5
                auc.append(auc_score)
            except ValueError as e:
                logging.warning(f"AUC calculation failed for {labels[i]}: {e}")
                auc.append(0.5)
        else:
            auc.append(0.0)
    
    for i, name in enumerate(labels):
        metrics[f"{name}_precision"] = pr[i] if i < len(pr) else 0.0
        metrics[f"{name}_recall"] = rc[i] if i < len(rc) else 0.0
        metrics[f"{name}_f1"] = f1[i] if i < len(f1) else 0.0
        metrics[f"{name}_auc"] = auc[i]

    return metrics, logits, gts

# ───────────────────────────────────────────────────────
def load_model_from_checkpoint(checkpoint_path: str,
                               labels: List[str],
                               device: torch.device):
    """
    Load either plain SigLIP or SigLIP + calibration, depending on what the
    checkpoint contains.  Returns (model, thresholds).
    """
    logging.info(f"Loading model from {checkpoint_path}")
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state = ckpt["model"]

    # ------------------------------------------------------------------
    #  Detect whether a calibrator is present (keys start with "calib.")
    # ------------------------------------------------------------------
    has_calib = any(k.startswith("calib.") for k in state)
    n_cls = len(labels)

    # 1️⃣  create backbone exactly like in training
    backbone = Merlin(ImageEmbedding=True)
    base_model = SigLIPClassifier(backbone, n_cls, drop=0.1)

    if has_calib:
        logging.info("Checkpoint contains a calibration layer – using CalibratedSigLIP")

        # 2️⃣  initialise an empty calibrator
        calib_layer = _AffineCalibrator(n_cls)

        # 3️⃣  wrap both into one nn.Module
        model = CalibratedSigLIP(base_model, calib_layer)
    else:
        logging.info("No calibration layer found – loading plain SigLIP model")
        model = base_model

    # --------------------------------------------------------------
    #  Handle possible 'module.' prefixes (DDP) and load parameters
    # --------------------------------------------------------------
    if any(k.startswith("module.") for k in state):
        state = {k.replace("module.", "", 1): v for k, v in state.items()}

    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        logging.warning(f"Missing keys: {len(missing)} | Unexpected keys: {len(unexpected)}")

    model.to(device).eval()

    # If you exported the calibrated model, you no longer need per‑class thresholds:
    # the decision point is exactly 0.5.  Otherwise fall back to what the
    # training script saved (or a scalar 0.5 if absent).
    if has_calib:
        thresholds = np.full(n_cls, 0.5, dtype=np.float32)
    else:
        thresholds = ckpt.get("thresholds", np.full(n_cls, 0.5, dtype=np.float32))

    logging.info("Model ready for inference")
    return model, thresholds

# ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Evaluate SigLIP model on validation set")
    parser.add_argument("--model-path", required=True, help="Path to model checkpoint")
    parser.add_argument("--csv", default="/data/all_ct_with_labels.csv", help="CSV file with data")
    parser.add_argument("--label-columns", nargs="+", default=None, help="Label columns")
    parser.add_argument("--three-channel", action="store_true", help="Use three-channel windowing")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for evaluation")
    parser.add_argument("--num-workers", type=int, default=4, help="Number of data loader workers")
    parser.add_argument("--device", default="cuda", help="Device to use")
    parser.add_argument("--optimize-thresholds", action="store_true", help="Search for optimal thresholds")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--output-dir", default="eval_results", help="Output directory for results")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load default labels if not provided
    if args.label_columns is None:
        labels_file = ROOT / "default_labels18.json"
        if labels_file.exists():
            args.label_columns = json.loads(labels_file.read_text())
            logging.info(f"Loaded {len(args.label_columns)} default labels")
        else:
            raise ValueError("No label columns provided and default_labels18.json not found")
    
    # Setup device - use CUDA if available, otherwise CPU
    if torch.cuda.is_available() and args.device.startswith("cuda"):
        device = torch.device(args.device)
        logging.info(f"Using device: {device} (CUDA available)")
    else:
        device = torch.device("cpu")
        if args.device.startswith("cuda"):
            logging.warning(f"CUDA requested but not available, falling back to CPU")
        else:
            logging.info(f"Using device: {device}")
    
    # Load model
    model, saved_thresholds = load_model_from_checkpoint(args.model_path, args.label_columns, device)
    
    # Create validation dataset with exact training parameters
    val_transform = get_val_transform()
    val_dataset = CTDataset(args.csv, args.label_columns, "val", val_transform, args.three_channel)
    
    # Match training DataLoader parameters exactly
    pin_memory_device = f"cuda:0" if torch.cuda.is_available() else None
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, 
                           num_workers=4, pin_memory=True,  # Match training: 4 workers
                           pin_memory_device=pin_memory_device,
                           persistent_workers=True, prefetch_factor=2, 
                           worker_init_fn=_worker_init_fn)  # Missing in evaluation!
    
    logging.info(f"Validation set: {len(val_dataset)} samples")
    
    # Evaluate with saved thresholds
    logging.info("Evaluating with saved thresholds...")
    metrics, logits, gts = evaluate(model, val_loader, device, args.label_columns, saved_thresholds)
    
    # Print results
    print("\n" + "="*80)
    print("EVALUATION RESULTS WITH SAVED THRESHOLDS")
    print("="*80)
    
    # Core metrics
    core_metrics = ["macro_f1", "micro_f1", "macro_auc", "CRG"]
    for metric in core_metrics:
        if metric in metrics:
            print(f"  {metric:>15s}: {metrics[metric]:.4f}")
    
    print("-"*40)
    print("Per-class F1 Scores:")
    for label in args.label_columns:
        f1_key = f"{label}_f1"
        if f1_key in metrics:
            print(f"  {label:>25s}: {metrics[f1_key]:.4f}")
    
    print("-"*40)
    print("Per-class AUC Scores:")
    for label in args.label_columns:
        auc_key = f"{label}_auc"
        if auc_key in metrics:
            print(f"  {label:>25s}: {metrics[auc_key]:.4f}")
    
    # Save results
    results_file = output_dir / "evaluation_results.json"
    with open(results_file, "w") as f:
        json.dump(metrics, f, indent=2)
    logging.info(f"Results saved to {results_file}")

    # Save per-sample predictions as CSV
    if logits.shape[0] > 0:
        pred_df = pd.DataFrame()
        pred_df['index'] = np.arange(logits.shape[0])
        for i, label in enumerate(args.label_columns):
            pred_df[f'{label}_score'] = logits[:, i]
            pred_df[f'{label}_prediction_label'] = (logits[:, i] > (saved_thresholds[i] if hasattr(saved_thresholds, '__len__') else saved_thresholds)).astype(int)
            pred_df[f'{label}_gt'] = gts[:, i]
        pred_csv_file = output_dir / "per_sample_predictions.csv"
        pred_df.to_csv(pred_csv_file, index=False)
        logging.info(f"Per-sample predictions saved to {pred_csv_file}")
    
    # Optimize thresholds if requested
    if args.optimize_thresholds:
        logging.info("Searching for optimal thresholds...")
        optimal_thresholds, macro_f1_opt = search_thresholds(logits, gts)
        
        # Evaluate with optimal thresholds
        metrics_opt, _, _ = evaluate(model, val_loader, device, args.label_columns, optimal_thresholds)
        
        print("\n" + "="*80)
        print("EVALUATION RESULTS WITH OPTIMIZED THRESHOLDS")
        print("="*80)
        
        for metric in core_metrics:
            if metric in metrics_opt:
                print(f"  {metric:>15s}: {metrics_opt[metric]:.4f}")
        
        print(f"\nOptimal thresholds:")
        for i, label in enumerate(args.label_columns):
            print(f"  {label:>25s}: {optimal_thresholds[i]:.3f}")
        
        # Save optimized results
        results_opt = {
            "metrics": metrics_opt,
            "thresholds": optimal_thresholds.tolist(),
            "macro_f1_with_optimal": macro_f1_opt
        }
        results_opt_file = output_dir / "evaluation_results_optimized.json"
        with open(results_opt_file, "w") as f:
            json.dump(results_opt, f, indent=2)
        logging.info(f"Optimized results saved to {results_opt_file}")
    
    print("="*80)

if __name__ == "__main__":
    main() 