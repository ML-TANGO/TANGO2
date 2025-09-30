from fastapi import APIRouter, Depends, Request, Path
from pydantic import BaseModel
from utils.resource import CustomResource, response, token_checker
from utils.settings import LOGIN_METHOD
from utils.msa_db import db_user
# import utils.db as db

logout = APIRouter(
    prefix = "/logout"
)

# class LogoutModel(BaseModel):
#     user_name: str
#     password: str

def svc_logout(user_id, token):
    # delete login_session
    db_user.delete_login_session(user_id=user_id)
    return response(status=1, message="success", logout=True)

@logout.post("", tags=["logout"])
@token_checker
async def post_logout():
    cr = CustomResource()
    res = svc_logout(user_id=cr.check_user_id(), token=cr.check_token())
    # log_access({'username':request.headers.get('Jf-User'), 'header':dict(request.headers), 'ret':ret})
    return res