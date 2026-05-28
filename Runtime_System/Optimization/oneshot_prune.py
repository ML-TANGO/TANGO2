#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLaMA-2 13B 원샷 프루닝(One-shot pruning) 스크립트
- Hugging Face Transformers 기반
- 글로벌 L1(magnitude) 비구조적 프루닝
- 프루닝 후 마스크 영구 반영(prune.remove)
- 간단 PPL 평가 및 희소도 리포트

사용 예시:
python llama2_13b_oneshot_prune.py \
  --model_id meta-llama/Llama-2-13b-hf \
  --sparsity 0.5 \
  --save_dir ./llama2-13b-pruned-50 \
  --eval_texts "Large language models are powerful." "프루닝 후 성능 확인용 텍스트"

사전 준비:
- Hugging Face에서 meta-llama/Llama-2-13b-hf 접근 권한 승인
- `huggingface-cli login`
- VRAM 여유(다중 GPU면 device_map="auto"가 자동 분산)
"""

import argparse
import math
from typing import List, Tuple

import torch
from torch import nn
import torch.nn.utils.prune as prune
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase


def set_seed(seed: int = 42):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def dtype_from_str(s: str):
    s = s.lower()
    if s == "fp16":
        return torch.float16
    if s == "bf16":
        return torch.bfloat16
    return torch.float32


def collect_linear_targets(model: PreTrainedModel, include: List[str], exclude: List[str]) -> List[Tuple[nn.Module, str]]:
    targets = []
    for name, m in model.named_modules():
        if isinstance(m, nn.Linear):
            if include and not any(k in name for k in include):
                continue
            if exclude and any(k in name for k in exclude):
                continue
            targets.append((m, "weight"))
    return targets


def global_one_shot_prune(model: PreTrainedModel, amount: float, include=None, exclude=None):
    targets = collect_linear_targets(model, include, exclude)
    if not targets:
        raise RuntimeError("프루닝 대상(nn.Linear.weight)이 없습니다. include/exclude 필터를 확인하세요.")

    for m, _ in targets:
    	prune.l1_unstructured(m, name="weight", amount=amount)
    
    # 마스크를 weight에 영구 반영
    for m, _ in targets:
        prune.remove(m, "weight")
    return targets


def report_sparsity(model: PreTrainedModel) -> float:
    total, zeros = 0, 0
    with torch.no_grad():
        for m in model.modules():
            if isinstance(m, nn.Linear):
                w = m.weight.data
                total += w.numel()
                zeros += (w == 0).sum().item()
    return (zeros / total) if total else 0.0


@torch.no_grad()
def quick_ppl(model: PreTrainedModel, tok: PreTrainedTokenizerBase, texts: List[str], device: str, max_len: int = 512) -> float:
    losses = []
    for t in texts:
        enc = tok(t, return_tensors="pt", truncation=True, max_length=max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        out = model(**enc, labels=enc["input_ids"])  # causal LM: labels=inputs
        losses.append(out.loss.item())
    return math.exp(sum(losses) / max(1, len(losses)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_id", default="meta-llama/Llama-2-13b-hf", help="HF 모델 ID")
    ap.add_argument("--sparsity", type=float, default=0.5, help="글로벌 프루닝 비율 [0~1]")
    ap.add_argument("--save_dir", default="./llama2-13b-pruned")
    ap.add_argument("--dtype", choices=["fp16","bf16","fp32"], default="fp16")
    ap.add_argument("--device", choices=["auto","cuda","cpu"], default="auto")
    ap.add_argument("--include", nargs="*", default=None, help="포함할 모듈명 부분문자열(여러 개 가능)")
    ap.add_argument("--exclude", nargs="*", default=["lm_head"], help="제외할 모듈명 부분문자열(기본: lm_head)")
    ap.add_argument("--eval_texts", nargs="*", default=None, help="간단 PPL 평가용 텍스트들")
    ap.add_argument("--max_len", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    set_seed(args.seed)

    # 장치/정밀도 설정
    dtype = dtype_from_str(args.dtype)
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
        device_map = "auto" if device == "cuda" else None
    else:
        device = args.device
        device_map = None if device == "cpu" else "auto"

    # 토크나이저/모델 로드
    tok = AutoTokenizer.from_pretrained(args.model_id, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token or tok.unk_token

    print(f"[Load] model={args.model_id} dtype={dtype} device={device}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=dtype,
        device_map=None,
        low_cpu_mem_usage=False,
        use_safetensors=True,
    )
    if device_map is None:
        model.to(device)

    # 원샷 프루닝
    print(f"[Prune] global L1 one-shot amount={args.sparsity}")
    _ = global_one_shot_prune(model, amount=args.sparsity, include=args.include, exclude=args.exclude)

    # 희소도 출력
    sp = report_sparsity(model)
    print(f"[Sparsity] global={sp:.2%}")

    # 간단 PPL
    if args.eval_texts:
        ppl = quick_ppl(model, tok, args.eval_texts, device=device, max_len=args.max_len)
        print(f"[Eval] PPL={ppl:.4f} | texts={len(args.eval_texts)}")

    # 저장(HF 형식)
    print(f"[Save] -> {args.save_dir}")
    model.save_pretrained(args.save_dir, safe_serialization=True)
    tok.save_pretrained(args.save_dir)
    print("[Done]")


if __name__ == "__main__":
    main()

