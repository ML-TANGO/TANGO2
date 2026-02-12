# import traceback, os, json, subprocess, statistics, time, logging, functools, threading
# from datetime import datetime

# from utils.resource import CustomResource, response
# from utils.exceptions import *
# from utils.exceptions_deployment import *

# from utils.PATH import * 
# from utils.TYPE import *
# import utils.common as common
# from utils.msa_db import db_user, db_deployment
# from utils.redis_key import DEPLOYMENT_WORKER_RESOURCE_LIMIT, WORKSPACE_PODS_STATUS, DEPLOYMENT_WORKER_RESOURCE
# from utils.redis import get_redis_client
# from utils.common import byte_to_gigabyte

# POD_MEMORY_HISTORY_KEY = "mem_history"
# POD_CPU_HISTORY_KEY = "cpu_history"
# POD_GPU_HISTORY_KET = "gpu_history"

# redis_client = get_redis_client()

# # from kubernetes import client, stream
# # networkingV1Api = client.NetworkingV1Api()
# # coreV1Api = client.CoreV1Api()

# def check_deployment_worker_log_dir(workspace_name, deployment_name, start_time=None, end_time=None, deployment_worker_id=None):
#     result = {
#         "error":1,
#         "message":"No worker made",
#         "log_dir":[]
#     }
#     if start_time==None:
#         start_time_ts=0
#     else:
#         start_time_ts=common.date_str_to_timestamp(start_time)
#     if end_time==None:
#         end_time_ts=30000000000
#     else:
#         end_time_ts=common.date_str_to_timestamp(end_time)
    
#     workspace_info = db_deployment.get_workspace(workspace_name=workspace_name)
#     deployment_info = db_deployment.get_deployment(deployment_name=deployment_name)
    
#     main_storage_name = workspace_info["main_storage_name"]
#     log_dir_path = JF_DEPLOYMENT_PATH.format(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name)+"/log"

#     # print( workspace_info.get("workspace_id"))
#     tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_info.get("id"))
#     redis_pod_list = json.loads(tmp_workspace_pod_status)
#     deployment_redis_list = redis_pod_list.get('deployment', dict())
#     deployment_worker_redis_list = deployment_redis_list.get(str(deployment_info.get("id")))

#     if os.path.exists(log_dir_path)==False:
#         return result
#     if deployment_worker_id!=None:
#         log_dir_list = [str(deployment_worker_id)]
#     else:
#         log_dir_list = os.listdir(log_dir_path)
        
#     for log_dir in log_dir_list:
#         if os.path.isdir(os.path.join(log_dir_path, str(log_dir))):
#             deployment_worker_run_time_file_path = GET_POD_RUN_TIME_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name,
#                                                                                         workspace_name=workspace_name,
#                                                                                         deployment_name=deployment_name,
#                                                                                         deployment_worker_id=int(log_dir))
#             if os.path.exists(deployment_worker_run_time_file_path):
#                 run_time_info=common.load_json_file(deployment_worker_run_time_file_path) # 경우에 따라서는 retry를 하지 않아도 되는 상황이 생길 수 있음
#                 if run_time_info !=None:
#                 # try:
#                     run_start_ts = common.date_str_to_timestamp(run_time_info["start_time"])
#                     run_end_ts = common.date_str_to_timestamp(run_time_info["end_time"])
#                     if run_start_ts>end_time_ts or run_end_ts<start_time_ts:
#                         result["message"]="No worker in time range"
#                     else:
#                         result["log_dir"].append(log_dir)
#                 # try:
#                 #     with open(deployment_worker_run_time_file_path, "r") as f:
#                 #         run_time_data = f.read()
#                 #         run_time_info = json.loads(run_time_data)
#                 #     run_start_ts = common.date_str_to_timestamp(run_time_info["start_time"])
#                 #     run_end_ts = common.date_str_to_timestamp(run_time_info["end_time"])
#                 #     if run_start_ts>end_time_ts or run_end_ts<start_time_ts:
#                 #         result["message"]="No worker in time range"
#                 #     else:
#                 #         result["log_dir"].append(log_dir)
#                 # except:
#                 #     traceback.print_exc()
#                 #     continue
#             # elif check_worker_dir_and_install(workspace_name, deployment_name, [log_dir])==False:
#             elif deployment_worker_redis_list is not None and str(log_dir) in deployment_worker_redis_list:
#                 if deployment_worker_redis_list.get(str(log_dir)).get("status") == "installing":
#                     result["message"]="Worker Installing"
                    
#     if len(result["log_dir"])==0:
#         return result
#     result["error"]=0
#     result["message"]=""
#     return result

# def check_worker_dir_and_install(workspace_name, deployment_name, worker_dir_list): 
#     worker_dir_list=[str(i) for i in worker_dir_list]
#     status_list=[]
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#     for worker_id_str in worker_dir_list:
#         deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
#                                                                             workspace_name=workspace_name, 
#                                                                             deployment_name=deployment_name, 
#                                                                             deployment_worker_id=int(worker_id_str))
#         try:
#             if POD_NGINX_ACCESS_LOG_FILE_NAME not in os.listdir(deployment_worker_log_dir):
#                 # return False
#                 status_list.append(False)
#         except FileNotFoundError:
#             status_list.append(False)

#     if len(status_list)==len(worker_dir_list):
#         return False
#     return True

# # ==========================================================================
# # dashboard 
# # ==========================================================================
# # </dashboard_status> 
# def get_deployment_dashboard_status(deployment_id, start_time=None, end_time=None):
#     """
#     배포 > 대시보드
#     total_info(dict): 맨 위 4개
#         deployment_run_time: 배포작동시간
#         total_call_count: 전체 콜 수
#         total_success_rate: 응답 성공률
#         running_worker_count: 작동 중인 워커
#         ???==========
#         total_log_size: 30292,
#         restart_count: 0,
#         error_worker_count: 0,
#     resource_info: 위에서 2번째 (4개 게이지 차트) - min, max, average
#         cpu_usage_rate(cpu사용률)
#         ram_usage_rate(ram 사용률)
#         gpu_core_usage_rate(gpu core 사용률)
#         gpu_mem_usage_rate(gpu mem 사용률)
#     worker_start_time 
#         가운데 - 범위(UTC+9) 에 들어감
#     """

#     try:

#         deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
#         workspace_name = deployment_info["workspace_name"]
#         deployment_name = deployment_info["name"]
#         workspace_id = deployment_info.get("workspace_id")
        
#         log_dir_result = check_deployment_worker_log_dir(workspace_name=workspace_name, deployment_name=deployment_name)
#         total_info = get_deployment_api_total_count_info(worker_dir_list=log_dir_result["log_dir"], workspace_name=workspace_name, deployment_name=deployment_name)
#         running_worker_list = get_running_worker_dir(workspace_id=workspace_id, deployment_id=deployment_id)

#         resource_info = get_deployment_resource_info(
#             worker_dir_list=running_worker_list["running_worker_list"] + running_worker_list["error_worker_list"], 
#             deployment_id=deployment_id)
    
#         result = {
#         "total_info": {
#             "total_call_count": total_info["total_call_count"], # 전체 콜 수
#             "total_success_rate": total_info["total_success_rate"], # 응답성공률
#             "total_log_size": total_info["total_log_size"], # 전체 콜 수 옆에 뜨는 용량
#             "restart_count": total_info["restart_count"], 
#             "running_worker_count": len(running_worker_list["running_worker_list"]), # 작동중인 워커
#             "error_worker_count": len(running_worker_list["error_worker_list"]), # 0보다 크면 작동중인 워커 옆에 빨간색으로 표시됨
#             "deployment_run_time": get_deployment_run_time(deployment_id=deployment_id) if log_dir_result["error"]!=1 else 0 # 배포작동시간 
#         },
#         # TODO
#         "resource_info": {
#             "cpu_usage_rate": resource_info["cpu_usage_rate"],
#             "ram_usage_rate": resource_info["ram_usage_rate"],
#             "gpu_mem_usage_rate": resource_info["gpu_mem_usage_rate"],
#             "gpu_core_usage_rate": resource_info["gpu_core_usage_rate"],
#             "gpu_use_mem": resource_info["gpu_use_mem"],
#             "gpu_total_mem": resource_info["gpu_total_mem"],
#             "gpu_mem_unit": resource_info["gpu_mem_unit"],
#         },
#         "worker_start_time": get_worker_start_time(deployment_id=deployment_id) # 배포작동시간
#         }
#         return response(status=1, message="success", result=result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="get dashboard status error")

# # running/error_worker_count -----------------
# def get_running_worker_dir(workspace_id, deployment_id):
#     error_worker_list=[]
#     running_worker_list=[]

#     # deployment_status_list = deployment_redis.get_deployment_worker_status_list(workspace_id=workspace_id, deployment_id=deployment_id)
#     deployment_status_list = []
#     tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
#     if tmp_workspace_pod_status is None:
#         data = dict()
#         if tmp_workspace_pod_status is None:
#             data = dict()
#         else:
#             data = json.loads(tmp_workspace_pod_status)

#         deployment_data = data.get('deployment', dict())
#         for data_deployment_id, data_deployment_list in deployment_data.items():
#             try:
#                 if int(data_deployment_id) == deployment_id:
#                     deployment_status_list = data_deployment_id
#                     break
#             except:
#                 pass

#     if len(deployment_status_list) > 0:
#         for key, value in deployment_status_list.items():
#             if value["status"] == "running":
#                 running_worker_list.append(key)
#             else:
#                 error_worker_list.append(key)

#     return {
#         "running_worker_list" : running_worker_list,
#         "error_worker_list" : error_worker_list
#     }

# # worker_start_time, deployment_run_time -----------------
# def get_worker_start_time(deployment_id):
#     # import utils.common as common
#     run_time_list = get_deployment_run_time_list(deployment_id=deployment_id)
#     # print("RUN TIME LIST" , run_time_list)
#     run_time_list = [dic for dic in run_time_list if dic!={}]
#     run_time_list = sorted(run_time_list, key=lambda run_time: (run_time[POD_RUN_TIME_START_TIME_KEY], run_time[POD_RUN_TIME_END_TIME_KEY]))
#     # print(run_time_list)
#     if len(run_time_list)>0:
#         return run_time_list[0][POD_RUN_TIME_START_TIME_KEY]
#     else:
#         return datetime.strftime(datetime.now(), POD_RUN_TIME_DATE_FORMAT)

# def get_deployment_run_time_list(deployment_id=None, workspace_name=None, deployment_name=None, *args, **kwargs):
#     """
#     Description : deployment_id or workspace_name deployment_name 조합으로 해당 조건에 맞는 worker 들의 run time 정보를 list로 가져오는 함수

#     Args :
#         deployment_id (int) : 
#         ----------------------
#         workspace_name (str) :
#         deployment_name (str) :

#     Returns :
#         (list): [ { "start_time": "2022-03-10 03:24:13", "end_time": "2022-03-10 05:49:31" } ... ]
#     """
    
#     if deployment_id is not None:
#         deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
#         if deployment_info is None:
#             return []
#         workspace_name = deployment_info["workspace_name"]
#         deployment_name = deployment_info["name"]

#     run_time_info_list = []
#     for deployment_worker_id in get_deployment_worker_list_from_folder(workspace_name=workspace_name, deployment_name=deployment_name):
#         run_time_info = get_deployment_worker_run_time_info(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id, *args, **kwargs)
#         if run_time_info is not None:
#             run_time_info_list.append(run_time_info)

#     return run_time_info_list

# def get_deployment_worker_list_from_folder(workspace_name, deployment_name):
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#     deployment_log_dir = JF_DEPLOYMENT_LOG_DIR_PATH.format(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name)
#     worker_list = []
#     try:
#         for name in os.listdir(deployment_log_dir):
#             full_path = os.path.join(deployment_log_dir, name)
#             if os.path.isdir(full_path):
#                 worker_list.append(name)
#     except FileNotFoundError as fne:
#         return []
#     except Exception as e:
#         traceback.print_exc()
#         return []
#     return worker_list

# def get_deployment_run_time(deployment_id=None, workspace_name=None, deployment_name=None, *args, **kwargs):
#     """
#     Description : deployment_id or workspace_name deployment_name 조합으로 해당 조건에 맞는 deployment의 run_time의 ts 값 내려주는 함수

#     Args :
#         deployment_id (int) : 
#         ----------------------
#         workspace_name (str) :
#         deployment_name (str) :

#     Returns :
#         (int): run time timestamp
#     """
#     import utils.common as common
#     run_time_list = get_deployment_run_time_list(deployment_id=deployment_id, workspace_name=workspace_name, deployment_name=deployment_name, *args, **kwargs)
#     # print("RUN TIME LIST" , run_time_list)
#     run_time_list = [dic for dic in run_time_list if dic!={}]
#     run_time_list = sorted(run_time_list, key=lambda run_time: (run_time["start_time"], run_time["end_time"]))

#     base_start_time_ts = -1
#     base_end_time_ts = -1
#     run_time_ts = 0
#     for i, run_time in enumerate(run_time_list):
#         current_start_time_ts = common.date_str_to_timestamp(run_time["start_time"])
#         current_end_time_ts = common.date_str_to_timestamp(run_time["end_time"])
        
#         if base_start_time_ts == -1:
#             base_start_time_ts = current_start_time_ts
#         if base_end_time_ts == -1:
#             base_end_time_ts = current_end_time_ts
            
#         if (base_start_time_ts <= current_start_time_ts and current_start_time_ts <= base_end_time_ts) and i != len(run_time_list) -1 :
#             base_end_time_ts = current_end_time_ts
#         else:
#             if i == len(run_time_list) -1:
#                 base_end_time_ts = current_end_time_ts
#             run_time_ts += base_end_time_ts - base_start_time_ts
#             base_start_time_ts = -1
#             base_end_time_ts = -1
#     return run_time_ts

# # resource_info -------------------------
# def get_deployment_resource_info(worker_dir_list, deployment_id=None, deployment_worker_id=None):
#     ndigits=3
#     result = {
#         "cpu_usage_rate":{
#             "min": 0,
#             "max": 0,
#             "average": 0
#         },
#         "ram_usage_rate":{
#             "min": 0,
#             "max": 0,
#             "average":0
#         },
#         "gpu_mem_usage_rate":{
#             "min": 0,
#             "max": 0,
#             "average":0
#         },
#         "gpu_core_usage_rate":{
#             "min": 0,
#             "max": 0,
#             "average":0
#         },
#         "gpu_use_mem":0,
#         "gpu_total_mem":0,
#         "gpu_mem_unit":"MiB"
#     }
    
#     if len(worker_dir_list)==0:
#         return result
#     # pod_list = kube_data.get_pod_list()
#     rate_dic={
#         "cpu_usage_rate":[],
#         "ram_usage_rate":[],
#         "gpu_mem_usage_rate":[],
#         "gpu_core_usage_rate":[],
#         "worker_id":[],
#         "gpu_use_mem":[],
#         "gpu_total_mem":[]
#     }
#     for worker_id_str in worker_dir_list:
#         # get cpu info
#         rate_dic["worker_id"].append(int(worker_id_str))
        
#         pod_name = db_deployment.get_deployment_worker(deployment_worker_id=int(worker_id_str))["api_path"] +"-" + worker_id_str 

#         cpu_info = get_pod_cpu_ram_usage_file(pod_name=pod_name)
#         if cpu_info!=None:
#             rate_dic["cpu_usage_rate"].append(cpu_info.get(CPU_USAGE_ON_POD_KEY))
#             rate_dic["ram_usage_rate"].append(cpu_info.get(MEM_USAGE_PER_KEY))
#         else:
#             # index 통해 min max worker id 구하기 위해서
#             rate_dic["cpu_usage_rate"].append(0)
#             rate_dic["ram_usage_rate"].append(0)

#         # get gpu info
#         # gpu_info = kube_new.get_pod_gpu_usage_info(deployment_worker_id = int(worker_id_str))
#         gpu_info = get_pod_gpu_usage_file(pod_name=pod_name)

#         # if gpu_info!=None and gpu_info["recordable"]==True:
#         gpu_core_usage_rate_sum=0
#         gpu_mem_usage_rate_sum=0
#         gpu_use_mem_sum=0
#         gpu_total_mem_sum=0
#         if gpu_info!=None:
#             gpu_core_usage_rate=[]
#             gpu_mem_usage_rate=[]
#             gpu_use_mem=[]
#             gpu_total_mem=[]
#             gpu_info_key=list(gpu_info.keys())
#             # gpu_info_key.remove("recordable")
#             gpu_count=0
#             for key in gpu_info_key:
#                 if gpu_info[key].get("recordable")!=False:
#                     gpu_core_usage_rate.append(gpu_info[key].get(GPU_UTIL_KEY))
#                     gpu_mem_usage_rate.append(gpu_info[key].get(GPU_MEM_USED_KEY)/gpu_info[key].get(GPU_MEM_TOTAL_KEY)*100)
#                     gpu_use_mem.append(gpu_info[key].get(GPU_MEM_USED_KEY))
#                     gpu_total_mem.append(gpu_info[key].get(GPU_MEM_TOTAL_KEY))
#                     gpu_count+=1
#             if gpu_count!=0:
#                 gpu_core_usage_rate_sum=sum(gpu_core_usage_rate)/len(gpu_info.keys())
#                 gpu_mem_usage_rate_sum=(sum(gpu_use_mem)/sum(gpu_total_mem))*100
#                 gpu_use_mem_sum=sum(gpu_use_mem)
#                 gpu_total_mem_sum=sum(gpu_total_mem)

#         # index 통해 min max worker id 구하기 위해서
#         rate_dic["gpu_core_usage_rate"].append(gpu_core_usage_rate_sum)
#         rate_dic["gpu_mem_usage_rate"].append(gpu_mem_usage_rate_sum)
#         rate_dic["gpu_use_mem"].append(gpu_use_mem_sum)
#         rate_dic["gpu_total_mem"].append(gpu_total_mem_sum)
#     resource_key_list = list(rate_dic.keys())
#     resource_key_list.remove("worker_id")
#     resource_key_list.remove("gpu_use_mem")
#     resource_key_list.remove("gpu_total_mem")
#     for key in resource_key_list:
#         result[key]["average"]=get_statistic_result([i for i in rate_dic[key] if i>0], logic="mean", ndigits=ndigits)
#         result[key]["min"]=get_statistic_result([i for i in rate_dic[key] if i>0], logic="min", ndigits=ndigits)
#         result[key]["max"]=get_statistic_result([i for i in rate_dic[key] if i>0], logic="max", ndigits=ndigits)
#         if result[key]["min"]!=result[key]["max"]:
#             result[key]["min_worker_id"]=rate_dic["worker_id"][rate_dic[key].index(min([i for i in rate_dic[key] if i>0]))]
#             result[key]["max_worker_id"]=rate_dic["worker_id"][rate_dic[key].index(max(rate_dic[key]))]
#     for key in ["gpu_use_mem", "gpu_total_mem"]:
#         result[key]=sum(rate_dic[key])

#     return result

# def get_deployment_api_total_count_info(worker_dir_list, workspace_name, deployment_name):
#     # worker_dir_list = worker id list
#     import time
#     ndigits=3
#     result={
#         "total_call_count": 0,
#         "total_success_rate":0,
#         "total_log_size":0,
#         "restart_count": str(0) # str 해야지 됨???
#     }
#     total_call_count=0
#     # total_success=0
#     total_nginx_success=0
#     total_log_size_list=[]
#     check_import_list=[]
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
    
#     for worker_id_str in worker_dir_list:
#         deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
#                                                                              workspace_name=workspace_name, 
#                                                                             deployment_name=deployment_name, 
#                                                                             deployment_worker_id=int(worker_id_str))
#         try:
#             file_list = os.listdir(deployment_worker_log_dir)
#         except FileNotFoundError as fne:
#             continue
#         nginx_count_info={
#             "total_count":0,
#             "success_count":0
#         }
#         main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#         nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=int(worker_id_str))

#         if os.path.exists(nginx_log_count_file):
#             data = common.load_json_file(file_path=nginx_log_count_file)
#             if data is not None:
#                 nginx_count_info = data
#             # try:
#             #     for i in range(5):
#             #         with open(nginx_log_count_file, "r") as f:
#             #             nginx_count_info=json.load(f)
#             # except:
#             #     pass
#         nginx_count=nginx_count_info["total_count"]
#         # nginx_count = get_file_line_count(deployment_worker_log_dir, POD_NGINX_ACCESS_LOG_FILE_NAME)
#         total_call_count+=nginx_count
#         log_size = get_dir_size(deployment_worker_log_dir)
#         if log_size !=None:
#             total_log_size_list.append(log_size)
#         # check_import=check_deployment_api_monitor_import(file_list=file_list)
        
#         check_import = True if POD_API_LOG_IMPORT_CHECK_FILE_NAME in file_list else False
        
#         check_import_list.append(check_import)
#         # success = get_nginx_success_count(deployment_worker_log_dir)
#         nginx_success = nginx_count_info["success_count"]
#         # if check_import:
#         #     try:
#         #         monitor_count_file_path = "{}/{}".format(deployment_worker_log_dir, POD_API_LOG_COUNT_FILE_NAME)
#         #         with open(monitor_count_file_path, "r") as f:
#         #             monitor_count_info = literal_eval(f.read())
#         #         success = monitor_count_info["success"]
#         #     except:
#         #         success = 0
#         #     total_success+=success
#         total_nginx_success+=nginx_success

#     result["total_call_count"]=total_call_count
#     result["total_success_rate"]=round((total_nginx_success/total_call_count)*100, ndigits=ndigits) if total_call_count>0 else 0

#     result["total_log_size"]=sum(total_log_size_list)
#     # result["restart_count"]="dummy"
#     return result

# def get_dir_size(file_path):
#     if os.path.exists(file_path):
#         cmd = "du -b {}".format(file_path)
#         try:
#             out = subprocess.check_output(cmd, shell=True).strip().decode()
#             out = out.split("\t")[0]
#             return int(out)
#         except:
#             traceback.print_exc()
#             return None
#     else:
#         return 0

# def get_statistic_result(result, logic="mean", ndigits=3):
#     import math
#     def calculate_percentile(arry, percentile):
#         size = len(arry)
#         return sorted(arry)[int(math.ceil((size * percentile) / 100)) - 1]
#     if len(result)==0:
#         return 0
#     elif logic in ["mean","average"]:
#         return round(statistics.mean(result), ndigits=ndigits)
#     elif logic == "median":
#         return round(statistics.median(result), ndigits=ndigits)
#     elif logic == "min":
#         return round(min(result), ndigits=ndigits)
#     elif logic == "max":
#         return round(max(result), ndigits=ndigits)
#     elif logic[:10]=="percentile":
#         return round(calculate_percentile(arry=result, percentile=int(logic[10:])), ndigits=ndigits)

# def get_pod_cpu_ram_usage_file(pod_name=None):
#     # kube 대체
#     try:
#         # { "cpu_usage": 4.725 (Per), "mem_usage": 340127744 (Byte) }
#         # {'cpu_usage_on_node': 0.773808, 'cpu_usage_on_pod': 0.773808, 'mem_usage': 2401140736, 'mem_limit': 10737418240, 'mem_usage_per': 22.3624, 'timestamp': 1666070127, 'cpu_cores_on_pod': 12}
#         # resource_data_path = POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_JF_API.format(pod_name=pod_name)
#         resource_data_path = get_pod_resource_usage_path(pod_name=pod_name)

#         if resource_data_path != None:
#             resource_data_path += "/resource_usage.json" 
#             data=common.load_json_file(file_path=resource_data_path)
#         else:
#             data = None
#         if data !=None :
#             data[CPU_USAGE_ON_NODE_KEY] = min(data[CPU_USAGE_ON_NODE_KEY], 100)
#             data[CPU_USAGE_ON_POD_KEY] = min(data[CPU_USAGE_ON_POD_KEY], 100)
#             return data
#         else:
#             return POD_RESOURCE_DEFAULT
#     except FileNotFoundError:
#         return POD_RESOURCE_DEFAULT
#     except KeyError:
#         return POD_RESOURCE_DEFAULT
#     except Exception as e:
#         traceback.print_exc()
#         return POD_RESOURCE_DEFAULT

# def get_pod_gpu_usage_file(pod_name):
#     # kube 대체
#     def check_recordable(data):
#         # MIG 같은 경우에는 사용량 측정을 제대로 할 수 없음
#         for gpu_value in data.values():
#             try:
#                 if type(gpu_value) == type(str()):
#                     return False
#             except Exception as e :
#                 traceback.print_exc()
#                 return False
#         return True

#     # { "0": { "util_gpu": 0, "util_memory": 0, "memory_free": 8643, "memory_used": 2535, "memory_total": 11178, "timestamp": 1664266328 } }
#     # resource_data_path = POD_GPU_USAGE_RECORD_FILE_PATH_IN_JF_API.format(pod_name=pod_name)
#     resource_data_path = get_pod_resource_usage_path(pod_name=pod_name)
#     try:
#         if resource_data_path != None:
#             resource_data_path += "/gpu_usage.json" 
#             data = common.load_json_file(file_path=resource_data_path)
#         if data != None:
#             for value in data.values():
#                 if check_recordable(value)==False:
#                     value["recordable"]=False
#         return data
#     except FileNotFoundError:
#         return None

# def get_pod_resource_usage_path(pod_name):
#     try:
#         deployment_worker_id = int(str(pod_name).split('-')[1].split('.')[0])
#         info = db_deployment.get_worker_path_info(deployment_worker_id=deployment_worker_id)
#         deployment_path = JF_DEPLOYMENT_PATH.format(
#             main_storage_name=info.get("main_storage_name"),
#             workspace_name=info.get("workspace_name"),
#             deployment_name=info.get("deployment_name")
#         )
#         return deployment_path + f"/pod_resource_usage/{pod_name.split('.')[0]}"
#     except:
#         traceback.print_exc()
#         return None

# # </dashboard/options>
# def get_deployment_dashboard_running_worker(deployment_id, start_time=None, end_time=None):
#     res = {
#         "deployment_running_worker" : []
#     }
#     try:
#         for item in db_deployment.get_deployment_worker_list(deployment_id=deployment_id,running=False):
#             res["deployment_running_worker"].append(item["id"])
#         return response(status=1, result=res, message="success")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, result=res, message="get dashboard running worker error")

# # </dashboard_history> 
# #  배포 -> 워커 -> 워커 상세정보 페이지 - 워커 정보 하위
# def get_deployment_api_monitor_graph(deployment_id, start_time, end_time, interval, absolute_location, worker_list, search_type="range", get_csv=False):
#     try:
#         # from deployment_worker.service import check_deployment_worker_log_dir, check_worker_dir_and_install
#         info = db_deployment.get_deployment(deployment_id=deployment_id)
#         workspace_name = info["workspace_name"] 
#         deployment_name = info["name"]
#         message = "Success getting dashboard history info"

#         # check ==============================================================================
#         if worker_list != None:
#             worker_list = [int(i.strip()) for i in worker_list.split(",")]
#         else:
#             # worker 없는경우
#             log_dir_result = check_deployment_worker_log_dir(workspace_name=workspace_name, deployment_name=deployment_name,
#                                                             start_time=start_time, end_time=end_time)
#             if log_dir_result["error"]==1:
#                 message = log_dir_result["message"]
#                 # return response(status=0, message=log_dir_result["message"])
#             else:
#                 worker_list = [int(i) for i in log_dir_result["log_dir"]]
#         # check worker installing
#         if worker_list !=None:
#             if check_worker_dir_and_install(workspace_name, deployment_name, worker_list)==False:
#                 message = "Worker Installing"
#             # return response(status=0, message="Worker Installing")

#         # result = get_result_from_history_file(workspace_name, deployment_name, worker_list)
#         # Get info ==============================================================================
#         result = get_result_from_history_file(workspace_name=workspace_name, deployment_name=deployment_name,
#                                             worker_list=worker_list, start_time=start_time, end_time=end_time, 
#                                             interval=interval, absolute_location=absolute_location, search_type=search_type)

#         # 다운로드 기능 ==============================================================================
#         if get_csv==True:
#             if len(result["error_log_list"])==0:
#                 raise DeploymentAbnormalHistoryCSVNotExistError
#                 # return response(status=0, message="No abnormal history result")
#             csv_result=[]
#             csv_result.append(list(result["error_log_list"][0].keys()))
#             for error_dic in result["error_log_list"]:
#                 csv_result.append(list(error_dic.values()))
#             return common.csv_response_generator(data_list=csv_result)
#             # return response(status=1, result=csv_result, message="Success getting abnormal history csv")
#         return response(status=1, result=result, message=message)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="get dashboard history error")

# def get_result_from_history_file(workspace_name, deployment_name, worker_list, start_time, end_time, interval, 
#                                 absolute_location, search_type):
#     history_list=[]
#     ndigits=5
#     processing_response_key_list = ["min", "max", "average", "median", "99", "95", "90"]
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]

#     if worker_list!=None:
#         for deployment_worker_id in worker_list:
#             deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
#                                                                                  workspace_name=workspace_name, 
#                                                                                 deployment_name=deployment_name, 
#                                                                                 deployment_worker_id=deployment_worker_id)
#             if search_type=="range":
#                 history_file_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_HISTORY_FILE_NAME)
#                 history_file_back_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_HISTORY_BACK_FILE_NAME)
#             else:
#                 history_file_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_LIVE_HISTORY_FILE_NAME)
#                 history_file_back_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_LIVE_HISTORY_BACK_FILE_NAME)

#             if os.path.exists(history_file_path):
#                 data = common.load_json_file(file_path=history_file_path)
#                 if data is not None:
#                     history_list.append(data)
#                 else:
#                     data = common.load_json_file(file_path=history_file_back_path)
#                     if data is not None:
#                         history_list.append(data)
#                     else:
#                         raise Exception("Json Decode error")
#                 # with open(history_file_path, "r") as f:
#                 #     # history_dic=json.load(f)
#                 #     history_list.append(json.load(f))

#     # from datetime import datetime, timedelta
#     time_variable_result = get_time_variables(start_time, end_time, interval, absolute_location)
#     start_timestamp = time_variable_result["start_timestamp"]
#     # end_timestamp=time_variable_result["end_timestamp"]
#     additional_start_sec = time_variable_result["additional_start_sec"]
#     # additional_start_count=time_variable_result["additional_start_count"]
#     total_idx_count = time_variable_result["total_idx_count"]
    
#     # 기본 time 만 포함한 graph 틀
#     result = []
#     # 초기 gpu list 받기
#     gpu_num_list = []
#     if len(history_list) > 0 :
#         for result_dic in history_list:
#             key_list = list(result_dic.keys())
#             if len(key_list)>0:
#                 graph_result = result_dic[key_list[0]]["graph_result"]
#                 if len(graph_result)>0:
#                     tmp_num_list = list(graph_result["gpu_resource"].keys())
#                     gpu_num_list = tmp_num_list if len(tmp_num_list)>len(gpu_num_list) else gpu_num_list

#     # 앞에 추가 start sec 이 있는경우
#     if additional_start_sec > 0:
#         for i in range(total_idx_count):
#             time_stamp = start_timestamp+interval*(i-1)+additional_start_sec
#             dic = get_default_api_monitor_graph_result(time=time_stamp, gpu_num_list=gpu_num_list, 
#                                                         interval=interval, search_type=search_type, 
#                                                         processing_response_key_list=processing_response_key_list)
#             if len(gpu_num_list)>=1:
#                 for gpu_num in gpu_num_list:
#                     dic["gpu_resource"][gpu_num]["gpu_memory_total"]=[]
#                     dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=[]
#                     dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=[]
#                     dic["gpu_resource"][gpu_num]["average_util_gpu"]=[]
#                     dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=[]
#                     dic["gpu_resource"][gpu_num]["count"]=[]
#             result.append(dic)
#         # 첫번째 시간 start_time_obj 로 받기
#         result[0]["time"] = start_timestamp
#     # 앞에 추가 sec 이 없는 경우
#     else:
#         for i in range(total_idx_count):
#             time_stamp = start_timestamp+interval*i
#             dic = get_default_api_monitor_graph_result(time=time_stamp, gpu_num_list=gpu_num_list,
#                                                         interval=interval, search_type=search_type, 
#                                                         processing_response_key_list=processing_response_key_list)
#             if len(gpu_num_list)>=1:
#                 for gpu_num in gpu_num_list:
#                     dic["gpu_resource"][gpu_num]["gpu_memory_total"]=[]
#                     dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=[]
#                     dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=[]
#                     dic["gpu_resource"][gpu_num]["average_util_gpu"]=[]
#                     dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=[]
#                     dic["gpu_resource"][gpu_num]["count"]=[]
#             result.append(dic)
#     key_list = list(result[0].keys())
#     rm_key_list = ["time", "time_local", "gpu_resource", "worker_count", "time_list", "error_rate", "nginx_error_rate", "monitor_error_rate"]
#     for res_key in ["processing_time", "response_time"]:
#         for key in processing_response_key_list:
#             rm_key_list.append("{}_{}".format(key, res_key))
#     for rm_k in rm_key_list:
#         key_list.remove(rm_k)
#     if len(gpu_num_list)>=1:
#         key_gpu_list = list(result[0]["gpu_resource"]['0'].keys())

#     nginx_access_count_info={}
#     error_log_list=[]
#     total_code_dic={}
#     processing_response_key_list_count = ["min", "max", "average", "median", "99", "95", "90", "count"]
#     response_value_list = [[] for i in processing_response_key_list_count]
#     processing_value_list = [[] for i in processing_response_key_list_count]
#     response_time_info={
#         "response_time":dict(zip(processing_response_key_list_count, response_value_list)),
#         "processing_time":dict(zip(processing_response_key_list_count, processing_value_list)),
#         "time":[]
#     }
#     # result 내의 result_dic 에 각 값의 list 담기
#     for result_dic in result:
#         time_iter=0
#         for t_stamp in result_dic["time_list"]:

#             time_str = str(t_stamp)
#             for history_dic in history_list:
#                 if history_dic.get(time_str) !=None:
#                     graph_result = history_dic[time_str]["graph_result"]
#                     for key in key_list:
#                         append_value = graph_result[key]
#                         result_dic[key].append(append_value if append_value!=[] else 0)
#                     if len(gpu_num_list)>=1:
#                         for gpu_num in gpu_num_list:
#                             if graph_result["gpu_resource"].get(gpu_num)!=None:
#                                 for key_gpu in key_gpu_list:
#                                     append_value = graph_result["gpu_resource"][gpu_num][key_gpu]
#                                     result_dic["gpu_resource"][gpu_num][key_gpu].append(append_value if append_value!=[] else 0)
#                     result_dic["worker_count"][time_iter]+=1
#                     error_log_list.extend(history_dic[time_str]["error_log_list"])

#                     for key in history_dic[time_str]["total_code_dic"].keys():
#                         if total_code_dic.get(key)!=None:
#                             for detail_key in history_dic[time_str]["total_code_dic"][key].keys():
#                                 if total_code_dic[key].get(detail_key) != None:
#                                     total_code_dic[key][detail_key]+=history_dic[time_str]["total_code_dic"][key][detail_key]
#                                 else:
#                                     total_code_dic[key][detail_key]=history_dic[time_str]["total_code_dic"][key][detail_key]
#                         else:
#                             total_code_dic[key]=history_dic[time_str]["total_code_dic"][key]
                            
#                     for key in history_dic[time_str]["nginx_access_count_info"].keys():
#                         if nginx_access_count_info.get(key)!=None:
#                             nginx_access_count_info[key]+=history_dic[time_str]["nginx_access_count_info"][key]
#                         else:
#                             nginx_access_count_info[key]=history_dic[time_str]["nginx_access_count_info"][key]
#                     for res_key in ["processing_time", "response_time"]:
#                         for key in processing_response_key_list:
#                             # response_time_info[res_key][key].append(history_dic[time_str]["total_info"][res_key][key])
#                             result_dic["{}_{}".format(key,res_key)].append(history_dic[time_str]["total_info"][res_key][key])
#             time_iter+=1
#     # list 값들 합치기 (average or sum)
#     if len(gpu_num_list)>=1:
#         key_gpu_list.remove("count")
#         key_gpu_list.remove("gpu_memory_total")
#     cpu_key_list=["average_mem_usage_per", "average_cpu_usage_on_pod"]
#     # api_response_key_list=[i+"_response_time" for i in ["min", "max", "average"]]
#     # nginx_response_key_list=[i+"_nginx_response_time" for i in ["min", "max", "average"]]
#     api_response_key_list=[]
#     nginx_response_key_list=[]
#     for key in processing_response_key_list:
#         nginx_response_key_list.append("{}_{}".format(key, "response_time"))
#         api_response_key_list.append("{}_{}".format(key, "processing_time"))
#     count_dic = {"processing_time":"success_count", "response_time":"nginx_count"}

#     total_error_count_list=[]
#     total_call_count_list=[]
#     nginx_error_count_list=[]
#     monitor_error_count_list=[]
#     monitor_call_count_list=[]
#     for result_dic in result:
#         del result_dic["time_list"]
#         result_dic["worker_count"]=max(result_dic["worker_count"])
#         monitor_count = sum(result_dic["monitor_count"])
#         success_count = sum(result_dic["success_count"])
#         nginx_count=sum(result_dic["nginx_count"])
#         result_dic["error_count"]=sum(result_dic["error_count"])
#         result_dic["nginx_error_count"]=sum(result_dic["nginx_error_count"])
#         result_dic["monitor_error_count"]=sum(result_dic["monitor_error_count"])
#         # result_dic["error_rate"]=round(result_dic["error_count"]/nginx_count, ndigits)
#         # result_dic["nginx_error_rate"]=round(result_dic["nginx_error_count"]/nginx_count, ndigits)
#         # result_dic["monitor_error_rate"]=round(result_dic["monitor_error_count"]/count, ndigits)
#         if nginx_count>0:
#             range_list=list(range(len(result_dic["nginx_count"])))
#             result_dic["error_rate"]=round(result_dic["error_count"]/(nginx_count+result_dic["error_count"]), ndigits)
#             result_dic["nginx_error_rate"]=round(result_dic["nginx_error_count"]/(nginx_count+result_dic["error_count"]), ndigits)
#             for key in nginx_response_key_list:
#                 logic=key.split("_")[0]
#                 if logic=="average":
#                     average_dic = [result_dic[key][i]*result_dic["nginx_count"][i] for i in range_list if result_dic["nginx_count"][i]>0]
#                     result_dic[key]=round(sum(average_dic)/nginx_count, ndigits)
#                 elif logic in [ "99", "95", "90"]:
#                     result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic="median", ndigits=ndigits)

#                 else:
#                     result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic=logic, ndigits=ndigits)
#         else:
#             for key in nginx_response_key_list:
#                 result_dic[key]=0
#         if monitor_count>0:
#             result_dic["monitor_error_rate"]=round(result_dic["monitor_error_count"]/monitor_count, ndigits)
#             range_list=list(range(len(result_dic["monitor_count"])))
#             for key in cpu_key_list:
#                 average_dic=[result_dic[key][i]*result_dic["monitor_count"][i] for i in range_list]
#                 result_dic[key]=round(sum(average_dic)/monitor_count, ndigits)
#             if len(gpu_num_list)>=1:
#                 for gpu_num in gpu_num_list:
#                     for key in key_gpu_list:
#                         if sum(result_dic["gpu_resource"][gpu_num]["count"])>0:
#                             gpu_range_list=range(len(result_dic["gpu_resource"][gpu_num]["count"]))
#                             average_dic=[result_dic["gpu_resource"][gpu_num][key][i]*result_dic["gpu_resource"][gpu_num]["count"][i] for i in gpu_range_list]
#                             result_dic["gpu_resource"][gpu_num][key]=round(sum(average_dic)/sum(result_dic["gpu_resource"][gpu_num]["count"]), ndigits)
#                         else:
#                             result_dic["gpu_resource"][gpu_num][key]=0
#                     result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]=sum(set(result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]))
#                     result_dic["gpu_resource"][gpu_num]["count"]=sum(result_dic["gpu_resource"][gpu_num]["count"])
#         else:
#             for key in cpu_key_list:
#                 result_dic[key]=0
#             if len(gpu_num_list)>=1:
#                 for gpu_num in gpu_num_list:
#                     for key in key_gpu_list:
#                         result_dic["gpu_resource"][gpu_num][key]=0
#                     result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]=sum(set(result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]))
#                     result_dic["gpu_resource"][gpu_num]["count"]=sum(result_dic["gpu_resource"][gpu_num]["count"])
#         if success_count>0:
#             range_list=list(range(len(result_dic["success_count"])))
#             for key in api_response_key_list:
#                 logic=key.split("_")[0]
#                 if logic=="average":
#                     average_dic = [result_dic[key][i]*result_dic["success_count"][i] for i in range_list if result_dic["success_count"][i]>0]
#                     result_dic[key]=sum(average_dic)/success_count
#                 elif logic in [ "99", "95", "90"]:
#                     result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic="median", ndigits=ndigits)
#                 else:
#                     result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic=logic, ndigits=ndigits)
#         else:
#             for key in api_response_key_list:
#                 result_dic[key]=0
        
#         result_dic["monitor_count"]=monitor_count
#         result_dic["success_count"]=success_count
#         result_dic["nginx_count"]=nginx_count
#         total_call_count_list.append(result_dic["nginx_count"]+result_dic["nginx_error_count"])
#         total_error_count_list.append(result_dic["error_count"])
#         nginx_error_count_list.append(result_dic["nginx_error_count"])
#         monitor_error_count_list.append(result_dic["monitor_error_count"])
#         monitor_call_count_list.append(result_dic["monitor_count"])

#         # for key in ["min", "max", "average"]:
#             # response_time_info["processing_time"][key].append(result_dic[key+"_response_time"])
#             # response_time_info["response_time"][key].append(result_dic[key+"_nginx_response_time"])


#         for res_key in ["processing_time", "response_time"]:
#             response_time_info[res_key]["count"].append(result_dic[count_dic[res_key]])
#             for key in processing_response_key_list:
#                 response_time_info[res_key][key].append(result_dic["{}_{}".format(key,res_key)])
#                 # response_time_info[res_key][key].append(result_dic["{}_{}".format(key,res_key)])

#         response_time_info["time"].append(result_dic["time"])

#     # print("response_time_info: ",response_time_info)
#     for key in ["processing_time", "response_time"]:
#         response_time_info[key]["total_average"]=[response_time_info[key]["average"][i]*response_time_info[key]["count"][i] 
#                         for i in range(len(response_time_info[key]["count"])) if response_time_info[key]["count"][i]>0]
#         if len(response_time_info[key]["total_average"])>0:
#             response_time_info[key]["total_average"]=sum(response_time_info[key]["total_average"])/sum(response_time_info[key]["count"])
#         else:
#             response_time_info[key]["total_average"]=0
#         if len(response_time_info[key]["max"])>0:
#             max_idx = response_time_info[key]["max"].index(max(response_time_info[key]["max"]))
#             response_time_info[key]["max_time"]=response_time_info["time"][max_idx]
#     total_error_rate_list=[total_error_count_list[i]/total_call_count_list[i] for i in range(total_idx_count) if total_error_count_list[i]>0]
#     nginx_error_rate_list=[nginx_error_count_list[i]/total_call_count_list[i] for i in range(total_idx_count) if nginx_error_count_list[i]>0]
#     monitor_error_rate_list=[monitor_error_count_list[i]/monitor_call_count_list[i] for i in range(total_idx_count) if monitor_error_count_list[i]>0]

#     return_result = {
#         "graph_result":result,
#         "nginx_access_count_info": nginx_access_count_info,
#         "error_log_list": error_log_list,
#         "code_list": total_code_dic,
#         "total_info":{
#             "call":{
#                 "total":sum(total_call_count_list),
#                 "min":get_statistic_result([i for i in total_call_count_list if i>0], "min", ndigits),
#                 "max":get_statistic_result(total_call_count_list, "max", ndigits)
#             },
#             "abnormal":{
#                 "total":{
#                     "count":sum(total_error_count_list),
#                     "max_count":get_statistic_result(total_error_count_list, "max", ndigits),
#                     "rate":round(sum(total_error_count_list)/sum(total_call_count_list), ndigits) if sum(total_call_count_list)>0 else 0,
#                     "max_rate":get_statistic_result(total_error_rate_list, "max", ndigits)
#                 },
#                 "nginx":{
#                     "count":sum(nginx_error_count_list),
#                     "max_count":get_statistic_result(nginx_error_count_list, "max", ndigits),
#                     "rate":round(sum(nginx_error_count_list)/sum(total_call_count_list), ndigits) if sum(total_call_count_list)>0 else 0,
#                     "max_rate":get_statistic_result(nginx_error_rate_list, "max", ndigits)
#                 },
#                 "api":{
#                     "count":sum(monitor_error_count_list),
#                     "max_count":get_statistic_result(monitor_error_count_list, "max", ndigits),
#                     "rate":round(sum(monitor_error_count_list)/sum(monitor_call_count_list), ndigits) if sum(monitor_call_count_list)>0 else 0,
#                     "max_rate":get_statistic_result(monitor_error_rate_list, "max", ndigits)
#                 }
#             },
#             "processing_time":{
#                 "average":round(response_time_info["processing_time"]["total_average"], ndigits),
#                 "median":get_statistic_result([i for i in response_time_info["processing_time"]["median"] if i>0], "median", ndigits),
#                 "99":get_statistic_result([i for i in response_time_info["processing_time"]["99"] if i>0], "median", ndigits),
#                 "95":get_statistic_result([i for i in response_time_info["processing_time"]["95"] if i>0], "median", ndigits),
#                 "90":get_statistic_result([i for i in response_time_info["processing_time"]["90"] if i>0], "median", ndigits),
#                 "min":get_statistic_result([i for i in response_time_info["processing_time"]["min"] if i>0], "min", ndigits),
#                 "max":get_statistic_result(response_time_info["processing_time"]["max"], "max", ndigits),
#                 "max_timestamp":response_time_info["processing_time"].get("max_time")
#             },
#             "response_time":{
#                 "average":round(response_time_info["response_time"]["total_average"], ndigits),
#                 "median":get_statistic_result([i for i in response_time_info["response_time"]["median"] if i>0], "median", ndigits),
#                 "99":get_statistic_result([i for i in response_time_info["response_time"]["99"] if i>0], "median", ndigits),
#                 "95":get_statistic_result([i for i in response_time_info["response_time"]["95"] if i>0], "median", ndigits),
#                 "90":get_statistic_result([i for i in response_time_info["response_time"]["90"] if i>0], "median", ndigits),
#                 "min":get_statistic_result([i for i in response_time_info["response_time"]["min"] if i>0], "min", ndigits),
#                 "max":get_statistic_result(response_time_info["response_time"]["max"], "max", ndigits),
#                 "max_timestamp":response_time_info["response_time"].get("max_time")
#             }
#         }
#     }
#     return return_result

# def get_time_variables(start_time, end_time, interval, absolute_location):
#     from datetime import datetime, timedelta
#     # time string type 에서 datetime type 으로 변경
#     # start_time_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
#     # end_time_obj = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
#     start_timestamp = common.date_str_to_timestamp(start_time, POD_RUN_TIME_DATE_FORMAT)
#     end_timestamp = common.date_str_to_timestamp(end_time, POD_RUN_TIME_DATE_FORMAT)
#     # 프론트 요청에서 time 범위 꼬이는 경우가 자주 발생해 예외처리
#     if start_timestamp>end_timestamp:
#         end_timestamp=start_timestamp+interval
#     # interval time delta 로 변경
#     # interval_timedelta = timedelta(seconds = interval)
#     additional_start_sec = 0
#     if absolute_location:
#         # interval 기준으로 범위 나누기: start time 의 timestamp 을 interval 로 나누어 나머지값 구함
#         additional_start_sec = interval-start_timestamp%interval
#     # additional_start_sec = timedelta(seconds = additional_start_sec)
#     total_idx_count = (end_timestamp-start_timestamp-additional_start_sec)//interval
#     additional_end_count = 1 if (end_timestamp-start_timestamp-additional_start_sec)%interval else 0
#     additional_start_count = 1 if additional_start_sec else 0
#     total_idx_count += additional_end_count+additional_start_count
#     result = {
#         "start_timestamp":start_timestamp,
#         "end_timestamp":end_timestamp,
#         "additional_start_sec":additional_start_sec,
#         "additional_start_count":additional_start_count,
#         "total_idx_count":int(total_idx_count),
#     }
#     return result

# def get_default_api_monitor_graph_result(time, gpu_num_list, processing_response_key_list, 
#                                         interval=None, search_type="range"):
#     search_dic={
#         "range":600,
#         "live":1
#     }
#     dic = {
#         "time": time,
#         "time_local": 0,
#         "monitor_count": [],
#         "nginx_count": [], # nginx count
#         "success_count": [],
#         "error_count": [], # abnormal processing
#         "monitor_error_count": [], # abnormal processing api
#         "nginx_error_count": [], # abnormal processing nginx
#         "error_rate": 0,
#         "monitor_error_rate": 0,
#         "nginx_error_rate": 0,
#         "average_cpu_usage_on_pod": [], # cpu
#         "average_mem_usage_per": [], # ram
#         "worker_count": [0], # worker
#         "time_list":[time],
#         "gpu_resource":{}
#     }
#     for res_key in ["processing_time", "response_time"]:
#         for key in processing_response_key_list:
#             dic["{}_{}".format(key, res_key)]=[]
#     for gpu_num in gpu_num_list:
#         dic["gpu_resource"][gpu_num]={}
#         dic["gpu_resource"][gpu_num]["gpu_memory_total"]=0
#         dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=0
#         dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=0 # gpu mem
#         dic["gpu_resource"][gpu_num]["average_util_gpu"]=0 # gpu core
#         dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=0
#         dic["gpu_resource"][gpu_num]["count"]=0
#     if interval<=search_dic[search_type]:
#         return dic
#     else:
#         dic["time_list"]=[time+i*search_dic[search_type] for i in range(interval//search_dic[search_type])]
#         dic["worker_count"]=[0 for i in range(interval//search_dic[search_type])]
#         return dic

# # ==========================================================================
# # worker 상세 페이지
# # ==========================================================================
# # </worker/dashboard_history>
# # 워커 상세 페이지 - 상단 4개정보
# def get_deployment_worker_dashboard_status(deployment_worker_id): 
#     try:
#         # from utils.kube_pod_status import get_deployment_worker_status
#         # info = db.get_deployment_worker_name_info(deployment_worker_id=deployment_worker_id)
#         # workspace_name = info.get("workspace_name")
#         # deployment_name = info.get("deployment_name")
        
#         info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#         workspace_name = info["workspace_name"]
#         deployment_name = info.get("deployment_name")
        
#         # get count info
#         total_info = get_deployment_api_total_count_info(worker_dir_list=[deployment_worker_id], 
#                                                         workspace_name=workspace_name, deployment_name=deployment_name)
#         # get run time
#         total_info["deployment_run_time"]=get_deployment_worker_run_time(workspace_name=workspace_name, deployment_name=deployment_name, 
#                                                                         deployment_worker_id=deployment_worker_id)
#         # get restart count
#         # pod_list = kube_data.get_pod_list()
#         # worker_pod_list=kube.find_kuber_item_name_and_item(item_list=pod_list, deployment_worker_id=deployment_worker_id)

#         # worker_pod_list=kube_new.get_deployment_worker_pod_list(deployment_worker_id=deployment_worker_id, namespace="default")

#         # if len(worker_pod_list)>0:
#         #     total_info["restart_count"]=parsing_pod_restart_count(pod=worker_pod_list[0])
#         # else:
#         #     total_info["restart_count"]="unknown"
#         result={
#             "total_info":total_info,
#             "worker_start_time":get_deployment_worker_run_start_time(workspace_name, deployment_name, deployment_worker_id)
#         }

#         return response(status=1, message="success getting worker dashboard status", result=result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="get worker dashboard status error")

# # </worker/dashboard_resource_graph>
# # 워커 상세 페이지 - cpu, ram 그래프
# # 워커당 시간 2초 오래걸림

# # worker_graph = dict()
# # lock = threading.Lock()
# # def loop_deployment_worker_resource_usgae_graph():
# #     global worker_graph
# #     while True:
# #         try:
# #             with lock:
# #                 # 현재의 worker_list를 가져옵니다.
# #                 worker_list = db_deployment.get_deployment_worker_list(running=True)
# #                 current_ids = set(i.get("id") for i in worker_list)

# #                 # 현재 존재하는 worker_id를 기준으로 worker_graph를 업데이트합니다.
# #                 for worker_id in list(worker_graph.keys()):
# #                     if worker_id not in current_ids:
# #                         # id_list에 존재하지 않는 worker_id를 worker_graph에서 제거합니다.
# #                         del worker_graph[worker_id]

# #                 for i in worker_list:
# #                     deployment_worker_id = i.get("id")
# #                     worker_graph[deployment_worker_id] = get_deployment_worker_resource_usage_graph(deployment_worker_id=deployment_worker_id)["result"]
# #         except:
# #             pass
# #         time.sleep(1)
            
# # def get_loop_deployment_worker_resource_usgae_graph(deployment_worker_id):
# #     global worker_graph
# #     with lock:
# #         if deployment_worker_id in worker_graph:
# #             return worker_graph[deployment_worker_id]
# #         else:
# #             return {
# #                 POD_MEMORY_HISTORY_KEY : [],
# #                 POD_CPU_HISTORY_KEY : [],
# #                 POD_GPU_HISTORY_KET : None,

# #                 "cpu_cores": {
# #                     "cpu_cores_total" : None,
# #                     "cpu_cores_usage" : None
# #                 },
# #                 "ram": {
# #                     "ram_total": None, 
# #                     "ram_usage": None,
# #                 },
# #                 "gpus": None,
# #                 "network": None,
# #                 "status": {"status" : "stop"}
# #             }

# def get_deployment_worker_resource_usage_graph(deployment_worker_id, interval=None):
#     max_len = 300
#     # def get_gpu_history(pod_name):
#     #     def update_gpu_history_len(gpu_history):
#     #         for gpu_id in gpu_history.keys():
#     #             gpu_history[gpu_id] = gpu_history[gpu_id][-max_len:]

#     #     gpu_history = {}
#     #     # gpu_history_data = kube.get_pod_gpu_usage_history_info(pod_list=pod_list, deployment_worker_id=deployment_worker_id)
#     #     try:
#     #         # gpu_history_data = kube_new.get_pod_gpu_usage_history_info(deployment_worker_id=deployment_worker_id, namespace=workspace_namespace)
#     #         gpu_history_data = get_pod_gpu_usage_history_file(pod_name=pod_name)
#     #     except:
#     #         pass
        
#     #     if gpu_history_data is None:
#     #         return gpu_history
        
#     #     origin_log_len = len(gpu_history_data)
#     #     new_max_len = max_len
#     #     if origin_log_len > max_len:
#     #         new_max_len += (origin_log_len - max_len) % 10

#     #     gpu_history_data = gpu_history_data[-new_max_len:]
#     #     try:
#     #         for i, gpu_usage_data in enumerate(gpu_history_data):
#     #             # gpu_usage_data = json.loads(gpu_usage_data)
#     #             for key in gpu_usage_data.keys():
#     #                 if gpu_history.get(key) is None:
#     #                     gpu_history[key] = []
#     #                 if i >= max_len:
#     #                     break
#     #                 if i % 10 == 0:
#     #                     gpu_history[key].append({
#     #                         "x": i, #gpu_usage_data[key][TIMESTAMP_KEY],
#     #                         GPU_UTIL_KEY: gpu_usage_data[key][GPU_UTIL_KEY],
#     #                         GPU_MEM_UTIL_KEY: gpu_usage_data[key][GPU_MEM_UTIL_KEY],
#     #                         GPU_MEM_USED_KEY: gpu_usage_data[key][GPU_MEM_USED_KEY],
#     #                         GPU_MEM_TOTAL_KEY: gpu_usage_data[key][GPU_MEM_TOTAL_KEY]
#     #                     })
#     #     except:
#     #         traceback.print_exc()
#     #         print("OLD VER")
#     #         update_gpu_history_len(gpu_history)
            
#     #         return gpu_history
        
#     #     update_gpu_history_len(gpu_history)
        
#     #     return gpu_history

#     # def get_cpu_ram_history(pod_name):
#     #     # def get_cpu_ram_history(pod_list, deployment_worker_id, workspace_namespace):
#     #     # pod_usage_history = kube.get_pod_cpu_ram_usage_history_info(pod_list=pod_list, deployment_worker_id=deployment_worker_id)
        
#     #     # pod_usage_history = kube_new.get_pod_cpu_ram_usage_history_info(namespace=workspace_namespace, deployment_worker_id=deployment_worker_id)

#     #     pod_usage_history = get_pod_cpu_ram_usage_history_file(pod_name=pod_name)

#     #     if pod_usage_history is None:
#     #         return {
#     #             POD_CPU_HISTORY_KEY: [],
#     #             POD_MEMORY_HISTORY_KEY: []
#     #         }
        
#     #     origin_log_len = len(pod_usage_history)
#     #     new_max_len = max_len
#     #     if origin_log_len > max_len:
#     #         new_max_len += (origin_log_len - max_len) % 10
#     #     cpu_history = []
#     #     mem_history = []
#     #     pod_usage_history = pod_usage_history[-new_max_len:]
#     #     cpu_usage_on_pod = []
#     #     mem_usage = []
#     #     mem_usage_per = []
#     #     for i, pod_usage_data in enumerate(pod_usage_history):
#     #         # pod_usage_data = json.loads(pod_usage_data)
#     #         if i >= max_len:
#     #             break
#     #         if i % 10 == 0:
#     #             cpu_history.append({
#     #                 "x": i,#pod_usage_data[TIMESTAMP_KEY],
#     #                 CPU_USAGE_ON_POD_KEY: min(100, round(float(pod_usage_data[CPU_USAGE_ON_POD_KEY]), 2))
#     #             })
#     #             mem_history.append({
#     #                 "x": i, #pod_usage_data[TIMESTAMP_KEY],
#     #                 MEM_USAGE_KEY: round(float(pod_usage_data[MEM_USAGE_KEY]) ,2),
#     #                 MEM_LIMIT_KEY: pod_usage_data[MEM_LIMIT_KEY] / (1024*1024*1024) ,
#     #                 MEM_USAGE_PER_KEY: round(float(pod_usage_data[MEM_USAGE_PER_KEY]), 2)
#     #             })

#     #     return {
#     #         POD_MEMORY_HISTORY_KEY: mem_history[-500:],
#     #         POD_CPU_HISTORY_KEY: cpu_history[-500:]
#     #     }
#     # pod_list = kube.kube_data.get_pod_list()
#     # deployment_worker_status = kube.get_deployment_worker_status(deployment_worker_id=deployment_worker_id, pod_list=pod_list)
#     worker_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#     workspace_id = worker_info.get("workspace_id")
#     deployment_id = worker_info.get("deployment_id")
#     # deployment_id = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
    
#     workspace_namespace = JF_SYSTEM_NAMESPACE + "-" + str(workspace_id)
#     # deployment_worker_status = kube_new.get_deployment_pod_status(namespace=workspace_namespace, deployment_worker_id=deployment_worker_id)
#     # deployment_worker_status = deployment_redis.get_deployment_worker_status(workspace_id=workspace_id, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id)
#     deployment_list = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
#     redis_deployment_worker_status = json.loads(deployment_list).get("deployment")

#     deployment_worker_status = {"status" : "stop"}
#     if redis_deployment_worker_status is not None:
#         deployment_list = redis_deployment_worker_status.get(str(deployment_id))
#         if deployment_list is not None:
#             if str(deployment_worker_id) not in deployment_list:
#                 deployment_worker_status = {"status" : "stop"}
#             else:
#                 deployment_worker_status = deployment_list.get(str(deployment_worker_id))
#     # pod_name = worker_info.get("api_path") +"-" + str(deployment_worker_id) 
#     # pod_all_resource_info = get_pod_all_resource(deployment_worker_id=deployment_worker_id, status=deployment_worker_status["status"], 
#     #                                              workspace_namespace=workspace_namespace, pod_name=pod_name)

#     # cpu_ram_history = get_cpu_ram_history(pod_list=pod_list, deployment_worker_id=deployment_worker_id)    
#     # cpu_ram_history = get_cpu_ram_history(deployment_worker_id=deployment_worker_id, workspace_namespace=workspace_namespace)
#     # cpu_ram_history = get_cpu_ram_history(pod_name=pod_name)
    
#     tmp_redis_worker_resource = redis_client.hget(DEPLOYMENT_WORKER_RESOURCE, str(deployment_worker_id))
#     if tmp_redis_worker_resource is not None:
#         redis_worker_resource = json.loads(tmp_redis_worker_resource)
#     else:
#         print("redis_worker_resource: ", tmp_redis_worker_resource)
#         redis_worker_resource = {'cpu_cores' :  {'total' : 0, 'usage' : 0, 'percentage' : 0}, 'ram' : {'total' : 0, 'usage' : 0, 'percentage' : 0}, 'gpus' : 0}

#     history = {
#         # POD_MEMORY_HISTORY_KEY : cpu_ram_history[POD_MEMORY_HISTORY_KEY],
#         # POD_CPU_HISTORY_KEY : cpu_ram_history[POD_CPU_HISTORY_KEY],
#         # POD_GPU_HISTORY_KET : get_gpu_history(pod_name=pod_name),

#         "cpu_cores": {
#             "cpu_cores_total" : redis_worker_resource['cpu_cores']["total"], 
#             "cpu_cores_usage" : redis_worker_resource['cpu_cores']["percentage"]
#         },
#         "ram": {
#             "ram_total": byte_to_gigabyte(float(redis_worker_resource["ram"]['total'])),
#             "ram_usage": redis_worker_resource["ram"]['percentage']
#         },
#         "gpus": redis_worker_resource["gpus"],
#         "cpu_history" : redis_worker_resource["cpu_history"],
#         "mem_history" : redis_worker_resource["mem_history"],
#         "gpu_history" : redis_worker_resource["gpu_history"],
#         "network": None, # TODO 삭제
#         "status": deployment_worker_status
#     }
#     return response(status=1, result=history)

# # kube 대체
# def get_pod_cpu_ram_usage_history_file(pod_name):
#     try:
#         # {'cpu_usage_on_node': 0.773808, 'cpu_usage_on_pod': 0.773808, 'mem_usage': 2401140736, 'mem_limit': 10737418240, 'mem_usage_per': 22.3624, 'timestamp': 1666070127, 'cpu_cores_on_pod': 12}
#         # resource_history_data_path = POD_CPU_RAM_RESOURCE_USAGE_HISTORY_FILE_PATH_IN_JF_API.format(pod_name=pod_name)
        
#         resource_history_data_path = get_pod_resource_usage_path(pod_name=pod_name) + "/resource_usage_history.log"
        
#         # with open(resource_history_data_path, "r") as f:
#         #     resource_history_data = f.readlines()
#             # history_data_list = []
#             # for data in resource_history_data:
#             #     history_data_list.append(json.loads(data))
#         resource_history_data = common.load_json_file_to_list(file_path=resource_history_data_path)
#         return resource_history_data
#     except FileNotFoundError:
#         return []
#     except json.decoder.JSONDecodeError:
#         return []
#     except Exception as e:
#         traceback.print_exc()
#         return []

# def get_pod_gpu_usage_history_file(pod_name):
#     try:
#         # { "0": { "util_gpu": 0, "util_memory": 0, "memory_free": 8643, "memory_used": 2535, "memory_total": 11178, "timestamp": 1664266328 } }
#         resource_data_path = POD_GPU_USAGE_HISTORY_FILE_PATH_IN_JF_API.format(pod_name=pod_name)
#         # with open(resource_data_path, "r") as f:
#         #     resource_data = f.readlines()
#         resource_data = common.load_json_file_to_list(file_path=resource_data_path)
#         return resource_data
#     except FileNotFoundError:
#         # GPU가 없는 경우도 있음.. 그러면 안찍음
#         return None

# # </worker/dashboard_worker_info>
# # 워커 상세 페이지 - 워커정보 자세히 보기
# def get_deployment_worker_dashboard_worker_info(deployment_worker_id):
#     def get_deployment_running_info(id, is_worker=False):
#         # if is_worker:
#         #     deployment_version_info = db_deployment.get_deployment_worker_pod_run_info(id)
#         # else:
#         #     deployment_version_info= db_deployment.get_deployment_pod_run_info(id)
#         # deployment_version_info.update(deployment_version_info["deployment_template_info"])
#         # deployment_version_info["type"] = deployment_version_info[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY]
#         # if deployment_version_info["type"]==DEPLOYMENT_TYPE_A:
#         #     additional_info = db.get_deployment_worker_built_in_pod_run_info(deployment_version_info["built_in_model_id"])
#         #     if additional_info != None:
#         #         deployment_version_info.update(additional_info)
#         #     deployment_version_info["checkpoint"] = deployment_version_info.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY)
#         # elif deployment_version_info["type"]==DEPLOYMENT_TYPE_B:
#         #     run_code_info = deployment_version_info.get(DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY)
#         #     if run_code_info != None:
#         #         deployment_version_info["run_code"] = run_code_info.get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY)
#         # del deployment_version_info["deployment_template_info"]


#         deployment_version_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)


#         return deployment_version_info


#     def check_deployment_worker_version_change(deployment_worker_id):
#         # from deployment import get_deployment_running_info_o
#         # from deployment.service import get_deployment_running_info
#         # TODO 추후 db.get_deployment_id_from_worker_id 로 변경 예정
#         deployment_worker_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#         deployment_id = deployment_worker_info.get("deployment_id")
#         # get_running_info=get_deployment_running_info_o
#         # if deployment_worker_info["template_id"] !=None:
#         # get_running_info=get_deployment_running_info

#         deployment_worker_running_info = get_deployment_running_info(id=deployment_worker_id, is_worker=True)
#         deployment_running_info = get_deployment_running_info(id=deployment_id)
#         result={
#             "changed": False,
#             "changed_items": []
#         }
#         if deployment_worker_running_info!=deployment_running_info:

#             # added_list=[]
#             # dropped_list=[]
#             modified_list = []
#             # if set(deployment_worker_running_info.keys())!=set(deployment_running_info.keys()):
#             #     added_list = list(set(deployment_worker_running_info.keys())-set(deployment_running_info.keys()))
#             #     dropped_list = list(set(deployment_running_info.keys())-set(deployment_worker_running_info.keys()))
#             for key in deployment_worker_running_info.keys():
#                 if deployment_running_info.get(key)!=None:
#                     if deployment_worker_running_info[key]!=deployment_running_info[key]:
#                         modified_list.append({
#                             "item": key, 
#                             "latest_version": deployment_running_info[key], # 실행 시 반영 될 정보
#                             "current_version": deployment_worker_running_info[key] # 이미 실행 된 정보
#                         })
#             if len(modified_list)>0:
#                 result["changed"]= True
#                 # result["changed_items"]={"added":added_list, "droppped":dropped_list, "modified": modified_list}
#                 result["changed_items"]=modified_list
#         return result

#     # from utils.kube_pod_status import get_deployment_worker_status
#     try:
#         info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)

#         job_info = "{}/{}".format(info.get("job_name"), info.get("job_group_index")) if info.get("job_name") !=None else None
#         # deployment_worker_running_info = get_deployment_running_info(id=deployment_worker_id, is_worker=True)
#         # pod_list = kube.kube_data.get_pod_list()
#         # status = kube_new.get_deployment_pod_status(deployment_worker_id=deployment_worker_id)
#         # pod_all_resource_info = get_pod_all_resource(deployment_worker_id=deployment_worker_id, status=status)
#         # version_type = deployment_worker_running_info.get("type")
        
#         # checkpoint = deployment_worker_running_info.get("checkpoint")
#         # if checkpoint!=None and version_type==DEPLOYMENT_TYPE_A:
#         #     if job_info !=None:
#         #         # checkpoint = checkpoint[len(job_info)+1:]
#         #         checkpoint = checkpoint.split(job_info)[-1]
#         result = {
#             "description": info["description"],
#             "resource_info": {
#                 # "configuration" : "[temp]NVIDIA GeForce GTX 1080 Ti x 2ea,NVIDIA GeForce RTX 3060".split(","),
#                 "configuration": [info["gpu_name"]], # info.get("configurations").split(","),
#                 # "node_name": "",# info.get("node_name"),
#                 "cpu_cores": None, # pod_all_resource_info["cpu_cores"],
#                 "ram": None, # pod_all_resource_info["ram"]
#             },
#             "version_info": {
#                 "create_datetime": info["start_datetime"],
#                 "docker_image": info["image_name"],
#                 "type": None, # version_type,
#                 "training_name": info["project_name"], # deployment_worker_running_info.get("training_name"),
#                 # "built_in_model_name": info["built_in_model_name"], # deployment_worker_running_info.get("built_in_model_name"),
#                 "run_code": json.loads(info["command"])["script"] if info["command"] is not None else None, # deployment_worker_running_info.get("run_code"),
#                 "job_info": None, # job_info,
#                 "checkpoint": None, # checkpoint,
#                 "end_datetime": info["end_datetime"]
#             },
#             "version_info_changed": check_deployment_worker_version_change(deployment_worker_id)
#             # "running_info": deployment_worker_running_info
#         }
#         return response(status=1, result=result)
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Dashboard Worker info get error")

# def get_pod_all_resource(deployment_worker_id, status,  workspace_namespace, pod_name):
#     """
#     deployment worker resource 정보 조회
#     """    
#     cpu_cores = None # 할당 받은 총 cpu core 개수
#     cpu_cores_usage_on_node = None # 노드 대비 cpu core 사용량 (0 ~ 1)
#     cpu_cores_usage_on_pod = None # Pod 할당 받은 대비 cpu core 사용량 (0 ~ 1)
#     ram = None # 할당 받은 RAM SIZE (Byte)
#     ram_usage_per = None
#     network = None
#     gpus = {}

#     if status in KUBER_NOT_RUNNING_STATUS:
#         return {
#             "cpu_cores": cpu_cores,
#             "cpu_cores_usage": cpu_cores_usage_on_pod,
#             "ram": ram,
#             "ram_usage_per": ram_usage_per,
#             "network": network,
#             "gpus": gpus
#         }

#     # pod_name = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)["api_path"] +"-" + str(deployment_worker_id) 
#     pod_resource_info = get_pod_resource_info(deployment_worker_id=deployment_worker_id, namespace=workspace_namespace)
#     pod_resource_usage_info = get_pod_cpu_ram_usage_file(pod_name=pod_name)
#     pod_gpu_usage_info = get_pod_gpu_usage_file(pod_name=pod_name)


#     # CPU_USAGE_ON_NODE_KEY = "cpu_usage_on_node" # POD 내에서 NODE의 몇%인지 
#     # CPU_USAGE_ON_POD_KEY = "cpu_usage_on_pod" # POD 내에서 몇 %인지
#     # CPU_CORES_ON_POD_KEY = "cpu_cores_on_pod" # POD 내에서 코어 몇개 할당인지 

#     if pod_resource_info is not None:
#         # 총 자원 정보
#         cpu_cores = pod_resource_info["cpu"]
#         ram = pod_resource_info["memory"]

#         # POD 사용 정보
#         cpu_cores_usage_on_node = pod_resource_usage_info.get(CPU_USAGE_ON_NODE_KEY) if pod_resource_usage_info.get(CPU_USAGE_ON_NODE_KEY) is not None else "Unknown"
#         cpu_cores_usage_on_pod = pod_resource_usage_info.get(CPU_USAGE_ON_POD_KEY) if pod_resource_usage_info.get(CPU_USAGE_ON_POD_KEY) is not None else "Unknown"
#         ram_usage_per = pod_resource_usage_info.get(MEM_USAGE_PER_KEY) if pod_resource_usage_info.get(MEM_USAGE_PER_KEY) is not None else "Unknwon"
#         ram_usage_per = round(ram_usage_per, 2)
#         network = pod_resource_info[POD_NETWORK_INTERFACE_LABEL_KEY]


#     try:
#         if pod_gpu_usage_info is not None:
#             for k, v in pod_gpu_usage_info.items():
#                 # if k != "recordable":
#                 if v.get("recordable")==False:
#                     gpus[k] ={
#                         "utils_gpu": "unknown",
#                         "utils_memory": "unknown",
#                         "memory_used_ratio": "unknown",
#                         "memory_used": "",
#                         "memory_total": ""
#                     }
#                 else:
#                     util_gpu = v.get(GPU_UTIL_KEY)
#                     util_memory = v.get(GPU_MEM_UTIL_KEY)
#                     gpu_memory_free = v.get(GPU_MEM_FREE_KEY)
#                     gpu_memory_used = v.get(GPU_MEM_USED_KEY)
#                     gpu_memory_total= v.get(GPU_MEM_TOTAL_KEY)
#                     gpu_memory_used_ratio = None
#                     try:
#                         if gpu_memory_used is not None and gpu_memory_total is not None:
#                             gpu_memory_used_ratio = str(round(gpu_memory_used/gpu_memory_total * 100 ,2)) + "%"
#                     except Exception as e:
#                         traceback.print_exc()
#                         gpu_memory_used_ratio = "Error ({}/{})".format(gpu_memory_used, gpu_memory_total)
                        
#                     gpus[k] ={
#                         "utils_gpu": util_gpu,
#                         "utils_memory": util_memory,
#                         "memory_used_ratio": gpu_memory_used_ratio,
#                         "memory_used": gpu_memory_used,
#                         "memory_total": gpu_memory_total
#                     }
#                     # gpus.append("GPU-{} \n GPU util {}% \n MEM util {}% \n MEM INFO {}MB/{}MB".format(k, util_gpu, util_memory, gpu_memory_used, gpu_memory_total))
#                     # gpus.append()
#                     # gpus.append("GPU-{} \n GPU util {}% \n MEM util {}% \n MEM INFO {}MB/{}MB".format(k, util_gpu, util_memory, gpu_memory_used, gpu_memory_total))
#     except:
#         traceback.print_exc()
#         print("OLD VERSION Error")

#     return {
#         "cpu_cores": cpu_cores,
#         "cpu_cores_usage": cpu_cores_usage_on_pod,
#         "ram": ram,
#         "ram_usage_per": ram_usage_per,
#         "network": network,
#         "gpus": gpus
#     }

# def get_deployment_worker_run_time_info(workspace_name, deployment_name, deployment_worker_id, *args, **kwargs):
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#     deployment_worker_run_time_file_path = GET_POD_RUN_TIME_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     try:
#         data = common.load_json_file(file_path=deployment_worker_run_time_file_path, *args, **kwargs)
#         if data is not None:
#             run_time_info = data
#         else :
#             run_time_info = {}

#         # with open(deployment_worker_run_time_file_path, "r") as f:
#         #     run_time_data = f.read()
#         #     run_time_info = json.loads(run_time_data)
#     except:
#         return {}

#     return run_time_info

# def get_deployment_worker_run_time(workspace_name, deployment_name, deployment_worker_id):
#     run_time_info = get_deployment_worker_run_time_info(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     if run_time_info == {}:
#         return None
#     else :
#         current_start_time_ts = common.date_str_to_timestamp(run_time_info[POD_RUN_TIME_START_TIME_KEY])
#         current_end_time_ts = common.date_str_to_timestamp(run_time_info[POD_RUN_TIME_END_TIME_KEY])
#         return current_end_time_ts - current_start_time_ts

# def get_deployment_worker_run_start_time(workspace_name, deployment_name, deployment_worker_id):
#     from datetime import datetime
#     run_time_info = get_deployment_worker_run_time_info(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     if run_time_info == {}:
#         return datetime.strftime(datetime.now(), POD_RUN_TIME_DATE_FORMAT)
#     else :
#         return run_time_info[POD_RUN_TIME_START_TIME_KEY]

# # ##########################################################################
# # ==========================================================================
# # call chart
# # ==========================================================================
# def get_deployment_call_count_per_hour_chart(deployment_id, workspace_name, deployment_name):
#     log_per_hour_info_list = get_deployment_nginx_access_log_per_hour_list(deployment_id=deployment_id, workspace_name=workspace_name, deployment_name=deployment_name)
#     time_table = get_nginx_per_hour_time_table_dict(log_per_hour_info_list=log_per_hour_info_list)
#     return get_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)

# def get_deployment_nginx_access_log_per_hour_list(deployment_id, workspace_name, deployment_name):

#     deployment_worker_id_list = get_deployment_worker_list_from_folder(workspace_name=workspace_name, deployment_name=deployment_name)
#     worker_num_of_log_per_hour_info_list = []
#     for deployment_worker_id in deployment_worker_id_list:
#         per_hour_info_list = get_deployment_worker_nginx_access_log_per_hour_info_list(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         if per_hour_info_list:
#             worker_num_of_log_per_hour_info_list += per_hour_info_list
#     return worker_num_of_log_per_hour_info_list

# def get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id, workspace_name, deployment_name):

#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#     deployment_worker_nginx_access_log_per_hour_file_path = GET_POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     nginx_access_log_per_hour_info_list = []
#     try:
#         with open(deployment_worker_nginx_access_log_per_hour_file_path, "r") as f:
#             per_hour_data_list = f.readlines()
#             for per_hour_data in per_hour_data_list:
#                 nginx_access_log_per_hour_info_list.append(json.loads(per_hour_data))
#     except FileNotFoundError as fne:
#         return []
#     except json.decoder.JSONDecodeError as je:
#         return []
#     except Exception as e:
#         traceback.print_exc()
#         return []

#     return nginx_access_log_per_hour_info_list

# def get_nginx_per_hour_time_table_dict(log_per_hour_info_list, time_time_count=24):
#     if len(log_per_hour_info_list) == 0:
#         return {}
    
#     try:
#         sorted_log_per_hour_info_list = sorted(log_per_hour_info_list, key=lambda log_per_hour_info_list: (log_per_hour_info_list[DEPLOYMENT_NGINX_PER_TIME_KEY]))
#     except KeyError as ke:
#         traceback.print_exc()
#         return {}

#     last_time = sorted_log_per_hour_info_list[-1][DEPLOYMENT_NGINX_PER_TIME_KEY]
#     last_timestamp = common.date_str_to_timestamp(date_str=last_time, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)

#     time_table = {}
#     time_interval = 60 * 60 # test - (hour = 60 * 60)
#     # last 24 item time list
#     for i in range(time_time_count):
#         date_time = common.get_date_time(timestamp=last_timestamp - time_interval * i, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)
#         time_table[str(date_time)] = 0
        
#     return time_table

# def get_nginx_access_per_hour_chart(time_table, log_per_hour_info_list, data_key):
#     time_table = dict(time_table)
#     for data in log_per_hour_info_list:
#         try:
#             common.update_dict_key_count(dict_item=time_table, key=data[DEPLOYMENT_NGINX_PER_TIME_KEY], add_count=data[data_key], exist_only=True)        
#         except KeyError as ke:
#             # traceback.print_exc()
#             pass

#     chart_data = list(time_table.values())
#     chart_data.reverse()

#     # 최소 개수가 24개
#     if len(chart_data) < 24:
#         dummy = [0] * ( 24 - len(chart_data) )
#         chart_data = dummy + chart_data

#     return chart_data       

# def get_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_CALL_LOG_KEY)

# def get_median_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_RESPONSE_TIME_MEDIAN_KEY)

# def get_nginx_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)

# def get_api_monitor_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_API_MONITOR_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)

# def get_deployment_worker_per_hour_chart_dict(deployment_worker_id, workspace_name, deployment_name):
#     log_per_hour_info_list = get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id=deployment_worker_id, workspace_name=workspace_name, deployment_name=deployment_name)
#     time_table = get_nginx_per_hour_time_table_dict(log_per_hour_info_list=log_per_hour_info_list)
#     call_count_chart = get_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
#     median_chart = get_median_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
#     nginx_abnormal_count_chart = get_nginx_abnormal_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
#     api_monitor_abnormal_count_chart= get_api_monitor_abnormal_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)

#     return {
#         "call_count_chart": call_count_chart,
#         "median_chart": median_chart,
#         "nginx_abnormal_count_chart": nginx_abnormal_count_chart,
#         "api_monitor_abnormal_count_chart": api_monitor_abnormal_count_chart
#     }    

# def get_deployment_worker_nginx_call_count(workspace_name, deployment_name, deployment_worker_id):
#     main_storage_name = db_deployment.get_workspace(workspace_name=workspace_name)["main_storage_name"]
#     nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     try:
#         nginx_log_count_info = common.load_json_file(file_path=nginx_log_count_file)
#         if nginx_log_count_info is None:
#             return 0
#         return nginx_log_count_info.get("total_count")
#     except:
#         traceback.print_exc()
#         return None

# # ==========================================================================
# # kube 대체 함수
# # ==========================================================================
# # resource
# def get_pod_resource_info(deployment_worker_id, namespace="default"):
#     try:
#         result = {}
#         tmp_worker_limit = redis_client.get(DEPLOYMENT_WORKER_RESOURCE_LIMIT)
#         # cpu, memory 가 None이면  최대치

#         if len(tmp_worker_limit) > 0:
#             tmp_worker_limit = json.loads(tmp_worker_limit)
#             if str(deployment_worker_id) in tmp_worker_limit:
#                 worker_limit = tmp_worker_limit.get(str(deployment_worker_id)).get("limit") if tmp_worker_limit is not None else dict()
#                 result.update({"cpu": worker_limit.get("cpu"), "memory": worker_limit.get("memory"), POD_NETWORK_INTERFACE_LABEL_KEY: None})
#         return result
#     except Exception as e:
#         traceback.print_exc()
#         return None
