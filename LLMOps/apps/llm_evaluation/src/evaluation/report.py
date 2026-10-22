"""평가 실행 1건 리포트(Markdown) — 요약 + 샘플별 상세.

리포트를 서버에서 만드는 이유: 샘플별 상세(LLM 심사 사유·의도/슬롯 오답·custom 벤치마크
문항)는 API 로 노출되지 않고 job 출력 파일(jobs/<job>/output)에만 있다. PDF 는 만들지 않는다 —
평가 이미지에 한글 폰트·PDF 라이브러리가 없어서, 화면이 이 Markdown 을 렌더해 브라우저
인쇄로 저장한다. 모델 출력·코멘트는 외부 입력이라 표 셀 이스케이프나 코드 블록으로만 싣는다
(문서 구조를 바꾸지 못하게).
"""
from __future__ import annotations

import asyncio
import csv
import heapq
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from utils.llm_db import db_model

from evaluation import service as svc
from evaluation.constants import BENCHMARK_EVAL_TYPE, EVAL_TYPE_LABELS

# 유형별 샘플 상한 — 실행 하나가 MixATIS 828문장처럼 클 수 있어 문서·파드 메모리(256M)를 지킨다.
SAMPLE_LIMIT = 100
# 텍스트 블록 하나의 상한 — 모델이 같은 말을 반복하며 길게 뽑은 출력이 문서를 덮지 않게.
TEXT_LIMIT = 4000
# 표 셀 하나의 상한 — 실패 사유·문장처럼 셀에 들어가는 값도 길 수 있다.
CELL_LIMIT = 1000
# 출력 파일 한 줄의 상한 — 넘는 줄은 읽지 않고 건너뛴다(파드 메모리 256M).
_MAX_LINE = 1024 * 1024
# 화면과 같은 시각으로 — DB 는 UTC 로 저장하고 화면은 9시간을 더해 보인다(addNineHours).
_KST = timezone(timedelta(hours=9))

_STATUS_LABELS = {"completed": "완료", "running": "진행 중", "failed": "실패",
                  "cancelled": "취소", "pending": "대기"}


# ── Markdown 안전 출력 ────────────────────────────────────────────────────────

def md_cell(value) -> str:
    """표 셀 값 — 줄바꿈은 공백으로, `\\` 와 `|` 는 이스케이프해 표 구조를 지킨다. 비면 '-'."""
    if value is None:
        return "-"
    text = re.sub(r"\s*[\r\n]+\s*", " ", str(value)).strip()
    if len(text) > CELL_LIMIT:
        text = text[:CELL_LIMIT] + "…"
    return text.replace("\\", "\\\\").replace("|", "\\|") or "-"


def md_fence(text) -> str:
    """긴 텍스트를 코드 블록으로 — 내용의 백틱보다 긴 펜스를 써서 블록을 닫지 못하게 한다."""
    body = _clip("" if text is None else str(text))
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{body}\n{fence}"


_CLIP_NOTE = re.compile(r"\n…\(이하 [\d,]+자 생략\)$")


def _clip(text: str, limit: int = TEXT_LIMIT) -> str:
    """상한을 넘는 텍스트를 자르고 생략 분량을 적는다. 이미 자른 텍스트는 그대로 둔다
    (파일을 읽을 때 한 번, 렌더할 때 한 번 불려도 생략 표시가 겹치지 않게)."""
    if len(text) <= limit or (len(text) <= limit + 40 and _CLIP_NOTE.search(text)):
        return text
    return f"{text[:limit]}\n…(이하 {len(text) - limit:,}자 생략)"


def _clip_value(value):
    """파일에서 읽은 행의 텍스트를 담기 전에 자른다 — 샘플을 모아 두는 동안 메모리를 지킨다."""
    if isinstance(value, str):
        return _clip(value)
    if isinstance(value, list):
        return [_clip_value(v) for v in value[:8]]
    if isinstance(value, dict):
        return {k: _clip_value(v) for k, v in value.items()}
    return value


def _num(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if value != 0 and abs(value) < 0.0001:
            return f"{value:.2e}"
        return f"{round(value, 4):.4f}".rstrip("0").rstrip(".")
    return md_cell(value)


def _kst(value) -> str:
    """DB 시각(UTC, 'YYYY-MM-DD HH:MM:SS') → KST 'YYYY-MM-DD HH:MM'. 못 읽으면 원문 그대로."""
    try:
        when = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return md_cell(value)
    return (when + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def _table(head: tuple, rows: list) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(cells) + " |" for cells in rows]
    return "\n".join(lines)


def meta_rows(meta) -> list:
    """설정·실행 정보 dict → (키, 값) 행. 스칼라만 싣고(중첩은 전용 표가 다룬다), 문자열의
    절대 경로는 가린다 — 채점기가 진단용으로 남긴 컨테이너·NFS 경로가 문서에 남지 않게."""
    rows = []
    if not isinstance(meta, dict):
        return rows
    for key, value in meta.items():
        if str(key).startswith("_") or isinstance(value, (dict, list)):
            continue
        if isinstance(value, str):
            value = svc._redact_paths(value)
        rows.append((str(key), _num(value)))
    return rows


def _meta_section(title: str, meta) -> str:
    rows = meta_rows(meta)
    if not rows:
        return ""
    return f"### {title}\n\n" + _table(("항목", "값"), [(md_cell(k), v) for k, v in rows])


# ── 출력 파일 읽기 ───────────────────────────────────────────────────────────

def _contained(output_dir: str, path: str) -> bool:
    base = os.path.realpath(output_dir)
    return os.path.commonpath([os.path.realpath(path), base]) == base


def _output_file(output_dir: str, name: str) -> Optional[str]:
    path = os.path.join(output_dir, name)
    return path if _contained(output_dir, path) and os.path.isfile(path) else None


def _iter_jsonl(path: str) -> Iterator[dict]:
    """한 줄씩 읽는다(파일 전체를 메모리에 올리지 않는다). 깨진 줄·_MAX_LINE 을 넘는 줄은
    건너뛰고, 깨진 바이트는 대체 문자로 읽는다 — 한 줄 때문에 리포트 전체가 실패하지 않게."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        while True:
            line = f.readline(_MAX_LINE + 1)
            if not line:
                break
            if len(line) > _MAX_LINE:
                while line and not line.endswith("\n"):   # 나머지를 버린다
                    line = f.readline(_MAX_LINE + 1)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _shown_note(total: int, shown: int, what: str) -> str:
    if total > shown:
        return f"{what} {total}건 중 {shown}건을 싣습니다."
    return f"{what} {total}건입니다."


# ── 요약 ─────────────────────────────────────────────────────────────────────

def render_benchmark_summary(metrics: dict, eval_type: str) -> str:
    """벤치마크 채점기(lm-eval·LogicKor·MixATIS)가 남긴 metrics.json → 지표 요약."""
    parts = ["## 지표 요약"]
    if metrics.get("mock"):
        parts.append("> ⚠️ mock 채점기가 낸 점수입니다 — 실제 성능 지표가 아닙니다.")
    results = [r for r in metrics.get("results") or [] if isinstance(r, dict)]
    if results:
        parts.append(_table(("벤치마크", "메트릭", "점수"), [
            (md_cell(r.get("benchmark")), md_cell(r.get("metric")), _num(r.get("score")))
            for r in results]))
    if eval_type == "judge":
        parts.append(_judge_summary(metrics))
    elif eval_type == "intent":
        parts.append(_intent_summary(metrics))
    else:
        parts.append(_reference_summary(metrics))
    return "\n\n".join(p for p in parts if p)


def _reference_summary(metrics: dict) -> str:
    parts = []
    lmeval = metrics.get("lmeval") if isinstance(metrics.get("lmeval"), dict) else {}
    for bench, info in (lmeval.get("benchmarks") or {}).items():
        if not isinstance(info, dict):
            continue
        parts.append(f"### {md_cell(bench)}\n\n"
                     f"few-shot {_num(info.get('num_fewshot'))} · 문항 수 {_num(info.get('n'))}")
        rows = [(md_cell(m.get("metric")), md_cell(m.get("filter")), _num(m.get("score")),
                 _num(m.get("stderr"))) for m in info.get("metrics") or [] if isinstance(m, dict)]
        if rows:
            parts.append(_table(("메트릭", "필터", "점수", "표준오차"), rows))
        rows = [(md_cell(s.get("task")), md_cell(s.get("metric")), _num(s.get("score")),
                 _num(s.get("stderr"))) for s in info.get("subtasks") or [] if isinstance(s, dict)]
        if rows:
            parts.append(_table(("하위 태스크", "메트릭", "점수", "표준오차"), rows))
    failed = [f for f in metrics.get("failed_benchmarks") or [] if isinstance(f, dict)]
    if failed:
        parts.append("### 채점 실패\n\n" + _table(("벤치마크", "메트릭", "사유"), [
            (md_cell(f.get("benchmark")), md_cell(f.get("metric")),
             md_cell(svc._redact_paths(str(f.get("error") or ""))))
            for f in failed]))
    parts.append(_meta_section("실행 설정", lmeval))
    parts.append(_meta_section("체크포인트", metrics.get("checkpoint")))
    return "\n\n".join(p for p in parts if p)


def _judge_summary(metrics: dict) -> str:
    parts = []
    lk = metrics.get("logickor") if isinstance(metrics.get("logickor"), dict) else {}
    rows = [(md_cell(c.get("category")), _num(c.get("single")), _num(c.get("multi")),
             _num(c.get("count"))) for c in lk.get("categories") or [] if isinstance(c, dict)]
    if rows:
        parts.append("### 카테고리별 점수\n\n" + _table(("카테고리", "싱글턴", "멀티턴", "문항 수"), rows))
    if lk:
        parts.append(_table(("항목", "값"), [
            ("싱글턴 평균", _num(lk.get("single_turn"))), ("멀티턴 평균", _num(lk.get("multi_turn"))),
            ("종합", _num(lk.get("overall"))), ("문항 수", _num(lk.get("count"))),
            ("만점", _num(lk.get("scale_max")))]))
    parts.append(_meta_section("심판", metrics.get("judge")))
    parts.append(_meta_section("답변 생성", metrics.get("generate")))
    return "\n\n".join(p for p in parts if p)


def _intent_summary(metrics: dict) -> str:
    parts = []
    mx = metrics.get("mixatis") if isinstance(metrics.get("mixatis"), dict) else {}
    if mx:
        intent = mx.get("intent") if isinstance(mx.get("intent"), dict) else {}
        slot = mx.get("slot") if isinstance(mx.get("slot"), dict) else {}
        parts.append("### 의도·슬롯 지표\n\n" + _table(
            ("구분", "Accuracy", "Precision", "Recall", "F1"), [
                ("의도", _num(intent.get("acc")), _num(intent.get("precision")),
                 _num(intent.get("recall")), _num(intent.get("f1"))),
                ("슬롯", "-", _num(slot.get("precision")), _num(slot.get("recall")),
                 _num(slot.get("f1")))]))
        parts.append(_table(("항목", "값"), [("Joint accuracy", _num(mx.get("joint_acc"))),
                                            ("문항 수", _num(mx.get("count")))]))
    parts.append(_meta_section("평가 설정", metrics.get("evaluate")))
    parts.append(_meta_section("학습", metrics.get("train")))
    parts.append(_meta_section("답변 생성", metrics.get("generate")))
    return "\n\n".join(p for p in parts if p)


# ── 샘플별 상세 ──────────────────────────────────────────────────────────────

def render_reference_samples(output_dir: str, limit: int = SAMPLE_LIMIT) -> str:
    """custom 벤치마크만 문항별 기록(custom_samples.jsonl)이 있다 — F1 낮은 순."""
    head = "## 샘플별 상세"
    path = _output_file(output_dir, "custom_samples.jsonl")
    if not path:
        return (f"{head}\n\n> 표준 벤치마크(lm-evaluation-harness)는 채점기가 문항별 결과를 저장하지 않아"
                " 문항별 상세가 없습니다. 위의 점수·하위 태스크가 이 실행이 남긴 결과 전부입니다.")
    total = 0

    def counted():
        nonlocal total
        for row in _iter_jsonl(path):
            total += 1
            yield _clip_value(row)

    def f1_of(row):
        f1 = row.get("f1")
        return f1 if isinstance(f1, (int, float)) and not isinstance(f1, bool) else 0.0

    rows = heapq.nsmallest(limit, counted(), key=f1_of)
    parts = [head, _shown_note(total, len(rows), "F1 이 낮은 순으로")]
    for n, row in enumerate(rows, 1):
        refs = row.get("references")
        refs = "\n---\n".join(str(r) for r in refs) if isinstance(refs, list) else refs
        parts.append(f"### {n}. 문항 #{_num(row.get('index'))} — F1 {_num(row.get('f1'))} · "
                     f"EM {_num(row.get('em'))}\n\n**입력**\n\n{md_fence(row.get('input'))}\n\n"
                     f"**모델 출력**\n\n{md_fence(row.get('prediction'))}\n\n"
                     f"**정답**\n\n{md_fence(refs)}")
    return "\n\n".join(parts)


def _judge_files(output_dir: str) -> list:
    base = os.path.join(output_dir, "evaluated")
    if not (_contained(output_dir, base) and os.path.isdir(base)):
        return []
    files = []
    for root, _dirs, names in os.walk(base):
        for name in names:
            path = os.path.join(root, name)
            if name.endswith(".jsonl") and _contained(output_dir, path) and os.path.isfile(path):
                files.append(path)
    return sorted(files)


def render_judge_samples(output_dir: str, limit: int = SAMPLE_LIMIT) -> str:
    """LogicKor 심사 기록(evaluated/**.jsonl) → 문항별 질문·답변·심판 점수와 사유(1·2턴)."""
    head = "## 샘플별 상세 — 문항별 심사"
    files = _judge_files(output_dir)
    if not files:
        return f"{head}\n\n> 문항별 심사 기록이 없습니다(채점이 끝나지 않았거나 기록을 남기지 않은 채점기)."
    rows, total = [], 0
    for path in files:
        label = os.path.relpath(path, os.path.join(output_dir, "evaluated"))
        for row in _iter_jsonl(path):
            total += 1
            if len(rows) < limit:
                rows.append((label, _clip_value(row)))
    parts = [head, _shown_note(total, len(rows), "전체")]
    for label, row in rows:
        single = row.get("query_single") if isinstance(row.get("query_single"), dict) else {}
        multi = row.get("query_multi") if isinstance(row.get("query_multi"), dict) else {}
        title = (f"### {_num(row.get('id'))}. {md_cell(row.get('category'))} — "
                 f"싱글턴 {_num(single.get('judge_score'))} · 멀티턴 {_num(multi.get('judge_score'))}")
        if len(files) > 1:
            title += f" ({md_cell(label)})"
        parts.append(title)
        questions, outputs, refs = (row.get(k) if isinstance(row.get(k), list) else []
                                    for k in ("questions", "outputs", "references"))
        for turn, query in enumerate((single, multi)):
            block = [f"#### {turn + 1}턴",
                     f"**질문**\n\n{md_fence(_at(questions, turn))}",
                     f"**답변**\n\n{md_fence(_at(outputs, turn))}"]
            if _at(refs, turn):
                block.append(f"**참고 답변**\n\n{md_fence(_at(refs, turn))}")
            block.append(f"**심사 사유 ({_num(query.get('judge_score'))}점)**\n\n"
                         f"{md_fence(query.get('judge_message'))}")
            parts.append("\n\n".join(block))
    return "\n\n".join(parts)


def _at(items: list, i: int):
    return items[i] if i < len(items) else None


def _labels(value) -> list:
    """';' 로 이은 의도·슬롯 → 정렬한 목록. 채점기 overall_acc 와 같은 비교(순서 무시, 중복은
    센다)라 여기서 센 오답 수가 joint_acc 와 맞는다."""
    return sorted(v.strip() for v in str(value or "").split(";") if v.strip())


def render_intent_samples(output_dir: str, limit: int = SAMPLE_LIMIT) -> str:
    """MixATIS 문장별 결과(mixatis_eval.csv) → 의도나 슬롯이 틀린 문장만."""
    head = "## 샘플별 상세 — 오답 사례"
    path = _output_file(output_dir, "mixatis_eval.csv")
    if not path:
        return f"{head}\n\n> 문장별 결과 파일이 없습니다(채점이 끝나지 않았거나 이전 채점기 결과)."
    rows, total, wrong, broken = [], 0, 0, False
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        try:
            for row in csv.DictReader(f):
                total += 1
                if (_labels(row.get("gold_intents")) == _labels(row.get("pred_intents"))
                        and _labels(row.get("gold_slots")) == _labels(row.get("pred_slots"))):
                    continue
                wrong += 1
                if len(rows) < limit:
                    rows.append(row)
        except csv.Error:
            broken = True   # 너무 긴 필드 등 — 읽은 데까지만 싣는다
    note = f"전체 {total}건 중 {wrong}건이 오답입니다." if wrong else f"전체 {total}건을 모두 맞혔습니다."
    if wrong > len(rows):
        note += f" 앞 {len(rows)}건만 싣습니다."
    if broken:
        note += " 파일 일부를 읽지 못해 그 앞까지만 셌습니다."
    if not wrong:
        return f"{head}\n\n{note}"
    table = _table(("#", "문장", "정답 의도", "예측 의도", "정답 슬롯", "예측 슬롯"), [
        (str(n), md_cell(r.get("sentence")), md_cell(r.get("gold_intents")),
         md_cell(r.get("pred_intents")), md_cell(r.get("gold_slots")), md_cell(r.get("pred_slots")))
        for n, r in enumerate(rows, 1)])
    return "\n\n".join([head, note, table])


def render_expert(samples_res: dict, result_res: dict, limit: int = SAMPLE_LIMIT) -> str:
    """전문가 검수 — 진행·평균·분포 요약 + 샘플별 입력·출력·점수·코멘트."""
    samples = [s for s in samples_res.get("samples") or [] if isinstance(s, dict)]
    total = samples_res.get("total") or len(samples)
    rated = result_res.get("rated") or 0
    avg, pass_rate = result_res.get("avg_score"), result_res.get("pass_rate")
    parts = ["## 지표 요약", _table(("항목", "값"), [
        ("채점 진행", f"{rated} / {total}"),
        ("평균 점수 (1~5)", "-" if avg is None else f"{avg:.2f}"),
        ("통과율 (O 판정)", "-" if pass_rate is None else f"{pass_rate:.2f}%")])]
    dist = result_res.get("distribution")
    if isinstance(dist, dict):
        keys = sorted(dist, key=lambda k: int(k) if str(k).isdigit() else 0)
        parts.append("### 점수 분포\n\n" + _table(
            ("점수", *keys), [("샘플 수", *(_num(dist[k]) for k in keys))]))
    if samples_res.get("expert_prompt"):
        parts.append(f"### 채점 기준\n\n{md_fence(samples_res['expert_prompt'])}")

    ratings = {r.get("sample_idx"): r for r in result_res.get("ratings") or [] if isinstance(r, dict)}
    shown = samples[:limit]
    parts += ["## 샘플별 상세", _shown_note(len(samples), len(shown), "전체")]
    for s in shown:
        idx = s.get("idx")
        r = ratings.get(idx)
        num = idx + 1 if isinstance(idx, int) else idx
        if r:
            title = (f"### 샘플 {_num(num)} — {_num(r.get('score'))}점 · 판정 {md_cell(r.get('verdict'))}"
                     f" · {md_cell(r.get('rater_user'))} ({_kst(r.get('create_datetime'))} KST)")
        else:
            title = f"### 샘플 {_num(num)} — 미채점"
        block = [title, f"**입력**\n\n{md_fence(s.get('input'))}",
                 f"**모델 출력**\n\n{md_fence(s.get('real_output') or s.get('output'))}"]
        if s.get("reference"):
            block.append(f"**참고 답변**\n\n{md_fence(s.get('reference'))}")
        if s.get("image"):
            # 원본 참조는 경로라 파일 이름만 싣는다(이미지는 플랫폼 화면에서 본다).
            block.append(f"**이미지** {md_cell(os.path.basename(str(s['image'])))}")
        if s.get("csv_rows"):
            block.append(f"> AIS 표({len(s['csv_rows'])}행)는 플랫폼 화면에서 확인하세요.")
        if r and r.get("comment"):
            block.append(f"**코멘트**\n\n{md_fence(r.get('comment'))}")
        parts.append("\n\n".join(block))
    return "\n\n".join(parts)


# ── 조립 ─────────────────────────────────────────────────────────────────────

async def _project_of(row: dict) -> Optional[dict]:
    """eval_result → 소속 프로젝트(get_eval_result_by_job 는 eval_project_id 를 싣지 않는다)."""
    try:
        rows = await db_model.list_eval_results_by_ids([row["id"]], row["workspace_id"])
        project_id = (rows or [{}])[0].get("eval_project_id")
        return await db_model.get_eval_project(project_id) if project_id else None
    except Exception:
        return None


def _eval_type_of(row: dict, project: Optional[dict]) -> str:
    if project and project.get("eval_type") in EVAL_TYPE_LABELS:
        return project["eval_type"]
    metric_set = str(row.get("metric_set") or "")
    if metric_set == "expert":
        return "expert"
    first = metric_set.split(",")[0].split(":")[0]
    return BENCHMARK_EVAL_TYPE.get(first, "reference")


def _source_label(metrics, model_name: str) -> str:
    checkpoint, mode, model, deployment = db_model._eval_run_source(metrics)
    if mode == "checkpoint":
        return f"체크포인트 {checkpoint}"
    if mode == "deployment":
        commit = db_model._eval_run_source_commit(metrics)
        label = f"배포 {deployment or '-'} (모델 {model or '-'}"
        return label + (f", 커밋 {commit})" if commit else ")")
    return f"모델 {model_name}"


def render_header(info: dict) -> str:
    title = info.get("project_name") or info.get("run_name") or info["job_id"]
    rows = [("평가 프로젝트", md_cell(info.get("project_name"))),
            ("평가 유형", EVAL_TYPE_LABELS.get(info["eval_type"], info["eval_type"])),
            ("실행", f"{md_cell(info.get('run_name') or info.get('metric_set'))} "
                   f"(`{md_cell(info['job_id'])}`)"),
            ("상태", _STATUS_LABELS.get(info.get("status"), md_cell(info.get("status")))),
            ("실행 시각 (KST)", _kst(info.get("create_datetime"))),
            ("평가 대상 모델", md_cell(info.get("model_name"))),
            ("출력 생성", md_cell(info.get("source"))),
            ("데이터셋", md_cell(info.get("dataset_name")))]
    if info.get("judge"):
        rows.append(("심판 모델", md_cell(info["judge"])))
    if info.get("sample_limit"):
        rows.append(("문항 상한", f"태스크당 앞 {info['sample_limit']}문항(빠른 확인)"))
    rows.append(("리포트 생성 (KST)", datetime.now(_KST).strftime("%Y-%m-%d %H:%M")))
    return f"# 평가 리포트 — {_heading(title)}\n\n" + _table(("항목", "값"), rows)


def _heading(value) -> str:
    """제목 줄에 넣을 이름 — 서식 문자(#·*·`·| 등)를 걷어내 제목이 깨지거나 꾸며지지 않게 한다."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return re.sub(r"[#*`|\\\[\]<>_~]", "", text)[:CELL_LIMIT].strip() or "-"


def _safe_stem(text) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(text or "")).strip("_") or "평가"


def _filename(info: dict) -> str:
    stem = _safe_stem(info.get("project_name") or info.get("run_name"))
    return f"평가리포트_{stem}_{info['job_id'][:8]}.md"


async def build_run_report(model_id: int, job_id: str) -> dict:
    """평가 실행 1건 → {markdown, filename}. 화면 미리보기와 .md 다운로드가 같은 텍스트를 쓴다."""
    if not job_id or not svc._JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    if not row:
        raise ValueError("평가 실행을 찾을 수 없습니다")
    project = await _project_of(row)
    model_name = (await db_model.get_model(model_id=model_id) or {}).get("name") or "-"
    eval_type = _eval_type_of(row, project)
    info = {"job_id": job_id, "eval_type": eval_type, "model_name": model_name,
            "project_name": (project or {}).get("name"), "dataset_name": row.get("dataset_name"),
            "metric_set": row.get("metric_set"), "create_datetime": row.get("create_datetime"),
            "status": row.get("status"), "source": f"모델 {model_name}"}

    if eval_type == "expert":
        samples = await svc.get_expert_samples(model_id=model_id, job_id=job_id)
        result = await svc.get_expert_result(model_id=model_id, job_id=job_id)
        info.update(run_name=samples.get("run_name"), status=result.get("status") or info["status"])
        body = render_expert(samples, result)
    else:
        res = await svc.get_eval_result(model_id=model_id, job_id=job_id)
        metrics = res.get("metrics") if res.get("ready") else None
        if metrics:
            judge_model, judge_deployment = db_model._eval_run_judge(metrics)
            info.update(status="completed", source=_source_label(metrics, model_name),
                        judge=judge_deployment or judge_model,
                        sample_limit=db_model._eval_run_sample_limit(metrics))
            output_dir = await svc._eval_output_dir(model_id, job_id)
            render_samples = {"judge": render_judge_samples,
                              "intent": render_intent_samples}.get(eval_type, render_reference_samples)
            # 파일 읽기는 이벤트 루프 밖에서 — 큰 결과 파일을 세는 동안 다른 요청을 막지 않게.
            samples = await asyncio.to_thread(render_samples, output_dir)
            body = render_benchmark_summary(metrics, eval_type) + "\n\n" + samples
        else:
            info["status"] = res.get("status") or info["status"]
            label = _STATUS_LABELS.get(info["status"], info["status"])
            if info["status"] in ("failed", "cancelled"):
                body = f"> 채점이 끝나지 못하고 {label}되어 결과가 없습니다."
            else:
                body = f"> 채점 결과가 아직 없습니다(상태: {label}). 채점이 끝난 뒤 다시 내보내세요."

    return {"markdown": render_header(info) + "\n\n" + body + "\n", "filename": _filename(info)}


# ── 프로젝트 리포트(실행 전체 요약) ───────────────────────────────────────────
# 실행 1건 리포트가 한 실행을 깊게 본다면, 이쪽은 프로젝트의 실행들을 한 표로 나란히 놓는다.
# 샘플별 상세는 싣지 않는다. 화면의 실행 목록·비교와 같은 출처(get_project 의 비교표)를 쓰고,
# 비교표가 평탄화하며 버린 유형별 세부(LLM 심사 싱글/멀티턴·카테고리, 의도/슬롯 F1, 전문가 채점
# 진행)는 eval_result.metrics 원본에서 읽는다.

PROJECT_RUN_LIMIT = 200


def _raw_metrics(row: dict) -> dict:
    m = row.get("metrics")
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except ValueError:
            m = None
    if not isinstance(m, dict):
        return {}
    m.pop("_samples", None)   # 전문가 샘플 원문 — 요약에 쓰지 않는다
    return m


def _run_label(run: dict) -> str:
    """실행 이름 — 전문가 세션은 제목, 벤치마크 런은 벤치마크 id 목록. 같은 이름이 여럿일 수 있어
    job id 앞 8자를 함께 붙인다."""
    name = run.get("run_name")
    if not name:
        benches = [s.split(":")[0] for s in str(run.get("metric_set") or "").split(",") if s]
        name = ", ".join(dict.fromkeys(benches)) or "-"
    name = str(name).replace("`", "'")
    return f"{md_cell(name)} (`{md_cell(str(run.get('job_id') or '')[:8])}`)"


def _run_source(run: dict) -> str:
    model = run.get("model_name") or "-"
    if run.get("source_mode") == "checkpoint":
        return md_cell(f"{model} · 체크포인트 {run.get('checkpoint')}")
    if run.get("source_mode") == "deployment":
        label = f"배포 {run.get('source_deployment') or '-'} · 모델 {run.get('source_model') or '-'}"
        if run.get("source_commit"):
            label += f" · 커밋 {run['source_commit']}"
        return md_cell(label)
    return md_cell(model)


def _dig(data, *keys):
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data


def _expert_progress(run: dict, raw: dict) -> Optional[str]:
    if run.get("status") == "completed" and raw.get("_total"):
        return f"{raw.get('_rated', raw['_total'])} / {raw['_total']}"
    prog = run.get("expert_progress")
    if isinstance(prog, dict) and prog.get("total"):
        return f"{prog.get('rated', 0)} / {prog['total']}"
    return None


def _pct(value) -> Optional[str]:
    try:
        return None if value is None else f"{_num(float(value))}%"
    except (TypeError, ValueError):
        return None


# 정답 대조 표의 지표 열 상한 — lm-eval 프로젝트는 태스크가 수십 개라 표가 읽히지 않는다.
# 넘치는 지표는 '지표별 최고 실행'에서 본다.
PROJECT_METRIC_COLUMNS = 8


def _main_metric(run: dict, raw: dict, key: str, *path):
    """비교표 대표 점수(벤치마크 키) — 없으면 metrics 원본에서."""
    value = run["metrics"].get(key)
    return value if value is not None else _dig(raw, *path)


def _project_columns(eval_type: str, metric_keys: list) -> list:
    """유형별 지표 열 — (제목, 값 함수(run, raw), 최고 표시에 쓸 비교표 지표 키).
    비교표 지표 키는 벤치마크 id 라, 심사·의도 유형의 대표 점수는 고정 키(logickor·mixatis)다 —
    metric_keys 는 정렬돼 있어 첫 키가 대표라는 보장이 없다."""
    if eval_type == "judge":
        return [("종합", lambda r, m: _main_metric(r, m, "logickor", "logickor", "overall"), "logickor"),
                ("싱글턴", lambda r, m: _dig(m, "logickor", "single_turn"), None),
                ("멀티턴", lambda r, m: _dig(m, "logickor", "multi_turn"), None),
                ("심판", lambda r, m: r.get("judge_deployment") or r.get("judge_model"), None)]
    if eval_type == "intent":
        return [("Joint acc", lambda r, m: _main_metric(r, m, "mixatis", "mixatis", "joint_acc"), "mixatis"),
                ("의도 Acc", lambda r, m: _dig(m, "mixatis", "intent", "acc"), None),
                ("의도 F1", lambda r, m: _dig(m, "mixatis", "intent", "f1"), None),
                ("슬롯 F1", lambda r, m: _dig(m, "mixatis", "slot", "f1"), None)]
    if eval_type == "expert":
        return [("채점 진행", _expert_progress, None),
                ("평균 점수 (1~5)", lambda r, m: r["metrics"].get("expert_avg_score")
                 if r["metrics"].get("expert_avg_score") is not None
                 else _dig(r, "expert_progress", "avg_score"), "expert_avg_score"),
                ("통과율", lambda r, m: _pct(r["metrics"].get("expert_pass_rate")), "expert_pass_rate")]
    return [(md_cell(key), (lambda k: lambda r, m: r["metrics"].get(k))(key), key)
            for key in metric_keys[:PROJECT_METRIC_COLUMNS]]


def _summary_table(eval_type: str, runs: list, raw_by_job: dict, metric_keys: list,
                   best: dict) -> str:
    columns = _project_columns(eval_type, metric_keys)
    head = ("#", "실행", "평가 대상", "데이터셋", "상태", "실행 시각 (KST)", *(c[0] for c in columns))
    rows = []
    for n, run in enumerate(runs, 1):
        raw = raw_by_job.get(run.get("job_id"), {})
        cells = []
        for _title, get, best_key in columns:
            value = get(run, raw)
            if value is None:
                cell = "-"
            elif isinstance(value, str):
                cell = md_cell(value)
            else:
                cell = _num(value)
            if value is not None and best_key and best.get(best_key) == run.get("id"):
                cell += " ★"
            cells.append(cell)
        rows.append((str(n), _run_label(run), _run_source(run), md_cell(run.get("dataset_name")),
                     _STATUS_LABELS.get(run.get("status"), md_cell(run.get("status"))),
                     _kst(run.get("create_datetime")), *cells))
    return _table(head, rows)


def _best_section(runs: list, best: dict) -> str:
    index = {run.get("id"): (n, run) for n, run in enumerate(runs, 1)}
    rows = []
    for key, run_id in sorted(best.items()):
        if run_id not in index:
            continue
        n, run = index[run_id]
        rows.append((md_cell(key), f"#{n} {_run_label(run)}", _num(run["metrics"].get(key))))
    if not rows:
        return ""
    return "## 지표별 최고 실행\n\n" + _table(("지표", "실행", "점수"), rows)


def _hidden_metrics_section(runs: list, hidden: list) -> str:
    """요약 표에 못 실은 지표 — (실행 × 지표) 긴 표. 최고 기록이 없는 지표(실패·mock·빠른 확인
    런에만 있는 지표)도 여기서는 빠지지 않는다."""
    rows = [(f"#{n}", md_cell(key), _num(run["metrics"].get(key)))
            for n, run in enumerate(runs, 1) for key in hidden
            if run["metrics"].get(key) is not None]
    if not rows:
        return ""
    return "## 나머지 지표\n\n" + _table(("#", "지표", "점수"), rows)


def _judge_category_section(runs: list, raw_by_job: dict) -> str:
    """카테고리 × 실행 — 셀은 '싱글턴 / 멀티턴'. 어느 영역에서 차이가 나는지 한눈에 본다."""
    cols, order, cells = [], [], {}
    for n, run in enumerate(runs, 1):
        cats = _dig(raw_by_job.get(run.get("job_id"), {}), "logickor", "categories")
        if run.get("status") != "completed" or not isinstance(cats, list):
            continue
        cols.append(f"#{n}")
        for c in cats:
            if not isinstance(c, dict):
                continue
            name = md_cell(c.get("category"))
            if name not in order:
                order.append(name)
            cells[(name, f"#{n}")] = f"{_num(c.get('single'))} / {_num(c.get('multi'))}"
    if not cols:
        return ""
    rows = [(name, *(cells.get((name, col), "-") for col in cols)) for name in order]
    return ("## 카테고리별 점수 (싱글턴 / 멀티턴)\n\n"
            + _table(("카테고리", *cols), rows))


def _run_subject(run: dict) -> tuple:
    """무엇이 이 점수를 냈나 — 위임 런은 배포·서빙 모델, 그 외(체크포인트 포함)는 모델."""
    if run.get("source_mode") == "deployment":
        return ("deployment", run.get("source_deployment"), run.get("source_model"))
    return ("model", run.get("model_name"))


def _project_notes(runs: list, skipped_inference: int, truncated: int,
                   hidden_metrics: list, dropped_best: int) -> str:
    notes = []
    mock = [f"#{n}" for n, r in enumerate(runs, 1) if r.get("mock")]
    if mock:
        notes.append(f"mock 채점기 런({', '.join(mock)})은 실제 점수가 아니라 최고 기록·비교에서 뺐습니다.")
    quick = [f"#{n}" for n, r in enumerate(runs, 1) if r.get("sample_limit")]
    if quick:
        notes.append(f"빠른 확인 런({', '.join(quick)})은 태스크당 앞 일부 문항만 채점해 최고 기록·비교에서 뺐습니다.")
    models = {_run_subject(r) for r in runs}
    datasets = {r.get("dataset_name") for r in runs if r.get("dataset_name")}
    mixed = [what for what, values in (("모델", models), ("데이터셋", datasets)) if len(values) > 1]
    if mixed:
        notes.append(f"이 프로젝트의 실행에는 서로 다른 {'·'.join(mixed)}이 섞여 있습니다 — 점수를 나란히 볼 때 유의하세요.")
    if hidden_metrics:
        notes.append(f"지표가 많아 요약 표에는 앞 {PROJECT_METRIC_COLUMNS}개만 실었습니다 — 나머지 "
                     f"{len(hidden_metrics)}개({', '.join(hidden_metrics[:10])}"
                     f"{' 등' if len(hidden_metrics) > 10 else ''})는 '나머지 지표' 표에 있습니다.")
    if dropped_best:
        notes.append(f"최고 기록 {dropped_best}건은 싣지 않은 오래된 실행에 있어 '지표별 최고 실행'에서 뺐습니다.")
    if skipped_inference:
        notes.append(f"채점이 아닌 추론 생성 런 {skipped_inference}건은 요약에서 뺐습니다.")
    if truncated:
        notes.append(f"실행이 많아 오래된 {truncated}건은 싣지 않았습니다(최근 {PROJECT_RUN_LIMIT}건).")
    if not notes:
        return ""
    return "## 참고\n\n" + "\n".join(f"- {md_cell(n)}" for n in notes)


async def build_project_report(project_id: int) -> dict:
    """평가 프로젝트 → {markdown, filename}. 실행 1건 리포트와 같은 응답 모양(같은 모달이 쓴다)."""
    data = await svc.get_project(project_id=project_id)
    project = data.get("project") or {}
    comparison = data.get("runs") or {}
    eval_type = project.get("eval_type") if project.get("eval_type") in EVAL_TYPE_LABELS else "reference"
    metric_keys = list(comparison.get("metric_keys") or [])
    best = comparison.get("best") or {}

    all_runs = [r for r in comparison.get("runs") or [] if isinstance(r, dict)]
    scored = sorted((r for r in all_runs if r.get("metric_set") != "inference"),
                    key=lambda r: r.get("id") or 0)
    skipped_inference = len(all_runs) - len(scored)
    truncated = max(0, len(scored) - PROJECT_RUN_LIMIT)
    runs = scored[-PROJECT_RUN_LIMIT:]
    # 원본 metrics 는 **보여 줄 실행만** 읽는다 — get_project 가 이미 전체를 한 번 읽었고, 오래된
    # 전문가 세션은 샘플 원문을 metrics 에 담고 있어 프로젝트 전체를 다시 읽으면 무겁다.
    ids = [r["id"] for r in runs if r.get("id") is not None]
    rows = (await db_model.list_eval_results_by_ids(ids, int(project.get("workspace_id") or 0))
            if ids else [])
    raw_by_job = {r.get("job_str_id"): _raw_metrics(r) for r in rows or []}

    counts = {}
    for r in runs:
        counts[r.get("status")] = counts.get(r.get("status"), 0) + 1
    count_text = " · ".join(f"{_STATUS_LABELS.get(s, md_cell(s))} {c}" for s, c in counts.items()) or "0"
    header = (f"# 평가 프로젝트 리포트 — {_heading(project.get('name'))}\n\n" + _table(("항목", "값"), [
        ("평가 프로젝트", md_cell(project.get("name"))),
        ("평가 유형", EVAL_TYPE_LABELS.get(eval_type, eval_type)),
        ("설명", md_cell(project.get("description"))),
        ("생성자", md_cell(project.get("creator"))),
        ("생성일 (KST)", _kst(project.get("create_datetime"))),
        ("상태", _STATUS_LABELS.get(project.get("status"), md_cell(project.get("status")))),
        ("실행", f"{len(runs)}건 ({count_text})"),
        ("리포트 생성 (KST)", datetime.now(_KST).strftime("%Y-%m-%d %H:%M"))]))

    parts = [header, "## 실행 요약"]
    if runs:
        parts.append("★ 는 지표별 최고 기록입니다(완료·실측·전체 측정 런 중).")
        parts.append(_summary_table(eval_type, runs, raw_by_job, metric_keys, best))
    else:
        parts.append("> 아직 실행이 없습니다.")
    hidden = metric_keys[PROJECT_METRIC_COLUMNS:] if eval_type == "reference" else []
    parts.append(_best_section(runs, best))
    parts.append(_hidden_metrics_section(runs, hidden))
    if eval_type == "judge":
        parts.append(_judge_category_section(runs, raw_by_job))
    included = {r.get("id") for r in runs}
    dropped = sum(1 for run_id in best.values() if run_id not in included)
    parts.append(_project_notes(runs, skipped_inference, truncated, hidden, dropped))
    markdown = "\n\n".join(p for p in parts if p) + "\n"
    return {"markdown": markdown,
            "filename": f"평가프로젝트리포트_{_safe_stem(project.get('name'))}.md"}
