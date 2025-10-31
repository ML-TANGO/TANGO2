from fastapi import APIRouter, Depends, Request, Path
from login import service as svc
from login import model
from utils.resource import CustomResource, token_checker
from utils.settings import LOGIN_METHOD

login = APIRouter(
    prefix = "/login"
)

@login.post("", tags=["login"])
async def post_login(parsers: model.LoginModel, request: Request):
    res = svc.login(request=request, parsers=parsers)
    return res

@login.post("/force", tags=["login"])
async def post_login_force(body: model.LoginForceModel):
    user_name = body.user_name
    password = body.password
    token = body.token
    res = svc.login_force(user_name=user_name, password=password, user_token=token)
    return res

@login.post("/session_copy", tags=["login"])
@token_checker
async def post_session_copy():
    res = svc.session_copy(user_name=CustomResource().check_user())
    return res

