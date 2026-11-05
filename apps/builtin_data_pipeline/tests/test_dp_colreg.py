"""Unit tests for apps/builtin_data_pipeline/dp_colreg.py — COLREG 규칙 부합성.

이 노드는 생성·심사가 정렬되는 **결정론 앵커**라, 여기서 틀리면 "틀린 답을 잘 맞춘
모델"이 고득점한다. 그래서 이 스위트는 성능이 아니라 COLREG 1972 원문의 적용조건을
고정한다 — 각 테스트 이름에 근거 조항을 적는다.

임계값(HEAD_ON_ARC·RISK_*)은 튜닝 대상이라 값 자체를 고정하지 않는다. 고정하는 것은
"어떤 조건에서 어떤 판정이 나와야 하는가" 뿐이다.
"""
import math

import pytest

import dp_colreg as C


# ── 씬 만들기 ───────────────────────────────────────────────────────────────
OWN_LAT, OWN_LON = 35.0, 129.0


def own_ship(heading=0.0, knot=10.0, ship_type="Boat"):
    return {"ship_id": 0, "is_own": True, "type": ship_type,
            "lat": OWN_LAT, "lon": OWN_LON, "knot": knot, "heading": heading}


def target(bearing_deg, range_nm, heading=0.0, knot=10.0, ship_type="Boat", ship_id=1):
    """자선에서 진방위 `bearing_deg`, 거리 `range_nm` 인 곳에 배를 놓는다."""
    br = math.radians(bearing_deg)
    dlat = range_nm * math.cos(br) / C.NM_PER_DEG_LAT
    dlon = range_nm * math.sin(br) / (C.NM_PER_DEG_LAT * math.cos(math.radians(OWN_LAT)))
    return {"ship_id": ship_id, "is_own": False, "type": ship_type,
            "lat": OWN_LAT + dlat, "lon": OWN_LON + dlon, "knot": knot, "heading": heading}


# ── Rule 7 — 충돌위험이 없으면 조우가 성립하지 않는다 ────────────────────────
def test_rule7_no_target_is_safe():
    f = C.classify(own_ship(), [])
    assert f["encounter"] == "safe" and f["articles"] == []


def test_rule7_far_and_diverging_is_safe_without_articles():
    # 정횡 20NM, 반대 방향으로 멀어짐 → 위험 없음. 제15·17조를 붙이면 안 된다.
    f = C.classify(own_ship(heading=0.0), [target(90.0, 20.0, heading=90.0)])
    assert f["encounter"] == "safe"
    assert f["articles"] == []
    assert f["risk"] is False


def test_rule7_close_quarters_is_risk_even_when_separating():
    # 최근접점을 막 지나 벌어지는 중이라도 0.3NM 이면 근접상황이다. 7(a) "의심스러우면
    # 위험이 있다고 본다" — 이걸 '위험 없음' 으로 흘리면 조우 라벨이 통째로 빠진다.
    f = C.classify(own_ship(heading=0.0), [target(180.0, 0.3, heading=180.0, knot=12.0)])
    assert f["risk"] is True
    assert f["encounter"] != "safe"


def test_rule7_closing_within_thresholds_is_risk():
    f = C.classify(own_ship(heading=0.0), [target(0.0, 3.0, heading=180.0, knot=10.0)])
    assert f["risk"] is True


# ── Rule 14 — 정면 조우 ──────────────────────────────────────────────────────
def test_rule14_head_on_gives_both_give_way_and_article_14():
    f = C.classify(own_ship(heading=0.0), [target(0.0, 1.0, heading=180.0)])
    assert f["encounter"] == "head_on"
    assert f["own_role"] == "both_give_way"
    assert 14 in f["articles"]


def test_rule14c_wider_arc_admits_more_head_on():
    """14(c) 의심스러우면 정면으로 가정 — 여유각을 넓히면 정면 판정이 늘어야 한다."""
    others = [target(30.0, 1.0, heading=210.0)]
    assert C.classify(own_ship(), others, head_on_arc=10)["encounter"] != "head_on"
    assert C.classify(own_ship(), others, head_on_arc=40)["encounter"] == "head_on"


# ── Rule 13 — 추월 ──────────────────────────────────────────────────────────
def test_rule13_overtaking_from_astern_when_faster():
    # 자선이 타선 선미측(타선 뒤)에서 더 빠르게 접근 = 추월
    f = C.classify(own_ship(heading=0.0, knot=15.0), [target(0.0, 1.0, heading=0.0, knot=5.0)])
    assert f["encounter"] == "overtaking"
    assert f["own_role"] == "give_way"
    assert f["articles"] == [13]


def test_rule13a_survives_the_rule7_risk_gate():
    """13(a) 는 "Notwithstanding anything contained in the Rules of this Section" 이고
    제14·15조와 달리 충돌위험 문구가 없다. 그래서 위험 게이트가 추월을 지우면 안 된다."""
    # 20NM 앞의 배를 3kt 차이로 따라붙는 중 — TCPA 가 위험 창 밖이라 제7조만으로는
    # '위험 없음' 이지만, 13조는 충돌위험을 전제하지 않으므로 추월로 남아야 한다.
    f = C.classify(own_ship(heading=0.0, knot=18.0),
                   [target(0.0, 20.0, heading=0.0, knot=15.0)])
    assert f["risk"] is False
    assert f["encounter"] == "overtaking"
    assert f["articles"] == [13]


def test_overtaking_needs_closing_not_just_being_faster():
    """13(b) 의 "coming up with" 은 상대운동이다. 자선이 더 빠르지만 멀어지는 중이면
    추월이 아니다 — 스칼라 속도 비교만 하면 이런 배도 추월로 잡힌다."""
    own = own_ship(heading=0.0, knot=20.0)
    away = target(180.0, 0.5, heading=180.0, knot=20.0)   # 서로 반대로 멀어짐
    assert C.geometric_situation(own, away)[0] not in C.OVERTAKING_SITUATIONS


def test_being_overtaken_is_rule13_stand_on():
    """13조는 양방향을 규정한다. 뒤에서 더 빠른 배가 붙으면 자선은 피추월선이다."""
    f = C.classify(own_ship(heading=0.0, knot=8.0),
                   [target(180.0, 0.8, heading=0.0, knot=16.0)])
    assert f["encounter"] == "overtaking"
    assert f["own_role"] == "stand_on"
    assert 13 in f["articles"]


# ── Rule 15/17 — 횡단 ───────────────────────────────────────────────────────
def test_rule15_target_on_starboard_makes_us_give_way():
    f = C.classify(own_ship(heading=0.0), [target(45.0, 1.0, heading=270.0)])
    assert f["encounter"] == "crossing" and f["own_role"] == "give_way"
    assert 15 in f["articles"]


def test_rule17_target_on_port_makes_us_stand_on_with_phases():
    f = C.classify(own_ship(heading=0.0), [target(315.0, 1.0, heading=90.0)])
    assert f["encounter"] == "crossing" and f["own_role"] == "stand_on"
    assert f["articles"] == [17]
    # 17 은 단계가 있다 — 유지만 말하고 (a)(ii)/(b)/(c) 를 빼면 규칙의 절반이다.
    for phase in ("(a)(i)", "(a)(ii)", "(b)", "(c)"):
        assert phase in f["maneuver"]


# ── Rule 18 — 선박 사이의 책임 ──────────────────────────────────────────────
def test_rule18_fishing_target_flips_stand_on_to_give_way():
    """18(a)(iii) 동력선은 어로종사선에 진로를 양보한다 — 좌현측이라도 유지선이 아니다."""
    others = [target(315.0, 1.0, heading=90.0, ship_type="Fishing")]
    f = C.classify(own_ship(ship_type="Boat"), others)
    assert f["own_role"] == "give_way"
    assert 18 in f["articles"]
    assert f["rule18_basis"] == "Fishing"
    # 조우유형은 기하 그대로여야 한다(하류 앵커가 이 문자열로 대조한다).
    assert f["encounter"] == "crossing"


def test_rule18_does_not_override_overtaking():
    """18조 본문 "Except where Rules 9, 10 and 13 otherwise require" — 추월은 그대로."""
    others = [target(0.0, 1.0, heading=0.0, knot=5.0, ship_type="Fishing")]
    f = C.classify(own_ship(knot=15.0), others)
    assert f["encounter"] == "overtaking"
    assert f["articles"] == [13]
    assert f["rule18_basis"] is None


def test_rule18_does_not_apply_between_equal_ranks():
    """같은 서열끼리는 18조가 우열을 정하지 않으므로 기하 판정을 그대로 둔다."""
    others = [target(315.0, 1.0, heading=90.0, ship_type="Fishing")]
    f = C.classify(own_ship(ship_type="Fishing"), others)
    assert f["own_role"] == "stand_on"
    assert f["rule18_basis"] is None


def test_rule18_ignored_when_type_key_absent():
    """예전 AIS 노드가 만든 씬에는 `type` 키가 **아예 없다**. 기하만으로 판정해야 한다."""
    own, other = own_ship(), target(315.0, 1.0, heading=90.0)
    del own["type"]
    del other["type"]
    f = C.classify(own, [other])
    assert f["own_role"] == "stand_on" and f["rule18_basis"] is None


# ── Rule 7 — 대상선 선택 ────────────────────────────────────────────────────
def test_target_is_not_chosen_by_input_order():
    """Rule 7 은 접근하는 선박을 평가하라고 하지 입력 순서를 따르라고 하지 않는다."""
    far = target(90.0, 5.0, heading=270.0, ship_id=7)
    near = target(315.0, 0.5, heading=90.0, ship_id=9)
    f = C.classify(own_ship(), [far, near])
    assert f["target_ship_id"] == 9


# ── 하류 계약 ───────────────────────────────────────────────────────────────
def test_every_situation_maps_to_downstream_encounter_vocabulary():
    """encounter 문자열은 dp_generate·dp_judge 와 공유하는 계약이다.

    한쪽만 늘리면 생성은 번역을 못 하고 심사는 앵커를 못 찾아 조용히 0 점이 된다.
    """
    import dp_generate
    import dp_judge
    produced = {v["encounter"] for v in C.SITUATIONS.values()}
    assert produced <= set(dp_generate.ENCOUNTER_KO)
    assert produced <= set(dp_generate.ENCOUNTER_EN)
    assert produced <= set(dp_judge.ENCOUNTER_KW)


def test_every_role_maps_to_downstream_role_vocabulary():
    import dp_generate
    roles = ({v["own_role"] for v in C.SITUATIONS.values()}
             | {C.RULE18_GIVE_WAY["own_role"], C.RULE18_STAND_ON["own_role"]})
    assert roles <= set(dp_generate.ROLE_KO)
    assert roles <= set(dp_generate.ROLE_EN)


def test_every_situation_geometry_can_produce_exists_in_rule_table():
    """기하가 낼 수 있는 상황 키가 규칙 테이블에 다 있어야 한다(KeyError 방지).

    손으로 적은 목록이 아니라 실제 산출에서 뽑는다 — 새 반환값이 생기면 여기서 걸린다.
    """
    produced = set()
    for brg in range(0, 360, 15):
        for hdg in range(0, 360, 30):
            for knot in (4.0, 10.0, 18.0):
                produced.add(C.geometric_situation(
                    own_ship(), target(float(brg), 1.0, heading=float(hdg), knot=knot))[0])
    assert produced, "기하가 아무 상황도 내지 못했다"
    assert produced <= set(C.SITUATIONS)
    assert set(C.OVERTAKING_SITUATIONS) <= set(C.SITUATIONS)


# ── Rule 7 — 대상 선택이 위험을 가리면 안 된다 ───────────────────────────────
@pytest.mark.parametrize("diverging_range", [1.0, 1.99, 2.1, 5.0])
def test_ambiguously_near_diverging_vessel_yields_to_a_collision_course(diverging_range):
    """애매하게 가까우면서 **멀어지는** 배가 충돌 코스로 오는 배를 가리면 안 된다.

    임계값(RISK_RANGE_NM) 양쪽을 훑는다 — 예전 판은 임계 밖에서만 통과했다.
    """
    near_diverging = target(90.0, diverging_range, heading=90.0, knot=20.0, ship_id=7)
    far_collision = target(0.0, 3.0, heading=180.0, knot=10.0, ship_id=9)
    f = C.classify(own_ship(), [near_diverging, far_collision])
    assert f["target_ship_id"] == 9
    assert f["risk"] is True


@pytest.mark.parametrize("very_close_range", [0.05, 0.2, 0.5])
def test_a_vessel_within_arms_reach_is_the_fact_even_if_diverging(very_close_range):
    """수백 미터 앞의 배는 이탈 중이라도 그 씬의 사실이다 — 이미지에 찍혀 있는 배를
    사실에서 빼면 서술 정확도·이미지 근거 축이 옳은 서술을 벌한다.

    앞 테스트와 함께 두 구간을 각각 고정한다. 하나로 뭉치면 어느 쪽이든 잘못된 불변식을
    정답으로 굳히게 된다(예전 판이 그랬다).
    """
    very_close = target(180.0, very_close_range, heading=0.0, knot=1.0, ship_id=7)
    far_collision = target(0.0, 6.0, heading=180.0, knot=10.0, ship_id=9)
    f = C.classify(own_ship(), [very_close, far_collision])
    assert f["target_ship_id"] == 7
    assert f["range_nm"] <= C.VERY_CLOSE_NM


def test_non_risky_overtaking_must_not_outrank_a_real_collision_risk():
    """제13조는 충돌위험을 전제하지 않으므로 위험하지 않은 추월도 후보가 된다. 그러나
    후보 안에서 위험을 앞세우지 않으면 최종 판정이 'no_risk' 로 뒤집힌다."""
    non_risky_overtaking = target(67.0, 4.0, heading=0.0, knot=10.0, ship_id=7)
    real_risk = target(0.0, 8.0, heading=180.0, knot=20.0, ship_id=9)
    f = C.classify(own_ship(knot=20.0), [non_risky_overtaking, real_risk])
    assert f["target_ship_id"] == 9
    assert f["risk"] is True


def test_all_targets_unreadable_is_dropped_not_labelled_safe():
    """대상이 있었는데 전부 읽지 못한 것은 "위험 대상 없음" 과 다른 사실이다.
    조용히 안전으로 흘리면 그 씬이 그대로 학습 레코드가 된다."""
    with pytest.raises(ValueError):
        C.classify(own_ship(), [{"ship_id": 9, "is_own": False, "lat": "??"}])


def test_partial_target_failure_is_counted_in_facts():
    good = target(315.0, 1.0, heading=90.0, ship_id=3)
    f = C.classify(own_ship(), [{"ship_id": 4, "is_own": False, "lat": "??"}, good])
    assert f["target_ship_id"] == 3
    assert f["target_skipped"] == 1


def test_no_risk_fallback_reports_the_closing_vessel_not_the_receding_one():
    """이탈선은 TCPA 가 0 이라 위험도 순서로는 1등이 된다. 그대로 쓰면 "위험 없음 ·
    CPA 9해리 · TCPA 0분" 처럼 스스로 모순인 그라운딩이 나온다."""
    receding = target(90.0, 9.0, heading=90.0, knot=15.0, ship_id=3)
    approaching = target(0.0, 30.0, heading=180.0, ship_id=5)
    f = C.classify(own_ship(), [receding, approaching])
    assert f["risk"] is False
    assert f["target_ship_id"] == 5


def test_long_range_collision_course_is_not_safe():
    """CPA 0 인 정면 접근이 '아직 멀어서' 안전으로 분류되면 안 된다."""
    f = C.classify(own_ship(heading=0.0, knot=10.0),
                   [target(0.0, 11.0, heading=180.0, knot=10.0)])
    assert f["risk"] is True
    assert f["encounter"] == "head_on"


def test_target_choice_is_stable_for_identical_geometry():
    """같은 입력이 같은 결과를 내야 한다 — 동률에서 입력 순서로 흔들리면 안 된다."""
    a = target(315.0, 1.0, heading=90.0, ship_id=2)
    b = target(315.0, 1.0, heading=90.0, ship_id=5)
    assert (C.classify(own_ship(), [a, b])["target_ship_id"]
            == C.classify(own_ship(), [b, a])["target_ship_id"])


def test_target_identity_is_exposed_in_facts():
    """어느 배에 대한 판정인지 사실에 남아야 한다(다중선박 씬에서 필수)."""
    f = C.classify(own_ship(), [target(315.0, 1.0, heading=90.0,
                                       ship_type="Fishing Vessel", ship_id=4)])
    assert f["target_ship_id"] == 4
    assert f["target_ship_type"] == "Fishing Vessel"
    assert f["target_type_category"] == "fishing"


def test_one_bad_target_does_not_drop_the_whole_scene():
    good = target(315.0, 1.0, heading=90.0, ship_id=3)
    bad = {"ship_id": 4, "is_own": False, "type": "Boat", "lat": "??"}
    assert C.classify(own_ship(), [bad, good])["target_ship_id"] == 3


# ── 선종 어휘 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name, expected", [
    ("Fishing", "fishing"),
    ("Fishing Vessel", "fishing"),
    ("어선", "fishing"),
    ("30", "fishing"),                              # ITU-R M.1371 선종 코드
    ("Sailing Vessel", "sailing"),
    ("36", "sailing"),
    ("Restricted in ability to manoeuvre", "restricted"),
    ("Not Under Command", "not_under_command"),
    ("Cargo", "power_driven"),
    ("Cruise", "power_driven"),
])
def test_vessel_category_reads_real_ais_vocabulary(name, expected):
    """정확일치만 보면 'Fishing Vessel' 같은 흔한 표기가 통째로 빠지고, 그때 틀리는
    방향이 '자선이 유지선' 이라 위험한 쪽이다."""
    assert C.vessel_category(name) == expected


def test_unknown_vessel_type_suspends_rule18_instead_of_assuming_power_driven():
    """모르는 표기를 동력선으로 가정하면 실제로는 어선인 배에 대해 자선을 유지선으로
    라벨링하게 된다. 판정을 보류하고 그 사실이 드러나야 한다."""
    assert C.vessel_category("Zeta-9") is None
    f = C.classify(own_ship(), [target(315.0, 1.0, heading=90.0, ship_type="Zeta-9")])
    assert f["rule18_basis"] is None
    assert f["target_type_category"] is None


# ── Rule 18 — 선종 서열 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("own_type, other_type, expected_role", [
    ("Boat", "Fishing", "give_way"),        # 18(a) 동력선 → 어로종사선
    ("Boat", "Sailing Vessel", "give_way"),  # 18(a) 동력선 → 범선
    ("Sailing", "Fishing", "give_way"),      # 18(b) 범선 → 어로종사선
    ("Fishing", "Not Under Command", "give_way"),  # 18(c) 어로종사선 → 조종불능선
    ("Sailing", "Cargo", "stand_on"),        # 역방향: 동력선이 범선을 피해야 한다
    ("Fishing", "Cargo", "stand_on"),
])
def test_rule18_ranks_decide_the_role(own_type, other_type, expected_role):
    others = [target(315.0, 1.0, heading=90.0, ship_type=other_type)]
    f = C.classify(own_ship(ship_type=own_type), others)
    assert f["own_role"] == expected_role
    assert 18 in f["articles"]
    # 조우유형은 기하 그대로여야 한다(하류 앵커가 이 문자열로 대조한다).
    assert f["encounter"] == "crossing"


# ── Rule 17(c) — 좌현 전제 ──────────────────────────────────────────────────
def test_port_side_stand_on_keeps_the_rule17c_clause():
    f = C.classify(own_ship(), [target(315.0, 1.0, heading=90.0)])
    assert f["rel_bearing_deg"] < 0
    assert "좌현측" in f["maneuver"]


def test_starboard_quarter_stand_on_must_not_claim_a_port_side_vessel():
    """17(c) 는 좌현측 선박 한정이다. 우현 후방 대상에게 그 문장을 붙이면 결정론 앵커가
    거짓 사실을 생성 프롬프트에 박는다."""
    f = C.classify(own_ship(), [target(150.0, 1.0, heading=90.0, knot=2.0)])
    assert f["rel_bearing_deg"] > C.STARBOARD_ARC
    assert f["own_role"] == "stand_on"
    assert "좌현측" not in f["maneuver"]


# ── 경계 ────────────────────────────────────────────────────────────────────
def test_is_closing_is_false_for_zero_relative_motion():
    own = own_ship(heading=0.0, knot=10.0)
    same = target(0.0, 1.0, heading=0.0, knot=10.0)
    assert C.is_closing(own, same) is False


def test_is_closing_is_false_for_exactly_orthogonal_relative_motion():
    """부동소수 잔차(1e-16 규모)를 접근으로 오판하면 정지 중인 배가 추월이 된다."""
    own = own_ship(heading=0.0, knot=0.0)
    crossing_astern = target(180.0, 1.0, heading=90.0, knot=10.0)
    assert C.is_closing(own, crossing_astern) is False
    assert C.geometric_situation(own, crossing_astern)[0] not in C.OVERTAKING_SITUATIONS


def test_is_closing_is_false_after_passing_cpa():
    own = own_ship(heading=0.0, knot=10.0)
    passed = target(0.0, 1.0, heading=0.0, knot=20.0)   # 앞서 나가는 중
    assert C.is_closing(own, passed) is False


def test_stern_arc_boundary_is_not_decided_by_float_noise():
    """Rule 13(b) 의 "정횡후 22.5°보다 뒤" 는 엄격 경계다. 정확히 112.5° 로 놓은 입력이
    112.50000000000034 로 계산돼 추월로 넘어가면 안 된다."""
    own = own_ship(heading=0.0, knot=15.0)
    at_boundary = target(C.STARBOARD_ARC, 1.0, heading=0.0, knot=5.0)
    situation = C.geometric_situation(own, at_boundary)[0]
    assert situation != "overtaking_stand_on"


def test_dead_astern_is_not_called_a_port_side_vessel():
    """_norm180(180) 이 -180 을 돌려주므로 부호만 보면 정선미가 좌현측이 된다."""
    f = C.classify(own_ship(), [target(180.0, 1.0, heading=90.0)])
    assert f["rel_bearing_deg"] == -180.0
    assert "좌현측" not in f["maneuver"]


# ── Rule 18 보류 ────────────────────────────────────────────────────────────
def test_rule18_suspends_between_nuc_and_ram():
    """(a)~(c) 는 조종불능·조종제한을 항상 묶음으로 나열한다 — 둘 사이 우열은 없다.

    "보류" 는 기하 역할로 돌아가는 것이 아니다. 제15·17조는 두 동력선을 전제하므로,
    선종 서열을 모르면 기하 판정도 근거가 없다. 메타데이터만 검사하면 기하 역할로
    복귀하는 회귀가 그대로 통과한다(예전 판이 그랬다).
    """
    assert C.VESSEL_RANK["not_under_command"] == C.VESSEL_RANK["restricted"]
    f = C.classify(own_ship(ship_type="Not Under Command"),
                   [target(45.0, 1.0, heading=270.0,
                           ship_type="Restricted in ability to manoeuvre")])
    assert f["rule18_suspended"] is True
    assert f["own_role"] == "n/a"
    assert f["articles"] == []


@pytest.mark.parametrize("other_type", [
    "Vessel constrained by her draught",   # 18(d)
    "Seaplane",                            # 18(e)
    "WIG craft",                           # 18(f)
])
def test_rule18_suspends_for_categories_outside_abc(other_type):
    """(a)~(c) 로 서열이 나오지 않는 범주는 조항을 붙이지 않는다."""
    f = C.classify(own_ship(ship_type="Cargo"),
                   [target(45.0, 1.0, heading=270.0, ship_type=other_type)])
    assert f["rule18_suspended"] is True
    assert f["own_role"] == "n/a"
    assert f["articles"] == []


def test_rule18_over_head_on_keeps_the_geometry_label_and_cites_18():
    """제18조가 제14조를 대체해도 encounter 는 기하 라벨로 유지한다 — 이 문자열은 하류
    3곳이 공유하는 계약이라 값을 늘리면 한쪽만 갱신됐을 때 조용히 0 점이 된다."""
    f = C.classify(own_ship(ship_type="Cargo"),
                   [target(0.0, 1.0, heading=180.0, ship_type="Sailing Vessel")])
    assert f["encounter"] == "head_on"
    assert f["own_role"] == "give_way"
    assert 18 in f["articles"] and 14 not in f["articles"]


def test_unreadable_own_ship_type_suspends_rule18_instead_of_confirming_geometry():
    """자선 선종을 읽지 못하면 제18조가 전 씬에서 빠진다(자선은 항차 내내 한 척).
    그때 기하 역할을 확정하면, 어선을 상대로 자선이 유지선이라는 라벨이 학습 정답이 된다.
    """
    f = C.classify(own_ship(ship_type="Zeta-9"),
                   [target(315.0, 1.0, heading=90.0, ship_type="Fishing Vessel")])
    assert f["rule18_suspended"] is True
    assert f["own_role"] == "n/a" and f["articles"] == []


def test_legacy_scene_without_any_type_still_uses_geometry():
    """선종 컬럼이 아예 없는 예전 씬은 v1·v2 와 같이 기하만으로 판정한다 — 여기서
    보류하면 예전 데이터셋이 조항 앵커를 통째로 잃는다."""
    own, other = own_ship(), target(315.0, 1.0, heading=90.0)
    del own["type"]
    del other["type"]
    f = C.classify(own, [other])
    assert f["rule18_suspended"] is False
    assert f["own_role"] == "stand_on" and f["articles"] == [17]


def test_top_types_bucket_does_not_collide_with_a_real_ship_type():
    """분포 키가 사용자 CSV 표기라 '기타' 가 실제 값으로 들어온다. 잔여 합계가 그 값을
    덮으면 '특수선이 없었나 vs 표기를 못 읽었나' 판단 근거가 조용히 틀린다."""
    counter = {"기타": 500}
    counter.update({f"t{i}": i + 1 for i in range(C.TYPE_DISTRIBUTION_LIMIT + 5)})
    folded = C._top_types(counter)
    assert folded["기타"] == 500
    assert sum(folded.values()) == sum(counter.values())
