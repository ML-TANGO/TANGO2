from fastapi import APIRouter, Depends, Request, Path
from ingress_manager import service as svc
from ingress_manager import model

from utils.resource import response

# manager routine은 main.py에서 중앙집중식으로 시작됨
import sys

ingress_manager = APIRouter(
    prefix = "/ingress"
)

@ingress_manager.get("/healthz", summary="Liveness Probe", tags=["Health"])
async def get_liveness():
    return response(status=1, result={"status": "healthy"}, status_code=200)


@ingress_manager.post("/auth", summary="Authenticate User", tags=["Auth"])
async def authenticate_user(data: model.AuthenticateUserModel):
    cookie = svc.kong_authenticate_user(data.username)
    if not cookie:
        return response(status=0, result=None, status_code=401)
    return response(status=1, result=cookie, status_code=201)


@ingress_manager.post("/clear-plugins", summary="Clear Kong Plugins", tags=["Plugins"])
async def clear_plugins():
    svc.kong_clear_plugins()
    return response(status=1, status_code=200)


@ingress_manager.post("/consumer-group", summary="Create Consumer Group", tags=["ACL"])
async def create_consumer_group(data: model.CreateConsumerGroupModel):
    """워크스페이스 또는 프로젝트별 Consumer Group 생성"""
    group_name = svc.create_project_group(data.workspace_id, data.project_type, data.project_id)
    return response(status=1, result={"group_name": group_name}, status_code=201)


@ingress_manager.post("/project-acl", summary="Setup Project ACL", tags=["ACL"])
async def setup_project_acl(data: model.ProjectAccessModel):
    """프로젝트 ACL 설정"""
    group_name = svc.setup_project_acl(
        data.workspace_id, 
        data.project_id, 
        data.project_type, 
        data.is_public, 
        data.user_list
    )
    return response(status=1, result={"group_name": group_name}, status_code=201)


@ingress_manager.post("/route-acl", summary="Apply ACL to Route", tags=["ACL"])
async def apply_route_acl(data: model.RouteACLModel):
    """Route에 ACL 적용"""
    if data.is_public:
        group_name = f"w{data.workspace_id}"
    else:
        group_name = f"w{data.workspace_id}-{data.project_type}-{data.project_id}"
    
    success = svc.apply_acl_to_route(data.route_id, group_name)
    if success:
        return response(status=1, result={"group_name": group_name}, status_code=201)
    else:
        return response(status=0, result=None, status_code=500)


@ingress_manager.post("/consumer-to-group/{username}/{group_name}", summary="Add Consumer to Group", tags=["ACL"])
async def add_consumer_to_group(username: str, group_name: str):
    """Consumer를 Group에 추가"""
    success = svc.add_consumer_to_group(username, group_name)
    if success:
        return response(status=1, status_code=201)
    else:
        return response(status=0, status_code=500)


@ingress_manager.delete("/consumer-from-group/{username}/{group_name}", summary="Remove Consumer from Group", tags=["ACL"])
async def remove_consumer_from_group(username: str, group_name: str):
    """Consumer를 Group에서 제거"""
    success = svc.remove_consumer_from_group(username, group_name)
    if success:
        return response(status=1, status_code=200)
    else:
        return response(status=0, status_code=500)


@ingress_manager.post("/webhook/project-created", summary="Project Created Webhook", tags=["Webhook"])
async def webhook_project_created(data: model.ProjectAccessModel):
    """프로젝트 생성 시 호출되는 webhook"""
    result = svc.handle_project_created_webhook(
        project_id=data.project_id,
        project_type=data.project_type,
        workspace_id=data.workspace_id,
        is_public=data.is_public,
        user_list=data.user_list
    )
    
    if result["success"]:
        return response(status=1, result=result, status_code=201)
    else:
        return response(status=0, result=result, status_code=500)


@ingress_manager.post("/webhook/project-updated", summary="Project Updated Webhook", tags=["Webhook"])
async def webhook_project_updated(data: model.ProjectAccessModel):
    """프로젝트 업데이트 시 호출되는 webhook"""
    result = svc.handle_project_updated_webhook(
        project_id=data.project_id,
        project_type=data.project_type,
        workspace_id=data.workspace_id,
        is_public=data.is_public,
        user_list=data.user_list
    )
    
    if result["success"]:
        return response(status=1, result=result, status_code=200)
    else:
        return response(status=0, result=result, status_code=500)


@ingress_manager.post("/webhook/tool-created", summary="Tool Created Webhook", tags=["Webhook"])
async def webhook_tool_created(
    tool_id: str,
    project_id: str,
    project_type: str,
    workspace_id: str,
    route_id: str = None
):
    """툴 생성 시 호출되는 webhook"""
    result = await svc.handle_tool_created_webhook(
        tool_id=tool_id,
        project_id=project_id,
        project_type=project_type,
        workspace_id=workspace_id,
        route_id=route_id
    )
    
    if result["success"]:
        return response(status=1, result=result, status_code=201)
    else:
        return response(status=0, result=result, status_code=500)


@ingress_manager.post("/sync/force", summary="Force Sync All", tags=["Sync"])
async def force_sync_all():
    """모든 데이터를 강제로 동기화"""
    try:
        from ingress_manager.admin_api import (
            kong_sync_user_to_consumer,
            kong_sync_consumer_groups, 
            kong_sync_consumer_group_members,
            kong_auto_apply_acl_to_routes
        )
        
        # 순차적으로 동기화 실행
        kong_sync_user_to_consumer()
        kong_sync_consumer_groups()
        kong_sync_consumer_group_members()
        kong_auto_apply_acl_to_routes()
        
        return response(status=1, result={"message": "Force sync completed"}, status_code=200)
    except Exception as e:
        return response(status=0, result={"error": str(e)}, status_code=500)