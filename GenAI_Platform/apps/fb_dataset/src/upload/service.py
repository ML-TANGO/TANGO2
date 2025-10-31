from utils.resource import response
# from utils.common import JfLock, global_lock, generate_alphanum
# import utils.db as db
import utils.crypt as cryptUtil
from utils.exceptions import *
from shutil import *
from pathlib import Path, PurePath
import os
import traceback
from fastapi import UploadFile, File, BackgroundTasks
from helm_run import scp_upload_job, delete_helm, wget_upload_job, git_upload_job
from utils.redis_key import DATASET_PROGRESS, DATASET_UPLOADSIZE, DATASET_UPLOAD_LOCK, DATASET_DUPLICATE, SSE_PROGRESS, DATASET_UPLOAD_LIST
from utils.msa_db import db_dataset as dataset_db
from utils.msa_db import db_workspace as ws_db
from utils.msa_db import db_user as user_db
from utils.msa_db import db_storage as storage_db
from utils.PATH_NEW import JF_DATA_DATASET_PATH
from utils.redis import get_redis_client
import datetime
from utils.common import change_own, format_size
import threading
import shutil
import unicodedata
import subprocess
import time
import aiofiles

def get_dataset_path(dataset_id):
    try:
        dataset_info = dataset_db.get_dataset(dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        return Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
    except:
        traceback.print_exc()

def get_disk_usage(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    return result.split('\t')[0]

redis=get_redis_client()

def name_filter(name):
        return name.replace('&','_').replace('(','_').replace(')','_').replace(' ','_').replace('#','_').replace('$','_').replace('%','_').replace('[','').replace(']','')

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

def duplicate(upload_path:Path,redis_sub_key, name, type_, dataset_id, user_id ):
    result={}
    dir_file_name=None
    if type_=='dir':
        name=name.split('/')
        dir_file_name="/".join(name[1:])
        name=name[0]
        redis_sub_key=redis_sub_key.format(UPLOAD_NAME=name)
    else:
        redis_sub_key=redis_sub_key.format(UPLOAD_NAME=name)

    # redis_subkey = redis_subkey+'/'+name
    duplicate_key = DATASET_DUPLICATE.format(dataset_id=dataset_id, user_id=user_id)
    duplicate_list = redis.hget(duplicate_key,redis_sub_key)
    # print(duplicate_list)
    if duplicate_list is None:
        duplicate_path = duplicate_check(target=upload_path, destination=upload_path, name=name)
        duplicate_name = duplicate_path.name
        result[name]=duplicate_name
        redis.hset(duplicate_key,redis_sub_key,json.dumps(result))

    else:
        duplicate_dict=json.loads(duplicate_list)
        duplicate_name = duplicate_dict.get(name,None)
        if duplicate_name is None:
            duplicate_path = duplicate_check(target=upload_path, destination=upload_path, name=name)
            duplicate_name = duplicate_path.name
            duplicate_dict[name]=duplicate_name
            redis.hset(duplicate_key,redis_sub_key,json.dumps(duplicate_dict))
        else:
            duplicate_path=upload_path.joinpath(duplicate_name)


    if type_=='dir':
        return duplicate_path.joinpath(dir_file_name), redis_sub_key
    else:
        return duplicate_path, redis_sub_key






async def upload_name_check(dataset_id, data_list , path=None):
    try:
        global redis
        dataset_dir = get_dataset_path(dataset_id)
        result=[]
        # redis_sub_key=""
        redis_key=DATASET_PROGRESS.format(dataset_id=dataset_id)

        if path is not None:
            dataset_dir=dataset_dir.joinpath(path)
            # redis_sub_key=path
            print(dataset_dir)
            if not dataset_dir.exists():
                raise Exception(f"Not exist path : {path}")
        for data in data_list:
            data=unicodedata.normalize('NFC',data)
            name = name_filter(name=data)
            check_path = dataset_dir.joinpath(name)
            if check_path.exists():
                result.append({data:name})
            # destination_path = duplicate_check(target=dataset_dir, destination=dataset_dir, name=name)
            # if redis.hget(redis_key,redis_sub_key+destination_path.name) is None:
            #     result_dict[data]=destination_path.name
            # else:
            #     result_dict[data]="Already Uploading Data name"

        return response(status=1, result=result)
    except:
        traceback.print_exc()
        return response(status=0, message="upload check error")

#아직 사용중이지 않음.
# def upload_dummy_create(dataset_id, data_list , type_, path=None):
#     try:
#         global redis
#         dataset_dir = get_dataset_path(dataset_id)
#         result_dict={}
#         redis_sub_key=""
#         redis_key=DATASET_PROGRESS.format(dataset_id=dataset_id)

#         if path is not None:
#             # dataset_dir=dataset_dir.joinpath(path)
#             redis_sub_key=path
#         for data in data_list:
#             data=unicodedata.normalize('NFC',data)
#             name = name_filter(name=data)
#             redis_sub_key=redis_sub_key+name
#             dummy_path=dataset_dir.joinpath(redis_sub_key)
#             if type_ == "file":
#                 dummy_path.touch()
#             else:
#                 dummy_path.mkdir(parents=True, exist_ok=True)
#             upload_start_time = datetime.datetime.now().strftime('%y:%m:%d %H:%M:%S')
#             # destination_path = duplicate_check(target=dataset_dir, destination=dataset_dir, name=name)
#             # if redis.hget(redis_key,redis_sub_key+name) is None:
#             #     result_dict[data]=name
#             # else:
#             #     result_dict[data]="Already Uploading Data name"
#             upload_info = {
#                         'total_size': 10,
#                         'upload_size': 0,
#                         'datetime': upload_start_time,
#                         'type' : "size",
#                         'status' : "wait"
#                     }
#             redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))
#         return response(status=1, result=result_dict)
#     except:
#         traceback.print_exc()
#         return response(status=0, message="upload check error")

def upload_progress_check():
    while(True):
        try:
            global redis
            upload_list=redis.hgetall(DATASET_UPLOAD_LIST)
            time.sleep(1)
            if len(upload_list)==0:
                continue
            else:
                # upload_list=json.loads(upload_list)

                for sub_key,key in upload_list.items():
                    upload_info = redis.hget(key,sub_key)

                    if upload_info is not None:
                        upload_info=json.loads(upload_info)
                        if upload_info['complete']:
                            user_info = user_db.get_user(user_id=upload_info['upload_user'])
                            change_own(path=get_dataset_path(upload_info['dataset_id']).joinpath(sub_key), headers_user=user_info['name'])
                            redis.hdel(key,sub_key)
                            redis.hdel(DATASET_UPLOAD_LIST,sub_key)
                            if upload_info['delete_sub_key'] is not None:
                                # print(redis.hget(DATASET_DUPLICATE.format(dataset_id=dataset_id, user_id=upload_info['upload_user']),upload_info['delete_sub_key']))
                                redis.hdel(DATASET_DUPLICATE.format(dataset_id=dataset_id, user_id=upload_info['upload_user']),upload_info['delete_sub_key'])
                                # print(redis.hget(DATASET_DUPLICATE.format(dataset_id=dataset_id, user_id=upload_info['upload_user']),upload_info['delete_sub_key']))
                            continue
                        else:
                            dataset_id = upload_info['dataset_id']
                            dataset_path = get_dataset_path(dataset_id).joinpath(upload_info['path'])
                            if not dataset_path.exists():
                                redis.hdel(key,sub_key)
                                redis.hdel(DATASET_UPLOAD_LIST,sub_key)
                                continue
                            if upload_info.get('job',False):
                                upload_size=upload_info['upload_size']
                            else:
                                if upload_info['upload_type']=="file":
                                    upload_size = dataset_path.stat().st_size
                                else:
                                    upload_size = int(get_disk_usage(dataset_path))
                            upload_info['upload_size']=upload_size
                            current_time = datetime.datetime.now().replace(microsecond=0)
                            #datetime.strftime(,'%Y:%M:%d %H:%M:%S')
                            upload_start_time = datetime.datetime.strptime(upload_info['datetime'],'%y:%m:%d %H:%M:%S')
                            upload_info['progress'] = int(upload_size/upload_info['total_size']*100)
                            total_second=(current_time-upload_start_time).total_seconds()
                            if total_second==0:
                                total_second=1
                            speed = upload_size/total_second

                            if int(speed) == 0 :
                                upload_info['remain_time'] = None
                            else:
                                upload_info['remain_time'] = round((upload_info['total_size']-upload_size)/speed) if upload_info['total_size']-upload_size != 0 or speed !=0 else 0
                            redis.hset(key,sub_key,json.dumps(upload_info))
        except:
            traceback.print_exc()


async def upload_data(files, dataset_id, path, headers_user, type_, chunk_id, size=None, chunk_start=False, overwrite=True):
    try:
        import time
        global redis
        start_time = time.time()
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        dataset_info = dataset_db.get_dataset(dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        redis_key=DATASET_PROGRESS.format(dataset_id=dataset_id)
        delete_sub_key=None
        write_mode = 'ab+'
        redis_sub_key = "{UPLOAD_NAME}"
        print("="*50)
        print(f"chunk_id : {chunk_id}")
        if path is not None:
            path=unicodedata.normalize('NFC',path)
            dataset_dir=dataset_dir.joinpath(path)
            redis_sub_key=path + redis_sub_key

        if not dataset_dir.exists():
            raise Exception(f"not exist upload path {path}")
            # dataset_dir.mkdir(parents=True, exist_ok=True)
            # change_own(path=dataset_dir, headers_user=headers_user)
        end_time = time.time()
        print(f"chunk_id : {chunk_id} get Path time: {end_time-start_time}")
        for file in files:
            try:
                start_time = time.time()
                # unicode normalization because MAC OS
                filename = unicodedata.normalize('NFC',file.filename)
                upload_data = name_filter(filename) # file.filename # file['name']
                start_time = time.time()
                # Overwrite or duplicate
                if overwrite:
                    upload_path = dataset_dir.joinpath(upload_data)
                    if chunk_start:
                        write_mode = 'wb+'
                else:
                    upload_path, delete_sub_key = duplicate(upload_path=dataset_dir, redis_sub_key=redis_sub_key, name=upload_data, type_=type_, dataset_id=dataset_id, user_id=user_id)
                print(upload_path)
                # return True
                if type_ =="file":
                    redis_sub_key=redis_sub_key.format(UPLOAD_NAME=upload_path.relative_to(dataset_dir))
                else:
                    redis_sub_key=redis_sub_key.format(UPLOAD_NAME=str(upload_path.relative_to(dataset_dir)).split('/')[0])

                end_time = time.time()
                print(f"chunk_id = {chunk_id}, create redis subkey {end_time-start_time}")


                if not upload_path.parent.exists():
                    upload_path.parent.mkdir(parents=True, exist_ok=True)
                    change_own(path=upload_path.parent, headers_user=headers_user)
                start_time = time.time()
                upload_start_time = datetime.datetime.now().strftime('%y:%m:%d %H:%M:%S')
                if chunk_start:
                    upload_info = {
                                'dataset_id':dataset_id,
                                'dataset_name':dataset_info['name'],
                                'workspace_id' : workspace_info['id'],
                                'workspace_name' : workspace_info['name'],
                                'upload_user' : user_id,
                                'path' : redis_sub_key,
                                'upload_type' : type_,
                                'total_size': size,
                                'upload_size': 0,
                                'datetime': upload_start_time,
                                'type' : "size",
                                'status' : "running",
                                'delete_sub_key' : delete_sub_key,
                                'complete' : False,
                                'progress' : 0
                            }
                    print(f"upload redis set {redis_key} {redis_sub_key}")
                    redis.hset(DATASET_UPLOAD_LIST,redis_sub_key,redis_key)
                    redis.hset(SSE_PROGRESS.format(user_id=user_id),redis_sub_key,redis_key)
                    redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))
                end_time = time.time()
                print(f"chunk_id = {chunk_id}, redis set {end_time-start_time}")
                start_time = time.time()
                async with aiofiles.open(upload_path, mode=write_mode) as f:
                    await f.write(file.file.read())
                    # change_own(path=upload_path, headers_user=headers_user)
                end_time = time.time()
                print(f"chunk_id = {chunk_id}, chunk write {end_time-start_time}")
            except FileExistsError as e:
                raise e
            except Exception as e:
                # shutil.rmtree(dataset_dir)
                upload_info=redis.hget(redis_key, redis_sub_key)
                # change_own(path=dataset_dir.joinpath(redis_sub_key), headers_user=headers_user)
                if upload_info is None:
                    pass
                else:
                    upload_info=json.loads(upload_info)
                    upload_info['status']="error"

                    redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))
                traceback.print_exc()
                raise e
        return response(status=1, message="success upload request")
    except Exception as e:
        traceback.print_exc()
        raise e

async def upload_data_back(files, dataset_id, path, headers_user, type_, size=None, chunk_start=False, overwrite=True):
    try:
        global redis
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        dataset_info = dataset_db.get_dataset(dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        redis_key=DATASET_PROGRESS.format(dataset_id=dataset_id)
        delete_sub_key=None
        is_dir=False
        write_mode = 'ab+'
        redis_sub_key = "{UPLOAD_NAME}"

        if path is not None:
            path=unicodedata.normalize('NFC',path)
            dataset_dir=dataset_dir.joinpath(path)
            redis_sub_key=path + redis_sub_key

        if not dataset_dir.exists():
            raise Exception(f"not exist upload path {path}")
            # dataset_dir.mkdir(parents=True, exist_ok=True)
            # change_own(path=dataset_dir, headers_user=headers_user)

        for file in files:
            try:
                # unicode normalization because MAC OS
                filename = unicodedata.normalize('NFC',file.filename)
                upload_data = name_filter(filename) # file.filename # file['name']

                # Overwrite or duplicate
                if overwrite:
                    upload_path = dataset_dir.joinpath(upload_data)
                    if chunk_start:
                        write_mode = 'wb+'
                else:
                    upload_path, delete_sub_key = duplicate(upload_path=dataset_dir, redis_sub_key=redis_sub_key, name=upload_data, type_=type_, dataset_id=dataset_id, user_id=user_id)
                # return True

                # redis_sub_key setting for upload_progress and upload_info
                if type_=='dir':
                    # print(upload_path.relative_to(dataset_dir))
                    # print(type(upload_path.relative_to(dataset_dir)))
                    redis_sub_key=redis_sub_key.format(UPLOAD_NAME=str(upload_path.relative_to(dataset_dir)).split('/')[0])
                    is_dir=True
                    #redis_sub_key.format(UPLOAD_NAME=name_filter(file.filename.split('/')[0]))
                else:
                    redis_sub_key=redis_sub_key.format(UPLOAD_NAME=upload_path.relative_to(dataset_dir))
                    #redis_sub_key.format(UPLOAD_NAME=upload_data)

                # return 0
                # redis_sub_key=unicodedata.normalize('NFC',redis_sub_key)
                upload_key=DATASET_UPLOADSIZE.format(dataset_id=dataset_id)

                pre_upload_size=redis.hget(upload_key,redis_sub_key)

                if pre_upload_size is None:
                    redis.hset(upload_key,redis_sub_key,0)

                if not upload_path.parent.exists():
                    upload_path.parent.mkdir(parents=True, exist_ok=True)
                    change_own(path=upload_path.parent, headers_user=headers_user)

                upload_start_time = datetime.datetime.now().strftime('%y:%m:%d %H:%M:%S')
                with open(upload_path, mode=write_mode) as f:
                    f.write(file.file.read()) # file.file.read() #file['content']
                    upload_size=int(file.size)
                    lock_key = DATASET_UPLOAD_LOCK.format(dataset_id=dataset_id, name=redis_sub_key)
                    lock = redis.lock(lock_key)
                    if lock.acquire(blocking=True):
                        redis.hincrby(upload_key, redis_sub_key, amount=upload_size)
                        lock.release()
                    upload_size=int(redis.hget(upload_key,redis_sub_key))
                    # if upload_size==0:
                    #     raise Exception
                    if type_=="file":
                        upload_size=int(upload_path.stat().st_size)
                    upload_info = redis.hget(redis_key, redis_sub_key)
                    if upload_info is None:
                        # if type_=='dir':
                        #     change_own(path=dataset_dir.joinpath(redis_sub_key), headers_user=headers_user)
                        upload_info = {
                            'total_size': size,
                            'upload_size': upload_size,
                            'datetime': upload_start_time,
                            'type' : "size",
                            'status' : "running",
                            'delete_sub_key' : delete_sub_key,
                            'is_dir' : is_dir
                        }
                    else:
                        upload_info=json.loads(upload_info)
                        upload_info['upload_size']= upload_size # int(redis.hget(upload_key,redis_sub_key))
                    redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))
                change_own(path=upload_path, headers_user=headers_user)
            except FileExistsError as e:
                raise e
            except Exception as e:
                # shutil.rmtree(dataset_dir)
                upload_info=redis.hget(redis_key, redis_sub_key)
                if upload_info is None:
                    upload_info = {
                        'total_size': size,
                        'upload_size': 0,
                        'datetime': upload_start_time,
                        'type' : "size",
                        'status' : "error",
                        'delete_sub_key' : delete_sub_key
                    }
                else:
                    upload_info=json.loads(upload_info)
                    upload_info['status']="error"

                redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))
                redis.delete(   )
                # print("")
                traceback.print_exc()
                raise e


        # background_tasks.add_task(upload_file_thread, files, dataset_dir, redis_key, path, type, size, headers_user, upload_key, start, overwrite)

        return response(status=1, message="success upload request")
    except Exception as e:
        traceback.print_exc()
        raise e


def scp_upload(body, headers_user):
    try:
        dataset_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        destination_path=dataset_dir
        if body.path is not None:
            destination_path=dataset_dir.joinpath(body.path)

        if not destination_path.exists():
            return response(status=0, message = f"Not exist '{body.path}' ")
        # destination_path.mkdir(parents=True, exist_ok=True)

        image=os.getenv("JFB_DATASET_IMAGE")
        redis_key=DATASET_PROGRESS.format(dataset_id=body.dataset_id)
        download_time = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        helm_name=f"upload-scp-{headers_user}-{download_time}"
        # redis_sub_key=DATASET_PROGRESS_SUB_KEY.format(workspace_name=workspace_info['name'], dataset_name=dataset_info['name'], job_type="scp", job_name=job_name)
        res,message=scp_upload_job(ip=body.ip, username=body.username,
                                password=body.password, target=body.file_path,
                                destination=destination_path, path=body.path,
                                redis_key=redis_key, helm_name=helm_name,
                                image=image, storage_name=storage_info['name'],
                                header_user=headers_user,dataset_id=body.dataset_id,
                                dataset_name=dataset_info['name'], workspace_id=workspace_info['id'],
                                workspace_name=workspace_info['name'], user_id=user_id)

        if not res:
            delete_helm(helm_name=helm_name)
            return response(status=0, message = message)

        return response(status=1, message = "scp upload request complete")
    except:
        delete_helm(helm_name=helm_name)
        traceback.print_exc()
        return response(status=0, message = "scp upload fail")

def wget_upload(body, headers_user):
    try:
        dataset_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']
        destination_path=dataset_dir

        if  body.path is not None:
            destination_path=dataset_dir.joinpath(body.path)

        if not destination_path.exists():
            return response(status=0, message = f"Not exist {body.path}")

        image=os.getenv("JFB_DATASET_IMAGE")

        redis_key=DATASET_PROGRESS.format(dataset_id=body.dataset_id)
        download_time = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        helm_name= f"upload-wget-{headers_user}-{download_time}"
        res,message=wget_upload_job(upload_url=body.upload_url, path=body.path,
                                destination=destination_path, redis_key=redis_key,
                                helm_name=helm_name, image=image,
                                storage_name=storage_info['name'],
                                header_user=headers_user, dataset_id=body.dataset_id,
                                dataset_name=dataset_info['name'], workspace_id=workspace_info['id'],
                                workspace_name=workspace_info['name'], user_id=user_id)
        if not res:
            delete_helm(helm_name=helm_name)
            return response(status=0, message = message)

        return response(status=1, message = "wget upload request complete")
    except:
        delete_helm(helm_name=helm_name)
        traceback.print_exc()
        return response(status=0, message = "wget upload fail")

def git_upload(body, headers_user):
    try:
        dataset_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
        user_id = user_db.get_user_id(headers_user)
        user_id = user_id['id']


        if  body.path is not None:
            dataset_dir=dataset_dir.joinpath(body.path)

        if not dataset_dir.exists():
            return response(status=0, message = f"Not exist {body.path}")

        if body.git_cmd == "pull":
            if not dataset_dir.joinpath('.git').exists():
                raise Exception("Directory is not a Git repository.")

        image=os.getenv("JFB_DATASET_IMAGE")

        redis_key=DATASET_PROGRESS.format(dataset_id=body.dataset_id)
        # redis_sub_key=body.git_repo_url.split('/')[-1]
        # redis.hset(redis_key,redis_sub_key,)
        download_time = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        helm_name= f"upload-git-{headers_user}-{download_time}"
        res,message=git_upload_job(git_repo_url=body.git_repo_url, git_access=body.git_access,
                                   git_id=body.git_id, git_access_token=body.git_access_token,
                                   git_cmd=body.git_cmd,destination=dataset_dir,
                                   path=body.path, redis_key=redis_key,
                                   helm_name=helm_name, image=image,
                                   storage_name=storage_info['name'], header_user=headers_user,
                                   dataset_id=body.dataset_id,dataset_name=dataset_info['name'],
                                   workspace_id=workspace_info['id'],workspace_name=workspace_info['name'],
                                   user_id=user_id)
        if not res:
            delete_helm(helm_name=helm_name)
            return response(status=0, message = message)

        return response(status=1, message = "git upload request complete")
    except Exception as e:
        delete_helm(helm_name=helm_name)
        traceback.print_exc()
        return response(status=0, message = f"git upload fail '{e}'")

# def git_pull(body, headers_user):
#     try:
#         dataset_info = dataset_db.get_dataset(body.dataset_id)
#         workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
#         storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
#         dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))
#         user_id = user_db.get_user_id(headers_user)
#         user_id = user_id['id']

#         if  body.path is not None:
#             dataset_dir=dataset_dir.joinpath(body.path)

#         if not dataset_dir.exists():
#             return response(status=0, message = f"Not exist {body.path}")

#         image=os.getenv("JFB_DATASET_IMAGE")

#         redis_key=DATASET_PROGRESS.format(dataset_id=body.dataset_id)
#         download_time = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
#         helm_name= f"git-pull-{headers_user}-{download_time}"
#         res,message=git_pull_job(upload_url=body.upload_url, redis_key=redis_key, helm_name=helm_name, image=image, storage_name=storage_info['name'], header_user=headers_user)
#         if not res:
#             delete_helm(helm_name=helm_name)
#             return response(status=0, message = message)

#         return response(status=1, message = "wget upload request complete")
#     except:
#         traceback.print_exc()
#         return response(status=0, message = "wget upload fail")