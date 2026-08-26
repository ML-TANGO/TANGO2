#!/usr/bin/env python3
"""
eval/metrics.py — 생성 결과 JSONL 을 채점한다.

세 갈래로 잰다.

  표면  : BLEU-1..4, ROUGE-1/2/L, METEOR, chrF++, CIDEr-D
          한국어는 어절 분절이 신뢰하기 어려우므로 형태소(Kiwi) 단위로 토큰화해
          계산하고, chrF++ 는 문자 n-gram 이라 토크나이저 없이 계산한다.
  의미  : BERTScore (한국어 인코더)
  내용  : 조우 유형 / 항법상 지위 / COLREG 조항 / 권고 조종 / 수치 일치도
          수치의 정답은 참조 문장이 아니라 CSV 원본이다.

SPICE 는 넣지 않는다. 번들 구현이 Stanford CoreNLP 기반 영어 전용이고 한국어
씬그래프 파서가 없다.

사용:
  python eval/metrics.py --pred results/eval_20260728/qwen3_sds9k.jsonl \
      --image_dir /home/yvvyee/data/AIVN-SDS/20260728 \
      --out results/eval_20260728/qwen3_sds9k.metrics.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
import statistics as st
from collections import Counter

import pandas as pd

from eval.sds_fields import extract, csv_truth, encounter_from_filename


# TER 에만 쓰는 표본 크기. 이유는 계산 지점의 주석에 있다.
TER_SAMPLE = 200

# ── 토크나이저 ────────────────────────────────────────────────────────────────
_kiwi = None


def morphs(text: str) -> list:
    """형태소 토큰. Kiwi 가 없으면 공백 분절로 물러난다."""
    global _kiwi
    if _kiwi is None:
        try:
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
        except Exception:
            _kiwi = False
    if _kiwi is False:
        return text.split()
    return [t.form for t in _kiwi.tokenize(text)]


# ── 표면 지표 ─────────────────────────────────────────────────────────────────

def surface_metrics(preds: list, refs: list) -> dict:
    out = {}

    tok_p = [" ".join(morphs(p)) for p in preds]
    tok_r = [" ".join(morphs(r)) for r in refs]

    # BLEU. 이미 형태소로 나눈 뒤이므로 sacrebleu 의 내부 토크나이저를 끈다.
    import sacrebleu
    bleu = sacrebleu.corpus_bleu(tok_p, [tok_r], tokenize="none",
                                 force=True, lowercase=False)
    out["BLEU"] = bleu.score
    for i, p in enumerate(bleu.precisions, start=1):
        out[f"BLEU-{i}"] = p

    # chrF++ 는 문자 n-gram 이라 원문 그대로 넣는다.
    out["chrF++"] = sacrebleu.corpus_chrf(preds, [refs], word_order=2).score
    out["chrF"] = sacrebleu.corpus_chrf(preds, [refs], word_order=0).score
    # TER 는 편집거리에 이동(shift) 탐색이 붙어 길이에 급격히 민감하다. 실측에서
    # 평균 766자를 내는 구성 하나가 1,000건에 50분을 넘겨도 끝나지 않았다. 그래서
    # 고정 인덱스 표본으로 한정한다. 모든 구성이 같은 인덱스를 쓰므로 구성 간
    # 비교는 유지되고, 전수 값이 아니라는 점만 이름에 남긴다.
    ter_idx = list(range(0, len(tok_p), max(1, len(tok_p) // TER_SAMPLE)))[:TER_SAMPLE]
    out["TER"] = sacrebleu.corpus_ter(
        [tok_p[i] for i in ter_idx], [[tok_r[i] for i in ter_idx]]
    ).score
    out["TER_n"] = len(ter_idx)

    # ROUGE. rouge_score 의 기본 토크나이저는 한글을 지우므로 형태소 문자열을
    # 넣고 tokenizer 를 공백 분절로 바꾼다.
    from rouge_score import rouge_scorer

    class _WS:
        def tokenize(self, text):
            return text.split()

    rs = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"],
                                  use_stemmer=False, tokenizer=_WS())
    acc = {"rouge1": [], "rouge2": [], "rougeL": []}
    for p, r in zip(tok_p, tok_r):
        sc = rs.score(r, p)
        for k in acc:
            acc[k].append(sc[k].fmeasure)
    for k, v in acc.items():
        out[f"ROUGE-{k[5:].upper()}" if k != "rougeL" else "ROUGE-L"] = \
            100 * sum(v) / max(len(v), 1)

    # METEOR. nltk 구현은 WordNet 동의어를 쓰는데 한국어 synset 이 없으므로
    # 사실상 정확 일치와 어간 일치만 반영된다. 그 한계를 알고 참고용으로 싣는다.
    try:
        import nltk
        from nltk.translate.meteor_score import meteor_score
        try:
            nltk.data.find("corpora/wordnet.zip")
        except LookupError:
            nltk.download("wordnet", quiet=True)
        ms = [meteor_score([morphs(r)], morphs(p)) for p, r in zip(preds, refs)]
        out["METEOR"] = 100 * sum(ms) / max(len(ms), 1)
    except Exception as e:
        out["METEOR"] = None
        out["METEOR_error"] = f"{type(e).__name__}: {e}"

    # CIDEr-D. 참조가 샘플당 하나뿐이라 IDF 가 약해지는 점을 감안해 읽는다.
    try:
        from pycocoevalcap.cider.cider import Cider
        gts = {i: [tok_r[i]] for i in range(len(tok_r))}
        res = {i: [tok_p[i]] for i in range(len(tok_p))}
        score, _ = Cider().compute_score(gts, res)
        out["CIDEr-D"] = 100 * float(score)
    except Exception as e:
        out["CIDEr-D"] = None
        out["CIDEr_error"] = f"{type(e).__name__}: {e}"

    return out


def bertscore_metric(preds: list, refs: list, model: str, batch_size: int) -> dict:
    try:
        from bert_score import score as bs
        P, R, F = bs(preds, refs, model_type=model, num_layers=17,
                     lang="ko", verbose=False, batch_size=batch_size,
                     rescale_with_baseline=False)
        return {
            "BERTScore-P": 100 * P.mean().item(),
            "BERTScore-R": 100 * R.mean().item(),
            "BERTScore-F1": 100 * F.mean().item(),
            "BERTScore_model": model,
        }
    except Exception as e:
        return {"BERTScore-F1": None,
                "BERTScore_error": f"{type(e).__name__}: {e}"}


# ── 내용 지표 ─────────────────────────────────────────────────────────────────

def hangul_stats(preds: list) -> dict:
    """
    한글 비율. CC3M 까지만 학습된 기준선은 한국어 지시를 무시하고 영문 캡션을
    내므로 다른 지표가 모두 바닥에 붙는다. 그 원인이 품질이 아니라 언어 자체에
    있다는 것을 이 값이 구분해 준다.
    """
    def ratio(t):
        letters = [ch for ch in t if ch.isalpha()]
        if not letters:
            return 0.0
        han = sum(1 for ch in letters if "가" <= ch <= "힣")
        return han / len(letters)

    rs = [ratio(p) for p in preds]
    return {
        "hangul_ratio_mean": 100 * sum(rs) / max(len(rs), 1),
        "korean_output_pct": 100 * sum(1 for r in rs if r > 0.5) / max(len(rs), 1),
    }


def _acc(pairs):
    """(정답, 예측) 목록에서 정답이 있는 건만 세어 정확도를 낸다."""
    usable = [(g, p) for g, p in pairs if g is not None]
    if not usable:
        return None, 0
    hit = sum(1 for g, p in usable if g == p)
    return 100 * hit / len(usable), len(usable)


def _num_stats(pairs, tol):
    """(정답, 예측) 수치쌍에서 허용오차 내 비율과 절대오차 통계."""
    usable = [(g, p) for g, p in pairs if g is not None and p is not None]
    if not usable:
        return {"within_tol": None, "mae": None, "median_ae": None,
                "n": 0, "coverage": 0.0}
    errs = [abs(g - p) for g, p in usable]
    total = sum(1 for g, _ in pairs if g is not None)
    return {
        "within_tol": 100 * sum(1 for e in errs if e <= tol) / len(errs),
        "mae": sum(errs) / len(errs),
        "median_ae": st.median(errs),
        "n": len(usable),
        "coverage": 100 * len(usable) / max(total, 1),
    }


def content_metrics(rows: list, image_dir: str) -> dict:
    enc_pairs, role_pairs, turn_pairs = [], [], []
    art_tp = art_fp = art_fn = 0
    num = {k: [] for k in ["cpa", "tcpa", "own_course", "own_speed",
                           "tgt_course", "tgt_speed"]}
    count_pairs = []
    two_sec = 0
    fmt_ok = 0
    port_violation = port_cases = advises_turn = 0
    empty = 0
    lens = []

    for r in rows:
        pred_t = r["prediction"]
        if not pred_t.strip():
            empty += 1
        lens.append(len(pred_t))

        P = extract(pred_t, r["id"])
        G = extract(r["reference"], r["id"])
        two_sec += int(P["has_two_sections"])
        fmt_ok += int(P["follows_format"])

        # 조우 유형의 정답은 파일명이다. 참조 텍스트보다 앞선 근거다.
        enc_pairs.append((encounter_from_filename(r["id"]), P["encounter"]))
        role_pairs.append((G["role"], P["role"]))
        turn_pairs.append((G["turn_dir"], P["turn_dir"]))
        # 육안 식별 타선 수의 정답은 참조 문장이다. CSV 행 수는 시야 밖 선박까지
        # 세므로 이 항목의 정답이 될 수 없다.
        count_pairs.append((G["vessel_count"], P["vessel_count"]))

        art_tp += len(G["articles"] & P["articles"])
        art_fp += len(P["articles"] - G["articles"])
        art_fn += len(G["articles"] - P["articles"])

        # 좌현 변침 금지 위반. 참조가 금지를 명시한 건에 한해 센다.
        if G["says_port_forbidden"]:
            port_cases += 1
            if P["advises_port_turn"]:
                port_violation += 1
        # 조종을 아예 권고하지 않아도 위반율은 0 이 된다. 두 경우를 구분할 수
        # 있도록 조종을 권고한 비율을 함께 남긴다.
        if P["turn_dir"] is not None:
            advises_turn += 1

        stem = os.path.splitext(os.path.basename(r["image"]))[0]
        csv_path = os.path.join(image_dir, "csv", f"{stem}.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.lower()
            T = csv_truth(df)
            for k in num:
                num[k].append((T.get(k), P.get(k)))

    n = len(rows)
    enc_acc, enc_n = _acc(enc_pairs)
    role_acc, role_n = _acc(role_pairs)
    turn_acc, turn_n = _acc(turn_pairs)
    cnt_acc, cnt_n = _acc(count_pairs)

    # 조항을 하나도 인용하지 않은 모델은 정밀도가 0/0 이 된다. 그것을 None 으로
    # 두면 표에서 '측정 못 함'처럼 보이지만 실제로는 맞힌 것이 없다는 뜻이므로
    # 0 으로 적는다. 대조할 정답 조항 자체가 없을 때만 None 이다.
    if art_tp + art_fp + art_fn == 0:
        art_p = art_r = art_f = None
    else:
        art_p = 100 * art_tp / (art_tp + art_fp) if (art_tp + art_fp) else 0.0
        art_r = 100 * art_tp / (art_tp + art_fn) if (art_tp + art_fn) else 0.0
        art_f = (2 * art_p * art_r / (art_p + art_r)) if (art_p + art_r) else 0.0

    TOL = {"cpa": 0.05, "tcpa": 5.0, "own_course": 1.0,
           "own_speed": 0.1, "tgt_course": 1.0, "tgt_speed": 0.1}

    return {
        **hangul_stats([r["prediction"] for r in rows]),
        "multi_paragraph_pct": 100 * two_sec / n,
        "sds_format_pct": 100 * fmt_ok / n,
        "empty_pct": 100 * empty / n,
        "pred_len_median": st.median(lens),
        "pred_len_mean": sum(lens) / n,

        "encounter_acc": enc_acc, "encounter_n": enc_n,
        "role_acc": role_acc, "role_n": role_n,
        "turn_dir_acc": turn_acc, "turn_dir_n": turn_n,
        "vessel_count_vs_ref_acc": cnt_acc, "vessel_count_n": cnt_n,

        "colreg_precision": art_p,
        "colreg_recall": art_r,
        "colreg_f1": art_f,
        "colreg_tp": art_tp, "colreg_fp": art_fp, "colreg_fn": art_fn,

        "port_turn_violation_pct":
            100 * port_violation / port_cases if port_cases else None,
        "port_turn_cases": port_cases,
        "advises_turn_pct": 100 * advises_turn / n,

        "numeric": {k: _num_stats(v, TOL[k]) for k, v in num.items()},
        "numeric_tolerance": TOL,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser("생성 결과 채점")
    p.add_argument("--pred", required=True, help="generate.py 가 만든 JSONL")
    p.add_argument("--image_dir", required=True, help="csv/ 를 담은 데이터셋 루트")
    p.add_argument("--out", required=True)
    p.add_argument("--bertscore_model", default="klue/roberta-large")
    p.add_argument("--bertscore_batch", type=int, default=32)
    p.add_argument("--skip_bertscore", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    rows = [json.loads(l) for l in open(args.pred, encoding="utf-8")]
    preds = [r["prediction"] for r in rows]
    refs = [r["reference"] for r in rows]
    print(f"[Metrics] {len(rows):,}건  ({args.pred})", flush=True)

    result = {"pred_file": os.path.basename(args.pred), "n": len(rows)}

    print("[Metrics] 표면 지표 …", flush=True)
    result["surface"] = surface_metrics(preds, refs)

    if not args.skip_bertscore:
        print("[Metrics] BERTScore …", flush=True)
        result["semantic"] = bertscore_metric(
            preds, refs, args.bertscore_model, args.bertscore_batch)
    else:
        result["semantic"] = {}

    print("[Metrics] 내용 지표 …", flush=True)
    result["content"] = content_metrics(rows, args.image_dir)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[Metrics] → {args.out}", flush=True)


if __name__ == "__main__":
    main()
