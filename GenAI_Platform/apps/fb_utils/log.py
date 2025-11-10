from enum import Enum
from utils.msa_db import db_user
from utils.msa_db import db_workspace
import json
from datetime import datetime
from zoneinfo import ZoneInfo


class LogParam:
    class Task(Enum):
        def __str__(self):
            return self.value

        PIPELINE = "pipeline"
        DATASET = "dataset"
        IMAGE = "image"
        TRAINING = "training"
        PREPROCESSING = "preprocessing"
        DEPLOYMENT = "deployment"
        WORKSPACE = "workspace"
        USER = "user"

    class Action(Enum):
        def __str__(self):
            return self.value

        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"


# {"instance_name": ..., "instance_count": ..., ""}
class InstanceInfo:
    def __init__(self, instance_name, instance_count):
        self.instance_name = instance_name
        self.instance_count = instance_count

    def to_dict(self):
        return {
            "instance_name": self.instance_name,
            "instance_count": self.instance_count,
        }


# {"storage_name": "nfs-local", "storage-type": "main", "storage-size": 1_000}
class StorageInfo:
    def __init__(self, storage_name, storage_type, storage_size):
        self.storage_name = storage_name
        self.storage_type = storage_type
        self.storage_size = storage_size

    def to_dict(self):
        return {
            "storage_name": self.storage_name,
            "storage_type": self.storage_type,
            "storage_size": self.storage_size,
        }


# {"start_time": ..., "end_time": ..., "instances": [InstanceInfo, ...], "storages": [StorageInfo, ...]}
class WorkspaceAllocationInfo:
    def calc_duration_minutes(self):
        start_time = datetime.strptime(self.start_time, "%Y-%m-%d %H:%M")
        last_time = (
            datetime.strptime(self.last_time, "%Y-%m-%d %H:%M")
            if self.last_time
            else None
        )
        init_time = last_time if last_time and start_time < last_time else start_time

        end_time = datetime.strptime(self.end_time, "%Y-%m-%d %H:%M")
        current_time = datetime.strptime(self.current_time, "%Y-%m-%d %H:%M")
        termination_time = end_time if end_time < current_time else current_time

        duration_minutes = int((termination_time - init_time).total_seconds()) // 60
        return duration_minutes if duration_minutes > 0 else 0

    def __init__(self, start_time, end_time, last_time, instances, storages):
        self.start_time = start_time
        self.end_time = end_time
        self.last_time = last_time
        self.instances = instances
        self.storages = storages

    def to_dict(self):
        self.current_time = datetime.now(ZoneInfo("Asia/Seoul")).strftime(
            "%Y-%m-%d %H:%M"
        )
        self.duration_minutes = self.calc_duration_minutes()
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "current_time": self.current_time,
            "last_time": self.last_time,
            "duration_minutes": self.duration_minutes,
            "instances": [instance.to_dict() for instance in self.instances],
            "storages": [storage.to_dict() for storage in self.storages],
        }


def logging_info_history(
    task,
    action,
    task_name=None,
    user_id=None,
    user_name=None,
    workspace_id=None,
    workspace_name=None,
    update_details=None,
    info=None,
):
    """
    :param task: string, one of workspace, training, job, hyperparams, image, or dataset
    :param action: string, one of add, create, update, delete, auto_labeling, download, uploadData or deleteDate
    :param user_id: user_id or user_name
    :param workspace: workspace_id or workspace_name
    :param task_name: string, name of task
    :param update_details: stirng, updated detailed information
    :param info: json object, additional information
    """
    # if info is dict or list, convert to json string
    if info:
        if type(info) == dict or type(info) == list:
            info = json.dumps(info)

    user = (
        db_user.get_user(user_id=user_id).get("name")
        if user_id
        else user_name if user_name else None
    )
    workspace = (
        db_workspace.get_workspace(workspace_id=workspace_id).get("name")
        if workspace_id
        else workspace_name if workspace_name else None
    )

    print(
        f'[JFB/USAGE] {{"user": "{user}", "task": "{task}", "action": "{action}", "workspace": "{workspace}", "task_name": "{task_name}", "update_details": "{update_details}", "info": {info}}}'
    )


def logging_history(
    task,
    action,
    task_name=None,
    user_id=None,
    user_name=None,
    workspace_id=None,
    workspace_name=None,
    update_details=None,
):
    """
    :param task: string, one of workspace, training, job, hyperparams, image, or dataset
    :param action: string, one of add, create, update, delete, auto_labeling, download, uploadData or deleteDate
    :param user: user_id or user_name
    :param workspace: workspace_id or workspace_name
    :param task_name: string, name of task
    :param update_details: stirng, updated detailed information
    """
    user = (
        db_user.get_user(user_id=user_id).get("name")
        if user_id
        else user_name if user_name else None
    )
    workspace = (
        db_workspace.get_workspace(workspace_id=workspace_id).get("name")
        if workspace_id
        else workspace_name if workspace_name else None
    )

    print(
        f'[JFB/USAGE] {{"user": "{user}", "task": "{task}", "action": "{action}", "workspace": "{workspace}", "task_name": "{task_name}", "update_details": "{update_details}"}}'
    )


async def logging_history_async(
    task,
    action,
    task_name=None,
    user_id=None,
    user_name=None,
    workspace_id=None,
    workspace_name=None,
    update_details=None,
):
    """
    :param task: string, one of workspace, training, job, hyperparams, image, or dataset
    :param action: string, one of add, create, update, delete, auto_labeling, download, uploadData or deleteDate
    :param user: user_id or user_name
    :param workspace: workspace_id or workspace_name
    :param task_name: string, name of task
    :param update_details: stirng, updated detailed information
    """
    user_info = await db_user.get_user_async(user_id=user_id)
    user = user_info.get("name") if user_id else user_name if user_name else None
    workspace_info = await db_workspace.get_workspace_async(workspace_id=workspace_id)
    workspace = (
        workspace_info.get("name")
        if workspace_id
        else workspace_name if workspace_name else None
    )

    print(
        f'[JFB/USAGE] {{"user": "{user}", "task": "{task}", "action": "{action}", "workspace": "{workspace}", "task_name": "{task_name}", "update_details": "{update_details}"}}'
    )

def logging_project_pod_history(
    workspace_name,
    start_datetime,
    item_name,
    item_type,
    project_name,
    end_datetime,
    period,
    type,
    type_detail,
    total_gpu_count,
    instance_name,
    gpu_name,
    instance_type,
    gpu_allocate,
    cpu_allocate,
    ram_allocate,
    total_used_cpu = None,
    total_used_ram = None,
):
    allocation_info = {
        "workspace_name": workspace_name,
        "start_datetime": start_datetime,
        "item_name": item_name,
        "item_type": item_type,
        "project_name": project_name,
        "end_datetime": end_datetime,
        "period": period,
        "type": type,
        "type_detail": type_detail,
        "total_gpu_count": total_gpu_count,
        "total_used_cpu": total_used_cpu,
        "total_used_ram": total_used_ram,
        "instance_info": {
            "instance_name": instance_name,
            "gpu_name": gpu_name,
            "instance_type": instance_type,
            "gpu_allocate": gpu_allocate,
            "cpu_allocate": cpu_allocate,
            "ram_allocate": ram_allocate
        }
    }
    
    log = {
        "log_type": "allocation",
        "allocation_info": json.dumps(allocation_info, separators=(',', ':'))  # JSON 문자열로 변환
    }
    print("[JFB/USAGE]", json.dumps(log, separators=(',', ':')))