#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import threading
import traceback
from urllib import request
import string
import random

FLASK_IMPORT=False
flask_import=False
try:
    from flask import request as flaskrequest
    from flask import wrappers
    FLASK_IMPORT=True
    flask_import=True
except:
    pass

CHERRYPY_IMPORT=False
cherrypy_import=False
try:
    from cherrypy import request as cherrypyrequest
    CHERRYPY_IMPORT=True
    cherrypy_import=True
except:
    pass

DJANGO_IMPORT=False
django_import=False
try:
    import django
    from django.http import HttpRequest as djangorequest
    DJANGO_IMPORT=True
    django_import=True
except:
    pass

FASTAPI_IMPORT=False
fastapi_import=False
try:
    from fastapi import Request as fastapirequest
    from fastapi.responses import JSONResponse
    FASTAPI_IMPORT=True
    fastapi_import=True
except:
    pass

import functools
import os
import json
import time
lock = threading.Lock()
ERROR_CONDITION={"jf_API_status":"error"}
ERROR_CONDITION_LOGIC="or"
ERROR_CODE_KEY="jf_API_error_code"
MESSAGE_KEY="jf_API_message"
RETURN_ERROR_OPTIONS=True

DEFAULT_ERROR_VALUE="error"
DEFAULT_ERROR_MESSAGE="API function error"
def env_check(key, default):
    if os.environ.get(key) is None:
        return default
    else:
        return os.environ.get(key)

STATUS_VAR_KEY="jf_return_status"
IMPORT_CHECK_FILE_PATH = env_check(key="POD_API_LOG_IMPORT_CHECK_FILE_PATH_IN_POD", default="/log/import.txt")
CPU_RAM_USAGE_FILE_PATH = env_check(key="POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_POD", default="/resource_log/resource_usage.json")
GPU_USAGE_FILE_PATH = env_check(key="POD_GPU_USAGE_RECORD_FILE_PATH_IN_POD", default="/resource_log/gpu_usage.json")
API_LOG_BASE_PATH = env_check(key="POD_API_LOG_BASE_PATH_IN_POD", default="/log")
API_LOG_FILE_NAME = env_check(key="POD_API_LOG_FILE_NAME", default="monitor.txt")
API_LOG_COUNT_FILE_NAME = env_check(key="POD_API_LOG_COUNT_FILE_NAME", default="count.json")

return_dic={}

os.system("mkdir -p {}".format(API_LOG_BASE_PATH))
with open(IMPORT_CHECK_FILE_PATH, "w") as f:
    f.write("")

def get_cpu_ram_usage():
    cpu_cores_on_pod = None
    cpu_usage_on_pod = None
    mem_usage_per = None
    mem_limit = None

    for i in range(100):
        try:
            with open(CPU_RAM_USAGE_FILE_PATH, "r") as f:
                res = json.loads(f.read())
                cpu_cores_on_pod = res.get("cpu_cores_on_pod")
                cpu_usage_on_pod = res.get("cpu_usage_on_pod")

                mem_usage_per = res.get("mem_usage_per")
                mem_limit = res.get("mem_limit")
                break
        except json.JSONDecodeError:
            time.sleep(0.1)
            pass
        except :
            break
    return {
        "cpu_cores_on_pod": cpu_cores_on_pod,
        "cpu_usage_on_pod": cpu_usage_on_pod,
        "mem_usage_per": mem_usage_per,
        "mem_limit": mem_limit
    }

def get_gpu_usage():
    form = {
    }
    for i in range(100):
        try:
            with open(GPU_USAGE_FILE_PATH, "r") as f:
                res = json.loads(f.read())
                for gpu_idx in res.keys():
                    form[gpu_idx]= {
                        "util_gpu": res[gpu_idx].get("util_gpu"),
                        "util_memory": res[gpu_idx].get("util_memory"),
                        "memory_free": res[gpu_idx].get("memory_free"),
                        "memory_used": res[gpu_idx].get("memory_used"),
                        "memory_total": res[gpu_idx].get("memory_total")
                    }
                break
        except json.JSONDecodeError:
            time.sleep(0.1)
            pass
        except :
            break

    return form

def update_value_list_by_result(variables, update_list, result, key):
    if result.get(key)!=None:
        variables[key]=result[key]
        update_list.append(key)



def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def set_status(status_dic, message=None, error_code=None):
    """status api 내부에서 선언하는 경우

    Args:
        status_dic (dic): unique key 의 dic값. ex) {"status_key": "SSDFDFDF"}
        message (str, optional): 메세지
        error_code (int, optional): error 코드. 입력할 경우 error 로 count 됨
    """    
    global return_dic
    status_key=status_dic.get("status_key")
    return_dic[status_key]={}
    if message != None:
        return_dic[status_key][MESSAGE_KEY]=message
    if error_code != None:
        return_dic[status_key][ERROR_CODE_KEY]=error_code
        return_dic[status_key]["jf_API_status"]="error"

def api_monitor(method=None, router=None, use_set_status=False):
    """Decorator that monitors api calls.

    Args:
        method (str, optional): api method. ex) POST GET PUT DELETE.
        router (str, optional): api router. ex) "/" "/test".
        use_set_status (bool, optional): api 내부에서 set_status 함수를 통해 error 선언하는 경우
    Returns:
        function: api_deco
    """    
    def api_deco(func):
        """Decorator that monitors api calls.

        Args:
            func (fuction): deco 사용하는 function

        Returns:
            type 미정: api 의 return 값. ex) dic, response wrapper
        """
        @functools.wraps(func)
        async def wrap(*args, **kwargs):
            global flask_import
            global cherrypy_import
            global django_import
            global fastapi_import
            
            deployment_path = API_LOG_BASE_PATH
            save_file_name = API_LOG_FILE_NAME
            count_save_file_name = API_LOG_COUNT_FILE_NAME
            SUCCESS_STATUS = "success"
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S")
            function_name = func.__name__

            input_method = method
            if method == None:
                # 실제 실행 환경 감지 - args를 먼저 체크
                method_detected = False
                
                # 전달된 args에서 Request 객체 확인
                for arg in args:
                    # FastAPI Request 객체 체크
                    if hasattr(arg, 'method') and hasattr(arg, 'url') and hasattr(arg, 'headers'):
                        input_method = arg.method
                        method_detected = True
                        break
                    # Django Request 객체 체크  
                    elif hasattr(arg, 'method') and hasattr(arg, 'path') and str(type(arg)).find('WSGIRequest') != -1:
                        input_method = arg.method
                        method_detected = True
                        break
                
                # args에서 감지되지 않은 경우에만 전역 context 시도 (Flask 제외)
                if not method_detected:
                    try:
                        if cherrypy_import:
                            input_method = cherrypyrequest.method
                    except Exception as e:
                        pass

            input_router = router
            if router == None:
                # 실제 실행 환경에서 라우터 정보 감지
                router_detected = False
                
                # args에서 Request 객체 체크
                for arg in args:
                    # FastAPI Request
                    if hasattr(arg, 'url') and hasattr(arg.url, 'path'):
                        input_router = arg.url.path
                        router_detected = True
                        break
                    # Django Request
                    elif hasattr(arg, 'path') and str(type(arg)).find('WSGIRequest') != -1:
                        input_router = arg.path
                        router_detected = True
                        break
                
                # args에서 감지되지 않은 경우에만 전역 context 시도 (Flask 제외)
                if not router_detected:
                    try:
                        if cherrypy_import:
                            input_router = cherrypyrequest.script_name
                    except Exception as e:
                        pass

            # response time 기록
            start_time = datetime.now()
            
            # result 의 status(success, error) 값 받기
            try:
                error_variables = {
                    MESSAGE_KEY:None,
                    ERROR_CODE_KEY:9999
                }
                
                # async 함수인지 확인
                import inspect
                if inspect.iscoroutinefunction(func):
                    if use_set_status==False:
                        result = await func(*args, **kwargs)
                    else:
                        status_key=id_generator()
                        result = await func(status_key=status_key, *args, **kwargs)
                else:
                    if use_set_status==False:
                        result = func(*args, **kwargs)
                    else:
                        status_key=id_generator()
                        result = func(status_key=status_key, *args, **kwargs)

                # print("error cond", ERROR_CONDITION)
                status = SUCCESS_STATUS
                status_dic = {}
                delete_keys = []
                try:
                    # return status 관련 값들 처리 (error, error code, message)
                    if type(result)==dict:
                        result_copy=result.copy()
                    elif flask_import or django_import or fastapi_import:
                        if flask_import and type(result) == type(wrappers.Response()):
                            result_copy = json.loads(result.response[0])
                        elif django_import and type(result) == django.http.response.JsonResponse:
                            result_copy = json.loads(result.content)
                        elif fastapi_import and type(result) == JSONResponse:
                            result_copy = json.loads(result.body)
                        else:
                            result_copy = result if type(result)==dict else {}
                    else:
                        result_copy={}
                    # error status 를 function 내부에 선언하는 경우
                    if use_set_status:
                        global return_dic
                        result_copy.update(return_dic[status_key])
                        del return_dic[status_key]

                    # result key값과 error_condition key값 교집합 구하기
                    error_status_included_keys = set(list(ERROR_CONDITION.keys()))&set(list(result_copy.keys()))
                    if len(error_status_included_keys)>=1:
                        delete_keys.extend(error_status_included_keys)
                        # logic and 일때 error_condition 과 result 가 동일할 경우
                        if ERROR_CONDITION_LOGIC=="and":
                            tmp_dic = {key:result_copy[key] for key in error_status_included_keys}
                            if ERROR_CONDITION==tmp_dic:
                                status = DEFAULT_ERROR_VALUE
                        #logic or 일때  error_condition 과 동일한 key value 가 result 에 있는 경우
                        else:
                            for key in error_status_included_keys:
                                if result_copy[key]==ERROR_CONDITION[key]:
                                    status = DEFAULT_ERROR_VALUE
                                    break
                    # error_variables 와 delete_keys 업데이트 
                    # if status==DEFAULT_ERROR_VALUE:
                    update_value_list_by_result(error_variables, delete_keys, result_copy, MESSAGE_KEY)
                    update_value_list_by_result(error_variables, delete_keys, result_copy, ERROR_CODE_KEY)
                    if type(result)==dict:
                        if RETURN_ERROR_OPTIONS==False:
                            for key in delete_keys:
                                del result[key]
                except Exception as e:
                    print(e)
                    pass
            except Exception as e:
                # nginx랑 중복되기 때문에 아무것도 안함.
                traceback.print_exc()
                raise e
                
            # response time 기록
            response_time = (datetime.now()-start_time).total_seconds()
            
            info = {
                "method":input_method,
                "router":input_router,
                "response_time":response_time,
                "function_name":function_name,
                # "request": str(request_data),
                # "request": request_data,
                "cpu_ram_resource": get_cpu_ram_usage(),
                "gpu_resource": get_gpu_usage(),
                "status":status
            }
            if error_variables.get(MESSAGE_KEY)!=None:
                info.update({
                    "message": error_variables[MESSAGE_KEY]
                })
            if status != SUCCESS_STATUS:
                info.update({
                    # "message": error_variables[MESSAGE_KEY],
                    "error_code": error_variables[ERROR_CODE_KEY]
                })
            # elif type(result)==dict and result.get(MESSAGE_KEY)!=None:
            #     info.update({
            #         "message": result[MESSAGE_KEY]
            #     })

            with lock:
                current=datetime.now()
                info["time"] = current.strftime("%Y-%m-%d %H:%M:%S")
                with open("{}/{}".format(deployment_path, save_file_name), mode= "a", encoding="utf8") as f:
                    f.write(json.dumps(info)+"\n")
                if os.path.isfile("{}/{}".format(deployment_path, count_save_file_name)):
                    with open("{}/{}".format(deployment_path, count_save_file_name), mode= "r", encoding="utf8") as f:
                        status_dic = json.load(f)
                        if status in status_dic.keys():
                            status_dic[status]+=1
                        else:
                            status_dic[status]=1
                else:
                    status_dic = {status:1}
                with open("{}/{}".format(deployment_path, count_save_file_name), mode="w", encoding="utf8") as f:
                    json.dump(status_dic, f, indent=4, ensure_ascii=False)
            return result
        return wrap
    return api_deco
