import traceback, json, subprocess, os, asyncio, aiofiles, httpx
from huggingface_hub import login, model_info, HfApi, hf_hub_download
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
from datetime import datetime
from requests.exceptions import HTTPError, ConnectionError, Timeout

from utils import topic_key
from utils.settings import JF_KAFKA_DNS
from utils.kube import PodName
from utils import TYPE
from utils import settings
from utils import redis_key
from utils import PATH
from utils import common

from utils.common import is_good_name
from utils.llm_db import db_items as db
from utils.msa_db import db_dataset
from utils.crypt import front_cipher
from utils import llm_deployment
from utils.redis import get_redis_client_async
from utils.workspace_resource import get_workspace_instance_total_info

# TODO status
async def get_playground_list(workspace_id, user_id):
    result = []
    try:
        item_list = await db.get_playground_list(workspace_id=workspace_id)

        # bookmark
        user_playground_bookmark_list = [playground_bookmark["playground_id"]
            for playground_bookmark in await db.get_user_playground_bookmark_list(user_id=user_id)]


        for item in item_list:
            status = await get_playground_status(playground_id=item.get("id"))
            # users
            if item.get("access") == 1:
                users=[]
            else:
                users = await db.get_user_playground_list(playground_id=item.get("id"))
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "description" : item.get("description"),
                "create_datetime" : item.get("create_datetime"),
                "update_datetime" : item.get("create_datetime"),
                "access" : item.get("access"),
                "owner" : db.get_user(user_id=item.get("create_user_id")).get("name"),
                "status" : status.get("status") if status else TYPE.KUBE_POD_STATUS_STOP,
                "bookmark" : 1 if item.get("id") in user_playground_bookmark_list else 0,
                "users":  users,
            })
        result.sort(key=lambda x: x['id'], reverse=True)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_playground_info(playground_id):
    """
    플레이그라운드 목록에서 수정시 쓰는 info
    """
    result = dict()
    try:
        item = await db.get_playground(playground_id=playground_id)
        if item.get("access") == 1:
            users=[]
        else:
            users = await db.get_user_playground_list(playground_id=playground_id)
        result = {
            "id" : item.get("id"),
            "workspace_id" : item.get("workspace_id"),
            "name" : item.get("name"),
            "description" : item.get("description"),
            "owner" : db.get_user(user_id=item.get("create_user_id")).get("name"),
            "access" : item.get("access"),
            "create_datetime" : item.get("create_datetime"),
            "update_datetime" : item.get("update_datetime"),
            "users":  users,
        }
    except:
        traceback.print_exc()
    return result


async def create_playground(workspace_id, name, description, access, user_name=None, owner_id=None, users_id=[]):
    try:
        owner_id = owner_id if owner_id else db.get_user(user_name=user_name).get("id")
        # playground
        res, playground_id = await db.insert_playground(workspace_id=workspace_id, name=name, description=description, create_user_id=owner_id, access=access)
        if not res:
            return False 

        # user_playground
        users_id.append(owner_id)
        playgrounds_id = [playground_id]*len(users_id)
        insert_user_playground_result, message = await db.insert_user_playground_list(
            playgrounds_id=playgrounds_id, users_id=users_id)
    except Exception as e:
        traceback.print_exc()
        return False

async def delete_playground(id_list):
    try:
        # 배포 삭제
        for playground_id in id_list:
            playground_info = await db.get_playground(playground_id=playground_id)
            if playground_info is None:
                continue
            playground_deployment_info = playground_info.get("deployment")
            if playground_deployment_info is None:
                continue
            playground_deployment_info = json.loads(playground_deployment_info)
            playground_deployment_id = playground_deployment_info.get("deployment_playground_id")
            playground_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            playground_reranker_id = playground_deployment_info.get("deployment_reranker_id")
            deployment_ids = [x for x in [playground_deployment_id, playground_embedding_id, playground_reranker_id] if x]
            db.delete_deployments(deployment_ids=deployment_ids)
        
        # playground 삭제        
        res = await db.delete_playground(id_list=id_list)
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def update_playground_description(playground_id, description):
    try:
        res = await db.update_playground(playground_id=playground_id, description=description)
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def get_playground_status(playground_id):
    result = {"status" : "stop", "init_deployment" : False}
    """
    init_deployment
        False일 경우, 초기 배포 시작 안한 상태
        True일 경우, 초기 배포 이미 한 상태
    """
    try:
        if playground_id == 192:
            return result
        # playground deployment info
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            try:
                print(playground_id)
            except:
                pass
            raise Exception("Not Exist Playground")
        
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
            return result
        playground_deployment_info = json.loads(playground_deployment_info)

        # deployment init
        # deployment_init = playground_deployment_info.get("deployment_init")
        deployment_init = True if playground_deployment_info.get("deployment_playground_id") is not None else None
        result["init_deployment"] = True if deployment_init == True else False

        # deployment status - 중지 (실행안한 상태)
        deployment_id = playground_deployment_info.get("deployment_playground_id")
        if deployment_id is None:
            return result

        # deployment_id
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        deployment_run = playground_deployment_info.get("deployment_run")
        deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id") if deployment_run.get("run_embedding") else None
        deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id") if deployment_run.get("run_reranker") else None

        # installing, stop -> deployment_playground_id, DB로 바로 판단
        playground_worker_list = db.get_deployment_worker_list(deployment_id=deployment_playground_id, running=True)
        if len(playground_worker_list) == 0:
            result["status"] = TYPE.KUBE_POD_STATUS_STOP
            return result
        elif len(playground_worker_list) > 0:
            result["status"] = TYPE.KUBE_POD_STATUS_PENDING
        
        # running -> redis 사용
        redis_client = await get_redis_client_async()
        redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, playground_info.get("workspace_id"))
        redis_pod_list = json.loads(redis_workspace_pod_status) if redis_workspace_pod_status else dict()
        deployment_worker_redis_list = redis_pod_list.get('deployment', dict())

        # running playground -> redis 아무것도 없으면 종료(stop or pending인 경우)
        playground_redis_list = deployment_worker_redis_list.get(str(deployment_playground_id))
        if playground_redis_list is None or len(playground_redis_list) == 0:
            return result
        
        # running rag 
        running_status = True 
        for item_id in [deployment_playground_id, deployment_embedding_id, deployment_reranker_id]:
            if item_id is None:
                continue
            print(item_id)
            worker_list = deployment_worker_redis_list.get(str(item_id))

            print(worker_list)
            if worker_list and len(worker_list) > 0:
                status = list(worker_list.values())[0]['status']
                if status != TYPE.KUBE_POD_STATUS_RUNNING:
                    running_status = False
            else:
                running_status = False

        # 여기까지 넘어온경우 Installing or Rudnning
        result['status'] = TYPE.KUBE_POD_STATUS_RUNNING if running_status else TYPE.KUBE_POD_STATUS_INSTALLING

        ### ===== 최초 init deployment 업데이트 =====
        if result["status"] == TYPE.KUBE_POD_STATUS_INSTALLING or result["status"] == "running" and (deployment_init == None or deployment_init == False):
            result["init_deployment"] = True
            playground_deployment_info["deployment_init"] = True
            playground_deployment_info = json.dumps(playground_deployment_info)
            await db.update_playground(playground_id=playground_id, deployment=playground_deployment_info)

        return result
    except:
        traceback.print_exc()
        return result

async def update_playground(playground_id, description, access, owner_id, users_id):
    try:
        res = await db.update_playground(
            playground_id=playground_id, description=description, access=access, create_user_id=owner_id
        )

        if not res:
            raise
        
        # user_playground update --------------------------------------------------------------------------------------------------------
        # org_users_id = [user['user_id'] for user in db.(playground_id)]
        org_users_id = [user['user_id'] for user in await db.get_user_playground_list(playground_id)]

        users_id.append(owner_id)
        del_user = list(set(org_users_id) - set(users_id))
        add_user = list(set(users_id) - set(org_users_id))

        ### Insert User playground
        insert_result, message = await db.insert_user_playground_list(playgrounds_id=[playground_id]*len(add_user), users_id=add_user)
        if not insert_result:
            print("insert user playground error : {}".format(str(message)))
            raise 
        
        ### Delete User playground
        delete_result, message = await db.delete_user_playground(playgrounds_id=[playground_id]*len(del_user), users_id=del_user)
        if not delete_result:
            print("delete user playground error : {}".format(str(message)))
            raise 

        return True
    except:
        traceback.print_exc()
        return False



# bookmark ===================================================================================

async def add_playground_bookmark(playground_id, user_id):
    try:
        res = await db.insert_playground_bookmark(playground_id=playground_id, user_id=user_id)
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def delete_playground_bookmark(playground_id, user_id):
    try:
        res = await db.delete_playground_bookmark(playground_id=playground_id, user_id=user_id)
        return True if res else False
    except:
        traceback.print_exc()
        return False

# 상세페이지 ===================================================================================

async def get_playground(playground_id):
    result = {"info" : None, "info_instance" :None, "info_request" :{"url" : None, "method" : None, "format" : None},
              "model" : None, "model_parameter" :None}
    try:
        item = await db.get_playground(playground_id=playground_id)
        deployment = item.get("deployment")
        model = item.get("model")
        model_parameter = item.get("model_parameter")

        # INFO
        result["info"] = dict()
        result['info']['id'] = item["id"]
        result['info']['name'] = item["name"]
        result['info']['access'] = item.get("access")
        result['info']['description'] = item["description"]
        result['info']['create_datetime'] = item["create_datetime"]
        result['info']['update_datetime'] = item["update_datetime"]
        result['info']['owner'] = db.get_user(user_id=item.get("create_user_id")).get("name")
        result['info']['accelerator'] = bool(item.get("accelerator", False))

        # users
        if item.get("access") == 1:
            users=[]
        else:
            users=[item.get("user_name") for item in await db.get_user_playground_list(playground_id=item.get("id"))]
        result['info']['users'] = users

        # INFO - instance
        try:
            if deployment:
                deployment_playground = json.loads(deployment)
                deployment_playground_id = deployment_playground.get("deployment_playground_id")
                deployment_embedding_id = deployment_playground.get("deployment_embedding_id")
                deployment_reranker_id = deployment_playground.get("deployment_reranker_id")

                result["info_instance"] = dict()
                result["info_request"] = dict()

                if deployment_playground_id:
                    deployment_info = db.get_deployment(deployment_id=deployment_playground_id)
                    api_path = deployment_info.get("api_path")
                    url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}/{api_path}"
                    if settings.EXTERNAL_HOST_PORT != 80 or settings.EXTERNAL_HOST_PORT != 443:
                        url = f"{url}:{settings.EXTERNAL_HOST_PORT}/{api_path}"

                    # playground request
                    # playground 배포는 따로 deployment_data_form을 저장하지 않음, 현재 playground 코드는 고정이므로 데이터폼도 고정

                    result["info_request"]= {
                        "url" : url,
                        "method" : "POST",
                        "format" : [{
                            "test_type": "dataset",
                            "session_id": "Optional[int]",
                            "test_dataset_id": "int",
                            "test_dataset_filename": "str"
                        },
                        {
                            "test_type": "question",
                            "session_id": "Optional[int]",
                            "test_question": "str"
                        }]
                    }
                    instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                            instance_allocate=deployment_info.get("instance_allocate"),
                                                                            resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                            )
                    # playground instance
                    result["info_instance"]["model"] = dict()
                    result["info_instance"]["model"] = instance_info
                else:
                    # playground instance
                    result["info_instance"]["model"] = None

                # ==============================================================================================================
                if settings.GITC_USED:
                    deployment_run = deployment_playground.get("deployment_run")
                    if deployment_run:
                        run_embedding = deployment_run.get("run_embedding")
                        run_reranker = deployment_run.get("run_reranker")
                    else:
                        run_embedding = None
                        run_reranker = None

                    if run_embedding and deployment_embedding_id:
                        deployment_info = db.get_deployment(deployment_id=deployment_embedding_id)
                        instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                                instance_allocate=deployment_info.get("instance_allocate"),
                                                                                resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                                )
                        result["info_instance"]["embedding"] = dict()
                        result["info_instance"]["embedding"] = instance_info
                    else:
                        result["info_instance"]["embedding"] = None
                    if run_reranker and deployment_reranker_id:
                        deployment_info = db.get_deployment(deployment_id=deployment_reranker_id)
                        instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                                instance_allocate=deployment_info.get("instance_allocate"),
                                                                                resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                                )
                        result["info_instance"]["reranker"] = instance_info
                    else:
                        result["info_instance"]["reranker"] = None
                # ==============================================================================================================
                
                result["info_instance"]["immediately_status"] = True # TODO 
        except:
            traceback.print_exc()
            pass

        # MODEL - Parameter
        try:
            if model_parameter:
                model_parameter = json.loads(model_parameter)
                result['model_parameter'] = dict()
                result['model_parameter']['temperature'] = model_parameter.get("temperature")
                result['model_parameter']['top_p'] = model_parameter.get("top_p")
                result['model_parameter']['top_k'] = model_parameter.get("top_k")
                result['model_parameter']['repetition_penalty'] = model_parameter.get("repetition_penalty")
                result['model_parameter']['max_new_tokens'] = model_parameter.get("max_new_tokens")
            else:
                result['model_parameter'] = None
        except:
            pass

        # MODEL
        try:
            if model:
                model = json.loads(model)
                result['model'] = dict()
                result['model']["model_type"] = model.get("model_type")
                result['model']["model_hf_id"] = model.get("model_huggingface_id")
                
                db_commit_info = await db.get_commit_model(commit_id=model.get("model_allm_commit_id"))
                result['model']["model_allm_name"] = db_commit_info.get("model_name") if db_commit_info else None
                result['model']["model_allm_id"] = db_commit_info.get("model_id") if db_commit_info else None
                result['model']["model_allm_commit_name"] = db_commit_info.get("name") if db_commit_info else None
                result['model']["model_allm_commit_id"] = db_commit_info.get("id") if db_commit_info else None

                model_info = model.get("model_info", {}) 
                result['model']["commit"] = model_info.get("commit")
                result['model']["access"] = model_info.get("access")
                result['model']["create_datetime"] = model_info.get("create_datetime")
                result['model']["update_datetime"] = model_info.get("update_datetime")
                result['model']["description"] = model_info.get("description")
                result['model']["url"] = model_info.get("url")
            else:
                result['model'] = None
        except:
            pass
        

        # GITC의 경우 사용하는 RAG PROMPT
        if settings.GITC_USED:
            rag = item.get("rag")
            prompt = item.get("prompt")
            tmp = get_rag_prompt_info(rag=rag, prompt=prompt)
            result["rag"] = tmp.get("rag")
            result["prompt"] = tmp.get("prompt")

    except Exception as e:
        traceback.print_exc()
    return result



async def get_rag_prompt_info(rag, prompt):
    result = {"rag" : None, "prompt" : None}
    try:
        # RAG   
        try:
            rag = json.loads(rag) if rag else None
            if rag and rag.get("rag_id"):
                rag_id = rag.get("rag_id")

                result['rag'] = dict()
                result["rag"]['id'] = rag_id # 플레이그라운드 세팅 값
                result["rag"]['chunk_max'] = rag.get("rag_chunk_max") # 플레이그라운드 세팅 값
                
                # rag db
                rag_info = await db.get_rag(rag_id=rag_id)
                result["rag"]['name'] = rag_info.get("name")
                result["rag"]['chunk_len'] = rag_info.get("chunk_len")
                result["rag"]['embedding_huggingface_model_id'] = rag_info.get("embedding_huggingface_model_id")
                result["rag"]['reranker_huggingface_model_id'] = rag_info.get("reranker_huggingface_model_id")

                # rag docs db
                total_size = 0
                total_count = 0
                doc_list = []
                for doc in await db.get_rag_doc_list(rag_id=rag_id):
                    doc_list = [{"name" : doc.get("doc_name"), "id" : doc.get("doc_id")}]
                    total_count += 1
                    total_size += doc.get("size", 0)
                result["rag"]['rag_doc_list'] = doc_list
                result["rag"]['docs_total_count'] = total_count
                result["rag"]['docs_total_size'] = total_size
            else:
                result["rag"] = None
        except:
            pass

        # PROMPT
        try:
            prompt = json.loads(prompt)
            if prompt and prompt.get("prompt_id"):
                result['prompt'] = dict()
                result['prompt']['id'] = prompt.get("prompt_id")
                result['prompt']['name'] = prompt.get("prompt_name")
                result['prompt']['commit_name'] = prompt.get("prompt_commit_name")
                result['prompt']['system_message'] = prompt.get("system_message")
                result['prompt']['user_message'] = prompt.get("user_message")
            else:
                result['prompt'] = None
        except:
            pass
    except Exception as e:
        traceback.print_exc()
    return result

async def update_playground_options(playground_id, is_rag, is_prompt, accelerator,
                model_type, model_huggingface_id, model_huggingface_token, model_allm_id, model_allm_commit_id, model_info,
                model_temperature, model_top_p, model_top_k, model_repetition_penalty, model_max_new_tokens, 
                rag_id, rag_chunk_max, prompt_id, prompt_name, prompt_commit_name, prompt_system_message, prompt_user_message
            ):
    try:
        # playground
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("check playground id")

        # model
        model = json.dumps({"model_type": model_type, "model_huggingface_id" : model_huggingface_id, "model_huggingface_token" : model_huggingface_token,
                            "model_allm_id" : model_allm_id, "model_allm_commit_id" : model_allm_commit_id,
                            "model_info": model_info})
        model_parameter = json.dumps({"temperature": model_temperature, "top_p" : model_top_p, "top_k" : model_top_k, "repetition_penalty" : model_repetition_penalty, "max_new_tokens" : model_max_new_tokens})
        
        # rag
        rag = json.dumps({"rag_chunk_max" : rag_chunk_max, "rag_id" : rag_id})
        is_embedding = False
        is_reranker = False
        if rag_id != None:
            rag_info = await db.get_rag(rag_id=rag_id)
            test_embedding_run = rag_info.get("test_embedding_run")
            is_embedding = True if test_embedding_run else False
            test_reranker_run = rag_info.get("test_reranker_run")
            is_reranker = True if test_reranker_run else False

        # prompt
        prompt = json.dumps({"prompt_id" : prompt_id, "prompt_name" : prompt_name, "prompt_commit_name" : prompt_commit_name, "system_message" : prompt_system_message, "user_message" : prompt_user_message})

        # deployment_run: 무조건 들어감
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is not None:
            playground_deployment_info = json.loads(playground_deployment_info) # 기존정보 유지
            deployment = playground_deployment_info
        else:
            deployment = dict()
        deployment["deployment_run"] = {"run_rag" : is_rag, "run_embedding" : is_embedding,  "run_reranker" : is_reranker,  "run_prompt" : is_prompt}
        deployment = json.dumps(deployment)

        res = await db.update_playground(playground_id=playground_id, deployment=deployment, model=model, model_parameter=model_parameter, rag=rag,  prompt=prompt, accelerator=accelerator)
        return True if res else False
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

async def get_playground_instance_options(playground_id):
    result = []
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        workspace_id = playground_info.get("workspace_id")
        result = db.get_workspace_instance_list(workspace_id=workspace_id)
    except:
        traceback.print_exc()
    return result

async def get_playground_deployment_monitoring(playground_id):
    result = {"playground_id" : None, "embedding_id" : None, "reranker_id" : None}
    try:
        # playground -> playground_deployment
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
            return result
        
        # init deployment
        playground_deployment_info = json.loads(playground_deployment_info)
        playground_id = playground_deployment_info.get("deployment_playground_id")
        embedding_id = playground_deployment_info.get("deployment_embedding_id")
        reranker_id = playground_deployment_info.get("deployment_reranker_id")
        
        result["playground_id"] = playground_id
        result["embedding_id"] = embedding_id
        result["reranker_id"] = reranker_id
        return result
    except:
        traceback.print_exc()
        return result

# model ===================================================================================
async def get_hugging_face_model(model_name : str = None, huggingface_token : str = None, private : int = 0) -> List[str]:
    """hf_token이 들어오면 private model
    """
    result = []
    try:
        api = HfApi()
        if private:
            huggingface_token = front_cipher.decrypt(huggingface_token)
            models = api.list_models(limit=10, task="text-generation", library="transformers", model_name=model_name, expand=["private"], token=huggingface_token)
        else:
            models = api.list_models(limit=10, task="text-generation", library="transformers", model_name=model_name)

        for model_info in models: 
            # model_info = api.model_info(model.id) # list_models 에서 가져온 정보로 조회가 안되 model_info사용 (author, last_modified...)
            result.append({
                "id" : model_info.id,
                "create_datetime" : model_info.created_at.strftime("%Y-%m-%d %H:%M:%S") if model_info.created_at else None,
                "update_datetime" : model_info.last_modified.strftime("%Y-%m-%d %H:%M:%S") if model_info.last_modified else None,
                "access" : not model_info.private,
                "owner" : model_info.author,
                "commit" : model_info.sha,
                "url" : f"https://huggingface.co/{model_info.id}",
                "description" : None
            })
    except:
        traceback.print_exc()
    return result

async def get_playground_model_list(workspace_id, model_name, is_mine, user_name):
    result = {"hf_model_list" : [], "allm_model_list" : []}
    try:
        try:
            hf_model_list = await get_hugging_face_model(huggingface_token=None, model_name=model_name)
            result["hf_model_list"] = hf_model_list
        except:
            pass
        try:
            # ALLM MODEL
            allm_model_list = await db.get_models_option(workspace_id=workspace_id, model_name=model_name)
            for item in allm_model_list:
                
                if is_mine and item.get("create_user_name") != user_name:
                    continue
                
                result["allm_model_list"].append({
                    "id" : item.get("id"),
                    "name" : item.get("name"),
                    "owner" : item.get("create_user_name"),
                })
        except:
            pass
    except:
        traceback.print_exc()
    return result

async def get_playground_model_commit_list(model_id, commit_name, is_mine, user_name):
    result = []
    try:
        print(commit_name)
        model_commit_list = await db.get_commit_models_option(model_id=model_id, commit_name=commit_name)
        for item in model_commit_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            result.append({
                "model_name" : item.get("model_name"),
                "model_commit_name" : item.get("name"),
                "model_commit_id" : item.get("id"),
                "owner" : item.get("create_user_name"),
                "create_datetime" : item.get("create_datetime"),
                "update_datetime" : item.get("update_datetime"),
                "access" : item.get("access"),
                "description" : item.get("description"),
                "url" : None,
            })
    except:
        traceback.print_exc()
    return result

async def check_model_access( token: str, model_id: str = None) -> bool:
    """
    해당 Hugging Face 모델에 대해 주어진 토큰으로 접근 권한이 있는지 확인하는 함수 (비동기 버전).

    Parameters:
    model_id (str): 접근하려는 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.

    Returns:
    bool: 접근 권한이 있으면 True, 없으면 False.
    """
    loop = asyncio.get_event_loop()
    # token = front_cipher.decrypt(token)
    try:
        # Hugging Face API로 로그인 (토큰 기반)
        await loop.run_in_executor(None, login, token)
        if model_id is not None:
            # 모델 정보 요청 (권한 확인)
            await loop.run_in_executor(None, model_info, model_id)
        return True  # 접근 권한이 있음

    except HTTPError as e:
        # 모델에 접근할 권한이 없거나 존재하지 않음
        print(f"Error: Cannot access the model '{model_id}' with the provided token.")
        print(f"Details: {e}")
        return False

    except Exception as e:
        # 기타 오류
        print(f"An unexpected error occurred while checking access: {e}")
        return False

# rag ===================================================================================
async def get_playground_rag_list(workspace_id, rag_name, is_mine, user_name):
    result = []
    try:
        rag_list = await db.get_rag_list(workspace_id=workspace_id, like_rag_name=rag_name)
        for item in rag_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            if item.get("embedding_huggingface_model_id") is None:
                continue

            # doc list
            doc_list = [{"name" : doc.get("doc_name"), "id" : doc.get("doc_id")} for doc in await db.get_rag_doc_list(rag_id=item.get("id"))]
 
            # result
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name"),
                "chunk_len" : item.get("chunk_len"),
                "docs_total_count" : item.get("docs_total_count"),
                "docs_total_size" : item.get("docs_total_size"),
                "doc_list" : doc_list,
                "embedding_huggingface_model_id" : item.get("embedding_huggingface_model_id"),
                "reranker_huggingface_model_id" : item.get("reranker_huggingface_model_id"),
            })
    except:
        traceback.print_exc()
    return result

# prompt ===================================================================================
async def get_playground_prompt_list(workspace_id, prompt_name, is_mine, user_name):
    result = []
    try:
        prompt_list = await db.get_prompt_list(workspace_id=workspace_id, like_prompt_name=prompt_name)
        prompt_list = await db.get_prompt_list()

        for item in prompt_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name")
            })
    except:
        traceback.print_exc()
    return result

async def get_playground_prompt_commit_list(prompt_id, commit_name, is_mine, user_name):
    result = []
    try:
        prompt_commit_list = await db.get_commit_prompt_list(prompt_id=prompt_id, like_commit_name=commit_name)
        for item in prompt_commit_list:

            if is_mine and item.get("create_user_name") != user_name:
                continue

            result.append({
                "prompt_id" : prompt_id,
                "prompt_commit_id" : item.get("commit_id"),
                "prompt_name" : item.get("prompt_name"),
                "prompt_commit_name" : item.get("commit_name"),
                "system_message" : item.get("system_message"),
                "user_message" : item.get("user_message"),
                "owner" : item.get("create_user_name")
            })
    except:
        traceback.print_exc()
    return result


# 실행관련 ===================================================================================
# API 요청
async def start_playground(user_name, playground_id, 
            model_instance_id, model_instance_count, model_gpu_count,
            embedding_instance_id, embedding_instance_count, embedding_gpu_count,
            reranker_instance_id, reranker_instance_count, reranker_gpu_count,
            restart=False
        ):
    """
    1. playground 실행, 2. deployment 생성
    TODO 현재는 플레이그라운드 1개만 만든다고 진행 (model, model + prompt)
    """
    try:
        # =============================================================================
        # 재식작일 경우, 중단
        # =============================================================================
        if restart:
            await stop_playground(playground_id=playground_id)
        # =============================================================================
        # info
        # =============================================================================
        user_id = db.get_user(user_name=user_name).get("id")
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground_id")

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info:
            playground_deployment_info = json.loads(playground_deployment_info)
            playground_deployment_run = playground_deployment_info.get("deployment_run") # 이 값은 플레이그라운드 저장시 DB에 저장됨
            deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
            deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")
        else:
            # deployment info가 없다는건, deployment_run이 없다는 의미 -> 세팅이 안되어 있다
            # deployment_run은 update_playground에서 무조건 세팅함
            raise Exception("Not set up playground deployment")

        # =============================================================================
        # 자원 설정
        # =============================================================================
        # playground 의 자원은 모델의 자원을 사용
        playground_instance_id = model_instance_id
        playground_instance_count = model_instance_count
        playground_gpu_count = model_gpu_count
        
        # =============================================================================
        # 배포 생성
        # =============================================================================
        run_embedding, run_reranker =  False, False
        # 플레이그라운드 배포
        if deployment_playground_id:
            # 재배포
            await update_deployment(deployment_id=deployment_playground_id, instance_id=playground_instance_id, instance_count=playground_instance_count, gpu_count=playground_gpu_count)
        else:
            # 초기배포
            deployment_playground_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="playground",
                                                               instance_id=playground_instance_id, instance_count=playground_instance_count, gpu_count=playground_gpu_count)

        # rag 정보
        rag_id = None
        if (embedding_instance_id and embedding_instance_count > 0) or (reranker_instance_id and reranker_instance_count > 0):
            playground_rag_info = playground_info.get("rag")
            if playground_rag_info:
                rag_info = json.loads(playground_rag_info)
                rag_id = rag_info.get("rag_id")
            else:
                raise Exception("Not Exist Playground RAG")

        # rag embedding 배포
        if embedding_instance_id and embedding_instance_count > 0:
            run_embedding = True
            if deployment_embedding_id:
                await update_deployment(deployment_id=deployment_embedding_id, instance_id=embedding_instance_id, instance_count=embedding_instance_count, gpu_count=embedding_gpu_count)
            else:
                deployment_embedding_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="embedding",
                                                                  instance_id=embedding_instance_id, instance_count=embedding_instance_count, gpu_count=embedding_gpu_count, rag_id=rag_id)    

        # rag reranker 배포
        if reranker_instance_id and reranker_instance_count > 0:
            run_reranker = True
            if deployment_reranker_id:
                await update_deployment(deployment_id=deployment_reranker_id, instance_id=reranker_instance_id, instance_count=reranker_instance_count, gpu_count=reranker_gpu_count)
            else:
                deployment_reranker_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="reranker",
                                                                 instance_id=reranker_instance_id, instance_count=reranker_instance_count, gpu_count=reranker_gpu_count, rag_id=rag_id)    

        # 배포 정보 업데이트
        playground_deployment= json.dumps({"deployment_playground_id" : deployment_playground_id, "deployment_embedding_id" : deployment_embedding_id, "deployment_reranker_id" : deployment_reranker_id,
                                           "deployment_run" : playground_deployment_run}) 
        await db.update_playground(playground_id=playground_id, deployment=playground_deployment)

        # =============================================================================
        # 워커 생성
        # =============================================================================
        await run_deployment_playground(playground_id=playground_id, run_embedding=run_embedding, run_reranker=run_reranker)
        return True
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

# 배포 생성
async def create_deployment(playground_id, user_id, deployment_type, instance_id, instance_count, gpu_count, rag_id=None):
    try:
        print("create_deployment", playground_id, user_id, deployment_type, instance_id, instance_count, gpu_count, rag_id)
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        
        workspace_id = playground_info.get("workspace_id")
        workspace_name = db.get_workspace(workspace_id=workspace_id)["name"]

        instance_info = db.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")

        # instance의 실제 cpu/ram allocate 값을 사용
        deployment_cpu_limit = instance_info.get('cpu_allocate', 0)
        deployment_ram_limit = instance_info.get('ram_allocate', 0)
        
        image_real_name=f"{settings.DOCKER_REGISTRY_URL}{settings.DEPLOYMENT_LLM_IMAGE}" ### LLM 배포 이미지는 1. main.py에서 image db에 넣음. 2. image build: /jp/libs/fb_image/llm
        image_id = db.get_image_id_by_real_name(real_name=image_real_name).get('id')

        if deployment_type == "playground":
            deployment_name = f"playground-{playground_id}"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_MODEL)
        elif deployment_type == "embedding":
            deployment_name = f"playground-{playground_id}-rag-{rag_id}-embedding"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_RAG_EMBEDDING)
        elif deployment_type == "reranker":
            deployment_name = f"playground-{playground_id}-rag-{rag_id}-reranker"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_RAG_RERANKER)
        
        # check: 이름 유효성 확인
        if is_good_name(name=deployment_name) == False:
            raise Exception("유효하지 않은 이름입니다.")
        # check: 이름 존재 확인                
        if db.check_workspace_deployment_name(deployment_name=deployment_name, workspace_id=workspace_id):
            raise Exception("이미 존재하는 이름입니다.")
        
        # api 주소 생성
        default_api_path = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type=TYPE.DEPLOYMENT_TYPE).get_base_pod_name()

        # 배포 생성
        insert_deployment_result = db.insert_deployment_llm(workspace_id=workspace_id, user_id=user_id, name=deployment_name, access=1, image_id=image_id,
            instance_type=instance_type, instance_id=instance_id, instance_allocate=instance_count, gpu_per_worker=gpu_count,
            deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit, api_path=default_api_path, llm=llm_type)
        
        # 배포 ID
        if not insert_deployment_result["result"]:
            print("Create Deployment DB Insert Error: {}".format(insert_deployment_result["message"]))
            raise "Create Deployment DB Insert Error"
        deployment_id = insert_deployment_result["id"]
        return deployment_id
    except Exception as e:
        # traceback.print_exc()
        raise Exception(e)

# 배포 업데이트
async def update_deployment(deployment_id, instance_id, instance_count, gpu_count):
    try:
        instance_info = db.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")
        db.update_deployment(deployment_id=deployment_id, instance_id=instance_id, instance_type=instance_type, instance_allocate=instance_count, gpu_per_worker=gpu_count)
    except Exception as e:
        traceback.print_exc()
        raise(str(e))

# 워커 실행
async def run_deployment_playground(playground_id, run_embedding=False, run_reranker=False):
    """1. deployment 워커 실행, playground pod 만 실행시킴, rag pod는 아님"""
    try:
        playground_info = await db.get_playground(playground_id=playground_id)

        # playground deployment
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None:
            raise Exception("배포 정보가 없습니다.")
        playground_deployment_info = json.loads(playground_deployment_info)
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
        deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")

        # playground rag
        playground_rag_info = playground_info.get("rag")
        if playground_rag_info is not None:
            playground_rag_info = json.loads(playground_rag_info)
            rag_id = playground_rag_info.get("rag_id")
            rag_chunk_max = playground_rag_info.get("rag_chunk_max")
        else:
            rag_id = None
            rag_chunk_max = None

        # run worker - playground
        await llm_deployment.run_worker(deployment_id=deployment_playground_id, llm_type="playground", llm_id=playground_id,
                                        playground_run_rag_reranker=run_reranker)

        # run worker - embedding
        if run_embedding:
            await llm_deployment.run_worker(deployment_id=deployment_embedding_id, llm_type=TYPE.PLAYGROUND_RAG_EMBEDDING, llm_id=rag_id)

        # run worker - reranker
        if run_reranker:
            # rag_embedding_run: rag의 경우 embedding을 기다려야하지만 playground에서 굳이 기다릴 필요가 있을까?
            rag_embedding_run = 1 if run_embedding else 0
            await llm_deployment.run_worker(deployment_id=deployment_reranker_id, llm_type=TYPE.PLAYGROUND_RAG_RERANKER, llm_id=rag_id, rag_embedding_run=rag_embedding_run)

        # ===========================================================================================
        # RESULT
        # ===========================================================================================
        print("worker run : ", playground_deployment_info)
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

# 중단
async def stop_playground(playground_id):
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            return True
        # workspace_id = playground_info.get("workspace_id")

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is not None:
            playground_deployment_info = json.loads(playground_deployment_info)
            deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
            deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")


            if deployment_embedding_id or deployment_reranker_id:
                playground_rag_info = playground_info.get("rag")
                if playground_rag_info is not None:
                    playground_rag_info = json.loads(playground_rag_info)
                    rag_id = playground_rag_info.get("rag_id")

            if deployment_playground_id is not None:
                await llm_deployment.uninstall_worker(deployment_id=deployment_playground_id, llm_type="playground", llm_id=playground_id)
            if deployment_embedding_id is not None:
                await llm_deployment.uninstall_worker(deployment_id=deployment_embedding_id, llm_type=TYPE.PLAYGROUND_RAG_EMBEDDING, llm_id=rag_id)
            if deployment_reranker_id is not None:
                print(deployment_reranker_id, rag_id)
                await llm_deployment.uninstall_worker(deployment_id=deployment_reranker_id, llm_type=TYPE.PLAYGROUND_RAG_RERANKER, llm_id=rag_id) 

            # DB: playground test 기록 삭제
            await db.delete_playground_test(playground_id)
        return True
    except:
        traceback.print_exc()
        return False

# 테스트 ===================================================================================
async def get_test_options(playground_id):
    result = {"dataset_list" : [], "test_url" : None}
    try:
        playground_info = await db.get_playground_url(playground_id=playground_id) # URL 까지 가져옴
        if playground_info is None:
            raise Exception("Not Exist Playground")
        workspace_id = playground_info.get("workspace_id")
        base_api_path = playground_info.get("api_path")

        # dataset_list
        result["dataset_list"] = await db.get_datasets(workspace_id=workspace_id)

        if settings.EXTERNAL_HOST_REDIRECT:
            api_address = settings.EXTERNAL_HOST
        else:
            api_address = f"{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}"
        result["test_url"] = f"{settings.INGRESS_PROTOCOL}://{api_address}/deployment/{base_api_path}"
    except Exception as e:
        traceback.print_exc()
    return result

async def get_test_dataset_options(dataset_id, user_name):
    result = []
    try:
        dataset_info = db_dataset.get_dataset(dataset_id=dataset_id)
        workspace_id = dataset_info.get("workspace_id")
        workspace_info = db.get_workspace(workspace_id=workspace_id)

        user_id = db.get_user(user_name=user_name).get("id")
        user_uuid = user_id + settings.USER_UUID_SET
        
        storage = PATH.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"])
        directory = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"])
        pod_playground_dataset_path = "/datasets" + directory.replace(storage, '')
        
        print(directory)
        # Check if directory exists
        if not os.path.exists(directory):
            return result

        # Asynchronously find files and folders
        for item in Path(directory).rglob('*'):
            item_metadata = item.stat()
            item_uuid = item_metadata.st_uid
            owner = common.get_own_user(uuid=item_uuid) if item_uuid != 0 else "admin"

            if item.is_dir():
                continue
            
            if item.is_file() and item.suffix not in ['.arrow', '.csv', '.txt', '.json', '.jsonl', '.zst']:
                continue

            # result.append({
            #     # playground pod은 테스트 전에 실행하므로, 어떤 경로를 데이터셋을 쓸지 모르기때문에, access 경로부터 알려준다.
            #     "file_path": pod_playground_dataset_path + str(item.relative_to(directory)),
            #     "is_owner": user_name, # item_uuid == user_uuid,
            #     "is_folder": True if item.is_dir() else False
            # })
            
            dataset_name_str = str(item)
            try:
                input_list = []
                try:
                    async with aiofiles.open(dataset_name_str, mode='r', encoding='utf-8') as f:
                        lines = await f.readlines()
                        for line in lines:
                            input_list.append(line.strip())
                except:
                    traceback.print_exc()
                    print("파일 내용 읽기 실패")

                result.append({
                    "owner": owner, # item_uuid == user_uuid,
                    "file_name" : dataset_name_str.replace(directory, "").lstrip("/"), # 파일 이름
                    "input_list" : input_list, # 파일 내용
                })
            except:
                traceback.print_exc()
                pass
    except Exception as e:
        traceback.print_exc()
    return result

# async def get_playground_deployment_monitoring(playground_id):
#     result = {"playground_id" : None, "embedding_id" : None, "reranker_id" : None}
#     try:
#         # playground -> playground_deployment
#         playground_info = await db.get_playground(playground_id=playground_id)
#         if playground_info is None:
#             raise Exception("Not Exist Playground")
        
#         playground_deployment_info = playground_info.get("deployment")
#         if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
#             return result
        
#         # init deployment
#         playground_deployment_info = json.loads(playground_deployment_info)
#         playground_id = playground_deployment_info.get("deployment_playground_id")
#         embedding_id = playground_deployment_info.get("deployment_embedding_id")
#         reranker_id = playground_deployment_info.get("deployment_reranker_id")
        
#         result["playground_id"] = playground_id
#         result["embedding_id"] = embedding_id
#         result["reranker_id"] = reranker_id
#         return result
#     except:
#         traceback.print_exc()
#         return result

async def get_test_log(playground_id):
    """
    플레이그라운드 종료하면 로그 삭제됨
    """
    result = []
    try:
        test_log_list = await db.get_test_log_list(playground_id=playground_id)
        for item in test_log_list:
            # print(item.get("end_datetime") - item.get("start_datetime"))
            start_datetime = item.get("start_datetime")
            end_datetime = item.get("end_datetime")
            result.append({
                "type" : item.get("type"),
                "input" : item.get("input"),
                "output" : item.get("output"),
                "model" : item.get("model"),
                "rag" : item.get("rag"),
                "prompt" : item.get("prompt"),
                "start_datatime" : start_datetime.strftime("%Y-%m-%d %H:%M:%S"),    
                "end_datatime" : end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "response_time" : (end_datetime - start_datetime).total_seconds(),    
            })
    except:
        traceback.print_exc()
    return result

async def get_test_download(playground_id):
    result = [["type", "input", "output", "model", "rag", "prompt", "start_datetime", "end_datetime", "response_time"]]
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        playground_name = playground_info.get("name")
        
        test_log_list = await db.get_test_log_list(playground_id=playground_id)
        for item in test_log_list:
            start_datetime = item.get("start_datetime")
            end_datetime = item.get("end_datetime")
            result.append([item.get("type"), item.get("input"), item.get("output"), item.get("model"), item.get("rag"), item.get("prompt"), 
                           item.get("start_datetime").strftime("%Y-%m-%d %H:%M:%S"), item.get("end_datetime").strftime("%Y-%m-%d %H:%M:%S"),
                           (end_datetime - start_datetime).total_seconds()])
        return common.csv_response_generator(data_list=result, filename=f"playground_{playground_name}_log")
    except:
        traceback.print_exc()
        return None

async def playground_test(playground_id, test_type, test_dataset_id, test_dataset_filename, test_question, session_id=None, network_load=0):
    """
    network_load: 없음 0, 저 1, 중 2, 고3
    """
    result = None
    message = None
    try:
        # playground
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None:
            raise Exception("Not Exist Playground Deployment")
        playground_deployment_info = json.loads(playground_deployment_info)
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        
        # 테스트 url
        deployment_info = db.get_deployment(deployment_id=deployment_playground_id)
        api_path = deployment_info.get("api_path")
        if settings.EXTERNAL_HOST_REDIRECT:
            test_url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}/deployment/{api_path}"
        else:
            test_url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/deployment/{api_path}"
        
        # TODO test url -> 내부 kubernetes dns로 변경
        # workspace_id = deployment_info.get("workspace_id")
        # test_url = f"http://deployment-llm-playground-{playground_id}--service.{TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)}:18555"

        # 테스트 실행
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(test_url, json={"test_type": test_type, "session_id": session_id,
                                                         "test_dataset_id": test_dataset_id, "test_dataset_filename": test_dataset_filename,
                                                         "test_question": test_question}, timeout=1800)
                if response.status_code == 401:
                    raise Exception("Setting up the playground")
                elif response.status_code == 402:
                    raise Exception("Playground Model Error")
                elif response.status_code == 200:
                    result = response.json()
                else:
                    raise Exception(str(response.json()))
        except Exception as e:
            raise Exception(e)

        return result, message
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

import os, asyncio,subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor

# SSH 비밀번호
PASSWORD = "acryl"

def get_hosts():
    try:
        with open('/app/bg-flow-ip-1', 'r') as file1, open('/app/bg-flow-ip-2', 'r') as file2:
            ip_list = [line.strip() for line in file1] + [line.strip() for line in file2]
        
        if len(ip_list) == 0:
            raise Exception("No hosts found")    
        
        return ip_list
    except Exception as e:
        print(f"Error reading files: {e}")
        return []

def ssh_command_async(host, remote_command):
    """
    SSH 명령어를 실행
    """
    ssh_command = f"sshpass -p {PASSWORD} ssh -o StrictHostKeyChecking=no {host} '{remote_command}' &"
    try:
        # 명령 실행
        ret_code = os.system(ssh_command)
        
    except Exception as e:
        print(f"[{host}] Error occurred: {e}")
        
def ssh_command_sync(host, remote_command):
    """
    SSH 명령어를 실행하고 결과를 반환
    """
    ssh_command = f"sshpass -p {PASSWORD} ssh -o StrictHostKeyChecking=no {host} '{remote_command}'"
    try:
        # 명령 실행 및 출력 캡처
        output = subprocess.check_output(ssh_command, shell=True, encoding="utf-8")
        return output.strip()
    except subprocess.CalledProcessError as e:
        return {"host": host, "success": False, "error": e.output.strip(), "return_code": e.returncode}

def run_parallel_commands(remote_command):
    """
    여러 호스트에 대해 병렬로 명령어 실행
    """
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(ssh_command_async, host, remote_command) for host in get_hosts()]
        for future in futures:
            future.result()  # 각 스레드의 결과를 기다림

def start_bg():
    """
    Background 작업 시작
    """
    try:
        print("start bg")
        remote_command = "cd ~/distributed && ./perftest_run.sh"
        run_parallel_commands(remote_command)
    except Exception as e:
        traceback.print_exc()
        return "fail"
    return "success"

def stop_bg():
    """
    Background 작업 중지
    """
    try:
        print("stop bg")
        remote_command = "pkill ib_; pkill python3; pkill perftest; pkill perf_main;"
        run_parallel_commands(remote_command)
    except Exception as e:
        traceback.print_exc()
        return "fail"
    return "success"

async def start_jonathan_accel():
    """
    Jonathan Acceleration 시작
    """
    try:
        print("start jonathan accel")
        # 확실히 정지 후 시작 (PERF_ENABLE=1)
        if stop_bg() == "success":
            await asyncio.sleep(1)
            perf_main_command = "cd ~/distributed/perf && ./run_perf_main.sh"
            run_parallel_commands(perf_main_command)
            
            perftest_command = "cd ~/distributed && PERF_ENABLE=1 ./perftest_run.sh"
            run_parallel_commands(perftest_command)
            return "success"
        return "fail"
        
    except Exception as e:
        traceback.print_exc()
        return "fail"

async def stop_jonathan_accel():
    """
    Jonathan Acceleration 중지
    """
    try:
        print("stop jonathan accel")
        # 확실히 정지 후 시작 (PERF_ENABLE=0)
        if stop_bg() == "success":
            await asyncio.sleep(1)
            remote_command = "cd ~/distributed && PERF_ENABLE=0 ./perftest_run.sh"
            run_parallel_commands(remote_command)
            return "success"
        
        return "fail"
    except Exception as e:
        traceback.print_exc()
        return "fail"

async def get_jonathan_accel():
    """
    Jonathan Acceleration 상태 가져오기
    """
    try:
        count = 0
        for host in get_hosts():
            output = ssh_command_sync(host, "ps -ef | grep run_perf_main | wc -l")
            if isinstance(output, dict):
                raise TypeError(f"ssh command 실패. Background Pod들의 연결상태 확인 필요!")
            count += int(output)
        
        # 베이스 상태에서 2줄은 검색됨
        status = "running" if count >= 6 else "stopped"
        
        perftest_cnt = 0
        for host in get_hosts():
            output = ssh_command_sync(host, "ps -ef | grep ib_write_bw | wc -l")
            if isinstance(output, dict):
                raise TypeError(f"ssh command 실패. Background Pod들의 연결상태 확인 필요!")
            perftest_cnt += int(output)
        
        if perftest_cnt < 6:
            if stop_bg() == "success":
                await asyncio.sleep(1)
                start_bg()
        
        return status
    except Exception as e:
        traceback.print_exc()
        return "error"
