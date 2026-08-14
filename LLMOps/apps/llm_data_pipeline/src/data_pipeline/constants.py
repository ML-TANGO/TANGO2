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

# ── 단계(stage) ─────────────────────────────────────────────────────────────
STAGES = ("preprocess", "filter", "generate", "gate")

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
    {"key": "저품질 이미지", "desc": "흐림 · 최소 해상도 · 노출 이상",
     "param": {"name": "흐림 기준값", "key": "blur", "min": 10, "max": 90, "unit": "", "default": 40}},
    {"key": "민감 콘텐츠", "desc": "유해 이미지 차단 · 개인정보 검출 후 가림",
     "param": {"name": "유해 이미지 기준값", "key": "nsfw", "min": 50, "max": 99, "unit": "ratio", "default": 85}},
)

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
GENERATION_MODELS = (
    {"id": "qwen8b", "name": "Qwen3-VL-8B-Instruct", "license": "apache-2.0", "family": "qwen"},
    {"id": "qwen4b", "name": "Qwen3-VL-4B-Instruct", "license": "apache-2.0", "family": "qwen"},
    {"id": "intern3", "name": "InternVL3-8B", "license": "mit", "family": "internvl"},
    {"id": "gemma3", "name": "Gemma 3 12B", "license": "Gemma Terms", "family": "gemma"},
)

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
