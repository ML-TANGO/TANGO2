import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils import settings, TYPE
import traceback
NFS_PROVISIONER_HELM_CHART_NAME= "nfs-subdir-external-provisioner"
LOCAL_PATH_PROVISIONER_HELM_CHART_NAME= "local-path-provisioner"
STORAGE_HELM_CHART_NAME = "storage_check"
PVC_CHART_NAME = "volume"
STORAGE_EXPORTER = "storage-exporter"

def create_storage_pvc(ip, name, mountpoint, type):
    try:

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        command=f"""helm install {name} /app/src/storage/helm_chart/{PVC_CHART_NAME} \
            -n {namespace} \
            --set server={ip} \
            --set path={mountpoint} \
            --set name={name} \
            --set type={type} \
            --set namespace="{namespace}" \
            """
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip()
            # 멱등 처리 — 형제 함수(create_storage_exporter / create_storage_local_provisioner)와 같은 규약.
            #   릴리스가 이미 있으면 성공으로 본다. 실패로 돌리면 호출부(storage_service.create_storage)가
            #   delete_helm(name) 으로 **직전에 정상 생성된 PVC 릴리스를 지우므로**, 복구 재시도가
            #   자기 PVC 를 삭제하는 결과가 된다(check job 실패로 DB row 만 지워진 뒤 재시도하는 경로).
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(f"Warning: Helm install failed for {name}:", file=sys.stderr)
            print("Error:", err_msg, file=sys.stderr)
            return False, f"Error executing Helm command: {err_msg}"
        return True, result.stdout
    except Exception as e:
        traceback.print_exc()
        return False, str(e)
    
def delete_helm(name):
    try:

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        
        command=f"""helm uninstall {name} -n {namespace} """

        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False

def create_storage_check_job( name, helm_name ):
    try:
        
        env={
            "NAME": name
        }

        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        image = os.getenv("JFB_RESOURCE_IMAGE")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        
        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{STORAGE_HELM_CHART_NAME}/ \
            -n {namespace} \
            --set name="{name}" \
            --set helm_name="{helm_name}" \
            --set namespace="{namespace}" \
            --set image="{image}" \
            {env_command} \
            """

        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(result.stdout )
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout 
    
def create_storage_exporter(helm_name, name, mountpoint, storage_id, server = None, type = None):
    try:
        delete_helm(helm_name)

        env={
            "STORAGE_ID": storage_id
        }

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        registry = os.getenv("SYSTEM_DOCKER_REGISTRY_URL")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        
        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{STORAGE_EXPORTER}/ \
            -n {namespace} \
            --set name="{name}" \
            --set server="{server}" \
            --set type="{type}" \
            --set mountpoint="{mountpoint}" \
            --set registry="{registry}" \
            {env_command} \
            --debug \
            """
        print("Executing command:", command, file=sys.stderr)
        
        os.chdir("/app/src/storage/helm_chart/")
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        if result.returncode != 0:
            err_msg = result.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(f"Warning: Helm install failed for {helm_name}:", file=sys.stderr)
            print("Command:", command, file=sys.stderr)
            print("Return code:", result.returncode, file=sys.stderr)
            print("Output:", result.stdout, file=sys.stderr)
            print("Error:", err_msg, file=sys.stderr)
            return False, err_msg
        else:
            print(f"Successfully installed {helm_name}", file=sys.stderr)
            return True, result.stdout
            
    except Exception as e:
        print(f"Unexpected error during helm install for {helm_name}:", str(e), file=sys.stderr)
        traceback.print_exc()
        return False, str(e)

def create_storage_local_provisioner(name, mountpoint, reclaimPolicy="Retain"):
    try:
        helm_name= name
        
        delete_helm(helm_name)

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{LOCAL_PATH_PROVISIONER_HELM_CHART_NAME} \
            -n {namespace} \
            --set sharedFileSystemPath={mountpoint} \
            --set storageClass.name={helm_name} \
            --set storageClass.reclaimPolicy={reclaimPolicy} \
            --set configmap.name={helm_name}-config \
            --debug \
            """
        print("Executing command:", command, file=sys.stderr)
        
        os.chdir("/app/src/storage/helm_chart/")
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        if result.returncode != 0:
            err_msg = result.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(f"Warning: Helm install failed for {helm_name}:", file=sys.stderr)
            print("Command:", command, file=sys.stderr)
            print("Return code:", result.returncode, file=sys.stderr)
            print("Output:", result.stdout, file=sys.stderr)
            print("Error:", err_msg, file=sys.stderr)
            return False, err_msg
        else:
            print(f"Successfully installed {helm_name}", file=sys.stderr)
            return True, result.stdout
            
    except Exception as e:
        print(f"Unexpected error during helm install for {helm_name}:", str(e), file=sys.stderr)
        traceback.print_exc()
        return False, str(e)

def create_storage_nfs_provisioner(ip, name, mountpoint, reclaimPolicy="Retain"):
    try:
        helm_name= name

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        
        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{NFS_PROVISIONER_HELM_CHART_NAME} \
            -n {namespace} \
            --set nfs.server={ip} \
            --set nfs.path={mountpoint} \
            --set storageClass.name={helm_name} \
            --set storageClass.reclaimPolicy={reclaimPolicy} \
            --set namespace="{namespace}" \
            """
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False
# create_storage_nfs_provisioner(ip="192.168.1.14",name="jake-sc",mountpoint="/jf-storage-class")
# create_storage_check_job("192.168.1.14", "local", 'jake-sc', '/jf-storage-class')