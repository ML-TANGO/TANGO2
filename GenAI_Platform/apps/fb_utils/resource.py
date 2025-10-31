from fastapi import FastAPI, HTTPException #, Request, ResponseResponse
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.datastructures import MutableHeaders
from starlette.background import BackgroundTask
from starlette_context import plugins
from starlette_context.plugins import Plugin
from starlette_context.middleware import RawContextMiddleware, ContextMiddleware
from starlette_context.errors import MiddleWareValidationError
from starlette_context import context
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional, Any, Union, Mapping
from datetime import date, datetime, timedelta
import logging
import traceback
import time
import functools
import json
json_encode = json.JSONEncoder().encode

from utils import settings
from utils import common
from utils.crypt import session_cipher
from utils.msa_db import db_user
# # import utils.db as db
import utils.crypt as crypt


# =================================
# Response
# =================================
# https://github.com/tiangolo/fastapi/blob/master/fastapi/applications.py
# https://github.com/encode/starlette/blob/master/starlette/responses.py


def response(**kwargs):
    """
    **kwargs(all):
        status : 1 (정상), 0 (비정상)
        message : front에 보여질 메세지
        result : 실제 데이터
        self_response(ex flask - make_response, send_from_directory): 파일 다운로드와 같이 자체 response를 쓰게 되는 경우에는 self_response 라는 key에 담아서 전달
    """
    params = ['status', 'message', 'result']
    for param in params:
        if param not in kwargs.keys():
            kwargs[param] = None

    return kwargs

# TODO 다양한 response 처리 할 수 있도록 CustomeResponse 에서 추가 개발 필요
class CustomResponse(Response):
    media_type="application/json"

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Mapping[str, str]] = None,
        media_type: Optional[str] = None,
        background: Optional[BackgroundTask] = None
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.background = background
        self.body = self.render(json_encode(content))
        self.init_headers(headers)

    @property
    def headers(self) -> MutableHeaders:

        if not hasattr(self, "_headers"):
            self._headers = MutableHeaders(raw=self.raw_headers)

        self._headers['Access-Control-Allow-Origin'] = '*'
        self._headers['Access-Control-Allow-Headers'] = '*'
        self._headers['Access-Control-Allow-Credentials'] = 'true' # True
        self._headers["Access-Control-Expose-Headers"] = '*'
        self._headers["JF-Response"] = "True"

        return self._headers

# =================================
# token_checkers
# =================================
# msa 수정: return 에서 await 추가, send 삭제

always_check_func_list = ["RemoveNode.get", "AddNode.get"]
def check_func(func_str):
    for check_func in always_check_func_list:
        if check_func in func_str:
            return True
    return False

def def_token_checker(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):

        # MSA 중복로그인 불가
        # is_check_func = check_func(str(f))
        # if settings.NO_TOKEN_VALIDATION_CHECK == True and not is_check_func:
        #     print("token_checker: no token validation check")
        #     return await f(*args, **kwargs)

        # token
        TOKEN_EXPIRED_TIME = 60000000 # settings.TOKEN_EXPIRED_TIME
        TOKEN_UPDATE_TIME = 60000000 # settings.TOKEN_UPDATE_TIME #TOKEN_EXPIRED_TIME + 3600
        TOKEN_VALIDATE_TIME = 2

        # response
        result = {"status": None, "message": None}
        fail_response = { "status": 0, "expired": True }
        header_token = ""

        try:
            # headers - JF
            headers = context["headers"]
            header_user = headers.get('JF-User')
            header_token = headers.get('Jf-Token')
            header_session = headers.get('Jf-Session')

            # jonathan (포털 설정)
            if settings.LOGIN_METHOD == "jonathan":
                return {"message" : "token_checker - jonathan 부분 수정해야됨 (msa 전환)"}
                # ===================================
                # marker_pass = False
                # marker_check_func_list = ["LoginSessionCopy.post", "Built_in_model_Annotation_LIST.get", "Built_in_model_LIST.get", "Datasets_auto_labeling", "SessionUpdate"]
                # for marker_func in marker_check_func_list:
                #     if marker_func in str(f):
                #         marker_pass = True

                # if marker_pass:
                #     pass
                # elif header_user in ["root", "lyla", "daehan-acriil", "yeobie", "edgar", "daehan", "will", "robert", "irene", "jake", "jason","lico"]: # root 는 통합 토큰 체크 안함
                #     return f(*args, **kwargs)
                # else:
                #     if not is_jonathan_token_valid(request):
                #         return fail_response
                # ===================================

            # Master Token Free pass
            if header_user is None or header_token is None:
                fail_response["message"] = "Header not exist"
                return fail_response
            elif header_user in ["admin", "daniel", "klod","jake","wyatt","min","luke","owen","david","aaron"]: # root 는 통합 토큰 체크 안함
                return f(*args, **kwargs)
            elif header_user == "login" and header_token == "login":
                print("Login Step")
                result =  {"status": True, "login": True}
                return fail_response

            # token check
            token_user, start_timestamp, gen_count = session_cipher.decrypt(header_token).split("/")
            if header_user != token_user:
                print("Header data is invalid")
                fail_response["message"] = "Header data invalid"
                return fail_response

            db_user_info = db_user.get_user(user_name=header_user)
            if header_user != db_user_info["name"]:
                print("Token data is invalid")
                fail_response["message"] = "Token data invalid"
                return fail_response

            session_info, message = db_user.get_login_session(session_id=header_session)
            if session_info is None:
                fail_response["message"] = "Not logined"
                return fail_response

            # print("HEADER ", header_token, int(time.time()) - int(float(start_timestamp)))
            session_token_user, session_start_timestamp, session_gen_count = session_cipher.decrypt(session_info["token"]).split("/")
            last_call_timestamp = common.date_str_to_timestamp(session_info["last_call_datetime"])


            if header_token != session_info["token"]:
                valid_time = int(time.time()) - int(float(start_timestamp)) < TOKEN_VALIDATE_TIME
                expired_time = int(time.time()) - int(float(start_timestamp)) < TOKEN_EXPIRED_TIME
                valid_gen_count_op1 = int(session_gen_count) - int(gen_count) < 2
                valid_gen_count_op2 = int(session_gen_count) >= int(gen_count)
                if valid_time:
                    print("Already Updated Token But still valid")
                    return f(*args, **kwargs)
                elif not valid_time and (valid_gen_count_op1 and valid_gen_count_op2) and expired_time:
                    print("Already Updated Token But still valid2")
                    return f(*args, **kwargs)
                else :
                    fail_response["message"] =  "Changed Token or Logouted by other login"
                    return fail_response

            if int(time.time()) - int(last_call_timestamp) > TOKEN_EXPIRED_TIME:
                db_user.delete_login_session(header_token, db_user_info["id"])
                fail_response["message"] =  "Expired Token "
                return fail_response

            # print("ST " , int(start_timestamp), (time.time()))

            last_call_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            if int(time.time()) - int(float(start_timestamp)) > TOKEN_UPDATE_TIME: # and not is_check_func:
                # #Token Update - OLD
                # print("UPDATE TOKEN !!!")
                # #TODO 갱신 안정화 필요 (token 날렸는데 업데이트 안하는 경우 발생 (프론트의 비동기? 때문?),
                # #TODO 토큰에 추가 정보가 필요할 수 있음(몇번 째 콜 횟수 라던가)
                # #TODO TOKEN UPDATE 시 Header를 통할 수 있도록 (2022-01-20 다운로드 시 업데이트 되면 문제..)
                # new_token = crypt.gen_user_token(header_user, int(gen_count)+1)
                # db_user.update_login_session_token(old_token=header_token, new_token=new_token)
                # header_token = new_token
                # result["token"] = new_token
                # f_Response = f(*args, **kwargs)
                # return response_item_add(f_Response, {"token": new_token})
                #Token Update
                print("UPDATE TOKEN !!!")
                #TODO 갱신 안정화 필요 (token 날렸는데 업데이트 안하는 경우 발생 (프론트의 비동기? 때문?),
                #TODO 토큰에 추가 정보가 필요할 수 있음(몇번 째 콜 횟수 라던가)
                #TODO TOKEN UPDATE 시 Header를 통할 수 있도록 (2022-01-20 다운로드 시 업데이트 되면 문제..)
                new_token = crypt.gen_user_token(header_user, int(gen_count)+1)
                result["token"] = new_token
                f_Response = f(*args, **kwargs)
                result, message = db_user.update_login_session_token(old_token=header_token, new_token=new_token)
                if result == False:
                    return f_Response
                print("UPDATED TOKEN @@@")
                # MSA 전환
                # return response_item_add(f_Response, {"token": new_token})
                return CustomResponse(content=f_Response, headers={"token": new_token})

                # if added_f_Response is None:
                #     return f_Response
                # header_token = new_token
                # return added_f_Response
            else :
                db_user.update_login_session_last_call_datetime(token=header_token, datetime=last_call_datetime)
            db_user.update_login_session_user_id_last_call_datetime(user_id=db_user_info["id"], datetime=last_call_datetime)

        except Exception as e:
            return f(*args, **kwargs) # API 에러나면 아래코드 exception으로 빠져서 아예 토큰 에러가 발생한 경우가 있었음 (데이터셋)
            # traceback.print_exc()
            # print("token_checker - Cath: ", e, header_token)
            # result =  {"status": False, "message": "Invalid Token "}
            # result.update(fail_response)
            # return result
        return f(*args, **kwargs)
    return decorated_function



def token_checker(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):

        # MSA 중복로그인 불가
        # is_check_func = check_func(str(f))
        # if settings.NO_TOKEN_VALIDATION_CHECK == True and not is_check_func:
        #     print("token_checker: no token validation check")
        #     return await f(*args, **kwargs)

        # token
        TOKEN_EXPIRED_TIME = 60000000 # settings.TOKEN_EXPIRED_TIME
        TOKEN_UPDATE_TIME = 60000000 # settings.TOKEN_UPDATE_TIME #TOKEN_EXPIRED_TIME + 3600
        TOKEN_VALIDATE_TIME = 2

        # response
        result = {"status": None, "message": None}
        fail_response = { "status": 0, "expired": True }
        header_token = ""

        try:
            # headers - JF
            headers = context["headers"]
            header_user = headers.get('JF-User')
            header_token = headers.get('Jf-Token')
            header_session = headers.get('Jf-Session')

            # jonathan (포털 설정)
            if settings.LOGIN_METHOD == "jonathan":
                return {"message" : "token_checker - jonathan 부분 수정해야됨 (msa 전환)"}
                # ===================================
                # marker_pass = False
                # marker_check_func_list = ["LoginSessionCopy.post", "Built_in_model_Annotation_LIST.get", "Built_in_model_LIST.get", "Datasets_auto_labeling", "SessionUpdate"]
                # for marker_func in marker_check_func_list:
                #     if marker_func in str(f):
                #         marker_pass = True

                # if marker_pass:
                #     pass
                # elif header_user in ["root", "lyla", "daehan-acriil", "yeobie", "edgar", "daehan", "will", "robert", "irene", "jake", "jason","lico"]: # root 는 통합 토큰 체크 안함
                #     return f(*args, **kwargs)
                # else:
                #     if not is_jonathan_token_valid(request):
                #         return fail_response
                # ===================================

            # Master Token Free pass
            if header_user is None or header_token is None:
                fail_response["message"] = "Header not exist"
                return fail_response
            elif header_user in ["admin", "daniel", "klod","jake","wyatt","min","luke","owen","david","aaron"]: # root 는 통합 토큰 체크 안함
                return await f(*args, **kwargs)
            elif header_user == "login" and header_token == "login":
                print("Login Step")
                result =  {"status": True, "login": True}
                return fail_response

            # token check
            token_user, start_timestamp, gen_count = session_cipher.decrypt(header_token).split("/")
            if header_user != token_user:
                print("Header data is invalid")
                fail_response["message"] = "Header data invalid"
                return fail_response

            db_user_info = db_user.get_user(user_name=header_user)
            if header_user != db_user_info["name"]:
                print("Token data is invalid")
                fail_response["message"] = "Token data invalid"
                return fail_response

            session_info, message = db_user.get_login_session(session_id=header_session)
            if session_info is None:
                fail_response["message"] = "Not logined"
                return fail_response

            # print("HEADER ", header_token, int(time.time()) - int(float(start_timestamp)))
            session_token_user, session_start_timestamp, session_gen_count = session_cipher.decrypt(session_info["token"]).split("/")
            last_call_timestamp = common.date_str_to_timestamp(session_info["last_call_datetime"])


            if header_token != session_info["token"]:
                valid_time = int(time.time()) - int(float(start_timestamp)) < TOKEN_VALIDATE_TIME
                expired_time = int(time.time()) - int(float(start_timestamp)) < TOKEN_EXPIRED_TIME
                valid_gen_count_op1 = int(session_gen_count) - int(gen_count) < 2
                valid_gen_count_op2 = int(session_gen_count) >= int(gen_count)
                if valid_time:
                    print("Already Updated Token But still valid")
                    return await f(*args, **kwargs)
                elif not valid_time and (valid_gen_count_op1 and valid_gen_count_op2) and expired_time:
                    print("Already Updated Token But still valid2")
                    return await f(*args, **kwargs)
                else :
                    fail_response["message"] =  "Changed Token or Logouted by other login"
                    return fail_response

            if int(time.time()) - int(last_call_timestamp) > TOKEN_EXPIRED_TIME:
                db_user.delete_login_session(header_token, db_user_info["id"])
                fail_response["message"] =  "Expired Token "
                return fail_response

            # print("ST " , int(start_timestamp), (time.time()))

            last_call_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            if int(time.time()) - int(float(start_timestamp)) > TOKEN_UPDATE_TIME: # and not is_check_func:
                # #Token Update - OLD
                # print("UPDATE TOKEN !!!")
                # #TODO 갱신 안정화 필요 (token 날렸는데 업데이트 안하는 경우 발생 (프론트의 비동기? 때문?),
                # #TODO 토큰에 추가 정보가 필요할 수 있음(몇번 째 콜 횟수 라던가)
                # #TODO TOKEN UPDATE 시 Header를 통할 수 있도록 (2022-01-20 다운로드 시 업데이트 되면 문제..)
                # new_token = crypt.gen_user_token(header_user, int(gen_count)+1)
                # db_user.update_login_session_token(old_token=header_token, new_token=new_token)
                # header_token = new_token
                # result["token"] = new_token
                # f_Response = f(*args, **kwargs)
                # return response_item_add(f_Response, {"token": new_token})
                #Token Update
                print("UPDATE TOKEN !!!")
                #TODO 갱신 안정화 필요 (token 날렸는데 업데이트 안하는 경우 발생 (프론트의 비동기? 때문?),
                #TODO 토큰에 추가 정보가 필요할 수 있음(몇번 째 콜 횟수 라던가)
                #TODO TOKEN UPDATE 시 Header를 통할 수 있도록 (2022-01-20 다운로드 시 업데이트 되면 문제..)
                new_token = crypt.gen_user_token(header_user, int(gen_count)+1)
                result["token"] = new_token
                f_Response = await f(*args, **kwargs)
                result, message = db_user.update_login_session_token(old_token=header_token, new_token=new_token)
                if result == False:
                    return f_Response
                print("UPDATED TOKEN @@@")
                # MSA 전환
                # return response_item_add(f_Response, {"token": new_token})
                return CustomResponse(content=f_Response, headers={"token": new_token})

                # if added_f_Response is None:
                #     return f_Response
                # header_token = new_token
                # return added_f_Response
            else :
                db_user.update_login_session_last_call_datetime(token=header_token, datetime=last_call_datetime)
            db_user.update_login_session_user_id_last_call_datetime(user_id=db_user_info["id"], datetime=last_call_datetime)

        except Exception as e:
            return await f(*args, **kwargs) # API 에러나면 아래코드 exception으로 빠져서 아예 토큰 에러가 발생한 경우가 있었음 (데이터셋)
            # traceback.print_exc()
            # print("token_checker - Cath: ", e, header_token)
            # result =  {"status": False, "message": "Invalid Token "}
            # result.update(fail_response)
            # return result
        return await f(*args, **kwargs)
    return decorated_function


# =================================
# MiddleWare
# =================================
# https://stackoverflow.com/questions/57204499/is-there-a-fastapi-way-to-access-current-request-data-globally/72664502#72664502
# https://github.com/encode/starlette/blob/master/starlette/middleware/cors.py
# https://github.com/tomwojcik/starlette-context/tree/master/starlette_context

class CustomPlugin(Plugin):
    key = "headers"

    async def process_request(
        self, request: Union[Request, HTTPConnection]
    ) -> Optional[Any]:
        res = request.headers

        if not res:
            return None

        try:
            res = request.headers
        except Exception as e:
            res = None
        return res

CustomMiddleWare = [
    Middleware(
        ContextMiddleware,
        plugins=(
            # plugins.RequestIdPlugin(),
            # plugins.CorrelationIdPlugin(),
            # plugins.DateHeaderPlugin(),
            CustomPlugin(),
        )
    ),
    Middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
]

# =================================
# Request
# =================================
# https://github.com/encode/starlette/blob/master/starlette/requests.py

class CustomResource:
    def __init__(self):
        self._headers = None  # 초기에는 None으로 설정

    @property
    def headers(self):
        # 객체를 생성할 때만 header 값 설정할 수 있도록
        # TODO 요청이 여러번 들어와서 header가 바뀌어야 할 필요도 있을지,,,
        if self._headers is None:
            self._headers = context.get("headers", None)
        return self._headers

    def test(self):
        res = self.headers
        return res["jf-user"]

    def is_root(self):
        #print ('login_name should get from session') #TODO
        try:
            if self.headers.get('Jf-User'):
                login_name = self.headers.get('Jf-User')
                if login_name == settings.ADMIN_NAME:
                    return True, ""
        except:
            traceback.print_exc()
        # return False, response(status=0,message="Permission Error. Not root")
        return False, {"status": 0, "message":"Permission Error"}

    def check_user(self):
        ## 유저 권한은 무엇으로 체크 ?
        #print ('user_name should get from session') #TODO
        ret_user = None
        try:
            if self.headers.get('Jf-User'):
                # print(self.headers.get('Jf-User'))
                user_name = self.headers['Jf-User']
                if type(user_name) == str:
                    if db_user.get_user(user_name=user_name):
                        return user_name
                    else:
                        None
                else:
                    return None
        except:
            traceback.print_exc()
        return ret_user

    def check_user_id(self):
        # print ('user_id should get from session') #TODO
        rows = db_user.execute_and_fetch('SELECT id FROM user WHERE name=%s', (self.check_user(),))
        try:
            user_id = rows[0]['id']
        except:
            user_id = None
            #TODO redirect to logout. remove sesssion.
        return user_id

    def is_admin_user(self):
        is_admin = False
        try:
            user_name = self.check_user()
            rows = db_user.execute_and_fetch('SELECT id, user_type FROM user WHERE name=%s', (user_name,))
            if rows[0]['user_type'] == 0:
                is_admin = True
        except:
            traceback.print_exc()
            raise ValueError('User {} does not exist.'.format(user_name))
        return is_admin

    def check_token(self):
        token = None
        try:
            if self.headers.get('Jf-Token'):
                token = self.headers['Jf-Token']
                if type(token) == str:
                    return token
                else:
                    return None
        except:
            traceback.print_exc()
        return token

    def get_jf_headers(self):
        res = {}
        for key in ['jf-user', 'jf-token', 'jf-session']: # 대문자 인식 X?
            if key in self.headers.keys():
                res[key] = self.headers[key]
            else:
                res[key] = None
        return res
