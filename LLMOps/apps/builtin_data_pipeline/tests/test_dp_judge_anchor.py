"""Unit tests for apps/builtin_data_pipeline/dp_judge.py — 앵커 대조.

앵커 대조는 판사 점수보다 우선하는 판정이라(불일치면 colreg_correctness 를 0 으로 강등)
여기가 헐거우면 게이트 전체가 헐거워진다.

고정하는 불변식: **조항 앵커는 인용 형태로만 인정한다.** 생성 프롬프트가 변침각·목표
CPA·안전속력을 숫자로 쓰라고 강제하므로, 맨 숫자를 찾으면 "CPA 0.6해리"가 6조 인용으로,
"우현 15° 변침"이 15조 인용으로 잡혀 조항을 한 번도 인용하지 않은 조언이 통과한다.
"""
import pytest

import dp_judge as J


def facts(encounter, articles, own_role="give_way"):
    return {"encounter": encounter, "articles": articles, "own_role": own_role}


# ── 숫자 오탐이 통과하면 안 된다 ────────────────────────────────────────────
@pytest.mark.parametrize("articles, advice", [
    ([14, 6], "우현으로 변침하고 목표 CPA 0.6해리를 확보하라."),
    ([14, 6], "안전속력 6kt 로 감속할 것."),
    ([15, 16], "우현 15° 변침하여 타선 선미로 통과하라."),
    ([15, 16], "목표 CPA 1.6해리, 안전속력 16kt."),
    ([13], "13kt 로 유지하며 이격하라."),
])
def test_bare_numbers_do_not_count_as_article_citation(articles, advice):
    # 조우유형 단어가 없으므로 조항 앵커만으로 판정된다.
    assert J.colreg_anchor_ok(advice, facts("head_on", articles), "ko") is False


def test_article_6_is_not_matched_inside_article_16():
    assert J.colreg_anchor_ok("제16조에 따라 조치하라.", facts("head_on", [6]), "ko") is False


# ── 진짜 인용은 통과해야 한다 ───────────────────────────────────────────────
@pytest.mark.parametrize("articles, advice", [
    ([14, 6], "COLREG 제14조에 따라 우현 20° 변침, 안전속력 8kt."),
    ([15, 16], "제15조 및 제16조에 따라 타선 선미로 피하라."),
    ([14, 6], "제6조 안전속력을 준수하여 감속하라."),
    ([18, 16], "제18조에 따라 어선의 진로를 양보한다."),
])
def test_citation_form_counts(articles, advice):
    assert J.colreg_anchor_ok(advice, facts("head_on", articles), "ko") is True


def test_english_uses_rule_n_form():
    f = facts("crossing", [15, 16])
    assert J.colreg_anchor_ok("Alter course to starboard 15 deg, CPA 1.6NM.", f, "en") is False
    assert J.colreg_anchor_ok("Per Rule 15 and Rule 16, pass astern.", f, "en") is True


@pytest.mark.parametrize("advice", [
    "Per Rules 15 and 16, pass astern.",   # 복수형 — 가장 자연스러운 연접 인용
    "per rule 15, pass astern.",           # 소문자
    "COLREG Rule-15 applies.",             # 하이픈
])
def test_english_citation_variants_are_accepted(advice):
    """오탈락도 오탐과 같은 무게로 나쁘다 — 이 앵커는 모델 점수를 0 으로 덮어쓴다."""
    assert J.colreg_anchor_ok(advice, facts("crossing", [15, 16]), "en") is True


# ── 조우유형 단어만으로도 통과한다(기존 판정 유지) ──────────────────────────
def test_encounter_keyword_alone_passes():
    assert J.colreg_anchor_ok("횡단 상황이므로 우현 변침.", facts("crossing", [15, 16]), "ko")


@pytest.mark.parametrize("advice", [
    "오늘 날씨가 좋다.",
    # 생성 프롬프트가 모든 상황에 "안전속력(kt)" 을 수치로 쓰라고 강제하므로, 맨 "안전"
    # 을 인정 표기로 두면 조우가 없다고 계산된 레코드에 "우현 변침" 이라 써도 통과한다.
    "우현 20° 변침하고 안전속력 8kt 를 유지하라.",
    "목표 CPA 1.0해리 확보, 안전속력 10kt.",
    "Alter course to starboard 20 deg, safe speed 8kt.",
    "It is unsafe to hold course; alter to starboard.",
    "안전하지 않다. 충돌위험이 있다.",
])
def test_no_articles_does_not_pass_everything(advice):
    """제7조상 위험 없음(articles=[])에서 조항 검사를 공허하게 참으로 두면,
    아무 말이나 앵커를 통과해 이 대조가 검증하는 것이 없어진다."""
    assert J.colreg_anchor_ok(advice, facts("safe", [], own_role="n/a"), "ko") is False


@pytest.mark.parametrize("advice", [
    "충돌위험 없음 — 침로·속력 유지.",
    "위험 대상 없음.",
    "There is no risk of collision; maintain course and speed.",
])
def test_safe_facts_pass_when_the_advice_actually_says_so(advice):
    assert J.colreg_anchor_ok(advice, facts("safe", [], own_role="n/a"), "ko") is True


def test_article_anchor_is_not_gated_by_record_language():
    """한쪽 언어만 시도하면 반대 언어로 인용한 정상 조언이 오탈락한다."""
    f = facts("crossing", [15], own_role="give_way")
    assert J.colreg_anchor_ok("Per Rule 15, alter course to starboard.", f, "ko") is True
    assert J.colreg_anchor_ok("제15조에 따라 우현 변침.", f, "en") is True


def test_newline_between_rule_and_number_is_not_a_citation():
    f = facts("crossing", [15], own_role="give_way")
    assert J.colreg_anchor_ok("per the Rules\n15 knots", f, "en") is False


def test_role_claim_never_changes_the_anchor_verdict():
    """역할 주장은 점수에 개입하지 않는다.

    자유 서술에서 역할을 정규식으로 집어내려는 시도는 세 차례 모두 오탐과 오탈을 함께
    남겼다(어순 · 명사 부정 · 대명사 · 문장부호 없는 긴 조언). 앵커는 모델 점수를
    **덮어쓰는** 판정이라 오탐 하나가 옳은 답을 게이트에서 떨어뜨린다. 그래서 채점에서
    분리했고, 이 테스트가 그 분리를 고정한다.
    """
    f = facts("crossing", [15, 16], own_role="give_way")
    inverted = "횡단 상황이며 자선은 유지선이므로 침로를 유지한다."
    assert J.role_contradicted(inverted, "give_way") is True   # 참고 표시는 남는다
    assert J.colreg_anchor_ok(inverted, f, "ko") is True       # 그러나 점수는 건드리지 않는다


@pytest.mark.parametrize("advice", [
    "자선의 좌현측 타선이 유지선이므로 제15조에 따라 우현 20° 변침한다.",   # 어순
    "자선은 유지선이 아니라 피항선이므로 제15조에 따라 우현 변침한다.",     # 명사 부정
    "횡단 상황이며 자선은 타선(유지선)의 선미로 통과한다.",                 # 괄호 삽입
    "Crossing situation; she must keep clear by passing astern.",       # 대명사
])
def test_normal_advice_is_not_penalised_by_the_role_heuristic(advice):
    """이 문장들은 세 라운드에 걸쳐 각각 다른 이유로 오탈락했다."""
    assert J.colreg_anchor_ok(advice, facts("crossing", [15, 16],
                                            own_role="give_way"), "ko") is True


@pytest.mark.parametrize("maneuver_key", [
    "no_target", "no_risk", "head_on", "overtaking", "overtaking_stand_on",
    "crossing_give_way", "crossing_stand_on", "crossing_stand_on_abaft",
])
def test_advice_built_from_the_prompt_contract_passes(maneuver_key):
    """생성 프롬프트가 요구하는 대로(조우유형 명시 + 조항 인용 + 권고 반영) 쓴 조언은
    앵커를 통과해야 한다. 파이프라인이 자기 정답을 거부하면 게이트가 무의미해진다.

    권고문만으로는 통과를 요구하지 않는다 — 권고는 조언의 한 조각이고, 조우유형과 조항
    명시는 프롬프트가 따로 강제하는 항목이다.
    """
    import dp_colreg
    import dp_generate
    situation = dp_colreg.SITUATIONS[maneuver_key]
    word = dp_generate.ENCOUNTER_KO[situation["encounter"]]
    cites = " ".join(f"제{a}조" for a in situation["articles"])
    advice = f"{word} 상황입니다. {cites} {situation['maneuver']}".strip()
    assert J.colreg_anchor_ok(advice, situation, "ko") is True


@pytest.mark.parametrize("override", ["RULE18_GIVE_WAY", "RULE18_STAND_ON",
                                      "RULE18_SUSPENDED"])
def test_rule18_overrides_pass_the_anchor(override):
    """제18조 override 는 조우유형(기하)을 그대로 두고 역할·조항만 바꾼다. 그 조합으로
    조립한 조언도 통과해야 한다 — 보류(articles=[])는 조우유형 표기로만 통과한다."""
    import dp_colreg
    import dp_generate
    facts_18 = dict(dp_colreg.SITUATIONS["crossing_give_way"])
    facts_18.update(getattr(dp_colreg, override))
    word = dp_generate.ENCOUNTER_KO[facts_18["encounter"]]
    cites = " ".join(f"제{a}조" for a in facts_18["articles"])
    advice = f"{word} 상황입니다. {cites} {facts_18['maneuver']}".strip()
    assert J.colreg_anchor_ok(advice, facts_18, "ko") is True


# ── 조우 표기는 생성 계약에서 파생된다 ─────────────────────────────────────
def test_encounter_vocabulary_is_derived_from_the_generation_contract():
    """판사가 자기 목록을 들면, 생성 프롬프트가 "이 단어로 명시하라" 고 강제한 표기를
    배제해 지시를 정확히 따른 조언이 0 점이 된다. 실제로 그렇게 깨졌다."""
    import dp_generate
    for key, mandated in dp_generate.ENCOUNTER_KO.items():
        assert mandated in J.ENCOUNTER_KW[key]
        assert dp_generate.ENCOUNTER_EN[key] in J.ENCOUNTER_KW[key]


@pytest.mark.parametrize("advice", [
    "안전 상황입니다. 침로·속력을 유지하고 안전속력 10kt 를 유지하라.",
    "Safe situation. Maintain course and speed at a safe speed of 10kt.",
])
def test_advice_following_the_mandated_wording_passes(advice):
    assert J.colreg_anchor_ok(advice, facts("safe", [], own_role="n/a"), "ko") is True


def test_anchor_rule_version_is_recorded():
    """판정 방식이 바뀌면 이전 런과 점수를 나란히 놓을 수 없다 — 산출물에 판이 남아야 한다."""
    assert J.ANCHOR_RULE_VERSION >= 4
