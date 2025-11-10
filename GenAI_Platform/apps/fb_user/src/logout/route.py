from fastapi import APIRouter, Request, Response, Depends
from utils.resource import response, get_auth, get_user_id
from utils.msa_db import db_user

logout = APIRouter(prefix="/logout")

def svc_logout(user_id, token):
    # 로그인 세션 삭제
    db_user.delete_login_session(user_id=user_id)
    return response(status=1, message="success", logout=True, status_code=200)

@logout.post("", tags=["logout"])
async def post_logout(request: Request):
    res = response(status=1, message="success", logout=True, status_code=200)

    try:
        _, session = get_auth()
        user_id = get_user_id()
        
        # 세션 삭제 로직 실행
        res = svc_logout(user_id=user_id, token=session)
    except Exception as e:
        print(f"Error: {e}")
    
    # 🟢 쿠키 삭제 (Set-Cookie 헤더를 설정하여 만료 처리)
    res.delete_cookie(
        key="session",
        path="/",  # 설정한 path와 동일해야 함
    )

    return res