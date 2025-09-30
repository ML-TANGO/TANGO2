# # from flask_restful import Resource
# import re
# import json
# import os
# import time
# import traceback

# # import utils.db as db
# from utils.resource import CustomResource, response  #, token_checker
# import utils.common as common
# import utils.kube as kube
# from utils.kube import kube_data

# from utils import settings
# from utils.ssh_sync import update_workspace_users_etc
# from utils.TYPE import *
# from utils.exceptions import *
# from utils.access_check import admin_access_check



# # import utils.storage as storage

# from utils import gpu
# # import image as imgZ
# # from storage import *
# from utils.storage_image_control import *

# JF_WS_DIR = settings.JF_WS_DIR
# JF_ETC_DIR = settings.JF_ETC_DIR
# # JUPYTER_FLAG = kube.JUPYTER_FLAG

# # ns = api.namespace('workspaces', description='워크스페이스 관련 API')

# # create_parser = reqparse.RequestParser()
# # create_parser.add_argument('workspace_name', type=str, required=True, location='json', help="워크스페이스명")
# # create_parser.add_argument('manager_id', type=int, required=True, location='json', help="매니저 아이디")
# # create_parser.add_argument('training_gpu', type=int, required=True, location='json', help="training gpu 수")
# # create_parser.add_argument('deployment_gpu', type=int, required=True, location='json', help="deployment gpu 수")
# # create_parser.add_argument('start_datetime', type=str, required=True, location='json', help="서비스 시작 시간")
# # create_parser.add_argument('end_datetime', type=str, required=True, location='json', help="서비스 만료 시간")
# # create_parser.add_argument('users_id', type=list, required=False, location='json', help="유저 목록 ex. [user_id, user_id, user_id, ...]")
# # create_parser.add_argument('guaranteed_gpu', type=int, required=False, location='json', default=1, help="Workspace 내에서 GPU 자원 보장 여부 0 | 1 (False, True) ")
# # create_parser.add_argument('description', type=str, required=False, default='', location='json', help="Workspace Description len 200")
# # create_parser.add_argument('storage_id', type=int, required=True, location='json', help="워크스페이스가 생성될 Storage ID")
# # create_parser.add_argument('workspace_size', type=str, required=False, location='json', help="워크스페이스 사이즈(할당형일 경우만)")

# # update_parser = reqparse.RequestParser()
# # update_parser.add_argument('workspace_id', type=int, required=True, location='json', help="워크스페이스ID")
# # update_parser.add_argument('workspace_name', type=str, required=True, location='json', help="워크스페이스명")
# # update_parser.add_argument('training_gpu', type=int, required=True, location='json', help="training gpu 수")
# # update_parser.add_argument('deployment_gpu', type=int, required=True, location='json', help="deployment gpu 수")
# # update_parser.add_argument('start_datetime', type=str, required=True, location='json', help="서비스 시작 시간")
# # update_parser.add_argument('end_datetime', type=str, required=True, location='json', help="서비스 만료 시간")
# # update_parser.add_argument('manager_id', type=str, required=True, location='json', help="매니저 아이디")
# # update_parser.add_argument('users_id', type=list, required=True, location='json', help="유저 목록 ex. [user_id, user_id, user_id, ...]")
# # update_parser.add_argument('guaranteed_gpu', type=int, required=False, location='json', default=None, help="Workspace 내에서 GPU 자원 보장 여부 0 | 1 (False, True) ")
# # update_parser.add_argument('description', type=str, required=False, default='', location='json', help="Workspace Description len 200")
# # update_parser.add_argument('workspace_size', type=str, required=False, location='json', help="워크스페이스 사이즈(할당형일 경우만)")


# # delete_parser = reqparse.RequestParser()
# # delete_parser.add_argument('workspaces_id', type=list, required=True, location='json', help="워크스페이스ID ex.[workspace_id, workspace_id]")

# # page_parser = reqparse.RequestParser()
# # page_parser.add_argument('page', type=int, required=False, location='args', help="페이지 번호")
# # page_parser.add_argument('size', type=int, required=False, location='args', help="한 페이지당 개수")
# # page_parser.add_argument('search_key', type=str, required=False, location='args', help="검색 타입")
# # page_parser.add_argument('search_value', type=str, required=False, location='args', help="검색 값")

# # favorites_parser = reqparse.RequestParser()
# # favorites_parser.add_argument('workspace_id', type=int, required=True, location='json', help="대상 워크스페이스명")
# # favorites_parser.add_argument('action', type=int, required=True, location='json', help="삭제(0), 추가(1)")

# # description_update_parser = reqparse.RequestParser()
# # description_update_parser.add_argument('description', type=str, required=True, location='json', help="수정 한 Description")

# # get_ws_quota_parser = reqparse.RequestParser()
# # get_ws_quota_parser.add_argument('workspace_name', type=str, required=True, help="Workspace 이름")

# # set_ws_quota_parser = reqparse.RequestParser()
# # set_ws_quota_parser.add_argument('workspace_name', type=str, required=True, help="Workspace 이름")
# # set_ws_quota_parser.add_argument('size', type=str, required=True, help="크기")
# # set_ws_quota_parser.add_argument('unit', type=str, required=True, help="단위")

# # gpu_update_parser = reqparse.RequestParser()
# # gpu_update_parser.add_argument('training_gpu', type=int, required=True, location='json', help="수정 한 Training gpu 개수")
# # gpu_update_parser.add_argument('deployment_gpu', type=int, required=True, location='json', help="수정 한 Deplyoment gpu 개수")

# def is_workspace_good_name(workspace_name):
#     is_good = common.is_good_name(name=workspace_name)
#     if is_good == False:
#         raise WorkspaceNameInvalidError
#     return True

# def delete_workspace_folder(workspace_name):

#     is_workspace_good_name(workspace_name=workspace_name)

#     workspace_dir_path = JF_WORKSPACE_PATH.format(workspace_name=workspace_name)
#     common.rm_rf(workspace_dir_path)

# def get_workspace_active_item_list(workspace_id):
#     """
#         Description : Workspace 에서 사용중이거나 사용 예정인 아이템 목록 조회

#         Args :
#             workspace_id (int) : 확인할 Workspace id

#         Return :
#             (list) :
#     """
#     pod_list = kube.kube_data.get_pod_list()

#     # 실제 Active 중인 Item 목록 정보
#     workspace_pod_list = kube.find_kuber_item_name_and_item(item_list=pod_list, workspace_id=workspace_id)

#     # Queue에 대기중인 아이템 정보

#     workspace_queue_list = []

#     all_queue_list = db.get_all_queue_item_with_info()
#     for queue_info in all_queue_list:
#         if int(queue_info.get("workspace_id")) == int(workspace_id):
#             workspace_queue_list.append(queue_info)

#     return workspace_pod_list, workspace_queue_list

# def get_workspace_info(workspace_id):
#     #TODO running status를 workspace_id 기반으로 찾도록 변경필요
#     #지금 구조에서도 다 찾을 수 있지만, 아이템이 추가 될 때 마다 같이 수정이 되어야 함
#     try:
#         workspace = db.get_workspace(workspace_id=workspace_id)
#         if workspace is None:
#             return None

#         training_list = db.get_training_list(workspace_id=workspace_id)
#         deployment_list = db.get_deployment_list(workspace_id=workspace_id)

#         pod_list = kube_data.get_pod_list(try_update=False)

#         training_used_gpu = 0
#         deployment_used_gpu = 0

#         # TODO REMOVE - 상태 체크를 이렇게 하지 않고 workspace id 기반으로 변경 (2022-11-02)
#         # if training_list is not None:
#         #     for training in training_list:
#         #         workspace_name = workspace['workspace_name']
#         #         training_name = training['training_name']
#         #         status = kube.get_training_status(training_id=training["id"], pod_list=pod_list)
#         #         editor_status = kube.get_training_tool_pod_status(training_tool_id=training["tool_editor_id"], pod_list=pod_list)
#         #         training['status'] = status['status']
#         #         training['editor_status'] = editor_status['status']
#         # else :
#         #     training_list = []

#         # if deployment_list is not None:
#         #     for deployment in deployment_list:
#         #         deployment_status = kube.get_deployment_status(deployment_id=deployment["id"], pod_list=pod_list)
#         #         deployment["status"] = deployment_status["status"]
#         # else :
#         #     deployment_list = []

#         # workspace['training'] = training_list
#         # workspace['deployment'] = deployment_list


#         workspace_pod_list, workspace_queue_list = get_workspace_active_item_list(workspace_id=workspace_id)

#         workspace["running_status"] = len(workspace_pod_list) + len(workspace_queue_list) > 0
#         workspace['user'] = db.get_workspace_users(workspace_id=workspace_id)
#         workspace['usage'] = db.get_storage_image_control(workspace_id=workspace_id)
#         return workspace
#     except:
#         traceback.print_exc()
#         return None

# import time
# def get_workspace_list(page, size, search_key, search_value, user_id, user_name):
#     result = []
#     try:
#         st = time.time()
#         workspaces = db.get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value, user_id=user_id)
#         # print("get workspace " , time.time() - st)
#         if workspaces is not None:
#             st = time.time()
#             try:
#                 pod_list = kube_data.get_pod_list()
#             except:
#                 traceback.print_exc()
#                 pod_list = None
#             try:
#                 workspace_gpu_used_info = kube.get_workspace_gpu_count(pod_list=pod_list, workspace_list=workspaces)
#                 # print("kube ", time.time() - st)
#             except:
#                 traceback.print_exc()
#                 gpu_used = {}

#             all_workspace_users_list = db.get_workspace_users()
#             all_workspace_users_dict = common.gen_dict_from_list_by_key(target_list=all_workspace_users_list, id_key="workspace_id")


#             all_workspace_count_info_list = db.get_workspace_count_info_list()
#             all_workspace_count_info_dict = common.gen_dict_from_list_by_key(target_list=all_workspace_count_info_list, id_key="workspace_id")

#             st = time.time()
#             for workspace in workspaces:
#                 status = common.get_workspace_status(workspace)
#                 workspace_data = {"id": workspace["id"],
#                                   "name": workspace["workspace_name"],
#                                   "create_datetime": workspace["create_datetime"],
#                                   "start_datetime": workspace["start_datetime"],
#                                   "end_datetime": workspace["end_datetime"],
#                                   "status": status,
#                                   "description": workspace["description"],
#                                   "guaranteed_gpu": workspace["guaranteed_gpu"],
#                                   "gpu": {
#                                       "deployment": {
#                                           "total": workspace["gpu_deployment_total"],
#                                           "used": workspace_gpu_used_info.get(workspace["id"])["deployment_used"]
#                                       },
#                                       "training": {
#                                           "total": workspace["gpu_training_total"],
#                                           "used": workspace_gpu_used_info.get(workspace["id"])["training_used"]
#                                       },
#                                       "total":{
#                                           "total": workspace["gpu_training_total"]+workspace["gpu_deployment_total"],
#                                           "used": workspace_gpu_used_info.get(workspace["id"])["deployment_used"] + workspace_gpu_used_info.get(workspace["id"])["training_used"]
#                                       }
#                                   },
#                                   "user": {}, "training": {}, "percent": 0, "manager": workspace["manager_name"]
#                                   }

#                 users = all_workspace_users_dict.get(workspace["id"])
#                 for u in users:
#                     if u['user_name'] == user_name:
#                         workspace_data['favorites'] = u['favorites']
#                 user_data = {"total": len(users), "list": [{"name":user['user_name'], "id":user['id']} for user in users]}
#                 workspace_data['user'] = user_data

#                 count_info = all_workspace_count_info_dict.get(workspace["id"])
#                 if count_info is not None:
#                     count_info = count_info[0]
#                 else :
#                     continue
#                 workspace_data["images"] = count_info.get("image_count")
#                 workspace_data["datasets"] = count_info.get("dataset_count")
#                 workspace_data["deployments"] = count_info.get("deployment_count")
#                 workspace_data["trainings"] = count_info.get("training_count")
#                 workspace_data["usage"] = db.get_storage_image_control(workspace_id=workspace["id"])

#                 # image_list = db.get_image_workspace_id(workspace["id"])
#                 # if image_list is not None:
#                 #     workspace_data['images'] = len(image_list)
#                 # else:
#                 #     workspace_data['images'] = 0

#                 # dataset_list = db.get_dataset_list(workspace_id = workspace["id"])
#                 # if dataset_list is not None:
#                 #     workspace_data['datasets'] = len(dataset_list)
#                 # else:
#                 #     workspace_data['datasets'] = 0

#                 # deployment_list = db.get_deployment_list(workspace_id = workspace["id"])
#                 # if deployment_list is not None:
#                 #     workspace_data['deployments'] = len(deployment_list)
#                 # else:
#                 #     workspace_data['deployments'] = 0

#                 # training_data = {"running": 0, "pending": 0, "stop": 0, "expired": 0, "reserved": 0}
#                 # trainings = db.get_training_list(workspace_id=workspace['id'])
#                 # for training in trainings:
#                 #     workspace_name = workspace['workspace_name']
#                 #     training_name = training['training_name']
#                 #     status = kube.get_training_status(training_id=training["id"], pod_list=pod_list)
#                 #     if status["status"] not in ["pending", "stop", "expired", "reserved"]:
#                 #         status["status"] = "running"
#                 #     training_data[status['status']] += 1
#                 # training_data['total'] = training_data['running'] + training_data['pending'] + training_data['stop'] + training_data['expired']
#                 # workspace_data['training'] = training_data

#                 # users = db.get_workspace_users(workspace_id=workspace['id'])
#                 # for u in users:
#                 #     if u['user_name'] == user_name:
#                 #         workspace_data['favorites'] = u['favorites']
#                 # user_data = {"total": len(users), "list": [{"name":user['user_name'], "id":user['id']} for user in users]}
#                 # workspace_data['user'] = user_data

#                 result.append(workspace_data)
#             # print("workspace for ", time.time() - st )
#     except:
#         traceback.print_exc()
#     return result




# def get_workspace(workspace_id, user):
#     # TODO 유저권한에 따라서 처리 방법을 => json 에 저장된 users list 에 존재하는 user 에게만 정보 보여줌
#     try:
#         workspace = get_workspace_info(workspace_id)
#         users = db.get_workspace_users(workspace_id)
#         if workspace is None:
#             res = response(status=0, message="Not found workspace", result=[])
#         elif user == 'root' or (users is not None and user in users):
#             res = response(status=1, result=workspace)
#         else:
#             res = response(status=0, message="permission error", result=[])
#         return res
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get workspace Error", result=[])
#         #return response(status=0, message=e, result=[])


# def get_workspaces(headers_user, page, size, search_key, search_value):
#     try:
#         if headers_user is None:
#             return response(status=0, message="Jf-user is None in headers")
#         #TODO TEMP ROOT DISABLE
#         #if headers_user == 'root' or True:
#             # if page < 1:
#             #     res = response(status=0, message="Invalid page number")
#             # else:
#         user_info = db.get_user(user_name=headers_user)
#         if user_info is not None:
#             if user_info['user_type'] == 0:
#                 # Admin ?
#                 list_ = get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value,
#                                             user_id=None, user_name=headers_user)
#                 # count = db.get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value, user_id=None)
#                 count = len(list_)
#             else:
#                 # User ?
#                 list_ = get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value,
#                                             user_id=user_info['id'], user_name=headers_user)
#                 # count = db.get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value, user_id=user_info['id'])
#                 count = len(list_)
#             list_active = [info for info in list_ if info.get("status")=="active"]
#             list_expired = [info for info in list_ if info.get("status")!="active"]
#             # res = response(status=1, result={"list": list_, "total": count})
#             res = response(status=1, result={"list": list_active+list_expired, "total": count})
#         else:
#             res = response(status=0, message="Can not find user")
#             #pass
#         return res
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get workspaces Error")
#         #return response(status=0, message=e)

# def create_workspace_base_structure(workspace_dir, workspace_name, force=False):

#     dir_list = [
#         workspace_dir,
#         '{}/deployments'.format(workspace_dir),
#         '{}/trainings'.format(workspace_dir),
#         '{}/datasets'.format(workspace_dir),
#         '{}/datasets/0'.format(workspace_dir),
#         '{}/datasets/1'.format(workspace_dir),
#         '{}/docker_images'.format(workspace_dir),
#         '{}/test'.format(workspace_dir)
#     ]
#     if force:
#         for dir_ in dir_list:
#             try:
#                 os.makedirs(dir_, exist_ok=True)
#             except Exception as e:
#                 pass

#     else :
#         for dir_ in dir_list:
#             print(dir_)
#             os.makedirs(dir_, exist_ok=True)

#     link_dir_path = JF_WORKSPACE_PATH.format(workspace_name=workspace_name)
#     if workspace_dir != link_dir_path :
#         subprocess.run(['ln -s {} {}'.format(workspace_dir, link_dir_path)],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8')

# def create_workspace(headers_user, manager_id, workspace_name, training_gpu, deployment_gpu, start_datetime, end_datetime, users, description, guaranteed_gpu, storage_id, workspace_size):
#     try:

#         aval_gpu_info = gpu.get_workspace_aval_gpu(workspace_id=None, start_datetime=start_datetime, end_datetime=start_datetime, guaranteed_gpu=guaranteed_gpu)
#         aval_gpu_info["gpu_free"] = 50  # 삭제 예정
#         if aval_gpu_info["gpu_free"] < int(deployment_gpu) + int(training_gpu):

#             print(aval_gpu_info["gpu_free"])

#             return response(status=0, message='Workspace resource have not enough GPUs {}/{}'.format(aval_gpu_info["gpu_free"], aval_gpu_info["gpu_total"]))

#         is_workspace_good_name(workspace_name=workspace_name)

#         if db.get_workspace(workspace_name=workspace_name) is not None:
#             raise WorkspaceNameDuplicatedError

#         try:
#             workspace_dir, workspace_size_byte = make_workspace_base(workspace_name, storage_id, workspace_size)
#             create_workspace_base_structure(workspace_dir=workspace_dir, workspace_name=workspace_name)
#         except:
#             traceback.print_exc()
#             # raise Exception('Workspace {} failed to create workspace dir.'.format(workspace_name))
#             return response(status=0, message='Workspace {} failed to create workspace dir.'.format(workspace_name))

#         res = db.insert_workspace(manager_id=manager_id, workspace_name=workspace_name,
#                                     training_gpu=training_gpu, deployment_gpu=deployment_gpu,
#                                     start_datetime=start_datetime, end_datetime=end_datetime,
#                                     description=description, guaranteed_gpu=guaranteed_gpu)
#         if res:
#             workspace = db.get_workspace(workspace_name=workspace_name)
#             db.insert_storage_image_control(workspace_id=workspace['id'], size=workspace_size_byte, storage_id=storage_id)

#             # TODO 존재하지 않는 유저 에러처리 안하고 존재하는 유저만 insert 하기 위하여 아래처럼 변경함.
#             # TODO 에러처리하는 방향으로 바꿀 시 소스 변경 필요(workspace 삭제 후 에러 return). update 쪽도 같음
#             users.append(manager_id)
#             for user in users:
#                 db.insert_user_workspace(workspace_id=workspace["id"], user_id=user)

#             update_workspace_users_etc(workspace_id=workspace["id"])

#             db.logging_history(
#                 user=headers_user, task='workspace',
#                 action='create', workspace_id=workspace["id"]
#             )
#             return response(status=1, message="success")
#         else:
#             delete_workspace_folder(workspace_name=workspace_name)
#             return response(status=0, message="db insert failed")

#     except CustomErrorList as ce:
#         raise ce
#     except Exception as e:
#         # traceback.print_exc()
#         # return response(status=0, message="Create workspace Error")
#         raise e


# def update_workspace(workspace_id, workspace_name, training_gpu, deployment_gpu, start_datetime, end_datetime, users, description, guaranteed_gpu,
#                     headers_user, manager_id, workspace_size):
#     try:
#         org_workspace = db.get_workspace(workspace_id=workspace_id)

#         if org_workspace is None:
#             raise WorkspaceNotExistError

#         if org_workspace['workspace_name'] != workspace_name:
#             raise WorkspaceNameChangeNotSupportedError



#         aval_gpu_info = gpu.get_workspace_aval_gpu(workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=start_datetime, guaranteed_gpu=guaranteed_gpu)
#         aval_gpu_info["gpu_free"] = 50  # 삭제 예정
#         if aval_gpu_info["gpu_free"] < int(deployment_gpu) + int(training_gpu):
#             #sum of the all node's gpu < sum of the alloacted total gpu - now total gpu  + update total gpu
#             return response(status=0, message='The number of GPUs modified is greater than node resources.')


#         resource_update_check = True
#         #TODO 자원 수정과, 다른 정보 수정을 한번에 하도록 수정 필요
#         # db.update_workspace(workspace_id=workspace_id, training_gpu=training_gpu, deployment_gpu=deployment_gpu, start_datetime=start_datetime, end_datetime=end_datetime, manager_id=org_workspace['manager_id'])


#         get_org_user_list = db.get_workspace_users(workspace_id=workspace_id)
#         org_user_id_list = []
#         for user_info in get_org_user_list:
#             org_user_id_list.append(user_info['id'])

#         users.append(int(manager_id))
#         add_user, del_user = common.get_add_del_item_list(users, org_user_id_list)
#         training_del_user = {}



#         training_status_check = True
#         training_owner_check = True
#         owner_move_error = ""
#         training_list = db.get_training_list(workspace_id=workspace_id)
#         # user_and_running_training = [] # {user_name: , training_name: }
#         # pod_list = kube_data.get_pod_list(try_update=True)
#         pod_list = kube.get_list_namespaced_pod()
#         for training in training_list :
#             owner_info = db.get_training_owner(training_id=training["id"])
#             training_status = kube.get_training_status(training_id=training["id"])
#             tool_editor_status = kube.get_training_tool_pod_status(training_tool_id=training['tool_editor_id'], pod_list=pod_list)
#             if training_status["status"] != "stop":
#                 if owner_info["owner_id"] in del_user:
#                     #Cannot Delete Owner From running training
#                     training_status_check = False
#                     training_owner_check = False
#                     owner_move_error += "{} is {} training owner \n".format(owner_info["owner_name"], training["training_name"])
#             if tool_editor_status["status"] != "stop":
#                 if owner_info["owner_id"] in del_user:
#                     #Cannot Delete Owner From running training
#                     training_status_check = False
#                     training_owner_check = False
#                     owner_move_error += "{} is {} jupyter(CPU) owner \n".format(owner_info["owner_name"], training["training_name"])

#         if training_status_check and training_owner_check:
#             update_result, message = db.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, training_gpu=training_gpu, deployment_gpu=deployment_gpu,
#                                                             start_datetime=start_datetime, end_datetime=end_datetime, manager_id=manager_id,
#                                                             description=description, guaranteed_gpu=guaranteed_gpu)
#             if update_result:

#                 if workspace_size != '0' and workspace_size is not None  :
#                     before_workspace_size = common.convert_unit_num(value = (db.get_storage_image_control(workspace_id=workspace_id)['size']*1.016),target_unit='Gi', return_num=True)
#                     capacity = str(int(before_workspace_size)+int(workspace_size.split('G')[0]))+"G"
#                     update_workspace_image(workspace_id=workspace_id, capacity=capacity)
#                 training_list = db.get_workspace_training_list(workspace_id=org_workspace["id"])
#                 training_id_list = [training["id"] for training in training_list]
#                 # user_training 같이 제거
#                 for training_id in training_id_list:
#                     db.delete_user_training_users(training_id=training_id, users_id=del_user)

#                 db.insert_user_workspace_s(workspaces_id=[[workspace_id]]*len(add_user), users_id=add_user)
#                 db.delete_user_workspace_s(workspaces_id=[[workspace_id]]*len(del_user), users_id=del_user)
#                 # # SSH SETTING
#                 if len(add_user) > 0 or len(del_user) > 0:
#                     # updated_user_list = [ user_info["user_name"] for user_info in db.get_workspace_users(workspace_id=workspace_id)]
#                     # update_workspace_users_etc(users=updated_user_list, workspace_name=org_workspace['workspace_name'], training_list=training_list)
#                     update_workspace_users_etc(workspace_id=workspace_id)
#                 # 수정 내용 history 추가
#                 log_desc_arr = []
#                 org_w_name = org_workspace['workspace_name']
#                 org_w_desc = org_workspace['description']
#                 org_w_start_datetime = org_workspace['start_datetime']
#                 org_w_end_datetime = org_workspace['end_datetime']
#                 org_w_gpu_training_total = org_workspace['gpu_training_total']
#                 org_w_gpu_deployment_total = org_workspace['gpu_deployment_total']
#                 org_w_manager_id = org_workspace['manager_id']

#                 if org_w_desc != description: log_desc_arr.append('Descripiton') # description
#                 if org_w_start_datetime != start_datetime or org_w_end_datetime != end_datetime:
#                     log_desc_arr.append('Period') # start_datetime, end_datetime
#                 if org_w_gpu_training_total != training_gpu: log_desc_arr.append('GPUs for Training') # gpu t
#                 if org_w_gpu_deployment_total != deployment_gpu: log_desc_arr.append('GPUs for Deployment') # gpu d
#                 if str(org_w_manager_id) != manager_id: log_desc_arr.append('Manager') # manager
#                 match_count = 0
#                 for user_data in users:
#                     for org_user_data in get_org_user_list:
#                         if org_user_data['id'] == user_data:
#                             match_count += 1
#                             break

#                 if match_count != len(users): log_desc_arr.append('Users') # users
#                 db.logging_history(
#                     user=headers_user, task='workspace',
#                     action='update', workspace_id=workspace_id,
#                     update_details='/'.join(log_desc_arr)
#                 )
#                 return response(status=1, message="success")
#             else:
#                 return response(status=0, message="db update failed")
#                 #return response(status=0, message="db update failed [{}]".foramt(message))
#         elif not training_status_check:
#             if resource_update_check:
#                 update_result, message = db.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name,
#                                                             training_gpu=training_gpu, deployment_gpu=deployment_gpu,
#                                                             start_datetime=start_datetime, end_datetime=end_datetime,
#                                                             manager_id=org_workspace['manager_id'], description=description, guaranteed_gpu=guaranteed_gpu)
#                 if update_result:
#                     return response(status=0, message="GPU resource updated, but user cannot move, jupyter or training running : {}".format(owner_move_error))
#                 else :
#                     return response(status=0, message="GPU resource update fail and jupyter or training running  : {} ".foramt(owner_move_error))
#                     #return response(status=0, message="GPU resource update fail [{}] and jupyter or training running  : {} ".foramt(message, owner_move_error))
#             return response(status=0, message="Update fail jupyter or training running : {}".format(owner_move_error))
#         elif not training_owner_check:
#             return response(status=0, message="Can not remove user")

#     except CustomErrorList as ce:
#         raise ce
#     except Exception as e:
#         # traceback.print_exc()
#         # return response(status=0, message="Update workspace Error")
#         raise e

# def delete_workspace(id_list, headers_user):
#     try:

#         status = 0
#         delete_flag = True
#         manger_check_flag = True
#         message = ""
#         name_list = []
#         workspace_info = []
#         for workspace_id in id_list:
#             workspace = get_workspace_info(workspace_id=workspace_id)
#             if workspace is None:
#                 continue

#             workspace_name = workspace['workspace_name']
#             name_list.append(workspace_name)

#             if workspace["running_status"]:
#                 raise RunningWorkspaceDeleteError

#             # for training in workspace['training']:
#             #     # if training['status'] != 'stop' or training["jupyter"].get("CPU").get("status") != "stop" or training["jupyter"].get("GPU").get("status") != "stop":
#             #     if training['status'] != 'stop' or training['editor_status'] != 'stop':
#             #         delete_flag = False
#             #         message += "[{}] have running [{}] training(job or jupyter(CPU or GPU).\n".format(workspace_name, training["training_name"])

#             # for deployment in workspace["deployment"]:
#             #     if deployment["status"] != "stop":
#             #         delete_flag = False
#             #         message += "[{}] have running [{}] deployment\n".format(workspace_name, deployment["name"])

#             workspace_info.append(workspace)


#         if delete_flag and manger_check_flag:
#             if len(name_list) != len(id_list):
#                 message = "Not found workspaces"
#             for idx, workspace_id in enumerate(id_list):
#                 workspace_name = name_list[idx]
#                 try:
#                     if not remove_workspace(workspace_id=workspace_id) :
#                         delete_workspace_folder(workspace_name=workspace_name)
#                 except Exception as e:
#                     traceback.print_exc()
#                     message += "[{}] Reason : {}".format(workspace_name, e) + " Workspace failed to remove workspace dir\n"
#                     delete_flag = False
#                     continue

#                 res = db.delete_workspace(workspace_id=workspace_id)
#                 if res:
#                     db.delete_user_workspace(workspace_id=workspace_id)

#                     message += "[{}] ".format(name_list[idx]) + "success\n"
#                     continue
#                 else:
#                     message += "[{}] ".format(name_list[idx]) + "db delete failed\n"
#                     delete_flag = False
#                     continue
#             if delete_flag:
#                 status = 1

#         return response(status=status, message=message)

#     except CustomErrorList as ce:
#         raise ce
#     except Exception as e:
#         # traceback.print_exc()
#         # return response(status=0, message="Delete workspace Error")
#         raise e


# def update_favorites(workspace_id, action, headers_user):
#     try:
#         if headers_user is None:
#             return response(status=0, message="Jf-user is None in headers")
#         user_id = db.get_user_id(headers_user)
#         if user_id is not None:
#             user_id = user_id['id']
#             result = db.update_favorites(user_id, workspace_id, action)
#             if result :
#                 return response(status=1, message="OK")
#             else:
#                 return response(status=0, message="Can not update db")
#         else:
#             return response(status=0, message="Can not find user")

#     except Exception as e:
#         print(e)
#         return response(status=0, message="Update favorites Error")

# # @ns.route('/<int:workspace_id>', methods=['GET'], doc={'params': {'workspace_id': '워크스페이스 ID'}})
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class Workspace(CustomResource):
# #     def __init__(self, workspace_id):
# #         self.workspace_id = workspace_id

# #     @token_checker
# #     def get(self, workspace_id):
# #         """해당 id의 워크스페이스 정보 조회"""
# #         res = get_workspace(workspace_id=workspace_id, user=self.check_user())
# #         db.request_logging(self.check_user(), 'workspaces/'+str(workspace_id), 'get', None, res['status'])
# #         return self.send(res)


# # @ns.route("", methods=['GET', 'POST', 'PUT'])
# # @ns.route('/<id_list>', methods=['DELETE'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class Workspaces(CustomResource):
# #     @token_checker
# #     @ns.expect(page_parser)
# #     def get(self):
# #         """워크스페이스 목록 조회"""
# #         args = page_parser.parse_args()
# #         page = args['page']
# #         size = args['size']
# #         search_key = args['search_key']
# #         search_value = args['search_value']
# #         res = get_workspaces(headers_user=self.check_user(), page=page, size=size, search_key=search_key,
# #                                         search_value=search_value)
# #         db.request_logging(self.check_user(), 'workspaces', 'get', None, res['status'])
# #         return self.send(res)

# #     @ns.expect(create_parser)
# #     @token_checker
# #     @admin_access_check(create_parser)
# #     def post(self):
# #         """워크스페이스 생성"""
# #         try:
# #             args = create_parser.parse_args()
# #             manager_id = args['manager_id']
# #             workspace_name = args['workspace_name']
# #             training_gpu = args['training_gpu']
# #             deployment_gpu = args['deployment_gpu']
# #             start_datetime = args['start_datetime']
# #             end_datetime = args['end_datetime']
# #             users = args['users_id']
# #             guaranteed_gpu = args["guaranteed_gpu"]
# #             description = args['description']
# #             storage_id = args['storage_id']
# #             workspace_size = args['workspace_size']

# #             res = create_workspace(manager_id=manager_id, workspace_name=workspace_name, training_gpu=training_gpu,
# #                                                 deployment_gpu=deployment_gpu, start_datetime=start_datetime, end_datetime=end_datetime,
# #                                                 description=description, guaranteed_gpu=guaranteed_gpu, users=users, headers_user=self.check_user(),
# #                                                 storage_id = storage_id, workspace_size=workspace_size)

# #             db.request_logging(self.check_user(), 'workspaces', 'post', str(args), res['status'])

# #             return self.send(res)
# #         except CustomErrorList as ce:
# #             return self.send(ce.response())
# #         except Exception as e:
# #             # Unknwon Error
# #             traceback.print_exc()
# #             return self.send(response(status=0, message="Workspace Create Error : {}".format(e)))

# #     @ns.expect(update_parser)
# #     @token_checker
# #     @admin_access_check()
# #     def put(self):
# #         """워크스페이스 수정"""
# #         try:
# #             args = update_parser.parse_args()
# #             workspace_id = args['workspace_id']
# #             workspace_name = args['workspace_name']
# #             training_gpu = args['training_gpu']
# #             deployment_gpu = args['deployment_gpu']
# #             start_datetime = args['start_datetime']
# #             end_datetime = args['end_datetime']
# #             users = args['users_id']
# #             manager_id = args['manager_id']
# #             guaranteed_gpu = args["guaranteed_gpu"]
# #             description = args['description']
# #             workspace_size = args['workspace_size']
# #             res = update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, training_gpu=training_gpu,
# #                                                 deployment_gpu=deployment_gpu, start_datetime=start_datetime, end_datetime=end_datetime, users=users,
# #                                                 description=description, guaranteed_gpu=guaranteed_gpu, headers_user=self.check_user(), manager_id=manager_id, workspace_size=workspace_size)
# #             db.request_logging(self.check_user(), 'workspaces', 'put', str(args), res['status'])
# #             return self.send(res)
# #         except CustomErrorList as ce:
# #             return self.send(ce.response())
# #         except Exception as e:
# #             traceback.print_exc()
# #             return self.send(response(status=0, message="Workspace Upade Error : {}".format(e)))

# #     @ns.param('id_list', 'id list')
# #     @token_checker
# #     @admin_access_check()
# #     def delete(self, id_list):
# #         """워크스페이스 삭제"""
# #         try:
# #             id_list = id_list.split(',')
# #             res = delete_workspace(id_list=id_list, headers_user=self.check_user())
# #             db.request_logging(self.check_user(), 'workspaces/'+str(id_list), 'delete', None, res['status'])
# #             return self.send(res)
# #         except CustomErrorList as ce:
# #             return self.send(ce.response())
# #         except Exception as e:
# #             traceback.print_exc()
# #             return self.send(response(status=0, message="Delete Workspace Error : {}".format(e)))


# # @ns.route("/favorites")
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class Favorites(CustomResource):
# #     @token_checker
# #     @ns.expect(favorites_parser)
# #     def post(self):
# #         """즐겨찾기 추가/삭제"""
# #         args = favorites_parser.parse_args()
# #         workspace_id = args['workspace_id']
# #         action = args['action']
# #         res = update_favorites(workspace_id=workspace_id, action=action, headers_user=self.check_user())
# #         db.request_logging(self.check_user(), 'workspaces/favorites', 'post', str(args), res['status'])
# #         return self.send(res)

# def get_workspace_gpu(workspace_id, headers_user):
#     try:
#         workspace_info = db.get_workspace(workspace_id=workspace_id)
#         check_result, res = permission_check(user=headers_user, workspace_info=workspace_info, permission_level=2)
#         if not check_result:
#             return res

#         training_gpu = int(workspace_info["gpu_training_total"])
#         deployment_gpu = int(workspace_info["gpu_deployment_total"])

#         result = {
#             "total_gpu": training_gpu + deployment_gpu,
#             "training_gpu" : training_gpu,
#             "deployment_gpu" : deployment_gpu,
#         }
#         return response(status=1, result=result)

#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get workspace gpu error : {}".format(e))

# def update_workspace_gpu(workspace_id, training_gpu, deployment_gpu, headers_user):
#     try:
#         workspace_info = db.get_workspace(workspace_id=workspace_id)
#         check_result, res = permission_check(user=headers_user, workspace_info=workspace_info, permission_level=2)
#         if not check_result:
#             return res

#         org_training_gpu = int(workspace_info["gpu_training_total"])
#         org_deployment_gpu = int(workspace_info["gpu_deployment_total"])
#         org_gpu_total = org_training_gpu + org_deployment_gpu
#         new_gpu_total = int(training_gpu) + int(deployment_gpu)

#         if training_gpu < 0 or deployment_gpu < 0:
#             return response(status=0, message="Cannot use '-' number value. training_gpu {}  deployment_gpu {}".format(training_gpu, deployment_gpu))
#         if org_gpu_total != new_gpu_total:
#             return response(status=0, message="Not math gpu total. Original : {} | New : {}".format(org_gpu_total, new_gpu_total))

#         db.update_workspace_gpu(workspace_id=workspace_id, training_gpu=int(training_gpu), deployment_gpu=int(deployment_gpu))

#         return response(status=1, message="Updated workspace gpu")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Update workspace gpu error : {}".format(e))


# # @ns.route("/<workspace_id>/gpu", methods=['GET', 'PUT'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class WorkspaceUpdateGpu(CustomResource):
# #     @token_checker
# #     def get(self, workspace_id):
# #         """워크스페이스 매니저 GPU 수정관련 조회"""

# #         res = get_workspace_gpu(workspace_id, self.check_user())

# #         return self.send(res)

# #     @token_checker
# #     @ns.expect(gpu_update_parser)
# #     def put(self, workspace_id):
# #         """워크스페이스 매니저 GPU 수정 """
# #         args = gpu_update_parser.parse_args()
# #         training_gpu = args["training_gpu"]
# #         deployment_gpu = args["deployment_gpu"]
# #         res = update_workspace_gpu(workspace_id, training_gpu, deployment_gpu, self.check_user())

# #         return self.send(res)

# def get_workspace_description(workspace_id, headers_user):
#     try:
#         workspace_info = db.get_workspace(workspace_id=workspace_id)
#         check_result, res = permission_check(user=headers_user, workspace_info=workspace_info, permission_level=2)
#         if not check_result:
#             return res

#         result = {
#             "description" : workspace_info["description"]
#         }
#         return response(status=1, result=result)

#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get workspace description error : {}".format(e))

# def update_workspace_description(workspace_id, description, headers_user):
#     try:
#         workspace_info = db.get_workspace(workspace_id=workspace_id)
#         check_result, res = permission_check(user=headers_user, workspace_info=workspace_info, permission_level=2)
#         if not check_result:
#             return res

#         db.update_workspace_description(workspace_id=workspace_id, description=description)

#         return response(status=1, message="Updated workspace description")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Update workspace description error : {}".format(e))

# # @ns.route("/<workspace_id>/description", methods=['GET', 'PUT'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class WorkspaceUpdateDescription(CustomResource):
# #     @token_checker
# #     def get(self, workspace_id):
# #         """워크스페이스 매니저 Description 수정"""
# #         res = get_workspace_description(workspace_id, self.check_user())
# #         return self.send(res)

# #     @token_checker
# #     @ns.expect(description_update_parser)
# #     def put(self, workspace_id):
# #         """워크스페이스 매니저 Description 수정"""
# #         args = description_update_parser.parse_args()
# #         description = args["description"]

# #         res = update_workspace_description(workspace_id, description, self.check_user())
# #         return self.send(res)

# # @ns.route("/set_ws_quota")
# # @ns.response(200, 'Success')
# # class Set_ws_quota(CustomResource):
# #     @ns.expect(set_ws_quota_parser)
# #     def get(self):
# #         """워크스페이스당 디스크 용량 제한 설정"""
# #         args = set_ws_quota_parser.parse_args()
# #         workspace_name = args['workspace_name']
# #         size = args['size']
# #         unit = args['unit']
# #         res = storage.set_workspace_quota(workspace_name,size,unit)
# #         return res

# # @ns.route("/get_ws_quota")
# # @ns.response(200, 'Success')
# # @ns.response(500, 'Fail')
# # class Get_ws_quota(CustomResource):
# #     @ns.expect(get_ws_quota_parser)
# #     def get(self):
# #         """워크스페이스당 디스크 용량 제한 설정값 불러오기"""
# #         args = get_ws_quota_parser.parse_args()
# #         workspace_name = args['workspace_name']
# #         res = storage.get_workspace_quota(workspace_name)
# #         return res

# def permission_check(user, workspace_info=None, workspace_manager=None, permission_level=0):
#     # permission level =  root(3) >= workspace owner ,training owner(2) >= user(1)
#     # return permission_level, response or message

#     error_message = ""
#     users = []
#     if workspace_info is not None:
#         workspace_manager = workspace_info["manager_name"]

#     if user is None:
#         return 0, response(status=0, message="Jf-user is None in headers")

#     if user == "root":
#         return 3, ""
#     elif permission_level >= 3:
#         error_message = "Must be a root"
#         return 0, response(status=0, message="Permission error : {}".format(error_message))

#     if user == "root" or user == workspace_manager:
#         return 2, ""
#     elif permission_level >= 2:
#         error_message = "Must be a root or Workspace manager"
#         return 0, response(status=0, message="Permission error : {}".format(error_message))


#     if user in users:
#         return 1, ""

#     return 0, response(status=0, message="Permission error : {}".format(error_message))

# def get_workspace_quota(workspace_name):
#     try:
#         result, error = common.launch_on_host("mfsgetquota -h /jfbcore/jf-data/workspaces/" + workspace_name)
#         dictToReturn = dict()
#         for line in result.splitlines()[1:]:
#             splitLine = line.replace(" ", '').split('|')
#             if splitLine[0] != 'size':
#                 dictToReturn[splitLine[0]] = splitLine[1]
#             else:
#                 dictToReturn[splitLine[0]] = splitLine[1]
#                 dictToReturn['soft_limit'] = splitLine[2]
#                 dictToReturn['hard_limit'] = splitLine[3]
#         return dictToReturn
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get workspace quota error : {}".format(e))

# def set_workspace_quota(workspace_name, size, unit):
#     try:
#         quota = int(quota) * 1.074
#         result, error = common.launch_on_host("mfssetquota -S " + str(
#             quota) + unit + " /jfbcore/jf-data/workspaces/" + workspace_name + """ | grep "size" | grep -v "real""")
#         return result
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Set workspace quota error : {}".format(e))