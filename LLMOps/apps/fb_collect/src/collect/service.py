#-*- coding:utf-8 -*-
from utils.resource import response
# import utils.db as db
import utils.msa_db.db_collect as collect_db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_instance as instance_db
import utils.msa_db.db_workspace as ws_db
import utils.db as db
from utils.msa_db import db_user as user_db 
from utils.msa_db import db_storage as storage_db
import utils.crypt as cryptUtil
from utils.exception.exceptions import *
from utils.common import *
from utils.access_check import *
from shutil import *
from pathlib import Path, PurePath
from utils.PATH import JF_DATA_DATASET_PATH
from utils import topic_key, TYPE
# from utils.lock import jf_dataset_lock
import subprocess
import os
import fnmatch
import traceback
from datetime import datetime 
import tarfile
import zipfile
from PIL import Image
import io
import requests
import urllib
import aiohttp
# from upload.service import upload_data
from pwd import getpwuid
from utils.redis_key import DATASET_PROGRESS, DATASET_STORAGE_USAGE, DATASET_FILEBROWSER_POD_STATUS, DATASET_UPLOADSIZE, DATASET_UPLOAD_LOCK, DATASET_DUPLICATE, DATASET_UPLOAD_LIST, WORKSPACE_PODS_STATUS
from utils.redis import get_redis_client, get_redis_client_async

# from helm_run import create_decompress_job, delete_helm, filebrowser_run
from utils.access_check import check_dataset_access_level
from utils.common import get_own_user, format_size
import hashlib
from functools import lru_cache, cache
from utils.workspace_resource import get_workspace_instance_used
from collect import helm_run as helm
from utils.msa_db import db_collect_history as history_db
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from aiokafka import AIOKafkaProducer

# from aiokafka import AIOKafkaProducer

DATA_PATH="/jf-data/{STORAGE_NAME}/data/{WORKSPACE_NAEM}/{ACCESS}/{DATASET_NAME}"

# redis = get_redis_client()
#def create_dataset_base_dir()

def create_collector(body):
    try:
        if collect_db.get_collect_info(name=body.name) is not None:
            raise Exception("already exist collect")
        collect_id = collect_db.insert_collect(name=body.name, description=body.description,  dataset_id=body.dataset_id, dataset_path=body.dataset_path,
                                    instance_id= body.instance_id, instance_count= body.instance_count, collect_method= body.collect_method, collect_cycle=body.collect_cycle, collect_cycle_unit=body.collect_cycle_unit,
                                    collect_storage_limit= body.collect_storage_limit, collect_storage_size=body.collect_storage_size, collect_storage_unit=body.collect_storage_unit,
                                    collect_information_list= json.dumps(body.collect_information_list), access= body.access, owner_id= body.owner_id, workspace_id=body.workspace_id,
                                    members = json.dumps(body.members))
        sys.stdout.flush()
        if collect_id:
            return True
    except Exception as e:
        raise e

async def get_collectors_async(workspace_id=None): #, headers_user=None
    try :
        # global redis
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        # user_info = user_db.get_user_id(headers_user)
        # user_id = 1 if user_info['id'] is None else user_info['id']
        
        collect_lists = collect_db.get_collect_list(workspace_id=workspace_id)
        
        # Redis 연결 시도 - 실패해도 기본 상태로 계속 진행
        pod_status = None
        try:
            redis_client = await get_redis_client_async()
            pod_status_raw = await redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
            if pod_status_raw:
                pod_status = json.loads(pod_status_raw).get(TYPE.COLLECT_TYPE, None)
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 기본 상태로 진행: {e}")
            pod_status = None

        for collect_info in collect_lists:
            user_list=[]
            collect_info['instance_info']=instance_db.get_instance(instance_id=collect_info['instance_id'])
            try:
                collect_info['owner']=user_db.get_user(user_id=collect_info['owner_id'])['name']
            except:
                collect_info['owner']=None
            try:
                collect_info['dataset_name']=dataset_db.get_dataset(dataset_id=collect_info['dataset_id'])['name']
            except:
                collect_info['dataset_name']=None
            collect_info['collect_information_list'] = json.loads(collect_info['collect_information_list'])
            collect_info['status'] = pod_status.get(str(collect_info['id']), None) if pod_status else None
            if collect_info['members']:
                collect_info['members'] = json.loads(collect_info['members'])
                for user_id in collect_info['members']:
                    user_list.append({user_id : user_db.get_user(user_id=user_id)['name']})
            collect_info['members'] = user_list

        res = {'list' : collect_lists, 'total' : len(collect_lists) }
        return res
    except:
        traceback.print_exc()
        return False

async def get_collector_info_async(id=None, name=None): #, headers_user=None
    try :
        # global redis
        result={}
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        # user_info = user_db.get_user_id(headers_user)
        # user_id = 1 if user_info['id'] is None else user_info['id']
        
        members=[]
        collector_info = collect_db.get_collect_info(collect_id=id, name=name)

        instance_info = instance_db.get_instance(instance_id=collector_info['instance_id'])
        workspace_instance_resource_allocate = db.get_workspace_allocate_instance(workspace_id=collector_info['workspace_id'],instance_id=int(collector_info['instance_id']))
        try:
            collector_info['dataset_name']=dataset_db.get_dataset(dataset_id=collector_info['dataset_id'])['name']
        except:
            collector_info['dataset_name']=None
        collector_info['owner']=user_db.get_user(user_id=collector_info['owner_id'])['name']
        collector_info['collect_information_list'] = json.loads(collector_info['collect_information_list'])
        if collector_info['members']:
            for user_id in json.loads(collector_info['members']):
                user_info = user_db.get_user(user_id=user_id)
                if user_info:
                    members.append(user_info['name'])
            # members.extend(user_db.get_user(user_id=user_id)['name'] )
        collector_info['members'] = members
        resource_used, instance_used = await get_workspace_instance_used(instance_id=int(collector_info['instance_id']), workspace_id=collector_info['workspace_id'])

        cpu_available = True
        ram_available = True
        
        available_cpu_core = (instance_info["cpu_allocate"] * workspace_instance_resource_allocate["instance_allocate"]) - resource_used["cpu"]
        
        if available_cpu_core <= 0 or available_cpu_core < (instance_info["cpu_allocate"]*collector_info['instance_count']) :
            cpu_available = False
        available_ram = (instance_info["ram_allocate"] * workspace_instance_resource_allocate["instance_allocate"]) - resource_used["ram"]
        
        if available_ram < 0 or available_ram < (instance_info["ram_allocate"]*collector_info['instance_count']) :
            ram_available = False

        # Redis 연결 시도 - 실패해도 기본 상태로 계속 진행
        pod_status = None
        try:
            redis_client = await get_redis_client_async()
            pod_status_raw = await redis_client.hget(WORKSPACE_PODS_STATUS, collector_info['workspace_id'])
            if pod_status_raw:
                pod_status = json.loads(pod_status_raw).get(TYPE.COLLECT_TYPE, None)
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 기본 상태로 진행: {e}")
            pod_status = None

        result={
            "collect_info" : collector_info,
            "instance_info" : instance_info,
            "instance_usage_info": {
                "cpu":{
                    "available_cpu_core" : available_cpu_core,
                    "available" : cpu_available
                },
                "memory":{
                    "available_memory":available_ram,
                    "available" : ram_available
                },
                "usage_info":instance_used
            },
            "status" : pod_status.get(str(collector_info['id']), {"status": collector_info['status']}) if pod_status else TYPE.KUBE_POD_STATUS_STOP
        }
        return result
    except:
        traceback.print_exc()
        return False
    
def get_collector_history(id=None): #TODO EFK와 연동시켜야함
    try :
        # global redis
        collect_history_list=[]
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        # user_info = user_db.get_user_id(headers_user)
        # user_id = 1 if user_info['id'] is None else user_info['id']
        # collector_info = collect_db.get_collect_info(collect_id=id)
        collect_history_list = history_db.get_collect_history_list(collect_id=id)
        if collect_history_list:
            for collect_history in collect_history_list:
                collect_history['collect_information'] = json.loads(collect_history['collect_information'])
        # collector_info['collect_information_list'] = json.loads(collector_info['collect_information_list'])
        
        
        # for collect in collector_info['collect_information_list']:
        #     result.append(
        #         {
        #             "collect_info" : collect,
        #             "datetime" : "2024-12-02 08:00:00",
        #             "status" : "success"
        #         }
        #     )
        return collect_history_list
    except:
        traceback.print_exc()
        return collect_history_list
    
async def delete_collect(id ): #headers_user
    try:
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        if collect_db.get_collect_info(collect_id=id) is None:
            return response(status=0, message="Not exist collect")
        res=collect_db.delete_collect(id=id)
        if res:
            return True
    except Exception as e:
         return response(status=0, message=e)
    
async def update_collector(id, body): #, headers_user
    try:
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        if collect_db.get_collect_info(collect_id=id) is None:
            raise Exception("not exist collect")

        body['members']=json.dumps(body['members'])
        if body['collect_information_list']:
            body['collect_information_list']= json.dumps(body['collect_information_list'])
        res =collect_db.update_collect(id=id, **body)
        return res
    except Exception as e:
        traceback.print_exc()
        raise e
    
def collect_options(workspace_id, headers_user):
    try:
        res = {
                "dataset_list" : dataset_db.get_dataset_list(workspace_id=workspace_id),
                "user_list" : user_db.get_user_list_in_workspace(workspace_id=workspace_id),
                "instance_list" : ws_db.get_workspace_instance_list(workspace_id=workspace_id),
                "deployment_list" : db.get_deployment_list_in_workspace(workspace_id=workspace_id)
            }
        return res
    except Exception as e:
        raise e
    
def get_data_path(dataset_id):
    try:
        dataset_info = db.get_dataset(dataset_id)
        workspace_info = db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'],
                                                WORKSPACE_NAME=workspace_info['name'],
                                                ACCESS= dataset_info['access'], 
                                                DATASET_NAME=dataset_info['name']))
        return dataset_dir
    except:
        return False
    
async def start_collector(collect_id, headers_user=None):
    try:
        collect_info = await collect_db.get_collect_info_async(collect_id=collect_id)
        kwargs={'start_datetime':None,
                'status': TYPE.KUBE_POD_STATUS_PENDING}
        if collect_info['end_datetime']:
           kwargs['end_datetime']=None
                
        collect_db.update_collect(id=collect_id, **kwargs)

        dataset_info = db.get_dataset(collect_info['dataset_id'])
        if collect_info:
            collect_info['create_datetime'] =  collect_info['create_datetime'].strftime('%Y-%m-%d %H:%M:%S') if collect_info['create_datetime'] else None
            collect_info['start_datetime'] = collect_info['start_datetime'].strftime('%Y-%m-%d %H:%M:%S') if collect_info['start_datetime'] else None
            collect_info['end_datetime'] = collect_info['end_datetime'].strftime('%Y-%m-%d %H:%M:%S') if collect_info['end_datetime'] else None
            pod_info={
                "collect_id" : collect_info['id'],
                "workspace_id" : collect_info['workspace_id'],
                "gpu_count" : 0,
                "gpu_cluster_auto" : False,
                "gpu_auto_cluster_case" : {},
                "gpu_select" : [],
                "instance_id" : collect_info['instance_id'],
                "resource_type" : collect_info['instance_type'],
                "pod_type" : COLLECT_TYPE,
                "work_func_type" : "",
                "image" : os.getenv("JF_COLLECT_APP_IMAGE"),
                "helm_name" : f"collect-{collect_info['name']}-{collect_info['id']}".lower(),
                "collect_info" : collect_info,
                "sub_path" : f"{dataset_info['access']}/{dataset_info['name']}",
                "data_path" : collect_info['dataset_path'],
                "seconds" : convert_to_seconds(num=collect_info['collect_cycle'], unit=collect_info['collect_cycle_unit']),
                "size" : convert_to_bytes(size=collect_info['collect_storage_size'], unit=collect_info['collect_storage_unit']) if collect_info['collect_storage_limit'] else 0

            }
            # helm_name= f"collect-{collect_info['name']}-{collect_info['id']}"
            
            # sub_path = f"{dataset_info['access']}/{dataset_info['name']}"
            # data_path = collect_info['dataset_path']
            # # dataset_dir=get_data_path(dataset_id=collect_info['dataset_id'])
            # # data_path=dataset_dir.joinpath(collect_info['dataset_path'])
            # seconds = convert_to_seconds(num=collect_info['collect_cycle'], unit=collect_info['collect_cycle_unit'])
            # if collect_info['collect_storage_limit']:
            #     size = convert_to_bytes(size=collect_info['collect_storage_size'], unit=collect_info['collect_storage_unit'])
            # else:
            #     size = 0
            
            if collect_info['collect_method'] == "public_api":
                pod_info['work_func_type']=PUBLICAPI_TYPE
            elif collect_info['collect_method'] == "crawling":
                pod_info['work_func_type']=CRAWLING_TYPE
            elif collect_info['collect_method'] == "remote_server":
                pod_info['work_func_type']=REMOTESERVER_TYPE
            elif collect_info['collect_method'] == "flightbase":
                pod_info['work_func_type']=FB_DEPLOY_TYPE
            else:
                return response(status=0, message="Unkown collect method")
                
            producer = AIOKafkaProducer(
            bootstrap_servers=settings.JF_KAFKA_DNS,
            value_serializer=lambda v: v.encode('utf-8'),  # 문자열 값을 바이트로 직렬화
            # key_serializer=lambda v: v.encode('utf-8')    # 문자열 키를 바이트로 직렬화
            )
            # 프로듀서 시작
            await producer.start()
            try:
                # 메시지 보내기
                topic = topic_key.SCHEDULER_TOPIC
                message = json.dumps(pod_info)
                print(message)
                await producer.send_and_wait(topic, value=message)
            except:
                traceback.print_exc()
            finally:
                # 프로듀서 종료
                await producer.stop()
            return response(status=1, message="collect start request complete")
        else:
            return response(status=0, message="not exist collect")
    except Exception as e:
        traceback.print_exc()
        raise e 

async def stop_collector(collect_id,  headers_user=None):
    try:
        collect_info = await collect_db.get_collect_info_async(collect_id=collect_id)
        if collect_info:
            redis_client = await get_redis_client_async()
            pod_status = await redis_client.hget(WORKSPACE_PODS_STATUS, collect_info['workspace_id'])
            if pod_status:
                pod_status= json.loads(pod_status)[TYPE.COLLECT_TYPE]
                pod_status=pod_status.get(str(collect_id), None)
                if pod_status:        
                    helm_name= f"collect-{collect_info['name']}-{collect_info['id']}"
                    if collect_info['collect_method'] == "public_api":
                        helm.delete_helm(helm_name=helm_name, workspace_id=collect_info['workspace_id'])
                    elif collect_info['collect_method'] == "crawling":
                        helm.delete_helm(helm_name=helm_name, workspace_id=collect_info['workspace_id'])
                    elif collect_info['collect_method'] == "remote_server":
                        helm.delete_helm(helm_name=helm_name, workspace_id=collect_info['workspace_id'])
                    elif collect_info['collect_method'] == "flightbase":
                        helm.delete_helm(helm_name=helm_name, workspace_id=collect_info['workspace_id'])
                    else:
                        return response(status=0, message="Unkown collect method")
                kwargs={
                    'end_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': TYPE.KUBE_POD_STATUS_STOP
                }
                collect_db.update_collect(id=collect_id, **kwargs)
            return response(status=1, message="The collector stop completed.")
        else:
            return response(status=0, message="not exist collect")
    except Exception as e:
        raise e 

async def get_dataset_dir(dataset_id):
    try:
        dataset_info = await dataset_db.get_dataset_async(dataset_id=dataset_id)
        workspace_info = await ws_db.get_workspace_async(workspace_id=dataset_info['workspace_id'])
        storage_info = await storage_db.get_storage_async(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(DATA_PATH.format(STORAGE_NAME=storage_info['name'], 
                                            WORKSPACE_NAEM=workspace_info['name'], 
                                            ACCESS=dataset_info['access'], 
                                            DATASET_NAME=dataset_info['name']))
        return dataset_dir
    
    except Exception as e:
        traceback.print_exc()
        return None

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


async def get_dataset_dir_list(dataset_id,path=""):
    try:
        dataset_dir = await get_dataset_dir(dataset_id=dataset_id)
        if path:
            dataset_dir=dataset_dir.joinpath(path)
        folder_list = [item.name for item in dataset_dir.iterdir() if item.is_dir()]

        return folder_list

    except Exception as e:
        traceback.print_exc()
        return None

async def get_public_data_api_list():
    try:
        # result={}
        # url = "https://api.odcloud.kr/api/15062804/v1/uddi:722d145f-78f6-4897-be36-b7acf5ad6487"
        # service_key = "GVhNhO5wfapPfkjDpWVpZ2G0RTs/4DvSIcgR/rrYjZTX1c9O08m851TzIjAP90L36DQ02yuQwZpQUGfmUZkh5w=="

        # # 쿼리 파라미터와 헤더 설정
        # params = {
        #     "page": 1,
        #     "perPage": 10,
        #     "serviceKey": service_key
        # }
        # headers = {
        #     "Authorization": service_key
        # }
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(url, params=params, headers=headers) as res:
        #         if res.status == 200:
        #             result = await res.json()

        #         else:
        #             result = await res.text()
        # return response(status=1,result=result)
        public_api_list = await collect_db.get_public_api_list()
        for public_api in public_api_list:
            public_api['jsonData'] = json.loads(public_api['jsonData'])
        return public_api_list

    except Exception as e:
        traceback.print_exc()
        raise e
    
async def update_bookmark(id, bookmark:bool):
    try:
        collect_info = await collect_db.get_collect_info_async(collect_id=id)
        if not collect_info:
            return response(status=0, message="Not exist collect ID")
        res = await collect_db.update_collect_bookmark(id=id, bookmark= 1 if bookmark else 0)
        if res:
            return response(status=1, message="Bookmark Update Complete")
        else:
            return response(status=0, message="Bookmark Update Fail")
    except Exception as e:
        traceback.print_exc()
        raise e

#get_dataset_dir_list
async def delete_history_data(collect_id, history_id):
    try:
        collect_info = await collect_db.get_collect_info_async(collect_id=collect_id)
        dataset_dir = await get_dataset_dir(dataset_id=collect_info['dataset_id'])
        if not dataset_dir:
            return response(status=0, message="Not exist data path")
        if not collect_info:
            return response(status=0, message="Not exist collect ID")
        if history_id:
            history_info = history_db.get_collect_history(id=history_id)
            if history_info:
                target_path = dataset_dir.joinpath(history_info['path'])
                if target_path.exists():
                    if target_path.is_file():
                        target_path.unlink()  # 파일 삭제
                    elif target_path.is_dir():
                        shutil.rmtree(target_path)  # 폴더 및 그 안의 모든 파일 삭제
                if history_db.delete_collect_history(id=history_id):
                    return response(status=1, message="history delete complete")
                else:
                    return response(status=0, message="history delete fail")
        else:
            target_path = dataset_dir.joinpath(collect_info['dataset_path'])
            for item in target_path.iterdir():
                if item.exists():
                    if item.is_file():
                        item.unlink()
                    else:
                        shutil.rmtree(item)

            if await history_db.delete_all_collect_history_async(collect_id=collect_id):
                return response(status=1, message="history delete complete")
            else:
                return response(status=0, message="history delete fail")

    except Exception as e:
        traceback.print_exc()
        raise e
                    
