import re
import json
import time
from utils import settings
# import workspace
import traceback
import queue
import threading
import subprocess
import asyncio
import requests

# import utils.kube as kube
# import utils.db as db
import utils.msa_db.db_image as db_image_msa
import utils.registry as registry

import utils.common as common
from utils.common import generate_alphanum, ensure_path, writable_path

from utils.resource import response
from utils.exceptions import *
from utils.log import logging_history, LogParam

# 파일 관련 임포트
import os
import shutil
# from werkzeug.datastructures import FileStorage
# from werkzeug.utils import secure_filename

from image.settings import JF_CONTAINER_RUNTIME

ROOT_USRE = 1
ACCESS_WORKSPACE = 0
ACCESS_ALL = 1

IMAGE_STATUS_PENDING = 0
IMAGE_STATUS_INSTALLING = 1
IMAGE_STATUS_READY = 2
IMAGE_STATUS_FAILED = 3
IMAGE_STATUS_DELETING = 4

IMAGE_UPLOAD_TYPE_STR = {
    0 : "built-in", 1 : "pull", 2 : "tar", 3 : "build", 4 : "tag", 5 : "ngc", 6 : "commit", 7 : "copy",
}

# PATH 변수
DOCKER_REGISTRY_URL = settings.DOCKER_REGISTRY_URL  # 192.168.X.XX:5000/

BASE_DOCKERFILE_PATH = settings.BASE_DOCKERFILE_PATH  # in docker
HOST_BASE_DOCKERFILE_PATH = settings.HOST_BASE_DOCKERFILE_PATH  # in host
DOCKERFILE_PATH_SKEL = 'dockerfile/{random_str}/Dockerfile' # relative path for db store
DOCKERFILE_FULL_PATH_SKEL = BASE_DOCKERFILE_PATH + '/' + DOCKERFILE_PATH_SKEL

BASE_IMAGE_PATH = settings.BASE_IMAGE_PATH  # in docker
HOST_BASE_IMAGE_PATH = settings.HOST_BASE_IMAGE_PATH  # in host
IMAGE_PATH_SKEL = 'tar/{random_str}.tar'  # relative path for db store
IMAGE_FULL_PATH_SKEL = BASE_IMAGE_PATH + '/' + IMAGE_PATH_SKEL


from kubernetes import config, client
config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()


# TODO configmap
if JF_CONTAINER_RUNTIME == "docker":
    IMAGE_CLI = "docker"
elif JF_CONTAINER_RUNTIME == "containerd":
    IMAGE_CLI = "nerdctl"

# ##############################################################################################################
# ##############################################################################################################
# ##############################################################################################################
import os
import traceback
import subprocess
import asyncio

line = 0
def save_log_install_image(std_out=None, std_err=None, image_id=None, message=None, layer_log=False, layer=None):
    """
    Description :
        이미지 설치 시 launcher 로그 저장, docker command 부분 (pull, build, tag, push) + print
        pull(pull, ngc) -> _save_log_layer
        echo 사용시 std_out에 > 가 포함되어, 저장될 문자열이 파일로 만들어지는 경우가 있어서 ''으로 처리함
    Args :
        std_out, std_err, message (str) : log
        _type(int), layer(dict) : pull, ngc, push일 때 필요한 input
    """
    try:
        dir_path = BASE_IMAGE_PATH + "/log"
        ensure_path(dir_path)
        file_path = dir_path + "/{}.log".format(image_id)

        def _save_log_install_layer(std_out, file_path):
            '''
            Description
                pull(pull, ngc), push 설치 로그
                ! progressbar - pull, pushing은 안되고, ngc는 됨
            # layer
                pull case
                    Already exists / Pulling fs layer, Waiting, Downloading
                    Verifying Checksum, Download complete, Extracting, Pull complete
                push case
                    Preparing, Waiting, Pusing, Pushed, Mounted from
            # layer 아닌 경우
                ':' 이 std_out에 포함되어도 layer가 아닌 경우가 있어서 따로 분리함
            '''
            global line
            if b'\x1b[F\x1b[K' in std_out.encode():
                pass
            elif "The push refers to repository" in std_out or "Pulling from" in std_out:
            # push 시작(The push refers to repository), pull 시작(Pulling from)
                    cmd = "echo '{}\\n.' >> {}".format(std_out, file_path) # '.'을 다음줄에 입력해줘야 sed 동작
                    os.system(cmd)
                    line = sum(1 for _ in open(file_path)) # sed 부분 업데이트를 위해 line 위치 가져옴
            elif any(x in std_out for x in ("Digest", 'Status', 'digest')):
            # 마지막 부분
                cmd = "echo '{}' >> {}".format(std_out, file_path)
            elif ":" in std_out:
            # layer 부분
                tmp = std_out.split(":")
                _hash = tmp[0]
                if len(_hash) == 12: # layer 인경우
                    _status = ''.join(tmp[1:])
                    if '/' in _status:
                        _status = _status.replace('/', '\/') # sed에서 '/'포함시 에러 (ex. Mounted from)
                    layer[_hash] = _status
                    cmd = """sed -i "{}s/.*/layer: {}/g" {}""".format(line, layer, file_path)
                    os.system(cmd)
                else: # layer 아닌 경우
                    os.system("echo '{}' >> {}".format(std_out, file_path))
            else:
            # TODO 다른 case?
                os.system("echo '{}' >> {}".format(std_out, file_path))

        if std_out:
            if layer_log == True:
                _save_log_install_layer(std_out, file_path)
            else:
                os.system("echo '{}' >> {}".format(std_out, file_path))
        if std_err:
            os.system("echo '{}' >> {}".format(std_err, file_path))
        if message: # 코드에서 print로 보고 싶은 부분
            os.system("echo '{}' >> {}".format(message, file_path))
    except Exception as e:
        traceback.print_exc()

# def logging_history(user, task, action, task_name, workspace_id=None, update_details=None):
#     """로그(history): user(UserName), task(image), action(CRUD)"""
#     try:
#         if type(workspace_id) != list or workspace_id == []: # 워크스페이스 아이디 없는 경우
#             db.logging_history(workspace_id=None, user=user, task=task, action=action, task_name=task_name,
#                                update_details=update_details)
#         else:
#             for wid in workspace_id: # 워크스페이스 아이디 있는 경우
#                 db.logging_history(workspace_id=wid, user=user, task=task, action=action, task_name=task_name,
#                                    update_details=update_details)
#     except Exception as error:
#         traceback.print_exc()
#         return error

# ##############################################################################################################
# ############################################### CRUD #########################################################
# ##############################################################################################################

def get_image_list(workspace_id, user_id):
    try:
        """db에 저장된 image 정보 가져옴"""
        image_list = []
        rows = db_image_msa.get_image_list(workspace_id)

        for row in rows:
            item = {
                # 기본정보
                'id': row['id'],
                'image_name': row['name'],
                'status': row['status'],
                'fail_reason': row['fail_reason'], # 추가
                'type': row['type'],
                'access': row['access'],

                'size': row['size'] if row['size'] else None,
                'workspace': row['workspace'],
                'user_name': row['user_name'],
                'create_datetime': row['create_datetime'],
                'update_datetime': row['update_datetime'],

                # 상세정보
                'description': row['description'],
                'tag': row['real_name'].split(':')[-1],
                'iid': row['iid'],
                'repository': ':'.join(row['real_name'].split(':')[0:-1]),
                'library': row['libs_digest'] if row['libs_digest'] else None,

                # has_permission
                'has_permission': check_has_permission(user_id=user_id, build_type=row['type'], image_id=row['id'],
                                                       owner=row['uploader_id'], access=row['access'],
                                                       workspace_id=workspace_id),

                # 기타
                'real_name' : row['real_name'],
                'docker_digest' : row['docker_digest'] if row['docker_digest'] else None,
                'upload_filename' : row['upload_filename'] if row['upload_filename'] else None
            }
            image_list.append(item)
        result = {
            "list": image_list,
            "total": len(image_list)
        }
        return response(status=1, message="OK", result=result)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        raise GetImageError

def get_image_single(image_id):
    """단일 image 상세 정보"""
    try:
        res = db_image_msa.get_image_single(image_id)
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        raise GetImageError

def update_image(image_id, image_name, workspace_id_list, access, description, user):
    """이미지 업데이트"""
    try:
        if access == ACCESS_ALL:
            workspace_id_list = []

        # update: name, access, description
        db_image_msa.update_image_data(image_id=image_id, data={
            "name": image_name, "access": access, "description": description
        })

        # update: workspace
        db_image_msa.update_image_workspace(
            image_id=image_id, access=access, workspace_id_list=workspace_id_list)

        # 로그
        logging_history(user=user, task='image', action='update',
                        task_name=image_name, workspace_id=workspace_id_list)

        return response(status=1, message="OK", result=None)
    except Exception as e:
        traceback.print_exc()
        raise UpdateImageError

def delete_image(delete_all_list, delete_ws_list, workspace_id, delete_user):
    """
    이미지 삭제
    이 함수에서는 워크스페이스 db만 수정(워크스페이스 삭제)하거나 status를 deleting으로 변경한다.
    실제로는 delete_image_all_place 에서 실제 이미지를 삭제 및 log 남김
    image_old에서는 삭제방식 다름 (def delete_image(user_id, image_id)) - status에 따라 바로 삭제 하거나, sync에서 삭제
    """
    try:
        status = 1
        message = {"success" : list(), "fail" : list(), "installing(try again)" : list()}

        delete_image_list = delete_all_list + delete_ws_list
        for delete_image in delete_image_list:
            try:
                image_info = db_image_msa.get_image_single(delete_image)
            except:
                pass

            # access 확인
            res, delete_type = check_delete_access(delete_image, delete_all_list, delete_ws_list, workspace_id, delete_user)
            if not res:
                status *= 0
                message["fail"].append(image_info["image_name"] + ' (permission error)')
                continue

            # 대기중, 설치중
            if image_info["status"] == 0 or image_info["status"] == 1:
                status *= 0
                message["installing(try again)"].append(image_info["image_name"])
                continue

            # 워크스페이스 : DB만 삭제
            if delete_type == ACCESS_WORKSPACE:
                db_image_msa.delete_image_workspace(delete_image, workspace_id)
                message["success"].append(image_info["image_name"] + f' (in {workspace_id} workspace)')

            # 전체 삭제 or (워크스페이스 삭제 & 이미지가 속해있는 워크스페이스가 없는 경우)
            if delete_type == ACCESS_ALL or (delete_type == ACCESS_WORKSPACE and not db_image_msa.get_workspace_image_id(delete_image)):
                # 상태가 실패함이면 db 바로 삭제
                if image_info["status"] == 3:
                    db_image_msa.delete_image(delete_image)
                    message["success"].append(image_info["image_name"] + ' (all)')
                    continue

                # 레지스트리, 로컬, DB 삭제
                db_image_msa.update_image_data(image_id=delete_image, data={"status" : IMAGE_STATUS_DELETING})
                message["success"].append(image_info["image_name"] + ' (all)')

            logging_history(task=LogParam.Task.IMAGE, action=LogParam.Action.DELETE, user_id=delete_user, task_name=image_info["real_name"])
        return response(status=status, message=str(message), result=None)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        raise DeleteImageError

def check_has_permission(image_id, user_id, workspace_id, owner, access, build_type):
    """
    flag to disable or enable buttons to edt/delete in User's Docker image page

    0 : 아무것도 못함
    1 : owner, 수정가능 + 전체삭제
    2 : owner, 수정가능 + 전체삭제 + 선택삭제
    3 : manager, 수정불가 + 선택삭제
    """
    try:
        # build-in 수정, 삭제 모두 막음
        if build_type == 0:
            return 0

        # root
        if user_id == ROOT_USRE:
            return 1

        # owner
        if user_id == owner:
            if access == ACCESS_ALL:
                return 1
            else:
                return 2

        # manager
        '''
        1. 이미지의 워크스페이스 모두 가져옴 -> 현재 워크스페이스 아이디가 있는지 확인
        2. 현재 워크스페이스의 매니저를 가져옴 -> 유저 아이디와 매니저 아이디가 같은지 확인
        '''
        for workspace in db_image_msa.get_image_workspace_list(image_id):
            wid = workspace["workspace_id"]
            if workspace_id == wid:
                for manager_id in db_image_msa.get_workspace_manager_id(wid):
                    if user_id == manager_id["manager_id"]:
                        return 3
        return 0
    except :
        traceback.print_exc()
        raise ImagePermissionError

def check_delete_access(image_id, delete_all_list, delete_ws_list, workspace_id, delete_user):
    """유저의 삭제 이미지 권한 확인"""
    try:
        uploader_id = db_image_msa.get_image_single(image_id)["uploader_id"]

        # 전체 삭제 체크
        if image_id in delete_all_list:
            if delete_user == uploader_id or delete_user == ROOT_USRE:
                return True, ACCESS_ALL
        # WS 삭제 체크
        elif image_id in delete_ws_list:
            manager_list = [manager['manager_id'] for manager in db_image_msa.get_image_manager_list(image_id)]
            image_workspace_list = [workspace_id['workspace_id'] for workspace_id in db_image_msa.get_image_workspace_list(image_id)]

            if delete_user == uploader_id or delete_user == ROOT_USRE or \
                (delete_user in manager_list and workspace_id in image_workspace_list):
                return True, ACCESS_WORKSPACE
        else:
            return False, None
    except :
        traceback.print_exc()
        raise ImagePermissionError

# ##############################################################################################################
# ########################################## image list ########################################################
# ##############################################################################################################
# ngc
def get_ngc_image_list():
    """
    Get all ngc registry images.
    :rtype: list
    """
    try:
        result = subprocess.check_output(["""ngc registry image list --format_type 'json' || echo ''"""], shell=True, stderr=subprocess.PIPE).decode('utf-8').strip()

        ngc_images = json.loads(result)
        images = []
        for ngc_image in ngc_images:
            if ngc_image.get("latestTag") is not None and ngc_image.get(
                    "publisher") is not None:  # can not install if latestTag is not provided
                if ngc_image["sharedWithOrgs"]:
                    repository = ngc_image["sharedWithOrgs"][0]
                elif ngc_image["sharedWithTeams"]:
                    repository = ngc_image["sharedWithTeams"][0]
                else:
                    print("NGC IMAGE URL NEW CASE")
                    continue

                name = ngc_image["name"]
                publisher = ngc_image["publisher"]
                ugc_image_name = f"nvcr.io/{repository}/{name}"

                image = {
                    "name": name,
                    "publisher": publisher,
                    "ngc_image_name": ugc_image_name,
                }
                images.append(image)

        if not images :
            raise GetNgcImageError
        return response(status=1, message="OK", result=images)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise GetNgcImageError
    except Exception as e:
        traceback.print_exc()
        raise GetNgcImageError

def get_ngc_image_tag_list(ngc_image_name):
    """
    ngc_image 의 Tag 조회
    ex) ngc_image_name : nvcr.io/nvidia/cuda
    """
    try:
        result = subprocess.check_output([f"ngc registry image info {ngc_image_name} --format_type 'json' || echo ''"], shell=True, stderr=subprocess.PIPE).decode('utf-8').strip()

        # if error: raise GetNgcImageTagError
        ngc_image = json.loads(result)
        if ngc_image["canGuestPull"]:
            images = [
                {
                    "url": f"{ngc_image_name}:{tag}",
                    "tag": tag
                } for tag in ngc_image["tags"]
            ]
        return response(status=1, message="OK", result=images)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise GetNgcImageTagError
    except Exception as e:
        traceback.print_exc()
        raise GetNgcImageTagError

# tag
def get_tag_list(registry=False):
    """tag_list is system images of host machine"""
    try:
        docker_image_list = dict()

        # TODO cluster True를 대체할 방법이 필요함
        cmd = IMAGE_CLI + """ images --digests --format "'{{json .}}'" || echo ''"""
        image_list = subprocess.check_output([cmd], shell=True, stderr=subprocess.PIPE).decode('utf-8').strip()

        data = {"NODE" : image_list}
        for ip, value in data.items():
            docker_image_list[ip] = list()
            if value != "":
                result = value.split('\n')[:-1]
                for item in result:
                    item = json.loads(item.replace("'", ""))
                    docker_image_list[ip].append(item)

        image_list = []
        for ip, values in docker_image_list.items():
            for docker_image in values:
                # registry에 있는 이미지인데 docker url이 없거나, 이미지 이름 none인 것
                if (registry and DOCKER_REGISTRY_URL not in docker_image["Repository"]) \
                or docker_image["Repository"] == "<none>":
                    continue
                image = {
                    "name": docker_image["Repository"] + ':' + docker_image["Tag"],
                    "id": docker_image["ID"],
                    'node_ip' : ip
                }
                image_list.append(image)
        return response(status=1, message="OK", result=image_list)
    except :
        traceback.print_exc()
        raise GetAdminImageError

# comment
def get_image_history(image_id):
    """
    도커 이미지 히스토리를 가져옴
    # docker history에서 제공 하는 것 : IMAGE, CREATED(Created At), CREATED BY, SIZE, COMMENT
    """
    try:
        # return response(status=1, message="OK", result=tmp_data)
        image_info = db_image_msa.get_image_single(image_id)
        image_status = image_info['status']
        real_name = image_info["real_name"]

        # error : 설치되지 않은 이미지
        if image_status != IMAGE_STATUS_READY:
            raise NotExistImageError(image_name=real_name)

        # # GET CONFIG DIGEST
        # tmp = []
        # real_name = image_info.get("real_name")
        # registry = real_name.split('/')[0]
        # tmp_repository = real_name.replace(registry + "/", "").split(":")
        # repository = tmp_repository[0]
        # tag = tmp_repository[1]
        # headers = { "Accept" : "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.index.v1+json"}
        # url = f"http://{registry}/v2/{repository}/manifests/{tag}"

        # response = requests.get(url, headers=headers)
        # if response.status_code == 200:
        #     response_json = response.json()
        #     config_digest = response_json.get('config').get('digest')


        #     # GET METADATA
        #     url = f"http://{registry}/v2/{repository}/blobs/{config_digest}"
        #     response = requests.get(url, headers=headers)

        #     if response.status_code == 200:
        #         response_json = response.json()
        #         history_list = response_json.get('history')

        # # image pull
        INSECURE_REGISTRY=""
        if IMAGE_CLI == "nerdctl" and settings.DOCKER_REGISTRY_PROTOCOL == "http://":
            INSECURE_REGISTRY = "--insecure-registry"

        cmd = f"""{IMAGE_CLI} pull {INSECURE_REGISTRY} {real_name}""" # nerdctl 일 경우, insecure-registry 관련 에러인데 pull은 됨
        result = subprocess.check_output([cmd], shell=True, stderr=subprocess.PIPE).decode('utf-8').strip()

        # image history
        cmd = IMAGE_CLI + """ history {} --format='{{{{json .}}}}'""".format(real_name)
        result = subprocess.check_output([cmd], shell=True, stderr=subprocess.PIPE).decode('utf-8').strip()
        # if result == '':
        #     return response(status=1, message="OK", result=[])

        result = result.split('\n')[:-1]

        res = []
        for tmp in result:
            history = json.loads(tmp)
            if IMAGE_CLI == "docker":
                IMAGE_ID = "ID"
            elif IMAGE_CLI == "nerdctl":
                IMAGE_ID = "Snapshot"

            if '<missing>' not in history[IMAGE_ID]: # docker history에서 <missing> 다음 히스토리만 가져옴 (missing은 commit 부분 아님)
                res.append(
                    {
                        'Image ID': history[IMAGE_ID] ,
                        'CreatedAt': history.get("CreatedSince"), # nerdctl은 createAt 을 가져올수 없음
                        'Comment': history['Comment'],
                        'author' : history['CreatedBy'],
                        'size' : history['Size'],
                    }
                )
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return response(status=0, result=[])
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=[])

# ################################################# 기타 #######################################################

async def get_image_install_log(image_id):
    """
    Description
        docker image 설치하는 로그 파일을 읽어옴
        pull(pull, ngc)인경우, layer 부분 json처럼 내려줌 (json은 아님, 프론트에서 str아니면 에러발생)
    """
    info = db_image_msa.get_image(image_id=image_id)
    try:
        # if info.get("status") == IMAGE_STATUS_READY or info.get("status") == IMAGE_STATUS_FAILED:
        #     return response(status=1, message="OK", result={"log" :["Finish Install"], "status" : info.get("status")})

        data = {
            "count" : 100,
            "imageJobName" : f'{IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{str(info.get("id"))}'
        }
        rquest_logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/image/all", data=data)
        logs = rquest_logs.get("logs")
        res_log = []
        for i in logs:
            try:
                tmp = i.get("fields").get('log')
                if 'does not seem to support HTTPS, falling back to plain HTTP' in tmp:
                    continue
                res_log.append(tmp)
            except:
                pass

        return {"log" : res_log, "status" : info.get("status")}
    except Exception as e:
        traceback.print_exc()
        return {"log" : None, "status" : info.get("status")}

def get_image(image_id):
    try:
        res = None
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT *
                FROM image
                WHERE id = {}
            """.format(image_id)

            cur.execute(sql)
            res = cur.fetchone()

    except Exception as e:
        traceback.print_exc()
        pass
    return res

def get_commit_image_installing_status(tool_id):
    """
    input:
        tool_id : commit한 training tool id
    output:
        True : commit 완료 O
        False : commit 완료 X
    """
    try:
        image_info = db_image_msa.get_installing_commit_image_list(tool_id=tool_id)
        if image_info.get("status") == IMAGE_STATUS_READY:
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc()
        return None


