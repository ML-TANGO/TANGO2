#!/usr/bin/env python3
"""Logickor_web 의 누락된 SFT 학습데이터를 부트스트랩한다.

configs/*.yaml 이 가리키는 `data/logickor_sft_high_converted.jsonl` 은 ETRI 가
few-shot 증강으로 만든 데이터로, .gitignore 의 `data/*` 규칙 때문에 저장소에
포함되어 있지 않다. 그래서 auto.sh 의 Step 1(train) 이 바로 실패한다.

여기서는 같은 저장소에 이미 들어있는 LogicKor 생성결과(generated/*.jsonl)를
학습 포맷으로 변환해 파이프라인이 끝까지 도는 부트스트랩 데이터를 만든다.
    - 소스: Evaluation/Logickor/generated/<run>/default.jsonl
            (evaluated/ 의 judge_score 평균이 가장 높은 default 프롬프트 실행분)
    - 출력: Logickor_web/data/logickor_sft_high_converted.jsonl

⚠️ 이건 "환경이 도는지"를 검증하기 위한 대체물이지 ETRI 정본 데이터가 아니다.
   정본 jsonl 을 받으면 같은 경로에 덮어쓰면 된다(스키마 동일).

출력 스키마는 train/dataloader.py:validate_rows 규약을 따른다.
    turn1: messages=[user(q1), assistant(a1)],                     meta={question_id, turn:1}
    turn2: messages=[user(q1), assistant(a1), user(q2), assistant(a2)], meta={question_id, turn:2}
    - question_id 는 정확히 2회(turn1/turn2) 등장해야 한다.
    - 마지막 메시지는 반드시 assistant 여야 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVE_DIR = Path(__file__).resolve().parent
EVAL_DIR = SERVE_DIR.parent
DEFAULT_SOURCE = EVAL_DIR / "Logickor" / "generated" / "Gemma4-e4b-it" / "step" / "v0" / "default.jsonl"
DEFAULT_OUTPUT = EVAL_DIR / "Logickor_web" / "data" / "logickor_sft_high_converted.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    # ETRI 산출물은 UTF-8 BOM 이 붙어 있다(dataloader 도 utf-8-sig 를 쓴다).
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno} JSON 파싱 실패: {exc}") from exc
    return rows


def to_sft_rows(src_rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    skipped: list[int] = []
    for row in src_rows:
        qid = row.get("id")
        questions = row.get("questions") or []
        outputs = row.get("outputs") or []
        # turn1/turn2 가 모두 있어야 question_id 가 정확히 2회 등장한다.
        if not isinstance(qid, int) or len(questions) < 2 or len(outputs) < 2:
            skipped.append(qid)
            continue
        q1, q2 = str(questions[0]).strip(), str(questions[1]).strip()
        a1, a2 = str(outputs[0]).strip(), str(outputs[1]).strip()
        if not (q1 and q2 and a1 and a2):
            skipped.append(qid)
            continue
        out.append({
            "messages": [
                {"role": "user", "content": q1},
                {"role": "assistant", "content": a1},
            ],
            "meta": {"question_id": qid, "turn": 1, "category": row.get("category")},
        })
        out.append({
            "messages": [
                {"role": "user", "content": q1},
                {"role": "assistant", "content": a1},
                {"role": "user", "content": q2},
                {"role": "assistant", "content": a2},
            ],
            "meta": {"question_id": qid, "turn": 2, "category": row.get("category")},
        })
    if skipped:
        print(f"[warn] turn1/turn2 가 온전치 않아 제외한 question_id: {skipped}", file=sys.stderr)
    return out


def validate(rows: list[dict]) -> dict:
    """train/dataloader.py:validate_rows 와 같은 불변식을 미리 검사한다."""
    if not rows:
        raise SystemExit("생성된 행이 없습니다.")
    per_qid: dict[int, int] = {}
    for idx, row in enumerate(rows):
        msgs = row["messages"]
        if len(msgs) < 2 or msgs[-1]["role"] != "assistant":
            raise SystemExit(f"row {idx}: 마지막 메시지가 assistant 가 아닙니다.")
        if row["meta"]["turn"] not in (1, 2):
            raise SystemExit(f"row {idx}: turn 이 1/2 가 아닙니다.")
        qid = row["meta"]["question_id"]
        per_qid[qid] = per_qid.get(qid, 0) + 1
    bad = [q for q, c in per_qid.items() if c != 2]
    if bad:
        raise SystemExit(f"question_id 가 정확히 2회가 아닌 항목: {bad[:10]}")
    return {"rows": len(rows), "question_ids": len(per_qid)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="LogicKor 생성결과 jsonl")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="출력 SFT jsonl")
    ap.add_argument("--force", action="store_true", help="이미 있으면 덮어쓴다")
    args = ap.parse_args()

    if args.output.exists() and not args.force:
        print(f"[skip] 이미 존재합니다: {args.output}  (덮어쓰려면 --force)")
        return
    if not args.source.exists():
        raise SystemExit(f"소스가 없습니다: {args.source}")

    rows = to_sft_rows(read_jsonl(args.source))
    stats = validate(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(args.output)  # 원자적 교체

    print(f"[ok] {args.output}")
    print(f"     source={args.source}")
    print(f"     rows={stats['rows']}  question_ids={stats['question_ids']}")


if __name__ == "__main__":
    main()
