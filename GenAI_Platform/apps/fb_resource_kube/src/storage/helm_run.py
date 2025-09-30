import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils import settings, TYPE
import traceback
NFS_PROVISIONER_HELM_CHART_NAME= "nfs-subdir-external-provisioner"
STORAGE_HELM_CHART_NAME = "storage_check"
PVC_CHART_NAME = "volume"
STORAGE_EXPORTER = "storage-exporter"

def create_storage_pvc(ip, name, mountpoint):
    try:

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")


        command=f"""helm install {name} /app/src/storage/helm_chart/{PVC_CHART_NAME} \
            -n {namespace} \
            --set server={ip} \
            --set path={mountpoint} \
            --set name={name} \
            --set namespace="{namespace}" \
            """
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
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout

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
            "NAME":"storage-"+name
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

def create_storage_exporter(helm_name, name, server, mountpoint, storage_id ):
    try:

        env={
            "STORAGE_ID": storage_id
        }

        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        registry = os.getenv("DOCKER_REGISTRY_URL")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"

        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{STORAGE_EXPORTER}/ \
            -n {namespace} \
            --set name="{name}" \
            --set server="{server}" \
            --set mountpoint="{mountpoint}" \
            --set registry="{registry}" \
            {env_command} \
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
        print(result.stdout )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout

def create_storage_nfs_provisioner(ip, name, mountpoint):
    try:
        helm_name= name

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")


        command=f"""helm install {helm_name} /app/src/storage/helm_chart/{NFS_PROVISIONER_HELM_CHART_NAME} \
            -n {namespace} \
            --set nfs.server={ip} \
            --set nfs.path={mountpoint} \
            --set storageClass.name={helm_name} \
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