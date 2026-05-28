import subprocess
import os
import traceback
from utils import settings, TYPE
from utils.redis import get_redis_client
from utils.redis_key import JOB_LIST

WORKSPACE_HELM_NAME = "workspace-{}-{}"
WORKSPACE_STORAGE_HELM_NAME = "workspace-{}-{}-storage"
WORKSPACE_DELETE_DATA_HELM_NAME = "workspace-{}-delete-data"
WORKSPACE_MAIN_DATA_STORAGE_NAME = "{}-main-pvc"
WORKSPACE_DATA_DATA_STORAGE_NAME = "{}-data-pvc"
WORKSPACE_NAMESPACE = "{}-{}"
# Helm 명령을 실행할 함수 정의

def create_workspace_namespace_volume(workspace_id : int , workspace_name: str,  cpu_cores: int, memory: int, gpu_count: int, main_sc: str, data_sc:str, main_storage_request: int = None, data_storage_request: int = None, sc_type: str = None):
    try:
        if main_storage_request is None:
            main_storage_request = "100Gi"

        if data_storage_request is None:
            data_storage_request = "100Gi"

        if sc_type is None:
            sc_type = TYPE.STORAGE_TYPE_LOCAL
        
        if sc_type not in TYPE.STORAGE_TYPES:
            raise Exception(f"Invalid storage type: {sc_type}")
        
        access_mode = TYPE.STORAGE_ACCESS_MODE_READ_WRITE
        if sc_type == TYPE.STORAGE_TYPE_LOCAL:
            access_mode = TYPE.STORAGE_ACCESS_MODE_READ_WRITE
        elif sc_type == TYPE.STORAGE_TYPE_NFS:
            access_mode = TYPE.STORAGE_ACCESS_MODE_READ_WRITE_MANY
            
        os.chdir("/app/helm_chart/")
        helm_name = WORKSPACE_HELM_NAME.format(settings.JF_SYSTEM_NAMESPACE, workspace_id)
        # helm install storage.tgz
        # helm 의 namespace는 JF_SYSTEM_NAMESPACE(헬름관리), helm 실행하여 생성되는 리소스의 namespace는 template에서 관리
        command=f"helm install {helm_name} \
            -n {settings.JF_SYSTEM_NAMESPACE} --create-namespace \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set system.registry={settings.SYSTEM_DOCKER_REGISTRY_URL} \
            --set system.imagePullSecrets.enabled={settings.JONATHAN_IMAGE_PULL_SECRETS_EABLED} \
            --set system.privateRepo.enabled={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set system.privatePip.enabled={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set system.storage.accessMode={access_mode} \
            --set workspace.id={workspace_id} \
            --set workspace.name={workspace_name} \
            --set workspace.namespace={workspace_name} \
            --set quota.memory={memory} \
            --set quota.cpu={cpu_cores} \
            --set quota.gpu={gpu_count} \
            --set volume.jfBin.type={settings.JF_VOLUME_BIN_TYPE} \
            --set volume.jfBin.path={settings.JF_VOLUME_BIN_PATH} \
            --set volume.jfBin.server={settings.JF_VOLUME_BIN_SERVER} \
            ./workspace"
            #             --set volume.jfData.type={settings.JF_VOLUME_DATA_TYPE} \
            # --set volume.jfData.path={settings.JF_VOLUME_DATA_PATH } \
            # --set volume.jfData.server={settings.JF_VOLUME_DATA_SERVER} \
            #         --set workspace.main_storage.storageClassName={main_sc} \
            # --set workspace.main_storage.requests.storage={main_storage_request} \
            # --set workspace.data_storage.storageClassName={data_sc} \
            # --set workspace.data_storage.requests.storage={data_storage_request} \
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(result.stdout)


        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        if "cannot re-use a name that is still in use" in err_msg:
            return True, ""
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg

def delete_workspace_namespace_volume(workspace_id : int):
    try:
        os.chdir("/app/helm_chart/")
        helm_name = WORKSPACE_HELM_NAME.format(settings.JF_SYSTEM_NAMESPACE, workspace_id)
        command=f"helm uninstall {helm_name} -n {settings.JF_SYSTEM_NAMESPACE}"
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg
    
def create_workspace_pvc(workspace_id, workspace_name, main_sc, main_storage_request, data_sc, data_storage_request):
    try:
        os.chdir("/app/helm_chart/")
        helm_name = WORKSPACE_STORAGE_HELM_NAME.format(settings.JF_SYSTEM_NAMESPACE, workspace_id)
        command=f"helm install {helm_name} ./storage \
            -n {settings.JF_SYSTEM_NAMESPACE} \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set workspace.id={workspace_id} \
            --set workspace.name={workspace_name} \
            --set workspace.namespace={workspace_name} \
            --set workspace.main_storage.storageClassName={main_sc} \
            --set workspace.main_storage.requests.storage={main_storage_request} \
            --set workspace.data_storage.storageClassName={data_sc} \
            --set workspace.data_storage.requests.storage={data_storage_request} "
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg
    
def delete_workspace_pvc(workspace_id):
    try:
        os.chdir("/app/helm_chart/")
        helm_name = WORKSPACE_STORAGE_HELM_NAME.format(settings.JF_SYSTEM_NAMESPACE, workspace_id)
        command=f"helm uninstall {helm_name} \
              -n {settings.JF_SYSTEM_NAMESPACE}"
        
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg
    
def update_workspace_storage(workspace_id, workspace_name, main_storage, main_sc, main_storage_request, data_storage, data_sc, data_storage_request):
    try:
        os.chdir("/app/helm_chart/")
        env={
            "WORKSPACE_ID": workspace_id,
            "WORKSPACE_NAME" : workspace_name,
            "WORKSPACE_NAMESPACE" : workspace_name,
            "MAIN_SC": main_sc,
            "MAIN_STORAGE_REQUEST" : main_storage_request,
            "DATA_SC" : data_sc,
            "DATA_STORAGE_REQUEST" : data_storage_request
        }
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"

        pod_name = f"workspace-{workspace_id}-update"
        image=f"{settings.SYSTEM_DOCKER_REGISTRY_URL}jfb-system/workspace_app:dev"

        command=f"helm install {pod_name} ./workspace_storage_update \
            -n {settings.JF_SYSTEM_NAMESPACE} \
            --set workspace_id={workspace_id} \
            --set name={pod_name} \
            --set image={image} \
            --set main_storage={main_storage} \
            --set data_storage={data_storage} \
            --set registry={settings.DOCKER_REGISTRY_URL} \
            {env_command}"
        
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        redis_client = get_redis_client()
        redis_client.hset(JOB_LIST,pod_name,settings.JF_SYSTEM_NAMESPACE)
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg
    

def delete_workspace_data_storage(workspace_id, workspace_name, main_sc, data_sc):
    try:
        os.chdir("/app/helm_chart/")
        helm_name = WORKSPACE_DELETE_DATA_HELM_NAME.format(workspace_id)
        job_name = f"job-workspace-delete-data-{workspace_id}"
        command=f"helm install {helm_name} ./delete_workspace_data \
              -n {settings.JF_SYSTEM_NAMESPACE} \
              --set workspace_id={workspace_id} \
              --set workspace_name={workspace_name} \
              --set job_name={job_name} \
              --set registry={settings.SYSTEM_DOCKER_REGISTRY_URL} \
              --set main_storage={main_sc} \
              --set data_storage={data_sc}"
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg