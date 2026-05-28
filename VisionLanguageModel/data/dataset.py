"""
Dataset and Collator for VisionLanguageModelV2

Supports LLaVA-format JSON:
  [{"id": "...", "image": "filename.jpg",
    "conversations": [
        {"from": "human", "value": "<image>\nQuestion"},
        {"from": "gpt",   "value": "Answer"}
    ]}, ...]

Label masking:
  - All prompt tokens (system + user message) → -100
  - Image feature positions → -100 (handled by model.forward)
  - Pad tokens → -100
  - Only the assistant response tokens contribute to loss
"""
import os
import json
import torch
from torch.utils.data import Dataset
from PIL import Image
from typing import Optional, Dict, List
from dataclasses import dataclass


class LLaVADataset(Dataset):
    """
    Dataset for LLaVA-format JSON conversations with single image per sample.

    Args:
        data_path  : path to chat.json (or any JSON with the LLaVA format)
        image_dir  : directory containing the images
        tokenizer  : HuggingFace tokenizer (should have <image> as special token)
        image_processor: processor for image → pixel_values (CLIPImageProcessor, etc.)
        max_seq_len: maximum total token length (sequences are truncated, not skipped)
        image_token : token string for image placeholder (default "<image>")
    """

    HUMAN = "human"
    GPT   = "gpt"

    def __init__(
        self,
        data_path: str,
        image_dir: str,
        tokenizer,
        image_processor,
        max_seq_len: int = 2048,
        image_token: str = "<image>",
    ):
        super().__init__()
        self.image_dir       = image_dir
        self.tokenizer       = tokenizer
        self.image_processor = image_processor
        self.max_seq_len     = max_seq_len
        self.image_token     = image_token
        self.image_token_id  = tokenizer.convert_tokens_to_ids(image_token)

        with open(data_path, "r") as f:
            self.data = json.load(f)

        print(f"[Dataset] Loaded {len(self.data):,} samples from {data_path}")
        print(f"[Dataset] image_dir    : {image_dir}")
        print(f"[Dataset] max_seq_len  : {max_seq_len}")
        print(f"[Dataset] image_token  : '{image_token}' (id={self.image_token_id})")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict:
        sample = self.data[idx]
        convs  = sample["conversations"]

        # ── Parse conversation ────────────────────────────────────────────────
        human_msg = ""
        gpt_msg   = ""
        for turn in convs:
            if turn["from"] == self.HUMAN:
                human_msg = turn["value"]
            elif turn["from"] == self.GPT:
                gpt_msg = turn["value"]

        # Normalize: ensure <image> is in the human message
        if self.image_token not in human_msg:
            human_msg = self.image_token + "\n" + human_msg

        # ── Tokenize: full conversation ───────────────────────────────────────
        #
        # Llama 3.1 chat template:
        #   <|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n...<|eot_id|>
        #   <|start_header_id|>user<|end_header_id|>\n\n{human}<|eot_id|>
        #   <|start_header_id|>assistant<|end_header_id|>\n\n{gpt}<|eot_id|>

        full_msgs = [
            {"role": "user",      "content": human_msg},
            {"role": "assistant", "content": gpt_msg},
        ]
        prompt_msgs = [
            {"role": "user", "content": human_msg},
        ]

        full_text   = self.tokenizer.apply_chat_template(
            full_msgs, tokenize=False, add_generation_prompt=False
        )
        prompt_text = self.tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )

        # Tokenize without adding extra BOS (apply_chat_template already adds it)
        full_ids   = self.tokenizer(
            full_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids[0]
        prompt_ids = self.tokenizer(
            prompt_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids[0]

        # ── Truncate to max_seq_len ───────────────────────────────────────────
        if len(full_ids) > self.max_seq_len:
            full_ids = full_ids[:self.max_seq_len]

        prompt_len = min(len(prompt_ids), len(full_ids))

        # ── Build labels: mask prompt, keep response ──────────────────────────
        labels = full_ids.clone()
        labels[:prompt_len] = -100   # mask system + user turns

        # The <image> token is inside the user prompt → already masked.
        # model.forward() will expand it to N image tokens, all with label=-100.

        # ── Load and preprocess image ─────────────────────────────────────────
        image_path = os.path.join(self.image_dir, sample["image"])
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as e:
            # Return a black image on load failure
            image = Image.new("RGB", (336, 336), color=0)

        pixel_values = self.image_processor(
            images=image, return_tensors="pt"
        ).pixel_values[0]  # (C, H, W)

        return {
            "input_ids":      full_ids,
            "labels":         labels,
            "pixel_values":   pixel_values,
        }


# ── Collator ──────────────────────────────────────────────────────────────────

@dataclass
class DataCollatorForVLM:
    """
    Pads input_ids, labels to the longest sequence in the batch.
    Stacks pixel_values.
    """
    pad_token_id: int
    label_pad_id: int = -100

    def __call__(self, batch: List[Dict]) -> Dict[str, torch.Tensor]:
        input_ids_list    = [b["input_ids"]    for b in batch]
        labels_list       = [b["labels"]       for b in batch]
        pixel_values_list = [b["pixel_values"] for b in batch]

        # Pad to max length in batch
        max_len = max(ids.shape[0] for ids in input_ids_list)

        padded_ids    = []
        padded_labels = []
        attn_masks    = []

        for ids, lbl in zip(input_ids_list, labels_list):
            pad_len = max_len - ids.shape[0]
            if pad_len > 0:
                pad_ids = torch.full((pad_len,), self.pad_token_id, dtype=ids.dtype)
                pad_lbl = torch.full((pad_len,), self.label_pad_id, dtype=lbl.dtype)
                ids = torch.cat([ids, pad_ids], dim=0)
                lbl = torch.cat([lbl, pad_lbl], dim=0)

            attn = (ids != self.pad_token_id).long()
            padded_ids.append(ids)
            padded_labels.append(lbl)
            attn_masks.append(attn)

        return {
            "input_ids":      torch.stack(padded_ids,    dim=0),
            "attention_mask": torch.stack(attn_masks,    dim=0),
            "labels":         torch.stack(padded_labels, dim=0),
            "pixel_values":   torch.stack(pixel_values_list, dim=0),
        }
