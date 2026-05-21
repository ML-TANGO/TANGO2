import os
import sys
import math
import json
import ast
import random
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from torch.utils.data import Dataset, DataLoader, DistributedSampler

import wandb

# Add Merlin to path for model imports
_merlin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Merlin")
if _merlin_dir not in sys.path:
    sys.path.insert(0, _merlin_dir)

# ---- your chest2vec helpers (must be importable) ----
from chest2vec import (
    Chest2Vec,
    encode_with_eos_ids,
    get_last_hidden_state,
    last_token_pool,
    build_qwen_query,
)
from chest2vec.eval_stage3_section import (
    LatentDictSectionPooler,
    load_pooler,
)

# =========================================================
# Sectioned mode constants
# =========================================================
# Pooler section order (must match pretrained checkpoint)
ANATOMY_COLUMNS = [
    "Lungs + Pleura",
    "Airways & Trachea",
    "Mediastinum & Hila",
    "Cardiovascular",
    "Thoracic MSK",
    "Upper abdomen",
    "Lower neck",
    "Others",
    "impression",
]

# Sections valid for sampling (have TotalSeg labels)
SAMPLABLE_SECTIONS = [s for s in ANATOMY_COLUMNS if s != "impression"]

# Name mapping: section.json uses "Lung + Pleura" (singular),
# CSV/pooler uses "Lungs + Pleura" (plural)
SECTION_JSON_TO_CSV = {"Lung + Pleura": "Lungs + Pleura"}
CSV_TO_SECTION_JSON = {v: k for k, v in SECTION_JSON_TO_CSV.items()}

# Per-section instructions for direct encoding mode
SECTION_INSTRUCTIONS = {
    "Lungs + Pleura": "Retrieve the chest CT that is similar to the given report about the lungs and pleura.",
    "Airways & Trachea": "Retrieve the chest CT that is similar to the given report about the airways and trachea.",
    "Mediastinum & Hila": "Retrieve the chest CT that is similar to the given report about the mediastinum and hila.",
    "Cardiovascular": "Retrieve the chest CT that is similar to the given report about the cardiovascular system.",
    "Thoracic MSK": "Retrieve the chest CT that is similar to the given report about the thoracic bones and chest wall.",
    "Upper abdomen": "Retrieve the chest CT that is similar to the given report about the upper abdomen.",
    "Lower neck": "Retrieve the chest CT that is similar to the given report about the lower neck.",
    "Others": "Retrieve the chest CT that is similar to the given report about other miscellaneous findings.",
}


def load_section_label_map(section_json_path: str) -> Dict[str, List[int]]:
    """Load section.json and return CSV-name -> label_indices mapping."""
    with open(section_json_path, "r") as f:
        data = json.load(f)
    mapping = {}
    for json_name, info in data["sections"].items():
        csv_name = SECTION_JSON_TO_CSV.get(json_name, json_name)
        mapping[csv_name] = info["label_indices"]
    return mapping


# =========================================================
# DDP utilities
# =========================================================
def setup_distributed():
    if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
        rank = int(os.environ["RANK"])
        world_size = int(os.environ["WORLD_SIZE"])
        local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    else:
        rank, world_size, local_rank = 0, 1, 0

    if world_size > 1:
        if torch.cuda.is_available():
            backend = "nccl"
            torch.cuda.set_device(local_rank)
        else:
            backend = "gloo"
        dist.init_process_group(backend=backend)

    return rank, world_size, local_rank


def cleanup_distributed():
    if dist.is_initialized():
        dist.destroy_process_group()


def is_dist() -> bool:
    return dist.is_available() and dist.is_initialized() and dist.get_world_size() > 1


def get_rank() -> int:
    return dist.get_rank() if is_dist() else 0


def get_world_size() -> int:
    return dist.get_world_size() if is_dist() else 1


def rank0_print(*args, **kwargs):
    if get_rank() == 0:
        print(*args, **kwargs)


def check_lora_gradients(model: nn.Module) -> float:
    """Compute total L2 norm of LoRA gradients (similar to clip_grad_norm)."""
    total_norm_sq = 0.0
    for name, param in model.named_parameters():
        if "lora_" in name.lower() and param.requires_grad:
            if param.grad is not None:
                total_norm_sq += param.grad.data.norm(2).item() ** 2
    return total_norm_sq ** 0.5  # sqrt of sum of squares


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def all_reduce_mean(x: torch.Tensor) -> torch.Tensor:
    if not is_dist():
        return x
    y = x.clone()
    dist.all_reduce(y, op=dist.ReduceOp.SUM)
    y /= get_world_size()
    return y


def _sync_gradients(optimizer):
    """All-reduce gradients across DDP ranks via a single coalesced operation.

    This is needed because the training code calls model.module.encode_*() directly,
    bypassing DDP's forward hooks. Without this, each rank trains independently.
    """
    if not dist.is_initialized() or dist.get_world_size() <= 1:
        return

    grads = []
    for group in optimizer.param_groups:
        for p in group['params']:
            if p.grad is not None:
                grads.append(p.grad)
    if not grads:
        return

    # Flatten all gradients into a single contiguous buffer
    flat = torch._utils._flatten_dense_tensors(grads)
    dist.all_reduce(flat, op=dist.ReduceOp.AVG)
    # Unflatten back into individual gradient tensors
    for g, synced in zip(grads, torch._utils._unflatten_dense_tensors(flat, grads)):
        g.copy_(synced)


def gather_variable_first_dim_no_grad(x: torch.Tensor) -> torch.Tensor:
    """
    all_gather for variable first-dim (no grad).
    Pads to max size then trims.
    """
    if not is_dist():
        return x

    device = x.device
    world = get_world_size()

    n_local = torch.tensor([x.shape[0]], device=device, dtype=torch.long)
    n_list = [torch.zeros_like(n_local) for _ in range(world)]
    dist.all_gather(n_list, n_local)
    ns = [int(t.item()) for t in n_list]
    n_max = max(ns)

    if x.shape[0] < n_max:
        pad_shape = (n_max - x.shape[0],) + x.shape[1:]
        pad = torch.zeros(pad_shape, device=device, dtype=x.dtype)
        x_pad = torch.cat([x, pad], dim=0)
    else:
        x_pad = x

    out_list = [torch.zeros_like(x_pad) for _ in range(world)]
    dist.all_gather(out_list, x_pad)

    chunks = [out_list[r][: ns[r]] for r in range(world)]
    return torch.cat(chunks, dim=0)


# =========================================================
# Data: CSV + NPZ (ct only)
# =========================================================
def load_ct_from_npz(npz_path: Path, mask_type: str) -> torch.Tensor:
    npz_path = Path(npz_path)
    with np.load(npz_path, allow_pickle=False) as z:
        keys = list(z.keys())
        if "ct" in keys:
            ct = z["ct"]
        elif "image" in keys:
            ct = z["image"]
        else:
            raise KeyError(f"No CT key found in {npz_path}. Keys={keys}")
        
        if mask_type == "repeat":
            mask = torch.from_numpy(z["ct"])
        elif mask_type == "ones":
            mask = torch.ones(ct.shape)
        else:
            if "totalseg" in keys:
                mask = torch.from_numpy(z["totalseg"])
            else:
                raise KeyError(f"No TotalSegmentator key found in {npz_path}. Key='totalseg'")

            if mask_type == "mask_to_ones":
                mask = (mask != 0).int()
            elif mask_type == "all":
                pass
            else:
                raise KeyError(f"No Mask Type key found. You can use repeat/ones/mask_to_nes/all, but you use {mask_type}")

    # Min-max normalize to [0, 1]
    ct_min, ct_max = ct.min(), ct.max()
    if ct_max - ct_min > 0:
        ct = (ct - ct_min) / (ct_max - ct_min)
    else:
        ct = np.zeros_like(ct)

    if not (ct.ndim == 4 and ct.shape[0] == 1):
        raise ValueError(f"Expected ct shape (1,D,H,W), got {ct.shape} in {npz_path}")

    if not (mask.ndim == 4 and mask.shape[0] == 1):
        raise ValueError(f"Expected mask shape (1,D,H,W), got {ct.shape} in {npz_path}")

    return torch.from_numpy(ct.astype(np.float32)), mask


class CTTextDataset(Dataset):
    def __init__(
        self,
        csv_path: str,
        npz_root: str,
        mask_type: str,
        split: str,  # "train" or "val"
        text_primary: str = "refined_findings",
        text_fallback: str = "findings",
        object_id_col: str = "object_id",
        split_col: str = "split",
    ):
        df = pd.read_csv(csv_path)

        for col in [text_primary, text_fallback, object_id_col, split_col]:
            if col not in df.columns:
                raise ValueError(f"CSV missing column: {col}")

        df = df[df[split_col].astype(str) == split].reset_index(drop=True)
        if len(df) == 0:
            raise ValueError(f"No rows for split='{split}' in {csv_path}")

        # pick text: refined_findings if present else findings
        t = df[text_primary].where(df[text_primary].notna(), df[text_fallback])
        t = t.fillna("").astype(str)
        keep = t.str.strip().str.len() > 0
        df = df[keep].reset_index(drop=True)
        t = t[keep].reset_index(drop=True)

        root = Path(npz_root)

        paths = []
        obj_ids = df[object_id_col].astype(str).tolist()
        for oid in obj_ids:
            fname = oid if oid.endswith(".npz") else oid + ".npz"
            p = root / fname
            if not p.exists():
                raise FileNotFoundError(f"Missing NPZ: {p}")
            paths.append(p)

        self.paths = paths
        self.mask_type = mask_type
        self.texts = t.tolist()

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx: int) -> Tuple[int, torch.Tensor, str]:
        ct, mask = load_ct_from_npz(self.paths[idx], mask_type=self.mask_type)  # (1,D,H,W)
        # 3-channel for Merlin: [original_ct, repeated_ct, mask_or_ct]
        return idx, torch.cat([ct, ct, mask], dim=0), self.texts[idx]


@dataclass
class Batch:
    idx: torch.Tensor           # [B]
    ct: torch.Tensor            # [B,3,D,H,W]
    texts: List[str]            # len=B


def collate_fn(examples: List[Tuple[int, torch.Tensor, str]]) -> Batch:
    idxs, cts, texts = zip(*examples)
    idx = torch.tensor(idxs, dtype=torch.long)
    ct = torch.stack(cts, dim=0)  # [B,3,D,H,W]
    return Batch(idx=idx, ct=ct, texts=list(texts))


# =========================================================
# Sectioned data: CSV + NPZ (ct + totalseg)
# =========================================================
@dataclass
class SectionedBatch:
    idx: torch.Tensor                   # [B]
    ct: torch.Tensor                    # [B,1,D,H,W] normalized CT
    totalseg: torch.Tensor              # [B,1,D,H,W] integer segmentation labels
    global_texts: List[str]             # len=B, full report texts
    section_names: List[List[str]]      # len=B, each inner list has 2 section names
    section_texts: List[List[str]]      # len=B, each inner list has 2 section texts (for direct mode)


class SectionedCTTextDataset(Dataset):
    def __init__(
        self,
        csv_path: str,
        npz_root: str,
        section_json_path: str,
        split: str,
        text_primary: str = "refined_findings",
        text_fallback: str = "findings",
        object_id_col: str = "object_id",
        split_col: str = "split",
        min_sections: int = 2,
        exclude_sections: Optional[List[str]] = None,
    ):
        df = pd.read_csv(csv_path)

        for col in [text_primary, text_fallback, object_id_col, split_col, "exist_section"]:
            if col not in df.columns:
                raise ValueError(f"CSV missing column: {col}")

        df = df[df[split_col].astype(str) == split].reset_index(drop=True)
        if len(df) == 0:
            raise ValueError(f"No rows for split='{split}' in {csv_path}")

        # Pick text: refined_findings if present else findings
        t = df[text_primary].where(df[text_primary].notna(), df[text_fallback])
        t = t.fillna("").astype(str)
        keep = t.str.strip().str.len() > 0
        df = df[keep].reset_index(drop=True)
        t = t[keep].reset_index(drop=True)

        # Parse exist_section and filter to samplable sections
        section_label_map = load_section_label_map(section_json_path)
        exclude = set(exclude_sections) if exclude_sections else set()
        samplable_set = (set(SAMPLABLE_SECTIONS) & set(section_label_map.keys())) - exclude
        if exclude:
            rank0_print(f"Excluding sections from sampling: {sorted(exclude)}")
        rank0_print(f"Samplable sections ({len(samplable_set)}): {sorted(samplable_set)}")

        parsed_sections = []
        for raw in df["exist_section"]:
            try:
                secs = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                secs = []
            valid = [s for s in secs if s in samplable_set]
            parsed_sections.append(valid)

        # Filter samples with >= min_sections
        keep2 = [len(ps) >= min_sections for ps in parsed_sections]
        df = df[keep2].reset_index(drop=True)
        t = t[keep2].reset_index(drop=True)
        parsed_sections = [ps for ps, k in zip(parsed_sections, keep2) if k]

        # Verify NPZ files exist
        root = Path(npz_root)
        paths = []
        obj_ids = df[object_id_col].astype(str).tolist()
        for oid in obj_ids:
            fname = oid if oid.endswith(".npz") else oid + ".npz"
            p = root / fname
            if not p.exists():
                raise FileNotFoundError(f"Missing NPZ: {p}")
            paths.append(p)

        self.paths = paths
        self.texts = t.tolist()
        self.parsed_sections = parsed_sections
        # Keep section text columns for direct mode
        self._section_text_df = df[[c for c in SAMPLABLE_SECTIONS if c in df.columns]].copy()

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx: int):
        npz_path = self.paths[idx]
        with np.load(npz_path, allow_pickle=False) as z:
            keys = list(z.keys())
            if "ct" in keys:
                ct = z["ct"]
            elif "image" in keys:
                ct = z["image"]
            else:
                raise KeyError(f"No CT key found in {npz_path}. Keys={keys}")
            if "totalseg" not in keys:
                raise KeyError(f"No totalseg key in {npz_path}. Sectioned mode requires it.")
            totalseg = z["totalseg"]

        # Min-max normalize CT to [0, 1]
        ct_min, ct_max = ct.min(), ct.max()
        if ct_max - ct_min > 0:
            ct = (ct - ct_min) / (ct_max - ct_min)
        else:
            ct = np.zeros_like(ct)

        if not (ct.ndim == 4 and ct.shape[0] == 1):
            raise ValueError(f"Expected ct shape (1,D,H,W), got {ct.shape} in {npz_path}")

        ct_tensor = torch.from_numpy(ct.astype(np.float32))           # [1,D,H,W]
        totalseg_tensor = torch.from_numpy(totalseg.astype(np.int32))  # [1,D,H,W]

        # Random sample 2 sections
        available = self.parsed_sections[idx]
        if len(available) >= 2:
            chosen = random.sample(available, 2)
        else:
            chosen = [available[0], available[0]]

        # Get per-section texts from CSV columns
        section_texts = []
        for sec_name in chosen:
            if sec_name in self._section_text_df.columns:
                txt = str(self._section_text_df.iloc[idx][sec_name])
                if txt.strip() == "" or txt == "nan":
                    txt = "No findings."
            else:
                txt = "No findings."
            section_texts.append(txt)

        return (idx, ct_tensor, totalseg_tensor, self.texts[idx], chosen, section_texts)


def sectioned_collate_fn(examples) -> SectionedBatch:
    idxs, cts, totsegs, texts, section_names_list, section_texts_list = zip(*examples)
    idx = torch.tensor(idxs, dtype=torch.long)
    ct = torch.stack(cts, dim=0)            # [B,1,D,H,W]
    totalseg = torch.stack(totsegs, dim=0)  # [B,1,D,H,W]
    return SectionedBatch(
        idx=idx,
        ct=ct,
        totalseg=totalseg,
        global_texts=list(texts),
        section_names=list(section_names_list),
        section_texts=list(section_texts_list),
    )


def build_sectioned_image_variants(
    ct: torch.Tensor,                       # [B,1,D,H,W]
    totalseg: torch.Tensor,                 # [B,1,D,H,W]
    section_names: List[List[str]],         # B lists, each with 2 section names
    section_label_map: Dict[str, List[int]],
    mask_channel_mode: str = "masked_ct",   # "masked_ct" = ct*mask, "binary" = raw mask
) -> torch.Tensor:
    """
    Build 3 image variants per sample: [global, local1, local2].
    Returns [B*3, 3, D, H, W] ordered as [g0,l1_0,l2_0, g1,l1_1,l2_1, ...].
    """
    use_masked_ct = (mask_channel_mode == "masked_ct")
    B = ct.shape[0]
    variants = []

    for i in range(B):
        ct_i = ct[i]       # [1,D,H,W]
        seg_i = totalseg[i]  # [1,D,H,W]

        # Global: [ct, ct, ct] for masked_ct mode, [ct, ct, ones] for binary mode
        if use_masked_ct:
            variants.append(torch.cat([ct_i, ct_i, ct_i], dim=0))
        else:
            variants.append(torch.cat([ct_i, ct_i, torch.ones_like(ct_i)], dim=0))

        # Local1 and Local2
        for sec_name in section_names[i]:
            csv_name = sec_name
            json_name = CSV_TO_SECTION_JSON.get(csv_name, csv_name)
            label_indices = section_label_map.get(csv_name) or section_label_map.get(json_name)

            if label_indices:
                idx_tensor = torch.tensor(label_indices, device=seg_i.device, dtype=seg_i.dtype)
                mask = torch.isin(seg_i, idx_tensor).float()
            else:
                mask = torch.ones_like(ct_i)

            ch3 = ct_i * mask if use_masked_ct else mask
            variants.append(torch.cat([ct_i, ct_i, ch3], dim=0))

    return torch.stack(variants, dim=0)  # [B*3, 3, D, H, W]


# =========================================================
# Vision encoder: Merlin (I3ResNet backbone)
# =========================================================
class MerlinVisionEncoder(nn.Module):
    """
    Wrapper for Merlin's pretrained I3ResNet (inflated ResNet-152) encoder.
    Expects 3-channel input: [original_ct, repeated_ct, mask_or_ct].
    Outputs 2048-dim features from backbone avgpool.
    """
    MERLIN_SPATIAL_SIZE = (160, 224, 224)  # (D, H, W) expected by Merlin

    def __init__(self, freeze: bool = False):
        super().__init__()

        from merlin.models.load import Merlin as MerlinLoader
        rank0_print("Loading pretrained Merlin encoder...")
        merlin = MerlinLoader()

        # Extract the I3ResNet backbone from the image encoder
        self.i3_resnet = merlin.model.encode_image.i3_resnet
        # Use ImageEmbedding mode: returns 2048-dim avgpool features
        # (skips the contrastive_head and classifier which we don't need)
        self.i3_resnet.ImageEmbedding = True

        # Free the full Merlin model (text encoder, etc.)
        del merlin

        if freeze:
            for p in self.parameters():
                p.requires_grad = False
            rank0_print("Merlin vision encoder: frozen")

    def forward(self, ct: torch.Tensor) -> torch.Tensor:
        """
        Args:
            ct: [B, 3, D, H, W] float tensor
                ch0 = original CT, ch1 = repeated CT, ch2 = mask or repeated CT
        Returns:
            [B, 2048] feature tensor
        """
        # Resize to Merlin's expected spatial dimensions
        if ct.shape[2:] != self.MERLIN_SPATIAL_SIZE:
            ct = F.interpolate(
                ct.float(),
                size=self.MERLIN_SPATIAL_SIZE,
                mode="trilinear",
                align_corners=False,
            )

        # I3ResNet expects [B, C, H, W, D] — it permutes internally to [B, C, D, H, W]
        ct = ct.permute(0, 1, 3, 4, 2)  # [B,3,D,H,W] -> [B,3,H,W,D]

        features = self.i3_resnet(ct)  # [B, 2048]
        return features

    def forward_spatial(self, ct: torch.Tensor) -> torch.Tensor:
        """
        Return spatial feature maps [B, 2048, D', H', W'] before avgpool.
        Used by VisionAttentionPooler for section-aware spatial pooling.
        """
        if ct.shape[2:] != self.MERLIN_SPATIAL_SIZE:
            ct = F.interpolate(
                ct.float(),
                size=self.MERLIN_SPATIAL_SIZE,
                mode="trilinear",
                align_corners=False,
            )

        # I3ResNet expects [B, C, H, W, D] — it permutes internally to [B, C, D, H, W]
        ct = ct.permute(0, 1, 3, 4, 2)  # [B,3,D,H,W] -> [B,3,H,W,D]

        # Replicate I3ResNet.forward() up to layer4 (skip avgpool)
        net = self.i3_resnet
        x = ct.permute(0, 1, 4, 2, 3)  # [B,C,H,W,D] -> [B,C,D,H,W]
        if x.shape[1] == 1:
            x = torch.cat((x, x, x), dim=1)
        x = net.conv1(x)
        x = net.bn1(x)
        x = net.relu(x)
        x = net.maxpool(x)
        x = torch.utils.checkpoint.checkpoint(net.layer1, x)
        x = torch.utils.checkpoint.checkpoint(net.layer2, x)
        x = torch.utils.checkpoint.checkpoint(net.layer3, x)
        x = torch.utils.checkpoint.checkpoint(net.layer4, x)
        return x  # [B, 2048, D', H', W']


# =========================================================
# Vision Attention Pooler (learned, adapted from LatentDictSectionPooler)
# =========================================================
class VisionAttentionPooler(nn.Module):
    """
    Learned attention pooler over spatial feature maps from the vision backbone.
    Replaces AdaptiveAvgPool3d for section-aware spatial pooling.

    Architecture (adapted from LatentDictSectionPooler in stage3_section.py):
      - K dictionary latents attend over spatial positions
      - Condition latents on global (avgpool) feature
      - Merge K latents → 1 pooled vector
      - MLP residual + output projection
    """
    def __init__(
        self,
        hidden_size: int,
        num_latents: int = 8,
        mlp_hidden: Optional[int] = None,
        dropout: float = 0.1,
        cond_on_global: bool = True,
        output_dim: Optional[int] = None,
    ):
        super().__init__()
        self.H = int(hidden_size)
        self.K = int(num_latents)
        self.cond_on_global = bool(cond_on_global)
        self.output_dim = int(output_dim) if output_dim else self.H

        self.ln_x = nn.LayerNorm(self.H)
        self.ln_d = nn.LayerNorm(self.H)

        self.dict_latents = nn.Parameter(torch.empty(self.K, self.H))
        nn.init.normal_(self.dict_latents, mean=0.0, std=0.02)

        self.global_proj = nn.Linear(self.H, self.H, bias=False) if self.cond_on_global else None

        self.merge_q = nn.Parameter(torch.empty(self.H))
        nn.init.normal_(self.merge_q, mean=0.0, std=0.02)

        self.scale_tok = 1.0 / math.sqrt(self.H)
        self.scale_merge = 1.0 / math.sqrt(self.H)
        self.drop = nn.Dropout(float(dropout)) if dropout and dropout > 0 else nn.Identity()

        mlp_hidden = int(mlp_hidden) if (mlp_hidden and mlp_hidden > 0) else self.H
        self.mlp = nn.Sequential(
            nn.Linear(self.H, mlp_hidden, bias=False),
            nn.GELU(),
            nn.Linear(mlp_hidden, self.H, bias=False),
        )

        self.out_proj = (
            nn.Linear(self.H, self.output_dim, bias=False)
            if self.output_dim != self.H
            else nn.Identity()
        )

    def forward(
        self,
        spatial_feats: torch.Tensor,
        attention_mask: torch.Tensor,
        global_feat: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Args:
            spatial_feats: [B, N, H] flattened spatial features
            attention_mask: [B, N] binary mask (1=attend, 0=ignore)
            global_feat: [B, H] optional global conditioning (avgpool features)
        Returns:
            [B, output_dim] pooled features (NOT L2-normalized)
        """
        B, N, H = spatial_feats.shape
        orig_dtype = spatial_feats.dtype

        x = self.ln_x(spatial_feats).float()    # [B, N, H]
        D = self.ln_d(self.dict_latents).float()  # [K, H]

        if self.cond_on_global and global_feat is not None:
            cond = torch.tanh(self.global_proj(global_feat).float())  # [B, H]
            Q = D.unsqueeze(0) + cond.unsqueeze(1)  # [B, K, H]
        else:
            Q = D.unsqueeze(0).expand(B, -1, -1)  # [B, K, H]

        # Cross-attention: latents attend over spatial positions
        scores = torch.einsum("bnh,bkh->bkn", x, Q) * self.scale_tok  # [B, K, N]
        scores = scores.masked_fill(attention_mask[:, None, :] == 0, -1e4)
        attn = torch.softmax(scores, dim=-1)
        attn = self.drop(attn)

        pooled_lat = torch.einsum("bkn,bnh->bkh", attn, x)  # [B, K, H]

        # Merge K → 1
        merge_scores = torch.einsum("bkh,h->bk", pooled_lat, self.merge_q.float()) * self.scale_merge
        merge_attn = torch.softmax(merge_scores, dim=-1)
        merge_attn = self.drop(merge_attn)
        pooled = torch.einsum("bkh,bk->bh", pooled_lat, merge_attn)  # [B, H]

        # MLP residual + output projection
        y = pooled + self.mlp(pooled.to(orig_dtype)).float()
        y = self.out_proj(y.to(orig_dtype))
        return y.to(orig_dtype)


# =========================================================
# SigLIP sigmoid loss with learnable logit_scale + logit_bias
# (DDP-safe gather with grad)
# =========================================================
class GatherLayer(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        if not is_dist():
            return x
        world_size = dist.get_world_size()
        rank = dist.get_rank()
        output = [torch.zeros_like(x) for _ in range(world_size)]
        dist.all_gather(output, x)
        ctx.rank = rank
        ctx.batch_size = x.shape[0]
        return torch.cat(output, dim=0)

    @staticmethod
    def backward(ctx, grad_output):
        if not is_dist():
            return grad_output
        start = ctx.rank * ctx.batch_size
        end = start + ctx.batch_size
        return grad_output[start:end]


def gather_features(features: torch.Tensor, gather: bool = True) -> torch.Tensor:
    if not gather or not is_dist():
        return features
    return GatherLayer.apply(features)


class SigLIPLoss(nn.Module):
    """
    SigLIP/SigLIP2-style sigmoid contrastive loss:
      BCEWithLogits over all (image,text) pairs with diagonal positives.
    Includes learnable logit_scale (log-space) and logit_bias.
    """
    def __init__(self, init_logit_scale: Optional[float] = None, init_logit_bias: float = -10.0):
        super().__init__()
        if init_logit_scale is None:
            # common CLIP default ~ log(1/0.07)
            init_logit_scale = float(np.log(1 / 0.07))
        self.logit_scale = nn.Parameter(torch.tensor(init_logit_scale, dtype=torch.float32))
        self.logit_bias = nn.Parameter(torch.tensor(init_logit_bias, dtype=torch.float32))

    def forward(self, image_features: torch.Tensor, text_features: torch.Tensor, gather_distributed: bool = True):
        image_features = F.normalize(image_features.float(), dim=-1)
        text_features = F.normalize(text_features.float(), dim=-1)

        local_bs = image_features.shape[0]

        if gather_distributed and is_dist():
            all_image = gather_features(image_features, gather=True)
            all_text = gather_features(text_features, gather=True)
            rank = dist.get_rank()
        else:
            all_image = image_features
            all_text = text_features
            rank = 0

        global_bs = all_image.shape[0]

        # clamp logit_scale in log-space (exp stability)
        scale = self.logit_scale.clamp(max=math.log(100.0)).exp()

        logits_i2t = scale * (image_features @ all_text.t()) + self.logit_bias
        logits_t2i = scale * (text_features @ all_image.t()) + self.logit_bias

        # optional clamp for sigmoid stability
        logits_i2t = logits_i2t.clamp(min=-100.0, max=100.0)
        logits_t2i = logits_t2i.clamp(min=-100.0, max=100.0)

        # labels: positives at offset diagonal
        labels = torch.zeros((local_bs, global_bs), device=image_features.device, dtype=torch.float32)
        offset = rank * local_bs
        pos = offset + torch.arange(local_bs, device=image_features.device)
        labels.scatter_(1, pos.unsqueeze(1), 1.0)

        loss_i2t = F.binary_cross_entropy_with_logits(logits_i2t, labels, reduction="mean")
        loss_t2i = F.binary_cross_entropy_with_logits(logits_t2i, labels, reduction="mean")
        return 0.5 * (loss_i2t + loss_t2i)


class SectionedSigLIPLoss(nn.Module):
    """
    Combined local + global SigLIP contrastive loss for sectioned training.

    Local:  Per-sample 3x3 SigLIP (3 img variants x 3 txt variants, diagonal positive).
    Global: Batch-wide (B*3)x(B*3) SigLIP with DDP gather, diagonal positive.
    """
    def __init__(
        self,
        init_logit_scale: Optional[float] = None,
        init_logit_bias: float = -10.0,
        local_weight: float = 1.0,
        global_weight: float = 1.0,
        global_only_weight: float = 1.0,
    ):
        super().__init__()
        if init_logit_scale is None:
            init_logit_scale = float(np.log(1 / 0.07))
        self.logit_scale = nn.Parameter(torch.tensor(init_logit_scale, dtype=torch.float32))
        self.logit_bias = nn.Parameter(torch.tensor(init_logit_bias, dtype=torch.float32))
        self.local_weight = local_weight
        self.global_weight = global_weight
        self.global_only_weight = global_only_weight

    def _siglip_bce(self, query: torch.Tensor, bank: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        scale = self.logit_scale.clamp(max=math.log(100.0)).exp()
        logits = (scale * (query @ bank.t()) + self.logit_bias).clamp(-100.0, 100.0)
        return F.binary_cross_entropy_with_logits(logits, labels, reduction="mean")

    def forward(
        self,
        image_features: torch.Tensor,   # [B*3, D]
        text_features: torch.Tensor,    # [B*3, D]
        gather_distributed: bool = True,
    ):
        image_features = F.normalize(image_features.float(), dim=-1)
        text_features = F.normalize(text_features.float(), dim=-1)

        local_bs = image_features.shape[0]  # B*3
        B = local_bs // 3

        # ---- LOCAL LOSS: per-sample 3x3 contrastive ----
        local_labels = torch.eye(3, device=image_features.device, dtype=torch.float32)
        local_loss = torch.tensor(0.0, device=image_features.device)
        for i in range(B):
            s, e = i * 3, i * 3 + 3
            img_i = image_features[s:e]   # [3, D]
            txt_i = text_features[s:e]    # [3, D]
            l_i2t = self._siglip_bce(img_i, txt_i, local_labels)
            l_t2i = self._siglip_bce(txt_i, img_i, local_labels)
            local_loss = local_loss + 0.5 * (l_i2t + l_t2i)
        local_loss = local_loss / max(B, 1)

        # ---- GLOBAL LOSS: (B*3) x (global_B*3) contrastive ----
        if gather_distributed and is_dist():
            all_image = gather_features(image_features, gather=True)
            all_text = gather_features(text_features, gather=True)
            rank = dist.get_rank()
        else:
            all_image = image_features
            all_text = text_features
            rank = 0

        global_bs = all_image.shape[0]
        labels = torch.zeros((local_bs, global_bs), device=image_features.device, dtype=torch.float32)
        offset = rank * local_bs
        pos = offset + torch.arange(local_bs, device=image_features.device)
        labels.scatter_(1, pos.unsqueeze(1), 1.0)

        g_i2t = self._siglip_bce(image_features, all_text, labels)
        g_t2i = self._siglip_bce(text_features, all_image, labels)
        global_loss = 0.5 * (g_i2t + g_t2i)

        # ---- GLOBAL-ONLY LOSS: B x B contrastive on global variants only ----
        img_global = image_features[0::3].contiguous()   # [B, D]
        txt_global = text_features[0::3].contiguous()    # [B, D]
        local_bs_go = img_global.shape[0]

        if gather_distributed and is_dist():
            all_img_go = gather_features(img_global, gather=True)
            all_txt_go = gather_features(txt_global, gather=True)
            rank_go = dist.get_rank()
        else:
            all_img_go = img_global
            all_txt_go = txt_global
            rank_go = 0

        global_bs_go = all_img_go.shape[0]
        labels_go = torch.zeros((local_bs_go, global_bs_go), device=image_features.device, dtype=torch.float32)
        offset_go = rank_go * local_bs_go
        pos_go = offset_go + torch.arange(local_bs_go, device=image_features.device)
        labels_go.scatter_(1, pos_go.unsqueeze(1), 1.0)

        go_i2t = self._siglip_bce(img_global, all_txt_go, labels_go)
        go_t2i = self._siglip_bce(txt_global, all_img_go, labels_go)
        global_only_loss = 0.5 * (go_i2t + go_t2i)

        total = self.local_weight * local_loss + self.global_weight * global_loss + self.global_only_weight * global_only_loss
        return total, local_loss.detach(), global_loss.detach(), global_only_loss.detach()


# =========================================================
# Merlin + Chest2Vec model
# =========================================================
class MerlinWithChest2Vec(nn.Module):
    def __init__(
        self,
        vision: MerlinVisionEncoder,
        vision_dim: int,
        embed_dim: int,
        chest2vec_path: str,
        chest2vec_device: str,
        default_instruction: str,
        freeze_text: bool = False,
        full_finetune_text: bool = False,
        use_text_projection: bool = True,
        use_visual_projection: bool = True,
        chest2vec_use_4bit: bool = False,
        force_flash_attention_2: bool = False,
    ):
        super().__init__()
        self.vision = vision
        self.vision_dim = vision_dim
        self.embed_dim = embed_dim

        self.default_instruction = default_instruction
        self.freeze_text = freeze_text
        self.full_finetune_text = full_finetune_text

        # ---- load Chest2Vec wrapper ----
        self._chest2vec_wrapper = Chest2Vec.from_pretrained(
            chest2vec_path,
            device=chest2vec_device,
            use_4bit=chest2vec_use_4bit,
            force_flash_attention_2=force_flash_attention_2,
        )
        # Register the underlying PeftModel so params are visible to PyTorch/DDP
        self.text_encoder = self._chest2vec_wrapper.model
        self.text_tokenizer = self._chest2vec_wrapper.tokenizer
        self.text_device = self._chest2vec_wrapper.device

        # Infer text hidden dim once (cheap)
        with torch.no_grad():
            out = self._chest2vec_wrapper.embed_instruction_query(
                [self.default_instruction],
                ["dummy"],
                max_len=32,
                batch_size=1,
                return_cpu_float32=False,
            )
            text_dim = int(out.embedding.shape[-1])
        self.text_dim = text_dim

        # projections
        if use_visual_projection and vision_dim != embed_dim:
            self.visual_projection = nn.Linear(vision_dim, embed_dim, bias=False)
            nn.init.normal_(self.visual_projection.weight, std=vision_dim ** -0.5)
        else:
            self.visual_projection = nn.Identity()

        if use_text_projection and text_dim != embed_dim:
            self.text_projection = nn.Linear(text_dim, embed_dim, bias=True)
            nn.init.normal_(self.text_projection.weight, std=text_dim ** -0.5)
        else:
            self.text_projection = nn.Identity()

        # ---- configure Chest2Vec trainability ----
        self._configure_text_trainability()

        # loss module inside model so DDP sync works for scale/bias
        self.loss_fn = SigLIPLoss(init_logit_scale=None, init_logit_bias=-10.0)

    def _configure_text_trainability(self):
        # If freeze_text: freeze all
        if self.freeze_text:
            self.text_encoder.eval()
            for p in self.text_encoder.parameters():
                p.requires_grad = False
            rank0_print("Chest2Vec: frozen (no grad)")
            return

        # Else: train either full model or LoRA-only
        self.text_encoder.train()

        if self.full_finetune_text:
            for p in self.text_encoder.parameters():
                p.requires_grad = True
            rank0_print("Chest2Vec: FULL fine-tune enabled")
        else:
            # LoRA-only: enable grads only for lora_ params
            lora_params = 0
            total = 0
            lora_param_names = []
            for n, p in self.text_encoder.named_parameters():
                total += p.numel()
                if "lora_" in n.lower():
                    p.requires_grad = True
                    lora_params += p.numel()
                    lora_param_names.append(n)
                else:
                    p.requires_grad = False
            rank0_print(f"Chest2Vec: LoRA-only enabled ({lora_params:,} params trainable out of {total:,})")
            if lora_param_names:
                rank0_print(f"  LoRA parameters ({len(lora_param_names)}): {lora_param_names[:5]}{'...' if len(lora_param_names) > 5 else ''}")

    def encode_image(self, ct: torch.Tensor) -> torch.Tensor:
        x = self.vision(ct)                 # [B, vision_dim]
        x = self.visual_projection(x)       # [B, embed_dim]
        x = F.normalize(x, dim=-1)
        return x

    def _encode_text_train(self, instructions: List[str], texts: List[str], max_len: int) -> torch.Tensor:
        """
        Training-compatible encoding (no inference_mode, no detach),
        matches your CXR chest2vec LoRA path.
        """
        device = self.text_device
        tok = self.text_tokenizer

        q_texts = [build_qwen_query(i, str(t)) for i, t in zip(instructions, texts)]
        enc = encode_with_eos_ids(tok, q_texts, max_len)
        input_ids = enc["input_ids"].to(device, non_blocking=True)
        attention_mask = enc["attention_mask"].to(device, non_blocking=True)

        h = get_last_hidden_state(self.text_encoder, input_ids, attention_mask)  # [B,T,H]
        emb = last_token_pool(h, attention_mask)                                 # [B,H]
        emb = emb.float()

        # safety clamps (same spirit as your script)
        emb = torch.clamp(emb, min=-1e4, max=1e4)
        norm = emb.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-8)
        emb = emb / norm
        return emb

    def encode_text(
        self,
        texts: List[str],
        max_len: int,
        instructions: Optional[List[str]] = None,
        chest2vec_batch_size: int = 16,
    ) -> torch.Tensor:
        if instructions is None:
            instructions = [self.default_instruction] * len(texts)
        elif isinstance(instructions, str):
            instructions = [instructions] * len(texts)

        if len(instructions) != len(texts):
            if len(instructions) == 1:
                instructions = instructions * len(texts)
            else:
                raise ValueError("instructions length must match texts length or be 1")

        if self.freeze_text:
            with torch.no_grad():
                out = self._chest2vec_wrapper.embed_instruction_query(
                    instructions,
                    [str(t) for t in texts],
                    max_len=max_len,
                    batch_size=min(chest2vec_batch_size, len(texts)),
                    return_cpu_float32=False,
                )
                emb = out.embedding  # already normalized in your chest2vec code
        else:
            emb = self._encode_text_train(instructions, texts, max_len=max_len)

        emb = emb.to(self.text_projection.weight.device if isinstance(self.text_projection, nn.Linear) else emb.device)
        emb = emb.to(self.text_projection.weight.dtype if isinstance(self.text_projection, nn.Linear) else emb.dtype)
        emb = self.text_projection(emb)     # [B, embed_dim]
        emb = F.normalize(emb, dim=-1)
        return emb

    def forward(self, batch: Batch, max_text_len: int, chest2vec_batch_size: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        img = self.encode_image(batch.ct)
        txt = self.encode_text(batch.texts, max_len=max_text_len, chest2vec_batch_size=chest2vec_batch_size)
        loss = self.loss_fn(img, txt, gather_distributed=True)
        return loss, img, txt

    # ----- sectioned mode methods -----

    def load_section_pooler(self, pooler_dir: str):
        """Load pretrained LatentDictSectionPooler (frozen)."""
        pooler, doc_proj = load_pooler(pooler_dir, self.text_dim)
        self.section_pooler = pooler.to(self.text_device)
        self.section_pooler.eval()
        for p in self.section_pooler.parameters():
            p.requires_grad = False
        if doc_proj is not None:
            self.section_doc_proj = doc_proj.to(self.text_device)
            self.section_doc_proj.eval()
            for pp in self.section_doc_proj.parameters():
                pp.requires_grad = False
        else:
            self.section_doc_proj = None
        rank0_print(f"Section pooler loaded from {pooler_dir} (frozen)")

    def _encode_text_hidden_states(
        self, texts: List[str], max_len: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Encode texts and return hidden states + EOS embedding.
        Returns: (hidden_states [B,T,H], attention_mask [B,T], eos_emb [B,H])
        """
        device = self.text_device
        tok = self.text_tokenizer
        instructions = [self.default_instruction] * len(texts)
        q_texts = [build_qwen_query(i, str(t)) for i, t in zip(instructions, texts)]
        enc = encode_with_eos_ids(tok, q_texts, max_len)
        input_ids = enc["input_ids"].to(device, non_blocking=True)
        attention_mask = enc["attention_mask"].to(device, non_blocking=True)

        if self.freeze_text:
            with torch.no_grad():
                h = get_last_hidden_state(self.text_encoder, input_ids, attention_mask)
                eos_emb = last_token_pool(h, attention_mask)
        else:
            h = get_last_hidden_state(self.text_encoder, input_ids, attention_mask)
            eos_emb = last_token_pool(h, attention_mask)

        return h, attention_mask, eos_emb

    def encode_text_sectioned(
        self,
        texts: List[str],
        section_names: List[List[str]],  # B lists, each with 2 section names
        max_len: int,
    ) -> torch.Tensor:
        """
        Encode texts → 3 embeddings per sample: [global_eos, section1, section2].
        Returns: [B*3, embed_dim]
        """
        B = len(texts)
        h, attn_mask, eos_emb = self._encode_text_hidden_states(texts, max_len)

        # Section pooler (frozen, detached)
        with torch.no_grad():
            section_embs = self.section_pooler(
                h.detach(), attn_mask, eos_emb.detach()
            )  # [B, S, H]

        # Normalize raw EOS
        eos_emb = eos_emb.float()
        eos_emb = torch.clamp(eos_emb, min=-1e4, max=1e4)
        eos_norm = eos_emb.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-8)
        eos_emb = eos_emb / eos_norm

        # Build [B*3, H]: [global0, sec1_0, sec2_0, global1, sec1_1, sec2_1, ...]
        all_embs = []
        for i in range(B):
            all_embs.append(eos_emb[i])  # global
            for sec_name in section_names[i]:
                if sec_name in ANATOMY_COLUMNS:
                    sec_idx = ANATOMY_COLUMNS.index(sec_name)
                    all_embs.append(section_embs[i, sec_idx])
                else:
                    all_embs.append(eos_emb[i])  # fallback to global
        all_embs = torch.stack(all_embs, dim=0).float()  # [B*3, H]

        # Project and normalize
        proj_device = self.text_projection.weight.device if isinstance(self.text_projection, nn.Linear) else all_embs.device
        proj_dtype = self.text_projection.weight.dtype if isinstance(self.text_projection, nn.Linear) else all_embs.dtype
        all_embs = all_embs.to(device=proj_device, dtype=proj_dtype)
        all_embs = self.text_projection(all_embs)
        all_embs = F.normalize(all_embs, dim=-1)
        return all_embs  # [B*3, embed_dim]

    def encode_text_sectioned_direct(
        self,
        global_texts: List[str],
        section_names: List[List[str]],   # B lists, each with 2 section names
        section_texts: List[List[str]],   # B lists, each with 2 section texts
        max_len: int,
        chest2vec_batch_size: int = 16,
    ) -> torch.Tensor:
        """
        Direct section encoding: encode each section text with its own instruction
        through the full Chest2Vec pipeline (no pooler).
        Returns: [B*3, embed_dim]
        """
        B = len(global_texts)

        # Gather all texts and instructions in order:
        # [global0, sec1_0, sec2_0, global1, sec1_1, sec2_1, ...]
        all_texts = []
        all_instructions = []
        for i in range(B):
            # Global: full report with default instruction
            all_texts.append(global_texts[i])
            all_instructions.append(self.default_instruction)
            # Two section texts with section-specific instructions
            for j, sec_name in enumerate(section_names[i]):
                all_texts.append(section_texts[i][j])
                all_instructions.append(
                    SECTION_INSTRUCTIONS.get(sec_name, self.default_instruction)
                )

        # Encode all B*3 texts through the standard encode_text path
        all_embs = self.encode_text(
            all_texts,
            max_len=max_len,
            instructions=all_instructions,
            chest2vec_batch_size=chest2vec_batch_size,
        )  # [B*3, embed_dim]

        return all_embs

    def _encode_image_sectioned_pooler(
        self,
        ct: torch.Tensor,              # [B, 1, D, H, W]
        totalseg: torch.Tensor,         # [B, 1, D, H, W]
        section_names: List[List[str]], # B lists, each with 2 section names
        section_label_map: Dict[str, List[int]],
    ) -> torch.Tensor:
        """
        Encode images with learned attention pooling.
        Runs backbone ONCE per sample, then pools with different section masks.
        Returns [B*3, embed_dim] ordered as [global_0, sec1_0, sec2_0, global_1, ...].
        """
        B = ct.shape[0]

        # Build 3-channel input: [ct, ct, ct] (no mask channel needed)
        ct_3ch = torch.cat([ct, ct, ct], dim=1)  # [B, 3, D, H, W]

        # Run backbone once → spatial features [B, C, D', H', W']
        spatial = self.vision.forward_spatial(ct_3ch)
        _, C, Ds, Hs, Ws = spatial.shape
        N = Ds * Hs * Ws

        # Global feature for conditioning (avgpool)
        global_feat = spatial.mean(dim=(-3, -2, -1))  # [B, C]

        # Flatten spatial dims: [B, N, C]
        spatial_flat = spatial.flatten(2).permute(0, 2, 1)  # [B, N, C]

        # Build attention masks for all B*3 variants
        all_masks = []
        for i in range(B):
            # Global variant: attend to all spatial positions
            all_masks.append(torch.ones(N, device=ct.device, dtype=torch.float32))

            # 2 section variants
            for sec_name in section_names[i]:
                csv_name = sec_name
                json_name = CSV_TO_SECTION_JSON.get(csv_name, csv_name)
                label_indices = section_label_map.get(csv_name) or section_label_map.get(json_name)

                if label_indices:
                    idx_tensor = torch.tensor(label_indices, device=totalseg.device, dtype=totalseg.dtype)
                    seg_mask = torch.isin(totalseg[i], idx_tensor).float()  # [1, D, H, W]
                    # Downsample to feature map spatial dims
                    seg_mask_ds = F.interpolate(
                        seg_mask.unsqueeze(0),  # [1, 1, D, H, W]
                        size=(Ds, Hs, Ws),
                        mode='trilinear',
                        align_corners=False,
                    ).squeeze(0).squeeze(0)  # [D', H', W']
                    seg_mask_ds = (seg_mask_ds > 0.1).float()
                    # Ensure at least some positions are attended to
                    if seg_mask_ds.sum() < 1:
                        seg_mask_ds = torch.ones_like(seg_mask_ds)
                    all_masks.append(seg_mask_ds.flatten())  # [N]
                else:
                    all_masks.append(torch.ones(N, device=ct.device, dtype=torch.float32))

        attn_masks = torch.stack(all_masks, dim=0)  # [B*3, N]

        # Expand spatial and global: each sample repeated 3 times
        spatial_expanded = spatial_flat.repeat_interleave(3, dim=0)  # [B*3, N, C]
        global_expanded = global_feat.repeat_interleave(3, dim=0)  # [B*3, C]

        # Pool with learned attention
        pooled = self.vision_pooler(spatial_expanded, attn_masks, global_expanded)  # [B*3, vision_dim]

        # Project + normalize (same as encode_image)
        pooled = self.visual_projection(pooled)  # [B*3, embed_dim]
        pooled = F.normalize(pooled, dim=-1)
        return pooled

    def forward_sectioned(
        self,
        batch: SectionedBatch,
        section_label_map: Dict[str, List[int]],
        max_text_len: int,
        chest2vec_batch_size: int,
        section_mode: str = "pooler",
        mask_channel_mode: str = "masked_ct",
    ):
        """
        Forward pass for sectioned mode.
        Returns: (total_loss, local_loss, global_loss, global_only_loss, img_embs [B*3,D], txt_embs [B*3,D])
        """
        # Encode images: use vision attention pooler if available, else original avgpool path
        if hasattr(self, 'vision_pooler') and self.vision_pooler is not None:
            img_embs = self._encode_image_sectioned_pooler(
                batch.ct, batch.totalseg, batch.section_names, section_label_map,
            )  # [B*3, embed_dim]
        else:
            img_variants = build_sectioned_image_variants(
                batch.ct, batch.totalseg, batch.section_names, section_label_map,
                mask_channel_mode=mask_channel_mode,
            )  # [B*3, 3, D, H, W]
            img_embs = self.encode_image(img_variants)  # [B*3, embed_dim]

        # Encode texts → 3 per sample
        if section_mode == "direct":
            txt_embs = self.encode_text_sectioned_direct(
                batch.global_texts, batch.section_names,
                batch.section_texts, max_len=max_text_len,
                chest2vec_batch_size=chest2vec_batch_size,
            )  # [B*3, embed_dim]
        else:
            txt_embs = self.encode_text_sectioned(
                batch.global_texts, batch.section_names, max_len=max_text_len,
            )  # [B*3, embed_dim]

        total_loss, local_loss, global_loss, global_only_loss = self.sectioned_loss_fn(
            img_embs, txt_embs, gather_distributed=True,
        )
        return total_loss, local_loss, global_loss, global_only_loss, img_embs, txt_embs


# =========================================================
# Retrieval metrics: topk i2t / t2i
# =========================================================
@torch.no_grad()
def retrieval_topk(
    img_embs: torch.Tensor,  # [N,D] normalized
    txt_embs: torch.Tensor,  # [N,D] normalized
    k_list=(1, 5, 10),
    sim_chunk_elems: int = 2_000_000,
) -> Dict[str, float]:
    device = img_embs.device
    N = img_embs.shape[0]
    maxk = max(k_list)

    # chunk size ~ sim_chunk_elems / N
    chunk = max(1, min(N, sim_chunk_elems // max(N, 1)))

    gt = torch.arange(N, device=device)

    def _acc(query: torch.Tensor, bank: torch.Tensor, prefix: str) -> Dict[str, float]:
        hits = {k: 0 for k in k_list}
        for s in range(0, N, chunk):
            e = min(N, s + chunk)
            sims = query[s:e] @ bank.t()  # [m,N]
            topk = sims.topk(maxk, dim=1).indices
            g = gt[s:e].unsqueeze(1)
            for k in k_list:
                hits[k] += int((topk[:, :k] == g).any(dim=1).sum().item())
        return {f"{prefix}_top{k}": hits[k] / float(N) for k in k_list}

    out = {}
    out.update(_acc(img_embs, txt_embs, "i2t"))
    out.update(_acc(txt_embs, img_embs, "t2i"))
    return out


@torch.no_grad()
def validate(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    amp: bool,
    max_text_len: int,
    chest2vec_batch_size: int,
    sim_chunk_elems: int,
    max_val_samples: int = 0,
):
    model.eval()
    m = model.module if hasattr(model, "module") else model

    loss_sum = 0.0
    count = 0

    idx_list = []
    img_list = []
    txt_list = []

    for batch in val_loader:
        batch = Batch(
            idx=batch.idx.to(device, non_blocking=True),
            ct=batch.ct.to(device, non_blocking=True),
            texts=batch.texts,
        )

        with torch.cuda.amp.autocast(enabled=amp, dtype=torch.bfloat16 if amp else torch.float32):
            loss, img, txt = m(batch, max_text_len=max_text_len, chest2vec_batch_size=chest2vec_batch_size)

        bs = batch.ct.shape[0]
        loss_sum += float(loss.item()) * bs
        count += bs

        idx_list.append(batch.idx.detach().cpu())
        img_list.append(img.detach().cpu())
        txt_list.append(txt.detach().cpu())

        if max_val_samples > 0 and count >= max_val_samples:
            break

    # reduce loss across ranks
    loss_sum_t = torch.tensor([loss_sum], device=device, dtype=torch.float64)
    count_t = torch.tensor([count], device=device, dtype=torch.float64)
    if is_dist():
        dist.all_reduce(loss_sum_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(count_t, op=dist.ReduceOp.SUM)
    val_loss = (loss_sum_t / count_t.clamp_min(1.0)).item()

    # retrieval metrics: gather embeddings (no grad)
    idx_local = torch.cat(idx_list, dim=0) if idx_list else torch.empty((0,), dtype=torch.long)
    img_local = torch.cat(img_list, dim=0) if img_list else torch.empty((0, m.embed_dim), dtype=torch.float32)
    txt_local = torch.cat(txt_list, dim=0) if txt_list else torch.empty((0, m.embed_dim), dtype=torch.float32)

    if is_dist():
        idx_all = gather_variable_first_dim_no_grad(idx_local.to(device=device, dtype=torch.long)).cpu()
        img_all = gather_variable_first_dim_no_grad(img_local.to(device=device)).cpu()
        txt_all = gather_variable_first_dim_no_grad(txt_local.to(device=device)).cpu()
    else:
        idx_all, img_all, txt_all = idx_local, img_local, txt_local

    metrics = {}
    if get_rank() == 0 and idx_all.numel() > 0:
        # deduplicate padded repeats from DistributedSampler
        order = torch.argsort(idx_all)
        idx_sorted = idx_all[order]
        img_sorted = img_all[order]
        txt_sorted = txt_all[order]

        unique_mask = torch.ones_like(idx_sorted, dtype=torch.bool)
        unique_mask[1:] = idx_sorted[1:] != idx_sorted[:-1]
        img_u = img_sorted[unique_mask]
        txt_u = txt_sorted[unique_mask]

        if max_val_samples > 0 and img_u.shape[0] > max_val_samples:
            img_u = img_u[:max_val_samples]
            txt_u = txt_u[:max_val_samples]

        img_u = F.normalize(img_u.to(device=device, dtype=torch.float32), dim=-1)
        txt_u = F.normalize(txt_u.to(device=device, dtype=torch.float32), dim=-1)

        metrics = retrieval_topk(img_u, txt_u, k_list=(1, 5, 10), sim_chunk_elems=sim_chunk_elems)

    return val_loss, metrics


@torch.no_grad()
def validate_sectioned(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    amp: bool,
    max_text_len: int,
    section_label_map: Dict[str, List[int]],
    sim_chunk_elems: int,
    max_val_samples: int = 0,
    section_mode: str = "pooler",
    mask_channel_mode: str = "masked_ct",
):
    model.eval()
    m = model.module if hasattr(model, "module") else model

    loss_sum = 0.0
    local_loss_sum = 0.0
    global_loss_sum = 0.0
    count = 0

    idx_list = []
    img_list = []
    txt_list = []
    # Per-section retrieval: {section_name: {"img": [...], "txt": [...]}}
    per_section_embs: Dict[str, Dict[str, list]] = {}

    for batch in val_loader:
        batch = SectionedBatch(
            idx=batch.idx.to(device, non_blocking=True),
            ct=batch.ct.to(device, non_blocking=True),
            totalseg=batch.totalseg.to(device, non_blocking=True),
            global_texts=batch.global_texts,
            section_names=batch.section_names,
            section_texts=batch.section_texts,
        )

        with torch.cuda.amp.autocast(enabled=amp, dtype=torch.bfloat16 if amp else torch.float32):
            total_loss, local_loss, global_loss, global_only_loss, img_emb, txt_emb = m.forward_sectioned(
                batch, section_label_map,
                max_text_len=max_text_len,
                chest2vec_batch_size=16,
                section_mode=section_mode,
                mask_channel_mode=mask_channel_mode,
            )

        bs = batch.ct.shape[0]
        loss_sum += float(total_loss.item()) * bs
        local_loss_sum += float(local_loss.item()) * bs
        global_loss_sum += float(global_loss.item()) * bs
        count += bs

        # Global embeddings (index 0 of each triplet)
        global_img = img_emb[0::3].detach().cpu()   # [B, D]
        global_txt = txt_emb[0::3].detach().cpu()    # [B, D]

        idx_list.append(batch.idx.detach().cpu())
        img_list.append(global_img)
        txt_list.append(global_txt)

        # Collect per-section embeddings (indices 1,2 of each triplet)
        sec1_img = img_emb[1::3].detach().cpu()      # [B, D]
        sec1_txt = txt_emb[1::3].detach().cpu()
        sec2_img = img_emb[2::3].detach().cpu()
        sec2_txt = txt_emb[2::3].detach().cpu()
        for i in range(bs):
            for j, (s_img, s_txt) in enumerate([(sec1_img, sec1_txt), (sec2_img, sec2_txt)]):
                sec_name = batch.section_names[i][j]
                if sec_name not in per_section_embs:
                    per_section_embs[sec_name] = {"img": [], "txt": []}
                per_section_embs[sec_name]["img"].append(s_img[i])
                per_section_embs[sec_name]["txt"].append(s_txt[i])

        if max_val_samples > 0 and count >= max_val_samples:
            break

    # reduce loss across ranks
    loss_sum_t = torch.tensor([loss_sum], device=device, dtype=torch.float64)
    local_sum_t = torch.tensor([local_loss_sum], device=device, dtype=torch.float64)
    global_sum_t = torch.tensor([global_loss_sum], device=device, dtype=torch.float64)
    count_t = torch.tensor([count], device=device, dtype=torch.float64)
    if is_dist():
        dist.all_reduce(loss_sum_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(local_sum_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(global_sum_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(count_t, op=dist.ReduceOp.SUM)
    denom = count_t.clamp_min(1.0)
    val_loss = (loss_sum_t / denom).item()
    val_local = (local_sum_t / denom).item()
    val_global = (global_sum_t / denom).item()

    # retrieval metrics on global embeddings
    idx_local = torch.cat(idx_list, dim=0) if idx_list else torch.empty((0,), dtype=torch.long)
    img_local = torch.cat(img_list, dim=0) if img_list else torch.empty((0, m.embed_dim), dtype=torch.float32)
    txt_local = torch.cat(txt_list, dim=0) if txt_list else torch.empty((0, m.embed_dim), dtype=torch.float32)

    if is_dist():
        idx_all = gather_variable_first_dim_no_grad(idx_local.to(device=device, dtype=torch.long)).cpu()
        img_all = gather_variable_first_dim_no_grad(img_local.to(device=device)).cpu()
        txt_all = gather_variable_first_dim_no_grad(txt_local.to(device=device)).cpu()
    else:
        idx_all, img_all, txt_all = idx_local, img_local, txt_local

    metrics = {}
    if get_rank() == 0 and idx_all.numel() > 0:
        # --- global retrieval ---
        order = torch.argsort(idx_all)
        idx_sorted = idx_all[order]
        img_sorted = img_all[order]
        txt_sorted = txt_all[order]

        unique_mask = torch.ones_like(idx_sorted, dtype=torch.bool)
        unique_mask[1:] = idx_sorted[1:] != idx_sorted[:-1]
        img_u = img_sorted[unique_mask]
        txt_u = txt_sorted[unique_mask]

        if max_val_samples > 0 and img_u.shape[0] > max_val_samples:
            img_u = img_u[:max_val_samples]
            txt_u = txt_u[:max_val_samples]

        img_u = F.normalize(img_u.to(device=device, dtype=torch.float32), dim=-1)
        txt_u = F.normalize(txt_u.to(device=device, dtype=torch.float32), dim=-1)

        metrics = retrieval_topk(img_u, txt_u, k_list=(1, 5, 10), sim_chunk_elems=sim_chunk_elems)

        # --- per-section retrieval ---
        for sec_name, emb_dict in per_section_embs.items():
            sec_imgs = torch.stack(emb_dict["img"], dim=0)  # [N_sec, D]
            sec_txts = torch.stack(emb_dict["txt"], dim=0)
            if sec_imgs.shape[0] < 2:
                continue  # need at least 2 samples for retrieval
            sec_imgs = F.normalize(sec_imgs.to(device=device, dtype=torch.float32), dim=-1)
            sec_txts = F.normalize(sec_txts.to(device=device, dtype=torch.float32), dim=-1)
            sec_k_list = tuple(k for k in (1, 5, 10) if k <= sec_imgs.shape[0])
            if not sec_k_list:
                continue
            sec_m = retrieval_topk(sec_imgs, sec_txts, k_list=sec_k_list, sim_chunk_elems=sim_chunk_elems)
            # Use short key: e.g. "lungs_i2t_top1"
            short = sec_name.lower().replace(" + ", "_").replace(" & ", "_").replace(" ", "_")
            for k, v in sec_m.items():
                metrics[f"{short}_{k}"] = v

    return val_loss, val_local, val_global, metrics


# =========================================================
# Optimizer: param groups (vision / text / proj / logit)
# =========================================================
def split_decay(named_params):
    decay, no_decay = [], []
    for n, p in named_params:
        if not p.requires_grad:
            continue
        if p.ndim == 1 or n.endswith(".bias") or "norm" in n.lower() or "layernorm" in n.lower():
            no_decay.append(p)
        else:
            decay.append(p)
    return decay, no_decay


def build_optimizer(model: "MerlinWithChest2Vec", lr_vision, lr_text, lr_proj, weight_decay):
    groups = []

    # vision
    dv, ndv = split_decay(model.vision.named_parameters())
    if dv:
        groups.append({"params": dv, "lr": lr_vision, "weight_decay": weight_decay, "name": "vision"})
    if ndv:
        groups.append({"params": ndv, "lr": lr_vision, "weight_decay": 0.0, "name": "vision_nodecay"})

    # text encoder (only if trainable)
    dt, ndt = split_decay(model.text_encoder.named_parameters())
    if dt:
        groups.append({"params": dt, "lr": lr_text, "weight_decay": weight_decay, "name": "text"})
    if ndt:
        groups.append({"params": ndt, "lr": lr_text, "weight_decay": 0.0, "name": "text_nodecay"})

    # projections
    for name, mod in [("visual_proj", model.visual_projection), ("text_proj", model.text_projection)]:
        if isinstance(mod, nn.Identity):
            continue
        d, nd = split_decay(mod.named_parameters())
        if d:
            groups.append({"params": d, "lr": lr_proj, "weight_decay": weight_decay, "name": name})
        if nd:
            groups.append({"params": nd, "lr": lr_proj, "weight_decay": 0.0, "name": name + "_nodecay"})

    # logit params (loss module)
    dl, ndl = split_decay(model.loss_fn.named_parameters())
    if dl:
        groups.append({"params": dl, "lr": lr_proj, "weight_decay": weight_decay, "name": "logit"})
    if ndl:
        groups.append({"params": ndl, "lr": lr_proj, "weight_decay": 0.0, "name": "logit_nodecay"})

    # sectioned loss params (if present)
    if hasattr(model, "sectioned_loss_fn") and model.sectioned_loss_fn is not None:
        dsl, ndsl = split_decay(model.sectioned_loss_fn.named_parameters())
        if dsl:
            groups.append({"params": dsl, "lr": lr_proj, "weight_decay": weight_decay, "name": "sect_logit"})
        if ndsl:
            groups.append({"params": ndsl, "lr": lr_proj, "weight_decay": 0.0, "name": "sect_logit_nodecay"})

    # vision attention pooler (if present)
    if hasattr(model, "vision_pooler") and model.vision_pooler is not None:
        dvp, ndvp = split_decay(model.vision_pooler.named_parameters())
        if dvp:
            groups.append({"params": dvp, "lr": lr_proj, "weight_decay": weight_decay, "name": "vision_pooler"})
        if ndvp:
            groups.append({"params": ndvp, "lr": lr_proj, "weight_decay": 0.0, "name": "vision_pooler_nodecay"})

    return torch.optim.AdamW(groups, betas=(0.9, 0.98), eps=1e-6)


def get_cosine_schedule_with_warmup(optimizer, num_warmup_steps, num_training_steps, min_lr_ratios):
    """
    Cosine schedule with warmup and per-group minimum learning rates.
    min_lr_ratios: dict mapping group name to min_lr/initial_lr ratio
    """
    def lr_lambda(current_step, group_name):
        min_ratio = min_lr_ratios.get(group_name, 0.0)
        if current_step < num_warmup_steps:
            # Linear warmup
            return float(current_step) / float(max(1, num_warmup_steps))
        # Cosine decay to min_ratio
        progress = float(current_step - num_warmup_steps) / float(max(1, num_training_steps - num_warmup_steps))
        cosine_decay = 0.5 * (1.0 + math.cos(math.pi * progress))
        return min_ratio + (1.0 - min_ratio) * cosine_decay
    
    # Create lambdas for each param group
    lambdas = []
    for group in optimizer.param_groups:
        group_name = group.get("name", "default")
        # Determine which min_lr category this group falls into
        if "vision_pooler" in group_name:
            category = "proj"  # vision pooler uses proj lr (trained from scratch)
        elif "vision" in group_name:
            category = "vision"
        elif "text" in group_name:
            category = "text"
        else:
            category = "proj"
        lambdas.append(lambda step, cat=category: lr_lambda(step, cat))
    
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lambdas)


# =========================================================
# Train
# =========================================================
def main():
    import argparse

    p = argparse.ArgumentParser()

    # data
    p.add_argument("--csv_path", type=str, default="/data/all_ct_sectioned_with_labels_only_lungs.csv")
    p.add_argument("--npz_root", type=str, default="/data/preprocessed")
    p.add_argument("--max_text_len", type=int, default=256)
    p.add_argument("--text_primary", type=str, default="refined_findings")
    p.add_argument("--text_fallback", type=str, default="findings")
    p.add_argument("--mask_type", type=str, default="repeat")

    # models
    p.add_argument("--chest2vec_path", type=str, default="lukeingawesome/chest2vec_0.6b_chest")
    p.add_argument("--default_instruction", type=str,
                   default="Retrieve the chest CT that is similar to the given report.")
    p.add_argument("--embed_dim", type=int, default=0, help="0 => match vision dim (2048 for Merlin)")
    p.add_argument("--freeze_vision", action="store_true")
    p.add_argument("--freeze_text", action="store_true", help="Freeze Chest2Vec completely (default: LoRA training enabled)")
    p.add_argument("--full_finetune_text", action="store_true", help="Train ALL Chest2Vec params (not LoRA-only)")
    p.add_argument("--no_text_projection", action="store_true", help="Disable 1024->embed_dim projection")
    p.add_argument("--no_visual_projection", action="store_true", help="Disable vision->embed_dim projection (only ok if dims already match)")

    # chest2vec runtime
    p.add_argument("--chest2vec_batch_size", type=int, default=16)
    p.add_argument("--chest2vec_use_4bit", action="store_true")
    p.add_argument("--force_flash_attention_2", action="store_true")

    # train
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch_size", type=int, default=2)
    p.add_argument("--val_batch_size", type=int, default=2)
    p.add_argument("--lr_vision", type=float, default=1e-4)
    p.add_argument("--lr_text", type=float, default=1e-5)
    p.add_argument("--lr_proj", type=float, default=1e-4)
    p.add_argument("--min_lr_vision", type=float, default=1e-5, help="Min LR for vision encoder (cosine decay)")
    p.add_argument("--min_lr_text", type=float, default=1e-6, help="Min LR for text encoder (cosine decay)")
    p.add_argument("--min_lr_proj", type=float, default=1e-5, help="Min LR for projections (cosine decay)")
    p.add_argument("--warmup_steps", type=int, default=100, help="Warmup steps for LR scheduler")
    p.add_argument("--weight_decay", type=float, default=0.05)
    p.add_argument("--grad_accum", type=int, default=1)
    p.add_argument("--grad_cache", action="store_true", help="Enable gradient caching for more negatives")
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--amp", action="store_true")
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--log_every", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out_dir", type=str, default="./siglip_ckpts")

    # validation retrieval controls
    p.add_argument("--val_sim_chunk_elems", type=int, default=2_000_000)
    p.add_argument("--max_val_samples", type=int, default=0, help="0 => full val; else cap for retrieval")
    
    # debug/subset controls
    p.add_argument("--train_fraction", type=float, default=1.0, help="Fraction of training data to use (for debugging)")
    p.add_argument("--val_fraction", type=float, default=1.0, help="Fraction of validation data to use (for debugging)")

    # sectioned contrastive
    p.add_argument("--sectioned", action="store_true", help="Enable sectioned contrastive training")
    p.add_argument("--section_mode", type=str, default="pooler", choices=["pooler", "direct"],
                   help="'pooler': use pretrained LatentDictSectionPooler; 'direct': encode section texts directly")
    p.add_argument("--section_json", type=str, default="./section.json",
                   help="Path to section.json with TotalSeg label mappings")
    p.add_argument("--section_csv", type=str, default="./chest2vec/final_ct2_exist_section.csv",
                   help="CSV with exist_section column")
    p.add_argument("--section_pooler_dir", type=str, default="./chest2vec/stage3_ct_anatomy_0.6b/",
                   help="Directory containing pretrained section_pooler.pt")
    p.add_argument("--mask_channel_mode", type=str, default="masked_ct", choices=["masked_ct", "binary"],
                   help="Third channel: 'masked_ct' = ct*mask, 'binary' = raw binary mask")
    p.add_argument("--local_loss_weight", type=float, default=1.0, help="Weight for per-sample local 3x3 loss")
    p.add_argument("--global_loss_weight", type=float, default=1.0, help="Weight for batch-wide global loss")
    p.add_argument("--global_only_loss_weight", type=float, default=1.0, help="Weight for global-only BxB contrastive loss (full image + full report)")
    p.add_argument("--min_sections_per_sample", type=int, default=2, help="Min sections required per sample")
    p.add_argument("--exclude_sections", type=str, nargs="*", default=None,
                   help="Section names to exclude from sampling (e.g. 'Lower neck' 'Others')")
    p.add_argument("--use_vision_pooler", action="store_true",
                   help="Use learned VisionAttentionPooler instead of avgpool for sectioned mode")
    p.add_argument("--vision_pooler_latents", type=int, default=8,
                   help="Number of dictionary latents for VisionAttentionPooler")
    p.add_argument("--unfreeze_text_epoch", type=int, default=-1,
                   help="Epoch at which to unfreeze text LoRA (requires --freeze_text). "
                        "-1 = never unfreeze. Enables warm-start: vision pooler learns first, then text LoRA joins.")

    # resume
    p.add_argument("--resume", type=str, default=None, help="Path to checkpoint .pt file to resume training from")

    # wandb
    p.add_argument("--wandb_project", type=str, default="siglip-ct")
    p.add_argument("--wandb_name", type=str, default=None)
    p.add_argument("--wandb_entity", type=str, default=None)
    p.add_argument("--wandb_mode", type=str, default="online", choices=["online", "offline", "disabled"])

    args = p.parse_args()

    rank, world, local_rank = setup_distributed()
    device = torch.device(f"cuda:{local_rank}" if torch.cuda.is_available() else "cpu")

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    set_seed(args.seed + rank)

    # datasets/loaders
    section_label_map = None
    if args.sectioned:
        csv_for_data = args.section_csv
        train_ds = SectionedCTTextDataset(
            csv_path=csv_for_data,
            npz_root=args.npz_root,
            section_json_path=args.section_json,
            split="train",
            text_primary=args.text_primary,
            text_fallback=args.text_fallback,
            min_sections=args.min_sections_per_sample,
            exclude_sections=args.exclude_sections,
        )
        val_ds = SectionedCTTextDataset(
            csv_path=csv_for_data,
            npz_root=args.npz_root,
            section_json_path=args.section_json,
            split="val",
            text_primary=args.text_primary,
            text_fallback=args.text_fallback,
            min_sections=args.min_sections_per_sample,
            exclude_sections=args.exclude_sections,
        )
        active_collate = sectioned_collate_fn
        section_label_map = load_section_label_map(args.section_json)
        rank0_print(f"Sectioned mode: {len(section_label_map)} sections loaded from {args.section_json}")
    else:
        train_ds = CTTextDataset(
            csv_path=args.csv_path,
            npz_root=args.npz_root,
            mask_type=args.mask_type,
            split="train",
            text_primary=args.text_primary,
            text_fallback=args.text_fallback,
        )
        val_ds = CTTextDataset(
            csv_path=args.csv_path,
            npz_root=args.npz_root,
            mask_type=args.mask_type,
            split="val",
            text_primary=args.text_primary,
            text_fallback=args.text_fallback,
        )
        active_collate = collate_fn

    # Subset datasets for debugging if requested
    if args.train_fraction < 1.0:
        subset_size = int(len(train_ds) * args.train_fraction)
        indices = torch.randperm(len(train_ds))[:subset_size].tolist()
        train_ds = torch.utils.data.Subset(train_ds, indices)
        rank0_print(f"Using {args.train_fraction*100:.1f}% of training data: {len(train_ds)} samples")

    if args.val_fraction < 1.0:
        subset_size = int(len(val_ds) * args.val_fraction)
        indices = torch.randperm(len(val_ds))[:subset_size].tolist()
        val_ds = torch.utils.data.Subset(val_ds, indices)
        rank0_print(f"Using {args.val_fraction*100:.1f}% of validation data: {len(val_ds)} samples")

    train_sampler = DistributedSampler(train_ds, shuffle=True, drop_last=True) if is_dist() else None
    val_sampler = DistributedSampler(val_ds, shuffle=False, drop_last=False) if is_dist() else None

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        sampler=train_sampler,
        shuffle=(train_sampler is None),
        num_workers=args.num_workers,
        pin_memory=True,
        drop_last=True,
        collate_fn=active_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.val_batch_size,
        sampler=val_sampler,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
        drop_last=False,
        collate_fn=active_collate,
    )

    # Let rank 0 download models first; other ranks wait then load from cache
    if is_dist() and rank != 0:
        dist.barrier()

    # vision encoder (Merlin I3ResNet) + infer dim
    vision = MerlinVisionEncoder(freeze=args.freeze_vision).to(device)
    vision.eval()
    with torch.no_grad():
        if args.sectioned:
            # SectionedCTTextDataset returns (idx, ct[1,D,H,W], totalseg, text, sections, section_texts)
            _, ct0_raw, _, _, _, _ = train_ds[0]
            # Build a dummy 3-channel input: [ct, ct, ct]
            ct0 = torch.cat([ct0_raw, ct0_raw, ct0_raw], dim=0)
            ct0 = ct0.unsqueeze(0).to(device)  # [1,3,D,H,W]
        else:
            _, ct0, _ = train_ds[0]
            ct0 = ct0.unsqueeze(0).to(device)  # [1,3,D,H,W]
        with torch.cuda.amp.autocast(enabled=args.amp, dtype=torch.bfloat16 if args.amp else torch.float32):
            v0 = vision(ct0)
        vision_dim = int(v0.shape[-1])  # 2048 for Merlin

    embed_dim = vision_dim if args.embed_dim <= 0 else int(args.embed_dim)
    if get_rank() == 0:
        rank0_print(f"Merlin vision dim={vision_dim}, embed_dim={embed_dim}")

    # build model
    chest2vec_device = str(device)  # one GPU per rank
    model = MerlinWithChest2Vec(
        vision=vision,
        vision_dim=vision_dim,
        embed_dim=embed_dim,
        chest2vec_path=args.chest2vec_path,
        chest2vec_device=chest2vec_device,
        default_instruction=args.default_instruction,
        freeze_text=args.freeze_text,
        full_finetune_text=args.full_finetune_text,
        use_text_projection=not args.no_text_projection,
        use_visual_projection=not args.no_visual_projection,
        chest2vec_use_4bit=args.chest2vec_use_4bit,
        force_flash_attention_2=args.force_flash_attention_2,
    ).to(device)

    # Sectioned mode: load pretrained pooler (only for pooler mode) and attach sectioned loss
    if args.sectioned:
        if args.section_mode == "pooler":
            model.load_section_pooler(args.section_pooler_dir)
        else:
            rank0_print(f"Section mode: direct (no pooler loaded)")
        model.sectioned_loss_fn = SectionedSigLIPLoss(
            init_logit_scale=None,
            init_logit_bias=-10.0,
            local_weight=args.local_loss_weight,
            global_weight=args.global_loss_weight,
            global_only_weight=args.global_only_loss_weight,
        ).to(device)

        # Vision attention pooler: replaces avgpool with learned section-aware pooling
        if args.use_vision_pooler:
            model.vision_pooler = VisionAttentionPooler(
                hidden_size=vision_dim,
                num_latents=args.vision_pooler_latents,
                cond_on_global=True,
                output_dim=vision_dim,  # matches visual_projection input dim
            ).to(device)
            vp_params = sum(p.numel() for p in model.vision_pooler.parameters())
            rank0_print(f"VisionAttentionPooler: {vp_params:,} params "
                        f"(K={args.vision_pooler_latents}, hidden={vision_dim})")
        else:
            model.vision_pooler = None

    # Rank 0 done downloading — release other ranks
    if is_dist() and rank == 0:
        dist.barrier()

    if is_dist():
        model = torch.nn.parallel.DistributedDataParallel(
            model,
            device_ids=[local_rank] if device.type == "cuda" else None,
            output_device=local_rank if device.type == "cuda" else None,
            find_unused_parameters=True,  # text params may be frozen / LoRA-only
        )

    m = model.module if hasattr(model, "module") else model
    model = torch.compile(model, mode="reduce-overhead")

    optimizer = build_optimizer(
        m,
        lr_vision=args.lr_vision,
        lr_text=args.lr_text,
        lr_proj=args.lr_proj,
        weight_decay=args.weight_decay,
    )

    scaler = torch.cuda.amp.GradScaler(enabled=args.amp and device.type == "cuda")

    # Learning rate scheduler with cosine decay and warmup
    steps_per_epoch = len(train_loader) // args.grad_accum
    num_training_steps = steps_per_epoch * args.epochs
    min_lr_ratios = {
        "vision": args.min_lr_vision / args.lr_vision if args.lr_vision > 0 else 0.0,
        "text": args.min_lr_text / args.lr_text if args.lr_text > 0 else 0.0,
        "proj": args.min_lr_proj / args.lr_proj if args.lr_proj > 0 else 0.0,
    }
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, 
        num_warmup_steps=args.warmup_steps,
        num_training_steps=num_training_steps,
        min_lr_ratios=min_lr_ratios
    )
    rank0_print(f"Scheduler: cosine decay with {args.warmup_steps} warmup steps over {num_training_steps} total steps")
    rank0_print(f"  Vision: {args.lr_vision} → {args.min_lr_vision}")
    rank0_print(f"  Text: {args.lr_text} → {args.min_lr_text}")
    rank0_print(f"  Proj: {args.lr_proj} → {args.min_lr_proj}")

    # ---- resume from checkpoint ----
    start_epoch = 0
    if args.resume:
        rank0_print(f"Resuming from checkpoint: {args.resume}")
        ckpt = torch.load(args.resume, map_location=device)
        raw_model = model.module if hasattr(model, "module") else model
        raw_model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        if "scheduler" in ckpt:
            scheduler.load_state_dict(ckpt["scheduler"])
        else:
            # advance scheduler to match saved global_step
            for _ in range(ckpt.get("global_step", 0)):
                scheduler.step()
        if "scaler" in ckpt and args.amp:
            scaler.load_state_dict(ckpt["scaler"])
        start_epoch = ckpt["epoch"] + 1  # saved after completing that epoch
        global_step = ckpt.get("global_step", 0)
        best_val_loss = ckpt.get("best_val_loss", np.inf)
        rank0_print(f"Resumed: starting at epoch {start_epoch}, global_step {global_step}")

    # wandb
    if get_rank() == 0 and args.wandb_mode != "disabled":
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_name,
            entity=args.wandb_entity,
            mode=args.wandb_mode,
            config={
                **vars(args),
                "vision_dim": vision_dim,
                "embed_dim_effective": embed_dim,
                "world_size": world,
            },
        )

    os.makedirs(args.out_dir, exist_ok=True)

    if not args.resume:
        global_step = 0
        best_val_loss = np.inf
    for epoch in range(start_epoch, args.epochs):
        if train_sampler is not None:
            train_sampler.set_epoch(epoch)

        model.train()
        mm = model.module if hasattr(model, "module") else model

        # Warm-start: unfreeze text LoRA at specified epoch
        if args.unfreeze_text_epoch >= 0 and epoch == args.unfreeze_text_epoch and mm.freeze_text:
            rank0_print(f"=== Epoch {epoch}: Unfreezing text encoder LoRA ===")
            mm.freeze_text = False
            mm._configure_text_trainability()
            # Add newly trainable text params to optimizer
            dt, ndt = split_decay(mm.text_encoder.named_parameters())
            if dt:
                optimizer.add_param_group({"params": dt, "lr": args.lr_text, "weight_decay": args.weight_decay, "name": "text"})
            if ndt:
                optimizer.add_param_group({"params": ndt, "lr": args.lr_text, "weight_decay": 0.0, "name": "text_nodecay"})
            rank0_print(f"  Added text LoRA params to optimizer with lr={args.lr_text}")
        
        # Gradient caching buffers
        cached_img_embs = []
        cached_txt_embs = []
        cached_batches = []
        
        for step, batch in enumerate(train_loader):
            # ---- move batch to device ----
            if args.sectioned:
                batch = SectionedBatch(
                    idx=batch.idx.to(device, non_blocking=True),
                    ct=batch.ct.to(device, non_blocking=True),
                    totalseg=batch.totalseg.to(device, non_blocking=True),
                    global_texts=batch.global_texts,
                    section_names=batch.section_names,
                    section_texts=batch.section_texts,
                )
            else:
                batch = Batch(
                    idx=batch.idx.to(device, non_blocking=True),
                    ct=batch.ct.to(device, non_blocking=True),
                    texts=batch.texts,
                )

            micro_step = step % args.grad_accum
            is_last_micro = (step + 1) % args.grad_accum == 0
            local_loss_val = 0.0
            global_loss_val = 0.0
            global_only_loss_val = 0.0

            if args.grad_cache and args.grad_accum > 1:
                # ===== GRADIENT CACHING MODE (memory-efficient) =====
                with torch.no_grad():
                    with torch.cuda.amp.autocast(enabled=args.amp and device.type == "cuda", dtype=torch.bfloat16 if args.amp else torch.float32):
                        if args.sectioned:
                            img_variants = build_sectioned_image_variants(
                                batch.ct, batch.totalseg, batch.section_names, section_label_map,
                                mask_channel_mode=args.mask_channel_mode,
                            )
                            img_emb = mm.encode_image(img_variants).detach()  # [B*3, D]
                            if args.section_mode == "direct":
                                txt_emb = mm.encode_text_sectioned_direct(
                                    batch.global_texts, batch.section_names,
                                    batch.section_texts, max_len=args.max_text_len,
                                    chest2vec_batch_size=args.chest2vec_batch_size,
                                ).detach()  # [B*3, D]
                            else:
                                txt_emb = mm.encode_text_sectioned(
                                    batch.global_texts, batch.section_names, max_len=args.max_text_len,
                                ).detach()  # [B*3, D]
                        else:
                            img_emb = mm.encode_image(batch.ct).detach()
                            txt_emb = mm.encode_text(batch.texts, max_len=args.max_text_len, chest2vec_batch_size=args.chest2vec_batch_size).detach()

                cached_img_embs.append(img_emb)
                cached_txt_embs.append(txt_emb)
                cached_batches.append(batch)

                if is_last_micro:
                    all_img = torch.cat(cached_img_embs, dim=0)
                    all_txt = torch.cat(cached_txt_embs, dim=0)
                    all_img.requires_grad_(True)
                    all_txt.requires_grad_(True)

                    with torch.cuda.amp.autocast(enabled=args.amp and device.type == "cuda", dtype=torch.bfloat16 if args.amp else torch.float32):
                        if args.sectioned:
                            loss, local_loss_t, global_loss_t, global_only_loss_t = mm.sectioned_loss_fn(
                                all_img, all_txt, gather_distributed=True,
                            )
                            loss = loss * args.grad_accum
                            local_loss_val = float(local_loss_t.item())
                            global_loss_val = float(global_loss_t.item())
                            global_only_loss_val = float(global_only_loss_t.item())
                        else:
                            loss = mm.loss_fn(all_img, all_txt, gather_distributed=True) * args.grad_accum

                    scaler.scale(loss).backward()

                    # Re-encode with gradients using chain rule
                    embs_per_micro = args.batch_size * 3 if args.sectioned else args.batch_size
                    img_grads = all_img.grad.split(embs_per_micro)
                    txt_grads = all_txt.grad.split(embs_per_micro)

                    for cached_batch, img_grad, txt_grad in zip(cached_batches, img_grads, txt_grads):
                        with torch.cuda.amp.autocast(enabled=args.amp and device.type == "cuda", dtype=torch.bfloat16 if args.amp else torch.float32):
                            if args.sectioned:
                                iv = build_sectioned_image_variants(
                                    cached_batch.ct, cached_batch.totalseg,
                                    cached_batch.section_names, section_label_map,
                                    mask_channel_mode=args.mask_channel_mode,
                                )
                                img_emb_grad = mm.encode_image(iv)
                                if args.section_mode == "direct":
                                    txt_emb_grad = mm.encode_text_sectioned_direct(
                                        cached_batch.global_texts, cached_batch.section_names,
                                        cached_batch.section_texts, max_len=args.max_text_len,
                                        chest2vec_batch_size=args.chest2vec_batch_size,
                                    )
                                else:
                                    txt_emb_grad = mm.encode_text_sectioned(
                                        cached_batch.global_texts, cached_batch.section_names,
                                        max_len=args.max_text_len,
                                    )
                            else:
                                img_emb_grad = mm.encode_image(cached_batch.ct)
                                txt_emb_grad = mm.encode_text(cached_batch.texts, max_len=args.max_text_len, chest2vec_batch_size=args.chest2vec_batch_size)
                        surrogate = (img_emb_grad * img_grad.detach()).sum() + (txt_emb_grad * txt_grad.detach()).sum()
                        surrogate.backward()

                    cached_img_embs = []
                    cached_txt_embs = []
                    cached_batches = []
            else:
                # ===== STANDARD MODE (no caching) =====
                with torch.cuda.amp.autocast(enabled=args.amp and device.type == "cuda", dtype=torch.bfloat16 if args.amp else torch.float32):
                    if args.sectioned:
                        loss, local_loss_t, global_loss_t, global_only_loss_t, _, _ = mm.forward_sectioned(
                            batch, section_label_map,
                            max_text_len=args.max_text_len,
                            chest2vec_batch_size=args.chest2vec_batch_size,
                            section_mode=args.section_mode,
                            mask_channel_mode=args.mask_channel_mode,
                        )
                        local_loss_val = float(local_loss_t.item())
                        global_loss_val = float(global_loss_t.item())
                        global_only_loss_val = float(global_only_loss_t.item())
                    else:
                        loss, _, _ = mm(
                            batch,
                            max_text_len=args.max_text_len,
                            chest2vec_batch_size=args.chest2vec_batch_size,
                        )
                    loss = loss / args.grad_accum

                scaler.scale(loss).backward()

            if is_last_micro:
                # Log contrastive batch info on first step only
                if global_step == 0 and get_rank() == 0:
                    local_batch = args.batch_size
                    if args.grad_cache and args.grad_accum > 1:
                        local_samples = local_batch * args.grad_accum
                    else:
                        local_samples = local_batch
                    if args.sectioned:
                        local_samples *= 3  # 3 variants per sample
                    global_samples = local_samples * world
                    negatives = global_samples - 1
                    rank0_print(f"╔══════════════════════════════════════════════════════════╗")
                    rank0_print(f"║ Contrastive Learning Setup:                              ║")
                    rank0_print(f"║   Batch per GPU: {local_batch:<5} × GPUs: {world:<3} = {local_batch * world:<5} per forward   ║")
                    if args.sectioned:
                        rank0_print(f"║   Sectioned: 3 variants/sample                           ║")
                    if args.grad_cache and args.grad_accum > 1:
                        rank0_print(f"║   Grad cache: ON  × grad_accum: {args.grad_accum:<3} = {global_samples:<5} total      ║")
                    else:
                        rank0_print(f"║   Grad cache: OFF (standard accumulation)                ║")
                    rank0_print(f"║   ➜ Global batch size: {global_samples:<5}                             ║")
                    rank0_print(f"║   ➜ Negatives per sample: {negatives:<5}                          ║")
                    rank0_print(f"╚══════════════════════════════════════════════════════════╝")

                _sync_gradients(optimizer)
                scaler.unscale_(optimizer)

                if global_step % args.log_every == 0 and get_rank() == 0:
                    total_lora_grad = check_lora_gradients(model)
                else:
                    total_lora_grad = 0.0

                if args.max_grad_norm and args.max_grad_norm > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)

                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)

                # clamp logit_scale for stability
                with torch.no_grad():
                    mm.loss_fn.logit_scale.clamp_(max=math.log(100.0))
                    if args.sectioned:
                        mm.sectioned_loss_fn.logit_scale.clamp_(max=math.log(100.0))

                # logging
                if global_step % args.log_every == 0 and get_rank() == 0:
                    current_lr = optimizer.param_groups[0]['lr']

                    if args.sectioned:
                        log = {
                            "train/loss": float(loss.item() * args.grad_accum),
                            "train/local_loss": local_loss_val,
                            "train/global_loss": global_loss_val,
                            "train/global_only_loss": global_only_loss_val,
                            "train/logit_scale": float(mm.sectioned_loss_fn.logit_scale.exp().item()),
                            "train/logit_bias": float(mm.sectioned_loss_fn.logit_bias.item()),
                            "train/lora_grad_norm": total_lora_grad,
                            "train/lr": current_lr,
                            "train/epoch": epoch,
                        }
                        rank0_print(
                            f"epoch={epoch} step={global_step} "
                            f"loss={log['train/loss']:.4f} local={local_loss_val:.4f} global={global_loss_val:.4f} global_only={global_only_loss_val:.4f} "
                            f"scale={log['train/logit_scale']:.3f} bias={log['train/logit_bias']:.3f} "
                            f"lora_grad={total_lora_grad:.4f} lr={current_lr:.2e}"
                        )
                    else:
                        log = {
                            "train/loss": float(loss.item() / args.grad_accum) if args.grad_cache else float(loss.item() * args.grad_accum),
                            "train/logit_scale": float(mm.loss_fn.logit_scale.exp().item()),
                            "train/logit_bias": float(mm.loss_fn.logit_bias.item()),
                            "train/lora_grad_norm": total_lora_grad,
                            "train/lr": current_lr,
                            "train/epoch": epoch,
                        }
                        rank0_print(
                            f"epoch={epoch} step={global_step} "
                            f"loss={log['train/loss']:.4f} "
                            f"scale={log['train/logit_scale']:.3f} bias={log['train/logit_bias']:.3f} "
                            f"lora_grad={total_lora_grad:.4f} lr={current_lr:.2e}"
                        )

                    if args.wandb_mode != "disabled":
                        wandb.log(log, step=global_step)

                global_step += 1

        # ---- validation end of epoch
        if args.sectioned:
            val_loss, val_local, val_global, metrics = validate_sectioned(
                model=model,
                val_loader=val_loader,
                device=device,
                amp=args.amp and device.type == "cuda",
                max_text_len=args.max_text_len,
                section_label_map=section_label_map,
                sim_chunk_elems=args.val_sim_chunk_elems,
                max_val_samples=args.max_val_samples,
                section_mode=args.section_mode,
                mask_channel_mode=args.mask_channel_mode,
            )
        else:
            val_loss, metrics = validate(
                model=model,
                val_loader=val_loader,
                device=device,
                amp=args.amp and device.type == "cuda",
                max_text_len=args.max_text_len,
                chest2vec_batch_size=args.chest2vec_batch_size,
                sim_chunk_elems=args.val_sim_chunk_elems,
                max_val_samples=args.max_val_samples,
            )

        if get_rank() == 0:
            log = {"val/loss": float(val_loss), "val/epoch": epoch}
            if args.sectioned:
                log["val/local_loss"] = float(val_local)
                log["val/global_loss"] = float(val_global)
            if metrics:
                # Log all metrics with val/ prefix
                for mk, mv in metrics.items():
                    log[f"val/{mk}"] = float(mv)

            if args.sectioned:
                rank0_print(
                    f"[VAL] epoch={epoch} loss={val_loss:.4f} local={val_local:.4f} global={val_global:.4f}"
                )
                # Global retrieval
                rank0_print(
                    f"  Global: i2t@1={log.get('val/i2t_top1', 0):.3f} i2t@5={log.get('val/i2t_top5', 0):.3f} i2t@10={log.get('val/i2t_top10', 0):.3f} "
                    f"t2i@1={log.get('val/t2i_top1', 0):.3f} t2i@5={log.get('val/t2i_top5', 0):.3f} t2i@10={log.get('val/t2i_top10', 0):.3f}"
                )
                # Per-section retrieval
                for sec_name in SAMPLABLE_SECTIONS:
                    short = sec_name.lower().replace(" + ", "_").replace(" & ", "_").replace(" ", "_")
                    key_i2t1 = f"val/{short}_i2t_top1"
                    if key_i2t1 in log:
                        rank0_print(
                            f"  {sec_name}: "
                            f"i2t@1={log.get(f'val/{short}_i2t_top1', 0):.3f} "
                            f"i2t@5={log.get(f'val/{short}_i2t_top5', 0):.3f} "
                            f"t2i@1={log.get(f'val/{short}_t2i_top1', 0):.3f} "
                            f"t2i@5={log.get(f'val/{short}_t2i_top5', 0):.3f}"
                        )
            else:
                rank0_print(
                    f"[VAL] epoch={epoch} loss={val_loss:.4f} "
                    + (f"i2t@1={log.get('val/i2t_top1', 0):.3f} i2t@5={log.get('val/i2t_top5', 0):.3f} i2t@10={log.get('val/i2t_top10', 0):.3f} "
                       f"t2i@1={log.get('val/t2i_top1', 0):.3f} t2i@5={log.get('val/t2i_top5', 0):.3f} t2i@10={log.get('val/t2i_top10', 0):.3f}")
                )

            if args.wandb_mode != "disabled":
                wandb.log(log, step=global_step)

            # checkpoint
            ckpt = {
                "epoch": epoch,
                "global_step": global_step,
                "model": (model.module if hasattr(model, "module") else model).state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "scaler": scaler.state_dict() if args.amp else None,
                "best_val_loss": best_val_loss,
                "args": vars(args),
                "vision_dim": vision_dim,
                "embed_dim_effective": embed_dim,
            }

            if get_rank() == 0:
                ckpt_path = os.path.join(args.out_dir, f"epoch_{epoch}.pt")
                torch.save(ckpt, ckpt_path)
                rank0_print(f"Saved: {ckpt_path}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                ckpt_path = os.path.join(args.out_dir, f"best.pt")
                torch.save(ckpt, ckpt_path)
                rank0_print(f"Saved: {ckpt_path}")

    if get_rank() == 0:
        ckpt_path = os.path.join(args.out_dir, f"last.pt")
        torch.save(ckpt, ckpt_path)
        rank0_print(f"Saved: {ckpt_path}")

        if args.wandb_mode != "disabled":
            wandb.finish()

    cleanup_distributed()


if __name__ == "__main__":
    main()
