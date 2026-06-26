# -*- coding:utf-8 -*-
from utils.resource import response

# import utils.db as db
import utils.msa_db.db_analyzing as db_analyzer
from utils.exception.exceptions import *
from utils.common import *
from utils.access_check import *
from shutil import *
from pwd import getpwuid
from utils import redis_key
from utils.redis import get_redis_client_async
import utils.db as db
from utils import helm_dto
from utils import topic_key
from utils.workspace_resource import get_workspace_instance_total_info, get_workspace_instance_used

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
class KafkaProducer:
    def __init__(self):
        self.conf = {
            'bootstrap.servers' : f"{settings.JF_KAFKA_DNS}"
        }
        self.producer = Producer(self.conf)
    def produce(self, topic, key, value):
        self.producer.produce(topic, key, value)
        self.producer.poll(1)
        self.producer.flush()
kafka = KafkaProducer()
kafak_admin_client = AdminClient({'bootstrap.servers' : settings.JF_KAFKA_DNS})


async def check_healthz():
    try:
        redis_client = await get_redis_client_async()
        await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
        return True
    except:
        return False

def create_analyzer(name, description, instance_id, instance_allocate, access, owner_id, workspace_id, users_id):
    try:
        if db.get_analyzer_info(name=name) is not None:
            raise Exception("already exist analyzer")

        instance_info = db.get_instance(instance_id=instance_id)
        analyzer_id = db.insert_analyzer(
            name=name, description=description, instance_id=instance_id, instance_allocate=instance_allocate,
            access=access, owner_id=owner_id, workspace_id=workspace_id,
            graph_cpu_limit=instance_info.get("cpu_allocate"),
            graph_ram_limit=instance_info.get("ram_allocate"),
        )
        
        if not analyzer_id:
            return False

        users_id.append(owner_id)
        analyzers_id = [analyzer_id]*len(users_id)
        insert_user_analyzer_result, message = db.insert_user_analyzer_list(analyzers_id=analyzers_id, users_id=users_id)

        if not insert_user_analyzer_result:
            return False

        return True
    except Exception as e:
        traceback.print_exc()
        raise e

def get_analysis_list(workspace_id=None, user_id=None):  # , headers_user=None
    result = []
    try:
        analyzer_lists = db.get_analyzer_list(workspace_id=workspace_id)
        user_bookmark_list = [info["analyzer_id"]
            for info in db.get_user_analyzer_bookmark_list(user_id=user_id)]

        for item in analyzer_lists:
            result.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "create_datetime": item.get("create_datetime"),
                "update_datetime": item.get("update_datetime"),
                "access": item.get("access"),
                "owner": item.get("owner_name"),
                "workspace_id": item.get("workspace_id"),
                "instance" : {
                    "instance_name" : item.get("instance_name"),
                    "instance_allocate" : item.get("instance_allocate"),
                    "gpu_name" : item.get("gpu_name"),
                    "gpu_allocate" : item.get("gpu_allocate"),
                    "cpu_allocate" : item.get("cpu_allocate"),
                    "ram_allocate" : item.get("ram_allocate"),
                },
                "bookmark" : 1 if item["id"] in user_bookmark_list else 0,
            })
        
        result.sort(key=lambda x: x['id'], reverse=True)
        return result
    except:
        traceback.print_exc()
        return []
    
async def get_analyzer_info(analyzer_id=None, name=None): #, headers_user=None
    try:
        item = db.get_analyzer_info(analyzer_id=analyzer_id, name=name)
        users = db.get_user_analyzer_list(analyzer_id=analyzer_id) if item.get("access")==0 else []
        instance_info = await get_workspace_instance_total_info(instance_id=item.get("instance_id"), workspace_id=item.get("workspace_id"),
                                                                instance_allocate=item.get("instance_allocate"),
                                                                resource_limit=[{"cpu_limit" : item.get("graph_cpu_limit"), "ram_limit" : item.get("graph_ram_limit")}]
                                                                )
        result = {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "create_datetime": item.get("create_datetime"),
            "update_datetime": item.get("update_datetime"),
            "access": item.get("access"),
            "owner": item.get("owner_name"),
            "instance" : instance_info,
            "users" : users
        }
        return result
    except:
        traceback.print_exc()
        return None

def delete_analyzer(id_list, headers_user):
    try:
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        for id in id_list:
            if db_analyzer.get_analyzer_info(analyzer_id=id) is None:
                raise Exception("not exist analyzer")
            res =db_analyzer.delete_analyzer(id=id)

            # 토픽 삭제
            # kafak_admin_client.delete_topics([topic_key.ANALYZER_TOPIC.format(id)], operation_timeout=1)
        return res
    except Exception as e:
        raise e

def update_analyzer(analyzer_id, description, instance_id, instance_allocate, access, owner_id, users_id):
    try:
        if db_analyzer.get_analyzer_info(analyzer_id=analyzer_id) is None:
            raise Exception("not exist analyzer")
        result = db_analyzer.update_analyzer(id=analyzer_id, description=description, instance_id=instance_id, instance_allocate=instance_allocate, access=access, owner_id=owner_id)

        # user_analyzer update ------------------------------------------------------------------------------------------------------------
        org_users_id = [user['user_id'] for user in db.get_user_analyzer_list(analyzer_id)]
        users_id.append(owner_id)
        del_user = list(set(org_users_id) - set(users_id))
        add_user = list(set(users_id) - set(org_users_id))

        ### Insert User analyzer
        insert_result, message = db.insert_user_analyzer_list(analyzers_id=[analyzer_id]*len(add_user), users_id=add_user)
        if not insert_result:
            print("insert user analyzer error : {}".format(str(message)))
            raise Exception("insert user analyzer error")
        
        ### Delete User analyzer
        delete_result, message = db.delete_user_analyzer(analyzers_id=[analyzer_id]*len(del_user), users_id=del_user)
        if not delete_result:
            raise Exception("delete user analyzer error")

        return result
    except Exception as e:
        traceback.print_exc()
        raise str(e)


# ========================================================================
# Bookmark
# ========================================================================

def add_analyzer_bookmark(analyzer_id, user_id):
    try:
        result, message = db.insert_analyzer_bookmark(analyzer_id=analyzer_id, user_id=user_id)
        if result == True:
            return response(status=1)
        else :
            print("Add analyzer bookmark error : {}".format(message))
            # return response(status=0, message="Add deployment bookmark error : {}".format(message))
            raise
    except CustomErrorList as ce:
        traceback.print_exc()
        return response(status=0, message=ce.message)

def delete_analyzer_bookmark(analyzer_id, user_id):
    result, message = db.delete_analyzer_bookmark(analyzer_id=analyzer_id, user_id=user_id)
    if result == True:
        return response(status=1)
    else :
        print("Delete analyzer bookmark error : {}".format(message))
        # return response(status=0, message="Delete deployment bookmark error : {}".format(message))
        raise

# ========================================================================
# Graph
# ========================================================================
async def create_analyzer_graph(analyzer_id, name, workspace_id, create_user_id, dataset_id, file_path, graph_type, column, description=None):
    "data_path는 full path"
    try:
        # name check, 같은 프로젝트 내에서만 이름 안겹치도록
        result = await db.get_analyzer_graph(name=name, analyzer_id=analyzer_id) 
        if result != None:
            raise("이미 존재하는 graph")

        # DB 추가
        graph_id = await db.insert_analyzer_graph(name=name, workspace_id=workspace_id, create_user_id=create_user_id, description=description,
                                             analyzer_id=analyzer_id, dataset_id=dataset_id, file_path=file_path, graph_type=graph_type, column=column)
        if not graph_id:
            return False

        # helm parameter
        analyzer_info = db.get_analyzer_info(analyzer_id=analyzer_id)
        user_name = db.get_user(user_id=create_user_id).get("name")
        workspace_id = analyzer_info.get("workspace_id")
        workspace_name = analyzer_info.get("workspace_name")
        instance_id = analyzer_info.get("instance_id")
        resource_cpu = analyzer_info.get("cpu_allocate")
        resource_ram = analyzer_info.get("ram_allocate")

        dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
        access = dataset_info.get("access")
        dataset_name = dataset_info.get("name")
        storage_name = dataset_info.get("data_storage_name")
        data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=storage_name,WORKSPACE_NAME=workspace_name,
                                        ACCESS=access, DATASET_NAME=dataset_name, DATA_PATH=file_path)

        pod_name = f"analyzer-{analyzer_id}-{graph_id}"
        helm_name = TYPE.ANALYZER_HELM_NAME.format(analyzer_id=analyzer_id, graph_id=graph_id)

        param = helm_dto.HelmAnalyzer(
            analyzer_id=analyzer_id, graph_id=graph_id, graph_type=TYPE.ANALYZER_GRAPH_TYPE_INT_TO_STR.get(graph_type), data_path=data_path, column=column,
            metadata_instance_id=instance_id, metadata_workspace_id=workspace_id, metadata_workspace_name=workspace_name, metadata_user_name=user_name,
            metadata_pod_name=pod_name, metadata_helm_name=helm_name,
            resources_limits_cpu=resource_cpu, resources_limits_memory=resource_ram, pod_image=settings.ANALYZER_IMAGE
        )

        # kafka 요청
        kafka.produce(topic=topic_key.SCHEDULER_TOPIC, key=param.model_dump_json(), value=None)
        print("kafka", param)
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def delete_analyzer_graph(analyzer_id=None, graph_id_list=None):
    try:
        if graph_id_list is None:
            graph_id_list = [item.get("graph_id") for item in await db.get_analyzer_graph_list(analyzer_id=analyzer_id)]
            delete_all = True
        else:
            delete_all = False

        # 워커 헬름 삭제
        for item in graph_id_list:
            await delete_helm_analyzer(graph_id=item)
        
        # analyzer graph db 삭제
        if delete_all:
            result = await db.delete_analyzer_graph(analyzer_id=analyzer_id)
        else:
            result = await db.delete_analyzer_graph(graph_id_list=graph_id_list)
        return result
    except Exception as e:
        raise e

async def get_analyzer_graph_list(analyzer_id=None):
    result = []
    try:
        graph_list = await db.get_analyzer_graph_list(analyzer_id=analyzer_id)
        for item in graph_list:
            graph_type_int = item.get("graph_type")
            graph_data = item.get("graph_data") 
            graph_data = json.loads(graph_data) if graph_data else None
            
            # dataset
            dataset_id = item.get("dataset_id")
            dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
            dataset_name = dataset_info.get('name')
            data = item.get("file_path")

            # result
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "column" : item.get("column"),
                "type" : TYPE.ANALYZER_GRAPH_TYPE_INT_TO_STR[graph_type_int],
                "dataset" : dataset_name,
                "data" : data,
                "graph" : graph_data,
            })
            if graph_data and item.get('end_datetime') is None: # 결과 도출되면, helm 삭제, end_datetime 추가
                await delete_helm_analyzer(graph_id=item.get("id"))

    except Exception as e:
        traceback.print_exc()
    return result
    
async def delete_helm_analyzer(graph_id):
    try:
        graph_info = await db.get_analyzer_graph(id=graph_id)
        analyzer_id = graph_info.get("analyzer_id")
        workspace_id = graph_info.get("workspace_id")
        helm_name = TYPE.ANALYZER_HELM_NAME.format(analyzer_id=analyzer_id, graph_id=graph_id)
        helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)

        try:
            # 1. DB end datetime 기록
            db.update_end_datetime_analyzer_graph(graph_id=graph_id)

            # # 헬름 조회
            # command = f"helm list -n {helm_namespace} | grep {helm_name}"
            # print(command)
            # subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)

            # 2. 헬름 삭제
            command=f"helm uninstall -n {helm_namespace} {helm_name} "
            print(command)
            subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
        except Exception as e:
            pass
    except Exception as e:
        traceback.print_exc()
        raise e
