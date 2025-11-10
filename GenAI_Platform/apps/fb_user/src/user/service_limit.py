# from utils.resource import response
# # from flask_restplus import reqparse
# # from flask import send_file
# # from restplus import api
# from utils.common import JfLock, global_lock
# # from utils.resource import CustomResource, token_checker
# # # import utils.db as db
# from utils.msa_db import db_user

# import traceback
# # from utils.settings import USER_DOCKER_IMAGE_LIMIT, USER_DATASET_LIMIT, USER_TRAINING_LIMIT, USER_DEPLOYMENT_LIMIT

# # parser = reqparse.RequestParser()
# # Router Function

# # ns = api.namespace('users', description='USER API')
# # User GET
# # user_limit_get = api.parser()
# # user_limit_get.add_argument('workspace_id', required=False, default=None, type=int, location='args', help='Workspace ID, (None) For limit per user or (workspace id use) For limit per workspace')

# ####################################################################################################################################
# def user_docker_image_limit_check(user_id):
#     try:
#         result = {
#                 "current": 0,
#                 "limit" : None
#             }    
#         user_docker_image_list = db_user.get_user_docker_image(user_id)
        
#         if user_docker_image_list is None or len(user_docker_image_list) == 0:
#             result["current"] = 0
#         else :
#             result["current"] = len(user_docker_image_list)

#         result = limit_check(result)
#         return result
#     except Exception as e:
#         traceback.print_exc()

# def _user_docker_image_limit_check(user_id):
#     try:
#         if user_id is None:
#             raise RuntimeError('User ID is None.')
#         check_result = user_docker_image_limit_check(user_id)
#         return response(status=1, result=check_result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="User docker image limit check error : {} ".format(str(e)))
# ###################################################################################################################################
# ###################################################################################################################################
# def user_dataset_limit_check(user_id, workspace_id):
#     try:
#         result = {
#                 "current": 0,
#                 "limit" : None
#             }   
#         if workspace_id is None:
#             user_dataset_list = db_user.get_user_dataset(user_id)
#         else :
#             user_dataset_list = db_user.get_user_workspace_dataset(user_id, workspace_id)
        
#         if user_dataset_list is None or len(user_dataset_list) == 0:
#             result["current"] = 0
#         else :
#             result["current"] = len(user_dataset_list)

#         result = limit_check(result)
#         return result
#     except Exception as e:
#         traceback.print_exc()

# def _user_dataset_limit_check(user_id, workspace_id=None):
#     try:
#         if user_id is None:
#             raise RuntimeError('User ID is None.')
        
#         check_result = user_dataset_limit_check(user_id, workspace_id)
#         return response(status=1, result=check_result)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="User dataset limit check error : {} ".format(str(e)))
# ####################################################################################################################################
# ####################################################################################################################################
# # def user_training_limit_check(user_id, workspace_id):
# #     try:
# #         result = {
# #                 "current": 0,
# #                 "limit" : USER_TRAINING_LIMIT
# #             }   
# #         if workspace_id is None:
# #             user_training_list = db_user.get_user_training(user_id=user_id, only_owner=True)
# #         else :
# #             user_training_list = db_user.get_user_workspace_training(user_id=user_id, workspace_id=workspace_id, only_owner=True)
        
# #         if user_training_list is None or len(user_training_list) == 0:
# #             result["current"] = 0
# #         else :
# #             result["current"] = len(user_training_list)

# #         result = limit_check(result)
# #         return result
# #     except Exception as e:
# #         traceback.print_exc()

# # def _user_training_limit_check(user_id, workspace_id=None):
# #     try:
# #         if user_id is None:
# #             raise RuntimeError('User ID is None.')
        
# #         check_result = user_training_limit_check(user_id, workspace_id)
# #         return response(status=1, result=check_result)
# #     except Exception as e:
# #         traceback.print_exc()
# #         return response(status=0, message="User training limit check error : {} ".format(str(e)))
# # ####################################################################################################################################
# # ####################################################################################################################################
# # def user_deployment_limit_check(user_id, workspace_id):
# #     try:
# #         result = {
# #                 "current": 0,
# #                 "limit" : USER_DEPLOYMENT_LIMIT
# #             }   
# #         if workspace_id is None:
# #             user_deployment_list = db_user.get_user_deployment(user_id=user_id, only_owner=True)
# #         else :
# #             user_deployment_list = db_user.get_user_workspace_deployment(user_id=user_id, workspace_id=workspace_id, only_owner=True)
        
# #         if user_deployment_list is None or len(user_deployment_list) == 0:
# #             result["current"] = 0
# #         else :
# #             result["current"] = len(user_deployment_list)

# #         result = limit_check(result)
# #         return result
# #     except Exception as e:
# #         traceback.print_exc()

# # def _user_deployment_limit_check(user_id, workspace_id=None):
# #     try:
# #         if user_id is None:
# #             raise RuntimeError('User ID is None.')
        
# #         check_result = user_deployment_limit_check(user_id, workspace_id)
# #         return response(status=1, result=check_result)
# #     except Exception as e:
# #         traceback.print_exc()
# #         return response(status=0, message="User deployment limit check error : {} ".format(str(e)))
# ####################################################################################################################################
# ####################################################################################################################################
# def limit_check(check_result):
#     check_result["generable"] = True
#     if check_result["limit"] is not None:
#         if check_result["current"] <= check_result["limit"]:
#             return check_result
#         else :
#             check_result["generable"] = False
#             return check_result

#     return check_result

# # @ns.route("/limit/docker_image", methods=['GET'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class UserLimitDockerImage(CustomResource):
# #     @token_checker
# #     def get(self):
# #         """Docker Image Limit"""
# #         user_id = self.check_user_id()
# #         res = _user_docker_image_limit_check(user_id=user_id)
# #         return self.send(res)

# # @ns.route("/limit/dataset", methods=['GET'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class UserLimitDataset(CustomResource):
# #     @token_checker
# #     @ns.expect(user_limit_get)
# #     def get(self):
# #         """Dataset Limit"""
# #         args = user_limit_get.parse_args()
# #         workspace_id = args["workspace_id"]
# #         res = _user_dataset_limit_check(user_id=self.check_user_id(), workspace_id=workspace_id)
# #         return self.send(res)

# # @ns.route("/limit/training", methods=['GET'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class UserLimitTraining(CustomResource):
# #     @token_checker
# #     @ns.expect(user_limit_get)
# #     def get(self):
# #         """Training Limit"""
# #         args = user_limit_get.parse_args()
# #         workspace_id = args["workspace_id"]
# #         res = _user_training_limit_check(user_id=self.check_user_id(), workspace_id=workspace_id)
# #         return self.send(res)

# # @ns.route("/limit/deployment", methods=['GET'])
# # @ns.response(200, 'Success')
# # @ns.response(400, 'Validation Error')
# # class UserLimitDeployment(CustomResource):
# #     @token_checker
# #     @ns.expect(user_limit_get)
# #     def get(self):
# #         """Deployment Limit"""
# #         args = user_limit_get.parse_args()
# #         workspace_id = args["workspace_id"]
# #         res = _user_deployment_limit_check(user_id=self.check_user_id(), workspace_id=workspace_id)
# #         return self.send(res)
