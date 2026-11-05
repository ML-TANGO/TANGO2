from ingress_manager.admin_api import kong_api_request, kong_get_resources, delete_all_plugins
import requests
from typing import Optional, Dict, Any, List
from utils.settings import JF_KONG_ADMIN_DNS, JF_KONG_ADMIN_HTTP_PORT, JF_KONG_PROXY_DNS

KONG_ADMIN_URL = f"http://{JF_KONG_ADMIN_DNS}:{JF_KONG_ADMIN_HTTP_PORT}"
# KONG_ADMIN_URL = f"https://{JF_KONG_ADMIN_DNS}:8444"
def get_or_create_consumer(username: str) -> None:
    """
    Check if the consumer exists. If not, create a new consumer.
    
    Args:
        username (str): The username to check/create.
    """  
    res = kong_api_request("get", f"{KONG_ADMIN_URL}/consumers/{username}")
    if res:
        print(f"Consumer {username} already exists.")

    else:
        print(f"Consumer {username} does not exist. Creating...")
        kong_api_request("post", f"{KONG_ADMIN_URL}/consumers", json={"username": username})
        print(f"Consumer {username} created successfully.")


def get_or_create_key_auth(username: str) -> str:
    """
    Check if a key-auth credential exists for the consumer. If not, create a new one.

    Args:
        username (str): The username to check.

    Returns:
        str: The API Key.
    """
    url = f"{KONG_ADMIN_URL}/consumers/{username}/key-auth"
    res = kong_api_request("get", url).json()["data"]
    if len(res) > 0:
        apikey = res[0]["key"]
        print(f"Existing API Key found for {username}.")
        return apikey
    else:
        print(f"No existing key-auth for {username}. Creating new API key...")
    
    # Create new API Key
    response = kong_api_request("post", url, json={})
    apikey = response.json()["key"]
    print(f"New API Key created for {username}.")
    return apikey

def get_kong_session_cookie(apikey: str) -> Optional[str]:
    """
    Use the API key to authenticate with Kong Proxy and retrieve a session cookie.
    Tries multiple endpoints until a Set-Cookie header is found.

    Args:
        apikey (str): The API Key for authentication.

    Returns:
        Optional[str]: The session cookie if available, None otherwise.
    """
    candidate_paths = [
        "ssh", "projects", "workspaces", "preprocessing"
    ]

    for path in candidate_paths:
        url = f"http://{JF_KONG_PROXY_DNS}/api/{path}/healthz?apikey={apikey}"
        try:
            response = requests.get(url, timeout=1)
            print(f"[Requesting cookie via {path} app] Response: {response.status_code} - {response.text}")  # 503 에러 발생해도 Kong을 거치게 되어서 그런지 cookie를 잘 받아옴...
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                return set_cookie
        except Exception as e:
            print(f"[{path} app] Request failed: {e}")

    print("All health check endpoints failed or no Set-Cookie header returned.")
    return None

def kong_authenticate_user(username: str):
    # Ensure the consumer exists
    get_or_create_consumer(username)

    # Ensure the consumer has a key-auth credential
    apikey = get_or_create_key_auth(username)

    # Use the API key to get a session cookie
    session_cookie = get_kong_session_cookie(apikey)
    
    return session_cookie

def kong_clear_plugins():
    delete_all_plugins()

# Kong ACL 관련 함수들 - Consumer Groups 대신 개별 Consumer ACL 사용
def get_or_create_consumer_group(group_name: str) -> Dict[str, Any]:
    """
    DEPRECATED: Consumer Groups는 Kong 버전 호환성 문제로 사용하지 않음
    """
    print(f"Consumer Groups not supported. Using individual consumer ACL instead.")
    return {"name": group_name}

def add_consumer_to_group(username: str, group_name: str) -> bool:
    """
    DEPRECATED: Consumer Groups는 Kong 버전 호환성 문제로 사용하지 않음
    """
    print(f"Consumer Groups not supported. ACL will be managed by kong_sync_consumer_acl_groups.")
    return True

def remove_consumer_from_group(username: str, group_name: str) -> bool:
    """
    DEPRECATED: Consumer Groups는 Kong 버전 호환성 문제로 사용하지 않음
    """
    print(f"Consumer Groups not supported. ACL will be managed by kong_sync_consumer_acl_groups.")
    return True

def create_project_group(workspace_id: str, project_type: str = None, project_id: str = None) -> str:
    """
    프로젝트별 Consumer Group 이름 반환 (실제 생성은 하지 않음)
    """
    if project_type and project_id:
        group_name = f"w{workspace_id}-{project_type}-{project_id}"
    else:
        group_name = f"w{workspace_id}"
    
    return group_name

def setup_project_acl(workspace_id: str, project_id: str, project_type: str, 
                     is_public: bool, user_list: List[str]) -> str:
    """
    프로젝트 ACL 설정 (Consumer Groups 대신 kong_sync_consumer_acl_groups에서 처리)
    """
    if is_public:
        group_name = f"w{workspace_id}"
    else:
        group_name = f"w{workspace_id}-{project_type}-{project_id}"
    
    return group_name

def apply_acl_to_route(route_id: str, group_name: str) -> bool:
    """
    Route에 ACL 플러그인 적용
    """
    try:
        response = kong_api_request("post", f"{KONG_ADMIN_URL}/routes/{route_id}/plugins",
                                  json={
                                      "name": "acl",
                                      "config": {
                                          "allow": [group_name]
                                      }
                                  })
        print(f"ACL plugin applied to route {route_id} with group {group_name}")
        return True
    except Exception as e:
        print(f"Failed to apply ACL to route {route_id}: {e}")
        return False

# Webhook 기능 함수들
def handle_project_created_webhook(project_id: str, project_type: str, workspace_id: str, 
                                 is_public: bool, user_list: List[str] = None) -> Dict[str, Any]:
    """
    프로젝트 생성 시 호출되는 webhook 함수
    Consumer Groups 대신 개별 Consumer ACL 사용
    """
    try:
        # Consumer Groups는 사용하지 않고, kong_sync_consumer_acl_groups()에서 자동으로 처리됨
        # 여기서는 성공적으로 프로젝트가 생성되었음을 알리기만 함
        group_name = f"w{workspace_id}" if is_public else f"w{workspace_id}-{project_type}-{project_id}"
        
        return {
            "success": True,
            "group_name": group_name,
            "message": f"Project {project_id} ACL will be synced automatically by kong_sync_consumer_acl_groups"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to setup ACL for project {project_id}"
        }

def handle_project_updated_webhook(project_id: str, project_type: str, workspace_id: str,
                                 is_public: bool, user_list: List[str] = None) -> Dict[str, Any]:
    """
    프로젝트 업데이트 시 호출되는 webhook 함수
    Consumer Groups 대신 개별 Consumer ACL 사용
    """
    try:
        # Consumer Groups는 사용하지 않고, kong_sync_consumer_acl_groups()에서 자동으로 처리됨
        group_name = f"w{workspace_id}" if is_public else f"w{workspace_id}-{project_type}-{project_id}"
        
        return {
            "success": True,
            "group_name": group_name,
            "message": f"Project {project_id} ACL will be synced automatically by kong_sync_consumer_acl_groups"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to update ACL for project {project_id}"
        }

async def handle_tool_created_webhook(tool_id: str, project_id: str, project_type: str, 
                              workspace_id: str, route_id: str = None) -> Dict[str, Any]:
    """
    툴 생성 시 호출되는 webhook 함수 (Ingress Route에 ACL 적용)
    """
    try:
        from utils.msa_db import db_project, db_prepro
        
        # 프로젝트 정보 확인
        if project_type == "training":
            project_info = db_project.get_project(project_id=int(project_id))
        elif project_type == "preprocessing":
            project_info = db_prepro.get_preprocessing_simple_sync(preprocessing_id=int(project_id))
        else:
            raise ValueError(f"Unknown project type: {project_type}")
        
        if not project_info:
            raise ValueError(f"Project {project_id} not found")
        
        # ACL 그룹 결정
        if project_info["access"] == 0:  # 비공개 프로젝트
            group_name = f"w{workspace_id}-{project_type}-{project_id}"
        else:  # 공개 프로젝트
            group_name = f"w{workspace_id}"
        
        # Route가 제공된 경우 직접 ACL 적용
        if route_id:
            success = apply_acl_to_route(route_id, group_name)
            if not success:
                raise Exception(f"Failed to apply ACL to route {route_id}")
        
        return {
            "success": True,
            "group_name": group_name,
            "route_id": route_id,
            "message": f"Tool {tool_id} ACL setup completed"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to setup ACL for tool {tool_id}"
        }