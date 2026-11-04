from pydantic import BaseModel, Field
from typing import Optional
from utils.settings import INGRESS_PROTOCOL

class DeploymentIdModel(BaseModel):
    deployment_id: int = Field(description='deployment id')

class DeploymentPipelineModel(BaseModel):
    deployment_id: int = Field(description='deployment id')
    create_user_name : str = Field(description='create user name')
    
class DeploymentWorkerIdModel(BaseModel):
    deployment_worker_id: int = Field(description='deployment id')

class DeploymentApiModel(BaseModel):
    custom_deployment_json : Optional[str] = Field(description='Custom deployment information json in string')

class GetModel(BaseModel):
    workspace_id: Optional[int] = Field(default=None, description='Workspace id', type=int)
    training_id: Optional[str] = Field(default=None, description='Training id(training 페이지 내에서 조회하는 경우)')
    sort: Optional[str] = Field(default=None, description='Sort Type')
    protocol: Optional[str] = Field(default=INGRESS_PROTOCOL, description='front protocol =? http or https')

class GetNewModel(BaseModel):
    workspace_id: Optional[int] = Field(default=None, description='Workspace id', type=int)
    sort: Optional[str] = Field(default=None, description='Sort Type')
    protocol: Optional[str] = Field(default=INGRESS_PROTOCOL, description='front protocol =? http or https')
    
class GetAdminModel(BaseModel):
    workspace_id: Optional[int] = Field(default=None, description='Workspace id', type=int)
    protocol: Optional[str] = Field(default=INGRESS_PROTOCOL, description='front protocol =? http or https')

class GetTogalApiMonitorModel(BaseModel):
    deployment_id: int = Field(description='deployment id')
    start_time: Optional[str] = "2021-11-01 00:00:00"
    end_time: Optional[str] = "2021-11-07 00:00:00"
    interval: Optional[int] = Field(default=600, description='search interval second')
    worker_list: Optional[str] = Field(default=None, description='worker list')
    absolute_location: Optional[bool] = True
    search_type: Optional[str] = Field(default="range", description='search type range/live')

class CreateModel(BaseModel):
    workspace_id: int = Field(description='Workspace id')
    # 배포이름, 배포설명
    deployment_name: str = Field(description='deployment name')
    description: Optional[str] = Field(default="", description='deployment description')
    # 자원유형 : 단일 인스턴스만 가능 
    # instance_type: str = Field(description='instance_type : CPU or GPU ')
    instance_id: Optional[int] = Field(default=None, description="resource_group_id gpu model")
    instance_allocate: Optional[int] = Field(default=None, description="resource_group_id gpu model")
    # 접근권한 (public, private), 소유자, 사용자리스트
    access: Optional[int] = Field(default=1, description='Access Type : 0 = private, 1 = public')
    owner_id: int = Field(description='Owner Id' )
    users_id: Optional[list] = Field(default=list(), description='Users Id' )
    # 모델 유형
    model_type: str = Field(default="custom", description="custom or huggingface or built-in")
    training_type: Optional[str] = Field(default=None, description="학습에서 불러오기 - job or hps / pipeline (파이프라인은 training_id 안받음)")
    project_id: Optional[int] = Field(default=None, description="학습에서 불러오기 - 학습 id")
    training_id: Optional[int] = Field(default=None, description="학습에서 불러오기 - job,hps id")
    is_new_model_type: Optional[bool] = Field(default=False, description="새모델 불러오기")
    model_category: Optional[str] = Field(default=None, description="새모델 불러오기 - 카테고리(빌트인, 허깅페이스)")
    huggingface_model_id: Optional[str] = Field(default=None, description="새모델 불러오기 - huggingface id")
    huggingface_model_token: Optional[str] = Field(default=None, description="새모델 불러오기 - huggingface token")
    # new_model_id: Optional[str] = Field(default=None, description="새 모델 가져오기")
    # training_import: Optional[bool] = Field(default=True, description="학습에서 불러오기 True, 새모델 False")
    # huggingface_type: str = Field(default=None, description="new or old")
    # job_id: int = Field(default=None)

    class Config:
        protected_namespaces = () 

class UpdateModel(BaseModel):
    deployment_id: int = Field(description='deployment id ')
    description: Optional[str] = Field(default="", description='deployment description')
    # 자원유형 : 단일 인스턴스만 가능 
    # instance_type: str = Field(description='instance_type : CPU or GPU ')
    instance_id: Optional[int] = Field(default=None, description="단일 인스턴스만 가능")
    instance_allocate: Optional[int] = Field(default=None, description="인스턴스 할당량")
    access: int = Field(description='Access Type : 0 = private, 1 = public')
    owner_id: int = Field(description='Owner Id' )
    users_id: Optional[list] = Field(default=list(), description='Users Id' )
    model_type: str = Field(default="custom", description="custom or huggingface or ji")

    class Config:
        protected_namespaces = () 


class UpdateWorkerSettingModel(BaseModel):
    deployment_id: int = Field(description='deployment id ')
    # 배포설정
    # deployment_type: str = Field(description='deployment type : {}'.format(DEPLOYMENT_TYPES))
    ### custom
    training_id: Optional[int] = Field(description='front에서 training_id로 받고 백에서 project_id로 처리 /// training model??? (id)')
    command: Optional[dict] = Field(default=None, description='command = {"binary":"python", "script":"/jf-training-home/src/get_api.py", "arguments":"--a aa --b bb -c"}')
    environments: Optional[list] = Field(default=None, description='environments = [{"name":"FLASK_APP","value":"app"},{"name":"FLASK_ENV","value":"development"}]')
    # run_code: Optional[str] = Field(default=None, description='run_code = /src/[RUN CODE] (only in custom model)')
    ### job/hps
    # 동일하게 training_id
    # training_type: Optional[str] = Field(default=None, description='training type = job / hps / custom' )
    # job_id: Optional[int] = Field(default=None, description='job_id = checkpoint(id)')
    # hps_id: Optional[int] = Field(default=None, description='hps_id = checkpoint(id)')
    # hps_number: Optional[int] = Field(default=None, description='hps_number')
    # checkpoint: Optional[str] = Field(default=None, description='checkpoint = job_name/grop_index/checkpoint (name)')
    
    # 자원유형
    # instance_type: str = Field(description='instance_type : CPU or GPU ')
    # 단일 GPU이고, instance_id로 gpu 알수 있으므로 gpu id 전달 받지 않음 # instance_id는 배포 db 값 copy
    gpu_count: Optional[int] = Field(default=0, description='instance_type = GPU case -> gpu_count ')
    # gpu_id: Optional[int] = Field(default=None, description="워커 당 gpu 개수")
    # gpu_worker_count: Optional[int] = Field(default=0, description='워커 당 gpu 개수')s
    # gpu_id: Optional[int] = Field(default=None, description="resource_group_id gpu model")

    # 분산학습
    
    # gpu cluster
    # gpu_cluster_auto: Optional[bool] = Field(default=None, description="gpu cluster 자동 설정인 경우 True, 수동 설정인 경우 False, GPU 1개 이하 None")
    # gpu_cluster_select: Optional[dict] = Field(default=None, description="ex) {'gpu_count': 1, 'server'': 1, 'status': true}")

    # 도커이미지
    docker_image_id: int = Field(description='Docker Image ID (-1 = jf default)' )

class UpdateApiPathModel(BaseModel):
    deployment_id: int 
    api_path: str

class UpdateWorkerDescriptionModel(BaseModel):
    deployment_worker_id: int = Field(description='deployment_worker_id id')
    description: str = Field(description='Deployment Worker Description (1000)')
    
class DeleteDeploymentWorkerModel(BaseModel):
    deployment_worker_id_list: str = Field(description='deployment_worker_id list')

class DeploymentWorkerListModel(BaseModel):
    deployment_id : Optional[int] = Field(description='deployment id', type=int)
    deployment_worker_running_status :  Optional[int] = Field(default = 2, description='0 : stop, 1 : running, 2: all', type=int)


class PostHuggingfaceModelInput(BaseModel):
    model_name : Optional[str] = None
    huggingface_token : Optional[str] = None
    private : Optional[int] = 0
    task: Optional[str] = None

    class Config:
        protected_namespaces = () 