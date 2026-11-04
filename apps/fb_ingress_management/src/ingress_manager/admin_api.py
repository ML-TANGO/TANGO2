import requests
import time
import sys
import traceback
import json
import re
from typing import Optional, Dict, Any, List
from utils.settings import JF_KONG_ADMIN_DNS, JF_KONG_ADMIN_HTTP_PORT
from utils.msa_db import db_user, db_project, db_prepro

# ==========================================
# 🔧 MODE 설정 - 파일변경 감지 또는 앱재시작 시에 자동 반영
# ==========================================
DEBUG_MODE = False  # 🔄 여기서 True/False 변경
IS_DEV=False   # if True, 개발중 -> cross site 요청 허용

# 🔐 보안 설정
ALLOW_ALL_ROUTES = False  # 🔄 모든 경로 접근 허용 (개발/테스트용)
                          # True: 모든 보안 플러그인 제거, 전체 접근 허용
                          # False: ALLOWED_PATH 및 보안 정책 적용

ACL_ENABLED = False  # 🔄 ACL 플러그인 기능 활성화/비활성화
                    # True: 프로젝트별 접근 권한 제어 활성화
                    # False: 모든 ACL 설정 제거 및 비활성화
# ==========================================

def debug_log(message):
    """디버그 모드일 때만 로그 출력"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr)

KONG_ADMIN_URL = f"http://{JF_KONG_ADMIN_DNS}:{JF_KONG_ADMIN_HTTP_PORT}"
# KONG_ADMIN_URL = f"https://{JF_KONG_ADMIN_DNS}:8444"

# IDLING_TIMEOUT=86400  # 24h
# IDLING_TIMEOUT=21600  # 4h
IDLING_TIMEOUT=25920000  # 300d
# ROLLING_TIMEOUT=7200
ABSOLUTE_TIMEOUT=25920000 # 300d


BASE_SESSION_CONFIG = {
    "cookie_secure": False,  # False -> HTTP 허용
    "cookie_same_site": "None" if IS_DEV else "Lax",  # Strict(금지), Lax(일부 허용), None
    "cookie_http_only" : True,
    "idling_timeout": IDLING_TIMEOUT,  # 비활성 세션 유지 시간
    # "rolling_timeout": ROLLING_TIMEOUT,  # 요청 시마다 갱신
    "absolute_timeout": ABSOLUTE_TIMEOUT  # 무조건 로그아웃
}

ANONYMOUS_USER_ID=""
ALLOWED_PATH = [
    "/",  # 프론트(루트)
    "/api/(login|logout)(.*)/",
    "/api/users/register/",
    "/api/users/check/",
    # SP-8 §5.3 — 엣지 device heartbeat: 기관 디바이스가 자체 Bearer 토큰으로 호출(Kong
    # consumer 아님) → key-auth 면제. 백엔드(fb_resource) 토큰 검증이 실 게이트이고,
    # rate-limiting/request-size-limiting(edge-device-plugins.yaml)로 익명 표면 방어.
    # ⚠️ 실 device 연동(2차년도) 시 활성. apply 시 라이브 Kong route path 문자열과
    # 정확히 일치하는지 확인(GET {admin}/routes 의 paths) — 아래는 -device-api 인그레스 기준.
    "/api/edge/devices(.*)/",

    # Marker용 임시 허용 경로들
    # "/api/(workspaces)(.*)/",
    # "~/api/(workspaces)(.*)$",
    # "/api/(deployments|services)(.*)/",
    # "~/api/(deployments|services)(.*)$",
]

def kong_api_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30
) -> requests.Response:
    """
    Wrapper function for Kong Admin API requests.
    
    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE, etc.).
        url (str): Target URL or endpoint.
        headers (Optional[Dict[str, str]]): HTTP headers to include in the request.
        params (Optional[Dict[str, Any]]): Query parameters for the request.
        data (Optional[Dict[str, Any]]): Form-encoded data to send in the request body.
        json (Optional[Dict[str, Any]]): JSON data to send in the request body.
        timeout (int): Request timeout in seconds (default: 30).
    
    Returns:
        requests.Response: The response object from the request.
    """
    # Map HTTP methods to requests functions
    method = method.lower()
    func_map = {
        "get": requests.get,
        "post": requests.post,
        "put": requests.put,
        "delete": requests.delete,
        "patch": requests.patch
    }
    
    # Select the appropriate function based on the method
    func = func_map.get(method)
    if not func:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    # Perform the request
    try:
        response = func(
            url=url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
            # verify=False  # SSL 인증서 검증 건너뛰기
        )
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        return response
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP error during {method.upper()} request to {url}: {e.response.status_code} {e.response.text}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Error during {method.upper()} request to {url}: {e}") from e
    
def kong_get_resources(resource_name):
    response = kong_api_request(
                method="GET",
                url=f"{KONG_ADMIN_URL}/{resource_name}"
                )
    return response.json().get("data", [])
    
def kong_health_check():
    response = kong_api_request(
            method="GET",
            url=f"{KONG_ADMIN_URL}/status"
    )
    
    if response.status_code in [201, 200]:
        return True
    return False

def kong_sync_user_to_consumer():
    
    user_list = db_user.get_user_list()  # TODO: DNS 요청식으로 변경
    users = [item["name"] for item in user_list]
    users.append("anonymous-user") # MUST BE PRESENT

    consumers_raw = kong_get_resources("consumers")
    consumers = [consumer["username"] for consumer in consumers_raw if "username" in consumer]
    # print("res:", response.json(), file=sys.stderr)

    new_users = list(set(users) - set(consumers))
    

    for new_user in new_users:
        try:
            response = kong_api_request(
                method="POST",
                url=f"{KONG_ADMIN_URL}/consumers",
                json={"username": new_user}
            )
            if response.status_code in [201, 200]:
                print(f"Consumer {new_user} created.", file=sys.stderr)
        except Exception as e:
            print(f"Failed to create consumer {new_user}: {e}", file=sys.stderr)

    old_users = list(set(consumers) - set(users))
    # 게시(D6) 전용 consumer(dep-<id>)는 DB user 가 아니지만 publish_deployment_api 가 관리한다.
    # 제외하지 않으면 이 동기화가 ~5s 루프마다 삭제 → key-auth 크리덴셜 cascade 소멸 → 게시 키 401.
    # unpublish_deployment_api 에서만 삭제된다.
    old_users = [u for u in old_users if not (u.startswith("dep-") and u[4:].isdigit())]
    if len(old_users) or len(new_users):
        print(f"[SYNC User] Create: {new_users} |  Remove: {old_users}", file=sys.stderr)

    for old_user in old_users:
        try:
            response = kong_api_request(
                method="DELETE",
                url=f"{KONG_ADMIN_URL}/consumers/{old_user}"
            )
            if response.status_code == 204:
                print(f"Consumer {old_user} deleted.", file=sys.stderr)
        except Exception as e:
            print(f"Failed to delete consumer {old_user}: {e}", file=sys.stderr)


def kong_check_routes():
    """
    Key-auth plugin 추가 (config.anonymous: anonymous-user)
    """
    try:
        print("[ROUTE_CHECK] Starting route check...", file=sys.stderr)
        
        def create_key_auth_plugin(route_id, anonymous_id):
            """key-auth 플러그인 생성"""
            if not anonymous_id:
                print(f"Cannot create key-auth plugin: invalid anonymous ID", file=sys.stderr)
                return
                
            response = kong_api_request(
                method="POST",
                url=f"{KONG_ADMIN_URL}/routes/{route_id}/plugins",
                json={
                    "name": "key-auth",
                    "config": {
                        "anonymous": anonymous_id
                    }
                }
            )

            if response.status_code in [201, 200]:
                print("key-auth 플러그인 생성 완료")
            else:
                print(f"key-auth 플러그인 생성 실패: {response.status_code}, {response.text}")

        def update_key_auth_plugin(plugin_id, anonymous_id):
            """key-auth 플러그인 업데이트"""
            response = kong_api_request(
                method="PATCH",
                url=f"{KONG_ADMIN_URL}/plugins/{plugin_id}",
                json={
                    "config": {
                        "anonymous": anonymous_id
                    }
                }
            )

            if response.status_code in [200, 201]:
                print("key-auth 플러그인 업데이트 완료")
            else:
                print(f"key-auth 플러그인 업데이트 실패: {response.status_code}, {response.text}")

        def check_and_update_key_auth_plugin(route_id, plugins, anonymous_id):
            """key-auth 플러그인이 있고 anonymous가 올바르게 설정되었는지 확인"""
            if not anonymous_id:
                print(f"Cannot check key-auth plugin: invalid anonymous ID", file=sys.stderr)
                return
                
            for plugin in plugins:
                if plugin.get("name") == "key-auth":
                    config = plugin.get("config", {})
                    if config.get("anonymous") == anonymous_id:
                        return
                    else:
                        print("key-auth 플러그인의 anonymous 설정이 잘못됨 → 수정 필요")
                        update_key_auth_plugin(plugin["id"], anonymous_id)
                        return

            print("key-auth 플러그인이 없음 → 새로 생성")
            create_key_auth_plugin(route_id, anonymous_id)

        def create_request_termination_plugin(route_id, consumer_id):
            """request-termination 플러그인 생성"""
            if not consumer_id:
                print(f"Cannot create request-termination plugin: invalid consumer ID", file=sys.stderr)
                return
                
            response = kong_api_request(
                method="POST",
                url=f"{KONG_ADMIN_URL}/routes/{route_id}/plugins",
                json={
                        "name": "request-termination",
                        "consumer": {"id": consumer_id},
                        "config": {
                            "status_code": 403,
                        }
                }
            )

            if response.status_code in [201, 200]:
                print("request-termination 플러그인 생성 완료")
            else:
                print(f"request-termination 플러그인 생성 실패: {response.status_code}, {response.text}")

        def update_request_termination_plugin(plugin_id, consumer_id):
            """request-termination 플러그인 업데이트"""
            response = kong_api_request(
                method="PATCH",
                url=f"{KONG_ADMIN_URL}/plugins/{plugin_id}",
                json={
                    "consumer": {"id": consumer_id},
                    "config": {
                        "status_code": 403,
                    }
                }
            )

            if response.status_code in [200, 201]:
                print("request-termination 플러그인 업데이트 완료")
            else:
                print(f"request-termination 플러그인 업데이트 실패: {response.status_code}, {response.text}")

        def check_and_update_request_termination_plugin(route_id, plugins, consumer_id):
            """request-termination 플러그인이 있고 consumer가 anonymous-user로 설정되었는지 확인"""
            if not consumer_id:
                print(f"Cannot check request-termination plugin: invalid consumer ID", file=sys.stderr)
                return
                
            for plugin in plugins:
                if plugin.get("name") == "request-termination":
                    if plugin.get("consumer", {}).get("id") == consumer_id:
                        return
                    else:
                        print("request-termination 플러그인의 consumer 설정이 잘못됨 → 수정 필요")
                        update_request_termination_plugin(plugin["id"], consumer_id)
                        return

            print("request-termination 플러그인이 없음 → 새로 생성")
            create_request_termination_plugin(route_id, consumer_id)




        def display_routes_with_plugins():
            """Routes와 적용된 플러그인 출력"""
            print("[ROUTE_CHECK] Fetching routes and plugins for display...", file=sys.stderr)
            try:
                routes = kong_get_resources("routes")
                plugins = kong_get_resources("plugins")
                print(f"[ROUTE_CHECK] Found {len(routes)} routes and {len(plugins)} plugins", file=sys.stderr)
                
                # None 체크 추가 (오류 방지)
                plugin_map = {p["route"]["id"]: [] for p in plugins if p.get("route") and "id" in p["route"]}
                
                for p in plugins:
                    if p.get("route") and "id" in p["route"]:  # 안전한 체크
                        plugin_map[p["route"]["id"]].append(p["name"])
                
                print("\n========== Kong Routes & Plugins ==========", file=sys.stderr)
                for r in routes:
                    try:
                        route_name = r.get("name", "Unnamed Route")
                        if "." in route_name:
                            route_name = route_name.split(".")[1]
                        route_id = r["id"]
                        applied_plugins = ", ".join(plugin_map.get(route_id, ["None"]))
                        print(f"🔹 {route_name} → {applied_plugins}", file=sys.stderr)
                    except Exception as e:
                        print(f"[ROUTE_CHECK] Error processing route {r.get('name', 'unknown')}: {e}", file=sys.stderr)
                print("===========================================\n", file=sys.stderr)
            except Exception as e:
                print(f"[ROUTE_CHECK] Error in display_routes_with_plugins: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
            
        # Anonymous User ID 확인
        print("[ROUTE_CHECK] Getting anonymous user ID...", file=sys.stderr)
        global ANONYMOUS_USER_ID
        if ANONYMOUS_USER_ID == "":
            try:
                response = kong_api_request(
                        method="GET",
                        url=f"{KONG_ADMIN_URL}/consumers/anonymous-user"
                )
                ANONYMOUS_USER_ID = response.json().get("id")
                print(f"[ROUTE_CHECK] Anonymous user ID: {ANONYMOUS_USER_ID}", file=sys.stderr)
            except Exception as e:
                print(f"[ROUTE_CHECK] Failed to get anonymous user ID: {e}", file=sys.stderr)
                print("[ROUTE_CHECK] Attempting to create anonymous-user consumer...", file=sys.stderr)
                try:
                    # Try to create the anonymous user
                    create_response = kong_api_request(
                        method="POST",
                        url=f"{KONG_ADMIN_URL}/consumers",
                        json={"username": "anonymous-user"}
                    )
                    if create_response.status_code in [201, 200]:
                        ANONYMOUS_USER_ID = create_response.json().get("id")
                        print(f"[ROUTE_CHECK] Anonymous user created with ID: {ANONYMOUS_USER_ID}", file=sys.stderr)
                    else:
                        print(f"[ROUTE_CHECK] Failed to create anonymous user: {create_response.status_code} {create_response.text}", file=sys.stderr)
                        return  # Skip route processing if we can't get anonymous user
                except Exception as create_e:
                    print(f"[ROUTE_CHECK] Error creating anonymous user: {create_e}", file=sys.stderr)
                    return  # Skip route processing if we can't get anonymous user
        
        # Verify we have a valid anonymous user ID before proceeding
        if not ANONYMOUS_USER_ID:
            print("[ROUTE_CHECK] No valid anonymous user ID available, skipping route processing", file=sys.stderr)
            return

        # Routes별 플러그인 목록 확인
        print("[ROUTE_CHECK] Processing routes...", file=sys.stderr)
        routes = kong_get_resources("routes")
        print(f"[ROUTE_CHECK] Processing {len(routes)} routes", file=sys.stderr)
        
        processed_routes = 0
        
        for route in routes:
            route_id = route.get("id", "")
            paths = route.get("paths", [])

            # 전체 허용 모드 체크
            if ALLOW_ALL_ROUTES:
                # 모든 경로 허용: 기존 보안 플러그인들 제거
                response = kong_api_request(
                        method="GET",
                        url=f"{KONG_ADMIN_URL}/routes/{route_id}/plugins"
                )
                plugins = response.json().get("data", [])
                
                try:
                    kong_remove_security_plugins_from_route(route_id, plugins)
                except Exception as e:
                    print(f"Error removing security plugins from route {route_id}: {e}", file=sys.stderr)
                continue
            
            # 현재 경로가 허용된 경로인지 확인
            is_allowed_path = any(p in ALLOWED_PATH for p in paths)
            
            # /api로 시작하는 경로가 있는지 확인 (보안 플러그인 대상)
            has_api_path = any(p.startswith("/api") for p in paths)
            
            # API 경로가 아니면 스킵 (grafana, prometheus, filebrowser 등)
            if not has_api_path:
                continue

            # 현재 route의 플러그인 상태 확인
            response = kong_api_request(
                    method="GET",
                    url=f"{KONG_ADMIN_URL}/routes/{route_id}/plugins"
            )
            plugins = response.json().get("data", [])

            if is_allowed_path:
                # 허용된 경로: 보안 플러그인들이 있다면 제거
                try:
                    kong_remove_security_plugins_from_route(route_id, plugins)
                except Exception as e:
                    print(f"Error removing security plugins from route {route_id}: {e}", file=sys.stderr)
            else:
                # 보안이 필요한 경로: 보안 플러그인들 추가/업데이트
                processed_routes += 1
                
                try:
                    check_and_update_key_auth_plugin(route_id, plugins, ANONYMOUS_USER_ID)
                except Exception as e:
                    print(f"Error updating key-auth plugin for route {route_id}: {e}", file=sys.stderr)
                
                try:
                    check_and_update_request_termination_plugin(route_id, plugins, ANONYMOUS_USER_ID)
                except Exception as e:
                    print(f"Error updating request-termination plugin for route {route_id}: {e}", file=sys.stderr)
        
        print(f"[ROUTE_CHECK] Processed {processed_routes} routes with plugins", file=sys.stderr)
        print("[ROUTE_CHECK] Displaying routes and plugins...", file=sys.stderr)
        display_routes_with_plugins()
        print("[ROUTE_CHECK] Route check completed", file=sys.stderr)
        
    except Exception as e:
        print(f"[ROUTE_CHECK] Error in kong_check_routes: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def kong_remove_security_plugins_from_route(route_id, plugins):
    """허용된 경로에서 보안 플러그인들을 제거"""
    security_plugins = ["key-auth", "request-termination"]
    removed_plugins = []
    
    for plugin in plugins:
        plugin_name = plugin.get("name")
        if plugin_name in security_plugins:
            try:
                kong_api_request(
                    method="DELETE",
                    url=f"{KONG_ADMIN_URL}/plugins/{plugin['id']}"
                )
                removed_plugins.append(plugin_name)
                debug_log(f"Removed {plugin_name} plugin from route {route_id}")
            except Exception as e:
                print(f"Failed to remove {plugin_name} plugin from route {route_id}: {e}", file=sys.stderr)
    
    if removed_plugins:
        print(f"[ALLOWED_PATH] 허용된 경로에서 보안 플러그인 제거: {', '.join(removed_plugins)}", file=sys.stderr)

def kong_check_plugin():
    """ Session Plugin이 전역에 있는지 확인하고, 없으면 생성하고, 설정이 다르면 업데이트함 """
    plugins = kong_get_resources("plugins")

    # Session Plugin이 있는지 확인
    session_plugin = next((p for p in plugins if p.get("name") == "session"), None)

    if session_plugin:
        # 기존 설정 가져오기
        plugin_id = session_plugin["id"]
        existing_config = session_plugin.get("config", {})

        update_config = {
            key: value
            for key, value in BASE_SESSION_CONFIG.items()
            if existing_config.get(key) != value
        }

        if update_config:
            # PATCH 요청 (설정 업데이트)
            response = kong_api_request(
                method="PATCH",
                url=f"{KONG_ADMIN_URL}/plugins/{plugin_id}",
                json={"config": BASE_SESSION_CONFIG}
            )

            if response and response.status_code == 200:
                print(f"Session plugin updated: {plugin_id} using config={BASE_SESSION_CONFIG}", file=sys.stderr)
            else:
                print("Session Plugin PATCH 요청 실패", file=sys.stderr)
    else:
        # Plugin이 없는 경우 새로 생성
        print("Session Plugin이 없으므로 생성합니다.", file=sys.stderr)

        response = kong_api_request(
            method="POST",
            url=f"{KONG_ADMIN_URL}/plugins",
            json={
                "name": "session",
                "config": BASE_SESSION_CONFIG
            }
        )

        # if response and response.status_code in [200, 201]:
            # print(f"Session plugin created with idling_timeout={IDLING_TIMEOUT}, rolling_timeout={ROLLING_TIMEOUT}, absolute_timeout={ABSOLUTE_TIMEOUT}", file=sys.stderr)
        # else:
        #     print("Session Plugin 생성 실패", file=sys.stderr)
    # Session Plugin 전역 적용
    # plugins = kong_get_resources("plugins")
    # # session plugin 확인
    # if all(plugin.get("name") != "session" for plugin in plugins):
    #     response = kong_api_request(
    #         method="POST",
    #         url=f"{KONG_ADMIN_URL}/plugins",
    #         # TODO: 수치 정하기
    #         json={
    #             "name": "session",
    #             "config": {
    #                 "cookie_secure": False,   # HTTP도 허용
    #                 "cookie_same_site": None,
    #                 "idling_timeout": IDLING_TIMEOUT,   # 비활성 상태 세션 유지
    #                 "rolling_timeout": ROLLING_TIMEOUT,
    #                 "absolute_timeout": ABSOLUTE_TIMEOUT  # 무조건 로그아웃
    #             }
    #         }
    #     )
    #     if response.status_code == 201:
    #         print(f"Session plugin created. idling_timeout={IDLING_TIMEOUT}, rolling_timeout={ROLLING_TIMEOUT}, absolute_timeout={ABSOLUTE_TIMEOUT}", file=sys.stderr)



def delete_all_plugins():
    """모든 플러그인 삭제"""
    plugins = kong_get_resources("plugins")

    if not plugins:
        print("삭제할 플러그인이 없습니다.", file=sys.stderr)
        return

    plugin_count = len(plugins)
    print(f"[PLUGIN_RESET] 기존 플러그인 {plugin_count}개 삭제 중...", file=sys.stderr)
    
    deleted_count = 0
    for plugin in plugins:
        try:
            kong_api_request(
                method="DELETE",
                url=f"{KONG_ADMIN_URL}/plugins/{plugin['id']}"
            )
            deleted_count += 1
            debug_log(f"Plugin {plugin.get('name', 'unknown')} ({plugin['id']}) deleted")
        except Exception as e:
            print(f"Failed to delete plugin {plugin.get('name', 'unknown')} ({plugin['id']}): {e}", file=sys.stderr)
    
    print(f"[PLUGIN_RESET] 플러그인 삭제 완료: {deleted_count}/{plugin_count}", file=sys.stderr)

def kong_initialize_on_startup():
    """
    앱 시작 시 Kong 초기화 작업 수행
    - 현재 설정과 다른 부분만 자동으로 반영
    - 스마트한 동기화 (변경된 부분만 처리)
    """
    try:
        print("[STARTUP] Kong 설정 동기화 시작...", file=sys.stderr)
        
        # 전체 허용 모드 확인
        if ALLOW_ALL_ROUTES:
            print("🚨 [WARNING] ALLOW_ALL_ROUTES=True - 모든 경로 접근 허용 모드 (개발/테스트용)", file=sys.stderr)
            print("🔓 모든 보안 플러그인이 제거되고 전체 접근이 허용됩니다.", file=sys.stderr)
        
        # Session 플러그인 확인/설정 (변경된 부분만 업데이트)
        kong_check_plugin()
        
        # Consumer 동기화 (새/삭제된 사용자만 처리)
        kong_sync_user_to_consumer()
        
        # ACL 설정 (플래그 확인)
        if ACL_ENABLED:
            print("[STARTUP] ACL 기능 활성화됨 - Consumer ACL 동기화 수행", file=sys.stderr)
            kong_sync_consumer_acl_groups()
        else:
            print("[STARTUP] ACL 기능 비활성화됨 - 기존 ACL 설정 정리", file=sys.stderr)
            kong_cleanup_acl_when_disabled()
        
        # Route 플러그인 확인 (필요한 것만 추가/수정)
        kong_check_routes()
        
        # ACL Route 설정 (변경된 그룹만 업데이트)
        if ACL_ENABLED:
            kong_auto_apply_acl_to_routes()
        
        print("[STARTUP] Kong 설정 동기화 완료", file=sys.stderr)
        
    except Exception as e:
        print(f"[STARTUP] Kong 설정 동기화 중 오류 발생: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def kong_cleanup_acl_when_disabled():
    """
    ACL이 비활성화되었을 때 기존 ACL 관련 설정들을 정리
    - Consumer의 ACL 그룹 제거
    - Route의 ACL 플러그인 제거
    """
    try:
        print("[ACL_CLEANUP] ACL 비활성화로 인한 기존 설정 정리 시작...", file=sys.stderr)
        
        # 1. Consumer ACL 그룹 정리
        consumers = kong_get_resources("consumers")
        consumer_cleanup_count = 0
        
        for consumer in consumers:
            consumer_id = consumer.get("id")
            username = consumer.get("username", "unknown")
            
            if username == "anonymous-user":
                continue
                
            try:
                # Consumer의 ACL 그룹들 가져오기
                response = kong_api_request("get", f"{KONG_ADMIN_URL}/consumers/{consumer_id}/acls")
                existing_acls = response.json().get("data", [])
                
                if existing_acls:
                    # 모든 ACL 그룹 제거
                    for acl in existing_acls:
                        try:
                            kong_api_request("delete", f"{KONG_ADMIN_URL}/consumers/{consumer_id}/acls/{acl['id']}")
                            debug_log(f"Removed ACL group {acl['group']} from consumer {username}")
                        except Exception as e:
                            print(f"Failed to remove ACL group {acl['group']} from consumer {username}: {e}", file=sys.stderr)
                    
                    consumer_cleanup_count += 1
                    debug_log(f"Cleaned up {len(existing_acls)} ACL groups from consumer {username}")
                    
            except Exception as e:
                print(f"Error cleaning up ACL for consumer {username}: {e}", file=sys.stderr)
        
        # 2. Route ACL 플러그인 정리
        routes = kong_get_resources("routes")
        route_cleanup_count = 0
        
        for route in routes:
            route_id = route.get("id", "")
            route_name = route.get("name", "")
            
            try:
                # Route의 플러그인들 가져오기
                response = kong_api_request("get", f"{KONG_ADMIN_URL}/routes/{route_id}/plugins")
                plugins = response.json().get("data", [])
                
                # ACL 플러그인 찾아서 제거
                for plugin in plugins:
                    if plugin.get("name") == "acl":
                        try:
                            kong_api_request("delete", f"{KONG_ADMIN_URL}/plugins/{plugin['id']}")
                            debug_log(f"Removed ACL plugin from route {route_name}")
                            route_cleanup_count += 1
                        except Exception as e:
                            print(f"Failed to remove ACL plugin from route {route_name}: {e}", file=sys.stderr)
                        break
                        
            except Exception as e:
                print(f"Error cleaning up ACL plugin for route {route_name}: {e}", file=sys.stderr)
        
        print(f"[ACL_CLEANUP] 정리 완료 - Consumer: {consumer_cleanup_count}개, Route: {route_cleanup_count}개", file=sys.stderr)
        
    except Exception as e:
        print(f"[ACL_CLEANUP] ACL 정리 중 오류 발생: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def get_preprocessing_users_auth_sync(preprocessing_id):
    """
    get_preprocessing_users_auth의 동기 버전
    """
    try:
        from utils.msa_db.db_prepro import get_db
        import traceback
        
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT u.id, u.name as user_name
                FROM user_preprocessing up
                JOIN user u ON u.id = up.user_id
                WHERE up.preprocessing_id = %s"""
            cur.execute(sql, (preprocessing_id,))
            res = cur.fetchall()
        return res
    except Exception as e:
        print(f"Error in get_preprocessing_users_auth_sync: {e}", file=sys.stderr)
        traceback.print_exc()
        return []

def kong_sync_consumer_acl_groups():
    """
    DB에서 프로젝트 정보를 가져와서 Consumer에 직접 ACL 그룹을 할당
    Consumer Group 대신 개별 Consumer의 ACL 플러그인 설정을 사용
    워크스페이스 사용자 변경이나 권한 변경을 실시간으로 반영
    """
    try:
        if not ACL_ENABLED:
            debug_log("ACL is disabled, skipping consumer ACL group synchronization")
            return
            
        print("Starting consumer ACL group synchronization...", file=sys.stderr)
        
        # DB에서 실제 프로젝트 정보 가져오기 (동기 함수 사용)
        workspaces = db_project.get_workspace_name_and_id_list()
        training_projects = db_project.get_project_list()
        preprocessing_projects = db_prepro.get_preprocessing_list_sync()
        
        # 모든 consumer 가져오기
        consumers = kong_get_resources("consumers")
        
        processed_users = 0
        users_with_workspaces = 0
        users_without_workspaces = 0
        users_with_acl_cleanup = 0
        
        for consumer in consumers:
            username = consumer.get("username")
            consumer_id = consumer.get("id")
            
            if not username or username == "anonymous-user":
                continue

            # 게시(D6) consumer(dep-<id>)는 publish_deployment_api 가 ACL 그룹(=자기 group)을 관리한다.
            # 이 동기화가 DB user 아님을 이유로 그룹을 벗기면 게시 route 의 acl(allow=[dep-<id>])이
            # 소유 consumer 를 거부(403) → 제외한다.
            if username.startswith("dep-") and username[4:].isdigit():
                continue

            processed_users += 1
            
            # username으로 user 정보 조회
            user_info = db_user.get_user(user_name=username)
            if not user_info:
                print(f"User {username} not found in database - cleaning up ACL groups", file=sys.stderr)
                # DB에 없는 사용자의 ACL 그룹 모두 제거
                kong_assign_acl_groups_to_consumer(consumer_id, [])
                users_with_acl_cleanup += 1
                continue
                
            user_id = user_info["id"]
            
            # 현재 consumer의 ACL 그룹들
            current_groups = set()
            
            # 사용자의 워크스페이스 소속 확인
            user_workspaces = db_user.get_user_workspace(user_id)
            if not user_workspaces:
                users_without_workspaces += 1
                # workspace가 없는 사용자의 ACL 그룹 모두 제거
                print(f"User {username} has no workspaces - cleaning up ACL groups", file=sys.stderr)
                kong_assign_acl_groups_to_consumer(consumer_id, [])
                users_with_acl_cleanup += 1
                continue
                
            users_with_workspaces += 1
            
            for workspace in user_workspaces:
                workspace_id = workspace["id"]
                base_group = f"w{workspace_id}"
                current_groups.add(base_group)
                debug_log(f"User {username}: Added base workspace group {base_group}")
                
                # Training 프로젝트 권한 확인
                if training_projects:
                    for project in training_projects:
                        if project["workspace_id"] == workspace_id and project["access"] == 0:  # 비공개 프로젝트
                            project_id = project["id"]
                            debug_log(f"User {username}: Checking private training project {project_id}")
                            # Private 프로젝트: user_project 테이블의 사용자 + 프로젝트 소유자
                            project_users = db_project.get_project_users(project_id)  # user_project 테이블 조회
                            user_names = {user["user_name"] for user in project_users}
                            debug_log(f"Training project {project_id} users from user_project table: {user_names}")
                            
                            # 프로젝트 소유자도 추가 (create_user_id)
                            project_owner_id = project.get("create_user_id")
                            if project_owner_id:
                                project_owner = db_user.get_user(user_id=project_owner_id)
                                if project_owner:
                                    user_names.add(project_owner["name"])
                                    debug_log(f"Training project {project_id} owner added: {project_owner['name']}")
                            
                            if username in user_names:
                                project_group = f"w{workspace_id}-training-{project_id}"
                                current_groups.add(project_group)
                                debug_log(f"User {username}: Added training project group {project_group}")
                
                # Preprocessing 프로젝트 권한 확인
                if preprocessing_projects:
                    for preprocessing in preprocessing_projects:
                        if preprocessing["workspace_id"] == workspace_id and preprocessing["access"] == 0:  # 비공개 프로젝트
                            preprocessing_id = preprocessing["id"]
                            debug_log(f"User {username}: Checking private preprocessing project {preprocessing_id}")
                            # Private preprocessing: user_preprocessing 테이블의 사용자 + 프로젝트 소유자
                            preprocessing_users = get_preprocessing_users_auth_sync(preprocessing_id)  # 동기 함수 사용
                            user_names = {user["user_name"] for user in preprocessing_users}
                            debug_log(f"Preprocessing project {preprocessing_id} users from user_preprocessing table: {user_names}")
                            
                            # Preprocessing 소유자도 추가 (owner_id)
                            preprocessing_owner_id = preprocessing.get("owner_id")
                            if preprocessing_owner_id:
                                preprocessing_owner = db_user.get_user(user_id=preprocessing_owner_id)
                                if preprocessing_owner:
                                    user_names.add(preprocessing_owner["name"])
                                    debug_log(f"Preprocessing project {preprocessing_id} owner added: {preprocessing_owner['name']}")
                            
                            if username in user_names:
                                preprocessing_group = f"w{workspace_id}-preprocessing-{preprocessing_id}"
                                current_groups.add(preprocessing_group)
                                debug_log(f"User {username}: Added preprocessing project group {preprocessing_group}")
            
            debug_log(f"User {username}: Final ACL groups: {list(current_groups)}")
            
            # Consumer에 ACL 그룹 할당 (기존 그룹 정리 포함)
            kong_assign_acl_groups_to_consumer(consumer_id, list(current_groups))
        
        # 요약 로그 출력 (항상 표시)
        print(f"[ACL_SYNC] Consumer ACL sync: {processed_users} users processed, {users_with_workspaces} with workspaces, {users_without_workspaces} without workspaces, {users_with_acl_cleanup} cleaned up", file=sys.stderr)
                
    except Exception as e:
        print(f"Error syncing consumer ACL groups: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def kong_assign_acl_groups_to_consumer(consumer_id, group_names):
    """
    특정 Consumer에 ACL 그룹들을 할당
    기존 그룹은 삭제하고 새로운 그룹들로 완전히 동기화
    """
    try:
        if not ACL_ENABLED:
            debug_log("ACL is disabled, skipping ACL group assignment")
            return
            
        # 기존 ACL 그룹들 가져오기
        try:
            response = kong_api_request("get", f"{KONG_ADMIN_URL}/consumers/{consumer_id}/acls")
            existing_acls = response.json().get("data", [])
            existing_groups = {acl["group"] for acl in existing_acls}
        except:
            existing_acls = []
            existing_groups = set()
        
        # 새로 추가할 그룹들
        new_groups = set(group_names) - existing_groups
        
        # 삭제할 그룹들 (더 이상 권한이 없는 그룹들)
        old_groups = existing_groups - set(group_names)
        
        # 변경사항이 있는 경우만 로그 출력 (디버그 모드)
        if new_groups or old_groups:
            debug_log(f"Consumer {consumer_id} ACL update - Add: {list(new_groups)}, Remove: {list(old_groups)}")
        
        # 새 그룹들 추가
        for group_name in new_groups:
            try:
                kong_api_request("post", f"{KONG_ADMIN_URL}/consumers/{consumer_id}/acls",
                               json={"group": group_name})
                debug_log(f"Added ACL group {group_name} to consumer {consumer_id}")
            except Exception as e:
                print(f"Failed to add ACL group {group_name} to consumer {consumer_id}: {e}", file=sys.stderr)
        
        # 기존 그룹들 삭제 (권한이 없어진 그룹들)
        for acl in existing_acls:
            if acl["group"] in old_groups:
                try:
                    kong_api_request("delete", f"{KONG_ADMIN_URL}/consumers/{consumer_id}/acls/{acl['id']}")
                    debug_log(f"Removed ACL group {acl['group']} from consumer {consumer_id}")
                except Exception as e:
                    print(f"Failed to remove ACL group {acl['group']} from consumer {consumer_id}: {e}", file=sys.stderr)
                
    except Exception as e:
        print(f"Error assigning ACL groups to consumer {consumer_id}: {e}", file=sys.stderr)

# 기존 함수들을 비활성화하고 새로운 함수로 대체
def kong_sync_consumer_groups():
    """
    DEPRECATED: Consumer Group 대신 kong_sync_consumer_acl_groups 사용
    """
    debug_log("Consumer Groups not supported in this Kong version. Using individual consumer ACL groups instead.")
    pass

def kong_sync_consumer_group_members():
    """
    DEPRECATED: Consumer Group 대신 kong_sync_consumer_acl_groups 사용
    """
    debug_log("Consumer Group Members not supported in this Kong version. Using individual consumer ACL groups instead.")
    pass

def kong_auto_apply_acl_to_routes():
    """
    Pod의 실제 ingress URL 패턴에 대해 자동으로 ACL 플러그인 적용
    패턴: /jupyter/{pod_name}/, /vscode/{pod_name}/, /shell/{pod_name}/
    
    보안 강화:
    - Private project: 오직 w{workspace_id}-{project_type}-{project_id} 그룹만 허용
    - Public project: w{workspace_id} 그룹 허용
    """
    try:
        if not ACL_ENABLED:
            debug_log("ACL is disabled, skipping auto ACL application to routes")
            return
            
        if ALLOW_ALL_ROUTES:
            debug_log("ALLOW_ALL_ROUTES is enabled, skipping ACL application to routes")
            return
            
        routes = kong_get_resources("routes")
        route_updates = 0
        
        for route in routes:
            route_id = route.get("id", "")
            route_name = route.get("name", "")
            paths = route.get("paths", [])
            tags = route.get("tags", [])
            
            # ACL이 필요한 Route 패턴 확인
            acl_groups = []
            
            # Pod ingress URL 패턴 확인 (/jupyter/, /vscode/, /shell/)
            pod_path = None
            tool_type = None
            for path in paths:
                if path.startswith("/jupyter/"):
                    pod_path = path
                    tool_type = "jupyter"
                    break
                elif path.startswith("/vscode/"):
                    pod_path = path
                    tool_type = "vscode"
                    break
                elif path.startswith("/shell/"):
                    pod_path = path
                    tool_type = "shell"
                    break
            
            if pod_path and tool_type:
                try:
                    # Pod name 추출 (예: /jupyter/h29b2b06e132a2331189da93c1997f1f0-0-0/ -> h29b2b06e132a2331189da93c1997f1f0-0-0)
                    path_parts = pod_path.strip("/").split("/")
                    if len(path_parts) >= 2:
                        pod_name = path_parts[1]
                        
                        # tags에서 workspace ID 추출 (k8s-namespace:jonathan-system-9 -> 9)
                        workspace_id = None
                        for tag in tags:
                            if tag.startswith("k8s-namespace:"):
                                namespace = tag.split(":", 1)[1]
                                # namespace 패턴: jonathan-system-{workspace_id}
                                namespace_parts = namespace.split("-")
                                if len(namespace_parts) >= 3 and namespace_parts[-2] == "system":
                                    workspace_id = namespace_parts[-1]
                                    break
                        
                        if not workspace_id:
                            debug_log(f"Could not extract workspace_id from tags: {tags}")
                            continue
                        
                        debug_log(f"Processing route {route_name}: pod_name={pod_name}, tool_type={tool_type}, workspace_id={workspace_id}")
                        debug_log(f"Route tags: {tags}")
                        
                        # Pod name에서 프로젝트 정보 추출
                        debug_log(f"Extracting project info from pod name")
                        project_info = extract_project_info_from_pod_name(pod_name, tool_type)
                        
                        if project_info:
                            project_id = project_info["project_id"]
                            project_type = project_info["project_type"]
                            is_private = project_info["is_private"]
                            
                            debug_log(f"Project info found: project_id={project_id}, project_type={project_type}, is_private={is_private}")
                            
                            if is_private:
                                # Private project: 오직 프로젝트별 그룹만 허용
                                acl_groups = [f"w{workspace_id}-{project_type}-{project_id}"]
                                debug_log(f"Private {project_type} project {project_id}: applying specific ACL group {acl_groups[0]}")
                            else:
                                # Public project: 워크스페이스 그룹 허용
                                acl_groups = [f"w{workspace_id}"]
                                debug_log(f"Public {project_type} project {project_id}: applying workspace ACL group {acl_groups[0]}")
                        else:
                            # Project 정보를 찾을 수 없는 경우: 워크스페이스 기본 그룹 적용
                            acl_groups = [f"w{workspace_id}"]
                            debug_log(f"⚠️ Unknown project for pod {pod_name}: applying default workspace ACL group {acl_groups[0]}")
                        
                except (ValueError, IndexError, KeyError) as e:
                    debug_log(f"Failed to parse route info from {route_name}: {e}")
                    continue
            
            # ACL 그룹이 결정되었다면 플러그인 적용
            if acl_groups:
                try:
                    # 기존 ACL 플러그인 확인
                    response = kong_api_request("get", f"{KONG_ADMIN_URL}/routes/{route_id}/plugins")
                    plugins = response.json().get("data", [])
                    
                    # ACL 플러그인이 이미 있는지 확인
                    acl_plugin_exists = False
                    current_groups = []
                    
                    for plugin in plugins:
                        if plugin.get("name") == "acl":
                            acl_plugin_exists = True
                            current_groups = plugin.get("config", {}).get("allow", [])
                            
                            # 현재 그룹과 새 그룹이 다른지 확인
                            if set(current_groups) != set(acl_groups):
                                # ACL 그룹 완전 교체 (보안상 기존 그룹 제거)
                                kong_api_request("patch", f"{KONG_ADMIN_URL}/plugins/{plugin['id']}",
                                               json={
                                                   "config": {
                                                       "allow": acl_groups
                                                   }
                                               })
                                debug_log(f"ACL plugin updated for route {route_name}: {current_groups} -> {acl_groups}")
                                route_updates += 1
                            break
                    
                    if not acl_plugin_exists:
                        # ACL 플러그인 추가
                        kong_api_request("post", f"{KONG_ADMIN_URL}/routes/{route_id}/plugins",
                                       json={
                                           "name": "acl",
                                           "config": {
                                               "allow": acl_groups
                                           }
                                       })
                        debug_log(f"ACL plugin applied to route {route_name} with groups {acl_groups}")
                        route_updates += 1
                        
                except Exception as e:
                    print(f"Failed to apply ACL to route {route_name}: {e}", file=sys.stderr)
        
        if route_updates > 0:
            print(f"[ACL_ROUTES] Updated ACL for {route_updates} routes", file=sys.stderr)
                    
    except Exception as e:
        print(f"Error in auto ACL application: {e}", file=sys.stderr)

def extract_project_info_from_tags(tags, tool_type):
    """
    Kong route tags에서 project 정보를 추출
    Tags 예시: ['k8s-namespace:jonathan-system-9', 'label_project_tool_id:123', 'label_project_id:456']
    
    Returns:
        dict: {
            "project_id": int,
            "project_type": str,  # "training" or "preprocessing"
            "is_private": bool
        } or None if not found
    """
    try:
        debug_log(f"Extracting project info from tags: {tags}, tool_type: {tool_type}")
        
        # Tags에서 project_tool_id와 project_id 추출
        project_tool_id = None
        project_id = None
        preprocessing_id = None
        
        for tag in tags:
            if tag.startswith("label_project_tool_id:"):
                project_tool_id = int(tag.split(":", 1)[1])
                debug_log(f"Found project_tool_id from tags: {project_tool_id}")
            elif tag.startswith("label_project_id:"):
                project_id = int(tag.split(":", 1)[1])
                debug_log(f"Found project_id from tags: {project_id}")
            elif tag.startswith("label_preprocessing_tool_id:"):
                project_tool_id = int(tag.split(":", 1)[1])
                debug_log(f"Found preprocessing_tool_id from tags: {project_tool_id}")
            elif tag.startswith("label_preprocessing_id:"):
                preprocessing_id = int(tag.split(":", 1)[1])
                debug_log(f"Found preprocessing_id from tags: {preprocessing_id}")
        
        # Training project인 경우
        if project_id is not None and project_tool_id is not None:
            debug_log(f"Processing as training project: project_id={project_id}, project_tool_id={project_tool_id}")
            
            # Project access 확인
            project = db_project.get_project(project_id)
            if project:
                debug_log(f"Found training project: project_id={project_id}, access={project['access']}")
                return {
                    "project_id": project_id,
                    "project_type": "training",
                    "is_private": project["access"] == 0
                }
            else:
                debug_log(f"Training project not found: project_id={project_id}")
        
        # Preprocessing project인 경우
        elif preprocessing_id is not None and project_tool_id is not None:
            debug_log(f"Processing as preprocessing project: preprocessing_id={preprocessing_id}, preprocessing_tool_id={project_tool_id}")
            
            # Preprocessing access 확인
            with db_prepro.get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT access FROM preprocessing WHERE id = %s", (project_id,))
                result = cur.fetchone()
                preprocessing_info = result if result else None
            
            if preprocessing_info:
                debug_log(f"Found preprocessing project: preprocessing_id={preprocessing_id}, access={preprocessing_info['access']}")
                return {
                    "project_id": preprocessing_id,
                    "project_type": "preprocessing", 
                    "is_private": preprocessing_info["access"] == 0
                }
            else:
                debug_log(f"Preprocessing project not found: preprocessing_id={preprocessing_id}")
        
        # Tags에서 정보를 찾을 수 없는 경우, pod name으로 fallback 시도
        debug_log(f"Could not extract project info from tags, will try pod name fallback")
        return None
        
    except Exception as e:
        debug_log(f"Error extracting project info from tags {tags}: {e}")
        import traceback
        debug_log(f"Full traceback: {traceback.format_exc()}")
        return None

def extract_project_info_from_pod_name(pod_name, tool_type):
    """
    Pod name에서 project 정보를 추출
    
    새로운 Pod name 형식: {hash}-{project_tool_id} (수정 후)
    기존 Pod name 형식: {hash}-{숫자}-{숫자} (수정 전)
    
    Returns:
        dict: {
            "project_id": int,
            "project_type": str,  # "training" or "preprocessing"
            "is_private": bool
        } or None if not found
    """
    try:
        debug_log(f"Extracting project info from pod_name: {pod_name}, tool_type: {tool_type}")
        
        # Pod name에서 project_tool_id 추출
        # 새로운 형식: {hash}-{project_tool_id}에서 마지막 숫자 부분이 project_tool_id
        possible_project_tool_ids = []
        parts = pod_name.split('-')
        debug_log(f"Pod name parts: {parts}")
        
        # 마지막 부분이 숫자인지 확인 (새로운 형식)
        if len(parts) >= 2 and parts[-1].isdigit():
            project_tool_id = int(parts[-1])
            possible_project_tool_ids.append(project_tool_id)
            debug_log(f"Found project_tool_id from new format: {project_tool_id}")
        
        # 기존 형식도 지원 (모든 숫자 부분 시도)
        for part in parts:
            if part.isdigit() and int(part) > 0 and int(part) not in possible_project_tool_ids:
                possible_project_tool_ids.append(int(part))
                debug_log(f"Found potential project_tool_id from old format: {part}")
        
        if not possible_project_tool_ids:
            debug_log(f"No numeric parts found in pod name: {pod_name}")
            return None
        
        # Training project tools에서 매칭 시도
        debug_log(f"Checking training project tools...")
        with db_project.get_db() as conn:
            cur = conn.cursor()
            for project_tool_id in possible_project_tool_ids:
                sql = """
                    SELECT pt.id, pt.project_id, pt.tool_type, pt.tool_index, p.access, p.name as project_name
                    FROM project_tool pt
                    JOIN project p ON pt.project_id = p.id
                    WHERE pt.id = %s AND pt.request_status = 1
                """
                cur.execute(sql, (project_tool_id,))
                result = cur.fetchone()
                
                if result:
                    debug_log(f"Found training tool: project_tool_id={project_tool_id}, project_id={result['project_id']}, access={result['access']}")
                    return {
                        "project_id": result["project_id"],
                        "project_type": "training",
                        "is_private": result["access"] == 0
                    }
        
        # Preprocessing project tools에서 매칭 시도
        debug_log(f"Checking preprocessing project tools...")
        with db_prepro.get_db() as conn:
            cur = conn.cursor()
            for project_tool_id in possible_project_tool_ids:
                sql = """
                    SELECT pt.id, pt.preprocessing_id, pt.tool_type, pt.tool_index, p.access, p.name as preprocessing_name
                    FROM preprocessing_tool pt
                    JOIN preprocessing p ON pt.preprocessing_id = p.id
                    WHERE pt.id = %s AND pt.request_status = 1
                """
                cur.execute(sql, (project_tool_id,))
                result = cur.fetchone()
                
                if result:
                    debug_log(f"Found preprocessing tool: project_tool_id={project_tool_id}, preprocessing_id={result['preprocessing_id']}, access={result['access']}")
                    return {
                        "project_id": result["preprocessing_id"],
                        "project_type": "preprocessing", 
                        "is_private": result["access"] == 0
                    }
        
        debug_log(f"No project found for any project_tool_id candidates: {possible_project_tool_ids}")
        return None
        
    except Exception as e:
        debug_log(f"Error extracting project info from pod {pod_name}: {e}")
        import traceback
        debug_log(f"Full traceback: {traceback.format_exc()}")
        return None

def display_ingress_status_summary():
    """
    Tool Routes의 접근 권한 정보를 상세히 출력
    """
    try:
        # Routes 정보 수집
        routes = kong_get_resources("routes")
        
        # Tool routes 정보 수집
        tool_routes_summary = []
        
        for route in routes:
            route_id = route.get("id", "")
            route_name = route.get("name", "")
            paths = route.get("paths", [])
            tags = route.get("tags", [])
            
            # Plugins 정보 가져오기
            try:
                response = kong_api_request("get", f"{KONG_ADMIN_URL}/routes/{route_id}/plugins")
                plugins = response.json().get("data", [])
                
                # ACL 플러그인 확인
                acl_plugin = None
                for plugin in plugins:
                    if plugin.get("name") == "acl":
                        acl_plugin = plugin
                        break
                
                # Tool routes 확인 (jupyter, vscode, shell)
                for path in paths:
                    if any(path.startswith(f"/{tool}/") for tool in ["jupyter", "vscode", "shell"]):
                        
                        # Tool 정보 수집
                        tool_type = None
                        pod_name = None
                        workspace_id = None
                        
                        for tool in ["jupyter", "vscode", "shell"]:
                            if path.startswith(f"/{tool}/"):
                                tool_type = tool
                                path_parts = path.strip("/").split("/")
                                if len(path_parts) >= 2:
                                    pod_name = path_parts[1]
                                break
                        
                        # Workspace ID 추출
                        for tag in tags:
                            if tag.startswith("k8s-namespace:"):
                                namespace = tag.split(":", 1)[1]
                                namespace_parts = namespace.split("-")
                                if len(namespace_parts) >= 3 and namespace_parts[-2] == "system":
                                    workspace_id = namespace_parts[-1]
                                    break
                        
                        # ACL 그룹 정보
                        acl_groups = acl_plugin.get("config", {}).get("allow", []) if acl_plugin else []
                        
                        # Pod name에서 project 정보 추출
                        project_info = extract_project_info_from_pod_name(pod_name, tool_type) if pod_name else None
                        
                        # Tool ID 추출 (pod name에서)
                        tool_id = "unknown"
                        if pod_name:
                            # Pod name에서 숫자 부분들 찾기
                            numbers = re.findall(r'\d+', pod_name)
                            if numbers:
                                tool_id = numbers[-1]  # 마지막 숫자를 tool ID로 사용
                        
                        tool_routes_summary.append({
                            "tool_type": tool_type,
                            "tool_id": tool_id,
                            "pod_name": pod_name,
                            "workspace_id": workspace_id,
                            "acl_groups": acl_groups,
                            "has_acl": bool(acl_plugin),
                            "project_info": project_info
                        })
                        break
                        
            except Exception as e:
                debug_log(f"Error getting plugins for route {route_name}: {e}")
        
        # 현황 출력
        print(f"🛠️  Active Development Tools", file=sys.stderr)
        
        # Tool Routes 상세 현황
        if tool_routes_summary:
            # Tool 타입별 그룹화
            tools_by_type = {}
            for tool in tool_routes_summary:
                tool_type = tool["tool_type"]
                if tool_type not in tools_by_type:
                    tools_by_type[tool_type] = []
                tools_by_type[tool_type].append(tool)
            
            # Tool 아이콘 매핑
            tool_icons = {
                "jupyter": "📓",
                "vscode": "💻", 
                "shell": "🔧"
            }
            
            for i, (tool_type, tools) in enumerate(tools_by_type.items()):
                is_last_type = i == len(tools_by_type) - 1
                type_prefix = "└─" if is_last_type else "├─"
                tool_icon = tool_icons.get(tool_type.lower(), "🔨")
                instance_text = "instance" if len(tools) == 1 else "instances"
                print(f"{type_prefix} {tool_icon} {tool_type.upper()} ({len(tools)} {instance_text})", file=sys.stderr)
                
                for j, tool in enumerate(tools):
                    is_last_tool = j == len(tools) - 1
                    tool_prefix = "   └─" if (is_last_tool and is_last_type) else "   ├─"
                    
                    workspace_info = f"Workspace {tool['workspace_id']}" if tool['workspace_id'] else "Workspace unknown"
                    
                    # Project 정보 구성
                    project_info_str = ""
                    access_info = ""
                    project_name = ""
                    project_owner = ""
                    
                    if tool["project_info"]:
                        project_id = tool["project_info"]["project_id"]
                        project_type = tool["project_info"]["project_type"]
                        is_private = tool["project_info"]["is_private"]
                        
                        # Project 타입과 ID 정보
                        project_type_display = "Training" if project_type == "training" else "Preprocessing"
                        project_info_str = f"{project_type_display} {project_id}"
                        
                        # Project 이름과 소유자 정보 조회
                        try:
                            if project_type == "training":
                                project_detail = db_project.get_project(project_id=project_id)
                                if project_detail:
                                    project_name = project_detail.get("name", "")
                                    if project_detail.get("create_user_id"):
                                        owner = db_user.get_user(user_id=project_detail["create_user_id"])
                                        if owner:
                                            project_owner = owner["name"]
                            elif project_type == "preprocessing":
                                preprocessing_detail = db_prepro.get_preprocessing_simple_sync(preprocessing_id=project_id)
                                if preprocessing_detail:
                                    project_name = preprocessing_detail.get("name", "")
                                    if preprocessing_detail.get("owner_id"):
                                        owner = db_user.get_user(user_id=preprocessing_detail["owner_id"])
                                        if owner:
                                            project_owner = owner["name"]
                        except Exception as e:
                            debug_log(f"Error getting project details for {project_type} {project_id}: {e}")
                        
                        # Project 이름이 있으면 추가
                        if project_name:
                            project_info_str += f" ({project_name})"
                        
                        if is_private:
                            # Private project: 접근 가능한 사용자 목록 조회
                            try:
                                if project_type == "training":
                                    # Training project 사용자 조회
                                    project_users = db_project.get_project_users(project_id)
                                    user_names = [user["user_name"] for user in project_users]
                                    
                                    # 프로젝트 소유자 추가
                                    if project_owner and project_owner not in user_names:
                                        user_names.append(project_owner)
                                    
                                elif project_type == "preprocessing":
                                    # Preprocessing project 사용자 조회
                                    preprocessing_users = get_preprocessing_users_auth_sync(project_id)
                                    user_names = [user["user_name"] for user in preprocessing_users]
                                    
                                    # Preprocessing 소유자 추가
                                    if project_owner and project_owner not in user_names:
                                        user_names.append(project_owner)
                                
                                if user_names:
                                    access_info = f"🔒 Private ({', '.join(user_names[:3])}{'...' if len(user_names) > 3 else ''})"
                                else:
                                    access_info = f"🔒 Private ({project_owner})" if project_owner else "🔒 Private"
                            except Exception as e:
                                debug_log(f"Error getting users for {project_type} project {project_id}: {e}")
                                access_info = "🔒 Private (권한 조회 실패)"
                        else:
                            # Public project
                            access_info = "🌐 Public"
                    else:
                        # Project 정보를 찾을 수 없는 경우
                        project_info_str = "Unknown Project"
                        if tool["acl_groups"]:
                            # ACL 그룹이 있으면 해당 정보 표시
                            group_info = ", ".join(tool["acl_groups"][:2])
                            if len(tool["acl_groups"]) > 2:
                                group_info += "..."
                            access_info = f"🔑 ACL: {group_info}"
                        else:
                            access_info = "❌ No Access"
                    
                    print(f"{tool_prefix} {workspace_info} • {project_info_str} • {access_info}", file=sys.stderr)
        else:
            print(f"└─ 💤 No tools are currently running", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ Error generating tool status summary: {e}", file=sys.stderr)
        debug_log(f"Tool status summary error details: {traceback.format_exc()}")

def kong_force_sync_settings():
    """
    현재 설정 플래그에 따라 강제로 Kong 설정을 동기화
    수동 호출용 - 설정 변경 후 즉시 반영하고 싶을 때 사용
    """
    print("🔄 [FORCE_SYNC] Kong 설정 강제 동기화 시작...", file=sys.stderr)
    
    try:
        # Kong 상태 확인
        if not kong_health_check():
            print("❌ [FORCE_SYNC] Kong이 응답하지 않습니다.", file=sys.stderr)
            return False
        
        # 현재 플래그 상태 표시
        print(f"📋 [FORCE_SYNC] 현재 설정:", file=sys.stderr)
        print(f"   - ALLOW_ALL_ROUTES: {ALLOW_ALL_ROUTES}", file=sys.stderr)
        print(f"   - ACL_ENABLED: {ACL_ENABLED}", file=sys.stderr)
        print(f"   - DEBUG_MODE: {DEBUG_MODE}", file=sys.stderr)
        
        # 초기화 함수 실행
        kong_initialize_on_startup()
        
        print("✅ [FORCE_SYNC] Kong 설정 강제 동기화 완료!", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ [FORCE_SYNC] 동기화 중 오류: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

# 파일 끝에 추가 - 즉시 실행 코드
if __name__ == "__main__":
    print("🔧 Kong Admin API 설정 도구", file=sys.stderr)
    print("현재 설정으로 강제 동기화를 실행합니다...", file=sys.stderr)
    kong_force_sync_settings()