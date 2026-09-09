#!/usr/bin/env python3
"""데이터 파이프라인 — COLREG 계산 노드(kind=calc, stage=sds_colreg).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_colreg.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

조인된 씬의 AIS 기하로 조우 유형·피항선·적용 조항·근접위험도를 **결정론적으로** 계산한다.
생성 모델에 넣을 앵커라서 모델을 쓰지 않는다 — 여기서 모델이 판단하면 뒤의 심사가
모델의 답을 모델의 답으로 검증하는 꼴이 되어 환각을 걸러 낼 수 없다.

이 노드는 상류(조인) 산출물을 읽는다. BE 가 params.inputs 에 넣어 준다.

    inputs = {"scenes": "/dataset/_runs/<run>/<idx>"}   # dp_sds_join 산출

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·임계각 (비교의 기준)
  assets.jsonl   씬 1건 = 1줄 (조인 결과 + colreg 사실)
  drops.jsonl    계산할 수 없던 씬: 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        씬 이미지(다음 노드의 입력)
  samples/       화면에 보여줄 썸네일 일부

COLREG 원문 대조로 다음을 판정에 반영했다(RULE_VERSION=5).
  Rule 7   충돌위험이 없으면 조우 조항을 붙이지 않는다(제14·15조의 전제).
  Rule 13(a) 추월은 이 절의 다른 규정보다 우선하므로 가장 먼저 본다.
  Rule 14(c) 의심스러우면 정면 조우로 가정한다 — 임계각을 좁게 잘라 crossing 으로
           흘리던 것을 되돌렸다.
  Rule 17  유지선의 단계((a)(i)/(a)(ii)/(b))와 좌현 변침 금지((c))를 권고에 담는다.
  Rule 18  선종 서열((a)(b)(c))로 역할을 정한다. 자선이 특수선이면 유지선이 되기도 하고,
           서열을 확정할 수 없으면 **조항을 붙이지 않고 보류**한다(기하 복귀 금지 —
           제15·17조는 두 동력선을 전제한다).

남은 한계(의도적으로 다루지 않음)
  · Rule 13(d) — 한번 추월이면 방위가 변해도 추월로 유지해야 하는데, 이 노드는 씬 단위
    무상태 계산이라 같은 조우 시퀀스에서 라벨이 흔들릴 수 있다.
  · Rule 7(d)(i) — 방위 변화로 위험을 보는 판정은 시간축이 필요해 쓸 수 없다. CPA 가
    대용이며 그만큼 위험 창을 넓게 잡았다.
  · Rule 9/10 — 협수로·통항분리는 해도 정보가 없어 판정하지 않는다. 제18조의 예외라
    그 환경에서는 이 판정을 그대로 쓰면 안 된다.
  · 선종을 알아볼 수 없으면 제18조 판정을 보류하고 그 건수를 산출물에 남긴다
    (동력선으로 가정하면 자선을 유지선으로 잘못 라벨링하게 된다).
  · Rule 11/19 — 이 절은 서로 시계 내에 있는 선박에만 적용된다. 시정 제한이면 제19조라
    유지선 개념 자체가 없는데, 시정 판단 근거가 이미지뿐이라 여기서 가르지 않는다.
  · Rule 3(d) — "어로 종사 중"은 어구 사용 여부로 정해지지만 AIS 항행상태가 없어 선종으로
    대신한다. 과보수적이며(우리가 양보하는 쪽) 항행상태가 들어오면 좁혀야 한다.
  · 다중 조우 — 위험도 기준으로 고른 1척만 사실에 싣는다. 동시 판정은 규칙이 달라
    (제17조 협력동작 등) 별도 설계가 필요하다.
  · Rule 18(d)(e)(f) — 흘수제약선·수상항공기·위그선은 (a)~(c)와 다른 별도 의무라
    판정하지 않는다(범주는 인식하고 서열만 보류한다).
  · encounter 는 **기하 라벨**이다. 제18조가 걸려 제14조가 적용되지 않는 정면 기하도
    encounter="head_on" 을 유지한다 — 이 문자열은 하류 3곳이 공유하는 계약이라 값을
    늘리면 한쪽만 갱신됐을 때 조용히 0 점이 된다. 적용 조항은 articles 가 말한다.
"""
import argparse
import json
import math
import os
import shutil
import time

from dp_sds_ais import vessel_category

# ── 기능 이름 (BE constants.SDS_COLREG_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_GEOMETRY = "상대방위 · 침로차"
STEP_ENCOUNTER = "조우 분류"
STEP_RISK = "근접 위험도"

TS_FMT = "%Y-%m-%d %H:%M:%S"
SAMPLE_LIMIT = 24
THUMB_EDGE = 320

# 판정 방식의 판. 방식이 다르면 두 실행의 조우 분포를 나란히 놓고 비교할 수 없으므로
# 산출물에 남긴다.
#   v1 프로토타입 — 위험판정 없음 · 의심을 crossing 으로 해소 · 선종 무시 · 입력순서 첫 배
#   v2 Rule 7 게이트 + Rule 14(c) 방향 교정 + Rule 18 단방향 + 최근접 대상
#   v3 위험도 기반 대상 선택 · Rule 13 양방향+상대운동 · Rule 18 서열 · 제17조(c) 좌현
#      전제 한정 · 선종 부분일치와 미인식 보류
#   v4 대상 선택에 위험·접근을 1차 키로(무위험 추월이 실제 위험을 가리던 것) · 대상 전멸을
#      안전이 아니라 drop 으로 · NUC↔RAM 동률 보류 · 18(d)(e)(f) 범주 보류 · 선종 토큰
#      경계 매칭(프롬프트에는 정규 라벨만) · 접근·각도 경계 허용오차
#   v5 제18조 보류를 **진짜 보류**로(조항 미부여 — None 은 기하 역할로 복귀해 보류가 아니었다)
#      · 극근접 대상을 접근 여부보다 앞세움 · 선종 매칭을 부분일치로 되돌리고 라틴 축약만
#      경계 예외(한국어 합성어 복구)
RULE_VERSION = 5

# COLREG 판정 임계.
# HEAD_ON_ARC 는 프로토타입에서 13° 였다. Rule 14(b) 에는 각도 수치가 아예 없고
# 14(c) 가 "의심스러우면 정면 조우로 가정하고 그에 따라 행동하라"고 하므로, 좁게 잘라
# crossing 으로 흘려보내던 것은 규칙과 반대 방향이었다. COLREG 자신이 쓰는 각도 단위
# (Rule 13(b) 정횡후 22.5°, 현등 사출범위)를 기준으로 넓힌다. 노드 설정 슬라이더가 정수
# 도만 다루므로 22.5 를 올림한 23 을 쓴다 — 올림이 "의심은 정면 쪽으로"(14(c)) 방향이다.
# 설정에서 조정할 수 있고 실제 쓴 값이 config.json 에 남으므로 두 실행을 비교할 수 있다.
HEAD_ON_ARC = 23.0        # deg. 상대방위·상호 반대침로 판정에 함께 쓰는 여유각
STARBOARD_ARC = 112.5     # deg. 우현측 조우 구역
STERN_ARC = 112.5         # deg. 타선 선미측에서 접근 = 추월
NM_PER_DEG_LAT = 60.0

# Rule 7 — 제14·15조는 "so as to involve risk of collision" 을 전제로 한다. 위험이
# 없으면 조우 자체가 성립하지 않으므로 조항을 붙이면 안 된다. 7(a) 가 "의심스러우면
# 위험이 있다고 본다"이므로 문턱은 넉넉하게 잡는다 — 지금 이 거리 안이면 접근·이탈을
# 따지지 않고 근접상황으로 보고 위험으로 판정한다.
RISK_RANGE_NM = 2.0       # NM. 현재 거리가 이 안이면 무조건 위험
RISK_CPA_NM = 2.0         # NM. 접근 중이고 최근접이 이 안이면 위험
# 60분: 7(d)(i) 의 방위변화 판정을 쓸 수 없어 CPA 를 대용으로 쓰는데(collision_risk 참조),
# 창을 좁히면 "CPA 0 인데 33분 뒤라서 안전" 같은 거짓 안전이 나온다. 넓게 잡아 실제
# 위험을 놓치지 않는 쪽으로 틀린다.
RISK_TCPA_MIN = 60.0      # min. 그 최근접까지 이 시간 안에 도달하면 위험
# 이 거리 안이면 이탈 중이라도 대상 선택에서 무조건 앞세운다(_danger_key 참조).
VERY_CLOSE_NM = RISK_RANGE_NM / 4

def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_upstream(inputs):
    """조인 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("scenes")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — 조인 단계를 먼저 실행하세요 (inputs.scenes)")
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"조인 노드 산출물이 없습니다: {path}")
    return read_jsonl(path), src


# ── 기하 ────────────────────────────────────────────────────────────────────
def _norm180(a):
    return (a + 180.0) % 360.0 - 180.0


def bearing_deg(lat1, lon1, lat2, lon2):
    """정북 기준 진방위(0~360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def rel_bearing(own, other):
    """자선 선수 기준 상대방위(-180~180). 양수면 우현."""
    return _norm180(bearing_deg(own["lat"], own["lon"], other["lat"], other["lon"])
                    - own["heading"])


def _rel_xy(own, other):
    """자선 기준 상대위치(동쪽 NM, 북쪽 NM). 위경도를 NM 평면으로 편다."""
    coslat = math.cos(math.radians(own["lat"])) or 1e-9
    return ((other["lon"] - own["lon"]) * NM_PER_DEG_LAT * coslat,
            (other["lat"] - own["lat"]) * NM_PER_DEG_LAT)


def _vel(ship):
    """대지속도 벡터(동쪽 kt, 북쪽 kt)."""
    th = math.radians(ship["heading"])
    return ship["knot"] * math.sin(th), ship["knot"] * math.cos(th)


def range_nm(own, other):
    """현재 두 선박 사이 거리(NM).

    반올림하지 않는다 — 이 값이 대상선 선택 키로 쓰이는데 0.001 단위로 뭉치면 동률이
    생겨 같은 입력에서도 대상이 흔들린다. 표시할 때만 반올림한다.
    """
    rx, ry = _rel_xy(own, other)
    return math.hypot(rx, ry)


# 부동소수 잔차를 "접근 중" 으로 오판하지 않게 하는 허용오차. 정확히 직교인 상대운동은
# 내적이 0 이어야 하는데 위경도 변환 잔차로 1e-16 규모의 음수가 나와 추월로 잡혔다.
CLOSING_EPS = 1e-9
# 각도 경계도 같은 이유. Rule 13(b) 는 "22.5°보다 뒤" 라는 엄격 경계인데 정확히 112.5°
# 로 놓은 입력이 112.50000000000034 로 계산돼 통과했다.
ANGLE_EPS = 1e-6


def is_closing(own, other):
    """거리가 줄고 있는가. 상대위치와 상대속도의 내적 부호로 본다.

    Rule 13(b) 의 "coming up with another vessel" 은 상대운동의 문제다. 스칼라 속도
    비교(자선이 더 빠른가)로는 반대 방향으로 이탈하는 배까지 추월로 잡힌다.
    """
    rx, ry = _rel_xy(own, other)
    ovx, ovy = _vel(own)
    tvx, tvy = _vel(other)
    return (rx * (tvx - ovx) + ry * (tvy - ovy)) < -CLOSING_EPS


def cpa_tcpa(own, other):
    """평면 근사 최근접점(NM)과 도달시간(분). 반올림하지 않는다(range_nm 과 같은 이유).

    위경도를 NM 로 펴서 상대속도 벡터로 푼다. 항해 수분 규모의 조우에서는 지구 곡률
    오차가 판정에 영향을 주지 않는다.
    """
    rx, ry = _rel_xy(own, other)
    ovx, ovy = _vel(own)
    tvx, tvy = _vel(other)
    vx, vy = tvx - ovx, tvy - ovy
    v2 = vx * vx + vy * vy
    if v2 < 1e-9:
        # 상대속도가 0 = 거리가 변하지 않는다. 지금 거리가 곧 최근접이다.
        return math.hypot(rx, ry), 0.0
    tcpa_h = max(0.0, -(rx * vx + ry * vy) / v2)
    cx, cy = rx + vx * tcpa_h, ry + vy * tcpa_h
    return math.hypot(cx, cy), tcpa_h * 60.0


def collision_risk(own, other, cpa, tcpa):
    """Rule 7 — 충돌위험이 있는가. (위험여부, 사유).

    제14·15조가 "so as to involve risk of collision" 을 전제로 하므로, 위험이 없으면
    조우가 성립하지 않고 조항을 붙이면 안 된다. 다만 7(a) 가 "의심스러우면 위험이 있다고
    본다"이므로 문턱은 넉넉하게 잡는다 — 지금 가까우면 접근·이탈을 따지지 않고 위험으로
    보고, 접근 중이면 한참 뒤의 최근접까지 위험으로 본다.

    7(d)(i) 의 "방위가 거의 변하지 않으면 위험" 판정은 시간에 걸친 방위 변화를 봐야 하는데
    이 노드는 씬 단위 무상태 계산이라 쓸 수 없다. CPA 가 그 대용이고, 대용인 만큼 창을
    좁게 잡으면 거짓 '안전' 이 나오므로 넓게 잡는다.
    """
    if range_nm(own, other) <= RISK_RANGE_NM:
        return True, "close_quarters"
    if 0.0 < tcpa <= RISK_TCPA_MIN and cpa <= RISK_CPA_NM:
        return True, "closing"
    return False, "no_risk"


# ── 규칙 매핑 ───────────────────────────────────────────────────────────────
# 상황 → 자선 역할·적용조항·권고조치. 기하 계산(위)과 규칙 매핑(아래)을 갈라 둔 이유는
# 해기 지식을 가진 사람이 삼각함수를 읽지 않고 규칙만 따로 검토할 수 있게 하기 위해서다.
# ⚠️ encounter 문자열은 하류 계약이다 — dp_generate.ENCOUNTER_KO/EN 와
# dp_judge.ENCOUNTER_KW 가 같은 값을 키로 쓴다. 새 값을 넣으면 세 곳을 함께 고쳐야 한다.
SITUATIONS = {
    "no_target": {"encounter": "safe", "own_role": "n/a", "articles": [],
                  "maneuver": "위험 대상 없음"},
    "no_risk": {"encounter": "safe", "own_role": "n/a", "articles": [],
                "maneuver": "충돌위험 없음 — 경계를 유지하며 침로·속력 유지"},
    "head_on": {"encounter": "head_on", "own_role": "both_give_way", "articles": [14, 6],
                "maneuver": "우현으로 대각도 변침하여 좌현 대 좌현(Port-to-port) 통과"},
    "overtaking": {"encounter": "overtaking", "own_role": "give_way", "articles": [13],
                   "maneuver": "피추월선을 완전히 벗어날 때까지 타선 진로를 피함"},
    # 타선이 자선을 추월하는 반대 방향. Rule 13(d) 상 추월선이 완전히 벗어날 때까지
    # 그 지위가 유지되므로 자선은 유지선이다.
    "overtaking_stand_on": {"encounter": "overtaking", "own_role": "stand_on",
                            "articles": [13, 17],
                            "maneuver": "추월당하는 중 — 침로·속력 유지(제17조(a)(i)). "
                                        "추월선이 완전히 벗어날 때까지 갑작스러운 변침 금지"},
    "crossing_give_way": {"encounter": "crossing", "own_role": "give_way",
                          "articles": [15, 16],
                          "maneuver": "타선 선미로 피하도록 우현 변침, 타선 전방 횡단 금지"},
    # 타선이 좌현측에 있는 경우에만 제17조(c)(좌현측 선박에 대한 좌현 변침 금지)가
    # 성립한다. 방위와 무관하게 이 문장을 붙이면 계산이 앵커에 거짓을 넣는 꼴이 된다.
    "crossing_stand_on": {"encounter": "crossing", "own_role": "stand_on", "articles": [17],
                          "maneuver": "침로·속력 유지(제17조(a)(i)). 타선이 조치하지 않으면 "
                                      "단독으로 피항 조치할 수 있고(제17조(a)(ii)), 충돌을 "
                                      "피할 수 없게 되면 반드시 조치한다(제17조(b)). 이때 "
                                      "좌현측 선박에 대해서는 좌현 변침을 피한다(제17조(c))"},
    # 우현 정횡후. 좌현 전제가 서지 않으므로 17(c) 를 뺀다.
    "crossing_stand_on_abaft": {"encounter": "crossing", "own_role": "stand_on",
                                "articles": [17],
                                "maneuver": "침로·속력 유지(제17조(a)(i)). 타선이 조치하지 "
                                            "않으면 단독으로 피항 조치할 수 있고"
                                            "(제17조(a)(ii)), 충돌을 피할 수 없게 되면 "
                                            "반드시 조치한다(제17조(b))"},
}

# 추월 상황 키. Rule 13(a) 는 "Notwithstanding anything contained in the Rules of this
# Section" 이고 제14·15조와 달리 충돌위험 문구가 없다 — 그래서 제7조 게이트로 지우지 않는다.
OVERTAKING_SITUATIONS = ("overtaking", "overtaking_stand_on")

# Rule 18 서열. 숫자가 작을수록 우선이고, 숫자가 큰 쪽이 진로를 양보한다.
#   18(a) 동력선은 조종불능·조종제한·어로종사선·범선에 양보
#   18(b) 범선은 조종불능·조종제한·어로종사선에 양보
#   18(c) 어로종사선은 가능한 한 조종불능·조종제한선에 양보
# ⚠️ 조종불능(NUC)과 조종제한(RAM) **사이의** 우열은 18조에 없다 — (a)~(c)가 그 둘을
# 언제나 묶음으로 나열한다. 그래서 같은 숫자를 주고 동률에서는 판정을 보류한다. 전순서로
# 만들면 결정론 앵커가 원문에 없는 역할을 "제18조" 근거로 단정한다.
#
# 여기 없는 범주(흘수제약선 18(d) · 수상항공기 18(e) · 위그선 18(f))는 (a)~(c)와 다른
# 별도 의무라 이 노드가 판정하지 않는다 — 서열표에 없으면 자동으로 보류된다.
# 선종 → 범주 매핑은 AIS 어휘라서 dp_sds_ais.vessel_category 가 갖는다.
VESSEL_RANK = {"not_under_command": 0, "restricted": 0, "fishing": 1, "sailing": 2,
               "power_driven": 3}

# 방향을 명시한다 — 다른 SITUATIONS 항목은 모두 변침 방향을 담고 있고, 심사의
# actionability 축과 생성 프롬프트가 변침각을 수치로 요구한다.
RULE18_GIVE_WAY = {"own_role": "give_way", "articles": [18, 16],
                   "maneuver": "제18조에 따라 자선이 진로를 양보한다 — 조기에 대각도로 "
                               "변침해 충분히 이격하며, 가능하면 우현 변침을 택한다"}
# 제18조 판정을 **보류**할 때. None 을 돌려 기하 역할로 복귀하면 보류가 아니다 —
# 제15·17조는 두 동력선을 전제하므로, 선종을 모르면 기하도 근거가 되지 못한다. 조항을
# 붙이지 않고 역할을 비워 하류가 "정해지지 않았다" 를 알 수 있게 한다.
RULE18_SUSPENDED = {"own_role": "n/a", "articles": [],
                    "maneuver": "선종을 확인할 수 없어 제18조상 피항 관계를 판정하지 "
                                "않았다 — 경계를 강화하고 조기에 충분히 이격한다"}
RULE18_STAND_ON = {"own_role": "stand_on", "articles": [18, 17],
                   "maneuver": "제18조상 타선이 진로를 양보해야 한다 — 침로·속력 유지"
                               "(제17조(a)(i)). 타선이 조치하지 않으면 단독으로 피항 "
                               "조치할 수 있고(제17조(a)(ii)), 충돌을 피할 수 없게 되면 "
                               "반드시 조치한다(제17조(b))"}


def rule18_roles(situation, own, other):
    """Rule 18 서열로 자선 역할이 정해지는가. (역할|"suspended"|None, 근거표기|None).

    18조 본문이 "Except where Rules 9, 10 and 13 otherwise require" 이므로 추월(13조)은
    뒤집지 않는다. 협수로(9조)·통항분리(10조)는 해도 정보가 없어 판정하지 않으며, 그
    환경에서는 이 판정을 그대로 쓰면 안 된다.

    "suspended" 는 **기하 역할로 돌아가지 않는다**는 뜻이다. 제15·17조는 두 동력선을
    전제하므로, 선종을 읽지 못했거나 18조가 우열을 정하지 않는 조합(조종불능↔조종제한)
    에서는 기하 판정도 근거가 없다.
    """
    if situation in OVERTAKING_SITUATIONS or situation in ("no_target", "no_risk"):
        return None, None
    own_raw, other_raw = own.get("type"), other.get("type")
    if not own_raw and not other_raw:
        # 선종 컬럼이 아예 없는 예전 씬. 제18조를 적용할 근거가 없어 기하만으로 판정한다
        # (v1·v2 와 같은 동작). 양쪽을 동력선으로 가정하는 셈이며 docstring 에 명시한다.
        return None, None
    own_cat = vessel_category(own_raw)
    other_cat = vessel_category(other_raw)
    if own_cat is None or other_cat is None:
        return "suspended", (other_raw or own_raw)
    if own_cat not in VESSEL_RANK or other_cat not in VESSEL_RANK:
        return "suspended", (other_raw or own_raw)          # 18(d)(e)(f)
    if own_cat == other_cat:
        return None, None                                   # 같은 범주 = 기하가 정한다
    own_rank, other_rank = VESSEL_RANK[own_cat], VESSEL_RANK[other_cat]
    if own_rank == other_rank:
        return "suspended", other_raw                       # 조종불능 ↔ 조종제한
    if own_rank > other_rank:
        return "give_way", other_raw
    return "stand_on", other_raw


def geometric_situation(own, other, head_on_arc=None):
    """기하만으로 정하는 상황 키. 규칙 매핑은 SITUATIONS 가 맡는다.

    head_on_arc 는 정면으로 인정할 여유각(도). 상대방위와 상호 반대침로 판정에 같은 값을
    쓴다 — 둘 다 "얼마나 비껴도 정면으로 볼 것인가" 하나의 개념이고, 노드 설정도 하나의
    슬라이더로 받는다.
    """
    arc = HEAD_ON_ARC if head_on_arc is None else float(head_on_arc)
    rb = rel_bearing(own, other)
    hd = _norm180(other["heading"] - own["heading"])
    # 타선에서 본 자선의 방위 — 자선이 타선 선미측에서 접근하는지(추월) 판정용
    rb_from_other = _norm180(
        bearing_deg(other["lat"], other["lon"], own["lat"], own["lon"]) - other["heading"])
    closing = is_closing(own, other)

    # Rule 13(a) — 추월은 이 절의 다른 어떤 규정보다 우선하므로 가장 먼저 본다.
    # 자선이 추월하는 쪽과 추월당하는 쪽을 모두 본다(13조는 양방향 모두를 규정한다).
    if closing and abs(rb_from_other) > STERN_ARC + ANGLE_EPS:
        return "overtaking", rb, hd
    if closing and abs(rb) > STERN_ARC + ANGLE_EPS:
        return "overtaking_stand_on", rb, hd
    if abs(rb) <= arc and abs(abs(hd) - 180.0) <= arc:
        return "head_on", rb, hd
    if 0.0 <= rb <= STARBOARD_ARC:
        return "crossing_give_way", rb, hd
    # 제17조(c) 의 "좌현측 선박" 은 좌현 **정횡 안쪽**이다. _norm180(180) 이 -180 을
    # 돌려주므로 부호만 보면 정선미 대상까지 좌현측이라 말하게 된다.
    if -STARBOARD_ARC <= rb < 0.0:
        return "crossing_stand_on", rb, hd
    return "crossing_stand_on_abaft", rb, hd


def _danger_key(ev):
    """가장 위험한 대상을 고르는 순서.

    ① **실제 충돌위험**이 먼저다 — 이걸 1차 키로 두지 않으면 위험하지 않은 추월이
       TCPA 가 짧다는 이유로 진짜 충돌위험선을 앞질러 최종 판정을 'no_risk' 로 만든다.
    ② **극근접**이 그다음이다 — 수백 미터 앞의 배는 이탈 중이라도 그 씬의 사실이다.
       이미지에 찍혀 있는 배를 사실에서 빼면 서술 정확도·이미지 근거 축이 옳은 답을 벌한다.
    ③ 극근접이 아니면 **접근 중**이 먼저다 — 애매하게 가까우면서 멀어지는 배가 충돌
       코스로 오는 배를 가리면, 거짓 '안전' 은 아니어도 거짓 '유지' 가 된다.
    ④ 그다음 근접 상황 여부, 그 안에서는 거리 / 아니면 최근접 도달 시간.
    ⑤ ship_id 는 동률에서 같은 입력이 같은 결과를 내게 하는 결정성 장치다.
    """
    immediate = 0 if ev["basis"] == "close_quarters" else 1
    proximity = ev["range_nm"] if immediate == 0 else ev["tcpa"]
    return (0 if ev["risk"] else 1,
            0 if ev["range_nm"] <= VERY_CLOSE_NM else 1,
            0 if ev["closing"] else 1,
            immediate, proximity, ev["cpa"], str(ev["ship"].get("ship_id")))


def _report_key(ev):
    """위험 대상이 하나도 없을 때 사실에 실을 대표. 접근 중 · 최근접점이 가까운 순.

    `_danger_key` 를 그대로 쓰면 이탈선의 TCPA 가 0 이라 정렬 1등이 되어 "위험 없음 ·
    CPA 9해리 · TCPA 0분" 처럼 스스로 모순인 그라운딩이 나오고, 그 씬에서 유일하게
    서술할 값이 있는 원거리 접근선이 사실에서 사라진다.
    """
    return (0 if ev["closing"] else 1, ev["cpa"], ev["range_nm"],
            str(ev["ship"].get("ship_id")))


def classify(own, others, head_on_arc=None):
    """조우 판정. **가장 위험한** 대상 1척을 기준으로 한다.

    대상을 하나만 보는 것은 프로토타입과 같지만, 그 하나를 고르는 방식이 다르다. 파일에
    먼저 적힌 배(프로토타입)도, 단순히 가장 가까운 배도 아니다 — 위험 여부와 접근 여부를
    앞세워 고른다(`_danger_key`). 대표 1척 방식 자체의 한계는 남아 있다: 여러 척이
    동시에 위험한 씬에서 나머지는 사실에 실리지 않는다. 다중 조우 동시 판정은 규칙이
    달라(제17조 협력동작 등) 별도 설계가 필요하다.
    """
    empty = {"rel_bearing_deg": 0.0, "heading_diff_deg": 0.0, "cpa_nm": 0.0,
             "tcpa_min": 0.0, "range_nm": 0.0, "target_ship_id": None,
             "target_ship_type": None, "target_type_category": None,
             "target_skipped": 0, "risk": False, "risk_basis": "no_target",
             "rule18_basis": None, "rule18_suspended": False}
    if not others:
        return {**empty, **SITUATIONS["no_target"]}

    evals = []
    skipped = 0
    for ship in others:
        try:
            cpa, tcpa = cpa_tcpa(own, ship)
            rng = range_nm(own, ship)
            risk, basis = collision_risk(own, ship, cpa, tcpa)
            situation, rb, hd = geometric_situation(own, ship, head_on_arc)
            closing = is_closing(own, ship)
        except (KeyError, TypeError, ValueError):
            # 한 척이 나빠도 나머지로 판정한다. 건수는 사실에 실어 보고한다.
            skipped += 1
            continue
        evals.append({"ship": ship, "cpa": cpa, "tcpa": tcpa, "range_nm": rng,
                      "risk": risk, "basis": basis, "situation": situation,
                      "closing": closing, "rb": rb, "hd": hd})
    if not evals:
        # 대상이 있었는데 전부 읽지 못한 것은 "위험 대상 없음" 과 **다른 사실**이다.
        # 사유를 올려 run() 이 drops.jsonl 에 남기게 한다 — 조용히 안전으로 흘리면 그
        # 씬이 그대로 학습 레코드가 되고, 화면에서는 실패가 보이지 않는다.
        raise ValueError(f"대상선 {len(others)}척을 모두 읽지 못했습니다(기하 계산 실패)")

    relevant = [e for e in evals
                if e["risk"] or e["situation"] in OVERTAKING_SITUATIONS]
    chosen = min(relevant, key=_danger_key) if relevant else min(evals, key=_report_key)
    target = chosen["ship"]
    base = {"rel_bearing_deg": round(chosen["rb"], 2),
            "heading_diff_deg": round(chosen["hd"], 2),
            "cpa_nm": round(chosen["cpa"], 3), "tcpa_min": round(chosen["tcpa"], 1),
            "range_nm": round(chosen["range_nm"], 3),
            "target_ship_id": target.get("ship_id"),
            "target_ship_type": target.get("type") or None,
            "target_type_category": vessel_category(target.get("type")),
            "target_skipped": skipped,
            "risk": chosen["risk"], "risk_basis": chosen["basis"],
            "rule18_basis": None, "rule18_suspended": False}
    if not relevant:
        return {**base, **SITUATIONS["no_risk"]}

    facts = {**base, **SITUATIONS[chosen["situation"]]}
    role, why = rule18_roles(chosen["situation"], own, target)
    if role == "give_way":
        facts = {**facts, **RULE18_GIVE_WAY, "rule18_basis": why}
    elif role == "stand_on":
        facts = {**facts, **RULE18_STAND_ON, "rule18_basis": why}
    elif role == "suspended":
        facts = {**facts, **RULE18_SUSPENDED, "rule18_suspended": True}
    return facts


# ── 실행 ────────────────────────────────────────────────────────────────────
def _step_params(steps):
    """[[기능명, {파라미터}], ...] → {기능명: {파라미터}}. 꺼진 기능은 애초에 안 온다."""
    enabled = {}
    for s in steps or []:
        if isinstance(s, (list, tuple)) and s:
            enabled[s[0]] = (s[1] if len(s) > 1 and isinstance(s[1], dict) else {})
        elif isinstance(s, str):
            enabled[s] = {}
    return enabled


TYPE_DISTRIBUTION_LIMIT = 20


def _top_types(counter):
    """선종 분포를 상위 N + 기타 합계로 접는다."""
    if len(counter) <= TYPE_DISTRIBUTION_LIMIT:
        return dict(counter)
    top = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    kept = dict(top[:TYPE_DISTRIBUTION_LIMIT])
    # 키가 사용자 CSV 표기라 "기타" 가 실제 값으로 들어올 수 있다. 충돌하면 잔여 합계가
    # 실제 건수를 덮어써 분포가 조용히 틀린다.
    kept["(상위 밖 합계)"] = sum(v for _, v in top[TYPE_DISTRIBUTION_LIMIT:])
    return kept


def _thumb(src, dst):
    """썸네일. 실패해도 계산 결과는 유효하므로 삼키고 넘어간다."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            th = im.copy()
            th.thumbnail((THUMB_EDGE, THUMB_EDGE))
            th.save(dst, quality=80)
    except Exception as e:  # noqa: BLE001
        log("log", level="warn", message=f"썸네일 생성 실패({os.path.basename(src)}): {e}")


def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    enabled = _step_params(steps)
    # 세 기능은 한 계산의 단계라 따로 끌 수 없다(조우 분류는 상대방위를, 위험도는
    # 속도벡터를 쓴다). 설정은 화면 표시를 위해 받되 계산은 항상 전부 수행한다.
    if enabled and STEP_ENCOUNTER not in enabled:
        log("log", level="warn",
            message=f"'{STEP_ENCOUNTER}' 가 꺼져 있으나 이 노드의 계산은 분리할 수 없어 "
                    "전체를 수행합니다")

    # 정면 인정 각도는 '조우 분류' 기능의 파라미터로 온다(BE SDS_COLREG_LIBRARY).
    # 설정을 저장하지 않은 파이프라인은 모듈 기본값으로 돈다.
    head_on_arc = (enabled.get(STEP_ENCOUNTER) or {}).get("headOnArcDeg")
    head_on_arc = float(head_on_arc) if head_on_arc is not None else HEAD_ON_ARC

    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {}, "kind": "source"}]
    drops = []
    rows = []
    by_encounter = {}
    by_risk = {}
    by_target_type = {}
    n_rule18 = 0
    n_type_unknown = 0
    n_target_skipped = 0
    n_rule18_suspended = 0
    for it in items:
        own = it.get("own")
        # 기하에 필요한 값이 다 있어야 한다. lat 만 보면 heading/knot 결측이 통과해
        # 대상 계산이 전멸하고, 예전에는 그것이 조용히 '안전' 으로 나갔다.
        if not isinstance(own, dict) or not all(
                k in own for k in ("lat", "lon", "knot", "heading")):
            drops.append({"asset_id": it.get("asset_id"), "timestamp": it.get("timestamp"),
                          "reason": "no_own_ship",
                          "message": "자선 상태가 없어 기하를 세울 수 없습니다"})
            continue
        try:
            facts = classify(own, it.get("others") or [], head_on_arc)
        except Exception as e:  # noqa: BLE001 - 한 씬이 나빠도 배치를 죽이지 않는다
            drops.append({"asset_id": it.get("asset_id"), "timestamp": it.get("timestamp"),
                          "reason": "calc_error", "message": f"{type(e).__name__}: {e}"[:160]})
            continue
        by_encounter[facts["encounter"]] = by_encounter.get(facts["encounter"], 0) + 1
        basis = facts.get("risk_basis") or "unknown"
        by_risk[basis] = by_risk.get(basis, 0) + 1
        if facts.get("rule18_basis"):
            n_rule18 += 1
        if facts.get("rule18_suspended"):
            n_rule18_suspended += 1
        n_target_skipped += facts.get("target_skipped") or 0
        target_type = facts.get("target_ship_type")
        if target_type:
            by_target_type[target_type] = by_target_type.get(target_type, 0) + 1
            if facts.get("target_type_category") is None:
                n_type_unknown += 1
        rows.append({**it, "colreg": facts})

    by_reason = {}
    for d in drops:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    funnel.append({"stage": "COLREG 계산", "in": len(items), "out": len(rows),
                   "dropped": dict(by_reason), "kind": "transform"})

    n_sample = 0
    written = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            asset_id = r.get("asset_id") or f"c{written:06d}"
            rel = f"assets/{asset_id}.jpg"
            try:
                shutil.copyfile(os.path.join(src_dir, r.get("path") or ""),
                                os.path.join(out_dir, rel))
            except OSError as e:
                drops.append({"asset_id": asset_id, "timestamp": r.get("timestamp"),
                              "reason": "image_copy_failed", "message": str(e)[:120]})
                by_reason["image_copy_failed"] = by_reason.get("image_copy_failed", 0) + 1
                continue
            if n_sample < SAMPLE_LIMIT:
                _thumb(os.path.join(out_dir, rel),
                       os.path.join(out_dir, "samples", f"{asset_id}.jpg"))
                n_sample += 1
            written += 1
            f.write(json.dumps({**r, "path": rel}, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    funnel[-1]["out"] = written
    funnel[-1]["dropped"] = dict(by_reason)
    # note 는 이미지 복사 실패까지 반영된 뒤 계산한다 — 먼저 만들면 같은 행의 out 보다
    # 큰 숫자가 적혀 "숫자가 상태를 잘못 말하는" 상태가 된다.
    n_no_risk = by_risk.get("no_risk", 0) + by_risk.get("no_target", 0)
    funnel[-1]["note"] = (f"충돌위험 있음 {max(0, written - n_no_risk)}건 · "
                          f"제7조상 위험 없음 {min(written, n_no_risk)}건"
                          + (f" · 제18조로 역할 결정 {n_rule18}건" if n_rule18 else "")
                          + (f" · 제18조 판정 보류 {n_rule18_suspended}건"
                             if n_rule18_suspended else "")
                          + (f" · 선종 미인식 {n_type_unknown}건" if n_type_unknown else "")
                          + (f" · 대상 읽기 실패 {n_target_skipped}척" if n_target_skipped
                             else ""))

    summary = {
        "node": "sds_colreg", "run_id": run_id, "node_index": params.get("node_index"),
        "rule_version": RULE_VERSION,
        "dry_run": dry_run, "in": len(items), "out": written,
        "dropped_total": len(drops), "sample_count": n_sample,
        # 조우 유형 분포는 이 노드의 핵심 산출이다. 한쪽으로 쏠려 있으면 임계각이
        # 이 항차에 맞지 않는다는 신호라, 화면이 바로 보여줘야 한다.
        "encounter_distribution": by_encounter,
        # 제7조 위험판정 근거별 분포. 한쪽으로 쏠리면 임계(RISK_*)가 이 항차에 맞지
        # 않는다는 신호라 화면이 바로 보여줘야 한다.
        "risk_distribution": by_risk,
        "rule18_decided": n_rule18,
        # 선종 분포와 "알아보지 못한" 건수. 이게 없으면 제18조가 한 번도 적용되지 않은
        # 것이 "특수선이 없었다" 인지 "표기를 못 읽었다" 인지 구별되지 않는다.
        # 사용자 CSV 표기가 키라 씬 수만큼 늘 수 있다. DB JSON 컬럼·API 응답에 그대로
        # 실리므로 상위만 남기고 나머지는 합계로 접는다.
        "target_type_distribution": _top_types(by_target_type),
        "target_type_unrecognized": n_type_unknown,
        # 자선 선종을 읽지 못한 경우도 여기서 잡힌다 — 대상선만 세면 자선 미인식이
        # 무음이 되고(자선은 항차 내내 한 척) 제18조가 전 씬에서 조용히 빠진다.
        "rule18_suspended": n_rule18_suspended,
        "target_read_failed": n_target_skipped,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "rule_version": RULE_VERSION,
                   "thresholds": {"head_on_arc": head_on_arc, "head_on_recip": head_on_arc,
                                  "starboard_arc": STARBOARD_ARC, "stern_arc": STERN_ARC,
                                  "risk_range_nm": RISK_RANGE_NM, "risk_cpa_nm": RISK_CPA_NM,
                                  "risk_tcpa_min": RISK_TCPA_MIN},
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_colreg/in", value=len(items))
    log("metric", name="sds_colreg/out", value=written)
    log("metric", name="sds_colreg/dropped", value=len(drops))
    log("log", level="info", message=f"조우 분포: {json.dumps(by_encounter, ensure_ascii=False)}")
    if n_rule18_suspended:
        log("log", level="warn",
            message=f"제18조 판정을 보류한 씬 {n_rule18_suspended}건 — 선종을 읽지 "
                    "못했거나(자선 포함) 제18조가 우열을 정하지 않는 조합입니다. "
                    "해당 씬에는 조우 조항을 붙이지 않았습니다")
    if written and not by_target_type:
        log("log", level="warn",
            message="선종 정보가 없어 제18조를 적용하지 않았습니다 — AIS 원본에 "
                    "ship_type 컬럼이 있는지, AIS 노드를 다시 실행했는지 확인하세요")
    if n_target_skipped:
        log("log", level="warn",
            message=f"기하를 계산할 수 없어 건너뛴 대상선 {n_target_skipped}척 "
                    "— 해당 씬은 남은 대상으로 판정했습니다")
    if n_type_unknown:
        log("log", level="warn",
            message=f"선종을 알아보지 못한 씬 {n_type_unknown}건 — 제18조 판정을 보류했습니다. "
                    f"관측된 선종: "
                    f"{json.dumps(sorted(_top_types(by_target_type)), ensure_ascii=False)}")
    if written and len(by_encounter) == 1:
        only = next(iter(by_encounter))
        log("log", level="warn",
            message=f"모든 씬이 '{only}' 로 분류됐습니다 — 임계각이 이 항차에 맞는지 확인하세요")
    print(f"[dp_colreg] {len(items)} → {written} (제외 {len(drops)}) {by_encounter} → {out_dir}",
          flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 COLREG 계산 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_COLREG_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
