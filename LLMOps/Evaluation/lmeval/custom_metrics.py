"""
custom_metrics.py — 생성 결과에 대한 F1 / EM / BLEU / ROUGE 계산.

외부 패키지가 있으면 그것을 쓰고(sacrebleu, rouge_score), 없으면 순수 파이썬
구현으로 대체(fallback)하므로 의존성 없이도 동작한다.

한국어 처리
  한국어는 공백 단위 토큰이 어절(형태소 결합)이라 F1/ROUGE 가 과소평가된다.
  따라서 텍스트에 한글 비중이 높으면 '문자 단위' 토큰화를 사용한다
  (KoBEST/KLUE 계열 관행). lang="en"/"ko"/"auto" 로 강제 지정 가능.
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections import Counter
from typing import Iterable, Sequence

# --------------------------------------------------------------------------
# 선택적 의존성
# --------------------------------------------------------------------------
try:  # pragma: no cover
    import sacrebleu as _sacrebleu
except Exception:  # pragma: no cover
    _sacrebleu = None

try:  # pragma: no cover
    from rouge_score import rouge_scorer as _rouge_scorer
except Exception:  # pragma: no cover
    _rouge_scorer = None


_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_PUNCT = set(string.punctuation) | set("·…“”‘’「」『』《》〈〉、。！？，．")


# --------------------------------------------------------------------------
# 정규화 / 토큰화
# --------------------------------------------------------------------------
def is_korean(text: str, threshold: float = 0.15) -> bool:
    if not text:
        return False
    hangul = len(_HANGUL.findall(text))
    letters = sum(1 for c in text if not c.isspace())
    return letters > 0 and (hangul / letters) >= threshold


def normalize_answer(s: str) -> str:
    """SQuAD 공식 정규화(소문자화, 관사/구두점/여분 공백 제거) + NFKC."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = "".join(ch for ch in s if ch not in _PUNCT)
    return " ".join(s.split())


def tokenize(text: str, lang: str = "auto") -> list[str]:
    """F1/ROUGE 용 토큰화. 한국어는 문자 단위, 그 외는 공백+영숫자 단위."""
    norm = normalize_answer(text)
    if not norm:
        return []
    use_char = (lang == "ko") or (lang == "auto" and is_korean(norm))
    if use_char:
        return [c for c in norm if not c.isspace()]
    return norm.split()


# --------------------------------------------------------------------------
# EM / F1
# --------------------------------------------------------------------------
def exact_match(pred: str, gold: str) -> float:
    return 1.0 if normalize_answer(pred) == normalize_answer(gold) else 0.0


def token_f1(pred: str, gold: str, lang: str = "auto") -> tuple[float, float, float]:
    """(f1, precision, recall) — SQuAD 방식 토큰 중복 기반."""
    p_toks = tokenize(pred, lang)
    g_toks = tokenize(gold, lang)
    if not p_toks or not g_toks:
        # 둘 다 비었으면 정답(무응답 일치), 한쪽만 비었으면 0
        v = 1.0 if (not p_toks and not g_toks) else 0.0
        return v, v, v
    common = Counter(p_toks) & Counter(g_toks)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0, 0.0, 0.0
    precision = overlap / len(p_toks)
    recall = overlap / len(g_toks)
    f1 = 2 * precision * recall / (precision + recall)
    return f1, precision, recall


def max_over_golds(fn, pred: str, golds: Sequence[str], **kw) -> float:
    """복수 정답 중 최댓값 (SQuAD 관행)."""
    if not golds:
        return 0.0
    vals = []
    for g in golds:
        r = fn(pred, g, **kw) if kw else fn(pred, g)
        vals.append(r[0] if isinstance(r, tuple) else r)
    return max(vals)


# --------------------------------------------------------------------------
# BLEU
# --------------------------------------------------------------------------
def _ngrams(toks: Sequence[str], n: int) -> Counter:
    return Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def _bleu_fallback(preds: Sequence[str], refs: Sequence[Sequence[str]],
                   max_n: int = 4, lang: str = "auto") -> float:
    """코퍼스 단위 BLEU (brevity penalty + add-1 smoothing), 0~100 스케일."""
    import math

    clipped = [0] * max_n
    total = [0] * max_n
    pred_len = 0
    ref_len = 0
    for pred, ref_list in zip(preds, refs):
        p_toks = tokenize(pred, lang)
        r_tok_list = [tokenize(r, lang) for r in ref_list] or [[]]
        pred_len += len(p_toks)
        # 가장 길이가 가까운 reference 를 기준 길이로 사용
        ref_len += min((abs(len(r) - len(p_toks)), len(r)) for r in r_tok_list)[1]
        for n in range(1, max_n + 1):
            p_ng = _ngrams(p_toks, n)
            if not p_ng:
                continue
            max_ref = Counter()
            for r in r_tok_list:
                for g, c in _ngrams(r, n).items():
                    if c > max_ref[g]:
                        max_ref[g] = c
            clipped[n - 1] += sum(min(c, max_ref[g]) for g, c in p_ng.items())
            total[n - 1] += sum(p_ng.values())
    if total[0] == 0:
        return 0.0
    log_sum = 0.0
    for n in range(max_n):
        num = clipped[n] + (0 if n == 0 else 1)   # n>1 add-1 smoothing
        den = total[n] + (0 if n == 0 else 1)
        if den == 0 or num == 0:
            return 0.0
        log_sum += math.log(num / den) / max_n
    bp = 1.0 if pred_len > ref_len else math.exp(1 - ref_len / max(pred_len, 1))
    return 100.0 * bp * math.exp(log_sum)


def corpus_bleu(preds: Sequence[str], refs: Sequence[Sequence[str]],
                lang: str = "auto") -> float:
    """코퍼스 BLEU (0~100). sacrebleu 가 있으면 사용."""
    if not preds:
        return 0.0
    use_ko = (lang == "ko") or (lang == "auto" and is_korean(" ".join(preds[:50])))
    if _sacrebleu is not None:
        try:
            max_refs = max(len(r) for r in refs) if refs else 1
            ref_matrix = [[(r[i] if i < len(r) else "") for r in refs]
                          for i in range(max_refs)]
            tok = "char" if use_ko else "13a"
            return float(_sacrebleu.corpus_bleu(
                list(preds), ref_matrix, tokenize=tok).score)
        except Exception:
            pass
    return _bleu_fallback(preds, refs, lang="ko" if use_ko else "en")


def sentence_bleu(pred: str, golds: Sequence[str], lang: str = "auto") -> float:
    return _bleu_fallback([pred], [list(golds)], lang=lang)


# --------------------------------------------------------------------------
# ROUGE
# --------------------------------------------------------------------------
def _lcs_len(a: Sequence, b: Sequence) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def _f(match: int, n_pred: int, n_gold: int) -> float:
    if match == 0 or n_pred == 0 or n_gold == 0:
        return 0.0
    p = match / n_pred
    r = match / n_gold
    return 2 * p * r / (p + r)


def rouge_scores(pred: str, gold: str, lang: str = "auto") -> dict[str, float]:
    """ROUGE-1/2/L F-measure (0~1). rouge_score 패키지는 한국어에 부적합해
    한국어일 때는 항상 내부 문자 단위 구현을 사용한다."""
    p = tokenize(pred, lang)
    g = tokenize(gold, lang)
    r1 = _f(sum((Counter(p) & Counter(g)).values()), len(p), len(g))
    p2, g2 = _ngrams(p, 2), _ngrams(g, 2)
    r2 = _f(sum((p2 & g2).values()), sum(p2.values()), sum(g2.values()))
    rl = _f(_lcs_len(p, g), len(p), len(g))
    return {"rouge1": r1, "rouge2": r2, "rougeL": rl}


def rouge_max(pred: str, golds: Sequence[str], lang: str = "auto") -> dict[str, float]:
    if not golds:
        return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
    scored = [rouge_scores(pred, g, lang) for g in golds]
    return {k: max(s[k] for s in scored) for k in ("rouge1", "rouge2", "rougeL")}


# --------------------------------------------------------------------------
# 통합 진입점
# --------------------------------------------------------------------------
def evaluate_pairs(
    predictions: Sequence[str],
    references: Sequence[Sequence[str] | str],
    lang: str = "auto",
) -> dict:
    """
    (예측, 정답[복수 허용]) 쌍 목록에 대해 F1/EM/BLEU/ROUGE 를 계산.

    반환:
      {
        "count": n,
        "metrics": {"f1":.., "em":.., "bleu":.., "rouge1":.., "rouge2":.., "rougeL":..},
        "per_sample": [{"index":i, "prediction":..., "references":[...], "f1":.., ...}]
      }
    F1/EM/ROUGE 는 0~100(%) 스케일, BLEU 도 0~100 스케일로 통일한다.
    """
    refs: list[list[str]] = []
    for r in references:
        if isinstance(r, str):
            refs.append([r])
        elif r is None:
            refs.append([""])
        else:
            refs.append([str(x) for x in r])

    n = min(len(predictions), len(refs))
    per: list[dict] = []
    agg = Counter()
    for i in range(n):
        pred = predictions[i] or ""
        gold = refs[i]
        f1 = max_over_golds(token_f1, pred, gold, lang=lang)
        em = max_over_golds(exact_match, pred, gold)
        rg = rouge_max(pred, gold, lang)
        bl = sentence_bleu(pred, gold, lang)
        per.append({
            "index": i,
            "prediction": pred,
            "references": gold,
            "f1": 100 * f1, "em": 100 * em, "bleu": bl,
            "rouge1": 100 * rg["rouge1"],
            "rouge2": 100 * rg["rouge2"],
            "rougeL": 100 * rg["rougeL"],
        })
        agg["f1"] += 100 * f1
        agg["em"] += 100 * em
        agg["rouge1"] += 100 * rg["rouge1"]
        agg["rouge2"] += 100 * rg["rouge2"]
        agg["rougeL"] += 100 * rg["rougeL"]

    metrics = {k: (agg[k] / n if n else 0.0)
               for k in ("f1", "em", "rouge1", "rouge2", "rougeL")}
    # BLEU 는 코퍼스 단위가 표준
    metrics["bleu"] = corpus_bleu([p or "" for p in predictions[:n]], refs[:n], lang)
    return {"count": n, "metrics": metrics, "per_sample": per}


if __name__ == "__main__":  # 간단 자체 점검
    preds = ["파리는 프랑스의 수도입니다.", "The capital of France is Paris."]
    golds = [["프랑스의 수도는 파리이다."], ["Paris", "Paris is the capital of France"]]
    out = evaluate_pairs(preds, golds)
    for k, v in out["metrics"].items():
        print(f"{k:8s} {v:6.2f}")
