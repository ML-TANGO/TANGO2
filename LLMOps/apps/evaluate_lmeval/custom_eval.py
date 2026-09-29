"""커스텀 파일 평가 — 런 데이터셋(입력-정답 쌍)으로 생성한 뒤 F1/EM/BLEU/ROUGE.

행 해석은 **플랫폼 규약을 그대로 따른다**(llm_evaluation service.py `_row_to_sample`):
prompt/reference 키 우선순위와 Alpaca(`### Response:`) 분리가 같아야, 같은 데이터셋이
평가 추론 러너·전문가 평가에서 보이는 샘플과 여기서 채점되는 샘플이 일치한다. 이미지 전용
행은 텍스트 생성 평가 대상이 아니라 건너뛴다. 정답이 리스트면 복수 정답(최댓값)이다.

지표 구현은 ETRI `Evaluation/lmeval/custom_metrics.py` 를 옮긴 것이다 — 한국어는 공백
단위 F1/ROUGE 가 어절 결합 때문에 과소평가되므로 글자 단위로 토큰화하고, BLEU 는
sacrebleu `char` 토크나이저를 쓴다. 전부 0~100 스케일.

ETRI 원본과 다른 점 — Qwen3 류는 chat template 을 적용하면 사고 모드가 기본이라 답보다
`<think>…</think>` 가 먼저 나와 토큰 예산을 먹고 채점을 오염시킨다. 템플릿에
`enable_thinking=False` 를 넘기고, 그래도 나온 사고 블록은 채점 전에 걷어낸다.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import string
import unicodedata
from collections import Counter
from typing import List, Optional, Sequence, Tuple

# llm_evaluation service.py:1411-1412 와 같은 순서여야 한다(위 docstring).
PROMPT_KEYS = ("prompt", "input", "question", "instruction", "query", "text")
REFERENCE_KEYS = ("reference", "answer", "output", "completion", "response", "label",
                  "target", "caption")
DATA_EXTS = (".jsonl", ".json", ".csv")
MAX_JSON_BYTES = 50 * 1024 * 1024

_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_PUNCT = set(string.punctuation) | set("·…“”‘’「」『』《》〈〉、。！？，．")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


# ── 데이터 ────────────────────────────────────────────────────────────────────

def _first_value(row: dict, keys):
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        if isinstance(v, list):
            vals = [str(x).strip() for x in v if isinstance(x, (str, int, float)) and str(x).strip()]
            if vals:
                return vals
    return None


def _split_alpaca(text: str) -> Tuple[str, str]:
    m = re.search(r"###\s*Response\s*:\s*", text, re.IGNORECASE)
    if not m:
        return re.sub(r"###\s*Instruction\s*:\s*", "", text, flags=re.IGNORECASE).strip(), ""
    inp = re.sub(r"###\s*Instruction\s*:\s*", "", text[:m.start()], flags=re.IGNORECASE).strip()
    return inp, text[m.end():].strip()


def row_to_pair(row) -> Optional[Tuple[str, List[str]]]:
    """행 → (prompt, [정답…]) 또는 None(입력 또는 정답이 없는 행)."""
    if not isinstance(row, dict):
        return None
    has_explicit = any(k in row for k in PROMPT_KEYS if k != "text")
    if not has_explicit and isinstance(row.get("text"), str):
        prompt, alpaca_ref = _split_alpaca(row["text"])
        ref = _first_value(row, REFERENCE_KEYS) or alpaca_ref
    else:
        prompt = _first_value(row, PROMPT_KEYS)
        prompt = prompt if isinstance(prompt, str) else ""
        ref = _first_value(row, REFERENCE_KEYS) or ""
    refs = ref if isinstance(ref, list) else ([ref] if ref else [])
    if not prompt or not refs:
        return None
    return prompt, refs


def _rows(path: str):
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        yield None
    elif path.endswith(".json"):
        if os.path.getsize(path) > MAX_JSON_BYTES:
            raise ValueError(f"{os.path.basename(path)}: .json 이 {MAX_JSON_BYTES >> 20}MB 를 넘는다 — jsonl 로 올려라")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        yield from (data if isinstance(data, list)
                    else data.get("data", []) if isinstance(data, dict) else [])
    elif path.endswith(".csv"):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)


def load_pairs(dataset_dir: str, limit: Optional[int] = None):
    """데이터셋 디렉토리 → ([(prompt, refs)], 통계). 파일은 경로순으로 읽는다."""
    files = []
    for root, _dirs, names in os.walk(dataset_dir):
        files += [os.path.join(root, n) for n in names if n.lower().endswith(DATA_EXTS)]
    files.sort()
    pairs, skipped = [], 0
    for path in files:
        for row in _rows(path):
            pair = row_to_pair(row)
            if pair is None:
                skipped += 1
                continue
            pairs.append(pair)
            if limit and len(pairs) >= limit:
                return pairs, {"files": len(files), "skipped_rows": skipped}
    return pairs, {"files": len(files), "skipped_rows": skipped}


# ── 생성 ──────────────────────────────────────────────────────────────────────

def build_prompt(tokenizer, prompt: str) -> str:
    if not getattr(tokenizer, "chat_template", None):
        return prompt
    msgs = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                             enable_thinking=False)
    except TypeError:      # 추가 템플릿 변수를 받지 않는 토크나이저
        return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def fit_prompt(tokenizer, prompt: str, max_prompt: int) -> Tuple[List[int], bool]:
    """프롬프트 → 토큰 ID(≤ max_prompt), 잘렸는지.

    넘치면 **템플릿을 입히기 전의 사용자 내용**을 앞에서 넘친 만큼 잘라 다시 템플릿을 입힌다 —
    템플릿을 입힌 토큰열의 앞을 자르면 BOS·시스템 헤더·역할 마커가 날아가 모델이 반쯤 잘린
    템플릿을 보게 된다. 질문 끝과 생성 프롬프트는 뒤에 있어 앞을 자르는 쪽이 낫다.
    chat template 결과에는 BOS 가 이미 들어 있어 special token 을 다시 붙이지 않는다.
    """
    templated = bool(getattr(tokenizer, "chat_template", None))

    def encode(text: str) -> List[int]:
        return tokenizer(build_prompt(tokenizer, text), add_special_tokens=not templated)["input_ids"]

    ids = encode(prompt)
    over = len(ids) - max_prompt
    if over <= 0:
        return ids, False
    content = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    # 디코드→재토큰화 경계에서 토큰 수가 조금 달라질 수 있어 여유를 둔다.
    ids = encode(tokenizer.decode(content[over + 8:], skip_special_tokens=True))
    if len(ids) > max_prompt:          # 템플릿만으로도 넘치는 극단 — 마지막 수단
        ids = ids[-max_prompt:]
    return ids, True


def strip_think(text: str) -> str:
    text = _THINK_BLOCK.sub("", text or "")
    if "<think>" in text:              # 닫히지 않은 사고 블록 = 답이 나오기 전에 잘렸다
        text = text.split("<think>", 1)[0]
    return text.strip()


# ── 지표 (ETRI custom_metrics.py 이식) ─────────────────────────────────────────

def is_korean(text: str, threshold: float = 0.15) -> bool:
    letters = sum(1 for c in (text or "") if not c.isspace())
    return letters > 0 and len(_HANGUL.findall(text)) / letters >= threshold


def normalize_answer(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = "".join(ch for ch in s if ch not in _PUNCT)
    return " ".join(s.split())


def tokenize(text: str, korean: bool) -> List[str]:
    norm = normalize_answer(text)
    if not norm:
        return []
    return [c for c in norm if not c.isspace()] if korean else norm.split()


def _f(match: int, n_pred: int, n_gold: int) -> float:
    if not match or not n_pred or not n_gold:
        return 0.0
    p, r = match / n_pred, match / n_gold
    return 2 * p * r / (p + r)


def _ngrams(toks: Sequence[str], n: int) -> Counter:
    return Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def _lcs(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def pair_scores(pred: str, gold: str, korean: bool) -> dict:
    p, g = tokenize(pred, korean), tokenize(gold, korean)
    if not p or not g:
        f1 = 1.0 if (not p and not g) else 0.0
    else:
        f1 = _f(sum((Counter(p) & Counter(g)).values()), len(p), len(g))
    return {
        "f1": f1,
        "em": 1.0 if normalize_answer(pred) == normalize_answer(gold) else 0.0,
        "rouge1": _f(sum((Counter(p) & Counter(g)).values()), len(p), len(g)),
        "rouge2": _f(sum((_ngrams(p, 2) & _ngrams(g, 2)).values()),
                     max(len(p) - 1, 0), max(len(g) - 1, 0)),
        "rougeL": _f(_lcs(p, g), len(p), len(g)),
    }


def corpus_bleu(preds: List[str], refs: List[List[str]], korean: bool) -> float:
    import sacrebleu

    width = max(len(r) for r in refs) if refs else 1
    ref_matrix = [[(r[i] if i < len(r) else "") for r in refs] for i in range(width)]
    return float(sacrebleu.corpus_bleu(preds, ref_matrix,
                                       tokenize="char" if korean else "13a").score)


def evaluate_pairs(preds: List[str], refs: List[List[str]], lang: str = "auto") -> dict:
    """(예측, 복수 정답) → {"count", "korean", "metrics"(0~100), "per_sample"}."""
    korean = lang == "ko" or (lang == "auto" and is_korean(" ".join(r[0] for r in refs[:50])))
    keys = ("f1", "em", "rouge1", "rouge2", "rougeL")
    total = dict.fromkeys(keys, 0.0)
    per = []
    for i, (pred, golds) in enumerate(zip(preds, refs)):
        best = {k: max(pair_scores(pred, g, korean)[k] for g in golds) for k in keys}
        for k in keys:
            total[k] += best[k]
        per.append({"index": i, "prediction": pred, "references": golds,
                    **{k: round(100 * v, 2) for k, v in best.items()}})
    n = len(per)
    metrics = {k: (100 * total[k] / n if n else 0.0) for k in keys}
    metrics["bleu"] = corpus_bleu(preds, refs, korean) if n else 0.0
    metrics = {k: (0.0 if math.isnan(v) else round(v, 4)) for k, v in metrics.items()}
    return {"count": n, "korean": korean, "metrics": metrics, "per_sample": per}
