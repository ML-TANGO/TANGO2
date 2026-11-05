import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils import settings, TYPE
import traceback
from utils.redis_key import JOB_LIST, DATASET_FILEBROWSER_POD_STATUS
from utils.redis import get_redis_client
import json
DECOMPRESS_CHART_NAME="decompress"
WGET_CHART_NAME="wget"
SCP_CHART_NAME="scp"
FILEBROWSER_CHART_NAME="filebrowser"
GIT_CHART_NAEM='git'
redis = get_redis_client()

def create_decompress_job(target, destination, extention, redis_key, redis_sub_key, helm_name, image, storage_name, header_user,
                          dataset_id,dataset_name, workspace_id,workspace_name, user_id):
    try:
        # helm_name=redis_sub_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        env={
            "TARGET" : target,
            "DESTINATION" : destination,
            "EXTENTION" : extention,
            "REDIS_KEY" : redis_key,
            "REDIS_SUB_KEY" : redis_sub_key,
            "HEADER_USER" : header_user,
            "JOB_NAME" : helm_name,
            "DATASET_ID" : dataset_id,
            "DATASET_NAME" : dataset_name,
            "WORKSPACE_ID" : workspace_id,
            "WORKSPACE_NAME" : workspace_name,
            "UPLOAD_USER" : user_id
        }
        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/src/helm_chart/{DECOMPRESS_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set image="{image}" \
            --set storage_name="{storage_name}" \
            --set namespace="{namespace}" \
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
        redis.hset(JOB_LIST,helm_name,namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
def delete_helm(helm_name, namespace='jfb'):
    try:
        # helm_name=redis_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        # namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        
        command=f"""helm uninstall {helm_name} -n {namespace} """

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

def scp_upload_job(ip, username, password, target, destination, path, redis_key, helm_name, image, storage_name, header_user,
                   dataset_id,dataset_name, workspace_id,workspace_name, user_id):
    try:
        # helm_name=redis_sub_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        env={
            "IP": ip,
            "USER_NAME":username,
            "PASSWD":password,
            "TARGET" : target,
            "DESTINATION" : destination,
            "REDIS_KEY" : redis_key,
            "HEADER_USER" : header_user,
            "UPLOAD_PATH" : path,
            "JOB_NAME" : helm_name,
            "DATASET_ID" : dataset_id,
            "DATASET_NAME" : dataset_name,
            "WORKSPACE_ID" : workspace_id,
            "WORKSPACE_NAME" : workspace_name,
            "UPLOAD_USER" : user_id
        }
        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/src/helm_chart/{SCP_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set image="{image}" \
            --set storage_name="{storage_name}" \
            --set namespace="{namespace}" \
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
        redis.hset(JOB_LIST,helm_name,namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
def wget_upload_job(upload_url, destination, redis_key, path, helm_name, image, storage_name, header_user,
                    dataset_id,dataset_name, workspace_id,workspace_name, user_id):
    try:
        # helm_name=redis_sub_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        env={
            "DOWNLOAD_URL": upload_url,
            "DESTINATION" : destination,
            "REDIS_KEY" : redis_key,
            "HEADER_USER" : header_user,
            "UPLOAD_PATH" : path,
            "JOB_NAME" : helm_name,
            "DATASET_ID" : dataset_id,
            "DATASET_NAME" : dataset_name,
            "WORKSPACE_ID" : workspace_id,
            "WORKSPACE_NAME" : workspace_name,
            "UPLOAD_USER" : user_id
        }
        #TODO 네임스페이스를 어디로 지정?
        namespace = settings.JF_SYSTEM_NAMESPACE
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/src/helm_chart/{WGET_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set image="{image}" \
            --set storage_name="{storage_name}" \
            --set namespace="{namespace}" \
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
        redis.hset(JOB_LIST,helm_name,namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout

def git_upload_job(git_repo_url, destination, path, git_access, git_cmd, redis_key, helm_name, image, storage_name, header_user, 
                   dataset_id,dataset_name, workspace_id,workspace_name, user_id, git_id=None, git_access_token=None,):
    try:
        # helm_name=redis_sub_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        env={
            "GIT_REPO_URL": git_repo_url,
            "GIT_REPO_PATH" : destination,
            "REDIS_KEY" : redis_key,
            "HEADER_USER" : header_user,
            "GIT_ACCESS" : git_access,
            "GIT_ID" : git_id,
            "GIT_ACCESS_TOKEN" : git_access_token,
            "GIT_CMD" :git_cmd,
            "UPLOAD_PATH" : path,
            "JOB_NAME" : helm_name,
            "DATASET_ID" : dataset_id,
            "DATASET_NAME" : dataset_name,
            "WORKSPACE_ID" : workspace_id,
            "WORKSPACE_NAME" : workspace_name,
            "UPLOAD_USER" : user_id
        }
        #TODO 네임스페이스를 어디로 지정?
        namespace = settings.JF_SYSTEM_NAMESPACE 
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/src/helm_chart/{GIT_CHART_NAEM}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set image="{image}" \
            --set storage_name="{storage_name}" \
            --set namespace="{namespace}" \
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
        redis.hset(JOB_LIST,helm_name,namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
def filebrowser_run(filebrowser_name, dataset_path, dataset_pvc_name, ingress_path, namespace, dataset_id, workspace_id):
    try:
        # helm_name=redis_sub_key.replace(':',"-")
        # helm_name=helm_name.replace('_','-')
        # helm_name=helm_name.replace('/','.')
        # env={
        #     "DOWNLOAD_URL": upload_url,
        #     "DESTINATION" : destination,
        #     "REDIS_KEY" : redis_key,
        #     "HEADER_USER" : header_user
        # }
        #TODO 네임스페이스를 어디로 지정?
        ingress_class = settings.INGRESS_CLASS_NAME 
        registry_url= settings.SYSTEM_DOCKER_REGISTRY_URL
        # env_command=""
        # for key, val in env.items():
        #     if val:
        #         env_command += f" --set env.{key}={val}"
        command=f"""helm install {filebrowser_name} /app/src/helm_chart/{FILEBROWSER_CHART_NAME}/ \
            -n {namespace} \
            --set name="{filebrowser_name}" \
            --set dataset_path="{dataset_path}" \
            --set dataset_pvc_name="{dataset_pvc_name}" \
            --set ingress_path="{ingress_path}" \
            --set ingress_class="{ingress_class}" \
            --set dataset_id="{dataset_id}" \
            --set registry="{registry_url}" \
            --set workspace_id="{workspace_id}"
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
        pod_info={
            'url' : f"/{ingress_path}",
            'pod_status' : "pending"
        }
        redis.hset(DATASET_FILEBROWSER_POD_STATUS, dataset_id, json.dumps(pod_info))
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
# def git_pull_job(git_repo_url, destination, git_access, redis_key, helm_name, image, storage_name, header_user, git_id=None, git_access_token=None):
#     try:
#         # helm_name=redis_sub_key.replace(':',"-")
#         # helm_name=helm_name.replace('_','-')
#         # helm_name=helm_name.replace('/','.')
#         env={
#             "GIT_REPO_URL": git_repo_url,
#             "DESTINATION" : destination,
#             "REDIS_KEY" : redis_key,
#             "HEADER_USER" : header_user,
#             "GIT_ACCESS" : git_access,
#             "GIT_ID" : git_id,
#             "GIT_ACCESS_TOKEN" : git_access_token
#         }
#         #TODO 네임스페이스를 어디로 지정?
#         namespace = os.getenv("JF_SYSTEM_NAMESPACE")
#         env_command=""
#         for key, val in env.items():
#             if val:
#                 env_command += f" --set env.{key}={val}"
#         command=f"""helm install {helm_name} /app/src/helm_chart/{WGET_CHART_NAME}/ \
#             -n {namespace} \
#             --set name="{helm_name}" \
#             --set image="{image}" \
#             --set storage_name="{storage_name}" \
#             --set namespace="{namespace}" \
#             {env_command} \
#             """
#         result = subprocess.run(
#             command,
#             shell=True,
#             check=True,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#         )
#         print(result.stdout )
#         redis.hset(JOB_LIST,helm_name,namespace)
#         return True, result.stdout 
#     except subprocess.CalledProcessError as e:
#         traceback.print_exc()
#         return False, f"Error executing Helm command: {e.stderr}"
#     except:
#         traceback.print_exc()
#         return False, result.stdout



# create_storage_nfs_provisioner(ip="192.168.1.14",name="jake-sc",mountpoint="/jf-storage-class")
# create_storage_check_job("192.168.1.14", "local", 'jake-sc', '/jf-storage-class')