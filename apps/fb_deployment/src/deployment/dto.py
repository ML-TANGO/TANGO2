from pydantic import BaseModel, Field, validator, StrictStr
from typing import Optional, List
from utils.TYPE import DEPLOYMENT_TYPE, DEPLOYMENT_TYPE_CUSTOM


class DeploymentResourcesDetail(BaseModel):
    cpu: Optional[float] = 0.0
    memory: Optional[float] = 0.0
    gpu: Optional[int] = 0
    npu: Optional[int] = 0

class DeploymentResources(BaseModel):
    limits: Optional[DeploymentResourcesDetail] = None
    requests: Optional[DeploymentResourcesDetail] = None

class DeploymentInfo(BaseModel):
    pod_type: str = DEPLOYMENT_TYPE
    work_type: str = DEPLOYMENT_TYPE
    work_func_type: str = DEPLOYMENT_TYPE
    deployment_type:str = DEPLOYMENT_TYPE
    # -------------------------
    workspace_id: int
    workspace_name: str
    user: str
    deployment_id: int
    deployment_name: str
    deployment_worker_id: int
    project_name: Optional[str] = None
    # -------------------------
    pod_name: str
    pod_base_name: str
    pod_image: str
    run_code: Optional[str] = None
    # -------------------------
    instance_id: int
    resource_type: str #Optional[str] = None
    resource_group_id : Optional[int] = None
    resource_name : Optional[str] = None
    gpu_count: int
    gpu_cluster_auto: Optional[bool] = False
    gpu_auto_cluster_case: Optional[dict] = dict()
    gpu_select: Optional[list] = []
    resources: DeploymentResources
    # -------------------------
    model_type: str = DEPLOYMENT_TYPE_CUSTOM
    huggingface_model_id: Optional[str] = None
    huggingface_token: Optional[str] = None
    training_id: Optional[int] = None

    class Config:
        protected_namespaces = () 