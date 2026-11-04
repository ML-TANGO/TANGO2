from fastapi import APIRouter, Depends, Request, Path, Query

from records import service as svc
from utils.resource import get_auth

records = APIRouter(
    prefix = "/records"
)

@records.get("/options/workspaces")
async def get_records_option_workspaces():
    """
    워크스페이스 목록 조회

    반환:
    - result: []
        - {}, 워크스페이스 정보
            - id: int, 워크스페이스 ID
            - name: str, 워크스페이스명
            - description: str, 워크스페이스 설명
            - manager_name: str, 워크스페이스 관리자 이름
            - 그 외 create_datetime 등 기타 정보
    """
    user_name, _ = get_auth()
    res = svc.options_workspaces(headers_user=user_name)
    return res


@records.get("/options/trainings")
async def get_records_option_trainings(
    workspace_id: int = Query(description="워크스페이스 ID")
):
    """
    특정 워크스페이스 대상 학습 목록 조회

    반환:
    - result: []
        - {}, 학습 정보
            - id: int, 학습 ID
            - name: str, 학습명
            - 그 외 기타 정보
    """
    user_name, _ = get_auth()
    res = svc.options_trainings(workspace_id=workspace_id, headers_user=user_name)
    return res
"""
if workspace_id == None and usergroup_id == None:
    # workspace_list
    
elif workspace_id is not None:
    #training_list = db.get_training_name_and_id_list_new(str(workspace_id))
    # training_list = [training for training in training_list if training["name"] is not None or training["id"] is not None]
    training_list = [{"id": 1, "name": "Not implemented yet"}]

    result = {
        "training_list" : training_list
    }
    
elif usergroup_id is not None:
    #usergroup_info, message = db.get_usergroup(usergroup_id=usergroup_id)
    #training_list = db.get_users_training(user_id_list=usergroup_info["user_id_list"])
    #training_list = [ {"id": training["id"], "name":training["name"] } for training in training_list ]
    training_list = [{"id": 1, "name": "Not implemented yet"}]
    result = {
        "training_list": training_list
    }
"""

@records.get("/workspaces")
async def get_records_history(
    page: int = Query(1, description="페이지 번호, 1부터 시작"),
    size: int = Query(10, description="페이지당 노출될 기록 개수"),
    sort: str = Query("time_stamp", description="정렬 기준, 현재 미구현으로 인자와 무관하게 로그 시간 기반 조회"),
    order: str = Query("desc", description="오름차순/내림차순 ('asc' 혹은 'desc')"),
    action: str = Query("", description="이용 기록 필터링, 동작 - create/update/delete"),
    task: str = Query("", description="이용 기록 필터링, 작업 유형 - workspace/deployment/job/training/hyperparamsearch/training/dataset/image (default: '')"),
    search_key: str = Query("", description="검색 대상, workspace/user/task_name 중 하나"),
    search_value: str = Query("", description="검색어")
):
    """
    시스템 이용 기록 정보 상세 조회
    
    추후 반환 형식 변경 가능성 높음 -> 개발서버 임시로 빈 값 반환

    반환:
    - result: {"list": [{기록1}, {기록2}, ...]}, "total": 조건에 맞는 전체 기록 수(size와 무관)}
        - 기록:
            - time_stamp: 기록 시간
            - task: 작업 유형, workspace/deployment/job/training/hyperparamsearch/training/dataset/image
            - action: 동작, create/update/delete
            - task_name: 작업 대상 이름, job 혹은 hyperparamsearch일 경우 "<학습 이름> / <job/hps 이름>"
            - user: 사용자 이름
            - workspace: 워크스페이스명
            - update_details: 상세 정보, 현재 미구현으로 모두 "-"
    """
    res = svc.records_history(page=page, size=size, sort=sort, order=order, action=action, task=task, search_key=search_key, search_value=search_value)
    return res


@records.get("/summary")
async def get_summary():
    """
    시스템 정보 요약, 현재 정보 미구현으로 요청 시마다 무작위 데이터 반환
    
    반환:
    - result: []
        - {}, 워크스페이스 정보:
            - status: str, 상태, 현재 "active"로 고정
            - workspace_name: str, 워크스페이스명
            - create_datetime: str, 워크스페이스 생성 시점, YYYY-mm-dd HH:MM:SS
            - start_datetime: str, 현재 유효기간 시작 시점, YYYY-mm-dd HH:MM
            - end_datetime: str, 현재 유효기간 종료 시점, YYYY-mm-dd HH:MM
            - activation_time: int, 누적 플랫폼 사용 시간, 초
            - storage_usage: [], 평균 스토리지 사용 정보
                - {}
                    - storage_name: str, 스토리지명
                    - storage_utilization: int, 스토리지 사용량, MB
            - instance_usage: [], 누적 인스턴스 사용 정보
                - {}
                    - instance_name: str, 인스턴스명
                    - instance_time: int, 인스턴스 사용 시간, 초
            
    """
    res = svc.summary()
    return res

@records.get("/utilization/info")
async def get_utilization_info(
    workspace_id: int = Query(None, description="워크스페이스 ID, 없을 시 전체 워크스페이스 대상 조회")
):
    """
    워크스페이스별 사용 정보 상세 조회, 상단 대시보드용
    
    현재 미구현으로 무작위 더미 데이터 반환
    
    반환:
    - result: {}
        - summary: {}, 워크스페이스 정보 
            - activation_time: int, 누적 플랫폼 사용 시간, 초
            - storage_usage: [], 평균 스토리지 사용 정보
                - {}
                    - storage_name: str, 스토리지명
                    - storage_utilization: int, 스토리지 사용량, MB
            - instance_usage: [], 누적 인스턴스 사용 정보
                - {}
                    - instance_name: str, 인스턴스명
                    - instance_time: int, 인스턴스 사용 시간, 초
        - instance_allocation_histories: []
            - {}, 인스턴스 변경 기록
                - start_datetime: str, 인스턴스 할당 시작 시점, YYYY-mm-dd HH:MM
                - end_datetime: str, 인스턴스 할당 종료 시점, YYYY-mm-dd HH:MM
                - workspace_name: str, 워크스페이스명
                - instances: [], 변경된 인스턴스 정보 목록
                    - {}
                        - allocated_count: int, 할당된 인스턴스 개수    
                        - instance_info: {}, 인스턴스 상세 정보
                            - instance_name: str, 인스턴스명
                            - instance_count: int, 총 인스턴스 수
                            - instance_type: str, 인스턴스 타입, CPU/GPU
                            - instance_validation: bool, 인스턴스 유효성 여부
                            - gpu_name: str, GPU명
                            - gpu_total: int, GPU 수
                            - gpu_vram: int, GPU VRAM, MB
                            - gpu_group_id: int, GPU 그룹 ID
                            - gpu_allocate: int, 할당 GPU 수
                            - cpu_allocate: int, 할당 CPU 수
                            - ram_allocate: int, 할당 RAM, GB
                            - free_cpu: int, 남은 CPU 수
                            - free_ram: int, 남은 RAM, GB
    """
    res = svc.instance_info(workspace_id=workspace_id)
    return res

@records.get("/utilization/figure")
async def get_utilization_figure(
    workspace_id: int = Query(None, description="워크스페이스 ID, 없을 시 전체 워크스페이스 대상 조회"),
    start_datetime: str = Query(None, description="조회 시작 시간, YYYY-mm-dd HH:MM:SS, 없을 경우 데이터 최초점이나 미구현으로 지금으로부터 2시간 전"),
    end_datetime: str = Query(None, description="조회 종료 시간, YYYY-mm-dd HH:MM:SS, 없을 경우 데이터 최종점이나 미구현으로 지금 시점"),
    aggregation: str = Query("auto", description="집계 단위, minute/hour/day/week/month/quarter/year 중 하나 혹은 auto")
):
    """
    워크스페이스별 사용 정보 상세 조회, 중간의 그래프용
    
    현재 미구현으로 무작위 더미 데이터 반환
    
    반환:
    - result: [], 시각에 대해 오름차순 보장
        - {}, 시각별 정보
            - timestamp: str, 시각, YYYY-mm-dd HH:MM 
            - cpu: int, CPU 사용량
            - gpu: int, GPU 사용량
            - ram: int, RAM 사용량, GB 
            - storage: int, 스토리지 사용량, MB
    """
    res = svc.utilization_figure(workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=end_datetime, aggregation=aggregation)
    return res

@records.get("/utilization/history")
async def get_utilization_history(
    workspace_id: int = Query(None, description="워크스페이스 ID, 없을 시 전체 워크스페이스 대상 조회"),
    start_datetime: str = Query(None, description="조회 시작 시간, YYYY-mm-dd HH:MM:SS, 없을 경우 데이터 최초점"),
    end_datetime: str = Query(None, description="조회 종료 시간, YYYY-mm-dd HH:MM:SS, 없을 경우 데이터 최종점"),
    page: int = Query(1, description="페이지 번호, 1부터 시작"),
    size: int = Query(10, description="페이지당 노출될 기록 개수"),
    type: str = Query("", description="사용 유형 필터, editor/job/hyperparamsearch/deployment 중 하나, 없을 경우 사용 유형 필터링 없음"),
    search_key: str = Query("", description="검색 대상, workspace/training/deployment 중 하나"),
    search_term: str = Query("", description="검색어, 없는 경우 검색 없음")    
):
    """
    워크스페이스별 사용 정보 상세 조회, 하단 히스토리용 
    
    현재 미구현으로 무작위 더미 데이터 반환
    
    반환:
    - result: {}
        - total: int, 전체 기록 수
        - count: int, 현재 페이지 기록 수
        - last_idx: {}, 현재 미정, 실제 구현 시 다음 페이지 요청 시 백으로 재전달 필요할 수 있음. 
        - histories: []
            - {}
                - node_name: str, 노드 이름
                - instance_allocated_count: int, 할당된 인스턴스 개수
                - instance_info: {}
                    - instance_name: str, 인스턴스명
                    - instance_count: int, 총 인스턴스 수
                    - instance_type: str, 인스턴스 타입, CPU/GPU
                    - instance_validation: bool, 인스턴스 유효성 여부
                    - gpu_name: str, GPU명
                    - gpu_allocate: int, 할당 GPU 수
                    - cpu_allocate: int, 할당 CPU 수
                    - ram_allocate: int, 할당 RAM, GB
                - workspace_name: str, 워크스페이스 이름
                - type: str, 사용 유형, editor/job/hyperparamsearch/deployment 중 하나
                - type_detail: str, 도구 이름, 아래 참조
                    - editor인 경우) editor 이름
                    - job이나 hyperparamsearch인 경우) " / "로 구분해서 학습 이름과 job/hps 이름 연결
                    - deployment인 경우) 배포 이름
                - start_datetime: str, 시작 시간, YYYY-mm-dd HH:MM:SS
                - end_datetime: str, 종료 시간, YYYY-mm-dd HH:MM:SS
                - period: int, 사용 기간, 초            
    """
    res = await svc.instance_history(
        workspace_id=workspace_id, 
        start_datetime=start_datetime, end_datetime=end_datetime, 
        page=page, size=size, 
        type=type, 
        search_key=search_key, search_term=search_term)
    return res

@records.get("/uptime")
async def get_uptime_info(
    workspace_id: int = Query(None, description="워크스페이스 ID, 없을 시 전체 워크스페이스 대상 조회"),
    start_datetime: str = Query(description="조회 시작 시간, YYYY-mm-dd HH:MM:SS"),
    end_datetime: str = Query(description="조회 종료 시간, YYYY-mm-dd HH:MM:SS")
):
    """
    워크스페이스 및 프로젝트별 업타임 정보 조회
    
    반환:
    - result: {}
        - workspaceUptimes: [], 워크스페이스별 업타임 정보
            - {}
                - workspaceName: str, 워크스페이스명
                - globalUptimeSeconds: int, 전체 시간 기준 업타임 (초)
                - officeHourUptimeSeconds: int, 업무 시간 기준 업타임 (초)
        - projectUptimes: [], 프로젝트별 업타임 정보  
            - {}
                - workspaceName: str, 워크스페이스명
                - type: str, 프로젝트 타입 (training/hps/deployment)
                - projectName: str, 프로젝트명
                - globalUptimeSeconds: int, 전체 시간 기준 업타임 (초)
                - officeHourUptimeSeconds: int, 업무 시간 기준 업타임 (초)
    """
    res = svc.uptime(workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=end_datetime)
    return res

@records.get("/export/uptime")
async def export_uptime_info(
    workspace_id: int = Query(None, description="워크스페이스 ID, 없을 시 전체 워크스페이스 대상 조회"),
    start_datetime: str = Query(description="조회 시작 시간, YYYY-mm-dd HH:MM:SS"),
    end_datetime: str = Query(description="조회 종료 시간, YYYY-mm-dd HH:MM:SS")
):
    """
    워크스페이스 및 프로젝트별 업타임 정보 Excel 내보내기
    
    업타임 정보를 조회한 후, Excel 파일로 다운로드합니다.
    """
    from fastapi.responses import StreamingResponse
    from utils.excel_utils import create_uptime_excel, format_filename
    
    # 업타임 데이터 조회
    uptime_data = svc.get_uptime_info(workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=end_datetime)
    
    # 데이터가 없으면 에러 응답
    if not uptime_data:
        return JSONResponse(
            status_code=400,
            content={"error": "Failed to fetch uptime data"}
        )
    
    # Excel 파일 생성
    excel_buffer = create_uptime_excel(uptime_data, start_datetime, end_datetime)
    
    # 파일명 생성
    filename = format_filename(start_datetime, end_datetime)
    
    # Excel 파일 응답
    def iter_excel():
        excel_buffer.seek(0)
        yield excel_buffer.read()
    
    return StreamingResponse(
        content=iter_excel(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@records.get("/dev/workspaces") # TODO 엔드포인트 제거
async def get_workspaces():
    """
    워크스페이스 id 목록 확인용 (개발용, 임시)       
    """
    res = svc.retrieve_instances()
    return res