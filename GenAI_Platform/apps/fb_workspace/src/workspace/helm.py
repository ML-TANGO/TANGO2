import subprocess
import os
import traceback
from utils import settings


# Helm 명령을 실행할 함수 정의

def create_workspace_namespace_volume(workspace_id : int , workspace_name: str,  cpu_cores: int, memory: int, gpu_count: int, main_sc: str, data_sc:str, main_storage_request: int = None, data_storage_request: int = None):
    try:
        if main_storage_request is None:
            main_storage_request = "100Gi"

        if data_storage_request is None:
            data_storage_request = "100Gi"


        os.chdir("/app/helm_chart/")
        # helm install storage.tgz
        # helm 의 namespace는 JF_SYSTEM_NAMESPACE(헬름관리), helm 실행하여 생성되는 리소스의 namespace는 template에서 관리
        command=f"helm install workspace-{settings.JF_SYSTEM_NAMESPACE}-{workspace_id} \
            -n {settings.JF_SYSTEM_NAMESPACE} --create-namespace \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set system.registry={settings.DOCKER_REGISTRY_URL} \
            --set system.imagePullSecrets.enabled={settings.JONATHAN_IMAGE_PULL_SECRETS_EABLED} \
            --set workspace.id={workspace_id} \
            --set workspace.name={workspace_name} \
            --set workspace.namespace={workspace_name} \
            --set workspace.main_storage.storageClassName={main_sc} \
            --set workspace.main_storage.requests.storage={main_storage_request} \
            --set workspace.data_storage.storageClassName={data_sc} \
            --set workspace.data_storage.requests.storage={data_storage_request} \
            --set quota.memory={memory} \
            --set quota.cpu={cpu_cores} \
            --set quota.gpu={gpu_count} \
            --set volume.jfData.type={settings.JF_VOLUME_DATA_TYPE} \
            --set volume.jfData.path={settings.JF_VOLUME_DATA_PATH } \
            --set volume.jfData.server={settings.JF_VOLUME_DATA_SERVER} \
            --set volume.jfBin.type={settings.JF_VOLUME_BIN_TYPE} \
            --set volume.jfBin.path={settings.JF_VOLUME_BIN_PATH} \
            --set volume.jfBin.server={settings.JF_VOLUME_BIN_SERVER} \
            ./workspace"
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
        command=f"helm uninstall workspace-{settings.JF_SYSTEM_NAMESPACE}-{workspace_id} -n {settings.JF_SYSTEM_NAMESPACE}"

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
