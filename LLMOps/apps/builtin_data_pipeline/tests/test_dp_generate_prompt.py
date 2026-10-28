"""Unit tests for apps/builtin_data_pipeline/dp_generate.py — 프롬프트 조립 순서.

고정하는 불변식: **형식 지시(<describe>/<advice>)는 항상 프롬프트의 마지막에 온다.**
사용자 프롬프트를 그 뒤에 붙이면 그것이 모델에게 최종 발언이 되어 형식 지시를 덮어쓴다.
실제로 해양 파이프라인에 범용 VQA 기본값("JSON 배열로 하고 question/answer 키를
가진다")이 프리필된 채 실행돼, 생성 100건 중 87건이 parse_failed 로 떨어졌다.
"""
import pytest

import dp_generate as G

FACTS = {"encounter": "crossing", "own_role": "stand_on", "articles": [15, 17],
         "cpa_nm": 0.17, "tcpa_min": 0.6, "maneuver": "침로·속력 유지"}
# 이 사고를 일으킨 실제 값(constants.DEFAULT_PROMPT).
VQA_PROMPT = ("이 이미지에 대한 질문 3개와 그 답을 만들어라.\n"
              "출력은 JSON 배열로 하고 각 원소는 question, answer 키를 가진다.")
TAG_HEAD = {"ko": "반드시 <describe>", "en": "Reply EXACTLY as <describe>"}


@pytest.mark.parametrize("lang", ["ko", "en"])
@pytest.mark.parametrize("extra", ["", VQA_PROMPT, "짧게 답하라."])
def test_format_instruction_is_always_last(lang, extra):
    prompt = G.build_gen_prompt("AIS 텍스트", FACTS, lang, extra)
    assert prompt.splitlines()[-1].startswith(TAG_HEAD[lang])


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_user_prompt_precedes_format_instruction(lang):
    prompt = G.build_gen_prompt("AIS 텍스트", FACTS, lang, VQA_PROMPT)
    assert prompt.index("JSON 배열로") < prompt.index(TAG_HEAD[lang])


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_user_prompt_is_still_included(lang):
    """순서만 바꾼다 — 사용자 프롬프트를 버리지는 않는다."""
    prompt = G.build_gen_prompt("AIS 텍스트", FACTS, lang, "짧게 답하라.")
    assert "짧게 답하라." in prompt


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_assembly_order_is_ais_facts_instr_extra_tag(lang):
    """조립 순서 전체를 고정한다 — "tag 가 마지막"만 보면 extra 를 맨 앞으로 옮기는
    변경이 그대로 통과해, 사실 블록과 사용자 지시의 상대 위치가 조용히 바뀐다."""
    prompt = G.build_gen_prompt("AIS-마커", FACTS, lang, "EXTRA-마커")
    for earlier, later in (("AIS-마커", "[계산된" if lang == "ko" else "[Computed"),
                           ("[계산된" if lang == "ko" else "[Computed", "EXTRA-마커"),
                           ("EXTRA-마커", TAG_HEAD[lang])):
        assert prompt.index(earlier) < prompt.index(later), f"{earlier} → {later}"


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_no_extra_keeps_exact_assembly(lang):
    """extra 가 없으면 사실·지시·형식지시만 정해진 구분자로 이어진다."""
    prompt = G.build_gen_prompt("AIS 텍스트", FACTS, lang, "")
    instr = G.PROMPT_EN if lang == "en" else G.PROMPT_KO
    facts = G._facts_block(FACTS, lang)
    assert prompt.startswith(f"AIS 텍스트\n\n{facts}\n\n{instr}\n")
    assert prompt == prompt.rstrip()
    assert "\n\n\n" not in prompt


@pytest.mark.parametrize("extra", ["", "   ", "  \n\t "])
def test_blank_extra_never_inserts_a_line(extra):
    """공백만 있는 extra 는 줄을 만들지 않는다 — 호출부가 strip 하지 않아도."""
    assert (G.build_gen_prompt("AIS 텍스트", FACTS, "ko", extra)
            == G.build_gen_prompt("AIS 텍스트", FACTS, "ko", ""))


# 프롬프트 본문이 바뀌면 이 해시가 깨진다. 그때 PROMPT_REVISION 을 올리고 해시를
# 갱신하라 — dp_generate 가 개정 번호를 산출물에 남기는 이유(두 실행을 나란히 비교할
# 수 있어야 한다)를 사람이 기억에 의존하지 않게 하는 장치다.
PROMPT_GOLDEN = {"ko": "4fdf31e83eed6faa", "en": "6ec3477ad6abd0ee"}
PROMPT_GOLDEN_REVISION = 3


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_prompt_body_pinned_to_revision(lang):
    import hashlib
    assert G.PROMPT_REVISION == PROMPT_GOLDEN_REVISION, (
        "프롬프트 개정 번호가 바뀌었다면 PROMPT_GOLDEN 해시도 함께 갱신하라")
    prompt = G.build_gen_prompt("AIS 텍스트", FACTS, lang, "")
    got = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    assert got == PROMPT_GOLDEN[lang], (
        f"프롬프트 본문이 바뀌었다({lang}). PROMPT_REVISION 을 올리고 이 해시를 "
        f"{got} 로 갱신하라")
