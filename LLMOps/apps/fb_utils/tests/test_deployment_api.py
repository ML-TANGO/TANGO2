"""Unit tests for apps/fb_utils/deployment_api.py — 게시(D6) teardown core + 식별자 헬퍼.

teardown_deployment_api 는 publish 의 역연산으로, 3-way 리뷰에서 "부분 실패 시
유효 키 + 살아있는 route 를 남기면 안 된다"(HIGH)는 불변식을 재설계로 확보했다.
이 스위트는 그 불변식(크리덴셜-first, 각 단계 독립 시도, aggregate-raise, route_id
fallback 체인)을 mock 으로 고정한다. 실 Kong/DB 는 건드리지 않는다 —
`utils.deployment_api` 가 참조하는 `kong_helper`/`db_deployment` 를 patch 한다.
"""
from unittest.mock import Mock, patch

import pytest

from utils import deployment_api


# ── 순수 식별자 헬퍼 ──────────────────────────────────────────────────────
def test_route_path_prefixes_ext():
    assert deployment_api.external_route_path("abc") == "/ext/abc"


def test_consumer_name_is_dep_prefixed():
    assert deployment_api.api_consumer_name(7) == "dep-7"


def test_external_route_name_is_ext_dep_prefixed():
    assert deployment_api.external_route_name(7) == "ext-dep-7"


# ── teardown_deployment_api ───────────────────────────────────────────────
@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_uses_row_route_id_and_consumer(kong, db):
    """row 의 api_route_id/api_consumer 를 그대로 쓰고 2차 조회는 하지 않는다.

    consumer 는 결정적 fallback('dep-7')과 다른 값을 넣어, 코드가 row 값을
    실제로 읽는지(계산값으로 대체하지 않는지) 검증한다."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-custom", "api_route_id": "R1"}
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(7)

    kong.delete_key_auths.assert_called_once_with("dep-custom")
    kong.delete_consumer.assert_called_once_with("dep-custom")
    kong.delete_route.assert_called_once_with("R1")
    db.delete_deployment_api.assert_called_once_with(7)
    # route_id 를 row 에서 얻었으므로 배포/경로 2차 조회는 하지 않는다.
    db.get_deployment.assert_not_called()
    kong.find_route_id_by_path.assert_not_called()
    kong.find_route_id_by_name.assert_not_called()


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_uses_computed_consumer_when_row_lacks_key(kong, db):
    """row 가 있어도 api_consumer 키가 없으면 결정적 이름(dep-<id>)으로 fallback."""
    db.get_deployment_api.return_value = {"api_route_id": "R1"}  # api_consumer 누락
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(7)

    kong.delete_key_auths.assert_called_once_with("dep-7")
    kong.delete_consumer.assert_called_once_with("dep-7")


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_credentials_deleted_before_route_and_row(kong, db):
    """키 무효화 최우선 — 크리덴셜 삭제가 route 삭제·DB row 삭제보다 먼저.

    kong/db 를 한 parent mock 에 붙여 두 mock 에 걸친 호출 순서를 검증한다
    (route 뿐 아니라 DB row 삭제보다도 크리덴셜이 앞서는지까지 고정)."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    db.delete_deployment_api.return_value = {"result": True}
    parent = Mock()
    parent.attach_mock(kong, "kong")
    parent.attach_mock(db, "db")

    deployment_api.teardown_deployment_api(7)

    names = [c[0] for c in parent.mock_calls]
    assert names.index("kong.delete_key_auths") < names.index("kong.delete_route")
    assert names.index("kong.delete_consumer") < names.index("kong.delete_route")
    assert names.index("kong.delete_key_auths") < names.index("db.delete_deployment_api")


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_falls_back_to_path_lookup_when_no_route_id(kong, db):
    """row 에 route_id 가 없으면 get_deployment→api_path→find_route_id_by_path."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {"api_path": "abc"}
    kong.find_route_id_by_path.return_value = "R2"
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(9)

    # 2차 조회는 keyword 인자 deployment_id 로 호출된다(positional 이면 deployment_name 에 바인딩).
    db.get_deployment.assert_called_once_with(deployment_id=9)
    kong.find_route_id_by_path.assert_called_once_with("/ext/abc")
    kong.delete_route.assert_called_once_with("R2")
    kong.find_route_id_by_name.assert_not_called()
    # consumer 는 row 부재 시 결정적 이름으로 기본.
    kong.delete_key_auths.assert_called_once_with("dep-9")


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_falls_back_to_name_when_path_lookup_misses(kong, db):
    """api_path 는 있으나 path 로 route 를 못 찾으면 route name 으로 재탐색한다."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {"api_path": "abc"}
    kong.find_route_id_by_path.return_value = None      # path 조회 miss
    kong.find_route_id_by_name.return_value = "R3"
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(9)

    kong.find_route_id_by_path.assert_called_once_with("/ext/abc")
    kong.find_route_id_by_name.assert_called_once_with("ext-dep-9")
    kong.delete_route.assert_called_once_with("R3")


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_falls_back_to_name_lookup_when_path_missing(kong, db):
    """api_path 소실(배포 삭제) 시 path 조회를 건너뛰고 route name 으로 정리."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {}                 # api_path 없음
    kong.find_route_id_by_name.return_value = "R3"
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(9)

    db.get_deployment.assert_called_once_with(deployment_id=9)
    kong.find_route_id_by_path.assert_not_called()      # api_path falsy → 경로조회 자체 skip
    kong.find_route_id_by_name.assert_called_once_with("ext-dep-9")
    kong.delete_route.assert_called_once_with("R3")


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_skips_route_delete_when_none_found(kong, db):
    """route 를 못 찾으면 delete_route 는 건너뛰되 크리덴셜/row 는 정리한다."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {}
    kong.find_route_id_by_name.return_value = None
    db.delete_deployment_api.return_value = {"result": True}

    deployment_api.teardown_deployment_api(9)

    kong.delete_route.assert_not_called()
    kong.delete_key_auths.assert_called_once_with("dep-9")
    kong.delete_consumer.assert_called_once_with("dep-9")
    db.delete_deployment_api.assert_called_once_with(9)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_partial_failure_key_auths_continues_then_raises(kong, db):
    """delete_key_auths 실패해도 나머지를 모두 시도하고 마지막에 aggregate-raise."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    kong.delete_key_auths.side_effect = Exception("boom")
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    kong.delete_consumer.assert_called_once_with("dep-7")
    kong.delete_route.assert_called_once_with("R1")
    db.delete_deployment_api.assert_called_once_with(7)
    assert "delete_key_auths" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_partial_failure_consumer_continues_then_raises(kong, db):
    """delete_consumer 실패에도 route/DB 삭제는 계속 시도되고 aggregate-raise."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    kong.delete_consumer.side_effect = Exception("boom")
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    kong.delete_key_auths.assert_called_once_with("dep-7")
    kong.delete_route.assert_called_once_with("R1")
    db.delete_deployment_api.assert_called_once_with(7)
    assert "delete_consumer" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_partial_failure_route_continues_then_raises(kong, db):
    """delete_route 실패에도 DB row 삭제는 계속 시도되고 aggregate-raise."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    kong.delete_route.side_effect = Exception("boom")
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    kong.delete_key_auths.assert_called_once_with("dep-7")
    kong.delete_consumer.assert_called_once_with("dep-7")
    db.delete_deployment_api.assert_called_once_with(7)
    assert "delete_route" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_aggregates_multiple_failures(kong, db):
    """여러 단계가 실패하면 각 실패를 모아 하나의 예외로 raise."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    kong.delete_key_auths.side_effect = Exception("k")
    kong.delete_route.side_effect = Exception("r")
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    msg = str(exc.value)
    assert "delete_key_auths" in msg
    assert "delete_route" in msg


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_raises_when_db_delete_raises(kong, db):
    """delete_deployment_api 가 예외를 던져도 잡아서 aggregate-raise."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    db.delete_deployment_api.side_effect = Exception("db exploded")

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    assert "delete_deployment_api" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_raises_when_db_delete_reports_failure(kong, db):
    """delete_deployment_api 가 {result:False} 면(예외 미발생) 명시적으로 실패 처리."""
    db.get_deployment_api.return_value = {"api_consumer": "dep-7", "api_route_id": "R1"}
    db.delete_deployment_api.return_value = {"result": False, "message": "db locked"}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(7)

    assert "delete_deployment_api" in str(exc.value)
    assert "db locked" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_continues_when_secondary_lookup_raises(kong, db):
    """2차 배포 조회가 예외여도 키 무효화(크리덴셜 삭제)는 진행한다."""
    db.get_deployment_api.return_value = None
    db.get_deployment.side_effect = Exception("db blip")
    kong.find_route_id_by_name.return_value = None
    db.delete_deployment_api.return_value = {"result": True}

    # 크래시 없이 완료(모든 삭제 성공 → raise 없음).
    deployment_api.teardown_deployment_api(9)

    kong.delete_key_auths.assert_called_once_with("dep-9")
    kong.delete_consumer.assert_called_once_with("dep-9")
    db.delete_deployment_api.assert_called_once_with(9)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_path_lookup_raises_falls_through_to_name(kong, db):
    """path 조회가 예외여도 name 폴백은 계속 시도(독립 try) — path 실패가 route 정리를 막지 않는다.

    또한 조회 예외가 크리덴셜 삭제 전에 함수를 이탈시키면 유효 키가 살아남는다 — 그 회귀도 막는다."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {"api_path": "abc"}
    kong.find_route_id_by_path.side_effect = Exception("kong 500")
    kong.find_route_id_by_name.return_value = "R3"      # name 폴백은 성공
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(9)

    kong.find_route_id_by_name.assert_called_once_with("ext-dep-9")
    kong.delete_route.assert_called_once_with("R3")     # name 으로 찾은 route 삭제됨
    kong.delete_key_auths.assert_called_once_with("dep-9")
    kong.delete_consumer.assert_called_once_with("dep-9")
    db.delete_deployment_api.assert_called_once_with(9)
    assert "find_route_by_path" in str(exc.value)


@patch("utils.deployment_api.db_deployment")
@patch("utils.deployment_api.kong_helper")
def test_teardown_both_route_lookups_raise_still_deletes_credentials(kong, db):
    """path·name 조회가 모두 예외여도 크리덴셜/row 삭제는 진행하고 두 오류를 모아 raise."""
    db.get_deployment_api.return_value = None
    db.get_deployment.return_value = {"api_path": "abc"}
    kong.find_route_id_by_path.side_effect = Exception("kong 500")
    kong.find_route_id_by_name.side_effect = Exception("kong 500")
    db.delete_deployment_api.return_value = {"result": True}

    with pytest.raises(Exception) as exc:
        deployment_api.teardown_deployment_api(9)

    kong.delete_key_auths.assert_called_once_with("dep-9")
    kong.delete_consumer.assert_called_once_with("dep-9")
    kong.delete_route.assert_not_called()               # route_id 미해결 → route 삭제 skip
    db.delete_deployment_api.assert_called_once_with(9)
    msg = str(exc.value)
    assert "find_route_by_path" in msg
    assert "find_route_by_name" in msg
