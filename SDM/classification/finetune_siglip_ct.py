#!/usr/bin/env python3
# coding: utf-8
"""
Finetune SigLIP on chest‑CT multilabel classification (18 findings)

Adds:
• 3‑D aug, discriminative LR, focal‑BCE combo, dynamic threshold search
• Gradual unfreezing, SWA, EMA, WandB histograms
• Cleaner CLI, better typing, fewer global variables
• Multi-GPU distributed training support
"""

from __future__ import annotations
import argparse, logging, os, random, sys, warnings, re, math, json
import torch.distributed as dist
from pathlib import Path
from typing import Dict, List, Tuple, Optional
# test
import numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F
from sklearn.metrics import f1_score, precision_recall_fscore_support, roc_auc_score
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW, SGD
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau
from torch.optim.swa_utils import AveragedModel, SWALR
from transformers.optimization import get_cosine_schedule_with_warmup
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler, DistributedSampler
from torch.nn.parallel import DistributedDataParallel as DDP
from tqdm import tqdm

# --- make PyTorch checkpoint use the non‑reentrant engine -------------
import torch.utils.checkpoint as cp
if hasattr(cp, "config"):
    cp.config.set_reentrant(False)        # pytorch ≥1.13
# ----------------------------------------------------------------------

# ───────────────────────────────────────────────────────
try:
    import wandb; WANDB_OK = True
except ImportError:
    WANDB_OK = False; warnings.warn("wandb unavailable – external logging disabled")

# local imports
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "training"))
from training.ct_transform import get_train_transform, get_val_transform
from merlin import Merlin

# ───────────────────────────────────────────────────────
def setup_distributed():
    """Initialize distributed training if available."""
    if 'RANK' in os.environ and 'WORLD_SIZE' in os.environ:
        rank = int(os.environ['RANK'])
        world_size = int(os.environ['WORLD_SIZE'])
        local_rank = int(os.environ['LOCAL_RANK'])
        
        dist.init_process_group(backend='nccl')
        torch.cuda.set_device(local_rank)
        
        return rank, world_size, local_rank
    else:
        return 0, 1, 0

def cleanup_distributed():
    """Clean up distributed training."""
    if dist.is_initialized():
        dist.destroy_process_group()

def is_main_process():
    """Check if this is the main process (rank 0)."""
    return not dist.is_initialized() or dist.get_rank() == 0

# ───────────────────────────────────────────────────────
def set_seed(seed: int = 42):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark     = True
    # speed up matmuls on Ampere/Hopper
    torch.set_float32_matmul_precision('high')

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
class SigLIPClassifier(nn.Module):
    def __init__(self, backbone: nn.Module, n_classes: int, drop: float = .1):
        super().__init__()
        self.backbone = backbone
        dim = getattr(backbone, "output_dim", 2048)
        self.head = nn.Sequential(
            nn.Dropout(drop), nn.Linear(dim, dim // 2), nn.GELU(),
            nn.Dropout(drop), nn.Linear(dim // 2, n_classes)
        )
        self.head.apply(self._init)

    @staticmethod
    def _init(m):                                 # Xavier normal
        if isinstance(m, nn.Linear):
            nn.init.xavier_normal_(m.weight); nn.init.zeros_(m.bias)

    def forward(self, x):                         # (B,C,D,H,W)
        feat = self.backbone(x).flatten(1)
        return self.head(feat)

# ───────────────────────────────────────────────────────
def _hu_window_to_unit(volume: np.ndarray,
                       center: float,
                       width: float) -> np.ndarray:
    """
    Clip a HU volume to the given window and scale to [0,1].
    Args
        volume : raw HU ndarray, shape (D,H,W) or (C,D,H,W)
        center : window centre in HU
        width  : window width in HU
    """
    lower, upper = center - width / 2.0, center + width / 2.0
    vol = np.clip(volume, lower, upper)
    return (vol - lower) / (upper - lower)

class CTDataset(Dataset):
    """Loads npz volumes and on‑the‑fly window mixing."""
    def __init__(self, csv: str, labels: List[str], split: str,
                 transform=None, three_ch: bool = False, data_fraction: float = 1.0):
        self.df = pd.read_csv(csv).query("split==@split").reset_index(drop=True)
        
        # Subsample data for sanity testing
        if data_fraction < 1.0:
            n_samples = max(1, int(len(self.df) * data_fraction))
            self.df = self.df.sample(n=n_samples, random_state=42).reset_index(drop=True)
            logging.info(f"Sanity mode: Using {data_fraction:.1%} of {split} data ({n_samples:,} samples)")
        
        self.labels, self.transform, self.three_ch = labels, transform, three_ch
        logging.info(f"{split.capitalize():5s}: {len(self.df):,} vols")

    def __len__(self): return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        try:
            with np.load(row.img_path) as npz:
                arr = npz["image"]                         # (C,D,H,W) or (1,D,H,W)
        except Exception as e:
            logging.warning(f"Corrupt sample {row.img_path}: {e}")
            return self.__getitem__(random.randint(0, len(self) - 1))
        if self.three_ch:
            if arr.max() <= 1.0:                         # heuristic
                arr = arr * 2500.0 - 1000.0              # back‑to‑HU

            # arr shape: (C,D,H,W) or (D,H,W); unify to (D,H,W)
            if arr.ndim == 4:
                arr = arr[0]        # assume first channel is full‑range HU
            
            # Generate three standard windows
            #    lung (centre -600, width 1000)
            #    mediastinum (centre  40, width  400)
            #    bone (centre 700, width 1500)
            lung  = _hu_window_to_unit(arr,  -600, 1000)
            medi  = _hu_window_to_unit(arr,    40,  400)
            bone  = _hu_window_to_unit(arr,   700, 1500)

            channels = [lung, medi, bone]
            
            # optional random channel masking / swapping
            if random.random() < .15: random.shuffle(channels)
            if random.random() < .15:
                i = random.randint(0, 2); channels[i] = np.zeros_like(channels[i])
            arr = np.stack(channels, 0)                    # (3,D,H,W)

        img = torch.from_numpy(arr).float()
        if self.transform is not None: img = self.transform(img)
        tgt = torch.from_numpy(row[self.labels].values.astype(np.float32))
        return img, tgt

# ───────────────────────────────────────────────────────
def _worker_init_fn(worker_id):
    """Worker initialization function to set single-threaded NumPy/BLAS."""
    np.random.seed()
    torch.set_num_threads(1)

def make_loaders(csv: str, labels: List[str], bs: int, nw: int, three_ch: bool,
                 balance: bool, rank: int = 0, world_size: int = 1, data_fraction: float = 1.0):
    # Create transforms once to ensure validation consistency
    train_transform = get_train_transform()
    val_transform = get_val_transform()
    
    train_ds = CTDataset(csv, labels, "train", train_transform, three_ch, data_fraction)
    # For sanity testing, also reduce validation data
    val_fraction = data_fraction if data_fraction < 1.0 else 1.0
    val_ds   = CTDataset(csv, labels, "val",   val_transform,   three_ch, val_fraction)

    # Distributed training setup
    use_distributed = world_size > 1
    
    # Pin memory device for PyTorch 2.1+
    pin_memory_device = f"cuda:{rank}" if torch.cuda.is_available() else None
    
    if use_distributed:
        train_sampler = DistributedSampler(train_ds, num_replicas=world_size, rank=rank, shuffle=True)
        val_sampler = DistributedSampler(val_ds, num_replicas=world_size, rank=rank, shuffle=False)
        
        train_loader = DataLoader(train_ds, bs, sampler=train_sampler,
                                  num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                  persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
        val_loader = DataLoader(val_ds, bs, sampler=val_sampler,
                                num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
    elif balance:
        y = train_ds.df[labels].values
        # sample weights = #neg / #pos  (per class)  → flatten for multilabel
        cls_weights = (y.shape[0] - y.sum(0)) / (y.sum(0) + 1e-6)
        w = (y * cls_weights).sum(1)
        sampler = WeightedRandomSampler(w, num_samples=len(w), replacement=True)
        train_loader = DataLoader(train_ds, bs, sampler=sampler,
                                  num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                  persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
        val_loader = DataLoader(val_ds, bs, shuffle=False,
                                num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
    else:
        train_loader = DataLoader(train_ds, bs, shuffle=True,
                                  num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                  persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
        val_loader = DataLoader(val_ds, bs, shuffle=False,
                                num_workers=nw, pin_memory=True, pin_memory_device=pin_memory_device,
                                persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)

    return train_loader, val_loader

# ───────────────────────────────────────────────────────
def load_backbone(ckpt: str) -> Merlin:
    model = Merlin(ImageEmbedding=True)
    if ckpt and Path(ckpt).is_file():
        sd = torch.load(ckpt, map_location="cpu", weights_only=False)
        model.load_state_dict({k[7:]: v for k, v in sd.items()
                               if k.startswith("visual.")}, strict=False)
        logging.info(f"Loaded SigLIP visual weights ↗ {ckpt}")
    else:
        logging.warning("No pre‑trained weights found – backbone randomly initialised")
    return model

# ───────────────────────────────────────────────────────
def freeze_regex(model: nn.Module, patterns: List[str]):
    """Set requires_grad = False on params matching *any* of the regex patterns."""
    if not patterns: return
    compiled = [re.compile(p) for p in patterns]
    for n, p in model.named_parameters():
        if any(r.search(n) for r in compiled):
            p.requires_grad = False

# ───────────────────────────────────────────────────────
def calculate_crg_score(y_true: np.ndarray, y_pred: np.ndarray, labels: List[str]) -> Dict[str, float]:
    """
    Calculate CRG (Clinically Relevant Grade) score from binary predictions and ground truth.
    
    The CRG score is a clinical evaluation metric that balances true positives against
    false positives and false negatives with clinical weighting:
    
    Formula:
        X = (#labels per exam) * (#exams)  
        A = total positives in ground truth
        r = (X - A) / (2A)
        U = (X - A) / 2
        s = r * TP - r * FN - FP
        CRG = U / (2U - s)
    
    Args:
        y_true: Ground truth binary labels (N, num_classes)
        y_pred: Predicted binary labels (N, num_classes)  
        labels: List of label names
    
    Returns:
        Dictionary containing CRG metrics and intermediate values
    """
    if y_true.shape[0] == 0:
        return {"CRG": 0.0, "TP": 0, "FN": 0, "FP": 0, "X": 0, "A": 0, "r": 0.0, "U": 0.0, "score_s": 0.0}
    
    # Calculate TP, FN, FP across all classes and samples
    TP = int(((y_pred == 1) & (y_true == 1)).sum())
    FN = int(((y_pred == 0) & (y_true == 1)).sum())
    FP = int(((y_pred == 1) & (y_true == 0)).sum())
    
    num_images = y_true.shape[0]
    num_labels = len(labels)
    X = num_labels * num_images  # Total possible predictions
    A = int(y_true.sum())        # Total positive labels in ground truth
    
    # Handle edge case where no positive labels exist
    if A == 0:
        return {"CRG": 0.0, "TP": TP, "FN": FN, "FP": FP, "X": X, "A": A, "r": 0.0, "U": 0.0, "score_s": 0.0}
    
    # CRG calculation
    r = (X - A) / (2 * A)         # Ratio component
    U = (X - A) / 2               # Unnormalized component  
    s = r * TP - r * FN - FP      # Weighted score
    
    # Handle division by zero in final CRG calculation
    denominator = 2 * U - s
    crg = U / denominator if abs(denominator) > 1e-10 else 0.0
    
    # Clamp CRG to reasonable bounds [0, 1] for numerical stability
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
@torch.inference_mode()
def ddp_evaluate(model, loader, loss_fn, device, labels):
    """DDP-aware evaluation that runs on all ranks and reduces metrics."""
    if not dist.is_initialized():
        raise RuntimeError("ddp_evaluate called but distributed training not initialized")
        
    world_size = dist.get_world_size()
    rank = dist.get_rank()
    model.eval()
    
    # Collect all predictions and targets
    all_logits = []
    all_targets = []
    tot_loss = 0.0
    total_samples = 0

    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device)
        with torch.no_grad():
            out = model(x)
            logits = torch.sigmoid(out)
            tot_loss += loss_fn(out, y).item() * x.size(0)
            total_samples += x.size(0)
            
            all_logits.append(logits.cpu())
            all_targets.append(y.cpu())

    # Gather predictions and targets from all ranks
    if all_logits:
        local_logits = torch.cat(all_logits, dim=0)
        local_targets = torch.cat(all_targets, dim=0)
    else:
        local_logits = torch.empty(0, len(labels))
        local_targets = torch.empty(0, len(labels))

    # Move tensors to device before padding
    local_logits = local_logits.to(device, non_blocking=True)
    local_targets = local_targets.to(device, non_blocking=True)

    # Get local sizes and find max size across all ranks for padding
    local_size = torch.tensor([local_logits.shape[0]], device=device)
    all_sizes = [torch.zeros_like(local_size) for _ in range(world_size)]
    dist.all_gather(all_sizes, local_size)
    max_size = max(size.item() for size in all_sizes)
    
    # Pad tensors to max size to ensure same shape across ranks
    if local_logits.shape[0] < max_size:
        padding_logits = torch.zeros(max_size - local_size.item(), len(labels), device=device)
        padding_targets = torch.zeros(max_size - local_size.item(), len(labels), device=device)
        local_logits = torch.cat([local_logits, padding_logits], dim=0)
        local_targets = torch.cat([local_targets, padding_targets], dim=0)
    
    # Gather tensors from all ranks (now all have same shape)
    gathered_logits = [torch.zeros_like(local_logits) for _ in range(world_size)]
    gathered_targets = [torch.zeros_like(local_targets) for _ in range(world_size)]
    
    dist.all_gather(gathered_logits, local_logits)
    dist.all_gather(gathered_targets, local_targets)
    
    # Combine all gathered data (only on rank 0 for efficiency)
    if rank == 0:
        # Remove padding by using actual sizes from each rank
        all_logits_list = []
        all_targets_list = []
        for i, (g_logits, g_targets) in enumerate(zip(gathered_logits, gathered_targets)):
            actual_size = all_sizes[i].item()
            if actual_size > 0:
                all_logits_list.append(g_logits[:actual_size])
                all_targets_list.append(g_targets[:actual_size])
        
        if all_logits_list:
            all_logits_combined = torch.cat(all_logits_list, dim=0)
            all_targets_combined = torch.cat(all_targets_list, dim=0)
        else:
            all_logits_combined = torch.empty(0, len(labels))
            all_targets_combined = torch.empty(0, len(labels))
        
        logits_np = all_logits_combined.cpu().numpy()
        targets_np = all_targets_combined.cpu().numpy()
        preds_np = (logits_np > 0.5).astype(int)
        
        # Calculate metrics with full dataset
        if targets_np.shape[0] > 0:
            # Calculate F1, precision, recall with full data
            macro_f1 = f1_score(targets_np, preds_np, average="macro", zero_division=0)
            micro_f1 = f1_score(targets_np, preds_np, average="micro", zero_division=0)
            
            # Calculate AUC scores
            try:
                macro_auc = roc_auc_score(targets_np, logits_np, average="macro")
            except ValueError:
                macro_auc = 0.5
            
            # Per-class metrics
            pr, rc, f1_per_class, _ = precision_recall_fscore_support(
                targets_np, preds_np, average=None, zero_division=0, labels=range(len(labels)))
            
            auc_scores = []
            for i in range(len(labels)):
                try:
                    if len(np.unique(targets_np[:, i])) > 1:  # Check if both classes are present
                        auc = roc_auc_score(targets_np[:, i], logits_np[:, i])
                    else:
                        auc = 0.5  # Default when only one class present
                    auc_scores.append(auc)
                except ValueError:
                    auc_scores.append(0.5)
            
            # Calculate CRG score
            crg_metrics = calculate_crg_score(targets_np, preds_np, labels)
            
            # Debug information (only on rank 0)
            if rank == 0:
                pos_counts = targets_np.sum(axis=0)
                pred_counts = preds_np.sum(axis=0)
                logging.debug(f"DDP Validation: {targets_np.shape[0]} samples across all ranks")
                logging.debug(f"DDP Positive counts per class: {pos_counts[:5]}...")
                logging.debug(f"DDP Prediction counts per class: {pred_counts[:5]}...")
                logging.debug(f"DDP Macro AUC: {macro_auc:.4f}, AUC scores: {[f'{a:.3f}' for a in auc_scores[:3]]}...")
        else:
            macro_f1 = micro_f1 = macro_auc = 0.0
            pr = rc = f1_per_class = np.zeros(len(labels))
            auc_scores = [0.5] * len(labels)
            crg_metrics = {"CRG": 0.0}
    else:
        # Placeholder values for non-rank-0 processes
        macro_f1 = micro_f1 = macro_auc = 0.0
        pr = rc = f1_per_class = np.zeros(len(labels))
        auc_scores = [0.5] * len(labels)
        crg_metrics = {"CRG": 0.0}

    # Reduce loss across all processes
    total_loss_tensor = torch.tensor(tot_loss, device=device)
    total_samples_tensor = torch.tensor(total_samples, device=device)
    dist.all_reduce(total_loss_tensor, op=dist.ReduceOp.SUM)
    dist.all_reduce(total_samples_tensor, op=dist.ReduceOp.SUM)
    
    avg_loss = total_loss_tensor.item() / max(total_samples_tensor.item(), 1)

    # Broadcast metrics from rank 0 to all ranks
    metrics_tensor = torch.tensor([
        avg_loss, macro_f1, micro_f1, macro_auc, crg_metrics.get("CRG", 0.0)
    ] + list(pr) + list(rc) + list(f1_per_class) + auc_scores, device=device)
    
    dist.broadcast(metrics_tensor, src=0)
    
    # Unpack broadcasted metrics
    metrics_list = metrics_tensor.cpu().tolist()
    avg_loss = metrics_list[0]
    macro_f1 = metrics_list[1] 
    micro_f1 = metrics_list[2]
    macro_auc = metrics_list[3]
    crg_score = metrics_list[4]
    
    start_idx = 5
    pr = metrics_list[start_idx:start_idx + len(labels)]
    start_idx += len(labels)
    rc = metrics_list[start_idx:start_idx + len(labels)]
    start_idx += len(labels)
    f1_per_class = metrics_list[start_idx:start_idx + len(labels)]
    start_idx += len(labels)
    auc_scores = metrics_list[start_idx:start_idx + len(labels)]

    metrics = {
        "val_loss": avg_loss,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "macro_auc": macro_auc,
        "CRG": crg_score
    }
    
    # Add per-class metrics
    for i, name in enumerate(labels):
        metrics[f"{name}_precision"] = pr[i]
        metrics[f"{name}_recall"] = rc[i]
        metrics[f"{name}_f1"] = f1_per_class[i]
        metrics[f"{name}_auc"] = auc_scores[i]

    # Return logits and targets from rank 0 for threshold optimization
    return_logits = logits_np if rank == 0 and 'logits_np' in locals() else None
    return_targets = targets_np if rank == 0 and 'targets_np' in locals() else None
    
    return metrics, return_logits, return_targets

# ───────────────────────────────────────────────────────
@torch.inference_mode()
def search_thresholds(logits: np.ndarray, gts: np.ndarray,
                      step: float = 0.005) -> Tuple[np.ndarray, float]:
    best = np.zeros(logits.shape[1], dtype=np.float32); macro = 0.
    for c in range(logits.shape[1]):
        t_candidates = np.arange(0.05, 0.95, step, dtype=np.float32)
        f1s = [f1_score(gts[:, c], (logits[:, c] > t).astype(int),
                        zero_division=0) for t in t_candidates]
        idx = int(np.argmax(f1s)); best[c] = t_candidates[idx]
    macro = f1_score(gts, logits > best, average="macro", zero_division=0)
    return best, macro

# ───────────────────────────────────────────────────────
def evaluate(model, loader, loss_fn, device, labels,
             thresholds: np.ndarray | float, show_tqdm=False):
    model.eval(); tot_loss, logits, gts = 0., [], []
    iterator = loader if not show_tqdm else tqdm(loader, desc="val", ncols=80)
    with torch.no_grad():
        for x, y in iterator:
            x, y = x.to(device, non_blocking=True), y.to(device)
            out = model(x); tot_loss += loss_fn(out, y).item()
            logits.append(torch.sigmoid(out).cpu()); gts.append(y.cpu())
    
    if logits:
        logits = torch.cat(logits, dim=0).numpy()
        gts = torch.cat(gts, dim=0).numpy()
    else:
        logits = np.array([]).reshape(0, len(labels))
        gts = np.array([]).reshape(0, len(labels))

    if isinstance(thresholds, float):
        preds = (logits > thresholds).astype(int)
    else:
        preds = (logits > thresholds[None, :]).astype(int)

    # Calculate CRG score
    crg_metrics = calculate_crg_score(gts, preds, labels)

    # Calculate macro AUC with proper error handling
    macro_auc = 0.0
    if gts.shape[0] > 0:
        try:
            macro_auc = roc_auc_score(gts, logits, average="macro")
        except ValueError as e:
            logging.warning(f"Could not calculate macro AUC: {e}")
            macro_auc = 0.5

    metrics = {
        "val_loss":  tot_loss / max(len(loader.dataset), 1),
        "macro_f1":  f1_score(gts, preds, average="macro", zero_division=0),
        "micro_f1":  f1_score(gts, preds, average="micro", zero_division=0),
        "macro_auc": macro_auc,
        "CRG": crg_metrics["CRG"]
    }
    
    # per‑class metrics (precision / recall / f1 / auc) with better error handling
    pr, rc, f1, _ = precision_recall_fscore_support(
        gts, preds, average=None, zero_division=0, labels=range(len(labels)))
    
    auc = []
    for i in range(len(labels)):
        if gts.shape[0] > 0:
            try:
                # Check if both classes are present for this label
                unique_vals = np.unique(gts[:, i])
                if len(unique_vals) > 1:
                    auc_score = roc_auc_score(gts[:, i], logits[:, i])
                else:
                    # Only one class present - AUC is undefined, use 0.5
                    auc_score = 0.5
                    if is_main_process():  # Only log from main process
                        logging.debug(f"Only one class present for {labels[i]}: {unique_vals}")
                auc.append(auc_score)
            except ValueError as e:
                if is_main_process():
                    logging.warning(f"AUC calculation failed for {labels[i]}: {e}")
                auc.append(0.5)
        else:
            auc.append(0.0)
    
    for i, name in enumerate(labels):
        metrics[f"{name}_precision"] = pr[i] if i < len(pr) else 0.0
        metrics[f"{name}_recall"]    = rc[i] if i < len(rc) else 0.0
        metrics[f"{name}_f1"]        = f1[i] if i < len(f1) else 0.0
        metrics[f"{name}_auc"]       = auc[i]

    # Add some debugging info for the first evaluation
    if is_main_process() and gts.shape[0] > 0:
        pos_counts = gts.sum(axis=0)
        logging.debug(f"Validation set stats: {gts.shape[0]} samples, positive counts per class: {pos_counts[:5]}...")
        pred_counts = preds.sum(axis=0) 
        logging.debug(f"Prediction stats: positive predictions per class: {pred_counts[:5]}...")
        logit_stats = [f"{logits[:, i].mean():.3f}±{logits[:, i].std():.3f}" for i in range(min(3, len(labels)))]
        logging.debug(f"Logit stats (first 3 classes): {logit_stats}")

    return metrics, logits, gts

# ───────────────────────────────────────────────────────
def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser()
    # ───────── DDP
    parser.add_argument("--local_rank", type=int, default=int(os.getenv("LOCAL_RANK", 0)),
                        help="passed by torchrun; no need to set manually")
    # data / labels
    parser.add_argument("--csv", default="/data/all_ct_with_labels.csv")
    parser.add_argument("--label-columns", nargs="+", default=None)
    parser.add_argument("--three-channel", action="store_true")
    parser.add_argument("--balance-sampler", action="store_true")
    # model
    parser.add_argument("--pretrained", default="/model/3c_siglip/pytorch_model.bin")
    parser.add_argument("--freeze-regex", default="")
    parser.add_argument("--dropout", type=float, default=0.1)
    # optimisation
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lr-backbone-mult", type=float, default=0.1)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--optimizer", choices=["adamw", "sgd"], default="adamw")
    parser.add_argument("--scheduler", choices=["cosine", "plateau", "warmup"], default="cosine")
    parser.add_argument("--warmup-steps", type=int, default=1000)
    parser.add_argument("--grad-accum", type=int, default=1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--freeze-epochs", type=int, default=3, help="Keep backbone frozen for N epochs")
    parser.add_argument("--focal-gamma", type=float, default=2.0, help="Focal loss gamma parameter")
    # regularisation
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--use-ema", action="store_true", default=True)
    parser.add_argument("--use-swa", action="store_true", default=True)
    # ───────── WandB (new)
    parser.add_argument("--wandb-project", default="siglip-ct",
                        help="Weights‑and‑Biases *project* (entity/project)")
    parser.add_argument("--wandb-name", default=None,
                        help="Run name as shown in the WandB UI "
                             "(defaults to output‑folder name)")
    # misc
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--train-data-fraction", type=float, default=1.0,
                        help="Fraction of training data to use for sanity testing")
    parser.add_argument("--debug", action="store_true", 
                        help="Enable debug logging for detailed AUC/metrics information")
    parser.add_argument("--resume", type=str, default="",
                        help="Path to a checkpoint produced by this script "
                             "(`best_crg.pth`, `last_epoch.pth`, …).")
    args = parser.parse_args(argv)

    # world size / rank
    world_size = int(os.getenv("WORLD_SIZE", 1))
    rank       = int(os.getenv("RANK", 0))
    distributed = world_size > 1

    # ensure only rank‑0 prints unless explicitly desired
    log_level = args.log_level.upper()
    if args.debug and rank == 0:
        log_level = "DEBUG"
    
    logging.basicConfig(
        level=getattr(logging, log_level) if rank == 0 else logging.ERROR,
        format=f"%(asctime)s | r{rank} | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # initialise DDP
    if distributed and not dist.is_initialized():
        dist.init_process_group(backend="nccl", init_method="env://")
    
    set_seed(42 + rank)  # Different seed per process
    
    if rank == 0:
        Path(args.output).mkdir(parents=True, exist_ok=True)

    # default labels if not supplied
    if args.label_columns is None:
        args.label_columns = json.loads(Path(ROOT/"default_labels18.json").read_text())
        if rank == 0:
            logging.info(f"Loaded {len(args.label_columns)} default labels")
    else:
        # Handle case where label_columns is passed as a file path or JSON string
        if len(args.label_columns) == 1:
            # Single argument - could be a file path or JSON string
            arg = args.label_columns[0]
            if arg.startswith('['):
                # It's a JSON string
                try:
                    args.label_columns = json.loads(arg)
                    if rank == 0:
                        logging.info(f"Parsed {len(args.label_columns)} labels from JSON string")
                except json.JSONDecodeError as e:
                    if rank == 0:
                        logging.error(f"Failed to parse label_columns as JSON: {e}")
                    raise
            else:
                # It's a file path
                try:
                    args.label_columns = json.loads(Path(arg).read_text())
                    if rank == 0:
                        logging.info(f"Loaded {len(args.label_columns)} labels from file: {arg}")
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    if rank == 0:
                        logging.error(f"Failed to load labels from file {arg}: {e}")
                    raise

    # ───────── initialise WandB (after args, before training loop)
    if WANDB_OK and rank == 0:
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_name or Path(args.output).name,
            config=vars(args),
            dir=args.output,          # run files go next to checkpoints
            reinit=False,             # safer when ↻ in same process
        )
    torch.cuda.set_device(args.local_rank)
    device = torch.device("cuda", args.local_rank)

    # data - 4 workers per GPU instead of per node
    num_workers = 8
    tr_loader, val_loader = make_loaders(
        args.csv, args.label_columns, args.batch_size, num_workers,
        args.three_channel, args.balance_sampler, rank, world_size, args.train_data_fraction)

    # wrap samplers in DistributedSampler
    if distributed:
        if args.balance_sampler:
            warnings.warn("Balance‑sampler disabled in DDP (fallback to uniform shuffle)")
        
        # Pin memory device for PyTorch 2.1+
        pin_memory_device = f"cuda:{args.local_rank}" if torch.cuda.is_available() else None
        
        tr_loader = DataLoader(
            tr_loader.dataset,
            batch_size=args.batch_size,
            sampler=DistributedSampler(tr_loader.dataset, shuffle=True),
            num_workers=num_workers, pin_memory=True, pin_memory_device=pin_memory_device,
            persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)
        val_loader = DataLoader(
            val_loader.dataset,
            batch_size=args.batch_size,
            sampler=DistributedSampler(val_loader.dataset, shuffle=False),
            num_workers=num_workers, pin_memory=True, pin_memory_device=pin_memory_device,
            persistent_workers=True, prefetch_factor=2, worker_init_fn=_worker_init_fn)

    # model
    backbone = load_backbone(args.pretrained)
    model = SigLIPClassifier(backbone, len(args.label_columns), args.dropout).to(device)
    if distributed:
        model = torch.nn.parallel.DistributedDataParallel(
            model, device_ids=[args.local_rank], output_device=args.local_rank,
            find_unused_parameters=True, static_graph=True)  # Required when using frozen parameters

    # Get the actual model for parameter access (unwrap DDP if needed)
    model_module = model.module if distributed else model

    freeze_regex(model_module.backbone, [s for s in args.freeze_regex.split(",") if s])
    # param groups: backbone vs head
    param_groups = [
        {"params": [p for n, p in model_module.named_parameters()
                    if "backbone" in n and p.requires_grad],
         "lr": args.lr * args.lr_backbone_mult},
        {"params": [p for n, p in model_module.named_parameters()
                    if "backbone" not in n and p.requires_grad],
         "lr": args.lr}
    ]
    if args.optimizer == "adamw":
        opt = AdamW(param_groups, weight_decay=args.weight_decay)
    else:
        opt = SGD(param_groups, weight_decay=args.weight_decay, momentum=0.9)

    scaler = GradScaler(enabled=args.amp)

    # scheduler
    total_steps = math.ceil(len(tr_loader) / args.grad_accum) * args.epochs
    if args.scheduler == "warmup":
        sch = get_cosine_schedule_with_warmup(opt, args.warmup_steps, total_steps)
    elif args.scheduler == "cosine":
        sch = CosineAnnealingLR(opt, T_max=args.epochs)
    else:
        sch = ReduceLROnPlateau(opt, mode="max", factor=.5, patience=5)

    # SWA + EMA
    swa_model = AveragedModel(model_module) if args.use_swa else None
    swa_start = int(args.epochs * 0.6)
    swa_scheduler = SWALR(opt, swa_lr=args.lr * 0.05) if args.use_swa else None
    ema = AveragedModel(model_module, avg_fn=None) if args.use_ema else None

    # loss
    pos_w = torch.tensor(
        ( (tr_loader.dataset.df[args.label_columns].values.shape[0]
            - tr_loader.dataset.df[args.label_columns].sum(0).values)
          / (tr_loader.dataset.df[args.label_columns].sum(0).values + 1e-6)),
        dtype=torch.float, device=device)
    criterion = FocalBalancedLoss(pos_w, gamma=args.focal_gamma)
    if rank == 0:
        logging.info(f"Using focal loss with gamma={args.focal_gamma}")

    best_crg, patience = 0., 0
    thresholds = np.full(len(args.label_columns), args.threshold, dtype=np.float32)

    if WANDB_OK and rank == 0:
        wandb.watch(model, log='all', log_freq=100)

    # Resume from checkpoint if provided
    start_epoch = 1  # default = fresh run
    if args.resume and Path(args.resume).is_file():
        checkpoint = torch.load(args.resume,
                                map_location=f"cuda:{args.local_rank}",
                                weights_only=False)
        # 1) model -------------------------------------------------------------
        target = model.module if distributed else model
        
        # Handle DDP checkpoint compatibility
        checkpoint_state = checkpoint["model"]
        model_state = target.state_dict()
        
        # Check if checkpoint has DDP prefixes but current model doesn't (or vice versa)
        checkpoint_has_module = any(k.startswith("module.") for k in checkpoint_state.keys())
        model_has_module = any(k.startswith("module.") for k in model_state.keys())
        
        if checkpoint_has_module and not model_has_module:
            # Remove "module." prefix from checkpoint
            checkpoint_state = {k[7:] if k.startswith("module.") else k: v 
                              for k, v in checkpoint_state.items()}
            if is_main_process():
                logging.info("Removed 'module.' prefixes from checkpoint for compatibility")
        elif not checkpoint_has_module and model_has_module:
            # Add "module." prefix to checkpoint
            checkpoint_state = {f"module.{k}": v for k, v in checkpoint_state.items()}
            if is_main_process():
                logging.info("Added 'module.' prefixes to checkpoint for compatibility")
        
        # Filter out keys that don't match (e.g., different model architecture)
        filtered_state = {}
        for k, v in checkpoint_state.items():
            if k in model_state:
                if v.shape == model_state[k].shape:
                    filtered_state[k] = v
                else:
                    if is_main_process():
                        logging.warning(f"Shape mismatch for {k}: checkpoint {v.shape} vs model {model_state[k].shape}")
            else:
                if is_main_process() and args.debug:
                    logging.debug(f"Skipping unmatched key: {k}")
        
        # Load the compatible state dict
        missing_keys, unexpected_keys = target.load_state_dict(filtered_state, strict=False)
        
        if is_main_process():
            if missing_keys:
                logging.info(f"Missing keys in checkpoint: {len(missing_keys)} (model has new parameters)")
                if args.debug:
                    logging.debug(f"Missing keys: {missing_keys[:10]}{'...' if len(missing_keys) > 10 else ''}")
            if unexpected_keys:
                logging.info(f"Unexpected keys in checkpoint: {len(unexpected_keys)} (checkpoint has extra parameters)")
                if args.debug:
                    logging.debug(f"Unexpected keys: {unexpected_keys[:10]}{'...' if len(unexpected_keys) > 10 else ''}")
            logging.info(f"Successfully loaded {len(filtered_state)} parameters from checkpoint")
        # EMA / SWA (optional) with compatibility handling
        if args.use_ema and "ema" in checkpoint and ema is not None:
            ema_state = checkpoint["ema"]
            # Handle DDP compatibility for EMA
            if checkpoint_has_module and not model_has_module:
                ema_state = {k[7:] if k.startswith("module.") else k: v 
                           for k, v in ema_state.items() if k != "n_averaged"}
            elif not checkpoint_has_module and model_has_module:
                ema_state = {f"module.{k}" if k != "n_averaged" else k: v 
                           for k, v in ema_state.items()}
            ema.load_state_dict(ema_state, strict=False)
            if is_main_process():
                logging.info("Loaded EMA state from checkpoint")
                
        if args.use_swa and "swa" in checkpoint and swa_model is not None:
            swa_state = checkpoint["swa"] 
            # Handle DDP compatibility for SWA
            if checkpoint_has_module and not model_has_module:
                swa_state = {k[7:] if k.startswith("module.") else k: v 
                           for k, v in swa_state.items() if k != "n_averaged"}
            elif not checkpoint_has_module and model_has_module:
                swa_state = {f"module.{k}" if k != "n_averaged" else k: v 
                           for k, v in swa_state.items()}
            swa_model.load_state_dict(swa_state, strict=False)
            if is_main_process():
                logging.info("Loaded SWA state from checkpoint")

        # 2) optimisation ------------------------------------------------------
        opt.load_state_dict(checkpoint["opt"])
        sch.load_state_dict(checkpoint["sch"])
        scaler.load_state_dict(checkpoint["scaler"])

        # 3) bookkeeping -------------------------------------------------------
        thresholds = checkpoint.get("thresholds", thresholds)
        best_crg   = checkpoint.get("best_crg", 0.0)
        patience   = checkpoint.get("patience", 0)

        start_epoch = checkpoint["epoch"] + 1    # resume *after* the stored epoch
        if is_main_process():
            logging.info(f"▶ Resumed from {args.resume} @ epoch {start_epoch}")
    else:
        if is_main_process() and args.resume:
            logging.warning(f"--resume={args.resume} not found. Starting fresh.")

    # training loop ────────────────────────────────────
    for epoch in range(start_epoch, args.epochs + 1):
        if distributed and isinstance(tr_loader.sampler, DistributedSampler):
            tr_loader.sampler.set_epoch(epoch)
        
        # (1) freeze schedule
        if epoch == args.freeze_epochs + 1:
            model_module = model.module if distributed else model
            for p in model_module.backbone.parameters(): p.requires_grad = True
            if rank == 0:
                logging.info("Backbone unfrozen")

        model.train(); running = 0.
        
        # Only show progress bar on main process
        if rank == 0:
            pbar = tqdm(enumerate(tr_loader, 1), total=len(tr_loader), ncols=120,
                        desc=f"epoch[{epoch:03d}]")
        else:
            pbar = enumerate(tr_loader, 1)
        
        opt.zero_grad()

        for step, (x, y) in pbar:
            x, y = x.to(device, non_blocking=True), y.to(device)
            with autocast(enabled=args.amp):
                loss = criterion(model(x), y) / args.grad_accum
            scaler.scale(loss).backward()
            running += loss.item() * args.grad_accum

            if step % args.grad_accum == 0 or step == len(tr_loader):
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                scaler.step(opt); scaler.update(); opt.zero_grad()
                if ema: ema.update_parameters(model.module if distributed else model)
                if swa_model and epoch >= swa_start: swa_model.update_parameters(model.module if distributed else model)
            
            if rank == 0 and hasattr(pbar, 'set_postfix'):
                pbar.set_postfix(loss=f"{running/step:.4f}")

        # scheduler step
        if args.scheduler == "plateau":
            # will step later after val_metrics computed
            pass
        elif args.scheduler == "warmup":
            sch.step()
        else:
            sch.step()

        # (2) validation — distributed across all ranks
        eval_model = ema if ema else (model.module if distributed else model)
        
        # Enable debug logging for first few epochs
        if rank == 0 and epoch <= 3 and args.debug:
            logging.info(f"Running validation for epoch {epoch} with debug info enabled...")
        
        if distributed:
            # Use distributed evaluation on all ranks
            val_metrics, distributed_logits, distributed_gts = ddp_evaluate(eval_model, val_loader, criterion, device, args.label_columns)
            
            # Only do threshold search on rank 0 using gathered data
            if rank == 0 and distributed_logits is not None:
                thresholds, macro_at_opt = search_thresholds(distributed_logits, distributed_gts)
                val_metrics["macro_f1_opt"] = macro_at_opt
                
            # Broadcast thresholds from rank 0 to all ranks
            thresholds_tensor = torch.from_numpy(thresholds).float().to(device)
            dist.broadcast(thresholds_tensor, src=0)
            thresholds = thresholds_tensor.cpu().numpy()
        else:
            # Single GPU evaluation
            val_metrics, val_logits, val_gts = evaluate(eval_model, val_loader, criterion, device,
                                                        args.label_columns, thresholds)
            thresholds, macro_at_opt = search_thresholds(val_logits, val_gts)
            val_metrics["macro_f1_opt"] = macro_at_opt

        # (3) SWA scheduler step
        if swa_model and epoch >= swa_start and swa_scheduler:
            swa_scheduler.step()

        # Scheduler step (only rank 0 for plateau, all ranks for others)
        if args.scheduler == "plateau" and rank == 0:
            sch.step(val_metrics["CRG"])

        # Logging and tracking (only on rank 0)
        if rank == 0:
            # Core metrics for concise logging
            core_metrics = {k: v for k, v in val_metrics.items() 
                           if k in ["val_loss", "macro_f1", "macro_auc", "CRG", "macro_f1_opt"]}
            msg = " | ".join(f"{k}:{v:.4f}" if isinstance(v, float) else f"{k}:{v}"
                             for k, v in core_metrics.items())
            logging.info(f"Epoch {epoch:03d} – {msg}")
            
            # Detailed per-class logging
            f1_scores = [f"{k.replace('_f1', '')}:{v:.3f}" for k, v in val_metrics.items() 
                        if k.endswith("_f1") and not k.startswith("macro") and not k.startswith("micro")]
            auc_scores = [f"{k.replace('_auc', '')}:{v:.3f}" for k, v in val_metrics.items() 
                         if k.endswith("_auc") and not k.startswith("macro")]
            
            if f1_scores:
                logging.info(f"Per-class F1: {' | '.join(f1_scores)}")
            if auc_scores:
                logging.info(f"Per-class AUC: {' | '.join(auc_scores)}")

        if WANDB_OK and rank == 0:
            # Log all metrics to wandb
            wandb_metrics = {"epoch": epoch, **val_metrics}
            
            # Create summary metrics for easy tracking
            wandb_metrics["summary/CRG_score"] = val_metrics.get("CRG", 0.0)
            wandb_metrics["summary/macro_F1"] = val_metrics.get("macro_f1", 0.0) 
            wandb_metrics["summary/macro_AUC"] = val_metrics.get("macro_auc", 0.0)
            
            # Group per-class metrics for better organization
            for label in args.label_columns:
                if f"{label}_f1" in val_metrics:
                    wandb_metrics[f"class_f1/{label}"] = val_metrics[f"{label}_f1"]
                if f"{label}_auc" in val_metrics:
                    wandb_metrics[f"class_auc/{label}"] = val_metrics[f"{label}_auc"]
                if f"{label}_precision" in val_metrics:
                    wandb_metrics[f"class_precision/{label}"] = val_metrics[f"{label}_precision"]
                if f"{label}_recall" in val_metrics:
                    wandb_metrics[f"class_recall/{label}"] = val_metrics[f"{label}_recall"]
            
            wandb.log(wandb_metrics)

        # Checkpoint saving and early stopping (only on rank 0)
        early_stop = False
        if rank == 0:
            current_crg = val_metrics.get("CRG", 0.0)
            
            # Save best CRG checkpoint if improved
            if current_crg > best_crg:
                best_crg, patience = current_crg, 0
                
                # Save best CRG checkpoint
                best_path = Path(args.output) / "best_crg.pth"
                ckpt = {
                    "epoch":       epoch,
                    "model":       eval_model.state_dict(),
                    "opt":         opt.state_dict(),
                    "sch":         sch.state_dict(),
                    "scaler":      scaler.state_dict(),
                    "thresholds":  thresholds,
                    "best_crg":    best_crg,
                    "patience":    patience,
                    "metrics":     val_metrics,
                }
                if ema: ckpt["ema"] = ema.state_dict()
                if swa_model: ckpt["swa"] = swa_model.state_dict()
                torch.save(ckpt, best_path)
                logging.info(f"New best CRG: {current_crg:.4f} at epoch {epoch}")
            else:
                patience += 1
                if patience >= args.patience:
                    logging.info("Early stopping ↑ patience exhausted")
                    early_stop = True
            
            # Always save last epoch checkpoint (every epoch for resumability)
            last_path = Path(args.output) / "last_epoch.pth"
            ckpt = {
                "epoch":       epoch,
                "model":       eval_model.state_dict(),
                "opt":         opt.state_dict(),
                "sch":         sch.state_dict(),
                "scaler":      scaler.state_dict(),
                "thresholds":  thresholds,
                "best_crg":    best_crg,
                "patience":    patience,
                "metrics":     val_metrics,
            }
            if ema: ckpt["ema"] = ema.state_dict()
            if swa_model: ckpt["swa"] = swa_model.state_dict()
            torch.save(ckpt, last_path)
            logging.info(f"Saved checkpoint: {last_path} (epoch {epoch})")
        
        # Synchronize early stopping decision across all ranks
        if distributed:
            early_stop_tensor = torch.tensor(int(early_stop), device=device)
            dist.broadcast(early_stop_tensor, src=0)
            early_stop = bool(early_stop_tensor.item())
            
        if early_stop:
            break

    # (6) SWA batchnorm update + final eval
    if rank == 0 and swa_model:
        torch.optim.swa_utils.update_bn(tr_loader, swa_model, device=device)
        final_model = swa_model
    else:
        final_model = ema if ema else (model.module if distributed else model)

    if rank == 0:
        final_metrics, *_ = evaluate(final_model, val_loader,
                                     criterion, device, args.label_columns, thresholds)
        
        # Enhanced final metrics logging
        logging.info("="*80)
        logging.info("FINAL EVALUATION RESULTS")
        logging.info("="*80)
        
        # Core metrics
        core_metrics = ["val_loss", "macro_f1", "micro_f1", "macro_auc", "CRG"]
        for metric in core_metrics:
            if metric in final_metrics:
                logging.info(f"  {metric:>15s}: {final_metrics[metric]:.4f}")
        
        logging.info("-"*40)
        logging.info("Per-class F1 Scores:")
        for label in args.label_columns:
            f1_key = f"{label}_f1"
            if f1_key in final_metrics:
                logging.info(f"  {label:>25s}: {final_metrics[f1_key]:.4f}")
        
        logging.info("-"*40) 
        logging.info("Per-class AUC Scores:")
        for label in args.label_columns:
            auc_key = f"{label}_auc"
            if auc_key in final_metrics:
                logging.info(f"  {label:>25s}: {final_metrics[auc_key]:.4f}")
        
        logging.info("="*80)
        
        if WANDB_OK:
            # Add final summary metrics to wandb
            final_summary = {
                "final/CRG_score": final_metrics.get("CRG", 0.0),
                "final/macro_F1": final_metrics.get("macro_f1", 0.0),
                "final/macro_AUC": final_metrics.get("macro_auc", 0.0),
                "final/micro_F1": final_metrics.get("micro_f1", 0.0),
            }
            
            # Add per-class final metrics
            for label in args.label_columns:
                if f"{label}_f1" in final_metrics:
                    final_summary[f"final_class_f1/{label}"] = final_metrics[f"{label}_f1"]
                if f"{label}_auc" in final_metrics:
                    final_summary[f"final_class_auc/{label}"] = final_metrics[f"{label}_auc"]
            
            wandb.summary.update({**final_metrics, **final_summary})
            wandb.finish()

    # clean up
    if distributed:
        dist.barrier()
        dist.destroy_process_group()

if __name__ == "__main__": main()