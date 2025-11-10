#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
# import statistics
import math
import traceback
# import dateutil_test as dateutil
from dateutil_test.parser.isoparser import isoparse
import os
import json
from datetime import datetime, timezone, timedelta
import argparse
import copy

def get_statistic_result(result, logic="mean", ndigits=3):
    def calculate_percentile(arry, percentile):
        size = len(arry)
        return sorted(arry)[int(math.ceil((size * percentile) / 100)) - 1]
    if len(result)==0:
        return 0
    if logic =="mean":
        mean_result=sum(result)/len(result)
        return round(mean_result, ndigits=ndigits)
    if logic == "median":
        median_result=sorted(result)
        len_result=len(median_result)
        if len_result==0:
            return 0
        if len_result%2==1:
            median_result=median_result[int((len_result+1)/2-1)]
        else:
            median_result=(median_result[int(len_result/2)-1]+median_result[int(len_result/2)])/2
        return round(median_result, ndigits=ndigits)
    if logic == "min":
        return round(min(result), ndigits=ndigits)
    if logic == "max":
        return round(max(result), ndigits=ndigits)
    if logic[:10]=="percentile":
        return round(calculate_percentile(arry=result, percentile=int(logic[10:])), ndigits=ndigits)

def flatten_list(input_list):
    return [item for sublist in input_list for item in sublist if type(sublist)==list]

# def date_str_to_timestamp(date_str, date_format="%Y-%m-%d %H:%M"):
#     return datetime.timestamp(datetime.strptime(date_str, date_format))

def date_str_to_timestamp(date_str, date_format="%Y-%m-%d %H:%M"):
    """
    date_format = "%Y-%m-%d"..... | iso8601
    """
    default_date_format_list = [
        "iso8601",
        "%Y-%m-%d",
        "%Y-%m-%d %H",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S"
    ]
    if date_str is None:
        return 0
    
    timestamp = 0

    try:
        if date_format == "iso8601":
            # timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
            timestamp = time.mktime(isoparse(date_str).timetuple())
        else :
            # timestamp = time.mktime(datetime.strptime(date_str, date_format).timetuple())
            timestamp = datetime.timestamp(datetime.strptime(date_str, date_format))
    except:
        traceback.print_exc()
        # for compatibility
        for date_format in default_date_format_list:
            try:
                if date_format == "iso8601":
                    # timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
                    timestamp = time.mktime(isoparse(date_str).timetuple())
                else :
                    # timestamp = time.mktime(datetime.strptime(date_str, date_format).timetuple())
                    timestamp = datetime.timestamp(datetime.strptime(date_str, date_format))
                break
            except:
                pass

    return timestamp

def update_dict_key_count(dict_item, key, add_count=1, default=0, exist_only=False):
    # exist_only(True|False) = dict key have to exist. if not skip.
    if dict_item.get(key) is None:
        if exist_only == True:
            return 
        
        dict_item[key] = default

    dict_item[key] += add_count

def update_code_dic(total_code_dic, code_dic):
    if len(code_dic)>0:
        for key in code_dic.keys():
            # if type(key) in [tuple]:
            #     print(code_dic)
            detail_key = str(key)
            if key>=200 and key<600:
                main_key = detail_key[0]+"00"
            else:
                main_key = "rest"

            if detail_key in total_code_dic[main_key].keys():
                total_code_dic[main_key][detail_key]+=code_dic[key]
            else:
                total_code_dic[main_key][detail_key]=code_dic[key]
    return total_code_dic

def update_nginx_error_log(error_log_list, result_list=None, i=None, log_dic=None):
    def all_dashboard(error_log_list, result_list, i):
        for result_dic in result_list:
            if result_dic[i].get("nginx_error_log_list") is not None:              
                error_log_list += [ error_log for error_log in result_dic[i].get("nginx_error_log_list") ]

    def only_worker(error_log_list, log_dic):
        # print("ERROR LOG ", log_dic.get("nginx_error_log_list"))
        error_log_list += log_dic.get("nginx_error_log_list")

    if log_dic is None:
        all_dashboard(error_log_list=error_log_list, result_list=result_list, i=i)
    else :
        only_worker(error_log_list=error_log_list, log_dic=log_dic)

def update_nginx_access_count_info(nginx_access_count_info, result_list=None, i=None, log_dic=None):
    def all_dashboard(nginx_access_count_info, result_list, i):
        for result_dic in result_list:
            if result_dic[i].get("nginx_access_count_info") is not None:
                for k, v in result_dic[i].get("nginx_access_count_info").items():
                    update_dict_key_count(dict_item=nginx_access_count_info, key=k, add_count=v)
    
    def only_worker(nginx_access_count_info, log_dic):
        for k, v in log_dic.get("nginx_access_count_info").items():
            update_dict_key_count(dict_item=nginx_access_count_info, key=k, add_count=v)

    if log_dic is None:
        all_dashboard(nginx_access_count_info=nginx_access_count_info, result_list=result_list, i=i)
    else :
        only_worker(nginx_access_count_info=nginx_access_count_info, log_dic=log_dic)

def update_monitor_error_log(error_log_list, log_dic=None):
    # print("ERROR LOG ", log_dic.get("monitor_error_log_list"))
    error_log_list += log_dic.get("monitor_error_log_list")

def get_default_api_monitor_graph_result(time, gpu_num_list):
    dic = {
        "time": time,
        "time_local": 0,
        "monitor_count": 0,
        "nginx_count": 0,
        "success_count": 0,
        "error_count": 0,
        "monitor_error_count": 0,
        "nginx_error_count": 0,
        "processing_time": [],
        "response_time": [],
        "average_cpu_usage_on_pod": [],
        "average_mem_usage_per": [],
        "gpu_resource":{},
        "nginx_error_log_list": [],
        "monitor_error_log_list": [],
        "nginx_access_count_info": {} 
    }
    for gpu_num in gpu_num_list:
        dic["gpu_resource"][gpu_num]={}
        dic["gpu_resource"][gpu_num]["gpu_memory_total"]=0
        dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=0
        dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=0
        dic["gpu_resource"][gpu_num]["average_util_gpu"]=0
        dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=0
        dic["gpu_resource"][gpu_num]["count"]=0

    return dic

parser = argparse.ArgumentParser()
parser.add_argument("--deployment_worker_id", type=int, required=True)
parser.add_argument("--interval", type=int, default=600)
parser.add_argument("--update_time", type=float, default=10)
parser.add_argument("--search_type", type=str, default="range")
args = parser.parse_args()

def env_check(key, default):
    if os.environ.get(key) is None:
        return default
    else:
        return os.environ.get(key)

IMPORT_CHECK_FILE_PATH = env_check(key="POD_API_LOG_IMPORT_CHECK_FILE_PATH_IN_POD", default="/log/import.txt")
CPU_RAM_USAGE_FILE_PATH = env_check(key="POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_POD", default="/resource_log/resource_usage.json")
GPU_USAGE_FILE_PATH = env_check(key="POD_GPU_USAGE_RECORD_FILE_PATH_IN_POD", default="/resource_log/gpu_usage.json")
LOG_BASE_PATH = env_check(key="POD_API_LOG_BASE_PATH_IN_POD", default="/log")
NGINX_ACCESS_LOG_FILE_NAME = env_check(key="POD_NGINX_ACCESS_LOG_FILE_NAME", default="nginx_access.log")
API_LOG_FILE_NAME = env_check(key="POD_API_LOG_FILE_NAME", default="monitor.txt")
API_LOG_COUNT_FILE_NAME = env_check(key="POD_API_LOG_COUNT_FILE_NAME", default="count.json")
POD_RUN_TIME_DATE_FORMAT = env_check(key="POD_RUN_TIME_DATE_FORMAT", default="%Y-%m-%d %H:%M:%S")
POD_DASHBOARD_HISTORY_FILE_NAME = env_check(key="POD_DASHBOARD_HISTORY_FILE_NAME", default="dashboard_history.json")
POD_DASHBOARD_HISTORY_BACK_FILE_NAME = env_check(key="POD_DASHBOARD_HISTORY_BACK_FILE_NAME", default="dashboard_history_bak.json")
POD_DASHBOARD_LIVE_HISTORY_FILE_NAME = env_check(key="POD_DASHBOARD_LIVE_HISTORY_FILE_NAME", default="dashboard_live_history.json")
POD_DASHBOARD_LIVE_HISTORY_BACK_FILE_NAME = env_check(key="POD_DASHBOARD_LIVE_HISTORY_FILE_NAME", default="dashboard_live_history_bak.json")
# POD_RUN_NGINX_TIME_DATE_FORMAT='%Y-%m-%dT%H:%M:%S+00:00'
POD_RUN_NGINX_TIME_DATE_FORMAT='iso8601'
deployment_worker_id=args.deployment_worker_id
interval=args.interval
update_time=args.update_time

history_file_name=POD_DASHBOARD_HISTORY_FILE_NAME if args.search_type=="range" else POD_DASHBOARD_LIVE_HISTORY_FILE_NAME
history_file_back_name=POD_DASHBOARD_HISTORY_BACK_FILE_NAME if args.search_type=="range" else POD_DASHBOARD_LIVE_HISTORY_BACK_FILE_NAME
error_file_name="history_error.log"
interval_idx = 0
current_idx = 0

ndigits=10
total_logic="mean"
nginx_line_idx=0
monitor_line_idx=0

worker_start_time = time.time()
print("while start")
next_idx=True
nginx_idx=0
monitor_idx=0
nginx_pass_info={"current_idx":0, "next_idx":0}
monitor_pass_info={"current_idx":0, "next_idx":0}
gpu_num_list = []
while True:
    try:
        # interval index 통해 start time, end time 받기
        start_time = worker_start_time - worker_start_time%interval + interval*interval_idx
        end_time = worker_start_time - worker_start_time%interval + interval*(interval_idx+1)
        # 파일 읽기
        nginx_access_log=[]
        monitor_log=[]
        line_iter=1
        # 파일 읽는 시점의 시간 받기
        now_time = time.time()
        if os.path.exists("{}/{}".format(LOG_BASE_PATH, NGINX_ACCESS_LOG_FILE_NAME)):
            with open("{}/{}".format(LOG_BASE_PATH, NGINX_ACCESS_LOG_FILE_NAME), "r") as f:
                if nginx_idx==0:
                    nginx_access_log = f.readlines()
                else:
                    for line in f:
                        if line_iter>nginx_idx:
                            nginx_access_log.append(line)
                        line_iter+=1
                # nginx_access_log = f.readlines()
                # nginx_access_log = nginx_access_log[nginx_idx:]
                nginx_access_log = [json.loads(dic) for dic in nginx_access_log]
        if len(nginx_access_log)>0:
            line_iter=1
            # if os.path.exists(IMPORT_CHECK_FILE_PATH):
            if os.path.exists("{}/{}".format(LOG_BASE_PATH, API_LOG_FILE_NAME)):
                with open("{}/{}".format(LOG_BASE_PATH, API_LOG_FILE_NAME), "r") as f:
                    if monitor_idx==0:
                        monitor_log = f.readlines()
                    else:
                        for line in f:
                            if line_iter>monitor_idx:
                                monitor_log.append(line)
                            line_iter+=1
                    # monitor_log = f.readlines()[monitor_idx:]                    
                    monitor_log = [json.loads(dic) for dic in monitor_log]
                    # print("==============")
                    # print(line_iter,monitor_log)
            # 초기 gpu list 받기
            if monitor_idx==0:
                if os.path.exists(IMPORT_CHECK_FILE_PATH):
                    # time.sleep(10)
                    gpu_num_list = []
                    if len(monitor_log) > 0:
                        gpu_num_list = list(monitor_log[0]["gpu_resource"].keys())
                    for gpu_num in gpu_num_list:
                        if monitor_log[0]["gpu_resource"][gpu_num]["util_gpu"] == "[N/A]":
                            gpu_num_list=[]
                            break
                    # print("gpu num list", gpu_num_list)
            # 빈 result_dic 만들기 if next_idx==True
            if next_idx==True:
                result_dic = get_default_api_monitor_graph_result(time=start_time, gpu_num_list=gpu_num_list)
                if len(gpu_num_list)>=1:
                    for gpu_num in gpu_num_list:
                        # result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]=[]
                        result_dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=[]
                        # result_dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=[]
                        result_dic["gpu_resource"][gpu_num]["average_util_gpu"]=[]
                        result_dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=[]
                        # result_dic["gpu_resource"][gpu_num]["count"]=[]
                result_back=copy.deepcopy(result_dic)
                # error_log_list=[]
                nginx_access_count_info = {}
                code_dic={}
                nginx_pass_info={"current_idx":0, "next_idx":0}
                nginx_all_count=0
                monitor_pass_info={"current_idx":0, "next_idx":0}
                # print("result_dic_updated")
                next_idx=False
            # code_dic={}

            # monitor 관련 통계
            monitor_error_count=0
            monitor_line_idx=0
            for log_idx in range(len(monitor_log)):
                log_dic=monitor_log[log_idx]
                time_str = log_dic["time"]
                log_dic["time"]=date_str_to_timestamp(log_dic["time"], POD_RUN_TIME_DATE_FORMAT)
                if log_dic["time"]<start_time:
                    monitor_line_idx+=1
                    # raise RuntimeError("index not in interval")
                    # with open("{}/{}".format(LOG_BASE_PATH, "log_to_graph_error.txt"), "a") as f:
                    # # with open("log_to_graph_error.txt", "a") as f:
                    #     f.write("error time: {} error type: {}\n".format(time_str, "monitor"))
                    # print("monitor index not in interval", args.search_type, start_time, log_dic["time"])
                    # 시간 이전 index 가 있어도 다 누락되는거는 아님
                    # pass
                elif log_dic["time"]>=start_time and log_dic["time"]<end_time:
                    monitor_line_idx+=1
                    result_dic["monitor_count"]+=1
                    # all_count+=1

                    # cpu 기록 추가
                    cpu_usage_on_pod=log_dic["cpu_ram_resource"]["cpu_usage_on_pod"] if log_dic["cpu_ram_resource"]["cpu_usage_on_pod"] is not None else 0
                    mem_usage_per=log_dic["cpu_ram_resource"]["mem_usage_per"] if log_dic["cpu_ram_resource"]["mem_usage_per"] is not None else 0
                    result_dic["average_cpu_usage_on_pod"].append(cpu_usage_on_pod)
                    result_dic["average_mem_usage_per"].append(mem_usage_per)
                    # gpu 기록 추가
                    if len(gpu_num_list)>=1:
                        for gpu_num in gpu_num_list:
                            
                            gpu_memory_used = log_dic["gpu_resource"][gpu_num]["memory_used"] if log_dic["gpu_resource"][gpu_num]["memory_used"] is not None else 0
                            gpu_memory_total = log_dic["gpu_resource"][gpu_num]["memory_total"] if log_dic["gpu_resource"][gpu_num]["memory_total"] is not None else 0  # 0 / 0 때문에
                            util_gpu = log_dic["gpu_resource"][gpu_num]["util_gpu"] if log_dic["gpu_resource"][gpu_num]["util_gpu"] is not None else 0
                            util_gpu_memory = log_dic["gpu_resource"][gpu_num]["util_memory"] if log_dic["gpu_resource"][gpu_num]["util_memory"] is not None else 0
                            # print("avg gpu mem list",result_dic["gpu_resource"][gpu_num]["average_gpu_memory_used"])
                            result_dic["gpu_resource"][gpu_num]["average_gpu_memory_used"].append(gpu_memory_used)
                            result_dic["gpu_resource"][gpu_num]["average_util_gpu"].append(util_gpu)
                            result_dic["gpu_resource"][gpu_num]["average_util_gpu_memory"].append(util_gpu_memory)
                            result_dic["gpu_resource"][gpu_num]["gpu_memory_total"] = gpu_memory_total
                            result_dic["gpu_resource"][gpu_num]["count"]+=1
                    # if log_dic["status"]=="success":
                    if log_dic.get("error_code")==None:
                        result_dic["success_count"]+=1
                        # success_count+=1
                        result_dic["processing_time"].append(log_dic["response_time"])
                    else:
                        call_status = log_dic.get("error_code")
                        result_dic["error_count"]+=1
                        result_dic["monitor_error_count"]+=1
                        if call_status != None:
                            if code_dic.get(call_status)==None:
                                code_dic[call_status]=1
                            else:
                                code_dic[call_status]+=1
                        # error_count+=1
                        # monitor_error_count+=1
                        result_dic["monitor_error_log_list"].append({
                            "worker": deployment_worker_id,
                            "request": str(log_dic.get("method"))+" "+str(log_dic.get("router")),
                            "status": call_status,
                            "time_local": time_str,
                            "message": log_dic.get("message")
                        })
                    if monitor_pass_info["next_idx"]>0:
                        print("monitor index not arranged")
                        monitor_pass_info["current_idx"]+=1
                else:
                    monitor_line_idx+=1
                    monitor_pass_info["next_idx"]+=1
            
            # nginx 관련 통계
            nginx_error_count=0
            # nginx_all_count=0
            nginx_line_idx=0
            # nginx_error_idx=0
            nginx_time_delay_count=0
            for log_idx in range(len(nginx_access_log)):
                # nginx_line_idx+=1
                log_dic = nginx_access_log[log_idx]
                # Front에서 할 경우 OPTIONS를 날림..
                if "OPTIONS" in log_dic["request"] :
                    nginx_line_idx+=1
                    nginx_time_delay_count+=1
                    print("OPTIONS in request")
                    continue
                log_dic["time_local"] = date_str_to_timestamp(log_dic["time_local"], POD_RUN_NGINX_TIME_DATE_FORMAT)
                time_obj = datetime.fromtimestamp(log_dic["time_local"])
                time_str=datetime.strftime(time_obj,POD_RUN_TIME_DATE_FORMAT)
                if log_dic["time_local"]<start_time:
                    nginx_line_idx+=1
                    # 이전 인덱스 들어와도 기록 가능함
                    # print("nginx index not in interval", args.search_type, start_time, log_dic["time_local"])
                    # # raise RuntimeError("index not in interval")
                    # with open("{}/{}".format(LOG_BASE_PATH, "log_to_graph_error.txt"), "a") as f:
                    # # with open("log_to_graph_error.txt", "a") as f:
                    #     f.write("error time: {} error type: {}\n".format(time_str, "nginx"))
                    # pass
                elif log_dic["time_local"]>=start_time and log_dic["time_local"]<end_time:
                    nginx_all_count+=1
                    nginx_line_idx+=1
                    call_status = int(log_dic["status"])
                    update_dict_key_count(dict_item=result_dic["nginx_access_count_info"], key=call_status)
                    if code_dic.get(call_status)==None:
                        code_dic[call_status]=1
                    else:
                        code_dic[call_status]+=1
                    if 200 <=  call_status and call_status <300:
                        # success_count+=1
                        result_dic["nginx_count"]+=1
                        result_dic["response_time"].append(float(log_dic["request_time"]))
                        # pass
                    else :
                        # error_count+=1
                        result_dic["error_count"]+=1
                        result_dic["nginx_error_count"]+=1
                        # nginx_error_count+=1
                        result_dic["nginx_error_log_list"].append({
                            "worker": deployment_worker_id,
                            "request": log_dic["request"],
                            "status": log_dic["status"],
                            "time_local": time_str,
                            "message": None
                        })
                    if nginx_pass_info["next_idx"]>0:
                        nginx_pass_info["current_idx"]+=1
                else:
                    nginx_line_idx+=1
                    nginx_pass_info["next_idx"]+=1
            
            # dashboard history json 저장
            if result_back==result_dic:
                pass
            else:
                total_code_dic={
                    "200":{},
                    "300":{},
                    "400":{},
                    "500":{},
                    "rest":{}
                }
                error_log_list=[]
                # nginx_access_count_info = {}
                average_response_time_list = [i for i in result_dic["response_time"] if i>0]
                average_processing_time_list = [i for i in result_dic["processing_time"] if i>0]
                # average_nginx_response_time_list = [i for i in result_dic["average_nginx_response_time"] if i>0]
                # average_response_time_list = [i for i in result_dic["average_response_time"] if i>0]
                update_code_dic(total_code_dic, code_dic)
                update_monitor_error_log(error_log_list=error_log_list, log_dic=result_dic)
                update_nginx_error_log(error_log_list=error_log_list, log_dic=result_dic)
                update_nginx_access_count_info(nginx_access_count_info=nginx_access_count_info, log_dic=result_dic)
                # result_dic_new=result_dic.copy()
                result_dic_new=copy.deepcopy(result_dic)
                # if result_dic["nginx_count"]>0:
                    # result_dic_new["average_nginx_response_time"]=get_statistic_result(average_nginx_response_time_list, total_logic, ndigits)
                    # result_dic_new["min_nginx_response_time"]=get_statistic_result(average_nginx_response_time_list, "max", ndigits)
                    # result_dic_new["max_nginx_response_time"]=get_statistic_result(average_nginx_response_time_list, "min", ndigits)
                if result_dic["monitor_count"]>0:
                    result_dic_new["average_cpu_usage_on_pod"]=get_statistic_result(result_dic["average_cpu_usage_on_pod"], total_logic, ndigits)
                    result_dic_new["average_mem_usage_per"]=get_statistic_result(result_dic["average_mem_usage_per"], total_logic, ndigits)
                    if len(gpu_num_list)>=1:
                        for gpu_num in gpu_num_list:
                            if result_dic["gpu_resource"][gpu_num]["count"]>0:
                                count = result_dic["gpu_resource"][gpu_num]["count"]
                                gpu_memory_total = result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]
                                result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used"] = get_statistic_result(result_dic["gpu_resource"][gpu_num]["average_gpu_memory_used"], total_logic, ndigits)
                                result_dic_new["gpu_resource"][gpu_num]["average_util_gpu"] = get_statistic_result(result_dic["gpu_resource"][gpu_num]["average_util_gpu"], total_logic, ndigits)
                                result_dic_new["gpu_resource"][gpu_num]["average_util_gpu_memory"] = get_statistic_result(result_dic["gpu_resource"][gpu_num]["average_util_gpu_memory"], total_logic, ndigits)
                                if gpu_memory_total>0:
                                    result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used_per"] = result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used"] / gpu_memory_total * 100
                                else:
                                    result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used_per"] = 0
                                result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used_per"] = round(result_dic_new["gpu_resource"][gpu_num]["average_gpu_memory_used_per"], ndigits)

                                # result_dic["gpu_resource"][gpu_num]["gpu_memory_total"] = gpu_memory_total
                                result_dic_new["gpu_resource"][gpu_num]["count"] = count
                # if result_dic["success_count"]>0:
                #     result_dic_new["average_response_time"]=get_statistic_result(average_response_time_list, total_logic, ndigits)
                #     result_dic_new["max_response_time"]=get_statistic_result(average_response_time_list, "max", ndigits)
                #     result_dic_new["min_response_time"]=get_statistic_result(average_response_time_list, "min", ndigits)
                for key in ["monitor_error_log_list", "nginx_error_log_list", "nginx_access_count_info", 
                            "response_time", "processing_time"]:
                    del result_dic_new[key]
                # del result_dic_new["nginx_error_log_list"]
                # del result_dic_new["nginx_access_count_info"]
                # del result_dic_new["response_time"]
                # del result_dic_new["processing_time"]
                return_result = {
                    "graph_result":result_dic_new,
                    "nginx_access_count_info": nginx_access_count_info,
                    "error_log_list": error_log_list,
                    "total_code_dic": total_code_dic,
                    "total_info":{
                        "call":{
                            "total":nginx_all_count
                        },
                        # "abnormal":{
                        #     "total":result_dic["error_count"]
                        # },
                        "processing_time":{
                            "min":get_statistic_result(average_processing_time_list, "min", ndigits),
                            "max":get_statistic_result(average_processing_time_list, "max", ndigits),
                            "average":get_statistic_result(average_processing_time_list, "mean", ndigits),
                            "median":get_statistic_result(average_processing_time_list, "median", ndigits),
                            "99":get_statistic_result(average_processing_time_list, "percentile99", ndigits),
                            "95":get_statistic_result(average_processing_time_list, "percentile95", ndigits),
                            "90":get_statistic_result(average_processing_time_list, "percentile90", ndigits)
                        },
                        "response_time":{
                            "min":get_statistic_result(average_response_time_list, "min", ndigits),
                            "max":get_statistic_result(average_response_time_list, "max", ndigits),
                            "average":get_statistic_result(average_response_time_list, "mean", ndigits),
                            "median":get_statistic_result(average_response_time_list, "median", ndigits),
                            "99":get_statistic_result(average_response_time_list, "percentile99", ndigits),
                            "95":get_statistic_result(average_response_time_list, "percentile95", ndigits),
                            "90":get_statistic_result(average_response_time_list, "percentile90", ndigits)
                        }
                    }
                }
                if os.path.isfile("{}/{}".format(LOG_BASE_PATH, history_file_name)):
                    with open("{}/{}".format(LOG_BASE_PATH, history_file_name), "r") as f:
                        history_dic = json.load(f)
                        history_dic[str(start_time)]=return_result
                        if interval==1:
                            if len(history_dic.keys())>3600:
                                del_key_list = list(history_dic.keys())
                                del_key_list = del_key_list[:-3600]
                                for key in history_dic.keys():
                                    del history_dic[key]
                    os.system("cp {}/{} {}/{}".format(LOG_BASE_PATH, history_file_name, LOG_BASE_PATH, history_file_back_name))
                    with open("{}/{}".format(LOG_BASE_PATH, history_file_name), "w") as f:
                        json.dump(history_dic, f, ensure_ascii=False)
                    os.system("rm {}/{}".format(LOG_BASE_PATH, history_file_back_name))                    
                else:
                    history_dic={str(start_time): return_result}
                    with open("{}/{}".format(LOG_BASE_PATH, history_file_name), "w") as f:
                        json.dump(history_dic, f, ensure_ascii=False)

            nginx_idx+=nginx_line_idx
            monitor_idx+=monitor_line_idx

        if now_time>end_time+2:
            interval_idx+=1
            next_idx=True
            nginx_idx=nginx_idx-nginx_pass_info["next_idx"]-nginx_pass_info["current_idx"]
            monitor_idx=monitor_idx-monitor_pass_info["next_idx"]-monitor_pass_info["current_idx"]
        else:
            time.sleep(update_time)
    except:
        now_datetime=datetime.strftime(datetime.now(timezone(timedelta(hours=9))), POD_RUN_TIME_DATE_FORMAT)
        tb="==============\n"
        tb+="time kst: {}\n".format(now_datetime)
        tb+="{}\n".format(traceback.format_exc())
        with open("{}/{}".format(LOG_BASE_PATH, error_file_name), "a") as f:
            f.write(tb)
        time.sleep(1)