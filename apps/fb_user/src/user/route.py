from fastapi import APIRouter, Depends, Request, Path
from user import service as svc
from user import service_group as svc_group
# from user import service_limit as svc_limit

from user import model
from utils.resource import response, get_auth, get_user_id

users = APIRouter(
    prefix = "/users"
)

@users.get("/healthz")
async def healthz():
    return response(status_code=200, result={"status": "healthy"})


@users.get("/login-check")
async def login_check():
    user_id = get_user_id()
    if user_id is None:
        return response(status=0, message="User Not Found")
    else:
        return response(status=1, message="User Found", result={"user_id": user_id})

@users.get("/option")
async def get_user_option():  
    user_name, _ = get_auth()
    res = svc.user_option(headers_user=user_name)
    return res

@users.get("/group/option", tags=["users/group"])
async def get_usergroup_option():
    user_name, _ = get_auth()
    res = svc_group.usergroup_option(headers_user=user_name)
    return res

@users.get("")
async def get_users():
# async def get_users(args: model.UserGetModel = Depends()):
    # search_key = args.search_key
    # size = args.size
    # page = args.page
    # search_value = args.search_value
    res = svc.get_users(search_key=None, size=None, page=None, search_value=None)
    # db.request_logging
    return res

@users.post("")
async def create_users(args: model.UserCreateModel):

    # workspaces_id = args.workspaces_id
    new_user_name = args.new_user_name
    password = args.password
    user_type = args.user_type
    email = args.email
    job = args.job
    nickname = args.nickname
    team = args.team
    usergroup_id = args.usergroup_id

    # create_user_list = [{"new_user_name": new_user_name, "password": password, "workspaces_id": workspaces_id, "user_type": user_type, "usergroup_id": usergroup_id}]

    user_name, _ = get_auth()
    if user_name != "admin":
        return {"status": 0, "message":"Permission Error"}
    
    res = svc.create_user_new(new_user_name=new_user_name, password=password, user_type=user_type,
                              email=email, job=job, nickname=nickname, team=team,
                              usergroup_id=usergroup_id, headers_user=user_name)
    # usergroup_id ???
    # db.request_logging(self.check_user(), 'users', 'post', str(args), res['status'])
    return res

@users.put("")
async def update_user(body: model.UserUpdateModel):
    select_user_id = body.select_user_id
    new_password = body.new_password
    # workspaces_id = body.workspaces_id
    usergroup_id = body.usergroup_id
    #user_type = args['user_type'] #TODO user_type 처리 어떻게? root 비밀번호 변경하면 프론트에서 3 쏴줘서 user로 변함
    email = body.email
    job = body.job
    nickname = body.nickname
    team = body.team

    user_name, _ = get_auth()
    res = svc.update_user_new(select_user_id=select_user_id, new_password=new_password,
                             usergroup_id=usergroup_id, headers_user=user_name,
                             email=email, job=job, nickname=nickname, team=team)

    # db.request_logging(self.check_user(), 'users', 'put', str(args), res['status'])
    # update_user_list = [{"select_user_id": select_user_id, "new_password": new_password, "user_type": user_type, "workspaces_id": workspaces_id}]
    # response = update_user(update_user_list)
    return res
    

# @users.get("/workspaces", description="유저 Workspace List")
# async def get_workspaces(user_id: int):
#     res = svc.get_user_workspaces(user_id=user_id)
#     # db.request_logging(self.check_user(), 'users/workspaces', 'get', str(args), res['status'])
#     return res


@users.put("/password", description="admin Password Update")
async def update_password(body: model.UserPasswordUpdateMode):
    password = body.password
    new_password = body.new_password

    user_name, _ = get_auth()
    res = svc.update_user_password(password=password, new_password=new_password, headers_user=user_name)
    return res

# MSA 전환 주석 -> home ssh key 관련 사용 안하는 것으로 보임

# @users.post("/recover-linux-user")
# async def recoever_linux_user(body: model.UserRecoverLinuxModel):
#     user_ids = body.user_ids.split(',')
#     password = body.password
#     res = svc.recover_linux_user(user_ids, password)
#     return res

# =============================================================================
# users/group
# =============================================================================
# users_group = APIRouter(
#     prefix = "/users/group"
# )

@users.get("/group", tags=["users/group"])
async def get_usergroups():
    
    user_name, _ = get_auth()
    if user_name == "admin":
        # res = svc_group.get_usergroup_list(page=page, size=size, search_key=search_key, search_value=search_value)
        res = svc_group.get_usergroup_list(page=None, size=None, search_key=None, search_value=None)
    else:
        res = response(status=0, message="Permisson Error")
    return res


@users.post("/group", tags=["users/group"])
async def create_usergroup(body: model.UserGroupCreateModel):
    usergroup_name = body.usergroup_name
    user_id_list = body.user_id_list
    description = body.description

    user_name, _ = get_auth()
    if user_name == "admin":
        res = svc_group.create_usergroup(usergroup_name=usergroup_name, user_id_list=user_id_list, description=description)
    else:
        res = response(status=0, message="Permisson Error")
    return res

@users.put("/group", tags=["users/group"])
async def update_usergropus(body: model.UserGroupUpdateModel):
    usergroup_id = body.usergroup_id
    usergroup_name = body.usergroup_name
    user_id_list = body.user_id_list
    description = body.description

    user_name, _ = get_auth()
    if user_name == "admin":
        res = svc_group.update_usergroup(usergroup_id=usergroup_id, usergroup_name=usergroup_name, user_id_list=user_id_list, description=description)
    else:
        res = response(status=0, message="Permisson Error")
    return res


# =============================================================================
# users/register
# =============================================================================

@users.post('/register', tags=['user/register'])
def post_user_register(body: model.UserRegisterModel):
    res = svc.request_user_register(
        name=body.name, password=body.password, nickname=body.nickname,
        job=body.job, email=body.email, team=body.team)
    return res

@users.put('/register', tags=['user/register'])
def put_user_register(body: model.UserRegisterConfirmModel):
    """
    # Input
        status: bool (승인 True, 거절 False)
        register_id: GET /api/users에서 register_id가 내려옴
    """
    res = svc.approve_user_register(register_id=body.register_id, approve=body.approve, usergroup_id=body.usergroup_id)
    return res

# =============================================================================
# users/limit
# =============================================================================
# users_limit = APIRouter(
#     prefix = "/users/limit",
# )

# @users.get("/limit/dataset", tags=["users/limit"])
# async def check_user_dataset(workspace_id: int = None):
#     cr = CustomResource()
#     res = svc_limit._user_dataset_limit_check(user_id=user_id, workspace_id=workspace_id)
#     return res


# @users.get("/limit/deployment", tags=["users/limit"])
# async def check_user_deployment(workspace_id: int = None):
#     cr = CustomResource()
#     res = svc_limit._user_deployment_limit_check(user_id=user_id, workspace_id=workspace_id)
#     return res


# @users.get("/limit/training", tags=["users/limit"])
# async def check_user_training(workspace_id: int = None):
#     cr = CustomResource()
#     res = svc_limit._user_training_limit_check(user_id=user_id, workspace_id=workspace_id)
#     return res


# @users.get("/limit/docker_image", tags=["users/limit"])
# async def check_user_dockerimage(workspace_id: int = None):
#     cr = CustomResource()
#     res = svc_limit._user_docker_image_limit_check(user_id=user_id)
#     return res




# =============================================================================
# path param
# =============================================================================

@users.get("/check/{user_name}")
async def check_user_name(user_name):
    # cr = CustomResource()
    # res = svc.check_user_name(user_name=user_name, headers_user=user_name)
    res = svc.check_user_name(user_name=user_name)
    # db.request_logging(self.check_user(), 'users/check/'+str(user_name), 'get', None, res['status'])
    return res


# MSA user private key
# @users.get("/getpk/{user_name}")
# async def get_private_key_user(user_name):
#   return send_file('/home/' + user_name +'/.ssh/' + user_name)


@users.get("/group/{usergroup_id}", tags=["users/group"])
async def get_usergroup(usergroup_id: int):
    user_name, _ = get_auth()
    if user_name == "admin":
        res = svc_group.get_usergroup(usergroup_id=usergroup_id)
    else:
        res = response(status=0, message="Permisson Error")
    return res


@users.delete("/group/{id_list}", tags=["users/group"])
async def delete_usergroups(id_list: str):
    id_list = id_list.split(',')
    
    user_name, _ = get_auth()
    if user_name == "admin":
        res = svc_group.delete_usergroup(usergroup_id_list=id_list)
    else:
        res = response(status=0, message="Permisson Error")
    return res


@users.get('/register/{register_id}', tags=['user/register'])
def get_user_register(register_id: int):
    """
    # Input
        status: bool (승인 True, 거절 False)
        register_id: GET /api/users에서 register_id가 내려옴
    """
    res = svc.get_user_register(register_id=register_id)
    return res


@users.get("/{user_id}", description="유저 ID 단순 조회")
async def get_user(user_id):
    res = svc.get_user(user_id=user_id)
    # db.request_logging(self.check_user(), 'users/'+str(user_id), 'get', None, res['status'])
    return res


@users.delete("/{id_list}")
async def delete_users(id_list):
    id_list = id_list.split(',')

    user_name, _ = get_auth()
    if user_name != "admin":
        return {"status": 0, "message":"Permission Error"}
    
    res = svc.delete_users(id_list=id_list, headers_user=user_name)
    # db.request_logging(self.check_user(), 'users/'+str(id_list), 'delete', None, res['status'])
    return res