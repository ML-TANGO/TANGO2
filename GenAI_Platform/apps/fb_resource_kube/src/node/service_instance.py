from utils.resource import CustomResource, response, token_checker
from utils.exceptions import *
from utils.PATH import *
from utils.TYPE import *
from utils.settings import KUBER_CONFIG_PATH, JF_COMPUTING_NODE_CPU_PERCENT, JF_COMPUTING_NODE_RAM_PERCENT
from utils.msa_db import db_node, db_workspace, db_instance
import traceback
from utils.common import byte_to_gigabyte
# from utils.redis import get_redis_client
import time

from kubernetes import config, client
config.load_kube_config(config_file=KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()

# ===================================================
# ===================================================

def get_instance_list(node_id):
    """
    node_total : {
        "cpu" : ,
        "ram" : ,
        "gpu" : ,
    }
    instance_list : [
        {
            "instance_name" : ,
            "instance_count" : ,
            "gpu_name" : ,
            "gpu_id" : ,
            "gpu_total" : ,
            "gpu_vram" : ,
            "gpu_allocate" : ,
            "cpu_allocate" : ,
            "ram_allocate" : ,
        }, ...
    ]
    """
    try:
        # ================================================================================================
        # computing node check
        node_info = db_node.get_node(node_id=node_id)

        # ================================================================================================
        # Node Resource
        node_cpu = db_node.get_node_cpu(node_id=node_id)['core']
        node_ram = 0
        for node_ram_info in db_node.get_node_memory_list(node_id=node_id):
            node_ram += byte_to_gigabyte(node_ram_info.get("size")) * node_ram_info.get("count")
        node_gpu_list = dict()
        for item in db_node.get_node_gpu_list(node_id=node_id, group_by_gpu=True):
            node_gpu_list[item["resource_group_id"]] = {
                "name" : item["resource_name"].replace("NVIDIA", "").strip() if item["resource_name"] is not None else None,
                "group_id" : item["resource_group_id"],
                "total" : item["gpu_count"],
                "vram" : item["gpu_memory"], # 같은 모델인데 메모리 다를 수가 있는지???
            }
        node_gpu_id_list = list(node_gpu_list.keys())
        result_node_gpu_list = node_gpu_list


        # ================================================================================================
        # Node Free Resource
        free_cpu = node_cpu * JF_COMPUTING_NODE_CPU_PERCENT
        free_ram = node_ram * JF_COMPUTING_NODE_RAM_PERCENT
        free_gpu_id_list = node_gpu_id_list

        # ================================================================================================
        # Node Instance
        node_instance_info_list = []
        for item in db_node.get_node_instance_list(node_id=node_id): # # TODO gpu orderby??

            gpu_name = item["gpu_name"].replace("NVIDIA", "").strip() if item["gpu_name"] is not None else None

            node_instance_info_list.append({
                # "instance_id" : item["instance_id"], # instance_id 내려줘야 하는지???
                "instance_name" : item["instance_name"],
                "instance_count" : item["instance_allocate"],
                "instance_type" : item["instance_type"],
                "instance_validation" : True,

                "gpu_name" : item["gpu_name"], #TODO 제거 nvidia
                "gpu_total" : node_gpu_list[item["gpu_resource_group_id"]]["total"] if item["gpu_resource_group_id"] is not None else None,
                "gpu_vram" : node_gpu_list[item["gpu_resource_group_id"]]["vram"] if item["gpu_resource_group_id"] is not None else None,
                "gpu_group_id" : item["gpu_resource_group_id"],
                "gpu_allocate" : item["gpu_allocate"],
                "cpu_allocate" : item["cpu_allocate"],
                "ram_allocate" : item["ram_allocate"],

                "free_cpu" : int(free_cpu),
                "free_ram" : int(free_ram),
                "free_gpu_id_list" : free_gpu_id_list.copy(), # 리스트는 참조타입이므로 직접 수정시 모두 바뀌기때문에 copy
            })

            # 인스턴스는 순차적으로 남은 리소스를 사용, 다음 인스턴스에서 사용할 수 있는 리소스 계산
            free_cpu -= item["instance_allocate"] * item["cpu_allocate"]
            free_cpu = free_cpu if free_cpu > 0 else 0
            free_ram -= (item["instance_allocate"] * item["ram_allocate"])
            free_ram = free_ram if free_ram > 0 else 0
            if item["gpu_resource_group_id"] is not None:
                free_gpu_id_list.remove(item["gpu_resource_group_id"])


        # ================================================================================================
        # Last Resource
        # 추가 버튼을 눌렀을때 인스턴스가 사용할 수 있는 잔여량
        last_free_resource = {
            "cpu" : int(free_cpu),
            "ram" : int(free_ram),
            "gpu_id_list" : free_gpu_id_list
        }
        #======================================================================================================
        # Result
        result = {
            "node_gpu_list" : result_node_gpu_list,
            "instance_list" : node_instance_info_list,
            "last_free_resource" : last_free_resource
        }

        # print(result)
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

# ===================================================
# 인스턴스 저장
def update_instance_list(node_id, instance_list):
    """
    instance 수정, 삭제시 다른 노드와 겹치는 인스턴스
        - 노드: 현재 작업하는 노드만 수정 삭제 (다른 노드는 건드리지 않음)
        - 워크스페이스: instance_id로 초기화 (수정, 삭제 모두 초기화)
        - project, deployment: instance_id로 초기화
    """
    try:
        # node 정보 ==================================================================
        node_info = db_node.get_node(node_id=node_id)
        node_gpu_list = db_node.get_node_gpu_list(node_id=node_id, group_by_gpu=True)
        node_gpu_info_list = dict()
        for item in node_gpu_list:
            node_gpu_info_list[item["resource_group_id"]] = {
                "name" : item["resource_name"],
                "group_id" : item["resource_group_id"],
                "total" : item["gpu_count"],
                "vram" : item["gpu_memory"], # 같은 모델인데 메모리 다를 수가 있는지???
            }

        node_total = {
            "cpu" : db_node.get_node_cpu(node_id=node_id)['core'],
            "ram" : db_node.get_node_memory(node_id=node_id)['size'],
            "gpu" : list(node_gpu_info_list.values())
        }

        node_instance_db_list = db_node.get_node_instance_list(node_id=node_id)
        node_instance_db_name_list = { item["instance_name"] : item for item in node_instance_db_list}
        instance_db_name_list = { item["instance_name"] : item for item in db_node.get_instance_list() }


        # 인스턴스 사용 체크 =============================================================
        # 기존에 있는 node의 instance_id로 사용중인 학습, 배포 pod 종료후에 수정 가능
        check_instance_id_list = [i.get("instance_id") for i in node_instance_db_list]
        if len(check_instance_id_list) > 0:
            instance_running_deployment_list = db_instance.get_deployment_list_in_instance(instance_id_list=check_instance_id_list)
            instance_running_tool_list = db_instance.get_tool_list_in_instance(instance_id_list=check_instance_id_list)
            instance_running_job_list = db_instance.get_job_list_in_instance(instance_id_list=check_instance_id_list)
            instance_running_hps_list = db_instance.get_hps_list_in_instance(instance_id_list=check_instance_id_list) # TODO hps 추가시 로직 확인

            if len(instance_running_deployment_list) > 0 or len(instance_running_tool_list) > 0 or \
                len(instance_running_job_list) > 0 or len(instance_running_hps_list) > 0:
                raise Exception("NODE에 할당된 Instance를 사용하는 학습 및 배포 종료 후에 수정해주세요.")

        # instance_list =============================================================
        update_list = []
        create_list = []
        update_flag = False # 요청들어왔는데 변경사항이 없으면 False
        for item in instance_list:

            item_instance_name = item.get("instance_name")
            if item_instance_name in instance_db_name_list:

                item_instance_id = instance_db_name_list.get(item_instance_name).get("id")
                item_instance_count = item.get("instance_count")
                instance_total_count = instance_db_name_list.get(item_instance_name).get("instance_count")
                instance_type = item.get("instance_type")

                if item_instance_name in node_instance_db_name_list:
                    # 수정 (instance 수정, node_instance 수정)
                    previous_node_instance_allocate = node_instance_db_name_list.get(item_instance_name).get("instance_allocate")
                    update_list.append({
                        "instance_id" : item_instance_id,
                        "instance_name" : item_instance_name,
                        "instance_total_count" : instance_total_count - previous_node_instance_allocate + item_instance_count,
                        "instance_count" : item_instance_count,
                        "instance_type" : instance_type,
                    })
                    if previous_node_instance_allocate != (item_instance_count):
                        update_flag = True
                else:
                    # 수정 (instance 수정, node_instance 생성)
                    update_list.append({
                        "instance_id" : item_instance_id,
                        "instance_name" : item_instance_name,
                        "instance_total_count" : instance_total_count + item_instance_count,
                        "instance_count" : item_instance_count,
                        "instance_type" : instance_type
                    })
                    update_flag = True
            else:
                # 생성
                if item.get("instance_type") == INSTANCE_TYPE_CPU:
                    item["gpu_allocate"] = 0

                create_list.append(item)
                update_flag = True
            try:
                # 삭제하는 item 에서 제외
                del node_instance_db_name_list[item_instance_name]
            except:
                pass

        # 인스턴스 삭제 리스트 =============================================================
        delete_list = list(node_instance_db_name_list.values())
        # node_instance 삭제하고, 전체 인스턴스에서 개수 차감할시 사용
        for item in delete_list:
            item["instance_total_count"] = instance_db_name_list[item["instance_name"]].get("instance_count") - item.get("instance_allocate")

        # 인스턴스 변경 체크  =============================================================
        if update_flag == False and len(delete_list) == 0:
            # 변경사항 없음
            print("No Change Instance")
            return True

        print("up", update_list)
        print("de", delete_list)
        print("cr", create_list)

        # node instance =======================================================================================================
        update_node_instance(node_id=node_id, instance_list=update_list)
        create_node_instance(node_id=node_id, instance_list=create_list)
        delete_node_instance(node_id=node_id, instance_list=delete_list)
        db_node.delete_unused_instance()

        # update, delete instance  ============================================================================================
        # update, delete - instance_id를 사용하여 workspace, project, deployment에서 instance_id가 있으면 초기화시킴
        init_instance_id_list = [i.get("instance_id") for i in delete_list] + [i.get("instance_id") for i in update_list]
        db_instance.init_workspace_instnace(instance_id_list=init_instance_id_list)
        db_instance.init_deployment_instance(instance_id_list=init_instance_id_list)
        db_instance.init_training_instance(instance_id_list=init_instance_id_list)

        return True
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

### 노드 인스턴스 생성
def create_node_instance(node_id, instance_list):
    """
    1. db
        - insert_instance
        - insert_node_instance

    2. kubernetes API node label 추가
    """
    try:
        # 1. DB ===============================================================
        if instance_list is None or len(instance_list) == 0:
            return True

        db_result, message = db_node.insert_instance(instance_list=instance_list)
        if db_result == False:
            raise

        db_result, message = db_node.insert_node_instance(node_id=node_id, instance_list=instance_list)
        if db_result == False:
            raise

        # 2. kubernetes node label ===============================================================
        for item in instance_list:
            if item.get("instance_type") == INSTANCE_TYPE_CPU:
                node_name = db_node.get_node(node_id=node_id).get("name")
                add_node_label_instane_name(node_name=node_name, instance_info=item)
                break # CPU instance 종류는 노드 당 1개

        return True
    except Exception as e:
        traceback.print_exc()
        return False

### 노드 인스턴스 수정
def update_node_instance(node_id, instance_list):
    try:
        if instance_list is None or len(instance_list) == 0:
            return True

        # instance: count 만 바꿔줌
        db_result, message = db_node.update_instance(instance_list=instance_list)
        if db_result == False:
            raise

        # node_instance: 없는경우 -> 생성, 있었던 경우는 삭제하고 새로 생성
        # node_instance DB
        db_result, message = db_node.delete_node_instance(node_id=node_id, instance_list=instance_list)
        if db_result == False:
            raise
        db_result, message = db_node.insert_node_instance(node_id=node_id, instance_list=instance_list)
        if db_result == False:
            raise

        # kubernetes cpu instance
        for item in instance_list:
            if item.get("instance_type") == INSTANCE_TYPE_CPU:
                node_name = db_node.get_node(node_id=node_id).get("name")
                add_node_label_instane_name(node_name=node_name, instance_info=item)
                break # CPU instance 종류는 노드 당 1개

        return True
    except Exception as e:
        traceback.print_exc()
        return False

### 노드 인스턴스 삭제
def delete_node_instance(node_id, instance_list):
    try:
        if instance_list is None or len(instance_list) == 0:
            return True

        db_result, message = db_node.delete_node_instance(node_id=node_id, instance_list=instance_list)
        if db_result == False:
            raise

        # node에서 없어지는만큼 전체 instance count에서 변경시켜줌
        db_result, message = db_node.update_instance(instance_list=instance_list)
        if db_result == False:
            raise

        for item in instance_list:
            if item.get("instance_type") == INSTANCE_TYPE_CPU:
                node_name = db_node.get_node(node_id=node_id).get("name")
                delete_node_label_instane_name(node_name=node_name, instance_info=item)
                break # CPU instance 종류는 노드 당 1개

        return True
    except Exception as e:
        traceback.print_exc()
        return False

# ===================================================
# 인스턴스 유효성 검사
def get_instance_validation(node_id: int, instance_list: list):
    try:
        # ================================================================================================
        # Node Resource
        node_cpu = db_node.get_node_cpu(node_id=node_id)['core']
        # node_ram = byte_to_gigabyte(db_node.get_node_memory(node_id=node_id)['size'])
        node_ram = 0
        for node_ram_info in db_node.get_node_memory_list(node_id=node_id):
            node_ram += byte_to_gigabyte(node_ram_info.get("size")) * node_ram_info.get("count")

        node_gpu_list = dict()
        for item in db_node.get_node_gpu_list(node_id=node_id, group_by_gpu=True):
            node_gpu_list[item["resource_group_id"]] = {
                "name" : item["resource_name"],
                "group_id" : item["resource_group_id"],
                "total" : item["gpu_count"],
                "vram" : item["gpu_memory"], # 같은 모델인데 메모리 다를 수가 있는지???
            }
        node_gpu_id_list = list(node_gpu_list.keys())
        result_node_gpu_list = node_gpu_list

        # ================================================================================================
        # Node Free Resource
        free_cpu = node_cpu * JF_COMPUTING_NODE_CPU_PERCENT
        free_ram = node_ram * JF_COMPUTING_NODE_RAM_PERCENT
        free_gpu_id_list = node_gpu_id_list

        # ================================================================================================
        # Node Instance
        node_instance_info_list = []
        for item in instance_list:

            # 유효성 검사

            # 할당량
            instance_count = item.get("instance_count")
            cpu_allocate = item.get("cpu_allocate")
            ram_allocate = item.get("ram_allocate")
            if item["instance_type"] == INSTANCE_TYPE_GPU:
                gpu_allocate = item.get("gpu_allocate")
                free_gpu = node_gpu_list[item["gpu_group_id"]].get("total")

            if instance_count is not None:
                # 이미 개수가 할당된 경우
                # free check
                free_cpu -= instance_count * cpu_allocate
                free_ram -= instance_count * ram_allocate
                if item["instance_type"] == INSTANCE_TYPE_GPU:
                    free_gpu -= instance_count * gpu_allocate

                # instance list
                node_instance_info_list.append({
                    "instance_name" : item["instance_name"],
                    "instance_type" : item["instance_type"],
                    "instance_validation" : True,
                    "instance_validation_message" : None,
                    "instance_count" : instance_count,

                    "gpu_name" : node_gpu_list[item["gpu_group_id"]]["name"] if item["gpu_group_id"] is not None else None,
                    "gpu_total" : node_gpu_list[item["gpu_group_id"]]["total"] if item["gpu_group_id"] is not None else None,
                    "gpu_vram" : node_gpu_list[item["gpu_group_id"]]["vram"] if item["gpu_group_id"] is not None else None,
                    "gpu_group_id" : item.get("gpu_group_id"),
                    "gpu_allocate" : item["gpu_allocate"],
                    "cpu_allocate" : item["cpu_allocate"],
                    "ram_allocate" : item["ram_allocate"],

                    "free_cpu" : int(free_cpu),
                    "free_ram" : int(free_ram),
                    "free_gpu_id_list" : free_gpu_id_list.copy(), # 리스트는 참조타입이므로 직접 수정시 모두 바뀌기때문에 copy
                })

                if item["instance_type"] == INSTANCE_TYPE_GPU:
                    free_gpu_id_list.remove(item["gpu_group_id"])

            else:
                # TODO allocate 가 0이 들어온경우
                def safe_divide(a, b):
                    try:
                        return a // b
                    except ZeroDivisionError:
                        return 0

                check_cpu = safe_divide(free_cpu, cpu_allocate)
                check_ram = safe_divide(free_ram, ram_allocate)
                check_gpu = None
                check_list = [check_cpu, check_ram,]

                if item["instance_type"] == INSTANCE_TYPE_GPU:
                    gpu_allocate = item.get("gpu_allocate")
                    free_gpu = node_gpu_list[item["gpu_group_id"]].get("total")
                    check_list.append(safe_divide(free_gpu, gpu_allocate))

                if 0 in check_list:
                    instance_validation = False
                    instance_allocate = 0
                    instance_validation_message = ""
                    if check_cpu <= 0:
                        instance_validation_message += f"할당한 CPU({cpu_allocate})가 잔여 cpu({free_cpu}) 초과함,"
                    if check_ram <= 0:
                        instance_validation_message += f"할당한 ram({ram_allocate})이 잔여 ram({ram_cpu}) 초과함,"
                    if check_gpu and check_gpu <= 0:
                        instance_validation_message += f"할당한 ram({gpu_allocate})이 잔여 ram({free_gpu}) 초과함,"

                    # TODO 실패하면 다음 인스턴스들은 검사 안하고 중단?
                else:
                    instance_validation = True
                    instance_allocate = min(check_list)
                    instance_validation_message = None

                # instance list
                node_instance_info_list.append({
                    "instance_name" : item["instance_name"],
                    "instance_type" : item["instance_type"],
                    "instance_validation" : instance_validation,
                    "instance_validation_message" : instance_validation_message,
                    "instance_count" : instance_allocate,

                    "gpu_name" : node_gpu_list[item["gpu_group_id"]]["name"] if item["gpu_group_id"] is not None else None,
                    "gpu_total" : node_gpu_list[item["gpu_group_id"]]["total"] if item["gpu_group_id"] is not None else None,
                    "gpu_vram" : node_gpu_list[item["gpu_group_id"]]["vram"] if item["gpu_group_id"] is not None else None,
                    "gpu_group_id" : item.get("gpu_group_id"),
                    "gpu_allocate" : item["gpu_allocate"],
                    "cpu_allocate" : item["cpu_allocate"],
                    "ram_allocate" : item["ram_allocate"],

                    "free_cpu" : int(free_cpu),
                    "free_ram" : int(free_ram),
                    "free_gpu_id_list" : free_gpu_id_list.copy(), # 리스트는 참조타입이므로 직접 수정시 모두 바뀌기때문에 copy
                })

                # 인스턴스는 순차적으로 남은 리소스를 사용, 다음 인스턴스에서 사용할 수 있는 리소스 계산
                free_cpu -= instance_allocate * item["cpu_allocate"]
                free_cpu = free_cpu if free_cpu > 0 else 0
                free_ram -= instance_allocate * item["ram_allocate"]
                free_ram = free_ram if free_ram > 0 else 0
                if item["gpu_group_id"] is not None:
                    free_gpu_id_list.remove(item["gpu_group_id"])

        # ================================================================================================
        # Last Resource
        # 추가 버튼을 눌렀을때 인스턴스가 사용할 수 있는 잔여량
        last_free_resource = {
            "cpu" : int(free_cpu),
            "ram" : int(free_ram),
            "gpu_id_list" : free_gpu_id_list
        }

        #======================================================================================================
        # Result
        result = {
            "node_gpu_list" : result_node_gpu_list,
            "instance_list" : node_instance_info_list,
            "last_free_resource" : last_free_resource
        }
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0)

# 인스턴스 노드 레이블 추가
def add_node_label_instane_name(node_name: int, instance_info: dict):
    try:
        kube_node = coreV1Api.read_node(name=node_name)
        if not kube_node.metadata.labels:
            kube_node.metadata.labels = {}
        kube_node.metadata.labels["jfb/cpu-instance.name"] = instance_info.get("instance_name")
        kube_node.metadata.labels["jfb/cpu-instance.id"] = str(instance_info.get("instance_id"))
        coreV1Api.patch_node(name=node_name, body=kube_node)
        kube_node = coreV1Api.read_node(name=node_name)
        print("CPU instance label: ", kube_node.metadata.labels.get("jfb/cpu-instance.name"))
        return True
    except:
        traceback.print_exc()
        return False

def delete_node_label_instane_name(node_name: int, instance_info: dict):
    try:
        kube_node = coreV1Api.read_node(name=node_name)
        if not kube_node.metadata.labels:
            kube_node.metadata.labels = {}
        if "jfb/cpu-instance.name" in kube_node.metadata.labels and kube_node.metadata.labels["jfb/cpu-instance.name"] == instance_info.get("instance_name"):
            kube_node.metadata.labels["jfb/cpu-instance.name"] = None
            kube_node.metadata.labels["jfb/cpu-instance.id"] = None
            coreV1Api.patch_node(name=node_name, body=kube_node)
            kube_node = coreV1Api.read_node(name=node_name)
            print("CPU instance label: ", kube_node.metadata.labels.get("jfb/cpu-instance.name"))
        return True
    except:
        traceback.print_exc()
        return False

# ===================================================
### 노드 인스턴스 초기화
def init_node_instance():
    try:
        while True:
            node_list = db_node.get_node_list()
            if len(node_list) > 0:
                break
            time.sleep(3)

        # instance_list = db_node.get_instance_list()
        DEFAULT_CPU = 1
        DEFAULT_RAM = 4
        DEFAULT_GPU = 1

        print("=============================================================")
        print("INIT NODE INSTANCE")
        print("=============================================================")

        for node in node_list:
            instance_update_list = []
            node_id = node['id']

            # computing node 확인
            if node.get("role") != NODE_ROLE_COMPUTING:
                continue

            # 인스턴스 존재
            if len(db_node.get_node_instance_list(node_id=node_id)) > 0:
                continue

            # 전체
            node_gpu_list = db_node.get_node_gpu_list(node_id=node_id, group_by_gpu=True)
            node_cpu = db_node.get_node_cpu(node_id=node_id)['core']
            node_ram = byte_to_gigabyte(db_node.get_node_memory(node_id=node_id)['size'])

            total_cpu = node_cpu * JF_COMPUTING_NODE_CPU_PERCENT
            total_ram = node_ram * JF_COMPUTING_NODE_RAM_PERCENT

            # gpu instance
            for node_gpu in node_gpu_list:
                node_gpu_count = node_gpu.get("gpu_count", 0)
                node_gpu_name = node_gpu.get("resource_name")
                if "NVIDIA" in node_gpu_name:
                    node_gpu_name = node_gpu_name.replace("NVIDIA", "").strip()

                instance_count = min(total_cpu // DEFAULT_CPU, total_ram // DEFAULT_RAM, node_gpu_count // DEFAULT_GPU)
                instance_update_list.append({
                    "instance_name" : f"{node_gpu_name}.{DEFAULT_GPU}.{DEFAULT_CPU}.{DEFAULT_RAM}",
                    "instance_count" : instance_count,
                    "instance_type" : INSTANCE_TYPE_GPU,
                    # "gpu_name" : node_gpu["resource_name"],
                    "gpu_id" : node_gpu["resource_group_id"], # TODO 삭제
                    "gpu_group_id" : node_gpu["resource_group_id"],
                    # "gpu_total" : ,
                    "gpu_allocate" : DEFAULT_GPU,
                    "cpu_allocate" : DEFAULT_CPU,
                    "ram_allocate" : DEFAULT_RAM,
                })
                total_cpu -= DEFAULT_CPU * instance_count
                total_ram -= DEFAULT_RAM * instance_count

            # CPU instance
            instance_count = min(total_cpu // DEFAULT_CPU, total_ram // DEFAULT_RAM)
            instance_update_list.append({
                "instance_name" : f"CPU.{DEFAULT_CPU}.{DEFAULT_RAM}",
                "instance_count" : instance_count,
                "instance_type" : INSTANCE_TYPE_CPU,
                # "gpu_name" : None,
                "gpu_id" : None, # TODO 삭제
                # "gpu_total" : ,
                "gpu_allocate" : 0,
                "cpu_allocate" : DEFAULT_CPU,
                "ram_allocate" : DEFAULT_RAM,
            })

            update_instance_list(node_id=node_id, instance_list=instance_update_list)
    except Exception as e:
        traceback.print_exc()
