from pydantic import BaseModel, Field, create_model
from typing import Optional, List, Dict, Any
# from utils.settings imposrt *
from utils.TYPE import *

def create_dynamic_model(model_name, field_list):
    fields = {}
    for key, (field_type, default_value) in field_list.items():
            fields[key] = (field_type, default_value)
    model = create_model(model_name, **fields)
    return model

PostNodeModel = create_dynamic_model("PostNodeModel",
    {
        "ip" : (str, Field(description='node ip' )),
        "interface_1g": (Optional[str], Field(default=None, description='For 1G' )),
        "interface_10g": (Optional[str], Field(default=None, description='For 10G' )),
        "interface_ib": (Optional[str], Field(default=None, description='For ib' )),
        "interfaces": (list, Field(description='Nodes all interfaces')),
        NODE_IS_CPU_SERVER_KEY: (Optional[int], Field(default=1, description='0 = False, 1 = True' )),
        NODE_IS_GPU_SERVER_KEY: (Optional[int], Field(default=1, description='0 = False, 1 = True' )),
        NODE_IS_NO_USE_SERVER_KEY: (Optional[int], Field(default=0, description='0 = False, 1 = True' )),
        NODE_CPU_LIMIT_PER_POD_DB_KEY: (Optional[float], Field(default=None, description='0.00 ~ MAX cores' )),
        NODE_CPU_CORE_LOCK_PER_POD_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_CPU_CORE_LOCK_PERCENT_PER_POD_DB_KEY: (Optional[int],Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %')),
        NODE_CPU_LIMIT_PER_GPU_DB_KEY: (Optional[float], Field(default=None, description='0.00 ~ MAX cores' )),
        NODE_CPU_CORE_LOCK_PER_GPU_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_CPU_CORE_LOCK_PERCENT_PER_GPU_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        NODE_MEMORY_LIMIT_PER_POD_DB_KEY: (Optional[str], Field(default=None, description='XXXGi' )),
        NODE_MEMORY_LOCK_PER_POD_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_MEMORY_LOCK_PERCENT_PER_POD_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        NODE_MEMORY_LIMIT_PER_GPU_DB_KEY: (Optional[str], Field(default=None, description='XXXGi' )),
        NODE_MEMORY_LOCK_PER_GPU_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_MEMORY_LOCK_PERCENT_PER_GPU_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        "ephemeral_storage_limit": (Optional[str], Field(default=None, description='XXXGi' )),
    }
)


PutNodeModel = create_dynamic_model("PutNodeModel",
    {
        "id" : (int, Field(description='node id' )),
        "interface_1g": (Optional[str], Field(default=None, description='For 1G' )),
        "interface_10g": (Optional[str], Field(default=None, description='For 10G' )),
        "interface_ib": (Optional[str], Field(default=None, description='For ib' )),
        "interfaces": (list, Field(description='Nodes all interfaces')),
        NODE_IS_CPU_SERVER_KEY: (Optional[int], Field(default=1, description='0 = False, 1 = True' )),
        NODE_IS_GPU_SERVER_KEY: (Optional[int], Field(default=1, description='0 = False, 1 = True' )),
        NODE_IS_NO_USE_SERVER_KEY: (Optional[int], Field(default=0, description='0 = False, 1 = True' )),
        NODE_CPU_LIMIT_PER_POD_DB_KEY: (Optional[float], Field(default=None, description='0.00 ~ MAX cores' )),
        NODE_CPU_CORE_LOCK_PER_POD_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_CPU_CORE_LOCK_PERCENT_PER_POD_DB_KEY: (Optional[int],Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %')),
        NODE_CPU_LIMIT_PER_GPU_DB_KEY: (Optional[float], Field(default=None, description='0.00 ~ MAX cores' )),
        NODE_CPU_CORE_LOCK_PER_GPU_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_CPU_CORE_LOCK_PERCENT_PER_GPU_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        NODE_MEMORY_LIMIT_PER_POD_DB_KEY: (Optional[str], Field(default=None, description='XXXGi' )),
        NODE_MEMORY_LOCK_PER_POD_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_MEMORY_LOCK_PERCENT_PER_POD_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        NODE_MEMORY_LIMIT_PER_GPU_DB_KEY: (Optional[str], Field(default=None, description='XXXGi' )),
        NODE_MEMORY_LOCK_PER_GPU_DB_KEY: (Optional[int], Field(default=0, description='0 = unlock | 1 = lock' )),
        NODE_MEMORY_LOCK_PERCENT_PER_GPU_DB_KEY: (Optional[int], Field(default=100, description='lock On 이더라도 lock 허용치 0 ~ n %' )),
        "ephemeral_storage_limit": (Optional[str], Field(default=None, description='XXXGi' )),
    }
)


# =============================================
# class SelectItem(BaseModel):
#     instance_name: str
#     instance_count: int
#     gpu_id: int
#     gpu_allocate: int
#     cpu_allocate: int
#     ram_allocate: int

class PostActiveNodeModel(BaseModel):
    node_id :  int = Field(description='node_id id')
    active : bool = Field(description='True : active, False : inactive')

class GetInstanceSettingModel(BaseModel):
    node_id :  int = Field(description='node_id id')

class PutAddInstanceSettingModel(BaseModel):
    node_id :  int = Field(description='node_id id')
    instance_list : Optional[list] = Field(default=None)

class GetAvalInstanceCountModel(BaseModel):
    aval_gpu: int
    aval_cpu: int
    aval_ram: int
    req_gpu: int
    req_cpu: int
    req_ram: int

class PostInstanceModel(BaseModel):
    node_id :  int = Field(description='node_id id')
    instance_list :  Optional[list] = Field(default=None)



class PutInstanceModel(BaseModel):
    class InstanceListModel(BaseModel):
        # instance_id: Optional[int] = Field(default=None)
        instance_name: str
        instance_count: int
        instance_type: str
        gpu_group_id: Optional[int] = Field(default=None)
        gpu_allocate: Optional[int] = Field(default=0)
        cpu_allocate: int
        ram_allocate: int

    node_id :  int = Field(description='node_id id')
    instance_list :  List[Dict[str, Any]]

class GetNodeInstanceModel(BaseModel):
    class InstanceListModel(BaseModel):
        # instance_id: Optional[int] = Field(default=None)
        # instance_count: int # 여기서는 count 없음
        instance_name: str
        instance_type: str
        instance_count: Optional[int] = Field(default=None, description="인스턴스 개수가 있으면 보내주고, 추가하는 인스턴스는 none")
        gpu_group_id: Optional[int] = Field(default=None)
        gpu_allocate: Optional[int] = Field(default=0)
        cpu_allocate: int
        ram_allocate: int
    node_id :  int = Field(description='node_id id')
    instance_list :  List[InstanceListModel]
