"""이중모델 배치 추론 인-프로세스 채점(WBS 4.3 배치).

apps/evaluate/app.py 의 자체메트릭(BLEU / ROUGE-1/2/L)을 그대로 포팅한 순수 파이썬 구현.
외부 의존(sacrebleu/rouge-score) 없음. SP-5(비동기 K8s 평가 job)는 trained model 전제라
ephemeral 세션 배치에 부적합 → 세션 대상 동기 배치는 여기서 경량 채점.
토크나이저는 공백분리+소문자(데모용 단순화, evaluate 와 동일). 정밀 평가는 SP-5/고려대 plugin.
"""
import math
from collections import Counter
from typing import Dict, List

_FIELD_MAX = 4000        # per-row 필드 길이 cap(ROUGE-L LCS O(n*m) DoS 방지)
SELF_METRICS = ("bleu", "rouge")


def _tok(s: str) -> List[str]:
    return str(s).lower().split()


def _ngrams(tokens: List[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)) if len(tokens) >= n else Counter()


def _bleu(preds: List[str], refs: List[str], max_n: int = 4) -> float:
    if not preds:
        return 0.0
    clipped = [0] * max_n
    total = [0] * max_n
    pred_len = ref_len = 0
    for pred, ref in zip(preds, refs):
        p_tok, r_tok = _tok(pred), _tok(ref)
        pred_len += len(p_tok)
        ref_len += len(r_tok)
        for n in range(1, max_n + 1):
            p_ng = _ngrams(p_tok, n)
            r_ng = _ngrams(r_tok, n)
            overlap = sum(min(c, r_ng.get(g, 0)) for g, c in p_ng.items())
            clipped[n - 1] += overlap
            total[n - 1] += sum(p_ng.values())
    precisions = []
    for n in range(max_n):
        c, t = clipped[n], total[n]
        if t == 0:
            continue
        precisions.append((c + 1.0) / (t + 1.0))
    if not precisions:
        return 0.0
    geo_mean = math.exp(sum(math.log(p) for p in precisions) / len(precisions))
    bp = 1.0 if pred_len >= ref_len else math.exp(1 - ref_len / pred_len) if pred_len > 0 else 0.0
    return round(bp * geo_mean * 100.0, 4)


def _rouge_n(pred: str, ref: str, n: int) -> float:
    p_ng, r_ng = _ngrams(_tok(pred), n), _ngrams(_tok(ref), n)
    if not r_ng or not p_ng:
        return 0.0
    overlap = sum(min(c, p_ng.get(g, 0)) for g, c in r_ng.items())
    recall = overlap / max(sum(r_ng.values()), 1)
    prec = overlap / max(sum(p_ng.values()), 1)
    return 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0


def _lcs(a: List[str], b: List[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _rouge_l(pred: str, ref: str) -> float:
    p_tok, r_tok = _tok(pred), _tok(ref)
    if not p_tok or not r_tok:
        return 0.0
    lcs = _lcs(p_tok, r_tok)
    prec = lcs / len(p_tok)
    recall = lcs / len(r_tok)
    return 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0


def score_pair(pred: str, ref: str, metric_set) -> Dict[str, float]:
    """단일 (pred, ref) per-sample 점수(0~100)."""
    pred = str(pred)[:_FIELD_MAX]
    ref = str(ref)[:_FIELD_MAX]
    out: Dict[str, float] = {}
    if "bleu" in metric_set:
        out["bleu"] = _bleu([pred], [ref])
    if "rouge" in metric_set:
        out["rouge1"] = round(_rouge_n(pred, ref, 1) * 100, 4)
        out["rouge2"] = round(_rouge_n(pred, ref, 2) * 100, 4)
        out["rougeL"] = round(_rouge_l(pred, ref) * 100, 4)
    return out


def corpus_scores(preds: List[str], refs: List[str], metric_set) -> Dict[str, float]:
    """코퍼스 요약 — BLEU 는 코퍼스 단위(evaluate 앱과 동일, per-sample 평균 아님. BLEU 는
    비선형이라 평균-of-per-sample 이 부정확), ROUGE 는 per-sample F1 평균(evaluate _rouge_corpus 동일)."""
    if not preds:
        return {}
    preds = [str(p)[:_FIELD_MAX] for p in preds]
    refs = [str(r)[:_FIELD_MAX] for r in refs]
    out: Dict[str, float] = {}
    if "bleu" in metric_set:
        out["bleu"] = _bleu(preds, refs)
    if "rouge" in metric_set:
        n = len(preds)
        out["rouge1"] = round(sum(_rouge_n(p, r, 1) for p, r in zip(preds, refs)) / n * 100, 4)
        out["rouge2"] = round(sum(_rouge_n(p, r, 2) for p, r in zip(preds, refs)) / n * 100, 4)
        out["rougeL"] = round(sum(_rouge_l(p, r) for p, r in zip(preds, refs)) / n * 100, 4)
    return out


def summarize(rows: List[Dict[str, float]], metric_set) -> Dict[str, float]:
    """per-sample score dict 리스트 → 메트릭별 평균(코퍼스 요약)."""
    if not rows:
        return {}
    keys = set()
    for r in rows:
        keys.update(k for k in r.keys() if isinstance(r.get(k), (int, float)))
    summary: Dict[str, float] = {}
    for k in keys:
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if vals:
            summary[k] = round(sum(vals) / len(vals), 4)
    return summary
