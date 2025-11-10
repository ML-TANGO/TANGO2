#-*- coding:utf-8 -*-
from utils.resource import response
# import utils.db as db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_workspace as ws_db
from utils.msa_db import db_user as user_db 
from utils.msa_db import db_storage as storage_db
import utils.crypt as cryptUtil
from utils.exception.exceptions import *
from utils.common import *
from utils.access_check import *
from utils import TYPE
from shutil import *
from pathlib import Path, PurePath
from utils.PATH import JF_DATA_DATASET_PATH
# from utils.lock import jf_dataset_lock
import subprocess
import os
import fnmatch
import traceback
from datetime import datetime 
import tarfile
import zipfile
from PIL import Image
import io
import requests
import urllib
from upload.service import upload_data
from pwd import getpwuid
from utils.redis_key import DATASET_PROGRESS, DATASET_STORAGE_USAGE, DATASET_FILEBROWSER_POD_STATUS, DATASET_UPLOADSIZE, DATASET_UPLOAD_LOCK, DATASET_DUPLICATE, DATASET_UPLOAD_LIST
from utils.redis import get_redis_client

from helm_run import create_decompress_job, delete_helm, filebrowser_run
from utils.access_check import check_dataset_access_level
from utils.common import get_own_user, format_size
import hashlib
from functools import lru_cache, cache

redis = get_redis_client()
#def create_dataset_base_dir()

def create_dataset(body,headers_user):
    """ 
        Dataset 생성 요청을 upload_method에 따라 알맞는 fuction 호출하고
        경로를 리턴 받았을 경우 DB에 insert해주는 함수
        ---
        # Arguments
            headers_user : User name
            body : 
            {
                dataset_name(str): 데이터셋 이름
                workspace_id(int): Workspace ID값
                access(int): 읽기쓰기 or 읽기
                description(str): 설명 
            }
        # Returns:
            status = 1(True) or 0(False)
            message = API에서 보내는 메세지
    """
    try:
        # headers_user = headers_user.check_user()
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        dataset_dir = None

        # dataset_lists = dataset_db.get_dataset_name_list(workspace_id=body['workspace_id'])
        if dataset_db.get_dataset(dataset_name=body['dataset_name'],workspace_id=body['workspace_id']) is not None:
            raise Exception("Already Exists Dataset")
        
        # if body['dataset_name'] in dataset_lists:
        #     return response(status = 0, message = "Exists dataset")

        workspace_info = ws_db.get_workspace(workspace_id=body['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'],
                                             WORKSPACE_NAME=workspace_info['name'],
                                             ACCESS=body['access'],
                                             DATASET_NAME=body['dataset_name']))

        if not dataset_dir.exists():
            # result = make_dir(dataset_dir,headers_user) #,headers_user
            dataset_dir.mkdir(parents=True,exist_ok=True)
        
        res = dataset_db.insert_dataset(
            name = body['dataset_name'],
            workspace_id = body['workspace_id'],
            create_user_id = user_id, 
            access = body['access'],
            description=body["description"])
        print(res)
        # db.logging_history(user="root", task="dataset", action="create", workspace_id=body['workspace_id'], task_name=body['dataset_name'], update_details='create dataset')
        return res
    except Exception as e:
        try:
            if dataset_dir is not None:
                os.system('rm -rf {}'.format(dataset_dir))
        except:
            traceback.print_exc()
        raise e
        #print(e.response())
        # return response(status = 0, result =e.response())

## front화면에서 datasets를 누르면 나오는 화면에 dataset들을 출력해주는 함수
#@cache
def get_datasets(workspace_id=None, page=None, size=None, search_key=None, search_value=None, headers_user=None):
    try :
        global redis
        if headers_user is None:
            return response(status=0, message="Jf-user is None in headers")
        user_info = user_db.get_user_id(headers_user)
        user_id = 1 if user_info['id'] is None else user_info['id']

        dataset_lists = dataset_db.get_dataset_list(workspace_id=workspace_id, user_id=user_id, search_key=search_key,search_value=search_value, user_type=user_info['user_type'] )
        dataset_list_len= len(dataset_lists)
        current_time = datetime.now()
        if dataset_lists is None:
            reval = {'list' : [], 'total' : 0 }
        else:
            # if page is not None and size is not None:
            #     start_num = (page-1)*size
            #     end_num = page * size
            #     dataset_lists = dataset_lists[start_num:end_num]

            for dataset in dataset_lists:
                try:
                    # TODO
                    # 학습, 전처리기, 수집기에서 사용중인 데이터셋인지 확인
                    # 학습 
                    prepro_tools = dataset_db.get_dataset_used_item_tools_list(dataset_id=dataset["id"], item_type=TYPE.PREPROCESSING_TYPE)
                    prepro_jobs = dataset_db.get_dataset_used_preprocessing_jobs_list(dataset_id=dataset["id"])
                    project_tools = dataset_db.get_dataset_used_item_tools_list(dataset_id=dataset["id"], item_type=TYPE.PROJECT_TYPE)
                    project_jobs = dataset_db.get_dataset_used_project_jobs_list(dataset_id=dataset["id"])
                    # project_hps = dataset_db.get_dataset_used_project_hps_list(dataset_id=dataset["id"])
                    
                    dataset_used_pods = prepro_tools + prepro_jobs + project_tools + project_jobs # + project_hps

                    if dataset_used_pods:
                        raise Exception("해당 데이터셋을 사용중입니다.")


                    dataset['permission_level'] = check_dataset_access_level(user_id=user_id, access_check_info=dataset)
                    dataset['modify_time'] = int((current_time - datetime.strptime(dataset['modify_datetime'],'%Y-%m-%d %H:%M:%S')).total_seconds()*0.016)
                    dataset['update_time'] = int((current_time - datetime.strptime(dataset['update_datetime'],'%Y-%m-%d %H:%M:%S')).total_seconds()*0.016)
                    dataset['size'] = int(redis.hget(DATASET_STORAGE_USAGE, dataset['id']))
                except Exception as e:
                    # traceback.print_exc()
                    print("dataset_error\n\n")
                    print(e)
                    dataset['permission_level'] = check_dataset_access_level(user_id=user_id, access_check_info=dataset)
                    dataset['modify_time'] = None
                    dataset['update_time'] = None
                    dataset['size'] = None
            reval = {'list' : dataset_lists, 'total' : dataset_list_len }
        return reval
    except:
        traceback.print_exc()
        return False

#@cache
def check_file(dataset_id, user_id, path : Path, search_path=None, search_page=1, search_size=10, search_type=None, search_key=None, search_value="", sort_type="name", reverse=False):
    global redis
    dataset_file_list = []
    try:
        data_path = path
        support_extension = ['.txt','.jpg','.jpeg','.png','.csv','.json','.md']

        if search_path is not None:
            data_path = path.joinpath(search_path)
        current_path_progress_list=[]
        progress_list=None
        # print(progress_list)
        # if search_page == 1:
        # redis.delete(DATASET_PROGRESS.format(dataset_id=dataset_id))
        # redis.delete(DATASET_UPLOADSIZE.format(dataset_id=dataset_id))
        progress_list = redis.hgetall(DATASET_PROGRESS.format(dataset_id=dataset_id))
        # for item,_ in progress_list.items():
        #     if path.joinpath(item).parent.name == data_path.name:
        #         current_path_progress_list.append(item)
                # print(value)
        #     current_path_progress_list.sort(reverse=True)
        # print(f"{dataset_id} : {progress_list}")
        if sort_type == "size":
            if reverse:
                data_list = list(filter(len,subprocess.run(['ls','-Sr', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))
            else:
                data_list = list(filter(len,subprocess.run(['ls','-S', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))
        elif sort_type == "update":
            if reverse:
                data_list = list(filter(len,subprocess.run(['ls','-tr', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))
            else:
                data_list = list(filter(len,subprocess.run(['ls','-t', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))
        else:
            if reverse:
                data_list = list(filter(len,subprocess.run(['ls','-r', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))
            else:
                data_list = list(filter(len,subprocess.run(['ls', f"{data_path}"], capture_output=True, text=True).stdout.split('\n')))

        # for item in current_path_progress_list:
        #     try:
        #         data_list.remove(item)
        #     except:
        #         pass
        # print(data_list)
        # print(data_list)
        file_list=[]
        dir_list=[]
        for data in data_list:
            data = data_path.joinpath(data)
            if data.is_file():
                file_list.append(data.name)
            else:
                dir_list.append(data.name)
        if search_type == 'all':
            tmp_file_list = dir_list+file_list
        elif search_type == 'dir':
            tmp_file_list = dir_list
        else:
            tmp_file_list = file_list
        # tmp_file_list = current_path_progress_list + tmp_file_list
        if search_value != "" :
            tmp_file_list=[data for data in tmp_file_list if search_value in str(data)]
            
        file_count = len(tmp_file_list)
        # search_size = -1
        if search_size == -1 :
            start_num = 0
            end_num = file_count
        else :
            start_num = (search_page-1)*search_size
            end_num = search_page * search_size
        
        # print(f"{dataset_id} : {progress_list}")
        #check search key, value
        for item in tmp_file_list[start_num:end_num]: 
            # print(item)
            data = data_path.joinpath(item)

            if data.exists():
                is_preview = False
                data_metadata = data.stat()
                if search_path is None:
                    redis_sub_key = item
                else:
                    redis_sub_key = search_path+"/"+item
                if progress_list:
                    upload_info = progress_list.get(redis_sub_key,None)
                    # print(upload_info)
                    # print(upload_info)
                    if upload_info is not None:
                        upload_info =json.loads(upload_info)
                        if upload_info['status']=="running":
                            if upload_info.get('progress'):
                                if upload_info['progress'] == 100 or upload_info['upload_size'] >= upload_info['total_size'] :
                                    upload_info['complete']=True
                                    redis.hset(DATASET_PROGRESS.format(dataset_id=dataset_id),redis_sub_key,json.dumps(upload_info))               
                        if upload_info['type'] == "size":
                            upload_info['upload_size'] = format_size(upload_info['upload_size'])
                            upload_info['total_size'] = format_size(upload_info['total_size'])
                else:
                    upload_info = None

                if data_metadata.st_uid == 0:
                    owner='root'
                else:
                    owner=get_own_user(uuid=data_metadata.st_uid)

                if data.is_dir():
                    type_ = 'dir'
                    search_path_size = 0
                else: #preview를 지원하는 확장자인지 구분
                    type_ = 'file'
                    file_ext = data.suffix
                    file_ext = file_ext.lower()
                    if file_ext in support_extension :
                        is_preview = True
                    search_path_size = data_metadata.st_size
                modified_timestamp = data_metadata.st_ctime
                modified = datetime.fromtimestamp(modified_timestamp).strftime('%Y-%m-%d %H:%M:%S')

                dataset_file_list.append({'type':type_, 'name':data.name, 'size': search_path_size,
                                        'modifier': owner, 'modified':modified, 'is_preview':is_preview, 'upload_info' : upload_info})
            else:
                # if search_path is None:
                #     redis_sub_key = item
                # else:
                #     redis_sub_key = search_path+"/"+item
                # redis.hdel(DATASET_PROGRESS.format(dataset_id=dataset_id),redis_sub_key)
                end_num+=1
    except:
        dataset_file_list = []
        file_count = 0
        # print(dataset_id)
        traceback.print_exc()
    return dataset_file_list,  file_count

#dataset의 파일목록 확인
#@cache
def get_dataset_files(dataset_id, search_path=None, search_page=1, search_size=10, search_type=None, search_key=None, search_value=None, headers_user=None, sort_type="name", reverse=False):
    try:
        user_info = user_db.get_user_id(headers_user)
        user_id = user_info['id']
        dataset_dir_info = dataset_db.get_dataset(dataset_id)

        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        path = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=dataset_dir_info['workspace_name'], ACCESS=dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        #workspace_name = dataset_dir_info['workspace_name'], access = dataset_dir_info['access'], dataset_name = dataset_dir_info['name'] + search_path
        
        result = {}
        dataset_file_list, file_count = check_file(dataset_id, user_id, path, search_path, search_page, search_size, search_type, search_key, search_value, sort_type, reverse)
        result['list'] = dataset_file_list
        result['file_count'] = file_count
        return response(status = 1, result = result)
    except:
        traceback.print_exc()
        return response(status = 0, message = "Get dataset files Error")


def make_empty_dir(body, headers_user):
    try:
        print("make directory")
        user_info = user_db.get_user_id(headers_user)
        user_id = user_info['id']
        dataset_dir_info = dataset_db.get_dataset(body['dataset_id'])
        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])

        if is_good_data_name(body['dir_name']) is None :
            return response(status = 0, message = 'Invalid dataset name "{}"'.format(body['dir_name']))

        # 필요없는 예외처리
        # workspace_info = db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        # if workspace_info is None:
        #     return response( status = 0, message = 'not exists workspace')

        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        if body['path'] is None:
            dataset_dir = dataset_dir.joinpath(body['dir_name'])
        else:
            dataset_dir = dataset_dir.joinpath(body['path'],body['dir_name'])

        
        dataset_dir.mkdir(parents=True, exist_ok=True) #return value None and Error occurs is Exception object
        change_own(dataset_dir,headers_user)
        return response(status = 1, message = "Create folder Succeed")
    except:
        try:
            os.system('rm -rf {}'.format(dataset_dir))
        except:
            traceback.print_exc()
        traceback.print_exc()
        return response(status = 0, message = "Create folder Error")
    
def handle_data(body,headers_user):
    user_info = user_db.get_user_id(headers_user)
    user_id = user_info['id']
    dataset_dir_info = dataset_db.get_dataset(body.dataset_id)
    workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
    storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
    dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
    target_path=dataset_dir
    destination_path=dataset_dir

    for item in body.items: #.split(","):
        if body.target_path is not  None:
            target_path=dataset_dir.joinpath(body.target_path)
        if body.destination_path is not None:
            destination_path=dataset_dir.joinpath(body.destination_path)
        destination_path = duplicate_check(target_path, destination_path ,item)

        if body.is_copy:
            shutil.copy2(target_path.joinpath(item), destination_path)
        else:
            shutil.move(target_path.joinpath(item), destination_path)
    return response(status = 1, message = "data handle Success")

def duplicate_check(target : Path, destination : Path, name):
    target_path=target.joinpath(name)
    if target_path.is_file():
        destination_path = destination.joinpath(name)            
        if destination_path.exists():
            file_name,file_Extension = os.path.splitext(name)
            num_file = len(list(destination.glob(f"{file_name}*{file_Extension}")))
            destination_path = destination.joinpath(file_name+'_'+str(num_file)+file_Extension)
            while True:
                if not destination_path.exists():
                    break
                num_file += 1
                destination_path = destination.joinpath(file_name+'_'+str(num_file)+file_Extension)
            
        return destination_path
    #folder
    else:
        destination_path = destination.joinpath(name)
        if os.path.exists(destination_path):
            num_folder = 1
            destination_path= destination.joinpath(name+'_'+str(num_folder))
            while True:
                if not destination_path.exists():
                    break
                num_folder += 1
                destination_path= destination.joinpath(name+'_'+str(num_folder))
        return destination_path

#@cache
def get_dataset_info(dataset_id, user_id):
    try:
        global redis
        dataset_dir_info = dataset_db.get_dataset(dataset_id)
        dataset_dir_info['permission_level']=check_dataset_access_level(user_id=user_id, access_check_info=dataset_dir_info)
        try:
            dataset_dir_info['size'] = int(redis.hget(DATASET_STORAGE_USAGE, dataset_id))
        except:
            dataset_dir_info['size'] = 0 

        # DB 기준으로 먼저 확인
        if dataset_dir_info.get('filebrowser') == 0:
            dataset_dir_info['filebrowser'] = None
        else:
            # DB가 1이면 Redis에서 세부 상태 확인
            filebrowser=redis.hget(DATASET_FILEBROWSER_POD_STATUS, dataset_id)
            if filebrowser is not None:
                try:
                    filebrowser_data = json.loads(filebrowser)
                    pod_status = filebrowser_data.get('pod_status', 'pending')
                    dataset_dir_info['filebrowser'] = pod_status
                except json.JSONDecodeError:
                    # Redis JSON이 잘못된 경우 기본값 반환
                    dataset_dir_info['filebrowser'] = 'pending'
            else:
                # Redis에 상태 정보가 없으면 기본값 반환 (설치 중일 가능성)
                dataset_dir_info['filebrowser'] = 'pending'
        return response(status = 1, result = dataset_dir_info)
    except:
        traceback.print_exc()
        return response(status = 0, message = "Get dataset directory Error")
            
def update_dataset_info(body,headers_user):
    try:
        """ 
            Dataset 정보 변경
            body로 들어온 argument들을 기존 db에 있는 정보들과 비교해서
            변경된 값을을 db에 업데이트 하고 workspace level의 history에 기록
            ---
            # Arguments
                headers_user : User name
                body : 
                {
                    dataset_name : 변경하거나 변경되지 않은 데이터셋 이름
                    workspace_id : 변경하거나 변경되지 않은 workspace id 값
                    access : 변경하거나 변경되지 않은 access 값
                    description : 변경하거나 변경되지 않은 데이터셋에 관한 설명
                    dataset_id : 변경되지 않는 데이터셋 ID값(Unique key)
                }
                

            # Returns:
                status(int) : 0(실패), 1(성공)
                message : API에서 보내는 메세지
                    
                example :
                {
                    "message": "OK"
                    "result": null
                    "status": 1
                }
        """        
        import copy
        print("dataset_info_update")
        dataset_dir_info = dataset_db.get_dataset(body['dataset_id'])
        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        
        path_change = False
        change_dataset_info = copy.deepcopy(dataset_dir_info)
        log_desc_arr = []
        #print(org_dataset_info)
        if body['dataset_name']!= dataset_dir_info['name'] :
            path_change=True
            change_dataset_info['name'] = body['dataset_name']
            if not is_good_data_name(body['dataset_name']):
                return response(status = 0, message = 'Invalid dataset name {}'.format(body['dataset_name']))
            # Check for duplicate dataset name
            if dataset_db.get_dataset(dataset_name=body['dataset_name'], workspace_id=body['workspace_id']) is not None:
                return response(status = 0, message = "Already Exists Dataset")
            log_desc_arr.append('Dataset Name change to "{}"'.format(body['dataset_name']))
            

        if body['workspace_id']!= dataset_dir_info['workspace_id'] :
            path_change=True
            change_dataset_info['workspace_id'] = body['workspace_id']
            change_dataset_info['workspace_name'] = ws_db.get_workspace(workspace_id=body['workspace_id'])['workspace_name']
            log_desc_arr.append('Workspace change to "{}"'.format(change_dataset_info['workspace_name']))

        if body['access']!= dataset_dir_info['access']:
            path_change=True
            change_dataset_info['access'] = body['access']
            log_desc_arr.append('Access Type change')
        
        print(body)
        if body['description'] != dataset_dir_info['description']:
            log_desc_arr.append('description change')
            if body['description'] is None:
                body['description']=" "

        target_path = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        destination_path = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= change_dataset_info['access'], DATASET_NAME=change_dataset_info['name']))
        dataset_dir_info['name']=change_dataset_info['name']
        dataset_dir_info['access']=change_dataset_info['access']
        shutil.move(target_path, destination_path)
        
        result = dataset_db.update_dataset(id=body['dataset_id'],
                                    name=dataset_dir_info['name'],
                                    workspace_id=body['workspace_id'],
                                    access=dataset_dir_info['access'],
                                    description=body["description"]
                                    )
        
        # if result :
        #     db.logging_history(
        #         user=headers_user, task='dataset',
        #         action='update', workspace_id=dataset_dir_info['workspace_id'],
        #         task_name=workspace_info['name'], update_details='/'.join(log_desc_arr)
        #         )
        return response(status = 1, message = 'complete dataset info update')
    except:
        traceback.print_exc()
        return response(status = 0, message = "dataset info Update Error")


def get_dir_size(search_path='.'):
    total_size = 0
    total_size = int(subprocess.run(['du -cb {} | grep total'.format(search_path)],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8').stdout.split('total')[0])
    return total_size 

#TODO DB에서 불러오는게 더 빠를수있음.
#@cache
def get_dataset_name_list(workspace_id):
    dataset_lists = dataset_db.get_dataset_list(workspace_id=workspace_id)
    dataset_name_list=[]
    for dataset in dataset_lists:
        dataset_name_list.append(dataset['dataset_name'])
    return dataset_name_list

def remove_dataset(id_list, headers_user, headers_user_id=None):
    print("remove dataset funtion")
    try:
        global redis
        d_id_list = id_list.split(',')

        for id_str in d_id_list :
            dataset_info = dataset_db.get_dataset(id_str)
            workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
            storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        
            if dataset_db.delete_dataset(id_str):
                
                delete_dataset_list = []
                dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=dataset_info['workspace_name'], ACCESS=dataset_info['access'], DATASET_NAME=dataset_info['name']))
                shutil.rmtree(dataset_dir)
                delete_dataset_list.append(dataset_info['name'])
                redis.delete(DATASET_PROGRESS.format(dataset_id=id_str))
                redis.delete(DATASET_UPLOADSIZE.format(dataset_id=id_str))
                namespace = os.getenv("JF_SYSTEM_NAMESPACE")
                # ws_namespace=f"{namespace}-{workspace_info['id']}"
                filebrowser_name = f"filebrowser-{id_str}"
                delete_helm(helm_name=filebrowser_name, namespace=namespace)
                # for dataset_item in delete_dataset_list:
                    # db.logging_history(
                    #     user=headers_user, task="dataset", 
                    #     action="delete", workspace_id=dataset_info['workspace_id'], 
                    #     task_name=dataset_item
                    # )
            else:
                return response(status = 0, message = 'Failed to delete dataset in DB')
        return response(status = 1, message = 'Remove dataset')
    except:
        traceback.print_exc()
        return response(status = 0, message = "Remove dataset Error")

#@cache
def preview(body, headers_user = None):
    try:
        print(body)
        print('preview funtion')
        if headers_user is None:
            return response(status = 0, message = "Jf-user is None in headers")
        user_info = user_db.get_user_id(headers_user)
        user_id = user_info['id']
        exel_ext = ['.csv']
        img_ext = ['.jpg','.jpeg','.png']
        encodings = ['utf-8', 'euc_kr', 'cp949','windows-1252','iso-8859-1','gb2312','gb18030']
        dataset_dir_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        
        if body.path is None:
            dataset_dir= dataset_dir.joinpath(body.file_name)
        else:
            dataset_dir= dataset_dir.joinpath(body.path, body.file_name)
        file_ext = dataset_dir.suffix
        file_ext = file_ext.lower()
        if file_ext == '.txt' :
            print('this is text file')
            try:
                with open(dataset_dir, "r", encoding ='utf-8') as file_ : 
                    text = file_.read()
            except:
                with open(dataset_dir, "r", encoding ='euc_kr') as file_ :
                    text = file_.read()
            output = { 'data' : text, 'type' : 'text'}
            return response(status = 1, result = output)
        elif file_ext =='.md' :
            try:
                with open(dataset_dir, "r", encoding ='utf-8') as file_ : 
                    text = file_.read()
            except:
                with open(dataset_dir, "r", encoding ='euc_kr') as file_ :
                    text = file_.read()
            output = { 'data' : text, 'type' : 'markdown'}
            return response(status = 1, result = output)
        elif file_ext in img_ext :
            print('this is image file')
            with Image.open(dataset_dir, mode='r') as img:
                #if img.mode in ("RGBA", "P", "LA"): img = img.convert("RGB")
                img_byte_arr = io.BytesIO()
                if img.format == "PNG" :
                    img.save(img_byte_arr, format='png')
                else:
                    img.save(img_byte_arr, format='jpeg')
                img = base64.encodebytes(img_byte_arr.getvalue()).decode()
            output = { 'data' : img, 'type' : 'image'}
            return response(status = 1, result = output)
        
    
        elif file_ext in exel_ext : 
            print('this is csv file')
            try:
                with open(dataset_dir, "r", encoding ='utf-8') as file_ : 
                    text = file_.read()
            except:
                with open(dataset_dir, "r", encoding ='euc_kr') as file_ :
                    text = file_.read()
            #text = file_.read()
            output = { 'data' : text, 'type' : 'text'}
            return response(status = 1, result = output)
        
        elif file_ext in '.json' :
            print('this is json file')
            json_data = []
            
            #json_data = [json.loads(line) for line in open(os.path.join(path,body['file_name']), 'r')]
            
            try:
                with open(dataset_dir, "r") as file_ :
                    json_data = json.load(file_)
                    output = { 'data' : json_data, 'type' : 'json'}
            except:
                with open(dataset_dir, "r") as file_ : 
                    json_data = file_.read()
                    output = { 'data' : json_data, 'type' : 'text'}
            
            return response(status = 1, result = output)

        else:
            return response(status = 0, message = "This extension is not supported.")
        # elif file_ext == '.mp4' :
        #     print('this is video file')
        #     os.system('pip install --upgrade pip')
        #     os.system('pip install opencv-python')
            
        #     import cv2
        #     vidcap = cv2.VideoCapture(os.path.join(path,body['file_name']))
        #     img_list=[]
        #     count = 0
        #     preview_path = '/jf-data/preview'
        #     if not os.path.isdir(preview_path) :
        #         os.system('mkdir -p {}'.format(preview_path))
        #     while(vidcap.isOpened()):
        #         ret, img = vidcap.read()
        #         #if(int(vidcap.get(1)) % 20 == 0):
        #         if img is None:
        #             break
        #         cv2.imwrite("/jf-data/preview/frame%d.jpg" % count, img)
        #         #print('Saved frame%d.jpg' % count)
                
        #         img = Image.open(os.path.join(preview_path,"frame%d.jpg" % count), mode='r')
        #         img_byte_arr = io.BytesIO()
        #         img.save(img_byte_arr, format='jpeg')
        #         img = base64.encodebytes(img_byte_arr.getvalue()).decode()
        #         img_list.append(img)
        #         os.system('rm {}'.format(os.path.join(preview_path,"frame%d.jpg" % count)))
        #         count += 1
        #     vidcap.release()
        #     print('read video complete')
        #     output = { 'data' : img_list, 'type' : 'video'}
        #     return response(status = 1, result = output)
        # elif file_ext == '.mp4' :
        #     with open(os.path.join(path,body['file_name']), "rb") as videoFile:
        #         video_content = videoFile.read()
        #         video_content = base64.b64encode(video_content)
                
        #         #result = json.load(video_content)
        #         #result = DatatypeConverter.printBase64Binary
        #         print(video_content)
        #     output = { 'data' : video_content, 'type' : 'video'}
        #     return response(status = 1, result = output)
    except Exception as e:
        traceback.print_exc()
        return response(status = 0, message = "dataset preview Error")

def name_filter(name):
    return name.replace('&','_').replace('(','_').replace(')','_').replace(' ','_').replace('#','_').replace('$','_').replace('%','_').replace('[','').replace(']','')

# def scan_workspace(workspace_ids, check = True):
#     """ 
#         데이터셋 목록을 DB와 File system을 비교하는 함수 
#         ---
#         # Arguments
#             body : 
#             {
#                 workspace_ids(list): 비교할 workspace들의 ID값
#                 check(bool): 파일갯수를 count 여부를 결정하는 Flag
#             }
#         # Returns:
#             None
#     """
#     print("scan workspace")
#     try:
#         for workspace_id in workspace_ids:
#             # get dataset_info in db
#             # res_db_datasets = dataset_db.get_dataset_list(workspace_id=workspace_id)
#             db_datasets = {}
#             # for res_db_dataset in res_db_datasets:
#                 # db_datasets[res_db_dataset['inode_number']] = res_db_dataset
#             workspace_name = (db.get_workspace(workspace_id = workspace_id))['workspace_name']
#             for access in ['0', '1']:
#                 path = '{}/{}/datasets/{}'.format(JF_WS_DIR, workspace_name, access)
#                 print(path)
#                 if not os.path.exists(path):
#                     continue
#                 for name in os.listdir(path):
#                     if '.ipynb_checkpoints' in name:
#                         continue
#                     full_path = os.path.join(path, name)
#                     print(full_path)
#                     if os.path.isdir(full_path):
#                         # _stat = stat_file(full_path)
#                         inode_number = str(_stat.st_ino)
#                         user_info = db.get_user_by_uid(_stat.st_uid)
#                         user_info_id = "1" if user_info is None else user_info["id"]
#                         user_info_name = "unknown" if user_info is None else user_info["name"]
#                         if inode_number in db_datasets.keys() :
#                             if not check :
#                                 db_datasets.pop(inode_number,None)
#                             else :
#                                 total_size = get_dir_size(full_path)
#                                 # file_count , dir_count = get_dir_count(full_path)
#                                 result = dataset_db.update_dataset(id = db_datasets[inode_number]['id'], name = name, 
#                                         workspace_id = workspace_id,
#                                         create_user_id = user_info_id,
#                                         access = access, 
#                                         description = None,
#                                         modify_datetime = datetime.fromtimestamp(_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'))
#                                 db_datasets.pop(inode_number,None)
#                                 continue
#                         else :
#                             print('db insert scan_workspace')
#                             result = dataset_db.insert_dataset(name = name,
#                                 workspace_id = workspace_id, 
#                                 create_user_id = user_info_id,
#                                 access = access,
#                                 description = "",
#                                 create_datetime=datetime.fromtimestamp(_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'))

#             #delete_db
#             if not check :
#                 if len(db_datasets) > 0 :
#                     print("delete dataset info in db")
#                     delete_ids=[]
#                     for db_key, db_value in db_datasets.items():
#                         delete_ids.append(str(db_value['id']))
#                     if len(delete_ids) != 0:
#                         dataset_db.delete_dataset(', '.join(delete_ids))
#     except:
#         traceback.print_exc()


def decompress(body, headers_user):
    try:
        dataset_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        redis_sub_key=""
        if body.path is not None:
            dataset_dir=dataset_dir.joinpath(body.path)
            redis_sub_key=body.path+redis_sub_key
        print(redis_sub_key)
        support_extension = ['.tar', '.zip', '.gz']
        filename = body.file # list to string and split 

        file_name,file_Extension = os.path.splitext(filename)
        
        if file_Extension not in support_extension:
            return response(status=0, message = 'Not support Decompression Extension')

        if file_Extension == '.gz':
            file_name,file_Extension = os.path.splitext(file_name)

        destination_path = duplicate_check(dataset_dir, dataset_dir, file_name)
        target_path=dataset_dir.joinpath(body.file)
        image=os.getenv("JFB_DATASET_IMAGE")
        redis_sub_key=redis_sub_key+destination_path.name
        redis_key=DATASET_PROGRESS.format(dataset_id=dataset_info['id'])
        download_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        helm_name=f"decompress-{headers_user}-{download_time}"
        # redis_sub_key=DATASET_PROGRESS_SUB_KEY.format(workspace_name=workspace_info['name'], dataset_name=dataset_info['name'], job_type="decompress", job_name=file_name)
        res,message=create_decompress_job(target=target_path, destination=destination_path, 
                                          extention=file_Extension, redis_key=redis_key, redis_sub_key=redis_sub_key,
                                          helm_name=helm_name, image=image, 
                                          storage_name=storage_info['name'], header_user=headers_user,
                                          dataset_id=body.dataset_id, dataset_name=dataset_info['name'], 
                                          workspace_id=workspace_info['id'], workspace_name=workspace_info['name'], 
                                          user_id=user_id)
        if not res:
            delete_helm(helm_name=redis_key)
            return response(status=0, message = message)

        return response(status=1, message = "Decompression request complete")
    except:
        traceback.print_exc()
        raise DecompressError
    
def decompress_fuc(compress_obj : zipfile.ZipFile, compress_list, destination_path, log_file_path, headers_user):
    try:
        os.system('mkdir -p {}'.format(destination_path))
        os.system('chown {}:{} "{}"'.format(headers_user, headers_user, destination_path))
        if not os.path.exists(log_file_path):
            os.system('mkdir -p {}'.format(os.path.dirname(log_file_path)))
        
        total=len(compress_list)
        curr=0
        for member in compress_list:
            # Extract member
            curr+=1
            percent = (curr/total) * 100
            with open(log_file_path,"a") as f:
                f.write(str("{}\n".format(int(percent))))
            compress_obj.extract(member=member,path=destination_path)
            target = member.filename.encode('cp437').decode('euc-kr')
            target = Path(destination_path).joinpath(target)
            Path(destination_path).joinpath(member.filename).rename(target)
            try :
                os.system('chown {}:{} "{}"'.format(headers_user, headers_user, os.path.join(destination_path,member.filename)))
            except :
                os.system('chown {}:{} "{}"'.format(headers_user, headers_user, os.path.join(destination_path,member.name)))
        compress_obj.close()
    except:
        traceback.print_exc()
        raise DecompressError



#update_file_or_folder
def remove_data(dataset_id, body, headers_user):
    try:
        global redis
        user_info = user_db.get_user_id(headers_user)
        user_id = user_info['id']
        dataset_dir_info = dataset_db.get_dataset(dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        #remove files
        remove_sub_key=""
        if body.path is not "/" and body.path is not None:
            dataset_dir = dataset_dir.joinpath(body.path)
            remove_sub_key=body.path
        # data_list = body['data_list'].split(',')
        for data in body.data_list:
            remove_file_path = dataset_dir.joinpath(data)
            change_own(path=remove_file_path,headers_user=headers_user)
            remove_data_info = redis.hget(DATASET_PROGRESS.format(dataset_id=dataset_id),remove_sub_key+data)

            if remove_data_info is not None:
                remove_data_info=json.loads(remove_data_info)
                if remove_data_info.get("job",False):
                    delete_helm(remove_data_info['job'])
                else:
                    print(remove_sub_key+data)
                    redis.delete(DATASET_UPLOADSIZE.format(dataset_id=dataset_id) ,remove_sub_key+data)
                redis.delete(DATASET_UPLOAD_LOCK.format(dataset_id=dataset_id, name=remove_sub_key+data))
                redis.hdel(DATASET_UPLOAD_LIST,DATASET_PROGRESS.format(dataset_id=dataset_id))
                redis.hdel(DATASET_PROGRESS.format(dataset_id=dataset_id),remove_sub_key+data)
                print(redis.hget(DATASET_UPLOADSIZE.format(dataset_id=dataset_id),remove_sub_key+data))
                print(redis.hget(DATASET_PROGRESS.format(dataset_id=dataset_id),remove_sub_key+data))

            if remove_file_path.exists():
                #TODO append log dataset_id + data name 
                
                if remove_file_path.is_file():
                    remove_file_path.unlink()
                else:
                    shutil.rmtree(remove_file_path)

                print(redis.hget(DATASET_PROGRESS.format(dataset_id=dataset_id),remove_sub_key+data))
            else:
                return response(status = 0, message = "Not exists target")

        return response(status = 1, message = 'Remove Data Complete')

    except:
        traceback.print_exc()
        return response(status = 0, message = "Remove Data Error")

#TODO dataset upload method 별로 분리 및 flightbase 업로드 로직 구현(중복 및 분할업로드 고려되어야 함)


def update_data(body, headers_user):
    try:
        user_info = user_db.get_user_id(headers_user)
        user_id = user_info['id']
        dataset_dir_info = dataset_db.get_dataset(body['dataset_id'])
        workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name']))
        #remove files
        if body['path'] is not None:
                dataset_dir = dataset_dir.joinpath(body['path'])
        target=dataset_dir.joinpath(body['data'])
        if target.exists():
            destination =target.with_name(body['new_name'])
            if destination.exists():
                return response(status = 0, message = f"Already exists data : {body['new_name']}")
            else:
                target.rename(destination)

        return response(status = 1, message = 'Change Data Complete')

    except:
        traceback.print_exc()
        return response(status = 0, message = "Change Data Error")
    
#@cache
def get_tree(dataset_id, headers_user):
    result={}
    user_info = user_db.get_user_id(headers_user)
    user_id = user_info['id']
    dataset_dir_info = dataset_db.get_dataset(dataset_id)
    workspace_info = ws_db.get_workspace(workspace_id=dataset_dir_info['workspace_id'])
    storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
    dataset_dir = JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_dir_info['access'], DATASET_NAME=dataset_dir_info['name'])
    dir_list=subprocess.run(["tree {} -d -fi -N".format(dataset_dir)],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8').stdout.replace(dataset_dir,'').split('\n')
    dir_list=list(filter(None, dir_list))
    dir_list.remove(dir_list[-1])
    result['tree'] = dir_list
    #dataset_dir_info['permission_level'] = check_dataset_access_level(headers_user, dataset_dir_info)
    return  response(status = 1, result = result)



# def git_clone(args,headers_user=None):
#     os.system('pip install GitPython')
#     import git 
#     try:
#         dataset_info = dataset_db.get_dataset(args.dataset_id)
#         ##create path##
#         path = JF_DATASET_PATH.format(workspace_name = dataset_info['workspace_name'], access = dataset_info['access'], dataset_name = dataset_info['name'])
#         if args.current_path is None:
#             path = path + args.dir
#         else :
#             path = path + args.current_path + args.dir

#         if os.path.exists(path):
#             print("exist folder")
#             return response(status = 0, message = "exist folder")
#         ##create url##
        
        
#         #url = 'http://github.com/teauk/jupyterlab-git.git'
#         git.Repo.clone_from(url,path)

#         #Clone시 생성되는 폴더 소유자 변경
#         os.system('chown {}:{} "{}"'.format(headers_user, headers_user, path))
#         #폴더 내 하위 파일,폴더 소유자 변경
#         # change_own(path,headers_user)
#         return response(status = 1, result = {'is_private' : False}, message = 'git clone success')
#     except Exception:
#         #private
#         url = args.url.split('//')
#         url = 'http://'+args.username+':'+args.accesstoken+'@'+url[1]
#         git.Repo.clone_from(url,path)

#         #Clone시 생성되는 폴더 소유자 변경
#         os.system('chown {}:{} "{}"'.format(headers_user, headers_user, path))
#         #폴더 내 하위 파일,폴더 소유자 변경
#         # change_own(path,headers_user)
#         return response(status = 1, result = {'is_private' : True}, message = 'git clone success')
#     except :
#         traceback.print_exc()
#         return response(status = 0, result = {'is_private' : True}, message = "git clone failed")


    

def update_data_training_form(dataset_id, data_training_form):
    dataset_info = dataset_db.get_dataset(dataset_id=dataset_id)
    dataset_list = [
        {
            "id": dataset_info["id"], 
            "name": dataset_info["name"], 
            "type": dataset_info["access"], 
            "workspace_name": dataset_info["workspace_name"] 
        }
    ]
    
    # comp_built_in_data_training_form_and_dataset(dataset_list=dataset_list, data_training_form_list=data_training_form)
    return response(status=1, result=dataset_list[0].get("data_training_form"))


def get_dataset_marker_files(dataset_id, search_path=None, headers_user=None):
    def find_all_files_with_subfolder(path):
        datas = []
        try:
            file_list = os.listdir(path)
        except OSError as e:
            print("os.listdir error : " , e)
            datas.append(path)
            return datas
            
        for name in file_list:
            if os.path.isdir(os.path.join(path,name)) == True:
                datas+=find_all_files_with_subfolder(os.path.join(path,name))
            if ".jpeg" in name or "jpg" in name or ".png" in name:
                datas.append(os.path.join(path,name))
        return datas
    
    def find_files_in_folder(path):
        datas = []
        file_list = os.listdir(path)
        for name in file_list:
            if os.path.isfile(os.path.join(path,name)) :
                if ".jpeg" in name or "jpg" in name or ".png" in name:
                    datas.append(name)
        return datas
    try:
        dataset_dir_info = dataset_db.get_dataset(dataset_id)
        path = JF_DATASET_PATH.format(workspace_name = dataset_dir_info['workspace_name'], access = dataset_dir_info['access'], dataset_name = dataset_dir_info['name'])
        if search_path is not None:
            path = path + search_path
        file_list = []
        if search_path is None:
            file_list = find_all_files_with_subfolder(path)
        else :
            file_list = find_files_in_folder(path)
        return response(status=1, result=file_list)
    except FileNotFoundError as fe:
        # traceback.print_exc()
        return response(status=0, result=[], message="Search Path : [{}]  is not exist.".format(search_path))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=[], message="Get dataset for marker error ")

#@cache
def get_filebrowser_url(dataset_id, headers_user=None):
    try:
        global redis
        print(redis.hgetall(DATASET_FILEBROWSER_POD_STATUS))
        filebrowser=redis.hget(DATASET_FILEBROWSER_POD_STATUS, dataset_id)
        if filebrowser is not None:
            filebrowser = json.loads(filebrowser)
            return response(status = 1, result = filebrowser['url'])
        else:
            return response(status = 0, result=None)
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)
    
def active_filebrowser_pod(dataset_id, active, background_tasks, headers_user=None):
    try:
        dataset_info = dataset_db.get_dataset(dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_list_in_workspace = dataset_db.get_dataset_list(workspace_id=dataset_info['workspace_id'])
        filebowser_count=0
        if dataset_list_in_workspace:
            for dataset in dataset_list_in_workspace:
                # DB 기준으로 카운팅
                if dataset.get('filebrowser') == 1:
                    filebowser_count += 1
        
        print(f"Active filebrowser count in workspace {workspace_info['id']}: {filebowser_count}")
        filebrowser_max_count = int(os.getenv("JF_FILEBROWSER_MAX_COUNT"))
        if active == "on" and filebowser_count >= filebrowser_max_count:
            return response(status = 0, message=f"Cannot use more than {filebrowser_max_count} Filebrowsers in this workspace Please shut down the unused Filebrowser.")
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        if dataset_info['access']==0:
            if dataset_info['create_user_id'] != user_id:
                raise Exception("inaccessible user")
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        # ws_namespace=f"{namespace}-{workspace_info['id']}"
        dataset_path=f"data/{workspace_info['name']}/{dataset_info['access']}/{dataset_info['name']}"
        dataset_pvc_name=storage_info['name']
        # dataset_pvc_name = f"{namespace}-{workspace_info['id']}-data-pvc"
        filebrowser_name = f"filebrowser-{dataset_id}"
        
        if active =="off":
            # 즉시 DB와 Redis 업데이트
            dataset_db.update_dataset(id=dataset_id, filebrowser=0)
            redis.hdel(DATASET_FILEBROWSER_POD_STATUS, dataset_id)
            background_tasks.add_task(delete_helm,helm_name=filebrowser_name, namespace=namespace)
            return response(status=1, message="filebrowser Off")
        elif active == "on":
            ingress_path = get_sha256_hash_filebrowser_name(f"{dataset_id}-{dataset_info['name']}")
            pod_info={
                'url' : f"/{ingress_path}",
                'pod_status' : "pending"
            }
            redis.hset(DATASET_FILEBROWSER_POD_STATUS, dataset_id, json.dumps(pod_info))
            background_tasks.add_task(filebrowser_run,filebrowser_name=filebrowser_name, dataset_path=dataset_path,
                        dataset_pvc_name=dataset_pvc_name, ingress_path=ingress_path,
                        namespace=namespace, dataset_id=dataset_id, workspace_id=dataset_info['workspace_id'])
            # 즉시 DB 업데이트
            dataset_db.update_dataset(id=dataset_id, filebrowser=1)
            return response(status=1, message="filebrowser On")
        else:
            raise Exception("Unknown Active Mode")

    except:
        traceback.print_exc()
        return response(status=0, message="filebrowser action failed") 


def get_sha256_hash_filebrowser_name(text):
    return hashlib.md5(text.encode()).hexdigest()

