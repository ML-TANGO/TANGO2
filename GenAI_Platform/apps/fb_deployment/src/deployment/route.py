from fastapi import APIRouter, Depends, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from utils.resource import response, get_auth, get_user_id
from utils.exception.exceptions import CustomErrorList
from utils.access_check import deployment_access_check #, workspace_access_check
import traceback
import logging

from deployment import model
from deployment import service as svc
from deployment import service_monitoring_new as svc_mon

deployments = APIRouter(
    prefix = "/deployments"
)

# =================================================================================================================
from utils.redis import get_redis_client
from utils.redis_key import WORKSPACE_PODS_STATUS
@deployments.get("/healthz")
def healthz():
    try:
        # print("pass")
        redis_client = get_redis_client()
        redis_client.hgetall(WORKSPACE_PODS_STATUS)
    
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

@deployments.delete("/api_log")
# @deployment_access_check(allow_max_level=3)
def delete_get_deployment_log_delete(deployment_id: int = True, end_time: str = None, worker_list: str = None):
    """delete deployment api, nginx log"""
    res = svc.get_deployment_log_delete(deployment_id=deployment_id, end_time=end_time, worker_list=worker_list)
    return res

@deployments.get("/download_api_log", description="download deployment api, nginx log")
# @deployment_access_check()
def get_deployment_download_api_log(
    background_tasks: BackgroundTasks,
    deployment_id: int,  nginx_log: bool, api_log: bool, worker_list: str = None, start_time: str = None, end_time: str = None,
):
    try:
        res = svc.get_deployment_log_download(deployment_id=deployment_id, worker_list=worker_list, 
                                            start_time=start_time, end_time=end_time,
                                            nginx_log=nginx_log, api_log=api_log, background_tasks=background_tasks)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.get("/download_abnormal_record", description="deployment dashboard history graph")
def get_deployment_download_abnormal_record(
    deployment_id: int, start_time: str, end_time: str, interval: int = 600, absolute_location: bool = True, worker_list: str = None, search_type: str = "range"
):
    try:
        res = svc_mon.get_deployment_api_monitor_graph(deployment_id=deployment_id, start_time=start_time, 
                                                    end_time=end_time, interval=interval, absolute_location=absolute_location,
                                                    worker_list=worker_list, get_csv=True)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.get("/worker_list_by_date")
def get_deployment_worklist_by_data(deployment_id: int = True, end_time: str = None):
        """delete deployment api, nginx log"""
        res = svc.get_deployment_log_delete(deployment_id=deployment_id, end_time=end_time, get_worker_list=True)
        return res
    
    
# 배포 ==================================================================
@deployments.get("")
# @workspace_access_check()
async def get_deployment_list(workspace_id: int):
    """
    # 배포 첫 화면 - 배포 리스트
    ## Input
        workspace_id
    ## output
        {
            "access": 0,
            "id": 14,
            "deployment_name": "d",
            "description": "q",
            "user_name": "klod",
            "bookmark": 0,
            "users": [
                {
                    "deployment_id": 14,
                    "user_id": 15,
                    "favorites": 0
                },
                {
                    "deployment_id": 14,
                    "user_id": 2,
                    "favorites": 0
                }
            ],
            # =======================
            # TODO
            "api_address": null,
            "deployment_status": {
                "status": "stop",
                "worker": {
                    "count": 0,
                    "status": {
                        "running": 0,
                        "installing": 0,
                        "error": 0
                    },
                    "resource_usage": {
                        "gpu": 0,
                        "cpu": 0
                    },
                    "configurations": [
                        ""
                    ]
                }
            },
            "call_count_chart": [],
            # ==========================
            # 삭제
            "built_in_model_name": null,
            "deployment_type": null,
            "item_deleted": [],
            "permission_level": null
        },
    """
    user_name, _ = get_auth()
    try:
        res = await svc.get_deployment_list(workspace_id=workspace_id, headers_user=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Deployment List Error : {}".format(e))

@deployments.put("")
# @deployment_access_check() # MSA access check flask 전환 막아둠
def put_deployment(body: model.UpdateModel):
    """
    # 배포 첫 화면 - 단일 수정
    
    # 기획에서 모델 타입은 수정 불가하도록 되어있음

    ## input
        {
            "deployment_id": int 배포아이디,
            "description" : 설명,
            "instance_type" : "gpu/cpu",
            "gpu_count" : 1, # 0이면 instance_type 은 cpu
            "gpu_id" : 1, # options에서 id 같이 내려줌
            "access" : 0,
            "owner_id" : 17,
            "users_id" : [15,2] # private 선택했을때 유저리스트
        }
    """
    try:
        users_id = body.users_id
        if users_id is None:
            users_id = []
        
        res = svc.update_deployment(
            # 배포 아이디, 설명
            deployment_id=body.deployment_id, description=body.description,
            # 접근권한
            access=body.access, owner_id=body.owner_id, users_id=users_id,
            # 자원유형
            instance_id=body.instance_id, instance_allocate=body.instance_allocate,
        )
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return {"Deployment Update Error : {}".format(e)}

@deployments.post("")
# @workspace_access_check()
def post_deployment(body: model.CreateModel):
    """
    배포 목록 리스트에서 단일 생성
    ---

    # 모델 
        model_type (str, required): custom, built-in, huggingface  
        is_new_model_type (bool, required) : 새모델 가져오기 일때 True, 학습에서 불러오기 False

    ## 학습에서 불러오기
        project_id (int)  
        training_id (int)  
        training_type (str) : job, hps  

    ## 새 모델 가져오기
        model_category (str) : 카테고리  
        huggingface_model_id (str) : built_in 모델, 허깅페이스 모델 선택시 허깅페이스 모델 아이디  
        huggingface_model_token (str) : 허깅페이스 모델 선택시 토큰 사용할경우 (private) 허깅페이스 토큰  
    """
    try:
        res = svc.create_deployment(
            workspace_id=body.workspace_id, 
            # 배포이름, 배포설명
            deployment_name=body.deployment_name, description=body.description,
            # 자원유형
            instance_id=body.instance_id, instance_allocate=body.instance_allocate,
            # instance_type=body.instance_type.upper(), 
            # 접근권한 (public, private), 소유자, 사용자리스트
            access=body.access, owner_id=body.owner_id, users_id=body.users_id,
            # 모델 유형
            model_type=body.model_type, is_new_model_type=body.is_new_model_type, 
            # 모델 유형 - 학습에서 불러오기
            project_id=body.project_id, training_id=body.training_id, training_type=body.training_type,
            # 모델 유형 - 새 모델 불러오기
            model_category=body.model_category, huggingface_model_id=body.huggingface_model_id, huggingface_model_token=body.huggingface_model_token,
        )
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Create Deployment Error : {}".format(e))

@deployments.get("/admin")
# @workspace_access_check()
def get_deployment_admin():

    # workspace_id = args.workspace_id
    # protocol = args.protocol
    res = svc.get_deployment_admin_list()
    return res

@deployments.get("/stop")
# @deployment_access_check()
def get_stop(deployment_id: int):
    """
    Deployment Stop
    admin - 배포 에서 deployment 중지 버튼 (개별 워커 중지 x, 배포 중지 버튼)
    """
    try:
        res = svc.stop_deployment(deployment_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=1, message="error")

@deployments.post("/bookmark")
# @workspace_access_check()
def post_deployment_bookmark(body: model.DeploymentIdModel):
    try:
        user_id = get_user_id()
        res = svc.add_deployment_bookmark(deployment_id=body.deployment_id, user_id=user_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.delete("/bookmark")
# @workspace_access_check()
def delete_deployment_bookmark(body: model.DeploymentIdModel):
    try:
        user_id = get_user_id()
        res = svc.delete_deployment_bookmark(deployment_id=body.deployment_id, user_id=user_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

# 배포코드생성 API
@deployments.post("/create_deployment_api")
def custom_deployment_api(args : model.DeploymentApiModel):
    custom_deployment_json_str = args.custom_deployment_json
    res = svc.create_deployment_api(custom_deployment_json_str=custom_deployment_json_str)
    return res


# 워커 ==================================================================
# 워커 세팅 수정
@deployments.put('/worker-setting')
# @deployment_access_check()
def put_deployment_worker_setting(body: model.UpdateWorkerSettingModel):
    """
        Deployment Worker Setting용 수정 API
        table 생성은 배포 생성시 같이 생성함 빈 값으로   
        project_id를 프론트로 받을때는 project_id로 받음 -> 추후 워커설정 배포유형선택시 job, hps 세팅이 필요하면 로직 변경 필요
    """
    try:
        res = svc.update_deployment_worker_setting(
                deployment_id=body.deployment_id, project_id=body.training_id, command=body.command, environments=body.environments,
                gpu_count=body.gpu_count,
                # gpu_cluster_auto=body.gpu_cluster_auto, gpu_auto_cluster_case=body.gpu_cluster_select,
                docker_image_id=body.docker_image_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return {"Deployment Update Error : {}".format(e)}

# 워커 세팅 조회
@deployments.get('/worker-setting/{deployment_id}')
# @deployment_access_check()
def get_deployment_worker_setting(deployment_id):
    """
        Deployment Worker Setting용 조회 API. 워커 리스트 페이지의 새 워커 설정 정보
        ---
        # inputs
        배포 id 입력
            deployment_id (int)
        ---
        # returns
            워커 리스트 페이지의 새 워커 설정 정보

            status (int): 0(실패), 1(성공)
            message (str): API로 부터 담기는 메세지
            # 성공 시 
            result (dict):
                type (str): 배포 타입 built-in/custom
                gpu_count (int): gpu 개수
                gpu_model (str): random / gpu 모델 명
                built_in_model_name (str): 빌트인 모델 이름 custom 인 경우 None
                training_name (str): 학습 이름 built-in pretrained, checkpoint id 통한 배포인 경우 None
                
        # MSA 변경
            deployment_name, deployment_description 추가
    """
    try:
        res = svc.get_deployment_worker_setting(deployment_id=deployment_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.get("/worker/stop")
# @deployment_access_check()
def delete_deployment_worker(deployment_worker_id: int):
    """Deployment Worker STOP"""
    try:
        # stop_deployment_worker_with_delete(deployment_worker_id=deployment_worker_id)
        # res = svc.delete_deployment_worker(deployment_worker_id=deployment_worker_id) # 함수 통합
        res, message = svc.stop_deployment_worker(deployment_worker_id=deployment_worker_id)
        return response(status=1, message="OK")
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.delete("/worker")
# @deployment_access_check(allow_max_level=3)
def delete_deployment_workers(body: model.DeleteDeploymentWorkerModel):
    """워커 페이지 -> 상단 중지된 워커 -> 리스트 삭제"""
    try:
        res = svc.delete_deployment_workers(deployment_worker_id_list=body.deployment_worker_id_list)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.post("/worker")
def post_deployment_worker(body: model.DeploymentIdModel):
    """Deployment Worker 생성"""
    try:
        user_name, _ = get_auth()
        res = svc.add_deployment_worker_new(deployment_id=body.deployment_id, headers_user=user_name)
        # res = svc_worker.add_deployment_worker_with_run(deployment_id=body.deployment_id, headers_user=user_name)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.post("/pipeline/worker")
def post_deployment_worker(body: model.DeploymentPipelineModel):
    """Deployment Worker 생성"""
    try:    
        res = svc.add_deployment_worker_new(deployment_id=body.deployment_id, headers_user=body.create_user_name)
        # res = svc_worker.add_deployment_worker_with_run(deployment_id=body.deployment_id, headers_user=user_name)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


@deployments.get("/worker")
# @deployment_access_check()
# def Deployment_worker(args : model.DeploymentWorkerListModel = Depends()):
def get_deployment_worker(deployment_id: int, deployment_worker_running_status: int = 2):
    try:
        user_id = get_user_id()
        res = svc.get_deployment_worker_list(deployment_id=deployment_id, deployment_worker_running_status=deployment_worker_running_status, user_id=user_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.put("/worker/description")
# @deployment_access_check()
def put_deployment_worker_description(body: model.UpdateWorkerDescriptionModel):
    """Deployment Worker description update"""
    try:
        res = svc.update_deployment_worker_description(deployment_worker_id=body.deployment_worker_id, description=body.description)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@deployments.get("/worker/system_log/{deployment_worker_id}")
def get_deployment_worker_system_log(deployment_worker_id):
    """
    Deployment system log 조회
    O 배포 -> 워커 -> 시스템로그 모달창
    """
    try:
        res = svc.get_worker_system_log(deployment_worker_id)
        return response(status=1, message="Success Getting Deployment Error Log", result=res)
    except:
        return response(status=0, message="Error Getting Deployment Error Log", result=None)
        
@deployments.get("/worker/system_log_download/{deployment_worker_id}")
def get_deployment_worker_system_log_download(deployment_worker_id):
    """
        Deployment System Log Download API
        O 배포 -> 워커 -> 시스템로그 모달창 -> 다운로드
        ---
        # inputs
        /worker/system_log_download/{deployment_worker_id} (동작 중인 Worker만 다운로드 가능)

        ---
        # returns

            text 다운로드 response
    """
    res = svc.get_worker_system_log_download(deployment_worker_id)
    return res


# 배포 > 모니터링, 워커 모두 사용 ==================================================================
# TODO 파일전환
@deployments.get("/dashboard_history", description="Deployment worker dashboard 의 상위 정보들")
def get_dashboard_history(args: model.GetTogalApiMonitorModel = Depends()):
    """
    1. total_info : 파란색 박스 4개
        call : 콜수
        abnormal : 비정상처리
        processing_time : 처리시간
        response_time : 응답시간
        
    2. graph_result
    
    3. code_list
    * nginx_access_count_info ?? 확인이 안됨, 쓰는건지???

    4. error_log_list : 비정상처리기록 
        {
        "worker": 999,
        "request": "POST / HTTP/1.1",
        "status": "500",
        "time_local": "2024-11-05 08:38:33",
        "message": null
        }
    """
    
    deployment_id = args.deployment_id
    start_time = args.start_time
    end_time = args.end_time
    interval = args.interval
    absolute_location = args.absolute_location
    worker_list = args.worker_list
    search_type = args.search_type
    res = svc_mon.get_deployment_api_monitor_graph(deployment_id=deployment_id, start_time=start_time, 
                                            end_time=end_time, interval=interval, absolute_location=absolute_location,
                                            worker_list=worker_list, search_type=search_type)




    # res = svc_mon.get_deployment_api_monitor_graph_new(deployment_id=deployment_id, start_time=start_time, 
    #                                         end_time=end_time, interval=interval, absolute_location=absolute_location,
    #                                         worker_list=worker_list, search_type=search_type)


    return res

# 배포 > 모니터링 ==================================================================
@deployments.get("/dashboard_status", description="deployment dashboard history graph") # 모니터링 dashboard_status
def get_dashboard_status(deployment_id: int = None):
    """
    result (dict):
        total_info (dict): 배포 작동 시간, 전체 콜 수, 응답 성공률, 작동중인 워커
            total_call_count (int): 워커들의 call count 의 합
            total_success_rate (float): nginx 200 인 count 의 비율
            total_log_size (int): 워커 directory의 size의 합 (byte)
            restart_count (int): 워커 pod의 재시작 횟수
            running_worker_count (int): 동작중인 워커 개수.
            error_worker_count (int): 에러 워커 개수.
            deployment_run_time (float): 배포 실행 시간 (중간에 모든 워커가 중지된 기간은 제외됨)
        resource_info (dict): 
            cpu_usage_rate (dict): cpu 사용률(0~1)의 min, max, average, min_worker_id, max_worker_id.
            ram_usage_rate (dict): ram 사용률(0~1)의 min, max, average, min_worker_id, max_worker_id.
            gpu_mem_usage_rate (dict): gpu 사용률(0~1)의 min, max, average, min_worker_id, max_worker_id. gpu 사용안할 시 전부 0.
            gpu_core_usage_rate (dict): gpu 코어 사용률(0~1)의 min, max, average, min_worker_id, max_worker_id. gpu 사용안할 시 전부 0.
            # min==max 인 경우
                    ex) {"min": 0.125, "max": 0.125, "average": 0.125}
            # min!=max 인 경우
                ex) {"min": 0.123, "max": 0.125, "average": 0.125, "min_worker_id": 30, "max_worker_id":32}
            gpu_use_mem (int): 워커에서 사용한 GPU 메모리
            gpu_total_mem (int): 워커에서 사용할 수 있는 총 GPU 메모리
            gpu_mem_unit (str): gpu memory 의 단위. 고정 값 "MiB"
        worker_start_time (str): 워커 시작 시간 ex) "2022-02-18 03:11:30"
    """
    res = svc_mon.get_deployment_dashboard_status(deployment_id=deployment_id)
    return res

@deployments.get("/dashboard_options")
def get_dashboard_deployment_running_worker(deployment_id: int, start_time=None, end_time=None):
    """
    배포 > 대시보드 > 게이지 차트 하단 > 워커 체크박스 리스트 
    """
    res = svc_mon.get_deployment_dashboard_running_worker(deployment_id=deployment_id, start_time=start_time, end_time=end_time)
    return res

# 배포 > 워커 ==================================================================
@deployments.get("/worker/dashboard_status") # 워커 dashboard_status
def get_deployment_worker_dashboard_status(deployment_worker_id: int):
    """
        Deployment worker dashboard current status info
        배포 -> 워커 -> 특정 워커 클릭 (미리보기 X, 워커 상세 페이지로 넘어감)
        상단 4개 정보 (작동시간, 전체콜수, 응답성공률, 재시작횟수)
        ---
        # returns
        Deployment worker dashboard 의 상위 정보들
            
            status (int): 0(실패), 1(성공)
            # 성공 시
            result (dict):
                total_info (dict): 작동 시간, 전체 콜 수, 응답 성궁률, 재시작 횟수
                    total_call_count (int)
                    total_success_rate (float): nginx 200 인 count 의 비율
                    total_log_size (int): 워커 경로의 size (byte)
                    restart_count (int): 워커 pod의 재시작 횟수
                    running_worker_count (int): 동작중인 워커 개수. 1
                    error_worker_count (int): 에러 워커 개수
                    deployment_run_time (float): 워커 실행 시간
                worker_start_time (str): 워커 시작 시간 ex) "2022-02-18 03:11:30"
            message (str): API로 부터 담기는 메세지
                
    """
    res = svc_mon.get_deployment_worker_dashboard_status(deployment_worker_id=deployment_worker_id)
    return res

@deployments.get("/worker/dashboard_resource_graph")
def get_deployment_worker_graph(deployment_worker_id: int, interval: int = 5):
    """
        Deployment Worker Graph
        배포 -> 워커 -> 특정 워커 클릭 (미리보기 X, 워커 상세 페이지로 넘어감)
        상단 4개 정보 아래, RAM CPU 그래프
        interval 5분?
    """
    res = svc_mon.get_deployment_worker_resource_usage_graph(deployment_worker_id=deployment_worker_id, interval=interval)
    return res

@deployments.get("/worker/dashboard_worker_info")
def get_deploymentWorker_dashboard_info(deployment_worker_id: int):
    """
        Deployment Worker dashboard worker info
        배포 -> 워커 -> 특정 워커 클릭 (미리보기 X, 워커 상세 페이지로 넘어감)
        중간 RAM CPU 그래프 아래 워커정보 자세히 보기
        ---
        # returns
        Deployment Worker dashboard 의 워커 정보 자세히 보기 정보들
            status (int): 0(실패), 1(성공)
            # 성공 시
            result (dict):
                description (str): 배포 description
                resource_info (dict): 워커의 자원 정보
                    configuration (list): ex) Intel(R) Core(TM) i9-9900KF CPU @ 3.60GHz
                    node_name (str): 
                    cpu_cores (str): CPU Core 개수
                    ram (str): RAM 용량 ex) 61Gi
                version_info (dict): 배포의 버전 정보
                    create_datetime (str): ex) 2022-02-07 09:20:10
                    end_datetime (str): ex) 2022-02-07 09:20:10
                    docker_image (str): docker image 이름
                    type (str): custom | built-in
                    training_name (str): training 이름
                    built_in_model_name (str): built in model 이름
                    run_code (str): ex) /src/get_api.py
                    job_info (str): [job_name]/[job_group_index] ex) job1/0
                    checkpoint (str): checkpoint 파일 경로 ex) 01-0.94.json
                version_info_changed (dict): 현재의 배포 정보와 다른 정보 표시
                    changed (bool): 현재의 배포 버전과 워커의 배포 버전이 다른지 여부
                                        * True = 버전이 다름
                                        * False = 버전이 동일함
                    changed_items (list): ex) [{item: "run_code", latest_version: "/src/app.py", current_version: "/src/app2.py"},...]
            message (str): API로 부터 담기는 메세지
    """ 
    res = svc_mon.get_deployment_worker_dashboard_worker_info(deployment_worker_id=deployment_worker_id)
    return res

@deployments.get("/deployment_name", description="Deployment 이름 조회")
def get_deployment_name_from_id(deployment_id: int = None):
    """배포 > 대시보드 페이지 때문에 남겨둠!!!"""
    res = svc.get_deployment_name(deployment_id=deployment_id)
    return res

# 옵션 ==================================================================
"""
GET deployments/options : 도커이미지, 유저리스트, gpu 리스트, 인스턴스 타입
GET deployments/options/usertrained : 학습 프로젝트 리스트
GET deployments/options/usertrained-training : 선택한 학습에서 코드, 컨피그 리스트
"""

# 학습 코드 리스트
@deployments.get("/options/usertrained-training")
async def get_option_usertrained_training(training_id : int):
    try:
        res = await svc.get_option_usertrained_training_list(training_id=training_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

# 학습리스트
@deployments.get("/options/usertrained")
def get_option_usertrained(workspace_id: int):
    user_name, _ = get_auth()
    try:
        res = svc.get_option_usertrained_list(workspace_id=workspace_id, headers_user=user_name)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


@deployments.get("/options")
async def get_deployment_options(workspace_id: int, deployment_id: int = None):
    """
    배포 options : 배포 생성, 배포 수정, 워커수정
    deployment_id 있으면 gpu_list (워커), 없으면 instance_list (배포)
    ---
    Return
    {
        "docker_image_list": [
            {
                "id": 1,
                "user_id": 25,
                "name": "jf_test",
                "real_name": "192.168.1.14:30500/jfb-system/train-test:latest",
                "file_path": null,
                "status": 2,
                "fail_reason": "tuple indices must be integers or slices, not str",
                "type": 0,
                "access": 0,
                "size": null,
                "iid": null,
                "docker_digest": null,
                "libs_digest": null,
                "description": null,
                "upload_filename": null,
                "create_datetime": "2024-06-05 06:18:06",
                "update_datetime": "2024-06-06 06:22:08"
            },
        ],
        "user_list": [
            {
                "workspace_id": 39,
                "user_id": 2,
                "favorites": 0,
                "user_name": "klod"
            },
        ],
        "instance_list": [
            {
                "id": 22,
                "name": "NVIDIA-TITAN-RTX.1.1.16",
                "allocate": 2,
                "ram": 16,
                "cpu": 1,
                "gpu": 1
            }
        ],
    }
    """
    try:
        res = await svc.get_deployment_options(workspace_id=workspace_id, deployment_id=deployment_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

# -------------배포페이지 path param-------

# @deployments.get("/efk/{worker_id}")
# def get_efk_deployment_worker_log(worker_id: str):
#     print("EFK LOG")
#     return svc_mon.get_efk_deployment_worker_log(worker_id=worker_id)

@deployments.get("/detail/{deployment_id}")
def get_deployment_name_from_id(deployment_id: int = None):
    """
    # 배포 사이드탭 - 배포정보 (상세조회)
    """
    user_name, _ = get_auth()
    res = svc.get_deployment_detail_info(deployment_id=deployment_id, headers_user=user_name)
    return res

@deployments.get("/{deployment_id}")
def get_deployment_id(deployment_id: int):
    """
    # 배포 첫 화면 - 단일 수정을 위한 GET 정보
    ## output
        {
            "workspace_id": 7,
            "workspace_name": "test2",
            "deployment_name": "userstest",
            "description": "b",
            "instance_type": "gpu",
            "gpu_count": 1,
            "gpu_model": "ram",
            "gpu_id": 1,
            "access": 0,
            "user_id": 17,
            "users": [
                {
                    "deployment_id": 18,
                    "user_id": 15,
                    "favorites": 0
                },
                {
                    "deployment_id": 18,
                    "user_id": 17,
                    "favorites": 0
                }
            ]
        }
    """
    user_name, _ = get_auth()
    res = svc.get_deployment(deployment_id=deployment_id, headers_user=user_name)
    return res

@deployments.delete("/{id_list}")
#@deployment_access_check()
def delete_deployments(id_list):
    """
    # 배포 첫화면 - user 단일 삭제, admin 복수 삭제
    """
    id_list = id_list.split(',')
    try:
        user_name, _ = get_auth()
        res = svc.delete_deployment(deployment_ids=id_list, headers_user=user_name)
        #db.request_logging(self.check_user(), 'deployments/'+str(id_list), 'delete', None, res['status'])
        return response(status=1, message="Delete Deployments OK")
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


