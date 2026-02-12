# import traceback
# from utils.settings import INGRESS_PROTOCOL, EXTERNAL_HOST, EXTERNAL_HOST_REDIRECT, DEPLOYMENT_API_MODE, JF_SYSTEM_NAMESPACE
# from utils.TYPE import DEPLOYMENT_PORT_MODE, DEPLOYMENT_TYPE #  TRAINING_TYPE,
# #(DEPLOYMENT_API_MODE_LABEL_KEY, DEPLOYMENT_PREFIX_MODE, DEPLOYMENT_API_PORT_NAME, KUBE_POD_STATUS_RUNNING, KUBE_POD_STATUS_INSTALLING)
# # from utils import db
# import utils.kube_parser as kube_parser
# # from utils.kube import get_pod_cpu_ram_usage_file, get_pod_gpu_usage_file, get_pod_cpu_ram_usage_history_file, get_pod_gpu_usage_history_file
# from kubernetes import client, stream
# networkingV1Api = client.NetworkingV1Api()
# coreV1Api = client.CoreV1Api()

# # list
# def get_deployment_pod_list(deployment_id, namespace="default"):
#     try:
#         selector=f"deployment_id={deployment_id}"
#         pod_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=selector).items
#         return pod_list
#     except Exception as e:
#         traceback.print_exc()
#         return None

# def get_deployment_worker_pod_list(deployment_worker_id, namespace="default"):
#     try:
#         selector=f"deployment_worker_id={deployment_worker_id}"
#         pod_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=selector).items

#         return pod_list
#     except Exception as e:
#         traceback.print_exc()
#         return None

# # status
# def get_deployment_pod_status(deployment_worker_id=None, deployment_id=None, namespace="default", start_datetime=None, end_datetime=None):
#     """
#     Description : 
#         deployment_id or deployment_worker_id로 pod status 조회
#     Args :
#         deployment_worker_id (int) : 특정 deployment_worker_id 만 조회 시

#         deployment_id (int) : deployment_id를 가진 worker들 status 종합하여 (하나라도 running이면 ?) (deployment_id 밑에 worker 종류 외에도 생기면 추가 옵션이 필요)

#         pod_list (object) : from kube_data.get_pod_list()
#         start_datetime (str) : Workspace 시작 시간 ex ) "2000-01-01 00:00" - 예약 상태 표시용
#         end_datetime (str) : Workspace 만료 시간 ex ) "2000-01-01 00:00" - 만료 상태 표시용
#     """
#     try:
#         if start_datetime is None:
#             start_datetime = "2000-01-01 00:00"
#         if end_datetime is None:
#             end_datetime = "9999-01-01 00:00"


#         # 하나라도 running 상태가 있으면 API 처리를 해줄 수 있으므로 Running 임
#         status = {"status": None, "reason": None, "resolution": None, "message": None, "phase": None, "interval": None, "restart_count": None}
#         """
#         status        running, installing, error, +
#         reason        워커 - 에러 종류 출력
#         resolution    워커 - 에러 종류 아래 해결방법 출력
#         restart_count 없으면 미리보기 터짐 (서빙 -> 배포 -> 워커 -> 미리보기)
#         """

#         # status = get_specific_deployment_worker_pod_status(deployment_id=deployment_id, deployment_worker_id=deployment_worker_id)
        
#         selector=""
#         if deployment_worker_id != None:
#             selector=f"deployment_worker_id={deployment_worker_id}"
#         elif deployment_id != None:
#             selector=f"deployment_id={deployment_id}"

#         pod_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=selector).items

#         if len(pod_list) > 0:
#             for pod_item in pod_list:
#                 # ========================================================================================================
#                 # TODO pod phase : Pending, Running, Succeded, Faile, Unkown
#                 if pod_item.status.phase == "Pending":
#                     status["status"] = "installing" # pending 상태를 따로 구분해서 보여주는 것??
#                     return status
#                 elif pod_item.status.container_statuses[0].started == False:
#                     # pod error 인 경우
#                     container_waiting_reason = {
#                         'CrashLoopBackOff' : 'This error can be caused by a variery of issues',
#                         'ErrImagePull' : 'Wrong image name, Check the image or tag exist',
#                         'ImagePullBackOff' : 'Wrong image name, Check the image or tag exist',
#                         'InvalidImageName' : 'Wrong image name, Check the image or tag exist',
#                         'CreateContainerConfigError' : 'ConfigMap or Secret is missing. Identify the missing ConfigMap or Secret',
#                         'CreateContainerError' : 'Container experienced an error when starting. Modify image specification to resolve it or Add a valid command to start the container',
#                         'RunContainerError': "Run Container Error. Check  Driver, package version or status. "
#                     }

#                     state = pod_item.status.container_statuses[0].state 
        
#                     if state.waiting and state.waiting.reason and state.waiting.reason in container_waiting_reason.keys():
#                         status["status"] = "error"
#                         status["reason"] = pod_item.status.container_statuses[0].state.waiting.reason
#                         status["resolution"] = container_waiting_reason[str(pod_item.status.container_statuses[0].state.waiting.reason)]
#                         try:
#                             status["message"] = pod_item.status.container_statuses[0].state.waiting.message
#                         except:
#                             pass
#                     elif state.waiting and state.waiting.reason and state.waiting.reason == "ContainerCreating":
#                         status["status"] = "installing"
#                         status["reason"] = "Take a long time to download image or Image have problem"
#                         status["resolution"] = "wait, and if pod restarts repeatly, this situation is error"
#                     return status
#                 elif pod_item.status.phase == "Failed":
#                     status["status"] = "Error"
#                     return status
#                 elif pod_item.status.phase != "Running":
#                     status["status"] = "installing"
#                     return status
#                 # ========================================================================================================
#                 pod_name = pod_item.metadata.name
#                 pod_command = ['/bin/sh', '-c', "ls -a /pod-status |  grep -v -e '^.$' -e '^..$'"]
#                 res = stream.stream(coreV1Api.connect_get_namespaced_pod_exec, namespace=namespace, name=pod_name, command=pod_command, stderr=True, stdout=True, tty=False)
#                 res = res.strip()

#                 if res == '.installing':
#                     status["status"] = "installing"
#                     break
#                 elif res == '.error':
#                     status["status"] = "error"
#                     break
#                 elif res == "":
#                     # TODO
#                     status["phase"] = pod_item.status.phase
#                     status["restart_count"] = pod_item.status.container_statuses[0].restart_count
#                     status["status"] = "running"
#         return status
#     except Exception as e:
#         traceback.print_exc()
#         return status
        
# def get_serving_status(service_id, start_datetime=None, end_datetime=None, namespace="default"):
#     """테스트 페이지에서 보여주는 status"""
#     status = get_deployment_pod_status(deployment_id=service_id, namespace="default", start_datetime=start_datetime, end_datetime=end_datetime)
#     if status["status"] == "running":
#         status["status"] = "active"
#     elif status["status"] == None:
#         status["status"] = "stop"
    
#     keylist = ["status", "reason"]
#     res =  dict(zip(keylist, [status[key] for key in keylist if key in status]))
#     return res

# # api    
# def get_deployment_full_api_address(deployment_id, namespace="default"):
#     try:
#         # 1. path
#         ingress_list = networkingV1Api.list_namespaced_ingress(namespace=namespace, label_selector=f"deployment_id={deployment_id}").items
#         if ingress_list == []:
#             return None
#         path = ingress_list[0].spec.rules[0].http.paths[0].path.replace("(/|$)(.*)", "")
        
#         # 2. address
#         if DEPLOYMENT_API_MODE == DEPLOYMENT_PORT_MODE:
#             print("ERROR: MSA에서 'prefix' 만 사용하는 경우에 대하여 로직 작성함")
#             return None
#         if EXTERNAL_HOST is None:
#             print("ERROR: MSA에서 EXTERNAL_HOST가 none 인 경우는 잘못된 경우, 로직필요")
#             return None
#         if EXTERNAL_HOST_REDIRECT == False:
#             print("ERROR: MSA에서 EXTERNAL_HOST_REDIRECT false 인 경우 없음, 로직필요")
#             return None

#         # 3. full address
#         full_api_address = f"{INGRESS_PROTOCOL}://{EXTERNAL_HOST}{path}/"
#         return full_api_address
#     except Exception as e:
#         traceback.print_exc()
#         return None

# # resource
# def get_pod_resource_info(deployment_worker_id, namespace="default"):
#     try:
#         result = {}
#         item_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=f"deployment_worker_id={deployment_worker_id}").items
#         if len(item_list) < 1:
#             return None
        
#         result.update(kube_parser.parsing_pod_other_resource(item_list[0]))
#         result.update(kube_parser.parsing_pod_network_interface(item_list[0]))
#         return result
#     except Exception as e:
#         return None

# def get_pod_cpu_ram_usage_info(deployment_worker_id, namespace="default"):
#     try:
#         item_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=f"deployment_worker_id={deployment_worker_id}").items
#         if len(item_list) < 1:
#             return None
#         data = get_pod_cpu_ram_usage_file(item_list[0].metadata.name)
#         return data
#     except Exception as e:
#         return None

# def get_pod_gpu_usage_info(deployment_worker_id, namespace="default"):
#     try:
#         item_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=f"deployment_worker_id={deployment_worker_id}").items
#         if len(item_list) < 1:
#             return None
#         data = get_pod_gpu_usage_file(item_list[0].metadata.name)
#         return data
#     except Exception as e:
#         return None

# def get_pod_cpu_ram_usage_history_info(deployment_worker_id, namespace="default"):
#     try:
#         item_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=f"deployment_worker_id={deployment_worker_id}").items
#         if len(item_list) < 1:
#             return None
#         data = get_pod_cpu_ram_usage_history_file(item_list[0].metadata.name)
#         return data
#     except Exception as e:
#         return None

# def get_pod_gpu_usage_history_info(deployment_worker_id, namespace="default"):
#     try:
#         item_list = coreV1Api.list_namespaced_pod(namespace=namespace, label_selector=f"deployment_worker_id={deployment_worker_id}").items
#         if len(item_list) < 1:
#             return None
#         data = get_pod_gpu_usage_history_file(item_list[0].metadata.name)
#         return data
#     except Exception as e:
#         return None

# # options
# def get_workspace_gpu_count(workspace_id=None, workspace_list=None):
#     # all workspaces
#     workspaces = {}
#     # {
#     #     "workspaces": {
#     #         "workspace_id" : {
#     #             "training_used" : ,
#     #             "training_total": ,
#     #             "deployment_used" : ,
#     #             "deployment_total" : , 
#     #         }
#     #     }
#     # }
#     # or workspace_id is not None
#     # {
#     #     "training_used" : ,
#     #     "training_total": ,
#     #     "deployment_used" : ,
#     #     "deployment_total" : ,  
#     # }
#     try:
#         if workspace_list is None:
#             workspace_list = db.get_workspace_list() if workspace_id is None else [ db.get_workspace(workspace_id=workspace_id) ]
            
#         for workspace in workspace_list:
#             workspaces[workspace["id"]] = {
#                 # "{}_used".format(TRAINING_TYPE) : 0,
#                 # "{}_total".format(TRAINING_TYPE): workspace["gpu_{}_total".format(TRAINING_TYPE)],
#                 "{}_used".format(DEPLOYMENT_TYPE) : 0,
#                 "{}_total".format(DEPLOYMENT_TYPE): workspace["gpu_{}_total".format(DEPLOYMENT_TYPE)]
#             }

#             # find_kuber_item_name_and_item_list = find_kuber_item_name_and_item(workspace_id=workspace["id"], item_list=pod_list)
#             # MSA 수정
#             selector=f"workspace_id={workspace['id']}"
#             pod_list = coreV1Api.list_namespaced_pod(namespace="default", label_selector=selector).items

#             for kuber_item in pod_list:
#                 pod = kuber_item["item"]
#                 pod_labels = kube_parser.parsing_item_labels(pod)
#                 type_ = kube_parser.parsing_pod_item_type(pod) + "_used"
#                 num_gpu = kube_parser.parsing_pod_gpu_usage_count(pod)
#                 pod_workspace_id = int(pod_labels['workspace_id'])
#                 if workspaces[pod_workspace_id].get(type_) is None:
#                     workspaces[pod_workspace_id][type_] = num_gpu
#                 else:
#                     workspaces[pod_workspace_id][type_]  += num_gpu
#     except:
#         traceback.print_exc()
#     return workspaces if workspace_id is None else workspaces.get(workspace_id)