"""llm_data_pipeline 서비스 계층.

DB 접근은 utils.llm_db.db_data_pipeline 에 맡기고, 여기서는 화면이 필요로 하는
"판정"을 만든다 — 노드 경고, 유형별 판정, 통과율 범위, 학습 형식 검사 결과처럼
사람이 다음에 뭘 해야 하는지 알려주는 값들.
"""
import math

from utils.llm_db import db_data_pipeline as db

from data_pipeline.constants import (
    CAPABILITIES,
    COORD_REMAP_STEP,
    DATASET_STATE_LABEL,
    DEFAULT_MAX_REGENERATE,
    DEFAULT_PROMPT,
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
    SPLIT_BY,
    SPLITS,
    STAGES,
    TAXONOMY,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    TRAIN_FORMATS,
    axes_for,
    thresholds_for,
)

# 단계 → 그 단계를 담당하는 노드 kind. 생성은 프리셋마다 이름이 다르다
# (범용은 'synth', 해양은 'gen') — 하나만 보면 SDS 설정이 저장되지 않는다.
STAGE_NODE_KINDS = {
    "preprocess": ("prep",),
    "filter": ("filter",),
    "generate": ("synth", "gen"),
    "gate": ("gate",),
}


def _find_stage_node(nodes, stage):
    kinds = STAGE_NODE_KINDS[stage]
    return next((n for n in nodes if n.get("kind") in kinds), None)


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
        "preprocess_library": [dict(s) for s in PREPROCESS_LIBRARY],
        "filter_library": [dict(s) for s in FILTER_LIBRARY],
        "generation_models": [dict(m) for m in GENERATION_MODELS],
        "generation_templates": [dict(t) for t in GENERATION_TEMPLATES],
        "prompt_chips": [dict(c) for c in PROMPT_CHIPS],
        "default_prompt": DEFAULT_PROMPT,
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
             "steps": [["자선 · 주변선 상태", "14 cols"], ["시계열 (초 단위)", "csv"]]},
            {"kind": "prep", "name": "전처리 · 영상",
             "steps": [["이미지 정규화", "RGB · 1024"], ["EXIF 보정", "방향"], ["타임스탬프 부여", "frame_idx"]]},
            {"kind": "filter", "name": "필터 · 영상",
             "steps": [["프레임 중복 제거", "phash ≤2"], ["저해상 컷", "512 미만"], ["흐림 필터", "사용 안 함"]]},
            {"kind": "prep", "name": "전처리 · AIS",
             "steps": [["단위 정규화", "knot · deg"], ["시간 정렬", "ts 오름차순"], ["씬 구조화", "자선 + 주변선"]]},
            {"kind": "filter", "name": "필터 · AIS",
             "steps": [["무효 좌표", "0 · 0 제거"], ["범위 위반", "heading"], ["중복 행", "ts + ship_id"]]},
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
         "steps": [["중복 제거", "0.95"], ["저품질 이미지", "선명도 40"], ["민감 콘텐츠", "유해 0.85"]]},
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


def _annotate_flow(nodes):
    """노드마다 입력/출력 타입과 경고를 붙인다.

    타입이 '데이터'에서 '레코드'로 바뀌는 지점은 생성 노드다. 그 뒤의 변형은 의미가
    달라지므로(원본이 아니라 레코드를 건드림) 타입을 따라가며 판정한다.
    """
    out = []
    cur_type = "—"
    for n in nodes:
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
        out.append({**n, "input_type": in_type, "output_type": cur_type,
                    "state": state, "warning": warn})
    return out


async def get_flow(dataset_id):
    ds = await get_dataset(dataset_id)
    nodes = await db.get_flow(dataset_id)
    preset = ds.get("preset") or PRESET_GENERIC
    if not nodes:
        # 아직 저장된 구성이 없으면 프리셋 기본값을 보여준다(빈 화면 방지).
        nodes = [{"kind": n["kind"], "name": n["name"], "steps": n["steps"], "config": {}}
                 for n in default_nodes(preset)]
    return {
        "dataset_id": dataset_id,
        "preset": preset,
        "editable": PRESET_META.get(preset, {}).get("editable", True),
        "nodes": _annotate_flow(nodes),
        # 비어 있으면 화면이 선형(0→1→2…)으로 그린다.
        "flow": ds.get("flow") or [],
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
    return {"preprocess": PREPROCESS_LIBRARY, "filter": FILTER_LIBRARY}.get(stage, ())


async def _preset_of(dataset_id):
    """데이터셋의 프리셋. 심사 축·임계를 고르는 기준이라 축을 쓰는 곳은 전부 이걸 거친다."""
    return (await get_dataset(dataset_id)).get("preset") or PRESET_GENERIC


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
        payload["models"] = [dict(m) for m in GENERATION_MODELS]
        payload["templates"] = [dict(t) for t in GENERATION_TEMPLATES]
        payload["prompt_chips"] = [dict(c) for c in PROMPT_CHIPS]
        payload["default_prompt"] = DEFAULT_PROMPT
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
    await get_dataset(dataset_id)
    versions = await db.list_versions(dataset_id) or []
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


async def create_version(dataset_id, version, mix, split, split_by):
    await get_dataset(dataset_id)
    if await db.version_exists(dataset_id, version):
        raise Conflict(f"이미 있는 버전입니다: {version}")

    stats = await db.get_review_stats(dataset_id) or {}
    total = int(stats.get("total") or 0)
    human = int(stats.get("approved") or 0) + int(stats.get("edited") or 0)
    gate = await get_gate_summary(dataset_id)

    cfg = (await get_stage(dataset_id, "generate")).get("config") or {}

    # 가중치·비율을 실제 건수로 확정해서 남긴다. 원본 dict 만 저장하면 "이 버전이
    # 무엇으로 구성됐는지" 를 나중에 재계산해야 하고, 그 사이 풀이 바뀌면 답이 달라진다.
    split_ratio = split or dict(DEFAULT_SPLIT)
    resolved_mix = allocate(mix, total) if mix else {}
    resolved_split = allocate(split_ratio, total) if split_ratio else {}

    await db.create_version(
        dataset_id=dataset_id, version=version,
        record_count=total, pass_rate=gate.get("pass_rate") or 0, human_reviewed=human,
        gen_model=cfg.get("generator_model"), judge_model=cfg.get("judge_model"),
        prompt_name=cfg.get("prompt_name"), thresholds=gate.get("thresholds"),
        mix={"weights": mix, "counts": resolved_mix},
        split={"ratio": split_ratio, "counts": resolved_split},
        split_by=split_by)
    return await list_versions(dataset_id)
