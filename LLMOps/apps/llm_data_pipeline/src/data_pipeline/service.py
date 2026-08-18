"""llm_data_pipeline 서비스 계층.

DB 접근은 utils.llm_db.db_data_pipeline 에 맡기고, 여기서는 화면이 필요로 하는
"판정"을 만든다 — 노드 경고, 유형별 판정, 통과율 범위, 학습 형식 검사 결과처럼
사람이 다음에 뭘 해야 하는지 알려주는 값들.
"""
import json
import math
import os
import time
import uuid

import aiohttp

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


# ── 노드 실행 ────────────────────────────────────────────────────────────────
# 단계 → 잡이 실행할 빌트인 스크립트. 노드 종류를 잡의 run_code 가 구분한다
# (프로젝트는 파이프라인당 하나라 엔티티의 built_in_data_tf 는 대표값일 뿐이다).
STAGE_SCRIPT = {
    "preprocess": "dp_prep.py",
    "filter": "dp_filter.py",
    "generate": "dp_generate.py",
    "gate": "dp_judge.py",
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
    node = _find_stage_node(await db.get_flow(dataset_id) or [], stage)
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

    out_dir = os.path.join(work_root, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    params = {
        "run_id": run_id,
        "node_index": node_index,
        "preset": ds.get("preset") or PRESET_GENERIC,
        "sources": (node.get("config") or {}).get("sources") or [],
        "steps": _runnable_steps(stage, node),
        "dry_run": bool(dry_run),
        "sample_size": int(sample_size),
        # 잡 pod 기준 경로 — 작업 데이터셋은 /dataset 에 마운트된다.
        "out_dir": f"/dataset/{rel_dir}",
        "datasets_root": "/datasets",
    }
    with open(os.path.join(out_dir, "params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    job = await _prepro_post("/jobs/pipeline/run", {
        "preprocessing_id": preprocessing_id,
        "job_name": f"dp-{dataset_id}-n{node_index}-{run_id}",
        "run_code": STAGE_SCRIPT[stage],
        "create_user_name": jf_user or "",
        # 잡의 /dataset 마운트 = 작업 데이터셋. 소스는 /datasets(RO)로 따로 붙는다.
        "dataset_id": work_id,
        "built_in_param": {"params_path": f"/dataset/{rel_dir}/params.json"},
    }, jf_user)

    return {"dataset_id": dataset_id, "stage": stage, "run_id": run_id,
            "node_index": node_index, "dry_run": bool(dry_run),
            "out_dir": rel_dir, "work_dataset_id": work_id,
            "preprocessing_id": preprocessing_id, "job": job}


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
        split_by=split_by,
        # 어느 실행에서 나온 레코드로 만든 버전인지 스냅샷한다. run 과 version 은
        # 직교하므로(1 run → N version, N run → 1 version) 이걸 남기지 않으면
        # 나중에 역산이 안 된다.
        source_runs=await db.get_source_runs(dataset_id))
    return await list_versions(dataset_id)
