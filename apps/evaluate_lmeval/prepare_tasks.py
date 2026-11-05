"""빌드 시점 준비 — 수정본 태스크 생성 + 데이터셋·지표 스크립트 적재 + 오프라인 재확인.

Dockerfile 이 두 번 부른다.
  python prepare_tasks.py fetch    # 네트워크 있음: drop_tango 생성, 전 태스크 데이터 적재
  python prepare_tasks.py verify   # HF_*_OFFLINE=1: 캐시만으로 전 태스크가 로드되는지

적재 위치는 HF_HOME(=/opt/lmeval/hf)이다. 런타임은 이것을 쓰기 가능한 /tmp 로 복사해 쓴다
(app._prepare_hf_cache). 문항 버전이 이미지 태그에 묶이는 것이 목적이다 — 잡 파드는
egress 가 막혀 있어(network.isolate) 런타임 다운로드가 원천적으로 불가능하다.

drop_tango — lm_eval 0.4.12 의 drop 은 `doc_to_target: "{{ answer|join(',')}}"` 가 원본
`answer` 구조체(dict)를 받아 **키 이름**('number,date,spans,worker_id,hit_id')을 정답으로
렌더한다. few-shot 예시가 그 문자열을 정답으로 보여 주니 모델이 그대로 베껴 EM·F1 이 0 이
된다(P0 실측). 채점(process_results)은 이미 올바른 `answers` 를 쓰므로 템플릿만
`answers[0]` 로 바꾸고, 소수("12.5")를 자르고 답 뒤 다음 지문까지 생성하게 두던 정지
시퀀스 "." 를 줄바꿈으로 바꾼다. 수정본 점수는 공개된 lm-eval DROP 수치와 비교할 수 없다.
"""
from __future__ import annotations

import os
import shutil
import sys

TASKS_DIR = os.environ.get("LMEVAL_TASKS_DIR", "/opt/lmeval/tasks")

_DROP_PATCHES = (
    ("task: drop\n", "task: drop_tango\n"),
    ("doc_to_target: \"{{ answer|join(',')}}\"", "doc_to_target: \"{{ answers[0]|join(', ') }}\""),
    ("generation_kwargs:\n  until:\n    - \".\"\n", "generation_kwargs:\n  until:\n    - \"\\n\"\n"),
)


def make_drop_tango() -> None:
    import lm_eval.tasks as T

    src = os.path.join(os.path.dirname(T.__file__), "drop")
    dst = os.path.join(TASKS_DIR, "drop_tango")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    path = os.path.join(dst, "default.yaml")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for old, new in _DROP_PATCHES:
        if old not in text:
            # upstream 이 바뀌었다 — 조용히 원본을 쓰면 DROP 이 다시 0 점이 된다.
            sys.exit(f"drop_tango: 패치 대상이 없다({old!r}) — lm_eval 버전을 확인하라")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"[prepare] {dst} 생성", flush=True)


def load_all() -> None:
    """레지스트리의 전 lm-eval 태스크를 로드한다(데이터셋 다운로드 또는 캐시 적중)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import evaluate
    import registry as REG
    from lm_eval.tasks import TaskManager, get_task_dict

    tm = TaskManager(include_path=TASKS_DIR)
    for bench in REG.BENCHMARKS.values():
        if bench.kind != "lmeval":
            continue
        tasks = get_task_dict(list(bench.tasks), tm)
        print(f"[prepare] {bench.id}: {len(tasks)} task(s) ok", flush=True)
    # 태스크 로드가 지표 스크립트를 부르지 않는 경로가 있어 명시적으로 적재한다.
    for metric in ("squad_v2", "code_eval"):
        evaluate.load(metric)
        print(f"[prepare] metric {metric} ok", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if mode == "fetch":
        make_drop_tango()
    load_all()
