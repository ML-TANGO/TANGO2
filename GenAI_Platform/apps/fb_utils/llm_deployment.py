from utils.llm_db import db_items as db
from utils import settings
from utils import TYPE
from utils import topic_key
from utils.kube import PodName
from utils import helm_dto 
from utils import common, redis_key
from utils.redis import get_redis_client_async

import json
import traceback
import subprocess
try:
    from confluent_kafka import Producer
except:
    pass

class KafkaLlmDeployment:
    def __init__(self):
        self.conf = {
            'bootstrap.servers' : f"{settings.JF_KAFKA_DNS}"
        }
        self.producer = Producer(self.conf)
    def produce(self, topic, key, value):
        self.producer.produce(topic, key, value)
        self.producer.poll(1)
        self.producer.flush()
kafka = KafkaLlmDeployment()

async def run_worker(deployment_id, llm_type, llm_id, playground_run_rag_reranker=False, rag_embedding_run=0):
    """
    llm_type: "rag" or "playground"
    llm_id: rag_id or playground_id
    """
    try:
        deployment_info = db.get_deployment(deployment_id=deployment_id)
        workspace_id = deployment_info.get("workspace_id")
        workspace_name = deployment_info.get("workspace_name")
        deployment_name = deployment_info.get("name")
        user_id = deployment_info.get("user_id")
        user_name = db.get_user_name(user_id=user_id).get("name")
        instance_id = deployment_info.get("instance_id")
        instance_allocate = deployment_info.get("instance_allocate")
        gpu_total_count = deployment_info.get("gpu_per_worker", 0) # llm에서 gpu_per_worker는 총 gpu_count (UI 상 전체 입력 받는 거로)
        docker_image_id = deployment_info.get("image_id")
        image_name = db.get_image_single(image_id=docker_image_id).get("real_name").replace(settings.DOCKER_REGISTRY_URL, "")
        # image_name = "jfb-system/llm_deployment:dev"
        deployment_cpu_limit = deployment_info.get('deployment_cpu_limit', 0)
        deployment_ram_limit = deployment_info.get('deployment_ram_limit', 0)


        # ===========================================================================================
        # gpu
        # ===========================================================================================

        redis_client = await get_redis_client_async()
        used_cluster_case = dict()
        gpu_cluster_auto = False
        pod_count = 1
        if gpu_total_count > 1:
            gpu_cluster_auto = True
            gpu_cluster_info = await common.get_gpu_cluster_info(instance_id=instance_id, redis_client=redis_client)
            gpu_cluster_cases = await common.get_auto_gpu_cluster(redis_client=redis_client, instance_id=instance_id, gpu_count=gpu_total_count, gpu_cluster_info=gpu_cluster_info)
            gpu_cluster_cases = sorted(gpu_cluster_cases, key=lambda x:x["gpu_count"])
            used_cluster_case = gpu_cluster_cases[0] # TODO 가장 좋은 cluster 유형만 선택
            pod_count = used_cluster_case.get("server")
        elif gpu_total_count == 1:
            used_cluster_case = {"server" : 1, "gpu_count" : 1}

        # ===========================================================================================
        # 워커 DB
        # ===========================================================================================
        instance_type = TYPE.INSTANCE_TYPE_GPU if gpu_total_count > 0 else TYPE.INSTANCE_TYPE_CPU 
        insert_worker_result = db.insert_deployment_worker_item(deployment_id=deployment_id, instance_id=instance_id, instance_type=instance_type,
                                                                gpu_per_worker=gpu_total_count, image_id=docker_image_id,
                                                                command=None, environments=None, project_id=None,
                                                                pod_count=pod_count)
        if not insert_worker_result["result"]:
            raise "Create Deployment DB Insert Error: {}".format(insert_worker_result["message"])
        worker_id = insert_worker_result["id"]

        # ===========================================================================================
        # Kafka
        # ===========================================================================================
        # pod_name: pod_base_name은 svc, ingress 이름에 사용 (워커아이디 제외)
        pod_base_name, unique_pod_name, _ \
            = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type="deployment", sub_flag=worker_id).get_all()
        
        llm_deployment_helm_name = TYPE.LLM_DEPLOYMENT_HELM_NAME.format(deployment_id=deployment_id, llm_type=llm_type, llm_id=llm_id)

        # deployment
        helm_deployment_parameter = helm_dto.HelmDeployment(
            gpu_count=gpu_total_count, metadata_instance_id=instance_id, metadata_workspace_id=workspace_id, metadata_workspace_name=workspace_name,
            metadata_user_name=user_name, metadata_pod_name=unique_pod_name, metadata_pod_base_name=pod_base_name, metadata_helm_name=llm_deployment_helm_name,
            resources_limits_cpu=deployment_cpu_limit, resources_limits_memory=deployment_ram_limit, resources_limits_gpu=gpu_total_count,
            pod_image=image_name, deployment_id=deployment_id, deployment_name=deployment_name, deployment_worker_id=worker_id,
            gpu_cluster_auto=gpu_cluster_auto, gpu_auto_cluster_case=used_cluster_case,
        )

        # llm
        helm_parameter = None
        if llm_type in TYPE.LLM_RAG_TYPE_LIST or llm_type == "rag" or llm_type == "embedding" or llm_type == "reranker":
            # RAG -------------------------------------------------------------------------------------
            helm_parameter = await get_rag_helm_parameter(helm_deployment_parameter=helm_deployment_parameter,
                                                          llm_type=llm_type,
                                                          rag_id=llm_id, 
                                                           rag_embedding_run=rag_embedding_run)
        elif llm_type == "playground":
            # PLAYGROUND -------------------------------------------------------------------------------------
            helm_parameter = await get_playground_helm_parameter(helm_deployment_parameter=helm_deployment_parameter, playground_id=llm_id,
                                                                 playground_run_rag_reranker=playground_run_rag_reranker)

        print('========helm_parameter========')
        print(helm_parameter, llm_type)
        print("topic", topic_key.SCHEDULER_TOPIC)
        # key에 넣어야지 scheduler에서 value로 받음?? TODO 추후 확인 필요
        kafka.produce(topic=topic_key.SCHEDULER_TOPIC, 
                      key=helm_parameter.model_dump_json(), value=None)
        
    except Exception as e:
        # traceback.print_exc()
        print(llm_type, llm_id)
        raise e

async def uninstall_worker(deployment_id, llm_type, llm_id):
    """
    llm type: rag, playground
    llm_id: rag_id or playground_id
    """
    try:
        print("uninstall_worker", deployment_id, llm_type, llm_id)
        deployment_info = db.get_deployment(deployment_id=deployment_id)

        # llm 은 배포당 워커 1개이므로, deployment_id 로 worker end_datetime 업데이트
        db.update_end_datetime_deployment_worker(deployment_id=deployment_id)

        helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=deployment_info.get("workspace_id"))
        llm_deployment_helm_name = TYPE.LLM_DEPLOYMENT_HELM_NAME.format(deployment_id=deployment_id, llm_type=llm_type, llm_id=llm_id)

        # async def uninstall_deployment_helm():
        command=f"helm uninstall -n {helm_namespace} {llm_deployment_helm_name} "
        try:
            print("uninstall worker 2")
            subprocess.run(
                command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            print("uninstall worker 3")
        except Exception as e:
            pass
        return 
        # # await uninstall_deployment_helm()
        # # command = f"helm list -n {helm_namespace} | grep {llm_deployment_helm_name}"
        # try:
        #     # subprocess.run(command, shell=True, check=True, text=True,
        #     #     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        #     # )
        #     # 결과가 나오면 삭제 안된것이므로 한번더 삭제
        #     # await uninstall_deployment_helm()
        # except Exception as e:
        #     pass
    except Exception as e:
        traceback.print_exc()
        raise e

async def get_playground_helm_parameter(helm_deployment_parameter, playground_id, playground_run_rag_reranker=False):
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        playground_name = playground_info.get("name")

        # playground deployment
        deployment = playground_info.get("deployment")
        deployment = json.loads(deployment) if deployment else dict()
        deployment_run = deployment.get("deployment_run")
        deployment_run = deployment_run if deployment_run else dict()
        model = playground_info.get("model")
        model = json.loads(model) if model else dict()
        model_parameter = playground_info.get("model_parameter")
        model_parameter = json.loads(model_parameter) if model_parameter else dict()
        rag = playground_info.get("rag")
        rag = json.loads(rag) if rag else dict()
        prompt = playground_info.get("prompt")
        prompt = json.loads(prompt) if prompt else dict()
        accelerator = playground_info.get("accelerator", False)

        # model
        model_type = model.get("model_type")
        model_allm_commit_id = model.get("model_allm_commit_id")
        model_allm_commit_name = None
        model_allm_name = None
        if model_type == "commit":
            model_commit_info = await db.get_commit_model(commit_id=model_allm_commit_id)
            model_allm_commit_name = model_commit_info.get("name")
            model_allm_name = model_commit_info.get("model_name")

        # helm parameter
        helm_parameter = helm_dto.HelmPlayground(
            **helm_deployment_parameter.model_dump(),
            llm_type="playground", llm_id=playground_id, llm_name=playground_name,
            playground_id=playground_id,
            accelerator=accelerator,
            # model
            model_type=model_type,
            model_huggingface_id=model.get("model_huggingface_id"),
            model_huggingface_token=model.get("model_huggingface_token"),
            model_allm_name=model_allm_name,
            model_allm_commit_name=model_allm_commit_name,
            # model parameter
            param_temperature=model_parameter.get("temperature"),
            param_top_p=model_parameter.get("top_p"),
            param_top_k=model_parameter.get("top_k"),
            param_repetition_penalty=model_parameter.get("repetition_penalty"),
            param_max_new_tokens=model_parameter.get("max_new_tokens"),
            # rag
            rag_chunk_max=rag.get("rag_chunk_max"),
            # prompt
            prompt_system_message=prompt.get("system_message"),
            prompt_user_message=prompt.get("user_message"),
            # run
            run_rag=deployment_run.get("run_rag"),
            run_prompt=deployment_run.get("run_prompt"),
            run_rag_reranker=playground_run_rag_reranker,
            rag_id=rag.get("rag_id"),
        )
        return helm_parameter
    except Exception as e:
        traceback.print_exc()
        raise e

async def get_rag_helm_parameter(helm_deployment_parameter,
                                 rag_id, rag_embedding_run=0, llm_type=None):
    """
    rag_embedding_run: reranker 실행시 embeding도 같이 실행하는지 여부 -> 같이 실행할 경우 embedding 처리를 기다림
    """
    try:
        rag_info = await db.get_rag(rag_id=rag_id)
        rag_name = rag_info.get("name")
        rag_chunk_len = rag_info.get("chunk_len", 1000) 

        if llm_type in TYPE.LLM_RAG_EMBEDDING_LIST:
            model_huggingface_id = rag_info.get("embedding_huggingface_model_id") 
            model_huggingface_token = rag_info.get("embedding_huggingface_model_id") 
        else:
            model_huggingface_id = rag_info.get("reranker_huggingface_model_id") 
            model_huggingface_token = rag_info.get("reranker_huggingface_token") 

        if not model_huggingface_id:
            raise Exception("Huggingface model is None")

        llm_type = llm_type if llm_type else "rag"
        helm_parameter = helm_dto.HelmRag(**helm_deployment_parameter.model_dump(),
                                          llm_type=llm_type, llm_id=rag_id, llm_name=rag_name,
                                          model_type="huggingface", model_huggingface_id=model_huggingface_id, model_huggingface_token=model_huggingface_token,
                                          rag_id=rag_id, rag_chunk_len=rag_chunk_len,
                                          rag_embedding_run=rag_embedding_run
                                        )
        return helm_parameter 
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)



