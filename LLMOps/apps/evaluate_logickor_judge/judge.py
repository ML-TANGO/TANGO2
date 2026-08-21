"""LogicKor 심판 채점 — 미채점 생성물(jsonl) → 심판 점수가 박힌 evaluated jsonl.

ETRI `Evaluation/Logickor_web/logickor_eval/evaluator.py` 의 로직을 CLI 스크립트에서
함수로 재구성한 것이다. **프롬프트 구성과 점수 파싱은 원본과 글자 단위로 같게 유지한다** —
여기서 달라지면 우리 점수가 ETRI 재현값과 어긋나고, 그 차이를 사후에 추적할 방법이 없다.
심판 시스템 프롬프트(JUDGE_TEMPLATE)는 원본 templates.py 를 그대로 임포트해 쓴다(복제 금지).

vLLM 런타임 옵션은 import 전에 세팅해야 하므로 모듈 최상단에서 처리한다(원본 동일).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# vLLM runtime options (must be set before importing vllm) — 원본 evaluator.py 동일.
os.environ.setdefault("VLLM_USE_V1", "0")
os.environ.setdefault("CUDA_MODULE_LOADING", "EAGER")
os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")

from templates import JUDGE_TEMPLATE  # noqa: E402  (원본 파일을 그대로 사용)

# 심판 프리셋 — 원본은 llama 를 개발자 개인 경로(/home/parkjb/...)로 박아뒀다. 컨테이너에서
# 존재하지 않는 경로라 제거하고, 공개 HF repo id 만 남긴다. 프리셋에 없는 값은 그대로
# 통과시키므로(원본 resolve 규약 유지) 임의 HF id·로컬 경로도 쓸 수 있다.
JUDGE_MODEL_PRESETS = {
    "gemma": "google/gemma-4-E4B-it",
}
DEFAULT_JUDGE_MODEL = "gemma"


def resolve_judge_model(judge_model: str) -> str:
    """프리셋 이름이면 매핑, 아니면 그대로 통과(원본 동일 규약)."""
    return JUDGE_MODEL_PRESETS.get(judge_model, judge_model)


def create_judge(judge_model: str, gpu_devices: str, model_len: int):
    """심판 모델을 vLLM 으로 로드. (llm, SamplingParams) 반환."""
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices
    gpu_counts = len([g for g in gpu_devices.split(",") if g.strip()]) or 1

    from vllm import LLM, SamplingParams

    llm = LLM(
        model=judge_model,
        tensor_parallel_size=gpu_counts,
        max_model_len=model_len,
        gpu_memory_utilization=0.8,
        trust_remote_code=True,
        enforce_eager=True,
    )
    return llm, SamplingParams


def build_prompt(model_output: Dict[str, Any], is_multi_turn: bool) -> Tuple[str, str]:
    """(system, user) 메시지 구성 — 원본 evaluator.build_prompt 와 동일."""
    model_questions = model_output["questions"]
    model_outputs = model_output["outputs"]
    model_references = model_output["references"]

    prompt = (
        f"아래의 내용을 주어진 평가 기준들을 충실히 반영하여 평가해라. 특히 모델 답변이 언어 요구사항을 준수하는지 반드시 확인해야 한다.\n\n"
        f"**Question**\n{model_questions[0]}"
    )
    if model_references and model_references[0]:
        prompt += f"\n\n**Additional Reference**\n{model_references[0]}"
    prompt += f"\n\n**Model's Response**\n{model_outputs[0]}"

    if is_multi_turn:
        prompt += f"\n\n**Follow-up Question.**\n{model_questions[1]}"
        if model_references and model_references[1]:
            prompt += f"\n\n**Additional Reference**\n{model_references[1]}"
        prompt += f"\n\n**Model's Response**\n{model_outputs[1]}"

    prompt += "\n\n[[대화 종료. 평가 시작.]]"
    system_content = JUDGE_TEMPLATE["multi_turn" if is_multi_turn else "single_turn"]
    return system_content, prompt


def parse_judgement(content: Optional[str]) -> Dict[str, Any]:
    """심판 출력 텍스트 → {judge_message, judge_score} — 원본과 동일 정규식.

    점수를 못 찾으면 0 점 + 사유를 메시지에 남긴다(원본 동일). 0 점이 조용히 평균을
    끌어내리므로 호출부가 그 개수를 세어 로그로 노출한다.
    """
    if content is None:
        content = ""
    cleaned = content.replace("*", "")

    m = re.search(r"평가:(.*?)점수:", cleaned, re.DOTALL)
    judge_message = m.group(1).strip() if m else "No judge message found"

    sm = re.search(r"점수:\s*(\d+(\.\d+)?)", cleaned)
    if sm:
        judge_score = float(sm.group(1))
    else:
        judge_message = "Impossible to judge: no score found in response."
        judge_score = 0.0
    return {"judge_message": judge_message, "judge_score": judge_score}


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def list_inputs(input_root: str) -> List[Path]:
    """채점 대상 jsonl 목록(숨김 제외).

    ⚠️ 심볼릭 링크는 따라가지 않는다. 데이터셋 내용은 사용자가 올린 tar/zip 이라 신뢰할
    수 없고, 호출부의 루트 검증(_resolve_input_root)은 루트 자체만 본다. 링크가 남아 있으면
    마운트 밖 파일이 심판 프롬프트와 /output/evaluated 아티팩트로 흘러나갈 수 있다.
    scoring.resolve_paths 와 같은 규칙(os.walk followlinks=False + islink 거부 +
    realpath 재검증)을 쓴다 — 두 컨테이너의 입력 수집 규칙이 갈라지면 안 된다.
    """
    real_root = os.path.realpath(input_root)

    def within(path: str) -> bool:
        try:
            return os.path.commonpath([os.path.realpath(path), real_root]) == real_root
        except ValueError:
            return False

    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(input_root, followlinks=False):
        dirnames[:] = [d for d in dirnames
                       if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not within(full):
                continue
            p = Path(full)
            if not _is_hidden(p.relative_to(input_root)):
                found.append(p)
    return sorted(found)


def judge_file(llm, sampling_params, in_path: Path, out_path: Path) -> Dict[str, int]:
    """파일 1개 채점 → out_path 에 query_single/query_multi 를 붙여 기록.

    한 파일의 전 문항 × 2턴을 한 배치로 llm.chat 에 넘긴다(원본 동일) — 문항별로 나눠
    호출하면 vLLM 배치 이득이 사라져 42문항이 수십분으로 늘어난다.
    """
    # 깨진 행은 스킵한다 — CPU 집계기(scoring.iter_records)와 같은 방어 수준. 한 줄
    # 파싱 실패로 42문항×2턴 배치와 수십 분짜리 GPU 잡 전체를 날리면 안 된다.
    rows: List[Dict[str, Any]] = []
    skipped = 0
    with open(in_path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            # build_prompt 가 요구하는 최소 shape 검증(없으면 IndexError 로 배치 전체 소실).
            q, o = rec.get("questions"), rec.get("outputs")
            if not (isinstance(q, list) and isinstance(o, list)
                    and len(q) >= 2 and len(o) >= 2):
                skipped += 1
                continue
            rec.setdefault("references", [None, None])
            rows.append(rec)

    if not rows:
        raise ValueError(
            f"{in_path.name}: 채점 가능한 행이 없다(스킵 {skipped}) — questions/outputs "
            "각 2턴을 가진 generator 산출물이 필요하다")

    conversations = []
    meta: List[Tuple[int, str]] = []
    for idx, row in enumerate(rows):
        for turn_key, is_multi in (("single", False), ("multi", True)):
            system_content, user_content = build_prompt(row, is_multi)
            conversations.append([
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ])
            meta.append((idx, turn_key))

    outputs = llm.chat(conversations, sampling_params, use_tqdm=False)

    results: Dict[int, Dict[str, Dict]] = {}
    unscored = 0
    for (idx, turn_key), out in zip(meta, outputs):
        parsed = parse_judgement(out.outputs[0].text)
        if parsed["judge_score"] == 0.0:
            unscored += 1
        results.setdefault(idx, {})[turn_key] = parsed

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig") as fh:
        for idx, row in enumerate(rows):
            row["query_single"] = results[idx]["single"]
            row["query_multi"] = results[idx]["multi"]
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"rows": len(rows), "judged": len(meta), "unscored": unscored,
            "skipped": skipped}


def run_judge(input_root: str, output_root: str, judge_model: str = DEFAULT_JUDGE_MODEL,
              gpu_devices: str = "0", model_len: int = 8192,
              max_output_tokens: int = 1024,
              hf_token: Optional[str] = None,
              progress_cb: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
    """input_root 하위 jsonl 전부 채점 → output_root 에 같은 상대경로로 기록."""
    inputs = list_inputs(input_root)
    if not inputs:
        raise FileNotFoundError(f"no *.jsonl under {input_root}")

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    resolved = resolve_judge_model(judge_model)
    if progress_cb:
        progress_cb(0.05, f"loading judge model {resolved}")
    llm, SamplingParams = create_judge(resolved, gpu_devices, model_len)
    sampling_params = SamplingParams(temperature=0.0, max_tokens=max_output_tokens)

    in_root = Path(input_root)
    out_root = Path(output_root)
    stats = {"files": 0, "rows": 0, "judged": 0, "unscored": 0, "skipped": 0,
             "judge_model": resolved, "outputs": []}
    for i, path in enumerate(inputs, start=1):
        rel = path.relative_to(in_root)
        s = judge_file(llm, sampling_params, path, out_root / rel)
        stats["files"] += 1
        stats["rows"] += s["rows"]
        stats["judged"] += s["judged"]
        stats["unscored"] += s["unscored"]
        stats["skipped"] += s["skipped"]
        stats["outputs"].append(str(rel))
        if progress_cb:
            progress_cb(0.05 + 0.85 * i / len(inputs), f"judged {rel} ({i}/{len(inputs)})")
    return stats
