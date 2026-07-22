"""Edge 워커 서비스 (SP-8 / 수용계획서 3.1).

remoteManager(K8s-free 브리지)가 관리하는 엣지 디바이스를 플랫폼 노드 테이블에
등록하고, remoteManager /metrics 폴링으로 연결상태/자원/배포상태를 갱신한다.
fb_resource 의 sync 패턴(requests + db_*)을 따른다.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests

from utils.msa_db import db_edge

REMOTE_MANAGER_TIMEOUT = 5  # sec
TOKEN_TTL_DAYS = 90
HEARTBEAT_OFFLINE_SEC = 300  # 미수신 5분 → offline
HEARTBEAT_MIN_INTERVAL_SEC = 30  # SP-8 §5.1 — 30초 미만 재호출 throttle(429)


class HeartbeatThrottled(Exception):
    """heartbeat 가 최소 간격(30s) 미만으로 재수신 → 라우트가 429 로 변환."""
    pass


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.strptime(str(v), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _derive_conn_status(w: dict) -> str:
    """last_seen staleness 로 online/offline 파생(heartbeat push 모델 — 폴러 불필요)."""
    ls = _parse_dt(w.get("last_seen"))
    if ls is None:
        return "offline"
    return "online" if (datetime.now() - ls).total_seconds() <= HEARTBEAT_OFFLINE_SEC else "offline"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_device_token(worker_id: int) -> dict:
    """노드별 Bearer 토큰 발급(재호출=rotation). 평문은 응답에서 1회만 노출."""
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    plaintext = secrets.token_urlsafe(32)
    prefix = plaintext[:8]
    expires_at = (datetime.now() + timedelta(days=TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    ok = db_edge.update_edge_worker_token(
        worker_id, token_hash=_hash_token(plaintext),
        token_prefix=prefix, token_expires_at=expires_at,
    )
    if not ok:
        raise Exception("failed to persist token")
    return {"worker_id": worker_id, "device_id": w["device_id"],
            "token": plaintext, "token_prefix": prefix, "expires_at": expires_at}


def verify_device_token(device_id: str, token: str) -> bool:
    """device-facing 요청의 Bearer 토큰 검증(상수시간 + 만료 확인)."""
    if not token:
        return False
    w = db_edge.get_edge_worker(device_id=device_id)
    if not w or not w.get("edge_token_hash"):
        return False
    # 만료 확인 — fail-closed: 만료값이 있는데 파싱 실패하면 만료로 간주(fail-open 금지).
    raw_exp = w.get("token_expires_at")
    if raw_exp is not None:
        exp = _parse_dt(raw_exp)
        if exp is None or datetime.now() > exp:
            return False
    return hmac.compare_digest(str(w["edge_token_hash"]), _hash_token(token))


def record_heartbeat(device_id: str, body) -> dict:
    """heartbeat 원본 저장 + last_seen/online 갱신."""
    w = db_edge.get_edge_worker(device_id=device_id)
    if not w:
        raise Exception(f"edge worker not found: {device_id}")
    # SP-8 §5.1 — 30초 미만 재수신 throttle(429). 등록 직후 첫 heartbeat 오탐 회피 위해
    # "이전 heartbeat 존재(last_heartbeat_json)" 를 게이트로 둔다(등록도 last_seen 을 세팅하므로).
    if w.get("last_heartbeat_json"):
        prev = _parse_dt(w.get("last_seen"))
        if prev is not None and (datetime.now() - prev).total_seconds() < HEARTBEAT_MIN_INTERVAL_SEC:
            raise HeartbeatThrottled(device_id)
    # 필드는 HeartbeatModel 에서 bound 되므로 정상 payload 는 8000 미만. 초과 시 blind
    # slice(잘린 무효 JSON 영속) 대신 거부해 이후 판독기 파손을 막는다.
    hb_json = json.dumps(body.model_dump())
    if len(hb_json) > 8000:
        raise Exception("heartbeat payload too large")
    if not db_edge.update_edge_worker_heartbeat(w["id"], last_heartbeat_json=hb_json, last_seen=_now()):
        raise Exception("failed to persist heartbeat")
    return {"device_id": device_id, "received": True}


def _safe_rm_url(url: str, suffix: str):
    """remote_manager_url 을 SSRF 방어 후 정규화 → `{scheme}://{host[:port]}{suffix}`.

    엣지 디바이스는 사설 LAN(192.168/10/172.16)에 정당히 있으므로 사설IP는 허용하되,
    loopback/link-local(169.254 metadata)/multicast/unspecified/reserved 와 userinfo·
    path·query·fragment 는 거부(내부 서비스·클라우드 메타데이터 SSRF 차단). 실패 시 None.
    """
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return None
        # userinfo(자격증명) / 임의 path / query / fragment 거부.
        if p.username or p.password or p.query or p.fragment:
            return None
        if p.path not in ("", "/"):
            return None
        # 호스트 해석 → 위험 대역 차단(사설은 허용).
        for _fam, _, _, _, sockaddr in socket.getaddrinfo(p.hostname, p.port or None):
            ip = ipaddress.ip_address(sockaddr[0])
            if (ip.is_loopback or ip.is_link_local or ip.is_multicast
                    or ip.is_unspecified or ip.is_reserved):
                return None
        netloc = p.hostname if not p.port else f"{p.hostname}:{p.port}"
        return f"{p.scheme}://{netloc}{suffix}"
    except Exception:
        return None


def _poll_remote_manager(url: str):
    """remoteManager centralagent /metrics 조회. 실패/위험URL 시 None(=offline 판정).

    기대 JSON(remoteManager node 메트릭, RT-remoteManager.md): node_cpu_total /
    memory_total / container_count / gpu / containers[{name,image,state,model,version}].
    """
    metrics_url = _safe_rm_url(url, "/metrics")
    if not metrics_url:
        return None
    try:
        # allow_redirects=False — 허용 호스트→내부 호스트 리다이렉트 우회 차단.
        resp = requests.get(metrics_url, timeout=REMOTE_MANAGER_TIMEOUT, allow_redirects=False)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _remote_ops(url: str, payload: dict):
    """remoteManager centralagent /ops 호출(SP-6 배포: pull/create/start). SSRF-safe.
    반환 (result_json|None, status_code, err). 네트워크 예외 메시지에 내부 host:port 가
    클라이언트로 새지 않도록 generic 사유만 반환(상세는 서버 로그)."""
    ops_url = _safe_rm_url(url, "/ops")
    if not ops_url:
        return None, 0, "unsafe or invalid remote_manager_url"
    try:
        resp = requests.post(ops_url, json=payload, timeout=REMOTE_MANAGER_TIMEOUT,
                             allow_redirects=False)
        if resp.status_code not in (200, 201, 202):
            return None, resp.status_code, f"remoteManager /ops returned {resp.status_code}"
        try:
            return resp.json(), resp.status_code, None
        except Exception:
            return {}, resp.status_code, None
    except Exception:
        traceback.print_exc()  # 상세(host/port 포함)는 서버 로그에만.
        return None, 0, "remoteManager unreachable"


def _labels_for(target_type: str, target_id: str):
    rows = db_edge.get_custom_labels(target_type=target_type, target_id=target_id)
    return [{"id": r["id"], "key": r["label_key"], "value": r["label_value"]} for r in rows]


def _worker_view(w: dict) -> dict:
    if not w:
        return None
    w = dict(w)
    has_token = bool(w.get("edge_token_hash"))
    # 인증 material(토큰 해시)은 응답에 노출하지 않는다(token_prefix/expires_at 만 표시).
    w.pop("edge_token_hash", None)
    # heartbeat 워커(토큰 발급됨)만 last_seen staleness 로 offline 파생. pull 전용
    # (remoteManager /metrics) 워커는 저장된 conn_status 유지 — 주기 폴러 부재로 인한
    # 오탐(→ SP-6 배포 셀렉터가 healthy 디바이스를 비활성화) 방지.
    if has_token:
        w["conn_status"] = _derive_conn_status(w)
    return {**w, "labels": _labels_for("edge_worker", w["device_id"])}


def _generate_device_id() -> str:
    """서버측 불변 식별자 생성 — 이름(가변)과 분리. 물리장비 heartbeat id 로 쓰인다."""
    return "edge-" + secrets.token_hex(4)  # edge-xxxxxxxx (8 hex)


def register_edge_worker(body) -> dict:
    # 이름은 사람이 식별하는 유일 키 — 중복 등록 방지(정확 일치).
    if db_edge.get_edge_worker(name=body.name):
        raise Exception(f"edge worker name already exists: {body.name}")
    # device_id 는 서버가 자동 생성(랜덤 불투명값). 극히 드문 충돌은 재시도로 회피.
    device_id = None
    for _ in range(5):
        candidate = _generate_device_id()
        if not db_edge.get_edge_worker(device_id=candidate):
            device_id = candidate
            break
    if device_id is None:
        raise Exception("failed to allocate unique device_id")
    wid = db_edge.insert_edge_worker(
        device_id=device_id, name=body.name, device_type=body.device_type,
        remote_manager_url=body.remote_manager_url,
    )
    if not wid:
        raise Exception("failed to register edge worker")
    # 등록 즉시 1회 폴링해 상태 채움(실패해도 offline 으로 등록은 유지).
    try:
        refresh_edge_worker(wid)
    except Exception:
        traceback.print_exc()
    return _worker_view(db_edge.get_edge_worker(worker_id=wid))


def list_edge_workers() -> list:
    return [_worker_view(w) for w in db_edge.get_edge_worker_list()]


def get_edge_worker(worker_id: int) -> dict:
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    return _worker_view(w)


def delete_edge_worker(worker_id: int) -> dict:
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    db_edge.delete_edge_worker(worker_id)
    # orphan 레이블 정리 — custom_label 은 device_id 키라 안 지우면 동일 device_id
    # 재등록 시 옛 레이블이 부활한다.
    db_edge.delete_custom_labels_for("edge_worker", w["device_id"])
    return {"deleted": worker_id}


def refresh_edge_worker(worker_id: int) -> dict:
    """remoteManager 폴링 → 연결상태/자원/배포 갱신. 핵심 [필수] 지표 채움."""
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    metrics = _poll_remote_manager(w["remote_manager_url"])
    if not isinstance(metrics, dict):
        db_edge.update_edge_worker_status(worker_id, conn_status="offline")
        return _worker_view(db_edge.get_edge_worker(worker_id=worker_id))

    # 신뢰 못 하는 remoteManager 응답 → 타입/길이/enum 검증 후 저장.
    containers = metrics.get("containers")
    if not isinstance(containers, list):
        containers = []
    # 배포 컨테이너 선별: model 키 있는 것 우선(헬퍼/사이드카 오판 방지) → running → 첫 컨테이너.
    cdicts = [c for c in containers if isinstance(c, dict)]
    deploy = (next((c for c in cdicts if c.get("model")), None)
              or next((c for c in cdicts if c.get("state") == "running"), None)
              or (cdicts[0] if cdicts else {}))
    state = str(deploy.get("state") or "").lower()
    deploy_state = state if state in ("running", "stopped", "error") else "stopped"

    def _trim(v, n):
        return str(v)[:n] if v is not None else None

    def _intval(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    cc = _intval(metrics.get("container_count"))
    ok = db_edge.update_edge_worker_status(
        worker_id,
        conn_status="online",
        last_seen=_now(),
        cpu_cores=_intval(metrics.get("node_cpu_total")),
        mem_total=_intval(metrics.get("memory_total")),
        gpu_info=_trim(metrics.get("gpu"), 256),
        container_count=cc if cc is not None else len(cdicts),
        deploy_model=_trim(deploy.get("model") or deploy.get("image"), 128),
        deploy_version=_trim(deploy.get("version"), 64),
        deploy_state=deploy_state,
    )
    if not ok:
        # 영속 실패를 online 성공으로 위장하지 않음.
        raise Exception("failed to persist edge worker status")
    return _worker_view(db_edge.get_edge_worker(worker_id=worker_id))


def deploy_edge_worker(worker_id: int, body) -> dict:
    """양자화 포팅 패키지(GGUF)를 Edge 워커에 remoteManager /ops 로 배포 (SP-6 / 3.10).

    기관 제공 Edge 실행 이미지 + SP-4 양자화 weight(gguf_path) 주입 → remoteManager 가
    pull/create/start. 성공 시 edge_worker.deploy_*(모델/버전/running) 갱신.
    """
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    # None 키 제거 — remoteManager 에 explicit null override 를 보내지 않는다.
    payload = {k: v for k, v in {
        "op": "deploy",
        "image": body.image,
        "model": body.model_name,
        "version": body.model_version,
        "gguf_path": body.gguf_path,
        "params": body.params or {},
    }.items() if v is not None}
    result, code, err = _remote_ops(w["remote_manager_url"], payload)
    if result is None:
        raise Exception(f"deploy failed: {err}")
    # 202(Accepted=async)는 완료 단정 X → deploying. remoteManager 가 유효 status 를
    # 주면 그걸 쓰고, 아니면 200/201=running, 그 외=deploying. (실상태는 다음 /metrics 폴링이 확정)
    rstate = str((result or {}).get("status") or "").lower()
    if rstate in ("running", "stopped", "error", "deploying"):
        deploy_state = rstate
    else:
        deploy_state = "running" if code in (200, 201) else "deploying"
    ok = db_edge.update_edge_worker_status(
        worker_id,
        conn_status="online",
        last_seen=_now(),
        deploy_model=str(body.model_name or body.image)[:128],
        # 재배포 시 옛 버전 잔류 방지 — 없으면 "" 로 명시 갱신(None 은 skip 됨).
        deploy_version=(str(body.model_version)[:64] if body.model_version else ""),
        deploy_state=deploy_state,
    )
    if not ok:
        raise Exception("failed to persist deploy status")
    return {
        "worker_id": worker_id,
        "device_id": w["device_id"],
        "model": body.model_name,
        "version": body.model_version,
        "image": body.image,
        "gguf_path": body.gguf_path,
        "deploy_state": deploy_state,
        "remote_manager_result": result,
    }


# ── 커스텀 레이블 ─────────────────────────────────────────────────────────────

def upsert_label(body) -> dict:
    if not db_edge.upsert_custom_label(
        body.target_type, body.target_id, body.label_key, body.label_value
    ):
        raise Exception("failed to upsert label")
    return {"target_type": body.target_type, "target_id": body.target_id,
            "key": body.label_key, "value": body.label_value}


def list_labels(target_type=None, target_id=None) -> list:
    rows = db_edge.get_custom_labels(target_type=target_type, target_id=target_id)
    return [{"id": r["id"], "target_type": r["target_type"], "target_id": r["target_id"],
             "key": r["label_key"], "value": r["label_value"]} for r in rows]


def delete_label(label_id: int) -> dict:
    db_edge.delete_custom_label(label_id)
    return {"deleted": label_id}
