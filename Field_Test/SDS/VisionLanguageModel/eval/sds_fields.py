#!/usr/bin/env python3
"""
eval/sds_fields.py — SDS 응답에서 구조적 항목을 뽑는다.

20260728 한글 시나리오의 응답은 닫힌 집합의 명제로 이루어진다. 조우 유형, 자선의
항법상 지위, 인용 COLREG 조항, 권고 조종, 그리고 CPA·TCPA·침로·속력 같은 수치다.
이것들을 뽑아내면 표면 겹침이 아니라 내용으로 채점할 수 있고, 수치는 참조 문장이
아니라 CSV 원본과 직접 대조할 수 있다.

여기서 하는 일은 추출뿐이다. 채점은 eval/metrics.py 가 한다.
"""
import re
from typing import Optional

# ── 조우 유형 ─────────────────────────────────────────────────────────────────
# 파일명이 정답을 담고 있다. crossing / headon / overtaking 과 각각의 _collision.
FILENAME_ENCOUNTER = {
    "crossing": "횡단",
    "crossing_collision": "횡단",
    "headon": "마주침",
    "headon_collision": "마주침",
    "overtaking": "추월",
    "overtaking_collision": "추월",
}

# 본문에 나타나는 표기. '정면'은 마주침의 다른 표현으로 함께 받는다.
ENCOUNTER_PATTERNS = [
    ("횡단",   re.compile(r"횡단")),
    ("추월",   re.compile(r"추월")),
    ("마주침", re.compile(r"마주침|정면\s*(상황|형세|조우)|대면")),
]

ROLE_PATTERNS = [
    ("피항선", re.compile(r"피항\s*(?:의무)?선|피항\s*의무")),
    ("유지선", re.compile(r"유지선|침로\s*[·,]?\s*속력을?\s*유지")),
]

# COLREG 조항. '제15·16조', '제17조(c)', '제19조 (d)(i)' 같은 표기를 모두 받는다.
ARTICLE_RUN = re.compile(r"제\s*((?:\d+\s*[·,和and&]*\s*)+)조")
ARTICLE_NUM = re.compile(r"\d+")

# 권고 조종
TURN = re.compile(r"(우현|좌현)\s*(\d+)\s*도\s*변침")
PORT_TURN_FORBIDDEN = re.compile(r"좌현\s*변침(?:은|를|을)?\s*(?:금|피|하지)")
PORT_TURN_ADVISED = re.compile(r"좌현\s*\d+\s*도\s*변침")
KEEP_COURSE = re.compile(r"침로\s*[·,]?\s*속력을?\s*유지|속력\s*유지|침로\s*유지")

# 수치
CPA_VAL = re.compile(r"CPA\s*(?:는|은)?\s*(?:약\s*)?([0-9]+\.?[0-9]*)\s*NM")
TCPA_VAL = re.compile(r"TCPA\s*(?:는|은)?\s*(?:약\s*)?([0-9]+\.?[0-9]*)\s*(?:s|초)")
# 자선의 침로와 속력은 표기가 갈린다. 실측한 변형은 다음 두 가지다.
#   자선(침로 146.0°, 23.2kt)
#   자선은 침로 75°·속력 12.3kt
# 사이 구분자를 쉼표와 가운뎃점 모두 받고 '속력' 표기도 선택적으로 받는다.
_CD = r"([0-9]+\.?[0-9]*)"
OWN_COURSE = re.compile(
    rf"자선[은는]?\s*\(?\s*침로\s*{_CD}\s*(?:°|도)?\s*[,·]?\s*(?:속력\s*)?{_CD}\s*kt"
)
TGT_COURSE = re.compile(
    rf"침로\s*{_CD}\s*(?:°|도)?\s*[,·]\s*(?:속력\s*)?{_CD}\s*kt"
)
DISTANCE_NM = re.compile(r"약\s*([0-9]+\.?[0-9]*)\s*NM")
# 육안으로 식별한 타선 수. CSV 의 행 수와 다르다. CSV 에는 시야 밖 선박도 들어
# 있으므로 이 값의 정답은 CSV 가 아니라 참조 문장이다.
VESSEL_COUNT = re.compile(r"타선\s*([0-9]+)\s*척")
VESSEL_SIZE = re.compile(r"([0-9]+)\s*m\s*급")


# 목록 기호나 마크다운 강조. 참조 응답에는 나타나지 않는다.
MARKUP = re.compile(r"^\s*(?:[-*·]|\d+[.)])\s|\*\*|^#{1,6}\s", re.MULTILINE)


def split_sections(text: str):
    """묘사와 조력으로 나눈다. 빈 줄이 없으면 전체를 묘사로 본다."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(parts) >= 2:
        return parts[0], "\n\n".join(parts[1:])
    return (parts[0] if parts else ""), ""


def follows_sds_format(text: str) -> bool:
    """
    참조 응답의 형식을 따르는지 본다.

    빈 줄로 나뉘는지만 보면 부족하다. 실측에서 LLaMarine 기준선은 AIS 를 번호
    목록으로 재서술하는 전혀 다른 형식을 내면서도 단락이 여러 개라 그 검사를
    통과했다. 그래서 단락이 정확히 둘이고, 목록이나 마크다운 기호가 없고,
    길이가 참조 분포(230~508자) 언저리인지까지 함께 본다.
    """
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(parts) != 2:
        return False
    if MARKUP.search(text):
        return False
    return 150 <= len(text) <= 700


def encounter_from_filename(image_or_id: str) -> Optional[str]:
    m = re.search(r"tango_sds-unity_([a-z_]+?)-\d{8}", image_or_id)
    if not m:
        return None
    return FILENAME_ENCOUNTER.get(m.group(1))


def _first_match(text: str, patterns):
    """본문에서 가장 먼저 나타나는 표기를 고른다. 여러 개면 등장 위치 순."""
    best, best_pos = None, len(text) + 1
    for label, pat in patterns:
        m = pat.search(text)
        if m and m.start() < best_pos:
            best, best_pos = label, m.start()
    return best


def extract_articles(text: str) -> set:
    """인용된 COLREG 조항 번호 집합."""
    out = set()
    for m in ARTICLE_RUN.finditer(text):
        out.update(int(n) for n in ARTICLE_NUM.findall(m.group(1)))
    return out


def _f(m, group=1):
    return float(m.group(group)) if m else None


def extract(text: str, image_or_id: str = "") -> dict:
    """응답 하나에서 구조적 항목을 모두 뽑는다."""
    desc, adv = split_sections(text)
    whole = text

    turn = TURN.search(adv or whole)
    own = OWN_COURSE.search(whole)

    # 타선 침로·속력은 자선 것과 같은 패턴에 걸리므로 자선 매치를 제외하고 찾는다.
    tgt = None
    for m in TGT_COURSE.finditer(whole):
        if own and m.start() == own.start():
            continue
        tgt = m
        break

    return {
        "has_two_sections": bool(desc and adv),
        "follows_format": follows_sds_format(text),
        "encounter": _first_match(whole, ENCOUNTER_PATTERNS),
        "role": _first_match(whole, ROLE_PATTERNS),
        "articles": extract_articles(whole),
        "turn_dir": turn.group(1) if turn else None,
        "turn_deg": float(turn.group(2)) if turn else None,
        "keeps_course": bool(KEEP_COURSE.search(adv or whole)),
        "says_port_forbidden": bool(PORT_TURN_FORBIDDEN.search(whole)),
        "advises_port_turn": bool(PORT_TURN_ADVISED.search(adv or whole)),
        "cpa": _f(CPA_VAL.search(whole)),
        "tcpa": _f(TCPA_VAL.search(whole)),
        "own_course": _f(own, 1),
        "own_speed": _f(own, 2),
        "tgt_course": _f(tgt, 1),
        "tgt_speed": _f(tgt, 2),
        "distance_nm": _f(DISTANCE_NM.search(whole)),
        "vessel_count": int(VESSEL_COUNT.search(whole).group(1))
                        if VESSEL_COUNT.search(whole) else None,
        "vessel_sizes": sorted({int(x) for x in VESSEL_SIZE.findall(whole)}),
        "n_chars": len(text),
        "desc_chars": len(desc),
        "adv_chars": len(adv),
    }


def csv_truth(df) -> dict:
    """CSV 한 건에서 정답 수치를 만든다. 기준선은 최소 CPA 인 타선이다."""
    own = df[df.my_ship == 1]
    others = df[df.my_ship == 0]
    if own.empty or others.empty:
        return {}
    o = own.iloc[0]
    t = others.loc[others.cpa.idxmin()]
    # 타선 척수는 넣지 않는다. CSV 행 수는 시야 밖 선박까지 세지만 본문의
    # '육안 타선 N척' 은 식별된 수라 서로 다른 값을 재게 된다.
    return {
        "cpa": float(t.cpa),
        "tcpa": float(t.tcpa),
        "own_course": float(o.heading),
        "own_speed": float(o.knot),
        "tgt_course": float(t.heading),
        "tgt_speed": float(t.knot),
        "vessel_sizes": sorted({int(x) for x in others.length}),
    }
