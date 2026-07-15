"""Unit tests for ingress_manager.manager — 게시(D6) orphan sweep 안전 불변식.

kong_sweep_orphan_publish 는 3-way 리뷰에서 BLOCK 3건을 재설계로 해소했다:
  (a) 정상 기준 = row 존재(enabled 무관) → 중지-보존 게시를 삭제하지 않는다.
  (b) route(ext-dep-<id>) 앵커 → 우연히 'dep-N' 이름의 유저 consumer 오삭제 방지.
  (c) DB/Kong 열거 실패 시 skip, grace, 삭제 직전 TOCTOU 재확인.
이 스위트는 그 불변식과 `_orphan_dep_id` 의 ascii-digit 가드를 고정한다.
실 Kong/DB 미접촉 — manager 가 참조하는 db_deployment/kong_helper/deployment_api/time 을 patch.

⚠️ TOCTOU 마스킹 주의: sweep 은 삭제 직전 `db_deployment.get_deployment_api(did)` 가
truthy 면 보존한다. 이 값을 명시하지 않으면 MagicMock 기본값(truthy)이 되어 **모든**
후보가 raced 로 보존돼, known-set/grace 로직이 깨져도 테스트가 통과해 버린다(false
confidence). 따라서 teardown 미호출을 known-set/grace 로 검증하는 테스트는 반드시
`db.get_deployment_api.return_value = None` 로 재확인 관문을 열어 둔다.
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
    """row 없는 ext-dep-<id> route(grace 초과)는 teardown 된다."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []          # row 전무
    kong.list_routes.return_value = [_route("ext-dep-8", created=100)]  # 900s 전 → grace 초과
    db.get_deployment_api.return_value = None             # TOCTOU 재확인: 여전히 없음

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_called_once_with(8)


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_preserves_known_row(db, kong, dep_api, mtime):
    """row 가 존재하는 id(enabled 무관)는 정상 → 삭제하지 않는다.

    get_deployment_api 를 None 으로 명시해 TOCTOU 관문을 열어 둔다. 그래야 known-set
    제외가 실제로 teardown 을 막는지 검증된다(안 그러면 truthy-mock 이 대신 막아 통과)."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = [5]
    kong.list_routes.return_value = [_route("ext-dep-5", created=100)]
    db.get_deployment_api.return_value = None

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_skips_when_db_query_fails(db, kong, dep_api, mtime):
    """list_deployment_api_ids 가 None(조회 실패) → 빈 집합 오인 방지 위해 전면 skip."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = None

    manager.kong_sweep_orphan_publish()

    kong.list_routes.assert_not_called()
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

    get_deployment_api=None 으로 TOCTOU 관문을 열어, grace 체크가 실제로 막는지 검증."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.return_value = [_route("ext-dep-9", created=NOW - 30)]  # 30s < 60s
    db.get_deployment_api.return_value = None

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_missing_created_at_treated_as_now(db, kong, dep_api, mtime):
    """created_at 누락 → now 로 간주 → grace 보호(즉시 삭제 방지).

    get_deployment_api=None 으로 TOCTOU 관문을 열어, 'now 간주 → grace' 가 실제로 막는지 검증."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.return_value = [_route("ext-dep-9")]  # created_at 없음
    db.get_deployment_api.return_value = None

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_toctou_recheck_preserves_raced_publish(db, kong, dep_api, mtime):
    """스윕 도중 publish 가 row 를 쓴 경우(삭제 직전 재확인 truthy) 보존."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []          # 열거 시점엔 row 없음
    kong.list_routes.return_value = [_route("ext-dep-8", created=100)]
    db.get_deployment_api.return_value = {"deployment_id": 8}  # 재확인 시 존재 → raced

    manager.kong_sweep_orphan_publish()

    # 삭제 직전 그 id 로 재확인했고, 존재하므로 teardown 은 하지 않는다.
    db.get_deployment_api.assert_called_once_with(8)
    dep_api.teardown_deployment_api.assert_not_called()


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


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_uses_max_created_at_for_duplicate_ids(db, kong, dep_api, mtime):
    """같은 id 의 route 가 여럿이면 max(created_at) 채택(보호적) — 최신이 grace 이내면 skip.

    get_deployment_api=None 으로 TOCTOU 관문을 열어, max() 보호가 실제로 막는지 검증."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.return_value = [
        _route("ext-dep-8", created=100),        # 오래됨
        _route("ext-dep-8", created=NOW - 10),   # 방금 → max → grace 보호
    ]
    db.get_deployment_api.return_value = None

    manager.kong_sweep_orphan_publish()

    dep_api.teardown_deployment_api.assert_not_called()


@patch("ingress_manager.manager.time")
@patch("ingress_manager.manager.deployment_api")
@patch("ingress_manager.manager.kong_helper")
@patch("ingress_manager.manager.db_deployment")
def test_sweep_continues_after_teardown_error(db, kong, dep_api, mtime):
    """한 후보 teardown 이 예외를 던져도 나머지 후보는 계속 처리한다(다음 주기 재시도)."""
    mtime.time.return_value = NOW
    db.list_deployment_api_ids.return_value = []
    kong.list_routes.return_value = [
        _route("ext-dep-8", created=100),
        _route("ext-dep-9", created=100),
    ]
    db.get_deployment_api.return_value = None

    def _boom(did):
        if did == 8:
            raise Exception("teardown failed for 8")

    dep_api.teardown_deployment_api.side_effect = _boom

    manager.kong_sweep_orphan_publish()

    swept = sorted(c.args[0] for c in dep_api.teardown_deployment_api.call_args_list)
    assert swept == [8, 9]  # 8 이 실패해도 9 는 시도됐다
