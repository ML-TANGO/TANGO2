# #####################################################################################################
# ####################################### 템플릿 기능 제거 #############################################
# #####################################################################################################

# from fastapi import APIRouter, Depends
# from utils.resource import CustomResource, response, token_checker
# from utils.exceptions import CustomErrorList
# import traceback
# import logging

# from deployment import model
# from deployment_template import service as svc

# class GetTemplateListModel(BaseModel):
#     workspace_id: int = Field(description='workspace id')
#     deployment_template_group_id: Optional[int] = Field(default=None, description='deployment template group id')
#     is_ungrouped_template: Optional[int] = Field(default=0, description='ungrouped=1')
    
# class CreateTemplateGroupModel(BaseModel):
#     workspace_id: int = Field(description='Workspace id')
#     deployment_template_group_name: str = Field(description='Deployment Template Group Name' )
#     deployment_template_group_description: Optional[str] = Field(default=None, description='Deployment Template Group Description' )

# class CreateTemplateModel(BaseModel):
#     workspace_id: int = Field(description='workspace id')
#     deployment_template_id: Optional[int] = Field(description='Deployment Template id')
#     deployment_template_name: str = Field(description='Deployment Template Name' )
#     deployment_template_description: Optional[str] = Field(default=None, description='Deployment Template Description' )
#     deployment_template_group_id: Optional[int] = Field(description='Deployment Template Group id')
#     deployment_template_group_name: Optional[str] = Field(description='Deployment Template Group Name' )
#     deployment_template_group_description: Optional[str] = Field(default=None, description='Deployment Template JSON' )
#     deployment_template: Optional[dict] = Field(default=None, description='Deployment Template JSON String' )
#     deployment_type: Optional[str] = Field(description='deployment type : {}'.format(DEPLOYMENT_TYPES))
#     training_id: Optional[int] = Field(default=None, description='training_id = training model (id)')
#     training_type: Optional[str] = Field(default=None, description='training type = job / hps' )
#     job_id: Optional[int] = Field(default=None, description='job_id')
#     hps_id: Optional[int] = Field(default=None, description='hps_id')
#     hps_number: Optional[int] = Field(default=None, description='hps_number')
#     checkpoint: Optional[str] = Field(default=None, description='checkpoint = job_name/grop_index/checkpoint (name)')
#     command: Optional[dict] = Field(default=None, description='command = {"binary":"python", "script":"/jf-training-home/src/get_api.py", "arguments":"--a aa --b bb -c"}')
#     environments: Optional[list] = Field(default=None, description='environments = [{"name":"FLASK_APP","value":"app"},{"name":"FLASK_ENV","value":"development"}]')
#     built_in_model_id: Optional[int] = Field(default=None, description='For default built-in')

# class UpdateTemplateModel(BaseModel):
#     workspace_id: int = Field(description='workspace id')
#     deployment_template_id: int = Field(description='deployment template id')
#     deployment_template_name: Optional[str] = Field(description='Deployment Template Name' )
#     deployment_template_description: Optional[str] = Field(default=None, description='Deployment Template Description' )
#     deployment_template_group_id: Optional[int] = Field(description='Deployment Template Group id')
#     deployment_template_group_name: Optional[str] = Field(description='Deployment Template Group Name' )
#     deployment_template_group_description: Optional[str] = Field(default=None, description='Deployment Template Group Description' )
    
# class UpdateTemplateGroupModel(BaseModel):
#     workspace_id: int = Field(description='Workspace id')
#     deployment_template_group_name: str = Field(description='Deployment Template Group Name' )
#     deployment_template_group_id: int = Field(description='Deployment Template Group id')
#     deployment_template_group_description: Optional[str] = Field(default=None, description='Deployment Template Group Description' )

# class DeploymentTemplateListModel(BaseModel):
#     workspace_id : Optional[int] = Field(description='Workspace id', type=int)
#     deployment_template_group_id : Optional[int] = Field(default=None, description='deployment template group id', type=int)
#     is_ungrouped_template : Optional[int] = Field(default=0, description='ungrouped=1', type=int)
    
# class DeploymentTemplateGroupModel(BaseModel):
#     workspace_id : Optional[int] = Field(description='Workspace id', type=int)


# from utils.access_check import deployment_access_check, workspace_access_check

# deployments_template = APIRouter(
#     prefix = "/deployments/template"
# )

# @deployments_template.get("")
# @token_checker
# @workspace_access_check()
# async def get_deployment_template(workspace_id: int, deployment_template_id: int):
#     res = svc.get_deployment_template(workspace_id=workspace_id, deployment_template_id=deployment_template_id)#, headers_user=self.check_user_id())
#     return res

# @deployments_template.post("")
# @token_checker
# async def post_deployment_template(body: model.CreateTemplateModel):
#     """
#         Deployment Template 생성
#         ---
#         # inputs
#             workspace_id (int)
#             deployment_template_name (str) - 배포 템플릿 이름
#             deployment_template_description (str) - 배포 템플릿 설명
#             deployment_template_group_id (int) - 배포 템플릿 그룹 ID
#                 * 그룹 선택하는 경우: 그룹 ID
#                 * 그룹 선택 안하는 경우: None
#             deployment_template_group_name (str) - 배포 템플릿 그룹 이름
#                 * 그룹 생성하는 경우: 그룹 이름
#                 * 그룹 생성 안하는 경우: None
#             deployment_template_group_description (str) - 배포 템플릿 그룹 설명
#             deployment_template(dict)
#                 * 배포유형 '설정값 직접 입력하기': json 값
#                 * 배포유형 나머지: None
#             deployment_template_id (int)
#                 * 배포유형 '템플릿 사용하기'
#                     * 값이 그대로: deployment_template_id
#                     * 값이 변함: None
#                 * 배포유형 나머지: None
#             deployment_type (str) - custom / built-in
#                 * 배포유형 Built-in 모델 사용하기: built-in
#                 * 배포유형 학습에서 가져오기:
#                     * training_type built_in 선택: built-in
#                     * training_type custom 선택: custom
#                 * 배포유형 나머지: None
#             training_id (int)
#                 * 배포유형 학습에서 가져오기: training id 값
#                 * 배포유형 나머지: None
#             training_type (str)
#                 * 배포유형 Built-in 모델 사용하기: None
#                 * 배포유형 학습에서 가져오기:
#                     * training_type built_in 선택: job / hps
#                     * training_type custom 선택: None
#             job_id (int)
#                 * training_type 이 job 일때만
#             hps_id (int)
#                 * training_type 이 hps 일때만
#             hps_number (int)
#                 * training_type 이 hps 일때만
#             command (dict)
#                 * deployment_type 이 built-in: None
#                 * deployment_type 이 custom: 
#                     * dict {"binary":"python", "script":"/jf-training-home/src/get_api.py", "arguments":"--a aa --b bb -c"}
#             environments (list)
#                 * deployment_type 이 built-in: None
#                 * deployment_type 이 custom: 
#                     * list [{"name":"FLASK_APP":"value":"app"}, {"name":"FLASK_ENV","value":"development"}]
#             checkpoint (str)
#                 * deployment_type 이 built-in: checkpoint
#                     * 00-0.68.json
#                 * deployment_type 이 custom: None
#             built_in_model_id (int)
#                 * deployment_type 이 built-in: built in model id
#                 * deployment_type 이 custom: None
#         ---
#         # returns

#             status (int): 0(실패), 1(성공)
#             message (str): API로 부터 담기는 메세지

#     """
#     try:
#         cr = CustomResource()
#         res = svc.create_deployment_template(workspace_id=body.workspace_id, deployment_template_id=body.deployment_template_id,
#                                     deployment_template_name=body.deployment_template_name, 
#                                     deployment_template_description=body.deployment_template_description, 
#                                     deployment_template_group_id=body.deployment_template_group_id, 
#                                     deployment_template_group_name=body.deployment_template_group_name, 
#                                     deployment_template_group_description=body.deployment_template_group_description,
#                                     deployment_template = body.deployment_template,
#                                     deployment_type=body.deployment_type, training_id=body.training_id, training_type=body.training_type, 
#                                     job_id=body.job_id, hps_id=body.hps_id, hps_number=body.hps_number, checkpoint=body.checkpoint, command=body.command, 
#                                     environments=body.environments, built_in_model_id=body.built_in_model_id, 
#                                     headers_user=cr.check_user_id())
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# @deployments_template.put("")
# @token_checker
# async def put_deployment_template(body: model.UpdateTemplateModel):
#     """
#         Deployment Template 수정
#         ---
#         # inputs
#             workspace_id (int)
#             deployment_template_id (int) - 배포 템플릿 ID
#             deployment_template_name (str) - 배포 템플릿 이름
#             deployment_template_description (str) - 배포 템플릿 설명
#             deployment_template_group_id (str) - 배포 템플릿 그룹 ID
#                 * 그룹 선택한 안한경우 - None
#             deployment_template_group_name (str) - 배포 템플릿 그룹 이름
#                 * 그룹 선택한 안한경우 - None
#             deployment_template_group_description (str) - 배포 템플릿 그룹 설명
#                 * 그룹 선택한 안한경우 - None
#         ---
#         # returns

#             status (int): 0(실패), 1(성공)
#             message (str): API로 부터 담기는 메세지

#     """
#     try:
#         cr = CustomResource()
#         res = svc.update_deployment_template(workspace_id=body.workspace_id, 
#                                     deployment_template_id=body.deployment_template_id,
#                                     deployment_template_name=body.deployment_template_name, 
#                                     deployment_template_description=body.deployment_template_description, 
#                                     deployment_template_group_id=body.deployment_template_group_id,
#                                     deployment_template_group_name=body.deployment_template_group_name, 
#                                     deployment_template_group_description=body.deployment_template_group_description, 
#                                     headers_user=cr.check_user_id())
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# @deployments_template.get("-list", description="Deployment Template 리스트 조회")
# @token_checker
# @workspace_access_check()
# async def get_template_list(args: model.GetTemplateListModel = Depends()):
#     cr = CustomResource()
#     res = svc.get_deployment_template_list(workspace_id=args.workspace_id, 
#                                     deployment_template_group_id=args.deployment_template_group_id,
#                                     is_ungrouped_template=args.is_ungrouped_template,
#                                     headers_user=cr.check_user_id())
#     return res

# @deployments_template.get("-group-list", description="Deployment Template Group 리스트 조회")
# @token_checker
# @workspace_access_check()
# async def get_template_group_list(workspace_id: int):
#     cr = CustomResource()
#     res = svc.get_deployment_template_group_list(workspace_id=workspace_id, headers_user=cr.check_user_id())
#     return res

# @deployments_template.post("-group", description="Deployment Template Group 생성")
# @token_checker
# async def post_deployment_template_group(body: model.CreateTemplateGroupModel):
#     try:
#         cr = CustomResource()
#         res = svc.create_deployment_template_group(workspace_id=body.workspace_id, 
#                                     deployment_template_group_name=body.deployment_template_group_name, 
#                                     deployment_template_group_description=body.deployment_template_group_description, 
#                                     headers_user=cr.check_user_id())
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# @deployments_template.put("-group", description="Deployment Template Group 수정")
# @token_checker
# async def put_deployment_template_group(body: model.UpdateTemplateGroupModel):
#     try:
#         cr = CustomResource()
#         res = svc.update_deployment_template_group(workspace_id=body.workspace_id, 
#                                     deployment_template_group_id=body.deployment_template_group_id,
#                                     deployment_template_group_name=body.deployment_template_group_name, 
#                                     deployment_template_group_description=body.deployment_template_group_description, 
#                                     headers_user=cr.check_user_id())
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# @deployments_template.get("-deployment-worker")
# @token_checker
# async def get_deployment_and_worker_by_template(template_id: int):
#     """
#         배포 템플릿을 사용하고 있는 배포/워커들 리스트 조회
#         ---
#         # inputs
#             workspace_id (int)

#     Returns:
#         : _description_
#     """
#     res = svc.get_deployment_and_worker_by_template(template_id)
#     return res

# @deployments_template.delete("-group/{id_list}", description="Deployment Template Group 삭제")
# @token_checker
# async def delete_deployment_template_group(id_list: str):
#     try:
#         deployment_template_group_ids = id_list.split(",")
#         cr = CustomResource()
#         res = svc.delete_deployment_template_group(
#             deployment_template_group_ids=deployment_template_group_ids, headers_user=cr.check_user_id())
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message=e)

# @deployments_template.delete("/{id_list}", description="배포 템플릿 삭제")
# @token_checker
# @workspace_access_check()
# async def delete_deployment_template(id_list: str):
#     deployment_template_ids = id_list.split(",")
#     cr = CustomResource()
#     res = svc.delete_deployment_template(deployment_template_ids=deployment_template_ids, headers_user=cr.check_user_id())
#     return res


# ============================================================================================
# template 주석
# ============================================================================================
# @deployments.get("/template-list")
# @token_checker
# async def deployment_template_list(args : model.DeploymentTemplateListModel = Depends()):
#     cr = CustomResource()
#     workspace_id = args.workspace_id
#     deployment_template_group_id = args.deployment_template_group_id
#     is_ungrouped_template = args.is_ungrouped_template

#     res = svc_template.get_deployment_template_list(workspace_id=workspace_id, 
#                                     deployment_template_group_id=deployment_template_group_id,
#                                     is_ungrouped_template=is_ungrouped_template,
#                                     headers_user=cr.check_user_id())
#     return res

# @deployments.get("/template-group-list")
# @token_checker
# async def deployment_template_list(args : model.DeploymentTemplateGroupModel = Depends()):
#     cr = CustomResource()
#     workspace_id = args.workspace_id
#     res = svc_template.get_deployment_template_group_list(workspace_id=workspace_id, headers_user=cr.check_user_id())
#     return res