"""
demo/app.py — VisionLanguageModelV2 SDS 데모 웹 애플리케이션

네 가지 데이터셋 포맷을 자동 감지하여 지원한다.

  [구 포맷 — 20260227]  input_data.csv + input_image.png + output_*.txt 5종
  [신 포맷 — 20250922]  input.csv (소문자) + frame_N.png + output.csv
  [신 포맷 — 20251031]  input.csv (대소문자) + frame_N.png + output.csv
  [평면 포맷 — 20260728] csv/ png/ describe_ko/ advice_ko/ 4개 디렉토리에
                         동일 stem 파일이 병렬 배치 (샘플 10,000개)
                         ※ bbox_* 는 배포본에 따라 이미지 좌표계와 맞기도 하고
                           어긋나기도 한다. 박스는 원본 값 그대로 그리고
                           모델 프롬프트에서만 뺀다. FLAT_BBOX_NOTICE 참고.

레이아웃:
  [상단 좌] 이미지 / CSV 테이블     [상단 우] 데이터셋 탐색기 (+ 프레임/인덱스 선택)
  ─────────────────────────────────────────────────────────────────────
  [중단 좌] 기대값 (출력유형 선택)   [중단 우] 모델 설정 + 출력유형
  ─────────────────────────────────────────────────────────────────────
  [하단] 채팅 (전체 너비)

실행:
  python demo/app.py
  → http://localhost:7860
"""
import gc
import glob
import os
import random
import re
import sys
import traceback
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import torch

# ── Path setup ────────────────────────────────────────────────────────────────
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
VLM_DIR  = os.path.dirname(DEMO_DIR)
sys.path.insert(0, VLM_DIR)

import gradio as gr

# ── Constants ─────────────────────────────────────────────────────────────────
# 절대경로 대신 VLM_DIR 기준 상대경로로 산출.
# 기본값을 평면 포맷으로 두면 시작 직후부터 인덱스 네비게이션이 표시된다.
DEFAULT_DATASET_PATH = os.path.normpath(os.path.join(VLM_DIR, "../dataset/20260728"))
CHECKPOINTS_ROOT     = os.path.join(VLM_DIR, "checkpoints")
DEFAULT_VISION_MODEL = "openai/clip-vit-large-patch14-336"
DEFAULT_LLM_MODEL    = "meta-llama/Llama-3.1-8B-Instruct"

# ── 출력 유형 ─────────────────────────────────────────────────────────────────
# 구 포맷 (20260227): 5종
OLD_OUTPUT_TYPES = [
    "영문 해상상황묘사",
    "한글 해상상황묘사",
    "영문 항해조력메시지",
    "한글 항해조력메시지",
    "간결 항해조력메시지",
]
# 신 포맷 (20250922 / 20251031): 단일
NEW_OUTPUT_TYPE  = "항해 상황인식"
NEW_OUTPUT_TYPES = [NEW_OUTPUT_TYPE]

# 평면 포맷 (20260728): 국문 2종 (describe_ko / advice_ko)
FLAT_OUTPUT_TYPES = [
    "한글 해상상황묘사",
    "한글 항해조력메시지",
]

OUTPUT_TYPES = OLD_OUTPUT_TYPES  # UI 초기값 (구 포맷 기준)

FILE_MAP = {
    "영문 해상상황묘사":    "output_describe_en.txt",
    "한글 해상상황묘사":   "output_describe_kor.txt",
    "영문 항해조력메시지":  "output_advice_en.txt",
    "한글 항해조력메시지": "output_advice_kor.txt",
    "간결 항해조력메시지": "output_advice_compact.txt",
}

# 평면 포맷: 출력유형 → (디렉토리, 파일 접미사)
FLAT_FILE_MAP = {
    "한글 해상상황묘사":   ("describe_ko", ".describe_ko.txt"),
    "한글 항해조력메시지": ("advice_ko",   ".advice_ko.txt"),
}

# 평면 포맷 판별에 필요한 최소 디렉토리
FLAT_REQUIRED_DIRS = ("csv", "png")

# 평면 포맷 샘플 드롭다운에 현재 인덱스 기준 앞뒤로 표시할 항목 수
FLAT_WINDOW = 50

# 평면 포맷(20260728)의 bbox_* 는 배포본에 따라 두 가지가 돌아다닌다.
#
#   구 배포본  PNG 와 다른 카메라 기준. AIS 상대방위로 핀홀 모델을 적합하면
#              광학중심이 562px(폭 약 1124 기준)로 나와 1920 폭 이미지와 맞지
#              않는다. 타선 1척 샘플 250건에서 IoU 는 전 건 0, 박스 중심
#              거리는 중앙값 442px 였다.
#   신 배포본  이미지 좌표계로 맞춰져 있다. 같은 적합에서 광학중심 960.2px,
#              R²=0.9998, 잔차 중앙값 1.31px 로 1920 폭 이미지 중심과 맞는다.
#
# 어느 쪽인지 파일만 보고는 알 수 없으므로 박스는 CSV 값 그대로 그린다.
# 신 배포본이면 선박 위에 놓이고, 구 배포본이면 눈에 띄게 어긋나 보인다.
#
# 모델 프롬프트의 AIS 텍스트에서는 바운딩박스를 뺀다. 지금 체크포인트들이
# 구 배포본으로, 그것도 bbox 없는 입력으로 학습되었으므로 추론 입력도 같아야
# 한다. AIS 표에는 원본 값을 그대로 보여준다.
FLAT_BBOX_NOTICE = (
    "ℹ️ 바운딩박스는 `bbox_*` 값을 그대로 그립니다. 이 데이터셋의 구 배포본은 "
    "좌표가 다른 카메라 기준이라 박스가 선박에서 크게 벗어나 보이고, 신 배포본은 "
    "선박 위에 놓입니다. 모델 프롬프트에서는 bbox 를 제외합니다. 현재 체크포인트가 "
    "bbox 없는 입력으로 학습되었기 때문입니다. AIS 표에는 원본 값을 그대로 "
    "표시합니다."
)

PROMPT_MAP = {
    "영문 해상상황묘사":
        "Based on the camera image and AIS data provided, describe the current maritime situation in detail.",
    "한글 해상상황묘사":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 현재 해상 상황을 상세히 묘사하시오.",
    "영문 항해조력메시지":
        "Based on the camera image and AIS data provided, provide navigational advice "
        "for the own vessel in accordance with COLREG rules.",
    "한글 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 COLREG 규칙에 따른 "
        "자선의 항해 조력 메시지를 제공하시오.",
    "간결 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 간결한 항해 조력 메시지를 제공하시오. "
        "속도 조치, 방향 조치, 적용 근거(COLREG 조항)를 포함하시오.",
    NEW_OUTPUT_TYPE:
        "사진과 AIS 데이터를 바탕으로 현재 해상상황을 묘사하고 "
        "COLREG 규칙에 따른 올바른 항해 조력 메시지를 생성하시오.",
}

CSV_KO_COLUMNS = {
    "timestamp":    "시간",
    "my_ship":      "자선여부",
    "ship_id":      "선박ID",
    "ship_type":    "선박종류",
    "length":       "길이(m)",
    "width":        "너비(m)",
    "draft":        "흘수(m)",
    "latitude":     "위도",
    "longitude":    "경도",
    "knot":         "속도(kt)",
    "heading":      "방향(°)",
    "bbox_x":       "BBox_X",
    "bbox_y":       "BBox_Y",
    "bbox_width":   "BBox_W",
    "bbox_height":  "BBox_H",
    "cpa":          "CPA(NM)",
    "tcpa":         "TCPA(s)",
}

# ── Global model state ────────────────────────────────────────────────────────
_model = None
_model_device = None

# ── Global SPICE scorer (lazy-initialized on first use) ───────────────────────
_spice_scorer = None


def _get_spice_scorer():
    """Spice scorer를 lazy-init한다. Java 11 호환 monkey-patch 포함."""
    global _spice_scorer
    if _spice_scorer is None:
        try:
            import subprocess as _sp
            import pycocoevalcap.spice.spice as _spice_mod

            _orig_check_call = _sp.check_call

            def _java11_check_call(cmd, **kwargs):
                if isinstance(cmd, list) and cmd and cmd[0] == "java" and "-jar" in cmd:
                    java11_flags = [
                        "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                        "--add-opens", "java.base/java.util=ALL-UNNAMED",
                    ]
                    cmd = [cmd[0]] + java11_flags + cmd[1:]
                return _orig_check_call(cmd, **kwargs)

            _spice_mod.subprocess.check_call = _java11_check_call

            from pycocoevalcap.spice.spice import Spice
            _spice_scorer = Spice()
        except Exception:
            pass
    return _spice_scorer


def compute_spice(hypothesis: str, reference: str) -> dict | None:
    """SPICE F-score를 계산한다.

    pycocoevalcap이 없거나 reference가 비어 있으면 None을 반환한다.
    reference가 오류 메시지("(" 로 시작)인 경우에도 None을 반환한다.

    Note: spice.py는 plain string 형식을 기대한다. dict {"caption": ...} 형식을
    전달하면 Java ClassCastException이 발생하므로 반드시 plain string을 사용한다.
    """
    if not hypothesis or not reference:
        return None
    reference = reference.strip()
    if reference.startswith("(") or reference.startswith("❌"):
        return None

    scorer = _get_spice_scorer()
    if scorer is None:
        return {"error": "pycocoevalcap 미설치 — pip install pycocoevalcap"}

    try:
        # plain string 형식: {"caption":...} dict가 아닌 문자열 직접 전달
        gts = {0: [reference]}
        res = {0: [hypothesis]}
        score, scores = scorer.compute_score(gts, res)
        detail = scores[0] if scores else {}
        return {"F": round(float(score), 4), "detail": detail}
    except Exception as exc:
        return {"error": str(exc)}


def _is_korean(text: str) -> bool:
    """텍스트에 한글 문자가 포함되어 있으면 True."""
    return any("가" <= c <= "힣" for c in text)


def format_spice_result(result: dict | None, hypothesis: str = "") -> str:
    """SPICE 결과 dict를 Markdown 문자열로 포맷한다."""
    if result is None:
        return ""
    if "error" in result:
        return f"⚠️ SPICE 계산 실패: {result['error']}"

    f_score = result.get("F", 0.0)
    detail  = result.get("detail", {})
    lines   = ['<br><br>', "### 📊 SPICE 평가 결과", f"**전체 F-score: `{f_score:.4f}`**"]

    if hypothesis and _is_korean(hypothesis):
        lines.append(
            "> ℹ️ SPICE는 Stanford CoreNLP 기반으로 영문에 최적화되어 있습니다. "
            "한국어 텍스트의 경우 점수가 낮게 측정될 수 있습니다."
        )

    cat_order = ["All", "Object", "Relation", "Attribute",
                 "Cardinality", "Color", "Count", "Size"]
    cat_kr = {
        "All": "전체", "Object": "객체", "Relation": "관계",
        "Attribute": "속성", "Cardinality": "수량", "Color": "색상",
        "Count": "개수", "Size": "크기",
    }

    # 존재하는 카테고리만 수집
    present = [(cat_kr.get(c, c), detail[c]) for c in cat_order if detail.get(c)]

    if present:
        col_names = [name for name, _ in present]
        header    = "| 지표 | " + " | ".join(col_names) + " |"
        sep       = "|---| " + " | ".join("---" for _ in present) + " |"
        pr_row    = "| Precision | " + " | ".join(f"{d.get('pr', 0):.3f}" for _, d in present) + " |"
        re_row    = "| Recall    | " + " | ".join(f"{d.get('re', 0):.3f}" for _, d in present) + " |"
        f_row     = "| F-score   | " + " | ".join(f"{d.get('f',  0):.3f}" for _, d in present) + " |"
        lines += ["", header, sep, pr_row, re_row, f_row]

    return "\n".join(lines)


# ── Dataset format helpers ────────────────────────────────────────────────────

def _natural_sort_key(s: str):
    """숫자 포함 문자열을 자연 순서(dataset1 < dataset2 < dataset10)로 정렬하는 키."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def _is_flat_dataset(dataset_path: str) -> bool:
    """평면 포맷(20260728) 여부. csv/ 와 png/ 디렉토리가 모두 있으면 True."""
    root = dataset_path.strip()
    return all(os.path.isdir(os.path.join(root, d)) for d in FLAT_REQUIRED_DIRS)


# 평면 포맷 샘플 stem 목록 캐시 (10,000개 파일 목록을 이벤트마다 재조회하지 않기 위함)
_FLAT_CACHE: dict = {}


def _flat_samples(dataset_path: str, refresh: bool = False) -> list:
    """평면 포맷 데이터셋의 샘플 stem 목록을 정렬하여 반환 (캐시)."""
    key = os.path.realpath(dataset_path.strip())
    if refresh or key not in _FLAT_CACHE:
        csv_dir = os.path.join(key, "csv")
        if os.path.isdir(csv_dir):
            _FLAT_CACHE[key] = sorted(
                os.path.splitext(f)[0]
                for f in os.listdir(csv_dir)
                if f.endswith(".csv")
            )
        else:
            _FLAT_CACHE[key] = []
    return _FLAT_CACHE[key]


def _flat_index_of(dataset_path: str, sample_name: str):
    """평면 포맷에서 샘플 stem의 인덱스를 반환. 없으면 None."""
    samples = _flat_samples(dataset_path)
    try:
        return samples.index(sample_name)
    except ValueError:
        return None


def _flat_dropdown_update(samples: list, index: int):
    """현재 인덱스 주변 창(window)만 담은 샘플 드롭다운 업데이트를 생성."""
    if not samples:
        return gr.update(choices=[], value=None)
    index = max(0, min(len(samples) - 1, index))
    lo = max(0, index - FLAT_WINDOW)
    hi = min(len(samples), index + FLAT_WINDOW + 1)
    return gr.update(choices=samples[lo:hi], value=samples[index])


def _detect_fmt(dataset_path: str, sample_name: str = "") -> str:
    """포맷을 감지한다.

    'flat' — 평면 포맷 (20260728): 데이터셋 루트에 csv/ png/ 디렉토리
    'new'  — 샘플 디렉토리에 input.csv + output.csv
    'old'  — 샘플 디렉토리에 input_data.csv
    """
    if _is_flat_dataset(dataset_path):
        return "flat"
    sample_dir = os.path.join(dataset_path.strip(), sample_name)
    if os.path.exists(os.path.join(sample_dir, "input.csv")):
        return "new"
    return "old"


def _list_frames(sample_dir: str) -> list:
    """frame_*.png 파일을 숫자 순으로 반환 (확장자 제외)."""
    names = [
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(sample_dir, "frame_*.png"))
    ]
    return sorted(names, key=lambda n: int(n.split("_")[-1]))


def _load_csv_normalized(path: str) -> pd.DataFrame:
    """CSV 읽고 컬럼명을 소문자로 정규화."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower()
    return df


def _format_ais_df(df: pd.DataFrame, lang: str, include_bbox: bool = True) -> str:
    """정규화된 DataFrame으로 AIS 텍스트 생성.

    ship_type 컬럼이 있으면 포함한다. cpa/tcpa 컬럼(평면 포맷 20260728)이 있으면
    타선 항목에 함께 포함한다.

    include_bbox=False 이면 타선 항목에서 바운딩박스를 뺀다. 평면 포맷은 현재
    체크포인트가 bbox 없는 입력으로 학습되었으므로 이 경로를 쓴다
    (FLAT_BBOX_NOTICE).

    이 문자열은 모델 입력이 되므로 scripts/prepare_sds_dataset.py 의
    format_ais() 와 같아야 한다. 한쪽만 고치면 학습 프롬프트와 추론 프롬프트가
    갈라진다.
    """
    has_type = "ship_type" in df.columns
    has_cpa  = "cpa" in df.columns and "tcpa" in df.columns

    def _cpa_str(row, en: bool) -> str:
        if not has_cpa:
            return ""
        if en:
            return f" | CPA:{float(row['cpa']):.4f}NM TCPA:{float(row['tcpa']):.2f}s"
        return f" | CPA:{float(row['cpa']):.4f}NM TCPA:{float(row['tcpa']):.2f}초"

    def _bbox_str(row, en: bool) -> str:
        if not include_bbox:
            return ""
        bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
        label = "BoundingBox" if en else "바운딩박스"
        return f" | {label}:[{bbox}]"

    if lang == "en":
        lines = ["[Vessel AIS Information]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m x {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            stype = f" Type:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- Own vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                lines.append(
                    f"- Nearby vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                    f"{_bbox_str(row, True)}{_cpa_str(row, True)}"
                )
    else:
        lines = ["[선박 AIS 정보]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m × {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            stype = f" 종류:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- 자선 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                lines.append(
                    f"- 주변선박 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                    f"{_bbox_str(row, False)}{_cpa_str(row, False)}"
                )
    return "\n".join(lines)


# ── Dataset helpers ───────────────────────────────────────────────────────────

def scan_dataset(path: str):
    """데이터셋 경로를 스캔하여 샘플 목록을 반환.

    반환값 5개: (샘플 드롭다운, 상태 메시지, 인덱스 네비 표시여부, 인덱스 값, 전체 개수 라벨)
    """
    path = path.strip()
    # 레이아웃 블록(Column)의 표시 여부는 gr.update() 가 아닌 컴포넌트 인스턴스로 갱신한다.
    # Gradio 6 에서 gr.update(visible=...) 는 레이아웃 블록에 적용되지 않는다.
    _hide_nav = (gr.Column(visible=False), 0, "")

    if not os.path.isdir(path):
        return (gr.update(choices=[], value=None),
                f"❌ 경로를 찾을 수 없습니다: `{path}`", *_hide_nav)

    # ── 평면 포맷 (20260728): csv/ 의 stem 목록이 곧 샘플 목록 ──────────────
    if _is_flat_dataset(path):
        samples = _flat_samples(path, refresh=True)
        if not samples:
            return (gr.update(choices=[], value=None),
                    "⚠️ `csv/` 디렉토리에 샘플이 없습니다.", *_hide_nav)
        return (
            _flat_dropdown_update(samples, 0),
            f"✅ **{len(samples):,}개** 샘플 발견 (평면 포맷)",
            gr.Column(visible=True),
            0,
            f"총 {len(samples):,}개 · 인덱스 0 ~ {len(samples) - 1}",
        )

    # ── 디렉토리 포맷 (20250922 / 20251031 / 20260227) ─────────────────────
    samples = sorted(
        [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))],
        key=_natural_sort_key,
    )

    if not samples:
        return (gr.update(choices=[], value=None),
                "⚠️ 샘플 디렉토리가 없습니다.", *_hide_nav)

    return (
        gr.update(choices=samples, value=samples[0]),
        f"✅ **{len(samples)}개** 샘플 발견",
        *_hide_nav,
    )


def _draw_bboxes(image: Image.Image, df: pd.DataFrame) -> Image.Image:
    """타선 바운딩 박스를 초록색으로 그리고 선박ID 이름표를 추가. (df는 소문자 컬럼)"""
    img = image.copy()
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15
        )
    except OSError:
        font = ImageFont.load_default()

    BOX_COLOR  = "#00FF00"
    TEXT_BG    = "#00CC00"
    TEXT_FG    = "#000000"
    LINE_WIDTH = 2

    for _, row in df.iterrows():
        if int(row["my_ship"]) == 1:
            continue

        x = float(row["bbox_x"])
        y = float(row["bbox_y"])
        w = float(row["bbox_width"])
        h = float(row["bbox_height"])

        if w <= 0 or h <= 0:
            continue

        ship_id = int(row["ship_id"])
        label   = f" ID:{ship_id} "

        draw.rectangle([x, y, x + w, y + h], outline=BOX_COLOR, width=LINE_WIDTH)

        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        label_y = y - th - 4 if y - th - 4 >= 0 else y + 2
        draw.rectangle([x, label_y, x + tw, label_y + th + 2], fill=TEXT_BG)
        draw.text((x, label_y + 1), label, fill=TEXT_FG, font=font)

    return img


def load_sample(dataset_path: str, sample_name: str, frame: str = None):
    """선택된 샘플/프레임의 이미지(bbox 포함)와 CSV를 반환."""
    if not sample_name:
        return None, pd.DataFrame()

    root = dataset_path.strip()
    fmt  = _detect_fmt(root, sample_name)

    if fmt == "flat":
        csv_path = os.path.join(root, "csv", f"{sample_name}.csv")
        img_path = os.path.join(root, "png", f"{sample_name}.png")

        df_raw = _load_csv_normalized(csv_path) if os.path.exists(csv_path) else None
        image  = Image.open(img_path).convert("RGB") if os.path.exists(img_path) else None

        # bbox_* 를 원본 값 그대로 그린다 (FLAT_BBOX_NOTICE).
        # 모델 프롬프트에서는 여전히 제외한다.
        if image is not None and df_raw is not None and not df_raw.empty:
            image = _draw_bboxes(image, df_raw)

        if df_raw is not None:
            df_display = df_raw.rename(columns=CSV_KO_COLUMNS)
            if "자선여부" in df_display.columns:
                df_display["자선여부"] = df_display["자선여부"].map({1: "✅ 자선", 0: "타선"})
        else:
            df_display = pd.DataFrame({"오류": [f"csv 없음: {sample_name}.csv"]})

        return image, df_display

    sample_dir = os.path.join(root, sample_name)

    if fmt == "new":
        if not frame:
            frames = _list_frames(sample_dir)
            frame = frames[0] if frames else None
        if not frame:
            return None, pd.DataFrame({"오류": ["프레임 없음"]})

        csv_path = os.path.join(sample_dir, "input.csv")
        img_path = os.path.join(sample_dir, f"{frame}.png")

        if os.path.exists(csv_path):
            df_all   = _load_csv_normalized(csv_path)
            df_frame = df_all[df_all["file_name"] == frame].copy()
        else:
            df_frame = None

        image = Image.open(img_path).convert("RGB") if os.path.exists(img_path) else None
        if image is not None and df_frame is not None and not df_frame.empty:
            image = _draw_bboxes(image, df_frame)

        if df_frame is not None and not df_frame.empty:
            df_display = (
                df_frame
                .drop(columns=["file_name"], errors="ignore")
                .rename(columns=CSV_KO_COLUMNS)
            )
            if "자선여부" in df_display.columns:
                df_display["자선여부"] = df_display["자선여부"].map({1: "✅ 자선", 0: "타선"})
        else:
            df_display = pd.DataFrame({"오류": ["input.csv 없음 또는 해당 프레임 없음"]})

        return image, df_display

    else:
        csv_path = os.path.join(sample_dir, "input_data.csv")
        img_path = os.path.join(sample_dir, "input_image.png")

        df_raw = _load_csv_normalized(csv_path) if os.path.exists(csv_path) else None
        image  = Image.open(img_path).convert("RGB") if os.path.exists(img_path) else None

        if image is not None and df_raw is not None:
            image = _draw_bboxes(image, df_raw)

        if df_raw is not None:
            df_display = df_raw.rename(columns=CSV_KO_COLUMNS)
            if "자선여부" in df_display.columns:
                df_display["자선여부"] = df_display["자선여부"].map({1: "✅ 자선", 0: "타선"})
        else:
            df_display = pd.DataFrame({"오류": ["input_data.csv 없음"]})

        return image, df_display


def load_expected(
    dataset_path: str, sample_name: str, output_type: str, frame: str = None
) -> str:
    """선택된 출력 유형의 기대값 텍스트를 반환."""
    if not sample_name or not output_type:
        return ""

    root = dataset_path.strip()
    fmt  = _detect_fmt(root, sample_name)

    if fmt == "flat":
        entry = FLAT_FILE_MAP.get(output_type)
        if entry is None:
            return f"(지원하지 않는 출력 유형: {output_type})"
        subdir, suffix = entry
        path = os.path.join(root, subdir, f"{sample_name}{suffix}")
        if not os.path.exists(path):
            return f"(파일 없음: {subdir}/{sample_name}{suffix})"
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    sample_dir = os.path.join(root, sample_name)

    if fmt == "new":
        if not frame:
            frames = _list_frames(sample_dir)
            frame = frames[0] if frames else None
        csv_path = os.path.join(sample_dir, "output.csv")
        if not os.path.exists(csv_path) or not frame:
            return "(output.csv 없음)"
        df = _load_csv_normalized(csv_path)
        row = df[df["file_name"] == frame]
        if row.empty:
            return f"({frame} 항목 없음)"
        return str(row.iloc[0]["text"]).strip()

    else:
        filename = FILE_MAP.get(output_type, "")
        path = os.path.join(sample_dir, filename)
        if not os.path.exists(path):
            return f"(파일 없음: {filename})"
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()


def format_ais_text(
    dataset_path: str, sample_name: str, lang: str = "ko", frame: str = None
) -> str:
    """CSV를 자연어 형태로 포맷하여 모델 프롬프트에 포함할 텍스트 생성."""
    root = dataset_path.strip()
    fmt  = _detect_fmt(root, sample_name)

    if fmt == "flat":
        csv_path = os.path.join(root, "csv", f"{sample_name}.csv")
        if not os.path.exists(csv_path):
            return ""
        # 평면 포맷은 bbox 를 프롬프트에 넣지 않는다. 이 데이터셋으로 학습한
        # 체크포인트가 bbox 없는 입력으로 학습되므로 추론도 같아야 한다.
        return _format_ais_df(
            _load_csv_normalized(csv_path), lang, include_bbox=False
        )

    sample_dir = os.path.join(root, sample_name)

    if fmt == "new":
        if not frame:
            frames = _list_frames(sample_dir)
            frame = frames[0] if frames else None
        csv_path = os.path.join(sample_dir, "input.csv")
        if not os.path.exists(csv_path) or not frame:
            return ""
        df = _load_csv_normalized(csv_path)
        df = df[df["file_name"] == frame]
    else:
        csv_path = os.path.join(sample_dir, "input_data.csv")
        if not os.path.exists(csv_path):
            return ""
        df = _load_csv_normalized(csv_path)

    return _format_ais_df(df, lang)


# ── Model helpers ─────────────────────────────────────────────────────────────

def get_checkpoint_choices():
    result = []
    if os.path.isdir(CHECKPOINTS_ROOT):
        for root, dirs, files in os.walk(CHECKPOINTS_ROOT):
            if "projector.bin" in files:
                rel      = os.path.relpath(root, VLM_DIR)
                has_lora = os.path.exists(os.path.join(root, "adapter_config.json"))
                label    = f"{rel}  [LoRA]" if has_lora else rel
                result.append(label)
    return sorted(result) or ["(체크포인트 없음)"]


def _unload_model():
    global _model, _model_device
    if _model is not None:
        _model.cpu()
        del _model
        _model = None
        _model_device = None
        gc.collect()
        torch.cuda.empty_cache()


def load_model(checkpoint_label: str, vision_model: str, llm_model: str) -> str:
    global _model, _model_device

    if not checkpoint_label or checkpoint_label == "(체크포인트 없음)":
        return "❌ 유효한 체크포인트를 선택하세요."

    checkpoint_dir_rel = checkpoint_label.replace("  [LoRA]", "").strip()
    checkpoint_dir     = os.path.join(VLM_DIR, checkpoint_dir_rel)

    projector_path = os.path.join(checkpoint_dir, "projector.bin")
    if not os.path.exists(projector_path):
        return f"❌ projector.bin을 찾을 수 없습니다:\n`{checkpoint_dir}`"

    has_lora = os.path.exists(os.path.join(checkpoint_dir, "adapter_config.json"))
    _unload_model()

    try:
        from model import VLMConfig, build_model as _build
        from model.checkpoint import load_projector_config, resolve_projector_settings

        # 프로젝터 구조는 학습 시점에 결정되므로 체크포인트에 기록된 값을 따른다.
        # vlm_config.json 이 없는 구 체크포인트는 VLMConfig 기본값(mlp2x_gelu)으로 떨어진다.
        proj_settings, proj_sources = resolve_projector_settings(
            {}, load_projector_config(projector_path)
        )
        print(f"[Demo] Projector type: {proj_settings['projector_type']} "
              f"(from {proj_sources['projector_type']})")

        config = VLMConfig(
            vision_model_name=vision_model.strip(),
            llm_model_name=llm_model.strip(),
            freeze_vision=True,
            freeze_llm=not has_lora,
            **proj_settings,
        )

        m = _build(config, torch_dtype=torch.bfloat16)

        proj_state = torch.load(projector_path, map_location="cpu", weights_only=True)
        m.projector.load_weights(proj_state)

        if has_lora:
            from peft import PeftModel
            m.language_model = PeftModel.from_pretrained(
                m.language_model, checkpoint_dir, torch_dtype=torch.bfloat16,
            )
            m.language_model = m.language_model.merge_and_unload()
            print("[Demo] LoRA weights merged.")

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        m = m.to(device)
        m.eval()

        _model        = m
        _model_device = device

        mem_gb   = torch.cuda.memory_allocated(device) / 1e9 if device.type == "cuda" else 0
        mode_str = "프로젝터 + LoRA" if has_lora else "프로젝터 전용"
        # 리샘플러 계열은 패치 수와 무관하게 쿼리 토큰 수만큼 이미지 토큰을 만든다.
        proj_desc = f"`{config.projector_type}`"
        if config.is_resampler_projector:
            proj_desc += f" (쿼리 토큰 {config.projector_num_query_tokens}개)"
        return (
            f"✅ **모델 로드 완료** ({mode_str})\n"
            f"- 체크포인트: `{checkpoint_dir_rel}`\n"
            f"- 디바이스: `{device}` (VRAM {mem_gb:.1f} GB 사용)\n"
            f"- 프로젝터: {proj_desc}\n"
            f"- 이미지 토큰: `{config.num_image_tokens}개`\n"
            f"- 어휘 크기: `{len(m.tokenizer)}`"
        )

    except Exception:
        _unload_model()
        return f"❌ 모델 로드 실패:\n```\n{traceback.format_exc()}\n```"


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(
    dataset_path: str,
    sample_name: str,
    output_type: str,
    user_prompt: str,
    history: list,
    frame: str,
):
    history = list(history or [])

    if _model is None:
        history.append({"role": "assistant", "content": "⚠️ 먼저 모델을 로드해주세요."})
        return history
    if not sample_name:
        history.append({"role": "assistant", "content": "⚠️ 샘플을 선택해주세요."})
        return history

    root       = dataset_path.strip()
    fmt        = _detect_fmt(root, sample_name)
    sample_dir = os.path.join(root, sample_name)

    lang     = "en" if "영문" in output_type else "ko"
    ais_text = format_ais_text(dataset_path, sample_name, lang=lang, frame=frame)
    question = user_prompt.strip() if user_prompt.strip() else PROMPT_MAP.get(output_type, "")
    full_question = f"{ais_text}\n\n{question}" if ais_text else question

    frame_label = f" `{frame}`" if frame else ""
    user_msg = (
        f"**[샘플]** `{sample_name}`{frame_label}\n"
        f"**[출력유형]** {output_type}\n\n"
        f"```\n{ais_text}\n```\n\n"
        f"**{question}**"
    )
    history.append({"role": "user", "content": user_msg})

    try:
        if fmt == "flat":
            img_path = os.path.join(root, "png", f"{sample_name}.png")
        elif fmt == "new":
            if not frame:
                frames = _list_frames(sample_dir)
                frame = frames[0] if frames else None
            img_path = os.path.join(sample_dir, f"{frame}.png")
        else:
            img_path = os.path.join(sample_dir, "input_image.png")

        image = Image.open(img_path).convert("RGB")

        tokenizer       = _model.tokenizer
        image_processor = _model.vision_encoder.image_processor

        messages    = [{"role": "user", "content": f"<image>\n{full_question}"}]
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

        pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(_model_device, dtype=torch.bfloat16)

        input_ids = tokenizer(
            prompt_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids.to(_model_device)
        attention_mask = torch.ones_like(input_ids)

        with torch.no_grad():
            output_ids = _model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pixel_values=pixel_values,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1,
            )

        response = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        if "</think>" in response:
            response = response.split("</think>")[-1].strip()
        elif full_question in response:
            response = response.split(full_question)[-1].strip()

        history.append({"role": "assistant", "content": response})

        # ── SPICE 점수 계산 ────────────────────────────────────────────────
        expected_text = load_expected(dataset_path, sample_name, output_type, frame)
        spice_result  = compute_spice(response, expected_text)
        spice_md      = format_spice_result(spice_result, hypothesis=response)
        if spice_md:
            history.append({"role": "assistant", "content": spice_md})

    except Exception:
        history.append({
            "role": "assistant",
            "content": f"❌ 추론 실패:\n```\n{traceback.format_exc()}\n```",
        })

    return history


# ── UI event helpers ──────────────────────────────────────────────────────────

def on_sample_change(dataset_path: str, sample_name: str, current_ot: str):
    """샘플 선택 시 포맷 감지 → 프레임 드롭다운 / 출력유형 / 이미지 / 기대값 일괄 갱신.

    반환값 9개: (이미지, CSV, 프레임DD, 출력유형Radio, 채팅유형Radio, 기대값,
                 ot State, 인덱스, 이미지 안내문구)
    """
    _default_ot = OLD_OUTPUT_TYPES[0]
    _empty = (
        None, pd.DataFrame(),
        gr.update(choices=[], value=None, visible=False),
        gr.update(choices=OLD_OUTPUT_TYPES, value=_default_ot),
        gr.update(choices=OLD_OUTPUT_TYPES, value=_default_ot),
        "", _default_ot, gr.update(), "",
    )

    if not sample_name:
        return _empty

    try:
        root = dataset_path.strip()
        fmt  = _detect_fmt(root, sample_name)

        if fmt == "flat":
            ot  = current_ot if current_ot in FLAT_OUTPUT_TYPES else FLAT_OUTPUT_TYPES[0]
            idx = _flat_index_of(root, sample_name)
            img, df  = load_sample(dataset_path, sample_name)
            expected = load_expected(dataset_path, sample_name, ot)
            return (
                img, df,
                gr.update(choices=[], value=None, visible=False),
                gr.update(choices=FLAT_OUTPUT_TYPES, value=ot),
                gr.update(choices=FLAT_OUTPUT_TYPES, value=ot),
                expected, ot,
                gr.update() if idx is None else idx,
                FLAT_BBOX_NOTICE,
            )

        sample_dir = os.path.join(root, sample_name)

        if fmt == "new":
            frames = _list_frames(sample_dir)
            frame  = frames[0] if frames else None
            img, df = load_sample(dataset_path, sample_name, frame)
            expected = load_expected(dataset_path, sample_name, NEW_OUTPUT_TYPE, frame)
            return (
                img, df,
                gr.update(choices=frames, value=frame, visible=True),
                gr.update(choices=NEW_OUTPUT_TYPES, value=NEW_OUTPUT_TYPE),
                gr.update(choices=NEW_OUTPUT_TYPES, value=NEW_OUTPUT_TYPE),
                expected, NEW_OUTPUT_TYPE, gr.update(), "",
            )
        else:
            ot = current_ot if current_ot in OLD_OUTPUT_TYPES else _default_ot
            img, df  = load_sample(dataset_path, sample_name)
            expected = load_expected(dataset_path, sample_name, ot)
            return (
                img, df,
                gr.update(choices=[], value=None, visible=False),
                gr.update(choices=OLD_OUTPUT_TYPES, value=ot),
                gr.update(choices=OLD_OUTPUT_TYPES, value=ot),
                expected, ot, gr.update(), "",
            )
    except Exception as exc:
        err_df = pd.DataFrame({"오류": [str(exc)]})
        return (
            None, err_df,
            gr.update(choices=[], value=None, visible=False),
            gr.update(choices=OLD_OUTPUT_TYPES, value=_default_ot),
            gr.update(choices=OLD_OUTPUT_TYPES, value=_default_ot),
            f"❌ 샘플 로드 실패: {exc}", _default_ot, gr.update(), "",
        )


def on_frame_change(dataset_path: str, sample_name: str, frame: str, output_type: str):
    """프레임 변경 시 이미지 / CSV / 기대값 갱신."""
    if not sample_name or not frame:
        return None, pd.DataFrame(), ""
    img, df  = load_sample(dataset_path, sample_name, frame)
    expected = load_expected(dataset_path, sample_name, output_type, frame)
    return img, df, expected


def on_output_type_change(dataset_path: str, sample_name: str, output_type: str, frame: str):
    """출력유형 변경 시 기대값과 프롬프트 기본값 갱신."""
    expected = load_expected(dataset_path, sample_name, output_type, frame)
    prompt   = PROMPT_MAP.get(output_type, "")
    return output_type, prompt, expected


def flat_goto(dataset_path: str, index):
    """평면 포맷에서 인덱스로 이동. (인덱스 값, 샘플 드롭다운 업데이트) 반환.

    드롭다운 값이 바뀌면 sample_list.change 가 발생하여 나머지 UI가 갱신된다.
    """
    samples = _flat_samples(dataset_path)
    if not samples:
        return gr.update(), gr.update()

    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    i = max(0, min(len(samples) - 1, i))

    return i, _flat_dropdown_update(samples, i)


def flat_step(dataset_path: str, index, delta: int):
    """현재 인덱스에서 delta 만큼 이동 (범위를 벗어나면 양끝에서 멈춘다)."""
    try:
        cur = int(index)
    except (TypeError, ValueError):
        cur = 0
    return flat_goto(dataset_path, cur + delta)


def flat_random(dataset_path: str):
    """평면 포맷에서 임의의 샘플로 이동."""
    samples = _flat_samples(dataset_path)
    if not samples:
        return gr.update(), gr.update()
    return flat_goto(dataset_path, random.randrange(len(samples)))


def _initial_visibility(dataset_path: str):
    """앱 시작 시점의 (프레임 드롭다운, 인덱스 네비게이션) 표시 여부를 결정한다.

    Gradio 6 에서는 demo.load 가 페이지 로드 직후 visible 을 갱신하면 그 이후의
    첫 번째 visible 변경이 프런트엔드에 반영되지 않는다. 따라서 초기 표시 여부는
    빌드 시점에 확정하고, 로드 핸들러는 visible 을 전송하지 않는다.
    """
    try:
        path = dataset_path.strip()
        if _is_flat_dataset(path):
            return False, True
        subs = sorted(
            (d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))),
            key=_natural_sort_key,
        )
        if subs and _detect_fmt(path, subs[0]) == "new":
            return True, False
    except OSError:
        pass
    return False, False


def _strip_visible(update):
    """업데이트 dict 에서 visible 키를 제거한다. (demo.load 전용)"""
    if isinstance(update, dict) and "visible" in update:
        return {k: v for k, v in update.items() if k != "visible"}
    return update


# ── Gradio UI ─────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
    .section-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; }
    .csv-table { font-size: 0.82rem; }
    #expected-box textarea { font-size: 0.85rem; line-height: 1.6; }
    .idx-total p { font-size: 0.8rem; opacity: 0.75; margin: 2px 0 0 2px; }
    .img-notice p { font-size: 0.82rem; line-height: 1.5; margin: 4px 2px 0 2px;
                    color: #92400e; background: #fef3c7; border-left: 3px solid #f59e0b;
                    padding: 6px 10px; border-radius: 4px; }
"""


def build_ui():
    # 초기 표시 여부는 빌드 시점에 확정한다 (_initial_visibility 참고).
    init_frame_visible, init_nav_visible = _initial_visibility(DEFAULT_DATASET_PATH)

    with gr.Blocks(title="VLM SDS Demo") as demo:

        gr.Markdown("# 🚢 ETRI Vessel Agent (SDS-VLM)", elem_classes="section-title")
        gr.Markdown(
            "선박 자율항행 지원을 위한 추론 데모입니다.  \n"
            "Aivenautics 데이터셋 지원 포맷: **20250922·20251031** (구 포맷 — 프레임 선택 가능) / "
            "**20260227** (신 포맷) / **20260728** (평면 포맷 — 인덱스 이동)"
        )

        # ── 상단: 이미지/CSV + 탐색기 ──────────────────────────────────────────
        with gr.Row(equal_height=False):

            # 상단 좌: 이미지 + CSV
            with gr.Column(scale=3):
                gr.Markdown("### 📸 입력 이미지", elem_classes="section-title")
                img_display = gr.Image(label="이미지", height=320)
                # 값이 빈 문자열이면 아무것도 렌더링되지 않으므로 visible 토글이 불필요하다.
                img_notice = gr.Markdown("", elem_classes="img-notice")
                gr.Markdown("### 📊 AIS 데이터", elem_classes="section-title")
                csv_display = gr.Dataframe(
                    label="AIS",
                    interactive=False,
                    wrap=False,
                    elem_classes="csv-table",
                )

            # 상단 우: 탐색기
            with gr.Column(scale=1, min_width=280):
                gr.Markdown("### 📁 데이터셋 탐색기", elem_classes="section-title")

                with gr.Row():
                    path_input = gr.Textbox(
                        value=DEFAULT_DATASET_PATH,
                        label="데이터셋 경로",
                        placeholder="/path/to/dataset",
                        scale=4,
                    )
                    path_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                with gr.Row(visible=False) as path_explorer_row:
                    with gr.Column():
                        path_file_explorer = gr.FileExplorer(
                            root_dir="/home",
                            glob="**",
                            ignore_glob="**/.*",
                            file_count="single",
                            label="데이터셋 디렉토리 선택",
                            height=240,
                        )
                        path_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                scan_btn    = gr.Button("📂 스캔", variant="secondary", size="sm")
                scan_status = gr.Markdown("")

                # 평면 포맷 전용 인덱스 네비게이션 (평면 포맷일 때만 표시)
                with gr.Column(visible=init_nav_visible) as index_nav_col:
                    idx_number = gr.Number(
                        value=0,
                        precision=0,
                        minimum=0,
                        label="인덱스",
                    )
                    with gr.Row():
                        prev_btn = gr.Button("◀ 이전", size="sm", scale=1)
                        next_btn = gr.Button("다음 ▶", size="sm", scale=1)
                        rand_btn = gr.Button("🎲 랜덤", size="sm", scale=1)
                    idx_total_md = gr.Markdown("", elem_classes="idx-total")

                sample_list = gr.Dropdown(
                    choices=[],
                    value=None,
                    label="샘플 목록",
                )

                # 프레임 포맷 전용 프레임 선택 (해당 포맷일 때만 표시)
                frame_dd = gr.Dropdown(
                    choices=[],
                    value=None,
                    label="프레임 선택 (구 포맷)",
                    visible=init_frame_visible,
                )

        gr.Markdown("---")

        # ── 하단: 기대값 + 채팅 ────────────────────────────────────────────────
        with gr.Row(equal_height=False):

            # 하단 좌: 기대값
            with gr.Column(scale=2):
                gr.Markdown("### 📋 기대값 (Ground Truth)", elem_classes="section-title")

                output_type_radio = gr.Radio(
                    choices=OLD_OUTPUT_TYPES,
                    value=OLD_OUTPUT_TYPES[0],
                    label="출력 유형",
                )
                expected_box = gr.Textbox(
                    label="기대값 텍스트",
                    lines=14,
                    max_lines=20,
                    interactive=False,
                    elem_id="expected-box",
                )

            # 하단 우: 모델 + 채팅
            with gr.Column(scale=3, elem_id="chat-col"):
                gr.Markdown("### 💬 모델 추론", elem_classes="section-title")

                with gr.Accordion("⚙️ 모델 설정", open=True):
                    with gr.Row():
                        checkpoint_dd = gr.Dropdown(
                            choices=get_checkpoint_choices(),
                            value=get_checkpoint_choices()[0],
                            label="체크포인트 디렉토리 (projector.bin / LoRA 자동 감지)",
                            scale=4,
                        )
                        refresh_btn     = gr.Button("🔄", scale=0, min_width=44, size="sm")
                        ckpt_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as ckpt_explorer_row:
                        with gr.Column():
                            ckpt_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                ignore_glob="**/.*",
                                file_count="single",
                                label="체크포인트 디렉토리 선택",
                                height=240,
                            )
                            ckpt_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        vision_input = gr.Textbox(
                            value=DEFAULT_VISION_MODEL,
                            label="비전 모델 경로 (기본값: 허깅페이스에서 다운로드)",
                            scale=4,
                        )
                        vision_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as vision_explorer_row:
                        with gr.Column():
                            vision_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                ignore_glob="**/.*",
                                file_count="single",
                                label="비전 모델 디렉토리 선택",
                                height=240,
                            )
                            vision_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        llm_input = gr.Textbox(
                            value=DEFAULT_LLM_MODEL,
                            label="언어 모델 경로 (기본값: 허깅페이스에서 다운로드)",
                            scale=4,
                        )
                        llm_browse_btn = gr.Button("📂", scale=0, min_width=44, size="sm")
                    with gr.Row(visible=False) as llm_explorer_row:
                        with gr.Column():
                            llm_file_explorer = gr.FileExplorer(
                                root_dir="/home",
                                glob="**",
                                ignore_glob="**/.*",
                                file_count="single",
                                label="언어 모델 디렉토리 선택",
                                height=240,
                            )
                            llm_explorer_close = gr.Button("✕ 닫기", size="sm", variant="secondary")

                    with gr.Row():
                        load_btn = gr.Button("모델 로드", variant="primary", scale=2)
                        with gr.Column(scale=3):
                            model_status = gr.Markdown("⚪ 모델 미로드")

                chat_type = gr.Radio(
                    choices=OLD_OUTPUT_TYPES,
                    value=OLD_OUTPUT_TYPES[0],
                    label="채팅 출력 유형 (기대값과 연동됨)",
                )

        gr.Markdown("---")

        # ── 채팅 패널 (전체 너비) ─────────────────────────────────────────────
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 💬 대화", elem_classes="section-title")
                chatbot = gr.Chatbot(
                    label="대화",
                    height=500,
                    avatar_images=(None, "🤖"),
                )
                prompt_input = gr.Textbox(
                    value=PROMPT_MAP[OLD_OUTPUT_TYPES[0]],
                    label="프롬프트 (편집 가능 — 비우면 출력 유형 기본값 사용)",
                    lines=3,
                )
                with gr.Row():
                    infer_btn = gr.Button("🚀 추론 실행", variant="primary", scale=3)
                    clear_btn = gr.Button("🗑️ 초기화", variant="secondary", scale=1)

        # ── Event bindings ─────────────────────────────────────────────────────

        # Radio validation 우회용 State (choices 변경과 무관하게 항상 유효한 ot 문자열 보관)
        current_ot_state = gr.State(OLD_OUTPUT_TYPES[0])

        _SAMPLE_OUTPUTS = [img_display, csv_display, frame_dd,
                           output_type_radio, chat_type, expected_box, current_ot_state,
                           idx_number, img_notice]

        # 스캔 → 첫 샘플 자동 로드를 하나의 핸들러로 처리한다.
        # scan 과 load 를 .then 으로 잇고 sample_list 를 입력으로 읽으면,
        # choices 가 교체된 직후 이전 데이터셋의 값이 남아 Dropdown 검증 오류
        # ("... is not in the list of choices") 가 발생할 수 있다.
        # 첫 샘플 이름을 scan 결과에서 직접 꺼내 쓰면 이 경합이 사라진다.
        def _scan_and_load(path):
            dd, status, nav_col, _idx, total = scan_dataset(path)
            first = dd.get("value") if isinstance(dd, dict) else None
            return (dd, status, nav_col, total,
                    *on_sample_change(path, first or "", None))

        _SCAN_AND_LOAD_OUTPUTS = (
            [sample_list, scan_status, index_nav_col, idx_total_md] + _SAMPLE_OUTPUTS
        )

        scan_btn.click(
            fn=_scan_and_load,
            inputs=[path_input],
            outputs=_SCAN_AND_LOAD_OUTPUTS,
        )
        path_input.submit(
            fn=_scan_and_load,
            inputs=[path_input],
            outputs=_SCAN_AND_LOAD_OUTPUTS,
        )

        # 샘플 선택 → 포맷 감지 → 이미지/CSV/프레임DD/출력유형/기대값 일괄 갱신
        # current_ot_state 사용 — Radio를 직접 읽으면 choices 불일치 시 validation 에러 발생
        sample_list.change(
            fn=on_sample_change,
            inputs=[path_input, sample_list, current_ot_state],
            outputs=_SAMPLE_OUTPUTS,
        )

        # 인덱스 네비게이션 (평면 포맷) → 샘플 드롭다운 값 변경 → sample_list.change 로 연쇄
        # idx_number 는 .input() 만 사용한다. .change() 를 쓰면 on_sample_change 가
        # idx_number 를 갱신할 때 되먹임 루프가 발생한다.
        idx_number.input(
            fn=flat_goto,
            inputs=[path_input, idx_number],
            outputs=[idx_number, sample_list],
        )
        prev_btn.click(
            fn=lambda p, i: flat_step(p, i, -1),
            inputs=[path_input, idx_number],
            outputs=[idx_number, sample_list],
        )
        next_btn.click(
            fn=lambda p, i: flat_step(p, i, +1),
            inputs=[path_input, idx_number],
            outputs=[idx_number, sample_list],
        )
        rand_btn.click(
            fn=flat_random,
            inputs=[path_input],
            outputs=[idx_number, sample_list],
        )

        # 프레임 변경 (신 포맷) → 이미지 / CSV / 기대값 갱신
        frame_dd.change(
            fn=on_frame_change,
            inputs=[path_input, sample_list, frame_dd, current_ot_state],
            outputs=[img_display, csv_display, expected_box],
        )

        # 출력유형 변경 → 기대값 + 프롬프트 기본값 + chat_type 연동 + State 동기화
        def _on_ot_radio_change(path, sample, ot, frame):
            chat, prompt, expected = on_output_type_change(path, sample, ot, frame)
            return chat, prompt, expected, ot

        def _on_chat_type_change(path, sample, ct, frame):
            ot_radio, prompt, expected = on_output_type_change(path, sample, ct, frame)
            return ot_radio, prompt, expected, ct

        output_type_radio.change(
            fn=_on_ot_radio_change,
            inputs=[path_input, sample_list, output_type_radio, frame_dd],
            outputs=[chat_type, prompt_input, expected_box, current_ot_state],
        )
        chat_type.change(
            fn=_on_chat_type_change,
            inputs=[path_input, sample_list, chat_type, frame_dd],
            outputs=[output_type_radio, prompt_input, expected_box, current_ot_state],
        )

        # ── 파일 탐색기 이벤트 ────────────────────────────────────────────────

        path_browse_btn.click(fn=lambda: gr.update(visible=True), outputs=[path_explorer_row])
        path_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[path_file_explorer],
            outputs=[path_input, path_explorer_row],
        )
        path_explorer_close.click(fn=lambda: gr.update(visible=False), outputs=[path_explorer_row])

        def _select_ckpt_from_path(p):
            if not p:
                return gr.update(), gr.update(visible=False)
            has_proj = os.path.exists(os.path.join(p, "projector.bin"))
            has_lora = os.path.exists(os.path.join(p, "adapter_config.json"))
            try:
                rel = os.path.relpath(p, VLM_DIR)
            except ValueError:
                rel = p
            label   = (f"{rel}  [LoRA]" if has_lora else rel) if has_proj else p
            choices = get_checkpoint_choices()
            if label not in choices:
                choices = sorted(choices + [label])
            return gr.update(choices=choices, value=label), gr.update(visible=False)

        ckpt_browse_btn.click(fn=lambda: gr.update(visible=True), outputs=[ckpt_explorer_row])
        ckpt_file_explorer.change(
            fn=_select_ckpt_from_path,
            inputs=[ckpt_file_explorer],
            outputs=[checkpoint_dd, ckpt_explorer_row],
        )
        ckpt_explorer_close.click(fn=lambda: gr.update(visible=False), outputs=[ckpt_explorer_row])

        vision_browse_btn.click(fn=lambda: gr.update(visible=True), outputs=[vision_explorer_row])
        vision_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[vision_file_explorer],
            outputs=[vision_input, vision_explorer_row],
        )
        vision_explorer_close.click(fn=lambda: gr.update(visible=False), outputs=[vision_explorer_row])

        llm_browse_btn.click(fn=lambda: gr.update(visible=True), outputs=[llm_explorer_row])
        llm_file_explorer.change(
            fn=lambda p: (p, gr.update(visible=False)) if p else (gr.update(), gr.update()),
            inputs=[llm_file_explorer],
            outputs=[llm_input, llm_explorer_row],
        )
        llm_explorer_close.click(fn=lambda: gr.update(visible=False), outputs=[llm_explorer_row])

        refresh_btn.click(
            fn=lambda: gr.update(choices=get_checkpoint_choices()),
            outputs=[checkpoint_dd],
        )

        # 모델 로드
        load_btn.click(
            fn=lambda: (gr.update(interactive=False, value="로딩 중..."), "🔄 모델 로드 중..."),
            outputs=[load_btn, model_status],
            queue=False,
        ).then(
            fn=load_model,
            inputs=[checkpoint_dd, vision_input, llm_input],
            outputs=[model_status],
        ).then(
            fn=lambda: gr.update(interactive=True, value="모델 로드"),
            outputs=[load_btn],
        )

        # 추론 실행 (frame_dd 포함): 버튼 비활성화 → 추론 → 버튼 복원
        infer_btn.click(
            fn=lambda: gr.update(interactive=False, value="⏳ 추론 중..."),
            outputs=[infer_btn],
            queue=False,
        ).then(
            fn=run_inference,
            inputs=[path_input, sample_list, chat_type, prompt_input, chatbot, frame_dd],
            outputs=[chatbot],
        ).then(
            fn=lambda: gr.update(interactive=True, value="🚀 추론 실행"),
            outputs=[infer_btn],
        )

        # 채팅 초기화
        clear_btn.click(fn=lambda: [], outputs=[chatbot])

        # ── 앱 시작 시 자동 스캔 + 첫 샘플 로드 ────────────────────────────────
        # 로드 핸들러는 visible 을 전송하지 않는다 (_initial_visibility 주석 참고).

        # 스캔과 첫 샘플 로드를 demo.load 하나로 처리한다. 핸들러를 둘로 나누면
        # 같은 컴포넌트(특히 이미지)에 동시에 기록되어 갱신이 유실된다.
        def _initial_load(dp):
            dd, status, _col, _idx, total = scan_dataset(dp)
            first = dd.get("value") if isinstance(dd, dict) else None
            out = on_sample_change(dp, first or "", None)
            return (dd, status, total, *out[:2], _strip_visible(out[2]), *out[3:])

        demo.load(
            fn=_initial_load,
            inputs=[path_input],
            outputs=[sample_list, scan_status, idx_total_md] + _SAMPLE_OUTPUTS,
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser("VLM SDS Demo")
    p.add_argument("--host",  default="0.0.0.0")
    p.add_argument("--port",  type=int, default=7860)
    p.add_argument("--share", action="store_true", help="Gradio public URL")
    args = p.parse_args()

    demo = build_ui()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            font=[gr.themes.GoogleFont("Noto Sans KR"), "sans-serif"],
            font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
        ),
        css=CUSTOM_CSS,
    )
