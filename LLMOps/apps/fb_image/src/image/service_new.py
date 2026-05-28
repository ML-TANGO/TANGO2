import traceback
import subprocess
import sys, os, re, json
from utils import settings, TYPE
from utils.exception.exceptions import *
from utils.msa_db import db_project, db_image, db_node
from utils.common import generate_alphanum, ensure_path, writable_path
from utils.resource import response

from kubernetes import config, client
config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()

# 파일 관련 임포트
import os
import shutil
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


from image.settings import JF_IMAGE_APP_IMAGE, JF_CONTAINER_RUNTIME, JF_CONTAINER_DATA_ROOT

DOCKER_REGISTRY_URL = settings.DOCKER_REGISTRY_URL


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


ROOT_USRE = 1
ACCESS_WORKSPACE = 0
ACCESS_ALL = 1

IMAGE_STATUS_PENDING = 0
IMAGE_STATUS_INSTALLING = 1
IMAGE_STATUS_READY = 2
IMAGE_STATUS_FAILED = 3
IMAGE_STATUS_DELETING = 4

IMAGE_UPLOAD_TYPE_BUILT_IN = 0
IMAGE_UPLOAD_TYPE_PULL = 1
IMAGE_UPLOAD_TYPE_TAR = 2
IMAGE_UPLOAD_TYPE_BUILD = 3
IMAGE_UPLOAD_TYPE_TAG = 4
IMAGE_UPLOAD_TYPE_NGC = 5
IMAGE_UPLOAD_TYPE_COMMIT = 6
IMAGE_UPLOAD_TYPE_COPY = 7



def check_if_name_is_valid(name):
    """도커 이미지 업로드 -> 이름 중복 체크"""
    try:
        if not name:
            raise ValidImageNameEmptyError
        elif db_image.check_if_image_name_exists(image_name=name):
            raise Exception("중복된 이미지 이름이거나, 다른 워크스페이스에서 사용하는 이미지 이름입니다.")
        return True
    except Exception as e:
        raise Exception(str(e))

def check_image_workspace(access, user_id, workspace_id_list):
    try:

        if access == ACCESS_ALL:
            workspace_id_list = []
        else:
            workspace_id_list = [workspace_id_list]
            
        # Permission checking of workspace
        if user_id in db_image.get_admin_user_id_list():
            effective_user_id = None
        else:
            effective_user_id = user_id

        workspace_list = db_image.get_workspace_list(user_id=effective_user_id)
        for workspace_id in workspace_id_list:
            if int(workspace_id) not in [row['id'] for row in workspace_list]:
                # Does not exist or No permission
                # raise ValueError('Workspace of requested id {} does not exist.'.format(workspace_id))
                raise NotExistWorkspaceError(workspace_id=workspace_id)
        return workspace_id_list
    except Exception as e:
        raise Exception(str(e))

def generate_image_tag_name(image_name=None, type_=None, random_str=None):
    """Image create 할 때, real_name 생성"""
    try:
        if random_str is None:
            random_str = generate_alphanum(6)
        name_noescape = re.sub('[^a-zA-Z0-9\-]', '', image_name).lower()
        name_noescape = re.sub('[-]*$', '', name_noescape)
        real_name = DOCKER_REGISTRY_URL + 'jfb/by{}-{}:{}'.format(type_, name_noescape, random_str)
        return real_name
    except Exception as e:
        traceback.print_exc()
        raise e
    
# =======================================================================================

def helm_install_image(command, image_id):
    try:
        os.chdir("/app/helm/")
        subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except Exception as e:
        db_image.update_image_data(image_id=image_id, data={"status": IMAGE_STATUS_FAILED})
        subprocess.check_output([f'helm uninstall -n {settings.JF_SYSTEM_NAMESPACE}-image image-{image_id}'], shell=True, stderr=subprocess.PIPE)
        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg

def create_image(image_name, access, workspace_id_list, user_id, image_type, item=None, description=None,):
    """
    item:
        pull: url
        commit: training_tool_id, message
    """
    image_id = None
    try:
        # CHECK
        check_if_name_is_valid(image_name)
        workspace_id_list = check_image_workspace(access=access, user_id=user_id, workspace_id_list=workspace_id_list)
        
        # info - create image name
        create_image_name = generate_image_tag_name(image_name=image_name, type_=image_type)

        # DB
        image_id = db_image.insert_create_image(user_id=user_id, image_name=image_name, real_name=create_image_name, description=description,
                                                upload_type=TYPE.IMAGE_UPLOAD_TYPE_TO_INT.get(image_type), status=IMAGE_STATUS_INSTALLING,
                                                access=access, file_path=None, upload_filename=json.dumps(item), iid=None)
        if len(workspace_id_list) > 0:
            db_image.insert_image_workspace(image_id, workspace_id_list)
        
        helm_name = TYPE.IMAGE_TYPE_HELM.format(image_type, image_id)
        # HELM command
        command = f"helm install {helm_name} \
                -n {settings.JF_SYSTEM_NAMESPACE}-image --create-namespace \
                --set common.imageId='{image_id}' \
                --set common.imageName='{create_image_name}' \
                --set common.systemRegistryUrl='{settings.SYSTEM_DOCKER_REGISTRY_URL}' \
                --set common.userRegistryUrl='{settings.DOCKER_REGISTRY_URL}' \
                --set common.systemAppImage='{JF_IMAGE_APP_IMAGE}' \
                --set common.systemNamespace='{settings.JF_SYSTEM_NAMESPACE}' \
                --set common.systemContainerRuntime='{JF_CONTAINER_RUNTIME}' \
                --set common.systemContainerDataRoot='{JF_CONTAINER_DATA_ROOT}'  "

        if image_type == "commit":
            # info - job 실행시킬 node
            label_selector = "work_func_type=tool,project_item_id={}".format(item.get("training_tool_id"))
            pod = coreV1Api.list_pod_for_all_namespaces(label_selector=label_selector)
            if 1 > len(pod.items):
                raise Exception("Not existed pod")
            pod_name = pod.items[0].metadata.name
            pod_node_name = pod.items[0].spec.node_name
            
            command += f"--set common.imageType=commit \
                --set commit.nodeName='{pod_node_name}' \
                --set commit.trainingPodName='{pod_name}' \
                --set commit.commitMessage='{item.get('message')}' \
                ./image"
        elif image_type == "pull":
            command += f"--set common.imageType=pull \
                --set pull.pullImageUrl='{item.get('url')}' \
                ./image"
        elif image_type == "ngc":
            command += f"--set common.imageType=ngc \
                --set ngc.pullImageUrl='{item.get('url')}' \
                ./image"
        elif image_type == "copy":
            original_image_id = item.get("image_id")
            original_image_real_name = db_image.get_image(image_id=original_image_id).get("real_name")
            command += f"--set common.imageType=copy \
                --set copy.pullImageUrl='{original_image_real_name}' \
                ./image"
        elif image_type == "tag":
            node_ip = item.get('node_ip')
            node_name = db_image.get_node_name(node_ip=node_ip).get("node_name")
            command += f"--set common.imageType=tag \
                --set tag.nodeName='{node_name}' \
                --set tag.pullImageUrl='{item.get('selected_image_name')}' \
                ./image"
                
        # HELM install
        res, message = helm_install_image(command=command, image_id=image_id)
        if res == True:
            pass # DB 상태 성공 종료
        else:
            db_image.delete_image(image_id=image_id)
            raise Exception(message)
        pass
    except Exception as e:
        if image_id is not None:
            db_image.delete_image(image_id=image_id)
        raise Exception(e)

def create_image_file(image_name, access, workspace_id_list, user_id, image_type, item=None, description=None,):
    """
    item:
        pull: url
        commit: training_tool_id, message
    """
    try:
        # CHECK
        check_if_name_is_valid(image_name)
        workspace_id_list = check_image_workspace(access=access, user_id=user_id, workspace_id_list=workspace_id_list)
        
        # file check
        if image_type == "build" or image_type == "tar":
            file_ = item["file_"]
            file_name = file_.filename.split('/')[-1]
            file_name = secure_filename(file_name)

            try:
                chunk_file_name = item["chunk_file_name"]
            except:
                chunk_file_name = None

            if (not file_name.endswith('.tar') and chunk_file_name is None) and file_name != "Dockerfile":
                raise ValidTypeError
            elif (image_type == "tar" and file_name.endswith('.tar')) or (image_type == "build" and file_name.endswith('.tar')):
                item["save"] = "tar"
            elif file_name == "Dockerfile" and image_type == "build":
                item["save"] = "Dockerfile"
            else:
                raise Exception("Invalid file Error")
        
        # 파일 save
        if item["save"] == "Dockerfile":
            res, message, result = save_file_for_installing_image(type_="build", item=item)
            # parameter = file_parameter_by_build(result)
            parameter = {
                'file_path' : result["file_path"],
                'upload_filename' : result["upload_filename"], 
                'random_str' : result["random_string"]
            }
        # elif type_ == 'tar':
        elif item["save"] == "tar":
            res, message, result = save_file_for_installing_image(type_="tar", item=item)
            if res == True and message == "testing":
                # 대용량 파일 전송시 필요
                # 아직 파일이 완전히 전송되지 않은 경우 message==testing 을 리턴, 완전히 전송 된 경우 message == "OK"
                # print("not end of file")
                return response(status=1, message=message, result=result)            
            # parameter = file_parameter_by_tar(result)
            parameter = {
                'file_path' : result['file_path'],
                'upload_filename' : result['upload_filename'],
                'random_str' : result['random_string']
            }

        file_path = parameter['file_path']
        upload_filename = parameter['upload_filename']
        random_str = parameter['random_str']
        
        # info - create image name
        create_image_name = generate_image_tag_name(image_name=image_name, type_=image_type)

        # DB
        image_id = db_image.insert_create_image(user_id=user_id, image_name=image_name, real_name=create_image_name, description=description,
                                                upload_type=TYPE.IMAGE_UPLOAD_TYPE_TO_INT.get(image_type), status=IMAGE_STATUS_INSTALLING,
                                                access=access, file_path=None, upload_filename=None, iid=None)
        if len(workspace_id_list) > 0:
            db_image.insert_image_workspace(image_id, workspace_id_list)
        
        helm_name = TYPE.IMAGE_TYPE_HELM.format(image_type, image_id)
        # HELM command
        command = f"helm install {helm_name} \
                -n {settings.JF_SYSTEM_NAMESPACE}-image --create-namespace \
                --set common.imageId='{image_id}' \
                --set common.imageName='{create_image_name}' \
                --set common.systemRegistryUrl='{settings.SYSTEM_DOCKER_REGISTRY_URL}' \
                --set common.userRegistryUrl='{settings.DOCKER_REGISTRY_URL}' \
                --set common.systemAppImage='{JF_IMAGE_APP_IMAGE}' \
                --set common.systemNamespace='{settings.JF_SYSTEM_NAMESPACE}' \
                --set common.systemContainerRuntime='{JF_CONTAINER_RUNTIME}' \
                --set common.systemContainerDataRoot='{JF_CONTAINER_DATA_ROOT}'  "

        if image_type == "build":
            command += f"--set common.imageType=build \
                --set build.filePath='{file_path}' \
                ./image"
        elif image_type == "tar":
            command += f"--set common.imageType=tar \
                --set tar.filePath='{file_path}' \
                ./image"

        print(command)
        # HELM install
        res, message = helm_install_image(command=command, image_id=image_id)
        if res == True:
            pass # DB 상태 성공 종료
        else:
            db_image.delete_image(image_id=image_id)
            raise Exception(message)

        return response(status=1, message="OK", result=result)    
    except Exception as e:
        db_image.delete_image(image_id=image_id)
        raise Exception(e)

def save_file_for_installing_image(type_, item):
    """이미지 생성: dockerfile build, tar 방식일때 파일 업로드"""
    try:
        # 업로드 파일명
        '''
        https://werkzeug.palletsprojects.com/en/2.0.x/datastructures/#werkzeug.datastructures.FileStorage

        example
        file_                   : <FileStorage: 'Dockerfile' ('application/octet-stream')>
        file_.filename(파일종류) : Dockerfile
        file_.content_type     : application/octet-stream
        file_.headers          : Content-Disposition: form-data; name="file"; filename="Dockerfile"
        '''
        #-------------------------------------------------------------------------------------------
        # if type_ == "tar":
        if item["save"] == "tar":
            chunk_file_name = item['chunk_file_name']
            end_of_file = item['end_of_file']
        # elif type_ == "build":
        elif item["save"] == "Dockerfile":
            chunk_file_name = None
        
        file_ = item['file_']
        upload_filename = file_.filename
        file_name = file_.filename.split('/')[-1]
        file_name = secure_filename(file_name)

        #-------------------------------------------------------------------------------------------
        # jf-data/tmp
        #-------------------------------------------------------------------------------------------
        '''
        ensure_path : 보안체크
        writable_path : 임시 경로로 write 테스트
        while문 : 임의의 문자를 넣어 파일 저장
        경로 : 파일 저장(도커) /jf-data/images, 이미지 빌드(호스트) /jfbcore/jf-data/images
        '''
        upload_dir = '/jf-data/images' # settings.JF_UPLOAD_DIR
        upload_dir += '/dockerfile' if item['save'] =='Dockerfile' else '/tar'
        
        # TODO MSA
        ensure_path(upload_dir)
        if not writable_path(upload_dir):
            raise WritablePathError(path=upload_dir)
        
        if item["save"] == "Dockerfile":
            while True:
                random_str_temp = generate_alphanum(6)
                file_path_temp = upload_dir + '/{}.Dockerfile'.format(random_str_temp)
                if not os.path.exists(file_path_temp):
                    break
            file_.save(file_path_temp, buffer_size=16*1024)
        elif item["save"] == "tar":
            if chunk_file_name is None:
                # 처음에만 호출되고, temp 경로가 정해지면 chunk_file_name에 값이 담겨 이부분을 호출하지 않음
                while 1:
                    random_str_temp = generate_alphanum(6)
                    file_path_temp = upload_dir + '/{}.tar'.format(random_str_temp)
                    if not os.path.exists(file_path_temp):
                    # 존재하지 않으면, while문 나와서 file_path_temp 사용, 존재하면 다시 경로 생성
                        break
            else:
                random_str_temp = chunk_file_name
                file_path_temp = upload_dir + '/{}.tar'.format(random_str_temp)

            # 파일 write
            with open(file_path_temp, "ab") as fw:
                fw.write(file_.read())

            # 대용량 파일 전송시 front에서 파일을 잘라서 전송함, 아직 마지막까지 전달이 안된 경우 message=="testing", chunk_file_name을 리턴
            if not end_of_file:
                return True, "testing", {"chunk_file_name" : random_str_temp}

        #-------------------------------------------------------------------------------------------
        # check the dockerfile in tar if type == build && file == tarfile
        if type_ == "build" and item["save"] == "tar":
            try:
                # tar tvf {path} Dockerfile로 찾지 못하는 경우가 있음 && 압축해제시 폴더가 생성되면 안되고 바로 파일들이 풀려야함 (Dockerfile 최상위)
                command = """tar tvf {} | grep Dockerfile | awk '{{ print $6 }}'""".format(file_path_temp)
                output = subprocess.check_output(command , shell=True, stderr=subprocess.STDOUT).strip().decode()
                tmp_output_list = output.split('\n')

                if "No such" in output:
                    raise SaveFileForImageError(message=output)
                elif len(tmp_output_list) >= 2:
                    """Dockerfile, Dockerfile.xxx 같이 있는 경우
                    -> 'Dockerfile'을 기준으로 빌드
                    'Dockerfile' 은 없고 'Dockerfile.xxx' 만 있는 경우
                    -> Dockerfile.xxx 파일이 하나이면, 빌드
                    -> 여러개인 경우 에러
                    """
                    for i in tmp_output_list:
                        if i.split("/")[-1] == "Dockerfile":
                            dockerfile_path = i
                            break
                    else:
                        raise SaveFileForImageError(message="file named 'Dockerfile' must have only one")
                else:
                    dockerfile_path = output
            except subprocess.CalledProcessError as e:
                print("e->", e.output.decode('utf-8'))
                traceback.print_exc()
                raise SaveFileForImageError(message=e.output.decode('utf-8'))

        #-------------------------------------------------------------------------------------------
        # jf-data/images
        #-------------------------------------------------------------------------------------------
        '''
        BASE_DOCKERFILE_PATH = '/jf-data/images' # in docker
        DOCKERFILE_PATH_SKEL = 'dockerfile/{random_str}/Dockerfile'  # relative path for db store
        DOCKERFILE_FULL_PATH_SKEL = BASE_DOCKERFILE_PATH + '/' + DOCKERFILE_PATH_SKEL
        -> file_path + '/' + file_fullpath = '/jf-data/images' + '/' + 'dockerfile/RblLnf/Dockerfile'
        -> path : file_path에서 Dockerfile 빠진 것
        
        # MSA 전환 후 host 가 아닌 pod 안에서 처리
        '''
        
        print(type_)
        random_string = generate_alphanum(6)
        if type_ == "build":
            global DOCKERFILE_PATH_SKEL
            if item["save"] == "tar":
                DOCKERFILE_PATH_SKEL = 'dockerfile/{random_str}.tar'
            file_path = DOCKERFILE_PATH_SKEL.format(random_str=random_string)
            file_fullpath = BASE_DOCKERFILE_PATH + '/' + file_path
            print("*****************")
            print(file_fullpath)
        elif type_ == "tar":
            file_path = IMAGE_PATH_SKEL.format(random_str=random_string)
            file_fullpath = BASE_IMAGE_PATH + '/' + file_path


        path = os.path.dirname(file_fullpath)
        ensure_path(path)
        if not writable_path(path):
            raise WritablePathError(path=path)
        shutil.move(file_path_temp, file_fullpath)

        #-------------------------------------------------------------------------------------------
        # revise file_path (tar path + dockerfile path) if type == build && file == tarfile
        if type_ == "build" and item["save"] == "tar":
            file_path = file_path + "/" + dockerfile_path
            file_path = file_path.replace("/.", "") # Dockerfile이 최상위일 경우 dockerfile/abc.tar/./Dockerfile 이렇게 됨

        return True, "OK", {"upload_filename": upload_filename, "file_path": file_path, "random_string": random_string}
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        raise SaveFileForImageError