# -*- coding: utf-8 -*-
"""
ugen_data.py
------------
UGEN(Young1993/UGEN, COLING 2022)의 "Unified Generative QA" 패러다임을
Qwen3-8B(decoder-only causal LM)에 맞게 재구성한 공용 데이터 모듈.

원본 UGEN은 T5(encoder-decoder)로 intent/slot을 QA 문제로 풀었다.
- Q1 (intent) : "what are the intents of the sentence according to options?" + options
- Q5 (slot)   : "which words are the slot values ... List them with their slot names." + options
- A5 형식     : "value is one slotname,value is one slotname,..."

본 모듈은 위 프롬프트/정답 형식을 그대로 가져오되,
causal LM 학습/추론에 쓰기 좋도록 chat 메시지 형태로 변환한다.

데이터 포맷(MixATIS_clean / MixSNIPS_clean):
  <data_dir>/<split>/seq.in   : 토큰들이 공백으로 구분된 문장 1줄
  <data_dir>/<split>/seq.out  : seq.in과 같은 길이의 BIO 슬롯 태그 1줄
  <data_dir>/<split>/label    : '#'로 구분된 다중 intent 1줄
  <data_dir>/intent.json      : {intent_label: readable_name}
  <data_dir>/slot.json        : {slot_label: readable_name}
"""

import os
import json
from typing import List, Dict, Tuple

# ----- UGEN 원본과 동일한 질문 텍스트 ------------------------------------------
Q_INTENT = "question: what are the intents of the sentence according to options?"
Q_SLOT = ("question: which words are the slot values in the sentence? "
          "List them with their slot names.")

SYSTEM_PROMPT = (
    "You are a spoken-language-understanding assistant. "
    "Answer strictly in the requested format with no explanation."
)


def load_label_maps(data_dir: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """intent.json / slot.json 을 읽어 {label: readable_name} 두 딕셔너리를 반환."""
    with open(os.path.join(data_dir, "intent.json"), encoding="utf-8") as f:
        intent_map = json.load(f)
    with open(os.path.join(data_dir, "slot.json"), encoding="utf-8") as f:
        slot_map = json.load(f)
    return intent_map, slot_map


def read_split(data_dir: str, split: str) -> List[Dict]:
    """
    seq.in / seq.out / label 세 파일을 읽어
    [{"tokens": [...], "slots": [...], "intents": [...]}] 리스트로 반환.
    """
    base = os.path.join(data_dir, split)
    with open(os.path.join(base, "seq.in"), encoding="utf-8") as f:
        seq_in = [ln.strip() for ln in f if ln.strip() != ""]
    with open(os.path.join(base, "seq.out"), encoding="utf-8") as f:
        seq_out = [ln.strip() for ln in f if ln.strip() != ""]
    with open(os.path.join(base, "label"), encoding="utf-8") as f:
        labels = [ln.strip() for ln in f if ln.strip() != ""]

    assert len(seq_in) == len(seq_out) == len(labels), (
        f"split '{split}' 길이 불일치: "
        f"seq.in={len(seq_in)}, seq.out={len(seq_out)}, label={len(labels)}"
    )

    samples = []
    for text, tags, lab in zip(seq_in, seq_out, labels):
        tokens = text.split()
        slots = tags.split()
        intents = lab.split("#")  # 다중 intent
        if len(tokens) != len(slots):
            # 토큰/태그 길이가 어긋난 비정상 라인은 건너뜀
            continue
        samples.append({"tokens": tokens, "slots": slots, "intents": intents})
    return samples


def extract_slot_pairs(tokens: List[str], slots: List[str],
                       slot_map: Dict[str, str]) -> List[Tuple[str, str]]:
    """
    BIO 태그를 파싱해 (slot value, readable slot name) 쌍 리스트를 만든다.
    UGEN data_qa.py 의 슬롯 추출 로직과 동일한 규칙.
    """
    pairs = []
    i, n = 0, len(slots)
    while i < n:
        tag = slots[i]
        if tag != "O":
            slot_label = tag[2:]                      # 'B-xxx' -> 'xxx'
            readable = slot_map.get(slot_label, slot_label)
            j = i + 1
            # 같은 슬롯의 I- 태그를 이어 붙임
            while j < n and slots[j][0] != "B" and slots[j][2:] == slot_label:
                j += 1
            value = " ".join(tokens[i:j]).strip()
            pairs.append((value, readable))
            i = j
        else:
            i += 1
    return pairs


def gold_intents_readable(intents: List[str], intent_map: Dict[str, str]) -> List[str]:
    """intent 라벨 리스트를 readable 이름으로 변환 후 정렬(UGEN과 동일하게 sorted)."""
    return sorted(intent_map.get(it, it) for it in intents)


# ----- 프롬프트 / 정답 문자열 생성 --------------------------------------------
def build_intent_user(tokens: List[str], intent_map: Dict[str, str]) -> str:
    sentence = "sentence: " + " ".join(tokens)
    options = "options: " + ",".join(intent_map.values())
    return f"{sentence}\n{Q_INTENT}\n{options}"


def build_slot_user(tokens: List[str], slot_map: Dict[str, str]) -> str:
    sentence = "sentence: " + " ".join(tokens)
    options = "options: " + ",".join(sorted(slot_map.values()))
    return f"{sentence}\n{Q_SLOT}\n{options}"


def format_intent_answer(gold_intents: List[str]) -> str:
    """예: 'airport,city,quantity' (정렬·쉼표 결합)"""
    return ",".join(gold_intents)


def format_slot_answer(slot_pairs: List[Tuple[str, str]]) -> str:
    """예: 'california is one state name,la is one city name'"""
    return ",".join(f"{val} is one {name}" for val, name in slot_pairs)


# ----- 예측 문자열 파싱(추론 결과 -> 비교용 구조) ------------------------------
def parse_intent_answer(text: str) -> List[str]:
    """모델 출력 문자열을 intent 집합(정렬 리스트)으로 파싱."""
    text = text.strip()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    # 중복 제거 후 정렬 — UGEN intent_acc 는 정렬된 동일성 비교
    return sorted(set(parts))


def parse_slot_answer(text: str) -> List[Tuple[str, str]]:
    """
    'X is one Y' 패턴을 (value, slotname) 쌍으로 파싱.
    구분자는 쉼표. 'is one' 이 없는 항목은 무시.
    """
    pairs = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if " is one " in chunk:
            val, name = chunk.split(" is one ", 1)
            pairs.append((val.strip(), name.strip()))
    return pairs


# ----- chat 메시지 빌더 -------------------------------------------------------
def make_chat(user_content: str, answer: str = None) -> List[Dict[str, str]]:
    """
    학습용(answer 포함) 또는 추론용(answer=None) chat 메시지 생성.
    """
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    if answer is not None:
        msgs.append({"role": "assistant", "content": answer})
    return msgs


def build_training_examples(data_dir: str, split: str) -> List[Dict]:
    """
    한 발화당 2개의 SFT 예제(intent QA, slot QA)를 생성.
    반환: [{"messages": [...], "task": "intent"|"slot"}]
    """
    intent_map, slot_map = load_label_maps(data_dir)
    samples = read_split(data_dir, split)
    out = []
    for s in samples:
        tokens, slots, intents = s["tokens"], s["slots"], s["intents"]

        # intent QA
        gi = gold_intents_readable(intents, intent_map)
        out.append({
            "task": "intent",
            "messages": make_chat(build_intent_user(tokens, intent_map),
                                  format_intent_answer(gi)),
        })

        # slot QA
        pairs = extract_slot_pairs(tokens, slots, slot_map)
        out.append({
            "task": "slot",
            "messages": make_chat(build_slot_user(tokens, slot_map),
                                  format_slot_answer(pairs)),
        })
    return out


def build_eval_examples(data_dir: str, split: str = "test") -> List[Dict]:
    """
    평가용: 발화당 1개 항목(정답 intent 집합 + 정답 slot 쌍 + 두 프롬프트)을 생성.
    """
    intent_map, slot_map = load_label_maps(data_dir)
    samples = read_split(data_dir, split)
    out = []
    for s in samples:
        tokens, slots, intents = s["tokens"], s["slots"], s["intents"]
        gi = gold_intents_readable(intents, intent_map)
        pairs = extract_slot_pairs(tokens, slots, slot_map)
        out.append({
            "sentence": " ".join(tokens),
            "intent_messages": make_chat(build_intent_user(tokens, intent_map)),
            "slot_messages": make_chat(build_slot_user(tokens, slot_map)),
            "gold_intents": gi,                       # 정렬된 readable 리스트
            "gold_slots": [list(p) for p in pairs],   # [[value, name], ...]
        })
    return out


if __name__ == "__main__":
    # 간단한 동작 확인
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "../UGEN/data/MixATIS_clean"
    intent_map, slot_map = load_label_maps(d)
    print(f"intents={len(intent_map)}, slots={len(slot_map)}")
    tr = build_training_examples(d, "train")
    ev = build_eval_examples(d, "test")
    print(f"train SFT 예제 수={len(tr)}  (발화 {len(tr)//2}개 x 2)")
    print(f"test  발화 수={len(ev)}")
    print("\n[INTENT 학습 예제]")
    for m in tr[0]["messages"]:
        print(f"  {m['role']}: {m['content'][:120]}")
    print("\n[SLOT 학습 예제]")
    for m in tr[1]["messages"]:
        print(f"  {m['role']}: {m['content'][:160]}")
    print("\n[EVAL 예제 gold]")
    print("  gold_intents:", ev[0]["gold_intents"])
    print("  gold_slots  :", ev[0]["gold_slots"])
