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
    return f"# 평가 리포트 — {md_cell(title)}\n\n" + _table(("항목", "값"), rows)


def _filename(info: dict) -> str:
    stem = info.get("project_name") or info.get("run_name") or "평가"
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", str(stem)).strip("_") or "평가"
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
