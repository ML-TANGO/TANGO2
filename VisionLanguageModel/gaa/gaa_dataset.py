"""
GAA-aware Dataset and Data Collator

Extends LLaVADataset to load per-sample bounding boxes used as privileged
information for the Geometric Attention Alignment loss.

Expected JSON format (superset of LLaVA format):
  {
    "id": "...",
    "image": "filename.png",
    "conversations": [...],
    "bboxes": [[x1, y1, x2, y2], ...]   ← normalized [0, 1] coords, may be absent
  }

When "bboxes" is absent or empty the sample still trains normally via L_SFT;
only L_geo is skipped for that sample.
"""
from typing import Dict, List
from dataclasses import dataclass

from data.dataset import LLaVADataset, DataCollatorForVLM


class GAADataset(LLaVADataset):
    """LLaVADataset extended with bounding-box loading for GAA training."""

    def __getitem__(self, idx: int) -> Dict:
        item = super().__getitem__(idx)
        item["bboxes"] = self.data[idx].get("bboxes", [])
        return item


@dataclass
class GAADataCollator(DataCollatorForVLM):
    """
    DataCollatorForVLM extended to pass bounding boxes through the batch.

    Bboxes have variable cardinality per sample and cannot be stacked into
    a single tensor, so they are kept as a plain Python list.
    """

    def __call__(self, batch: List[Dict]) -> Dict:
        bboxes = [b.get("bboxes", []) for b in batch]
        # Strip bboxes so the parent collator only sees tensor-compatible fields
        clean = [{k: v for k, v in b.items() if k != "bboxes"} for b in batch]
        collated = super().__call__(clean)
        collated["bboxes"] = bboxes
        return collated
