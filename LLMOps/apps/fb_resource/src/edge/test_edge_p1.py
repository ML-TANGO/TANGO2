"""SP-8 P1 회귀 테스트 (순수 로직 — 실 DB 불요, db_edge monkeypatch).

실행(fb_resource pod 내부, import 경로 정합):
    cd /app/src && python -m pytest edge/test_edge_p1.py -v
CI 러너는 없음 — 수동/라이브 검증 보완용. 프로젝트 검증 패턴(함수단위 + 클러스터 e2e)에 맞춤.
"""
import re
from datetime import datetime, timedelta

import pytest

from edge import model, edge_service
from utils.msa_db import db_edge


# ── model 검증 ────────────────────────────────────────────────────────────────

def test_register_requires_name():
    # device_id 는 서버 자동생성(입력 X), name 은 필수. location/sdx_domain/hw_model 제거됨.
    m = model.RegisterEdgeWorkerModel(
        name="부산항-오린-01", device_type="orin",
        remote_manager_url="http://192.168.0.9:8080")
    assert m.name == "부산항-오린-01"
    assert m.device_type == "orin"


def test_register_rejects_missing_name():
    with pytest.raises(Exception):
        model.RegisterEdgeWorkerModel(remote_manager_url="http://192.168.0.9:8080")


def test_heartbeat_clamps_pct():
    m = model.HeartbeatModel(cpu_pct=150, gpu_pct=-5)
    assert m.cpu_pct == 100.0
    assert m.gpu_pct == 0.0


def test_heartbeat_caps_last_error_length():
    with pytest.raises(Exception):
        model.HeartbeatModel(last_error="x" * 600)  # max_length=512


def test_heartbeat_rejects_out_of_range_numeric():
    # 음수 자원/지연은 거부(S4 — 나머지 수치 필드 bound).
    with pytest.raises(Exception):
        model.HeartbeatModel(disk_gb=-1)
    with pytest.raises(Exception):
        model.HeartbeatModel(inference_latency_p50_ms=-10)
    with pytest.raises(Exception):
        model.HeartbeatModel(inference_count_total=-1)


# ── 토큰 발급/검증 ────────────────────────────────────────────────────────────

def test_token_roundtrip_and_reject(monkeypatch):
    store = {"id": 1, "device_id": "orin-01"}
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda worker_id=None, device_id=None: store)

    def _save(worker_id, token_hash, token_prefix, token_expires_at):
        store.update(edge_token_hash=token_hash, token_prefix=token_prefix,
                     token_expires_at=token_expires_at)
        return True
    monkeypatch.setattr(db_edge, "update_edge_worker_token", _save)

    issued = edge_service.issue_device_token(1)
    tok = issued["token"]
    assert len(tok) >= 20 and issued["token_prefix"] == tok[:8]
    assert edge_service.verify_device_token("orin-01", tok) is True
    assert edge_service.verify_device_token("orin-01", "wrong-token") is False
    assert edge_service.verify_device_token("orin-01", "") is False


def test_token_expired_rejected(monkeypatch):
    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    store = {"id": 1, "device_id": "orin-01",
             "edge_token_hash": edge_service._hash_token("t"),
             "token_expires_at": past}
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda worker_id=None, device_id=None: store)
    assert edge_service.verify_device_token("orin-01", "t") is False


def test_token_unparseable_expiry_fails_closed(monkeypatch):
    # S6 — 만료값이 있으나 파싱 불가 → 만료로 간주(fail-closed).
    store = {"id": 1, "device_id": "orin-01",
             "edge_token_hash": edge_service._hash_token("t"),
             "token_expires_at": "not-a-date"}
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda worker_id=None, device_id=None: store)
    assert edge_service.verify_device_token("orin-01", "t") is False


# ── offline-on-read 파생 ──────────────────────────────────────────────────────

def test_derive_conn_status_stale_is_offline():
    fresh = {"last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    stale = {"last_seen": (datetime.now() - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M:%S")}
    assert edge_service._derive_conn_status(fresh) == "online"
    assert edge_service._derive_conn_status(stale) == "offline"
    assert edge_service._derive_conn_status({"last_seen": None}) == "offline"


def test_worker_view_offline_derivation_is_token_gated(monkeypatch):
    # I1 — heartbeat 워커(토큰有)만 파생, pull 전용(토큰無)은 저장 conn_status 유지.
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    stale = (datetime.now() - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M:%S")

    hb_worker = {"id": 1, "device_id": "hb", "conn_status": "online",
                 "last_seen": stale, "edge_token_hash": "abc", "token_prefix": "abc"}
    pull_worker = {"id": 2, "device_id": "pull", "conn_status": "online",
                   "last_seen": stale, "edge_token_hash": None, "token_prefix": None}

    hb_view = edge_service._worker_view(hb_worker)
    pull_view = edge_service._worker_view(pull_worker)

    assert hb_view["conn_status"] == "offline"       # 토큰 워커 stale → 파생 offline
    assert pull_view["conn_status"] == "online"      # pull 워커 → 저장값 유지(회귀 차단)
    # 인증 해시는 응답에서 제거(S1).
    assert "edge_token_hash" not in hb_view
    assert "edge_token_hash" not in pull_view


# ── db_edge SQL 파라미터 자리수 정합 ──────────────────────────────────────────

def test_insert_edge_worker_param_arity(monkeypatch):
    captured = {}

    class _Cur:
        lastrowid = 1

        def execute(self, sql, params):
            captured["sql"], captured["params"] = sql, params

    class _Conn:
        def cursor(self):
            return _Cur()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(db_edge, "get_db", lambda: _Conn())
    db_edge.insert_edge_worker("edge-a1b2c3d4", "n", "orin", "http://192.168.0.9:8080")
    assert len(re.findall(r"%s", captured["sql"])) == len(captured["params"]) == 4


# ── 2026-09-11 엣지 배포 표면 변경 회귀 테스트 ────────────────────────────────
# 3-way 리뷰(기능·보안·codex)가 잡은 P1 3건 + P2 2건에 대응. 전부 순수 로직 +
# db_edge monkeypatch 로, 위 기존 테스트와 같은 규율을 따른다(실 DB·실 디바이스 불요).


def test_stop_outcome_rejects_device_error():
    """디바이스가 {"status":"error"} 를 주면 성공으로 세지 않는다.

    _remote_ops 는 200/201/202 를 전부 통과시키므로 `result is not None` 만으로
    판정하면, docker 권한·daemon 오류로 컨테이너가 살아 있는데 플랫폼이 'stopped'
    라 말하는 조용한 거짓이 된다(실 agent 는 error 를 네 경로에서 반환).
    """
    ok, reason = edge_service._stop_outcome(
        {"status": "error", "detail": "docker not available on device"}, 200, None)
    assert ok is False
    assert "docker not available" in reason


def test_stop_outcome_does_not_assume_202():
    """202(비확정)를 stopped 로 단정하지 않는다 — 실상태는 다음 /metrics 가 확정."""
    ok, reason = edge_service._stop_outcome({"status": "accepted"}, 202, None)
    assert ok is False
    assert "not confirmed" in reason


def test_stop_outcome_accepts_stopped_and_bare_200():
    """status=stopped 는 성공. status 가 **아예 없을 때만** HTTP 코드로 판정한다."""
    ok, _ = edge_service._stop_outcome({"status": "stopped"}, 200, None)
    assert ok is True
    ok, _ = edge_service._stop_outcome({}, 200, None)
    assert ok is True


def test_stop_outcome_rejects_explicit_running():
    """{"status":"running"} 은 '아직 돌고 있다' 는 뜻이다 — HTTP 200 이라고 중지로
    뒤집으면 컨테이너가 살아 있는데 화면이 '중지됨' 이라 말한다."""
    ok, reason = edge_service._stop_outcome({"status": "running"}, 200, None)
    assert ok is False and "running" in reason


def test_stop_outcome_rejects_non_dict_response():
    """dict 가 아닌 JSON 응답에서 AttributeError 를 던지면 안 된다.

    delete 경로에서는 그 예외가 DB 삭제 **전에** 터져 삭제 자체를 실패시킨다 —
    "결과와 무관하게 삭제는 진행한다" 는 delete_edge_worker 의 약속을 깬다.
    """
    for bad in ([1, 2, 3], "ok", 7):
        ok, reason = edge_service._stop_outcome(bad, 200, None)
        assert ok is False and "unexpected" in reason


def test_stop_outcome_sanitizes_device_detail():
    """detail 은 기관 통제 밖 장비가 준 문자열이다 — 절단 + 제어문자 제거."""
    ok, reason = edge_service._stop_outcome(
        {"status": "error", "detail": "a\nb\r\n" + "X" * 500}, 200, None)
    assert ok is False
    assert "\n" not in reason and "\r" not in reason
    assert len(reason) < 300


def test_stop_outcome_propagates_unreachable():
    ok, reason = edge_service._stop_outcome(None, 0, "remoteManager unreachable")
    assert ok is False and reason == "remoteManager unreachable"


def test_heartbeat_throttle_keyed_on_heartbeat_column_not_last_seen(monkeypatch):
    """throttle 기준은 last_heartbeat_at 이다.

    last_seen 은 등록·refresh(/metrics 폴링)·deploy 도 갱신하는 '생존 증거'라,
    그 값에 30초 게이트를 걸면 UI 새로고침 한 번이 규약을 지킨 디바이스의 다음
    heartbeat 를 429 로 튕긴다. last_seen 이 방금 갱신됐어도 heartbeat 는 통과해야 한다.
    """
    now = datetime.now()
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "last_seen": now.strftime("%Y-%m-%d %H:%M:%S"),          # refresh 가 막 갱신
        "last_heartbeat_at": (now - timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_json": "{}",
    })
    monkeypatch.setattr(db_edge, "update_edge_worker_heartbeat",
                        lambda *a, **kw: True)
    body = model.HeartbeatModel(timestamp="2026-09-11T00:00:00", cpu_pct=1.0)
    assert edge_service.record_heartbeat("edge-a1b2c3d4", body)["received"] is True


def test_heartbeat_throttles_on_recent_heartbeat(monkeypatch):
    """반대로 last_heartbeat_at 이 30초 내면 여전히 throttle 된다(규약 유지)."""
    now = datetime.now()
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "last_seen": (now - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_at": (now - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_json": "{}",
    })
    body = model.HeartbeatModel(timestamp="2026-09-11T00:00:00", cpu_pct=1.0)
    with pytest.raises(edge_service.HeartbeatThrottled):
        edge_service.record_heartbeat("edge-a1b2c3d4", body)


def test_heartbeat_first_ever_is_not_throttled(monkeypatch):
    """컬럼이 NULL(첫 heartbeat·구 데이터)이면 throttle 하지 않는다."""
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_at": None, "last_heartbeat_json": None,
    })
    monkeypatch.setattr(db_edge, "update_edge_worker_heartbeat", lambda *a, **kw: True)
    body = model.HeartbeatModel(timestamp="2026-09-11T00:00:00", cpu_pct=1.0)
    assert edge_service.record_heartbeat("edge-a1b2c3d4", body)["received"] is True


def test_refresh_clears_deploy_fields_with_empty_sentinel(monkeypatch):
    """컨테이너 0건을 관측하면 모델·버전을 "" 로 비운다.

    db_edge 는 None 필드를 skip 하므로 그냥 넘기면 deploy_state 만 stopped 가 되고
    옛 모델명이 화석으로 남아 화면이 "그 모델이 죽었다" 는 거짓을 말한다.
    """
    captured = {}
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_model": "qwen", "deploy_version": "q4", "deploy_state": "running",
    })
    # _poll_remote_manager 는 튜플이 아니라 metrics dict 하나를 반환한다(실패 시 None).
    monkeypatch.setattr(edge_service, "_poll_remote_manager",
                        lambda url: {"containers": [], "container_count": 0,
                                     "node_cpu_total": 8, "memory_total": 16})

    def _upd(worker_id, **kw):
        captured.update(kw)
        return True

    monkeypatch.setattr(db_edge, "update_edge_worker_status", _upd)
    monkeypatch.setattr(edge_service, "_worker_view", lambda w: w)
    edge_service.refresh_edge_worker(1)
    assert captured["deploy_state"] == "stopped"
    assert captured["deploy_model"] == "" and captured["deploy_version"] == ""


def test_delete_attempts_stop_for_deploying_state(monkeypatch):
    """deploying 도 stop 대상이다.

    deploy 가 202(async)를 받으면 그 상태로 남는데, running 만 보면 그때 삭제한
    워커의 컨테이너가 이후 기동돼 유령으로 남고 attempted=false 라 UI 경고도 없다.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_state": "deploying", "last_seen": now,
        "edge_token_hash": "x", "last_heartbeat_json": "{}",
    })
    sent = {}

    def _ops(url, payload):
        sent["payload"] = payload
        return {"status": "stopped"}, 200, None

    monkeypatch.setattr(edge_service, "_remote_ops", _ops)
    monkeypatch.setattr(db_edge, "delete_edge_worker", lambda wid: True)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    res = edge_service.delete_edge_worker(1)
    assert sent["payload"] == {"op": "stop"}
    assert res["stop"]["attempted"] is True and res["stop"]["ok"] is True


def test_delete_skips_stop_when_offline(monkeypatch):
    """offline 디바이스에는 stop 을 보내지 않는다 — 도달 못 하는데 getaddrinfo(앱
    타임아웃 없음) + HTTP 5s 만큼 삭제가 묶인다. 엣지는 전원 꺼짐이 정상 상태다."""
    stale = (datetime.now() - timedelta(seconds=9999)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_state": "running", "last_seen": stale,
        "edge_token_hash": "x", "last_heartbeat_json": "{}",
    })

    def _boom(url, payload):
        raise AssertionError("offline 디바이스에 stop 을 보내면 안 된다")

    monkeypatch.setattr(edge_service, "_remote_ops", _boom)
    monkeypatch.setattr(db_edge, "delete_edge_worker", lambda wid: True)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    res = edge_service.delete_edge_worker(1)
    assert res["stop"]["attempted"] is False and res["deleted"] == 1


def test_delete_does_not_mask_db_failure(monkeypatch):
    """DB 삭제 실패를 성공으로 위장하지 않는다 — 컨테이너는 내렸는데 행이 남으면
    화면에는 배포가 계속 살아 있는 것으로 보인다."""
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": None, "deploy_state": "stopped",
    })
    monkeypatch.setattr(db_edge, "delete_edge_worker", lambda wid: False)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    with pytest.raises(Exception, match="failed to delete edge worker"):
        edge_service.delete_edge_worker(1)


def test_stop_requires_remote_manager_url(monkeypatch):
    """heartbeat-only 디바이스(URL NULL 허용)는 /ops 방향이 없어 중지가 불가능하다.
    online 이어도 그렇다 — online 은 heartbeat(디바이스→플랫폼) 판정이다."""
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4", "remote_manager_url": None,
        "conn_status": "online", "deploy_state": "running",
    })
    with pytest.raises(Exception, match="heartbeat-only"):
        edge_service.stop_edge_worker(1)


def test_delete_attempts_stop_for_pull_only_worker_with_stale_last_seen(monkeypatch):
    """pull-only 워커(토큰 없음)는 last_seen 이 오래돼도 stop 을 시도해야 한다.

    last_seen 은 토큰 워커에서만 디바이스 push 기반이라 liveness 로 유효하다.
    pull-only 워커에서는 "우리가 마지막에 폴링한 시각" 일 뿐이고 주기 폴러가 없어
    자연 소멸한다 — 그 값으로 건너뛰면 도달 가능한 디바이스의 컨테이너가 유령으로
    남는다. 이 케이스가 앞선 테스트 묶음에 없어서 회귀가 드러나지 않았다.
    """
    stale = (datetime.now() - timedelta(seconds=9999)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_state": "running", "last_seen": stale,
        "edge_token_hash": None,          # ← pull-only
        "last_heartbeat_json": None,
    })
    sent = {}

    def _ops(url, payload):
        sent["payload"] = payload
        return {"status": "stopped"}, 200, None

    monkeypatch.setattr(edge_service, "_remote_ops", _ops)
    monkeypatch.setattr(db_edge, "delete_edge_worker", lambda wid: True)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    res = edge_service.delete_edge_worker(1)
    assert sent.get("payload") == {"op": "stop"}
    assert res["stop"]["attempted"] is True and res["stop"]["ok"] is True


def test_delete_attempts_stop_for_error_state(monkeypatch):
    """error 상태도 stop 대상 — deploy 실패는 컨테이너 부재를 보장하지 않는다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_state": "error", "last_seen": now,
        "edge_token_hash": "x", "last_heartbeat_json": "{}",
    })
    sent = {}

    def _ops(url, payload):
        sent["payload"] = payload
        return {"status": "stopped"}, 200, None

    monkeypatch.setattr(edge_service, "_remote_ops", _ops)
    monkeypatch.setattr(db_edge, "delete_edge_worker", lambda wid: True)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    res = edge_service.delete_edge_worker(1)
    assert sent.get("payload") == {"op": "stop"}
    assert res["stop"]["attempted"] is True and res["stop"]["ok"] is True


def test_delete_proceeds_even_if_stop_raises(monkeypatch):
    """best-effort stop 이 예외를 던져도 삭제는 진행된다(함수가 약속한 불변식)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": "http://192.168.0.9:8080",
        "deploy_state": "running", "last_seen": now,
        "edge_token_hash": "x", "last_heartbeat_json": "{}",
    })

    def _boom(url, payload):
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(edge_service, "_remote_ops", _boom)
    deleted = {}
    monkeypatch.setattr(db_edge, "delete_edge_worker",
                        lambda wid: deleted.setdefault("id", wid) or True)
    monkeypatch.setattr(db_edge, "delete_custom_labels_for", lambda *a: True)
    res = edge_service.delete_edge_worker(1)
    assert deleted.get("id") == 1                      # 삭제가 실제로 일어났다
    assert res["stop"]["attempted"] is True and res["stop"]["ok"] is False
    assert "RuntimeError" in res["stop"]["reason"]


def test_ensure_schema_reports_failure_separately(monkeypatch):
    """스키마 보정 실패를 성공과 구분해 반환한다.

    이전 판본은 실패 시 빈 목록을 돌려줘 호출자가 "이미 컬럼이 있어 할 일 없음" 과
    구분할 수 없었고, 그래서 일시적 실패가 INFO 로 묻힌 채 컬럼 없는 서비스가 계속
    살아 heartbeat 가 전건 실패할 수 있었다.
    """
    def _boom():
        raise RuntimeError("access denied for ALTER")

    monkeypatch.setattr(db_edge, "get_db", _boom)
    res = db_edge.ensure_edge_worker_schema()
    assert res["applied"] == []
    assert len(res["failed"]) == 1
    assert res["failed"][0]["column"] == "last_heartbeat_at"
    assert "RuntimeError" in res["failed"][0]["error"]
