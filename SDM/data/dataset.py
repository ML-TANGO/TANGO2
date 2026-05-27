"""
CT-JEPA v2 Data Module
========================
CT volume loading, HU windowing, TotalSegmentator region mask computation,
dataset and dataloader creation.

Adapted for the actual data format:
- CSV: cepa/final_ct2.csv with object_id, findings, split columns
- NPZ: /data/preprocessed/{object_id} with ct (1,192,256,256) float32
  (pre-windowed to [-1000, 2000] HU) and totalseg (1,192,256,256) uint16
"""

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
import os
import zipfile
from typing import Optional, Dict, Tuple, List


# ---------------------------------------------------------------------------
# HU Windowing
# ---------------------------------------------------------------------------

WINDOW_PARAMS = {
    0: {"center": 450,  "width": 2100},   # lung: -600 to 1500
    1: {"center": 195,  "width": 310},    # mediastinal: 40 to 350
    2: {"center": 0,    "width": 2000},   # general: -1000 to 1000
    3: {"center": 1500, "width": 5000},   # full: -1000 to 4000 (TODO: int16)
}

WINDOW_NAMES = {0: "lung", 1: "med", 2: "general", 3: "full"}


def apply_window(volume_hu: np.ndarray, window_id: int) -> np.ndarray:
    """Apply HU windowing: clamp + scale to [0,1].

    Expects float input (pre-windowed to [-1000, 2000] HU range).
    """
    params = WINDOW_PARAMS[window_id]
    wl = params["center"]
    ww = params["width"]
    low = wl - ww / 2
    high = wl + ww / 2
    windowed = (volume_hu.astype(np.float32) - low) / (high - low)
    windowed = np.clip(windowed, 0.0, 1.0)
    return windowed


# ---------------------------------------------------------------------------
# TotalSegmentator -> Region Masks at Stage-2 Resolution
# ---------------------------------------------------------------------------

REGION_GROUPS = {
    0:  "background",
    1:  "lung_left_upper",
    2:  "lung_left_lower",
    3:  "lung_right_upper",
    4:  "lung_right_middle",
    5:  "lung_right_lower",
    6:  "heart",
    7:  "aorta",
    8:  "pulmonary_artery",
    9:  "trachea_bronchi",
    10: "esophagus",
    11: "thyroid",
    12: "spine_thoracic",
    13: "ribs_left",
    14: "ribs_right",
    15: "sternum",
    16: "scapula_left",
    17: "scapula_right",
    18: "clavicle_left",
    19: "clavicle_right",
    20: "liver_dome",
    21: "stomach",
    22: "mediastinal_fat",
    23: "chest_wall_muscle",
    24: "pleura",
}

# Mapping from TotalSeg label IDs to coarse groups.
# NOTE: Incomplete — only maps 10 of 117+ TotalSeg labels. Unmapped labels are
# silently ignored (their regions will be empty). Expand this mapping for full
# anatomy coverage based on your TotalSeg version.
TOTALSEG_TO_REGION = {}
for i in range(1, 6):
    TOTALSEG_TO_REGION[i] = i
for i in range(10, 15):
    TOTALSEG_TO_REGION[i] = 6


def compute_region_masks_s2(totalseg: np.ndarray,
                            num_regions: int = 25,
                            grid_s2: Tuple[int, int, int] = (12, 16, 16),
                            ) -> torch.Tensor:
    """Compute soft region masks at Stage-2 resolution from TotalSeg."""
    D_full, H_full, W_full = totalseg.shape
    D2, H2, W2 = grid_s2
    N_s2 = D2 * H2 * W2
    pool_kernel = (D_full // D2, H_full // H2, W_full // W2)

    region_masks = torch.zeros(num_regions, N_s2)

    for region_id in range(num_regions):
        if region_id == 0:
            binary = (totalseg == 0).astype(np.float32)
        else:
            labels = [k for k, v in TOTALSEG_TO_REGION.items() if v == region_id]
            if not labels:
                continue
            binary = np.zeros_like(totalseg, dtype=np.float32)
            for lid in labels:
                binary += (totalseg == lid).astype(np.float32)
            binary = np.clip(binary, 0, 1)

        binary_tensor = torch.from_numpy(binary).float().unsqueeze(0).unsqueeze(0)
        pooled = F.avg_pool3d(binary_tensor, kernel_size=pool_kernel)
        region_masks[region_id] = pooled.flatten()

    return region_masks


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class CTJEPADataset(Dataset):
    """
    Dataset for CT-JEPA v2 training.

    Reads from:
    - CSV with columns: object_id (NPZ filename), findings (report text), split
    - NPZ files at data_root/{object_id} with keys: ct (1,D,H,W float, pre-windowed
      to [-1000, 2000] HU), totalseg (1,D,H,W uint16)
    """

    def __init__(self, csv_path: str, data_root: str,
                 img_col: str = "object_id",
                 text_col: str = "findings",
                 split_col: str = "split",
                 split: str = "train",
                 has_reports: bool = True,
                 max_text_len: int = 256):
        super().__init__()
        self.data_root = data_root
        self.has_reports = has_reports
        self.max_text_len = max_text_len

        df = pd.read_csv(csv_path)

        # Filter by split if column exists
        if split_col and split_col in df.columns and split is not None:
            df = df[df[split_col] == split].reset_index(drop=True)

        img_paths = (data_root + os.sep + df[img_col].astype(str)).tolist()

        if has_reports and text_col in df.columns:
            texts = df[text_col].where(df[text_col].notna() & (df[text_col].astype(str).str.strip() != ''))
            texts = texts.astype(object).where(texts.notna(), None).tolist()
        else:
            texts = [None] * len(df)

        self.samples = [{"img_path": p, "report_text": t} for p, t in zip(img_paths, texts)]

    def __len__(self):
        return len(self.samples)

    def _load_sample(self, idx: int) -> Dict[str, torch.Tensor]:
        """Load a single sample. May raise on corrupted files."""
        sample = self.samples[idx]

        data = np.load(sample['img_path'])
        ct_hu = data['ct']  # (1, D, H, W) or (D, H, W) float

        if ct_hu.ndim == 4:
            ct_hu = ct_hu[0]

        totalseg = data.get('totalseg', None)
        if totalseg is not None and totalseg.ndim == 4:
            totalseg = totalseg[0]

        # Random window selection
        window_id = np.random.randint(0, len(WINDOW_PARAMS))

        # Apply windowing
        volume = apply_window(ct_hu, window_id)
        volume = torch.from_numpy(volume).float().unsqueeze(0)  # (1, D, H, W)

        output = {
            'volume': volume,
            'window_id': torch.tensor(window_id, dtype=torch.long),
        }

        # TotalSeg region masks
        if totalseg is not None:
            output['region_masks_s2'] = compute_region_masks_s2(totalseg)
        else:
            output['region_masks_s2'] = None

        # Text (raw string, tokenized by Chest2Vec in model)
        output['report_text'] = sample['report_text'] if self.has_reports else None

        return output

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                return self._load_sample(idx)
            except (ValueError, OSError, EOFError, zipfile.BadZipFile) as e:
                # Corrupted/truncated NPZ file — try a random different sample
                if attempt < max_retries - 1:
                    idx = np.random.randint(0, len(self.samples))
                else:
                    raise RuntimeError(
                        f"Failed to load any sample after {max_retries} retries. "
                        f"Last error: {e}"
                    )


# ---------------------------------------------------------------------------
# Multi-label Probe Dataset (for linear probe evaluation)
# ---------------------------------------------------------------------------

# Columns to exclude when auto-detecting label columns
_NON_LABEL_COLUMNS = {
    'object_id', 'findings', 'split', 'impression', 'refined_findings',
    'indication', 'Unnamed: 0', 'Lungs', 'Airways & Trachea', 'Pleura',
    'Mediastinum & Hila', 'Cardiovascular', 'Chest Wall', 'Bones / Spine',
    'Upper abdomen', 'Lower neck', 'Breast & Axilla', 'Others',
    'Lungs + Pleura', 'Thoracic MSK',
}


def detect_label_columns(df: pd.DataFrame) -> List[str]:
    """Find multi-label columns with values in {-1, 0, 1}."""
    cols = []
    for c in df.columns:
        if c in _NON_LABEL_COLUMNS:
            continue
        if df[c].dtype in ['int64', 'float64']:
            unique = set(df[c].dropna().unique())
            if unique and unique.issubset({-1, 0, 1}):
                cols.append(c)
    return cols


class MultiLabelProbeDataset(Dataset):
    """
    Dataset for multi-label linear probe evaluation.

    Auto-detects binary label columns from the CSV ({-1, 0, 1} values).
    Treats -1 as 0 (uncertain → negative).
    """

    def __init__(self, csv_path: str, data_root: str,
                 img_col: str = "object_id",
                 split_col: str = "split",
                 split: str = "val"):
        super().__init__()
        self.data_root = data_root

        df = pd.read_csv(csv_path)
        if split_col and split_col in df.columns and split is not None:
            df = df[df[split_col] == split].reset_index(drop=True)

        self.label_columns = detect_label_columns(df)
        self.num_classes = len(self.label_columns)

        # Build labels matrix: (N, num_classes), treat -1 as 0
        labels = df[self.label_columns].fillna(0).values.astype(np.float32)
        labels[labels < 0] = 0.0
        self.labels = labels

        self.img_paths = (data_root + os.sep + df[img_col].astype(str)).tolist()

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx: int) -> Dict:
        try:
            data = np.load(self.img_paths[idx])
        except (ValueError, OSError, EOFError, zipfile.BadZipFile):
            idx = np.random.randint(0, len(self.img_paths))
            data = np.load(self.img_paths[idx])

        ct_hu = data['ct']
        if ct_hu.ndim == 4:
            ct_hu = ct_hu[0]

        totalseg = data.get('totalseg', None)
        if totalseg is not None and totalseg.ndim == 4:
            totalseg = totalseg[0]

        window_id = np.random.randint(0, len(WINDOW_PARAMS))
        volume = apply_window(ct_hu, window_id)
        volume = torch.from_numpy(volume).float().unsqueeze(0)

        output = {
            'volume': volume,
            'window_id': torch.tensor(window_id, dtype=torch.long),
            'label': torch.from_numpy(self.labels[idx]),
        }

        if totalseg is not None:
            output['region_masks_s2'] = compute_region_masks_s2(totalseg)
        else:
            output['region_masks_s2'] = None

        return output


def probe_collate_fn(batch: list) -> dict:
    """Collation for probe dataset (no text fields)."""
    collated = {
        'volume': torch.stack([b['volume'] for b in batch]),
        'window_id': torch.stack([b['window_id'] for b in batch]),
        'label': torch.stack([b['label'] for b in batch]),
    }
    masks = [b['region_masks_s2'] for b in batch]
    if all(m is not None for m in masks):
        collated['region_masks_s2'] = torch.stack(masks)
    else:
        collated['region_masks_s2'] = None
    return collated


# ---------------------------------------------------------------------------
# Collation
# ---------------------------------------------------------------------------

def collate_fn(batch: list) -> dict:
    """Custom collation handling optional fields."""
    B = len(batch)

    collated = {
        'volume': torch.stack([b['volume'] for b in batch]),
        'window_id': torch.stack([b['window_id'] for b in batch]),
    }

    # Region masks — stack only if ALL samples have them
    masks = [b['region_masks_s2'] for b in batch]
    if all(m is not None for m in masks):
        collated['region_masks_s2'] = torch.stack(masks)
    else:
        collated['region_masks_s2'] = None

    # Text (raw strings, tokenized by Chest2Vec in model)
    collated['texts'] = [b['report_text'] for b in batch]

    return collated


# ---------------------------------------------------------------------------
# DataLoader Creation
# ---------------------------------------------------------------------------

def create_dataloader(config, is_train: bool = True, split: str = "train",
                      sampler=None, dataset=None) -> DataLoader:
    """Create training or validation dataloader from config.

    Args:
        sampler: Optional DistributedSampler for multi-GPU training.
                 When provided, shuffle is disabled (sampler handles it).
        dataset: Optional pre-built dataset. If None, creates one from config.
    """
    if dataset is None:
        dataset = CTJEPADataset(
            csv_path=config.data.csv_path,
            data_root=config.data.data_root,
            img_col=config.data.img_col,
            text_col=config.data.text_col,
            split_col=config.data.split_col,
            split=split,
            has_reports=config.text.use_text,
            max_text_len=config.text.text_max_tokens,
        )

    nw = config.training.num_workers
    use_persistent = nw > 0

    return DataLoader(
        dataset,
        batch_size=config.training.batch_size,
        shuffle=(is_train and sampler is None),
        sampler=sampler,
        num_workers=nw,
        collate_fn=collate_fn,
        pin_memory=True,
        drop_last=is_train,
        persistent_workers=use_persistent,
        timeout=600 if nw > 0 else 0,
        prefetch_factor=config.training.prefetch_factor if nw > 0 else None,
    )
