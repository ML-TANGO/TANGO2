#!/usr/bin/env python
"""
Llama DPO Optimizer 기반 FIPO 2-pass 벤치마크 평가 스크립트

고정 파이프라인:
  - Optimizer: Llama 3.1 8B + DPO LoRA adapter (--adapter_path)
  - Generator: pretrained Qwen/Qwen3-8B (adapter 없음, 고정)

FIPO 논문/공식 repo 정렬 옵션 (--fipo_paper_eval):
  - MCQ(HellaSwag/MMLU): optimized prompt + 1-token logit 채점
  - GSM8K: optimized prompt + max_new_tokens=4096 generation
  - Optimizer G_N: raw prompt 길이 기반 동적 설정 (--gn_policy dynamic)

사용 예:
  python infer_dpo_llama.py --fipo_paper_eval \\
      --adapter_path .../dpo_llama3_1_8b_use_silver/checkpoint-11250
"""

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from typing import Dict, Optional

import torch
from datasets import DownloadConfig, DownloadMode
from huggingface_hub import snapshot_download
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_ADAPTER_PATH = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/model/"
    "FIPO_dpo_llama3_1_8b_instruct"
)
DEFAULT_OPTIMIZER_BASE = "meta-llama/Meta-Llama-3.1-8B-Instruct"
DEFAULT_GENERATOR = "Qwen/Qwen3-8B"  # pretrained base, adapter 없음 (고정)
DEFAULT_PROMPTS_JSON = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/"
    "prompt_optimization_FIPO/data/prompts.json"
)
DEFAULT_LOG_DIR = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/prompt_optimization/"
    "prompt_optimization_FIPO/inference"
)

SEP_DOUBLE = "=" * 80
SEP_SINGLE = "-" * 80


class Tee:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, "w", encoding="utf-8")
        self._stdout = sys.stdout

    def write(self, msg: str):
        self._stdout.write(msg)
        self._f.write(msg)

    def flush(self):
        self._stdout.flush()
        self._f.flush()

    def close(self):
        self._f.close()


def read_prompts_json(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    required = ["optimizer", "s_r", "g_r"]
    missing = [k for k in required if k not in obj]
    if missing:
        raise ValueError(f"Missing keys in prompts.json: {missing}")
    return obj


def resolve_num_samples(num_samples: int) -> Optional[int]:
    """num_samples <= 0 이면 전체 split 사용."""
    if num_samples <= 0:
        return None
    return num_samples


def format_num_samples_label(num_samples: int) -> str:
    return "전체" if num_samples <= 0 else str(num_samples)


def load_benchmark(
    benchmark: str,
    num_samples: int,
    mmlu_subject: str = "all",
    local_files_only: bool = False,
):
    from datasets import load_dataset

    cap = resolve_num_samples(num_samples)
    print(f"[데이터셋] {benchmark} 로드 중 ({format_num_samples_label(num_samples)})...")
    load_kwargs = {}
    if local_files_only:
        load_kwargs["download_config"] = DownloadConfig(local_files_only=True)
        load_kwargs["download_mode"] = DownloadMode.REUSE_DATASET_IF_EXISTS

    if benchmark == "gsm8k":
        ds = load_dataset("openai/gsm8k", "main", split="test", **load_kwargs)
    elif benchmark == "hellaswag":
        ds = load_dataset("hellaswag", split="validation", **load_kwargs)
    elif benchmark == "mmlu":
        ds = load_dataset("cais/mmlu", mmlu_subject, split="test", **load_kwargs)
    else:
        raise ValueError(f"지원하지 않는 benchmark: {benchmark}")

    if cap is not None and cap < len(ds):
        ds = ds.select(range(cap))

    samples = []
    for row in ds:
        samples.append(parse_sample(benchmark, row))
    return samples


def parse_sample(benchmark: str, row: dict) -> dict:
    if benchmark == "gsm8k":
        ans_text = row["answer"].split("####")[-1].strip().replace(",", "")
        return {
            "raw_prompt": row["question"],
            "choices": None,
            "answer_idx": None,
            "answer_text": ans_text,
        }

    if benchmark == "hellaswag":
        endings = row["endings"]
        label = int(row["label"])
        return {
            "raw_prompt": (
                f"Context: {row['ctx']}\n\n"
                f"A. {endings[0]}\n"
                f"B. {endings[1]}\n"
                f"C. {endings[2]}\n"
                f"D. {endings[3]}"
            ),
            "choices": endings,
            "answer_idx": label,
            "answer_text": "ABCD"[label],
        }

    if benchmark == "mmlu":
        choices = row["choices"]
        label = row["answer"]
        choice_str = "\n".join(f"{chr(65 + i)}. {c}" for i, c in enumerate(choices))
        return {
            "raw_prompt": f"Question: {row['question']}\n\n{choice_str}",
            "choices": choices,
            "answer_idx": label,
            "answer_text": "ABCD"[label],
        }

    raise ValueError(f"지원하지 않는 benchmark: {benchmark}")


def resolve_model_path(model_name_or_path: str, local_files_only: bool) -> str:
    if not local_files_only:
        return model_name_or_path
    if os.path.isdir(model_name_or_path):
        return model_name_or_path
    return snapshot_download(repo_id=model_name_or_path, local_files_only=True)


def maybe_set_pad_token(tokenizer):
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"


def load_optimizer(
    adapter_path: str,
    optimizer_base: str,
    device: str,
    local_files_only: bool = False,
):
    print(f"\n[Optimizer 로드] adapter={adapter_path}")
    print(f"[Optimizer base] {optimizer_base}")

    tok = None
    try:
        tok = AutoTokenizer.from_pretrained(
            adapter_path,
            use_fast=True,
            local_files_only=local_files_only,
        )
    except Exception:
        base_path = resolve_model_path(optimizer_base, local_files_only=local_files_only)
        tok = AutoTokenizer.from_pretrained(
            base_path,
            use_fast=True,
            local_files_only=local_files_only,
        )
    maybe_set_pad_token(tok)

    adapter_config_path = os.path.join(adapter_path, "adapter_config.json")
    if os.path.exists(adapter_config_path):
        base_path = resolve_model_path(optimizer_base, local_files_only=local_files_only)
        try:
            base = AutoModelForCausalLM.from_pretrained(
                base_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
                local_files_only=local_files_only,
            )
        except Exception as e:
            if local_files_only:
                raise
            print(f"[경고] optimizer base 온라인 로드 실패 -> 캐시 fallback: {e}")
            base_path = resolve_model_path(optimizer_base, local_files_only=True)
            base = AutoModelForCausalLM.from_pretrained(
                base_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
                local_files_only=True,
            )
        base.config.use_cache = True
        model = PeftModel.from_pretrained(base, adapter_path)
    else:
        model_path = resolve_model_path(adapter_path, local_files_only=local_files_only)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
            local_files_only=local_files_only,
        )
        model.config.use_cache = True

    model.eval()
    print(f"  tokenizer type : {type(tok).__name__}")
    print(f"  eos_token      : {repr(tok.eos_token)}  (id={tok.eos_token_id})")
    print(f"  pad_token      : {repr(tok.pad_token)}  (id={tok.pad_token_id})")
    return tok, model


def is_qwen(tokenizer) -> bool:
    cls_name = type(tokenizer).__name__.lower()
    model_id = getattr(tokenizer, "name_or_path", "").lower()
    return "qwen" in cls_name or "qwen" in model_id


def apply_chat_template(tokenizer, messages, **extra_kwargs) -> str:
    kwargs = dict(tokenize=False, add_generation_prompt=True)
    kwargs.update(extra_kwargs)
    if is_qwen(tokenizer):
        kwargs["enable_thinking"] = False
    return tokenizer.apply_chat_template(messages, **kwargs)


def load_generator(model_name: str, device: str, local_files_only: bool = False):
    print(f"\n[Generator 로드] {model_name}")
    print("  mode           : pretrained base only (LoRA/adapter 미사용)")
    model_path = resolve_model_path(model_name, local_files_only=local_files_only)
    tok_kwargs = dict(use_fast=True, local_files_only=local_files_only)
    model_kwargs = dict(
        torch_dtype=torch.bfloat16,
        device_map=device,
        local_files_only=local_files_only,
    )
    try:
        tok = AutoTokenizer.from_pretrained(model_path, **tok_kwargs)
    except Exception as e:
        if local_files_only:
            raise
        print(f"[경고] generator tokenizer 온라인 로드 실패 -> 캐시 fallback: {e}")
        model_path = resolve_model_path(model_name, local_files_only=True)
        tok = AutoTokenizer.from_pretrained(
            model_path,
            use_fast=True,
            local_files_only=True,
        )
    maybe_set_pad_token(tok)
    if is_qwen(tok):
        print("  backend        : Qwen (enable_thinking=False for chat template)")

    try:
        model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)
    except Exception as e:
        if local_files_only:
            raise
        print(f"[경고] generator model 온라인 로드 실패 -> 캐시 fallback: {e}")
        model_path = resolve_model_path(model_name, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
            local_files_only=True,
        )
    model.config.use_cache = True
    model.eval()
    print(f"  tokenizer type : {type(tok).__name__}")
    print(f"  eos_token      : {repr(tok.eos_token)}  (id={tok.eos_token_id})")
    print(f"  pad_token      : {repr(tok.pad_token)}  (id={tok.pad_token_id})")
    return tok, model


def unload(model):
    del model
    torch.cuda.empty_cache()
    print("[GPU 캐시 해제 완료]")


@torch.inference_mode()
def run_inference(model, tokenizer, prompt: str, device: str, max_new_tokens: int = 512) -> str:
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        add_special_tokens=False,
    ).to(device)
    input_len = inputs["input_ids"].shape[1]
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()


def is_mcq_benchmark(benchmark: str) -> bool:
    return benchmark in ("hellaswag", "mmlu")


def get_mcq_choice_token_ids(tokenizer) -> Dict[str, int]:
    choice_ids = {}
    for letter in "ABCD":
        token_id = tokenizer.convert_tokens_to_ids(letter)
        if token_id is None or token_id == getattr(tokenizer, "unk_token_id", None):
            encoded = tokenizer.encode(letter, add_special_tokens=False)
            if not encoded:
                raise ValueError(f"Tokenizer cannot encode MCQ choice token: {letter}")
            token_id = encoded[0]
        choice_ids[letter] = token_id
    return choice_ids


@torch.inference_mode()
def predict_mcq_logit(model, tokenizer, chat_prompt: str, device: str) -> str:
    """FIPO 공식 get_model_infer_batch_logits.py 방식: 첫 토큰 A/B/C/D logit 비교."""
    inputs = tokenizer(
        chat_prompt,
        return_tensors="pt",
        add_special_tokens=False,
    ).to(device)
    logits = model(**inputs).logits[0, -1]
    scores = {
        letter: float(logits[token_id])
        for letter, token_id in get_mcq_choice_token_ids(tokenizer).items()
    }
    return max(scores, key=scores.get)


def build_fipo_optimizer_text(raw_prompt: str, prompts: Dict[str, str], max_words: int = 256) -> str:
    text = prompts["optimizer"]
    text = text.replace("S_P", raw_prompt)
    text = text.replace("O_C", "")
    text = text.replace("G_N", str(max_words))
    return text


def truncate_to_max_words(text: str, max_words: int) -> str:
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def is_multiple_choice_prompt(raw_prompt: str, benchmark: str) -> bool:
    if benchmark in ("hellaswag", "mmlu"):
        return True
    # 안전 보완: 포맷 자체로도 판별
    return all(x in raw_prompt for x in ["A.", "B.", "C.", "D."])


def resolve_optimizer_max_words(
    raw_prompt: str,
    benchmark_name: str,
    optimizer_max_words: int,
    optimizer_max_words_mcq: int,
    gn_policy: str,
) -> int:
    cap = (
        optimizer_max_words_mcq
        if is_multiple_choice_prompt(raw_prompt, benchmark_name)
        else optimizer_max_words
    )
    if gn_policy == "fixed":
        return cap
    # FIPO training: G_N=len(chosen.split()). Inference proxy: raw prompt word count.
    return max(1, min(len(raw_prompt.split()), cap))


def postprocess_optimized_prompt(
    raw_prompt: str,
    optimized_prompt: str,
    benchmark: str,
    max_words: int,
    keep_raw_for_mcq: bool,
) -> str:
    # 객관식은 재서술을 막고 원문 유지(요청사항 반영)
    if keep_raw_for_mcq and is_multiple_choice_prompt(raw_prompt, benchmark):
        return raw_prompt.strip()
    return truncate_to_max_words(optimized_prompt, max_words=max_words)


def build_optimizer_input(
    tokenizer,
    raw_prompt: str,
    prompts: Dict[str, str],
    optimizer_max_words: int,
) -> str:
    optimizer_text = build_fipo_optimizer_text(
        raw_prompt=raw_prompt,
        prompts=prompts,
        max_words=optimizer_max_words,
    )
    messages = [{"role": "user", "content": optimizer_text}]
    return apply_chat_template(tokenizer, messages)


def build_generator_input(tokenizer, prompt: str, benchmark: str) -> str:
    if benchmark == "gsm8k":
        system = (
            "You are a math solver. "
            "Read the problem carefully and solve it step by step. "
            "At the end, write the final numerical answer after '####'."
        )
    else:
        system = (
            "You are a question answering assistant. "
            "Read the question and choose the single best answer. "
            "Respond with only the letter: A, B, C, or D."
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    return apply_chat_template(tokenizer, messages)


def extract_answer(response: str, benchmark: str) -> str:
    if benchmark == "gsm8k":
        m = re.search(r"####\s*([\d,]+)", response)
        if m:
            return m.group(1).replace(",", "")
        nums = re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", response)
        return nums[-1].replace(",", "") if nums else ""

    clean = response.strip()

    # 1) 명시적 정답 패턴 우선
    explicit = re.search(
        r"(?:final\s*answer|answer|정답)\s*[:\-]?\s*\(?([ABCD])\)?",
        clean,
        flags=re.IGNORECASE,
    )
    if explicit:
        return explicit.group(1).upper()

    # 2) 전체 텍스트에서 A/B/C/D 단일 토큰을 찾아 마지막 값을 사용
    all_choices = re.findall(r"\b([ABCD])\b", clean.upper())
    if all_choices:
        return all_choices[-1]

    # 3) 기존 초반부 탐색 fallback
    m = re.search(r"\b([ABCD])\b", clean[:30])
    if m:
        return m.group(1).upper()
    if clean and clean[0] in "ABCD":
        return clean[0]
    return ""


def is_correct(pred: str, gold: str, benchmark: str) -> bool:
    if not pred:
        return False
    if benchmark == "gsm8k":
        try:
            return float(pred.replace(",", "")) == float(gold.replace(",", ""))
        except ValueError:
            return False
    return pred.upper() == gold.upper()


def run_generator_answer(
    gen_model,
    gen_tok,
    chat_prompt: str,
    device: str,
    benchmark: str,
    max_new_tokens: int,
    mcq_eval_mode: str,
):
    if is_mcq_benchmark(benchmark) and mcq_eval_mode == "logit":
        pred = predict_mcq_logit(gen_model, gen_tok, chat_prompt, device)
        return f"[logit] {pred}", pred
    response = run_inference(
        gen_model,
        gen_tok,
        chat_prompt,
        device,
        max_new_tokens=max_new_tokens,
    )
    return response, extract_answer(response, benchmark)


def print_sample_result(
    i: int,
    total: int,
    raw_prompt: str,
    opt_prompt: str,
    gold: str,
    base_resp: str,
    base_pred: str,
    base_ok: bool,
    fipo_resp: str,
    fipo_pred: str,
    fipo_ok: bool,
    no_baseline: bool,
):
    print(SEP_DOUBLE)
    print(f"[샘플 {i + 1}/{total}]  정답: {gold}")
    print(SEP_SINGLE)
    print("【Raw Prompt】")
    print(textwrap.fill(raw_prompt, 76, initial_indent="  ", subsequent_indent="  "))
    print()
    print("【Optimized Prompt (FIPO)】")
    print(textwrap.fill(opt_prompt, 76, initial_indent="  ", subsequent_indent="  "))
    print()

    if not no_baseline:
        ok_str = "✓ 정답" if base_ok else "✗ 오답"
        print(f"【Generator 응답 — Baseline】  예측: {base_pred or '(없음)'}  {ok_str}")
        print(textwrap.fill(base_resp[:300], 76, initial_indent="  ", subsequent_indent="  "))
        print()

    ok_str = "✓ 정답" if fipo_ok else "✗ 오답"
    print(f"【Generator 응답 — FIPO】  예측: {fipo_pred or '(없음)'}  {ok_str}")
    print(textwrap.fill(fipo_resp[:300], 76, initial_indent="  ", subsequent_indent="  "))
    print()


def print_summary(results: list, benchmark: str, no_baseline: bool):
    n = len(results)
    fipo_correct = sum(r["fipo_correct"] for r in results)
    fipo_acc = fipo_correct / n if n else 0

    print(SEP_DOUBLE)
    print(f"  ■ 최종 평가 결과  |  {benchmark.upper()}  |  n={n}")
    print(SEP_SINGLE)
    if not no_baseline:
        base_correct = sum(r["base_correct"] for r in results)
        base_acc = base_correct / n if n else 0
        delta = fipo_acc - base_acc
        sign = "+" if delta >= 0 else ""
        print(f"  {'모델':<30} {'정답':>6}  {'정확도':>8}")
        print(f"  {'-' * 48}")
        print(f"  {'Baseline (raw -> generator)':<30} {base_correct:>6}  {base_acc:>8.4f}")
        print(f"  {'FIPO (optimizer -> generator)':<30} {fipo_correct:>6}  {fipo_acc:>8.4f}")
        print(f"  {'개선폭 (FIPO - Baseline)':<30} {'':>6}  {sign}{delta:>7.4f}")
    else:
        print(f"  {'FIPO (optimizer -> generator)':<30} {fipo_correct:>6} / {n}  {fipo_acc:.4f}")
    print()


def print_all_summary(all_results: dict, no_baseline: bool):
    print()
    print(SEP_DOUBLE)
    print("  ■ 전체 벤치마크 통합 요약")
    print(SEP_SINGLE)
    if no_baseline:
        print(f"  {'벤치마크':<14} {'n':>5}  {'FIPO 정확도':>12}")
        print(f"  {'-' * 36}")
        for bname, results in all_results.items():
            n = len(results)
            facc = sum(r["fipo_correct"] for r in results) / n if n else 0
            print(f"  {bname:<14} {n:>5}  {facc:>12.4f}")
    else:
        print(f"  {'벤치마크':<14} {'n':>5}  {'Baseline':>10}  {'FIPO':>10}  {'개선폭':>10}")
        print(f"  {'-' * 56}")
        for bname, results in all_results.items():
            n = len(results)
            bacc = sum(r["base_correct"] for r in results) / n if n else 0
            facc = sum(r["fipo_correct"] for r in results) / n if n else 0
            delta = facc - bacc
            sign = "+" if delta >= 0 else ""
            print(f"  {bname:<14} {n:>5}  {bacc:>10.4f}  {facc:>10.4f}  {sign}{delta:>9.4f}")
    print()


def run_optimizer_pass(
    opt_tok,
    opt_model,
    samples: list,
    device: str,
    max_new_tokens: int,
    benchmark_name: str,
    prompts: Dict[str, str],
    optimizer_max_words: int,
    optimizer_max_words_mcq: int,
    keep_raw_for_mcq: bool,
    gn_policy: str,
) -> list:
    optimized = []
    n = len(samples)
    print(
        f"\n  [Pass 1 - {benchmark_name}]  Optimizer 추론 중 "
        f"({n}개, max_new_tokens={max_new_tokens}, G_N={gn_policy})..."
    )
    for i, s in enumerate(samples):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    최적화 중... {i + 1}/{n}")
        effective_max_words = resolve_optimizer_max_words(
            raw_prompt=s["raw_prompt"],
            benchmark_name=benchmark_name,
            optimizer_max_words=optimizer_max_words,
            optimizer_max_words_mcq=optimizer_max_words_mcq,
            gn_policy=gn_policy,
        )
        inp = build_optimizer_input(
            opt_tok,
            s["raw_prompt"],
            prompts=prompts,
            optimizer_max_words=effective_max_words,
        )
        generated = run_inference(
            opt_model,
            opt_tok,
            inp,
            device,
            max_new_tokens=max_new_tokens,
        )
        optimized.append(
            postprocess_optimized_prompt(
                raw_prompt=s["raw_prompt"],
                optimized_prompt=generated,
                benchmark=benchmark_name,
                max_words=effective_max_words,
                keep_raw_for_mcq=keep_raw_for_mcq,
            )
        )
    print(f"    완료: {n}개")
    return optimized


def run_generator_pass(
    gen_tok,
    gen_model,
    samples: list,
    optimized_prompts: list,
    device: str,
    max_new_tokens: int,
    benchmark: str,
    no_baseline: bool,
    mcq_eval_mode: str,
) -> list:
    results = []
    n = len(samples)
    eval_desc = mcq_eval_mode if is_mcq_benchmark(benchmark) else "generation"
    print(
        f"\n  [Pass 2 - {benchmark}]  Generator 추론 & 채점 중 "
        f"({n}개, mode={eval_desc}, max_new_tokens={max_new_tokens})..."
    )
    for i, (s, opt_prompt) in enumerate(zip(samples, optimized_prompts)):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    생성 중... {i + 1}/{n}")

        fipo_inp = build_generator_input(gen_tok, opt_prompt, benchmark)
        fipo_resp, fipo_pred = run_generator_answer(
            gen_model,
            gen_tok,
            fipo_inp,
            device,
            benchmark,
            max_new_tokens,
            mcq_eval_mode,
        )
        fipo_ok = is_correct(fipo_pred, s["answer_text"], benchmark)

        base_resp = ""
        base_pred = ""
        base_ok = False
        if not no_baseline:
            base_inp = build_generator_input(gen_tok, s["raw_prompt"], benchmark)
            base_resp, base_pred = run_generator_answer(
                gen_model,
                gen_tok,
                base_inp,
                device,
                benchmark,
                max_new_tokens,
                mcq_eval_mode,
            )
            base_ok = is_correct(base_pred, s["answer_text"], benchmark)

        print_sample_result(
            i=i,
            total=n,
            raw_prompt=s["raw_prompt"],
            opt_prompt=opt_prompt,
            gold=s["answer_text"],
            base_resp=base_resp,
            base_pred=base_pred,
            base_ok=base_ok,
            fipo_resp=fipo_resp,
            fipo_pred=fipo_pred,
            fipo_ok=fipo_ok,
            no_baseline=no_baseline,
        )

        results.append(
            {
                "idx": i,
                "raw_prompt": s["raw_prompt"],
                "optimized": opt_prompt,
                "gold": s["answer_text"],
                "fipo_response": fipo_resp,
                "fipo_pred": fipo_pred,
                "fipo_correct": fipo_ok,
                "base_response": base_resp,
                "base_pred": base_pred,
                "base_correct": base_ok,
            }
        )
    return results


BENCHMARKS_ALL = ["gsm8k", "hellaswag", "mmlu"]

# FIPO 공식 repo (scripts/test_inference.sh) 기본값
FIPO_MAX_NEW_TOKENS_OPT = 4096
FIPO_MAX_NEW_TOKENS_GEN_GSM8K = 4096
FIPO_MAX_NEW_TOKENS_GEN_MCQ = 1  # multichoice E_TARLEN=1 + logit
FIPO_MAX_NEW_TOKENS_GEN_MCQ_FREEFORM = 16


def resolve_max_new_tokens_gen(
    benchmark: str,
    gsm8k: int,
    mcq: int,
    override: Optional[int] = None,
    mcq_eval_mode: str = "logit",
) -> int:
    if override is not None:
        return override
    if benchmark == "gsm8k":
        return gsm8k
    if benchmark in ("hellaswag", "mmlu"):
        if mcq_eval_mode == "logit":
            return 1
        return mcq
    raise ValueError(f"지원하지 않는 benchmark: {benchmark}")


def resolve_keep_raw_for_mcq(mcq_raw_guard: bool, no_mcq_raw_guard: bool) -> bool:
    if no_mcq_raw_guard:
        return False
    return mcq_raw_guard


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Llama DPO Optimizer + pretrained Qwen Generator FIPO 2-pass 벤치마크 평가"
        )
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default="all",
        choices=["gsm8k", "hellaswag", "mmlu", "all"],
        help="평가할 벤치마크 (기본값: all -> 3개 순차 실행)",
    )
    parser.add_argument(
        "--adapter_path",
        type=str,
        default=DEFAULT_ADAPTER_PATH,
        help="DPO LoRA 어댑터 경로 (Llama Prompt Optimizer)",
    )
    parser.add_argument(
        "--optimizer_base_model",
        type=str,
        default=DEFAULT_OPTIMIZER_BASE,
        help=f"Optimizer base model (기본값: {DEFAULT_OPTIMIZER_BASE})",
    )
    parser.add_argument(
        "--prompts_json",
        type=str,
        default=DEFAULT_PROMPTS_JSON,
        help=f"FIPO prompts.json 경로 (기본값: {DEFAULT_PROMPTS_JSON})",
    )
    parser.add_argument(
        "--optimizer_max_words",
        type=int,
        default=256,
        help="prompts.json의 G_N에 주입할 최대 단어 수 (기본값: 128)",
    )
    parser.add_argument(
        "--optimizer_max_words_mcq",
        type=int,
        default=512,
        help="객관식 G_N 상한 (dynamic 정책에서 cap, fixed 정책에서 고정값)",
    )
    parser.add_argument(
        "--mcq_raw_guard",
        action="store_true",
        help="MCQ에서 optimized prompt 대신 raw prompt 유지 (FIPO 논문 방식 아님)",
    )
    parser.add_argument(
        "--no_mcq_raw_guard",
        action="store_true",
        help="(호환용) MCQ raw guard 비활성화. 기본값이 이미 비활성화",
    )
    parser.add_argument(
        "--mcq_eval_mode",
        type=str,
        default="logit",
        choices=["logit", "freeform"],
        help="MCQ 채점 방식: logit(FIPO 공식) | freeform(자유 생성+파싱)",
    )
    parser.add_argument(
        "--gn_policy",
        type=str,
        default="dynamic",
        choices=["dynamic", "fixed"],
        help="Optimizer G_N 정책: dynamic(FIPO, raw 길이 기반) | fixed",
    )
    parser.add_argument(
        "--fipo_paper_eval",
        action="store_true",
        help="FIPO 논문/공식 repo 평가 설정 일괄 적용 (logit MCQ, dynamic G_N, raw guard off)",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=100,
        help="벤치마크당 샘플 수 (0 이하 = 해당 split 전체 사용)",
    )
    parser.add_argument("--mmlu_subject", type=str, default="all", help="MMLU 과목")
    parser.add_argument("--no_baseline", action="store_true", help="Baseline 생략")
    parser.add_argument(
        "--max_new_tokens_opt",
        type=int,
        default=FIPO_MAX_NEW_TOKENS_OPT,
        help="Optimizer 최대 생성 토큰 (FIPO 공식 N_LEN=4096)",
    )
    parser.add_argument(
        "--max_new_tokens_gen",
        type=int,
        default=None,
        help="모든 benchmark에 동일 Generator max_new_tokens 적용 (지정 시 아래 gsm8k/mcq 설정 무시)",
    )
    parser.add_argument(
        "--max_new_tokens_gen_gsm8k",
        type=int,
        default=FIPO_MAX_NEW_TOKENS_GEN_GSM8K,
        help="GSM8K Generator max_new_tokens (FIPO 공식 E_TARLEN=4096)",
    )
    parser.add_argument(
        "--max_new_tokens_gen_mcq",
        type=int,
        default=FIPO_MAX_NEW_TOKENS_GEN_MCQ_FREEFORM,
        help="MCQ freeform 모드 Generator max_new_tokens (logit 모드에서는 1 고정)",
    )
    parser.add_argument("--log_dir", type=str, default=DEFAULT_LOG_DIR, help="로그 저장 디렉터리")
    parser.add_argument("--save_json", action="store_true", help="JSON 상세 결과 저장")
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="device (예: cuda, cpu, auto)",
    )
    parser.add_argument(
        "--hf_token",
        type=str,
        default=os.environ.get("HF_TOKEN", None),
        help="HuggingFace 액세스 토큰",
    )
    parser.add_argument(
        "--offline",
        type=int,
        default=0,
        choices=[0, 1],
        help="1이면 로컬 캐시만 사용, 0이면 온라인 우선 후 캐시 fallback",
    )
    args = parser.parse_args()

    if args.fipo_paper_eval:
        args.mcq_eval_mode = "logit"
        args.gn_policy = "dynamic"
        args.mcq_raw_guard = False
        args.no_mcq_raw_guard = True
        args.max_new_tokens_opt = FIPO_MAX_NEW_TOKENS_OPT
        args.max_new_tokens_gen_gsm8k = FIPO_MAX_NEW_TOKENS_GEN_GSM8K
        args.max_new_tokens_gen_mcq = FIPO_MAX_NEW_TOKENS_GEN_MCQ

    keep_raw_for_mcq = resolve_keep_raw_for_mcq(args.mcq_raw_guard, args.no_mcq_raw_guard)

    if args.hf_token:
        os.environ["HF_TOKEN"] = args.hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = args.hf_token
        print("[HuggingFace] 토큰 환경변수 설정 완료")

    benchmarks = BENCHMARKS_ALL if args.benchmark == "all" else [args.benchmark]
    prompts = read_prompts_json(args.prompts_json)
    local_files_only = bool(args.offline)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ckpt_tag = os.path.basename(args.adapter_path.rstrip("/"))
    gen_tag = DEFAULT_GENERATOR.replace("/", "-")
    bench_tag = args.benchmark
    if args.benchmark == "mmlu":
        bench_tag += f"_{args.mmlu_subject}"
    sample_tag = "all" if args.num_samples <= 0 else str(args.num_samples)
    log_stem = f"{timestamp}_{bench_tag}_{ckpt_tag}_gen-{gen_tag}_n{sample_tag}"
    txt_path = os.path.join(args.log_dir, f"{log_stem}.txt")
    json_path = os.path.join(args.log_dir, f"{log_stem}.json")

    os.makedirs(args.log_dir, exist_ok=True)
    tee = Tee(txt_path)
    sys.stdout = tee

    print(SEP_DOUBLE)
    print(f"  Llama DPO Optimizer 벤치마크 평가  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP_SINGLE)
    print(f"  benchmark        : {args.benchmark}  ->  {' -> '.join(benchmarks)}")
    print(f"  adapter_path     : {args.adapter_path}  (Llama DPO LoRA)")
    print(f"  optimizer_base   : {args.optimizer_base_model}")
    print(f"  generator_model  : {DEFAULT_GENERATOR}  (pretrained, adapter 없음)")
    print(f"  prompts_json     : {args.prompts_json}")
    print(f"  optimizer G_N    : policy={args.gn_policy}, cap={args.optimizer_max_words} (mcq cap: {args.optimizer_max_words_mcq})")
    print(f"  mcq eval mode    : {args.mcq_eval_mode}")
    print(f"  mcq raw guard    : {'활성화' if keep_raw_for_mcq else '비활성화 (FIPO paper)'}")
    print(f"  fipo_paper_eval  : {'ON' if args.fipo_paper_eval else 'OFF'}")
    print(f"  max_new_tokens_opt : {args.max_new_tokens_opt}")
    if args.max_new_tokens_gen is not None:
        print(f"  max_new_tokens_gen : {args.max_new_tokens_gen} (all benchmarks)")
    else:
        mcq_tok = (
            1 if args.mcq_eval_mode == "logit" else args.max_new_tokens_gen_mcq
        )
        print(
            f"  max_new_tokens_gen : gsm8k={args.max_new_tokens_gen_gsm8k}, "
            f"mcq={mcq_tok} ({args.mcq_eval_mode})"
        )
    print(
        "  [설정] optimizer/generator 분리 "
        f"(optimizer=Llama+adapter, generator={DEFAULT_GENERATOR})"
    )
    print(f"  offline mode     : {args.offline}")
    print(f"  num_samples      : {format_num_samples_label(args.num_samples)} (벤치마크당)")
    print(f"  baseline 비교    : {'비활성화' if args.no_baseline else '활성화'}")
    print(f"  device           : {args.device}", end="")
    if torch.cuda.is_available():
        print(
            f"  ({torch.cuda.get_device_name(0)}, "
            f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.0f}GB)",
            end="",
        )
    print()
    print(f"  log (txt)        : {txt_path}")
    print(SEP_DOUBLE)

    print()
    all_samples = {}
    for bname in benchmarks:
        subj = args.mmlu_subject if bname == "mmlu" else "all"
        all_samples[bname] = load_benchmark(
            bname,
            args.num_samples,
            subj,
            local_files_only=local_files_only,
        )
        print(f"  {bname:<12} -> {len(all_samples[bname])}개 샘플 준비")
    print()

    print(SEP_SINGLE)
    print("  [Pass 1] Prompt Optimizer 로드 -> 전체 벤치마크 최적화")
    print(SEP_SINGLE)
    opt_tok, opt_model = load_optimizer(
        args.adapter_path,
        args.optimizer_base_model,
        args.device,
        local_files_only=local_files_only,
    )
    all_optimized = {}
    for bname in benchmarks:
        all_optimized[bname] = run_optimizer_pass(
            opt_tok,
            opt_model,
            all_samples[bname],
            args.device,
            args.max_new_tokens_opt,
            bname,
            prompts=prompts,
            optimizer_max_words=args.optimizer_max_words,
            optimizer_max_words_mcq=args.optimizer_max_words_mcq,
            keep_raw_for_mcq=keep_raw_for_mcq,
            gn_policy=args.gn_policy,
        )
    unload(opt_model)
    del opt_tok
    print(f"\n  Optimizer 언로드 완료. 전체 {sum(len(v) for v in all_optimized.values())}개 최적화 완료.")

    print()
    print(SEP_SINGLE)
    print("  [Pass 2] Generator 로드 -> 전체 벤치마크 추론 & 채점")
    print(SEP_SINGLE)
    gen_tok, gen_model = load_generator(
        DEFAULT_GENERATOR,
        args.device,
        local_files_only=local_files_only,
    )
    all_results = {}
    for bname in benchmarks:
        gen_max_tokens = resolve_max_new_tokens_gen(
            bname,
            gsm8k=args.max_new_tokens_gen_gsm8k,
            mcq=args.max_new_tokens_gen_mcq,
            override=args.max_new_tokens_gen,
            mcq_eval_mode=args.mcq_eval_mode,
        )
        all_results[bname] = run_generator_pass(
            gen_tok,
            gen_model,
            all_samples[bname],
            all_optimized[bname],
            args.device,
            gen_max_tokens,
            bname,
            args.no_baseline,
            args.mcq_eval_mode,
        )
        print_summary(all_results[bname], bname, args.no_baseline)
    unload(gen_model)
    del gen_tok

    if len(benchmarks) > 1:
        print_all_summary(all_results, args.no_baseline)

    print(f"텍스트 로그 저장: {txt_path}")
    if args.save_json:
        tee.flush()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"JSON 결과 저장 : {json_path}")

    tee.close()
    sys.stdout = tee._stdout


if __name__ == "__main__":
    main()
    
