from fastapi import FastAPI
# from monitoring.route import monitoring
from monitoring.monitoring_service import set_cpu_info_to_redis, set_gpu_info_to_redis, set_mem_info_to_redis, \
    set_workspace_pod_status,set_storage_usage_info, set_node_info_to_redis,delete_complete_job, gpu_alloc_usage
from monitoring.monitoring_service import init_node_resource_info, init_node_info, workspace_resource_usage, \
    get_storage_usage_info, set_dataset_storage_usage_info,set_project_storage_usage_info, insert_mongodb_user_dashboard_timeline,\
    insert_mongodb_admin_dashboard_timeline, dataset_progress_clear, set_filebrowser_pod_list, set_deployment_pod_resouce_limit
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
import threading
from utils.mongodb import get_mongodb_conn, DATABASE
from utils.mongodb_key import USER_DASHBOARD_TIMELINE, ADMIN_DASHBOARD_TIMELINE
# from utils.scheduler_init import initialize_scheduler

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
    # deployment_thread= threading.Thread(target=set_deployment_info)
    # training_thread = threading.Thread(target=set_training_pod_status)
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
    deplyoment_worker_pod_resource_thread = threading.Thread(target=set_deployment_pod_resouce_limit)

    # cpu_thread.daemon = True
    # gpu_thread.daemon = True
    # mem_thread.daemon = True
    # workspace_thread.daemon = True
    # storage_thread.daemon = True
    # node_thread.daemon = True
    # delete_job_thread.daemon = True
    # gpu_alloc_usage_thread.daemon = True
    # workspace_resource_usage_thread.daemon = True
    # workspace_storage_usage_thread.daemon = True
    # dataset_storage_usage_thread.daemon = True
    # project_storage_usage_thread.daemon = True
    # dashboard_timeline_thread.daemon = True
    # admin_dashboard_timeline_thread.daemon = True
    # # dataset_progress_check_thread.daemon = True
    # dataset_filebrowser_check_thread.daemon = True
    # deplyoment_worker_pod_resource_thread.daemon = True
    set_gpu_info_to_redis()
    cpu_thread.start()
    # gpu_thread.start()
    mem_thread.start()
    workspace_thread.start()
    storage_thread.start()
    # deployment_thread.start()
    node_thread.start()
    delete_job_thread.start()
    gpu_alloc_usage_thread.start()
    workspace_resource_usage_thread.start()
    workspace_storage_usage_thread.start()
    dataset_storage_usage_thread.start()
    project_storage_usage_thread.start()
    dashboard_timeline_thread.start()
    admin_dashboard_timeline_thread.start()
    # dataset_progress_check_thread.start()
    dataset_filebrowser_check_thread.start()
    deplyoment_worker_pod_resource_thread.start()

def main():
    # app = initialize_app()
    dashboard_timeline_collection_init()
    set_redis()
    init_node_info()
    init_node_resource_info()

    # initialize_scheduler()
    # return app

if __name__=="__main__":
    main()
    # uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
