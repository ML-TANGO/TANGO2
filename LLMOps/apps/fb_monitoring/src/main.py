# from fastapi import FastAPI
# from monitoring.route import monitoring
from monitoring.monitoring_service import set_cpu_info_to_redis, set_gpu_info_to_redis, set_mem_info_to_redis, \
    set_workspace_pod_status,set_storage_usage_info, set_node_info_to_redis,delete_complete_job, gpu_alloc_usage
from monitoring.monitoring_service import init_node_resource_info, init_node_info, workspace_resource_usage, \
    get_storage_usage_info, set_dataset_storage_usage_info,set_project_storage_usage_info, insert_mongodb_user_dashboard_timeline,\
    insert_mongodb_admin_dashboard_timeline, dataset_progress_clear, set_filebrowser_pod_list, set_deployment_pod_resouce_limit, \
    get_deployment_worker_resource, get_gpu_resource_utilization, get_pod_resource_usage_in_workspace, get_model_commit_pod, \
    workspace_basic_cost, workspace_instance_cost, workspace_storage_cost, set_model_storage_usage_info, set_rag_storage_usage_info
# from utils.resource import CustomResponse
# from utils.resource import CustomMiddleWare
import threading, logging
from utils.mongodb import get_mongodb_conn, DATABASE
from utils.mongodb_key import USER_DASHBOARD_TIMELINE, ADMIN_DASHBOARD_TIMELINE
from utils.settings import JF_PRICING_MODE, LLM_USED
from utils.redis import start_redis_health_monitor
from health_check import start_health_check_server
# from utils.scheduler_init import initialize_scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# def initialize_app():
#     app = FastAPI()
#     api = FastAPI(
#         title="JFB API",
#         version='0.1',
#         default_response_class=CustomResponse,
#         middleware=CustomMiddleWare,
#         openapi_url="/monitoring/openapi.json",
#         docs_url="/monitoring/docs",
#         redoc_url="/monitoring/redoc"
#     )

#     api.include_router(monitoring)
#     app.mount('/api', api)    
#     return app

def dashboard_timeline_collection_init():
    client = get_mongodb_conn()
    # KDN 
    msa_jfb = client[DATABASE]
    # kdn_db.create_collection(NOTIFICATION_COLLECTION, capped=True, max=10000)
    msa_jfb[USER_DASHBOARD_TIMELINE].create_index([("create_datetime", 1)], expireAfterSeconds=5184000 ) # 60일
    msa_jfb[ADMIN_DASHBOARD_TIMELINE].create_index([("create_datetime", 1)], expireAfterSeconds=5184000 ) # 30일

def set_redis():
    cpu_thread = threading.Thread(target=set_cpu_info_to_redis)
    # gpu_thread = threading.Thread(target=set_gpu_info_to_redis)
    mem_thread = threading.Thread(target=set_mem_info_to_redis)
    workspace_thread = threading.Thread(target=set_workspace_pod_status)
    storage_thread = threading.Thread(target=set_storage_usage_info)
    
    # hps_thread = threading.Thread(target=set_hps_pod_status)
    node_thread = threading.Thread(target=set_node_info_to_redis)
    delete_job_thread = threading.Thread(target=delete_complete_job)
    gpu_alloc_usage_thread = threading.Thread(target=gpu_alloc_usage)
    workspace_resource_usage_thread = threading.Thread(target=workspace_resource_usage)
    workspace_storage_usage_thread = threading.Thread(target=get_storage_usage_info)
    dataset_storage_usage_thread = threading.Thread(target=set_dataset_storage_usage_info)
    project_storage_usage_thread = threading.Thread(target=set_project_storage_usage_info)
    dashboard_timeline_thread = threading.Thread(target=insert_mongodb_user_dashboard_timeline)
    admin_dashboard_timeline_thread = threading.Thread(target=insert_mongodb_admin_dashboard_timeline)
    # dataset_progress_check_thread = threading.Thread(target=dataset_progress_clear)
    dataset_filebrowser_check_thread = threading.Thread(target=set_filebrowser_pod_list)
    deplyoment_worker_pod_resource_thread = threading.Thread(target=get_deployment_worker_resource)
    deplyoment_worker_pod_resource_limit_thread = threading.Thread(target=set_deployment_pod_resouce_limit)
    gpu_resource_utilization_thread = threading.Thread(target=get_gpu_resource_utilization)
    # node_resource_usage_thread = threading.Thread(target=get_node_resource_usage_info)
    get_pod_resource_usage_in_workspace_thread= threading.Thread(target=get_pod_resource_usage_in_workspace)
    get_model_commit_pod_thread = threading.Thread(target=get_model_commit_pod)

    dashboard_timeline_thread.daemon = True
    admin_dashboard_timeline_thread.daemon = True
    set_gpu_info_to_redis()
    cpu_thread.start()
    # gpu_thread.start()
    mem_thread.start()
    workspace_thread.start()
    storage_thread.start()
    
    node_thread.start()
    delete_job_thread.start()
    gpu_alloc_usage_thread.start()
    workspace_resource_usage_thread.start()
    workspace_storage_usage_thread.start()
    dataset_storage_usage_thread.start()
    project_storage_usage_thread.start()
    dashboard_timeline_thread.start()
    admin_dashboard_timeline_thread.start()
    dataset_filebrowser_check_thread.start()
    deplyoment_worker_pod_resource_thread.start()
    deplyoment_worker_pod_resource_limit_thread.start()
    gpu_resource_utilization_thread.start()
    get_pod_resource_usage_in_workspace_thread.start()
    get_model_commit_pod_thread.start()

    
    if LLM_USED:
        model_storage_usage_thread= threading.Thread(target=set_model_storage_usage_info)
        model_storage_usage_thread.start()
        rag_storage_usage_thread= threading.Thread(target=set_rag_storage_usage_info)
        rag_storage_usage_thread.start()
        
def main():
    # app = initialize_app()
    logging.info("Starting monitoring application...")
    
    # Redis 헬스 모니터 시작
    start_redis_health_monitor()
    
    # Health check 서버 시작
    try:
        start_health_check_server(port=8080)
    except Exception as e:
        logging.error(f"Health check 서버 시작 실패: {e}")
    
    dashboard_timeline_collection_init()
    set_redis()
    init_node_info()
    init_node_resource_info()
    
    logging.info("Monitoring application started successfully")
    
    # initialize_scheduler()
    # return app

if __name__=="__main__":
    main()
    # uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
