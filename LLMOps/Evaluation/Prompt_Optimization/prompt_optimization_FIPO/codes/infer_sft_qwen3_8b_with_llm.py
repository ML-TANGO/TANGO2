#!/usr/bin/env python
"""
FIPO 파이프라인 벤치마크 평가 스크립트

별도 학습 없이 순수 추론(inference)만으로 평가합니다.

파이프라인:
  Raw Prompt
      │
      ▼
  [Prompt Optimizer: SFT LoRA Qwen3-8B]  ← 우리가 학습한 모델
      │
      ▼
  Optimized Prompt
      │
      ▼
  [Generator LLM]                         ← 별도 모델 (frozen, 학습 없음)
      │
      ▼
  Answer → Accuracy

지원 벤치마크:
  gsm8k      수학 추론           (Exact Match on final number)
  hellaswag  상식 추론 4지선다   (Accuracy) ← cosmos_qa 대체 (datasets 4.x 호환)
  mmlu       다분야 지식 4지선다 (Accuracy)
  all        위 3개 순차 실행    (모델을 각 1회만 로드)

비교:
  Baseline : raw prompt → Generator (optimizer 없이)
  FIPO     : raw prompt → Optimizer → Generator

사용 예시:
  # 3개 벤치마크 모두 순차 실행 (권장)
  python infer_sft_qwen3_8b_with_llm.py --benchmark all --num_samples 100

  # GSM8K 단독
  python infer_sft_qwen3_8b_with_llm.py --benchmark gsm8k --num_samples 100

  # HellaSwag (commonsense) 단독
  python infer_sft_qwen3_8b_with_llm.py --benchmark hellaswag --num_samples 200

  # MMLU 특정 과목
  python infer_sft_qwen3_8b_with_llm.py --benchmark mmlu --mmlu_subject high_school_math --num_samples 50

  # baseline 없이 FIPO만 (속도 2배)
  python infer_sft_qwen3_8b_with_llm.py --benchmark all --num_samples 100 --no_baseline
"""

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# ──────────────────────────────────────────────────────────────
# 기본 경로
# ──────────────────────────────────────────────────────────────
DEFAULT_ADAPTER_PATH = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/promptopti/model/sft/checkpoint-5625"
)
DEFAULT_GENERATOR    = "meta-llama/Llama-2-7b-chat-hf"
DEFAULT_LOG_DIR      = (
    "/scratch/x3397a11/minkyu/workspace/ETRI/promptopti/FIPO_Project/inference"
)

SEP_DOUBLE = "═" * 80
SEP_SINGLE = "─" * 80

OPTIMIZER_SYSTEM = (
    "You are a prompt optimizer. Rewrite the user's raw prompt into a clearer, "
    "more detailed, and more effective instruction prompt. "
    "Return only the rewritten optimized prompt."
)


# ──────────────────────────────────────────────────────────────
# Tee: stdout + 파일 동시 출력
# ──────────────────────────────────────────────────────────────
class Tee:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f      = open(path, "w", encoding="utf-8")
        self._stdout = sys.stdout

    def write(self, msg: str):
        self._stdout.write(msg)
        self._f.write(msg)

    def flush(self):
        self._stdout.flush()
        self._f.flush()

    def close(self):
        self._f.close()


# ══════════════════════════════════════════════════════════════
# 1. 데이터셋 로드 & 프롬프트 포맷
# ══════════════════════════════════════════════════════════════

def load_benchmark(benchmark: str, num_samples: int, mmlu_subject: str = "all"):
    from datasets import load_dataset
    print(f"[데이터셋] {benchmark} 로드 중 ({num_samples}개)...")

    if benchmark == "gsm8k":
        ds = load_dataset("openai/gsm8k", "main", split="test")
    elif benchmark == "hellaswag":
        # cosmos_qa는 datasets 4.x에서 Python 스크립트 방식이라 지원 종료
        # hellaswag는 동일한 commonsense 4지선다 벤치마크
        ds = load_dataset("hellaswag", split="validation")
    elif benchmark == "mmlu":
        ds = load_dataset("cais/mmlu", mmlu_subject, split="test")
    else:
        raise ValueError(f"지원하지 않는 benchmark: {benchmark}")

    if num_samples and num_samples < len(ds):
        ds = ds.select(range(num_samples))

    samples = []
    for row in ds:
        samples.append(parse_sample(benchmark, row))
    return samples


def parse_sample(benchmark: str, row: dict) -> dict:
    """벤치마크 row → 공통 dict: raw_prompt, choices, answer_idx, answer_text"""
    if benchmark == "gsm8k":
        # answer 필드: "... #### 42"
        ans_text = row["answer"].split("####")[-1].strip().replace(",", "")
        return {
            "raw_prompt":  row["question"],
            "choices":     None,              # 주관식
            "answer_idx":  None,
            "answer_text": ans_text,          # 정수 문자열
        }

    elif benchmark == "hellaswag":
        # label은 문자열 "0"~"3"
        endings = row["endings"]              # list of 4 endings
        label   = int(row["label"])           # 0~3
        return {
            "raw_prompt": (
                f"Context: {row['ctx']}\n\n"
                f"A. {endings[0]}\n"
                f"B. {endings[1]}\n"
                f"C. {endings[2]}\n"
                f"D. {endings[3]}"
            ),
            "choices":     endings,
            "answer_idx":  label,
            "answer_text": "ABCD"[label],
        }

    elif benchmark == "mmlu":
        choices  = row["choices"]             # list of 4
        label    = row["answer"]              # 0~3
        choice_str = "\n".join(f"{chr(65+i)}. {c}" for i, c in enumerate(choices))
        return {
            "raw_prompt": (
                f"Question: {row['question']}\n\n"
                f"{choice_str}"
            ),
            "choices":     choices,
            "answer_idx":  label,
            "answer_text": "ABCD"[label],
        }


# ══════════════════════════════════════════════════════════════
# 2. 모델 로드 / 해제
# ══════════════════════════════════════════════════════════════

def load_optimizer(adapter_path: str, device: str):
    print(f"\n[Optimizer 로드] {adapter_path}")
    tok = AutoTokenizer.from_pretrained(adapter_path, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"

    base = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-8B", torch_dtype=torch.bfloat16, device_map=device
    )
    base.config.use_cache = True
    model = PeftModel.from_pretrained(base, adapter_path)
    model.eval()
    return tok, model


def load_generator(model_name: str, device: str):
    print(f"\n[Generator 로드] {model_name}")
    tok = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tok.pad_token is None:
        # Llama2는 pad_token이 없으므로 eos_token으로 대체
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"

    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.bfloat16, device_map=device
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


# ══════════════════════════════════════════════════════════════
# 3. 추론 함수
# ══════════════════════════════════════════════════════════════

@torch.inference_mode()
def run_inference(model, tokenizer, prompt: str, device: str,
                  max_new_tokens: int = 512, temperature: float = 0.0) -> str:
    # apply_chat_template(tokenize=False) 결과물은 이미 special token 문자열을 포함.
    # add_special_tokens=False 로 중복 추가 방지 (Qwen3, Llama2 공통 안전).
    inputs    = tokenizer(prompt, return_tensors="pt",
                          add_special_tokens=False).to(device)
    input_len = inputs["input_ids"].shape[1]
    outputs   = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,          # 평가는 greedy (재현성)
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(
        outputs[0][input_len:], skip_special_tokens=True
    ).strip()


def build_optimizer_input(tokenizer, raw_prompt: str) -> str:
    messages = [
        {"role": "system", "content": OPTIMIZER_SYSTEM},
        {"role": "user",   "content": f"Raw prompt:\n{raw_prompt}"},
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False,
        add_generation_prompt=True, enable_thinking=False,
    )


def is_qwen(tokenizer) -> bool:
    """Qwen 계열 tokenizer 여부 판별"""
    cls_name = type(tokenizer).__name__.lower()
    model_id  = getattr(tokenizer, "name_or_path", "").lower()
    return "qwen" in cls_name or "qwen" in model_id


def build_generator_input(tokenizer, prompt: str, benchmark: str) -> str:
    """Generator에게 넘길 최종 입력 구성 (모델 계열에 따라 chat template 분기)"""
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
        {"role": "user",   "content": prompt},
    ]

    kwargs = dict(tokenize=False, add_generation_prompt=True)
    # enable_thinking 은 Qwen3 전용 파라미터 — 다른 모델에서는 TypeError 발생
    if is_qwen(tokenizer):
        kwargs["enable_thinking"] = False

    return tokenizer.apply_chat_template(messages, **kwargs)


# ══════════════════════════════════════════════════════════════
# 4. 정답 추출 & 채점
# ══════════════════════════════════════════════════════════════

def extract_answer(response: str, benchmark: str) -> str:
    """모델 응답에서 답 추출"""
    if benchmark == "gsm8k":
        # "#### 42" 형식 우선
        m = re.search(r'####\s*([\d,]+)', response)
        if m:
            return m.group(1).replace(",", "")
        # 마지막 등장 숫자
        nums = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', response)
        return nums[-1].replace(",", "") if nums else ""
    else:
        # 응답 앞부분에서 A/B/C/D 찾기
        clean = response.strip()
        m = re.search(r'\b([ABCD])\b', clean[:30])
        if m:
            return m.group(1)
        # 첫 글자가 선택지인 경우
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
    else:
        return pred.upper() == gold.upper()


# ══════════════════════════════════════════════════════════════
# 5. 결과 출력 & 저장
# ══════════════════════════════════════════════════════════════

def print_sample_result(i: int, total: int, raw_prompt: str,
                        opt_prompt: str, gold: str,
                        base_resp: str, base_pred: str, base_ok: bool,
                        fipo_resp: str, fipo_pred: str, fipo_ok: bool,
                        benchmark: str, no_baseline: bool):
    print(SEP_DOUBLE)
    print(f"[샘플 {i+1}/{total}]  정답: {gold}")
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
    fipo_acc     = fipo_correct / n if n else 0

    print(SEP_DOUBLE)
    print(f"  ■ 최종 평가 결과  |  {benchmark.upper()}  |  n={n}")
    print(SEP_SINGLE)

    if not no_baseline:
        base_correct = sum(r["base_correct"] for r in results)
        base_acc     = base_correct / n if n else 0
        delta        = fipo_acc - base_acc
        print(f"  {'모델':<30} {'정답':>6}  {'정확도':>8}")
        print(f"  {'─'*48}")
        print(f"  {'Baseline (raw → generator)':<30} {base_correct:>6}  {base_acc:>8.4f}")
        print(f"  {'FIPO (optimizer → generator)':<30} {fipo_correct:>6}  {fipo_acc:>8.4f}")
        sign = "+" if delta >= 0 else ""
        print(f"  {'개선폭 (FIPO - Baseline)':<30} {'':>6}  {sign}{delta:>7.4f}")
    else:
        print(f"  {'FIPO (optimizer → generator)':<30} {fipo_correct:>6} / {n}  {fipo_acc:.4f}")
    print()


# ══════════════════════════════════════════════════════════════
# 6. 벤치마크 단위 실행 함수
# ══════════════════════════════════════════════════════════════

def run_optimizer_pass(opt_tok, opt_model, samples: list,
                       device: str, max_new_tokens: int,
                       benchmark_name: str) -> list:
    """Pass 1: 샘플 리스트 전체에 대해 최적화 프롬프트 생성"""
    optimized = []
    n = len(samples)
    print(f"\n  [Pass 1 – {benchmark_name}]  Optimizer 추론 중 ({n}개)...")
    for i, s in enumerate(samples):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    최적화 중... {i+1}/{n}")
        inp = build_optimizer_input(opt_tok, s["raw_prompt"])
        optimized.append(run_inference(opt_model, opt_tok, inp, device,
                                       max_new_tokens=max_new_tokens))
    print(f"    완료: {n}개")
    return optimized


def run_generator_pass(gen_tok, gen_model, samples: list,
                       optimized_prompts: list, device: str,
                       max_new_tokens: int, benchmark: str,
                       no_baseline: bool) -> list:
    """Pass 2: 최적화 프롬프트로 Generator 추론 + 채점"""
    results = []
    n = len(samples)
    print(f"\n  [Pass 2 – {benchmark}]  Generator 추론 & 채점 중 ({n}개)...")
    for i, (s, opt_prompt) in enumerate(zip(samples, optimized_prompts)):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    생성 중... {i+1}/{n}")

        fipo_inp  = build_generator_input(gen_tok, opt_prompt, benchmark)
        fipo_resp = run_inference(gen_model, gen_tok, fipo_inp, device,
                                  max_new_tokens=max_new_tokens)
        fipo_pred = extract_answer(fipo_resp, benchmark)
        fipo_ok   = is_correct(fipo_pred, s["answer_text"], benchmark)

        base_resp = base_pred = ""
        base_ok   = False
        if not no_baseline:
            base_inp  = build_generator_input(gen_tok, s["raw_prompt"], benchmark)
            base_resp = run_inference(gen_model, gen_tok, base_inp, device,
                                      max_new_tokens=max_new_tokens)
            base_pred = extract_answer(base_resp, benchmark)
            base_ok   = is_correct(base_pred, s["answer_text"], benchmark)

        print_sample_result(
            i, n, s["raw_prompt"], opt_prompt, s["answer_text"],
            base_resp, base_pred, base_ok,
            fipo_resp, fipo_pred, fipo_ok,
            benchmark, no_baseline,
        )
        results.append({
            "idx":           i,
            "raw_prompt":    s["raw_prompt"],
            "optimized":     opt_prompt,
            "gold":          s["answer_text"],
            "fipo_response": fipo_resp,
            "fipo_pred":     fipo_pred,
            "fipo_correct":  fipo_ok,
            "base_response": base_resp,
            "base_pred":     base_pred,
            "base_correct":  base_ok,
        })
    return results


def print_all_summary(all_results: dict, no_baseline: bool):
    """3개 벤치마크 통합 요약 테이블"""
    print()
    print(SEP_DOUBLE)
    print("  ■ 전체 벤치마크 통합 요약")
    print(SEP_SINGLE)

    if no_baseline:
        print(f"  {'벤치마크':<14} {'n':>5}  {'FIPO 정확도':>12}")
        print(f"  {'─'*36}")
        for bname, results in all_results.items():
            n    = len(results)
            facc = sum(r["fipo_correct"] for r in results) / n if n else 0
            print(f"  {bname:<14} {n:>5}  {facc:>12.4f}")
    else:
        print(f"  {'벤치마크':<14} {'n':>5}  {'Baseline':>10}  {'FIPO':>10}  {'개선폭':>10}")
        print(f"  {'─'*56}")
        for bname, results in all_results.items():
            n    = len(results)
            bacc = sum(r["base_correct"] for r in results) / n if n else 0
            facc = sum(r["fipo_correct"] for r in results) / n if n else 0
            delta = facc - bacc
            sign  = "+" if delta >= 0 else ""
            print(f"  {bname:<14} {n:>5}  {bacc:>10.4f}  {facc:>10.4f}  {sign}{delta:>9.4f}")
    print()


# ══════════════════════════════════════════════════════════════
# 7. 메인
# ══════════════════════════════════════════════════════════════

BENCHMARKS_ALL = ["gsm8k", "hellaswag", "mmlu"]


def main():
    parser = argparse.ArgumentParser(
        description="FIPO 파이프라인 벤치마크 평가 (학습 없이 inference만)"
    )
    parser.add_argument(
        "--benchmark", type=str, default="all",
        choices=["gsm8k", "hellaswag", "mmlu", "all"],
        help="평가할 벤치마크 (기본값: all → 3개 순차 실행)",
    )
    parser.add_argument(
        "--adapter_path", type=str, default=DEFAULT_ADAPTER_PATH,
        help="SFT LoRA 어댑터 경로 (Prompt Optimizer)",
    )
    parser.add_argument(
        "--generator_model", type=str, default=DEFAULT_GENERATOR,
        help=(
            f"Generator LLM 모델명 (기본값: {DEFAULT_GENERATOR}). "
            "반드시 chat/instruct 버전 사용 (예: meta-llama/Llama-2-7b-chat-hf). "
            "base 모델은 chat template이 없어 오류 발생."
        ),
    )
    parser.add_argument(
        "--num_samples", type=int, default=100,
        help="벤치마크당 테스트 샘플 수 (기본값: 100)",
    )
    parser.add_argument(
        "--mmlu_subject", type=str, default="all",
        help="MMLU 과목 (기본값: all, 예: high_school_math)",
    )
    parser.add_argument(
        "--no_baseline", action="store_true",
        help="Baseline 비교 없이 FIPO만 평가 (속도 2배 빠름)",
    )
    parser.add_argument(
        "--max_new_tokens_opt", type=int, default=512,
        help="Optimizer 최대 생성 토큰 (기본값: 512)",
    )
    parser.add_argument(
        "--max_new_tokens_gen", type=int, default=256,
        help="Generator 최대 생성 토큰 (기본값: 256)",
    )
    parser.add_argument(
        "--log_dir", type=str, default=DEFAULT_LOG_DIR,
        help=f"결과 저장 디렉터리 (기본값: {DEFAULT_LOG_DIR})",
    )
    parser.add_argument(
        "--save_json", action="store_true",
        help="JSON 상세 결과도 저장",
    )
    parser.add_argument(
        "--device", type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument(
        "--hf_token", type=str, default=os.environ.get("HF_TOKEN", None),
        help=(
            "HuggingFace 액세스 토큰 (gated 모델 다운로드 시 필요). "
            "예: --hf_token hf_xxxxxxxxxxxx. "
            "설정 시 huggingface_hub.login()을 통해 인증됩니다."
        ),
    )
    args = parser.parse_args()

    # ── HuggingFace 토큰 인증 ─────────────────────────────────
    # login() 대신 환경변수 직접 설정: 서버 검증 없이 모델 다운로드 시 사용됨
    if args.hf_token:
        os.environ["HF_TOKEN"] = args.hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = args.hf_token
        print("[HuggingFace] 토큰 환경변수 설정 완료")

    # ── 실행할 벤치마크 목록 결정 ─────────────────────────────
    benchmarks = BENCHMARKS_ALL if args.benchmark == "all" else [args.benchmark]

    # ── 로그 파일 경로 ────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ckpt_tag  = os.path.basename(args.adapter_path.rstrip("/"))
    gen_tag   = args.generator_model.replace("/", "-")
    bench_tag = args.benchmark
    if args.benchmark == "mmlu":
        bench_tag += f"_{args.mmlu_subject}"

    log_stem  = f"{timestamp}_{bench_tag}_{ckpt_tag}_gen-{gen_tag}_n{args.num_samples}"
    txt_path  = os.path.join(args.log_dir, f"{log_stem}.txt")
    json_path = os.path.join(args.log_dir, f"{log_stem}.json")

    os.makedirs(args.log_dir, exist_ok=True)
    tee = Tee(txt_path)
    sys.stdout = tee

    # ── 실행 헤더 ─────────────────────────────────────────────
    print(SEP_DOUBLE)
    print(f"  FIPO 파이프라인 벤치마크 평가  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP_SINGLE)
    print(f"  benchmark      : {args.benchmark}  →  실행 순서: {' → '.join(benchmarks)}")
    print(f"  optimizer      : {args.adapter_path}")
    print(f"  generator      : {args.generator_model}")
    print(f"  num_samples    : {args.num_samples}  (벤치마크당)")
    print(f"  baseline 비교  : {'비활성화' if args.no_baseline else '활성화'}")
    print(f"  device         : {args.device}", end="")
    if torch.cuda.is_available():
        print(f"  ({torch.cuda.get_device_name(0)},  "
              f"{torch.cuda.get_device_properties(0).total_memory/1e9:.0f}GB)", end="")
    print()
    print(f"  log (txt)      : {txt_path}")
    print(SEP_DOUBLE)

    # ── 데이터 로드 (모든 벤치마크) ───────────────────────────
    print()
    all_samples: dict = {}
    for bname in benchmarks:
        subj = args.mmlu_subject if bname == "mmlu" else "all"
        all_samples[bname] = load_benchmark(bname, args.num_samples, subj)
        print(f"  {bname:<12} → {len(all_samples[bname])}개 샘플 준비")
    print()

    # ══════════════════════════════════════════════════════════
    # PASS 1: Optimizer를 한 번만 로드 → 모든 벤치마크 최적화
    # ══════════════════════════════════════════════════════════
    print(SEP_SINGLE)
    print("  [Pass 1]  Prompt Optimizer 로드 → 전체 벤치마크 최적화")
    print(SEP_SINGLE)

    opt_tok, opt_model = load_optimizer(args.adapter_path, args.device)
    all_optimized: dict = {}
    for bname in benchmarks:
        all_optimized[bname] = run_optimizer_pass(
            opt_tok, opt_model, all_samples[bname],
            args.device, args.max_new_tokens_opt, bname,
        )

    unload(opt_model)
    del opt_tok
    print(f"\n  Optimizer 언로드 완료. 전체 {sum(len(v) for v in all_optimized.values())}개 최적화 완료.")

    # ══════════════════════════════════════════════════════════
    # PASS 2: Generator를 한 번만 로드 → 모든 벤치마크 추론 & 채점
    # ══════════════════════════════════════════════════════════
    print()
    print(SEP_SINGLE)
    print("  [Pass 2]  Generator 로드 → 전체 벤치마크 추론 & 채점")
    print(SEP_SINGLE)

    gen_tok, gen_model = load_generator(args.generator_model, args.device)
    all_results: dict  = {}
    for bname in benchmarks:
        all_results[bname] = run_generator_pass(
            gen_tok, gen_model,
            all_samples[bname], all_optimized[bname],
            args.device, args.max_new_tokens_gen,
            bname, args.no_baseline,
        )
        print_summary(all_results[bname], bname, args.no_baseline)

    unload(gen_model)
    del gen_tok

    # ── 통합 요약 (all 모드일 때만) ──────────────────────────
    if len(benchmarks) > 1:
        print_all_summary(all_results, args.no_baseline)

    print(f"텍스트 로그 저장: {txt_path}")

    # ── JSON 저장 ─────────────────────────────────────────────
    if args.save_json:
        tee.flush()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"JSON 결과 저장 : {json_path}")

    tee.close()
    sys.stdout = tee._stdout


if __name__ == "__main__":
    main()
