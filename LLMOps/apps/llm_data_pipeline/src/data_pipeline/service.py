"""llm_data_pipeline 서비스 계층.

DB 접근은 utils.llm_db.db_data_pipeline 에 맡기고, 여기서는 화면이 필요로 하는
"판정"을 만든다 — 노드 경고, 유형별 판정, 통과율 범위, 학습 형식 검사 결과처럼
사람이 다음에 뭘 해야 하는지 알려주는 값들.
"""
import asyncio
import hashlib
import json
import logging
import math
import os
import shutil
import time
import uuid
from datetime import datetime

import aiohttp

from utils import TYPE
from utils.llm_db import db_data_pipeline as db

from data_pipeline.constants import (
    CAPABILITIES,
    COORD_REMAP_STEP,
    DATASET_STATE_LABEL,
    DEFAULT_MAX_REGENERATE,
    DEFAULT_SPLIT,
    DEFAULT_SPLIT_BY,
    DIRECTIONAL_STEPS,
    FILTER_LIBRARY,
    GENERATION_MODELS,
    GENERATION_TEMPLATES,
    GEOMETRIC_STEPS,
    HARD_NEGATIVE_MAX_PCT,
    PASS_RATE_RANGE,
    PREPROCESS_LIBRARY,
    PRESET_AXES,
    PRESET_GENERIC,
    PRESET_META,
    PRESET_SDS_COLREG,
    PRESET_THRESHOLDS,
    PROMPT_CHIPS,
    SDS_AIS_CLEAN_LIBRARY,
    SDS_AIS_LIBRARY,
    SDS_AIS_SCENE_LIBRARY,
    SDS_COLREG_LIBRARY,
    SDS_JOIN_LIBRARY,
    SDS_VIDEO_LIBRARY,
    SELECTABLE_MODELS,
    SPLIT_BY,
    SPLITS,
    STAGES,
    TAXONOMY,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    TRAIN_FORMATS,
    axes_for,
    prompt_for,
    stages_for,
    thresholds_for,
)

# 단계 → 그 단계를 담당하는 노드 kind. 생성은 프리셋마다 이름이 다르다
# (범용은 'synth', 해양은 'gen') — 하나만 보면 SDS 설정이 저장되지 않는다.
STAGE_NODE_KINDS = {
    # 실행은 없지만 설정(sources)을 담는 노드. 이것이 없으면 저장 요청이 노드를 못 찾는다.
    "data": ("data",),
    "preprocess": ("prep",),
    "filter": ("filter",),
    "generate": ("synth", "gen"),
    "gate": ("gate",),
    "sds_video": ("src",),
    "sds_ais": ("src",),
    # AIS 행 정제는 필터, 씬 구조화는 전처리 종류다 — 영상 갈래와 kind 가 겹치므로
    # 아래 STAGE_NODE_PICK 이 이름으로 가른다.
    "sds_ais_clean": ("filter",),
    "sds_ais_scene": ("prep",),
    "sds_join": ("join",),
    "sds_colreg": ("calc",),
    # 조립·내보내기. 프리셋과 무관하게 파이프라인의 마지막 노드다.
    "assemble": ("out",),
}

# kind 만으로 못 가리는 단계: (이름 후보, 같은 kind 안에서의 순번).
# 해양 프리셋은 원천 노드가 둘 다 kind='src' 라, 이름을 보지 않으면 항해 영상 단계가
# AIS 노드를 집어 든다. 사용자가 이름을 바꿨을 때는 순번으로 되짚는다 — 이름만 보면
# 개명 즉시 단계가 죽고, 순번만 보면 노드를 재배열했을 때 조용히 엉뚱한 노드를 문다.
STAGE_NODE_PICK = {
    "sds_video": (("항해 영상",), 0),
    "sds_ais": (("AIS 로그",), 1),
    # prep·filter 는 갈래마다 하나씩 있다. 이름을 먼저 보고, 이름을 바꿨으면 순번으로
    # 되짚는다. 범용 프리셋의 '전처리'·'필터' 도 같은 목록에 넣어 pick 하나로 처리한다.
    "preprocess": (("전처리 · 영상", "전처리"), 0),
    "filter": (("필터 · 영상", "필터"), 0),
    # 옛 이름('전처리 · AIS'·'필터 · AIS')도 받는다 — 그 이름으로 저장된 파이프라인이
    # 이미 있고, 인덱스를 다시 매기면 실행 이력이 어긋난다.
    "sds_ais_clean": (("AIS 행 정제", "필터 · AIS"), 1),
    "sds_ais_scene": (("AIS 씬 구조화", "전처리 · AIS"), 1),
}


def _find_stage_node(nodes, stage):
    cands = [n for n in nodes if n.get("kind") in STAGE_NODE_KINDS[stage]]
    if not cands:
        return None
    pick = STAGE_NODE_PICK.get(stage)
    if not pick:
        return cands[0]
    names, ordinal = pick
    named = [n for n in cands if n.get("name") in names]
    if named:
        return named[0]
    return cands[ordinal] if ordinal < len(cands) else None


class NotFound(Exception):
    """호출부가 404 로 바꿀 수 있게 구분해서 던진다."""


class Conflict(Exception):
    """이미 있는 것을 또 만들려 할 때. 덮어쓰지 않고 거부한다."""


# ── 메타 ────────────────────────────────────────────────────────────────────
def get_meta():
    """화면이 쓰는 상수 묶음. FE 가 같은 값을 따로 하드코딩하지 않게 서버가 내려준다."""
    return {
        # 축은 프리셋마다 다르므로 프리셋별로 내려준다. 하나만 내려주면 FE 가 SDS
        # 데이터셋에도 범용 축 라벨을 붙이게 된다.
        "gate_axes": {p: [dict(a) for a in ax] for p, ax in PRESET_AXES.items()},
        "default_thresholds": {p: dict(t) for p, t in PRESET_THRESHOLDS.items()},
        "threshold_range": [THRESHOLD_MIN, THRESHOLD_MAX],
        "default_max_regenerate": DEFAULT_MAX_REGENERATE,
        "pass_rate_range": list(PASS_RATE_RANGE),
        "taxonomy": list(TAXONOMY),
        "capabilities": list(CAPABILITIES),
        "presets": [{"key": k, **v} for k, v in PRESET_META.items()],
        "stages": list(STAGES),
        # 프리셋마다 쓸 수 있는 단계가 다르다. 하나로 내려주면 범용 파이프라인에도
        # 항해 영상 단계가 떠서 사용자가 못 쓰는 진입점을 계속 마주하게 된다.
        "stages_by_preset": {p: list(stages_for(p)) for p in PRESET_META},
        "preprocess_library": [dict(s) for s in PREPROCESS_LIBRARY],
        "filter_library": [dict(s) for s in FILTER_LIBRARY],
        # 이미지를 못 받는 모델은 후보에서 뺀다 — 고르면 배포는 되고 추론만
        # 전량 실패해서 원인이 화면에 드러나지 않는다.
        "generation_models": [dict(m) for m in SELECTABLE_MODELS],
        "generation_templates": [dict(t) for t in GENERATION_TEMPLATES],
        "prompt_chips": [dict(c) for c in PROMPT_CHIPS],
        # 기본 프롬프트도 프리셋마다 다르다. 하나만 내려주면 해양 파이프라인에도
        # 범용 VQA 프롬프트가 프리필돼 생성이 형식을 어긴다.
        "default_prompt_by_preset": {p: prompt_for(p) for p in PRESET_META},
        "hard_negative_max_pct": HARD_NEGATIVE_MAX_PCT,
        "splits": list(SPLITS),
        "default_split": dict(DEFAULT_SPLIT),
        "split_by": list(SPLIT_BY),
        "default_split_by": DEFAULT_SPLIT_BY,
        "train_formats": list(TRAIN_FORMATS),
        "dataset_state_label": dict(DATASET_STATE_LABEL),
        "geometric_steps": list(GEOMETRIC_STEPS),
        "directional_steps": list(DIRECTIONAL_STEPS),
        "coord_remap_step": COORD_REMAP_STEP,
    }


# ── 데이터셋 ────────────────────────────────────────────────────────────────
def _pass_rate_flag(pass_rate):
    """통과율이 정상 범위 밖인지. 낮으면 생성이 나쁘고, 높으면 게이트가 헐겁다."""
    if pass_rate is None:
        return None
    lo, hi = PASS_RATE_RANGE
    return "out_of_range" if (pass_rate < lo or pass_rate > hi) else "normal"


async def list_datasets(workspace_id):
    rows = await db.list_datasets(workspace_id=workspace_id) or []
    for r in rows:
        r["state_label"] = DATASET_STATE_LABEL.get(r.get("state"), r.get("state"))
        r["pass_rate_flag"] = _pass_rate_flag(r.get("latest_pass_rate"))
    return {
        "workspace_id": workspace_id,
        "pass_rate_range": list(PASS_RATE_RANGE),
        "datasets": rows,
        "unreviewed_total": sum((r.get("unreviewed_count") or 0) for r in rows),
    }


async def get_dataset(dataset_id):
    row = await db.get_dataset(dataset_id)
    if not row:
        raise NotFound(f"dataset not found: {dataset_id}")
    row["state_label"] = DATASET_STATE_LABEL.get(row.get("state"), row.get("state"))
    row["preset_meta"] = PRESET_META.get(row.get("preset"), {})
    return row


async def create_dataset(workspace_id, name, description, preset, create_user):
    # UNIQUE 위반을 드라이버까지 보내면 에러 메시지에 테이블·제약조건명이 실려 나간다.
    if await db.dataset_name_exists(workspace_id, name):
        raise Conflict(f"이미 있는 데이터셋 이름입니다: {name}")
    dataset_id = await db.create_dataset(
        workspace_id=workspace_id, name=name, description=description,
        preset=preset, create_user=create_user)
    # 새 데이터셋은 프리셋 기본 노드 체인을 갖고 시작한다. 빈 캔버스를 주면
    # 사용자가 무엇부터 놓아야 하는지 알 수 없다.
    await db.replace_flow(dataset_id, preset, default_nodes(preset))
    return await get_dataset(dataset_id)


async def update_dataset(dataset_id, name, description, state):
    await get_dataset(dataset_id)  # 없으면 여기서 NotFound
    await db.update_dataset(dataset_id, name=name, description=description, state=state)
    return await get_dataset(dataset_id)


async def delete_dataset(dataset_id):
    await get_dataset(dataset_id)
    await db.delete_dataset(dataset_id)
    return {"dataset_id": dataset_id, "deleted": True}


# ── 업로드(asset) ───────────────────────────────────────────────────────────
async def get_assets(dataset_id, limit=100, offset=0):
    await get_dataset(dataset_id)
    summary = await db.get_asset_summary(dataset_id) or {}
    failures = await db.get_asset_failures(dataset_id) or []
    assets = await db.list_assets(dataset_id, limit=limit, offset=offset) or []

    # 실패는 사유별로 묶어서 보여준다. 같은 사유 수십 건을 나열해도 정보가 늘지 않는다.
    if failures:
        failed_rows = await db.list_assets(dataset_id, status="failed", limit=500) or []
        for f in failures:
            f["paths"] = [a["path"] for a in failed_rows
                          if a.get("fail_reason") == f.get("reason")][:3]

    return {
        "dataset_id": dataset_id,
        "summary": {k: int(v or 0) for k, v in (summary or {}).items()},
        "failures": failures,
        "assets": assets,
    }


async def register_assets(dataset_id, rows):
    await get_dataset(dataset_id)
    await db.insert_assets(dataset_id, rows)
    return await get_assets(dataset_id)


# ── 파이프라인 노드 ─────────────────────────────────────────────────────────
def default_nodes(preset):
    """프리셋 기본 노드 체인.

    범용은 편집 가능한 뼈대만 주고, 해양 COLREG 는 도메인 순서(원천 → 정제 → 조인 →
    결정론 계산 → 생성 → 심사 → 조립)가 결과의 전제라 그대로 고정한다.
    """
    if preset == PRESET_SDS_COLREG:
        return [
            {"kind": "src", "name": "항해 영상",
             "steps": [["브리지 카메라 영상", "mp4"], ["타임스탬프 프레임", "1 fps"]]},
            {"kind": "src", "name": "AIS 로그",
             # 첫 항목은 기능 목록(SDS_AIS_LIBRARY)의 key 와 같아야 한다 — 설정을 저장하지
             # 않은 파이프라인은 표시 이름으로 켜진 기능을 되짚기 때문이다. 아래 config 로
             # 못박아 두지만, 표시와 실제가 어긋나 보이지 않게 이름도 맞춘다.
             "steps": [["단위 정규화", "knot · deg"], ["자선 · 주변선 상태", "14 cols"]],
             "config": {"enabled": {"단위 정규화": True}, "params": {}}},
            {"kind": "prep", "name": "전처리 · 영상",
             "steps": [["이미지 정규화", "RGB · 1024"], ["EXIF 보정", "방향"], ["타임스탬프 부여", "frame_idx"]]},
            {"kind": "filter", "name": "필터 · 영상",
             "steps": [["중복 제거", "해밍 ≤2"], ["최소 해상도", "512 px"], ["흐림", "사용 안 함"]],
             # 목업 cfg 그대로: 프레임 중복 phash ≤2 · 저해상 512 미만 · 흐림·노출 사용 안 함.
             # 설정을 명시해 두는 이유: 저장된 설정이 없으면 표시 이름으로 켜진 기능을
             # 되짚는데, 그러면 '흐림'까지 켜져 해양 프레임(선명도 1.8~9.8)이 전량 탈락한다.
             "config": {"enabled": {"중복 제거": True, "최소 해상도": True},
                        "params": {"dupTh": 97, "minEdge": 512}}},
            # AIS 갈래도 영상 갈래처럼 단계마다 노드를 둔다.
            # 순서는 목업(전처리 → 필터)이 아니라 **데이터 흐름**을 따른다 — 씬을 만든 뒤
            # 행을 지우면 씬 안에 무효 행이 남거나 씬을 다시 만들어야 한다. 목업 숫자도
            # 그 모순을 보여준다(필터가 200'행'을 받는다 = 아직 씬이 아니다).
            {"kind": "filter", "name": "AIS 행 정제",
             "steps": [["무효 좌표", "lat·lon 0"], ["범위 위반", "heading 0~360"],
                       ["중복 행", "ts + ship_id"]],
             "config": {"enabled": {"무효 좌표": True, "범위 위반": True, "중복 행": True},
                        "params": {}}},
            {"kind": "prep", "name": "AIS 씬 구조화",
             "steps": [["시간 정렬", "ts 오름차순"], ["씬 구조화", "자선 + 주변선"]],
             "config": {"enabled": {"시간 정렬": True, "씬 구조화": True}, "params": {}}},
            {"kind": "join", "name": "조인",
             "steps": [["프레임 × AIS", "ts 최근접"], ["허용오차", "Δt ≤ 1s"], ["무매칭 처리", "드롭"]]},
            {"kind": "calc", "name": "COLREG 계산",
             "steps": [["상대방위 · 침로차", "결정론"], ["조우 분류", "13 · 14 · 15 · 17"], ["근접 위험도", "CPA · TCPA"]]},
            {"kind": "gen", "name": "생성",
             "steps": [["사실 grounding", "facts + AIS"], ["이미지 서술", "Qwen3-VL"], ["describe + advice", "2회 재시도"]]},
            {"kind": "gate", "name": "VLM 심사",
             "steps": [["4축 채점", "InternVL3"], ["COLREG 앵커 대조", "객관 검증"], ["이미지 어블레이션", "grounding"]]},
            {"kind": "out", "name": "조립 · 내보내기",
             "steps": [["LLaVA 대화 JSON", "train"], ["씬 폴더", "ts별"], ["단계 중간물", "funnel"]]},
        ]
    return [
        {"kind": "data", "name": "데이터", "steps": []},
        {"kind": "prep", "name": "전처리",
         "steps": [["정제", "RGB + EXIF"], ["구조 추출", "PDF + 표"], ["리사이즈", "1024px"]]},
        {"kind": "filter", "name": "필터",
         "steps": [["중복 제거", "0.95"], ["흐림", "선명도 40"], ["최소 해상도", "512 px"],
                   ["민감 콘텐츠", "유해 0.85"]]},
        {"kind": "synth", "name": "생성", "steps": []},
        {"kind": "gate", "name": "VLM 심사", "steps": []},
    ]


def _node_warning(node, input_type):
    """노드 경고 판정.

    레코드가 만들어진 뒤(input_type == '레코드') 이미지를 기하적으로 바꾸면 이미 매긴
    심사 점수가 그 레코드를 설명하지 못하게 된다. 좌표 보정까지 빠지면 bbox 가 원본
    기준으로 남아 이미지와 어긋나므로 더 심각하다.
    """
    step_names = [s[0] for s in (node.get("steps") or []) if s]
    geom = [s for s in step_names if s in GEOMETRIC_STEPS]
    if not geom or input_type != "레코드":
        return "normal", ""
    if COORD_REMAP_STEP not in step_names:
        return "danger", "영역 좌표가 깨집니다 · 좌표 보정 추가"
    directional = [s for s in step_names if s in DIRECTIONAL_STEPS]
    tail = " · 사람 판정" if directional else ""
    return "warn", f"심사 점수{tail} 무효 → 재심사"


def _stage_by_node_index(nodes):
    """노드 index → 단계 이름.

    `_find_stage_node` 를 그대로 재사용한다 — 화면이 이름이나 순번으로 다시 추측하면
    규칙이 두 곳으로 갈라지고, 한쪽만 고치면 저장이 엉뚱한 노드로 간다(해양 프리셋의
    항해 영상/AIS 는 둘 다 kind='src' 라 특히 쉽게 어긋난다).

    한 단계에 노드가 여럿인 경우(해양의 전처리·필터가 영상/AIS 로 두 벌) 첫 노드만
    잡힌다 — 단계 API 자체가 단계당 노드 하나를 가정하는 기존 제약이다.
    """
    mapping = {}
    for i, stage in enumerate(STAGES):
        node = _find_stage_node(nodes, stage)
        if node is None:
            continue
        idx = node.get("node_index")
        if idx is None:
            try:
                idx = nodes.index(node)
            except ValueError:
                continue
        mapping.setdefault(idx, stage)
    return mapping


def _annotate_flow(nodes):
    """노드마다 입력/출력 타입과 경고를 붙인다.

    타입이 '데이터'에서 '레코드'로 바뀌는 지점은 생성 노드다. 그 뒤의 변형은 의미가
    달라지므로(원본이 아니라 레코드를 건드림) 타입을 따라가며 판정한다.
    """
    out = []
    cur_type = "—"
    stage_of = _stage_by_node_index(nodes)
    for i, n in enumerate(nodes):
        kind = n.get("kind")
        in_type = "—" if kind in ("data", "src") else cur_type
        if kind in ("synth", "gen"):
            cur_type = "레코드"
        elif kind in ("data", "src"):
            cur_type = "데이터"
        elif kind == "join":
            cur_type = "씬"
        elif kind == "calc":
            cur_type = "씬 + 사실"
        elif kind == "out":
            cur_type = "학습셋"
        state, warn = _node_warning(n, in_type)
        _stage = stage_of.get(n.get("node_index", i))
        if not _stage and kind in ("prep", "filter") and not warn:
            # 예전 프리셋으로 만들어진 파이프라인에는 AIS 전처리·필터 노드가 남아 있다.
            # 인덱스를 다시 매기면 실행 이력(node_index 로 묶여 있다)이 엉뚱한 노드를
            # 가리키므로 지우지 않고, 왜 누를 수 없는지 화면에 말해 준다.
            state = "warn"
            warn = "'AIS 로그' 노드가 이미 수행합니다 — 이 노드는 실행하지 않습니다"
        out.append({**n, "input_type": in_type, "output_type": cur_type,
                    "state": state, "warning": warn,
                    # 이 노드의 설정을 저장할 단계 이름. 없으면 저장 경로가 없는 노드다
                    # (해양의 조립·내보내기, 두 번째 전처리/필터).
                    "stage": _stage})
    return out


def _passed_of(run):
    """이 실행에서 **통과한** 건수.

    대부분의 노드는 걸러낸 것을 버리므로 out_count 가 곧 통과 건수다. 그런데 심사
    노드는 **미달을 버리지 않는다**(재생성·검수 대상으로 남긴다) — 그래서 out_count 는
    '채점을 마친 건수'이고, 그것을 통과로 표시하면 통과율이 항상 100% 로 보인다.
    실제 통과 건수는 노드가 funnel.json 에 passed 로 남기므로 그것을 쓴다.
    """
    if not run:
        return None
    funnel = run.get("funnel") or {}
    passed = funnel.get("passed")
    return passed if isinstance(passed, int) else run.get("out_count")


def _run_brief(run):
    """캔버스가 노드 위에 얹을 최소 정보. funnel 전문은 실행 상세에서 본다."""
    if not run:
        return None
    return {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "dry_run": bool(run.get("dry_run")),
        "in": run.get("in_count"),
        "out": run.get("out_count"),
        # 통과와 산출은 심사 노드에서 갈린다(위 _passed_of 참고). 화면이 스스로
        # 단계별 예외를 두지 않도록 BE 가 갈라 준다.
        "passed": _passed_of(run),
        "dropped": run.get("dropped_count"),
        "error_reason": run.get("error_reason"),
        "started_at": run.get("create_datetime"),
        "ended_at": run.get("end_datetime"),
    }


def _derive_edges(nodes, preset):
    """노드 체인의 간선을 **상류 배선에서** 만든다.

    화면이 간선을 하드코딩하면(목업 인덱스 배열) 노드 구성이 조금만 달라져도 그림과 실행이
    갈린다 — 실제로 이 갈림 때문에 캔버스는 전처리가 체인 안에 있다고 그렸는데 실행은
    아무것도 읽지 못했다. 무엇이 무엇을 먹는지는 상류 배선이 정본이므로 그것을 그린다.

    단계가 있는데 배선이 없으면(범용 전처리처럼 /datasets 를 직접 읽는 경우) 직전 노드에
    잇는다. 단계가 아예 없는 노드는 **잇지 않는다** — 해양의 '전처리 · AIS'·'필터 · AIS' 는
    수집 노드가 그 일을 이미 하므로 체인 밖이고, 선으로 이으면 다시 거짓말이 된다.
    """
    stage_of = _stage_by_node_index(nodes)
    node_of_stage = {}
    for idx, stage in stage_of.items():
        node_of_stage.setdefault(stage, idx)

    edges = []
    for i, n in enumerate(nodes):
        idx = n.get("node_index", i)
        if n.get("kind") in ("data", "src"):
            continue  # 원천은 입력이 없다
        stage = stage_of.get(idx)
        if stage:
            by_preset = STAGE_UPSTREAM_BY_PRESET.get(stage)
            spec = (by_preset or {}).get(preset) if by_preset else STAGE_UPSTREAM.get(stage)
        else:
            spec = None
        if spec:
            for up_stage in spec.values():
                up_idx = node_of_stage.get(up_stage)
                if up_idx is not None:
                    edges.append([up_idx, idx])
            continue
        # 단계가 없는 노드는 조립(out)만 이어 준다 — 실행은 안 되지만 체인의 끝이다.
        if stage or n.get("kind") == "out":
            if i > 0:
                edges.append([nodes[i - 1].get("node_index", i - 1), idx])
    return edges


async def get_flow(dataset_id):
    ds = await get_dataset(dataset_id)
    nodes = await db.get_flow(dataset_id)
    preset = ds.get("preset") or PRESET_GENERIC
    seeded = not nodes
    if seeded:
        # 아직 저장된 구성이 없으면 프리셋 기본값을 보여준다(빈 화면 방지).
        # config 를 버리면 프리셋이 실어 둔 기본 설정(해양 필터의 흐림 OFF 등)이 사라져,
        # 첫 실행이 표시 이름 매칭으로 엉뚱한 기능을 켠다.
        nodes = [{"kind": n["kind"], "name": n["name"], "steps": n["steps"],
                  "config": n.get("config") or {}}
                 for n in default_nodes(preset)]

    # 노드마다 최신 실행을 붙인다. 화면이 노드 수만큼 따로 물어보면 캔버스 한 번 그리는 데
    # 요청이 열 개 넘게 나간다. 아직 저장 전인 기본 체인에는 실행이 있을 수 없으므로 건너뛴다.
    latest = {} if seeded else await db.latest_runs_by_node(dataset_id)
    for i, n in enumerate(nodes):
        n["latest_run"] = _run_brief(latest.get(n.get("node_index", i)))

    return {
        "dataset_id": dataset_id,
        "preset": preset,
        "editable": PRESET_META.get(preset, {}).get("editable", True),
        "nodes": _annotate_flow(nodes),
        # 저장된 간선이 있으면 그것을, 없으면 상류 배선에서 만든 것을 준다. 예전에는
        # 빈 배열을 줘서 화면이 하드코딩 간선으로 그렸고, 그림과 실행이 갈렸다.
        "flow": ds.get("flow") or _derive_edges(nodes, preset),
    }


async def replace_flow(dataset_id, preset, nodes, flow=None):
    """노드 체인 저장.

    편집 가능 여부는 **저장된 프리셋**으로 판정한다. 요청 바디의 preset 으로 보면
    sds_colreg 데이터셋에 preset="generic" 을 보내는 것만으로 고정 잠금이 풀린다.
    """
    ds = await get_dataset(dataset_id)
    current = ds.get("preset") or PRESET_GENERIC
    if not PRESET_META.get(current, {}).get("editable", True):
        label = PRESET_META.get(current, {}).get("label", current)
        raise Conflict(
            f"'{label}' 프리셋은 노드 구성이 고정입니다 "
            "(조인·계산 순서가 바뀌면 결과가 성립하지 않습니다).")
    if preset != current:
        raise Conflict(
            f"프리셋은 저장 시 바꿀 수 없습니다 (현재 '{current}', 요청 '{preset}').")
    payload = [n.model_dump() if hasattr(n, "model_dump") else dict(n) for n in nodes]
    await db.replace_flow(dataset_id, current, payload, flow=flow)
    return await get_flow(dataset_id)


# ── 단계 설정 ───────────────────────────────────────────────────────────────
def _stage_library(stage):
    return {
        "preprocess": PREPROCESS_LIBRARY,
        "filter": FILTER_LIBRARY,
        "sds_video": SDS_VIDEO_LIBRARY,
        "sds_ais": SDS_AIS_LIBRARY,
        "sds_ais_clean": SDS_AIS_CLEAN_LIBRARY,
        "sds_ais_scene": SDS_AIS_SCENE_LIBRARY,
        "sds_join": SDS_JOIN_LIBRARY,
        "sds_colreg": SDS_COLREG_LIBRARY,
    }.get(stage, ())


async def _preset_of(dataset_id):
    """데이터셋의 프리셋. 심사 축·임계를 고르는 기준이라 축을 쓰는 곳은 전부 이걸 거친다."""
    return (await get_dataset(dataset_id)).get("preset") or PRESET_GENERIC


# ── 소스 데이터셋 목록 ───────────────────────────────────────────────────────
# 원본 적재는 기존 데이터셋(드라이브)이 하고, 파이프라인은 거기서 폴더를 골라 읽는다.
# 목록을 화면이 직접 플랫폼 API 에서 가져오지 않고 여기서 정리해 주는 이유:
#   1. 노드가 먹는 경로 규칙("{access}/{이름}{서브폴더}")이 한 곳에만 있어야 한다.
#      화면이 조립하면 규칙이 두 곳으로 갈라지고, 한쪽만 고치면 조용히 빈 결과가 된다.
#   2. 작업 데이터셋(파이프라인 산출물)은 목록에서 빠져야 한다 — 자기 출력을 자기 입력으로
#      고를 수 있으면 안 된다.
_SOURCE_LIST_PAGE_SIZE = 200
# 폴더 트리는 실행 산출물이 쌓이면 수천 줄이 된다. 화면 셀렉트에 담을 만큼만 준다.
_SOURCE_FOLDER_LIMIT = 300


async def list_source_datasets(workspace_id, jf_user=None):
    """소스로 고를 수 있는 플랫폼 데이터셋. path 는 노드에 그대로 넣는 값이다."""
    url = (f"{_DATASET_BASE}?workspace_id={int(workspace_id)}"
           f"&page=1&size={_SOURCE_LIST_PAGE_SIZE}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"Jf-User": jf_user or ""},
                               timeout=aiohttp.ClientTimeout(total=60)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"dataset 목록 HTTP {resp.status}: {text[:200]}")
            data = json.loads(text)
    if not data.get("status"):
        # 플랫폼은 사용자를 못 찾아도 status 0 으로만 답한다(빈 목록과 구분되지 않는다).
        raise RuntimeError(f"dataset 목록 조회 실패: {data.get('message')}")
    rows = ((data.get("result") or {}).get("list")) or []
    excluded = set(await db.list_work_dataset_ids(workspace_id))
    out = []
    for r in rows:
        if r.get("id") in excluded:
            continue
        name, access = r.get("dataset_name"), r.get("access")
        if not name or access is None:
            continue
        out.append({
            "id": r["id"], "name": name, "access": access,
            "size": r.get("size"), "description": r.get("description"),
            # 노드가 /datasets 아래에서 찾는 경로. 화면은 이 값을 그대로 sources 에 넣는다.
            "path": f"{access}/{name}",
        })
    return out


async def list_source_folders(workspace_id, dataset_id, jf_user=None):
    """데이터셋 안의 폴더. 첫 항목은 항상 전체(루트)."""
    url = f"{_DATASET_BASE}/{int(dataset_id)}/tree"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"Jf-User": jf_user or ""},
                               timeout=aiohttp.ClientTimeout(total=60)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"폴더 조회 HTTP {resp.status}: {text[:200]}")
            data = json.loads(text)
    if not data.get("status"):
        raise RuntimeError(f"폴더 조회 실패: {data.get('message')}")
    tree = ((data.get("result") or {}).get("tree")) or []
    folders = [{"path": "/", "name": "/ (전체)"}]
    # 파이프라인이 만든 중간물은 소스가 아니다 — 자기 산출물을 다시 먹는 경로가 된다.
    for t in tree:
        if not isinstance(t, str) or not t.startswith("/"):
            continue
        if t.startswith(("/_runs", "/_preview")):
            continue
        folders.append({"path": t, "name": t})
        if len(folders) >= _SOURCE_FOLDER_LIMIT:
            break
    truncated = len(tree) > _SOURCE_FOLDER_LIMIT
    return {"dataset_id": int(dataset_id), "folders": folders, "truncated": truncated}


# ── 노드 실행 ────────────────────────────────────────────────────────────────
# 단계 → 잡이 실행할 빌트인 스크립트. 노드 종류를 잡의 run_code 가 구분한다
# (프로젝트는 파이프라인당 하나라 엔티티의 built_in_data_tf 는 대표값일 뿐이다).
STAGE_SCRIPT = {
    "preprocess": "dp_prep.py",
    "filter": "dp_filter.py",
    "generate": "dp_generate.py",
    "gate": "dp_judge.py",
    "sds_video": "dp_sds_video.py",
    "sds_ais": "dp_sds_ais.py",
    "sds_ais_clean": "dp_sds_ais_clean.py",
    "sds_ais_scene": "dp_sds_ais_scene.py",
    "sds_join": "dp_sds_join.py",
    "sds_colreg": "dp_colreg.py",
    "assemble": "dp_assemble.py",
}

# 상류 노드가 있는 단계: {params.inputs 키: 상류 단계}. 조인은 소스 데이터셋이 아니라
# 앞 두 노드의 산출물을 읽으므로, BE 가 그 경로를 찾아 넣어 줘야 실행된다.
# 생성은 프리셋마다 상류가 다르다 — 해양은 COLREG 계산(앵커가 있어야 프롬프트가 선다),
# 범용은 필터. 단계 이름만 보고 하나로 묶으면 한쪽 프리셋에서 "노드 없음" 이 뜬다.
STAGE_UPSTREAM_BY_PRESET = {
    # 조립은 심사 산출물을 읽는다. 프리셋과 무관하게 게이트가 유일한 상류다.
    "assemble": {PRESET_GENERIC: {"records": "gate"},
                 PRESET_SDS_COLREG: {"records": "gate"}},
    # 해양의 전처리는 /datasets 가 아니라 **항해 영상 노드의 프레임**을 받는다.
    # 목업 SDS_FLOW = 0(영상)→2(전처리)→3(필터)→6(조인), SDS_IN[전처리]='프레임'.
    # 범용은 원본을 /datasets 에서 직접 읽으므로 상류가 없다.
    "preprocess": {PRESET_SDS_COLREG: {"assets": "sds_video"}},
    "filter": {PRESET_SDS_COLREG: {"assets": "preprocess"},
               PRESET_GENERIC: {"assets": "preprocess"}},
    # 조인은 **필터를 통과한** 프레임을 받는다(중복·저해상 프레임이 씬에 섞이지 않게).
    # AIS 쪽은 수집 노드가 단위 정규화·씬 구조화·무효/범위/중복 제거까지 끝내므로
    # 그 산출을 그대로 받는다 — 목업의 '전처리 · AIS'·'필터 · AIS' 가 하는 일이 그것이다.
    "sds_ais_clean": {PRESET_SDS_COLREG: {"assets": "sds_ais"}},
    "sds_ais_scene": {PRESET_SDS_COLREG: {"assets": "sds_ais_clean"}},
    "sds_join": {PRESET_SDS_COLREG: {"frames": "filter", "scenes": "sds_ais_scene"}},
    "generate": {PRESET_SDS_COLREG: {"records": "sds_colreg"},
                 PRESET_GENERIC: {"records": "filter"}},
    "gate": {PRESET_SDS_COLREG: {"records": "generate"},
             PRESET_GENERIC: {"records": "generate"}},
}

STAGE_UPSTREAM = {
    "sds_colreg": {"scenes": "sds_join"},
}

# 작업 데이터셋 안의 경로. 미리보기는 표본만 돌리고 이력에 남기지 않는다.
RUN_DIR = "_runs"
PREVIEW_DIR = "_preview"

_PREPRO_BASE = "http://{host}:{port}/api/preprocessing".format(
    host=os.getenv("JFB_APP_PREPROCESSING_SVC_SERVICE_HOST", "jfb-app-preprocessing-svc"),
    port=os.getenv("JFB_APP_PREPROCESSING_SVC_SERVICE_PORT", "80"))


async def _prepro_post(path, body, jf_user):
    """전처리 MSA 호출. 실패 사유를 그대로 올려 사용자가 원인을 본다."""
    url = _PREPRO_BASE + path
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body,
                                headers={"Jf-User": jf_user or ""},
                                timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"preprocessing {path} HTTP {resp.status}: {text[:200]}")
            data = json.loads(text)
    if not data.get("status"):
        raise RuntimeError(f"preprocessing {path}: {data.get('message')}")
    return data.get("result") or {}


def _new_run_id():
    """run_id 는 매 실행 새로 발급한다 — 부분 재실행이 이전 산출물을 덮지 않게."""
    return f"r{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _runnable_steps(stage, node):
    """노드가 실제로 실행할 [기능명, 파라미터] 목록.

    `llm_dp_node.steps` 는 캔버스에 보여줄 **표시값**(예: ["리사이즈", "1024px"])이라
    그대로 넘기면 노드가 파라미터를 못 읽는다. 실제 값은 `config.enabled/params` 에 있다.
    실행 순서는 라이브러리 정의 순서를 따른다(사용자가 순서를 바꾸는 UI 는 아직 없다).

    config 가 비어 있으면(기본 노드 그대로) 표시값의 기능명만 살려 기본 파라미터로 돈다 —
    설정을 한 번도 저장하지 않은 파이프라인도 의미 있게 실행되게.
    """
    library = _stage_library(stage)
    if not library:
        return []
    cfg = node.get("config") or {}
    enabled = cfg.get("enabled") or {}
    saved = cfg.get("params") or {}
    if not enabled:
        shown = {s[0] if isinstance(s, (list, tuple)) else s for s in (node.get("steps") or [])}
        enabled = {name: True for name in shown}

    steps = []
    for item in library:
        key = item["key"]
        if not enabled.get(key):
            continue
        pspec = item.get("param") or {}
        pkey = pspec.get("key")
        if pkey:
            steps.append([key, {pkey: saved.get(pkey, pspec.get("default"))}])
        else:
            steps.append([key, {}])
    return steps


# 작업 데이터셋은 access=0(생성자만 수정)으로 만든다. 플랫폼의 데이터셋 삭제는 사용 중
# 검사가 없으므로, 정책을 바꾸지 않고 오삭제 가능성을 줄일 수 있는 유일한 수단이다.
WORK_DATASET_ACCESS = 0
_DATASET_BASE = "http://{host}:{port}/api/datasets".format(
    host=os.getenv("JFB_APP_DATASET_SVC_SERVICE_HOST", "jfb-app-dataset-svc"),
    port=os.getenv("JFB_APP_DATASET_SVC_SERVICE_PORT", "80"))


def _work_dataset_root(storage_name, workspace_name, access, dataset_name):
    """BE 파드에서 본 작업 데이터셋 디렉터리(PATH.JF_DATA_DATASET_PATH 와 같은 규약)."""
    return f"/jf-data/{storage_name}/data/{workspace_name}/{access}/{dataset_name}"


async def _work_dataset_root_of(ds):
    """이 파이프라인의 작업 데이터셋 디렉터리. 없으면 사유를 그대로 올린다 —
    "왜 릴리스가 안 되는가"를 경로 없음으로 뭉뚱그리면 원인을 찾을 수 없다."""
    name = ds.get("work_dataset_name")
    if not name:
        raise Conflict("작업 데이터셋이 아직 없습니다 — 노드를 한 번 실행하세요")
    storage_name = await db.get_workspace_storage_name(ds["workspace_id"])
    if not storage_name:
        raise Conflict(f"워크스페이스 스토리지를 찾을 수 없습니다: {ds['workspace_id']}")
    return _work_dataset_root(storage_name, ds["workspace_name"],
                              WORK_DATASET_ACCESS, name)


async def _ensure_work_dataset(ds, jf_user):
    """파이프라인이 소유한 빈 작업 데이터셋을 보장한다(최초 실행 시 생성).

    파이프라인 생성 시점이 아니라 첫 실행 때 만드는 이유: 이미 만들어진 파이프라인도
    그대로 동작하고, 실행하지 않는 파이프라인이 빈 데이터셋을 남기지 않는다.

    소스 데이터셋에 쓰지 않고 별도 데이터셋에 쌓는다 — 합성(synthesis)은 입력 데이터셋
    안의 output_subdir 에 쓰는데, 그러면 원본이 오염되고 남이 그 데이터셋을 지우면
    산출물까지 함께 사라진다.
    """
    if ds.get("work_dataset_id") and ds.get("work_dataset_name"):
        return ds["work_dataset_id"], ds["work_dataset_name"]

    name = f"dp-{ds['id']}-{ds['name']}"[:120]
    form = aiohttp.FormData()
    form.add_field("workspace_id", str(ds["workspace_id"]))
    form.add_field("dataset_name", name)
    form.add_field("access", str(WORK_DATASET_ACCESS))
    form.add_field("description", f"데이터 파이프라인 #{ds['id']} 산출물(중간 결과 · 릴리스)")
    async with aiohttp.ClientSession() as session:
        async with session.post(_DATASET_BASE, data=form,
                                headers={"Jf-User": jf_user or ""},
                                timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
    # 이미 있으면(동시 실행 패자) 생성은 실패해도 아래 재조회로 id 를 얻는다.
    # 데이터셋 생성은 result 로 새 id(정수)를 그대로 돌려준다 — dict 로 가정하면 터진다.
    work_id = None
    try:
        data = json.loads(text)
        if data.get("status"):
            res = data.get("result")
            work_id = res if isinstance(res, int) else (res or {}).get("id")
    except ValueError:
        pass
    if not isinstance(work_id, int):
        work_id = await db.find_platform_dataset_id(ds["workspace_id"], name)
    if not work_id:
        raise RuntimeError(f"작업 데이터셋을 만들지 못했습니다: {text[:200]}")

    await db.set_work_dataset(ds["id"], work_id, name)
    fresh = await get_dataset(ds["id"])
    return fresh.get("work_dataset_id") or work_id, fresh.get("work_dataset_name") or name


# 자기 설정에 소스가 없으면 데이터 노드에서 물려받는 단계.
# 화면은 소스를 데이터 노드에서 고른다(목업 기준). 그런데 실제로 /datasets 를 읽는 것은
# 전처리 노드다 — 데이터 노드는 실행되지 않는다. 그래서 실행 시점에 물려받는다.
STAGE_SOURCE_INHERIT = ("preprocess",)

# /datasets 에서 원본을 읽는 단계. 소스가 없으면 읽을 것이 없으므로 **띄우기 전에** 끊는다.
# 예전에는 그대로 띄워 0건으로 끝났다 — 사용자에게는 "성공, 0건" 으로 보여서 무엇이
# 잘못됐는지 알 수 없었다(제외도 0이라 걸러진 것도 아니다).
#
# 프리셋마다 다르다: 해양의 전처리는 소스가 아니라 **영상 노드의 프레임**을 받아야 한다
# (목업 SDS_FLOW: 영상→전처리→필터→조인, SDS_IN[전처리]='프레임'). 그러니 해양 전처리에
# "소스를 고르세요" 라고 안내하면 사용자를 틀린 방향으로 보낸다.
STAGE_NEEDS_SOURCES_BY_PRESET = {
    PRESET_GENERIC: ("preprocess",),
    PRESET_SDS_COLREG: ("sds_video", "sds_ais"),
}



def _resolve_sources(stage, node, nodes):
    """이 실행이 읽을 소스 경로 목록.

    자기 노드 설정이 우선이다 — 예전에 전처리 노드에 직접 저장한 파이프라인이 있고,
    그것을 데이터 노드 값으로 덮어쓰면 이미 돌던 파이프라인의 입력이 조용히 바뀐다.
    """
    own = (node.get("config") or {}).get("sources") or []
    if own or stage not in STAGE_SOURCE_INHERIT:
        return own
    data_node = _find_stage_node(nodes, "data")
    return ((data_node or {}).get("config") or {}).get("sources") or []


async def _resolve_upstream(stage, nodes, dataset_id):
    """조인처럼 앞 노드 산출물을 먹는 단계의 inputs. 없으면 어느 단계가 빠졌는지 말한다.

    상류는 실행 이력(llm_dp_run)에서 찾는다. 파일시스템을 훑던 이전 방식은 실행 중인
    잡과 끝난 잡을 산출물 유무로만 갈라서, 반쯤 쓰다 죽은 디렉터리를 성공으로 볼 수
    있었다. 이력은 리콘사일러가 done 으로 마감한 것만 done 이다.
    """
    by_preset = STAGE_UPSTREAM_BY_PRESET.get(stage)
    if by_preset:
        spec = by_preset.get(await _preset_of(dataset_id))
    else:
        spec = STAGE_UPSTREAM.get(stage)
    if not spec:
        return None
    inputs, missing = {}, []
    for key, up_stage in spec.items():
        up_node = _find_stage_node(nodes, up_stage)
        if up_node is None:
            missing.append(f"{up_stage}(노드 없음)")
            continue
        run = await db.latest_done_run(dataset_id, up_node.get("node_index", 0))
        if not run:
            missing.append(up_stage)
            continue
        inputs[key] = f"/dataset/{run['out_dir']}"
    if missing:
        raise Conflict("먼저 실행해야 하는 단계가 있습니다: " + ", ".join(missing))
    return inputs


# 단계 → 그 단계가 필요로 하는 서빙 역할.
# 심사는 판사 하나만 쓴다. 이미지 근거(image_grounding)를 평점이 아니라 **어블레이션**으로
# 재는데(이미지 없이 조언을 다시 만들어 원본과 같은지 비교), 그 재생성도 판사가 한다
# (프로토타입과 같음) — 덕분에 생성 모델을 함께 띄우지 않아도 되고 GPU 하나로 끝난다.
STAGE_SERVING_ROLES = {
    "generate": ("generator",),
    "gate": ("judge",),
}

# 서빙을 기다렸다 잡을 띄우는 작업. asyncio 가 참조 없는 task 를 수거하지 않게 붙든다.
_DISPATCH_TASKS = {}


async def _serving_urls(dataset_id, roles, jf_user=None, verify=False):
    """준비된 서빙 주소 {역할: {url, model_id, hf_id}} 와 아직 없는 역할 목록.

    verify=True 면 장부가 ready 라고 해도 **배포가 실제로 살아 있는지** 확인한다.
    장부만 믿으면 밖에서 내려간 배포의 주소를 그대로 내보내고, 그것을 받은 잡이 사라진
    내부 DNS 를 불러 전량 serving_error 로 죽는다 — 실측으로 심사 100건이
    'Name or service not known' 으로 전멸했다.

    확인이 필요한 곳은 잡을 바로 던지는 빠른 경로뿐이다. ensure_serving 직후에 다시
    묻는 것은 중복이고, 그 조회가 일시적으로 실패하면 건강한 서빙을 두고 실행만
    죽는다 → 그 경로는 verify=False 로 둔다.
    """
    ds = await get_dataset(dataset_id)
    user = jf_user or ds.get("create_user") or ""
    ready, missing = {}, []
    for role in roles:
        row = await db.get_serving(dataset_id, role)
        if not (row and row.get("status") == "ready" and row.get("playground_id")):
            missing.append(role)
            continue
        if verify and not await _serving_usable(dataset_id, role, row, user):
            missing.append(role)
            continue
        ready[role] = {
            "url": serving_endpoint(row["playground_id"], ds["workspace_id"]),
            "model_id": row.get("model_id"), "hf_id": row.get("hf_id"),
        }
        # 노드는 내부 DNS 로 직접 부르므로 BE 에 호출 기록이 남지 않는다. 여기서 찍지
        # 않으면 유휴가 배포 시각 기준으로 계산돼, 방금 쓴 배포가 회수된다.
        # 순전한 부기이므로 실패가 실행을 죽이게 두지 않는다 — 여기서 예외가 나가면
        # job_name 이 빈 running 행이 남아 리콘사일러가 30분간 그 데이터셋을 busy 로 본다.
        try:
            await db.touch_serving(dataset_id, role)
        except Exception:  # noqa: BLE001
            logging.warning("[dp-serving] 사용시각 기록 실패 dataset=%s role=%s",
                            dataset_id, role, exc_info=True)
    return ready, missing


async def _serving_usable(dataset_id, role, row, user):
    """장부의 이 배포를 그대로 잡에 넘겨도 되는가.

    두 가지를 본다. 모델 대조가 먼저인 이유는 값이 싸고, 교체할 배포에 생존 확인
    비용을 들일 필요가 없기 때문이다.
    """
    # 1) 장부가 가리키는 모델이 지금 설정과 다르면 옛 배포가 살아 있어도 쓸 수 없다.
    #    사용자가 모델만 바꿔 저장하면 장부는 그대로이므로(upsert 는 ensure_serving
    #    에서만 돈다) 여기서 걸러야 한다. 안 걸러내면 화면은 새 모델이라 말하는데
    #    생성·채점은 옛 모델이 하고, 그 model_id 가 산출물 config.json 에 기록돼
    #    "두 실행을 나란히 비교한다"는 전제가 조용히 깨진다.
    try:
        want = await _role_model_id(dataset_id, role)
    except Exception:  # noqa: BLE001 - 설정을 못 읽으면 ensure_serving 이 사유를 낸다
        want = None
    if want != row.get("model_id"):
        logging.warning("[dp-serving] 설정 모델 불일치 → 재준비 dataset=%s role=%s "
                        "장부=%s 설정=%s", dataset_id, role, row.get("model_id"), want)
        return False
    return await _serving_alive(row["playground_id"], user, dataset_id, role)


async def _serving_alive(playground_id, user, dataset_id, role):
    """배포가 지금도 도는가. **부정 판정은 한 번 더 확인한 뒤에** 내린다.

    이 상태 API 는 사라진 배포만 예외로 알려 주는 것이 아니다. llm_playground 의
    get_playground_status 는 기본값이 `{"status": "stop"}` 이고, Redis 파드 캐시가
    비었거나 내부 오류를 삼켰을 때 그 기본값을 **정상 응답으로** 돌려준다. 그래서
    _playground_gone 만으로는 흔한 오탐을 못 가른다. 한 번을 그대로 믿으면 멀쩡한
    배포를 헐고 30분 콜드 스타트를 다시 태운다 — 부정 판정의 대가가 그만큼 크므로
    10초를 더 쓴다. 연속으로 확정하는 모양은 PLAYGROUND_GONE_LIMIT 관례와 같다.
    """
    for attempt in (1, 2):
        try:
            if await _playground_status(playground_id, user) == "running":
                return True
        except Exception as e:  # noqa: BLE001 - 사라진 것은 즉시 확정, 나머지는 재확인
            if _playground_gone(e):
                logging.warning("[dp-serving] 배포 없음 dataset=%s role=%s playground=%s",
                                dataset_id, role, playground_id)
                return False
            logging.warning("[dp-serving] 상태 조회 실패(%s회) dataset=%s role=%s",
                            attempt, dataset_id, role, exc_info=True)
        if attempt == 1:
            await asyncio.sleep(SERVING_POLL_S)
    logging.warning("[dp-serving] 연속 2회 not-running → 재준비 dataset=%s role=%s "
                    "playground=%s", dataset_id, role, playground_id)
    return False


async def _write_and_dispatch(out_dir, params, dispatch, run_pk, job_name, jf_user):
    """params.json 을 쓰고 잡을 띄운 뒤 실행 이력에 잡 이름을 채운다.

    쓰기가 먼저인 이유: 잡이 먼저 뜨면 params.json 이 아직 없어 노드가 즉시 죽는다.
    """
    with open(os.path.join(out_dir, "params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    job = await _prepro_post("/jobs/pipeline/run", dispatch, jf_user)
    await db.set_run_job(run_pk, job_name)
    return job


async def _dispatch_when_serving_ready(dataset_id, roles, out_dir, params, dispatch,
                                       run_pk, job_name, jf_user):
    """서빙을 준비한 뒤 잡을 띄운다. 실패하면 그 실행을 사유와 함께 닫는다.

    실패를 실행 이력에 적어야 한다 — 여기서 조용히 끝나면 실행은 영영 running 으로
    남고, 사용자는 24시간 뒤 "종료 기록도 산출물도 없다" 만 보게 된다.
    """
    try:
        for role in roles:
            await ensure_serving(dataset_id, role, jf_user)
        serving, missing = await _serving_urls(dataset_id, roles, jf_user)
        if missing:
            raise Conflict("서빙 준비가 끝나지 않았습니다: " + ", ".join(missing))
        params["serving"] = serving
        await _write_and_dispatch(out_dir, params, dispatch, run_pk, job_name, jf_user)
        logging.warning("[dp-run] 서빙 준비 후 디스패치 run=%s %s", run_pk, job_name)
    except Exception as e:  # noqa: BLE001
        logging.exception("[dp-run] 서빙 준비 실패로 실행 취소 run=%s", run_pk)
        await db.finish_run(run_pk, "failed",
                            error_reason=f"모델 서빙 준비 실패: {e}"[:1000])
    finally:
        _DISPATCH_TASKS.pop(run_pk, None)


async def run_stage(dataset_id, stage, dry_run=False, sample_size=10, jf_user=None):
    """노드 하나를 잡으로 띄운다.

    설정을 params.json 으로 **작업 데이터셋 안에** 써 두고 잡에는 그 경로만 넘긴다.
    노드 설정은 기능 목록·순서·파라미터가 중첩된 구조라 `--key value` 로 펼치면
    helm --set 의 콤마·중괄호 이스케이프에 걸린다.
    """
    if stage not in STAGE_SCRIPT:
        raise ValueError(f"실행할 수 없는 단계입니다: {stage}")

    ds = await get_dataset(dataset_id)
    workspace_id = ds["workspace_id"]
    nodes = await db.get_flow(dataset_id) or []
    node = _find_stage_node(nodes, stage)
    if node is None:
        raise NotFound(f"'{stage}' 단계에 해당하는 노드가 파이프라인에 없습니다")

    # 파이프라인당 전처리 프로젝트 하나(멱등). 노드마다 만들면 같은 파이프라인의 노드가
    # 서로 다른 instance 에 할당돼 쿼터를 노드 종류 수만큼 문다.
    ensured = await _prepro_post("/data-pipeline/ensure",
                                 {"workspace_id": workspace_id, "dp_dataset_id": dataset_id},
                                 jf_user)
    preprocessing_id = ensured["preprocessing_id"]

    run_id = _new_run_id()
    node_index = node.get("node_index", 0)
    base = PREVIEW_DIR if dry_run else RUN_DIR
    rel_dir = f"{base}/{run_id}/{node_index}"

    work_id, work_name = await _ensure_work_dataset(ds, jf_user)
    storage_name = await db.get_workspace_storage_name(workspace_id)
    if not storage_name:
        raise Conflict("워크스페이스에 data 스토리지가 없습니다")
    work_root = _work_dataset_root(storage_name, ds["workspace_name"],
                                   WORK_DATASET_ACCESS, work_name)

    # 상류가 있는 단계는 잡을 만들기 **전에** 확인한다 — 먼저 파드를 띄우고 노드
    # 안에서 죽으면 사용자는 "실패"만 보고 무엇을 먼저 돌려야 하는지 모른다.
    upstream = await _resolve_upstream(stage, nodes, dataset_id)

    out_dir = os.path.join(work_root, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    params = {
        "run_id": run_id,
        "node_index": node_index,
        "preset": ds.get("preset") or PRESET_GENERIC,
        "sources": _resolve_sources(stage, node, nodes),
        "steps": _runnable_steps(stage, node),
        "dry_run": bool(dry_run),
        "sample_size": int(sample_size),
        # 잡 pod 기준 경로 — 작업 데이터셋은 /dataset 에 마운트된다.
        "out_dir": f"/dataset/{rel_dir}",
        "datasets_root": "/datasets",
    }
    if upstream:
        params["inputs"] = upstream
    # 노드 설정 원본도 함께 넘긴다. steps 는 라이브러리 기반 기능 목록이라, 생성처럼
    # 라이브러리가 없는 단계(언어·프롬프트·모델이 곧 설정)는 원본이 없으면 읽을 게 없다.
    params["config"] = node.get("config") or {}

    preset = ds.get("preset") or PRESET_GENERIC
    # 기능 목록이 있는 단계인데 켜진 기능이 하나도 없으면 이 실행은 통과시키기만 한다.
    # 그것을 성공으로 남기면 사용자는 필터가 돈 줄 안다(실제로 100→100, 제외 0 이 나왔다).
    # 노드의 표시 이름이 라이브러리 key 와 다를 때 조용히 이렇게 되므로 목록도 함께 알린다.
    _library = _stage_library(stage)
    if _library and not params["steps"]:
        raise Conflict(
            f"'{node.get('name') or stage}' 에서 실행할 기능이 하나도 없습니다 — 노드를 열어 "
            "사용할 기능을 저장하세요. 이 단계의 기능 목록: "
            + ", ".join(item["key"] for item in _library))

    if stage in (STAGE_NEEDS_SOURCES_BY_PRESET.get(preset) or ()) and not params["sources"]:
        raise Conflict(
            f"'{node.get('name') or stage}' 노드가 읽을 소스가 지정되지 않았습니다 — "
            "캔버스에서 노드를 열고 데이터 소스(데이터셋 · 폴더)를 먼저 고르세요")

    job_name = f"dp-{dataset_id}-n{node_index}-{run_id}"
    roles = STAGE_SERVING_ROLES.get(stage) or ()

    # 잡을 띄우기 **전에** running 으로 남긴다. 띄운 뒤에 적으면 그 사이 요청이 끊겼을 때
    # 잡은 도는데 이력이 없는 상태가 되고, 그 실행은 영영 마감되지 않는다.
    # 서빙이 필요한 단계는 job_name 을 비워 둔다 = "아직 띄우지 않았다"(리콘사일러의 판별 근거).
    run_pk = await db.create_run(dataset_id, run_id, node_index, stage,
                                 "" if roles else job_name, bool(dry_run), rel_dir)

    dispatch = {"preprocessing_id": preprocessing_id, "job_name": job_name,
                "run_code": STAGE_SCRIPT[stage], "create_user_name": jf_user or "",
                # 잡의 /dataset 마운트 = 작업 데이터셋. 소스는 /datasets(RO)로 따로 붙는다.
                "dataset_id": work_id,
                "built_in_param": {"params_path": f"/dataset/{rel_dir}/params.json"}}

    result = {"dataset_id": dataset_id, "stage": stage, "run_id": run_id,
              "node_index": node_index, "dry_run": bool(dry_run),
              "out_dir": rel_dir, "work_dataset_id": work_id,
              "preprocessing_id": preprocessing_id}

    if not roles:
        result["job"] = await _write_and_dispatch(out_dir, params, dispatch,
                                                  run_pk, job_name, jf_user)
        return result

    serving, missing = await _serving_urls(dataset_id, roles, jf_user, verify=True)
    if not missing:
        params["serving"] = serving
        result["job"] = await _write_and_dispatch(out_dir, params, dispatch,
                                                  run_pk, job_name, jf_user)
        result["serving"] = {r: v["model_id"] for r, v in serving.items()}
        return result

    # 서빙이 없으면 여기서 끊지 않고 준비를 시작한 뒤, 준비되면 잡을 띄운다. 사용자가
    # 고른 것은 "자동 배포"이므로 한 번의 클릭으로 끝나야 한다 — 여기서 거절하면
    # 사용자는 몇 분 뒤에 같은 버튼을 다시 눌러야 한다는 것을 스스로 알아내야 한다.
    _DISPATCH_TASKS[run_pk] = asyncio.create_task(
        _dispatch_when_serving_ready(dataset_id, roles, out_dir, params, dispatch,
                                     run_pk, job_name, jf_user))
    result["job"] = None
    result["pending_serving"] = list(missing)
    return result


async def get_stage(dataset_id, stage):
    """단계 설정 + 그 단계에서 쓸 수 있는 기능 목록."""
    ds = await get_dataset(dataset_id)
    preset = ds.get("preset") or PRESET_GENERIC
    nodes = await db.get_flow(dataset_id) or []
    node = _find_stage_node(nodes, stage)

    payload = {
        "dataset_id": dataset_id,
        "stage": stage,
        "config": (node or {}).get("config") or {},
        "steps": (node or {}).get("steps") or [],
        "library": [dict(s) for s in _stage_library(stage)],
    }
    if stage == "generate":
        payload["models"] = [dict(m) for m in SELECTABLE_MODELS]
        payload["templates"] = [dict(t) for t in GENERATION_TEMPLATES]
        payload["prompt_chips"] = [dict(c) for c in PROMPT_CHIPS]
        payload["default_prompt"] = prompt_for(preset)
    if stage == "gate":
        payload["axes"] = [dict(a) for a in axes_for(preset)]
        payload["default_thresholds"] = thresholds_for(preset)
        payload["threshold_range"] = [THRESHOLD_MIN, THRESHOLD_MAX]
    return payload


async def save_stage(dataset_id, stage, config):
    """단계 설정을 해당 노드의 config 에 저장한다.

    노드 체인 자체는 그대로 두고 config 만 바꾸므로, 저장 후 전체를 다시 써 넣는다
    (노드 인덱스가 어긋나지 않게 replace_flow 를 그대로 쓴다).
    """
    ds = await get_dataset(dataset_id)
    preset = ds.get("preset") or PRESET_GENERIC
    nodes = await db.get_flow(dataset_id)
    if not nodes:
        nodes = default_nodes(preset)

    target = _find_stage_node(nodes, stage)
    if target is None:
        raise NotFound(f"'{stage}' 단계에 해당하는 노드가 파이프라인에 없습니다")

    # 임계값 축 집합 검사 — dto 는 body 만 보고 프리셋을 몰라 여기서 한다.
    # 축이 어긋난 채 저장되면 채점이 전부 미평가로 떨어져 통과율이 0 이 된다.
    if stage == "gate" and isinstance(config.get("thresholds"), dict):
        valid = set(thresholds_for(preset))
        got = set(config["thresholds"])
        if got != valid:
            raise ValueError(
                f"'{PRESET_META.get(preset, {}).get('label', preset)}' 프리셋의 심사 축과 다릅니다. "
                f"필요: {sorted(valid)} / 받음: {sorted(got)}")

    target["config"] = config

    await db.replace_flow(dataset_id, preset, nodes)
    return await get_stage(dataset_id, stage)


def judge_model_pairing(generator_model, judge_model):
    """생성/심사 모델 조합 판정.

    같은 모델이면 자기 결과를 자기가 채점하므로 맹점이 그대로 통과한다 → 차단.
    같은 계열이면 학습 데이터·구조가 겹쳐 독립성이 약하다 → 경고.
    """
    by_id = {m["id"]: m for m in GENERATION_MODELS}
    g, j = by_id.get(generator_model), by_id.get(judge_model)
    if not g or not j:
        return {"level": "error", "message": "알 수 없는 모델입니다"}
    # 이미지를 못 받는 모델은 배포까지는 성공하고 추론이 전량 400 으로 실패한다.
    # 그 실패는 노드 drops 에만 남아 화면에서 원인이 안 보이므로 여기서 막는다.
    unusable = list(dict.fromkeys(m["name"] for m in (g, j) if not m.get("vision")))
    if unusable:
        return {"level": "blocked",
                "message": f"{', '.join(unusable)} 은 이미지 입력을 받지 못해 이 "
                           "파이프라인에 쓸 수 없습니다. 다른 모델을 고르세요."}
    if generator_model == judge_model:
        return {"level": "blocked",
                "message": "생성 모델과 심사 모델이 같으면 맹점이 겹쳐 게이트가 무의미해집니다. "
                           "다른 계열의 모델을 고르세요."}
    if g["family"] == j["family"]:
        return {"level": "warn",
                "message": f"같은 계열 모델입니다 ({g['family']}). 심사 독립성이 약합니다."}
    return {"level": "ok", "message": ""}


# ── 검수 ────────────────────────────────────────────────────────────────────
async def list_records(dataset_id, order, taxonomy, review_state, limit, offset):
    preset = await _preset_of(dataset_id)
    records = await db.list_records(
        dataset_id, review_state=review_state, taxonomy=taxonomy,
        order=order, limit=limit, offset=offset) or []
    stats = await db.get_review_stats(dataset_id) or {}
    tax_rows = await db.get_taxonomy_distribution(dataset_id) or []
    total_tax = sum((t.get("count") or 0) for t in tax_rows) or 1
    return {
        "dataset_id": dataset_id,
        "axes": [dict(a) for a in axes_for(preset)],
        "thresholds": await get_effective_thresholds(dataset_id),
        "stats": {k: int(v or 0) for k, v in (stats or {}).items()},
        "taxonomy_distribution": [
            {"taxonomy": t["taxonomy"], "count": t["count"],
             "pct": round((t["count"] or 0) * 100 / total_tax)}
            for t in tax_rows
        ],
        "records": records,
    }


async def get_record(record_id):
    row = await db.get_record(record_id)
    if not row:
        raise NotFound(f"record not found: {record_id}")
    row["reviews"] = await db.list_reviews(record_id) or []
    # 축은 레코드가 속한 데이터셋의 프리셋을 따른다 — 레코드만 보고는 알 수 없다.
    preset = await _preset_of(row["dataset_id"])
    row["axes"] = [dict(a) for a in axes_for(preset)]
    row["thresholds"] = await get_effective_thresholds(row["dataset_id"])
    return row


async def get_record_by_key(dataset_id, record_key):
    """사람이 읽는 키(vdf-0009855)로 레코드를 연다. 화면 URL 이 이 키를 쓴다."""
    await get_dataset(dataset_id)
    record_id = await db.get_record_by_key(dataset_id, record_key)
    if record_id is None:
        raise NotFound(f"record not found: {record_key}")
    return await get_record(record_id)


async def review_record(record_id, verdict, taxonomy, edited_question, edited_answer, reviewer):
    row = await db.get_record(record_id)
    if not row:
        raise NotFound(f"record not found: {record_id}")
    if verdict == "edited" and not (edited_question or edited_answer):
        raise ValueError("'수정 후 승인'은 수정본이 있어야 합니다")
    if verdict == "rejected" and not taxonomy:
        raise ValueError("거절은 오류 유형을 함께 남겨야 합니다 (다음 생성을 고칠 근거)")
    await db.insert_review(record_id, verdict, taxonomy, edited_question, edited_answer, reviewer)
    return await get_record(record_id)


# ── 분포 분석 ───────────────────────────────────────────────────────────────
def _coverage_flag(record_count, asset_count, dataset_assets=0):
    """유형별 판정 — 레코드와 원본을 함께 봐야 원인이 갈린다.

    원본도 레코드도 없으면 업로드부터, 원본은 있는데 레코드가 없거나 원본 수에 비해
    턱없이 적으면 생성 조건 문제, 원본 자체가 희소하면 데이터를 더 올려야 한다.
    """
    if not record_count:
        # 원본이 하나도 없으면 업로드부터, 원본은 있는데 레코드가 없으면 생성 조건 문제.
        return "생성 부족" if dataset_assets else "데이터 없음"
    if asset_count and record_count < asset_count * 0.5:
        return "생성 부족"
    if asset_count and asset_count < 100:
        return "데이터 부족"
    return "충분"


async def get_coverage(dataset_id):
    await get_dataset(dataset_id)
    rows = await db.get_coverage(dataset_id) or []
    by_cap = {r["capability"]: r for r in rows}
    total = sum((r.get("record_count") or 0) for r in rows)
    # 레코드의 asset_ref 로만 세면 "아직 생성 안 한 원본" 이 안 보여 진단이 뒤집힌다.
    dataset_assets = await db.count_assets(dataset_id)

    out = []
    for cap in CAPABILITIES:
        r = by_cap.get(cap, {})
        recs = int(r.get("record_count") or 0)
        assets = int(r.get("asset_count") or 0)
        out.append({
            "capability": cap,
            "record_count": recs,
            "asset_count": assets,
            "pct": round(recs * 100 / total) if total else 0,
            "flag": _coverage_flag(recs, assets, dataset_assets),
        })
    return {
        "dataset_id": dataset_id,
        "total_records": total,
        "dataset_assets": dataset_assets,
        "coverage": out,
    }


async def get_effective_thresholds(dataset_id):
    """이 데이터셋에 실제로 적용 중인 임계값.

    게이트 단계에 저장된 값이 있으면 그것을 쓴다. 상수만 보면 사용자가 화면에서
    임계값을 바꿔 저장해도 통과율이 그대로여서 저장 기능이 없는 것과 같아진다.
    """
    cfg = (await get_stage(dataset_id, "gate")).get("config") or {}
    saved = cfg.get("thresholds") or {}
    # 기본값은 프리셋의 축 집합이다. 범용 기본값으로 시작하면 SDS 축이 하나도 없어
    # 저장된 값이 전부 걸러지고(아래 `axis in merged`) 임계가 빈 dict 가 된다.
    merged = thresholds_for(await _preset_of(dataset_id))
    for axis, value in saved.items():
        if axis in merged:
            try:
                merged[axis] = float(value)
            except (TypeError, ValueError):
                pass
    return merged


async def get_gate_summary(dataset_id, thresholds=None):
    """게이트 현황 — 통과율 + 축별 미달 분포. 가장 많이 걸린 축이 다음에 고칠 곳."""
    await get_dataset(dataset_id)
    th = thresholds or await get_effective_thresholds(dataset_id)
    stats = await db.get_review_stats(dataset_id) or {}
    total = int(stats.get("total") or 0)
    fails = await db.get_gate_fail_distribution(dataset_id, th)
    # 통과율은 "한 축이라도 미달인 레코드"를 빼서 구한다. 축별 최대값을 쓰면 서로 다른
    # 축에서 떨어진 레코드가 빠져 통과율이 부풀고, 합을 쓰면 중복 계산된다.
    failed_total = await db.count_gate_failed(dataset_id, th)
    pass_rate = round((total - failed_total) * 100 / total) if total else 0
    top_axis = max(fails, key=fails.get) if fails else None
    return {
        "dataset_id": dataset_id,
        "axes": [dict(a) for a in axes_for(await _preset_of(dataset_id))],
        "thresholds": th,
        "total": total,
        "pass_rate": pass_rate,
        "pass_rate_range": list(PASS_RATE_RANGE),
        "pass_rate_flag": _pass_rate_flag(pass_rate),
        "fail_distribution": fails,
        "failed_total": failed_total,
        "top_fail_axis": top_axis,
    }


# ── 구성 · 분할 · 버전 ──────────────────────────────────────────────────────
def allocate(mix, pool):
    """가중치를 실제 건수로 바꾼다 (최대잉여법).

    내림만 하면 합이 풀보다 모자란다. 남은 1건씩을 **소수부가 큰 순서**로 나눠 준다.
    잔여분을 가중치 최대 유형에 통째로 몰면 풀이 작을 때 한쪽으로 쏠린다
    (동일 가중치 3종에 풀 2건이면 한 유형이 2건을 다 가져간다).
    """
    if not mix or pool <= 0:
        return {k: 0 for k in mix} if mix else {}
    total_weight = sum(mix.values())
    if total_weight <= 0:
        return {k: 0 for k in mix}

    exact = {k: pool * w / total_weight for k, w in mix.items()}
    counts = {k: math.floor(v) for k, v in exact.items()}
    remainder = pool - sum(counts.values())
    # 소수부 내림차순, 동률이면 키 순서로 — 같은 입력이면 항상 같은 결과가 나오게.
    for k in sorted(exact, key=lambda x: (-(exact[x] - counts[x]), x))[:remainder]:
        counts[k] += 1
    return counts


def _format_violation(record, fmt):
    """레코드 하나가 해당 학습 형식을 위반하는지. 위반이면 사람이 읽을 사유를 돌려준다."""
    q = record.get("question") or ""
    a = record.get("answer") or ""
    if not q or not a:
        return "질문 또는 답이 비어 있음 — 학습 샘플로 성립하지 않음"
    # 이미지 자리표시자 개수와 실제 참조 개수가 어긋나면 로더가 터진다.
    if fmt == "Qwen3-VL" and q.count("<image>") > 1:
        return "이미지 자리 표시가 2개 이상 — 참조 이미지와 개수 불일치"
    if fmt == "Gemma 3" and len(q) + len(a) > 8000:
        return "토큰 상한 초과 추정 — 질문+답 길이가 8,000자를 넘음"
    return None


async def verify_format(dataset_id, formats):
    """학습 형식 미리 검사.

    실제 학습 코드가 읽을 수 있는지 데이터셋을 만들기 전에 본다. 여기서 걸리면
    학습을 시작하고 몇 시간 뒤 죽는 대신 지금 고칠 수 있다.
    """
    await get_dataset(dataset_id)
    records = await db.list_records(dataset_id, limit=100000) or []
    total = len(records)

    results, failures = [], []
    for fmt in formats:
        bad = []
        for r in records:
            reason = _format_violation(r, fmt)
            if reason:
                bad.append({"record_key": r.get("record_key"), "format": fmt, "reason": reason})
        results.append({
            "format": fmt,
            "passed": total - len(bad),
            "total": total,
            "tone": "green" if not bad else "orange",
        })
        failures.extend(bad[:5])
    return {"dataset_id": dataset_id, "results": results, "failures": failures[:10]}


async def list_versions(dataset_id):
    ds = await get_dataset(dataset_id)
    versions = await db.list_versions(dataset_id) or []
    # 산출물 위치는 규약(releases/{version})으로 정해지므로 컬럼을 늘리지 않는다. 다만
    # **파일이 실제로 있는지**는 봐야 한다 — DB 행만 남고 디렉터리가 지워진 버전을
    # 받을 수 있는 것처럼 보여주면 안 된다(옛 릴리스는 파일 자체가 없다).
    try:
        work_root = await _work_dataset_root_of(ds)
    except Exception:  # noqa: BLE001 - 작업 데이터셋이 없으면 그냥 경로를 비운다
        work_root = None
    for v in versions:
        rel = os.path.join(RELEASE_DIR, v["version"])
        v["export_dir"] = rel
        v["export_ready"] = bool(
            work_root and os.path.isfile(os.path.join(work_root, rel, "manifest.json")))
    # 직전 버전 대비 증감을 함께 준다 — 버전 목록은 "무엇이 나아졌나"를 보는 화면이다.
    prev = None
    for v in versions:
        v["delta"] = {} if prev is None else {
            "record_count": (v.get("record_count") or 0) - (prev.get("record_count") or 0),
            "pass_rate": (v.get("pass_rate") or 0) - (prev.get("pass_rate") or 0),
            "human_reviewed": (v.get("human_reviewed") or 0) - (prev.get("human_reviewed") or 0),
        }
        # 생성 모델과 심사 모델이 같은 채로 만들어진 버전은 신뢰할 수 없다고 표시한다.
        v["same_model"] = bool(v.get("gen_model")) and v.get("gen_model") == v.get("judge_model")
        prev = v
    return {"dataset_id": dataset_id, "versions": versions}


# ── 릴리스 산출물 ───────────────────────────────────────────────────────────
# 릴리스는 DB 행이 아니라 **파일**이 본체다. 통계는 확정 저장되지만 레코드 내용은
# 재검수로 바뀌므로, 그 시점의 내용을 물리적으로 써서 고정한다.
RELEASE_DIR = "releases"
RELEASE_IMAGE_DIR = "images"

# 우리 VLM 학습기(llm_model_vlm_fine_tuning.py)가 읽는 평면 스키마.
#   image       — **데이터셋 파일 디렉터리 기준 상대경로**. realpath+commonpath 로 봉쇄돼
#                 있어 `..` 도 심볼릭 링크도 거부된다 → 이미지는 실파일(하드링크)로 둔다.
#   instruction — 리터럴 이미지 토큰은 콜레이터가 지우고 자기가 placeholder 를 넣는다.
#                 그래서 평면 포맷에는 `<image>` 를 넣지 않는다(LLaVA 쪽은 필요하므로 넣는다).
#   output      — 학습 타깃.
RELEASE_FILES = {
    "train": "train.jsonl",
    "validation": "validation.jsonl",
    "test": "test.jsonl",
}
IMAGE_TOKEN = "<image>"


def _strip_image_token(text):
    return (text or "").replace(IMAGE_TOKEN, " ").strip()


def _release_group_key(rec, split_by):
    """분할 그룹 키. 같은 그룹은 절대 갈라지지 않는다.

    기본이 문서 ID 인 이유: 같은 문서(같은 장면)의 다른 프레임이 train 과 test 로
    갈리면 사실상 정답을 미리 본 셈이라 평가 점수가 부풀려진다.
    """
    lin = rec.get("lineage") or {}
    if split_by == "이미지":
        return str(rec.get("asset_ref") or rec.get("record_key"))
    if split_by == "무작위":
        return str(rec.get("record_key") or rec.get("id"))
    # 문서 ID(기본) — 해양은 장면, 문서형은 원본 파일이 그 단위다.
    return str(lin.get("scene_id") or lin.get("src") or rec.get("asset_ref")
               or rec.get("record_key"))


def _assign_splits(records, split_ratio, split_by):
    """레코드 → split. 그룹 단위로 배정하며 같은 입력이면 항상 같은 결과가 나온다.

    난수를 쓰지 않는 이유: 릴리스는 재현 가능해야 한다. 그룹 키 해시로 순서를 고정하고
    남은 목표 건수가 가장 많은 split 에 그룹을 넣는다(그룹 크기가 달라도 총량이 목표에
    가장 가깝게 수렴한다).
    """
    groups = {}
    for rec in records:
        groups.setdefault(_release_group_key(rec, split_by), []).append(rec)
    targets = allocate(split_ratio, len(records)) if split_ratio else {}
    if not targets:
        targets = {"train": len(records)}
    remain = dict(targets)
    out = {}
    for key in sorted(groups, key=lambda k: hashlib.md5(k.encode("utf-8")).hexdigest()):
        # 남은 목표가 가장 큰 split 로. 동률이면 SPLITS 순서로 — 결정성 유지.
        target_split = max(remain, key=lambda sp: (remain[sp], -list(remain).index(sp)))
        for rec in groups[key]:
            out[rec["id"]] = target_split
        remain[target_split] -= len(groups[key])
    return out, targets


def _release_selection(records, thresholds):
    """릴리스에 담을 레코드. 담은 이유·뺀 이유를 함께 돌려준다(manifest 감사용).

    규칙: 사람이 반려한 것은 무조건 뺀다. 사람이 승인·수정한 것은 게이트 점수와
    무관하게 담는다(사람 판단이 판사보다 위다). 나머지는 게이트 통과분만.
    게이트 미달을 그대로 담으면 게이트가 장식이 된다.
    """
    kept, dropped = [], {"rejected": 0, "gate_failed": 0}
    for rec in records:
        state = rec.get("review_state")
        if state == "rejected":
            dropped["rejected"] += 1
            continue
        if state in ("approved", "edited"):
            kept.append(rec)
            continue
        scores = rec.get("scores") or {}
        if all(float(scores.get(ax, -1)) >= th for ax, th in thresholds.items()):
            kept.append(rec)
        else:
            dropped["gate_failed"] += 1
    return kept, dropped


def _link_or_copy(src, dst):
    """하드링크 우선, 안 되면 복사. 심볼릭 링크는 쓰지 않는다 — 학습기가 realpath 로
    봉쇄를 검사하므로 링크 대상이 릴리스 디렉터리 밖이면 그 이미지는 조용히 스킵된다."""
    if os.path.exists(dst):
        return "reused"
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def _write_release_files(release_dir, records, splits, work_root):
    """평면 jsonl(우리 학습기) + LLaVA json(프로토타입·외부 트레이너) + images/ 를 쓴다."""
    img_dir = os.path.join(release_dir, RELEASE_IMAGE_DIR)
    os.makedirs(img_dir, exist_ok=True)

    by_split = {sp: [] for sp in SPLITS}
    snapshot, llava, image_stat = [], [], {"linked": 0, "copied": 0, "reused": 0, "missing": 0}

    for rec in records:
        split = splits.get(rec["id"], "train")
        asset_ref = rec.get("asset_ref") or ""
        image_rel = None
        if asset_ref:
            src = os.path.join(work_root, asset_ref)
            if os.path.isfile(src):
                # 파일명 충돌 방지: 레코드 키를 파일명에 넣는다(같은 프레임이 언어별로
                # 여러 레코드가 되므로 원본 파일명만 쓰면 서로 덮어쓴다).
                base = f"{rec['record_key'].replace(':', '_').replace('/', '_')}" \
                       f"{os.path.splitext(src)[1] or '.jpg'}"
                image_stat[_link_or_copy(src, os.path.join(img_dir, base))] += 1
                image_rel = f"{RELEASE_IMAGE_DIR}/{base}"
            else:
                image_stat["missing"] += 1

        instruction = _strip_image_token(rec.get("question"))
        answer = rec.get("answer") or ""
        flat = {
            "id": rec["record_key"], "image": image_rel,
            "instruction": instruction, "output": answer,
            "split": split, "capability": rec.get("capability"),
            "review_state": rec.get("review_state"), "scores": rec.get("scores") or {},
        }
        snapshot.append(flat)
        if image_rel:
            by_split.setdefault(split, []).append(flat)
            llava.append({
                "id": rec["record_key"], "image": image_rel,
                "conversations": [
                    {"from": "human", "value": f"{IMAGE_TOKEN}\n{instruction}"},
                    {"from": "gpt", "value": answer},
                ],
            })

    def _dump_jsonl(name, rows):
        with open(os.path.join(release_dir, name), "w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    _dump_jsonl("records.jsonl", snapshot)
    for split, name in RELEASE_FILES.items():
        _dump_jsonl(name, by_split.get(split) or [])
    with open(os.path.join(release_dir, "llava.json"), "w", encoding="utf-8") as fp:
        json.dump(llava, fp, ensure_ascii=False, indent=2)

    counts = {sp: len(by_split.get(sp) or []) for sp in SPLITS}
    # 이미지가 없는 레코드는 학습에 못 쓴다(VLM 이므로 이미지 필수) — 스냅샷에는 남기되
    # 분할 파일에서는 빠지므로, 그 차이를 감춰선 안 된다.
    return {"counts": counts, "images": image_stat,
            "trainable": sum(counts.values()), "snapshot": len(snapshot)}


async def create_version(dataset_id, version, mix, split, split_by):
    """릴리스. **파일을 먼저 쓰고** DB 행을 남긴다.

    순서가 중요하다: 행을 먼저 쓰면 파일 산출이 실패했을 때 "릴리스됐다고 나오는데
    받을 것이 없는" 버전이 남는다. 파일이 본체이므로 파일이 먼저다.
    """
    ds = await get_dataset(dataset_id)
    if await db.version_exists(dataset_id, version):
        raise Conflict(f"이미 있는 버전입니다: {version}")

    thresholds = await get_effective_thresholds(dataset_id)
    all_records = await db.list_records_for_release(dataset_id)
    if not all_records:
        raise Conflict("적재된 레코드가 없습니다 — 심사를 먼저 실행하세요")

    kept, dropped = _release_selection(all_records, thresholds)
    if not kept:
        raise Conflict(
            f"릴리스할 레코드가 없습니다 — 게이트 미달 {dropped['gate_failed']}건 · "
            f"반려 {dropped['rejected']}건. 임계값을 조정하거나 검수로 승인하세요")

    # 구성(mix)은 유형별 상한이다. 상한에 걸리면 **점수 높은 순**으로 남긴다.
    split_ratio = split or dict(DEFAULT_SPLIT)
    resolved_mix = allocate(mix, len(kept)) if mix else {}
    if resolved_mix:
        by_cap, picked = {}, []
        for rec in kept:
            by_cap.setdefault(rec.get("capability") or "", []).append(rec)
        for cap, cap_recs in by_cap.items():
            limit = resolved_mix.get(cap)
            cap_recs.sort(key=lambda r: (-(float(r.get("worst_score") or 0)), r["id"]))
            picked += cap_recs if limit is None else cap_recs[:limit]
        kept = sorted(picked, key=lambda r: r["id"])

    splits, split_targets = _assign_splits(kept, split_ratio, split_by or DEFAULT_SPLIT_BY)

    work_root = await _work_dataset_root_of(ds)
    release_dir = os.path.join(work_root, RELEASE_DIR, version)
    if os.path.isdir(release_dir) and os.listdir(release_dir):
        # write-once. 같은 이름으로 덮어쓰면 이미 받아간 사람의 데이터셋과 내용이
        # 달라지는데 버전 이름은 같아, 재현이 불가능해진다.
        raise Conflict(f"릴리스 디렉터리가 이미 있습니다: {RELEASE_DIR}/{version}")
    os.makedirs(release_dir, exist_ok=True)

    written = _write_release_files(release_dir, kept, splits, work_root)
    if not written["trainable"]:
        raise Conflict("이미지가 있는 레코드가 없어 학습에 쓸 수 없습니다 "
                       "(VLM 학습은 이미지가 필수입니다)")

    gate = await get_gate_summary(dataset_id, thresholds)
    cfg = (await get_stage(dataset_id, "generate")).get("config") or {}
    source_runs = await db.get_source_runs(dataset_id)
    human = sum(1 for r in kept if r.get("review_state") in ("approved", "edited"))

    manifest = {
        "version": version, "dataset_id": dataset_id,
        "dataset_name": ds.get("name"), "preset": ds.get("preset"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "record_count": len(kept), "snapshot_count": written["snapshot"],
        "trainable_count": written["trainable"],
        "split": {"ratio": split_ratio, "by": split_by or DEFAULT_SPLIT_BY,
                  "targets": split_targets, "counts": written["counts"]},
        "mix": {"weights": mix, "counts": resolved_mix},
        "selection": {"rule": "반려 제외 · 승인/수정 무조건 포함 · 나머지는 게이트 통과분",
                      "candidates": len(all_records), "kept": len(kept),
                      "dropped": dropped},
        "thresholds": thresholds, "pass_rate": gate.get("pass_rate") or 0,
        "human_reviewed": human,
        "gen_model": cfg.get("generator_model"), "judge_model": cfg.get("judge_model"),
        "source_runs": source_runs,
        "images": written["images"],
        "files": {"snapshot": "records.jsonl", "llava": "llava.json",
                  **{k: v for k, v in RELEASE_FILES.items()},
                  "image_dir": RELEASE_IMAGE_DIR},
        "trainer_contract": {
            "reader": "llm_model_vlm_fine_tuning.load_vlm_samples",
            "keys": ["image", "instruction", "output"],
            "image_path": "릴리스 디렉터리 기준 상대경로(images/…). 심볼릭 링크 불가",
        },
    }
    with open(os.path.join(release_dir, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)

    # 분할을 레코드에도 새긴다 — 다음 릴리스·누수 검증이 이 값을 본다.
    await db.set_record_splits([(sp, rid) for rid, sp in splits.items()])

    await db.create_version(
        dataset_id=dataset_id, version=version,
        record_count=len(kept), pass_rate=gate.get("pass_rate") or 0,
        human_reviewed=human,
        gen_model=cfg.get("generator_model"), judge_model=cfg.get("judge_model"),
        prompt_name=cfg.get("prompt_name"), thresholds=thresholds,
        mix={"weights": mix, "counts": resolved_mix},
        split={"ratio": split_ratio, "counts": written["counts"]},
        split_by=split_by or DEFAULT_SPLIT_BY,
        source_runs=source_runs)

    result = await list_versions(dataset_id)
    result["released"] = {
        "version": version,
        "dir": os.path.join(RELEASE_DIR, version),
        "record_count": len(kept), "trainable": written["trainable"],
        "counts": written["counts"], "images": written["images"],
        "dropped": dropped,
    }
    return result


# ── 실행 이력 조회 ───────────────────────────────────────────────────────────
async def list_runs(dataset_id, node_index=None, limit=50):
    """실행 이력(최신순). 화면이 "언제 뭘 돌렸고 어떻게 끝났는지" 를 여기서 본다."""
    await get_dataset(dataset_id)
    runs = await db.list_runs(dataset_id, node_index=node_index, limit=limit) or []
    # 목록에는 funnel 전문을 싣지 않는다 — 실행 50건이면 단계 수백 개가 따라와
    # 응답이 커지는데, 목록에서 쓰는 건 카운트뿐이다. 전문은 단건 조회에 있다.
    # 다만 통과 건수는 funnel 에서만 나오므로 **버리기 전에** 뽑는다(심사 노드는
    # 미달을 버리지 않아 out_count 가 통과 건수와 다르다).
    for r in runs:
        r["passed"] = _passed_of(r)
        r.pop("funnel", None)
    return {
        "dataset_id": dataset_id,
        "node_index": node_index,
        "runs": runs,
    }


async def get_run(dataset_id, run_id):
    """실행 단건 + funnel 전문(단계별 in/out/dropped)."""
    await get_dataset(dataset_id)
    run = await db.get_run(dataset_id, run_id)
    if not run:
        raise NotFound(f"실행을 찾을 수 없습니다: {run_id}")
    return run


# ── 산출물 미리보기 · 비교 ───────────────────────────────────────────────────
# 노드가 무엇을 남기는지: assets.jsonl(통과) · drops.jsonl(제외) · samples/(썸네일) ·
# config.json(이 실행의 설정) · funnel.json(단계별 카운트).
# AIS 노드처럼 이미지가 없는 노드는 통과분이 scenes.jsonl 로 나온다.
# AIS 갈래의 중간 노드(적재·행 정제)는 씬이 되기 전이라 통과분이 rows.jsonl 이다.
PASSED_FILES = ("assets.jsonl", "scenes.jsonl", "rows.jsonl", "records.jsonl")
DROPS_FILE = "drops.jsonl"
# 한 번에 내려줄 상한. 화면은 스크롤하며 offset 으로 더 가져간다.
PREVIEW_MAX = 200


async def _run_output_dir(dataset_id, run):
    """실행 산출물의 절대 경로. 작업 데이터셋 밖으로 나가면 거부한다.

    out_dir 은 우리가 만든 값이지만 DB 를 거쳐 오므로, 값이 바뀌면 임의 경로를 읽는
    통로가 된다. 실제 파일을 열기 전에 작업 데이터셋 안인지 확인한다.
    """
    ds = await get_dataset(dataset_id)
    name = ds.get("work_dataset_name")
    if not name:
        raise NotFound("작업 데이터셋이 아직 없습니다")
    storage_name = await db.get_workspace_storage_name(ds["workspace_id"])
    if not storage_name:
        raise Conflict("워크스페이스에 data 스토리지가 없습니다")
    work_root = os.path.realpath(
        _work_dataset_root(storage_name, ds["workspace_name"], WORK_DATASET_ACCESS, name))
    out_dir = os.path.realpath(os.path.join(work_root, run["out_dir"]))
    if os.path.commonpath([out_dir, work_root]) != work_root:
        raise ValueError("산출물 경로가 작업 데이터셋을 벗어납니다")
    return out_dir


def _read_jsonl_page(path, limit, offset):
    """(전체 건수, 그 구간). 한 줄씩 읽어 큰 파일도 메모리를 물지 않는다."""
    if not os.path.isfile(path):
        return 0, []
    items, total = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            if total > offset and len(items) < limit:
                try:
                    items.append(json.loads(line))
                except ValueError:
                    # 잡이 쓰는 도중이면 마지막 줄이 잘려 있을 수 있다. 건너뛰되
                    # 건수에는 넣지 않는다(화면의 total 과 목록이 어긋나지 않게).
                    total -= 1
    return total, items


def _drop_reasons(path):
    """사유별 건수. 제외 목록을 다 내려보내지 않아도 왜 빠졌는지 한눈에 보이게."""
    counts = {}
    if not os.path.isfile(path):
        return counts
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                reason = json.loads(line).get("reason") or "unknown"
            except ValueError:
                continue
            counts[reason] = counts.get(reason, 0) + 1
    return counts


async def preview_run(dataset_id, run_id, kind="passed", limit=50, offset=0):
    """실행 산출물 미리보기 — 노드 드로어의 '통과' · '제외' 열.

    '입력' 열은 상류 실행의 통과분이므로 별도 엔드포인트를 두지 않는다. 화면이 같은
    미리보기를 상류 run_id 로 한 번 더 부르면 된다(그래야 노드가 늘어도 API 가 안 는다).
    """
    run = await db.get_run(dataset_id, run_id)
    if not run:
        raise NotFound(f"실행을 찾을 수 없습니다: {run_id}")
    limit = max(1, min(int(limit), PREVIEW_MAX))
    offset = max(0, int(offset))
    out_dir = await _run_output_dir(dataset_id, run)

    if kind == "dropped":
        path = os.path.join(out_dir, DROPS_FILE)
        total, items = _read_jsonl_page(path, limit, offset)
        payload = {"reasons": _drop_reasons(path)}
    else:
        kind = "passed"
        path = next((p for p in (os.path.join(out_dir, n) for n in PASSED_FILES)
                     if os.path.isfile(p)), os.path.join(out_dir, PASSED_FILES[0]))
        total, items = _read_jsonl_page(path, limit, offset)
        payload = {"source_file": os.path.basename(path)}
        # 썸네일이 실제로 있는 자산만 표시한다. 노드가 앞부분 일부만 만들기 때문에
        # (전량 만들면 용량이 터진다) 없는 것을 링크로 걸면 깨진 이미지가 뜬다.
        samples = os.path.join(out_dir, "samples")
        have = set(os.listdir(samples)) if os.path.isdir(samples) else set()
        for it in items:
            aid = it.get("asset_id")
            it["has_thumb"] = bool(aid) and f"{aid}.jpg" in have

    return {
        "dataset_id": dataset_id, "run_id": run_id, "stage": run["stage"],
        "node_index": run["node_index"], "status": run["status"],
        "kind": kind, "total": total, "limit": limit, "offset": offset,
        "items": items, **payload,
    }


async def run_thumb_path(dataset_id, run_id, asset_id):
    """썸네일 파일의 절대 경로. asset_id 가 경로로 해석되지 않게 막는다."""
    if not asset_id or "/" in asset_id or "\\" in asset_id or asset_id.startswith("."):
        raise ValueError("잘못된 asset_id 입니다")
    run = await db.get_run(dataset_id, run_id)
    if not run:
        raise NotFound(f"실행을 찾을 수 없습니다: {run_id}")
    out_dir = await _run_output_dir(dataset_id, run)
    samples = os.path.realpath(os.path.join(out_dir, "samples"))
    path = os.path.realpath(os.path.join(samples, f"{asset_id}.jpg"))
    if os.path.commonpath([path, samples]) != samples:
        raise ValueError("썸네일 경로가 산출물 디렉터리를 벗어납니다")
    if not os.path.isfile(path):
        raise NotFound(f"썸네일이 없습니다: {asset_id}")
    return path


async def record_image_path(dataset_id, record_id):
    """검수 화면이 보여줄 **레코드 원본 이미지**의 절대 경로.

    썸네일 경로(`/runs/{run_id}/thumb/{asset_id}`)를 쓰지 않는 이유가 셋 있다.
      1. 노드는 앞부분 일부만 썸네일로 만든다(100건 중 24건). 검수 큐는 점수 낮은
         순이라 리뷰어가 실제로 여는 레코드가 표본에 없을 확률이 오히려 높다.
      2. 레코드의 `asset_ref` 는 슬래시를 포함한 경로인데 그 엔드포인트는 단일
         세그먼트 asset_id 만 받는다(경로 주입 차단).
      3. 화면이 run_id 와 경로를 스스로 조립해야 해서, 검수 큐 응답에 계보를 실어야
         한다. 무엇을 어디서 읽을지는 BE 가 이미 알고 있으므로 여기서 끝낸다.

    asset_ref 는 작업 데이터셋 루트 기준 상대경로다. DB 를 거쳐 오는 값이라 파일을
    열기 전에 작업 데이터셋 안인지 반드시 확인한다.
    """
    ds = await get_dataset(dataset_id)
    record = await db.get_record(record_id)
    if not record or int(record.get("dataset_id") or 0) != int(dataset_id):
        raise NotFound(f"레코드를 찾을 수 없습니다: {record_id}")
    asset_ref = (record.get("asset_ref") or "").strip()
    if not asset_ref:
        raise NotFound("이 레코드에는 이미지가 없습니다")

    work_root = os.path.realpath(await _work_dataset_root_of(ds))
    path = os.path.realpath(os.path.join(work_root, asset_ref))
    if os.path.commonpath([path, work_root]) != work_root:
        raise ValueError("이미지 경로가 작업 데이터셋을 벗어납니다")
    if not os.path.isfile(path):
        # 실행 산출물이 정리됐을 수 있다 — 어느 경로를 찾았는지 말해 준다.
        raise NotFound(f"이미지 파일이 없습니다: {asset_ref}")
    return path


def _config_diff(a, b):
    """두 실행의 설정 차이. 무엇을 바꿔서 결과가 달라졌는지가 비교의 핵심이다."""
    def flat(cfg):
        out = {}
        for name, params in ((s[0], s[1] if len(s) > 1 else {})
                             for s in (cfg or {}).get("steps") or []
                             if isinstance(s, (list, tuple)) and s):
            out[name] = params or {}
        return out

    fa, fb = flat(a), flat(b)
    changed = []
    for name in sorted(set(fa) | set(fb)):
        if name not in fa:
            changed.append({"step": name, "change": "added", "a": None, "b": fb[name]})
        elif name not in fb:
            changed.append({"step": name, "change": "removed", "a": fa[name], "b": None})
        elif fa[name] != fb[name]:
            changed.append({"step": name, "change": "param", "a": fa[name], "b": fb[name]})
    return changed


def _funnel_diff(a, b):
    """단계별 in/out 차이. 단계 구성이 다르면 이름 기준으로 맞춘다."""
    sa = {s["stage"]: s for s in (a or {}).get("funnel") or []}
    sb = {s["stage"]: s for s in (b or {}).get("funnel") or []}
    rows = []
    for name in list(sa) + [n for n in sb if n not in sa]:
        x, y = sa.get(name), sb.get(name)
        rows.append({
            "stage": name,
            "a": {"in": (x or {}).get("in"), "out": (x or {}).get("out"),
                  "dropped": (x or {}).get("dropped")} if x else None,
            "b": {"in": (y or {}).get("in"), "out": (y or {}).get("out"),
                  "dropped": (y or {}).get("dropped")} if y else None,
            "delta_out": (None if not (x and y)
                          else (y.get("out") or 0) - (x.get("out") or 0)),
        })
    return rows


async def compare_runs(dataset_id, run_a, run_b):
    """두 실행 A/B 비교 — '기능을 넣었다 뺐다' 한 결과가 어떻게 달라졌는지.

    설정(config.json)을 산출물 옆에 남겨 두는 이유가 여기다. 이게 없으면 두 결과를
    나란히 놓아도 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    """
    runs = []
    for rid in (run_a, run_b):
        run = await db.get_run(dataset_id, rid)
        if not run:
            raise NotFound(f"실행을 찾을 수 없습니다: {rid}")
        runs.append(run)
    ra, rb = runs
    if ra["node_index"] != rb["node_index"]:
        raise Conflict(
            f"서로 다른 노드의 실행은 비교할 수 없습니다 "
            f"(n{ra['node_index']} {ra['stage']} vs n{rb['node_index']} {rb['stage']})")

    cfgs = []
    for run in runs:
        out_dir = await _run_output_dir(dataset_id, run)
        path = os.path.join(out_dir, "config.json")
        try:
            with open(path, encoding="utf-8") as f:
                cfgs.append(json.load(f))
        except (OSError, ValueError):
            cfgs.append({})

    return {
        "dataset_id": dataset_id,
        "node_index": ra["node_index"],
        "stage": ra["stage"],
        "a": {**_run_brief(ra), "config": cfgs[0]},
        "b": {**_run_brief(rb), "config": cfgs[1]},
        "config_diff": _config_diff(cfgs[0], cfgs[1]),
        "funnel_diff": _funnel_diff(ra.get("funnel"), rb.get("funnel")),
        "delta": {
            "in": (rb.get("in_count") or 0) - (ra.get("in_count") or 0),
            "out": (rb.get("out_count") or 0) - (ra.get("out_count") or 0),
            # 심사 노드는 미달을 버리지 않아 out 이 통과 건수가 아니다 — 통과 증감을
            # 따로 준다. 이게 없으면 임계값을 바꿔 비교해도 증감이 항상 0 으로 보인다.
            "passed": (_passed_of(rb) or 0) - (_passed_of(ra) or 0),
            "dropped": (rb.get("dropped_count") or 0) - (ra.get("dropped_count") or 0),
        },
    }


# ── 생성·심사용 VLM 서빙(자동 배포·회수) ────────────────────────────────────
# 카탈로그의 모델 id 는 이름표일 뿐 실행 중인 서빙을 가리키지 않는다. 생성·심사 노드가
# 추론을 하려면 실제 배포가 있어야 하므로, BE 가 필요한 시점에 띄우고 끝나면 회수한다.
#
# 배포 주체가 잡이 아니라 BE 인 이유: 잡이 직접 띄우면 잡이 죽는 순간 배포가 고아가 되고
# (아무도 내리지 않아 GPU 가 영영 잠긴다), 잡 파드에 플랫폼 배포 권한을 새로 뚫어야 한다.
# BE 는 이미 실행 이력 리콘사일러를 돌리고 있으므로 회수를 거기에 얹는다.
_PLAYGROUND_BASE = "http://{host}:{port}/api/playgrounds".format(
    host=os.getenv("JFB_LLM_PLAYGROUND_SVC_SERVICE_HOST", "jfb-llm-playground-svc"),
    port=os.getenv("JFB_LLM_PLAYGROUND_SVC_SERVICE_PORT", "80"))

# 역할 → (모델을 고르는 단계, 설정 키). 생성 모델 == 심사 모델이면 맹점이 겹쳐 게이트가
# 무의미해지는데, 그것은 judge_model_pairing 이 설정 단계에서 이미 막는다.
# 두 역할 모두 **생성 단계** 설정에서 읽는다 — 심사 모델도 GenerateConfigBody 에 있다
# (심사 단계 설정은 임계값만 쥔다). 심사 노드에서 찾으면 영영 비어 있다.
SERVING_ROLE_SOURCE = {
    "generator": ("generate", "generator_model"),
    "judge": ("generate", "judge_model"),
}
SERVING_POLL_S = 10
# 가중치 내려받기 + 엔진 기동까지. huggingface 콜드 스타트가 길어 넉넉히 잡는다.
SERVING_READY_TIMEOUT_S = 30 * 60
# 이 데이터셋에 도는 실행이 하나도 없는 채로 이만큼 지나면 회수한다. 실행 중에는
# 회수하지 않는다 — 노드는 서빙을 내부 DNS 로 직접 부르므로 BE 에 호출 기록이 남지 않아,
# 시간만 보고 판단하면 한 시간짜리 잡을 도중에 끊는다.
SERVING_IDLE_RECLAIM_S = 30 * 60
# deployment_llm 차트 service 포트.
SERVING_PORT = 18555
# 중지 요청 후 파드가 실제로 사라지기까지 기다리는 상한. 이보다 오래 걸리면 배포가
# 비정상이므로, 계속 붙들고 있지 말고 다음 단계로 넘어가 사유를 남긴다.
TEARDOWN_WAIT_S = 120


async def _playground_post(path, body, jf_user):
    """playground MSA 호출. 실패 사유를 그대로 올려 사용자가 원인을 본다."""
    async with aiohttp.ClientSession() as session:
        async with session.post(_PLAYGROUND_BASE + path, json=body,
                                headers={"Jf-User": jf_user or ""},
                                timeout=aiohttp.ClientTimeout(total=180)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"playground {path} HTTP {resp.status}: {text[:300]}")
            data = json.loads(text)
    if not data.get("status"):
        raise RuntimeError(f"playground {path}: {data.get('message')}")
    return data.get("result") or {}


async def _playground_get(path, jf_user):
    async with aiohttp.ClientSession() as session:
        async with session.get(_PLAYGROUND_BASE + path,
                               headers={"Jf-User": jf_user or ""},
                               timeout=aiohttp.ClientTimeout(total=60)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"playground {path} HTTP {resp.status}: {text[:300]}")
            data = json.loads(text)
    if not data.get("status"):
        raise RuntimeError(f"playground {path}: {data.get('message')}")
    return data.get("result") or {}


def serving_endpoint(playground_id, workspace_id):
    """노드가 때릴 추론 주소.

    인그레스(`/deployment/{api_path}`)가 아니라 **클러스터 내부 DNS** 를 준다. 노드 잡과
    서빙 배포가 같은 워크스페이스 네임스페이스에 있으므로, 내부로 부르면 인그레스·Kong·
    인증을 통째로 우회한다(잡에 자격증명을 넘길 필요가 없어진다).

    래퍼 계약: POST / 에 {"test_type":"question","test_question":..., "images":[base64...]}.
    """
    ns = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    return f"http://deployment-llm-playground-{playground_id}--service.{ns}:{SERVING_PORT}/"


def _catalog_model(model_id):
    """카탈로그에서 배포에 필요한 것(hf_id·VRAM)을 꺼낸다."""
    for m in GENERATION_MODELS:
        if m["id"] == model_id:
            if not m.get("hf_id"):
                raise Conflict(f"'{m['name']}' 은 배포 경로가 없는 모델입니다")
            # 후보에서 빼기 전에 저장된 설정이 남아 있을 수 있다. 그대로 띄우면 배포는
            # 성공하고 추론만 전량 400 이 되므로, 30분 콜드 스타트를 태우기 전에 끊는다.
            if not m.get("vision"):
                raise Conflict(f"'{m['name']}' 은 이미지 입력을 받지 못하는 모델입니다"
                               "(서빙이 멀티모달 프로세서를 만들지 못함) — "
                               "생성 단계에서 다른 모델을 고르세요")
            return m
    raise NotFound(f"카탈로그에 없는 모델입니다: {model_id}")


async def _role_model_id(dataset_id, role):
    """역할에 해당하는 단계 설정에서 모델 id 를 읽는다."""
    stage, key = SERVING_ROLE_SOURCE[role]
    nodes = await db.get_flow(dataset_id) or []
    node = _find_stage_node(nodes, stage)
    if node is None:
        raise NotFound(f"'{stage}' 단계 노드가 파이프라인에 없습니다")
    model_id = (node.get("config") or {}).get(key)
    if not model_id:
        raise Conflict(f"'{stage}' 단계에서 모델을 먼저 고르세요")
    return model_id


async def _playground_status(playground_id, jf_user):
    """s2s 폴링용 단건 상태. SSE 는 파싱할 수 없어 이 경로가 따로 있다."""
    res = await _playground_get(f"/status-sync/{playground_id}", jf_user)
    return res.get("status")


# playground 가 없을 때 llm_playground 가 돌려주는 문구. 조회 자체가 실패한 것과
# 배포가 사라진 것을 가려내는 유일한 단서라 여기 한 곳에 모아 둔다.
PLAYGROUND_GONE_MARK = "not exist"
PLAYGROUND_GONE_LIMIT = 3


def _playground_gone(exc):
    """배포가 더 이상 존재하지 않아서 난 오류인가(일시적 조회 실패와 구분)."""
    return PLAYGROUND_GONE_MARK in str(exc).lower()


async def _playground_delete(path, jf_user):
    async with aiohttp.ClientSession() as session:
        async with session.delete(_PLAYGROUND_BASE + path,
                                  headers={"Jf-User": jf_user or ""},
                                  timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"playground DELETE {path} HTTP {resp.status}: {text[:300]}")
            data = json.loads(text)
    if not data.get("status"):
        raise RuntimeError(f"playground DELETE {path}: {data.get('message')}")
    return data.get("result")


async def _teardown_playground(playground_id, jf_user):
    """배포를 내리고 껍데기까지 지운다.

    중지만 하면 GPU 는 돌아오지만 playground 행이 남는다. 자동 배포는 매번 새로 만들므로
    (pipeline_deploy 가 create 부터 한다) 중지만 반복하면 쓰지 않는 배포 껍데기가 목록에
    계속 쌓여 사용자가 자기가 만든 배포를 그 사이에서 못 찾는다.

    실패해도 호출부를 막지 않는다 — 회수는 최선 노력이고, GPU 를 돌려주는 stop 이 먼저
    끝나기만 하면 목적은 달성된다. 남은 껍데기는 다음 주기가 다시 지운다.
    """
    try:
        await _playground_post("/stop", {"playground_id": playground_id}, jf_user)
    except Exception:  # noqa: BLE001
        logging.warning("[dp-serving] stop 실패 playground=%s", playground_id, exc_info=True)

    # 중지 요청이 돌아왔다고 GPU 가 돌아온 것은 아니다 — 파드가 사라져야 쿼터가 풀린다.
    # 여기서 기다리지 않으면 곧바로 이어지는 배포가 "지금 GPU 여유가 없습니다" 로 거절된다
    # (모델을 바꿔 재배포하는 경로가 스스로 물리는 자리다).
    for _ in range(TEARDOWN_WAIT_S // SERVING_POLL_S):
        try:
            if await _playground_status(playground_id, jf_user) != "running":
                break
        except Exception:  # noqa: BLE001 - 조회가 안 되면 이미 사라진 것으로 본다
            break
        await asyncio.sleep(SERVING_POLL_S)
    else:
        logging.warning("[dp-serving] 중지 확인 시간초과 playground=%s", playground_id)

    try:
        await _playground_delete(f"/{playground_id}", jf_user)
    except Exception:  # noqa: BLE001
        logging.warning("[dp-serving] delete 실패 playground=%s", playground_id, exc_info=True)


# 같은 (데이터셋, 역할) 의 준비를 직렬화한다. 두 실행 요청이 죽은 ready 배포를 동시에
# 발견하면 각자 teardown + 배포를 해서, 나중 기록이 앞선 playground_id 를 덮어쓰고 그
# 배포가 장부 밖 고아로 GPU 를 문다 — upsert 를 배포보다 먼저 하는 이유(고아 방지)와 같은
# 취지다. 이 서비스는 레플리카 1개 전제이며, 다중 레플리카로 가면 외부 컨테이너 GPU 경합에
# 쓰는 Redis SETNX 방식으로 올려야 한다.
_SERVING_LOCKS = {}


def _serving_lock(dataset_id, role):
    key = (dataset_id, role)
    lock = _SERVING_LOCKS.get(key)
    if lock is None:
        lock = _SERVING_LOCKS[key] = asyncio.Lock()
    return lock


async def ensure_serving(dataset_id, role, jf_user=None):
    """역할당 준비를 하나씩만 돌린다. 실제 준비는 _ensure_serving."""
    if role not in SERVING_ROLE_SOURCE:
        raise ValueError(f"알 수 없는 역할입니다: {role}")
    async with _serving_lock(dataset_id, role):
        return await _ensure_serving(dataset_id, role, jf_user)


async def _ensure_serving(dataset_id, role, jf_user=None):
    """역할(generator|judge)에 맞는 VLM 서빙을 준비하고 노드가 쓸 주소를 돌려준다.

    이미 같은 모델이 살아 있으면 그대로 쓴다 — 콜드 스타트가 수 분이라, 노드마다 다시
    띄우면 실행 시간이 배포 대기로 채워진다.
    """
    ds = await get_dataset(dataset_id)
    if not ds:
        raise NotFound(f"데이터셋이 없습니다: {dataset_id}")
    model_id = await _role_model_id(dataset_id, role)
    model = _catalog_model(model_id)
    user = jf_user or ds.get("create_user") or ""

    existing = await db.get_serving(dataset_id, role)
    if (existing and existing.get("status") == "ready"
            and existing.get("model_id") == model_id and existing.get("playground_id")):
        # 생존 판별은 _serving_alive 하나만 쓴다. 여기와 빠른 경로가 서로 다른 기준을
        # 쓰면, 같은 일시적 조회 실패가 들어온 경로에 따라 재배포되거나 재사용된다.
        if await _serving_alive(existing["playground_id"], user, dataset_id, role):
            await db.touch_serving(dataset_id, role)
            return {"role": role, "model_id": model_id, "hf_id": model["hf_id"],
                    "playground_id": existing["playground_id"], "status": "ready",
                    "endpoint": serving_endpoint(existing["playground_id"],
                                                 ds["workspace_id"]),
                    "reused": True}

    # 소유 기록을 배포 **전에** 남긴다. 여기서 프로세스가 끊겨도 리콘사일러가 이 행을
    # 보고 정리할 수 있다 — 기록이 없으면 GPU 만 물고 아무도 모르는 배포가 된다.
    await db.upsert_serving(dataset_id, role, model_id, model["hf_id"])
    row = await db.get_serving(dataset_id, role)
    serving_id = row["id"]

    # 쓸 수 없게 된 옛 배포(모델 변경·죽은 배포)는 먼저 내린다. 안 내리면 GPU 를 물고
    # 있어 새 배포가 자원 부족으로 거절된다.
    old_pid = row.get("playground_id")
    if old_pid:
        await _teardown_playground(old_pid, user)

    try:
        res = await _playground_post("/pipeline-deploy", {
            "workspace_id": ds["workspace_id"],
            "model_huggingface_id": model["hf_id"],
            "user_name": user,
            "min_vram_gb": model.get("min_vram_gb"),
            "model_instance_count": 1,
            "model_gpu_count": 1,
            "name": f"dp{dataset_id}-{role}-{model_id}"[:60],
        }, user)
    except Exception as e:
        # 자원 부족이면 여기서 끝난다 — 잡을 띄우기 전이라 사용자는 사유를 그대로 본다.
        await db.set_serving(serving_id, status="failed", error_reason=str(e))
        raise Conflict(f"{role} 모델 배포 실패: {e}") from e

    playground_id = res.get("playground_id")
    if not playground_id:
        await db.set_serving(serving_id, status="failed",
                             error_reason="배포 응답에 playground_id 가 없습니다")
        raise Conflict("배포 응답에 playground_id 가 없습니다")
    # 주소를 playground_id 와 **같은 시점에** 갱신한다. 나중에(ready 때) 미루면 준비 중
    # 장부가 직전 배포의 죽은 주소를 그대로 내보여, 그것을 읽은 쪽이 사라진 배포를 부른다.
    endpoint = serving_endpoint(playground_id, ds["workspace_id"])
    await db.set_serving(serving_id, playground_id=playground_id, api_path=endpoint)
    deadline = time.monotonic() + SERVING_READY_TIMEOUT_S
    last = None
    missing = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(SERVING_POLL_S)
        try:
            last = await _playground_status(playground_id, user)
        except Exception as e:  # noqa: BLE001 - 일시적 조회 실패로 배포를 버리지 않는다
            # 배포가 아예 없어진 것(밖에서 회수·삭제)은 일시적 실패가 아니다. 재시도로
            # 버티면 없는 배포를 30분 기다리고, 그 동안 이 준비 태스크가 살아 있어서
            # 다음 배포 요청이 계속 "이미 준비 중" 으로 튕긴다.
            if _playground_gone(e):
                missing += 1
                if missing >= PLAYGROUND_GONE_LIMIT:
                    last = "deleted"
                    break
            else:
                missing = 0
            logging.warning("[dp-serving] 상태 조회 실패 playground=%s", playground_id,
                            exc_info=True)
            continue
        missing = 0
        if last == "running":
            await db.set_serving(serving_id, status="ready", api_path=endpoint)
            await db.touch_serving(dataset_id, role)
            logging.warning("[dp-serving] ready dataset=%s role=%s model=%s playground=%s",
                            dataset_id, role, model_id, playground_id)
            return {"role": role, "model_id": model_id, "hf_id": model["hf_id"],
                    "playground_id": playground_id, "status": "ready",
                    "endpoint": endpoint, "reused": False}
        if last == "error":
            break

    if last == "deleted":
        reason = "배포가 준비 도중 밖에서 삭제되었습니다"
    elif last == "error":
        reason = "배포가 error 로 끝났습니다"
    else:
        reason = (f"{SERVING_READY_TIMEOUT_S // 60}분 안에 준비되지 않았습니다"
                  f"(마지막 상태: {last})")
    # 준비되지 않은 배포를 그대로 두면 GPU 만 문다. 이미 사라진 배포는 내릴 것이 없다.
    if last != "deleted":
        await _teardown_playground(playground_id, user)
    await db.set_serving(serving_id, status="failed", error_reason=reason, released=True)
    raise Conflict(f"{role} 모델 서빙 준비 실패: {reason}")


# 준비 중인 배포의 백그라운드 작업. asyncio 는 참조가 없는 task 를 수거해 버리므로
# 여기에 붙들어 둔다 — 놓치면 폴링이 조용히 사라지고 서빙은 pending 에 머문다.
_SERVING_TASKS = {}


async def _cancel_serving_tasks(dataset_id, role=None):
    """준비 중인 배포 태스크를 끊는다. 회수·재배포 **전에** 부른다.

    남겨 두면 방금 지운 배포를 계속 폴링하다 장부를 되돌려 쓰고, 그 태스크가 사는
    동안 새 배포 요청이 "이미 준비 중" 으로 튕긴다.
    """
    keys = [k for k in list(_SERVING_TASKS)
            if k[0] == int(dataset_id) and (role is None or k[1] == role)]
    for key in keys:
        task = _SERVING_TASKS.pop(key, None)
        if not task or task.done():
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - 끊는 중에 난 오류는 회수를 막지 않는다
            logging.warning("[dp-serving] 준비 태스크 취소 중 오류 %s", key, exc_info=True)
        logging.warning("[dp-serving] 준비 태스크 취소 dataset=%s role=%s", key[0], key[1])


async def start_serving(dataset_id, role, jf_user=None):
    """준비를 백그라운드로 시작하고 **지금 상태**를 즉시 돌려준다.

    ensure_serving 은 가중치 내려받기까지 기다리므로 수 분에서 수십 분이 걸린다. 그것을
    HTTP 요청에 그대로 물리면 화면이 그동안 멈춘 것처럼 보이고 게이트웨이 타임아웃에
    걸린다. 그래서 시작만 하고, 진행은 서빙 현황 조회로 본다.
    """
    key = (int(dataset_id), role)
    task = _SERVING_TASKS.get(key)
    if task and not task.done():
        return {"dataset_id": dataset_id, "role": role, "status": "preparing",
                "message": "이미 준비 중입니다"}

    async def _run():
        try:
            await ensure_serving(dataset_id, role, jf_user)
        except Exception:  # noqa: BLE001 - 사유는 llm_dp_serving.error_reason 에 남는다
            logging.exception("[dp-serving] 준비 실패 dataset=%s role=%s", dataset_id, role)
        finally:
            _SERVING_TASKS.pop(key, None)

    _SERVING_TASKS[key] = asyncio.create_task(_run())
    return {"dataset_id": dataset_id, "role": role, "status": "preparing",
            "message": "배포를 시작했습니다"}


async def list_servings(dataset_id):
    """이 파이프라인이 쥐고 있는 서빙 현황(화면·운영 확인용)."""
    rows = await db.list_servings(dataset_id)
    ds = await get_dataset(dataset_id)
    ws = (ds or {}).get("workspace_id")
    for r in rows:
        r["endpoint"] = (serving_endpoint(r["playground_id"], ws)
                         if r.get("playground_id") and ws else None)
    return rows


async def release_serving(dataset_id, role=None, jf_user=None):
    """서빙을 내린다. role 을 생략하면 이 파이프라인이 쥔 것 전부."""
    ds = await get_dataset(dataset_id)
    user = jf_user or (ds or {}).get("create_user") or ""
    await _cancel_serving_tasks(dataset_id, role)
    released = []
    for row in await db.list_servings(dataset_id):
        if role and row["role"] != role:
            continue
        if row["status"] in ("released", "failed") and not row.get("playground_id"):
            continue
        if row.get("playground_id"):
            await _teardown_playground(row["playground_id"], user)
        await db.set_serving(row["id"], status="released", released=True)
        released.append(row["role"])
    return {"dataset_id": dataset_id, "released": released}


async def reconcile_servings_once():
    """유휴 서빙 회수 + 준비되다 만 배포 정리. 반환값은 회수한 건수.

    회수 판정에 '이 데이터셋에 도는 실행이 있는가'를 함께 본다 — 노드는 서빙을 내부
    DNS 로 직접 부르므로 BE 에 사용 기록이 남지 않는다. 시간만 보면 한 시간짜리 생성
    잡을 도중에 끊어 버린다.
    """
    servings = await db.list_live_servings()
    if not servings:
        return 0
    busy = {r["dataset_id"] for r in (await db.list_running_runs() or [])}
    reclaimed = 0
    for row in servings:
        try:
            # 준비 중이던 배포를 입양한다. BE 가 준비 폴링 도중 재시작하면 배포는 살아
            # 있는데 장부는 pending 에 멈춘다 — 그대로 두면 다음 요청이 멀쩡한 배포를
            # 헐고 처음부터 다시 띄운다(콜드 스타트를 한 번 더 문다).
            if row["status"] == "pending" and row.get("playground_id"):
                ds = await get_dataset(row["dataset_id"])
                user = (ds or {}).get("create_user") or ""
                try:
                    if await _playground_status(row["playground_id"], user) == "running":
                        await db.set_serving(
                            row["id"], status="ready",
                            api_path=serving_endpoint(row["playground_id"],
                                                      ds["workspace_id"]))
                        logging.warning("[dp-serving] 입양 dataset=%s role=%s playground=%s",
                                        row["dataset_id"], row["role"], row["playground_id"])
                        continue
                except Exception:  # noqa: BLE001 - 조회 실패는 아래 유휴 판정에 맡긴다
                    logging.warning("[dp-serving] 입양 판정 실패 id=%s", row["id"],
                                    exc_info=True)

            if row["dataset_id"] in busy:

                # 실행 중이면 회수하지 않는다. 이때 사용시각을 찍어 둬야 유휴 시계가

                # "실행이 끝난 시점"부터 돈다 — 안 찍으면 45분짜리 잡이 끝난 직후

                # 다음 주기에서 이미 45분 유휴로 보여 방금 쓴 배포가 즉시 회수된다.

                try:

                    await db.touch_serving(row["dataset_id"], row["role"])

                except Exception:  # noqa: BLE001 - 부기 실패가 리콘사일러를 멈추지 않게

                    logging.warning("[dp-serving] 사용시각 기록 실패 dataset=%s role=%s",

                                    row["dataset_id"], row["role"], exc_info=True)

                continue
            idle = _age_seconds(row.get("last_used_datetime") or row.get("create_datetime"))
            if idle < SERVING_IDLE_RECLAIM_S:
                continue
            ds = await get_dataset(row["dataset_id"])
            user = (ds or {}).get("create_user") or ""
            if row.get("playground_id"):
                await _teardown_playground(row["playground_id"], user)
            await db.set_serving(
                row["id"], status="released", released=True,
                error_reason=f"{int(idle // 60)}분간 쓰이지 않아 회수했습니다")
            reclaimed += 1
            logging.warning("[dp-serving] 회수 dataset=%s role=%s playground=%s (유휴 %d분)",
                            row["dataset_id"], row["role"], row.get("playground_id"),
                            int(idle // 60))
        except Exception:  # noqa: BLE001 - 하나의 실패가 나머지를 막지 않게
            logging.exception("[dp-serving] 회수 실패 id=%s", row.get("id"))
    return reclaimed


# ── 실행 이력 리콘사일러 ─────────────────────────────────────────────────────
# 노드 잡은 산출물을 작업 데이터셋에 파일로만 남기고 끝난다. 잡이 "끝났다"고 우리에게
# 알려주는 경로가 없으므로, 주기적으로 훑어 running 실행을 마감한다.
#
# 콜백(노드가 BE 를 호출) 대신 폴링을 고른 이유: 노드 스크립트가 네트워크·인증에
# 의존하지 않아도 되고, 잡이 죽어 콜백을 못 보낸 경우까지 같은 경로로 처리된다.
RECONCILE_INTERVAL_S = 20
# 잡이 끝났는데도 산출물이 없으면 실패다. 다만 파일 쓰기와 종료 기록 사이에 NFS
# 지연이 있을 수 있어, 종료 직후 한 주기는 더 기다린다.
RECONCILE_GRACE_S = 30
# 종료 기록조차 없이 사라진 잡(스케줄러가 기록을 남기기 전에 죽은 경우)의 상한.
RECONCILE_MAX_AGE_S = 24 * 3600


def _read_funnel(path):
    """노드가 남긴 funnel.json. 쓰는 도중이면 파싱에 실패하므로 다음 주기로 미룬다."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _age_seconds(value):
    """DATETIME 컬럼(드라이버에 따라 datetime 또는 str)의 경과 초. 모르면 0."""
    if value is None:
        return 0.0
    if isinstance(value, str):
        try:
            value = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return 0.0
    try:
        return (datetime.now() - value).total_seconds()
    except TypeError:
        return 0.0


# 심사 결과를 화면이 읽는 곳으로 옮기는 자리. 노드는 산출물을 파일로만 남기므로
# 여기서 적재하지 않으면 실행은 성공인데 심사·검수·분포 화면이 계속 0 으로 보인다.
RECORD_INGEST_CHUNK = 500

# 심사 레코드에는 학습 샘플의 질문·답이 따로 없다(노드는 상황 서술과 조언을 남긴다).
# 화면과 형식 검사가 질문/답 쌍을 요구하므로 여기서 조립한다. 노드가 나중에
# question/answer 를 직접 내보내면 그 값을 그대로 쓴다(아래 우선순위).
RECORD_TASK_INSTRUCTION = {
    "ko": "위 정보와 이미지를 보고 현재 해상 상황을 서술하고 COLREG 에 따른 항해 조언을 제시하라.",
    "en": ("Describe the current maritime situation from the information and image above, "
           "and give navigational advice in accordance with COLREG."),
}


def _record_question(rec):
    """학습 샘플의 질문. 이미지 자리표시는 하나만 둔다(형식 검사가 2개 이상을 거른다)."""
    if rec.get("question"):
        return rec["question"]
    lang = rec.get("lang") or "ko"
    ais = rec.get(f"ais_text_{lang}") or rec.get("ais_text_ko") or rec.get("ais_text") or ""
    instruction = RECORD_TASK_INSTRUCTION.get(lang, RECORD_TASK_INSTRUCTION["ko"])
    return "\n".join(x for x in ("<image>", ais, instruction) if x)


def _record_answer(rec):
    if rec.get("answer"):
        return rec["answer"]
    return "\n\n".join(x for x in (rec.get("describe"), rec.get("advice")) if x)


def _record_judge_comment(rec):
    """축별 근거를 사람이 읽는 한 덩어리로. 컬럼이 VARCHAR(2000) 이라 잘라 담는다."""
    why = rec.get("judge_rationale")
    if isinstance(why, dict):
        text = " | ".join(f"{k}: {v}" for k, v in why.items() if v)
    else:
        text = str(why or "")
    return text[:2000] or None


def _record_rows(rec_list, run, preset):
    """records.jsonl → db.insert_records 가 받는 튜플.

    taxonomy 를 비워 두는 것이 중요하다 — 그 컬럼은 검수자가 고르는 **오류 유형**이고
    COLREG 조우유형이 아니다. 여기서 채우면 검수 화면의 오류 분포가 오염된다.
    조우유형·기하는 lineage 로 보낸다.
    """
    cap = "general_vqa" if preset == PRESET_SDS_COLREG else None
    out = []
    for rec in rec_list:
        key = rec.get("record_key") or rec.get("asset_id")
        if not key:
            continue
        asset_ref = rec.get("path")
        if asset_ref:
            asset_ref = os.path.join(run["out_dir"], asset_ref)[:255]
        lineage = {
            "run_id": run.get("run_id"), "out_dir": run.get("out_dir"),
            "gen_model": rec.get("gen_model"), "judge_model": rec.get("judge_model"),
            "lang": rec.get("lang"), "src": rec.get("src"),
            "scene_id": rec.get("scene_id"), "frame_idx": rec.get("frame_idx"),
            "timestamp": rec.get("timestamp"), "colreg": rec.get("colreg"),
            "gate_passed": rec.get("gate_passed"),
            "failed_axes": rec.get("failed_axes"),
            "unmeasured_axes": rec.get("unmeasured_axes"),
        }
        out.append((
            str(key)[:64], rec.get("capability") or cap, None,
            _record_question(rec), _record_answer(rec),
            rec.get("scores") or {}, _record_judge_comment(rec),
            None, asset_ref, lineage,
        ))
    return out


async def _ingest_gate_records(dataset_id, out_dir, run):
    """심사 산출물을 llm_dp_record 에 적재한다. 같은 레코드는 덮어쓴다(upsert)."""
    path = os.path.join(out_dir, "records.jsonl")
    if not os.path.isfile(path):
        return 0
    preset = await _preset_of(dataset_id)
    recs, bad = [], 0
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except ValueError:
                bad += 1
    if bad:
        logging.warning("[dp-record] 깨진 줄 %d개 건너뜀 run=%s", bad, run.get("run_id"))
    rows = _record_rows(recs, run, preset)
    saved = 0
    for i in range(0, len(rows), RECORD_INGEST_CHUNK):
        saved += await db.insert_records(dataset_id, rows[i:i + RECORD_INGEST_CHUNK]) or 0
    logging.warning("[dp-record] 적재 dataset=%s run=%s 레코드=%d",
                    dataset_id, run.get("run_id"), len(rows))
    return len(rows)


async def _reconcile_run(run, root_cache):
    """실행 하나를 마감 시도. 마감했으면 True, 아직 도는 중이면 False."""
    dataset_id = run["dataset_id"]
    work_root = root_cache.get(dataset_id)
    if work_root is None:
        ds = await get_dataset(dataset_id)
        name = ds.get("work_dataset_name")
        if not name:
            # 작업 데이터셋이 아직 없다 = 산출물이 있을 수 없다. 다음 주기에 다시 본다.
            return False
        storage_name = await db.get_workspace_storage_name(ds["workspace_id"])
        if not storage_name:
            return False
        work_root = _work_dataset_root(storage_name, ds["workspace_name"],
                                       WORK_DATASET_ACCESS, name)
        root_cache[dataset_id] = work_root

    out_dir = os.path.join(work_root, run["out_dir"])
    summary = _read_funnel(os.path.join(out_dir, "funnel.json"))
    if summary is not None:
        await db.finish_run(
            run["id"], "done",
            in_count=summary.get("in"), out_count=summary.get("out"),
            dropped_count=summary.get("dropped_total"),
            funnel=summary)
        logging.info("[dp-run] done id=%s %s %s→%s",
                     run["id"], run["stage"], summary.get("in"), summary.get("out"))
        # 마감을 먼저 하고 적재한다. 적재를 먼저 걸면 여기서 실패할 때 실행이 running
        # 으로 남아 다음 주기마다 같은 일을 되풀이한다(끝난 잡인데 끝나지 않은 것으로 보인다).
        if run["stage"] == "gate" and not run.get("dry_run"):
            try:
                await _ingest_gate_records(dataset_id, out_dir, run)
            except Exception:  # noqa: BLE001 - 적재 실패가 실행 마감을 되돌리지 않는다
                logging.exception("[dp-record] 적재 실패 run=%s", run.get("run_id"))
        return True

    # 산출물이 없다. 잡이 이미 끝났다면 실패로 닫는다 — 안 그러면 running 이 영원히 남아
    # 상류 탐색이 "먼저 실행하세요"만 반복하고 사용자는 이유를 모른다.
    end = await db.get_job_end_state(run.get("job_name") or "") or {}
    if end.get("end_datetime") and _age_seconds(end["end_datetime"]) > RECONCILE_GRACE_S:
        status = end.get("end_status") or "unknown"
        reason = end.get("error_reason") or f"잡이 {status} 로 끝났으나 산출물이 없습니다"
        await db.finish_run(run["id"], "failed", error_reason=reason[:1000])
        logging.warning("[dp-run] failed id=%s %s: %s", run["id"], run["stage"], reason[:200])
        return True

    # 잡 이름이 비어 있다 = 서빙을 기다리다 끝내 띄우지 못했다. BE 가 그 사이 재시작하면
    # 기다리던 작업이 사라지므로, 여기서 닫지 않으면 24시간 동안 running 으로 남는다.
    if not (run.get("job_name") or "").strip():
        if _age_seconds(run.get("create_datetime")) > SERVING_READY_TIMEOUT_S + RECONCILE_GRACE_S:
            await db.finish_run(
                run["id"], "failed",
                error_reason="모델 서빙을 기다리다 잡을 띄우지 못했습니다(준비 중 중단)")
            logging.warning("[dp-run] 미디스패치 실행 정리 id=%s %s", run["id"], run["stage"])
            return True
        return False

    if _age_seconds(run.get("create_datetime")) > RECONCILE_MAX_AGE_S:
        await db.finish_run(run["id"], "failed",
                            error_reason="종료 기록도 산출물도 없이 24시간이 지났습니다")
        logging.warning("[dp-run] stale id=%s %s", run["id"], run["stage"])
        return True
    return False


async def reconcile_runs_once():
    """running 실행을 한 바퀴 훑는다. 반환값은 마감한 건수(테스트·운영 확인용)."""
    runs = await db.list_running_runs()
    if not runs:
        return 0
    root_cache = {}
    closed = 0
    for run in runs:
        try:
            if await _reconcile_run(run, root_cache):
                closed += 1
        except Exception:  # noqa: BLE001 - 한 실행의 실패가 나머지를 막지 않게
            logging.exception("[dp-run] reconcile 실패 id=%s", run.get("id"))
    return closed


async def reconcile_loop():
    """앱이 살아 있는 동안 도는 백그라운드 루프."""
    logging.info("[dp-run] 리콘사일러 시작 (주기 %ss)", RECONCILE_INTERVAL_S)
    while True:
        try:
            await reconcile_runs_once()
        except Exception:  # noqa: BLE001 - 루프가 죽으면 실행이 영영 마감되지 않는다
            logging.exception("[dp-run] reconcile 주기 실패")
        try:
            # 서빙 회수는 실행 마감 **뒤에** 돈다 — 방금 끝난 실행이 먼저 done 으로 닫혀야
            # busy 집합에서 빠지고, 그래야 마지막 잡이 끝난 서빙이 이 주기에 회수된다.
            await reconcile_servings_once()
        except Exception:  # noqa: BLE001 - 회수가 막히면 GPU 가 계속 잠긴다
            logging.exception("[dp-serving] 회수 주기 실패")
        await asyncio.sleep(RECONCILE_INTERVAL_S)
