import traceback

# import utils.mpi as mpi
import utils.common as common

import os
import sys
import kubernetes
from utils.exceptions import *
# from utils.kube import coreV1Api, extensV1Api, get_service_port, delete_service, kube_data, delete_service_training_tool
# from utils.kube_setting_cmd import *
# from utils.kube_network_attachment_definitions import get_network_attachment_definitions_annotations_for_pod_annotations
# import utils.kube_common_volume as kube_common_volume
# # import utils.db as db
sys.path.insert(0, os.path.abspath('..'))

from utils.settings import *
from utils.TYPE import *
# from nodes import is_cpu_pod_run_on_only_cpu_nodes
# from utils.pod import pod_start_new
### KUBE RESOURCE KEY
# memory: "1Gi"
# cpu: "3.5"
# ephemeral-storage: "100Mi"
# nvidia.com/gpu: "1"
# nvidia.com/mig-xxx: "1"

########## trainings/ 폴더 구조
# TYPE : Job
# job-checkpoints/{job_name=job_group}/{job_index}/DATA
# job_logs/{job_id}.jflog
#
# TYPE : HPS
# hps-checkpoints/{hps_name=hps_group}/{hps_index}/DATA
# hps_save_load_files/{hps_name=hps_group}/{data_name}-{hps_index}.json #for save load json
# hps_logs/{} #for log json

# basic / advanced

# ENV
ENV_DEPLOYMENT_PREFIX="JFB_DEPLOYMENT_PREFIX"

class PodName():
    def __init__(self, workspace_name, item_name, item_type, sub_item_name=None, sub_flag=None):
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

        self.set_base_pod_name(workspace_name=workspace_name, item_name=item_name, sub_item_name=sub_item_name, item_type=item_type)
        self.set_unique_pod_name(base_pod_name=self.base_pod_name, sub_flag=sub_flag)
        self.set_container_name(workspace_name=workspace_name, item_name=item_name, item_type=item_type, sub_flag=sub_flag)


    def set_base_pod_name(self, workspace_name, item_name, item_type, sub_item_name=None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C |
        sub_item_name (str) (optional) : Job name, Hps name ...
        """
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if sub_item_name is not None:
            name = "{}-{}".format(name, sub_item_name)
        base_pod_name = "{}".format(common.gen_pod_name_hash(name.replace("-","0")))
        self.base_pod_name =  base_pod_name

    def set_unique_pod_name(self, base_pod_name, sub_flag=None):
        """
        base_pod_name (str) : from create_base_pod_name(). (hash)
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        if sub_flag is None:
            self.unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)
        self.unique_pod_name = unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)

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

# ENV FORMAT
class ENV():
    def __init__(self, owner_name=None, item_id=None, env_list=None):
        """
        owner_name (str) : owner name
        item_id (int) : item id (training_tool_id, ...)
        """
        if env_list is None:
            env_list = []
        self.env_list = env_list #form = [ {"name":"ENV_NAME", "value": "ENV_VALUE"} ]
        self._add_default(owner_name=owner_name, item_id=item_id)

    def get_env_list(self):
        return self.env_list

    def _add_default(self, owner_name, item_id):
        self._add_default_jf_home()
        self._add_default_item_host(owner_name=owner_name)
        self._add_default_item_id(item_id=item_id)

    def _add_default_jf_home(self):
        self.add_env(name=KUBE_ENV_JF_HOME_KEY, value=KUBE_ENV_JF_HOME_DEFAULT_VALUE)

    def _add_default_item_host(self, owner_name):
        # user name
        self.add_env(name=KUBE_ENV_JF_ITEM_OWNER_KEY, value=owner_name)

    def _add_default_item_id(self, item_id):
        self.add_env(name=KUBE_ENV_JF_ITEM_ID_KEY, value=item_id)

    def add_ddp_env(self, hosts, total_gpu_count):
        self.add_env("JF_OMPI_HOSTS", hosts)
        self.add_env("JF_N_GPU", total_gpu_count)
        if total_gpu_count < 2:
            self.add_env("OMPI_COMM_WORLD_SIZE", 1)
            self.add_env("OMPI_COMM_WORLD_RANK", 0)
            self.add_env("OMPI_COMM_WORLD_LOCAL_RANK", 0)

    def add_default_env_job(self, log_base, job_id, hosts, total_gpu_count):
        """
        Description : Job Default env 추가

        Args :
            log_base (str) : job log를 저장할 dir 기본 경로 (JF_TRAINING_JOB_LOG_DIR_POD_PATH)
            job_id (int) : 실행하는 job id
            hosts (str) : mpirun -H [여기] 에 들어갈 포맷. ex) 192.168.1.11:2,192.168.1.12:2
            total_gpu_count (int) : 사용하는 GPU TOTAL (각 group의 총합) 개수 (GPU가 1일 땐 mpirun 명령어를 사용하지 않기에 ddp 케이스에서는 mpirun이 내려주는 env를 강제로 생성)
        """
        self.add_env(name="JF_GRAPH_LOG_FILE_PATH", value="{log_base}/{item_id}.jflog_graph".format(log_base=log_base, item_id=job_id))
        self.add_env(name="JF_GRAPH_LOG_BASE_PATH", value=log_base)
        self.add_ddp_env(hosts=hosts, total_gpu_count=total_gpu_count)
        # self.add_env("JF_OMPI_HOSTS", hosts)
        # self.add_env("JF_N_GPU", total_gpu_count)
        # if total_gpu_count < 2:
        #     self.add_env("OMPI_COMM_WORLD_SIZE", 1)
        #     self.add_env("OMPI_COMM_WORLD_RANK", 0)
        #     self.add_env("OMPI_COMM_WORLD_LOCAL_RANK", 0)

    def add_default_env_hyperparamsearch(self, hps_id, hps_name, save_file_name, load_file_name, hosts, total_gpu_count):
        """
        Description :
            # FOR
            # SAVE ORIGINAL RECORED = (Graph, log)
            # SAVE APPEND

        Args :
            hps_id (int) : hyperparameter search item id
            hps_name (str) : hyperparameter search item name
            save_file_name (str) : hyperparameter search result save file name. 현재는 지정 불가. 자동 지정해줌. (.json으로 끝나야하며 없으면 강제로 붙임)
            load_file_name : hyperparameter search result load file name. 현재는 지정 불가. 자동 지정해줌. (.json으로 끝나야하며 없으면 강제로 붙임)
        """
        save_file_name = save_file_name if save_file_name[-5:] == ".json" else save_file_name + ".json"
        if load_file_name is not None:
            load_file_name = load_file_name if load_file_name[-5:] == ".json" else load_file_name + ".json"

        self.add_env(name="JF_HPS_ORIGINAL_RECORD_FILE_PATH", value=JF_TRAINING_HPS_LOG_ORIGINAL_RECORD_FILE_POD_PATH.format(hps_id=hps_id))
        self.add_env(name="JF_HPS_ORIGINAL_RECORD_N_ITER_FILE_PATH", value=JF_TRAINING_HPS_LOG_N_ITER_FILE_DIR_POD_PATH.format(hps_id=hps_id))
        self.add_env(name="JF_HPS_SAVE_FILE_BASE_PATH", value=JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH.format(hps_name=hps_name))
        self.add_env(name="JF_HPS_ID", value=str(hps_id))
        self.add_env(name="JF_HPS_SAVE_FILE_NAME", value=save_file_name)
        self.add_env(name="JF_HPS_LOAD_FILE_NAME", value=load_file_name)

        self.add_ddp_env(hosts=hosts, total_gpu_count=total_gpu_count)

    def add_default_env_deployment_worker(self, deployment_running_type, workdir):
        """
        Args :
            deployment_running_type (str) : DEPLOYMENT_RUN_CHEKCPOINT, DEPLOYMENT_RUN_CUSTOM, DEPLOYMENT_RUN_PRETRAINED, DEPLOYMENT_RUN_USERTRAINED
        """
        self.add_env(name="POD_API_LOG_BASE_PATH_IN_POD", value=POD_API_LOG_BASE_PATH_IN_POD) # API LOG BASE PATH
        self.add_env(name="POD_API_LOG_FILE_PATH_IN_POD", value=POD_API_LOG_FILE_PATH_IN_POD) # API MONITOR LOG FILE PATH
        self.add_env(name="POD_API_LOG_FILE_NAME", value=POD_API_LOG_FILE_NAME) # API MONITOR LOG FILE_NAME
        self.add_env(name="POD_API_LOG_COUNT_FILE_NAME", value=POD_API_LOG_COUNT_FILE_NAME) # LOG COUNT FILE NAME

        # API MONITOR LOG 가 Import 되었는지 확인하는 파일
        self.add_env(name="POD_API_LOG_IMPORT_CHECK_FILE_PATH_IN_POD", value=POD_API_LOG_IMPORT_CHECK_FILE_PATH_IN_POD)

        # POD GPU USAGE LOG FILE PATH  - gpu 사용량 관련 파일 저장 위치
        self.add_env(name="POD_GPU_USAGE_RECORD_FILE_PATH_IN_POD", value=POD_GPU_USAGE_RECORD_FILE_PATH_IN_POD)

        # POD CPU RAM USAGE LOG PATH - cpu ram 사용량 관련 파일 저장 위치
        self.add_env(name="POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_POD", value=POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_POD)

        self.add_env(name="DEPLOYMENT_RUNNING_TYPE", value=deployment_running_type)
        if deployment_running_type == DEPLOYMENT_RUN_CUSTOM:
            self.add_env(name=KUBE_ENV_JF_DEPLOYMENT_PWD_KEY, value=JF_TRAINING_SRC_POD_PATH)
        elif deployment_running_type == DEPLOYMENT_RUN_SANDBOX:
            if workdir != None:
                self.add_env(name=KUBE_ENV_JF_DEPLOYMENT_PWD_KEY, value=workdir)
            else:
                self.add_env(name=KUBE_ENV_JF_DEPLOYMENT_PWD_KEY, value=JF_TRAINING_SRC_POD_PATH)
        else :
            self.add_env(name=KUBE_ENV_JF_DEPLOYMENT_PWD_KEY, value=JF_BUILT_IN_MODELS_MODEL_POD_PATH)

    def add_env(self, name, value):
        self.env_list.append({
            "name": name,
            "value": str(value)
        })

    def add_env_share_nvidia_gpu(self, gpu_uuid_list):
        self.env_list.append({
                "name": "NVIDIA_VISIBLE_DEVICES",
                "value": ",".join(gpu_uuid_list)
            })

    def add_env_no_nvidia_gpu(self):
        self.env_list.append({
                "name": "NVIDIA_VISIBLE_DEVICES",
                "value": ""
            })
        self.add_env_jf_gpu_num(value=0)

    def add_env_jf_gpu_num(self, value):
        # GPU COUNT
        self.add_env(name="JF_GPU", value=value)

    def add_env_jf_memory(self, value):
        # MEMORY SIZE
        self.add_env(name="JF_MEMORY", value=value)

    def add_env_jf_cpu(self, value):
        # CPU CORE
        self.add_env(name="JF_CPU", value=value)

    def add_env_jf_ephemeral_storage(self, value):
        # EPHEMERAL STORAGE
        self.add_env(name="JF_TEMPORARY_STORAGE", value=value)

    # TODO 대체 함수 개발 시 제거 예정 (2022-11-24 Yeobie)
    def add_resource_info_env(self, gpu_use, gpu_resource_key, resource_limits, gpu_uuid_list=None):
        if gpu_use == 0 and gpu_uuid_list is None:
            self.add_env_no_nvidia_gpu()
        elif gpu_uuid_list is not None:
            self.add_env_share_nvidia_gpu(gpu_uuid_list=gpu_uuid_list)

        kube_resource_limits = get_kube_resource_limits(gpu_use=gpu_use, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits)
        for key, value in kube_resource_limits.items():
            if NVIDIA_GPU_BASE_LABEL_KEY in key:
                self.add_env_jf_gpu_num(value=value)

            elif K8S_RESOURCE_MEMORY_KEY == key:
                self.add_env_jf_memory(value=value)

            elif K8S_RESOURCE_CPU_KEY == key:
                self.add_env_jf_cpu(value=value)

            elif K8S_RESOURCE_EPHEMERAL_STORAGE_KEY == key:
                self.add_env_jf_ephemeral_storage(value=value)

    def add_resource_info_env_new(self, kube_resource_limits, gpu_uuid_list=None):
        """
            Description :
        """
        for key, value in kube_resource_limits.items():
            if NVIDIA_GPU_BASE_LABEL_KEY in key:
                self.add_env_jf_gpu_num(value=value)

                if value == 0 and gpu_uuid_list is None:
                    self.add_env_no_nvidia_gpu()
                elif gpu_uuid_list is not None:
                    self.add_env_share_nvidia_gpu(gpu_uuid_list=gpu_uuid_list)

            elif K8S_RESOURCE_MEMORY_KEY == key:
                self.add_env_jf_memory(value=value)

            elif K8S_RESOURCE_CPU_KEY == key:
                self.add_env_jf_cpu(value=value)

            elif K8S_RESOURCE_EPHEMERAL_STORAGE_KEY == key:
                self.add_env_jf_ephemeral_storage(value=value)

    def add_env_list(self, environments):
        for env in environments:
            self.add_env(name=env["name"], value=env["value"])

class Label():
    def __init__(self, workspace_id, workspace_name, executor_id, executor_name):
        """
        workspace_id (int) : 아이템이 실행 되는 workspace id
        workspace_name (str) : 아이템이 실행 되는 workspace name
        executor_id (int) : 실행자 user id (or 소유자 id)
        executor_name (str) : 실행자 user name (or 소유자 name)
        work_type (str) : GPU 사용 형태가 TRAINING_TYPE | DEPLOYMENT_TYPE 이냐 구분용
        work_func_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C | DEPLOYMENT_ITEM_A
        """
        locals_ = locals().copy()
        try:
            del locals_["self"]
        except:
            pass

        for k, v in locals_.items():
            locals_[k] = str(v)
        self.labels = locals_

        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.executor_id = executor_id
        self.executor_name = executor_name

    def set_training_work_type_labels(self, work_func_type):
        self.labels.update({
            "work_type": TRAINING_TYPE,
            "work_func_type": work_func_type
        })

    def set_deployment_work_type_labels(self, work_func_type):
        self.labels.update({
            "work_type": DEPLOYMENT_TYPE,
            "work_func_type": work_func_type
        })


    def get_tool_default_labels(self, training_name, training_id,
                            training_tool_id, training_tool_type, gpu_count,
                            owner_name, training_type, pod_name, image_id):
        # Labels 생성 시 최소한으로 있어야 하는 정보들
        default_labels = {
            "pod_name": pod_name,
            "training_name": str(training_name),
            "training_id": str(training_id),
            "training_tool_id": str(training_tool_id),
            "training_tool_type": str(training_tool_type),
            "training_total_gpu": str(gpu_count),
            "user": str(owner_name),
            "training_type": str(training_type),
            "image_id": str(image_id)
        }
        self.labels.update(default_labels)
        self.set_training_work_type_labels(work_func_type=TRAINING_ITEM_B)
        return self.labels

    def get_ssh_pod_default_labels(self, pod_info, pod_name, image_id):
        ssh_default_labels = {
            "training_group": pod_name,
            "pod_name": pod_name,
            "training_name": str(pod_info["training_name"]),
            "training_id": str(pod_info["training_id"]),
            "training_tool_id": str(pod_info["training_tool_id"]),
            "training_tool_type": str(pod_info["training_tool_type"]),
            "training_total_gpu": str(pod_info["gpu_count"]),
            "user": pod_info["owner"],
            "training_type": pod_info["training_type"],
            "image_id": str(image_id)
        }
        self.labels.update(ssh_default_labels)
        self.set_training_work_type_labels(work_func_type=TRAINING_ITEM_B)
        return self.labels

    def get_jupyter_default_labels(self, training_name, training_id,
                                        training_tool_id, training_tool_type, gpu_count,
                                        owner_name, training_type, pod_name, image_id):
        """
        training_tool_type (str):
        training_type (str) : advanced | built_in
        """
        jupyter_default_labels = {
            "pod_name": pod_name,
            "training_name": str(training_name),
            "training_id": str(training_id),
            "training_tool_id": str(training_tool_id),
            "training_tool_type": str(training_tool_type),
            "training_total_gpu": str(gpu_count),
            "user": str(owner_name),
            "training_type": str(training_type),
            "image_id": str(image_id)
        }

        self.labels.update(jupyter_default_labels)
        self.set_training_work_type_labels(work_func_type=TRAINING_ITEM_B)
        return self.labels

    def get_job_default_labels(self, training_name, training_id, training_index, training_tool_id,
                                owner_name, training_type, job_name, job_id, job_group_number, job_group_index,
                                create_datetime, total_gpu_count, pod_name, interfaces_type):
        workspace_name = self.workspace_name

        job_default_labels = {
            "training_group": '{}-{}'.format(workspace_name, training_name), # For Training Case
            "training_index": str(training_index),
            "training_total_gpu": str(total_gpu_count),
            "pod_name": pod_name,
            "training_name": str(training_name),
            "training_id": str(training_id),
            "user": str(owner_name),
            "training_type":  str(training_type),  # service or training or jupyter
            "job_name": str(job_name),
            "job_group_number": str(job_group_number),
            "job_group_index": str(job_group_index),
            "job_id": str(job_id),
            "training_tool_id": str(training_tool_id),
            POD_NETWORK_INTERFACE_LABEL_KEY: interfaces_type.replace(" ","-"),
            "create_datetime" : str(common.date_str_to_timestamp(create_datetime)) # 이어하기 생기면 구분을 위해서
        }
        self.labels.update(job_default_labels)
        self.set_training_work_type_labels(TRAINING_ITEM_A)
        return self.labels

    def get_hyperparamsearch_default_labels(self, training_name, training_id, training_index, training_tool_id,
                                            owner_name, training_type, hps_name, hps_id, hps_group_id, hps_group_index,
                                            pod_name, total_gpu_count, interfaces_type):
        workspace_name = self.workspace_name
        hyperparamsearch_default_labels = {
            "training_group": '{}-{}'.format(workspace_name, training_name), # For Training Case
            "training_index": str(training_index),
            "training_total_gpu": str(total_gpu_count),
            "pod_name": pod_name,
            "training_name": str(training_name),
            "training_id": str(training_id),
            "user": str(owner_name),
            "training_type":  str(training_type),  # service or training or jupyter
            "hps_name": str(hps_name),
            "hps_group_id": str(hps_group_id),
            "hps_group_index": str(hps_group_index),
            "hps_id": str(hps_id),
            "training_tool_id": str(training_tool_id),
            POD_NETWORK_INTERFACE_LABEL_KEY: interfaces_type.replace(" ","-")
        }
        self.labels.update(hyperparamsearch_default_labels)
        self.set_training_work_type_labels(TRAINING_ITEM_C)
        return self.labels

    def get_deployment_default_labels(self, total_gpu_count, deployment_name, deployment_id, deployment_worker_id, parent_deployment_worker_id,
                                    owner_name, deployment_type, api_mode, pod_name, pod_base_name):
        deployment_default_labels = {
            "deployment_total_gpu": str(total_gpu_count),
            "pod_name": str(pod_name),
            "pod_base_name": str(pod_base_name),
            "deployment_name": str(deployment_name),
            "deployment_id": str(deployment_id),
            "deployment_worker_id": str(deployment_worker_id),
            "user": str(owner_name),
            "deployment_type":  str(deployment_type),  # service or training or jupyter
            DEPLOYMENT_API_MODE_LABEL_KEY: api_mode,
            PARENT_DEPLOYMENT_WORKER_ID_LABEL_KEY: str(parent_deployment_worker_id)
        }
        self.labels.update(deployment_default_labels)
        self.set_deployment_work_type_labels(DEPLOYMENT_ITEM_A)
        return self.labels

class Volume():
    def __init__(self, pod_name):
        self.volumes = []
        self.volumeMounts = []
        self.pod_name = pod_name

        self._set_init(pod_name=pod_name)

    def _set_init(self, pod_name):
        self._set_pod_status_volumes_and_mounts(pod_name=pod_name)

    def _set_pod_status_volumes_and_mounts(self, pod_name):
        self.volumes.append(kube_common_volume.get_pod_status_flag_volumes(pod_name))
        self.volumeMounts.append(kube_common_volume.get_pod_status_flag_volume_mounts())

    # ADD
    def add_dataset_volumes_and_volume_mounts(self, workspace_name, dataset_name, dataset_access, destination=None):
        if dataset_name is None:
            return 0

        self.volumes += [
            kube_common_volume.get_pod_workspace_dataset_item_volumes(dataset_name=dataset_name, workspace_name=workspace_name, dataset_access=dataset_access)
        ]
        if destination==None:
            self.volumeMounts += [
                kube_common_volume.get_pod_workspace_dataset_item_basic_volume_mounts(dataset_access=dataset_access),
                kube_common_volume.get_pod_workspace_dataset_item_name_volume_mounts(dataset_access=dataset_access, dataset_name=dataset_name)
            ]
        else:
            self.volumeMounts += [
                kube_common_volume.get_pod_deployment_dataset_item_name_volume_mounts(dataset_access=dataset_access, destination=destination)
            ]

    def add_built_in_model_volumes_and_volume_mounts(self, built_in_model_path):
        if built_in_model_path is None:
            return 0

        self.volumes += [
            kube_common_volume.get_pod_built_in_model_volumes(built_in_model_path=built_in_model_path)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_built_in_model_volume_mounts()
        ]

    def add_job_checkpoint_volumes_and_volume_mounts(self, workspace_name, training_name):
        """
        Description :
            Job checkpoint 접근용 mount 추가.
            /jf-home/job-checkpoints
        """
        self.volumes += [
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2()
        ]

    def add_hps_checkpoint_volumes_and_volume_mounts(self, workspace_name, training_name):
        """
        Description :
            hps checkpoint 접근용 mount 추가.
            /jf-home/hps-checkpoints
        """
        self.volumes += [
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2()
        ]

    def add_pod_training_home_src(self, workspace_name, training_name, destination=None):
        self.volumes += [
            kube_common_volume.get_pod_training_home_src_volumes(workspace_name=workspace_name, training_name=training_name)
        ]
        if destination==None:
            self.volumeMounts += [
                kube_common_volume.get_pod_training_home_src_volume_mounts2()
            ]
        else:
            self.volumeMounts += [
                kube_common_volume.get_pod_training_home_src_volume_mounts_destination2(destination=destination)
            ]

    def add_example_and_benchmark_code(self):
        self.volumes += [
            kube_common_volume.get_pod_example_code_volumes(),
            kube_common_volume.get_pod_benchmark_code_volumes()
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_example_code_volume_mounts(),
            kube_common_volume.get_pod_benchmark_code_volume_mounts()
        ]

    def add_checkpoints_volumes_and_volume_mounts(self, workspace_name, dir_name):
        self.volumes += [
            kube_common_volume.get_pod_checkpoint_data_volumes(workspace_name=workspace_name, dir_name=dir_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_checkpoint_data_volume_mounts()
        ]

    def add_userinfo_etc_host_volumes_and_volume_mounts(self, workspace_name, training_name):
        self.volumes += [
            kube_common_volume.get_pod_userinfo_etc_host_volumes(workspace_name=workspace_name, training_name=training_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_userinfo_etc_host_volume_mounts()
        ]

    def add_dataset_ro_volumes_and_volume_mounts(self, workspace_name):
        self.volumes += [
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2()
        ]

    def add_dataset_rw_volumes_and_volume_mounts(self, workspace_name):
        self.volumes += [
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2()
        ]

    # GET
    def get_default_volumes_and_volume_mounts(self, workspace_name, training_name):
        self.add_pod_training_home_src(workspace_name=workspace_name, training_name=training_name)
        self.add_userinfo_etc_host_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)

        return self.volumes, self.volumeMounts

    def get_rstudio_pod_default_volumes_and_volume_mounts(self, workspace_name, training_name):
        self.add_pod_training_home_src(workspace_name=workspace_name, training_name=training_name)
        self.add_userinfo_etc_host_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)
        self.volumes +=[
            kube_common_volume.get_pod_etc_sync_script_volumes(),
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_support_binary_volumes()
        ]
        self.volumeMounts +=[
            kube_common_volume.get_pod_etc_sync_script_volume_mounts(),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2(),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2(),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_support_binary_volume_mounts()
        ]
        return self.volumes, self.volumeMounts

    def get_ssh_pod_default_volumes_and_volume_mounts(self, workspace_name, training_name, owner_name, pod_name):
        self.volumes += [
            kube_common_volume.get_pod_training_home_src_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_userinfo_etc_host_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_etc_sync_script_volumes(),
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_resource_usage_volumes(pod_name),
            kube_common_volume.get_pod_api_deco_volumes(),
            kube_common_volume.get_pod_support_binary_volumes()
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_training_home_src_volume_mounts(owner=owner_name),
            kube_common_volume.get_pod_training_home_src_volume_mounts2(),
            kube_common_volume.get_pod_userinfo_etc_host_volume_mounts(),
            kube_common_volume.get_pod_etc_sync_script_volume_mounts(),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts(owner_name),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2(),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts(owner_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2(),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts(owner_name),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts(owner_name),
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_resource_usage_volume_mounts(pod_name),
            kube_common_volume.get_pod_api_deco_volume_mounts(),
            kube_common_volume.get_pod_support_binary_volume_mounts()
        ]
        return self.volumes, self.volumeMounts

    def get_jupyter_default_volumes_and_volume_mounts(self, workspace_name, training_name, owner_name, pod_name):
        self.volumes += [
            kube_common_volume.get_pod_training_home_src_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_userinfo_etc_host_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_etc_sync_script_volumes(),
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_resource_usage_volumes(pod_name),
            kube_common_volume.get_pod_api_deco_volumes(),
            kube_common_volume.get_pod_support_binary_volumes()
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_training_home_src_volume_mounts(owner=owner_name),
            kube_common_volume.get_pod_training_home_src_volume_mounts2(),
            kube_common_volume.get_pod_userinfo_etc_host_volume_mounts(),
            kube_common_volume.get_pod_etc_sync_script_volume_mounts(),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts(owner_name),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2(),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts(owner_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2(),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts(owner_name),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts(owner_name),
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2(),
            kube_common_volume.get_pod_resource_usage_volume_mounts(pod_name),
            kube_common_volume.get_pod_api_deco_volume_mounts(),
            kube_common_volume.get_pod_support_binary_volume_mounts()
        ]
        return self.volumes, self.volumeMounts

    def get_job_default_volumes_and_volume_mounts(self, workspace_name, training_name, job_name, job_group_index, dataset_name, dataset_access, built_in_path):
        pod_name = self.pod_name
        self.volumes += [
            kube_common_volume.get_pod_resource_usage_volumes(pod_name=pod_name),
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_training_home_src_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_job_logs_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name), # Job Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name), # HPS Checkpoint 접근용
            kube_common_volume.get_pod_example_code_volumes(),
            kube_common_volume.get_pod_benchmark_code_volumes(),
            kube_common_volume.get_pod_training_job_checkpoints_save_volumes(workspace_name=workspace_name, training_name=training_name,
                                                                            job_name=job_name, job_group_index=job_group_index)
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_resource_usage_volume_mounts(pod_name=pod_name),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2(),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2(),
            kube_common_volume.get_pod_training_home_src_volume_mounts2(),
            kube_common_volume.get_pod_training_job_logs_volume_mounts(),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2(), # Job Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2(), # HPS Checkpoint 접근용
            kube_common_volume.get_pod_example_code_volume_mounts(),
            kube_common_volume.get_pod_benchmark_code_volume_mounts(),
            kube_common_volume.get_pod_training_job_checkpoints_save_volume_mounts()
        ]
        self.add_dataset_volumes_and_volume_mounts(workspace_name=workspace_name, dataset_name=dataset_name, dataset_access=dataset_access)
        self.add_built_in_model_volumes_and_volume_mounts(built_in_model_path=built_in_path)
        return self.volumes, self.volumeMounts

    def get_hyperparamsearch_default_volumes_and_volume_mounts(self, workspace_name, training_name, hps_name, hps_group_index,
                                                                    dataset_name, dataset_access, built_in_path):
        pod_name = self.pod_name

        self.add_pod_training_home_src(workspace_name=workspace_name, training_name=training_name)
        self.add_example_and_benchmark_code()
        self.add_dataset_volumes_and_volume_mounts(workspace_name=workspace_name, dataset_name=dataset_name, dataset_access=dataset_access)
        self.add_built_in_model_volumes_and_volume_mounts(built_in_model_path=built_in_path)

        self.volumes += [
            kube_common_volume.get_pod_resource_usage_volumes(pod_name=pod_name),
            kube_common_volume.get_pod_workspace_dataset_ro_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_workspace_dataset_rw_volumes(workspace_name=workspace_name),
            kube_common_volume.get_pod_training_hps_save_load_files_volumes(workspace_name=workspace_name, training_name=training_name, hps_name=hps_name),
            kube_common_volume.get_pod_training_hps_logs_volumes(workspace_name=workspace_name, training_name=training_name),
            kube_common_volume.get_pod_training_job_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name), # Job Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_volumes(workspace_name=workspace_name, training_name=training_name), # HPS Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_save_volumes(workspace_name=workspace_name, training_name=training_name, hps_name=hps_name, hps_group_index=hps_group_index),
            kube_common_volume.get_pod_training_hps_run_file_volumes(),
        ]
        self.volumeMounts += [
            kube_common_volume.get_pod_resource_usage_volume_mounts(),
            kube_common_volume.get_pod_workspace_dataset_ro_volume_mounts2(),
            kube_common_volume.get_pod_workspace_dataset_rw_volume_mounts2(),
            kube_common_volume.get_pod_training_hps_save_load_files_volume_mounts(),
            kube_common_volume.get_pod_training_hps_logs_volume_mounts(),
            kube_common_volume.get_pod_training_job_checkpoints_volume_mounts2(), # Job Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_volume_mounts2(), # HPS Checkpoint 접근용
            kube_common_volume.get_pod_training_hps_checkpoints_save_volume_mounts(),
            kube_common_volume.get_pod_training_hps_run_file_volume_mounts(),
        ]
        return self.volumes, self.volumeMounts

    def get_deployment_default_volumes_and_volume_mounts(self, workspace_name, deployment_name, deployment_worker_id, deployment_template_type,
                                                        built_in_model_path, checkpoint_dir_path,
                                                        pod_name, mounts, training_name=None):
        """
        Description :

        Args:
            workspace_name (str)
            deployment_name (str)
            deployment_worker_id (int)
            deployment_template_type (str) : DEPLOYMENT_RUN_CHEKCPOINT, DEPLOYMENT_RUN_CUSTOM, DEPLOYMENT_RUN_PRETRAINED, DEPLOYMENT_RUN_USERTRAINED

            built_in_model_path

            checkpoint_dir_path
            checkpoint_workspace_name

            training_name (str) *optional : 커스텀 배포나, built_in 사용자 학습 결과가 있을 때 사용
        """

        self.add_dataset_ro_volumes_and_volume_mounts(workspace_name=workspace_name)
        self.add_dataset_rw_volumes_and_volume_mounts(workspace_name=workspace_name)
        if deployment_template_type == DEPLOYMENT_RUN_CUSTOM:
            self.add_job_checkpoint_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)
            self.add_hps_checkpoint_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)
            self.add_pod_training_home_src(workspace_name=workspace_name, training_name=training_name)

        if deployment_template_type == DEPLOYMENT_RUN_USERTRAINED:
            self.add_job_checkpoint_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)
            self.add_hps_checkpoint_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name)

            self.add_built_in_model_volumes_and_volume_mounts(built_in_model_path=built_in_model_path)

        if deployment_template_type == DEPLOYMENT_RUN_PRETRAINED:
            self.add_built_in_model_volumes_and_volume_mounts(built_in_model_path=built_in_model_path)

        if deployment_template_type == DEPLOYMENT_RUN_CHEKCPOINT:
            # self.add_checkpoints_volumes_and_volume_mounts(workspace_name=checkpoint_workspace_name, dir_name=checkpoint_dir_path)
            self.add_checkpoints_volumes_and_volume_mounts(workspace_name=workspace_name, dir_name=checkpoint_dir_path)
            self.add_built_in_model_volumes_and_volume_mounts(built_in_model_path=built_in_model_path)

        if deployment_template_type == DEPLOYMENT_RUN_SANDBOX:
            if mounts !=None:
                training_mount = mounts.get("training")
                dataset_mount = mounts.get("dataset")

            if training_mount != None:
                for info in training_mount:
                    self.add_pod_training_home_src(workspace_name=workspace_name, training_name=info["name"],
                                                    destination=info["destination"])
            if dataset_mount != None:
                for info in dataset_mount:
                    self.add_dataset_volumes_and_volume_mounts(workspace_name=workspace_name, dataset_name=info["name"], dataset_access=info["access"],
                                                    destination=info["destination"])

        self.volumeMounts += [
            kube_common_volume.get_pod_deployment_worker_log_dir_volume_mounts(),
            kube_common_volume.get_pod_deployment_home_volume_mounts(),
            kube_common_volume.get_pod_resource_usage_volume_mounts(),
            kube_common_volume.get_pod_api_deco_volume_mounts(),
            kube_common_volume.get_pod_api_nginx_conf_volume_mounts(),
            kube_common_volume.get_pod_support_binary_volume_mounts()
        ]
        self.volumes  += [
            kube_common_volume.get_pod_deployment_worker_log_dir_volumes(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id),
            kube_common_volume.get_pod_deployment_home_volumes(workspace_name=workspace_name, deployment_name=deployment_name),
            kube_common_volume.get_pod_resource_usage_volumes(pod_name),
            kube_common_volume.get_pod_api_deco_volumes(),
            kube_common_volume.get_pod_api_nginx_conf_volumes(),
            kube_common_volume.get_pod_support_binary_volumes()
        ]
        return self.volumes, self.volumeMounts

class Command():
    def __init__(self):
        self.command = []

    def get_postStart_command(self):
        """
        Description :
            * 여기서 apt install이 들어가면
            E: Could not get lock /var/lib/apt/lists/lock - open (11: Resource temporarily unavailable)
            E: Unable to lock directory /var/lib/apt/lists/
        """
        # return [
        #     "/bin/bash", "-c",
        #     "({pod_configuration_update}) >> /root/configup 2>> /root/configup; ".format(
        #         pod_configuration_update=pod_configuration_update_cmd_(pod_name=pod_name)
        #     )
        # ]
        return [
            "/bin/sh", "-c",
            "touch {}/start;".format(POD_STATUS_IN_POD)
        ]

    def get_preStop_command(self):
        # 강제 종료의 경우 동작 X
        return [
            "/bin/sh", "-c",
            "touch {}/end;".format(POD_STATUS_IN_POD)
        ]

    # def get_XXX_pod_command():
    # "chmod 777 /tmp; "  <- 이미지가 깨진 경우에 대응하려고 했으나.. 플랫폼 역할은 아닌거 같음

    def get_default_command(self):
        return [
            "/bin/bash", "-c",
            "({ssh_setting_cmd});"
            "sleep infinity;".format(
                ssh_setting_cmd=ssh_setting_cmd()
            )
        ]

    def get_ssh_pod_command(self, ssh_banner_string):
        return [
            "/bin/bash", "-c",
            "({pod_resource_record})& " \
            "{pod_env_PATH_setting_cmd_set} "\
            "({api_running_checker_cmd})&"\
            "({ssh_setting_cmd}); "\
            "({ssh_banner_cmd}); "\
            "({ssh_motd_cmd}); "\
            "({api_stop_checker_cmd}); "\
            "sleep infinity; echo 333;".format(
                pod_resource_record=cpu_ram_resource_record_cmd(),
                pod_env_PATH_setting_cmd_set=pod_env_PATH_setting_cmd_set(),
                ssh_setting_cmd=ssh_setting_cmd(),
                ssh_banner_cmd=ssh_banner_cmd(ssh_banner_string),
                ssh_motd_cmd=ssh_motd_cmd(),
                api_running_checker_cmd=get_api_running_checker_cmd(
                    api_port=22,
                    action="rm {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD),
                    init="touch {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD)
                ),
                api_stop_checker_cmd=get_api_stop_checker_cmd(
                    api_port=22,
                    action=create_pod_status_error_flag_cmd()
                )
            )
        ]


    # def get_jupyter_pod_command(self, pod_name, ssh_banner_string, training_tool_type: str):
    #     if TOOL_TYPE[0] == training_tool_type:
    #         common_jupyter_lab_setting_cmd = jupyter_lab_setting_cmd_for_editor
    #     else:
    #         common_jupyter_lab_setting_cmd = jupyter_lab_setting_cmd

    #     command_template = '''({pod_resource_record})& {pod_env_PATH_setting_cmd_set} ({api_running_checker_cmd})& ({ssh_setting_cmd}); ({ssh_banner_cmd}); ({ssh_motd_cmd}); ({jupyter_pod_setting_cmd}); sleep infinity;'''

    #     return command_template.format(
    #             pod_resource_record=cpu_ram_resource_record_cmd(),
    #             pod_env_PATH_setting_cmd_set=pod_env_PATH_setting_cmd_set(),
    #             api_running_checker_cmd=get_api_running_checker_cmd(
    #                 api_port=8888,
    #                 action="rm {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD),
    #                 init="touch {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD)
    #             ),
    #             ssh_setting_cmd=ssh_setting_cmd(),
    #             ssh_banner_cmd=ssh_banner_cmd(ssh_banner_string),
    #             ssh_motd_cmd=ssh_motd_cmd(),
    #             jupyter_pod_setting_cmd=common_jupyter_lab_setting_cmd(get_base_url(pod_name, JUPYTER_FLAG)),
    #         )





    def get_jupyter_pod_command(self, pod_name, ssh_banner_string, training_tool_type: str):
        if TOOL_TYPE[0] == training_tool_type:
            common_jupyter_lab_setting_cmd = jupyter_lab_setting_cmd_for_editor
        else :
            common_jupyter_lab_setting_cmd = jupyter_lab_setting_cmd

        return [
            "/bin/bash", "-c",
            "({pod_resource_record})& " \
            "{pod_env_PATH_setting_cmd_set} "\
            "({api_running_checker_cmd})& "\
            "({ssh_setting_cmd}); "\
            "({ssh_banner_cmd}); "\
            "({ssh_motd_cmd}); "\
            "({jupyter_pod_setting_cmd}); "\
            "sleep infinity;".format(
                pod_resource_record=cpu_ram_resource_record_cmd(),
                pod_env_PATH_setting_cmd_set=pod_env_PATH_setting_cmd_set(),
                api_running_checker_cmd=get_api_running_checker_cmd(
                        api_port=8888,
                        action="rm {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD),
                        init="touch {POD_STATUS_INSTALLING_FLAG_IN_POD}".format(POD_STATUS_INSTALLING_FLAG_IN_POD=POD_STATUS_INSTALLING_FLAG_IN_POD)
                    ),
                ssh_setting_cmd=ssh_setting_cmd(),
                ssh_banner_cmd=ssh_banner_cmd(ssh_banner_string),
                ssh_motd_cmd=ssh_motd_cmd(),
                jupyter_pod_setting_cmd=common_jupyter_lab_setting_cmd(get_base_url(pod_name, JUPYTER_FLAG)),  #jupyter_pod_setting_cmd(owner, base_url_jupyter),
            )
        ]

    def get_rstudio_command(self):
        return [
            "/bin/bash", "-c",
            "({api_running_checker_cmd})&" \
            "({ssh_setting_cmd}); " \
            "({user_home_directory_check_and_change})& "\
            "({r_studio_cmd}); " \
            "({api_stop_checker_cmd}); "\
            "sleep infinity;".format(
                ssh_setting_cmd=ssh_setting_cmd(),
                r_studio_cmd=r_studio_cmd(),
                api_running_checker_cmd=get_api_running_checker_cmd(
                        api_port=DEFAULT_RSTUDIO_PORT,
                        action=remove_pod_status_installing_flag_cmd(),
                        init=create_pod_status_installing_flag_cmd()
                    ),
                user_home_directory_check_and_change=user_home_directory_check_and_change(),
                api_stop_checker_cmd=get_api_stop_checker_cmd(
                    api_port=DEFAULT_RSTUDIO_PORT,
                    action=create_pod_status_error_flag_cmd()
                )
            )
        ]

    def get_file_browser_command(self, base_url : str="/", admin_pw : str=""):
        return [
            "/bin/bash", "-c",
            "({api_running_checker_cmd})&" \
            "({ssh_setting_cmd}); " \
            "({file_browser_cmd}); " \
            "({file_browser_password_change_checker})&" \
            "({get_api_checker_cmd}); "\
            "sleep infinity;".format(
                ssh_setting_cmd=ssh_setting_cmd(),
                api_running_checker_cmd=get_api_running_checker_cmd(
                        api_port=DEFAULT_FILEBROWSER_PORT,
                        action=remove_pod_status_installing_flag_cmd(),
                        init=create_pod_status_installing_flag_cmd()
                    ),
                file_browser_password_change_checker=file_browser_password_change_checker(),
                file_browser_cmd=file_browser_cmd(base_url=base_url, admin_pw=admin_pw),
                get_api_checker_cmd=get_api_checker_cmd(
                    api_port=DEFAULT_FILEBROWSER_PORT,
                    running_action=create_pod_status_running_flag_cmd(),
                    stop_action=create_pod_status_stop_flag_cmd()
                )
            )
        ]

    def get_job_command(self, training_index, total_gpu, hosts, mpi_port, mpi_run_command, pod_name, network_group_category):
        init_command = ""
        if training_index == 0:
            init_command = mpi.get_master_init_command(total_gpu=total_gpu, hosts=hosts, mpi_port=mpi_port, mpi_run=mpi_run_command, network_group_category=network_group_category)
        else :
            init_command = mpi.get_worker_init_command(mpi_port=mpi_port, network_group_category=network_group_category)
        return [
            "/bin/bash", "-c",
            "({pod_resource_record})&" \
            "{init_command}".format(
                pod_resource_record=cpu_ram_resource_record_cmd(),
                init_command=init_command
            )
        ]

    def get_hyperparamsearch_command(self, training_index, search_option_command, mpi_run_command, hps_id,
                                    total_gpu, hosts, mpi_port, pod_name, network_group_category):
        if training_index == 0:
            mpi_run = '{} {} --command "{}" {}'.format(HYPERPARAM_SEARCH_RUN_FILE, search_option_command, mpi_run_command, mpi.get_log_command(item_id=hps_id, log_base=JF_TRAINING_HPS_LOG_DIR_POD_PATH))

            master_init = mpi.get_master_init_command(total_gpu=total_gpu, hosts=hosts, mpi_port=mpi_port, mpi_run=mpi_run, network_group_category=network_group_category)
            return ["/bin/bash", "-c", "({})& {}".format(cpu_ram_resource_record_cmd(), master_init) ]
        else :
            worker_init = mpi.get_worker_init_command(mpi_port=mpi_port, network_group_category=network_group_category)
            return ["/bin/bash", "-c", "({})& {}".format(cpu_ram_resource_record_cmd() ,worker_init) ]

    def get_deployment_command(self, deployment_api_port, run_code, deployment_worker_id=""):

        return [
            "/bin/bash", "-c",
            "{pod_env_PATH_setting_cmd_set}" \
            "({api_running_checker_cmd})& " \
            "{deployment_pod_check_required_bin_command} "\
            "{pod_resource_record_cmd_set}" \
            "{deployment_pod_others_record_cmd_set} " \
            "({check_nginx}); "\
            "({nginx_conf_setting})& "\
            "({pod_deployment_graph_log_command})& " \
            "({pod_deployment_live_graph_log_command})& " \
            "cd {KUBE_ENV_JF_DEPLOYMENT_PWD_KEY_ENV}; " \
            "echo 'DEPLOYMENT RUNCODE START';" \
            "{run_code};".format(
                pod_env_PATH_setting_cmd_set=pod_env_PATH_setting_cmd_set(),
                deployment_pod_check_required_bin_command=deployment_pod_check_required_bin_command(),
                pod_resource_record_cmd_set=pod_resource_record_cmd_set(),
                deployment_pod_others_record_cmd_set=deployment_pod_others_record_cmd_set(),
                check_nginx=get_nginx_install_cmd(),
                nginx_conf_setting=get_nginx_conf_setting(
                    api_running_checker_cmd=get_api_running_checker_cmd(
                        api_port=deployment_api_port,
                        action="echo SKIP",
                        init=""
                    )
                ),
                pod_deployment_graph_log_command=pod_deployment_graph_log_command(deployment_worker_id=deployment_worker_id),
                pod_deployment_live_graph_log_command=pod_deployment_graph_log_command(deployment_worker_id=deployment_worker_id, search_type="live"),
                KUBE_ENV_JF_DEPLOYMENT_PWD_KEY_ENV=KUBE_ENV_JF_DEPLOYMENT_PWD_KEY_ENV,
                api_running_checker_cmd=get_api_running_checker_cmd(
                        api_port=18555,
                        action=remove_pod_status_installing_flag_cmd(),
                        init=create_pod_status_installing_flag_cmd()
                    ),
                run_code=run_code
            )
        ]

#TODO PATH 정리 (PATH의 파라미터화 2021-07-06)



default_hps_checkpoint_path_docker = "/checkpoints-base" # POD 내부에서 /checkpoints -> /checkpoints-base/{n_iter}

# deployment model mount path name
source_path = "source-path"

# deployment api deco mount dic

######################################### 공용 CREAT ########################################
############################################################################################
def create_flag_service(pod_name, service_name, service_port_type=None, service_port_number=None, labels={}, ports=[], service_type=KUBE_SERVICE_TYPE[1],
                        selector=None, no_delete=False, namespace="default"):
    # type= "NodePort" (for ssh) KUBE_SERVICE_TYPE[0] , "ClusterIP" (for ingress) KUBE_SERVICE_TYPE[1]
    # JUPYTERFLAG, DEPLOYMENTFLAG, TENSORBOARDFLAG
    if len(ports) == 0 and (service_port_type is None or service_port_number is None):
        return True

    port_list = []
    if len(ports) == 0:
        ports = [{
            "name": service_port_type,
            "port": service_port_number,
            "targetPort": service_port_number
        }]



    labels["pod_name"] = pod_name
    if selector is None:
        selector = {
            "pod_name": pod_name
        }
    try:
        body = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "selector": selector,
                "type": service_type,
                "ports": ports
            }
        }
        coreV1Api.create_namespaced_service(body=body, namespace=namespace)
    except kubernetes.client.exceptions.ApiException as api_e:
        # print("[",e,"]")
        # print(e.status, type(e.status))
        # print(e.reason)
        # e_body = json.loads(e.body)
        # print("reason",e_body["reason"])
        # print("message",e_body["message"])
        # print("details", str(e.status) + "|" + e_body["details"]["causes"][0]["message"])
        # e.status = Error Code
        # Error Code ( 404 ) 존재 X
        # Error Code ( 409 ) 이미 존재
        # Error Code ( 422 ) Port 중복
        if api_e.status == 422:
            raise KubernetesServiceError(api_e)
        if api_e.status == 409 and no_delete == True:
            return True

        try:
            coreV1Api.delete_namespaced_service(name=service_name, namespace=namespace)
            coreV1Api.create_namespaced_service(body=body, namespace=namespace)
        except kubernetes.client.exceptions.ApiException as api_e:
            if api_e.status == 422:
                raise KubernetesServiceError(api_e)
        except:
            traceback.print_exc()
            return False
    except Exception as e :
        #TODO TEST
        raise e

    return True


def create_ingress(ingress_name, ingress_path, rewrite_target_path, service_name, service_port_number, labels={},
                no_delete=False, namespace="default"):
    try:
        body={
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": ingress_name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "ingressClassName": INGRESS_CLASS_NAME,
                "tls": [{
                    "secretName": "https-ingress"
                }],
                "rules": [{
                    "http": {
                        "paths": [{
                            "path": ingress_path, # ex ) /something(/|$)(.*) ingress_path[:-1] + INGRESS_PATH_ANNOTAION ..  not work ingress_path+"(.*)" ingress_path
                            "pathType": "Prefix",
                            "backend":{
                                "service": {
                                    "name": service_name,
                                    "port": {
                                        "number": service_port_number
                                    }
                                }
                            }
                        }]
                    }
                }]
            }
        }
        extensV1Api.create_namespaced_ingress(body=body, namespace=namespace)
        # body = {
        #     "apiVersion": "extensions/v1beta1",
        #     "kind": "Ingress",
        #     "metadata": {
        #         "name": ingress_name,
        #         "annotations":{
        #             "kubernetes.io/ingress.class": "nginx",
        #             "nginx.ingress.kubernetes.io/proxy-body-size": "50m", # 없으면 1Mb 이상은 안올라감
        #             "nginx.ingress.kubernetes.io/rewrite-target": rewrite_target_path, #/$2
        #             "nginx.ingress.kubernetes.io/ssl-passthrough": "true",
        #             "nginx.ingress.kubernetes.io/backend-protocol": "HTTP",
        #             "nginx.ingress.kubernetes.io/secure-backends": "true",
        #             "nginx.ingress.kubernetes.io/proxy-connect-timeout": str(DEPLOYMENT_RESPONSE_TIMEOUT),
        #             "nginx.ingress.kubernetes.io/proxy-send-timeout": str(DEPLOYMENT_RESPONSE_TIMEOUT),
        #             "nginx.ingress.kubernetes.io/proxy-read-timeout": str(DEPLOYMENT_RESPONSE_TIMEOUT)
        #             # "nginx.ingress.kubernetes.io/proxy-max-temp-file-size": "1024m" # Not Working
        #             # "nginx.ingress.kubernetes.io/enable-cors": "true",
        #             # "nginx.ingress.kubernetes.io/cors-allow-methods": "PUT, GET, POST, OPTIONS",
        #             # "nginx.ingress.kubernetes.io/cors-allow-origin": "*",
        #             # "nginx.ingress.kubernetes.io/cors-allow-credentials": "true"
        #         },
        #         "labels": labels
        #     },
        #     "spec": {
        #         "tls": [{
        #             "secretName": "https-ingress"
        #         }],
        #         "rules": [{
        #             "http": {
        #                 "paths": [{
        #                     "path": ingress_path, # ex ) /something(/|$)(.*) ingress_path[:-1] + INGRESS_PATH_ANNOTAION ..  not work ingress_path+"(.*)" ingress_path
        #                     "pathType": "Prefix",
        #                     "backend":{
        #                         "serviceName": service_name,
        #                         "servicePort": service_port_number
        #                     }
        #                 }
        #                 ]
        #             }
        #         }]
        #     }
        # }
    except kubernetes.client.exceptions.ApiException as api_e:
        if no_delete == True:
            return True
        try:
            extensV1Api.delete_namespaced_ingress(name=ingress_name, namespace=namespace)
            extensV1Api.create_namespaced_ingress(body=body, namespace=namespace)
        except:
            traceback.print_exc()
            return False
    except:
        try:
            extensV1Api.delete_namespaced_ingress(name=ingress_name, namespace=namespace)
            extensV1Api.create_namespaced_ingress(body=body, namespace=namespace)
        except:
            traceback.print_exc()
            return False
    return True


def create_pod(body, pod_name, labels, gpu_count, gpu_model, cpu_model, namespace="default", **kwargs):
    """
    Description :
        Pod 시작 기록 및 Configuration 업데이트를 공통적으로 관리하기 위한 함수

    Args :
        body (dict) : from get_pod_body()
        pod_name (str) : for pod name
        labels (dict) : for pod labels
        gpu_count (int) : for configuration updage
        gpu_model (str) : for configuration updage
        cpu_model (str) : for configuration updage

    Returns :
        Result (Bool), Message (str)
    """
    try:
        # print(body)
        coreV1Api.create_namespaced_pod(body=body, namespace=namespace)

        # # Record Start Time Update
        if kwargs.get("deployment_id"):
            db.update_deployment_start_time_init(deployment_id=kwargs.get("deployment_id"))
        elif kwargs.get("training_tool_id"):
            db.update_training_tool_start_time_init(training_tool_id=kwargs.get("training_tool_id"))
        # elif kwargs.get("job_id"):
        #     db.update_job_start_time(job_id=kwargs.get("job_id"))
        # elif kwargs.get("hps_id"):
        #     db.update_hyperparamsearch_start_time(hps_id=kwargs.get("hps_id"))
        # elif kwargs.get("deployment_worker_id") and kwargs.get("executor_id"):
        #     db.update_deployment_worker_start_time(deployment_worker_id=kwargs.get("deployment_worker_id"), executor_id=kwargs.get("executor_id"))

        kube_data.update_all_list()
        pod_start_new(labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)
        return True, ""

    except Exception as e:
        traceback.print_exc()
        coreV1Api.delete_namespaced_service(name=pod_name, namespace=namespace)
        return False, str(e)

def create_pod_except_api(labels, gpu_count, gpu_model, cpu_model, **kwargs):
    """
    create_pod 함수에서 coreV1Api 실행 부분만 제외
    """
    try:
        # # Record Start Time Update
        if kwargs.get("deployment_id"):
            db.update_deployment_start_time_init(deployment_id=kwargs.get("deployment_id"))
        elif kwargs.get("training_tool_id"):
            db.update_training_tool_start_time_init(training_tool_id=kwargs.get("training_tool_id"))
        kube_data.update_all_list()
        pod_start_new(labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

########################################### 공용 ###########################################
############################################################################################
def gen_built_in_run_code(built_in_model_info, total_gpu):
    run_code = built_in_model_info["training_py_command"]
    if built_in_model_info["checkpoint_save_path_parser"] is not None and built_in_model_info["checkpoint_save_path_parser"] != "":
        run_code += " --{} {} ".format(built_in_model_info["checkpoint_save_path_parser"], JF_TRAINING_CHECKPOINT_ITEM_POD_STATIC_PATH)

    if built_in_model_info["training_num_of_gpu_parser"] is not None and built_in_model_info["training_num_of_gpu_parser"] != "":
        run_code += " --{} {} ".format(built_in_model_info["training_num_of_gpu_parser"], total_gpu)

    return run_code

def get_run_code(run_code, built_in_model_info, total_gpu):
    run_code = run_code
    if built_in_model_info is not None:
        run_code = gen_built_in_run_code(built_in_model_info, total_gpu)
    return run_code

def get_item_name(pod_name, FLAG=None):
    # for ingress or service name
    item_name = "{}-{}".format(pod_name, FLAG) if FLAG is not None else pod_name
    return item_name

def get_node_hosts_and_nifs_and_exnifs(node_groups, interfaces):
    hosts = ",".join([ "{}:{}".format(node["ip"],node["gpu_usage"]) for node in node_groups])
    nifs = ",".join(interfaces["include"])
    exnifs = ",".join(interfaces["exclude"])

    return hosts, nifs, exnifs


def get_kube_resource_limits(gpu_use, gpu_resource_key, resource_limits, network_ib_use=None):
    # memory: "1Gi"
    # cpu: "3.5"
    # ephemeral-storage: "100Mi"
    if gpu_use == 0:
        kube_resource_limits = {}
    else :
        kube_resource_limits = {
            gpu_resource_key: gpu_use
        }
    node_cpu_cores = int(resource_limits.get("node_cpu_cores")) if resource_limits.get("node_cpu_cores") is not None else None
    node_ram = int(float(resource_limits.get("node_ram").replace("GB", ""))) if resource_limits.get("node_ram") is not None else None
    if gpu_use == 0:
        if resource_limits.get(NODE_CPU_LIMIT_PER_POD_DB_KEY) is not None:
            kube_resource_limits["cpu"] = str(resource_limits.get(NODE_CPU_LIMIT_PER_POD_DB_KEY))
            # pass

        if resource_limits.get(NODE_MEMORY_LIMIT_PER_POD_DB_KEY) is not None:
            kube_resource_limits["memory"] = str(resource_limits.get(NODE_MEMORY_LIMIT_PER_POD_DB_KEY))+"Gi"
            # pass

    else :
        if resource_limits.get(NODE_CPU_LIMIT_PER_GPU_DB_KEY) is not None:
            cpu_cores_limit = int(resource_limits.get(NODE_CPU_LIMIT_PER_GPU_DB_KEY)) * gpu_use
            cpu_cores_limit = min(node_cpu_cores, cpu_cores_limit)
            kube_resource_limits["cpu"] = str(cpu_cores_limit)
        elif node_cpu_cores is not None:
            kube_resource_limits["cpu"] = str(node_cpu_cores)

        if resource_limits.get(NODE_MEMORY_LIMIT_PER_GPU_DB_KEY) is not None:
            ram_limit = int(resource_limits.get(NODE_MEMORY_LIMIT_PER_GPU_DB_KEY)) * gpu_use
            ram_limit = min(node_ram, ram_limit)
            kube_resource_limits["memory"] = str(ram_limit)+"Gi"
        elif node_ram is not None:
            kube_resource_limits["memory"] = str(node_ram)+"Gi"

    if resource_limits.get("ephemeral_storage_limit") is not None:
        kube_resource_limits["ephemeral-storage"] = str(float(resource_limits.get("ephemeral_storage_limit")))+"Gi"

    if network_ib_use is not None:
        kube_resource_limits[IB_RESOURCE_LABEL_KEY] = 1

    print("KUBE RESOURCE", kube_resource_limits)

    return kube_resource_limits

def get_check_is_default_image(image):
    #TODO jf default 이미지에 대한 범위 정의 필요 (2021-06-14)
    if image is None:
        #이미지가 삭제 된 경우 여기서 None을 그대로 내려보냄
        return False

    if "jf_default" in image:
        return True
    return False


def get_pod_body(pod_name, labels, image, gpu_use, resource_limits,
                volume_mounts, volumes, command, container_name=None,
                env=None, postStart_command=None, preStop_command=None,
                node_name=None, mpi_port=None, annotations=None, restartPolicy="Never",
                hostNetwork=False, privileged=True, gpu_image_run_as_cpu=False, gpu_share_mode=False,
                namespace="default"):
    """
    Description :

    Args :
        gpu_image_run_as_cpu (bool) : gpu_use = 0 일 때 동작하며
                                      True = 사용자가 지정한 image를 그대로 사용
                                      False = jf_ml_cpu_image:latest로 변경해 사용 (해당 파라미터는 더 이상 필요 없어져 아마 삭제 예정)
    Returns :
        (dict) : kubernetes pod body용 dict
    """
    # =======================
    # hostNetwork = False
    # Training Jupyter(GPU)
    # Training Editor(CPU)
    # Deployment
    # =======================
    # =======================
    # hostNetwork = True
    # Training Job, Hps

    if annotations is None:
        annotations = {}
    if container_name is None:
        container_name = pod_name

    if gpu_share_mode == True:
        if NVIDIA_GPU_RESOURCE_LABEL_KEY in resource_limits:
            del resource_limits[NVIDIA_GPU_RESOURCE_LABEL_KEY]

    body = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "labels": labels,
            "annotations": annotations,
            "namespace": namespace
        },
        "spec": {
            "hostNetwork": hostNetwork,
            "hostIPC": True, #TODO JI Docker에서 사용하는 부분이 있음
            "restartPolicy": restartPolicy, # For training (Never) , For Deployment (Always)
            "terminationGracePeriodSeconds": 0,
            "hostname": container_name,
            "containers": [{
                "name": container_name,
                "image": image,
                "securityContext": {
                    "privileged": privileged,
                    "runAsUser": 0,
                    "runAsGroup": 0,
                    "fsGroup": 0,
                    "capabilities": {
                        "add": [
                            "IPC_LOCK"
                        ]
                    }
                },
                "imagePullPolicy": "IfNotPresent",
                "command": command,
                "resources": {
                    "requests": {
                        "cpu": "0",
                        "memory": "0",
                        "ephemeral-storage": "0"
                    },
                    "limits": resource_limits
                },
                "volumeMounts": volume_mounts,
                "lifecycle": {
                    "postStart": {
                        "exec": {
                            "command": ["/bin/sh", "-c", "echo START"]
                        }
                    },
                    "preStop": {
                        "exec": {
                            "command": ["/bin/sh", "-c", "echo END"]
                        }
                    }
                }
            }],
            "volumes": volumes
        }
    }

    # HPS
    # if gpu_use == 0:
    #     if env is None:
    #         env = []
    #     env += [
    #         {
    #             "name": "NVIDIA_VISIBLE_DEVICES",
    #             "value": ""
    #         }
    #         ]
    # #--> CUDA BASE  이미지를 사용하면서 GPU 0개로 보이게 할 순 있으나
    # # GPU가 없는 서버에서는 동작 할 수 없음
    if env is not None:
        body["spec"]["containers"][0]["env"] = env

    # ALL
    #TODO gpu_use = 0 and RUN_ON_CPU_NODE == True --> nodeselector (CPU NODES)
    if node_name is not None:
        body["spec"]["nodeName"] = node_name # TODO nodeselector
    # nodeSelector Part
    # if gpu_use == 0 :
    #     body["spec"]["nodeSelector"] = {
    #         "cpu_worker_node": "True"
    #     }

    if get_check_is_default_image(image) == True and gpu_image_run_as_cpu == False:
        if gpu_use == 0:
            body["spec"]["containers"][0]["image"] = JF_CPU_DEFAULT_IMAGE

    # ALL
    if postStart_command is not None:
        body["spec"]["containers"][0]["lifecycle"]["postStart"]["exec"]["command"] = postStart_command

    if preStop_command is not None:
        # 내부에서 정상적 종료가 아니라면 동작 안함
        body["spec"]["containers"][0]["lifecycle"]["preStop"]["exec"]["command"] = preStop_command

    if mpi_port is not None:
        body["metadata"]["labels"]["training_mpi_port"] = str(mpi_port)

    return body

# def is_rdma(pod_info, interfaces):
#     if pod_info["rdma"] == 1 and interfaces["type"] == INTERFACE_IB_OUTPUT:
#         return 1
#     else :
#         return 0

def is_rdma(network_group_category):
    # Infiniband가 있다고 하더라도 RDMA가 되는건 다른 문제임 - GPU가 지원하느냐, 하드웨어가 지원해주느냐
    if network_group_category == NETWORK_GROUP_CATEGORY_INFINIBAND:
        return 1
    return 0

def get_mpirun_command(rdma, gpu_acceleration, total_gpu, hosts, nifs, mpi_port, exnifs, run_code, parameter, item_id=None, log_base=None):
    with_log = True
    if item_id is None or log_base is None:
        with_log = False

    if rdma == 1:
        mpi_run_command_func = mpi.get_rdma_run_command
    elif gpu_acceleration == 1:
        mpi_run_command_func = mpi.get_p2p_run_command
    else :
        mpi_run_command_func = mpi.get_default_run_command

    if total_gpu == 0:
        mpi_run_command_func = mpi.get_cpu_run_command


    mpi_run_command = mpi_run_command_func(total_gpu=total_gpu, hosts=hosts, nifs=nifs, mpi_port=mpi_port, exnifs=exnifs,
                        run_code=run_code, parameter=parameter, item_id=item_id, log_base=log_base, with_log=with_log)


    return mpi_run_command

def get_base_url(pod_name, FLAG, rewrite_annotaion=False):
    flag = FLAG.replace("-","")
    # base_url = "/{flag}/{hash}".format(flag=flag, hash=common.gen_hash(pod_name.replace("-","0")))
    base_url = "/{flag}/{pod_name}/".format(flag=flag, pod_name=pod_name)

    if rewrite_annotaion == True:
        base_url = base_url[:-1] + INGRESS_PATH_ANNOTAION

    return base_url



########################################### FOR JOB ###########################################
###############################################################################################
def get_job_parameter(run_parameter, unified_memory):
    parameter = run_parameter
    if unified_memory == 1:
        parameter += " --unified_memory 1 "

    return parameter



########################################### FOR HPS ###########################################
###############################################################################################
def get_hyperparamsearch_search_option_command(search_method, init_points, search_count, search_interval, save_file_name, load_file_name, int_parameter):
    search_option = "--method {} ".format(search_method)
    if init_points is not None:
        search_option += " --init_points {} ".format(init_points)
    if search_count is not None:
        search_option += " --n_iter {} ".format(search_count)
    if search_interval is not None:
        search_option += " --interval {} ".format(search_interval)

    if save_file_name is not None:
        search_option += " --save_data {0}/{1}  ".format(JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name)
    if load_file_name is not None:
        search_option += " --load_data {0}/{1} ".format(JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, load_file_name)

    if int_parameter is not None and int_parameter != "":
        search_option += " --int_parameter {}".format(int_parameter)


    # search_option += "--save_data {0}/{1} --load_data {0}/{2}".format(JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name, load_file_name)

    return search_option

def get_hyperparamsearch_parameter(run_parameter, search_parameter):
    parameter = "{run_param} {search_param}".format(run_param=run_parameter, search_param=search_parameter)
    return parameter

######################################### FOR JUPYTER #########################################
###############################################################################################
def ports_to_service_ports(ports):
    # DB DATA TO KUBE FORM
    # for kuber service body.spec.ports
    service_ports = []
    for port in ports:
        if port["system_definition"] == 1:
            continue
        service_ports.append({
                "name": port["name"],
                "port": port["target_port"],
                "targetPort": port["target_port"],
                "protocol": port["protocol"],
                "nodePort": port["node_port"]
            })

    return service_ports

def get_processed_port_list(port_list, system_definition, service_type):
    # system_definition = 0, 1 # 0 = user define, 1 = system define
    # service_type = NodePort, ClusterIP
    processed_port_list = []
    if port_list is None:
        return processed_port_list

    for port in port_list:
        print("P" , port)
        print("P I ", port["system_definition"], system_definition)
        if port["system_definition"] == system_definition and port["service_type"] == service_type:
            processed_port_list.append({
                "name": port["name"],
                "port": port["target_port"],
                "targetPort": port["target_port"],
                "protocol": port["protocol"],
                "nodePort": port["node_port"]
            })
    return processed_port_list

def service_create_with_port_list(pod_name, port_list, labels, system_definition, service_type, NAME_FLAG):
    processed_port_list = get_processed_port_list(port_list, system_definition=system_definition, service_type=service_type)
    if len(processed_port_list) == 0:
        print("No ", system_definition, service_type, NAME_FLAG)
        return True
    service_name = get_item_name(pod_name, NAME_FLAG)
    create_flag_service(pod_name=pod_name, service_name=service_name, labels=labels, ports=processed_port_list, service_type=service_type)

def jupyter_ingress_create(pod_name, labels, service_port_number):
    service_name = get_item_name(pod_name, SYSTEM_CLUSTER_IP_PORT_FLAG)
    base_url_jupyter = get_base_url(pod_name, JUPYTER_FLAG)
    create_ingress(ingress_name=service_name, ingress_path=base_url_jupyter, rewrite_target_path=base_url_jupyter,
                        service_name=service_name, service_port_number=service_port_number, labels=labels)

def service_create_user_node_port_list(pod_name, port_list, labels):
    service_labels = dict(labels)
    service_labels[DEPLOYMENT_SERVICE_TYPE_LABEL_KEY] = DEPLOYMENT_SERVICE_USER_NODE_PORT_VALUE
    service_create_with_port_list(pod_name=pod_name, port_list=port_list, labels=service_labels,
                                system_definition=0, service_type=KUBE_SERVICE_TYPE[0], NAME_FLAG=USERPORT_NODEPORT_FLAG)

def service_create_user_cluster_ip_list(pod_name, port_list, labels):
    #TODO CHECK, Supoort not yet
    service_labels = dict(labels)
    service_labels[DEPLOYMENT_SERVICE_TYPE_LABEL_KEY] = DEPLOYMENT_SERVICE_USER_CLUSTER_IP_VALUE
    service_create_with_port_list(pod_name=pod_name, port_list=port_list, labels=service_labels,
                                system_definition=0, service_type=KUBE_SERVICE_TYPE[1], NAME_FLAG=USERPORT_CLUSTER_IP_PORT_FLAG)

def service_create_system_node_port_list(pod_name, port_list, labels):
    service_labels = dict(labels)
    service_labels[DEPLOYMENT_SERVICE_TYPE_LABEL_KEY] = DEPLOYMENT_SERVICE_SYSTEM_NODE_PORT_VALUE
    service_create_with_port_list(pod_name=pod_name, port_list=port_list, labels=service_labels,
                                system_definition=1, service_type=KUBE_SERVICE_TYPE[0], NAME_FLAG=SYSTEM_NODEPORT_FLAG)

def service_create_system_cluster_ip_list(pod_name, port_list, labels):
    service_labels = dict(labels)
    service_labels[DEPLOYMENT_SERVICE_TYPE_LABEL_KEY] = DEPLOYMENT_SERVICE_SYSTEM_CLUSTER_IP_VALUE
    service_create_with_port_list(pod_name=pod_name, port_list=port_list, labels=service_labels,
                                system_definition=1, service_type=KUBE_SERVICE_TYPE[1], NAME_FLAG=SYSTEM_CLUSTER_IP_PORT_FLAG)



####################################### FOR POD CREATE ########################################
###############################################################################################
#TODO job 실행 시 worker node env 에 제대로 값이 담길 수 있도록 mpirun 명령어 수정 필요
# TRAINING - TOOL
def create_tool_empty(pod_info, node_info):
    # 최소 요구 정보 경우에 따라 추가 가능함
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    training_type = pod_info["training_type"]
    training_tool_id = pod_info["training_tool_id"]
    training_tool_type = pod_info["training_tool_type"]
    training_tool_replica_number = pod_info["training_tool_replica_number"]
    owner_name = pod_info["owner"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    ports = pod_info["ports"]

    image = pod_info["image"]
    image_name = pod_info["image_name"]
    image_id = pod_info["image_id"]
    gpu_count = pod_info["gpu_count"]

    ## node_info_manager
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()


    # RESOURCE SETTING
    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)

    # ENV SETTING
    env_object = ENV(owner_name=owner_name, item_id=training_tool_id)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    # POD NAME SETTING
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name,
                                                                item_type=training_tool_type, sub_flag=training_tool_replica_number).get_all()

    # LABEL SETTING
    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_tool_default_labels(training_name=training_name, training_id=training_id,
                                        training_tool_id=training_tool_id, training_tool_type=training_tool_type, gpu_count=gpu_count,
                                        owner_name=owner_name, training_type=training_type, pod_name=unique_pod_name, image_id=image_id)

    # VOLUME SETTING
    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_default_volumes_and_volume_mounts(training_name=training_name, workspace_name=workspace_name)

    # COMMAND SETTING
    command_object = Command()
    command = command_object.get_default_command()
    postStart_command = command_object.get_postStart_command()
    preStop_command = command_object.get_preStop_command()

    # PORT SETTING
    try :
        delete_service_training_tool(training_tool_id=training_tool_id)
        service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_user_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
    except CustomErrorList as ce:
        rollback_service(unique_pod_name)
        raise ce
    except Exception as e:
        raise e



    body = get_pod_body(pod_name=unique_pod_name, container_name=container_name, labels=labels, image=image, gpu_use=gpu_count,
                resource_limits=kube_resource_limits, env=env_object.get_env_list(),
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                annotations=annotations,
                postStart_command=postStart_command, preStop_command=preStop_command,
                node_name=node_name, privileged=False, gpu_image_run_as_cpu=True)

    return create_pod(body=body, pod_name=unique_pod_name, training_tool_id=training_tool_id,
                    labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)

def create_job_pod(pod_info, training_index, node_info_manager, mpi_port):
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    job_name = pod_info["job_name"]
    job_id = pod_info["job_id"]
    training_tool_id = pod_info.get("training_tool_id")
    owner_name = pod_info["owner_name"]
    executor_name = pod_info["creator_name"]
    executor_id = pod_info["creator_id"]
    training_type = pod_info["training_type"]
    image = pod_info["image"]
    run_code = pod_info["run_code"]
    parameter = pod_info["parameter"]
    job_group_number = pod_info["job_group_number"]
    job_group_index = pod_info["job_group_index"]
    total_gpu = pod_info["gpu_count"]
    dataset_access = pod_info["dataset_access"]
    dataset_name = pod_info["dataset_name"]
    create_datetime = str(common.date_str_to_timestamp(pod_info["create_datetime"]))
    built_in_model_info = pod_info.get("built_in_model_info")

    mpi_port = mpi_port
    # node_info_manager
    hosts, nifs, exnifs = node_info_manager.get_hosts_include_interfaces_exclude_interfaces()
    node_info = node_info_manager.node_info_list[training_index]
    gpu_usage = node_info.get_requested_gpu_count()
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits(requested_network_group_only=True)
    cpu_model = node_info.get_cpu_model()
    network_interface_type = node_info.get_requested_network_group_name()
    network_group_info = node_info.get_requested_network_group_info()
    network_group_name = network_group_info.network_group_name
    network_group_category = network_group_info.category
    ## resource_info
    # training_index = training_index
    # selected_node = node_groups[training_index]
    # gpu_usage = selected_node["gpu_usage"]
    # node_name = selected_node["node"]
    # mpi_port = selected_node["mpi_port"]
    # gpu_resource_key = selected_node["gpu_resource_key"]
    # resource_limits = selected_node["resource_limits"]
    # network_interface_type = interfaces["type"] # INFINI or 10G or 1G
    # gpu_model = selected_node.get("gpu_model")
    # cpu_model = selected_node.get(NODE_CPU_MODEL_KEY)

    # hosts, nifs, exnifs = get_node_hosts_and_nifs_and_exnifs(node_groups=node_groups, interfaces=interfaces)

    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name, item_type=TRAINING_ITEM_A, sub_item_name=job_name, sub_flag="{}-{}".format(job_group_index,training_index)).get_all()

    env_object = ENV(owner_name=owner_name, item_id=job_id)
    env_object.add_default_env_job(log_base=JF_TRAINING_JOB_LOG_DIR_POD_PATH, job_id=job_id, hosts=hosts, total_gpu_count=total_gpu)
    # env_object.add_resource_info_env(gpu_use=gpu_usage, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    parameter = get_job_parameter(run_parameter=parameter, unified_memory=pod_info.get("unified_memory"))

    run_code = get_run_code(run_code=run_code, built_in_model_info=built_in_model_info, total_gpu=total_gpu)

    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_job_default_volumes_and_volume_mounts(
        workspace_name=workspace_name, training_name=training_name, job_name=job_name, job_group_index=job_group_index,
        dataset_name=dataset_name, dataset_access=dataset_access, built_in_path=pod_info.get("built_in_path"))


    labels_object = Label(workspace_id=workspace_id, workspace_name=workspace_name, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_job_default_labels(training_name=training_name, training_id=training_id, training_index=training_index, training_tool_id=training_tool_id,
                                owner_name=owner_name, training_type=training_type, job_name=job_name, job_id=job_id,
                                job_group_number=job_group_number, job_group_index=job_group_index,
                                create_datetime=create_datetime, total_gpu_count=total_gpu, pod_name=unique_pod_name, interfaces_type=network_interface_type)

    postStart_command = None

    mpi_run_command = get_mpirun_command(rdma=is_rdma(network_group_category=network_group_category), gpu_acceleration=pod_info["gpu_acceleration"],
                                        total_gpu=total_gpu, hosts=hosts, nifs=nifs, mpi_port=mpi_port, exnifs=exnifs,
                                        run_code=run_code, parameter=parameter, item_id=job_id, log_base=JF_TRAINING_JOB_LOG_DIR_POD_PATH)

    command = Command().get_job_command(training_index=training_index, total_gpu=total_gpu, hosts=hosts, mpi_port=mpi_port,
                            mpi_run_command=mpi_run_command, pod_name=unique_pod_name, network_group_category=network_group_category)

    # kuber_resource_limits = get_kube_resource_limits(gpu_use=gpu_usage, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits)


    body = get_pod_body(pod_name=unique_pod_name, labels=labels, image=image, gpu_use=gpu_usage,
            resource_limits=kube_resource_limits,
            volume_mounts=volume_mounts, volumes=volumes, command=command,
            env=env_object.get_env_list(), postStart_command=postStart_command, node_name=node_name,
            gpu_image_run_as_cpu=True, mpi_port=mpi_port, hostNetwork=True)

    return create_pod(body=body, pod_name=unique_pod_name, job_id=job_id,
                    labels=labels, gpu_count=gpu_usage, gpu_model=gpu_model, cpu_model=cpu_model)
    # try:
    #     coreV1Api.create_namespaced_pod(body=body, namespace="default")
    #     return True
    # except Exception as e :
    #     traceback.print_exc()
    #     return False

def create_hyperparamsearch_pod(pod_info, training_index, node_info_manager, mpi_port):
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    hps_name = pod_info["hps_name"]
    hps_id = pod_info["hps_id"]
    owner_name = pod_info["owner_name"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["creator_name"]
    training_type = pod_info["training_type"]
    image = pod_info["image"]
    run_code = pod_info["run_code"]
    run_parameter = pod_info["run_parameter"]
    search_parameter = pod_info["search_parameter"]
    int_parameter = pod_info["int_parameter"]
    hps_group_id = pod_info["hps_group_id"]
    hps_group_index = pod_info["hps_group_index"]
    total_gpu_count = pod_info["gpu_count"]
    dataset_access = pod_info["dataset_access"]
    dataset_name = pod_info["dataset_name"]
    training_tool_id = pod_info["training_tool_id"]

    search_method = pod_info["method"]
    search_count = pod_info["search_count"]
    search_interval = pod_info["search_interval"]
    init_points = pod_info["init_points"]
    save_file_name = pod_info["save_file_name"]
    load_file_name = pod_info["load_file_name"]


    mpi_port = mpi_port
    # node_info_manager
    hosts, nifs, exnifs = node_info_manager.get_hosts_include_interfaces_exclude_interfaces()
    node_info = node_info_manager.node_info_list[training_index]
    gpu_usage = node_info.get_requested_gpu_count()
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits(requested_network_group_only=True)
    cpu_model = node_info.get_cpu_model()
    network_interface_type = node_info.get_requested_network_group_name()
    network_group_info = node_info.get_requested_network_group_info()
    network_group_name = network_group_info.network_group_name
    network_group_category = network_group_info.category

    # ## resource info
    # training_index = training_index
    # selected_node = node_groups[training_index]
    # gpu_usage = selected_node["gpu_usage"]
    # node_name = selected_node["node"]
    # mpi_port = selected_node["mpi_port"]
    # gpu_resource_key = selected_node["gpu_resource_key"]
    # resource_limits = selected_node["resource_limits"]
    # network_interface_type = interfaces["type"]
    # gpu_model = selected_node.get("gpu_model")
    # cpu_model = selected_node.get(NODE_CPU_MODEL_KEY)

    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name, item_type=TRAINING_ITEM_C, sub_item_name=hps_name, sub_flag="{}-{}".format(hps_group_index, training_index)).get_all()

    env_object = ENV(owner_name=owner_name, item_id=hps_id)
    env_object.add_default_env_hyperparamsearch(hps_id=hps_id, hps_name=hps_name, save_file_name=save_file_name, load_file_name=load_file_name,
                                                hosts=hosts, total_gpu_count=total_gpu_count)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    search_option_command = get_hyperparamsearch_search_option_command(search_method=search_method, init_points=init_points, search_count=search_count,
                                                            search_interval=search_interval, save_file_name=save_file_name, load_file_name=load_file_name,
                                                            int_parameter=int_parameter)

    parameter = get_hyperparamsearch_parameter(run_parameter=run_parameter, search_parameter=search_parameter)
    run_code = get_run_code(run_code=run_code, built_in_model_info=pod_info.get("built_in_model_info"), total_gpu=total_gpu_count)


    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_hyperparamsearch_default_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name,
                                                                hps_name=hps_name, hps_group_index=hps_group_index, dataset_name=dataset_name, dataset_access=dataset_access,
                                                                built_in_path=pod_info["built_in_path"])

    labels_object = Label(workspace_id=workspace_id, workspace_name=workspace_name, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_hyperparamsearch_default_labels(training_name=training_name, training_id=training_id, training_index=training_index,
                                            training_tool_id=training_tool_id,
                                            owner_name=owner_name, training_type=training_type, hps_name=hps_name, hps_id=hps_id,
                                            hps_group_id=hps_group_id, hps_group_index=hps_group_index, pod_name=unique_pod_name,
                                            total_gpu_count=total_gpu_count, interfaces_type=network_interface_type)

    postStart_command = None

    mpi_run_command = get_mpirun_command(rdma=is_rdma(network_group_category=network_group_category), gpu_acceleration=pod_info["gpu_acceleration"],
                                        total_gpu=total_gpu_count, hosts=hosts, nifs=nifs, mpi_port=mpi_port, exnifs=exnifs,
                                        run_code=run_code, parameter=parameter)

    command = Command().get_hyperparamsearch_command(training_index=training_index, search_option_command=search_option_command, mpi_run_command=mpi_run_command,
                                hps_id=hps_id, total_gpu=total_gpu_count, hosts=hosts, mpi_port=mpi_port, pod_name=unique_pod_name, network_group_category=network_group_category)

    # kuber_resource_limits = get_kube_resource_limits(gpu_use=gpu_usage, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits)

    body = get_pod_body(pod_name=unique_pod_name, labels=labels, image=image, gpu_use=gpu_usage,
                resource_limits=kube_resource_limits,
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                env=env_object.get_env_list(), postStart_command=postStart_command, node_name=node_name,
                mpi_port=mpi_port, gpu_image_run_as_cpu=True,
                hostNetwork=True)

    return create_pod(body=body, pod_name=unique_pod_name, hps_id=hps_id,
                labels=labels, gpu_count=gpu_usage, gpu_model=gpu_model, cpu_model=cpu_model)
    # try:
    #     coreV1Api.create_namespaced_pod(body=body, namespace="default")
    #     return True
    # except Exception as e :
    #     traceback.print_exc()
    #     return False

def create_jupyter_pod(pod_info, node_info):
    def rollback_service(pod_name, namespace="default"):
        service_flag_list = [ USERPORT_NODEPORT_FLAG, USERPORT_CLUSTER_IP_PORT_FLAG, SYSTEM_NODEPORT_FLAG, SYSTEM_CLUSTER_IP_PORT_FLAG ]
        for flag in service_flag_list:
            service_name = get_item_name(pod_name, flag)
            try:
                delete_service(service_name=service_name, namespace=namespace)
            except :
                pass

    # jupyter_pod_info = {
    #     "workspace_name": workspace_name,
    #     "workspace_id": workspace_id,
    #     "training_name": training_name,
    #     "training_id": training_id,
    #     "training_tool_id": training_tool_id,
    #     "owner": owner_name,
    #     "executor_id": db.get_user(user_name=headers_user)["id"],
    #     "executor_name": headers_user,
    #     "training_type": training_type,
    #     "gpu_count": req_gpu_count,
    #     "editor": editor,
    #     "image": image,
    #     "users": users,
    #     "ports": None
    # }
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    training_tool_id = pod_info["training_tool_id"]
    training_tool_type = pod_info["training_tool_type"]
    training_tool_replica_number = pod_info["training_tool_replica_number"]
    owner_name = pod_info["owner"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    training_type = pod_info["training_type"]
    gpu_count = pod_info["gpu_count"]
    # editor = pod_info["editor"]
    image = JF_CPU_DEFAULT_IMAGE if training_tool_type == TOOL_TYPE[0] else pod_info["image"]
    image_name = pod_info["image_name"]
    image_id = pod_info["image_id"]
    # image = pod_info["image"]
    users = pod_info["users"]
    ports = pod_info["ports"]
    namespace = pod_info.get("namespace", "default")

    ## node_info_manager
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()
    ## resource info
    # node_info = node_groups[0]
    # node_name = node_info["node"]
    # gpu_resource_key = node_info["gpu_resource_key"]
    # resource_limits = node_info["resource_limits"]
    # gpu_model = node_info.get("gpu_model")
    # cpu_model = node_info.get(NODE_CPU_MODEL_KEY)

    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)

    env_object = ENV(owner_name=owner_name, item_id=training_tool_id)

    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name,
                                                                    item_type=training_tool_type, sub_flag=training_tool_replica_number).get_all()
    lables_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    labels = lables_object.get_jupyter_default_labels(training_name=training_name, training_id=training_id,
                                        training_tool_id=training_tool_id, training_tool_type=training_tool_type, gpu_count=gpu_count,
                                        owner_name=owner_name, training_type=training_type, pod_name=unique_pod_name, image_id=image_id)


    ssh_banner_string = "[{}] Workspace [{}] Training [{}] SSH".format(workspace_name, training_name, training_tool_type)

    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    # default_ports = [{"type":"ssh", "target_port": 22, "protocol": "TCP"}] # for ssh
    # pod_ports = ports_to_pod_ports(ports+default_ports)
    # ports = [{"type":"custom-test", "target_port": 1234, "protocol": "TCP"}]
    # service_ports = ports_to_service_ports(ports)

    # TODO NodePort | ClusterIP  구분하여 Service 구동할 수 있도록
    # SYSTEM - NodePort | ClusterIP
    # USER - NodePort 로 구성
    try :
        delete_service_training_tool(training_tool_id=training_tool_id)
        # [MSA 변경]
        """
        node port 사용 X -> 주석처리해둠(SSH를 다시 nodeport로 한다면 주석해제해야함)
        # service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        # service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        """
        # service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_user_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        # service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
    except CustomErrorList as ce:
        rollback_service(unique_pod_name, namespace=namespace)
        raise ce
    except Exception as e:
        raise e

    for port in ports:
        if port["system_definition"] == 1 and port["name"] == DEFAULT_JUPYTER_PORT_NAME:
            jupyter_ingress_create(pod_name=unique_pod_name, labels=labels, service_port_number=port["target_port"])

    volumes, volume_mounts = Volume(pod_name=unique_pod_name).get_jupyter_default_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name,
                                                                                owner_name=owner_name, pod_name=unique_pod_name)
    command = Command().get_jupyter_pod_command(pod_name=unique_pod_name, ssh_banner_string=ssh_banner_string, training_tool_type=training_tool_type)

    postStart_command = None

    body = get_pod_body(pod_name=unique_pod_name, container_name=container_name, labels=labels, image=image, gpu_use=gpu_count,
                resource_limits=kube_resource_limits, env=env_object.get_env_list(),
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                annotations=annotations, namespace=namespace,
                postStart_command=postStart_command, node_name=node_name, privileged=False, gpu_image_run_as_cpu=True)
    return create_pod(body=body, pod_name=unique_pod_name,training_tool_id=training_tool_id,
                    labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model, namespace=namespace)


def create_ssh_pod(pod_info, node_info):
    def rollback_service(pod_name):
        service_flag_list = [ USERPORT_NODEPORT_FLAG, USERPORT_CLUSTER_IP_PORT_FLAG, SYSTEM_NODEPORT_FLAG, SYSTEM_CLUSTER_IP_PORT_FLAG ]
        for flag in service_flag_list:
            service_name = get_item_name(pod_name, flag)
            try:
                delete_service(service_name=service_name)
            except :
                pass

    # jupyter_pod_info = {
    #     "workspace_name": workspace_name,
    #     "workspace_id": workspace_id,
    #     "training_name": training_name,
    #     "training_id": training_id,
    #     "training_tool_id": training_tool_id,
    #     "owner": owner_name,
    #     "executor_id": db.get_user(user_name=headers_user)["id"],
    #     "executor_name": headers_user,
    #     "training_type": training_type,
    #     "gpu_count": req_gpu_count,
    #     "editor": editor,
    #     "image": image,
    #     "users": users,
    #     "ports": None
    # }
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    training_tool_id = pod_info["training_tool_id"]
    training_tool_type = pod_info["training_tool_type"]
    training_tool_replica_number = pod_info["training_tool_replica_number"]
    owner_name = pod_info["owner"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    training_type = pod_info["training_type"]
    gpu_count = pod_info["gpu_count"]
    image = pod_info["image"]
    image_name = pod_info["image_name"]
    image_id = pod_info["image_id"]
    users = pod_info["users"]
    ports = pod_info["ports"]


    ## node_info_manager
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()

    # ## resource info
    # node_info = node_groups[0]
    # node_name = node_info["node"]
    # gpu_resource_key = node_info["gpu_resource_key"]
    # resource_limits = node_info["resource_limits"]
    # gpu_model = node_info.get("gpu_model")
    # cpu_model = node_info.get(NODE_CPU_MODEL_KEY)

    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)


    env_object = ENV(owner_name=owner_name, item_id=training_tool_id)

    base_pod_name, unique_pod_name, container_name = PodName(
        workspace_name=workspace_name, item_name=training_name, item_type=training_tool_type, sub_flag=training_tool_replica_number).get_all()

    # Training_name-[Tool(jupyter|editor)]-replica_num
    # ssh_user_setting(workspace_name=workspace_name, training_name=training_name, owner=owner, users=users)
    ssh_banner_string = "[{}] Workspace [{}] Training [{}] SSH".format(workspace_name, training_name, training_tool_type)

    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_ssh_pod_default_labels(pod_info=pod_info, pod_name=unique_pod_name, image_id=image_id)

    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    # SYSTEM - NodePort | ClusterIP
    # USER - NodePort 로 구성
    try :
        delete_service_training_tool(training_tool_id=training_tool_id)
        service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_user_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
    except CustomErrorList as ce:
        rollback_service(unique_pod_name)
        raise ce
    except Exception as e:
        raise e

    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_ssh_pod_default_volumes_and_volume_mounts(workspace_name=workspace_name, training_name=training_name, owner_name=owner_name, pod_name=unique_pod_name)

    command_object = Command()
    command = command_object.get_ssh_pod_command(ssh_banner_string=ssh_banner_string)
    postStart_command = command_object.get_postStart_command()
    preStop_command = command_object.get_preStop_command()

    body = get_pod_body(pod_name=unique_pod_name, container_name=container_name, labels=labels, image=image, gpu_use=gpu_count,
                resource_limits=kube_resource_limits, env=env_object.get_env_list(),
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                annotations=annotations,
                postStart_command=postStart_command, preStop_command=preStop_command,
                node_name=node_name, privileged=False, gpu_image_run_as_cpu=True)

    return create_pod(body=body, pod_name=unique_pod_name, training_tool_id=training_tool_id,
                    labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)

def create_rstudio_pod(pod_info, node_info):
    def rollback_service(pod_name):
        service_flag_list = [ USERPORT_NODEPORT_FLAG, USERPORT_CLUSTER_IP_PORT_FLAG, SYSTEM_NODEPORT_FLAG, SYSTEM_CLUSTER_IP_PORT_FLAG ]
        for flag in service_flag_list:
            service_name = get_item_name(pod_name, flag)
            try:
                delete_service(service_name=service_name)
            except :
                pass
    # 최소 요구 정보 경우에 따라 추가 가능함
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    training_type = pod_info["training_type"]
    training_tool_id = pod_info["training_tool_id"]
    training_tool_type = pod_info["training_tool_type"]
    training_tool_replica_number = pod_info["training_tool_replica_number"]
    owner_name = pod_info["owner"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    ports = pod_info["ports"]

    image = pod_info["image"]
    image_name = pod_info["image_name"]
    image_id = pod_info["image_id"]
    gpu_count = pod_info["gpu_count"]

    ## node_info_manager
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()

    # ## resource info
    # node_info = node_groups[0]
    # node_name = node_info["node"]
    # gpu_resource_key = node_info["gpu_resource_key"]
    # resource_limits = node_info["resource_limits"]
    # gpu_model = node_info.get("gpu_model")
    # cpu_model = node_info.get("cpu_model")


    # RESOURCE SETTING
    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)

    # ENV SETTING
    env_object = ENV(owner_name=owner_name, item_id=training_tool_id)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    # POD NAME SETTING
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name,
                                                                item_type=training_tool_type, sub_flag=training_tool_replica_number).get_all()

    # LABEL SETTING
    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_tool_default_labels(training_name=training_name, training_id=training_id,
                                        training_tool_id=training_tool_id, training_tool_type=training_tool_type, gpu_count=gpu_count,
                                        owner_name=owner_name, training_type=training_type, pod_name=unique_pod_name, image_id=image_id)

    # VOLUME SETTING
    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_rstudio_pod_default_volumes_and_volume_mounts(training_name=training_name, workspace_name=workspace_name)

    # COMMAND SETTING
    command_object = Command()
    # command = command_object.get_default_command()
    command = command_object.get_rstudio_command()
    postStart_command = command_object.get_postStart_command()
    preStop_command = command_object.get_preStop_command()

    # PORT SETTING
    try :
        delete_service_training_tool(training_tool_id=training_tool_id)
        service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_user_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
    except CustomErrorList as ce:
        rollback_service(unique_pod_name)
        raise ce
    except Exception as e:
        raise e

    # for port in ports:
    #     if port["system_definition"] == 1 and port["name"] == DEFAULT_RSTUDIO_PORT_NAME:
    #         rstudio_ingress_create(pod_name=unique_pod_name, labels=labels, service_port_number=port["target_port"])


    body = get_pod_body(pod_name=unique_pod_name, container_name=container_name, labels=labels, image=image, gpu_use=gpu_count,
                resource_limits=kube_resource_limits, env=env_object.get_env_list(),
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                annotations=annotations,
                postStart_command=postStart_command, preStop_command=preStop_command,
                node_name=node_name, privileged=False, gpu_image_run_as_cpu=True)

    return create_pod(body=body, pod_name=unique_pod_name, training_tool_id=training_tool_id,
                    labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)


    pass

def create_file_browser_pod(pod_info, node_info, ingress_use: bool = False):
    def rollback_service(pod_name):
        service_flag_list = [ USERPORT_NODEPORT_FLAG, USERPORT_CLUSTER_IP_PORT_FLAG, SYSTEM_NODEPORT_FLAG, SYSTEM_CLUSTER_IP_PORT_FLAG ]
        for flag in service_flag_list:
            service_name = get_item_name(pod_name, flag)
            try:
                delete_service(service_name=service_name)
            except :
                pass
    # 최소 요구 정보 경우에 따라 추가 가능함
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    training_name = pod_info["training_name"]
    training_id = pod_info["training_id"]
    training_type = pod_info["training_type"]
    training_tool_id = pod_info["training_tool_id"]
    training_tool_type = pod_info["training_tool_type"]
    training_tool_replica_number = pod_info["training_tool_replica_number"]
    owner_name = pod_info["owner"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    ports = pod_info["ports"]

    image = FILEBROWSER_IMAGE #pod_info["image"] #jf_training_tool_filebrowser:latest
    image_name = pod_info["image_name"] #jf_training_tool_filebrowser
    image_id = pod_info["image_id"]
    gpu_count = pod_info["gpu_count"]


    ## node_info_manager
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()

    ## resource info
    # node_info = node_groups[0]
    # node_name = node_info["node"]
    # gpu_resource_key = node_info["gpu_resource_key"]
    # resource_limits = node_info["resource_limits"]
    # gpu_model = node_info.get("gpu_model")
    # cpu_model = node_info.get("cpu_model")


    # RESOURCE SETTING
    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)

    # ENV SETTING
    env_object = ENV(owner_name=owner_name, item_id=training_tool_id)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)

    # POD NAME SETTING
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=training_name,
                                                                item_type=training_tool_type, sub_flag=training_tool_replica_number).get_all()

    # LABEL SETTING
    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    labels = labels_object.get_tool_default_labels(training_name=training_name, training_id=training_id,
                                        training_tool_id=training_tool_id, training_tool_type=training_tool_type, gpu_count=gpu_count,
                                        owner_name=owner_name, training_type=training_type, pod_name=unique_pod_name, image_id=image_id)

    # VOLUME SETTING
    volume_object = Volume(pod_name=unique_pod_name)
    volumes, volume_mounts = volume_object.get_rstudio_pod_default_volumes_and_volume_mounts(training_name=training_name, workspace_name=workspace_name)

    # # COMMAND SETTING
    # command_object = Command()
    # command = command_object.get_file_browser_command(pod_name=unique_pod_name)
    # postStart_command = command_object.get_postStart_command()
    # preStop_command = command_object.get_preStop_command()

    # PORT SETTING
    try :
        delete_service_training_tool(training_tool_id=training_tool_id)
        service_create_user_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_user_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_node_port_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
        service_create_system_cluster_ip_list(pod_name=unique_pod_name, port_list=ports, labels=labels)
    except CustomErrorList as ce:
        rollback_service(unique_pod_name)
        raise ce
    except Exception as e:
        raise e

    base_url = "/"
    ingress_use = FILEBROWSER_INGRESS_USE
    # IF INGRESS USE
    # INGRESS SETTING
    if ingress_use:
        service_port_number = None
        for port in ports:
            if port["system_definition"] == 1 and port["name"] == DEFAULT_FILEBROWSER_PORT_NAME:
                service_port_number = port["target_port"]
        service_name = get_item_name(pod_name=unique_pod_name, FLAG="--system-0")
        base_url = get_base_url(pod_name=unique_pod_name, FLAG=FILEBROWSER_FLAG)
        create_ingress(ingress_name=service_name, ingress_path=base_url, rewrite_target_path=base_url,
                        service_name=service_name, service_port_number=service_port_number, labels=labels)
    # COMMAND SETTING
    admin_pw = common.gen_hash("{}{}".format(workspace_id, training_tool_id))
    command_object = Command()
    command = command_object.get_file_browser_command(base_url=base_url, admin_pw=admin_pw)
    postStart_command = command_object.get_postStart_command()
    preStop_command = command_object.get_preStop_command()

    body = get_pod_body(pod_name=unique_pod_name, container_name=container_name, labels=labels, image=image, gpu_use=gpu_count,
                resource_limits=kube_resource_limits, env=env_object.get_env_list(),
                volume_mounts=volume_mounts, volumes=volumes, command=command,
                annotations=annotations,
                postStart_command=postStart_command, preStop_command=preStop_command,
                node_name=node_name, privileged=False, gpu_image_run_as_cpu=True)

    return create_pod(body=body, pod_name=unique_pod_name, training_tool_id=training_tool_id,
                    labels=labels, gpu_count=gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)


    pass

def update_jupyter_pod_service(labels, port_list):
    pod_name = labels["pod_name"]
    service_create_user_node_port_list(pod_name=pod_name, port_list=port_list, labels=labels)
    service_create_user_cluster_ip_list(pod_name=pod_name, port_list=port_list, labels=labels)
    service_create_system_node_port_list(pod_name=pod_name, port_list=port_list, labels=labels)
    service_create_system_cluster_ip_list(pod_name=pod_name, port_list=port_list, labels=labels)

# DEPLOYMENT -

    # try:
    #     coreV1Api.create_namespaced_pod(body=body, namespace="default")
    #     print("@!#!@#",body)
    #     db.update_deployment_start_time_init(deployment_id=deployment_id)
    #     return True, ""

    # except Exception as e:
    #     traceback.print_exc()
    #     coreV1Api.delete_namespaced_service(name=pod_name, namespace='default')
    #     return False, str(e)

# 템플릿 적용
def create_deployment_pod(pod_info, node_groups, gpu_uuid_list=None, parent_deployment_worker_id=None):
    """
    Description : Deployment Worker 실행을 위한 함수

    Args :
    pod_info (dict) :
    node_groups (list) : []

    # GPU Share 시 사용하는 변수들
    gpu_uuid_list (list) : [gpu0-uuid, gpu1-uuid ..] 강제로 할당 할 GPU의 UUID
    parent_deployment_worker_id (int) : GPU Share 의 기반으로 사용된 deployment worker id 정보 (부모가 종료되면 나머지 Worker들도 같이 종료)

    Returns :
    TODO

    """
    # gpu_uuid_list - gpu_share 시 사용하는 변수
    #TODO 하나의 POD에 멀티 API CASE를 고려해야할까?
    #8555가 아닌 다른 포트를 반드시 쓰겠다고 하는 경우가 있을까 => 없엉

    deployment_name = pod_info["deployment_name"]
    deployment_id = pod_info["deployment_id"]
    deployment_type = pod_info["deployment_type"]
    # gpu = pod_info["gpu"]
    # operating_type = pod_info["operating_type"]
    workspace_name = pod_info["workspace_name"]
    workspace_id = pod_info["workspace_id"]
    total_gpu_count = pod_info["gpu_count"]

    # training_name = pod_info["training_name"]
    training_name = pod_info.get("training_name")
    api_path = pod_info["api_path"]
    executor_id = pod_info["executor_id"]
    executor_name = pod_info["executor_name"]
    running_type = pod_info[DEPLOYMENT_TEMPLATE_TYPE_KEY]

    deployment_worker_id = pod_info.get("deployment_worker_id") # if pod_info.get("deployment_worker_id") is not None else ""
    if parent_deployment_worker_id is None:
        parent_deployment_worker_id = deployment_worker_id

    owner_name = pod_info["owner_name"]
    image = pod_info["image_real_name"]

    # built in model + checkpoint + pretrained additional info
    built_in_model_path = pod_info.get("built_in_model_path")
    # built_in_model_path = pod_info["built_in_model_path"]

    # checkpoint additional info
    checkpoint_id = pod_info.get("checkpoint_id")
    checkpoint_dir_path = pod_info.get("checkpoint_dir_path")
    # checkpoint_id = pod_info["checkpoint_id"]
    # checkpoint_dir_path = pod_info["checkpoint_dir_path"]
    # checkpoint_workspace_name = pod_info["checkpoint_workspace_name"]
    # is_default = True

    ## resource info
    node_info = node_groups[0]
    node_name = node_info["node"]
    gpu_resource_key = node_info["gpu_resource_key"]
    resource_limits = node_info["resource_limits"]
    gpu_model = node_info.get("gpu_model")
    cpu_model = node_info.get("cpu_model")

    ## GPU Share
    gpu_share_mode = True if gpu_uuid_list is not None else False

    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type=DEPLOYMENT_ITEM_A, sub_flag=deployment_worker_id).get_all()
    if api_path is None:
        api_path = base_pod_name

    # # 모델 내장 ckpt, 사용자 학습 model
    # if pod_info[DEPLOYMENT_TEMPLATE_CHECKPOINT_KEY] is not None and pod_info[DEPLOYMENT_TEMPLATE_CHECKPOINT_KEY]!="":
    #     is_default = False


    API_MODE = pod_info[DEPLOYMENT_API_MODE_LABEL_KEY]
    # deployment_py_command = pod_info["deployment_py_command"]
    deployment_py_command = pod_info.get("deployment_py_command")

    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)
    # labels = labels_object.get_deployment_default_labels(total_gpu_count=total_gpu_count, deployment_name=deployment_name, deployment_id=deployment_id,
    #                                                     deployment_worker_id=deployment_worker_id, owner_name=owner_name, deployment_type=deployment_type,
    #                                                     api_mode=API_MODE, pod_name=unique_pod_name, pod_base_name=base_pod_name)
    labels = labels_object.get_deployment_default_labels(total_gpu_count=total_gpu_count, deployment_name=deployment_name, deployment_id=deployment_id,
                                                        deployment_worker_id=deployment_worker_id, parent_deployment_worker_id=parent_deployment_worker_id,
                                                        owner_name=owner_name, deployment_type=deployment_type,
                                                        api_mode=API_MODE, pod_name=unique_pod_name, pod_base_name=base_pod_name)

    kube_resource_limits = get_kube_resource_limits(gpu_use=total_gpu_count, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits)

    env_object = ENV(owner_name=owner_name, item_id=deployment_worker_id)
    env_object.add_default_env_deployment_worker(deployment_running_type=running_type)
    env_object.add_resource_info_env(gpu_use=total_gpu_count, gpu_resource_key=gpu_resource_key, resource_limits=resource_limits, gpu_uuid_list=gpu_uuid_list)
    #TODO item_name_deployment -> 따로 함수에서 관리할 수 있도록
    item_name_deployment = get_item_name(base_pod_name, DEPLOYMENT_FLAG)
    if API_MODE == DEPLOYMENT_PREFIX_MODE:
        base_url_deployment = get_base_url(api_path, FLAG=DEPLOYMENT_FLAG, rewrite_annotaion=False)
        base_url_deployment_rewrite_annotation = get_base_url(api_path, FLAG=DEPLOYMENT_FLAG, rewrite_annotaion=True)
        create_flag_service(pod_name=unique_pod_name, service_name=item_name_deployment, service_port_type=DEPLOYMENT_API_PORT_NAME,
                            service_port_number=DEPLOYMENT_NGINX_DEFAULT_PORT, labels=labels, selector={"deployment_id": str(deployment_id)}, no_delete=True)
        create_ingress(ingress_name=item_name_deployment, ingress_path=base_url_deployment_rewrite_annotation, rewrite_target_path=INGRESS_REWRITE_DEFAULT,
                    service_name=item_name_deployment, service_port_number=DEPLOYMENT_NGINX_DEFAULT_PORT, labels=labels, no_delete=True)
    elif API_MODE == DEPLOYMENT_PORT_MODE:
        # PORT모드 일때는 무중단을 보장 할 수 없음.
        # selector에 묶인 POD들도 완전히 분산하여 받진 않음
        # "LoadBalancer" (외부 밸런서를 지정하지 않는 것) = "NodePort"  같은 성능을 보임
        base_url_deployment = "/"
        create_flag_service(pod_name=unique_pod_name, service_name=item_name_deployment, service_port_type=DEPLOYMENT_API_PORT_NAME,
                            service_port_number=DEPLOYMENT_API_DEFAULT_PORT, labels=labels, service_type="NodePort", selector={"deployment_id": str(deployment_id)}, no_delete=True)


    # if running_type == DEPLOYMENT_RUN_CUSTOM:
    #     pass
    # else :
    #     deployment_py_command = JF_BUILT_IN_MODELS_MODEL_POD_PATH + "/" + deployment_py_command

    if deployment_py_command.split(' ')[0][-3:]=='.py':
        # run_code = "python {deployment_py_command} --prefix {prefix} ".format(deployment_py_command=deployment_py_command, prefix=base_url_deployment)
        run_code = "python {deployment_py_command} ".format(deployment_py_command=deployment_py_command)
    else:
        # run_code = "{deployment_py_command} --prefix {prefix} ".format(deployment_py_command=deployment_py_command, prefix=base_url_deployment)
        run_code = "{deployment_py_command} ".format(deployment_py_command=deployment_py_command)

    if pod_info["deployment_num_of_gpu_parser"] is not None and pod_info["deployment_num_of_gpu_parser"] != "":
        run_code += " --{key} {value} ".format(key=pod_info["deployment_num_of_gpu_parser"], value=total_gpu_count)


    job_name=None
    job_group_index=None

    if running_type in [DEPLOYMENT_RUN_CUSTOM, DEPLOYMENT_RUN_USERTRAINED, DEPLOYMENT_RUN_CHEKCPOINT]:
    # if is_default==False:
        # User user ckpt
        # training_name = pod_info["training_name"]
        checkpoint_base_path=pod_info.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_DIR_KEY)
        checkpoint_file_path=pod_info.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY)
        # checkpoint_base_path = None
        # if checkpoint_id:
        #     file_name = pod_info["checkpoint"].split('/')[-1]
        #     # print("file_name {}".format(file_name))
        #     # TODO CHECK필요 - Checkpoint 업로드 시 해당 checkpoint 데이터 마운트 및 사용할 수 있도록 구조 변경 필요(2022-0713)
        # else:
        #     job_name = pod_info["checkpoint"].split('/')[0]
        #     job_group_index = pod_info["checkpoint"].split('/')[1]
        #     file_name = "/".join(pod_info["checkpoint"].split('/')[2:])

        #     checkpoint_base_path = JF_TRAINING_JOB_CHECKPOINT_ITEM_POD_PATH.format(job_name=job_name, job_group_index=job_group_index)

        if pod_info.get("checkpoint_load_dir_path_parser") is not None and pod_info.get("checkpoint_load_dir_path_parser") != "":
            run_code += "--{key} {value}/ ".format(key=pod_info.get("checkpoint_load_dir_path_parser"), value=checkpoint_base_path )

        if pod_info.get("checkpoint_load_file_path_parser") is not None and pod_info.get("checkpoint_load_file_path_parser") != "":
            run_code += "--{key} {value} ".format(key=pod_info.get("checkpoint_load_file_path_parser"), value=checkpoint_file_path )


    volumes, volume_mounts = Volume(pod_name=unique_pod_name).get_deployment_default_volumes_and_volume_mounts(
        workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id,
        running_type=running_type, training_name=training_name,
        built_in_model_path=built_in_model_path, checkpoint_dir_path=checkpoint_dir_path,
        pod_name=unique_pod_name)

    run_code = common.convert_run_code_to_run_command(run_code=run_code)

    command =  Command().get_deployment_command(deployment_api_port=DEPLOYMENT_API_DEFAULT_PORT, run_code=run_code, deployment_worker_id=deployment_worker_id)


    postStart_command = None


    body = get_pod_body(pod_name=unique_pod_name, labels=labels, image=image, gpu_use=total_gpu_count,
            resource_limits=kube_resource_limits, env=env_object.get_env_list(),
            volume_mounts=volume_mounts, volumes=volumes, command=command,
            restartPolicy="Always",
            postStart_command=postStart_command, node_name=node_name, privileged=False, gpu_image_run_as_cpu=True, gpu_share_mode=gpu_share_mode)

    return create_pod(body=body, pod_name=unique_pod_name, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id, executor_id=executor_id,
                labels=labels, gpu_count=total_gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)


# 최소 기능 묶음 형태 (배포 생성 부분 전부 이 방법으로 대체 2022-11-30)
def create_deployment_pod_new_method(workspace_id, workspace_name, deployment_id, deployment_name, deployment_worker_id,
                                    executor_id, executor_name, owner_name, deployment_type, deployment_template_type, training_name,
                                    node_info, total_gpu_count,
                                    deployment_api_mode, run_code, docker_image_real_name, mounts, environments, workdir,
                                    built_in_model_path=None, checkpoint_dir_path=None,
                                    api_path=None, gpu_uuid_list=None, parent_deployment_worker_id=None):
    """
        Args:
            deployment_api_mode (str) : prefix (ingress) or port
            run_code (str) : binary + file + options
    """
    ## resource info
    node_name = node_info.get_node_name()
    gpu_model = node_info.get_gpu_model()
    kube_resource_limits = node_info.get_resource_limits()
    cpu_model = node_info.get_cpu_model()

    # Multus CNI Setting
    annotations = get_network_attachment_definitions_annotations_for_pod_annotations(node_name=node_name, kube_resource_limits=kube_resource_limits)

    ## GPU Share
    gpu_share_mode = True if gpu_uuid_list is not None else False

    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type=DEPLOYMENT_ITEM_A, sub_flag=deployment_worker_id).get_all()
    if api_path is None:
        api_path = base_pod_name


    API_MODE = deployment_api_mode

    labels_object = Label(workspace_name=workspace_name, workspace_id=workspace_id, executor_id=executor_id, executor_name=executor_name)

    labels = labels_object.get_deployment_default_labels(total_gpu_count=total_gpu_count, deployment_name=deployment_name, deployment_id=deployment_id,
                                                        deployment_worker_id=deployment_worker_id, parent_deployment_worker_id=parent_deployment_worker_id,
                                                        owner_name=owner_name, deployment_type=deployment_type,
                                                        api_mode=API_MODE, pod_name=unique_pod_name, pod_base_name=base_pod_name)

    env_object = ENV(owner_name=owner_name, item_id=deployment_worker_id)
    # get training mount destination
    env_object.add_default_env_deployment_worker(deployment_running_type=deployment_template_type, workdir=workdir)
    env_object.add_resource_info_env_new(kube_resource_limits=kube_resource_limits)
    if environments !=None:
        env_object.add_env_list(environments=environments)

    item_name_deployment = get_item_name(base_pod_name, DEPLOYMENT_FLAG)
    if API_MODE == DEPLOYMENT_PREFIX_MODE:
        base_url_deployment = get_base_url(api_path, FLAG=DEPLOYMENT_FLAG, rewrite_annotaion=False)
        base_url_deployment_rewrite_annotation = get_base_url(api_path, FLAG=DEPLOYMENT_FLAG, rewrite_annotaion=True)
        create_flag_service(pod_name=unique_pod_name, service_name=item_name_deployment, service_port_type=DEPLOYMENT_API_PORT_NAME,
                            service_port_number=DEPLOYMENT_NGINX_DEFAULT_PORT, labels=labels, selector={"deployment_id": str(deployment_id)}, no_delete=True)
        create_ingress(ingress_name=item_name_deployment, ingress_path=base_url_deployment_rewrite_annotation, rewrite_target_path=INGRESS_REWRITE_DEFAULT,
                    service_name=item_name_deployment, service_port_number=DEPLOYMENT_NGINX_DEFAULT_PORT, labels=labels, no_delete=True)
    elif API_MODE == DEPLOYMENT_PORT_MODE:
        # PORT모드 일때는 무중단을 보장 할 수 없음.
        # selector에 묶인 POD들도 완전히 분산하여 받진 않음
        # "LoadBalancer" (외부 밸런서를 지정하지 않는 것) = "NodePort"  같은 성능을 보임
        base_url_deployment = "/"
        create_flag_service(pod_name=unique_pod_name, service_name=item_name_deployment, service_port_type=DEPLOYMENT_API_PORT_NAME,
                            service_port_number=DEPLOYMENT_API_DEFAULT_PORT, labels=labels, service_type="NodePort", selector={"deployment_id": str(deployment_id)}, no_delete=True)

    volumes, volume_mounts = Volume(pod_name=unique_pod_name).get_deployment_default_volumes_and_volume_mounts(
        workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id,
        deployment_template_type=deployment_template_type, training_name=training_name,
        built_in_model_path=built_in_model_path, checkpoint_dir_path=checkpoint_dir_path,
        pod_name=unique_pod_name, mounts=mounts)

    if run_code != None:
        command =  Command().get_deployment_command(deployment_api_port=DEPLOYMENT_API_DEFAULT_PORT, run_code=run_code, deployment_worker_id=deployment_worker_id)
    else:
        command = None
    postStart_command = None


    body = get_pod_body(pod_name=unique_pod_name, labels=labels, image=docker_image_real_name, gpu_use=total_gpu_count,
            resource_limits=kube_resource_limits, env=env_object.get_env_list(),
            volume_mounts=volume_mounts, volumes=volumes, command=command, annotations=annotations,
            restartPolicy="Always",
            postStart_command=postStart_command, node_name=node_name, privileged=False, gpu_image_run_as_cpu=True, gpu_share_mode=gpu_share_mode)

    return create_pod(body=body, pod_name=unique_pod_name, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id, executor_id=executor_id,
                labels=labels, gpu_count=total_gpu_count, gpu_model=gpu_model, cpu_model=cpu_model)


def update_deployment_pod_ingress(api_path, labels):
    pod_base_name = labels.get("pod_base_name")
    if api_path is None:
        api_path = pod_base_name

    base_url_deployment_rewrite_annotation = get_base_url(api_path, FLAG=DEPLOYMENT_FLAG, rewrite_annotaion=True)
    item_name_deployment = get_item_name(pod_base_name, DEPLOYMENT_FLAG)
    create_ingress(ingress_name=item_name_deployment, ingress_path=base_url_deployment_rewrite_annotation, rewrite_target_path=INGRESS_REWRITE_DEFAULT,
                    service_name=item_name_deployment, service_port_number=DEPLOYMENT_NGINX_DEFAULT_PORT, labels=labels, no_delete=False)