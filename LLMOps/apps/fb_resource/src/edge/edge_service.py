"""Edge 워커 서비스 (SP-8 / 수용계획서 3.1).

remoteManager(K8s-free 브리지)가 관리하는 엣지 디바이스를 플랫폼 노드 테이블에
등록하고, remoteManager /metrics 폴링으로 연결상태/자원/배포상태를 갱신한다.
fb_resource 의 sync 패턴(requests + db_*)을 따른다.
"""
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlparse

import threading
import time

import requests

from utils import PATH, settings
from utils.msa_db import db_edge, db_workspace

REMOTE_MANAGER_TIMEOUT = 5  # sec
# 플랫폼 → 디바이스 `/ops`·`/metrics` 인증 토큰(계약 v1)은 EDGE_OPS_TOKEN 이다.
# 전역 단일 값이며 K8s Secret 으로만 주입한다 — DB 에 두지 않으므로 edge_token 의
# '평문 미저장' 불변식을 깨지 않는다. 비어 있으면 헤더를 붙이지 않는다(토큰 검증이
# 없는 구버전 에이전트와의 하위호환). 아래 _ops_headers 참조.
TOKEN_TTL_DAYS = 90
HEARTBEAT_OFFLINE_SEC = 300  # 미수신 5분 → offline
HEARTBEAT_MIN_INTERVAL_SEC = 30  # SP-8 §5.1 — 30초 미만 재호출 throttle(429)
# 아티팩트 다운로드는 수 GB 를 흘린다. heartbeat 와 달리 게이트웨이 request-size-limiting
# 은 **요청 본문**만 제한해 응답 바이트에는 무의미하고, rate-limiting 플러그인은 아직
# 라이브 적용 전이다. 그래서 앱 레벨 백스톱을 둔다.
# 제한 방식은 **시간창 전송량 예산**이다. 동시 전송 수를 세는 방식도 만들어 봤으나
# 슬롯 반납을 응답 제너레이터의 finally 에 묶을 수밖에 없고, 클라이언트가 먼저 끊으면
# 그 finally 가 실행되지 않아 슬롯이 영구 누수됐다(실측: 정상 요청 1회 뒤 그 디바이스는
# 계속 429). 막으려던 것보다 더 나쁜 고장이다. 소비량을 쌓았다가 시간이 지나면 저절로
# 빠지는 예산 방식은 **누수가 원리적으로 불가능**하다 — 전송이 끊겨도 정리할 상태가 없다.
ARTIFACT_BUDGET_BYTES = 20 * 1024 ** 3     # 창당 허용 전송량(2.5GB 모델 8회분)
ARTIFACT_BUDGET_WINDOW_SEC = 600


class ArtifactUnavailable(Exception):
    """아티팩트를 줄 수 없다. **사유를 클라이언트에 구분해 주지 않는다.**

    배포 라우트는 예외 메시지를 그대로 응답에 싣는다(`message=str(e)`). 사유를 나누면
    (없음/미완료/파일부재/워크스페이스불명) 임의 lineage_id 를 넣어 배포를 반복하는
    것만으로 시스템 전역 quantize job 의 존재·완료·파일 실재를 이진탐색할 수 있다.
    상세는 `detail` 로 들고 서버 로그에만 남긴다.
    """

    def __init__(self, detail):
        self.detail = detail
        super().__init__("artifact unavailable")


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


def _is_stale(w: dict, field: str = "last_seen") -> bool:
    """`field` 시각이 임계를 넘겼는가 — conn_status 와 **분리된** 신선도.

    두 타임스탬프를 구분해서 쓴다.
      · `last_seen`          → **연결** 신선도. register·refresh·deploy·heartbeat 가 올린다.
      · `deploy_observed_at` → **배포상태** 신선도. 실제로 배포를 관측한 경로
        (/ops 응답, /metrics 폴링, heartbeat-only 워커의 model 보고)만 올린다.

    둘을 한 값으로 쓰면 안 된다. heartbeat 는 컨테이너를 보지 않으면서 last_seen 을
    올리므로(/metrics 만 docker ps 를 본다), 컨테이너가 죽었는데 에이전트만 살아
    heartbeat 를 보내는 디바이스가 화면에서 계속 신선한 'running' 으로 보인다.
    값이 없으면(한 번도 관측 안 됨) stale 로 본다 — "모른다" 가 맞는 답이다.
    """
    ts = _parse_dt(w.get(field))
    if ts is None:
        return True
    return (datetime.now() - ts).total_seconds() > HEARTBEAT_OFFLINE_SEC


def _derive_conn_status(w: dict) -> str:
    """last_seen staleness 로 online/offline 파생(heartbeat push 모델 — 폴러 불필요)."""
    return "offline" if _is_stale(w) else "online"


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
    # 디바이스가 보고한 model_loaded 를 배포 레코드에 대사한다 — 단 remote_manager_url 이
    # **없는**(heartbeat-only) 워커에 한정한다. 그 워커에게는 heartbeat 가 유일한 채널이라
    # 이 값이 아니면 무엇이 올라가 있는지 알 방법이 없고(/ops·/metrics 가 불가능하다,
    # stop_edge_worker 가 같은 이유로 거절한다), 경쟁 writer 도 없다.
    #   ⚠️ remoteManager 가 있는 워커는 대사하지 않는다. 두 가지 이유가 겹친다.
    #     (1) 경쟁: /ops·/metrics 가 같은 컬럼의 권위 writer 인데 heartbeat 는 독립 채널이라
    #         도착 순서가 보장되지 않는다. stop 직후 도착한 in-flight heartbeat 가 방금 비운
    #         deploy_model 을 되살리면, 이후 heartbeat 는 빈 값만 보내고 빈 값은 무시하도록
    #         설계돼 있어(아래) 그 잘못된 값이 다음 /refresh 까지 **영구히** 남는다.
    #         이 변경의 목적은 "모른다고 말하기" 인데 그건 "틀리게 말하기" 라 더 나쁘다.
    #     (2) 무이득: 레퍼런스 에이전트의 _last_deploy 는 /ops deploy 에서만 채워지므로
    #         그 워커의 model_loaded 는 플랫폼이 방금 배포한 값의 메아리다. 대사해도
    #         새로 알게 되는 것이 없고, 실상태 확정은 docker ps 를 보는 /refresh 몫이다.
    #   ⚠️ 빈 값은 "배포 없음" 이 아니라 "정보 없음" 으로 다룬다. 레퍼런스 에이전트의
    #     _last_deploy 는 in-memory 라, 컨테이너가 --restart unless-stopped 로 살아 있어도
    #     에이전트만 재시작되면 "" 가 된다. 그걸 비움으로 새기면 살아 있는 배포를 죽었다고
    #     기록한다.
    #   ⚠️ deploy_state 는 갱신하지 않는다. model_loaded 는 에이전트의 기억일 뿐
    #     컨테이너가 지금 돌고 있다는 증거가 아니다.
    #   ⚠️ 디바이스 제공 문자열이므로 _sanitize 를 거친다 — 이 값은 이제
    #     last_heartbeat_json blob 밖의 1급 컬럼이라 화면·envelope·로그로 퍼진다.
    #     제어문자·개행이 섞이면 로그에 가짜 다중 라인을 주입할 수 있다(CWE-117).
    reported_model = ""
    if not w.get("remote_manager_url"):
        reported_model = _sanitize(body.model_loaded, 128).strip()
    if not db_edge.update_edge_worker_heartbeat(
            w["id"], last_heartbeat_json=hb_json, last_seen=_now(),
            deploy_model=reported_model or None,
            # heartbeat-only 워커에서만 이 보고가 유일한 배포 관측이다. 그 외(대사하지
            # 않는 워커)는 None — heartbeat 는 컨테이너를 보지 않으므로 관측이 아니다.
            deploy_observed_at=_now() if reported_model else None):
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


# 워커별 배포 직렬화. 다운로드 인가(deploy_lineage_id)는 워커당 한 칸뿐이라, 같은 워커에
# 동시 배포가 들어오면 A 의 지시가 나가기도 전에 B 가 인가를 덮어쓸 수 있다. 그러면 A 의
# 에이전트가 받으러 왔을 때 B 의 아티팩트를 A 의 파일명으로 저장한다 — 엉뚱한 가중치가
# 올라간다. 에이전트의 409 는 디바이스 쪽 동시성만 막을 뿐 이 창은 닫지 못한다.
_deploy_locks = {}
_deploy_locks_guard = threading.Lock()


def _worker_deploy_lock(worker_id):
    with _deploy_locks_guard:
        return _deploy_locks.setdefault(worker_id, threading.Lock())


# ── ops 토큰 (플랫폼이 디바이스에 자신을 증명하는 공유 키) ────────────────────
# 저장소는 K8s Secret 하나. 키 2개를 둔다.
#   ops-token       현재 키 — 플랫폼은 **항상 이 값만** 부착한다(_ops_headers 참조).
#   ops-token-prev  직전 키 — 재발급 시 보관만 한다. 플랫폼은 이 값을 보내지 않는다.
# 재발급은 하드 컷오버다: 그 순간부터 새 키만 나가므로, 아직 교체하지 않은 디바이스는
# 401 로 거부된다(옛 키로 재시도하지 않는다 — 유출된 키의 수명을 늘리지 않기 위함).
# 디바이스측 OPS_TOKEN_PREV 는 그 반대 구간을 덮는다: 디바이스를 새 키로 바꾼 직후
# 아래 캐시(TTL) 때문에 플랫폼이 잠시 옛 키를 보낼 수 있는 창.
# ⚠️ DB 에 두지 않는다. 디바이스 토큰의 '해시만 저장' 불변식과 별개로, 이 값은 보내야
#    하므로 평문 보관이 불가피하고 DB 덤프·백업에 섞이면 안 된다.
OPS_SECRET_NAME = "jfb-edge-ops-token"
OPS_KEY = "ops-token"
OPS_KEY_PREV = "ops-token-prev"
# /ops·/metrics 는 화면 새로고침마다 불린다. 매번 kube-apiserver 를 두드리지 않도록
# 짧게 캐시한다 — 재발급 반영이 이 시간만큼 늦어지는 대신 API 부하가 없다.
_OPS_CACHE_TTL_SEC = 20
_ops_cache = {"at": 0.0, "value": None}
_ops_cache_lock = threading.Lock()


def _secret_read(namespace, name):
    """K8s Secret 읽기. ⚠️ kube 모듈은 **함수 안에서** import 한다 — 모듈 최상단에 두면
    aiohttp·paramiko 등 무거운 의존 체인이 딸려와, 이 파일을 import 하는 것만으로
    테스트 환경이 앱 전체 의존성을 요구하게 된다(실측으로 기존 스위트가 깨졌다)."""
    from utils import kube
    return kube.read_secret(namespace, name)


def _secret_write(namespace, name, string_data):
    from utils import kube
    return kube.create_or_replace_secret(namespace, name, string_data)


def _ops_secret(force: bool = False):
    """Secret 에서 {ops-token, ops-token-prev} 를 읽는다(TTL 캐시). 실패 시 {}."""
    now = time.monotonic()
    with _ops_cache_lock:
        if not force and _ops_cache["value"] is not None \
                and (now - _ops_cache["at"]) < _OPS_CACHE_TTL_SEC:
            return _ops_cache["value"]
    try:
        data = _secret_read(settings.SYSTEM_NAMESPACE, OPS_SECRET_NAME) or {}
    except Exception:
        # K8s API 에 못 닿는 설치(에어갭·권한 제한)도 있다 — env 폴백이 살아 있으므로
        # 여기서 죽이지 않는다.
        traceback.print_exc()
        data = {}
    with _ops_cache_lock:
        _ops_cache.update({"at": now, "value": data})
    return data


def _ops_token_current() -> str:
    """플랫폼이 부착할 현재 키. Secret 우선, 없으면 파드 env 폴백."""
    tok = (_ops_secret().get(OPS_KEY) or "").strip()
    return tok or os.environ.get("EDGE_OPS_TOKEN", "").strip()


def _ops_headers():
    """플랫폼 → 디바이스 인증 헤더. 토큰이 없으면 빈 dict — 검증하지 않는 구버전
    에이전트와의 하위호환. `/ops` 와 `/metrics` 가 같은 게이트를 쓴다."""
    token = _ops_token_current()
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_ops_token() -> dict:
    """관리자 조회 — 평문을 그대로 돌려준다.

    디바이스 토큰과 달리 **조회를 허용**한다. 전 디바이스 공통 값이라 1회 표시 방식이면
    디바이스를 한 대 추가할 때마다 전체를 재발급해야 한다(운영 불가).
    """
    data = _ops_secret(force=True)
    cur = (data.get(OPS_KEY) or "").strip()
    prev = (data.get(OPS_KEY_PREV) or "").strip()
    env_only = not cur and bool(os.environ.get("EDGE_OPS_TOKEN", "").strip())
    return {
        "configured": bool(cur) or env_only,
        "token": cur or os.environ.get("EDGE_OPS_TOKEN", "").strip(),
        # 회전 중이면 옛 키가 아직 살아 있다 — 화면이 "교체 진행 중" 을 말할 근거.
        "rotating": bool(prev),
        "prev_token": prev,
        # Secret 이 아니라 파드 env 로만 설정된 설치는 UI 로 회전할 수 없다.
        "managed": not env_only,
        "secret_name": OPS_SECRET_NAME,
        "namespace": settings.SYSTEM_NAMESPACE,
    }


def rotate_ops_token() -> dict:
    """새 키 발급. 기존 키는 prev 로 내려 보관만 한다(플랫폼은 새 키만 사용 — 하드 컷오버)."""
    data = _ops_secret(force=True)
    cur = (data.get(OPS_KEY) or "").strip() or os.environ.get("EDGE_OPS_TOKEN", "").strip()
    new = secrets.token_urlsafe(32)
    body = {OPS_KEY: new}
    if cur:
        body[OPS_KEY_PREV] = cur
    _secret_write(settings.SYSTEM_NAMESPACE, OPS_SECRET_NAME, body)
    _ops_secret(force=True)
    return {"token": new, "rotating": bool(cur),
            "message": "새 키가 발급됐습니다. 모든 디바이스를 교체한 뒤 옛 키를 폐기하세요."}


def retire_prev_ops_token() -> dict:
    """옛 키 폐기 — 이 시점부터 교체하지 않은 디바이스는 401 이 된다."""
    data = _ops_secret(force=True)
    cur = (data.get(OPS_KEY) or "").strip()
    if not cur:
        raise Exception("현재 키가 없어 폐기할 수 없습니다")
    _secret_write(settings.SYSTEM_NAMESPACE, OPS_SECRET_NAME, {OPS_KEY: cur})
    _ops_secret(force=True)
    return {"retired": True}


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
        resp = requests.get(metrics_url, timeout=REMOTE_MANAGER_TIMEOUT,
                            allow_redirects=False, headers=_ops_headers())
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
    # 계약 v1 — 토큰이 설정돼 있으면 항상 부착한다. heartbeat 의 디바이스 토큰과는
    # **다른 방향의 자격증명**이다(저쪽이 우리를 검증한다). 값이 없으면 헤더를 빼서
    # 검증 없는 구버전 에이전트와도 그대로 동작한다.
    try:
        resp = requests.post(ops_url, json=payload, timeout=REMOTE_MANAGER_TIMEOUT,
                             allow_redirects=False, headers=_ops_headers())
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
    # 어느 워크스페이스의 어떤 양자화 산출물이 어느 디바이스에 걸렸는지는 목록 조회
    # (인가 없음)로 흘리지 않는다 — lineage_id 를 추측해 배포에 넣는 공격의 정찰 정보다.
    w.pop("deploy_lineage_id", None)
    # heartbeat 워커(토큰 발급됨)만 last_seen staleness 로 offline 파생. pull 전용
    # (remoteManager /metrics) 워커는 저장된 conn_status 유지 — 주기 폴러 부재로 인한
    # 오탐(→ SP-6 배포 셀렉터가 healthy 디바이스를 비활성화) 방지.
    if has_token:
        w["conn_status"] = _derive_conn_status(w)
    # 신선도 두 축 — conn_status 와 **분리해서** 올린다(토큰/pull 워커 공통).
    # pull-only 워커는 주기 폴러가 없어 conn_status 가 "마지막 폴링이 성공했다" 는 뜻으로
    # 고정된다. 그것만 보면 전원이 꺼진 디바이스도 영구히 online + running 으로 남는다.
    # 그렇다고 conn_status 를 뒤집으면 canOperate(= isOnline && hasRemoteUrl,
    # EdgeDeploymentDetail) 가 도달 가능한 디바이스의 배포 버튼까지 막는다 — 바로 위
    # 주석이 경고한 회귀가 그것이다. 그래서 조작 게이트는 그대로 두고 "이 값이 얼마나
    # 오래된 관측인가" 만 별도로 알려, 화면이 deploy_state 를 라이브 상태로 단정하지
    # 않게 한다. 끊긴 디바이스의 현재 상태는 원리적으로 알 수 없으므로, 아는 척하는
    # 대신 모른다고 말하는 것이 이 필드의 목적이다.
    #   · contact_stale : 디바이스와 마지막으로 연결된 지 오래됐는가(last_seen).
    #   · deploy_stale  : 배포상태를 마지막으로 **관측**한 지 오래됐는가
    #                      (deploy_observed_at). heartbeat 는 컨테이너를 보지 않으므로
    #                      이 값을 올리지 못한다 — 그래서 "연결은 살아 있는데 배포상태는
    #                      옛 관측" 이라는 흔한 상태를 화면이 구분할 수 있다.
    w["contact_stale"] = _is_stale(w)
    w["deploy_stale"] = _is_stale(w, "deploy_observed_at")
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
    # 계약 v1 — 컨테이너 목록만으로는 '아직 모델을 받는 중' 과 '실패했다' 와 '중지됐다'
    # 가 전부 '컨테이너 없음' 으로 같아 보인다. 비동기 배포(202)를 쓰는 순간 그 셋을
    # 구분하지 못하면, 다운로드 중인 워커가 화면에서 '중지됨' 으로 보이고 사용자는
    # 배포가 실패한 줄 안다. 에이전트가 명시해 주는 두 값을 컨테이너 유추보다 앞세운다.
    # 디바이스가 준 문자열이라 절단·제어문자 제거를 거친다(로그 인젝션 방어).
    reported_error = _sanitize(metrics.get("last_deploy_error"), 512).strip()
    if reported_error:
        deploy_state = "error"
    elif metrics.get("deploy_in_progress"):
        # ⚠️ '컨테이너가 없을 때만' 으로 좁히면 안 된다. 재배포는 새 모델을 먼저 받고
        # 나서 옛 컨테이너를 교체하므로, 받는 동안 /metrics 에는 **옛 컨테이너가 그대로
        # 살아 있다.** 그 경우 컨테이너 유추가 이기면 옛 모델로 running 을 새기고,
        # 배포 노드 폴러는 새 배포가 끝나기도 전에 성공으로 단정한다.
        deploy_state = "deploying"

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
        # ⚠️ 비우기("" 센티널)는 **컨테이너가 실제로 사라졌을 때만** 한다. 진행 중이거나
        # 실패한 배포에서 비우면 방금 새긴 모델명이 사라져, 무엇을 받다가/무엇이 실패했는지
        # 화면에서 알 수 없게 된다. 그 경우엔 None 을 넘겨 컬럼을 건드리지 않는다.
        deploy_model=(None if deploy_state in ("deploying", "error")
                      else _trim(deploy.get("model") or deploy.get("image"), 128) or ""),
        deploy_version=(None if deploy_state in ("deploying", "error")
                        else _trim(deploy.get("version"), 64) or ""),
        deploy_state=deploy_state,
        # 사유는 error 일 때만 새기고 그 외에는 "" 로 명시 해제한다 — 옛 실패가 화석처럼
        # 남으면 정상 배포가 계속 실패로 보인다.
        deploy_error=reported_error if deploy_state == "error" else "",
        # /metrics 가 docker ps 를 실제로 봤다 — 배포상태를 관측한 순간이다.
        deploy_observed_at=_now(),
    )
    if not ok:
        # 영속 실패를 online 성공으로 위장하지 않음.
        raise Exception("failed to persist edge worker status")
    return _worker_view(db_edge.get_edge_worker(worker_id=worker_id))


def _resolve_artifact(lineage_id: int) -> str:
    """quantize_lineage.id → 아티팩트 절대경로. 경로는 **DB 에서만** 만든다.

    클라이언트가 준 gguf_path 문자열을 신뢰 체인에서 빼기 위한 함수다. 상대경로는
    DB 값이지만 그래도 commonpath 로 jobs 베이스 이탈을 막는다(llm_model 의 커밋
    이관과 같은 가드 — 방어는 겹쳐 둔다).

    ⚠️ 실패 사유는 **ArtifactUnavailable 로 뭉쳐서** 올린다(열거 오라클 차단).
    절대경로도 싣지 않는다 — 이 예외는 device-facing 응답으로도 나가므로 경로가 새면
    기관 장비 쪽에 우리 NFS 레이아웃이 노출된다. 상세는 서버 로그에만 남는다.
    """
    def _unavailable(detail):
        print(f"[edge] artifact unavailable (lineage_id={lineage_id}): {detail}")
        return ArtifactUnavailable(detail)

    row = db_edge.get_quantize_lineage(lineage_id)
    if not row:
        raise _unavailable("lineage not found")
    if (row.get("status") or "").lower() != "completed":
        raise _unavailable(f"lineage status is {row.get('status')!r}")
    rel = row.get("gguf_path")
    if not rel:
        raise _unavailable("lineage has no file path")
    ws = db_workspace.get_workspace(workspace_id=row["workspace_id"])
    if not ws or not ws.get("main_storage_name") or not ws.get("name"):
        raise _unavailable("workspace is not resolvable")
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )
    jobs_base = os.path.realpath(os.path.join(main_root, "jobs"))
    abs_path = os.path.realpath(os.path.join(main_root, rel))
    if os.path.commonpath([abs_path, jobs_base]) != jobs_base:
        raise _unavailable("path escapes jobs base")
    if not os.path.isfile(abs_path):
        raise _unavailable("file is missing on storage")
    # SDS(VLM) 양자화 패키지는 mmproj(비전) GGUF 가 함께 있어야 동작한다 — 엣지는 아직 GGUF 1개만
    # 전달하므로(remote_manager 계약) 보내면 이미지를 못 보는 모델이 된다. 지원 전까지 거절.
    try:
        with open(os.path.join(os.path.dirname(abs_path), "metadata.json"), encoding="utf-8") as f:
            package_meta = json.load(f) or {}
    except (OSError, ValueError):
        package_meta = {}
    if isinstance(package_meta, dict) and package_meta.get("mmproj_file"):
        raise _unavailable("VLM package (mmproj) is not supported for edge deploy yet")
    return abs_path


def _platform_public_base() -> str:
    """디바이스가 우리에게 되돌아올 때 쓰는 공개 주소(스킴+호스트[:포트]).

    jfb-settings 가 이미 게이트웨이 외부 주소를 env 로 주고 있으므로(EXTERNAL_HOST /
    INGRESS_PROTOCOL / EXTERNAL_HOST_PORT — 파드에서 실측 확인) 그것을 그대로 쓴다.
    별도 값을 새로 만들면 게이트웨이 주소가 바뀔 때 두 곳이 어긋난다.
    PLATFORM_PUBLIC_BASE 를 주면 그 값이 우선한다(리버스 프록시·도메인 분리 대비).
    """
    explicit = os.environ.get("PLATFORM_PUBLIC_BASE", "").strip().rstrip("/")
    if explicit:
        return explicit
    host = os.environ.get("EXTERNAL_HOST", "").strip()
    if not host:
        return ""
    proto = os.environ.get("INGRESS_PROTOCOL", "http").strip() or "http"
    port = os.environ.get("EXTERNAL_HOST_PORT", "").strip()
    netloc = f"{host}:{port}" if port and port not in ("80", "443") else host
    return f"{proto}://{netloc}"


def _artifact_url(device_id: str):
    """디바이스가 받아갈 아티팩트 URL. 경로에 파일을 담지 않는다 — 무엇을 줄지는
    서버가 워커의 deploy_lineage_id 로 정하므로, 디바이스가 경로를 고를 여지가 없다."""
    base = _platform_public_base()
    if not base:
        return None
    return f"{base}/api/edge/devices/{device_id}/artifact"


# 디바이스별 전송량 예산. fb_resource 는 단일 레플리카라 in-process 로 충분하다 —
# 레플리카를 늘리면 Redis 로 옮겨야 한다. 게이트웨이 rate-limiting 이 라이브로 붙으면
# 그쪽이 1차 방어가 되고 이건 앱-레벨 백스톱으로 남는다.
_artifact_budget_lock = threading.Lock()
_artifact_used = {}         # device_id -> [창 시작(monotonic), 소비 바이트]


def _budget_slot(device_id):
    """현재 창을 반환(만료됐으면 새 창으로 리셋). 호출자가 락을 들고 있어야 한다."""
    now = time.monotonic()
    slot = _artifact_used.get(device_id)
    if slot is None or (now - slot[0]) >= ARTIFACT_BUDGET_WINDOW_SEC:
        slot = [now, 0]
        _artifact_used[device_id] = slot
    return slot


def artifact_budget_check(device_id: str):
    """이번 창의 소비량이 이미 한도를 넘었나 → (ok, err). 상태를 남기지 않는다.

    바이트를 흘리지 않는 요청(HEAD)용. 실제 전송은 reserve 를 쓴다.
    """
    with _artifact_budget_lock:
        if _budget_slot(device_id)[1] >= ARTIFACT_BUDGET_BYTES:
            return False, "artifact transfer budget exceeded"
        return True, None


def artifact_budget_reserve(device_id: str, nbytes: int):
    """보낼 바이트를 **미리** 예산에 넣고 통과 여부를 정한다 → (ok, err).

    ⚠️ 확인만 하고 스트리밍 중에 사후 가산하면, 같은 디바이스가 동시에 N 개 연결을
    열었을 때 전부 '아직 0 바이트' 상태에서 통과해 한도의 N 배까지 흘러간다(리뷰 지적).
    시작 시점에 선반영하면 그 창이 닫힌다. 전송이 중간에 끊기면 실제보다 많이 센
    셈이 되지만 그건 안전한 방향이고, 시간창이 지나면 저절로 회복된다.
    """
    with _artifact_budget_lock:
        slot = _budget_slot(device_id)
        if slot[1] >= ARTIFACT_BUDGET_BYTES:
            return False, "artifact transfer budget exceeded"
        slot[1] += max(0, int(nbytes))
        return True, None


def resolve_device_artifact(device_id: str, token: str):
    """device-facing 다운로드 인가 → (절대경로|None, http_status, err).

    인증은 heartbeat 와 **같은 디바이스 토큰**이고, 인가는 배포 때 새긴
    `deploy_lineage_id` 하나뿐이다. 디바이스는 무엇을 받을지 고를 수 없다.
    """
    if not verify_device_token(device_id, token):
        return None, 401, "invalid device token"
    w = db_edge.get_edge_worker(device_id=device_id)
    lineage_id = (w or {}).get("deploy_lineage_id")
    if not lineage_id:
        return None, 404, "no artifact authorized for this device"
    try:
        return _resolve_artifact(lineage_id), 200, None
    except Exception as e:
        # ArtifactUnavailable 은 사유를 뭉갠 일반 문구다(상세는 서버 로그).
        return None, 404, str(e)


def deploy_edge_worker(worker_id: int, body) -> dict:
    """양자화 포팅 패키지(GGUF)를 Edge 워커에 remoteManager /ops 로 배포 (SP-6 / 3.10).

    기관 제공 Edge 실행 이미지 + SP-4 양자화 weight(gguf_path) 주입 → remoteManager 가
    pull/create/start. 성공 시 edge_worker.deploy_*(모델/버전/running) 갱신.
    """
    with _worker_deploy_lock(worker_id):
        return _deploy_edge_worker_locked(worker_id, body)


def _deploy_edge_worker_locked(worker_id: int, body) -> dict:
    w = db_edge.get_edge_worker(worker_id=worker_id)
    if not w:
        raise Exception(f"edge worker {worker_id} not found")
    # lineage_id 가 있으면 아티팩트를 **DB 로** 해석해 다운로드 URL 을 발급한다.
    # 해석 실패는 배포를 진행시키지 않는다 — 모델 없는 컨테이너를 띄우면 화면은
    # running 인데 서빙은 안 되는 조용한 실패가 된다(파일 부재를 여기서 드러낸다).
    lineage_id = getattr(body, "lineage_id", None)
    model_url = None
    gguf_for_payload = body.gguf_path
    prev_lineage_id = w.get("deploy_lineage_id")
    if lineage_id is not None:
        # ⚠️ 구버전 에이전트는 모르는 필드(model_url)를 조용히 무시하고, 받은 적 없는
        # lineage-… 파일명으로 컨테이너를 띄운다 → 화면은 running 인데 모델이 없다.
        # 계약 v1 을 보고하는 에이전트에만 이 경로를 연다(계약이 요구하는 필드다).
        probe = _poll_remote_manager(w["remote_manager_url"])
        if not isinstance(probe, dict) or not str(probe.get("contract_version") or "").strip():
            raise Exception("디바이스 에이전트가 계약 버전(contract_version)을 보고하지 "
                            "않습니다 — 모델 수신을 지원하는 에이전트로 업그레이드가 필요합니다")
        artifact_path = _resolve_artifact(lineage_id)   # 실패 시 예외 → 배포 거절
        model_url = _artifact_url(w["device_id"])
        if not model_url:
            # ⚠️ 여기서 조용히 구버전 폴백(gguf_path 문자열만 전송)으로 흐르면 안 된다.
            # 에이전트는 model_url 이 없으면 "파일이 이미 있다" 로 해석해 다운로드를
            # 건너뛴 채 컨테이너를 띄운다 → 이 기능이 없애려던 '모델 없는 컨테이너'가
            # 그대로 재발하고, 게다가 조용하다. 설정 누락은 배포 실패로 드러낸다.
            raise Exception("플랫폼 공개 주소가 설정되지 않아 아티팩트 URL 을 발급할 수 "
                            "없습니다 (EXTERNAL_HOST 또는 PLATFORM_PUBLIC_BASE 필요)")
        # 파일명을 lineage 에 종속시킨다. 에이전트는 MODEL_DIR 아래 이 이름으로 저장하고
        # '같은 이름 + 같은 크기' 를 이미 받은 것으로 간주하는데, 같은 아키텍처를 같은
        # 방식으로 재양자화하면 basename 도 크기도 같아지는 일이 흔하다 → 옛 가중치를
        # 그대로 띄우게 된다. lineage id 를 이름에 넣으면 그 충돌이 원천적으로 없다.
        gguf_for_payload = f"lineage-{lineage_id}-{os.path.basename(artifact_path)}"
        # ⚠️ 인가는 `/ops` **전에** 새긴다. 에이전트는 202 를 돌려준 직후 곧바로
        # 아티팩트를 받으러 오므로, 저장이 뒤에 오면 콜백이 인가를 못 봐서 404 가 나거나
        # (더 나쁘게) **직전 배포의 인가를 보고 옛 모델을 받아간다**.
        if not db_edge.update_edge_worker_lineage(worker_id, lineage_id):
            raise Exception("failed to persist artifact grant")
    # None 키 제거 — remoteManager 에 explicit null override 를 보내지 않는다.
    payload = {k: v for k, v in {
        "op": "deploy",
        "image": body.image,
        "model": body.model_name,
        "version": body.model_version,
        "gguf_path": gguf_for_payload,
        "model_url": model_url,
        "params": body.params or {},
    }.items() if v is not None}
    result, code, err = _remote_ops(w["remote_manager_url"], payload)
    if result is None:
        if lineage_id is not None:
            # 지시가 나가지 못했으면 방금 연 인가를 되돌린다(열어둔 채 방치 금지).
            db_edge.update_edge_worker_lineage(worker_id, prev_lineage_id)
        raise Exception(f"deploy failed: {err}")
    # 202(Accepted=async)는 완료 단정 X → deploying. remoteManager 가 유효 status 를
    # 주면 그걸 쓰고, 아니면 200/201=running, 그 외=deploying. (실상태는 다음 /metrics 폴링이 확정)
    # ⚠️ `_remote_ops` 는 200/201/202 를 전부 통과시키므로 "전송됐다" 가 "성공했다" 가
    # 아니다. 실 에이전트는 실패를 200 + {"status":"error"} 로 돌려준다 — stop 쪽은
    # `_stop_outcome` 이 이미 그 대칭 가드를 갖고 있는데 deploy 에만 없었다. 그대로 두면
    # 라우트가 성공 envelope 를 반환해 화면은 "배포 요청됨" 토스트를 띄우고, 사유까지
    # 빈 값으로 덮여 사용자가 원인을 알 길이 없다(리뷰 지적).
    rdict = result if isinstance(result, dict) else {}
    rstate = str(rdict.get("status") or "").lower()
    if rstate == "error":
        detail = _sanitize(rdict.get("detail"), 512).strip() or "deploy rejected by device"
        db_edge.update_edge_worker_status(
            worker_id, conn_status="online", last_seen=_now(),
            deploy_state="error", deploy_error=detail, deploy_observed_at=_now())
        if lineage_id is not None:
            # 배포가 거절됐으니 방금 연 다운로드 인가도 되돌린다.
            db_edge.update_edge_worker_lineage(worker_id, prev_lineage_id)
        raise Exception(f"deploy failed: {detail}")
    if rstate in ("running", "stopped", "deploying"):
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
        # 새 배포가 시작됐으니 직전 실패 사유는 지운다.
        deploy_error="",
        # /ops 가 응답했다 — 확정(running)이든 비확정(deploying)이든 방금 관측한 값이다.
        deploy_observed_at=_now(),
        # deploy_lineage_id 는 위에서 /ops 전에 이미 새겼다(경쟁 방지) — 여기서 다시
        # 쓰지 않는다.
    )
    if not ok:
        raise Exception("failed to persist deploy status")
    return {
        "worker_id": worker_id,
        "device_id": w["device_id"],
        "model": body.model_name,
        "version": body.model_version,
        "image": body.image,
        "gguf_path": gguf_for_payload,
        "model_url": model_url,
        "deploy_state": deploy_state,
        # 디바이스 원본 응답을 그대로 싣지 않는다 — 이 파일의 다른 디바이스 제공
        # 문자열은 모두 _sanitize 를 거친다(길이 상한 + 제어문자 제거).
        "remote_manager_status": _sanitize(rdict.get("status"), 32),
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
        # 중지가 확인됐으니 옛 실패 사유도 함께 지운다 — refresh·deploy 는 이미 그렇게
        # 하는데 stop 만 빠져 있어 죽은 사유가 DB 에 남았다(리뷰 지적).
        deploy_error="",
        # 디바이스가 stopped 를 확인해줬다 — 관측 시점 갱신.
        deploy_observed_at=_now(),
    )
    if not ok:
        raise Exception("failed to persist stop status")
    return {
        "worker_id": worker_id,
        "device_id": w["device_id"],
        "deploy_state": "stopped",
        "remote_manager_status": _sanitize(
            (result if isinstance(result, dict) else {}).get("status"), 32),
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
