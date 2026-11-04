# #####################################################################################################
# ####################################### 코드 백업 ####################################################
# #####################################################################################################

# from utils.resource import CustomResource, response, token_checker
# import traceback
# # import utils.db as db
# from utils.TYPE import *
# from utils.exceptions import *
# from utils import common
# from deployment import service as svc_deployment
# from utils.access_check import check_inaccessible_deployment_template, check_deployment_template_access_level, check_deployment_access_level


# def get_deployment_template(workspace_id, deployment_template_id):
#     try:
#         deployment_template_info = db.get_deployment_template_list(deployment_template_id)
#         deployment_template_info.update(deployment_template_info["template"])
#         result = {
#             "workspace_id": workspace_id,
#             "workspace_name": deployment_template_info["workspace_name"],
#             "name": deployment_template_info["name"],
#             "description": deployment_template_info["description"],
#             "user_id": deployment_template_info["user_id"],
#             "user_name": deployment_template_info["user_name"],
#             "deployment_template_type": deployment_template_info[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_TYPE_KEY],
#             "deployment_template": get_deployment_template_detail_info(deployment_template_info)
#         }
#         return response(status=1, result=result, message="OK")
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Create Deployment Template Fail")  

# def get_deployment_template_detail_info(deployment_template, template_key = "template"):
#     if deployment_template[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_TYPE_KEY] == DEPLOYMENT_RUN_SANDBOX:
#         result = deployment_template[template_key]
#         del result[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY]
#     else:
#         result = {
#             "deployment_type": deployment_template[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY],
#             "training_id": deployment_template.get(DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY),
#             "training_name": deployment_template.get(DEPLOYMENT_TEMPLATE_TRAINING_NAME_KEY),
#             "command": deployment_template.get(DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY),
#             "environments": deployment_template.get(DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY),
#             "built_in_model_id": deployment_template.get(DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY),
#             "built_in_model_name": deployment_template.get("built_in_model_name"),
#             "training_type": deployment_template.get(DEPLOYMENT_TEMPLATE_TRAINING_TYPE_KEY),
#             "job_id": deployment_template.get(DEPLOYMENT_TEMPLATE_JOB_ID_KEY),
#             "job_name": deployment_template.get("job_name"),
#             "job_group_index": deployment_template.get("job_group_index"),
#             "hps_id": deployment_template.get("hps_id"),
#             "hps_name": deployment_template.get("hps_name"),
#             "hps_group_index": deployment_template.get("hps_group_index"),
#             "hps_number": None,
#             "checkpoint": deployment_template.get(DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY)
#         }
#         if deployment_template.get(DEPLOYMENT_TEMPLATE_TRAINING_TYPE_KEY)==TRAINING_ITEM_C:
#             if deployment_template.get("hps_name")==None:
#                 hps_info = db.get_hyperparamsearch_list_from_hps_id_list([deployment_template.get("hps_id")])
#                 deployment_template["hps_name"] = hps_info["hps_name"]
#                 deployment_template["hps_group_index"] = hps_info["hps_group_index"]
                
#             hps_base_path = JF_TRAINING_HPS_CHECKPOINT_ITEM_POD_PATH.format(
#                 hps_name=deployment_template["hps_name"], hps_group_index=deployment_template["hps_group_index"]
#             )
#             # print("base path",hps_base_path)
#             result["hps_number"]=deployment_template[DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY].split(hps_base_path)[1].split("/")[1]
#     return result

# def get_deployment_template_list(workspace_id, deployment_template_group_id, is_ungrouped_template, headers_user):
#     try:
#         if is_ungrouped_template==1:
#             deployment_template_info_list = db.get_deployment_template_list_n(workspace_id=workspace_id, is_ungrouped_template=is_ungrouped_template)
#         elif deployment_template_group_id!=None:
#             deployment_template_info_list = db.get_deployment_template_list_n(workspace_id=workspace_id, deployment_template_group_id=deployment_template_group_id)
#         else:
#             deployment_template_info_list = db.get_deployment_template_list_n(workspace_id=workspace_id)
#         built_in_model_list = db.get_built_in_model_list()
#         built_in_model_list_dict = common.gen_dict_from_list_by_key(target_list=built_in_model_list, id_key="id")
        
#         deployment_template_info_result = []
#         deployment_template_name_list = []
#         for info in deployment_template_info_list:
#             info.update(info["template"])
#             deployment_template_name_list.append(info["name"])
#             # id, name, description, template, user_id, create_datetime
#             template_detail_info = get_deployment_template_detail_info(info)
#             deployment_template_info_result.append({
#                 "id": info["id"],
#                 "deployment_template_group_id":info["deployment_template_group_id"],
#                 "name": info["name"],
#                 "description": info["description"],
#                 "deployment_template_type": info[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_TYPE_KEY],
#                 "deployment_template": template_detail_info,
#                 "item_deleted": svc_deployment.get_item_deleted(item_deleted_info=info["item_deleted"], 
#                                                  built_in_model_name=info.get("built_in_model_name_real"), 
#                                                  deployment_type=template_detail_info.get("deployment_type")),
#                 "user_id": info["user_id"],
#                 "user_name": info["user_name"],
#                 "create_datetime": info["create_datetime"],
#                 "permission_level": check_deployment_template_access_level(user_id=headers_user, deployment_template_id=info["id"])
#             })
        
#         # 템플릿 생성 시 새로운 이름 default 값 받기 
#         deployment_template_new_name = svc_deployment.get_new_name(name_list=deployment_template_name_list,
#                                                     name_str=DEPLOYMENT_TEMPLATE_DEFAULT_NAME)
#         result = {
#             "deployment_template_info_list":deployment_template_info_result,
#             "deployment_template_new_name": deployment_template_new_name
#         }
#         return response(status=1, result=result, message="OK")
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Template Get Fail")   

# def create_deployment_template(workspace_id, deployment_template_id, deployment_template_name, deployment_template_description, 
#                                 deployment_template_group_id, deployment_template_group_name, deployment_template_group_description,
#                                 deployment_template, deployment_type, training_id, training_type, job_id, hps_id, hps_number,
#                                 checkpoint, command, environments, built_in_model_id, headers_user):
#     try:
#         # 템플릿 기본정보 아이템 생성
#         if deployment_template != None:
#             deployment_template_params = deployment_template
#             deployment_template_type_with_version = DEPLOYMENT_RUN_SANDBOX_V1
#         else:
#             deployment_template_params = {
#                 DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY: deployment_type,
#                 DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY: checkpoint,
#                 DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY: command,
#                 DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY: built_in_model_id,
#                 DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY: training_id,
#                 DEPLOYMENT_TEMPLATE_JOB_ID_KEY: job_id,
#                 DEPLOYMENT_TEMPLATE_HPS_ID_KEY: hps_id,
#                 DEPLOYMENT_TEMPLATE_HPS_NUMBER_KEY: hps_number,
#                 DEPLOYMENT_TEMPLATE_TRAINING_TYPE_KEY: training_type,
#                 DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY: environments
#             }
#             deployment_template_type_with_version = None
#         # template 저장
#         deployment_template_info = svc_deployment.create_template_by_template_params(template_params=deployment_template_params, workspace_id=workspace_id, owner_id=headers_user,
#                                 deployment_template_id=deployment_template_id, deployment_template_name=deployment_template_name, 
#                                 deployment_template_description=deployment_template_description,
#                                 deployment_template_group_id=deployment_template_group_id, deployment_template_group_name=deployment_template_group_name, 
#                                 deployment_template_group_description=deployment_template_group_description, deployment_template_type_with_version=deployment_template_type_with_version)

#         return response(status=1, message="Created Deployment Template")
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         raise ce
#     except Exception as e:
#         raise e

# def update_deployment_template(workspace_id, deployment_template_id, deployment_template_name, 
#                             deployment_template_description, deployment_template_group_id, 
#                             deployment_template_group_name, deployment_template_group_description, headers_user):
#     try:
#         # template group id 값 존재하는지 확인
#         # template group id 없는 경우 (새로 생성) 이름 체크 후 db insert
#         deployment_template_group_id = check_and_insert_deployment_template_group(
#                                                 deployment_template_group_id=deployment_template_group_id, 
#                                                 deployment_template_group_name=deployment_template_group_name, 
#                                                 deployment_template_group_description=deployment_template_group_description,
#                                                 workspace_id=workspace_id, user_id=headers_user)
#         # 권한 확인
#         check_result = check_inaccessible_deployment_template(user_id=headers_user, 
#                                             deployment_template_id=deployment_template_id, allow_max_level=4)
#         # 그룹 있는경우 이름 중복 체크
#         if deployment_template_group_id != None:
#             deployment_template_info = db.get_deployment_template_by_unique_key(
#                                                                     deployment_template_name=deployment_template_name, 
#                                                                     workspace_id=workspace_id,
#                                                                     deployment_template_group_id=deployment_template_group_id,
#                                                                     deployment_template_id=deployment_template_id)
#             if deployment_template_info != None:
#                 raise DeploymentTemplateNameExistError
#         # DB 업데이트
#         update_deployment_template_result, message = db.update_deployment_template(
#                                                     deployment_template_id=deployment_template_id,
#                                                     deployment_template_name=deployment_template_name,
#                                                     deployment_template_description=deployment_template_description,
#                                                     deployment_template_group_id=deployment_template_group_id)
#         if not update_deployment_template_result:
#             print("Deployment Template Error [{}]".format(message))
#             raise DeploymentTemplateDBUpdateError
#         return response(status=1, message="Update Deployment Template Success")  
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Update Deployment Template Fail")   

# def delete_deployment_template(deployment_template_ids, headers_user):
#     try:
#         # 권한확인
#         deployment_template_info_list = db.get_deployment_templates(deployment_template_ids)
#         for template_info in deployment_template_info_list:
#             check_result = check_inaccessible_deployment_template(user_id=headers_user, 
#                                                                 deployment_template_id=template_info['id'])

#         # db 에서 is_deleted 값을 1로 변경
#         deployment_template_ids = [str(info['id']) for info in deployment_template_info_list]
#         update_result, message = db.update_deployment_template_delete(deployment_template_ids=deployment_template_ids)
#         if not update_result:
#             raise DeploymentTemplateDBUpdateError

#         # history 기록
#         user_info=db.get_user(headers_user)
#         # 에초에 이름이 없는 템플릿은 is_deleted=1 이기 때문에 프론트 통해 삭제 불가능
#         deployment_template_name_list = [info["name"] for info in deployment_template_info_list if info["name"]!=None]
#         # if len(deployment_template_name_list)>0:
#         #     db.logging_history(
#         #         user=user_info['name'], task='deployment_template',
#         #         action='delete', workspace_id=template_info["workspace_id"],
#         #         task_name=','.join()
#         #     )

#         # 템플릿 삭제 시 is_deleted=1 인 템플릿 item에 대해서 참조하는 배포/워커 없으면 delete
#         delete_not_used_deployment_template()
#         return response(status=1, message="Deployment Template Delete Success")
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Template Delete Fail")

# def delete_not_used_deployment_template():
#     """
#     템플릿 삭제 시 is_deleted=1 인 템플릿 item에 대해서 참조하는 배포/워커 없으면 delete
#     """
#     # is_deleted=1 이고 참조하는 배포/워커가 없는 template id 받아오기
#     delete_list=db.get_deployment_template_delete_list()
#     if len(delete_list)>0:
#         delete_id_list = [str(info["id"]) for info in delete_list]
#         # deployment_template db 에서 해당 id 들 삭제
#         delete_result, message = db.delete_deployment_templates(deployment_template_id_list=delete_id_list)
#         if not delete_result:
#             print(message)
#             raise DeploymentTemplateDBDeleteError
#         print("deleted template ids: ", delete_id_list)



# def get_deployment_template_group_list(workspace_id, headers_user):
#     try:
#         deployment_template_group_info_list = db.get_deployment_template_group_list(workspace_id=workspace_id)
#         deployment_template_group_info_result = []
#         deployment_template_group_name_list = []
#         for info in deployment_template_group_info_list:
#             deployment_template_group_name_list.append(info["deployment_template_group_name"])
#             deployment_template_group_info_result.append({
#                 "id": info["id"],
#                 "name": info["deployment_template_group_name"],
#                 "description": info["deployment_template_group_description"],
#                 "user_id": info["user_id"],
#                 "user_name": info["user_name"],
#                 "create_datetime": info["create_datetime"],
#                 "permission_level": check_deployment_template_access_level(user_id=headers_user, deployment_template_group_id=info["id"])
#             })
#         deployment_template_group_new_name = svc_deployment.get_new_name(name_list=deployment_template_group_name_list,
#                                                     name_str=DEPLOYMENT_TEMPLATE_GROUP_DEFAULT_NAME)
#         result = {
#             "deployment_template_group_info_list":deployment_template_group_info_result,
#             "deployment_template_group_new_name":deployment_template_group_new_name
#         }
#         return response(status=1, result=result, message="OK")
#     except:
#         traceback.print_exc()
#         return response(status=0, message="Deployment Template Group Get Fail")  

# def create_deployment_template_group(workspace_id, deployment_template_group_name, 
#                                     deployment_template_group_description, headers_user):
#     try:
#         deployment_template_group_id = insert_deployment_template_group(workspace_id=workspace_id, 
#                             deployment_template_group_name=deployment_template_group_name, 
#                             deployment_template_group_description=deployment_template_group_description, 
#                             user_id=headers_user)
#         return response(status=1, message="Create Deployment Template Group Success")  
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         raise ce
#     except Exception as e:
#         raise e

# def update_deployment_template_group(workspace_id, deployment_template_group_id, 
#                                     deployment_template_group_name, deployment_template_group_description, headers_user):
#     try:
#         check_result = check_inaccessible_deployment_template(user_id=headers_user, 
#                                             deployment_template_group_id=deployment_template_group_id, allow_max_level=3)
#         # 이름 중복 체크
#         deployment_template_group_info = db.get_deployment_template_group_by_unique_key(
#                                                                 deployment_template_group_name=deployment_template_group_name, 
#                                                                 workspace_id=workspace_id,
#                                                                 deployment_template_group_id=deployment_template_group_id)
#         if deployment_template_group_info != None:
#             raise DeploymentTemplateGroupNameExistError
#         # DB 업데이트
#         update_deployment_template_group_result = db.update_deployment_template_group(
#                                                     deployment_template_group_id=deployment_template_group_id,
#                                                     deployment_template_group_name=deployment_template_group_name,
#                                                     deployment_template_group_description=deployment_template_group_description)
#         if not update_deployment_template_group_result['result']:
#             raise DeploymentTemplateGroupDBUpdateError
#         return response(status=1, message="Update Deployment Template Group Success")  
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         raise ce
#     except Exception as e:
#         raise e

# def delete_deployment_template_group(deployment_template_group_ids, headers_user):
#     try:
#         deployment_template_group_id_list = [int(i) for i in deployment_template_group_ids]
#         for deployment_template_group_id in deployment_template_group_id_list:
#             check_result = check_inaccessible_deployment_template(user_id=headers_user, 
#                                             deployment_template_group_id=deployment_template_group_id, allow_max_level=3)
#         # template group 에 속한 template_id 값들 받아와서 deployment_template 의 is_deleted=1 로 변경
#         update_deployment_template_result = db.update_deployment_template_delete_by_template_group_ids(
#                                                             deployment_template_group_ids=deployment_template_group_ids)
#         if update_deployment_template_result == False:
#             raise DeploymentTemplateDBUpdateError

#         delete_deployment_template_group_result, message = db.delete_deployment_template_groups(
#                                                             deployment_template_group_ids=deployment_template_group_ids)
#         if delete_deployment_template_group_result == False:
#             raise DeploymentTemplateGroupDBDeleteError

#         # 템플릿에서 is_deleted=1 인 템플릿 item에 대해서 참조하는 배포/워커 없으면 delete
#         delete_not_used_deployment_template()
#         return response(status=1, message="Delete Deployment Template Group Success")  
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         raise ce
#     except Exception as e:
#         raise e 

# def insert_deployment_template_group(workspace_id, deployment_template_group_name, deployment_template_group_description, user_id):
#     deployment_template_group_info = db.get_deployment_template_group_by_unique_key(deployment_template_group_name=deployment_template_group_name, 
#                                                                     workspace_id=workspace_id)
#     if deployment_template_group_info != None:
#         raise DeploymentTemplateGroupNameExistError
#     insert_deployment_template_group_result = db.insert_deployment_template_group(workspace_id=workspace_id,
#                                             deployment_template_group_name=deployment_template_group_name, 
#                                             deployment_template_group_description=deployment_template_group_description,
#                                             user_id=user_id)
#     if not insert_deployment_template_group_result['result']:
#         raise DeploymentTemplateGroupDBInsertError
#     deployment_template_group_id = insert_deployment_template_group_result['id']
#     return deployment_template_group_id

# def check_and_insert_deployment_template_group(deployment_template_group_id, deployment_template_group_name, 
#                                                 deployment_template_group_description, workspace_id, user_id):
#     # template group name + workspace id 통해 존재하는지 체크
#     if deployment_template_group_id == None:
#         # template group id 없는 경우
#         # template group name 이 있으면 (그룹 새로 생성하는 경우) 그룹 생성
#         if deployment_template_group_name != None:
#             deployment_template_group_id = insert_deployment_template_group(
#                             workspace_id=workspace_id, 
#                             deployment_template_group_name=deployment_template_group_name, 
#                             deployment_template_group_description=deployment_template_group_description, 
#                             user_id=user_id)
#     else:
#         # template group id 가 있는 경우 그룹 존재 하는지 체크
#         deployment_template_group_info = db.get_deployment_template_group(deployment_template_group_id=deployment_template_group_id)
#         if deployment_template_group_info == None:
#             raise DeploymentTemplateGroupNotExistError
#     return deployment_template_group_id

# def insert_template_group_and_template(workspace_id, deployment_template_group_id, 
#                                     deployment_template_name, deployment_template_description,
#                                     deployment_template_group_name, deployment_template_group_description, 
#                                     deployment_template, owner_id):
#     """deployment template group, deployment template 이름 중복 체크 후 DB insert

#     Args:
#         workspace_id (int): 워크스페이스 id
#         deployment_template_group_id (int): deployment_template_group id
#         deployment_template_name (str): deployment_template 이름
#         deployment_template_description (str): deployment_template 설명
#         deployment_template_group_name (str): deployment_template_group 이름
#         deployment_template_group_description (str): deployment_template_group 설명
#         deployment_template (dict): 배포 템플릿
#         owner_id (id): 생성자 id

#     Raises:
#         DeploymentTemplateGroupDBInsertError: _description_
#         DeploymentTemplateGroupNameExistError: _description_
#         DeploymentTemplateNameExistError: _description_
#         DeploymentTemplateDBInsertError: _description_

#     Returns:
#         int: INSERT 한 deployment_template 의 id
#     """
#     # template group id 값 존재하는지 확인
#     # template group id 없는 경우 (새로 생성) 이름 체크
#     # template group db insert
#     deployment_template_group_id = check_and_insert_deployment_template_group(
#                                                 deployment_template_group_id=deployment_template_group_id, 
#                                                 deployment_template_group_name=deployment_template_group_name, 
#                                                 deployment_template_group_description=deployment_template_group_description,
#                                                 workspace_id=workspace_id, user_id=owner_id)

#     # workspace id + template group id + template 이름으로 is_deleted 값 0 인 항목들 중 template_name 중복 체크
#     # 그룹 없는경우 중복체크 불필요
#     if deployment_template_group_id != None:
#         if deployment_template_name != None:
#             deployment_template_info = db.get_deployment_template_by_unique_key(deployment_template_name=deployment_template_name, 
#                                                                     deployment_template_group_id=deployment_template_group_id, 
#                                                                     workspace_id=workspace_id)
#             if deployment_template_info != None: 
#                 duplicated_template_info = db.get_deployment_template(deployment_template_id = deployment_template_info['id'])
#                 if duplicated_template_info['template'] == deployment_template:
#                     return duplicated_template_info['id']
#                 else:
#                     raise DeploymentTemplateNameExistError

#     # template 정보 DB INSERT
#     is_deleted = 0
#     if deployment_template_name==None:
#         is_deleted = 1
#     insert_deployment_template_result = db.insert_deployment_template(workspace_id=workspace_id, 
#                             deployment_template_name=deployment_template_name, 
#                             deployment_template_group_id=deployment_template_group_id, 
#                             deployment_template_description=deployment_template_description, 
#                             deployment_template=deployment_template, 
#                             user_id=owner_id, is_deleted=is_deleted)
#     if not insert_deployment_template_result['result']:
#         raise DeploymentTemplateDBInsertError
#     return insert_deployment_template_result['id']



# def get_create_deployment_template_type_with_version(deployment_type, training_id, checkpoint_id):
#     """
#     Description : Returns the type of deployment template in create/update.

#     Args:
#         deployment_type (str): built-in / custom
#         training_id (int): training id
#         checkpoint_id (int): checkpoint id

#     Returns:
#         str: template type in ["custom v1", "usertrained v1", "pretrained v1", "checkpoint v1"]
#     """
#     if deployment_type == DEPLOYMENT_TYPE_B:
#         deployment_template_type_with_version = DEPLOYMENT_RUN_CUSTOM_V1
#     elif deployment_type == DEPLOYMENT_TYPE_A and training_id != None and checkpoint_id == None:
#         deployment_template_type_with_version = DEPLOYMENT_RUN_USERTRAINED_V1
#     elif deployment_type == DEPLOYMENT_TYPE_A and training_id == None and checkpoint_id == None:
#         deployment_template_type_with_version = DEPLOYMENT_RUN_PRETRAINED_V1
#     elif deployment_type == DEPLOYMENT_TYPE_A and training_id == None and checkpoint_id != None:
#         deployment_template_type_with_version = DEPLOYMENT_RUN_CHEKCPOINT_V1
#     else:
#         return None
#     return deployment_template_type_with_version

# def get_deployment_and_worker_by_template(deployment_template_id):
#     try:
#         deployment_list = db.get_deployment_by_template(deployment_template_id=deployment_template_id)
#         deployment_worker_list = db.get_deployment_worker_by_template(deployment_template_id=deployment_template_id)
#         result={
#             "deployment_list":deployment_list,
#             "deployment_worker_list":deployment_worker_list
#         }
#         return response(status=1, result=result, message="OK")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# def check_duplicate_deployment_template_info(deployment_template, workspace_id):
#     deployment_template_info_list = db.get_deployment_template_exist(deployment_template=deployment_template, 
#                                             workspace_id=workspace_id, is_deleted=1)
#     # print("deployment_template_info_list:",deployment_template_info_list)
#     if deployment_template_info_list != None:
#         if len(deployment_template_info_list)!=0:
#             return deployment_template_info_list[0]["id"]
#     return None

# def check_deployment_template_id_info(deployment_template_id, deployment_template):
#     """배포 템플릿 id 정보와 입력받은 template 내용이 같은지 확인

#     Args:
#         deployment_template_id (int): template id
#         deployment_template (dict): template

#     Returns:
#         bool: 같을경우 True, 다를경우 False
#     """
#     deployment_template_current_info = db.get_deployment_template(deployment_template_id=deployment_template_id)
#     deployment_template_current = deployment_template_current_info["template"]
#     if deployment_template_current != deployment_template:
#         return False
#     return True

# def check_update_deployment_template_param_info(template_params, workspace_id):
#     training_id = template_params.get(DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY)
#     job_id = template_params.get(DEPLOYMENT_TEMPLATE_JOB_ID_KEY)
#     hps_id = template_params.get(DEPLOYMENT_TEMPLATE_HPS_ID_KEY)
#     # sandbox info
#     deployment_template_mount_info = template_params.get(DEPLOYMENT_TEMPLATE_MOUNT_KEY)
#     deployment_template_environment_info = template_params.get(DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY)
    
#     # 학습 정보
#     if training_id != None:
#         training_info = db.get_training(training_id=training_id) 
#         if training_info == None:
#             raise DeploymentSelectTrainingNotExistError
#         template_params[DEPLOYMENT_TEMPLATE_TRAINING_NAME_KEY] = training_info["training_name"]
#         if training_info["built_in_model_id"] != None:
#             template_params[DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY] = training_info["built_in_model_id"]

#     # 빌트인 정보
#     if template_params.get(DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY) != None:
#         built_in_model_info = db.get_built_in_model(model_id=template_params[DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY])
#         if built_in_model_info == None:
#             raise DeploymentSelectBuiltInModelNotExistError
#         template_params[DEPLOYMENT_TEMPLATE_BUILT_IN_NAME_KEY] = built_in_model_info["name"]

#     # JOB 정보
#     if job_id != None:
#         job_info = db.get_job(job_id=job_id)
#         if job_info == None:
#             raise DeploymentSelectJobNotExistError
#         template_params[DEPLOYMENT_TEMPLATE_JOB_NAME_KEY] = job_info["name"]
#         template_params[DEPLOYMENT_TEMPLATE_JOB_GROUP_INDEX_KEY] = job_info["job_group_index"]
    
#     # HPS 정보
#     if hps_id != None:
#         hps_info = db.get_hyperparamsearch(hps_id=hps_id)
#         if hps_info == None:
#             raise DeploymentSelectJobNotExistError
#         template_params[DEPLOYMENT_TEMPLATE_HPS_NAME_KEY] = hps_info["hps_group_name"]
#         template_params[DEPLOYMENT_TEMPLATE_HPS_GROUP_INDEX_KEY] = hps_info["hps_group_index"]
    
#     # mount 정보
#     if deployment_template_mount_info != None:
#         custom_params = {
#             "training_name_list": [],
#             "dataset_name_list": []
#         }
#         for mount_field in ["training", "dataset"]:
#             if deployment_template_mount_info.get(mount_field)!= None and type(deployment_template_mount_info.get(mount_field))==list:
#                 delete_index_list = []
#                 for idx in range(len(deployment_template_mount_info[mount_field])):
#                     if deployment_template_mount_info[mount_field][idx].get("name") == None:
#                         delete_index_list.append(idx)
#                     else:
#                         custom_params[mount_field+"_name_list"].append(deployment_template_mount_info[mount_field][idx].get("name") )
#                 delete_index_list.reverse()
#                 for idx in delete_index_list:
#                     del deployment_template_mount_info[mount_field][idx]
#                 if len(deployment_template_mount_info[mount_field])==0:
#                     del deployment_template_mount_info[mount_field]
#         if custom_params["training_name_list"] != []:
#             for training_name in custom_params["training_name_list"]:
#                 training_info = db.get_training(training_name=training_name, workspace_id=workspace_id)
#                 if training_info == None:
#                     raise DeploymentSelectTrainingNotExistError
            
#         if custom_params["dataset_name_list"] != []:
#             for dataset_name in custom_params["dataset_name_list"]:
#                 dataset_info = db.get_dataset(dataset_name=dataset_name, workspace_id=workspace_id)
#                 if dataset_info == None:
#                     raise DeploymentSelectDatasetNotExistError
            
#     if deployment_template_environment_info != None and type(deployment_template_environment_info)==list:
#         delete_index_list = []
#         for idx in range(len(deployment_template_environment_info)):
#             if type(deployment_template_environment_info[idx]) != dict:
#                 delete_index_list.append(idx)
#                 continue
#             if deployment_template_environment_info[idx].get("name")==None or deployment_template_environment_info[idx].get("value")==None:
#                 delete_index_list.append(idx)
#                 continue
#             if deployment_template_environment_info[idx].get("name")=="":
#                 delete_index_list.append(idx)
#                 continue
#         delete_index_list.reverse()
#         for idx in delete_index_list:
#             del deployment_template_environment_info[idx]
            
# def check_update_deployment_template_info(deployment_template):
#     # check command info: 필수 command (binary / code) 가 없는 경우 command field 삭제
#     # deployment_template_run_info = deployment_template.get(DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY)
#     # if deployment_template_run_info != None:
#     #     is_valid_command = False
#     #     if deployment_template_run_info.get(DEPLOYMENT_TEMPLATE_RUN_BINARY_KEY) !=None:
#     #         is_valid_command = True
#     #     if deployment_template_run_info.get(DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY) !=None:
#     #         is_valid_command = True
#     #     if is_valid_command == False:
#     #         del deployment_template[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY]

#     # check mount info: dataset, training mount 의 경우 필수 항목 (name) 이 없는 경우 field 삭제
#     deployment_template_mount_info = deployment_template.get(DEPLOYMENT_TEMPLATE_MOUNT_KEY)
#     if deployment_template_mount_info != None:
#         for mount_field in ["training", "dataset"]:
#             if deployment_template_mount_info.get(mount_field)!= None and type(deployment_template_mount_info.get(mount_field))==list:
#                 idx_list = []
#                 for idx in range(len(deployment_template_mount_info[mount_field])):
#                     if deployment_template_mount_info[mount_field][idx].get("name") == None:
#                         idx_list.append(idx)
#                 idx_list.reverse()
#                 for idx in idx_list:
#                     del deployment_template_mount_info[mount_field][idx]
#                 if len(deployment_template_mount_info[mount_field])==0:
#                     del deployment_template_mount_info[mount_field]


# def convert_deployment_db_to_template(deployment_id=None, deployment_worker_id=None):
#     """배포, 워커 id 통해 template 생성 DB INSERT 및 배포, 워커의 template_id UPDATE

#     Args:
#         deployment_id (int, optional): deployment id. Defaults to None.
#         deployment_worker_id (int, optional): deployment worker id. Defaults to None.

#     Raises:
#         ValueError: 배포 id 가 db에 없음
#         ValueError: 배포 워커 id 가 db에 없음
#         RuntimeError: 배포id 또는 워커 id 를 입력받아야함
#         RuntimeError: 템플릿에 type 정보 없음
#         RuntimeError: 템플릿 DB INSERT 에러
#         RuntimeError: 배포/워커 DB template_id UPDATE 에러

#     Returns:
#         int: template_id 
#     """    
#     try:
#         if deployment_id:
#             info = db.get_deployment(deployment_id=deployment_id)
#             if info==None:
#                 raise ValueError("No matching deployment_id in DB")
#             # deployment_name=info["name"]
#         elif deployment_worker_id:
#             info = db.get_deployment_worker(deployment_worker_id=deployment_worker_id)
#             if info==None:
#                 raise ValueError("No matching deployment_worker_id in DB")
#             # deployment_name=info["deployment_name"]
#             deployment_id = db.get_deployment_id_from_worker_id(deployment_worker_id=deployment_worker_id)
        
#         if deployment_id==None:
#             raise RuntimeError("deployment_id or deployment_worker_id needed")

#         workspace_id = info["workspace_id"]
#         if info.get("type") == None:
#             raise RuntimeError("Field 'type' should be 'built-in' / 'custom'")
        
#         deployment_template_type_with_version = get_create_deployment_template_type_with_version(deployment_type=info["type"], training_id=info["training_id"], 
#                                                             checkpoint_id=info["checkpoint_id"])
        
#         # template_type 통해 기본 template 포맷 받아오기
#         template = DEPLOYMENT_JSON_TEMPLATE[deployment_template_type_with_version]
#         # 배포 정보에 template key 있는경우 기본 포맷에 value 추가
#         for template_key in template:
#             if template_key in info:
#                 template[template_key] = info[template_key]

#         # template_type = usertrained_v1 의 경우 checkpoint 경로 업데이트
#         if deployment_template_type_with_version==DEPLOYMENT_RUN_USERTRAINED_V1:
#             template[DEPLOYMENT_TEMPLATE_TRAINING_TYPE_KEY]="job"
#             check_update_deployment_template_param_info(template_params=template, workspace_id=workspace_id)
#             svc_deployment.update_deployment_template_checkpoint_path(deployment_template=template, checkpoint_file_path=info["checkpoint"])
#         elif deployment_template_type_with_version==DEPLOYMENT_RUN_CUSTOM_V1:
#             template[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY][DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY]=info["run_code"]

#         template_info_list = db.get_deployment_template_exist(deployment_template=template, workspace_id=workspace_id, is_deleted=1)
#         if template_info_list != None:
#             len_template_info = len(template_info_list)
#         else:
#             len_template_info = 0
#         if len_template_info>0:
#             template = template_info_list[0]
#             template_id = template["id"]
#         else:
#             template_id = insert_template_group_and_template(workspace_id=workspace_id, 
#                                         deployment_template_group_id=None,
#                                         deployment_template_group_name=None,
#                                         deployment_template_group_description="", 
#                                         deployment_template_name=None,
#                                         deployment_template_description="", 
#                                         deployment_template=template, 
#                                         owner_id=info['user_id'])
#         if deployment_worker_id:
#             update_result, message = db.update_deployment_worker_template_id(deployment_worker_id=deployment_worker_id, 
#                                                                             deployment_template_id=template_id)
#         else:
#             update_result, message = db.update_deployment_template_id(deployment_id=deployment_id, deployment_template_id=template_id)
#         if update_result==False:
#             raise RuntimeError("DB template id update error {}".format(message))
#         return template_id
#     except Exception as e:
#         raise e


# def to_template():
#     """배포, 워커 전체 template 생성 DB INSERT 및 배포, 워커의 template_id UPDATE
#     """
#     error_list = []
#     done_list = []
#     deployment_list = db.get_deployment_list()
#     # template_id 없는 경우만 배포 id 값 담기
#     deployment_id_list = [info["id"] for info in deployment_list if info.get("template_id")==None]
#     for deployment_id in deployment_id_list:
#         try:
#             convert_deployment_db_to_template(deployment_id=deployment_id)
#             done_list.append(deployment_id)
#         except Exception as e:
#             e = str(e)
#             # 에러난 경우 error_list 에 담아서 loop 끝난 후 print
#             if len(e)>50:
#                 e = e[:50]
#             error_list.append({
#                 "id":deployment_id,
#                 "error":e
#             })
#     deployment_worker_list=db.get_deployment_worker_list()
#     # template_id 없는 경우만 배포 워커 id 값 담기
#     deployment_worker_id_list = [info["id"] for info in deployment_worker_list if info.get("template_id")==None]
#     worker_error_list=[]
#     worker_done_list=[]
#     for worker_id in deployment_worker_id_list:
#         try:
#             convert_deployment_db_to_template(deployment_worker_id = worker_id)
#             worker_done_list.append(worker_id)
#         except Exception as e:
#             e = str(e)
#             # 에러난 경우 error_list 에 담아서 loop 끝난 후 print
#             if len(e)>50:
#                 e = e[:50]
#             worker_error_list.append({
#                 "id":worker_id,
#                 "error":e
#             })
#     if len(error_list)>0:
#         print("Deployment Convert Error")
#         print(error_list)
#         print("================")
#     if len(worker_error_list)>0:
#         print("Deployment Worker Convert Error")
#         print(worker_error_list)
#         print("================")
#     print("convert success deployment:",done_list)
#     print("convert success worker:",worker_done_list)
#     print("================")
#     print("convert fail deployment:",[info['id'] for info in error_list])
#     print("convert fail worker:",[info['id'] for info in worker_error_list])
#     print("================")
#     print("done")


# # 임시, 삭제 예정
# def change_template_form(deployment_template_id):
#     template_info = db.get_deployment_template(deployment_template_id=deployment_template_id)
#     template = template_info["template"]
#     deployment_template_type = template.get("template_type")
#     if deployment_template_type==None:
#         return {
#             "status":True,
#             "message":"Not OLD Form"
#         }
#     template_base = DEPLOYMENT_JSON_TEMPLATE[deployment_template_type]
#     for key in template_base:
#         if template.get(key) !=None:
#             template_base[key] = template[key]
#     if template_base[DEPLOYMENT_TEMPLATE_KIND_INFO_KEY][DEPLOYMENT_TEMPLATE_TYPE_KEY]==DEPLOYMENT_RUN_CUSTOM:
#         template_base[DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY][DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY]=template["run_code"]
#     print("template:", template_base)
#     result, message = db.update_deployment_template_back(deployment_template_id=deployment_template_id, deployment_template=template_base)
#     if result==False:
#         return {
#             "status":False,
#             "message":message
#         }
#     return {
#             "status":True
#         }

# # 임시, 삭제 예정
# def update_all_old_template():
#     template_infos = db.get_deployment_template_list(workspace_id=4)
#     failures=[]
#     successes=[]
#     for info in template_infos:
#         deployment_template_id = info["id"]
#         try:
#             result = change_template_form(deployment_template_id)
#             if result["status"]==False:
#                 failures.append(deployment_template_id)
#             else:
#                 successes.append(deployment_template_id)
#         except:
#             traceback.print_exc()
#             failures.append(deployment_template_id)
#     print("FAIL IDS:", failures)
#     print("SUCCESS IDS:", successes)
