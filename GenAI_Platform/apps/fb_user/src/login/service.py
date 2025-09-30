from utils.resource import response #, token_checker
from utils.common import log_access
from utils.linux import linux_login_check
from utils.crypt import session_cipher, front_cipher
import utils.crypt as crypt
# # import utils.db as db
import utils.msa_db.db_user as db_user

import time
import json
import traceback

from login.jonathan_platform import get_user_info_with_jp_token, create_jf_user_name_from_email
from utils.settings import MAX_NUM_OF_LOGINS, LOGIN_METHOD, LOGIN_VALIDATION_CHECK_API, PASSWORD_KEY

if LOGIN_METHOD == "jfb":
    def login_valid_check(**kwargs):
        user_name = kwargs.get("user_name")
        if db_user.get_user_register(user_name=user_name) is not None:
            return False, response(status=0, message="Waiting for admin approval. Try logging in again later.")

        password_check_result, message = password_check(**kwargs)
        if password_check_result == False:
            return False, message

        return True, ""

elif LOGIN_METHOD == "jonathan":
    # def login_valid_check(**kwargs):
    #     if kwargs.get("user_name") is not None:
    #         if kwargs.get("user_name") in ["root", "lyla", "daehan-acriil", "yeobie", "edgar", "daehan", "will", "robert", "irene", "jake", "jason","lico"]:
    #             password_check_result, message = password_check(**kwargs)
    #             if password_check_result:
    #                 return True, ""
    #             else:
    #                 return False, message
    #         else:
    #             return False, response(status=0, message="Only admin can access")

    #     jonanthan_token_check_result, message = jonanthan_token_check(**kwargs)
    #     if jonanthan_token_check_result == False:
    #         return False, message
    #     return True, ""
    pass

elif LOGIN_METHOD == "kisti":
#     import requests
#     def otp_check(user_name, otp, **kwargs):
#         URL = LOGIN_VALIDATION_CHECK_API
#         res = requests.get("{}/info".format(URL))
#         if res.status_code != 200:
#             return response(status=0, message="OTP server response status [{}]".format(res.status_code))
#         # print("!!!", json.loads(res.text))

#         if user_name == "root":
#             user_name = KISTI_OTP_ROOT_USER_ID
#         params = {'id': user_name, 'token': otp}
#         res = requests.get("{}/auth".format(URL), params)
#         res = res.json()
#         if int(res["status"]) == 0:
#             return True, ""
#         else :
#             return False, response(stauts=0, message="OTP response status ({}) msg : ({}) ".format(res["status"], res["msg"]))

    def login_valid_check(**kwargs):
        password_check_result, message = password_check(**kwargs)
        if password_check_result == False:
            return False, message

        otp_check_result, message = otp_check(**kwargs)
        if otp_check_result == False:
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


def login(request, parsers):
    try:
        kwargs = parsers.dict()
        valid_check_result, message = login_valid_check(**kwargs)
        if valid_check_result == False:
            return message

        jp_user_info = None
        if LOGIN_METHOD == "jonathan" and kwargs["user_name"] is None:
            jp_user_info = get_user_info_with_jp_token(request)

            kwargs["user_name"] = jp_user_info["username"]

        user_name = kwargs["user_name"]
        user_info = db_user.login(user_name)

        if user_info is not None:
            result = {"user_name": user_name, "token": None, "logined_session": None,
                    "admin": True if user_name == 'admin' else False, "logined": False}

            # gen token
            token = crypt.gen_user_token(user_name, 0)
            result["token"] = token
            user_id = user_info["id"]

            if user_info["login_counting"] >= MAX_NUM_OF_LOGINS:
                return response(status=0, message="ID {} locked.".format(user_name), locked=True)

            # check user login
            login_result, message = db_user.get_login_session(user_id=user_id)

            if login_result is not None:
                # MSA 변경 -> 로그인 세션을 삭제
                db_user.delete_login_session(user_id=user_id)

                # # already logined
                # result["logined"] = True
                # ret = response(status=1, result=result, login=True)
                # # MSA 전환
                # # log_access({'username':user_name, 'header':dict(request.headers), 'ret':ret})
                # return ret

            print("insert_login_session")
            insert_result, message = db_user.insert_login_session(user_id=user_id, token=token)
            if not insert_result:
                return response(status=0, message="Login session error")
            result["logined_session"] = db_user.get_login_session(token=token)[0]["id"]
            db_user.update_user_login_counitng(user_id=user_id, set_default=True)
            ret = response(status=1, result=result, login=True)
            # MSA 전환
            # log_access({'username':user_name, 'header':dict(request.headers), 'ret':ret})

            return ret
        else:
            return response(status=0, message="Please retry login with correct ID and password.")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Login Error")


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