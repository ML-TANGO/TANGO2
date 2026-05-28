from utils.resource import response #, token_checker
from utils.crypt import session_cipher, front_cipher
import utils.crypt as crypt

import utils.msa_db.db_user as db_user
import time, traceback, datetime
import requests, sys

from utils.settings import MAX_NUM_OF_LOGINS, LOGIN_METHOD, LOGIN_VALIDATION_CHECK_API, PASSWORD_KEY, JF_INGRESS_MANAGEMENT_DNS

# JWT 생성 및 검증 관련 설정
SECRET_KEY = "your-secret-key"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 15

if LOGIN_METHOD == "jfb":
    def login_valid_check(**kwargs):
        user_name = kwargs.get("user_name")
        if db_user.get_user_register(user_name=user_name) is not None:
            return False, response(status=0, message="Waiting for admin approval. Try logging in again later.")
        
        password_check_result, message = password_check(**kwargs)
        if password_check_result == False:
            return False, message
        
        return True, ""

# =================================================================================================================================
# =================================================================================================================================

def password_check(user_name, password, **kwargs):
    import crypt
    password = front_cipher.decrypt(password)
    enc_pw = crypt.crypt(password, PASSWORD_KEY)
    user_info = db_user.get_user(user_name=user_name)
    if not user_info:
        return False, response(status=0, message="Please retry login with correct ID and password.")
    
    if user_info["password"] != enc_pw:
    # if linux_login_check(user_name, password) == False:
        
        login_warn=""
        if user_info is not None:
            # login counting
            if user_info["login_counting"] >= 2:
                login_warn = "(Retrials : {} times / Remaining retrials : {} times)".format(user_info["login_counting"]+1, MAX_NUM_OF_LOGINS-(user_info["login_counting"]+1))
            if user_info["login_counting"]+1 >= MAX_NUM_OF_LOGINS:
                update_result, message = db_user.update_user_login_counitng(user_id=user_info["id"])
                return False, response(status=0, message="ID {} locked.".format(user_name), locked=True)

            update_result, message = db_user.update_user_login_counitng(user_id=user_info["id"])
            login_counting = user_info["login_counting"] + 1
            if not update_result:
                print("Login db error log : ",message)
                #return response(status=0, message="Please retry login with correct ID and password. : {}".format(message), login_counting=login_counting)
        return False, response(status=0, message="Please retry login with correct ID and password.\n{}".format(login_warn))

    return True, ""

"""
2025-02-19~ Luke 작업중
- msa_jfb 에서 login_session Table 을 사용하지 않고, kong 에서 제공하는 session을 사용하도록 변경 (DB에서 관리할 필요 없음)
"""
def login(request, parsers):
    try:
        kwargs = parsers.dict()
        valid_check_result, message = login_valid_check(**kwargs)
        if valid_check_result == False:
            return message
            
        user_name = kwargs["user_name"]
        user_info = db_user.login(user_name)
        
        if user_info is not None:
            result = {
                        "user_name": user_name, 
                        "admin": True if user_name == 'admin' else False,
                        "logined": False
                    }

            user_id = user_info["id"]

            if user_info["login_counting"] >= MAX_NUM_OF_LOGINS:
                return response(status=0, message="ID {} locked.".format(user_name), locked=True)

            db_user.update_user_login_counitng(user_id=user_id, set_default=True)
            
            ################################################
            # 중복로그인 차단하는 기능 기획시 이 부분에서 처리
            # - 중복로그인 확인은 기존처럼 DB에서 Token 대신 Session 값을 넣어 확인하면 될 것 같음
            ################################################
            # login_result, message = db_user.get_login_session(user_id=user_id)
            # if login_result is not None:
            #     # MSA 변경 -> 로그인 세션을 삭제
            #     db_user.delete_login_session(user_id=user_id)
            #     # already logined
            #     result["logined"] = True
            #     ret = response(status=1, result=result, logined=True)
            #     # MSA 전환
            #     return ret

            # 세션 요청
            url=f"http://{JF_INGRESS_MANAGEMENT_DNS}/api/ingress/auth"
            cookie_res = requests.post(url=url, json={"username": user_name}, headers={"Content-Type": "application/json"})
            # print("cookie_res: ", cookie_res.text, file=sys.stderr)
            cookie_res = cookie_res.json()
            
            if not cookie_res["result"]:
                # return response(status=1, result=result, status_code=200)
                return response(status=0, result=result, message="Session cookie create error.", status_code=500)
            
            res = response(status=1, result=result, status_code=200)
            res.headers.append("Set-Cookie", cookie_res["result"])
            # print(f"headers: {res.headers}")
            return res
        else:
            return response(status=0, message="Please retry login with correct ID and password.", status_code=401)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Login Error")

def session_check(request):
    headers = request.headers
    x_consumer_username = headers.get('x-consumer-username')
    cookie = headers.get('cookie')
    return {"x-consumer-username": x_consumer_username, "cookie": cookie}
    
def test(request):
    headers = request.headers
    x_consumer_username = headers.get('x-consumer-username')
    cookie = headers.get('cookie')
    return {"x-consumer-username": x_consumer_username, "cookie": cookie}
# def login(request, parsers):
#     try:
#         kwargs = parsers.dict()
#         valid_check_result, message = login_valid_check(**kwargs)
#         if valid_check_result == False:
#             return message
        
#         jp_user_info = None
            
#         user_name = kwargs["user_name"]
#         user_info = db_user.login(user_name)
        
#         if user_info is not None:
#             result = {"user_name": user_name, "token": None, "logined_session": None,
#                     "admin": True if user_name == 'admin' else False, "logined": False}

#             # gen token
#             token = crypt.gen_user_token(user_name, 0)
#             result["token"] = token
#             user_id = user_info["id"]

#             if user_info["login_counting"] >= MAX_NUM_OF_LOGINS:
#                 return response(status=0, message="ID {} locked.".format(user_name), locked=True)
            
#             # check user login
#             login_result, message = db_user.get_login_session(user_id=user_id)

#             if login_result is not None:
#                 # MSA 변경 -> 로그인 세션을 삭제
#                 db_user.delete_login_session(user_id=user_id)

#                 # # already logined
#                 # result["logined"] = True
#                 # ret = response(status=1, result=result, login=True)
#                 # # MSA 전환
#                 # return ret

#             print("insert_login_session")
#             insert_result, message = db_user.insert_login_session(user_id=user_id, token=token)
#             if not insert_result:
#                 return response(status=0, message="Login session error")
#             result["logined_session"] = db_user.get_login_session(token=token)[0]["id"]
#             db_user.update_user_login_counitng(user_id=user_id, set_default=True)
#             ret = response(status=1, result=result, login=True)
#             # MSA 전환

#             return ret
#         else:
#             return response(status=0, message="Please retry login with correct ID and password.")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Login Error")

# """
#  Luke Notes:
#  2024-11-28
#  - logined_session : db에서 컬럼의 id를 session_id로 사용
#  - logined : 기존에 로그인했나 확인하기 위한 것 -> 이 값을 통해 기존 로그인된 세션을 로그아웃시키겠냐는 버튼을 활성화함 (token_checker 사용하지 않으면 현재는 중복 로그인이 되도록 허용된 상태임. 기획적으로 브라우저 범위 내에서 중복로그인 허용하자 였던 것 같은데, 추후 프론트엔드와 논의 필요.)
#  - https://aaai.atlassian.net/wiki/spaces/A/pages/86769698 에 정리중
# """
# def login_jwt(request, parsers):    
    
#     try:
#         kwargs = parsers.dict()
#         valid_check_result, message = login_valid_check(**kwargs)
#         if valid_check_result == False:
#             return message
            
#         user_name = kwargs["user_name"]
#         user_info = db_user.login(user_name)

#         if user_info is not None:
#             result = {
#                 "user_name": user_name,
#                 "token": None,
#                 "logined_session": None,
#                 "admin": True if user_name == 'admin' else False,
#                 "logined": False
#             }

#             user_id = user_info["id"]
#             if user_info["login_counting"] >= MAX_NUM_OF_LOGINS:
#                 return response(status=0, message="ID {} locked.".format(user_name), locked=True, status_code=401)
            
#             # check user login
#             login_result, message = db_user.get_login_session(user_id=user_id)
#             if login_result is not None:
#                 # MSA 변경 -> 로그인 세션을 삭제
#                 db_user.delete_login_session(user_id=user_id)

#             # Token
#             ic.kong_create_consumer(user_name)
#             credentials = ic.kong_create_jwt_credential(user_name, SECRET_KEY, JWT_ALGORITHM)
#             payload = {
#                 "iss": credentials["key"],
#                 "sub": user_name,
#                 "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=JWT_EXPIRATION_MINUTES),
#             }
#             token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
#             result["token"] = token

#             # insert login session
#             insert_result, message = db_user.insert_login_session(user_id=user_id, token=token)
#             if not insert_result:
#                 return response(status=0, message="Login session error")
#             result["logined_session"] = db_user.get_login_session(token=token)[0]["id"]
#             db_user.update_user_login_counitng(user_id=user_id, set_default=True)

            
#             return response(status=1, result=result, login=True, status_code=200)
            
#         else:
#             return response(status=0, message="Please retry login with correct ID and password.", status_code=401)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Login Error", status_code=401)


def login_force(user_name, password, user_token):
    try:
        # if password_check(user_name, password) == False:
        #     # exist user check
        #     user_info = db.get_user(user_name=user_name)
        #     if user_info is not None:
        #         # login counting
        #         update_result, message = db.update_user_login_counitng(user_id=user_info["id"])
        #         login_counting = user_info["login_counting"] + 1
        #         if not update_result:
        #             return response(status=0, message="Please retry login with correct ID and password.", login_counting=login_counting)
        #             #return response(status=0, message="Please retry login with correct ID and password. : {}".format(message), login_counting=login_counting)
        
        token_user, start_timestamp, gen_count = crypt.decrypt_user_token(user_token)
        cur_timestamp = time.time()
        if not (token_user == user_name and gen_count == 0):  
            return response(status=0, message="Login error : invalid token for {}".format(user_name))
        if not (cur_timestamp - start_timestamp) < 60:
            return response(status=0, message="Login error : expired token")

        user_token = crypt.gen_user_token(user_name, 0)

        result = {"user_name": user_name, "token": user_token, "logined_session": None,
                "admin": True if user_name == 'admin' else False, "logined": False}
        
        # if LOGIN_METHOD == "jonathan":
        #     jp_user_info = get_user_info_with_jp_token(request)
        #     if jp_user_info is not None:
        #         if jp_user_info["photo_url"] is not None:
        #             result['photo_url'] = jp_user_info["photo_url"]
        #         if jp_user_info["name"] is not None:
        #             result['jp_user_name'] = jp_user_info["name"]

        user_id = db_user.get_user(user_name=user_name)["id"]
        db_user.delete_login_session(user_id=user_id)
        insert_result, message = db_user.insert_login_session(user_id=user_id, token=user_token)
        result["logined_session"] = db_user.get_login_session(token=user_token)[0]["id"]
        if not insert_result:
            return response(status=0, message="Login session error", login_counting=login_counting)
            #return response(status=0, message="Login session error : {}".format(message), login_counting=login_counting)
        db_user.update_user_login_counitng(user_id=user_id, set_default=True)
        return response(status=1, result=result, login=True)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Login Force Error")
        #return response(status=0, message="Login Force Error: {}".format(str(e)))

def session_copy(user_name):
    try:
        user_token = crypt.gen_user_token(user_name, 0)
        user_id = db_user.get_user(user_name=user_name)["id"]
        insert_result, message = db_user.insert_login_session(user_id=user_id, token=user_token)
        print("session_copy : ", insert_result, message)

        result = {"user_name": user_name, "token": user_token, "logined_session": None,
                "admin": True if user_name == 'admin' else False}
        result["logined_session"] = db_user.get_login_session(token=user_token)[0]["id"]
        return response(status=1, result=result, login=True)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Session copy error : {}".format(e))