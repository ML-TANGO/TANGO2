# from flask_restful import Resource
from utils.resource import response
# from flask_restplus import reqparse
# from flask import send_file
# from restplus import api
# from utils.resource import CustomResource #, token_checker
# # import utils.db as db
from utils.msa_db import db_user
import utils.crypt as cryptUtil
from utils.exception.exceptions import *
import user.service_group as svc_group
from utils import mongodb, mongodb_key, notification_key, topic_key
from confluent_kafka import Producer
import os
import spwd
import pwd
import crypt
from datetime import datetime
import traceback
import subprocess
import requests
from utils.crypt import front_cipher

from utils import settings
MAX_NUM_OF_LOGINS = settings.MAX_NUM_OF_LOGINS
JF_SYSTEM_NAMESPACE = settings.JF_SYSTEM_NAMESPACE


USER_REGISTER_STATUS_REJECT = 0
USER_REGISTER_STATUS_ACCEPT = 1
USER_REGISTER_STATUS_WAITING = 2

conf = {
            'bootstrap.servers' : settings.JF_KAFKA_DNS
        }

def user_option(headers_user):
    try:
        if headers_user != settings.ADMIN_NAME:
            return response(status=0, message="permission denied")

        usergroup_list = [ {"id":group_info["id"], "name":group_info["name"]}  for group_info in db_user.get_usergroup_list() ] 

        result = {
            "usergroup_list" : usergroup_list
        }
        
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Option error : {}".format(e))

def check_user_name(user_name, headers_user=None):
    try:
        # linux x
        # if headers_user is None:
        #     return response(status=0, message="Jf-user is None in headers")
        # user_nmae_list = []
        # for p in pwd.getpwall():
        #     user_nmae_list.append(p[0])

        if db_user.get_user(user_name=user_name) is not None:
            return response(status=0, message="이미 사용중인 ID 입니다.")

        if db_user.get_user_register(user_name=user_name) is not None:
            return response(status=0, message="요청 대기중인 ID입니다.")

        return response(status=1, message="OK")        
    except:
        return response(status=0, message="Check user name Error")


def get_users(search_key, size, page, search_value):    
    user_result_list = []
    user_list = db_user.get_user_list(search_key=search_key, size=size, page=page, search_value=search_value)
    for user_n, user in enumerate(user_list):
        locked = False if user["login_counting"] < MAX_NUM_OF_LOGINS else True
        user_result_list.append({
            "id": user["id"],
            "name": user["name"],
            "locked": locked,
            "user_type": user["user_type"],
            "real_user_type": user["real_user_type"],
            "create_datetime": user["create_datetime"],
            "update_datetime": user["update_datetime"],
            "workspaces": user["workspaces"],
            "trainings": user["projects"],
            "deployments": user["deployments"],
            "images": user["images"],
            "datasets": user["datasets"],
            "usergroup": user["group_name"],
            "email" : user.get("email"),
            "team" : user.get("team"),
            "job" : user.get("job"),
            "nickname" : user.get("nickname"),
            # "not_in_linux": check_user_in_linux(user_name=user["name"], uid=user["uid"])
        })
        # user_list[user_n] = item

    if user_result_list is None:
        return response(status=0, message="User list get Error ")

    # =============================================================
    # 회원가입 리스트 추가
    user_register_list = [{
        "register_id" : user.get("id"), # user_register table의 id임
        "name" : user.get("name"),
        "usergroup" : user.get("usergroup_name"),
        "real_user_type" : 4,
        # "register_name" : user.get("register_name"),
        # "position" : user.get("position"),
        "create_datetime" : user.get("create_datetime"),
        # "user_type" : user.get("user_type"), # TODO,
    } for user in db_user.get_user_register_list()]

    # user_result_list = user_result_list + user_register_list 
    return response(status=1, message="OK", result={"list": user_result_list, "register_list" : user_register_list, "total": len(user_result_list + user_register_list)} )


def get_user(user_id):
    result = []
    try:
        # if users_id is not None:
        #     # Select Some User(s)
        #     for user_id in users_id:
        #         user_data = db_user.get_user(user_id=user_id)
        #         if user_data == None:
        #             return response(status=1, message="User ID [{}] Not Found ".format(user_id))
        #         user_data["training"] = db_user.get_user_training(user_id)
        #         user_data["workspace"] = db_user.get_user_workspace(user_id)
        #         result.append(user_data)
        # else:
        #     # Select All User
        #     result = db_user.get_user_list()
        #     for user_data in result:
        #         user_data["training"] = db_user.get_user_training(user_data['id'])
        #         user_data["workspace"] = db_user.get_user_workspace(user_data['id'])

        user_data = db_user.get_user(user_id=user_id)
        result = {
            "user_name": user_data["name"],
            "group_id": user_data["group_id"],
            "team" : user_data.get("team"),
            "job" : user_data.get("job"),
            "email" : user_data.get("email"),
            "nickname" : user_data.get("nickname"),
        }
        

    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get User Error", result=result)
        #return response(status=0, message="Get User Error [{}]".format(e), result=result)
    return response(status=1, result=result)
    



def create_user_new(new_user_name : str, password : str, user_type : int, headers_user : str, usergroup_id : int = None,
                    email: str = None, job: str = None, nickname: str = None, team: str = None): 
    if headers_user is None:
        return response(status=0, message="Jf-user is None in headers")
    if db_user.get_user(user_name=new_user_name):
        return response(status=0, message="Already Exist User")
    password = front_cipher.decrypt(password)
    enc_pw = crypt.crypt(password, settings.PASSWORD_KEY)
    uid = 1000 # TODO 임시 
    user_id = db_user.insert_user(user_name=new_user_name, password=enc_pw, uid=uid, user_type=user_type, email=email, job=job, nickname=nickname, team=team)
    if user_id:
        
        if usergroup_id: # 사용자 그룹 추가
            db_user.insert_user_group(user_group_id=usergroup_id, user_id=user_id)
        
        # SSH Pod 계정 생성
        if not request_ssh_pod({"name": new_user_name}, "create_user"):
            print(f"[JFB/INFO] creating user '{new_user_name}' failed in ssh pod", file=sys.stderr)

        return response(status=1, message=f"create user : {new_user_name}")
    else:
        return response(status=0, message="Create Error")
        
def check_user_have_training(user_id):
    #TODO User training Status Check + (running / stop)
    flag = True
    try:
        user_training = db_user.get_user_training(user_id=user_id, only_owner=True)
        if user_training is not None:
            if len(user_training) == 0:
                flag = False
                return flag, ""
            else:
                user_training = [training["name"] for training in user_training]
                return flag, {"status": 0, "message": "실행 중인 학습이 있습니다: [{}]".format(",".join(user_training))}
        else:
            return flag, {"status": 0, "message": "사용자 학습 상태를 확인할 수 없습니다."}
    except Exception as e:
        traceback.print_exc()
        return flag, {"status": 0, "message": "사용자 학습 상태 확인 중 오류가 발생했습니다."}
        #return flag, response(status=0, message="[{}]".format(e))
    

def check_user_have_deployment(user_id):
    flag = True
    try:
        user_deployment = db_user.get_user_deployment(user_id=user_id, only_owner=True)
        if user_deployment is not None:
            if len(user_deployment) == 0:
                flag = False
                return flag, ""
            else:
                user_deployment = [deployment["name"] for deployment in user_deployment]
                return flag, {"status": 0, "message": "실행 중인 배포가 있습니다: [{}]".format(",".join(user_deployment))}
        else:
            return flag, {"status": 0, "message": "사용자 배포 상태를 확인할 수 없습니다."}
    except Exception as e:
        traceback.print_exc()
        return flag, {"status": 0, "message": "사용자 배포 상태 확인 중 오류가 발생했습니다."}


def check_if_workspace_manager(user_id):
    flag = True
    try:
        manager_workspace = db_user.get_manager_workspace(user_id=user_id)
        if manager_workspace is not None:
            if len(manager_workspace) == 0:
                flag = False
                return flag, ""
            else:
                workspaces = [workspace["name"] for workspace in manager_workspace]
                return flag, {"status": 0, "message": "관리 중인 워크스페이스가 있습니다: [{}]".format(",".join(workspaces))}
        else:
            return flag, {"status": 0, "message": "워크스페이스 관리자 권한을 확인할 수 없습니다."}
    except Exception as e:
        traceback.print_exc()
        return flag, {"status": 0, "message": "워크스페이스 관리자 권한 확인 중 오류가 발생했습니다."}


def delete_users(id_list, headers_user):
    #User Exist Check
    # if headers_user is None:
    #     return response(status=0, message="Jf-user is None in headers")

    user_name_and_id_list = db_user.get_user_name_and_id_list(id_list)
    if user_name_and_id_list is None or len(user_name_and_id_list) != len(id_list):
        return response(status=0, message="사용자를 찾을 수 없습니다.")

    # 먼저 모든 사용자에 대해 삭제 가능 여부를 체크
    message = ""
    for user_info in user_name_and_id_list:
        #Check User have training
        flag_training, check_response_training = check_user_have_training(user_id=user_info["id"])
        if flag_training:
            message += "[{}] ".format(user_info["name"])+check_response_training["message"] +"\n"
        
        #Check User have deployment
        flag_deployment, check_response_deployment = check_user_have_deployment(user_id=user_info["id"])
        if flag_deployment:
            message += "[{}] ".format(user_info["name"])+check_response_deployment["message"] +"\n"

        flag_workspace, check_response_workspace = check_if_workspace_manager(user_id=user_info["id"])
        if flag_workspace:
            message += "[{}] ".format(user_info["name"])+check_response_workspace["message"] +"\n"

    # 체크에서 문제가 발견되면 삭제 중단 (SSH Pod 요청 없이)
    if message:
        return response(status=0, message=message + "사용자를 삭제하기 전에 위의 항목들을 먼저 정리해주세요.")

    # 모든 체크가 통과한 경우에만 실제 삭제 작업 수행
    # DB에서 사용자 삭제 먼저 수행
    if db_user.delete_users(id_list):
        # DB 삭제가 성공한 경우에만 SSH Pod 계정 삭제 수행
        for user_info in user_name_and_id_list:
            if not request_ssh_pod({"name": user_info["name"]}, "delete_user"):
                print(f"[JFB/INFO] deleting user \'{user_info['name']}\' failed in ssh pod", file=sys.stderr)
        
        # for user_info in user_name_and_id_list:
        #     os.system('userdel {}'.format(user_info["name"]))
        # # os.system('cp /etc/group /etc/gshadow /etc/passwd /etc/shadow /etc_host/') #etc backup
        # etc_backup()
        return response(status=1, message="사용자 [{}]가 성공적으로 삭제되었습니다.".format(",".join([user_info["name"] for user_info in user_name_and_id_list])))
    else:
        return response(status=0, message="데이터베이스에서 사용자 삭제 중 오류가 발생했습니다.")


def update_user_new(select_user_id : int,  headers_user : str, 
                    new_password : int = None,usergroup_id : int = None,
                    email: str = None, job: str = None, nickname: str = None, team: str = None):
    if headers_user is None:
        return response(status=0, message="Jf-user is None in headers")
    try:
        # User ID Exist Check
        user_info = db_user.get_user(user_id=select_user_id)
        if user_info is None:
            return response(status=0,message="No match user")
        
        # 비밀번호 업데이트        
        if new_password is not None:
            new_password = front_cipher.decrypt(new_password)
            new_enc_pw = crypt.crypt(new_password, settings.PASSWORD_KEY)
            res = db_user.update_user_password(user_id=select_user_id, new_password=new_enc_pw)
            if res != True:
                return response(status=0, message="Updated Failed user {} Password change".format(user_info["name"]))

        # 사용자그룹 업데이트
        origin_usergroup_id = user_info.get("usergroup_id")
        # db_user.delete_user_group(user_id=select_user_id) # 사용자 그룹 None 일때 제거, 사용자그룹 추가변경시에는 usergroup delete 후에 insert
        if usergroup_id != origin_usergroup_id:
            if origin_usergroup_id is None and usergroup_id != 0: # 추가
                db_user.insert_user_group(user_group_id=usergroup_id, user_id=select_user_id)
            elif origin_usergroup_id != None and usergroup_id is None: #삭제
                db_user.delete_user_group(user_id=select_user_id)
            else: # 수정
                db_user.update_user_usergroup(user_id=select_user_id, usergroup_id=usergroup_id)

        # 나머지 정보 업데이트
        db_user.update_user_info(user_id=select_user_id,
                                 email=email, job=job, nickname=nickname, team=team)

        return response(status=1, message="Updated user {}".format(user_info["name"]))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Upadet user error : {}".format(e))

def update_user_password(password, new_password, headers_user):
    try:
        # if linux_login_check(headers_user, front_cipher.decrypt(password)) == False:
        user_info = db_user.get_user(user_name=headers_user)
        if user_info:
            password=front_cipher.decrypt(password)
            enc_pw = crypt.crypt(password, settings.PASSWORD_KEY)
            if enc_pw != user_info["password"]:
            # if linux_login_check(headers_user, password) == False:
                return response(status=0, message="User password not matched")
            else :
                new_password=front_cipher.decrypt(new_password)
                new_enc_pw = crypt.crypt(new_password, settings.PASSWORD_KEY)
                # result = user_passwd_change(user_name=headers_user, new_password=new_password)
                if db_user.update_user_password(user_id=user_info["id"], new_password=new_enc_pw):

                    # for workspace in db_user.get_user_workspace(user_id=db_user.get_user_id(user_name=headers_user)["id"]):
                    #     update_workspace_users_etc(workspace_id=workspace["id"])
                    return response(status=1, message="User password updated")
                else :
                    return response(status=1, message="User password update fail")

    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Update user password error : {}".format(e))


def init_users():
    if os.system("ls /etc_host/passwd") == 0:
        os.system("cp {etc_host}/group {etc_host}/gshadow {etc_host}/passwd {etc_host}/shadow /etc/".format(etc_host=JF_ETC_DIR)) # BACKUP DATA TO DOCKER
    else :
        os.system('cp /etc/group /etc/gshadow /etc/passwd /etc/shadow {etc_host}/'.format(etc_host=JF_ETC_DIR))

def etc_backup():
    os.system('cp /etc/group /etc/gshadow /etc/passwd /etc/shadow {etc_host}/'.format(etc_host=JF_ETC_DIR)) #etc backup

ALREADY_EXIST = 0
NOT_FOUND = 1
ALREADY_EXIST_BUT_UID_DISMATCH = 2

def check_user_in_linux(user_name: str = None, uid: int = None, user_id: int = None) -> int:
    """
    Description: 리눅스 계정 존재 및 정상 여부(name과 uid가 db값과 일치) 체크

    Args:
        user_id (int): 유저 Id
        user_name (str): 유저 name
        uid (int): 유저 uid

    Returns:
        int: 리눅스 계정 유무 존재, 정상 여부 체크 (0, 1, 2)

    Examples:
        check_user_in_linux(3, 'test_id', 192)  # 0 (존재 O) | 1 (존재 X) | 2 (존재 O. but uid 불일치)
    """
    try:
        if user_name is None or uid is None:
            user_id, user_name, uid, *_ = db_user.get_user(user_id=user_id)
        
        for p in pwd.getpwall():
            PW_NAME = p[0]
            PW_UID = p[2]
            if user_name == PW_NAME:
                if uid == PW_UID:
                    return ALREADY_EXIST
                return ALREADY_EXIST_BUT_UID_DISMATCH
        return NOT_FOUND
        
    except Exception as e:                                      
        traceback.print_exc()


def get_user_workspaces(user_id):
    try:
        workspace_list = db_user.get_user_workspace(user_id=user_id)
    except Exception as e:
        return response(status=0,message="Get user workspaces Error")
        #return response(status=0,message=e)
    
    return response(status=1,result=workspace_list)


# SSH pod request
def request_ssh_pod(data, type):
    try:
        SSH_DNS = f"jfb-app-ssh-svc.{JF_SYSTEM_NAMESPACE}.svc.cluster.local"

        if type == "create_user":
            payload = {'user_name': data["name"]}
            headers = {'Content-Type': 'application/json'}
        elif type == "delete_user":
            payload = {'user_name': data["name"]}
            headers = {'Content-Type': 'application/json'}
        else:
            raise RuntimeError(f"Unknown request type: {type}")

        res = requests.post("http://{url}/api/ssh/{type}".format(url=SSH_DNS, type=type), json=payload, headers=headers).json()
        if res["status"]:
            return True
        return False
    except Exception as e:
        traceback.print_exc()
        return False
# ======================================================================================================
# 회원가입
from pydantic import BaseModel, ValidationError
def request_user_register(name, password, nickname=None, job=None, email=None, team=None):
    # name - 실제 아이디
    try:
        if db_user.get_user(user_name=name) is not None:
            return response(status=0, message="Already Exist User")

        if db_user.get_user_register(user_name=name) is not None:
            return response(status=0, message="Already Exist User")

        # 암호화
        password=front_cipher.decrypt(password)
        enc_pw = crypt.crypt(password, settings.PASSWORD_KEY)
        
        # DB user_register
        db_res, request_id = db_user.insert_user_register(name=name, password=enc_pw, nickname=nickname, job=job, email=email, team=team)
        if db_res == False:
            raise

        # 알림 (위의 모든 과정이 처리된 후에 알림 전송, 중간에 에러나면 알림이 전송되지 않도록)
        noti_user_name = name
        if team:
            noti_user_name = "{} {}".format(team, name)
        notification = mongodb.NotificationInfo(
            user_id=db_user.get_user(user_name="admin")["id"],
            user_type=notification_key.NOTIFICATION_USER_TYPE_ADMIN,
            noti_type=notification_key.NOTIFICATION_TYPE_USER,
            message=notification_key.USER_CREATE_REQUEST.format(user_name=noti_user_name),
        )
        producer = Producer(conf)
        producer.produce(topic=topic_key.ALERT_ADMIN_TOPIC,
                          value=notification.model_dump_json())
        producer.poll(1)
        producer.flush()
        # res, message = mongodb.insert_notification_history(notification=notification)
        # if not res:
        #     raise Exception(message)
        return response(status=1, message="OK")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="ERROR")
    
    
def get_user_register(register_id):
    # 가입정보확인
    try:
        user_info = db_user.get_user_register(register_id=register_id)
        res = {key: value for key, value in user_info.items() if key != "password"}
        res["register_id"] = res.pop("id")
        return response(status=1, message="OK", result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


def approve_user_register(approve, register_id, usergroup_id=None):
    try:
        if approve == True:
            # 유저등록
            user_info = db_user.get_user_register(register_id=register_id)
            user_name = user_info.get("name")
            password = user_info.get("password")
            nickname = user_info.get("nickname")
            job = user_info.get("job")
            team = user_info.get("team")
            email = user_info.get("email")
            
            # 유저 존재 확인
            if db_user.get_user(user_name=user_name):
                return response(status=0, message="Already Exist User")

            # user 등록
            user_id = db_user.insert_user(user_name=user_name, password=password, uid=1000, user_type=3,
                                           nickname=nickname, job=job, email=email, team=team) # TODO UID는 임시
            
            if user_id and usergroup_id: # 사용자 그룹 추가
                db_user.insert_user_group(user_group_id=usergroup_id, user_id=user_id)
            
            # SSH Pod 계정 생성
            if not request_ssh_pod({"name": user_name}, "create_user"):
                print(f"[JFB/INFO] creating user '{user_name}' failed in ssh pod", file=sys.stderr)
        else:
            # 거절
            # TODO
            pass
        
        # user_register DB 삭제
        db_user.delete_user_register(register_id=register_id)
        return response(status=1, message="OK")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))