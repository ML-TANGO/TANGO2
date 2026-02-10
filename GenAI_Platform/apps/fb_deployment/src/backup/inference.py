# from utils.resource import CustomResource, token_checker
# from flask_restplus import reqparse, Resource
# from restplus import api
# from utils.resource import response
# import utils.common as common
# import traceback
# import time

# import os
# import requests
# import utils.kube as kube
# # import utils.db as db
# import json
# import base64
# import threading
# from deployment import create_deployment_with_ckpt, delete_deployment
# from deployment_worker import add_deployment_worker_with_run
# from utils.exceptions import *
# from settings import DEPLOYMENT_RESPONSE_TIMEOUT, INFERENCE_GPU_DEFAULT

# ns = api.namespace('inferences', description='inference API(for dna)')

# inference_status_get_parser = api.parser()
# inference_status_get_parser.add_argument('inference_id', required=True, type=int, location='args', help="")

# inference_get_parser = api.parser()
# inference_get_parser.add_argument('inference_id', required=True, type=int, location='args', help="")

# inference_post_parser = api.parser()
# inference_post_parser.add_argument('model_id', required=True, type=int, location='json', help="")
# inference_post_parser.add_argument('data_path', required=True, type=list, location='json', help="")
# inference_post_parser.add_argument('gpu_count', required=False, type=int, default=INFERENCE_GPU_DEFAULT, location='json', help="")

# MOUNT_POINT = "/jf-data/nfs-data"
# INFERENCE_THREAD_NAME = "Inference-Thread-{}"

# # def deployment_api(model_id, data_path):
#     # 추론 모델 등록 단계
#     # model_id = ckpt_id | ckpt_id 는  built_in_model_id를 포함
#     # WS에 SIR.WS.002를 통해 model_id를 등록

#     # 추론 요청 단계
#     # WS에서 model_id와 datapath를 전달해 추론 요청
#     # 1. model_id 정보를 기반으로 built_in_model_id + ckpt_id 조합해서 배포 생성, datapath 데이터는 마스터가 nfs 경로에서 바로 이용(master api에서 배포 생성된 api로 날릴거기 때문)
#     # 2. 배포가 생성 시도, (생성 시도가 성공 -> 추론 요청에 response 성공, 생성 시도가 실패 (자원이 없거나 하는 이유로) -> 추론 요청에 response 실패)
#     # return에 inference_id 포함
#     # inference_id = deployment_id

#     # 추론 상태 조회 단계
#     # 3. 배포내 API가 실행 되기를 기다림
#     # 4. 배포 상태가 에러 -> 실패 저장, 배포 상태가 실행 중 -> 입력받은 data_path의 파일을 전송
#     # 5. response 받은 결과를 파일로 저장 (inference_id 기준으로)
#     # 6. 끝나면 배포 종료

#     # 추론 결과 조회 단계
#     # 7. inference_id로 배포 결과 요청 시 해당 파일 경로 전송


# # model_id = ifcModelID
# # checkpoint
# #

# # id
# # built_in_model_id
# # checkpoint_path

# # JF용
# # workerspace - training - job - param
# # COPY -> ?

# # 해당 이름으로 일치하는 workspace와 user가 있어야함
# DNA_LEVEL1_WORKSPACE = "dna-level1"
# DNA_LEVEL1_USER = "dna-level1"

# DNA_LEVEL2_WORKSPACE = "dna-level2"
# DNA_LEVEL2_USER = "dna-level2"



# def inference_request(model_id, data_path="/jfbcore/jf-data/nfs-data/deploytest", gpu_count=INFERENCE_GPU_DEFAULT, headers_user=None):
#     try:
#         user_id_info = db.get_user_id(user_name=headers_user) #TODO none case 시 처리
#         if user_id_info is None:
#             headers_user = DNA_LEVEL2_USER
#             user_id_info = db.get_user_id(user_name=DNA_LEVEL2_USER)

#         user_id = user_id_info["id"]
#         if headers_user == DNA_LEVEL1_USER :
#             # level1
#             workspace_id = db.get_workspace(workspace_name=DNA_LEVEL1_WORKSPACE)["id"]
#         elif headers_user == DNA_LEVEL2_USER :
#             # level2
#             workspace_id = db.get_workspace(workspace_name=DNA_LEVEL2_WORKSPACE)["id"]
#         else :
#             # level3
#             workspace_id = db.get_user_workspace(user_id=user_id)[0]["id"]


#         checkpoint_info = db.get_checkpoint(checkpoint_id=model_id)
#         #TODO 2021-12-27 deployment -> deployment_worker
#         create_and_run_result = create_deployment_with_ckpt(workspace_id=workspace_id, checkpoint_id=model_id, owner_id=user_id, gpu_count=gpu_count, headers_user=headers_user)
#         if create_and_run_result["status"] == 0:
#             return create_and_run_result

#         else:
#             inference_id = create_and_run_result["result"]["inference_id"]
#             add_result = add_deployment_worker_with_run(deployment_id=inference_id, headers_user=headers_user)
#             if add_result["status"] == 0:
#                 inference_id = create_and_run_result["result"]["inference_id"]
#                 delete_deployment([inference_id], "root")
#                 return add_result
#             master_to_deployment_thread = threading.Thread(name=INFERENCE_THREAD_NAME.format(inference_id), target=master_to_deployment_api, args=(data_path, inference_id, checkpoint_info["built_in_model_id"]))
#             master_to_deployment_thread.start()
#             return create_and_run_result

#         # inference_id from deployment_run


#         # do(data_path=data_path, inference_id=inference_id, built_in_model_id=checkpoint_info["built_in_model_id"])
#     except CustomErrorList as ce:
#         delete_deployment([inference_id], "root")
#         return response(status=0, message=ce.message)
#     except Exception as e:
#         inference_id = create_and_run_result["result"]["inference_id"]
#         delete_deployment([inference_id], "root")
#         traceback.print_exc()
#         return response(status=0, message="Inference Error.")


# # using thread
# def master_to_deployment_api(data_path, inference_id, built_in_model_id):

#     # built_in_model_id, checkpoint_path = get_model_detail_info(model_id)

#     # deployment_run_and_start(built_in_model_id, checkpoint_path)

#     # test "https://192.168.1.32:30001/deployment/h2e8eb0f593dc8978e3418fa8044d7b0c/" built_in_model_id = 1012

#     for i in range(DEPLOYMENT_RESPONSE_TIMEOUT):
#         kube_status = kube.get_deployment_worker_status(deployment_id=inference_id)
#         time.sleep(1)
#         print("{} watining. {}/{}".format(inference_id, i, DEPLOYMENT_RESPONSE_TIMEOUT))
#         if kube_status["status"] == "running":
#             break

#     model_api_url = kube.get_deployment_full_api_address(deployment_id=inference_id) # from deployment_id
#     if model_api_url is None:
#         delete_deployment([inference_id], "root")
#         raise ItemNotExistError("Model API not Exist")
#     print("URL ", model_api_url)

#     api_key = deployment_api_call_info_get(built_in_model_id)["api_key"] # from deployment_api_call_info_get


#     deployment_api_call_and_write(data_path=data_path, model_api_url=model_api_url, api_key=api_key, inference_id=inference_id)
#     delete_deployment([inference_id], "root")

#     # stop deployment

# def get_model_detail_info(model_id):
#     checkpoint_info = db.get_checkpoint(checkpoint_id=model_id)
#     if checkpoint_info is None:
#         raise ItemNotExistError("Model ID not Exist")
#     ## get built_in_model_id, ckpt_id
#     built_in_model_id = checkpoint_info["built_in_model_id"]
#     checkpoint_path = checkpoint_info["checkpoint_file_path"]
#     return built_in_model_id, checkpoint_path

# def deployment_api_call_info_get(built_in_model_id):
#     deployment_form_info = db.get_built_in_model_data_deployment_form(built_in_model_id)[0]
#     # deployment data form 은 무조건 하나만 있다고 가정

#     return {
#         "api_key": deployment_form_info["api_key"],
#         "category": deployment_form_info["category"]
#     }

# def deployment_api_call_and_write(data_path, model_api_url, api_key, inference_id):
#     item_type = ""
#     try:
#         # api_key - from built_in_model_deployment_form
#         print("API CALL TEST", data_path, model_api_url, api_key, inference_id)
#         url = model_api_url
#         result_path = get_inference_result_path(inference_id)
#         status_file_path = get_inference_result_status_file_path(inference_id)
#         done_mark = get_inference_done_mark(inference_id)
#         error_mark = get_inference_error_mark(inference_id)
#         type_mark = get_inference_type_mark(inference_id)

#         os.system("rm -r -f {}".format(result_path))
#         os.system("mkdir -p {}".format(result_path))

#         file_list = []
#         for path in data_path:
#             join_path = "{}/{}".format("", path) # MOUNT 경로가 FULL PATH가 아닌 경우에는 주석 된 부분 사용"{}/{}".format(MOUNT_POINT, path)
#             if os.path.isfile(join_path):
#                 file_list.append({
#                     "name": path.split("/")[-1],
#                     "path": "/".join(path.split("/")[:-1]),
#                     "join_path": "/".join(join_path.split("/")[:-1]),
#                 })
#                 continue

#             list_dir = os.listdir(join_path)
#             for name in list_dir:
#                 file_name = join_path+"/{}".format(name)
#                 if os.path.isfile(file_name):
#                     file_list.append({
#                         "name": name,
#                         "path": path,
#                         "join_path": join_path
#                     })

#         os.system("echo '{}/{}' > {}".format(0, len(file_list), status_file_path))

#         try:
#             for i, file_info in enumerate(file_list):
#                 name = file_info["name"]
#                 path = file_info["path"]
#                 join_path = file_info["join_path"]
#                 st = time.time()
#                 try:
#                     response = None
#                     response = requests.request("POST", url, files=[(api_key, (name,open(join_path+"/{}".format(name),'rb')))], verify=False, timeout=DEPLOYMENT_RESPONSE_TIMEOUT)
#                     js = json.loads(response.text)
#                 except:
#                     try:
#                         response = None
#                         response = requests.request("POST", url, files=[(api_key, (name,open(join_path+"/{}".format(name),'rb')))], verify=False, timeout=DEPLOYMENT_RESPONSE_TIMEOUT)
#                         js = json.loads(response.text)
#                     except:
#                         print("inference id : {} | file : {} | response : {}".format(inference_id, name, response))
#                         print("TIMEOUT : {}".format(time.time() - st))
#                         response_status = None
#                         if response is not None:
#                             response_status = response.status_code
#                         os.system("touch {}/{}.{}error".format(result_path, name, response_status))
#                         os.system("echo '{}/{}' > {}".format(i+1, len(file_list), status_file_path))
#                         continue

#                 for result_key, result_value in js.items():
#                     item_type = result_key
#                     os.system('echo "{}" > {}'.format(item_type, type_mark))
#                     print("DEPLOYMENT ITEM TYPE", item_type)

#                 # result는 1:1 맵핑
#                 for key, value in js[item_type][0].items():
#                     bs64 = base64.b64decode(value)
#                     os.system("mkdir -p {}/{}".format(result_path, path))
#                     with open("{}/{}/{}".format(result_path, path, name),"wb") as f:
#                         print("writed ", name)
#                         f.write(bs64)
#                         f.close()

#                 os.system("echo '{}/{}' > {}".format(i+1, len(file_list), status_file_path))
#         except:
#             print("inference id : {} | file : {} | response : {}".format(inference_id, name, response))
#             traceback.print_exc()
#             res, message = kube.kuber_item_remove(deployment_id=inference_id)


#     except FileNotFoundError as fne:
#         traceback.print_exc()
#         os.system('echo "{}" > {}'.format(fne, error_mark))
#         res, message = kube.kuber_item_remove(deployment_id=inference_id)
#     except Exception as e:
#         traceback.print_exc()
#         os.system('echo "{}" > {}'.format(e, error_mark))
#         res, message = kube.kuber_item_remove(deployment_id=inference_id)


#     set_inference_done_mark(inference_id) # os.system("touch {}".format(done_mark))
#     res, message = kube.kuber_item_remove(deployment_id=inference_id)


# def get_inference_result_path(inference_id):
#     result_path = "/jf-data/inference_result/{}/".format(inference_id)
#     return result_path

# def get_inference_error_mark(inference_id):
#     base_path = get_inference_result_path(inference_id)
#     error_mark ="{}/error".format(base_path)
#     return error_mark

# def get_inference_type_mark(inference_id):
#     base_path = get_inference_result_path(inference_id)
#     type_mark ="{}/.type".format(base_path)
#     return type_mark

# def get_inference_done_mark(inference_id):
#     base_path = get_inference_result_path(inference_id)
#     done_mark ="{}/.done".format(base_path)
#     return done_mark

# def set_inference_done_mark(inference_id):
#     os.system("rm {}".format(get_inference_result_status_file_path(inference_id)))
#     os.system("touch {}".format(get_inference_done_mark(inference_id)))

# def get_inference_result_status_file_path(inference_id):
#     base_path = get_inference_result_path(inference_id)
#     status_mark = "{}/.status".format(base_path)
#     return status_mark

# def inference_result_path_get(inference_id):
#     try:
#         inference_status = inference_status_get(inference_id)
#         if inference_status["status"] == 0:
#             return inference_status

#         elif inference_status["result"]["inference_status"] != 0:
#             return response(status=0, message="Inference is in progress.")

#         #TODO NFS-MOUNT 경로 정보 파라미터화
#         result_path = "/jf-data/inference_result/{}/*".format(inference_id)
#         target_path = "inference_result/{}/".format(inference_id)
#         mount_base_target_path = "{}/{}".format(MOUNT_POINT, target_path)
#         os.system("mkdir -p {}".format(mount_base_target_path))
#         os.system("mv {} {}".format(result_path, mount_base_target_path))
#         output_type = None
#         try:
#             with open(get_inference_type_mark(inference_id), "r") as fr:
#                 output_type = fr.read().replace("\n", "")
#         except Exception as e:
#             traceback.print_exc()


#         return response(status=1, result={
#             "file_path": target_path,
#             "type": output_type
#         })
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get Inference result error : {} ".format(e))

# def get_inference_thread(inference_id):
#     for key, value in common.PID_THREADING_DICT.items():
#         if INFERENCE_THREAD_NAME.format(inference_id) in value:
#             return True

#     return False


# def inference_status_get(inference_id):
#     # 0 = 완료
#     # 1 = 로딩 중 (kube로부터 deployment가 컨테이너 생성 중, 설치 중)
#     # 2 = 추론 중 (.status로 부터 파일 남은 개수 현황 정도)
#     try:
#         inference_form_kube_status = {
#             "status": None,
#             "reason": None,
#             "phase": None,
#             "interval": None
#         } # RTT 쪽에서 형변환 때문에 이것만 필요
#         done_path = get_inference_done_mark(inference_id) #"/jf-data/inference_result/{}/.running".format(inference_id)
#         status_path = get_inference_result_status_file_path(inference_id)
#         inference_status = 99
#         status_detail = None
#         ## 완료 = .done 파일이 있거나 하면?
#         if os.path.isfile(done_path):
#             inference_status = 0
#             return response(status=1, result={
#                 "inference_status": inference_status,
#                 "status_detail": None
#             })

#         ## 로딩 중 관련 스탭
#         kube_status = kube.get_deployment_worker_status(deployment_id=inference_id)
#         for key in inference_form_kube_status.keys():
#             inference_form_kube_status[key] = kube_status.get(key)

#         kube_status = inference_form_kube_status

#         if kube_status["status"] in ["running", "error"]:
#             inference_status = 2
#         elif kube_status["status"] is not "stop":
#             inference_status = 1
#         #running 이면 추론 중 스탭으로

#         print("THREAD EXIST ", get_inference_thread(inference_id))

#         if inference_status == 2 and get_inference_thread(inference_id) == False:
#             # MASTER API 에서 Thread가 종료 된 상황 - 진행 불가
#             # deployment 삭제
#             set_inference_done_mark(inference_id)
#             delete_deployment([inference_id], "root")
#             return response(status=1, result={
#                 "inference_status": 0,
#                 "status_detail": None
#             })

#         ## 추론 중 관련 스탭
#         try:
#             if os.path.isfile(status_path):
#                 inference_status = 2
#                 with open(status_path, "r") as fr:
#                     status_detail = fr.readline()
#         except:
#             traceback.print_exc()

#         return response(status=1, result={
#             "inference_status": inference_status,
#             "kube_status": kube_status,
#             "status_detail": status_detail
#         })
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Get inference status error : {}".format(e))

# @ns.route('')
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class Inference(CustomResource):
#     @ns.expect(inference_get_parser)
#     def get(self):
#         args = inference_get_parser.parse_args()
#         inference_id = args["inference_id"]

#         return self.send(inference_result_path_get(inference_id))

#     @ns.expect(inference_post_parser)
#     def post(self):
#         """TEST"""
#         args = inference_post_parser.parse_args()
#         model_id = args["model_id"]
#         data_path = args["data_path"]
#         gpu_count = args["gpu_count"]
#         headers_user = DNA_LEVEL2_USER if self.check_user() is None else  self.check_user()
#         print(headers_user)
#         res = inference_request(model_id, data_path, gpu_count, headers_user=headers_user)
#         return self.send(res)

# @ns.route('/status')
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class InferenceStatus(CustomResource):
#     @ns.expect(inference_status_get_parser)
#     def get(self):
#         args = inference_status_get_parser.parse_args()
#         inference_id = args["inference_id"]
#         inf_status = inference_status_get(inference_id)
#         print("Inf status", inf_status)
#         return self.send(inf_status)