import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils import settings, TYPE
import traceback
from utils.redis_key import JOB_LIST
from utils.redis import get_redis_client
NODE_ACTIVATE_CHART_NAME="node-activate"

redis = get_redis_client()

def create_node_active_job(node, active : bool):
    try:
        if active:
            status = "uncordon"
        else:
            status = "cordon"
            #"drain"
        helm_name=node+'-'+status
        print(status)
        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        command=f"""helm install {helm_name} /app/src/node/helm_chart/{NODE_ACTIVATE_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set node="{node}" \
            --set status="{status}" \
            --set namespace="{namespace}" \
            --set registry="{settings.DOCKER_REGISTRY_URL}" \
            """
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        redis.hset(JOB_LIST, helm_name, namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
def delete_helm(node, active : bool):
    try:
        if active:
            status = "uncordon"
        else:
            status = "drain"
        helm_name=node+'-'+status

        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        
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