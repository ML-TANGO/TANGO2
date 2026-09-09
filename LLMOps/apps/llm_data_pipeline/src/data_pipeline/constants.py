"""llm_data_pipeline 공용 상수 — 학습 데이터 파이프라인의 도메인 규칙 정본.

여기 있는 값은 화면(front/src/pages/llm/dataset)과 계약을 이룬다. FE 가 같은 값을
하드코딩하지 않도록 `GET /data-pipelines/meta` 로 그대로 내려준다.
"""

# ── 데이터셋 상태 ────────────────────────────────────────────────────────────
DATASET_STATES = ("draft", "running", "active", "archived")

# 상태 라벨(한글) — FE 배지 문구. 서버가 정본을 쥐고 FE 는 매핑만 한다.
DATASET_STATE_LABEL = {
    "draft": "초안",
    "running": "진행",
    "active": "활성",
    "archived": "보관",
}

# ── VLM 심사 4축 ────────────────────────────────────────────────────────────
# 심사 모델이 레코드마다 매기는 점수 축. key 는 DB(llm_dp_record.scores JSON)와 동일.
GATE_AXES = (
    {"key": "align", "label": "이미지 정합도", "short": "정합"},
    {"key": "imgdep", "label": "이미지 의존도", "short": "의존"},
    {"key": "answer", "label": "답변 가능성", "short": "답변"},
    {"key": "unique", "label": "정답 유일성", "short": "유일"},
)

# 축별 기본 임계값. 이 미만이면 미달 → 재생성 대상.
DEFAULT_THRESHOLDS = {"align": 0.75, "imgdep": 0.80, "answer": 0.80, "unique": 0.70}

# SDS(해양 COLREG) 심사 4축 — 범용 4축과 이름도 임계도 겹치지 않는다.
# 항해 조력은 "질문·답이 이미지와 맞는가"가 아니라 "상황 판단과 조치가 규칙에 맞는가"를
# 본다. 축을 하나로 합쳐 두면 SDS 레코드가 범용 축으로 채점돼 전부 미평가로 떨어진다.
SDS_GATE_AXES = (
    {"key": "situation_accuracy", "label": "상황 서술 정확도", "short": "상황"},
    {"key": "colreg_correctness", "label": "COLREG 판단 정확도", "short": "규칙"},
    {"key": "image_grounding", "label": "이미지 근거성", "short": "근거"},
    {"key": "actionability", "label": "조치 구체성", "short": "조치"},
)
SDS_THRESHOLDS = {"situation_accuracy": 0.75, "colreg_correctness": 0.80,
                  "image_grounding": 0.70, "actionability": 0.75}

# 임계값 조절 허용 범위 — 너무 낮추면 게이트가 무의미해지고, 너무 올리면 통과가 0 이 된다.
THRESHOLD_MIN = 0.50
THRESHOLD_MAX = 0.95

# 재생성 최대 횟수 기본값 — 미달 레코드를 몇 번까지 다시 만들지.
DEFAULT_MAX_REGENERATE = 3

# ── 통과율 정상 범위 ─────────────────────────────────────────────────────────
# 40% 미만이면 생성 품질이 나쁘고, 85% 초과면 게이트가 헐거워 사실상 걸러지지 않는다.
# 둘 다 "범위 밖"으로 표시해 사람이 원인을 보게 만든다.
PASS_RATE_RANGE = (40, 85)

# ── 오류 유형(사람 검수 taxonomy) ────────────────────────────────────────────
TAXONOMY = ("환각", "OCR오류", "모호", "누출", "정합 불일치")

# 원본 등록 상태 — 실패한 것도 남긴다(왜 실패했는지가 다음 업로드를 고칠 정보).
ASSET_STATUSES = ("registered", "duplicate", "failed")

# 검수 판정 종류.
REVIEW_VERDICTS = ("approved", "edited", "rejected")

# ── 데이터 유형(capability) ─────────────────────────────────────────────────
CAPABILITIES = (
    "captioning", "general_vqa", "ocr_document",
    "chart_table", "counting", "spatial_3d", "refusal",
)

# 유형별 판정 — 레코드 수와 데이터 수를 함께 봐야 원인이 갈린다.
#   데이터도 레코드도 없음      → 데이터 없음 (업로드부터)
#   데이터는 있는데 레코드 희소 → 생성 부족 (생성 조건 문제)
#   데이터 자체가 희소          → 데이터 부족 (업로드 필요)
COVERAGE_FLAGS = ("충분", "생성 부족", "데이터 부족", "데이터 없음")

# ── 파이프라인 프리셋 ────────────────────────────────────────────────────────
PRESET_GENERIC = "generic"
PRESET_SDS_COLREG = "sds_colreg"
PRESETS = (PRESET_GENERIC, PRESET_SDS_COLREG)

# 프리셋 라벨 + 편집 가능 여부. 해양 COLREG 는 노드 구성이 도메인 논리에 묶여 있어
# 임의 편집을 막는다(조인·계산 순서가 바뀌면 결과가 성립하지 않음).
PRESET_META = {
    PRESET_GENERIC: {"label": "범용", "editable": True},
    PRESET_SDS_COLREG: {"label": "해양 COLREG", "editable": False},
}

# 프리셋 → 심사 축·임계. 축을 쓰는 곳은 전부 데이터셋의 preset 을 통해 이 맵을 거친다.
PRESET_AXES = {
    PRESET_GENERIC: GATE_AXES,
    PRESET_SDS_COLREG: SDS_GATE_AXES,
}
PRESET_THRESHOLDS = {
    PRESET_GENERIC: DEFAULT_THRESHOLDS,
    PRESET_SDS_COLREG: SDS_THRESHOLDS,
}


def axes_for(preset):
    """프리셋의 심사 축. 모르는 프리셋은 범용으로 — 축이 없으면 화면이 빈 표가 된다."""
    return PRESET_AXES.get(preset or PRESET_GENERIC, GATE_AXES)


def thresholds_for(preset):
    """프리셋의 기본 임계값. 호출부가 수정하지 못하도록 사본을 준다."""
    return dict(PRESET_THRESHOLDS.get(preset or PRESET_GENERIC, DEFAULT_THRESHOLDS))

# ── 단계(stage) ─────────────────────────────────────────────────────────────
# 앞 4개는 모든 프리셋 공통, sds_* 셋은 해양 COLREG 전용 수집·조인 단계다.
# 프리셋별로 보여줄 단계는 STAGES_BY_PRESET 이 정한다 — 범용 파이프라인에 항해 영상
# 단계가 뜨면 사용자가 쓸 수 없는 단계를 계속 마주하게 된다.
# 'data' 는 **설정만 있고 실행은 없는** 단계다 — 원본을 어디서 마운트할지(sources)를
# 담을 자리가 필요해서 넣는다. 실행 목록(STAGES_BY_PRESET)에는 넣지 않는다:
# 실행하려 하면 STAGE_SCRIPT 에 없어 "실행할 수 없는 단계" 로 끊긴다.
STAGES = ("data", "preprocess", "filter", "generate", "gate",
          "sds_video", "sds_ais", "sds_ais_clean", "sds_ais_scene",
          "sds_join", "sds_colreg", "assemble")

# 전처리 기능 라이브러리.
PREPROCESS_LIBRARY = (
    {"key": "정제", "desc": "디코딩 · RGB 변환 · EXIF 방향 보정",
     "param": {"name": "디코딩 재시도", "key": "retry", "min": 0, "max": 5, "unit": "회", "default": 2}},
    {"key": "구조 추출", "desc": "PDF → 페이지 이미지 · 표 영역 좌표 · 문서 ID 보존",
     "param": {"name": "PDF 변환 해상도", "key": "dpi", "min": 96, "max": 300, "unit": "dpi", "default": 200}},
    {"key": "리사이즈", "desc": "긴 변 최대 크기로 축소 · 이미지 토큰 예산 조절",
     "param": {"name": "긴 변 최대 크기", "key": "longEdge", "min": 512, "max": 2048, "unit": "px", "default": 1024}},
    {"key": "크롭", "desc": "가운데 영역만 남김",
     "param": {"name": "남길 비율", "key": "cropPct", "min": 50, "max": 100, "unit": "%", "default": 90}},
    {"key": "회전", "desc": "무작위 회전 증강",
     "param": {"name": "최대 각도", "key": "rotDeg", "min": 0, "max": 45, "unit": "°", "default": 15}},
    {"key": "좌우 반전", "desc": "좌우 반전 증강",
     "param": {"name": "적용 비율", "key": "flipPct", "min": 0, "max": 100, "unit": "%", "default": 50}},
    {"key": "영역 좌표 보정", "desc": "기하 변형에 맞춰 bbox 좌표를 다시 계산",
     "param": {"name": "보정", "key": "remapAuto", "min": 0, "max": 1, "unit": "", "default": 1}},
)

# 필터 기능 라이브러리 — 제거된 것은 보관되고 개별 복구할 수 있다.
FILTER_LIBRARY = (
    {"key": "중복 제거", "desc": "파일 해시 + 비슷한 이미지(유사도)",
     "param": {"name": "비슷한 이미지 기준값", "key": "dupTh", "min": 80, "max": 99, "unit": "ratio", "default": 95}},
    # 흐림 · 최소 해상도 · 노출은 원래 '저품질 이미지' 한 스위치로 묶여 있었다. 그러면
    # 저해상 컷만 켤 수가 없다 — 해양 프레임은 저텍스처라 선명도가 1.8~9.8(실측)인데
    # 흐림 하한이 10 이어서, 해상도 컷을 켜려고 스위치를 올리면 전량 탈락했다.
    # 목업도 셋을 각각 끄고 켠다(흐림 사용 안 함 · 노출 사용 안 함 · 저해상 512 미만).
    {"key": "흐림", "desc": "라플라시안 분산이 기준 미만이면 제외 · 도메인마다 값이 크게 다르다",
     "param": {"name": "선명도 하한", "key": "blur", "min": 1, "max": 90, "unit": "", "default": 40}},
    {"key": "최소 해상도", "desc": "짧은 변이 기준보다 작으면 제외",
     "param": {"name": "짧은 변 최소", "key": "minEdge", "min": 128, "max": 2048, "unit": "px", "default": 512}},
    {"key": "노출 이상", "desc": "너무 밝거나 어두우면서 대비까지 없는 이미지만 제외",
     "param": {"name": "대비 하한", "key": "expoStd", "min": 5, "max": 60, "unit": "", "default": 25}},
    {"key": "민감 콘텐츠", "desc": "유해 이미지 차단 · 개인정보 검출 후 가림",
     "param": {"name": "유해 이미지 기준값", "key": "nsfw", "min": 50, "max": 99, "unit": "ratio", "default": 85}},
)

# ── 해양 COLREG 수집·조인 기능 라이브러리 ────────────────────────────────────
# key 는 캔버스에 그대로 뜨는 이름이자 노드 스크립트가 분기하는 값이다.
# apps/builtin_data_pipeline/dp_sds_*.py 의 STEP_* 상수와 문자 단위로 같아야 한다.

SDS_VIDEO_LIBRARY = (
    {"key": "타임스탬프 프레임", "desc": "브리지 카메라 영상을 초당 N장으로 솎아 시각을 붙임",
     "param": {"name": "초당 프레임 수", "key": "fps", "min": 0, "max": 30, "unit": "fps", "default": 1}},
    {"key": "장면 수 제한", "desc": "앞에서부터 N장까지만 — 0 이면 전량",
     "param": {"name": "최대 장면 수", "key": "scenes", "min": 0, "max": 5000, "unit": "장", "default": 0}},
)

# AIS 는 '정형화'와 '정제'가 한 노드 안에서 이어진다. 목업은 이를 전처리·AIS 와
# 필터·AIS 두 노드로 나눠 그리지만, 중간 산출물이 CSV 한 벌뿐이라 잡을 쪼개면
# NFS 왕복만 늘고 얻는 게 없다 — 기능은 그대로 두고 실행만 한 노드로 묶는다.
# AIS 갈래는 세 노드로 나뉜다 — 적재 / 행 정제 / 씬 구조화.
# 한 노드에 여섯 기능을 몰아 두면 임계값을 바꿔 한 단계만 다시 돌릴 수도, 단계별로
# 몇 행이 빠졌는지 볼 수도 없다(영상 갈래는 이미 세 노드다 — 같은 규칙을 따른다).
SDS_AIS_LIBRARY = (
    {"key": "단위 정규화", "desc": "knot · degree 파싱 · 숫자가 아닌 행 제거", "param": {}},
)

SDS_AIS_CLEAN_LIBRARY = (
    {"key": "무효 좌표", "desc": "위도·경도가 0 · 0 인 행 제거", "param": {}},
    {"key": "범위 위반", "desc": "침로가 0~360° 밖이거나 속도가 음수인 행 제거", "param": {}},
    {"key": "중복 행", "desc": "timestamp + ship_id 가 겹치는 행 제거", "param": {}},
)

SDS_AIS_SCENE_LIBRARY = (
    {"key": "시간 정렬", "desc": "timestamp 오름차순 — 같은 시각 행이 흩어지면 묶음이 쪼개진다", "param": {}},
    {"key": "씬 구조화", "desc": "같은 시각 행 묶음 → 자선 1척 + 주변선 N척", "param": {}},
)

SDS_COLREG_LIBRARY = (
    {"key": "상대방위 · 침로차", "desc": "자선 기준 방위와 침로 차이 — 결정론 계산", "param": {}},
    {"key": "조우 분류", "desc": "정면 · 횡단 · 추월 판정과 적용 조항(13 · 14 · 15 · 17)", "param": {}},
    {"key": "근접 위험도", "desc": "최근접점(CPA)과 도달시간(TCPA)", "param": {}},
)

SDS_JOIN_LIBRARY = (
    {"key": "프레임 × AIS", "desc": "프레임마다 시각이 가장 가까운 AIS 씬을 붙임", "param": {}},
    {"key": "허용오차", "desc": "이 시간차를 넘으면 짝이 없는 것으로 본다",
     "param": {"name": "허용 시간차", "key": "toleranceS", "min": 0, "max": 60, "unit": "초", "default": 1}},
    {"key": "무매칭 처리", "desc": "허용오차를 넘은 프레임을 버림 — 끄면 그대로 통과", "param": {}},
)

# 프리셋이 쓰는 단계. FE 가 이 목록으로 단계 진입점을 그린다.
STAGES_BY_PRESET = {
    PRESET_GENERIC: ("preprocess", "filter", "generate", "gate", "assemble"),
    PRESET_SDS_COLREG: ("sds_video", "sds_ais", "sds_ais_clean", "sds_ais_scene",
                        "sds_join", "sds_colreg",
                        "preprocess", "filter", "generate", "gate", "assemble"),
}


def stages_for(preset):
    """프리셋이 실행할 수 있는 단계. 모르는 프리셋은 공통 4단계로 떨어뜨린다."""
    return STAGES_BY_PRESET.get(preset or PRESET_GENERIC, STAGES_BY_PRESET[PRESET_GENERIC])


# ── 기하 변형 규칙 (심사 점수 무효화) ────────────────────────────────────────
# 레코드가 만들어진 뒤 이미지를 기하적으로 바꾸면 이미 매긴 심사 점수가 그 레코드를
# 더는 설명하지 못한다. 그래서 아래 기능이 '레코드' 단계에 걸리면 재심사가 필요하다.
GEOMETRIC_STEPS = ("크롭", "회전", "좌우 반전", "리사이즈")

# 그중 방향이 바뀌는 것들은 사람이 내린 판정까지 무효로 만든다(왼쪽/오른쪽이 뒤집힘).
DIRECTIONAL_STEPS = ("회전", "좌우 반전")

# 기하 변형과 짝을 이뤄야 하는 보정. 없으면 bbox 좌표가 원본 기준으로 남아 깨진다.
COORD_REMAP_STEP = "영역 좌표 보정"

# ── 생성 ────────────────────────────────────────────────────────────────────
# 생성/심사에 쓸 수 있는 모델. family 가 같으면 맹점이 겹쳐 심사 독립성이 약해진다.
# hf_id 는 파이프라인이 이 모델을 **자동 배포**할 때 쓰는 실제 저장소 경로다. 이게 없으면
# 카탈로그가 이름표일 뿐이라 노드가 무엇을 띄워야 할지 알 수 없다.
# min_vram_gb 는 bf16 가중치 + KV cache 여유의 대략치 — 배포 전에 자원이 되는지 보고
# 안 되면 잡을 띄우기 전에 거절한다(띄운 뒤 OOM 으로 죽으면 원인이 안 보인다).
# vision = 이 플랫폼 서빙 스택에서 **이미지 입력을 받을 수 있는가**. 서빙 파드는
# AutoProcessor 에 image_processor 가 붙는지로 VLM 을 판별하는데
# (deployment_llm/src/llm/playground.py `_load_processor`), InternVL 계열은 표준
# AutoProcessor 를 제공하지 않고 자체 타일링 파이프라인을 쓴다 → IS_VLM=False 로 떨어져
# 이미지가 실린 요청을 전부 HTTP 400 으로 거부한다(심사 100건이 전량 거부된 실측 사례).
# 카탈로그에서 지우지 않고 플래그로 두는 이유: 왜 빠졌는지가 남고, 서빙이 나중에 이
# 계열을 지원하면 여기만 바꾸면 된다.
GENERATION_MODELS = (
    {"id": "qwen8b", "name": "Qwen3-VL-8B-Instruct", "license": "apache-2.0", "family": "qwen",
     "hf_id": "Qwen/Qwen3-VL-8B-Instruct", "min_vram_gb": 24, "vision": True},
    {"id": "qwen4b", "name": "Qwen3-VL-4B-Instruct", "license": "apache-2.0", "family": "qwen",
     "hf_id": "Qwen/Qwen3-VL-4B-Instruct", "min_vram_gb": 16, "vision": True},
    {"id": "intern3", "name": "InternVL3-8B", "license": "mit", "family": "internvl",
     "hf_id": "OpenGVLab/InternVL3-8B", "min_vram_gb": 24, "vision": False},
    {"id": "gemma3", "name": "Gemma 3 12B", "license": "Gemma Terms", "family": "gemma",
     "hf_id": "google/gemma-3-12b-it", "min_vram_gb": 32, "vision": True},
    # 소형 검증용. 실 데이터 규모로 돌리기 전에 배선·계약을 확인하는 용도라 품질 기대치는 낮다.
    {"id": "qwen2vl2b", "name": "Qwen2-VL-2B-Instruct", "license": "apache-2.0", "family": "qwen",
     "hf_id": "Qwen/Qwen2-VL-2B-Instruct", "min_vram_gb": 8, "vision": True},
    {"id": "intern2b", "name": "InternVL2-2B", "license": "mit", "family": "internvl",
     "hf_id": "OpenGVLab/InternVL2-2B", "min_vram_gb": 8, "vision": False},
)

# 화면에 후보로 내보내는 것. 생성도 심사도 이미지를 넣으므로, 이미지를 못 받는 모델은
# 고를 수 있게 두면 안 된다 — 고르면 배포는 성공하고 추론만 전량 실패해서
# 원인이 화면에 드러나지 않는다.
SELECTABLE_MODELS = tuple(m for m in GENERATION_MODELS if m.get("vision"))

GENERATION_TEMPLATES = (
    {"key": "ocr_document", "name": "문서 OCR QA"},
    {"key": "chart_table", "name": "차트 · 표 QA"},
    {"key": "general_vqa", "name": "일반 VQA"},
    {"key": "captioning", "name": "캡션"},
    {"key": "struct", "name": "구조화 추출"},
)

# 프롬프트 제약 칩 — 문장을 프롬프트에 넣고 빼는 방식이라 사용자가 결과를 직접 본다.
# PAIRED 는 잠금(질문만 있고 답이 없는 레코드는 학습에 못 쓴다).
PROMPT_CHIPS = (
    {"id": "PAIRED", "label": "Q · A 동시 생성", "locked": True,
     "text": "질문과 답을 반드시 한 번에 함께 생성하라."},
    {"id": "GROUNDED", "label": "이미지에서 도출", "locked": False,
     "text": "답은 이미지에 실제로 보이는 정보에서만 명시적으로 도출하라. 추측하지 마라."},
    {"id": "NOTEXT", "label": "이미지 없이 답 금지", "locked": False,
     "text": "이미지를 보지 않고도 답할 수 있는 질문은 생성하지 마라."},
    {"id": "UNIQUE", "label": "정답 유일성", "locked": False,
     "text": "정답이 하나로 확정되는 질문만 생성하라. 복수 해석이 가능하면 버려라."},
)

DEFAULT_PROMPT = (
    "이 이미지에 대한 질문 3개와 그 답을 만들어라.\n"
    "출력은 JSON 배열로 하고 각 원소는 question, answer 키를 가진다."
)

# 프리셋별 기본 생성 프롬프트. 이 값은 사용자 프롬프트로 저장돼 노드 프롬프트에 그대로
# 들어가므로(dp_generate.build_gen_prompt 의 extra), 프리셋과 어긋나면 모델에게 상충하는
# 지시를 주게 된다 — 해양 파이프라인에 범용 VQA 기본값("질문 3개와 답을 JSON 배열로")이
# 프리필돼 생성 100건 중 87건이 parse_failed 로 떨어진 일이 있었다. 형식이 깨지는 쪽은
# 그 뒤 조립 순서를 고쳐(형식 지시가 항상 마지막) 막았고, **내용이 상충하는** 쪽을 막는
# 것이 여기다. 해양은 노드가 이미 완결된 지시(describe/advice + 수치 요구)를 만들므로
# 덧붙일 것이 없다 = 빈 문자열.
PRESET_PROMPTS = {
    PRESET_GENERIC: DEFAULT_PROMPT,
    PRESET_SDS_COLREG: "",
}


def prompt_for(preset):
    """프리셋의 기본 생성 프롬프트.

    미지 프리셋은 범용 프롬프트가 아니라 **빈 문자열**로 떨어진다. 새 프리셋을
    PRESET_META 에만 추가하고 여기를 빼먹었을 때, 범용 VQA 지시가 도메인 노드에
    주입되는 것이 빈 프롬프트보다 나쁘다 — 조립 순서 수정으로 형식은 지켜지므로
    parse_failed 같은 큰 신호 없이 내용 품질만 조용히 나빠진다. preset 이 아예
    없는(레거시) 데이터셋은 범용으로 본다.
    """
    return PRESET_PROMPTS.get(preset or PRESET_GENERIC, "")


# 함정 데이터 비율 상한 — 답할 수 없는 질문을 일부러 섞어 거절을 학습시킨다.
HARD_NEGATIVE_MAX_PCT = 15

# ── 분할 ────────────────────────────────────────────────────────────────────
SPLITS = ("train", "validation", "test")
DEFAULT_SPLIT = {"train": 80, "validation": 10, "test": 10}

# 분리 기준. 문서 ID 가 기본인 이유: 같은 문서의 다른 페이지가 train 과 test 로 갈리면
# 사실상 정답을 미리 본 셈이라 평가 점수가 부풀려진다.
SPLIT_BY = ("문서 ID", "이미지", "무작위")
DEFAULT_SPLIT_BY = "문서 ID"

# ── 학습 형식 검사 ───────────────────────────────────────────────────────────
# 실제 학습 코드가 읽을 수 있는지 미리 확인한다. 여기서 걸리면 학습 시작 후 죽는 대신
# 데이터셋을 만들기 전에 고칠 수 있다.
TRAIN_FORMATS = ("Qwen3-VL", "Gemma 3", "HuggingFace messages")

# ── SDS(해양 COLREG) ────────────────────────────────────────────────────────
# AIS 기하로 결정론적으로 계산하는 COLREG 조항. 생성 모델이 지어내지 못하도록
# 계산 결과를 grounding 으로 넣는다.
COLREG_RULES = ("13조", "14조", "15조", "17조")
COLREG_ENCOUNTERS = ("횡단", "마주침", "추월", "안전")
