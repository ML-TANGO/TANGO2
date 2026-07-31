"""
Kong Admin API 헬퍼 — 클러스터 배포 API 게시용 (SP-Deployment D6 §12).

fb_ingress_management(service.py/admin_api.py)의 consumer/key-auth/route-plugin
로직을 공유 모듈로 추출. 배포 서빙은 이미 Kong ingress route(`/deployment/{api_path}`)로
노출돼 있으나 그 route 는 내부 채팅도 익명으로 쓰므로 건드리지 않는다.
게시 = 같은 Kong service 를 가리키는 **전용 route**(`/ext/{api_path}`) 신설 + 거기에만
strict key-auth plugin 부착 + consumer/key 발급(외부 소비자=키 필수). = 라우트 분리.

키 원본은 저장하지 않고 Kong 에서 fetch 한다(get_key_auth). consumer 는 배포별 격리
(`dep-{deployment_id}`). key_names 는 플랫폼 관례(`apikey`)와 일치.
"""
import requests
from typing import Optional

from utils.settings import (
    JF_KONG_ADMIN_DNS,
    JF_KONG_ADMIN_HTTP_PORT,
)

KONG_ADMIN_URL = f"http://{JF_KONG_ADMIN_DNS}:{JF_KONG_ADMIN_HTTP_PORT}"
KEY_AUTH = "key-auth"
# 외부 호출 시 키 전달 위치(헤더/쿼리 `apikey`). 플랫폼의 ?apikey= 관례와 일치.
KEY_NAMES = ["apikey"]


def _request(method, path, json=None, params=None, ok_404=False, ok_409=False, timeout=10):
    """Kong Admin API 호출. ok_404=True 면 404 를 None 으로 반환(존재 확인용).
    ok_409=True 면 409(중복/충돌) 를 raise 없이 resp 로 반환(동시 생성 멱등 처리용)."""
    url = f"{KONG_ADMIN_URL}{path}"
    resp = requests.request(method.upper(), url, json=json, params=params, timeout=timeout)
    if ok_404 and resp.status_code == 404:
        return None
    if ok_409 and resp.status_code == 409:
        return resp
    resp.raise_for_status()
    return resp


# ── consumer ──
def get_or_create_consumer(username: str) -> None:
    if _request("get", f"/consumers/{username}", ok_404=True) is None:
        _request("post", "/consumers", json={"username": username})


def delete_consumer(username: str) -> None:
    _request("delete", f"/consumers/{username}", ok_404=True)


# ── service ──
def get_or_create_service(name: str, url: str):
    """이름이 같은 upstream service를 재사용하고 없으면 만든다. (service_id, created_now) 반환."""
    existing = _request("get", f"/services/{name}", ok_404=True)
    if existing is not None:
        return existing.json()["id"], False
    resp = _request(
        "post", "/services", json={"name": name, "url": url}, ok_409=True)
    if resp.status_code == 409:
        existing = _request("get", f"/services/{name}")
        return existing.json()["id"], False
    return resp.json()["id"], True


def delete_service(name_or_id: str) -> None:
    """전용 route 삭제 뒤 호출하는 service 멱등 정리."""
    _request("delete", f"/services/{name_or_id}", ok_404=True)


# ── key-auth (API key) ──
def get_key_auth(username: str) -> Optional[str]:
    resp = _request("get", f"/consumers/{username}/key-auth", ok_404=True)
    if resp is None:
        return None
    data = resp.json().get("data", [])
    return data[0].get("key") if data else None


def create_key_auth(username: str) -> str:
    body = _request("post", f"/consumers/{username}/key-auth", json={}).json()
    key = body.get("key")
    if not key:
        raise RuntimeError("Kong key-auth response missing 'key'")
    return key


def get_or_create_key_auth(username: str) -> str:
    return get_key_auth(username) or create_key_auth(username)


def delete_key_auths(username: str, except_id: Optional[str] = None) -> None:
    resp = _request("get", f"/consumers/{username}/key-auth", ok_404=True)
    if resp is None:
        return
    for cred in resp.json().get("data", []):
        cid = cred.get("id")
        if cid and cid != except_id:
            _request("delete", f"/consumers/{username}/key-auth/{cid}")


def rotate_key_auth(username: str) -> str:
    """새 키 발급 후 기존 키들 삭제(새 키 제외) — 0-key 윈도우 방지(N4)."""
    body = _request("post", f"/consumers/{username}/key-auth", json={}).json()
    new_id, new_key = body.get("id"), body.get("key")
    if not new_key:
        raise RuntimeError("Kong key-auth response missing 'key'")
    delete_key_auths(username, except_id=new_id)
    return new_key


# ── route 조회 (ingress 가 만든 route) ──
def find_route_id_by_path(path_prefix: str) -> Optional[str]:
    """paths 에 path_prefix 를 포함하는 Kong route 의 id. offset 페이지네이션."""
    params = {"size": 100}
    while True:
        body = _request("get", "/routes", params=params).json()
        for route in body.get("data", []):
            for p in (route.get("paths") or []):
                if p.rstrip("/") == path_prefix.rstrip("/"):
                    return route["id"]
        offset = body.get("offset")
        if not offset:
            return None
        params = {"size": 100, "offset": offset}


def find_route_id_by_name(name: str) -> Optional[str]:
    """name 이 일치하는 Kong route 의 id. offset 페이지네이션.
    게시 route(ext-dep-{id})를 배포/api_path 소실 후에도 찾기 위함(teardown fallback·orphan sweep)."""
    params = {"size": 100}
    while True:
        body = _request("get", "/routes", params=params).json()
        for route in body.get("data", []):
            if route.get("name") == name:
                return route["id"]
        offset = body.get("offset")
        if not offset:
            return None
        params = {"size": 100, "offset": offset}


def list_routes() -> list:
    """모든 Kong route(full dict, name·created_at 포함). offset 페이지네이션. orphan sweep 용."""
    out, params = [], {"size": 100}
    while True:
        body = _request("get", "/routes", params=params).json()
        out.extend(body.get("data", []))
        offset = body.get("offset")
        if not offset:
            return out
        params = {"size": 100, "offset": offset}


# ── key-auth plugin (route 에 부착 = 외부 호출 시 키 필수) ──
def get_key_auth_plugin_id(route_id: str) -> Optional[str]:
    """route 의 key-auth plugin id. offset 페이지네이션(plugin 다수 대비, H1)."""
    params = {"size": 100}
    while True:
        body = _request("get", f"/routes/{route_id}/plugins", params=params).json()
        for pl in body.get("data", []):
            if pl.get("name") == KEY_AUTH:
                return pl["id"]
        offset = body.get("offset")
        if not offset:
            return None
        params = {"size": 100, "offset": offset}


def attach_key_auth_plugin(route_id: str) -> str:
    """route 에 key-auth plugin 부착(멱등). 외부 소비자는 이후 키 필수."""
    existing = get_key_auth_plugin_id(route_id)
    if existing:
        return existing
    return _request(
        "post",
        f"/routes/{route_id}/plugins",
        json={"name": KEY_AUTH, "config": {"key_names": KEY_NAMES}},
    ).json()["id"]


def remove_key_auth_plugin(route_id: str) -> None:
    pid = get_key_auth_plugin_id(route_id)
    if pid:
        _request("delete", f"/routes/{route_id}/plugins/{pid}")


# ── route 생성/삭제 (게시 전용 라우트 = 내부 서빙 route 와 분리) ──
# 내부 채팅이 쓰는 공유 route(/deployment/{api_path}) 에 key-auth 를 붙이면 채팅이 401 되므로,
# 같은 upstream(Kong service)을 가리키는 **별개 route** 를 만들어 거기에만 key-auth 를 건다.
# 게시 route 는 비-`/api` 경로여야 fb_ingress_management 리콘사일러(5s)의 generic key-auth
# 덮어쓰기를 피한다. KIC 는 태그 스코프(managed-by-ingress-controller)라 untagged route 는
# 프루닝하지 않음(라이브 검증 완료).
def get_route(route_id: str) -> Optional[dict]:
    resp = _request("get", f"/routes/{route_id}", ok_404=True)
    return resp.json() if resp is not None else None


def get_route_service_id(route_id: str) -> Optional[str]:
    """route 가 물린 Kong service id — 게시 route 를 같은 service 에 붙이기 위함."""
    route = get_route(route_id)
    if not route:
        return None
    svc = route.get("service") or {}
    return svc.get("id")


def _repoint_route_service(route_id: str, service_id: str) -> None:
    """route 의 service 참조가 바뀌었으면(배포 재시작으로 새 Kong service) 재지정.
    재게시 시 옛 route 가 죽은 service 를 가리켜 502 나는 것 방지."""
    route = get_route(route_id)
    cur = ((route or {}).get("service") or {}).get("id")
    if cur != service_id:
        _request("patch", f"/routes/{route_id}", json={"service": {"id": service_id}})


def create_route_on_service(service_id: str, path: str, name: Optional[str] = None,
                            strip_path: bool = True):
    """service 에 route 생성. (route_id, created_now) 반환. untagged → KIC 프루닝 안 됨.
    - 같은 path route 존재 시 재사용 + service 참조가 바뀌었으면 repoint(재시작 대응). created_now=False.
    - 동시 publish name 충돌(409) 도 재조회로 흡수(멱등). created_now=False.
    created_now 는 호출측 롤백이 '이 호출이 만든 것'만 지우도록 하기 위함(동시 요청 자원 보존)."""
    existing = find_route_id_by_path(path)
    if existing:
        _repoint_route_service(existing, service_id)
        return existing, False
    body = {"paths": [path], "strip_path": strip_path}
    if name:
        body["name"] = name
    resp = _request("post", f"/services/{service_id}/routes", json=body, ok_409=True)
    if resp.status_code == 409:  # 동시 생성/이름 충돌 — 이미 만들어진 route 재사용(멱등)
        rid = find_route_id_by_path(path)
        if rid:
            _repoint_route_service(rid, service_id)
            return rid, False
        resp.raise_for_status()  # 409 인데 path 로 못 찾음 → 원 에러 표면화
    return resp.json()["id"], True


def delete_route(route_id: str) -> None:
    """route 삭제(멱등). 부착 plugin 도 Kong 이 함께 제거."""
    _request("delete", f"/routes/{route_id}", ok_404=True)


# ── ACL (consumer group 스코핑) ──
# key-auth 는 '이 Kong 의 유효 키인가'만 검증 → 모든 플랫폼 유저 키가 통과(교차테넌트 우회).
# acl plugin(allow=[group]) 을 페어링해 route 를 소유 consumer 의 group 으로 제한한다.
# (기존 apply_acl_to_route 패턴과 동형. 여기선 배포별 1:1 group = consumer 이름.)
def add_consumer_to_acl_group(username: str, group: str) -> None:
    """consumer 를 ACL group 에 추가(멱등: 이미 있으면 409 무시)."""
    _request("post", f"/consumers/{username}/acls", json={"group": group}, ok_409=True)


def get_plugin_id(route_id: str, name: str) -> Optional[str]:
    """route 의 특정 plugin id(offset 페이지네이션)."""
    params = {"size": 100}
    while True:
        body = _request("get", f"/routes/{route_id}/plugins", params=params).json()
        for pl in body.get("data", []):
            if pl.get("name") == name:
                return pl["id"]
        offset = body.get("offset")
        if not offset:
            return None
        params = {"size": 100, "offset": offset}


def attach_acl_plugin(route_id: str, group: str) -> str:
    """route 에 acl plugin 부착(멱등, allow=[group]). key-auth 와 페어링 = 소유 consumer 만 허용."""
    existing = get_plugin_id(route_id, "acl")
    if existing:
        return existing
    return _request("post", f"/routes/{route_id}/plugins",
                    json={"name": "acl", "config": {"allow": [group]}}).json()["id"]


def attach_plugin(route_id: str, name: str, config: dict) -> str:
    """route 에 임의 plugin 부착(멱등: 이미 있으면 기존 id 반환).

    게시(D6) route 남용가드(rate-limiting / request-size-limiting) 등 config 가
    plugin 마다 다른 경우를 위한 generic 부착기. route 삭제 시 함께 제거(cascade).
    """
    existing = get_plugin_id(route_id, name)
    if existing:
        return existing
    return _request("post", f"/routes/{route_id}/plugins",
                    json={"name": name, "config": config}).json()["id"]
