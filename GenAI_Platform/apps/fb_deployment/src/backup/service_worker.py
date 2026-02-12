# from logging import error
# from posix import listdir
# from pyexpat import model
# from sys import version_info
# from utils.resource import response
# # import utils.db as db
# # from utils.lock import jf_scheduler_lock
# import utils.scheduler as scheduler
# import utils.common as common
# from utils.TYPE import *
# from utils.settings import *
# from utils.kube_create_func import create_deployment_pod, create_deployment_pod_new_method
# # from utils.kube_create_func import create_deployment_pod_o
# # import utils.kube as kube
# # from deployment import get_deployment_running_info_o
# # from deployment.service import get_deployment_running_info
# from deployment.service_monitoring import get_running_worker_dir, get_statistic_result, get_deployment_api_total_count_info
# from utils.access_check import deployment_access_check, check_inaccessible_deployment, check_deployment_access_level
# from ast import literal_eval
# # from utils.kube import kube_data
# from utils.kube_parser import parsing_pod_restart_count
# from utils.exceptions import *
# from utils.exceptions_deployment import *
# from utils.settings import JF_SYSTEM_NAMESPACE

# from utils.kube_create_func import pod_start_new, PodName, Label, ENV, create_pod_except_api 
# from utils.msa_db import db_deployment
# from deployment import service_monitoring as svc_monitoring

# import time
# import subprocess
# import json
# import os
# import traceback


# # 배포 실행 방법
# CAES 1. Custom - run_code
# CASE 2. Built_in - pretrained - built_in_model run_code
# CASE 3. Built_in - user_trained - built_in_model run_code + checkpoint_file
# CASE 4. Built_in - checkpoint_id (checkpoint_id가 built_in_model + checkpoint 파일을 들고 있음)

# # 배포 실행에 필요한 정보
# CASE 1. run_code = run_code
# CASE 2. 
# # run_code

# class KubeNamespace:
#     def __init__(self, workspace_name=None, workspace_id=None):
#         self.workspace_name = workspace_name
#         self.workspace_id = workspace_id

#         if workspace_name is not None:
#             self.namespace = str(JF_SYSTEM_NAMESPACE) + "-" + str(self.workspace_name)
#         else:
#             workspace_name = db_deployment.get_workspace(workspace_id=workspace_id)["name"]
#             self.namespace = str(JF_SYSTEM_NAMESPACE) + "-" + str(workspace_name)

# ##########################################################################
# ##########################################################################
# ##########################################################################
# ##########################################################################

# def run_item_deleted(item_deleted_info):
#     training_exception_map = {
#         1: DeploymentSelectTrainingNotExistError,
#         2: DeploymentSelectJobNotExistError,
#         3: DeploymentSelectHPSNotExistError
#     }
#     if item_deleted_info.get("training")!=None and item_deleted_info.get("training")!=0 :
#         raise training_exception_map[item_deleted_info["training"]]
#     if item_deleted_info.get("built_in_model")==1:
#         raise DeploymentSelectBuiltInModelNotExistError
    
# def update_custom_deployment_run_info(deployment_worker_info):
#     from deployment.service import load_custom_api_system_info_to_json
#     deployment_id=deployment_worker_info["deployment_id"]
#     # model_info_json = load_custom_api_system_info_to_json(deployment_id=deployment_id)
#     model_info_json = load_custom_api_system_info_to_json(
#                         run_code_path=deployment_worker_info[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY].get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY), 
#                         training_name=deployment_worker_info["training_name"],
#                         workspace_name=deployment_worker_info["workspace_name"])
#     if model_info_json:
#         deployment_worker_info["deployment_form_list"] = model_info_json["deployment_input_data_form_list"]
#         for key in ["checkpoint_load_dir_path_parser","checkpoint_load_file_path_parser","deployment_num_of_gpu_parser"]:
#             model_info_json.get(key)
#     update_deployment_py_command_from_template(deployment_worker_info)
#     # if '/src/' == deployment_worker_info[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY].get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY)[:5]:
#     #     deployment_worker_info["deployment_py_command"] = deployment_worker_info[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY].get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY)[1:]
#     # else:
#     #     deployment_worker_info["deployment_py_command"] = deployment_worker_info[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY].get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY)

# def update_deployment_py_command_from_template(deployment_worker_info):
#     # deployment_py_command 에 (interpreter + command + arguments) 선언
#     deployment_template_run_info = deployment_worker_info.get(DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY)
#     if deployment_template_run_info != None:
#         deployment_worker_info["deployment_py_command"] = ""
#         if deployment_template_run_info.get(DEPLOYMENT_TEMPLATE_RUN_BINARY_KEY) !=None:
#             deployment_worker_info["deployment_py_command"] += deployment_template_run_info[DEPLOYMENT_TEMPLATE_RUN_BINARY_KEY]+" "
#         if deployment_template_run_info.get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY) !=None:
#             deployment_worker_info["deployment_py_command"] += deployment_template_run_info[DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY]+" "
#         if deployment_template_run_info.get(DEPLOYMENT_TEMPLATE_RUN_ARGUMENTS_KEY) !=None:
#             deployment_worker_info["deployment_py_command"] += deployment_template_run_info[DEPLOYMENT_TEMPLATE_RUN_ARGUMENTS_KEY]
    
# def update_json_deployment_run_info(deployment_worker_info):
#     update_deployment_py_command_from_template(deployment_worker_info)
#     deployment_template_mount_info = deployment_worker_info.get(DEPLOYMENT_TEMPLATE_MOUNT_KEY)
#     if deployment_template_mount_info != None:
#         # dataset access 값 받기
#         if deployment_template_mount_info.get("dataset") != None and type(deployment_template_mount_info.get("dataset"))==list:
#             for idx in range(len(deployment_template_mount_info["dataset"])):
#                 dataset_name = deployment_template_mount_info["dataset"][idx].get("name")
#                 dataset_access_info = db.get_dataset_access_by_dataset_name(workspace_id=deployment_worker_info["workspace_id"],
#                                                                             dataset_name=dataset_name)
#                 deployment_template_mount_info["dataset"][idx]["access"] = dataset_access_info["access"]

# def update_built_in_model_deployment_run_info(deployment_worker_info):
#     additional_info = db.get_deployment_worker_built_in_pod_run_info(deployment_worker_info["built_in_model_id"])
#     deployment_worker_info.update(additional_info)
#     deployment_worker_info["deployment_form_list"] = db.get_built_in_model_data_deployment_form(deployment_worker_info["built_in_model_id"])

# def update_deployment_template_info(deployment_worker_info):
#     """
#     Description: Update information about template of deployment worker .

#     Args:
#         deployment_worker_info (dict):
#     """
#     deployment_worker_info.update(deployment_worker_info["deployment_template_info"])
#     del deployment_worker_info["deployment_template_info"]

#     get_info_method_dic = {
#         DEPLOYMENT_RUN_CUSTOM: update_custom_deployment_run_info,
#         DEPLOYMENT_RUN_USERTRAINED: update_built_in_model_deployment_run_info,
#         DEPLOYMENT_RUN_PRETRAINED: update_built_in_model_deployment_run_info,
#         DEPLOYMENT_RUN_CHEKCPOINT: update_built_in_model_deployment_run_info,
#         DEPLOYMENT_RUN_SANDBOX: update_json_deployment_run_info
#     }
#     # TODO template type 받는 방식 통일 후 변경 예정 => Lyla 22/12/18
#     if deployment_worker_info.get(DEPLOYMENT_TEMPLATE_TYPE_KEY)==None:
#         deployment_worker_info[DEPLOYMENT_TEMPLATE_TYPE_KEY] = deployment_worker_info[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_TYPE_KEY]
#         deployment_worker_info["deployment_type"] = deployment_worker_info[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY]

#     update_run_info = get_info_method_dic.get(deployment_worker_info[DEPLOYMENT_TEMPLATE_TYPE_KEY])
#     if update_run_info !=None:
#         update_run_info(deployment_worker_info)

#     # info=DEPLOYMENT_JSON_TEMPLATE[template_info[DEPLOYMENT_TEMPLATE_TYPE_KEY]]
#     # return info.update(json.loads(template_info))

# 템플릿 적용
# def get_deployment_worker_info(deployment_worker_id):
#     """
#     Description: Get all deployment info about a deployment

#     Args:
#         deployment_worker_id (int): key value to run deployment

#     Returns:
#         dict: deployment_worker_info dictionary
#     """

#     deployment_worker_info={}
#     # deployment_worker_info["checkpoint"]=None
#     # deployment_worker_info["checkpoint_id"]=None
#     # deployment_worker_info["checkpoint_dir_path"]=None
#     # deployment_worker_info["checkpoint_workspace_name"]=None
#     # deployment_worker_info["built_in_model_path"]=None
#     # deployment_worker_info["built_in_model_id"]=None
#     # deployment_worker_info["checkpoint_load_dir_path_parser"]=None 
#     # deployment_worker_info["checkpoint_load_file_path_parser"]=None
#     # deployment_worker_info["deployment_num_of_gpu_parser"]=None
    
#     deployment_worker_info.update(db.get_deployment_worker_pod_run_info(deployment_worker_id=deployment_worker_id))

#     update_deployment_template_info(deployment_worker_info)

#     update_test_variable_and_db(deployment_worker_info)

#     return deployment_worker_info

# def update_test_variable_and_db(deployment_worker_info):
#     """
#     Description: Update the test variable and data form in deployment.

#     Args:
#         deployment_worker_info (dict): get_deployment_worker_info 를 통해 받은 dictionary

#     Raises:
#         DeploymentDataFormDBInsertError
#         DeploymentDBUpdateInputTypeError
#     """    
#     # insert deployment data form
#     from deployment.service import  init_current_deployment_data_form
#     deployment_id=deployment_worker_info["deployment_id"]
#     deployment_form_list=deployment_worker_info.get("deployment_form_list")
#     init_result, message = init_current_deployment_data_form(deployment_id=deployment_id, 
#                                                         built_in_model_id=deployment_worker_info.get("built_in_model_id"),
#                                                         deployment_form_list=deployment_form_list)
#     if init_result == False:
#         print(message)
#         raise DeploymentDataFormDBInsertError

#     # Update data input type
#     if deployment_form_list:
#         deployment_worker_info["input_type"] = ",".join([ deployement_form["category"] for deployement_form in deployment_form_list])
#     update_result, message = db.update_deployment_input_type(deployment_id=deployment_id, input_type=deployment_worker_info.get("input_type"))
#     if update_result == False:
#         print(message)
#         raise DeploymentDBUpdateInputTypeError


# template 삭제
# def get_deployment_worker_info_o(deployment_worker_id):
#     from deployment.service import load_custom_api_system_info_to_json, init_current_deployment_data_form, get_deployment_type_info
#     # deployment_worker_id, deployment_id, deployment_name, deployment_type, workspace_name, gpu_count, gpu_model
#     # image, owner_name, training_name, workspace_id, input_type, run_code
#     # deployment_worker_info = db.get_deployment_worker_run_minimum_info(deployment_worker_id=deployment_worker_id)
#     # deployment_id = db.get_deployment_worker(deployment_worker_id=deployment_worker_id).get("deployment_id")
#     deployment_worker_info = db.get_deployment_worker_run_minimum_info(deployment_worker_id)
#     # deployment_worker_info["deployment_worker_id"]=deployment_worker_id
#     deployment_worker_info["checkpoint"]=None
#     deployment_worker_info["checkpoint_id"]=None
#     deployment_worker_info["checkpoint_dir_path"]=None
#     deployment_worker_info["checkpoint_workspace_name"]=None
#     deployment_worker_info["built_in_model_path"]=None
#     deployment_worker_info["built_in_model_id"]=None
#     deployment_worker_info["checkpoint_load_dir_path_parser"]=None 
#     deployment_worker_info["checkpoint_load_file_path_parser"]=None
#     deployment_worker_info["deployment_num_of_gpu_parser"]=None
#     deployment_form_list=None
#     input_type=None
#     deployment_id = deployment_worker_info["deployment_id"]

#     deployment_running_type = get_deployment_type_info(id=deployment_worker_id, is_worker=True)
#     deployment_worker_info["running_type"] = deployment_running_type
#     if deployment_running_type==None:
#         return response(status=0, message="Deployment Run Type Undefined")

#     # CASE 1. Custom - run_code
#     # deployment_py_command, deployment_form_list 따로 받기
#     # checkpoint_load_dir_path_parser,checkpoint_load_file_path_parser, deployment_num_of_gpu_parser
#     if deployment_running_type==DEPLOYMENT_RUN_CUSTOM:
#         model_info_json = load_custom_api_system_info_to_json(deployment_id=deployment_id)
#         if model_info_json:
#             deployment_form_list = model_info_json["deployment_input_data_form_list"]

#             for key in ["checkpoint_load_dir_path_parser","checkpoint_load_file_path_parser","deployment_num_of_gpu_parser"]:
#                 if key in model_info_json.keys():
#                     deployment_worker_info[key]=model_info_json[key]

#         else:
#             deployment_form_list = None
#         if '/src/' == deployment_worker_info["run_code"][:5]:
#             deployment_worker_info["deployment_py_command"] = deployment_worker_info["run_code"][1:]
#         else:
#             deployment_worker_info["deployment_py_command"] = deployment_worker_info["run_code"]


#     # CASE 2. Built_in - checkpoint_id (checkpoint_id가 built_in_model + checkpoint 파일
#     # checkpoint_id, checkpoint_dir_path, checkpoint_workspace_name, built_in_model_path
#     elif deployment_running_type==DEPLOYMENT_RUN_CHEKCPOINT:
#         additional_info = db.get_deployment_worker_checkpoint_run_info(deployment_worker_id=deployment_worker_id)
#         deployment_worker_info.update(additional_info)
#         deployment_form_list = db.get_built_in_model_data_deployment_form(deployment_worker_info["built_in_model_id"])

#     # CASE 3. Built_in - pretrained - built_in_model run_code
#     # CASE 4. Built_in - usertrained - built_in_model run_code + checkpoint_file
#     elif deployment_running_type in [DEPLOYMENT_RUN_PRETRAINED, DEPLOYMENT_RUN_USERTRAINED]:
#         additional_info = db.get_deployment_worker_built_in_run_info(deployment_worker_id=deployment_worker_id)
#         deployment_worker_info.update(additional_info)
#         deployment_form_list = db.get_built_in_model_data_deployment_form(deployment_worker_info["built_in_model_id"])

#     # Insert data input form
#     init_result, message = init_current_deployment_data_form(deployment_id=deployment_id, built_in_model_id=deployment_worker_info["built_in_model_id"],
#                                                             deployment_form_list=deployment_form_list)
#     if init_result == False:
#         raise Exception("Insert deployemnt data form error : {}".format(message))

#     # Update data input type
#     if deployment_form_list:
#         input_type = ",".join([ deployement_form["category"] for deployement_form in deployment_form_list])
#     db.update_deployment_input_type(deployment_id=deployment_id, input_type=input_type)

#     return deployment_worker_info

# def update_deployment_worker_description(deployment_worker_id, description):
#     try:

#         update_result, message = db_deployment.update_deployment_worker_description(deployment_worker_id=deployment_worker_id, description=description)
#         if update_result:
#             return response(status=1, message="Updated")
#         else:
#             print("Deployment Worker description update error : {}".format(message))
#             raise DeploymentWorkerDescriptionDBUpdateError
#             # return response(status=0, message="Deployment Worker description update error : {}".format(message))


#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Worker description update error : {}".format(e))

# def check_deployment_worker_log_file(workspace_name, deployment_name, deployment_worker_id, nginx_log=True, api_log=True):
#     result = {
#         "error": 0,
#         "message": "",
#         "monitor_log": [],
#         "nginx_access_log": []
#     }

#     deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     try :
#         worker_log_dir_file_list = os.listdir(deployment_worker_log_dir)
#     except OSError as ose:
#         # No log
#         result["error"] = 1
#         result["message"] = "No Log"
#         return result
#     except Exception as e:
#         traceback.print_exc()
#         # Unknown error
#         result["error"] = 1
#         result["message"] = "Unknown error {}".format(e)
#         return result

#     if check_deployment_api_monitor_import(worker_log_dir_file_list) == False:
#         # api monitor not imported
#         result["message"] = "API Monitor Not Imported"
    
#     monitor_file_path = "{}/{}".format(deployment_worker_log_dir, POD_API_LOG_FILE_NAME)
#     nginx_access_file_path = "{}/{}".format(deployment_worker_log_dir, POD_NGINX_ACCESS_LOG_FILE_NAME)

#     # monitor.txt 의 time, response_time 추출해 list 에 담기
#     if api_log:
#         try:
#             with open(monitor_file_path, "r") as f:
#                 monitor_log = f.read().splitlines()
#         except:
#             monitor_log = []
#             result["message"] = "No Monitor Log"
#         result["monitor_log"] = monitor_log
        
#     if nginx_log:
#         try:
#             with open(nginx_access_file_path, "r") as f:
#                 nginx_access_log = f.read().splitlines()
#         except:
#             print("NGINX ACCESS LOG ERROR ")
#             traceback.print_exc()
#             nginx_access_log = []
#             result["message"] = "No Nginx Log"
#         result["nginx_access_log"] = nginx_access_log
#     return result

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
#     log_dir_path = JF_DEPLOYMENT_PATH.format(workspace_name=workspace_name, deployment_name=deployment_name)+"/log"
#     if os.path.exists(log_dir_path)==False:
#         return result
#     if deployment_worker_id!=None:
#         log_dir_list = [str(deployment_worker_id)]
#     else:
#         log_dir_list = os.listdir(log_dir_path)
#     for log_dir in log_dir_list:
#         if os.path.isdir(os.path.join(log_dir_path, str(log_dir))):
#             deployment_worker_run_time_file_path = GET_POD_RUN_TIME_FILE_PATH_IN_JF_API(workspace_name=workspace_name,
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
#             elif check_worker_dir_and_install(workspace_name, deployment_name, [log_dir])==False:
#                 result["message"]="Worker Installing"
#     if len(result["log_dir"])==0:
#         return result
#     result["error"]=0
#     result["message"]=""
#     return result

# def get_graph_log(end_time, start_time=None, deployment_id=None, deployment_worker_id=None, worker_list=None, nginx_log=True, api_log=True):
#     from ast import literal_eval
#     import time
#     result={
#         "error": 0,
#         "message": "",
#         "monitor_log": [],
#         "nginx_access_log": [],
#         "deployment_worker_id":None
#     }
#     if deployment_id!=None:
#         info = db.get_deployment_name_info(deployment_id=deployment_id)
#     elif deployment_worker_id!=None:
#         info = db.get_deployment_worker_name_info(deployment_worker_id=deployment_worker_id)
#     else:
#         return None
#     workspace_name = info.get("workspace_name")
#     deployment_name = info.get("deployment_name")
#     result_list = []
#     if worker_list==None:
#         log_dir_result = check_deployment_worker_log_dir(start_time=start_time, end_time=end_time,
#                                                                 workspace_name=workspace_name, deployment_name=deployment_name,
#                                                                 deployment_worker_id=deployment_worker_id)
#         if log_dir_result["error"]==1:
#             result["error"]=1
#             result["message"]=log_dir_result["message"]
#             result_list=[result]
#             return result_list
#         else:
#             worker_list = log_dir_result["log_dir"]
#     # else:
#     # load_file_time=time.time()
#     for log_dir in worker_list:
#         result = check_deployment_worker_log_file(workspace_name, deployment_name, log_dir, nginx_log, api_log)
#         result["deployment_worker_id"]=int(log_dir)
#         result_list.append(result)
#     # str 을 dic 형태로 변경
#     # dic_log_time=time.time()
#     if nginx_log:
#         for result in result_list:
#             result["nginx_access_log"] = [json.loads(dic) for dic in result["nginx_access_log"]]
#     if api_log:
#         for result in result_list:
#             try:
#                 result["monitor_log"] = [json.loads(dic.replace("\'", "\"")) for dic in result["monitor_log"]]
#             except:
#                 try:
#                     result["monitor_log"] = [literal_eval(dic) for dic in result["monitor_log"]]
#                 except:
#                     pass
#     return result_list

# def get_file_line_count(file_path, file_name):
#     cmd = "cd {} && cat {} | wc -l".format(file_path, file_name)
#     return int(subprocess.check_output(cmd, shell=True).strip().decode())


# def get_nginx_success_count(file_path):
#     result=0
#     for i in [2,3]:
#         grep_str = '"status": "{}[0-9][0-9]"'.format(i)
#         cmd = "cd {} &&grep '{}' {} |wc -l".format(file_path, grep_str, POD_NGINX_ACCESS_LOG_FILE_NAME)
#         result += int(subprocess.check_output(cmd, shell=True).strip().decode())
#     return result


# =======================================================================================================
# 주석 ==================================================================================================
# =======================================================================================================

# # run_deployment_worker =============================================
# # deployments_worker.get("/run") 사용 안되는 것 같음 -> post("") 로 worker 실행하는 것으로 파악됨
# def run_deployment_worker(deployment_worker_id, headers_user):
#     """
#     Description : Run Deployment Worker

#     Args :
#         deployment_worker_id (int) 
#         headers_user (str) : user name. from self.check_user()

#     Returns :
#         response()
#     """
#     try:
#         deployment_worker_info = get_deployment_worker_info(deployment_worker_id=deployment_worker_id)
#         run_result = ""
#         message = ""
#         # MSA lock 제거
#         # with jf_scheduler_lock:
#         check_result = scheduler.check_immediate_running_item_resource_new(requested_gpu_count=deployment_worker_info['gpu_count'], gpu_usage_type=DEPLOYMENT_TYPE, 
#                                             workspace_id=deployment_worker_info["workspace_id"], rdma_option=0, 
#                                             gpu_model=deployment_worker_info["gpu_model"], node_name=deployment_worker_info["node_name"])

#         if check_result is not None:
#             deployment_worker_info["executor_id"] = db.get_user(user_name=headers_user)["id"]
#             deployment_worker_info["executor_name"] = headers_user
#             deployment_worker_info[DEPLOYMENT_API_MODE_LABEL_KEY] = DEPLOYMENT_API_MODE
#             run_result, message = create_deployment_pod(deployment_worker_info, check_result["node_groups"])

#         else:
#             run_result = False
#             message = "No Resource"

#         if run_result:
#             return response(status=1, message="Deployment Run")
#         else:
#             return response(status=0, message="Deployment Cannot Run : [{}]".format(message))
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Cannot Run")

# def run_deployment_worker_new_method(deployment_worker_id, headers_user):
#     """
#     Description :
#         MSA 변경 scheduler.check_immediate_running_item_resource_new -> if 삭제

#     Args :
#         deployment_worker_id (int) 
#         headers_user (str) : user name. from self.check_user()

#     Returns :
#         response()
#     """
#     try:
#         print("Run deployment worker - method TEST")
#         deployment_worker_info = get_deployment_worker_info(deployment_worker_id=deployment_worker_id)
#         run_result = ""
#         message = ""

#         # check_result = scheduler.check_immediate_running_item_resource_new(requested_gpu_count=deployment_worker_info['gpu_count'], gpu_usage_type=DEPLOYMENT_TYPE, 
#         #                                             workspace_id=deployment_worker_info["workspace_id"], rdma_option=0, 
#         #                                             gpu_model=deployment_worker_info["gpu_model"], node_name=deployment_worker_info["node_name"])

#         # if check_result is not None:
#         executor_id = db.get_user(user_name=headers_user)["id"]
#         executor_name = headers_user
#         owner_name = deployment_worker_info["owner_name"]

#         # ENV/Volume/Label 용 정보
#         workspace_id = deployment_worker_info["workspace_id"]
#         workspace_name = deployment_worker_info["workspace_name"]
#         deployment_id = deployment_worker_info["deployment_id"]
#         deployment_name = deployment_worker_info["deployment_name"]
#         deployment_worker_id = deployment_worker_info["deployment_worker_id"]
#         deployment_type = deployment_worker_info["deployment_type"]
#         deployment_template_type = deployment_worker_info[DEPLOYMENT_TEMPLATE_TYPE_KEY]

#         # Pod 기반 정보
#         total_gpu_count = deployment_worker_info["gpu_count"]
#         # node_info = check_result.node_info_list[0]
#         docker_image_real_name = deployment_worker_info["image_real_name"]

#         # ================================================================
#         # node name 임시            
#         node_name=None
#         node_name_list = list(deployment_worker_info["node_name"].keys())
#         if node_name_list == ['@all'] or node_name_list == []:
#             node_name=None
#         elif len(node_name_list) == 1:
#             # ['@all'] 아닌데 len 1인경우
#             node_name = node_name_list[0]
#         elif len(node_name_list) > 1:
#             import random
#             # ['@all'] 이 아닌데 1보다 큰경우
#             node_name_list.remove('@all')
#             node_name = random.choice(node_name_list)
#         # ================================================================
        
#         # Optional
#         training_name = deployment_worker_info.get("training_name")
#         mounts = deployment_worker_info.get(DEPLOYMENT_TEMPLATE_MOUNT_KEY)
#         environments = deployment_worker_info.get(DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY)
#         workdir = deployment_worker_info.get(DEPLOYMENT_TEMPLATE_WORKING_DIRECTORY_KEY)
#         api_path = deployment_worker_info.get("api_path")
#         built_in_model_path = deployment_worker_info.get("built_in_model_path")
#         checkpoint_dir_path = deployment_worker_info.get("checkpoint_dir_path")
#         deployment_api_mode = DEPLOYMENT_API_MODE
        
#         # 실행 정보
#         run_code = get_deployment_run_code(deployment_worker_info=deployment_worker_info)

#         # MSA
#         # kube api -> helm
#         """
#         MSA 변경
#         create_deployment_pod_new_method -> create_deployment_pod_new_method
#         """
#         run_result, message = helm.create_deployment_helm(workspace_name=workspace_name, workspace_id=workspace_id, training_name=training_name,
#                                                     parent_deployment_worker_id=None, executor_id=executor_id, executor_name=executor_name,
#                                                     deployment_name=deployment_name, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id, 
#                                                     deployment_api_mode=deployment_api_mode, deployment_type=deployment_type, deployment_template_type=deployment_template_type,
#                                                     owner_name=owner_name, workdir=workdir, environments=environments, run_code=run_code,
#                                                     built_in_model_path=built_in_model_path, checkpoint_dir_path=checkpoint_dir_path, mounts=mounts, 
#                                                     total_gpu_count=total_gpu_count, docker_image_real_name=docker_image_real_name,
#                                                     node_name=node_name, api_path=api_path, gpu_uuid_list=None,)
            
#         # run_result, message = create_deployment_pod_new_method(workspace_id=workspace_id, workspace_name=workspace_name, deployment_id=deployment_id, deployment_name=deployment_name, 
#         #                                 deployment_worker_id=deployment_worker_id, executor_id=executor_id, executor_name=executor_name, owner_name=owner_name, 
#         #                                 deployment_type=deployment_type, deployment_template_type=deployment_template_type, training_name=training_name,
#         #                                 node_info=node_info, total_gpu_count=total_gpu_count,
#         #                                 deployment_api_mode=deployment_api_mode, run_code=run_code, docker_image_real_name=docker_image_real_name,
#         #                                 built_in_model_path=built_in_model_path, checkpoint_dir_path=checkpoint_dir_path, 
#         #                                 mounts=mounts, environments=environments, workdir=workdir,
#         #                                 api_path=api_path, gpu_uuid_list=None, parent_deployment_worker_id=None)

#         # else:
#         #     run_result = False
#         #     message = "No Resource"

#         if run_result:
#             return response(status=1, message="Deployment Run")
#         else:
#             # raise DeploymentCreatePodError
#             return response(status=0, message="Deployment Cannot Run : [{}]".format(message))
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Cannot Run")

# def run_deployment_worker_gpu_share(deployment_worker_id, headers_user, force_node_name, gpu_uuid_list, parent_deployment_worker_id):
#     try:

#         deployment_worker_info = get_deployment_worker_info_o(deployment_worker_id=deployment_worker_id)

#         run_result = ""
#         message = ""
        
#         force_gpu_model = db.get_deployment_worker(deployment_worker_id=deployment_worker_id)["configurations"]
#         check_result = scheduler.check_immediate_running_item_resource_force(req_gpu_count=deployment_worker_info['gpu_count'], gpu_model=deployment_worker_info["gpu_model"], 
#                                                             force_node_name=force_node_name, force_gpu_model=force_gpu_model)

#         if check_result["flag"] == True:
#             deployment_worker_info["executor_id"] = db.get_user(user_name=headers_user)["id"]
#             deployment_worker_info["executor_name"] = headers_user
#             deployment_worker_info[DEPLOYMENT_API_MODE_LABEL_KEY] = DEPLOYMENT_API_MODE
#             run_result, message = create_deployment_pod(pod_info=deployment_worker_info, node_groups=check_result["node_groups"], 
#                                                         gpu_uuid_list=gpu_uuid_list, parent_deployment_worker_id=parent_deployment_worker_id)

#         else:
#             run_result = False
#             message = check_result["message"]

#         if run_result:
#             return response(status=1, message="Deployment Run")
#         else:
#             print("Deployment Cannot Run : [{}]".format(message))
#             # return response(status=0, message="Deployment Cannot Run : [{}]".format(message))
#             raise DeploymentCreatePodError
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Cannot Run")

# # add_deployment_worker =============================================
# def add_deployment_worker(deployment_id):
#     try:
        
#         deployment_info = db.get_deployment(deployment_id=deployment_id)
#         description = deployment_info["description"]
#         template_id = deployment_info["template_id"]
#         gpu_count = deployment_info["gpu_count"]
#         gpu_model = deployment_info["gpu_model"]
#         node_mode = deployment_info["node_mode"]
#         node_name = deployment_info["node_name"]
#         docker_image_id = deployment_info["docker_image_id"] 
#         token = deployment_info["token"]
#         user_id = deployment_info["user_id"]
#         executor_id = deployment_info["executor_id"]

#         # deployment_id, description, template_id, 
#         # gpu_count, gpu_model, node_mode, node_name,
#         # docker_image_id, token, user_id, executor_id

#         inserted_id, message = db.insert_deployment_worker(deployment_id=deployment_id, description=description, template_id=template_id, 
#                             gpu_count=gpu_count, gpu_model=gpu_model, node_mode=node_mode, node_name=node_name,
#                             docker_image_id=docker_image_id, token=token, user_id=user_id, executor_id=executor_id)
#         print("INSERTED ID (add_deployment_worker) ", inserted_id)
#         if inserted_id == False:
#             print("Add Deployment Worker error : {}".format(message))
#             raise WorkerDBInsertError
#             # return response(status=0, message="Add Deployment Worker error : {}".format(message))

#         return response(status=1, message="OK", inserted_id=inserted_id)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Add Deployment Worker error")

# def add_deployment_worker_with_run(deployment_id, headers_user):
#     """
#     Description :

#     Args :
#         deployment_id (int) 
#         headers_user (str) : user name. from self.check_user()

#     Returns :
#         response()
#     """
#     try:
#         deployment_info = db.get_deployment(deployment_id=deployment_id)
#         workspace_id = deployment_info["workspace_id"]
#         description = deployment_info["description"]
#         # training_id = deployment_info["training_id"]
#         # training_name = deployment_info["training_name"]
#         # built_in_model_id = deployment_info["built_in_model_id"]
#         # job_id = deployment_info["job_id"]
#         # run_code = deployment_info["run_code"]
#         # checkpoint = deployment_info["checkpoint"]
#         # checkpoint_id = deployment_info["checkpoint_id"]
#         gpu_count = deployment_info["gpu_count"]
#         gpu_model = deployment_info["gpu_model"]
#         node_mode = deployment_info["node_mode"]
#         node_name = deployment_info["node_name"]
#         docker_image_id = deployment_info["docker_image_id"] 
#         token = deployment_info["token"]
#         user_id = deployment_info["user_id"]
#         executor_id = deployment_info["executor_id"]
#         run_item_deleted(item_deleted_info=deployment_info["item_deleted"])
#         # MSA lock 제거
#         # with jf_scheduler_lock:
#         # check_result = scheduler.check_immediate_running_item_resource_new(requested_gpu_count=gpu_count, gpu_usage_type=DEPLOYMENT_TYPE, 
#         #                                                     workspace_id=workspace_id, rdma_option=0, 
#         #                                                     gpu_model=gpu_model, node_name=node_name)
#         # if check_result is None:
#         #     print("Add Deployment Worker Fail : {}")
#         #     raise DeploymentRunSchedulerError
#         #     # return response(status=0, message="Add Deployment Worker Fail : {}".format(check_result["message"]))
        
#         # 템플릿 분기 처리 변경 예정 => Lyla
#         # if deployment_info["template_id"]==None:
#         #     add_result = add_deployment_worker_o(deployment_id=deployment_id)
#         #     if add_result["status"] == 1:
#         #         return run_deployment_worker_o(deployment_worker_id=add_result["inserted_id"], headers_user=headers_user)
#         #     else :
#         #         return add_result
#         # else:
#         add_result = add_deployment_worker(deployment_id=deployment_id)
#         if add_result["status"] == 1:
#             return run_deployment_worker_new_method(deployment_worker_id=add_result["inserted_id"], headers_user=headers_user) # TODO 테스트중
#         else :
#             return add_result
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         raise ce
#     except Exception as e:
#         traceback.print_exc()
#         raise e    

# def add_deployment_worker_gpu_share(deployment_worker_id):
#     try:
#         deployment_worker_info = db.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#         deployment_id = deployment_worker_info["deployment_id"]
#         gpu_count = deployment_worker_info["gpu_count"]
#         gpu_model = deployment_worker_info["gpu_model"]
#         configurations = deployment_worker_info["configurations"]

#         deployment_info = db.get_deployment(deployment_id=deployment_id)

#         workspace_id = deployment_info["workspace_id"]
#         description = deployment_info["description"]
#         training_id = deployment_info["training_id"]
#         training_name = deployment_info["training_name"]
#         built_in_model_id = deployment_info["built_in_model_id"] # 확인 필요 => Lyla
#         job_id = deployment_info["job_id"]
#         run_code = deployment_info["run_code"]
#         checkpoint = deployment_info["checkpoint"]
#         checkpoint_id = deployment_info["checkpoint_id"]
#         gpu_count = deployment_info["gpu_count"]
#         gpu_model = deployment_info["gpu_model"]
#         node_mode = deployment_info["node_mode"]
#         node_name = deployment_info["node_name"]
#         docker_image_id = deployment_info["docker_image_id"] 
#         token = deployment_info["token"]
#         user_id = deployment_info["user_id"]
#         executor_id = deployment_info["executor_id"]


#         inserted_id, message = db.insert_deployment_worker_o(deployment_id=deployment_id, description=description, training_id=training_id, training_name=training_name, 
#                             built_in_model_id=built_in_model_id, job_id=job_id, run_code=run_code, checkpoint=checkpoint, checkpoint_id=checkpoint_id, 
#                             gpu_count=gpu_count, gpu_model=gpu_model, node_mode=node_mode, node_name=node_name,
#                             docker_image_id=docker_image_id, token=token, user_id=user_id, executor_id=executor_id, configurations=configurations)
#         print("INSERTED ID (add_deployment_worker_gpu_share) ", inserted_id)
#         if inserted_id == False:
#             return response(status=0, message="Add Deployment Worker error : {}".format(message))

#         return response(status=1, message="OK", inserted_id=inserted_id)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Add Deployment Worker error")

# def add_deployment_worker_with_run_gpu_share(deployment_worker_id, headers_user):
#     """
#     Description :
#         API 확인 안됨, trigger 에서 사용??
#     Args :
#         deployment_id (int) 
#         headers_user (str) : user name. from self.check_user()
#     Returns :
#         response()
#     """
#     try:
#         pod_list = kube.kube_data.get_pod_list()
#         gpu_uuid_list, node_name = kube.get_pod_gpu_uuid_list_and_node_name(pod_list=pod_list, deployment_worker_id=deployment_worker_id)
#         #TODO GPU Copy를 못하는 - deployment worker가 종료된 상태거나, parsing이 불가능한 상태라면 실패 처리 필요
#         print(gpu_uuid_list, node_name)
#         if len(gpu_uuid_list) == 0 or node_name is None:
#             raise Exception("Unable to get GPU share related information.")
        
#         # MSA lock 제거
#         # with jf_scheduler_lock:
#         add_result = add_deployment_worker_gpu_share(deployment_worker_id=deployment_worker_id)
#         if add_result["status"] == 1:
#             return run_deployment_worker_gpu_share(deployment_worker_id=add_result["inserted_id"], headers_user=headers_user,
#                                                     force_node_name=node_name, gpu_uuid_list=gpu_uuid_list, parent_deployment_worker_id=deployment_worker_id)
#         else :
#             return add_result
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()

#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Add Deployment worker error : {}".format(e))

# def stop_deployment_worker_with_delete(deployment_worker_id):
#     return delete_deployment_worker(deployment_worker_id=deployment_worker_id)

# def get_deployment_worker_list(deployment_id, user_id):
#     """
#     deployment worker list 조회용
#     deployment_worker_status에서 restart_count 없으면 미리보기 터짐
#     deployment_worker_status에서 status running 일때 run_version, running_info 없으면 터짐
#     running_info history는 미리보기 누를떄 없으면 터짐
#     """
#     def is_changed(deployment_worker_info, deployment_info):
#         if str(deployment_info) != str(deployment_worker_info):
#             return deployment_info
#         else :
#             return False

#    # 템플릿 적용
#     def get_running_worker_info(deployment_worker_id, deployment_name, workspace_name, deployment_worker_info, permission_level):
#         # pod_all_resource_info = get_pod_all_resource(pod_list=pod_list, deployment_worker_id=deployment_worker_id, status=KUBE_POD_STATUS_RUNNING)
#         run_version = [ check_deployment_worker_version_change(deployment_worker_id) ] + [ { k : v } for k, v in get_deployment_running_info(id=deployment_worker_id, is_worker=True).items() ]
#         worker_run_time = get_deployment_worker_run_time(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)

#         chart_data = get_deployment_worker_per_hour_chart_dict(deployment_worker_id=deployment_worker_id, workspace_name=workspace_name, deployment_name=deployment_name)
#         resource_usage_graph = get_deployment_worker_resource_usage_graph(deployment_worker_id=deployment_worker_id, interval=60)["result"]
#         return {
#             "deployment_worker_id": deployment_worker_id,
#             "description": deployment_worker_info["description"],
#             "run_time": worker_run_time,
#             "run_env":[
#                 { "docker_image": deployment_worker_info["image_name"] },
#                 { "gpu_model": common.convert_gpu_model(deployment_worker_info["gpu_model"]) },
#                 { "gpu_count": deployment_worker_info["gpu_count"] },
#                 { "run_code": deployment_worker_info["run_code"] },
#             ],
#             "run_version": run_version,
#             "running_info": [
#                 { "configurations": deployment_worker_info["configurations"] },
#                 # { "cpu_cores": "{} | {}%".format(pod_all_resource_info["cpu_cores"], pod_all_resource_info["cpu_cores_usage"]) },
#                 # { "ram": "{} | {}%".format(pod_all_resource_info["ram"], pod_all_resource_info["ram_usage_per"]) },
#                 # { "gpus": pod_all_resource_info["gpus"] },
#                 # { "network": pod_all_resource_info["network"] },
#                 { "cpu_cores": "{} | {}%".format(resource_usage_graph["cpu_cores"]["cpu_cores_total"], resource_usage_graph["cpu_cores"]["cpu_cores_usage"]) },
#                 { "ram": "{} | {}%".format(resource_usage_graph["ram"]["ram_total"], resource_usage_graph["ram"]["ram_usage"]) },
#                 { "gpus": resource_usage_graph["gpus"] },
#                 { "network": resource_usage_graph["network"] },
#                 { "call_count_chart": chart_data["call_count_chart"]  },
#                 { "median_chart": chart_data["median_chart"] },
#                 { "nginx_abnormal_count_chart": chart_data["nginx_abnormal_count_chart"] },
#                 { "api_monitor_abnormal_count_chart": chart_data["api_monitor_abnormal_count_chart"] },
#                 { "mem_history" : resource_usage_graph.get("mem_history") },
#                 { "cpu_history" : resource_usage_graph.get("cpu_history") },
#                 { "gpu_history" : resource_usage_graph.get("gpu_history") }
#             ],
#             "worker_status": deployment_worker_status,
#             "permission_level": permission_level
#         }

#     def get_stop_worker_info(deployment_worker_id, workspace_name, deployment_name, deployment_worker_info, permission_level):
#         worker_run_time_info = get_deployment_worker_run_time_info(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         run_time = get_deployment_worker_run_time(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         return {
#             "deployment_worker_id": deployment_worker_id,
#             "operation_time": run_time,
#             "start_datetime": worker_run_time_info.get(POD_RUN_TIME_START_TIME_KEY),
#             "end_datetime": worker_run_time_info.get(POD_RUN_TIME_END_TIME_KEY),
#             "description": deployment_worker_info["description"],
#             "log_size": get_deployment_worker_log_size(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id) ,
#             "call_count": get_deployment_worker_nginx_call_count(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id),
#             "permission_level": permission_level
#         }

#     try:
#         permission_level = check_deployment_access_level(user_id=user_id, deployment_id=deployment_id) # permission_level 3 넘어가면 삭제 불가능
#         deployment_worker_list = db.get_deployment_worker_list(deployment_id=deployment_id)
#         deployment_info = db.get_deployment(deployment_id=deployment_id)
#         workspace_name = deployment_info["workspace_name"]
#         deployment_name = deployment_info["name"]

#         if deployment_worker_list is None or len(deployment_worker_list) == 0:
#             return response(status=1, result=[])

#         # pod_list = kube.kube_data.get_pod_list()
#         worker_list = []
#         for deployment_worker_info in deployment_worker_list:
#             deployment_worker_id = deployment_worker_info["id"]
#             # 분기처리 삭제 예정 => Lyla
#             # get_worker_info = get_running_worker_info_o
#             # if  deployment_worker_info["template_id"]!=None:
#             #     get_worker_info = get_running_worker_info
#             # deployment_worker_status = kube.get_deployment_worker_status(deployment_worker_id=deployment_worker_id, pod_list=pod_list)

#             #MSA 수정
#                 deployment_worker_list(db) 에는 종료한 pod 기록이 남아있음, kube api 조회시 조회가 안되는 pod은 worker list에 추가 안하는 걸로 코드 변경
#                 아래의 if 코드가 worker가 동작하는 worker 인지 확인하는 과정으로 보여짐
#                 stop worker를 보여주는 경우가 있는지? get_stop_worker_info -> 주석처리
#             #
#             deployment_worker_status = kube_new.get_deployment_pod_status(deployment_worker_id=deployment_worker_id)
#             if deployment_worker_status["status"] == None:
#                 continue
#             worker_list.append((get_running_worker_info(deployment_worker_id=deployment_worker_id, deployment_name=deployment_name, 
#                                                         workspace_name=workspace_name, deployment_worker_info=deployment_worker_info, permission_level=permission_level)))
            
#             # if deployment_worker_running_status == 1:
#             #     # Run status Worker only
#             #     if deployment_worker_status["status"] not in KUBER_RUNNING_STATUS:
#             #         continue

#             #     worker_list.append(get_running_worker_info(deployment_worker_id=deployment_worker_id, deployment_name=deployment_name, 
#             #                                             workspace_name=workspace_name, deployment_worker_info=deployment_worker_info, permission_level=permission_level))

#             # elif deployment_worker_running_status == 0:
#             #     # Stop status Worker only
#             #     if deployment_worker_status["status"] not in KUBER_NOT_RUNNING_STATUS:
#             #         continue
#             #     worker_list.append(get_stop_worker_info(deployment_worker_id=deployment_worker_id, deployment_name=deployment_name, 
#             #                                             workspace_name=workspace_name, deployment_worker_info=deployment_worker_info, permission_level=permission_level))
#             # elif deployment_worker_running_status == 2:

#             #     worker_list.append(get_running_worker_info(deployment_worker_id=deployment_worker_id, deployment_name=deployment_name, 
#             #                                             workspace_name=workspace_name, deployment_worker_info=deployment_worker_info, permission_level=permission_level))

# def get_deployment_run_code(deployment_worker_info):
#     """
#         # 작업 진행 중 
#     """
#     deployment_py_command = deployment_worker_info.get("deployment_py_command")
#     # runcode 없는 경우 처리
#     if deployment_py_command == None or deployment_py_command.replace(" ", "") == "":
#         return None

#     if deployment_py_command.split(' ')[0][-3:]=='.py' and deployment_py_command[:6]!="python":
#         run_code = "python {deployment_py_command} ".format(deployment_py_command=deployment_py_command)
#     else:
#         run_code = "{deployment_py_command} ".format(deployment_py_command=deployment_py_command)
        
#     if deployment_worker_info.get("deployment_num_of_gpu_parser") is not None and deployment_worker_info.get("deployment_num_of_gpu_parser") != "":
#         run_code += " --{key} {value} ".format(key=deployment_worker_info["deployment_num_of_gpu_parser"], value=deployment_worker_info["gpu_count"])


#     if deployment_worker_info.get(DEPLOYMENT_TEMPLATE_TYPE_KEY) in [DEPLOYMENT_RUN_CUSTOM, DEPLOYMENT_RUN_USERTRAINED, DEPLOYMENT_RUN_CHEKCPOINT]:
#         checkpoint_base_path=deployment_worker_info.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_DIR_KEY)
#         checkpoint_file_path=deployment_worker_info.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY)

#         if deployment_worker_info.get("checkpoint_load_dir_path_parser") is not None and deployment_worker_info.get("checkpoint_load_dir_path_parser") != "":
#             run_code += "--{key} {value}/ ".format(key=deployment_worker_info.get("checkpoint_load_dir_path_parser"), value=checkpoint_base_path )

#         if deployment_worker_info.get("checkpoint_load_file_path_parser") is not None and deployment_worker_info.get("checkpoint_load_file_path_parser") != "":
#             run_code += "--{key} {value} ".format(key=deployment_worker_info.get("checkpoint_load_file_path_parser"), value=checkpoint_file_path )

#     run_code = common.convert_run_code_to_run_command(run_code=run_code)
#     return run_code

# def is_parent_deployment_worker(deployment_worker_id):
#     # 사용하는 곳에서 helm으로 변경되어 안씀
#     pod_list = kube.kube_data.get_pod_list()
#     item_list = kube.find_kuber_item_name_and_item(item_list=pod_list, deployment_worker_id=deployment_worker_id)
    
#     if len(item_list) == 0:
#         raise ItemNotExistError
        
#     deployment_worker_labels = kube.get_pod_item_labels(pod_list=pod_list, deployment_worker_id=deployment_worker_id)
#     parent_deployment_worker_id = deployment_worker_labels.get(PARENT_DEPLOYMENT_WORKER_ID_LABEL_KEY)
#     if str(deployment_worker_id) == str(parent_deployment_worker_id):
#         return True
#     else :
#         return False

# def get_dir_size(dir_path):
#     cmd = "cd {} && du -b".format(dir_path)
#     out = subprocess.check_output(cmd, shell=True).strip().decode()
#     try:
#         out = out.split("\t")[0]
#         return int(out)
#     except:
#         traceback.print_exc()
#         return None

# def get_dir_size(file_path):
#     if os.path.exists(file_path):
#         cmd = "du -b {}".format(file_path)
#         out = subprocess.check_output(cmd, shell=True).strip().decode()
#         try:
#             out = out.split("\t")[0]
#             return int(out)
#         except:
#             traceback.print_exc()
#             return None
#     else:
#         return 0

# def get_deployment_api_total_count_info(worker_dir_list, workspace_name, deployment_name):
#     # worker_dir_list = worker id list
#     import time
#     ndigits=3
#     result={
#         "total_call_count": 0,
#         "total_success_rate":0,
#         "total_log_size":0,
#         "restart_count": 0
#     }
#     total_call_count=0
#     # total_success=0
#     total_nginx_success=0
#     total_log_size_list=[]
#     check_import_list=[]
#     for worker_id_str in worker_dir_list:
#         deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(workspace_name=workspace_name, 
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
#         nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=int(worker_id_str))

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
#         check_import=check_deployment_api_monitor_import(file_list=file_list)
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
#         cpu_info = kube_new.get_pod_cpu_ram_usage_info(deployment_worker_id = int(worker_id_str))
#         if cpu_info!=None:
#             rate_dic["cpu_usage_rate"].append(cpu_info.get(CPU_USAGE_ON_POD_KEY))
#             rate_dic["ram_usage_rate"].append(cpu_info.get(MEM_USAGE_PER_KEY))
#         else:
#             # index 통해 min max worker id 구하기 위해서
#             rate_dic["cpu_usage_rate"].append(0)
#             rate_dic["ram_usage_rate"].append(0)
#         # get gpu info
#         gpu_info = kube_new.get_pod_gpu_usage_info(deployment_worker_id = int(worker_id_str))
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

# # 사용??
# def get_deployment_worker_log_download(deployment_worker_id, start_time, end_time, nginx_log, api_log):
#     try:
#         from deployment.service import get_worker_info_dic, download_logfile
#         info = db.get_deployment_worker_name_info(deployment_worker_id=deployment_worker_id)
#         workspace_name = info.get("workspace_name")
#         deployment_name = info.get("deployment_name")
#         log_dir_path = JF_DEPLOYMENT_PATH.format(workspace_name=workspace_name, deployment_name=deployment_name)+"/log"
#         deployment_path = JF_DEPLOYMENT_PATH.format(workspace_name=workspace_name, deployment_name=deployment_name)
#         # get log filter by worker => log_worker_list
#         worker_info = get_worker_info_dic(start_time=start_time, end_time=end_time, worker_list=[deployment_worker_id], deployment_path=deployment_path)
#         if len(worker_info)==0:
#             return response(status=0, message="No log in input time range")
#         log_worker_list = worker_info.keys()
#         # log worker list 통해 log list 받기 => [{"nginx_access_log":[], "monitor_log":[], "deployment_worker_id": },..]
#         result_list = get_graph_log(start_time=start_time, end_time=end_time, deployment_worker_id=deployment_worker_id, 
#                                     worker_list=log_worker_list, nginx_log=nginx_log, api_log=api_log)
#         if len(result_list)==0:
#             return response(status=0, message="unknown error")
#         # worker 없는경우
#         if len(result_list)==sum(result_list[i].get("error") for i in range(len(result_list))):
#             return response(status=0, message=result_list[0]["message"])
#         # log file download
#         result = download_logfile(result_list, worker_info, deployment_path, start_time, end_time, nginx_log, api_log, deployment_name)
#         return result

#     except Exception as e:
#         traceback.print_exc()
#         # os.system('rm -r {}'.format(save_dir_name))
#         return response(status=0, message="downloading log error")

# # 템플릿 적용
# def check_deployment_worker_version_change(deployment_worker_id):
#     # from deployment import get_deployment_running_info_o
#     from deployment.service import get_deployment_running_info
#     # TODO 추후 db.get_deployment_id_from_worker_id 로 변경 예정
#     deployment_worker_info = db.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#     deployment_id = deployment_worker_info.get("deployment_id")
#     # get_running_info=get_deployment_running_info_o
#     # if deployment_worker_info["template_id"] !=None:
#     # get_running_info=get_deployment_running_info

#     deployment_worker_running_info = get_deployment_running_info(id=deployment_worker_id, is_worker=True)
#     deployment_running_info = get_deployment_running_info(id=deployment_id)
#     result={
#         "changed": False,
#         "changed_items": []
#     }
#     if deployment_worker_running_info!=deployment_running_info:

#         # added_list=[]
#         # dropped_list=[]
#         modified_list = []
#         # if set(deployment_worker_running_info.keys())!=set(deployment_running_info.keys()):
#         #     added_list = list(set(deployment_worker_running_info.keys())-set(deployment_running_info.keys()))
#         #     dropped_list = list(set(deployment_running_info.keys())-set(deployment_worker_running_info.keys()))
#         for key in deployment_worker_running_info.keys():
#             if deployment_running_info.get(key)!=None:
#                 if deployment_worker_running_info[key]!=deployment_running_info[key]:
#                     modified_list.append({
#                         "item": key, 
#                         "latest_version": deployment_running_info[key], # 실행 시 반영 될 정보
#                         "current_version": deployment_worker_running_info[key] # 이미 실행 된 정보
#                     })
#         if len(modified_list)>0:
#             result["changed"]= True
#             # result["changed_items"]={"added":added_list, "droppped":dropped_list, "modified": modified_list}
#             result["changed_items"]=modified_list
#     return result

# def check_deployment_api_monitor_import(file_list):
#     if POD_API_LOG_IMPORT_CHECK_FILE_NAME in file_list:
#         # API MONITOR IMPORTED
#         return True
#     else:
#         return False

# def check_worker_dir_and_install(workspace_name, deployment_name, worker_dir_list): 
#     worker_dir_list=[str(i) for i in worker_dir_list]
#     status_list=[]
#     for worker_id_str in worker_dir_list:
#         deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(workspace_name=workspace_name, 
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
