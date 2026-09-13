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
    # SP-8 §5.1 — 30초 미만 재수신 throttle(429).
    # ⚠️ 기준은 last_heartbeat_at(디바이스 푸시 전용)이다. last_seen 을 쓰면 안 된다 —
    # 등록·refresh(/metrics 폴링)·deploy 가 모두 last_seen 을 갱신하므로, UI 새로고침
    # 한 번이 규약을 지킨 디바이스의 다음 heartbeat 를 30초간 429 로 튕긴다(2026-09-11
    # 재현: refresh → t+18s·t+36s err:429 → t+54s 200). 그 상태가 offline 임계(300s)
    # 까지 이어지면 online 인 디바이스가 offline 으로 표시되고 배포 화면의 디바이스
    # 선택까지 막힌다. 컬럼이 NULL 이면(첫 heartbeat·구 데이터) throttle 하지 않는다 —
    # 이전 판본의 last_heartbeat_json 게이트가 노렸던 "등록 직후 오탐" 은 이 NULL 검사로
    # 자연히 충족된다.
    prev = _parse_dt(w.get("last_heartbeat_at"))
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


def _sanitize(v, limit: int = 200) -> str:
    """디바이스가 준 문자열을 응답·로그에 싣기 전에 절단 + 제어문자 제거.

    엣지 디바이스는 기관 통제 밖 장비라 `/ops` 응답 문자열을 신뢰할 수 없다. 이 파일은
    이미 디바이스 제공 값에 일관되게 상한을 둔다(heartbeat 8000 · gpu_info 256 ·
    deploy_model 128 · deploy_version 64). 상한이 없으면 응답·로그가 비대해지고,
    개행을 섞으면 로그에 가짜 다중 라인을 주입할 수 있다(CWE-117).
    """
    if v is None:
        return ""
    s = str(v)
    s = "".join(ch for ch in s if ch == " " or (ch.isprintable() and ch not in "\r\n\t"))
    return s[:limit]


def _stop_outcome(result, code, err):
    """remoteManager stop 응답 → (ok, reason). 확정 실패/비확정을 성공으로 세지 않는다.

    `_remote_ops` 는 200/201/202 를 전부 통과시키므로 `result is not None` 만으로는
    성공을 말할 수 없다 — 실 agent 는 `{"status":"error","detail":...}` 를 네 경로에서
    돌려준다(unknown op · image required · docker not available · 예외). 그걸 성공으로
    받으면 디바이스에 컨테이너가 살아 있는데 플랫폼은 'stopped' 라 말한다.
    202(비확정)도 단정하지 않는다 — 실상태는 다음 /metrics 폴링이 확정한다.
    """
    if result is None:
        return False, err
    # `resp.json()` 은 dict 가 아닐 수 있다(디바이스가 리스트·문자열·숫자 JSON 을 주면).
    # `(result or {}).get(...)` 은 truthy non-dict 에서 AttributeError 를 던지고, 그
    # 예외가 delete 경로에서는 DB 삭제 **전에** 터져 삭제 자체를 실패시킨다 —
    # "결과와 무관하게 삭제는 진행한다" 는 delete_edge_worker 의 약속을 깬다.
    if not isinstance(result, dict):
        return False, "unexpected /ops response shape"
    rstate = str(result.get("status") or "").lower()
    if rstate == "error":
        return False, f"device rejected stop: {_sanitize(result.get('detail')) or 'unknown'}"
    # 명시적 비-stopped 상태를 성공으로 세면 안 된다 — 특히 {"status":"running"} 은
    # "아직 돌고 있다" 는 뜻인데 HTTP 코드만 보면 중지로 뒤집힌다. status 가 아예
    # 없을 때만 HTTP 코드로 판정한다. 202 등 비확정도 단정하지 않는다(/metrics 가 확정).
    if rstate == "stopped":
        return True, None
    if not rstate and code in (200, 201):
        return True, None
    return False, f"stop not confirmed by device (status={rstate or code})"


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
    """워커 제거. 배포가 돌고 있으면 stop 을 **best-effort** 로 먼저 보낸다.

    stop 을 보내지 않으면 플랫폼 레코드만 사라지고 디바이스에서는 컨테이너가 계속
    돌아 유령 워크로드가 자원을 쥔다. 반대로 stop 성공을 삭제의 전제로 걸면 전원이
    꺼졌거나 망에서 빠진 디바이스를 영구히 제거할 수 없다 — 엣지에서는 그게 정상
    상태다. 그래서 결과와 무관하게 삭제는 진행하고, 무엇이 남을 수 있는지를 응답의
    `stop` 에 실어 호출자가 경고할 수 있게 한다(조용히 넘기지 않는다).
    """
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    stop = {"attempted": False, "ok": False, "reason": None}
    # 돌지 않는 컨테이너에 stop 을 보내려고 응답 없는 디바이스를 기다리며 삭제를
    # 지연시키지 않는다. URL 이 없으면(heartbeat-only) 보낼 방향 자체가 없다.
    #   · deploying 도 포함한다 — deploy 가 202(async)를 받으면 그 상태로 남는데,
    #     그때 삭제하면 이후 디바이스에서 컨테이너가 기동돼 유령으로 남고 attempted
    #     =false 라 UI 경고조차 안 뜬다(running 만 보던 것이 이 갭을 만들었다).
    #   · conn_status 가 offline 인 디바이스는 건너뛴다 — 어차피 도달 못 하는데
    #     _safe_rm_url 의 getaddrinfo(앱 타임아웃 없음) + HTTP 5s 만큼 삭제가 묶인다.
    #     엣지는 전원이 꺼지는 게 정상 상태라 그 대기를 기본 경로에 두면 안 된다.
    #   · error 도 포함한다 — deploy 실패는 "컨테이너가 없다" 는 보장이 아니다(이미지
    #     pull 실패 후 Created/crash-loop 컨테이너가 남을 수 있다).
    #   · offline 판정은 **토큰 워커에만** 적용한다. last_seen 은 토큰 워커에서는
    #     디바이스 push 기반이라 liveness 로 유효하지만, pull-only 워커에서는 "우리가
    #     마지막에 폴링한 시각" 일 뿐이고 주기 폴러가 없어 자연 소멸한다. 그 값으로
    #     건너뛰면 도달 가능한 디바이스의 stop 이 영구히 생략된다(_worker_view 가
    #     같은 이유로 has_token 분기를 두는 것과 동일한 논리).
    _stale = (bool(w.get("edge_token_hash"))
              and _derive_conn_status(w) != "online")
    if (w.get("remote_manager_url")
            and w.get("deploy_state") in ("running", "deploying", "error")
            and not _stale):
        stop["attempted"] = True
        # 어떤 예외도 삭제를 막지 못하게 한다 — 이 함수는 "결과와 무관하게 삭제는
        # 진행한다" 를 약속하므로, best-effort 가 실제로 best-effort 여야 한다.
        try:
            result, code, err = _remote_ops(w["remote_manager_url"], {"op": "stop"})
            ok, reason = _stop_outcome(result, code, err)
        except Exception as e:
            traceback.print_exc()
            ok, reason = False, f"stop attempt raised {type(e).__name__}"
        stop["ok"], stop["reason"] = ok, reason
    # 영속 실패를 삭제 성공으로 위장하지 않는다 — 컨테이너는 내렸는데 행이 남으면
    # 화면에는 배포가 계속 살아 있는 것으로 보인다.
    if not db_edge.delete_edge_worker(worker_id):
        raise Exception(f"failed to delete edge worker {worker_id}")
    # orphan 레이블 정리 — custom_label 은 device_id 키라 안 지우면 동일 device_id
    # 재등록 시 옛 레이블이 부활한다.
    db_edge.delete_custom_labels_for("edge_worker", w["device_id"])
    return {"deleted": worker_id, "stop": stop}


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
        # 컨테이너가 사라지면 모델·버전도 함께 비운다. db_edge 는 None 을 skip 하므로
        # (`None 필드는 건드리지 않음`) 그대로 넘기면 deploy_state 만 stopped 로 바뀌고
        # 옛 모델명이 화석처럼 남아, 화면이 "그 모델이 죽었다" 는 거짓을 말한다.
        # deploy_edge_worker 가 재배포 시 쓰는 것과 같은 "" 센티널로 명시 초기화한다.
        deploy_model=_trim(deploy.get("model") or deploy.get("image"), 128) or "",
        deploy_version=_trim(deploy.get("version"), 64) or "",
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


def stop_edge_worker(worker_id: int) -> dict:
    """배포된 컨테이너를 remoteManager /ops `op:"stop"` 으로 내린다.

    디바이스 쪽 구현은 이미 있었다(remote_manager_agent `op=="stop"` → 컨테이너 제거).
    플랫폼에 이를 호출하는 경로가 없어서, 배포는 되지만 중지는 불가능했고 워커를
    삭제해도 디바이스에는 컨테이너가 유령으로 남았다.

    성공 시 deploy_state='stopped' + 모델·버전을 "" 로 비운다 — refresh 와 같은 규약
    (None 은 db_edge 가 skip 하므로 옛 모델명이 화석으로 남는다).
    """
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    # heartbeat-only 디바이스(remote_manager_url NULL 허용)는 플랫폼→디바이스 방향이
    # 없으므로 중지 자체가 불가능하다. online 이어도 그렇다 — online 은 heartbeat
    # (디바이스→플랫폼) 판정이고 /ops 는 반대 방향이다. 사유를 구분해 올린다.
    if not w.get("remote_manager_url"):
        raise Exception("this device has no remote_manager_url (heartbeat-only)")
    result, code, err = _remote_ops(w["remote_manager_url"], {"op": "stop"})
    # 디바이스가 돌려준 status 를 검사한다 — deploy_edge_worker 가 rstate 를 보는 것과
    # 동형. 이걸 빼면 {"status":"error"} 나 비확정 202 도 stopped 로 영속돼, 컨테이너가
    # 살아 있는데 플랫폼이 "중지됨" 이라 말하는 조용한 거짓이 된다.
    stopped, reason = _stop_outcome(result, code, err)
    if not stopped:
        raise Exception(f"stop failed: {reason}")
    ok = db_edge.update_edge_worker_status(
        worker_id,
        conn_status="online",
        last_seen=_now(),
        deploy_model="",
        deploy_version="",
        deploy_state="stopped",
    )
    if not ok:
        raise Exception("failed to persist stop status")
    return {
        "worker_id": worker_id,
        "device_id": w["device_id"],
        "deploy_state": "stopped",
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
