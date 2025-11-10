import subprocess
import os
import sys
# sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import traceback
import json
from utils.msa_db import db_collect as collect_db
from utils import common, settings
import base64
import json
from datetime import datetime



PUBLIC_API_CHART_NAME = "public-api"
CRAWLING_CHART_NAME = "crawling"
REMOTE_SERVER_CHART_NAME="remote-server"
DEPLOYMENT_COPY_CHART_NAME ="flightbase"

def delete_helm(helm_name, workspace_id):
    try:      
        jonathan_ns = os.getenv("JF_SYSTEM_NAMESPACE")
        namespace = f"{jonathan_ns}-{workspace_id}"
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
    
def create_public_api_collector(pod_info : dict):
    try:

        helm_name=pod_info['helm_name']
        collect_info=pod_info['collect_info']
        sub_path=pod_info['sub_path']
        data_path=pod_info['data_path']
        seconds=pod_info['seconds']
        size=pod_info['size']
        image=pod_info['image']
        jonathan_ns = os.getenv("JF_SYSTEM_NAMESPACE")
        # helm_name=f"collect-{collect_info['name']}-{collect_info['id']}"
        namespace = f"{jonathan_ns}-{collect_info['workspace_id']}"
        registry_url =  settings.SYSTEM_DOCKER_REGISTRY_URL #  os.getenv("DOCKER_REGISTRY_URL")
        # image = os.getenv("JF_COLLECT_APP_IMAGE")

        # nested_dict = {}
        # for item in json.loads(collect_info['collect_information_list']):
        #     # Ensure the key field exists in the dictionary
        #     nested_dict["test"] = item
        # collect_info['create_datetime']=str(collect_info['create_datetime'])
        # collect_info_tmp = base64.b64encode(collect_info['collect_information_list'].encode('utf-8')).decode('utf-8')
        collect_info_tmp = common.helm_parameter_encoding(collect_info['collect_information_list'])
        # collect_info_tmp = json.dumps(nested_dict).encode('utf-8')
        # collect_info_tmp= collect_info_tmp.replace('"', '\"')
        db_env = common.get_flightbase_db_env()
        env={
            "COLLECT_ID" : collect_info['id'],
            "HELM_NAME" : helm_name,
            "NAMESPACE" : namespace,
            "DATA_PATH" : str(data_path),
            "LIMIT_SIZE" : str(size),
            "COLLECT_CYCLE": str(seconds)
        }
        
        dataset_pvc_name = f"{namespace}-data-pvc"
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        for key, val in db_env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/helm_chart/{PUBLIC_API_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}"\
            --set registry="{registry_url}"\
            --set image="{image}"\
            --set collect_id="{collect_info['id']}"\
            --set dataset_id="{collect_info['dataset_id']}"\
            --set dataset_pvc_name="{dataset_pvc_name}"\
            --set dataset_path="{sub_path}"\
            --set namespace="{namespace}"\
            --set workspace_id="{collect_info['workspace_id']}"\
            --set collect_info='{collect_info_tmp}'\
            --set resource.cpu="{collect_info['cpu_allocate']}"\
            --set resource.memory="{collect_info['ram_allocate']}G"\
            --set instance_id="{collect_info['instance_id']}"\
            {env_command} \
            """
        #             --set resource.cpu="{workspace_id}" \
            #  --set resource.momory="{workspace_id}" \
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result:
            kwargs={'start_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'end_datetime' :  None}
            collect_db.update_collect(id=collect_info['id'], **kwargs)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)


def create_crawling_collector(pod_info : dict):
    try:
        helm_name=pod_info['helm_name']
        collect_info=pod_info['collect_info']
        sub_path=pod_info['sub_path']
        data_path=pod_info['data_path']
        seconds=pod_info['seconds']
        size=pod_info['size']
        image=pod_info['image']

        jonathan_ns = os.getenv("JF_SYSTEM_NAMESPACE")
        # helm_name=f"collect-{collect_info['name']}-{collect_info['id']}"
        namespace = f"{jonathan_ns}-{collect_info['workspace_id']}"
        registry_url = settings.SYSTEM_DOCKER_REGISTRY_URL #os.getenv("DOCKER_REGISTRY_URL")
        # image = os.getenv("JF_COLLECT_APP_IMAGE")

        # nested_dict = {}
        # for item in json.loads(collect_info['collect_information_list']):
        #     # Ensure the key field exists in the dictionary
        #     nested_dict["test"] = item
        # collect_info['create_datetime']=str(collect_info['create_datetime'])
        # collect_info_tmp = base64.b64encode(collect_info['collect_information_list'].encode('utf-8')).decode('utf-8')
        collect_info_tmp = common.helm_parameter_encoding(collect_info['collect_information_list'])
        # collect_info_tmp = json.dumps(nested_dict).encode('utf-8')
        # collect_info_tmp= collect_info_tmp.replace('"', '\"')
        db_env = common.get_flightbase_db_env()
        env={
            "COLLECT_ID" : collect_info['id'],
            "HELM_NAME" : helm_name,
            "NAMESPACE" : namespace,
            "DATA_PATH" : str(data_path),
            "LIMIT_SIZE" : str(size),
            "COLLECT_CYCLE": str(seconds)
        }
        
        dataset_pvc_name = f"{namespace}-data-pvc"
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        for key, val in db_env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/helm_chart/{CRAWLING_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}"\
            --set registry="{registry_url}"\
            --set image="{image}"\
            --set collect_id="{collect_info['id']}"\
            --set dataset_id="{collect_info['dataset_id']}"\
            --set dataset_pvc_name="{dataset_pvc_name}"\
            --set dataset_path="{sub_path}"\
            --set namespace="{namespace}"\
            --set workspace_id="{collect_info['workspace_id']}"\
            --set collect_info='{collect_info_tmp}'\
            --set resource.cpu="{collect_info['cpu_allocate']}"\
            --set resource.memory="{collect_info['ram_allocate']}G"\
            --set instance_id="{collect_info['instance_id']}"\
            {env_command} \
            """
        #             --set resource.cpu="{workspace_id}" \
            #  --set resource.momory="{workspace_id}" \
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result:
            kwargs={'start_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'end_datetime' :  None}
            collect_db.update_collect(id=collect_info['id'], **kwargs)

        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

def create_remote_server_collector(pod_info:dict):
    try:
        helm_name=pod_info['helm_name']
        collect_info=pod_info['collect_info']
        sub_path=pod_info['sub_path']
        data_path=pod_info['data_path']
        seconds=pod_info['seconds']
        size=pod_info['size']
        image=pod_info['image']

        jonathan_ns = os.getenv("JF_SYSTEM_NAMESPACE")
        # helm_name=f"collect-{collect_info['name']}-{collect_info['id']}"
        namespace = f"{jonathan_ns}-{collect_info['workspace_id']}"
        registry_url = settings.SYSTEM_DOCKER_REGISTRY_URL
        # image = os.getenv("JF_COLLECT_APP_IMAGE")

        # nested_dict = {}
        # for item in json.loads(collect_info['collect_information_list']):
        #     # Ensure the key field exists in the dictionary
        #     nested_dict["test"] = item
        # collect_info['create_datetime']=str(collect_info['create_datetime'])
        # collect_info_tmp = base64.b64encode(collect_info['collect_information_list'].encode('utf-8')).decode('utf-8')
        collect_info_tmp = common.helm_parameter_encoding(collect_info['collect_information_list'])
        # collect_info_tmp = json.dumps(nested_dict).encode('utf-8')
        # collect_info_tmp= collect_info_tmp.replace('"', '\"')
        db_env = common.get_flightbase_db_env()
        env={
            "COLLECT_ID" : collect_info['id'],
            "HELM_NAME" : helm_name,
            "NAMESPACE" : namespace,
            "DATA_PATH" : str(data_path),
            "LIMIT_SIZE" : str(size),
            "COLLECT_CYCLE": str(seconds)
        }
        
        dataset_pvc_name = f"{namespace}-data-pvc"
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        for key, val in db_env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/helm_chart/{REMOTE_SERVER_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}"\
            --set registry="{registry_url}"\
            --set image="{image}"\
            --set collect_id="{collect_info['id']}"\
            --set dataset_id="{collect_info['dataset_id']}"\
            --set dataset_pvc_name="{dataset_pvc_name}"\
            --set dataset_path="{sub_path}"\
            --set namespace="{namespace}"\
            --set workspace_id="{collect_info['workspace_id']}"\
            --set collect_info='{collect_info_tmp}'\
            --set resource.cpu="{collect_info['cpu_allocate']}"\
            --set resource.memory="{collect_info['ram_allocate']}G"\
            --set instance_id="{collect_info['instance_id']}"\
            {env_command} \
            """
        #             --set resource.cpu="{workspace_id}" \
            #  --set resource.momory="{workspace_id}" \
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result:
            kwargs={'start_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'end_datetime' :  None}
            collect_db.update_collect(id=collect_info['id'], **kwargs)

        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)
    
def create_fb_deployment_collector(pod_info):
    try:

        helm_name=pod_info['helm_name']
        collect_info=pod_info['collect_info']
        sub_path=pod_info['sub_path']
        data_path=pod_info['data_path']
        seconds=pod_info['seconds']
        size=pod_info['size']
        image=pod_info['image']

        jonathan_ns = os.getenv("JF_SYSTEM_NAMESPACE")
        namespace = f"{jonathan_ns}-{collect_info['workspace_id']}"
        registry_url = settings.SYSTEM_DOCKER_REGISTRY_URL # os.getenv("DOCKER_REGISTRY_URL")
        # image = os.getenv("JF_COLLECT_APP_IMAGE")
        # deployment_path = f"/{storage_name}/main/{workspace_name}/deployments"

        # collect_info_tmp = common.helm_parameter_encoding(collect_info['collect_information_list'])

        db_env = common.get_flightbase_db_env()
        env={
            "COLLECT_ID" : collect_info['id'],
            "HELM_NAME" : helm_name,
            "NAMESPACE" : namespace,
            "DATA_PATH" : str(data_path),
            "LIMIT_SIZE" : str(size),
            "COLLECT_CYCLE": str(seconds)
        }
        
        dataset_pvc_name = f"{namespace}-data-pvc"
        main_pvc_name = f"{namespace}-main-pvc"
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        for key, val in db_env.items():
            if val:
                env_command += f" --set env.{key}={val}"

        command=f"""helm install {helm_name} /app/helm_chart/{DEPLOYMENT_COPY_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}"\
            --set registry="{registry_url}"\
            --set image="{image}"\
            --set collect_id="{collect_info['id']}"\
            --set dataset_id="{collect_info['dataset_id']}"\
            --set dataset_pvc_name="{dataset_pvc_name}"\
            --set dataset_path="{sub_path}"\
            --set namespace="{namespace}"\
            --set workspace_id="{collect_info['workspace_id']}"\
            --set main_pvc_name="{main_pvc_name}"\
            --set main_sub_path="deployments"\
            --set resource.cpu="{collect_info['cpu_allocate']}"\
            --set resource.memory="{collect_info['ram_allocate']}G"\
            --set instance_id="{collect_info['instance_id']}"\
            {env_command} \
            """
        #--set collect_info='{collect_info_tmp}'\

        #             --set resource.cpu="{workspace_id}" \
            #  --set resource.momory="{workspace_id}" \
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result:
            kwargs={'start_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'end_datetime' :  None}
            collect_db.update_collect(id=collect_info['id'], **kwargs)

        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)