"""
Dataset and collator for the native Gemma 4 multimodal model.

이 저장소의 LLaVADataset 과 목적은 같지만 만드는 것이 다르다. VisionLanguageModelV2
는 동결 CLIP 과 프로젝터를 직접 들고 있어 pixel_values 를 CLIPImageProcessor 로
만들면 됐다. Gemma 4 는 비전 타워와 커넥터를 자기가 들고 있고, 전처리 단계에서
이미 패치화까지 마친 (2520, 768) 텐서와 그 패치들의 (x, y) 좌표를 함께 넘겨받는다.
그래서 Gemma4Processor 를 그대로 쓴다.

라벨 마스킹은 실측에 기반한다.
  - add_generation_prompt=True 로 만든 프롬프트가 전체 시퀀스의 정확한 접두이다.
    그래서 앞 prompt_len 개를 -100 으로 덮으면 사용자 차례 전체가 가려진다.
  - mm_token_type_ids > 0 인 자리가 image_token 자리와 정확히 일치한다. 이미지
    토큰은 프롬프트 안에 있어 이미 가려지지만, 형식이 바뀌어도 새지 않도록
    이 마스크로 한 번 더 덮는다.

같은 이미지에 대해 프롬프트만 만든 것과 전체를 만든 것의 pixel_values 와
image_position_ids 가 동일함을 확인했으므로, 전체 쪽 것만 쓴다.
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import torch
from PIL import Image
from torch.utils.data import Dataset

# 라벨에서 무시할 값. HF 의 관례를 따른다.
IGNORE_INDEX = -100

# LLaVA 형식 JSON 의 화자 표기
HUMAN = "human"
GPT = "gpt"

# 사용자 메시지 안의 이미지 자리표시자. Gemma 4 는 자체 image_token 을 쓰므로
# 프롬프트 문자열에서는 걷어내고, 이미지는 채팅 템플릿의 image 항목으로 넣는다.
IMAGE_PLACEHOLDER = "<image>"


def _strip_placeholder(text: str) -> str:
    return text.replace(IMAGE_PLACEHOLDER, "").lstrip("\n")


def _mask_prompt_and_images(input_ids, prompt_len, mm_token_type_ids):
    labels = input_ids.clone()
    labels[:prompt_len] = IGNORE_INDEX
    if mm_token_type_ids is not None:
        labels[mm_token_type_ids > 0] = IGNORE_INDEX
    return labels


class Gemma4SDSDataset(Dataset):
    """
    LLaVA 형식 JSON 을 Gemma 4 채팅 템플릿으로 옮긴다.

    Args:
        data_path  : LLaVA 형식 JSON 경로
        image_dir  : 이미지 루트. 샘플의 "image" 가 이 아래의 상대경로다
        processor  : Gemma4Processor
        max_seq_len: 이 길이를 넘으면 뒤를 자른다
    """

    def __init__(self, data_path: str, image_dir: str, processor,
                 max_seq_len: int = 2048):
        super().__init__()
        self.image_dir = image_dir
        self.processor = processor
        self.max_seq_len = max_seq_len

        with open(data_path, encoding="utf-8") as f:
            self.data = json.load(f)

        print(f"[Gemma4Dataset] {len(self.data):,}건  ({data_path})")
        print(f"[Gemma4Dataset] image_dir   : {image_dir}")
        print(f"[Gemma4Dataset] max_seq_len : {max_seq_len}")

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict:
        sample = self.data[idx]

        human, gpt = "", ""
        for turn in sample["conversations"]:
            if turn["from"] == HUMAN:
                human = turn["value"]
            elif turn["from"] == GPT:
                gpt = turn["value"]
        human = _strip_placeholder(human)

        path = os.path.join(self.image_dir, sample["image"])
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            # 적재 실패를 조용히 넘기면 채점에서만 드러난다. 여기서 알린다.
            print(f"[Gemma4Dataset] 이미지 적재 실패, 검은 이미지로 대체: {path}")
            image = Image.new("RGB", (896, 896), color=0)

        user_turn = {"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": human},
        ]}
        full_msgs = [user_turn, {"role": "assistant",
                                 "content": [{"type": "text", "text": gpt}]}]

        full = self.processor.apply_chat_template(
            full_msgs, add_generation_prompt=False,
            tokenize=True, return_dict=True, return_tensors="pt")
        prompt = self.processor.apply_chat_template(
            [user_turn], add_generation_prompt=True,
            tokenize=True, return_dict=True, return_tensors="pt")

        input_ids = full["input_ids"][0]
        mm_ids = full["mm_token_type_ids"][0]
        prompt_len = min(prompt["input_ids"].shape[1], len(input_ids))

        if len(input_ids) > self.max_seq_len:
            input_ids = input_ids[: self.max_seq_len]
            mm_ids = mm_ids[: self.max_seq_len]
            prompt_len = min(prompt_len, self.max_seq_len)

        return {
            "input_ids": input_ids,
            "labels": _mask_prompt_and_images(input_ids, prompt_len, mm_ids),
            "mm_token_type_ids": mm_ids,
            "pixel_values": full["pixel_values"][0],
            "image_position_ids": full["image_position_ids"][0],
        }


class Gemma4TextDataset(Dataset):
    """
    이미지 없는 명령-응답 데이터. LLaMarine 단계에 쓴다.

    .parquet 는 instruction / output 컬럼을, .json 은 같은 키를 가진 객체의
    목록을 기대한다. train_text_lora.py 의 MarineTextDataset 과 같은 규약이다.
    """

    def __init__(self, data_path: str, processor, max_seq_len: int = 2048):
        super().__init__()
        self.processor = processor
        self.max_seq_len = max_seq_len

        if data_path.endswith(".parquet"):
            import pandas as pd
            self.records = pd.read_parquet(data_path).to_dict("records")
        else:
            with open(data_path, encoding="utf-8") as f:
                self.records = json.load(f)

        print(f"[Gemma4TextDataset] {len(self.records):,}건  ({data_path})")

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict:
        item = self.records[idx]
        instruction = item.get("instruction") or item.get("input") or ""
        output = item.get("output") or item.get("response") or ""

        user_turn = {"role": "user",
                     "content": [{"type": "text", "text": instruction}]}
        full_msgs = [user_turn, {"role": "assistant",
                                 "content": [{"type": "text", "text": output}]}]

        full = self.processor.apply_chat_template(
            full_msgs, add_generation_prompt=False,
            tokenize=True, return_dict=True, return_tensors="pt")
        prompt = self.processor.apply_chat_template(
            [user_turn], add_generation_prompt=True,
            tokenize=True, return_dict=True, return_tensors="pt")

        input_ids = full["input_ids"][0]
        prompt_len = min(prompt["input_ids"].shape[1], len(input_ids))
        if len(input_ids) > self.max_seq_len:
            input_ids = input_ids[: self.max_seq_len]
            prompt_len = min(prompt_len, self.max_seq_len)

        return {
            "input_ids": input_ids,
            "labels": _mask_prompt_and_images(input_ids, prompt_len, None),
        }


@dataclass
class Gemma4Collator:
    """
    input_ids 와 labels 를 배치 최댓값까지 오른쪽으로 채운다.

    pixel_values 와 image_position_ids 는 프로세서가 이미 2520 패치로 길이를
    맞춰 내보내므로 그대로 쌓기만 한다. 텍스트 전용 배치에는 없으므로 건너뛴다.
    """
    pad_token_id: int

    def __call__(self, batch: List[Dict]) -> Dict[str, torch.Tensor]:
        max_len = max(b["input_ids"].shape[0] for b in batch)

        ids, labels, attn, mm = [], [], [], []
        for b in batch:
            n = max_len - b["input_ids"].shape[0]
            i = b["input_ids"]
            l = b["labels"]
            if n > 0:
                i = torch.cat([i, torch.full((n,), self.pad_token_id, dtype=i.dtype)])
                l = torch.cat([l, torch.full((n,), IGNORE_INDEX, dtype=l.dtype)])
            ids.append(i)
            labels.append(l)
            attn.append((i != self.pad_token_id).long())
            if "mm_token_type_ids" in b:
                m = b["mm_token_type_ids"]
                if n > 0:
                    m = torch.cat([m, torch.zeros(n, dtype=m.dtype)])
                mm.append(m)

        out = {
            "input_ids": torch.stack(ids),
            "attention_mask": torch.stack(attn),
            "labels": torch.stack(labels),
        }
        if mm:
            out["mm_token_type_ids"] = torch.stack(mm)
        if "pixel_values" in batch[0]:
            out["pixel_values"] = torch.stack([b["pixel_values"] for b in batch])
            out["image_position_ids"] = torch.stack(
                [b["image_position_ids"] for b in batch])
        return out
