"""
custom_eval.py — 사용자가 준비한 JSON/JSONL/CSV(입력-정답 쌍)로 생성 평가.

지원 컬럼 이름(자동 탐지)
  입력 : input, prompt, question, instruction, query, src, text
  정답 : answer, answers, output, reference, references, target, label, gold, tgt
  (선택) context / passage 가 있으면 프롬프트에 함께 넣는다.

정답이 리스트면 복수 정답으로 처리해 최댓값(F1/EM/ROUGE)을 취한다.

CLI:
  python custom_eval.py --model <path> --file custom_data/sample.jsonl \
      --out runs/custom --limit 100 --max-new-tokens 256
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from typing import Any

import custom_metrics as CM
from model_loader import load_model, load_tokenizer, resolve_model_path

INPUT_KEYS = ["input", "prompt", "question", "instruction", "query", "src", "text"]
GOLD_KEYS = ["answer", "answers", "output", "reference", "references",
             "target", "targets", "label", "gold", "tgt", "completion"]
CTX_KEYS = ["context", "passage", "document", "paragraph"]


# --------------------------------------------------------------------------
# 데이터 로딩
# --------------------------------------------------------------------------
def load_records(path: str) -> list[dict]:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"커스텀 평가 파일이 없습니다: {path}")
    ext = os.path.splitext(path)[1].lower()

    if ext in (".jsonl", ".ndjson"):
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in ("data", "examples", "records", "items", "rows"):
                if isinstance(data.get(k), list):
                    return data[k]
            raise ValueError("JSON 최상위가 dict 인 경우 data/examples/records 키가 필요합니다.")
        return list(data)

    if ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f, delimiter=delim))

    raise ValueError(f"지원하지 않는 확장자: {ext} (json/jsonl/csv/tsv)")


def _pick(rec: dict, keys: list[str]):
    for k in keys:
        if k in rec and rec[k] not in (None, ""):
            return rec[k]
    # 대소문자 무시 재탐색
    low = {str(k).lower(): v for k, v in rec.items()}
    for k in keys:
        if k in low and low[k] not in (None, ""):
            return low[k]
    return None


def parse_records(records: list[dict]) -> tuple[list[str], list[list[str]], list[str]]:
    """→ (inputs, golds, contexts)"""
    inputs, golds, ctxs = [], [], []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"{i}번째 레코드가 dict 가 아닙니다: {type(rec)}")
        src = _pick(rec, INPUT_KEYS)
        gold = _pick(rec, GOLD_KEYS)
        if src is None or gold is None:
            raise ValueError(
                f"{i}번째 레코드에서 입력/정답 컬럼을 찾지 못했습니다. "
                f"키={list(rec.keys())}\n"
                f"입력 후보={INPUT_KEYS}\n정답 후보={GOLD_KEYS}")
        if isinstance(gold, dict) and "text" in gold:   # SQuAD 형식
            gold = gold["text"]
        if isinstance(gold, (list, tuple)):
            gold_list = [str(g) for g in gold if str(g).strip() != ""] or [""]
        else:
            gold_list = [str(gold)]
        inputs.append(str(src))
        golds.append(gold_list)
        ctxs.append(str(_pick(rec, CTX_KEYS) or ""))
    return inputs, golds, ctxs


# --------------------------------------------------------------------------
# 생성
# --------------------------------------------------------------------------
def build_prompt(tok, question: str, context: str, system: str | None,
                 use_chat_template: bool) -> str:
    user = f"{context}\n\n{question}".strip() if context else question
    if use_chat_template and getattr(tok, "chat_template", None):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": user}]
        try:
            return tok.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True)
        except Exception:
            pass
    return (f"{system}\n\n" if system else "") + user


def generate(model, tok, prompts: list[str], max_new_tokens: int = 256,
             batch_size: int = 8, temperature: float = 0.0,
             progress=None) -> list[str]:
    import torch

    device = next(model.parameters()).device
    tok.padding_side = "left"
    outs: list[str] = []
    n = len(prompts)
    for start in range(0, n, batch_size):
        chunk = prompts[start:start + batch_size]
        enc = tok(chunk, return_tensors="pt", padding=True,
                  truncation=True, max_length=4096).to(device)
        gen_kw = dict(max_new_tokens=max_new_tokens,
                      pad_token_id=tok.pad_token_id or tok.eos_token_id)
        if temperature and temperature > 0:
            gen_kw.update(do_sample=True, temperature=temperature, top_p=0.95)
        else:
            gen_kw.update(do_sample=False)
        with torch.no_grad():
            out = model.generate(**enc, **gen_kw)
        for i in range(len(chunk)):
            new_tokens = out[i][enc["input_ids"].shape[1]:]
            outs.append(tok.decode(new_tokens, skip_special_tokens=True).strip())
        if progress:
            progress(min(start + batch_size, n), n)
    return outs


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def run_custom_eval(
    model_path: str,
    file_path: str,
    out_dir: str,
    limit: int | None = None,
    max_new_tokens: int = 256,
    batch_size: int = 8,
    dtype: str = "bfloat16",
    lang: str = "auto",
    system_prompt: str | None = None,
    use_chat_template: bool = True,
    temperature: float = 0.0,
    model: Any = None,
    tokenizer: Any = None,
    log=print,
    progress=None,
) -> dict:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)

    records = load_records(file_path)
    inputs, golds, ctxs = parse_records(records)
    if limit:
        inputs, golds, ctxs = inputs[:limit], golds[:limit], ctxs[:limit]
    log(f"[custom] {file_path}: {len(inputs)}개 샘플 평가")

    if tokenizer is None:
        resolved = resolve_model_path(model_path)
        tokenizer = load_tokenizer(resolved)
    if model is None:
        resolved = resolve_model_path(model_path)
        model = load_model(resolved, dtype=dtype, log=log)

    prompts = [build_prompt(tokenizer, q, c, system_prompt, use_chat_template)
               for q, c in zip(inputs, ctxs)]
    preds = generate(model, tokenizer, prompts, max_new_tokens=max_new_tokens,
                     batch_size=batch_size, temperature=temperature,
                     progress=progress)

    res = CM.evaluate_pairs(preds, golds, lang=lang)
    res["file"] = file_path
    res["model"] = model_path
    res["elapsed_sec"] = round(time.time() - t0, 1)
    res["config"] = dict(limit=limit, max_new_tokens=max_new_tokens,
                         batch_size=batch_size, lang=lang,
                         use_chat_template=use_chat_template,
                         temperature=temperature)
    for i, p in enumerate(res["per_sample"]):
        p["input"] = inputs[i]

    with open(os.path.join(out_dir, "custom_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "custom_samples.jsonl"), "w", encoding="utf-8") as f:
        for p in res["per_sample"]:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    m = res["metrics"]
    log(f"[custom] F1={m['f1']:.2f} EM={m['em']:.2f} BLEU={m['bleu']:.2f} "
        f"ROUGE-1={m['rouge1']:.2f} ROUGE-2={m['rouge2']:.2f} ROUGE-L={m['rougeL']:.2f}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="커스텀 파일(JSON/CSV) 생성 평가")
    ap.add_argument("--model", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default="runs/custom")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-new-tokens", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--lang", default="auto", choices=["auto", "ko", "en"])
    ap.add_argument("--system-prompt", default=None)
    ap.add_argument("--no-chat-template", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    a = ap.parse_args()
    run_custom_eval(
        a.model, a.file, a.out, limit=a.limit, max_new_tokens=a.max_new_tokens,
        batch_size=a.batch_size, dtype=a.dtype, lang=a.lang,
        system_prompt=a.system_prompt, use_chat_template=not a.no_chat_template,
        temperature=a.temperature)


if __name__ == "__main__":
    main()
