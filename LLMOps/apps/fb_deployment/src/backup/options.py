# #####################################################################################################
# ####################################### 코드 백업 ####################################################
# #####################################################################################################

# import traceback
# import os
# import base64

# # import utils.db as db
# from utils.resource import response
# from utils import options
# from utils.TYPE import (TRAINING_TYPE, TRAINING_TYPE_A, TRAINING_TYPE_C, TRAINING_TYPE_D, TRAINING_BUILT_IN_TYPES,
#                         DEPLOYMENT_TYPE_A, DEPLOYMENT_TYPE_B, DEPLOYMENT_RUN_PRETRAINED, DEPLOYMENT_RUN_USERTRAINED,
#                         DEPLOYMENT_TYPE, DEPLOYMENT_TYPES, PORT_PROTOCOL_LIST, TOOL_DEFAULT_PORT, TOOL_TYPE)
# from utils.settings import JF_BUILT_IN_MODELS_PATH, JF_WS_DIR
# import kube

# def get_runcode_from_training_id(training_id):
#     try:
#         training_info = db.get_training(training_id=training_id)
#         run_code_list = options.get_run_code_list_from_src(workspace_name=training_info["workspace_name"], 
#                                                     training_name=training_info["training_name"])
#         return response(status=1, result={"run_code_list":run_code_list})
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get Deployment Template Option Fail")
    
# def get_checkpoint_from_training_id(training_id, sort_key, order_by, is_param):
#     try:
#         result = {
#             "job_list": options.get_job_checkpoint_info(training_id=training_id),
#             "hps_list": options.get_hps_checkpoint_info(training_id=training_id, sort_key=sort_key, order_by=order_by, is_param=is_param)
#         }
#         return response(status=1, result=result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get Deployment Template Option Fail")

# def get_deployment_template_option(workspace_id, deployment_template_type, headers_user):
#     def get_built_in_model_info(training_info_list, deployment_template_type):
#         result_list=[]
#         for info in training_info_list:
#             result = {
#                 "docker_image_id": info.get("docker_image_id"),
#                 "enable_to_deploy_with_gpu":info.get("enable_to_deploy_with_gpu"),
#                 "enable_to_deploy_with_cpu":info.get("enable_to_deploy_with_cpu"),
#                 "deployment_multi_gpu_mode": info.get("deployment_multi_gpu_mode"),
#                 "deployment_status": 1,
#                 "is_thumbnail":0
#             }
#             if info.get("type")==DEPLOYMENT_TYPE_A:
#                 if info["deployment_status"] != 1 or (info["enable_to_deploy_with_gpu"]!=1 and info["enable_to_deploy_with_cpu"]!=1):
#                     result["deployment_status"]=0
#             if deployment_template_type==DEPLOYMENT_RUN_PRETRAINED:
#                 result["deployment_status"]=info["exist_default_checkpoint"]
#                 if info["deployment_status"] != 1 or (info["enable_to_deploy_with_gpu"]!=1 and info["enable_to_deploy_with_cpu"]!=1):
#                     result["deployment_status"]=0
#             if info.get("thumbnail_path") !=None:
#                 result["is_thumbnail"]=1
#             result_list.append(result)
#         return result_list
#     try:
#         user_id=db.get_user_id(user_name=headers_user)["id"]
#         built_in_model_list = db.get_built_in_model_list()
#         result={}
#         if deployment_template_type==DEPLOYMENT_RUN_USERTRAINED:
#             built_in_training_list = db.get_workspace_built_in_training_list(workspace_id, user_id)
#             custom_training_list = db.get_workspace_custom_training_list(workspace_id, user_id)
#             # print("CHECK1", built_in_training_list)
#             # print("CHECK2", custom_training_list)
#             if built_in_training_list is None or len(built_in_training_list)==0:
#                 built_in_training_list = []
#             if custom_training_list is None or len(custom_training_list)==0:
#                 custom_training_list = []
#             # 리스트 두개 합치기
#             usertrained_training_list_tmp = built_in_training_list+custom_training_list

#             # 빌트인 모델 정보(배포 가능 방식, 배포 가능 여부, 썸네일 이미지) + 나머지 값들 업데이트
#             usertrained_training_list = get_built_in_model_info(usertrained_training_list_tmp, deployment_template_type)
#             built_in_key_list = ["built_in_model_id", "built_in_model_name", "built_in_model_kind"]
#             training_key_list = ["id", "name", "description", "user_id", "user_name", "type", "header_user_start_datetime", "bookmark"]
#             for i in range(len(usertrained_training_list)):
#                 for col in built_in_key_list:
#                     usertrained_training_list[i][col]=usertrained_training_list_tmp[i].get(col)
#                 for col in training_key_list:
#                     usertrained_training_list[i]["training_"+col]=usertrained_training_list_tmp[i][col]
#                 training_type = usertrained_training_list_tmp[i]["type"]
#                 usertrained_training_list[i]["deployment_type"] = DEPLOYMENT_TYPE_A if training_type==TRAINING_TYPE_C else DEPLOYMENT_TYPE_B
#             # id 역순으로 sorting
#             result["usertrained_training_list"]=sorted(usertrained_training_list, key=lambda x:(x["training_bookmark"], x["training_id"]), reverse=True)
#         elif deployment_template_type==DEPLOYMENT_RUN_PRETRAINED:
#             pretrained_built_in_model_list = get_built_in_model_info(built_in_model_list, deployment_template_type)
#             built_in_key_list = ["id", "name","kind", "description"]
#             for i in range(len(pretrained_built_in_model_list)):
#                 for col in built_in_key_list:
#                     pretrained_built_in_model_list[i]["built_in_model_"+col]=built_in_model_list[i][col]
#             result["pretrained_built_in_model_list"]=pretrained_built_in_model_list

#         built_in_model_thumbnail_image_info = {}
#         for info in built_in_model_list:
#             if info.get("thumbnail_path") != None:
#                 thumbnail_file_path = os.path.join(JF_BUILT_IN_MODELS_PATH, info.get("path"), info.get("thumbnail_path"))
#                 if os.path.isfile(thumbnail_file_path):
#                     with open(thumbnail_file_path, "rb") as image_file:
#                         file_extension = info["thumbnail_path"].split('.')[-1]
#                         built_in_model_thumbnail_image_info[info["id"]] = 'data:image/{};base64,'.format(
#                             file_extension) + str(base64.b64encode(image_file.read()).decode())
#         built_in_model_kind_list = db.get_built_in_model_kind_and_created_by()
#         # Sally 님 요청으로 key 값 변경: kind => label
#         for info in built_in_model_kind_list:
#             info["label"] = info["kind"]
#             del info["kind"]
#         result["built_in_model_kind_list"] = built_in_model_kind_list
#         result["built_in_model_thumbnail_image_info"] = built_in_model_thumbnail_image_info
#         return response(status=1, result=result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get Deployment Template Option Fail")


# def deployment_option(workspace_id, headers_user):
#     try:
#         if headers_user is None:
#             return response(status=0, message="Jf-user is None in headers")
#         if workspace_id == None:
#             # workspace_list
#             result = {
#                 "workspace_list" : db.get_workspace_name_and_id_list()
#             }
#             return response(status=1, result=result)
#         workspace_name = db.get_workspace(workspace_id=workspace_id)["workspace_name"]
#         # training_list = db.get_workspace_training_name_and_id_list(workspace_id=workspace_id, user_id=db.get_user_id(user_name=headers_user)["id"])
#         user_id=db.get_user_id(user_name=headers_user)["id"]
#         built_in_training_list = db.get_workspace_built_in_training_list(workspace_id, user_id)
#         custom_training_list = db.get_workspace_custom_training_list(workspace_id, user_id)
#         if built_in_training_list is None:
#             built_in_training_list = []
#         if custom_training_list is None:
#             custom_training_list = []


#         built_in_model_list = db.get_built_in_model_list()
#         trained_built_in_model_list = []
#         trained_built_in_model_list = [ {
#                                             "id": training["id"], 
#                                             "name": training["name"], 
#                                             "built_in_type": training["type"], 
#                                             "built_in_model_name" : training["built_in_model_name"],
#                                             "docker_image_id": training["docker_image_id"], 
#                                             "enable_to_deploy_with_gpu": training["enable_to_deploy_with_gpu"],
#                                             "enable_to_deploy_with_cpu": training["enable_to_deploy_with_cpu"],
#                                             "deployment_multi_gpu_mode": training["deployment_multi_gpu_mode"],
#                                             "deployment_status": training["deployment_status"], 
#                                             "header_user_job_start_datetime": training["header_user_start_datetime"]
#                                         } for training in built_in_training_list]
#                                         # } for training in training_list if training["type"] in TRAINING_BUILT_IN_TYPES ]
#         trained_built_in_model_list = options.get_training_checkpoints(workspace_name=workspace_name, model_list=trained_built_in_model_list)
#         trained_built_in_model_list = get_built_in_model_list_order_by_checkpoint_exist(trained_built_in_model_list)
#         trained_custom_model_list = [ {
#                                             "id": training["id"],
#                                             "name": training["name"],
#                                             "run_code_list":options.get_run_code_list_from_src(workspace_name=workspace_name, training_name=training["name"]),
#                                             "header_user_tool_start_datetime": training["header_user_start_datetime"]
#                                         } for training in custom_training_list]
#                                         # } for training in training_list if training["type"] != TRAINING_TYPE_C ]

#         # update_custom_list_with_run_code_count(trained_custom_model_list)
#         for info in trained_custom_model_list:
#             info["run_code_count"]=len(info["run_code_list"])
        
        
#         # 임시 주석
#         # pod_list = kube.kube_data.get_pod_list()
#         # node_list = kube.kube_data.get_node_list()

#         # gpu_model_status = kube.get_gpu_model_usage_status_with_other_resource_info(pod_list=pod_list, node_list=node_list)
#         # cpu_model_status = kube.get_cpu_model_usage_status_with_other_resource_info(pod_list=pod_list, node_list=node_list)
        
#         result = {
#             "built_in_model_kind_list": db.get_built_in_model_kind_and_created_by(), # TODO 삭제 예정
#             "built_in_model_list" : built_in_model_list,
#             "trained_built_in_model_list" : trained_built_in_model_list, # TODO 삭제 예정
#             "trained_custom_model_list" : trained_custom_model_list, # TODO 삭제 예정
#             "user_list": db.get_workspace_user_name_and_id_list(workspace_id),
#             "gpu_total": get_deployment_aval_gpu(workspace_id)["result"]["total_gpu"], #TODO remove
#             "gpu_usage_status": get_deployment_aval_gpu(workspace_id)["result"],
#             "docker_image_list": db.get_docker_image_name_and_id_list(workspace_id),
#             "gpu_model_status": options.get_gpu_model_status(),
#             "cpu_model_status": options.get_cpu_model_status()
#         }

#         return response(status=1, result=result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# def get_built_in_model_list_order_by_checkpoint_exist(trained_built_in_model_list):
#     no_checkpoint=[]
#     is_checkpoint=[]
#     for info in trained_built_in_model_list:
#         checkpoint_count = info.get("checkpoint_count")
#         if checkpoint_count == None or checkpoint_count == 0:
#             no_checkpoint.append(info)
#         else:
#             is_checkpoint.append(info)
#     return is_checkpoint+no_checkpoint


# def get_deployment_aval_gpu(workspace_id):
#     aval_gpu_info = {"total_gpu": 0, "free_gpu": 0}
#     try:

#         workspace_info = db.get_workspace(workspace_id=workspace_id)
#         if workspace_info is None:
#             return response(status=0, result=aval_gpu_info, message="Workspace id [{}] Not Exist".format(workspace_id))

#         total_gpu = workspace_info["gpu_deployment_total"]

#         workspace_used_gpu = kube.get_workspace_gpu_count(workspace_id=workspace_id)
#         if workspace_used_gpu is None:
#             workspace_used_gpu = 0
#         else :
#             workspace_used_gpu = workspace_used_gpu.get("{}_used".format(DEPLOYMENT_TYPE))
#         free_gpu = total_gpu - workspace_used_gpu

#         aval_gpu_info["total_gpu"] = total_gpu
#         aval_gpu_info["free_gpu"] = free_gpu

#         return response(status=1, result=aval_gpu_info)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, result=aval_gpu_info, message="Get deployment available gpu Error")
#         #return response(status=0, result=aval_gpu, message=str(e))
