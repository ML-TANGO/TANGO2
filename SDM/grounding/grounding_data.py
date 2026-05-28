"""
CT-JEPA v2 Grounding Data
===========================
Dataset and data loading for ReXGroundingCT evaluation and fine-tuning.

NPZ format at /data/preprocessed/:
  - ct: (1, 192, 256, 256) float — pre-windowed HU [-1000, 2000]
  - totalseg: (1, 192, 256, 256) uint16 — TotalSeg labels
  - rex: (num_findings, 192, 256, 256) uint16 — instance-labeled masks

dataset.json format:
  {train/val/test: [{name, findings: {idx: text}, entity_counts, categories, ...}]}
"""

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import json
import os
from typing import Dict, List, Optional, Tuple

from ..data.dataset import apply_window, compute_region_masks_s2, collate_fn as base_collate_fn, WINDOW_PARAMS


class ReXGroundingDataset(Dataset):
    """
    Dataset for ReXGroundingCT grounding evaluation and fine-tuning.

    Each sample is a (volume, finding_text, ground_truth_mask) triple.
    Multi-finding cases yield one sample per finding.
    """

    def __init__(self, dataset_json_path: str, data_root: str,
                 split: str = "test", max_text_len: int = 256,
                 window_id: Optional[int] = None):
        """
        Args:
            dataset_json_path: path to rexgrounding/dataset.json
            data_root: path to /data/preprocessed/
            split: "train", "val", or "test"
            max_text_len: max tokens for text
            window_id: if None, randomly sample; if int (0/1/2), use fixed window
        """
        super().__init__()
        self.data_root = data_root
        self.max_text_len = max_text_len
        self.fixed_window_id = window_id

        with open(dataset_json_path, 'r') as f:
            dataset = json.load(f)

        entries = dataset.get(split, [])

        # Flatten: one sample per finding
        self.samples = []
        for entry in entries:
            name = entry['name']
            npz_name = name.replace('.nii.gz', '.npz')
            npz_path = os.path.join(data_root, npz_name)

            if not os.path.exists(npz_path):
                continue

            findings = entry.get('findings', {})
            entity_counts = entry.get('entity_counts', {})
            categories = entry.get('categories', {})

            for finding_idx, finding_text in findings.items():
                self.samples.append({
                    'npz_path': npz_path,
                    'npz_name': npz_name,
                    'finding_idx': int(finding_idx),
                    'finding_text': finding_text,
                    'entity_count': entity_counts.get(finding_idx, 1),
                    'category': categories.get(finding_idx, 'unknown'),
                    'num_findings': len(findings),
                    'case_name': name,
                })

    def __len__(self):
        return len(self.samples)

    def _simple_tokenize(self, text: str) -> Tuple[torch.Tensor, torch.Tensor]:
        """Placeholder tokenization. Replace with BiomedCLIP tokenizer."""
        tokens = [ord(c) % 30000 for c in text[:self.max_text_len]]
        ids = torch.tensor(tokens, dtype=torch.long)
        mask = torch.ones(len(tokens), dtype=torch.long)
        if len(tokens) < self.max_text_len:
            pad_len = self.max_text_len - len(tokens)
            ids = torch.cat([ids, torch.zeros(pad_len, dtype=torch.long)])
            mask = torch.cat([mask, torch.zeros(pad_len, dtype=torch.long)])
        return ids, mask

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        sample = self.samples[idx]

        data = np.load(sample['npz_path'])
        ct_hu = data['ct']
        if ct_hu.ndim == 4:
            ct_hu = ct_hu[0]

        totalseg = data.get('totalseg')
        if totalseg is not None and totalseg.ndim == 4:
            totalseg = totalseg[0]

        # Window selection
        if self.fixed_window_id is not None:
            window_id = self.fixed_window_id
        else:
            window_id = np.random.randint(0, len(WINDOW_PARAMS))

        volume = apply_window(ct_hu, window_id)
        volume = torch.from_numpy(volume).float().unsqueeze(0)  # (1, D, H, W)

        # Ground truth mask
        rex = data.get('rex')
        if rex is not None:
            finding_idx = sample['finding_idx']
            if finding_idx < rex.shape[0]:
                gt_mask = torch.from_numpy((rex[finding_idx] > 0).astype(np.float32))
            else:
                gt_mask = torch.zeros(192, 256, 256)
        else:
            gt_mask = torch.zeros(192, 256, 256)

        # Text
        ids, mask = self._simple_tokenize(sample['finding_text'])

        # Region masks
        region_masks_s2 = None
        if totalseg is not None:
            region_masks_s2 = compute_region_masks_s2(totalseg)

        output = {
            'volume': volume,
            'window_id': torch.tensor(window_id, dtype=torch.long),
            'gt_mask': gt_mask,                        # (D, H, W) binary
            'text_input_ids': ids,
            'text_attention_mask': mask,
            'region_masks_s2': region_masks_s2,
            'finding_idx': sample['finding_idx'],
            'finding_text': sample['finding_text'],
            'category': sample['category'],
            'case_name': sample['case_name'],
        }

        return output


def grounding_collate_fn(batch: list) -> dict:
    """Collate for grounding dataset — handles string fields and gt_mask."""
    B = len(batch)

    collated = {
        'volume': torch.stack([b['volume'] for b in batch]),
        'window_id': torch.stack([b['window_id'] for b in batch]),
        'gt_mask': torch.stack([b['gt_mask'] for b in batch]),
        'text_input_ids': torch.stack([b['text_input_ids'] for b in batch]),
        'text_attention_mask': torch.stack([b['text_attention_mask'] for b in batch]),
        'finding_idx': [b['finding_idx'] for b in batch],
        'finding_text': [b['finding_text'] for b in batch],
        'category': [b['category'] for b in batch],
        'case_name': [b['case_name'] for b in batch],
    }

    if batch[0]['region_masks_s2'] is not None:
        collated['region_masks_s2'] = torch.stack([b['region_masks_s2'] for b in batch])
    else:
        collated['region_masks_s2'] = None

    return collated


def create_grounding_dataloader(dataset_json_path: str, data_root: str,
                                 split: str = "test", batch_size: int = 1,
                                 num_workers: int = 4, window_id: Optional[int] = None,
                                 ) -> DataLoader:
    """Create a DataLoader for ReXGroundingCT evaluation."""
    dataset = ReXGroundingDataset(
        dataset_json_path=dataset_json_path,
        data_root=data_root,
        split=split,
        window_id=window_id,
    )

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=(split == "train"),
        num_workers=num_workers,
        collate_fn=grounding_collate_fn,
        pin_memory=True,
        drop_last=(split == "train"),
    )
