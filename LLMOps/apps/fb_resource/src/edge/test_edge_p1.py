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
    # 컬럼 목록이 늘어도 의도는 같다 — 실패는 **컬럼별로 개별 보고**되고 삼켜지지 않는다.
    # 개수에 결합하면 컬럼이 추가될 때마다 의미 없이 깨진다(2026-09-16 deploy_observed_at).
    failed_cols = {f["column"] for f in res["failed"]}
    assert {"last_heartbeat_at", "deploy_observed_at"} <= failed_cols
    assert all("RuntimeError" in f["error"] for f in res["failed"])


# ── 2026-09-16 오프라인 신선도 + heartbeat 대사 회귀 테스트 ───────────────────

def test_worker_view_marks_stale_without_flipping_conn_status(monkeypatch):
    """끊긴 pull-only 워커는 conn_status 를 유지하되 신선도 필드로 사실을 알린다.

    conn_status 를 뒤집으면 canOperate(= isOnline && hasRemoteUrl)가 도달 가능한
    디바이스의 배포 버튼까지 막는다(위 token-gated 테스트가 지키는 회귀). 그렇다고
    끊긴 디바이스를 영구히 online + running 으로 두면 화면이 거짓을 말한다. 두 요구를
    분리하는 것이 이 필드의 목적이므로, 둘을 한 테스트에서 함께 고정한다.
    """
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    stale = (datetime.now() - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M:%S")
    view = edge_service._worker_view(
        {"id": 2, "device_id": "pull", "conn_status": "online", "last_seen": stale,
         "deploy_observed_at": stale, "deploy_state": "running",
         "edge_token_hash": None})
    assert view["conn_status"] == "online"   # 조작 게이트 입력 불변
    assert view["contact_stale"] is True     # 그러나 관측은 오래됐다고 알린다
    assert view["deploy_stale"] is True
    assert view["deploy_state"] == "running"  # 원본 보존(축약은 화면 몫)


def test_worker_view_fresh_observation_is_not_stale(monkeypatch):
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    fresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    view = edge_service._worker_view(
        {"id": 3, "device_id": "fresh", "conn_status": "online", "last_seen": fresh,
         "deploy_observed_at": fresh, "edge_token_hash": None})
    assert view["contact_stale"] is False
    assert view["deploy_stale"] is False


def test_worker_view_never_observed_is_stale(monkeypatch):
    """last_seen 이 없으면 '관측된 적 없음' → stale. 등록만 하고 한 번도 안 붙은 디바이스."""
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    view = edge_service._worker_view(
        {"id": 4, "device_id": "never", "conn_status": "offline", "last_seen": None,
         "deploy_observed_at": None, "edge_token_hash": None})
    assert view["contact_stale"] is True
    assert view["deploy_stale"] is True


def _capture_heartbeat(monkeypatch, model_loaded, remote_manager_url=None):
    """heartbeat 1회 기록 후 DAL 에 전달된 kwargs 를 돌려준다.

    remote_manager_url 기본 None = heartbeat-only 워커(대사 대상). 값을 주면
    remoteManager 를 함께 쓰는 워커가 되어 대사가 꺼져야 한다.
    """
    now = datetime.now()
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-a1b2c3d4",
        "remote_manager_url": remote_manager_url,
        "last_seen": (now - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_at": (now - timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat_json": "{}",
    })
    seen = {}

    def _fake(worker_id, **kw):
        seen.update(kw)
        seen["worker_id"] = worker_id
        return True

    monkeypatch.setattr(db_edge, "update_edge_worker_heartbeat", _fake)
    body = model.HeartbeatModel(timestamp="2026-09-16T00:00:00", cpu_pct=1.0,
                                model_loaded=model_loaded)
    assert edge_service.record_heartbeat("edge-a1b2c3d4", body)["received"] is True
    return seen


def test_heartbeat_reconciles_reported_model(monkeypatch):
    """디바이스가 보고한 model_loaded 가 배포 레코드에 반영된다.

    무엇이 올라가 있는지는 디바이스가 진실의 원천이다. 이전에는 이 값이
    last_heartbeat_json 안에만 묻혀, 현장에서 직접 교체한 모델이 화면에 영원히
    반영되지 않았다.
    """
    seen = _capture_heartbeat(monkeypatch, "qwen-edge-q4")
    assert seen["deploy_model"] == "qwen-edge-q4"


def test_heartbeat_empty_model_loaded_does_not_clear_deploy_model(monkeypatch):
    """빈 보고는 '배포 없음' 이 아니라 '정보 없음' 이다 → 컬럼을 건드리지 않는다.

    레퍼런스 에이전트의 _last_deploy 는 in-memory 라, 컨테이너가
    --restart unless-stopped 로 살아 있어도 에이전트만 재시작되면 "" 가 온다.
    그걸 반영하면 살아 있는 배포를 죽었다고 기록한다(DAL 은 None 을 skip).
    """
    assert _capture_heartbeat(monkeypatch, "")["deploy_model"] is None
    assert _capture_heartbeat(monkeypatch, None)["deploy_model"] is None


def test_heartbeat_does_not_touch_deploy_state(monkeypatch):
    """model_loaded 는 에이전트의 기억일 뿐 컨테이너 라이브 증거가 아니다.

    deploy_state 확정은 docker ps 를 실제로 보는 /refresh(/metrics) 몫이다.
    heartbeat 가 running 을 새기면 죽은 컨테이너를 살아 있다고 말하게 된다.
    """
    seen = _capture_heartbeat(monkeypatch, "qwen-edge-q4")
    assert "deploy_state" not in seen


def test_update_heartbeat_param_arity_with_and_without_model(monkeypatch):
    """heartbeat UPDATE 는 SET 절이 조건부로 늘어난다 → 자리수/파라미터 정합 고정.

    deploy_model 이 붙고 안 붙고에 따라 %s 개수가 달라지므로, 한쪽만 맞춰두면
    다른 경로가 런타임에 깨진다(pymysql 은 자리수 불일치를 실행 시점에야 알린다).
    """
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

    # deploy_model 없음 → last_seen, last_heartbeat_at, last_heartbeat_json, id = 4
    db_edge.update_edge_worker_heartbeat(1, last_heartbeat_json="{}", last_seen="t")
    assert len(re.findall(r"%s", captured["sql"])) == len(captured["params"]) == 4
    assert "deploy_model" not in captured["sql"]

    # deploy_model 있음 → 5
    db_edge.update_edge_worker_heartbeat(1, last_heartbeat_json="{}", last_seen="t",
                                         deploy_model="m")
    assert len(re.findall(r"%s", captured["sql"])) == len(captured["params"]) == 5
    assert "deploy_model=%s" in captured["sql"]
    # worker_id 는 항상 마지막 파라미터(WHERE id=%s).
    assert captured["params"][-1] == 1


def test_heartbeat_does_not_reconcile_when_remote_manager_exists(monkeypatch):
    """remoteManager 를 함께 쓰는 워커는 heartbeat 로 deploy_model 을 쓰지 않는다.

    그 워커에서는 /ops·/metrics 가 같은 컬럼의 권위 writer 이고 heartbeat 는 독립
    채널이라 도착 순서가 보장되지 않는다. stop 직후 도착한 in-flight heartbeat 가
    방금 비운 값을 되살리면, 이후 heartbeat 는 빈 값만 보내고 빈 값은 무시되므로
    잘못된 모델명이 다음 /refresh 까지 영구히 남는다. 게다가 레퍼런스 에이전트의
    model_loaded 는 /ops deploy 에서만 채워져 플랫폼이 배포한 값의 메아리라,
    대사해도 얻는 정보가 없다 — 위험만 있고 이득이 없는 조합이라 끈다.
    """
    seen = _capture_heartbeat(monkeypatch, "modelA",
                              remote_manager_url="http://192.168.0.9:8600")
    assert seen["deploy_model"] is None      # 컬럼 미변경
    assert "deploy_state" not in seen        # 여전히 미접촉


def test_heartbeat_sanitizes_reported_model(monkeypatch):
    """디바이스 제공 문자열은 _sanitize 규율을 따른다(제어문자·개행 제거).

    이 값은 이제 last_heartbeat_json blob 밖의 1급 컬럼이라 화면·envelope·로그로
    퍼진다. 개행이 남으면 로그에 가짜 다중 라인을 주입할 수 있다(CWE-117).
    """
    seen = _capture_heartbeat(monkeypatch, "qwen\r\n[FAKE] admin override\tX")
    assert "\n" not in seen["deploy_model"]
    assert "\r" not in seen["deploy_model"]
    assert "\t" not in seen["deploy_model"]
    assert seen["deploy_model"].startswith("qwen")


# ── 2026-09-16 배포상태 신선도 축 분리(codex 교차리뷰 HIGH) ────────────────────

def test_deploy_stale_is_independent_of_contact_freshness(monkeypatch):
    """연결은 신선한데 배포상태는 옛 관측인 상태를 화면이 구분할 수 있어야 한다.

    이것이 두 축을 나눈 이유다. heartbeat 는 last_seen 을 올리지만 컨테이너를 보지
    않는다(/metrics 만 docker ps 를 본다). 그래서 컨테이너가 죽었는데 에이전트만
    살아 heartbeat 를 보내는 디바이스는 '연결 신선 + 배포상태 옛 관측' 이 된다.
    한 축(last_seen)만 쓰면 이 디바이스가 계속 신선한 'running' 으로 보인다.
    """
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    now = datetime.now()
    view = edge_service._worker_view({
        "id": 5, "device_id": "hb", "conn_status": "online",
        "last_seen": now.strftime("%Y-%m-%d %H:%M:%S"),                       # heartbeat 가 방금 갱신
        "deploy_observed_at": (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
        "deploy_state": "running", "edge_token_hash": "abc",
    })
    assert view["conn_status"] == "online"
    assert view["contact_stale"] is False    # 연결은 살아 있다
    assert view["deploy_stale"] is True      # 그러나 배포상태는 옛 관측이다


def _capture_status(monkeypatch):
    """update_edge_worker_status 에 전달된 kwargs 를 포착한다."""
    seen = {}

    def _fake(worker_id, conn_status, **kw):
        seen.update(kw)
        seen["conn_status"] = conn_status
        return True

    monkeypatch.setattr(db_edge, "update_edge_worker_status", _fake)
    return seen


def test_refresh_records_deploy_observation(monkeypatch):
    """/metrics 폴링이 성공하면 배포상태를 관측한 것 → deploy_observed_at 갱신."""
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda **kw: {"id": 1, "device_id": "d",
                                      "remote_manager_url": "http://192.168.0.9:8600"})
    monkeypatch.setattr(edge_service, "_poll_remote_manager", lambda url: {
        "containers": [{"name": "c", "image": "i", "state": "running",
                        "model": "m", "version": "1"}],
        "container_count": 1, "node_cpu_total": 8, "memory_total": 16, "gpu": "none"})
    monkeypatch.setattr(edge_service, "_worker_view", lambda w: w)
    seen = _capture_status(monkeypatch)
    edge_service.refresh_edge_worker(1)
    assert seen.get("deploy_observed_at")     # 관측했다
    assert seen["deploy_state"] == "running"


def test_failed_poll_does_not_record_deploy_observation(monkeypatch):
    """폴링 실패(offline 표시)는 아무것도 관측하지 못한 것 → 신선도를 올리면 안 된다.

    여기서 갱신하면 도달 불가 디바이스의 옛 deploy_state 가 영원히 '신선' 해진다.
    """
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda **kw: {"id": 1, "device_id": "d",
                                      "remote_manager_url": "http://192.168.0.9:8600"})
    monkeypatch.setattr(edge_service, "_poll_remote_manager", lambda url: None)
    monkeypatch.setattr(edge_service, "_worker_view", lambda w: w)
    seen = _capture_status(monkeypatch)
    edge_service.refresh_edge_worker(1)
    assert seen["conn_status"] == "offline"
    assert "deploy_observed_at" not in seen


def test_heartbeat_only_reconcile_records_observation(monkeypatch):
    """heartbeat-only 워커에서는 model 보고가 유일한 배포 관측이다."""
    seen = _capture_heartbeat(monkeypatch, "qwen-edge-q4")
    assert seen["deploy_model"] == "qwen-edge-q4"
    assert seen.get("deploy_observed_at")


def test_heartbeat_without_model_records_no_observation(monkeypatch):
    """대사하지 않는 heartbeat 는 관측이 아니다 — 신선도를 올리지 않는다."""
    assert _capture_heartbeat(monkeypatch, "")["deploy_observed_at"] is None
    assert _capture_heartbeat(
        monkeypatch, "modelA",
        remote_manager_url="http://192.168.0.9:8600")["deploy_observed_at"] is None


# ── 계약 v1: 아티팩트 전달 / ops 토큰 / 비동기 배포 ──────────────────────────
# 이 절의 배경: 계약에 모델 파일을 장비로 옮기는 경로가 없어서, 규약대로 구현해도
# 모델 없는 컨테이너가 떴다. 그 구멍을 메우며 들어온 것이 아래 세 가지다 —
# (1) lineage_id 로 서버가 경로를 해석해 발급하는 model_url,
# (2) 플랫폼이 자신을 증명하는 ops 토큰,
# (3) 수 GB 수신을 위한 202 비동기 배포와 그 진행/실패 신호.

def test_public_base_prefers_explicit_override(monkeypatch):
    monkeypatch.setenv("PLATFORM_PUBLIC_BASE", "https://edge.example.com/")
    monkeypatch.setenv("EXTERNAL_HOST", "10.0.0.1")
    assert edge_service._platform_public_base() == "https://edge.example.com"


def test_public_base_derives_from_gateway_env(monkeypatch):
    """게이트웨이 주소를 새 값으로 중복 정의하지 않는다 — 어긋나면 디바이스가 못 온다."""
    monkeypatch.delenv("PLATFORM_PUBLIC_BASE", raising=False)
    monkeypatch.setenv("INGRESS_PROTOCOL", "http")
    monkeypatch.setenv("EXTERNAL_HOST", "10.0.0.1")
    monkeypatch.setenv("EXTERNAL_HOST_PORT", "31080")
    assert edge_service._platform_public_base() == "http://10.0.0.1:31080"


def test_public_base_omits_default_ports(monkeypatch):
    monkeypatch.delenv("PLATFORM_PUBLIC_BASE", raising=False)
    monkeypatch.setenv("INGRESS_PROTOCOL", "https")
    monkeypatch.setenv("EXTERNAL_HOST", "edge.example.com")
    monkeypatch.setenv("EXTERNAL_HOST_PORT", "443")
    assert edge_service._platform_public_base() == "https://edge.example.com"


def test_artifact_url_none_without_public_base(monkeypatch):
    """주소를 모르면 URL 을 지어내지 않는다 — 디바이스가 못 가는 곳을 주면 배포가 죽는다."""
    monkeypatch.delenv("PLATFORM_PUBLIC_BASE", raising=False)
    monkeypatch.delenv("EXTERNAL_HOST", raising=False)
    assert edge_service._artifact_url("edge-1") is None


def _artifact_fixture(monkeypatch, tmp_path, rel="jobs/j1/output/m.gguf",
                      status="completed", create=True):
    monkeypatch.setattr(edge_service.PATH, "JF_MAIN_STORAGE_PATH",
                        str(tmp_path) + "/{STORAGE_NAME}/main/{WORKSPACE_NAME}")
    target = tmp_path / "st" / "main" / "ws" / rel
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"gguf" * 4)
    monkeypatch.setattr(db_edge, "get_quantize_lineage", lambda lid: {
        "id": lid, "workspace_id": 2, "gguf_path": rel, "status": status})
    monkeypatch.setattr(edge_service.db_workspace, "get_workspace",
                        lambda workspace_id=None: {"name": "ws", "main_storage_name": "st"})
    return target


def test_resolve_artifact_returns_absolute_path(monkeypatch, tmp_path):
    target = _artifact_fixture(monkeypatch, tmp_path)
    assert edge_service._resolve_artifact(7) == str(target.resolve())


def test_resolve_artifact_rejects_incomplete_lineage(monkeypatch, tmp_path):
    """완료되지 않은 양자화를 배포하면 반쪽 파일이 장비로 간다."""
    _artifact_fixture(monkeypatch, tmp_path, status="running")
    with pytest.raises(edge_service.ArtifactUnavailable) as ei:
        edge_service._resolve_artifact(7)
    assert str(ei.value) == "artifact unavailable"     # 사유를 클라이언트에 구분해 주지 않는다
    assert "running" in ei.value.detail                # 상세는 서버 로그용으로만 보존


def test_resolve_artifact_rejects_path_escaping_jobs_base(monkeypatch, tmp_path):
    """경로는 DB 값이지만 가드를 겹쳐 둔다 — DB 가 오염되면 임의 파일이 새 나간다."""
    _artifact_fixture(monkeypatch, tmp_path, rel="../../outside.gguf")
    with pytest.raises(edge_service.ArtifactUnavailable) as ei:
        edge_service._resolve_artifact(7)
    assert ei.value.detail == "path escapes jobs base"


def test_resolve_artifact_error_never_leaks_absolute_path(monkeypatch, tmp_path):
    """사유는 device-facing 응답으로 나간다 — 우리 NFS 레이아웃이 새면 안 된다."""
    _artifact_fixture(monkeypatch, tmp_path, create=False)
    with pytest.raises(Exception) as ei:
        edge_service._resolve_artifact(7)
    assert str(tmp_path) not in str(ei.value)
    assert "/jf-data" not in str(ei.value)


def test_device_artifact_requires_valid_token(monkeypatch):
    monkeypatch.setattr(edge_service, "verify_device_token", lambda d, t: False)
    path, code, err = edge_service.resolve_device_artifact("edge-1", "nope")
    assert (path, code) == (None, 401) and "token" in err


def test_device_artifact_404_when_nothing_authorized(monkeypatch):
    """배포 지시를 받은 적 없는 디바이스는 아무 파일도 받아갈 수 없다."""
    monkeypatch.setattr(edge_service, "verify_device_token", lambda d, t: True)
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda **kw: {"id": 1, "device_id": "edge-1", "deploy_lineage_id": None})
    path, code, err = edge_service.resolve_device_artifact("edge-1", "ok")
    assert (path, code) == (None, 404) and "authorized" in err


def test_device_artifact_serves_only_the_authorized_lineage(monkeypatch, tmp_path):
    target = _artifact_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(edge_service, "verify_device_token", lambda d, t: True)
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda **kw: {"id": 1, "device_id": "edge-1", "deploy_lineage_id": 7})
    path, code, err = edge_service.resolve_device_artifact("edge-1", "ok")
    assert (path, code, err) == (str(target.resolve()), 200, None)


def test_ops_headers_omitted_without_token(monkeypatch):
    """토큰 없는 설치에 헤더를 붙이면 구버전 에이전트와의 호환이 깨진다."""
    monkeypatch.delenv("EDGE_OPS_TOKEN", raising=False)
    assert edge_service._ops_headers() == {}


def test_ops_headers_included_with_token(monkeypatch):
    monkeypatch.setenv("EDGE_OPS_TOKEN", "s3cret")
    assert edge_service._ops_headers() == {"Authorization": "Bearer s3cret"}


def _deploy_capture(monkeypatch, tmp_path, ops_result=None):
    _artifact_fixture(monkeypatch, tmp_path)
    monkeypatch.setenv("PLATFORM_PUBLIC_BASE", "http://plat:31080")
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "edge-1", "remote_manager_url": "http://dev:8600",
        "deploy_lineage_id": 99})                      # 직전 배포의 인가
    order = []
    sent = {}

    def _ops(url, payload):
        sent.update(payload)
        order.append("ops")
        return ops_result if ops_result is not None else ({"status": "deploying"}, 202, None)
    monkeypatch.setattr(edge_service, "_remote_ops", _ops)
    grants = []

    def _grant(wid, lineage_id):
        grants.append(lineage_id)
        order.append("grant")
        return True
    monkeypatch.setattr(db_edge, "update_edge_worker_lineage", _grant)
    persisted = {}
    monkeypatch.setattr(db_edge, "update_edge_worker_status",
                        lambda wid, **kw: persisted.update(kw) or True)
    # 계약 v1 을 보고하는 에이전트가 기본값 — 개별 테스트가 필요하면 덮어쓴다.
    monkeypatch.setattr(edge_service, "_poll_remote_manager",
                        lambda url: {"contract_version": "1.0"})
    return sent, persisted, grants, order


def test_deploy_issues_model_url_and_lineage_scoped_name(monkeypatch, tmp_path):
    """파일명을 lineage 에 묶는다 — 같은 basename+같은 크기의 재양자화가 옛 가중치로
    스킵되는 것을 이름 단계에서 원천 차단한다."""
    sent, _persisted, grants, _order = _deploy_capture(monkeypatch, tmp_path)
    body = model.DeployEdgeModel(image="img:1", model_name="qwen",
                                 model_version="q4", lineage_id=7)
    res = edge_service.deploy_edge_worker(1, body)
    assert sent["model_url"] == "http://plat:31080/api/edge/devices/edge-1/artifact"
    assert sent["gguf_path"] == "lineage-7-m.gguf"
    assert res["deploy_state"] == "deploying"      # 202 → 확정하지 않는다
    assert grants == [7]


def test_deploy_persists_grant_before_dispatching_ops(monkeypatch, tmp_path):
    """에이전트는 202 직후 곧바로 받으러 온다. 인가가 뒤에 저장되면 그 콜백이 404 를
    받거나 — 더 나쁘게 — **직전 배포의 인가를 보고 옛 모델을 받아간다**."""
    _sent, _persisted, grants, order = _deploy_capture(monkeypatch, tmp_path)
    edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert order == ["grant", "ops"]
    assert grants == [7]


def test_deploy_rolls_back_grant_when_dispatch_fails(monkeypatch, tmp_path):
    """지시가 못 나갔으면 방금 연 인가를 되돌린다 — 열어둔 채 방치하지 않는다."""
    _sent, _persisted, grants, _order = _deploy_capture(
        monkeypatch, tmp_path, ops_result=(None, 0, "remoteManager unreachable"))
    with pytest.raises(Exception, match="deploy failed"):
        edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert grants == [7, 99]        # 새 인가 → 직전 값으로 복원


def test_deploy_refuses_when_public_base_missing(monkeypatch, tmp_path):
    """URL 을 못 만들면 조용히 구버전 폴백으로 흘리면 안 된다 — 에이전트가 '파일이 이미
    있다' 로 해석해 모델 없는 컨테이너를 띄운다(이 기능이 없애려던 바로 그 실패)."""
    sent, _persisted, grants, _order = _deploy_capture(monkeypatch, tmp_path)
    monkeypatch.delenv("PLATFORM_PUBLIC_BASE", raising=False)
    monkeypatch.delenv("EXTERNAL_HOST", raising=False)
    with pytest.raises(Exception, match="공개 주소"):
        edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert sent == {} and grants == []      # /ops 도, 인가도 나가지 않았다


def test_deploy_without_lineage_keeps_legacy_payload(monkeypatch, tmp_path):
    """lineage_id 없는 기존 호출은 종전 그대로 — 문자열만 전달한다."""
    sent, _persisted, grants, _order = _deploy_capture(monkeypatch, tmp_path)
    body = model.DeployEdgeModel(image="img:1", gguf_path="jobs/j1/output/m.gguf")
    edge_service.deploy_edge_worker(1, body)
    assert "model_url" not in sent
    assert sent["gguf_path"] == "jobs/j1/output/m.gguf"
    assert grants == []          # lineage 배포가 아니면 인가를 건드리지 않는다


def _refresh_capture(monkeypatch, metrics):
    monkeypatch.setattr(db_edge, "get_edge_worker",
                        lambda **kw: {"id": 1, "device_id": "d", "remote_manager_url": "http://d:8600"})
    monkeypatch.setattr(edge_service, "_poll_remote_manager", lambda url: metrics)
    monkeypatch.setattr(edge_service, "_worker_view", lambda w: w)
    return _capture_status(monkeypatch)


def test_refresh_keeps_deploying_while_download_in_progress(monkeypatch):
    """다운로드 중에는 컨테이너가 없다 — 그걸 'stopped' 로 새기면 배포 실패로 보인다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [], "container_count": 0, "deploy_in_progress": True,
        "last_deploy_error": None})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "deploying"


def test_refresh_does_not_wipe_model_while_deploying(monkeypatch):
    """진행 중에 모델명을 비우면 무엇을 받는 중인지 화면에서 사라진다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [], "container_count": 0, "deploy_in_progress": True,
        "last_deploy_error": None})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_model"] is None      # None = 컬럼을 건드리지 않음
    assert seen["deploy_version"] is None


def test_refresh_reports_async_deploy_failure(monkeypatch):
    """비동기 실패는 /ops 응답에 없다 — /metrics 가 알려주지 않으면 영원히 모른다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [], "container_count": 0, "deploy_in_progress": False,
        "last_deploy_error": "download failed: HTTPError"})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "error"


def test_refresh_still_reports_stopped_when_agent_is_silent(monkeypatch):
    """두 필드가 없는 구버전 에이전트는 종전 판정을 유지해야 한다(하위호환)."""
    seen = _refresh_capture(monkeypatch, {"containers": [], "container_count": 0})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "stopped"


def test_refresh_prefers_progress_over_running_container(monkeypatch):
    """재배포는 새 모델을 먼저 받고 나중에 컨테이너를 교체한다 — 받는 동안 /metrics 에는
    **옛 컨테이너가 살아 있다**. 컨테이너 유추가 이기면 옛 모델로 running 을 새기고
    배포 폴러가 새 배포 완료 전에 성공으로 단정한다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [{"name": "edge-serve", "image": "old:1", "state": "running",
                        "model": "old-model", "version": "v0"}],
        "container_count": 1, "deploy_in_progress": True, "last_deploy_error": None})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "deploying"
    assert seen["deploy_model"] is None          # 옛 모델명을 새 상태로 굳히지 않는다


def test_worker_view_hides_download_grant(monkeypatch):
    """목록 조회는 인가 없이 열려 있다 — 어떤 lineage 가 어느 디바이스에 걸렸는지는
    lineage_id 추측 공격의 정찰 정보라 노출하지 않는다."""
    monkeypatch.setattr(db_edge, "get_custom_labels",
                        lambda target_type=None, target_id=None: [])
    view = edge_service._worker_view({
        "id": 1, "device_id": "edge-1", "deploy_lineage_id": 42,
        "edge_token_hash": "abc", "conn_status": "online"})
    assert "deploy_lineage_id" not in view
    assert "edge_token_hash" not in view


def test_artifact_budget_blocks_only_after_real_transfer(monkeypatch):
    """수 GB 응답에 상한이 없으면 유효 토큰 하나로 NFS·대역폭을 고갈시킬 수 있다
    (게이트웨이 request-size-limiting 은 요청 본문만 본다).

    ⚠️ 동시 전송 '슬롯' 방식은 쓰지 않는다. 반납을 응답 제너레이터의 finally 에 걸 수밖에
    없는데 클라이언트가 먼저 끊으면 실행되지 않아 슬롯이 영구 누수됐다(실측). 예산은
    끊겨도 정리할 상태가 없고 시간이 지나면 저절로 빠진다.
    """
    dev = "edge-budget-test"
    edge_service._artifact_used.pop(dev, None)
    assert edge_service.artifact_budget_check(dev) == (True, None)
    # 바이트 기준이라 작은 요청은 여러 번이어도 막히지 않는다.
    for _ in range(5):
        assert edge_service.artifact_budget_reserve(dev, 1024)[0] is True
    edge_service.artifact_budget_reserve(dev, edge_service.ARTIFACT_BUDGET_BYTES)
    ok, err = edge_service.artifact_budget_check(dev)
    assert ok is False and "budget" in err
    edge_service._artifact_used.pop(dev, None)


def test_artifact_budget_window_expires(monkeypatch):
    """창이 지나면 저절로 회복된다 — 끊긴 전송이 디바이스를 영구히 막지 않는다."""
    dev = "edge-budget-window"
    edge_service._artifact_used.pop(dev, None)
    edge_service.artifact_budget_reserve(dev, edge_service.ARTIFACT_BUDGET_BYTES)
    assert edge_service.artifact_budget_check(dev)[0] is False
    # 창 시작 시각을 과거로 밀면 다음 확인에서 새 창으로 리셋된다.
    edge_service._artifact_used[dev][0] -= edge_service.ARTIFACT_BUDGET_WINDOW_SEC + 1
    assert edge_service.artifact_budget_check(dev)[0] is True
    edge_service._artifact_used.pop(dev, None)


def test_refresh_preserves_async_failure_reason(monkeypatch):
    """상태만 error 로 새기면 화면이 '왜' 를 말할 수 없다 — 사유를 함께 보존한다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [], "container_count": 0, "deploy_in_progress": False,
        "last_deploy_error": "download failed: HTTP 404"})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "error"
    assert seen["deploy_error"] == "download failed: HTTP 404"


def test_refresh_clears_failure_reason_when_healthy(monkeypatch):
    """옛 실패가 화석처럼 남으면 정상 배포가 계속 실패로 보인다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [{"name": "edge-serve", "image": "i:1", "state": "running",
                        "model": "m", "version": "v"}],
        "container_count": 1, "deploy_in_progress": False, "last_deploy_error": None})
    edge_service.refresh_edge_worker(1)
    assert seen["deploy_state"] == "running"
    assert seen["deploy_error"] == ""          # "" = 명시 해제


def test_refresh_sanitizes_device_supplied_failure_reason(monkeypatch):
    """사유는 기관 통제 밖 장비가 준 문자열이다 — 제어문자로 로그를 위조할 수 없어야 한다."""
    seen = _refresh_capture(monkeypatch, {
        "containers": [], "container_count": 0, "deploy_in_progress": False,
        "last_deploy_error": "boom\r\n[FAKE] admin override\tX"})
    edge_service.refresh_edge_worker(1)
    assert "\n" not in seen["deploy_error"] and "\r" not in seen["deploy_error"]


def test_deploy_clears_previous_failure_reason(monkeypatch, tmp_path):
    """새 배포를 시작하면 직전 실패 사유는 지운다."""
    _sent, persisted, _grants, _order = _deploy_capture(monkeypatch, tmp_path)
    edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert persisted["deploy_error"] == ""


def test_deploy_rejects_device_reported_error(monkeypatch, tmp_path):
    """디바이스는 실패를 200 + {"status":"error"} 로 돌려준다(_stop_outcome 과 같은 이유).
    전송됐다는 것만 보고 성공이라 말하면 화면이 '배포 요청됨' 토스트를 띄운다."""
    _sent, persisted, grants, _order = _deploy_capture(
        monkeypatch, tmp_path,
        ops_result=({"status": "error", "detail": "docker not available on device"}, 200, None))
    with pytest.raises(Exception, match="docker not available"):
        edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert persisted["deploy_state"] == "error"
    assert persisted["deploy_error"] == "docker not available on device"   # 사유를 버리지 않는다
    assert grants == [7, 99]        # 거절됐으니 다운로드 인가도 되돌린다


def test_deploy_error_detail_is_sanitized(monkeypatch, tmp_path):
    """사유는 기관 통제 밖 장비가 준 문자열이다."""
    _sent, persisted, _grants, _order = _deploy_capture(
        monkeypatch, tmp_path,
        ops_result=({"status": "error", "detail": "x\r\n[FAKE] admin\tY"}, 200, None))
    with pytest.raises(Exception):
        edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert "\n" not in persisted["deploy_error"] and "\r" not in persisted["deploy_error"]


def test_deploy_tolerates_non_dict_device_response(monkeypatch, tmp_path):
    """디바이스가 리스트·문자열 JSON 을 주면 .get 이 터진다(_stop_outcome 이 겪은 것)."""
    _sent, persisted, _grants, _order = _deploy_capture(
        monkeypatch, tmp_path, ops_result=(["unexpected"], 200, None))
    res = edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert res["deploy_state"] == "running"        # 200 → running 으로 떨어진다


def test_artifact_budget_reserve_blocks_concurrent_bypass():
    """확인만 하고 사후 가산하면 동시 연결이 전부 '0 바이트' 상태에서 통과해 한도의 N 배가
    흘러간다. 시작 시점에 선반영해야 그 창이 닫힌다."""
    dev = "edge-reserve-test"
    edge_service._artifact_used.pop(dev, None)
    big = edge_service.ARTIFACT_BUDGET_BYTES
    assert edge_service.artifact_budget_reserve(dev, big)[0] is True
    ok, err = edge_service.artifact_budget_reserve(dev, big)   # 두 번째 동시 요청
    assert ok is False and "budget" in err
    edge_service._artifact_used.pop(dev, None)


def test_stop_clears_failure_reason(monkeypatch):
    """중지가 확인되면 옛 실패 사유도 지운다 — refresh·deploy 와 같은 규율."""
    monkeypatch.setattr(db_edge, "get_edge_worker", lambda **kw: {
        "id": 1, "device_id": "d", "remote_manager_url": "http://d:8600",
        "deploy_state": "error"})
    monkeypatch.setattr(edge_service, "_remote_ops",
                        lambda url, payload: ({"status": "stopped"}, 200, None))
    seen = _capture_status(monkeypatch)
    edge_service.stop_edge_worker(1)
    assert seen["deploy_state"] == "stopped"
    assert seen["deploy_error"] == ""


def test_deploy_rejects_agent_without_contract_version(monkeypatch, tmp_path):
    """구버전 에이전트는 모르는 model_url 을 조용히 무시하고 받은 적 없는 파일명으로
    컨테이너를 띄운다 — 화면은 running 인데 모델이 없다. 계약을 보고하는 에이전트에만
    이 경로를 연다."""
    sent, _persisted, grants, _order = _deploy_capture(monkeypatch, tmp_path)
    monkeypatch.setattr(edge_service, "_poll_remote_manager",
                        lambda url: {"containers": [], "container_count": 0})  # 버전 미보고
    with pytest.raises(Exception, match="contract_version"):
        edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert sent == {} and grants == []      # 지시도 인가도 나가지 않았다


def test_deploy_allows_agent_reporting_contract_version(monkeypatch, tmp_path):
    sent, _persisted, grants, _order = _deploy_capture(monkeypatch, tmp_path)
    monkeypatch.setattr(edge_service, "_poll_remote_manager",
                        lambda url: {"contract_version": "1.0"})
    edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1", lineage_id=7))
    assert sent["model_url"] and grants == [7]


def test_legacy_deploy_skips_capability_probe(monkeypatch, tmp_path):
    """lineage_id 없는 기존 호출은 모델 수신을 요구하지 않으므로 게이트를 걸지 않는다."""
    sent, _persisted, _grants, _order = _deploy_capture(monkeypatch, tmp_path)
    def _boom(url):
        raise AssertionError("레거시 배포에서 capability 폴링이 일어나면 안 된다")
    monkeypatch.setattr(edge_service, "_poll_remote_manager", _boom)
    edge_service.deploy_edge_worker(1, model.DeployEdgeModel(image="img:1"))
    assert "model_url" not in sent
