#!/usr/bin/env python
"""
SFT LoRA 어댑터 추론 스크립트
- 데이터셋 샘플 또는 커스텀 프롬프트로 테스트
- reference(GPT-4)와 비교해 BERTScore / ROUGE-2 / ROUGE-L 측정
- 결과를 텍스트 로그(.txt)로 저장

주요 인자:
  --adapter_path   LoRA 체크포인트 경로  (기본값: checkpoint-5625)
  --num_samples    데이터셋 샘플 수      (기본값: 5, custom_prompt 없을 때 사용)
  --custom_prompt  직접 입력 raw 프롬프트 (지정 시 데이터셋 대신 사용, 지표 계산 불가)
  --base_model     베이스 모델 경로      (기본값: Qwen/Qwen3-8B)
  --compare_base   베이스 모델과 출력 비교 (flag)
  --max_new_tokens 최대 생성 토큰 수     (기본값: 512)
  --temperature    생성 temperature      (기본값: 0.7, 0이면 greedy)
  --log_dir        로그 저장 디렉터리    (기본값: FIPO_Project/inference)
  --save_json      JSON 결과도 함께 저장 (flag)

사용 예시:
  # 데이터셋 5개 샘플 + 지표 계산
  python infer_sft_qwen3_8b.py

  # 샘플 수 조정
  python infer_sft_qwen3_8b.py --num_samples 10

  # 커스텀 프롬프트 (지표 계산 없음)
  python infer_sft_qwen3_8b.py --custom_prompt "Write a poem about AI"

  # 베이스 모델과 비교 + JSON 저장
  python infer_sft_qwen3_8b.py --num_samples 3 --compare_base --save_json
"""

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_ADAPTER_PATH = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/promptopti/model/sft/checkpoint-5625"
)
DEFAULT_LOG_DIR = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/promptopti/FIPO_Project/inference"
)

SYSTEM_PROMPT = (
    "You are a prompt optimizer. Rewrite the user's raw prompt into a clearer, "
    "more detailed, and more effective instruction prompt. "
    "Return only the rewritten optimized prompt."
)

SEP_DOUBLE = "═" * 80
SEP_SINGLE = "─" * 80


# ──────────────────────────────────────────────────────────────
# Tee: stdout과 파일에 동시 출력
# ──────────────────────────────────────────────────────────────
class Tee:
    def __init__(self, file_path: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self._file   = open(file_path, "w", encoding="utf-8")
        self._stdout = sys.stdout

    def write(self, msg: str):
        self._stdout.write(msg)
        self._file.write(msg)

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def close(self):
        self._file.close()


# ──────────────────────────────────────────────────────────────
# 평가 지표
# ──────────────────────────────────────────────────────────────
def load_metrics():
    """evaluate / bert_score 라이브러리 로드 (최초 1회)"""
    import evaluate
    from bert_score import score as bert_score_fn
    rouge = evaluate.load("rouge")
    return rouge, bert_score_fn


def compute_metrics(hypothesis: str, reference: str,
                    rouge, bert_score_fn, device: str) -> dict:
    """
    hypothesis : 모델 생성 텍스트
    reference  : GPT-4 정답 텍스트
    반환: {"rouge2": float, "rougeL": float, "bertscore_f1": float}
    """
    # ROUGE
    rouge_result = rouge.compute(
        predictions=[hypothesis],
        references=[reference],
        use_aggregator=True,
    )

    # BERTScore  (rescale_with_baseline=True → 0~1 범위로 보정)
    _, _, F1 = bert_score_fn(
        [hypothesis],
        [reference],
        lang="en",
        device=device,
        rescale_with_baseline=True,
        verbose=False,
    )

    return {
        "rouge2":       round(rouge_result["rouge2"], 4),
        "rougeL":       round(rouge_result["rougeL"], 4),
        "bertscore_f1": round(F1[0].item(), 4),
    }


# ──────────────────────────────────────────────────────────────
# 모델
# ──────────────────────────────────────────────────────────────
def build_chat_input(tokenizer, raw_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"Raw prompt:\n{raw_prompt}"},
    ]
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def load_model_and_tokenizer(adapter_path: str, base_model_name: str, device: str):
    print(f"[모델 로딩] base : {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(
        adapter_path, use_fast=True, trust_remote_code=False
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name, torch_dtype=torch.bfloat16, device_map=device
    )
    base_model.config.use_cache = True

    print(f"[어댑터 로딩] {adapter_path}")
    ft_model = PeftModel.from_pretrained(base_model, adapter_path)
    ft_model.eval()
    return tokenizer, ft_model


def load_dataset_samples(num_samples: int):
    from datasets import load_dataset
    print(f"[데이터셋] Junrulu/Prompt_Preference_Dataset — {num_samples}개 샘플 로드 중...")
    ds = load_dataset("Junrulu/Prompt_Preference_Dataset", split="train")
    return [
        {
            "raw_prompt": ds[i]["raw_prompt"],
            "reference":  ds[i]["gpt4_optimized_prompt"],
        }
        for i in range(min(num_samples, len(ds)))
    ]


@torch.inference_mode()
def generate(model, tokenizer, prompt_text: str, device: str,
             max_new_tokens: int = 512, temperature: float = 0.7) -> str:
    inputs   = tokenizer(prompt_text, return_tensors="pt",
                         add_special_tokens=False).to(device)
    input_len = inputs["input_ids"].shape[1]
    outputs   = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=temperature > 0,
        temperature=temperature if temperature > 0 else None,
        top_p=0.9   if temperature > 0 else None,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()


# ──────────────────────────────────────────────────────────────
# 출력 포맷
# ──────────────────────────────────────────────────────────────
def wrap(text: str) -> str:
    return textwrap.fill(text, width=78,
                         initial_indent="  ", subsequent_indent="  ")


def print_sample(idx: int, raw_prompt: str, ft_output: str,
                 reference: str = None, base_output: str = None,
                 ft_scores: dict = None, base_scores: dict = None):
    print(SEP_DOUBLE)
    print(f"[샘플 {idx + 1}]")
    print(SEP_SINGLE)

    print("【원본 프롬프트 (Raw Prompt)】")
    print(wrap(raw_prompt))
    print()

    if base_output is not None:
        print("【베이스 모델 출력 (Qwen3-8B)】")
        print(wrap(base_output))
        if base_scores:
            print(f"  ▶ ROUGE-2: {base_scores['rouge2']:.4f}  "
                  f"ROUGE-L: {base_scores['rougeL']:.4f}  "
                  f"BERTScore F1: {base_scores['bertscore_f1']:.4f}")
        print()

    print("【파인튜닝 모델 출력 (SFT LoRA)】")
    print(wrap(ft_output))
    if ft_scores:
        print(f"  ▶ ROUGE-2: {ft_scores['rouge2']:.4f}  "
              f"ROUGE-L: {ft_scores['rougeL']:.4f}  "
              f"BERTScore F1: {ft_scores['bertscore_f1']:.4f}")
    print()

    if reference is not None:
        print("【정답 레퍼런스 (GPT-4 최적화)】")
        print(wrap(reference))
        print()


def print_summary(score_list: list, label: str):
    """score_list: [{"rouge2": ..., "rougeL": ..., "bertscore_f1": ...}, ...]"""
    if not score_list:
        return
    n = len(score_list)
    avg_r2  = sum(s["rouge2"]       for s in score_list) / n
    avg_rl  = sum(s["rougeL"]       for s in score_list) / n
    avg_bs  = sum(s["bertscore_f1"] for s in score_list) / n

    print(f"\n  [{label}] 평균 지표 (n={n})")
    print(f"  {'지표':<18} {'평균':>8}")
    print(f"  {'─'*26}")
    print(f"  {'ROUGE-2':<18} {avg_r2:>8.4f}")
    print(f"  {'ROUGE-L':<18} {avg_rl:>8.4f}")
    print(f"  {'BERTScore F1':<18} {avg_bs:>8.4f}")


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SFT LoRA 모델 추론 + 정량 평가")
    parser.add_argument(
        "--adapter_path", type=str, default=DEFAULT_ADAPTER_PATH,
        help="LoRA 어댑터 체크포인트 경로 (기본값: checkpoint-5625)",
    )
    parser.add_argument(
        "--base_model", type=str, default="Qwen/Qwen3-8B",
        help="베이스 모델 이름 또는 경로 (기본값: Qwen/Qwen3-8B)",
    )
    parser.add_argument(
        "--custom_prompt", type=str, default=None,
        help="직접 입력할 raw 프롬프트. 미지정 시 데이터셋 샘플 사용 (지표 계산 불가)",
    )
    parser.add_argument(
        "--num_samples", type=int, default=5,
        help="custom_prompt 없을 때 데이터셋 샘플 수 (기본값: 5)",
    )
    parser.add_argument(
        "--compare_base", action="store_true",
        help="베이스 모델 출력과 지표를 나란히 비교",
    )
    parser.add_argument(
        "--max_new_tokens", type=int, default=512,
        help="최대 생성 토큰 수 (기본값: 512)",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="생성 temperature, 0이면 greedy (기본값: 0.7)",
    )
    parser.add_argument(
        "--log_dir", type=str, default=DEFAULT_LOG_DIR,
        help=f"로그 저장 디렉터리 (기본값: {DEFAULT_LOG_DIR})",
    )
    parser.add_argument(
        "--save_json", action="store_true",
        help="텍스트 로그와 함께 JSON 결과도 저장",
    )
    parser.add_argument(
        "--device", type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="사용할 디바이스 (기본값: cuda)",
    )
    args = parser.parse_args()

    # ── 로그 파일 경로 ────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ckpt_name = os.path.basename(args.adapter_path.rstrip("/"))
    mode_tag  = "custom" if args.custom_prompt else f"samples{args.num_samples}"
    log_stem  = f"{timestamp}_{ckpt_name}_{mode_tag}"
    txt_path  = os.path.join(args.log_dir, f"{log_stem}.txt")
    json_path = os.path.join(args.log_dir, f"{log_stem}.json")

    os.makedirs(args.log_dir, exist_ok=True)

    tee = Tee(txt_path)
    sys.stdout = tee

    # ── 헤더 ─────────────────────────────────────────────────
    print(SEP_DOUBLE)
    print(f"  SFT LoRA 추론 + 정량 평가  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP_SINGLE)
    print(f"  adapter_path  : {args.adapter_path}")
    print(f"  base_model    : {args.base_model}")
    print(f"  mode          : {'custom_prompt' if args.custom_prompt else f'dataset ({args.num_samples} samples)'}")
    print(f"  compare_base  : {args.compare_base}")
    print(f"  max_new_tokens: {args.max_new_tokens}  |  temperature: {args.temperature}")
    print(f"  device        : {args.device}", end="")
    if torch.cuda.is_available():
        print(f"  ({torch.cuda.get_device_name(0)})", end="")
    print()
    print(f"  log (txt)     : {txt_path}")
    if args.save_json:
        print(f"  log (json)    : {json_path}")
    print(SEP_DOUBLE)

    # ── 지표 로드 ─────────────────────────────────────────────
    has_reference = not args.custom_prompt   # custom_prompt면 reference 없음
    if has_reference:
        print("\n[지표 로드] evaluate (ROUGE) + bert_score ...")
        rouge, bert_score_fn = load_metrics()
    else:
        print("\n[지표] custom_prompt 모드 — reference 없으므로 지표 계산 생략")
        rouge = bert_score_fn = None

    # ── 모델 로드 ─────────────────────────────────────────────
    print()
    tokenizer, ft_model = load_model_and_tokenizer(
        args.adapter_path, args.base_model, args.device
    )

    # ── 샘플 준비 ─────────────────────────────────────────────
    if args.custom_prompt:
        samples = [{"raw_prompt": args.custom_prompt, "reference": None}]
    else:
        samples = load_dataset_samples(args.num_samples)

    results       = []
    ft_scores_all   = []
    base_scores_all = []

    print()
    for i, sample in enumerate(samples):
        raw_prompt = sample["raw_prompt"]
        reference  = sample.get("reference")
        chat_input = build_chat_input(tokenizer, raw_prompt)

        # FT 모델 추론
        print(f"[추론 중] 샘플 {i + 1}/{len(samples)} — FT 모델...")
        ft_output = generate(
            ft_model, tokenizer, chat_input, args.device,
            max_new_tokens=args.max_new_tokens, temperature=args.temperature,
        )

        # 베이스 모델 추론 (선택)
        base_output = None
        if args.compare_base:
            print(f"[추론 중] 샘플 {i + 1}/{len(samples)} — 베이스 모델...")
            with ft_model.disable_adapter():
                base_output = generate(
                    ft_model, tokenizer, chat_input, args.device,
                    max_new_tokens=args.max_new_tokens, temperature=args.temperature,
                )

        # 지표 계산
        ft_scores   = None
        base_scores = None
        if has_reference and reference:
            print(f"[지표 계산] 샘플 {i + 1}/{len(samples)}...")
            ft_scores = compute_metrics(
                ft_output, reference, rouge, bert_score_fn, args.device
            )
            ft_scores_all.append(ft_scores)

            if base_output is not None:
                base_scores = compute_metrics(
                    base_output, reference, rouge, bert_score_fn, args.device
                )
                base_scores_all.append(base_scores)

        # 출력
        print_sample(i, raw_prompt, ft_output, reference,
                     base_output, ft_scores, base_scores)

        results.append({
            "idx":         i,
            "raw_prompt":  raw_prompt,
            "ft_output":   ft_output,
            "ft_scores":   ft_scores,
            "base_output": base_output,
            "base_scores": base_scores,
            "reference":   reference,
        })

    # ── 전체 평균 요약 ────────────────────────────────────────
    if ft_scores_all:
        print(SEP_DOUBLE)
        print("  ■ 전체 평균 정량 지표 요약")
        print(SEP_SINGLE)
        print_summary(ft_scores_all, "SFT LoRA")
        if base_scores_all:
            print_summary(base_scores_all, "베이스 모델 (Qwen3-8B)")

    print()
    print(SEP_DOUBLE)
    print(f"총 {len(samples)}개 샘플 추론 완료.")
    print(f"텍스트 로그 저장: {txt_path}")

    # ── JSON 저장 (선택) ──────────────────────────────────────
    if args.save_json:
        tee.flush()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"JSON 결과 저장 : {json_path}")

    tee.close()
    sys.stdout = tee._stdout


if __name__ == "__main__":
    main()
