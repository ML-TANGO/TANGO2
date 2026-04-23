from utils import common, TYPE
from kubernetes import config, client
from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity

import aiohttp
import asyncio
import yaml
import os

# Ensure Kubernetes client is configured (in-cluster or via kubeconfig)
try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()  # Fallback for local testing

POD_ERROR_RESOLUTIONS = {
    "ErrImagePull": {
        "description": "Image not found or inaccessible.",
        "resolution": "Check image name/tag and registry access credentials."
    },
    "ImagePullBackOff": {
        "description": "Repeated image pull failures causing back-off.",
        "resolution": "Verify the image name, tag, and registry credentials."
    },
    "InvalidImageName": {
        "description": "Invalid image name provided.",
        "resolution": "Correct the image name in pod specification."
    },
    "OOMKilled": {
        "description": "Container ran out of memory.",
        "resolution": "Increase memory limits or optimize memory usage."
    },
    "OutOfcpu": {
        "description": "Insufficient CPU resources on nodes.",
        "resolution": "Free or increase CPU resources or reduce pod requests."
    },
    "OutOfmemory": {
        "description": "Insufficient memory resources on nodes.",
        "resolution": "Add memory resources or reduce pod memory requests."
    },
    "Evicted": {
        "description": "Pod evicted due to resource pressure.",
        "resolution": "Check node resource availability and adjust pod priorities."
    },
    "CrashLoopBackOff": {
        "description": "Pod is repeatedly crashing.",
        "resolution": "Check pod logs, identify crashes, and fix application errors."
    },
    "RunContainerError": {
        "description": "Container failed to start running.",
        "resolution": "Verify volumes, mounts, and container startup scripts."
    },
    "CreateContainerError": {
        "description": "Container creation failed.",
        "resolution": "Inspect pod events for conflicts or runtime errors."
    },
    "CreateContainerConfigError": {
        "description": "Container configuration generation failed.",
        "resolution": "Check ConfigMaps/Secrets and pod configuration."
    },
    "NetworkUnavailable": {
        "description": "Network not available on node.",
        "resolution": "Check node network (CNI plugin status)."
    },
    "VolumeMountError": {
        "description": "Volume mount failure.",
        "resolution": "Ensure PVCs/ConfigMaps/Secrets exist and are correctly mounted."
    },
    "PersistentVolumeError": {
        "description": "Persistent volume binding or mounting issue.",
        "resolution": "Check PVC/PV status and ensure correct provisioning."
    },
    "DeadlineExceeded": {
        "description": "Pod exceeded its execution deadline.",
        "resolution": "Adjust activeDeadlineSeconds or investigate application slowness."
    },
    "ContainerCannotRun": {
        "description": "Container cannot run due to command or binary issue.",
        "resolution": "Check container command, binaries, and compatibility."
    },
    "PodInitializing": {
        "description": "Pod is initializing (running init containers).",
        "resolution": "Wait or verify init container logs."
    }
}

def analyze_pod_error(pod):
    reason = None
    resolution = None
    status = 'unknown'
    terminated_times = []
    latest_finished_at = []

    if pod.status.phase == 'Pending':
        status = TYPE.KUBE_POD_STATUS_INSTALLING
        reason = 'Pending'
    elif pod.status.phase == 'Running':
        status = TYPE.KUBE_POD_STATUS_RUNNING
        for cs in pod.status.container_statuses or []:
            if not cs.ready:
                status =  TYPE.KUBE_POD_STATUS_INSTALLING
                reason = 'Container readiness probe not ready yet'
                break
            elif cs.state.waiting:
                reason = cs.state.waiting.reason
                if reason == 'ContainerCreating':
                    status = TYPE.KUBE_POD_STATUS_INSTALLING
                else:
                    status = TYPE.KUBE_POD_STATUS_ERROR
                break
    elif pod.status.phase in ('Succeeded', 'Failed'):
        for cs in pod.status.container_statuses or []:
            if cs.state.terminated:
                reason = cs.state.terminated.reason
                if reason == 'Completed':
                    status = TYPE.KUBE_POD_STATUS_DONE
                else:
                    status = TYPE.KUBE_POD_STATUS_ERROR
                break
        terminated_times = [
            cs.state.terminated.finished_at
            for cs in pod.status.container_statuses or []
            if cs.state.terminated and cs.state.terminated.finished_at
        ]
    if terminated_times:
        latest_finished_at = max(terminated_times)
        latest_finished_at = latest_finished_at.strftime(TYPE.TIME_DATE_FORMAT) 
    else:
        latest_finished_at = None

    # 상세 에러 분석
    if reason in POD_ERROR_RESOLUTIONS:
        resolution = POD_ERROR_RESOLUTIONS[reason]['resolution']
        reason_description = POD_ERROR_RESOLUTIONS[reason]['description']
    else:
        reason_description = reason or "Unknown error"
        resolution = "Check pod logs and events."

    return status, reason_description, resolution, latest_finished_at



def get_pod_info(namespace, pod_name):
    v1 = client.CoreV1Api()
    try:
        pod = v1.read_namespaced_pod(pod_name, namespace)
        return pod.to_dict()
    except ApiException as e:
        print(f"Error getting pod: {e}")
        return None

def get_all_pods(namespace : str, label_selector: str = ""):
    v1 = client.CoreV1Api()
    try:
        pod_list = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        # return [pod.to_dict() for pod in pod_list.items]
        return pod_list
    except ApiException as e:
        print(f"Error fetching pods: {e}")
        return None

def get_node_info(node_name):
    v1 = client.CoreV1Api()
    try:
        node = v1.read_node(node_name)
        return node.to_dict()
    except ApiException as e:
        print(f"Error getting node: {e}")
        return None


def get_pvc_info(namespace, pvc_name):
    v1 = client.CoreV1Api()
    try:
        pvc = v1.read_namespaced_persistent_volume_claim(pvc_name, namespace)
        return pvc.to_dict()
    except ApiException as e:
        print(f"Error getting pvc: {e}")
        return None


def get_pv_info(pv_name):
    v1 = client.CoreV1Api()
    try:
        pv = v1.read_persistent_volume(pv_name)
        return pv.to_dict()
    except ApiException as e:
        print(f"Error getting pv: {e}")
        return None


class PodName():
    def __init__(self, workspace_name, item_name, item_type, sub_item_name=None, sub_flag=None, start_datetime : str = None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment 
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C | 
        sub_item_name (str) (optional) : for unique. Job name, Hps name, or id
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        self.base_pod_name = "" # base name
        self.unique_pod_name = "" # [unique name] = [base name]-[sub-flag]
        self.container_name = "" # no hash [unique name]

        self.set_base_pod_name(workspace_name=workspace_name, item_name=item_name, sub_item_name=sub_item_name, item_type=item_type, start_datetime=start_datetime)
        self.set_unique_pod_name(base_pod_name=self.base_pod_name, sub_flag=sub_flag)
        self.set_container_name(workspace_name=workspace_name, item_name=item_name, item_type=item_type, sub_flag=sub_flag)

        
    def set_base_pod_name(self, workspace_name, item_name, item_type, sub_item_name=None, start_datetime : str = None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment 
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C | 
        sub_item_name (str) (optional) : Job name, Hps name ...

        # kube_create_func 모놀 코드
        ---
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if sub_item_name is not None:
            name = "{}-{}".format(name, sub_item_name)
        base_pod_name = "{}".format(common.gen_pod_name_hash(name.replace("-","0")))
        self.base_pod_name =  base_pod_name
        """
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if start_datetime:
            name = "{}-{}-{}-{}".format(name, item_name, item_type, start_datetime)
        if sub_item_name is not None:
            if not start_datetime:
                name = "{}-{}".format(name, sub_item_name)
            else:
                name = "{}-{}-{}".format(name, sub_item_name, start_datetime)
        base_pod_name = "{}".format(common.gen_pod_name_hash(name.replace("-","0")))
        self.base_pod_name =  base_pod_name

    def set_unique_pod_name(self, base_pod_name, sub_flag=None):
        """
        base_pod_name (str) : from create_base_pod_name(). (hash)
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..

        모놀코드
        ---
        if sub_flag is None:
            self.unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)
        self.unique_pod_name = unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)
        """
        if sub_flag is None:
            self.unique_pod_name = "{}-{}".format(base_pod_name, 0)
        else:
            self.unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)

    def set_container_name(self, workspace_name, item_name, item_type, sub_flag=None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment 
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C | 
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if sub_flag is not None:
            name = "{}-{}".format(name, sub_flag)

        self.container_name = name

    def get_all(self):
        return self.base_pod_name, self.unique_pod_name, self.container_name

    def get_base_pod_name(self):
        return self.base_pod_name


# === Node request budget helper (added for fine-tuning admission guard) =====

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeBudget:
    """대상 노드의 남은 K8s scheduler request 예산."""
    node_name: str
    memory_free_bytes: int
    cpu_free_millicores: int
    gpu_free: int
    # 진단용 원본 값
    memory_allocatable_bytes: int
    memory_used_bytes: int
    cpu_allocatable_millicores: int
    cpu_used_millicores: int


# K8s pod phase 중 "노드의 request 예산을 차지하는" 상태
# Succeeded/Failed는 terminated라 차감되지 않음.
_BUDGETED_POD_PHASES = {"Pending", "Running"}


def _millicores(cpu_qty) -> int:
    if cpu_qty is None:
        return 0
    return int(float(parse_quantity(str(cpu_qty))) * 1000)


def _bytes(mem_qty) -> int:
    if mem_qty is None:
        return 0
    return int(float(parse_quantity(str(mem_qty))))


def get_node_request_budget(node_name: str) -> NodeBudget:
    """주어진 노드의 남은 memory/cpu/gpu request 예산을 계산해 반환.

    Raises:
        ApiException: 노드 조회 실패 시. 호출자는 예외 시 FAIL_RETRY 처리(Task 4).
    """
    v1 = client.CoreV1Api()
    node = v1.read_node(node_name)
    alloc = node.status.allocatable or {}
    alloc_mem = _bytes(alloc.get("memory"))
    alloc_cpu_mc = _millicores(alloc.get("cpu"))
    alloc_gpu = int(alloc.get("nvidia.com/gpu", 0) or 0)

    pod_list = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
    used_mem = 0
    used_cpu_mc = 0
    used_gpu = 0
    for pod in pod_list.items or []:
        if pod.status is None or pod.status.phase not in _BUDGETED_POD_PHASES:
            continue
        # field_selector는 서버측 필터이지만, 방어적으로 클라이언트측에서도
        # 노드 이름을 재확인해 다른 노드의 Pod가 예산에 섞이지 않도록 한다.
        if pod.spec is None or pod.spec.node_name != node_name:
            continue
        for c in (pod.spec.containers or []):
            req = (c.resources.requests if c.resources else None) or {}
            used_mem += _bytes(req.get("memory"))
            used_cpu_mc += _millicores(req.get("cpu"))
            used_gpu += int(req.get("nvidia.com/gpu", 0) or 0)

    return NodeBudget(
        node_name=node_name,
        memory_free_bytes=max(0, alloc_mem - used_mem),
        cpu_free_millicores=max(0, alloc_cpu_mc - used_cpu_mc),
        gpu_free=max(0, alloc_gpu - used_gpu),
        memory_allocatable_bytes=alloc_mem,
        memory_used_bytes=used_mem,
        cpu_allocatable_millicores=alloc_cpu_mc,
        cpu_used_millicores=used_cpu_mc,
    )