"""커밋 이름 → 평가할 가중치 디렉토리.

차트는 모델의 commit_models 를 `/models/checkpoints` 에 RO 로 마운트한다(pod.yaml).
컨테이너가 받는 것은 **커밋 이름 한 조각**이지 경로가 아니다 — 경로를 받으면 params 로
마운트 밖을 열 수 있고 NFS 실경로가 로그·응답으로 샌다(evaluate-intent 와 같은 규약).

커밋은 두 형식이 있다.
  - merged: `config.json` + 전체 가중치 — 그대로 올린다.
  - lora:   `adapter_config.json` + 어댑터 — 서빙 파드(deployment_llm playground.py)와 같이
            기반 가중치 위에 `merge_and_unload` 로 병합해 /tmp 에 쓴 뒤 올린다. 서빙과 같은
            가중치를 채점해야 "배포가 서빙 중인 커밋의 점수"라는 뜻이 성립한다.
기반은 어댑터 설정의 base_model_name_or_path 가 가리키는 커밋이고, 그 경로가 이 모델의
commit_models 밖이면 첫 커밋(`source_model` = fb_utils TYPE.MODEL_FIRST_COMMIT_NAME)이다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from typing import Callable, Optional

CHECKPOINT_ROOT = "/models/checkpoints"
SOURCE_MODEL = "source_model"
MERGE_DIR = "/tmp/lmeval-merged"

_COMMIT_SEG_RE = re.compile(r"/commit_models/([^/]+)/?$")
_TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                    "tokenizer.model", "vocab.json", "merges.txt", "chat_template.jinja")


@dataclass(frozen=True)
class Checkpoint:
    name: str
    path: str                    # 컨테이너 안 실경로(metrics 에는 싣지 않는다)
    format: str                  # merged | lora
    base: Optional[str] = None   # lora 의 기반 커밋 이름


def _contained(root: str, path: str) -> str:
    real = os.path.realpath(path)
    root_real = os.path.realpath(root)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise ValueError("checkpoint path escapes the mounted checkpoint root")
    return real


def _segment(name: str, what: str) -> str:
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"{what} must be a single path segment")
    return name


def _base_of(adapter_dir: str) -> str:
    try:
        with open(os.path.join(adapter_dir, "adapter_config.json"), encoding="utf-8") as fh:
            ref = str(json.load(fh).get("base_model_name_or_path") or "")
    except (OSError, ValueError):
        ref = ""
    m = _COMMIT_SEG_RE.search(ref)
    return m.group(1) if m else SOURCE_MODEL


def resolve(name: str, root: str = CHECKPOINT_ROOT) -> Checkpoint:
    name = _segment(name, "checkpoint_name")
    path = _contained(root, os.path.join(root, name))
    if not os.path.isdir(path):
        raise ValueError(f"checkpoint not found: {name} (모델의 commit_models 에 그 이름의 커밋이 있는지 확인)")
    if os.path.isfile(os.path.join(path, "config.json")):
        return Checkpoint(name=name, path=path, format="merged")
    if os.path.isfile(os.path.join(path, "adapter_config.json")):
        base = _segment(_base_of(path), "adapter base commit")
        base_path = _contained(root, os.path.join(root, base))
        if base == name or not os.path.isfile(os.path.join(base_path, "config.json")):
            raise ValueError(f"{name}: LoRA 어댑터의 기반 가중치({base})를 찾지 못했다 — "
                             "merged HF 체크포인트가 있어야 한다")
        return Checkpoint(name=name, path=path, format="lora", base=base)
    raise ValueError(f"{name}: config.json 도 adapter_config.json 도 없다 — "
                     "merged HF 체크포인트 또는 LoRA 어댑터가 필요하다")


def materialize(ckpt: Checkpoint, root: str = CHECKPOINT_ROOT,
                log: Callable[[str], None] = print) -> str:
    """vLLM 이 올릴 디렉토리. merged 는 그대로, lora 는 병합본을 MERGE_DIR 에 만든다."""
    if ckpt.format == "merged":
        return ckpt.path
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.time()
    base_path = os.path.join(root, ckpt.base)
    shutil.rmtree(MERGE_DIR, ignore_errors=True)
    model = AutoModelForCausalLM.from_pretrained(base_path, dtype=torch.bfloat16)
    merged = PeftModel.from_pretrained(model, ckpt.path).merge_and_unload()
    merged.save_pretrained(MERGE_DIR, safe_serialization=True)
    # 토크나이저는 커밋(어댑터 쪽)에 있으면 그것을 — 학습이 특수 토큰을 바꿨을 수 있다.
    tok_src = ckpt.path if any(os.path.isfile(os.path.join(ckpt.path, f))
                               for f in _TOKENIZER_FILES) else base_path
    AutoTokenizer.from_pretrained(tok_src).save_pretrained(MERGE_DIR)
    log(f"[checkpoint] merged LoRA {ckpt.name} onto {ckpt.base} in {time.time() - t0:.0f}s")
    return MERGE_DIR
