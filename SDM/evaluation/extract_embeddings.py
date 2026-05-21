"""
Extract g_img embeddings from a CT-JEPA v2 checkpoint.

Loads the EMA target encoder, runs forward_full (no masking) on each sample,
and saves {ids, embeddings} as train.pt / val.pt.

Usage:
    python extract_embeddings.py \
        --checkpoint ./runs/ctjepa_v2/checkpoints/checkpoint_latest.pt \
        --csv_path ./final_ct2.csv \
        --npz_root /data/preprocessed \
        --output_dir ./ct/cepa_embs \
        --batch_size 8 --amp
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
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm

from ..config import CTJEPAConfig
from ..models.encoder import HierarchicalEncoder
from ..data.dataset import apply_window, compute_region_masks_s2


# ============================================================
# Lightweight dataset (no text, no masking — just volumes)
# ============================================================

class EmbeddingExtractionDataset(Dataset):
    """Load CT volumes for embedding extraction (no masking, no text)."""

    def __init__(self, csv_path: str, data_root: str,
                 img_col: str = "object_id",
                 split_col: str = "split",
                 split: str = "train",
                 window_id: int = 0):
        super().__init__()
        self.data_root = data_root
        self.window_id = window_id

        df = pd.read_csv(csv_path)
        if split_col and split_col in df.columns and split is not None:
            df = df[df[split_col] == split].reset_index(drop=True)

        self.ids = df[img_col].astype(str).tolist()
        self.img_paths = [os.path.join(data_root, oid) for oid in self.ids]

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx: int) -> Dict:
        try:
            data = np.load(self.img_paths[idx])
        except (ValueError, OSError, EOFError) as e:
            print(f"[WARN] Failed to load {self.img_paths[idx]}: {e}")
            # Return zeros — will be filtered out later
            return {
                "id": self.ids[idx],
                "volume": torch.zeros(1, 192, 256, 256, dtype=torch.float32),
                "window_id": torch.tensor(self.window_id, dtype=torch.long),
                "region_masks_s2": torch.zeros(25, 3072),
                "valid": False,
            }

        ct_hu = data["ct"]
        if ct_hu.ndim == 4:
            ct_hu = ct_hu[0]

        totalseg = data.get("totalseg", None)
        if totalseg is not None and totalseg.ndim == 4:
            totalseg = totalseg[0]

        volume = apply_window(ct_hu, self.window_id)
        volume = torch.from_numpy(volume).float().unsqueeze(0)

        region_masks = (
            compute_region_masks_s2(totalseg)
            if totalseg is not None
            else torch.zeros(25, 3072)
        )

        return {
            "id": self.ids[idx],
            "volume": volume,
            "window_id": torch.tensor(self.window_id, dtype=torch.long),
            "region_masks_s2": region_masks,
            "valid": True,
        }


def collate_fn(batch: list) -> dict:
    return {
        "ids": [b["id"] for b in batch],
        "volume": torch.stack([b["volume"] for b in batch]),
        "window_id": torch.stack([b["window_id"] for b in batch]),
        "region_masks_s2": torch.stack([b["region_masks_s2"] for b in batch]),
        "valid": [b["valid"] for b in batch],
    }


# ============================================================
# Load encoder from checkpoint
# ============================================================

def load_target_encoder(checkpoint_path: str, config: CTJEPAConfig,
                        device: torch.device) -> HierarchicalEncoder:
    """Load the EMA target encoder weights from a CTJEPA checkpoint."""
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state_dict = ckpt["model_state_dict"]

    # Extract target_encoder.* keys
    prefix = "target_encoder."
    target_sd = {}
    for k, v in state_dict.items():
        if k.startswith(prefix):
            target_sd[k[len(prefix):]] = v

    if not target_sd:
        raise ValueError(
            f"No target_encoder keys found in checkpoint. "
            f"Available prefixes: {set(k.split('.')[0] for k in state_dict.keys())}"
        )

    encoder = HierarchicalEncoder(config)
    encoder.load_state_dict(target_sd, strict=True)
    encoder = encoder.to(device).eval()

    print(f"Loaded target encoder from epoch {ckpt.get('epoch', '?')}, "
          f"step {ckpt.get('step', '?')}")
    return encoder


# ============================================================
# Extraction
# ============================================================

@torch.no_grad()
def extract_split(
    encoder: HierarchicalEncoder,
    dataset: EmbeddingExtractionDataset,
    batch_size: int,
    device: torch.device,
    amp: bool = True,
    num_workers: int = 4,
    embed_type: str = "s3_mean",
) -> Tuple[List[str], torch.Tensor]:
    """Extract embeddings for all samples in the dataset.

    Args:
        embed_type: Which embedding to extract:
            "g_img"   - AttentionalReadout global embedding (512-d)
            "s3_mean" - Mean-pooled S3 token features (512-d)
            "s2_mean" - Mean-pooled S2 token features (256-d)
            "concat"  - Concatenation of s3_mean + g_img (1024-d)
    """
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_fn,
        pin_memory=True,
        drop_last=False,
    )

    all_ids = []
    all_embs = []

    for batch in tqdm(loader, desc=f"Extracting ({embed_type})"):
        volume = batch["volume"].to(device, non_blocking=True)
        window_id = batch["window_id"].to(device, non_blocking=True)
        region_masks = batch["region_masks_s2"].to(device, non_blocking=True)
        valid = batch["valid"]

        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp):
            out = encoder.forward_full(volume, window_id, region_masks)

        if embed_type == "g_img":
            emb = out["g_img"]
        elif embed_type == "s3_mean":
            emb = out["s3_features"].mean(dim=1)  # (B, N_s3, D) -> (B, D)
        elif embed_type == "s2_mean":
            emb = out["s2_features"].mean(dim=1)  # (B, N_s2, D) -> (B, D)
        elif embed_type == "concat":
            s3_mean = out["s3_features"].mean(dim=1)
            emb = torch.cat([s3_mean, out["g_img"]], dim=-1)
        else:
            raise ValueError(f"Unknown embed_type: {embed_type}")

        # Filter out invalid samples
        for i, (sample_id, is_valid) in enumerate(zip(batch["ids"], valid)):
            if is_valid:
                all_ids.append(sample_id)
                all_embs.append(emb[i].float().cpu())

    embeddings = torch.stack(all_embs, dim=0)
    return all_ids, embeddings


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Extract CT-JEPA v2 embeddings")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to CTJEPA checkpoint .pt file")
    parser.add_argument("--csv_path", type=str, required=True,
                        help="Path to CSV with object_id and split columns")
    parser.add_argument("--npz_root", type=str, required=True,
                        help="Root directory containing NPZ files")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Directory to save train.pt and val.pt")
    parser.add_argument("--splits", nargs="+", default=["train", "val"],
                        help="Splits to extract (default: train val)")
    parser.add_argument("--config", type=str, default="base",
                        choices=["small", "base", "large"])
    parser.add_argument("--embed_type", type=str, default="s3_mean",
                        choices=["g_img", "s3_mean", "s2_mean", "concat"],
                        help="Embedding type (default: s3_mean)")
    parser.add_argument("--window_id", type=int, default=0,
                        help="HU window to use (0=med, 1=wide, 2=all). Default: 0")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--amp", action="store_true", help="Use mixed precision")
    parser.add_argument("--no_zscore", action="store_true",
                        help="Skip z-score normalization (default: z-score using train stats)")
    parser.add_argument("--device", type=str, default="cuda:0")
    args = parser.parse_args()

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Build config
    config = CTJEPAConfig()
    config.model.variant = args.config

    # Load encoder
    encoder = load_target_encoder(args.checkpoint, config, device)
    print(f"Encoder dim_s3 (embedding dim): {config.model.dim_s3}")

    os.makedirs(args.output_dir, exist_ok=True)

    # Extract all splits first
    all_splits = {}
    for split in args.splits:
        print(f"\n{'='*50}")
        print(f"Extracting split: {split}")
        print(f"{'='*50}")

        dataset = EmbeddingExtractionDataset(
            csv_path=args.csv_path,
            data_root=args.npz_root,
            split=split,
            window_id=args.window_id,
        )
        print(f"  Samples: {len(dataset)}")

        ids, embeddings = extract_split(
            encoder, dataset,
            batch_size=args.batch_size,
            device=device,
            amp=args.amp,
            num_workers=args.num_workers,
            embed_type=args.embed_type,
        )
        all_splits[split] = (ids, embeddings)

    # Z-score normalization using train statistics
    if not args.no_zscore and "train" in all_splits:
        train_embs = all_splits["train"][1]
        train_mean = train_embs.mean(dim=0)
        train_std = train_embs.std(dim=0).clamp(min=1e-8)
        print(f"\nZ-scoring embeddings (train mean norm={train_mean.norm():.2f}, "
              f"mean per-dim std={train_std.mean():.6f})")

        for split in all_splits:
            ids, embs = all_splits[split]
            all_splits[split] = (ids, (embs - train_mean) / train_std)
    elif not args.no_zscore:
        print("\nWARNING: --no_zscore not set but 'train' not in splits; skipping z-score")

    # Save
    for split, (ids, embeddings) in all_splits.items():
        out_path = os.path.join(args.output_dir, f"{split}.pt")
        torch.save({"ids": ids, "embeddings": embeddings}, out_path)
        print(f"  Saved {split}: {len(ids)} embeddings ({embeddings.shape}) -> {out_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
