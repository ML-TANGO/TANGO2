import json
import random
from typing import Any, Dict, List, Sequence, Tuple


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc
            rows.append(row)
    return rows


def validate_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        raise ValueError("Dataset is empty.")

    turns: Dict[int, int] = {}
    question_ids: Dict[int, int] = {}
    for idx, row in enumerate(rows):
        messages = row.get("messages")
        meta = row.get("meta", {})
        if not isinstance(messages, list) or len(messages) < 2:
            raise ValueError(f"Row {idx} has invalid messages.")
        if not isinstance(meta, dict):
            raise ValueError(f"Row {idx} has invalid meta.")

        question_id = meta.get("question_id")
        turn = meta.get("turn")
        if not isinstance(question_id, int):
            raise ValueError(f"Row {idx} missing integer meta.question_id.")
        if turn not in (1, 2):
            raise ValueError(f"Row {idx} has invalid meta.turn: {turn}")

        question_ids[question_id] = question_ids.get(question_id, 0) + 1
        turns[turn] = turns.get(turn, 0) + 1

        if messages[-1].get("role") != "assistant":
            raise ValueError(f"Row {idx} last message must be assistant.")

    invalid_group_sizes = [qid for qid, count in question_ids.items() if count != 2]
    if invalid_group_sizes:
        raise ValueError(
            "Each question_id must appear exactly twice (turn1/turn2). "
            f"Invalid question_ids: {invalid_group_sizes[:10]}"
        )

    return {
        "row_count": len(rows),
        "turn_counts": turns,
        "question_id_count": len(question_ids),
    }


def split_by_question_id(
    rows: Sequence[Dict[str, Any]],
    train_ratio: float,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    by_qid: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        qid = row["meta"]["question_id"]
        by_qid.setdefault(qid, []).append(row)

    question_ids = list(by_qid.keys())
    rng = random.Random(seed)
    rng.shuffle(question_ids)

    train_group_count = max(1, int(len(question_ids) * train_ratio))
    train_group_count = min(train_group_count, len(question_ids) - 1)

    train_qids = set(question_ids[:train_group_count])
    eval_qids = set(question_ids[train_group_count:])

    train_rows: List[Dict[str, Any]] = []
    eval_rows: List[Dict[str, Any]] = []
    for qid, group_rows in by_qid.items():
        if qid in train_qids:
            train_rows.extend(group_rows)
        else:
            eval_rows.extend(group_rows)

    overlap = train_qids.intersection(eval_qids)
    if overlap:
        raise RuntimeError(f"Group split leakage detected: {sorted(overlap)[:10]}")
    if not train_rows or not eval_rows:
        raise RuntimeError("Train/eval split must be non-empty.")

    stats = {
        "train_question_ids": len(train_qids),
        "eval_question_ids": len(eval_qids),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
    }
    return train_rows, eval_rows, stats
