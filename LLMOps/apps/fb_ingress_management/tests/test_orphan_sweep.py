"""Unit tests for ingress_manager.manager — 게시(D6) orphan sweep 안전 불변식.

kong_sweep_orphan_publish 는 3-way 리뷰에서 BLOCK 3건을 재설계로 해소했다:
  (a) 정상 기준 = row 존재(enabled 무관) → 중지-보존 게시를 삭제하지 않는다.
  (b) route(ext-dep-<id>) 앵커 → 우연히 'dep-N' 이름의 유저 consumer 오삭제 방지.
  (c) DB/Kong 열거 실패 시 skip, grace, 삭제 직전 후보별 재조회(TOCTOU + DB blip 방어).
이 스위트는 그 불변식과 `_orphan_dep_id` 의 ascii-digit 가드를 고정한다.
실 Kong/DB 미접촉 — manager 가 참조하는 db_deployment/kong_helper/deployment_api/time 을 patch.

TOCTOU 재확인 = **후보별로 teardown 직전** `db_deployment.list_deployment_api_ids()` 재조회
(단건 조회는 '부재'와 'DB 오류'가 둘 다 None 이라 구분 불가; 배치 스냅샷은 뒤 후보일수록 stale).
따라서 mock 은 list_deployment_api_ids 의 호출 순서로 재현한다:
`side_effect=[<시작 known>, <후보1 재조회>, <후보2 재조회>, ...]`.
teardown 미호출을 known-set/grace 로 검증하는 테스트는 재조회분을 **[](비어있음)** 으로 둬,
그 관문이 깨지면(예: grace 미적용) teardown 이 실제로 발생해 테스트가 실패하도록 한다(false-confidence 방지).
"""
from unittest.mock import patch

from ingress_manager import manager

NOW = 1000.0  # 고정 '현재' (created_at 을 이 기준으로 잡는다)


def _route(name, created=None):
    r = {"name": name}
    if created is not None:
        r["created_at"] = created
    return r


# ── _orphan_dep_id: prefix + ascii-digit 가드 ─────────────────────────────
def test_orphan_id_parses_ascii_digits():
    assert manager._orphan_dep_id("ext-dep-42", "ext-dep-") == 42


def test_orphan_id_none_on_prefix_mismatch():
    assert manager._orphan_dep_id("dep-42", "ext-dep-") is None


def test_orphan_id_none_on_non_digit_tail():
    assert manager._orphan_dep_id("ext-dep-abc", "ext-dep-") is None


def test_orphan_id_none_on_empty_tail():
    assert manager._orphan_dep_id("ext-dep-", "ext-dep-") is None


def test_orphan_id_none_on_missing_name():
    assert manager._orphan_dep_id(None, "ext-dep-") is None


def test_orphan_id_rejects_unicode_digit():
    """'²'.isdigit() 은 True 지만 int() 크래시 → isascii 가드가 None 으로 배제."""
    assert manager._orphan_dep_id("ext-dep-²", "ext-dep-") is None


# ── kong_sweep_orphan_publish ─────────────────────────────────────────────
@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_deletes_orphan_route(db, kong, dep_api, mtime):
    """row 없는 ext-dep-<id> route(grace 초과)는 teardown 된다.

    시작 known 빈 집합 + 후보별 재조회도 빈 집합 → 진짜 orphan 확정 → teardown."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], []]     # 시작 known, 후보 8 재조회
    kong.list_routes.return_value = [_route("ext-dep-8", created=100)]  # 900s 전 → grace 초과

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_called_once_with(8)
    dep_api.teardown_composite_service.assert_called_once_with(8)


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_preserves_known_row(db, kong, dep_api, mtime):
    """row 가 존재하는 id(enabled 무관)는 known-set 에서 제외 → 후보조차 안 됨 → 삭제 안 함.

    시작 [5] 로 5 를 제외; known 제외가 깨지면 후보 재조회([])에서 teardown 이 발생해 실패한다."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[5], []]    # 시작 known={5}; (제외가 깨질 때만 2번째 소비)
    kong.list_routes.return_value = [_route("ext-dep-5", created=100)]

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()
    assert db.list_deployment_api_ids.call_count == 1     # 후보 없음 → 후보별 재조회 안 함


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_skips_when_db_query_fails(db, kong, dep_api, mtime):
    """시작 list_deployment_api_ids 가 None(조회 실패) → 빈 집합 오인 방지 위해 전면 skip."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = None

    manager.kong_sweep_orphan_publish()

    kong.list_routes.assert_not_called()
    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_skips_candidate_when_recheck_fails(db, kong, dep_api, mtime):
    """후보별 재조회가 None(DB blip) → 부재로 오인해 유효 게시를 지우지 않도록 그 후보 보류.

    후속2 의 핵심: 단건 재확인이었으면 None 을 '부재'로 보고 teardown 했을 상황."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], None]   # 시작 known, 후보 8 재조회 실패
    kong.list_routes.return_value = [_route("ext-dep-8", created=100)]

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_skips_when_kong_enum_fails(db, kong, dep_api, mtime):
    """Kong route 열거 실패 → 부분 목록으로 유효 게시 오판 방지 위해 skip."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.side_effect = Exception("kong down")

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_grace_skips_fresh_route(db, kong, dep_api, mtime):
    """grace(60s) 이내 route 는 갓 게시(진행중)로 보고 skip.

    재조회분을 [] 로 둬, grace 가 안 먹으면 teardown 이 발생해 실패하도록 한다(gate open)."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], []]
    kong.list_routes.return_value = [_route("ext-dep-9", created=NOW - 30)]  # 30s < 60s

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_missing_created_at_treated_as_now(db, kong, dep_api, mtime):
    """created_at 누락 → now 로 간주 → grace 보호(즉시 삭제 방지)."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], []]
    kong.list_routes.return_value = [_route("ext-dep-9")]  # created_at 없음

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_recheck_preserves_raced_publish(db, kong, dep_api, mtime):
    """스윕 도중 publish 가 row 를 쓴 경우(후보별 재조회에 등장) 보존."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], [8]]    # 시작 known 없음 → 후보 8 재조회 시 등장
    kong.list_routes.return_value = [_route("ext-dep-8", created=100)]

    manager.kong_sweep_orphan_publish()

    assert db.list_deployment_api_ids.call_count == 2     # 시작 + 후보 8 재조회
    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_per_candidate_recheck_catches_between_candidate_publish(db, kong, dep_api, mtime):
    """후보별 재조회 — 앞 후보 teardown 중 뒤 후보가 재게시되면(다음 재조회에 등장) 뒤 후보는 보존.

    배치 스냅샷(루프 진입 전 1회)이었다면 이 재게시를 놓쳐 정상 배포를 오삭제했을 HIGH 회귀를 고정."""
    mtime.time.return_value = NOW
    # 시작 known 없음 → 후보 8 재조회 [](→teardown) → 후보 9 재조회 [9](사이에 재게시 → 보존)
    db.list_deployment_api_ids.side_effect = [[], [], [9]]
    kong.list_routes.return_value = [
        _route("ext-dep-8", created=100),
        _route("ext-dep-9", created=100),
    ]

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_called_once_with(8)  # 8 만, 9 는 보존


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_ignores_non_publish_routes(db, kong, dep_api, mtime):
    """ext-dep-<digits> 가 아닌 route(유저 route/비숫자 tail/무명)는 후보에서 제외."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.return_value = [
        _route("some-user-route", created=100),
        _route("ext-dep-abc", created=100),
        _route(None, created=100),
    ]

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()
    assert db.list_deployment_api_ids.call_count == 1     # 후보 없음 → 후보별 재조회 안 함


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_uses_max_created_at_for_duplicate_ids(db, kong, dep_api, mtime):
    """같은 id 의 route 가 여럿이면 max(created_at) 채택(보호적) — 최신이 grace 이내면 skip."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.side_effect = [[], []]
    kong.list_routes.return_value = [
        _route("ext-dep-8", created=100),        # 오래됨
        _route("ext-dep-8", created=NOW - 10),   # 방금 → max → grace 보호
    ]

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_continues_after_teardown_error(db, kong, dep_api, mtime):
    """한 후보 teardown 이 예외를 던져도 나머지 후보는 계속 처리한다(다음 주기 재시도)."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []          # 시작 + 각 후보 재조회 모두 빈 집합
    kong.list_routes.return_value = [
        _route("ext-dep-8", created=100),
        _route("ext-dep-9", created=100),
    ]

    def _boom(did):
        if did == 8:
            raise Exception("teardown failed for 8")

    dep_api.teardown_deployment_api.side_effect = _boom

    manager.kong_sweep_orphan_publish()

    swept = sorted(c.args[0] for c in dep_api.teardown_deployment_api.call_args_list)
    assert swept == [8, 9]  # 8 이 실패해도 9 는 시도됐다
    composite_swept = sorted(
        c.args[0] for c in dep_api.teardown_composite_service.call_args_list)
    assert composite_swept == [8, 9]  # 기본 정리 실패와 독립적으로 합성 service도 모두 시도
