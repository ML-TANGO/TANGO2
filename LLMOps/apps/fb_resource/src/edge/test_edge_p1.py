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

def test_register_accepts_hw_model_and_location():
    m = model.RegisterEdgeWorkerModel(
        device_id="orin-01", remote_manager_url="http://192.168.0.9:8080",
        hw_model="Jetson AGX Orin 64GB", location="부산항")
    assert m.hw_model == "Jetson AGX Orin 64GB"
    assert m.location == "부산항"


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
    db_edge.insert_edge_worker("orin-01", "n", "orin", "sds", "http://192.168.0.9:8080",
                               hw_model="AGX", location="busan")
    assert len(re.findall(r"%s", captured["sql"])) == len(captured["params"]) == 7
