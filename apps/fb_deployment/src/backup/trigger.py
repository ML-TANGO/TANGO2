# #####################################################################################################
# ####################################### 코드 백업 ####################################################
# #####################################################################################################

# import time
# from utils.kube import PodAllResourceUsageInfo, PodNginxInfo
# import utils.kube as kube
# import utils.kube_parser as kube_parser

# from deployment_worker.service import stop_deployment_worker, add_deployment_worker_with_run, add_deployment_worker_with_run_gpu_share
# import traceback

# # GPU Share 옵션은 어떻게 활용할지 고려 필요함

# STOP_MODE_OLDEST="oldest"
# STOP_MODE_LATEST="latest"

# class TriggerController:

#     def __init__(self, deployment_id, stop_mode=STOP_MODE_OLDEST):
#         self.deployment_id = deployment_id
#         self.executor_name = "root"
#         self.min_worker = None
#         self.max_worker = None
#         self.stop_mode = stop_mode # OLDEST, NEWEST

#     def add_deployment_worker(self):
#         try:
#             deployment_id = self.deployment_id
#             result = add_deployment_worker_with_run(deployment_id=deployment_id, headers_user=self.executor_name)
#             if result["status"] == 1:
#                 return True
#             else :
#                 print("FAIL ADD WORKER : ", result)
#                 return False
#         except :
#             traceback.print_exc()
#             return False
#         return True

#     def stop_deployment_worker(self, deployment_worker_id=None):
#         try:
#             if deployment_worker_id is None:
#                 if self.stop_mode == STOP_MODE_OLDEST:
#                     deployment_worker_id = self.get_oldest_deployment_worker_id()                
#                 elif self.stop_mode == STOP_MODE_LATEST:
#                     deployment_worker_id = self.get_latest_deployment_worker_id()
                
#             if deployment_worker_id is None:
#                 return False
            
#             stop_deployment_worker(deployment_worker_id=deployment_worker_id)
#         except:
#             traceback.print_exc()
#             return False
#         return True

#     def get_latest_deployment_worker_id(self):
#         """
#             Description : 특정 Deployment 내에서 가장 최신의 Deployment worker id 조회
#         """
#         worker_list = self._get_deployment_worker_list()
#         if len(worker_list) == 0:
#             return None
        
#         deployment_worker_id = kube_parser.parsing_item_labels(worker_list[-1]["item"])["deployment_worker_id"]
#         return deployment_worker_id


#     def get_oldest_deployment_worker_id(self):
#         """
#             Description : 특정 Deployment 내에서 가장 오래된 Deployment worker id 조회
#         """
        
#         worker_list = self._get_deployment_worker_list()
#         if len(worker_list) == 0:
#             return None
        
#         deployment_worker_id = kube_parser.parsing_item_labels(worker_list[0]["item"])["deployment_worker_id"]
        
#         return deployment_worker_id


#     def get_number_of_deployment_worker(self):
#         """
#             Description : 특정 Deployment 내에서 동작중인 Deployment Worker 개수
#         """
#         num_of_deployment_worker = len(self._get_deployment_worker_list())
#         return num_of_deployment_worker
    
#     def get_deployment_worker_id_list(self):
#         """
#             Description : 특정 Deployment 내에서 동작중인 Deployment worker id list 조회.
#         """

#         worker_list = self._get_deployment_worker_list()
#         deployment_worker_id_list = []
#         for worker in worker_list:
#             deployment_worker_id = kube_parser.parsing_item_labels(worker["item"])["deployment_worker_id"]
#             deployment_worker_id_list.append(deployment_worker_id)

#         return deployment_worker_id_list


#     def _get_deployment_worker_list(self):
#         # TODO GPU SHARE 하지 않는 WORKER LIST만 조회가 필요할 수 있음
#         pod_list = kube.kube_data.get_pod_list()
#         worker_list = kube.find_kuber_item_name_and_item(item_list=pod_list, deployment_id=self.deployment_id)
#         return worker_list

# # CPU / RAM / GPU / Network 탐지
# PodAllResourceUsageInfo

# # NGINX LOG Parsing
# PodNginxInfo
# # 시간 예약
# # TZ - UTC

# def trigger_main():

#     while(1):
        
#         # 추가 / 종료 / 아무 행동 X
#         # 이슈 사항
#         # - 여러개를 제시 할 것인가 ?
#         # - 여러개의 결과를 종합하는 경우 추가 / 종료 가 섞여있는 경우는 ?
#         # * 추가를 해야하는데 하지 않는 것은 서비스 속도에 영향이 있지만
#         # * 종료를 해야하는데 하지 않는 것은 서비스 속도에 영향이 적음
#         # Check - 사용자 코드 이벤트
#         # Check - CPU / RAM / GPU / Network 이벤트
#         # Check - NGINX LOG 이벤트
        
#         # 최소 개수를 보장
#         # Check - 시간 예약 이벤트 


#         # Check 결과를 종합해서 추가 / 종료 / 아무 행동 X 선택

#         time.sleep(1)

