

import os
import json
import asyncio
import aiofiles
import traceback
import shutil
import uuid
import math
import datetime
import subprocess
import time
import numpy as np

from fastapi import File, UploadFile, Request
from huggingface_hub import login, model_info, HfApi
from requests.exceptions import HTTPError, ConnectionError, Timeout
from typing import List, Union, Optional, Tuple
from pathlib import Path
from aiokafka import AIOKafkaProducer
from confluent_kafka.admin import AdminClient
from tensorboard.backend.event_processing import event_accumulator
from aiopath import AsyncPath

from utils import redis_key, TYPE, PATH, settings, common, topic_key, workspace_resource
from utils.redis import get_redis_client_async
from utils.llm_db import db_model
from utils.msa_db import db_workspace, db_user, db_instance
from model.dto import FineTuningConfig, FineTuningPodInfo
from utils.crypt import session_cipher, front_cipher
# from utils.mongodb_async import urls_collection
from utils.kube import PodName


async def is_folder_empty(folder_path):
    path = AsyncPath(folder_path)
    return await path.is_dir() and not any([child async for child in path.iterdir()])

async def check_healthz():
    redis_client = await get_redis_client_async()
    await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
    return True

# async def shorten_url(original_url):
#     existing_url = await urls_collection.find_one({"original_url":  f"http://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/{original_url}"})
#     if existing_url:
#         return existing_url['short_id']
    
#     short_id = str(uuid.uuid4())[:8]
#     await urls_collection.insert_one({
#         "short_id": short_id,
#         "original_url": f"http://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/{original_url}",
#         "clicks": 0,
#         "last_accessed": None
#     })
#     return short_id

# async def get_origin_url(short_id):
#     url_data = await urls_collection.find_one({"short_id": short_id})
#     if url_data:
#         await urls_collection.update_one(
#             {"short_id": short_id},
#             {"$inc": {"clicks": 1}, "$set": {"last_accessed": datetime.datetime.now()}}
#         )
#         return url_data
#     return None
    

async def parse_tensorboard_scalars_async(log_dir, max_steps=20):
    """
    TensorBoard 로그 디렉토리에서 스칼라 태그들을 파싱하여 각 태그의 x, y 데이터를 딕셔너리 형태로 반환합니다 (async 버전).
    또한 각 에포크 당 스텝 수 (steps_per_epoch)를 계산하여 반환합니다.
    
    Args:
        log_dir (str): TensorBoard 로그 디렉토리 경로.
        max_steps (int, optional): 출력할 최대 스텝의 개수. 기본값은 100입니다.
    """
    # 이벤트 어큐뮬레이터 로드
    ea = event_accumulator.EventAccumulator(log_dir)
    await asyncio.to_thread(ea.Reload)

    # 스칼라 태그들을 추출
    scalar_tags = ea.Tags()['scalars']
    parsed_data = {}
    latest_steps = 0
    train_steps_per_second = None  # 초당 스텝 수
    # 필요한 스칼라 태그 데이터 추출
    for tag in scalar_tags:
        # 특정 태그 값을 저장
        if tag not in TYPE.FINE_TUNING_LOG_TAGS:
            continue
        events = ea.Scalars(tag)
        steps = [event.step for event in events]
        values = [
            0.0 if event.value is None or (isinstance(event.value, float) and math.isnan(event.value)) 
            else event.value 
            for event in events
        ]
       
        latest_steps = steps[-1]

        # 스텝 수를 최대 max_steps로 제한하고 평균값 계산
        if len(steps) > max_steps:
            indices = np.linspace(0, len(steps) - 1, max_steps, dtype=int)
            steps = [steps[i] for i in indices]
            values = [
                np.mean(values[indices[j]:indices[j + 1]]) if j + 1 < len(indices) else np.mean(values[indices[j]:])
                for j in range(len(indices))
            ]

        parsed_data[tag] = {'steps': steps, 'values': values}

    return parsed_data, latest_steps



async def check_model_files(directory_path):
    # Define required file sets
    adapter_files = ["adapter_model.safetensors", "adapter_config.json"]
    model_files = ["model.safetensors", "config.json"]
    
    # List all files in the directory asynchronously
    try:
        items_in_directory = set(await asyncio.to_thread(os.listdir, directory_path))
    except FileNotFoundError:
        return False  # Return False if the directory doesn't exist
     # Filter out only the files in the directory
    files_in_directory = [item for item in items_in_directory if await asyncio.to_thread(os.path.isfile, os.path.join(directory_path, item))]

    # Check if either set of required files is present in the directory
    if adapter_files in files_in_directory or model_files in files_in_directory:
        return True
    else:
        return False

async def delete_helm_repo(helm_repo_name : str,  workspace_id : int):
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command = f"helm uninstall {helm_repo_name} -n {namespace}"
        
        print(command)
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(command)
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def create_model_helm(workspace_id : int, model_id : int, model_name:str, commit_model : str = None , commit_name : str = None,\
    huggingface_model_id : str = None, huggingface_token : str = None, save_commit_name : str = None) -> Tuple[bool, str]:
    """
    model_name : commit 되는 모델이 저장되는 모델
    commit_model : commit 하려는 모델 이름
    
    
    """
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command = ""
        mode = ""
        command += f' --set command.latest_checkpoint_path="{PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(MODEL_NAME=model_name)}"'
        if commit_model:
            mode = "copy_commit_model"
            
            if save_commit_name is None: # model 생성
                save_commit_name = TYPE.MODEL_FIRST_COMMIT_NAME # copy 하려는 commit model path
                command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_SOURCE_MODEL_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.src_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=commit_model, COMMIT_NAME=commit_name)}"'
                # command += f' --set command.src_tokenizer_path="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=commit_model)}"'
                # command += f' --set command.dst_tokenizer_dir="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.is_commit=1'
            else: # commit model 생성
                command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=save_commit_name)}"'
                command += f' --set command.dst_log_dir="{PATH.JF_POD_MODEL_COMMIT_LOG_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=save_commit_name)}"'
                command += f' --set command.src_model_log_path="{PATH.JF_POD_MODEL_LATEST_LOG_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.is_commit=0'
            
        elif huggingface_model_id:
            mode = "download_model"
            command += f' --set command.model_id="{huggingface_model_id}"'
            command += f' --set command.token="{huggingface_token}"'
            command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_SOURCE_MODEL_PATH.format(MODEL_NAME=model_name)}"'
            # command += f' --set command.tokenizer_dir="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=model_name)}"'
            

        os.chdir("/app/helm/")
        if save_commit_name is None:
            save_commit_name = TYPE.MODEL_FIRST_COMMIT_NAME

        helm_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
        image = settings.SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/llm-finetune:dev"
        helm_command = f"""helm install {helm_name} ./model_download \
            -n {namespace}  \
            --set namespace="{namespace}" \
            --set image="{image}" \
            --set labels.model_id={model_id} \
            --set labels.workspace_id={workspace_id} \
            --set labels.model_commit_type="{mode}" \
            --set labels.helm_name={helm_name} \
            --set labels.pod_type={TYPE.FINE_TUNING_TYPE} \
            --set labels.work_func_type="commit" \
            --set command.mode="{mode}" \
            {command} \
        """
        
        print(helm_command)
        process = await asyncio.create_subprocess_shell(
            helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.decode().strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(command)
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def load_or_stop_helm(workspace_id : int, model_id: int, latest_checkpoint_path : str, tmp_model_path: str = None, load_commit_model_path : str = None):
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command = ""
        mode = ""
        command += f' --set command.latest_checkpoint_path="{latest_checkpoint_path}"'
        if tmp_model_path:
            mode = "stop_fine_tuning"
            command += f' --set command.tmp_model_path="{tmp_model_path}"'
            
        elif load_commit_model_path:
            mode = "load_commit_model"
            command += f' --set command.load_commit_model_path="{load_commit_model_path}"'
            

        os.chdir("/app/helm/")

        helm_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
        image = settings.SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/llm-finetune:dev"
        helm_command = f"""helm install {helm_name} ./model_download \
            -n {namespace}  \
            --set namespace="{namespace}" \
            --set image="{image}" \
            --set labels.model_id={model_id} \
            --set labels.workspace_id={workspace_id} \
            --set labels.model_commit_type="{mode}" \
            --set command.mode="{mode}" \
            {command} \
        """
        
        print(helm_command)
        process = await asyncio.create_subprocess_shell(
            helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(command)
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)
    
    pass

async def create_model_folder(storage_name : str, workspace_name : str , model_name : str) -> bool:
    model_commit_dir = PATH.JF_MODEL_COMMIT_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_source_dir = PATH.JF_MODEL_TMP_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_config_dir = PATH.JF_MODEL_CONFIGURATION_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_log_dir = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_commit_log_dir = PATH.JF_MODEL_COMMIT_LOG_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_latest_checkpoint_dir = PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    paths = [model_commit_dir, model_source_dir, model_config_dir, model_log_dir, model_commit_log_dir, model_latest_checkpoint_dir]
    
    # mkdir
    for path in paths:
        try:
            # 디렉터리 생성 작업을 비동기적으로 처리
            await asyncio.to_thread(os.makedirs, path)
        except Exception:
            # 예외 처리도 비동기적으로 수행
            await asyncio.to_thread(traceback.print_exc)
            await asyncio.to_thread(common.rm_rf, path)
            await asyncio.to_thread(os.makedirs, path)
        
    return True


async def delete_model_folder(storage_name: str, workspace_name: str, model_name: str) -> bool:
    model_dir_path = PATH.JF_MAIN_MODEL_PATH.format(
        STORAGE_NAME=storage_name,
        WORKSPACE_NAME=workspace_name,
        MODEL_NAME=model_name
    )

    try:
        # subprocess를 사용하여 rm -rf 실행
        result = await asyncio.create_subprocess_exec(
            'rm', '-rf', model_dir_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            print(f"Error deleting folder: {stderr.decode().strip()}")
            return False

    except Exception as e:
        traceback.print_exc()
        return False

    return True

async def delete_commit_model_folder(storage_name : str, workspace_name : str, model_name : str, commit_name: str) -> bool:
    commit_model_dir_path = PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name, COMMIT_NAME=commit_name)
    try:
        await common.async_rmtree(commit_model_dir_path)
    except Exception as e:
        traceback.print_exc()
        return False
    return True


async def check_file_exists(file_path: str) -> bool:
    """
    비동기적으로 파일이 존재하는지 확인하는 함수.
    
    :param file_path: 확인하려는 파일의 경로
    :return: 파일이 존재하면 True, 존재하지 않으면 False
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, os.path.exists, file_path)


async def move_checkpoint_files_to_parent(path):
    """
    Checks if the specified path contains any subdirectories that start with 'checkpoint'.
    If such directories are found, moves all files from the one with the highest numerical suffix to the parent directory,
    and deletes the remaining checkpoint directories. Ensures that no 'checkpoint' folder remains in the path.

    Args:
        path (str): Path to the directory to search.

    Returns:
        bool: True if a checkpoint folder was found and files were moved, False otherwise.
    """
    # Check if the specified path is a directory
    if not await asyncio.to_thread(os.path.isdir, path):
        print(f"Error: The specified path '{path}' does not exist or is not a directory.")
        return False

    # Get list of items in the directory asynchronously
    try:
        items = await asyncio.to_thread(os.listdir, path)
    except Exception as e:
        print(f"Error accessing directory '{path}': {e}")
        return False

    # Find all 'checkpoint-*' directories and determine the one with the highest suffix
    checkpoint_dirs = []
    for item in items:
        if item.startswith('checkpoint-') and await asyncio.to_thread(os.path.isdir, os.path.join(path, item)):
            try:
                suffix = int(item.split('-')[-1])
                checkpoint_dirs.append((suffix, os.path.join(path, item)))
            except ValueError:
                continue

    if not checkpoint_dirs:
        print("No checkpoint folder found.")
        return False

    # Sort checkpoint directories by suffix in descending order
    checkpoint_dirs.sort(reverse=True, key=lambda x: x[0])

    # The directory with the highest suffix
    latest_checkpoint_dir = checkpoint_dirs[0][1]
    print(f"Found latest checkpoint folder: '{latest_checkpoint_dir}'")

    # Move each file in the latest checkpoint folder to the parent directory
    for file_name in await asyncio.to_thread(os.listdir, latest_checkpoint_dir):
        file_path = os.path.join(latest_checkpoint_dir, file_name)
        
        # Ensure it's a file before moving
        if await asyncio.to_thread(os.path.isfile, file_path):
            destination_path = os.path.join(path, file_name)
            
            try:
                await asyncio.to_thread(shutil.move, file_path, destination_path)
                print(f"Moved '{file_path}' to '{destination_path}'")
            except Exception as e:
                print(f"Error moving file '{file_path}': {e}")

    # Remove all checkpoint directories
    for _, checkpoint_dir in checkpoint_dirs:
        try:
            await asyncio.to_thread(shutil.rmtree, checkpoint_dir)
            print(f"Removed checkpoint folder: '{checkpoint_dir}'")
        except Exception as e:
            print(f"Error removing checkpoint folder '{checkpoint_dir}': {e}")

    # Ensure no 'checkpoint' folder remains in the path
    remaining_items = await asyncio.to_thread(os.listdir, path)
    if any(item.startswith('checkpoint') for item in remaining_items):
        print("Error: 'checkpoint' folder still exists in the path.")
        return False

    return True  # Return True if a checkpoint folder was found and files were moved

#==========
# OPTION
#==========

async def get_model_update(model_id : int):
    model_info = await db_model.get_model_simple(model_id=model_id)
    user_list = await db_model.get_model_user_list(model_id=model_id)
    model_info["user_list"] = user_list 
    return model_info

async def get_workspace_user(workspace_id : int) -> dict:
    workspace_info = db_user.get_user_list_in_workspace(workspace_id=workspace_id)
    return workspace_info

async def get_models_option(workspace_id : int, model_name : str = None, header_user_id : int = None, is_mine : bool = False):
    if is_mine:
        models = await db_model.get_models_option(workspace_id=workspace_id, model_name=model_name, create_user_id=header_user_id)
    else:
        models = await db_model.get_models_option(workspace_id=workspace_id, model_name=model_name)
    return models

async def get_commit_models_option(model_id : int, commit_name: str = None):
    
    commit_models = await db_model.get_commit_models_option(model_id=model_id, commit_name=commit_name)
    for commit_model in commit_models:
        commit_model["fine_tuning_config"]=json.loads(commit_model["fine_tuning_config"]) 
    return commit_models

async def get_dataset_list(workspace_id : int, create_user_id : int = None, dataset_name : str = None) -> List[dict]:
    
    datasets = await db_model.get_datasets(workspace_id=workspace_id, create_user_id=create_user_id, dataset_name=dataset_name)
    
    return datasets

async def get_instance_list(workspace_id : int) -> List[dict]:
    instance_list = await db_model.get_instance_list(workspace_id=workspace_id)
    for instance in instance_list:
        #TODO
        # allm 에서 사용중인 인스턴스 수 빼기 
        instance["available_instance"] = instance["instance_allocate"]
    return instance_list

async def get_models_by_huggingface(model_name : str = None, huggingface_token : str = None, private : int = 0) -> List[str]:
    api = HfApi()
    
    if private:
        huggingface_token = front_cipher.decrypt(huggingface_token)
        models = api.list_models(limit=10, task="text-generation", library="transformers", model_name=model_name, expand=["private"], token=huggingface_token)
    else:
        models = api.list_models(limit=10, task="text-generation", library="transformers", model_name=model_name)
    parse_model_ids = [ model.id for model in models]
    return parse_model_ids

async def check_model_access( token: str, model_id: str = None, model_create : bool = False) -> bool:
    """
    해당 Hugging Face 모델에 대해 주어진 토큰으로 접근 권한이 있는지 확인하는 함수 (비동기 버전).

    Parameters:
    model_id (str): 접근하려는 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.

    Returns:
    bool: 접근 권한이 있으면 True, 없으면 False.
    """
    loop = asyncio.get_event_loop()
    if not model_create:
        token = front_cipher.decrypt(token)
    try:
        # Hugging Face API로 로그인 (토큰 기반)
        await loop.run_in_executor(None, login, token)
        if model_id is not None:
            # 모델 정보 요청 (권한 확인)
            await loop.run_in_executor(None, model_info, model_id)
        return True  # 접근 권한이 있음

    except HTTPError as e:
        # 모델에 접근할 권한이 없거나 존재하지 않음
        print(f"Error: Cannot access the model '{model_id}' with the provided token.")
        print(f"Details: {e}")
        return False

    except Exception as e:
        # 기타 오류
        print(f"An unexpected error occurred while checking access: {e}")
        return False
    
async def get_dataset_files_and_folders(dataset_id : int, search_user_id : int, search : str = None)-> List[dict]:
    dataset_info = await db_model.get_dataset_model(dataset_id=dataset_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=dataset_info["workspace_id"])
    dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , \
            ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"])
    files_and_folders = await find_files_and_folders_by_extension(directory=dataset_path, extensions=TYPE.MODEL_DATA_EXTENSIONS, search_user_id=search_user_id, search=search)
    
    return files_and_folders

async def find_files_and_folders_by_extension(directory: str, extensions: list, search_user_id: int, search: str = None) -> List[dict]:
    result = []

    # Check if directory exists
    if not os.path.exists(directory):
        return result

    # Generate user UUID
    user_uuid = search_user_id + settings.USER_UUID_SET

    # Asynchronously find files and folders
    loop = asyncio.get_event_loop()
    tasks = []
    
    for item in Path(directory).rglob('*'):
        tasks.append(loop.run_in_executor(None, item.stat))

    stats = await asyncio.gather(*tasks)
    
    for item, item_metadata in zip(Path(directory).rglob('*'), stats):
        item_uuid = item_metadata.st_uid

        # If search term is provided, filter by file or folder name
        if search is not None and search not in item.name:
            continue

        # Check if item is a file with the correct extension
        if item.is_file() and any(item.suffix == ext for ext in extensions):
            result.append({
                "file_path": str(item.relative_to(directory)),
                "is_owner": item_uuid == user_uuid,
                "is_folder": False  # Indicate it's a file
            })

        # If item is a folder
        elif item.is_dir():
            result.append({
                "file_path": str(item.relative_to(directory)),
                "is_owner": item_uuid == user_uuid,
                "is_folder": True  # Indicate it's a folder
            })

    return result

async def add_dataset(model_id: int, dataset_id : int, training_data_path : str):
    
    dataset_info = await db_model.get_dataset_model(dataset_id=dataset_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=dataset_info["workspace_id"])
    training_data_full_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , \
            ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"], DATA_PATH=training_data_path)
    if check_file_exists(file_path=training_data_full_path):
        await db_model.create_fine_tuning_dataset(training_data_path=training_data_path, dataset_id=dataset_id, model_id=model_id)
    
        return True
    return False
#==========
    

async def get_models(workspace_id : int, header_user_id : int) -> List[dict]:

    models = await db_model.get_models(workspace_id=workspace_id)

    models_parse = []   

    redis_client = await get_redis_client_async()


    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)

    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}

    favorites_model = await db_model.get_favorite_models(header_user_id)

    favorites_model_id = [model["model_id"] for model in favorites_model]
    
    async def process_model(model):
        private_users  = await db_model.get_model_user_list(model_id=model["id"])
        res = {
            "id" : model["id"],
            "name" : model["name"],
            "bookmark" : model["id"] in favorites_model_id,
            "is_access" :  True if model["access"] == 1 or header_user_id in [user["user_id"] for user in private_users]  else False,
            "users" : private_users,
            "status" : {
                "fine_tuning" : model["latest_fine_tuning_status"],
                "commit" : model["commit_status"]
                },
            "create_user_name" : model["create_user_name"],
            "update_datetime" : model["update_datetime"],
            "create_datetime" : model["create_datetime"],
            "description" : model["description"]
        }
        if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
            if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model["id"]),{}):
                res["status"]["fine_tuning"] = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model["id"])]["status"]
        
        return res
        

    models_parse = await asyncio.gather(*(process_model(model) for model in models))

    return models_parse

async def get_commit_models(model_id : int) -> List[dict]:
    
    model_info = await db_model.get_model(model_id=model_id)
    
    commit_models = await db_model.get_commit_models(model_id=model_id)
    
          
    return {
        "list" : commit_models,
        "model_name" : model_info["name"]
    }

async def get_commit_model(commit_model_id : int):
    commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
    model_info = await db_model.get_model(model_id=commit_model_info["model_id"])
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    config = json.loads(commit_model_info.get("fine_tuning_config", "{}"))
    if commit_model_info["name"] != "source_model":
        try:
            commit_log_path = PATH.JF_MODEL_COMMIT_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                    WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"]) + "/{}".format(commit_model_info["name"])
            log_parser, _ = await parse_tensorboard_scalars_async(log_dir=commit_log_path)
            commit_model_info["result_log"] = log_parser
        except Exception as e:
            commit_model_info["result_log"] = {}
    return commit_model_info    


async def load_commit_model(commit_model_id : int) -> dict:
    commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
    if commit_model_info:
        model_id = commit_model_info["model_id"]
        model_info = await db_model.get_model(model_id=model_id)
        # workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
        # TODO
        # latest_checkpoint 에 있는 모델 삭제 후 해당 모델 copy
        latest_checkpoint_path = PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(MODEL_NAME=model_info["name"])
        load_model_path = PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_info["name"], COMMIT_NAME=commit_model_info["name"])
        
        res , message = await load_or_stop_helm(workspace_id=model_info["workspace_id"], model_id=model_id, latest_checkpoint_path=latest_checkpoint_path, load_commit_model_path=load_model_path)
        if res :
            await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_model_id, commit_type=TYPE.COMMIT_TYPE_LOAD)
        return res
    return False

async def update_model_description(model_id : int, description : str):
    res = await db_model.update_model_description(model_id=model_id, description=description)
    return res

async def update_model(model_id :int , description : str, access : int, create_user_id : int, user_list : List[int]) -> bool:
    
    try:
        res = await db_model.update_model(model_id=model_id, description=description, access=access, create_user_id=create_user_id)
        print(res)
        old_user_list = await db_model.get_model_user_list(model_id=model_id)
        old_user_list = [user["user_id"] for user in old_user_list]
        insert_user_list = list(set(user_list) - set(old_user_list))
        delete_user_list = list(set(old_user_list) - set(user_list))
        for user_id in delete_user_list:
            await db_model.delete_model_user_list(model_id=model_id, user_id=user_id)
        if insert_user_list:
            await db_model.create_model_user_list(model_id=model_id, user_list=insert_user_list)
        
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def set_bookmark_model(model_id : int, header_user_id : int):
    try:
        is_favorite_model = await db_model.get_favorite_model(model_id=model_id, user_id=header_user_id)
        if is_favorite_model:
            # 삭제
            await db_model.delete_favorite_model(model_id=model_id, user_id=header_user_id)
        else:
            # 추가 
            await db_model.create_favorite_model(model_id=model_id, user_id=header_user_id)
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def get_model_summary(model_id: int):
    model_info = await db_model.get_model(model_id=model_id)
    return {
        "name" : model_info["name"],
        "description" : model_info["description"],
        "huggingface_model_id" : model_info["huggingface_model_id"],
        "commit_model_name" : model_info["commit_model_name"],
        "create_user_name" : model_info["create_user_name"],
        "create_datetime" : model_info["create_datetime"],
        "update_datetime" : model_info["update_datetime"]
    }

async def create_commit_model(commit_name : str, commit_message : str, model_id : int, create_user_id : int) -> bool:
    
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    tmp_path = PATH.JF_MODEL_TMP_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    if not model_info:
        raise Exception(f"Error: not exist model")
    
    # duplicate check
    if await db_model.check_commit_model_by_name(model_id=model_id, commit_name=commit_name):
        raise Exception(f"Error: duplicate commit model name")
    
    redis_client = await get_redis_client_async()
    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    fine_tuning_status = TYPE.KUBE_POD_STATUS_DONE
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
    
    # model status check
    if model_info["latest_fine_tuning_status"] not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP]:
    # if any(status not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP] 
    #    for status in [fine_tuning_status, model_info["latest_fine_tuning_status"]]):
        raise Exception(f"Error: incomplete model")
    # adapter_model.safetensors, model.safetensors, adapter_config.json, config.json이 있는지 조사 
    if await check_model_files(tmp_path):
        raise Exception(f"Error: Invalid model")
    
    try:       
        commit_model_id = await db_model.create_commit_model(model_id=model_id, workspace_id=model_info["workspace_id"], create_user_id=create_user_id, fine_tuning_config=model_info["latest_fine_tuning_config"],
                                        commit_message=commit_message, name=commit_name, model_description=model_info["description"], steps_per_epoch=model_info["steps_per_epoch"]) 
        if commit_model_id:
            # TODO
            # model 이동
            res , message = await create_model_helm(workspace_id=model_info["workspace_id"], model_id=model_id, model_name=model_info["name"], commit_model=model_info["name"], \
                    save_commit_name=commit_name)
            if res:
                await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_model_id, commit_type=TYPE.COMMIT_TYPE_COMMIT)
            
            return res
        return False
            
    except Exception as e:
        if commit_model_id:
            await db_model.delete_commit_model(commit_model_id=commit_model_id)
            workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
            await delete_commit_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=commit_name)
        return False
            
async def create_model(workspace_id : int, model_name : str, description : str, create_user_id : int, private : int, huggingface_model_id : str = None, \
    commit_model_id : int = None, huggingface_token : str = None, access : int = 0, users_id : List[int] = []) -> bool:
    commit_model_info = {}
    model_id = None
    huggingface_git = None
    try:
        # check duplicate model name
        if await db_model.check_model_by_model_name(model_name=model_name, workspace_id=workspace_id):
            raise Exception(f"Error: model name duplicated")
        
        workspace_info = await db_model.get_workspace_model(workspace_id=workspace_id)
        
        if huggingface_model_id: # huggingface model download
            # 유효한 token인지 확인하는 작업 필요
            if not private: # 퍼블릭일 경우 회사 계정을 사용 
                huggingface_token = settings.HUGGINGFACE_TOKEN
            else:
                huggingface_token = front_cipher.decrypt(huggingface_token)
                # huggingface_token = huggingface_token
            if await check_model_access(model_id=huggingface_model_id, token=huggingface_token, model_create=True):
                huggingface_git = TYPE.HUGGINGFACE_MODEL_GIT.format(MODEL_ID=huggingface_model_id)
                model_id = await db_model.create_model(workspace_id=workspace_id, name=model_name, create_user_id=create_user_id, \
                    huggingface_model_id=huggingface_model_id, huggingface_token=huggingface_token, description=description, huggingface_git=huggingface_git, access=access)
            else:
                raise Exception(f"Error: Cannot access the model '{huggingface_model_id}' with the provided token.")
            
        elif commit_model_id: # workspace commit model copy 
            commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
            huggingface_git = commit_model_info["huggingface_git"]
            model_id = await db_model.create_model(workspace_id=workspace_id, name=model_name, create_user_id=create_user_id, latest_fine_tuning_config=commit_model_info["fine_tuning_config"], \
                commit_model_name="{}/{}".format(commit_model_info["model_name"], commit_model_info["name"]) , description=description, huggingface_git=huggingface_git, huggingface_model_id=commit_model_info["huggingface_model_id"], access=access)
            
        if model_id:
            # 사용자 추가 
            # print(users_id)
            if users_id:
                await db_model.create_model_user_list(model_id=model_id, user_list=users_id)
            # mkdir commit_model, source_model
            await create_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_name)
            # model copy or download
            # create helm 
            res , message = await create_model_helm(workspace_id=workspace_id, model_id=model_id, model_name=model_name, commit_model=commit_model_info.get("model_name",None), \
                commit_name=commit_model_info.get("name", None), huggingface_model_id=huggingface_model_id, huggingface_token=huggingface_token)
            if res == False:
                import sys
                print(f"Error: {message}", file=sys.stderr)
                raise Exception
            # create commit model 
            commit_id = await db_model.create_commit_model(model_id=model_id, create_user_id=create_user_id, workspace_id=workspace_id, fine_tuning_config=FineTuningConfig().model_dump_json(),
                                               commit_message="", name=TYPE.MODEL_FIRST_COMMIT_NAME, model_description=description)
            await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_id, commit_type=TYPE.COMMIT_TYPE_DOWNLOAD)
            
            
            return res
        return False
    except Exception as e:
        traceback.print_exc()
        if model_id:
            await db_model.delete_model(model_id=model_id)
            # rm model dir
            await delete_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_name)
        return False

async def delete_model(model_id : int) -> bool:
    
    model_info = await db_model.get_model(model_id=model_id)
    
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    
    # 현재 동작 중인지 확인
    redis_client = await get_redis_client_async()
    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            raise Exception(f"현재 파인튜닝중입니다. 해당 작업을 종료 후 진행해 주세요.")

    # 해당 모델을 다운 받고 있을 경우
    model_commit_helm_repo_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
    await delete_helm_repo(helm_repo_name=model_commit_helm_repo_name, workspace_id=model_info["workspace_id"])

    await db_model.delete_model(model_id=model_id)
    await delete_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"])
    
    return True

async def delete_model_dataset(model_dataset_id : int) -> bool:
    
    res = await db_model.delete_model_dataset(model_dataset_id=model_dataset_id)
    return res

async def delete_model_configuration(model_config_id : int) -> bool:
    
    model_config_file_info = await db_model.get_fine_tuning_config_file(model_config_id=model_config_id)
    model_info = await db_model.get_model(model_id=model_config_file_info["model_id"])
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    config_file_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=model_config_file_info["file_name"])
    if await common.async_delete_file(file_path=config_file_path):
        await db_model.delete_model_configuration(model_config_id=model_config_id)
        return True
    return False

async def get_model_fine_tuning(model_id : int) -> dict:
    
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    if model_info["latest_fine_tuning_config"] is None:
        fine_tuning_config = FineTuningConfig().model_dump()
    else:
        fine_tuning_config = json.loads(model_info["latest_fine_tuning_config"])
    model_datasets = await db_model.get_model_datasets(model_id=model_id)
    config_file_list = await db_model.get_fine_tuning_config_files(model_id=model_id)
    commit_list = await db_model.get_commit_models(model_id=model_id)
    # TODO
    # 1. latest_fine_tuning_status 에 따라 graph 보여주고 말고 추가
    # 2. model_dataset 이 실제로 존재하는지 check
    # 3. fine tuning 중인지 확인 (db에 있는걸로 할까 싶음)
    
    model_dataset_parse = []
    
    for model_dataset in model_datasets:
        data_path = model_dataset["training_data_path"]
        data_full_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=model_dataset["data_storage_name"] ,WORKSPACE_NAME=model_dataset["workspace_name"] , \
            ACCESS=model_dataset["access"] , DATASET_NAME=model_dataset["dataset_name"], DATA_PATH=data_path)
        data_exist = await check_file_exists(file_path=data_full_path)
        model_dataset_parse.append({
            "id" : model_dataset["id"],
            "dataset_name" : model_dataset["dataset_name"],
            "model_file_path" : data_path,
            "data_exist" : data_exist
        })
        
    config_file_parse = []
    
    for config_file in config_file_list:
        file_name = config_file["file_name"]
        config_file_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=file_name)
        file_exist = await check_file_exists(file_path=config_file_path)
        config_file_parse.append({
            "id" : config_file["id"],
            "file_name" : file_name,
            "file_size" : config_file["size"],
            "file_exist" : file_exist
        })
    
    # log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
    #     WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    # log_parser = await parse_tensorboard_scalars_async(log_dir=log_path)
    instance_info = db_instance.get_instance(instance_id=model_info["instance_id"])
    
    resource_info = await workspace_resource.get_workspace_instance_total_info(instance_id=model_info["instance_id"], workspace_id=model_info["workspace_id"], instance_allocate=model_info["instance_count"], resource_limit=[{
        "cpu_limit" : instance_info["cpu_allocate"]*model_info["instance_count"],
        "ram_limit" : instance_info["ram_allocate"]*model_info["instance_count"],
    }]) if  model_info["instance_id"] else {}
    
    # resource_info = {
    #     "instance_id" : model_info["instance_id"],
    #     "instance_count" : model_info["instance_count"],
    #     "instance_name" : model_info["instance_name"],
    #     "gpu_count" : model_info["gpu_count"],
    #     "pod_count" : model_info["pod_count"],
    #     "cluster_type" : "auto"
    # } if  model_info["instance_id"] else {}
    
    latest_commit_info = await db_model.get_commit_model(commit_id=model_info["latest_commit_id"])
    
    return {
        "commit_model_count" : len(commit_list),
        "model_id" : model_info["id"],
        "model_name" : model_info["name"],
        "steps_per_epoch" : model_info["steps_per_epoch"],
        "huggingface_git" : model_info["huggingface_git"],
        "huggingface_mode_id" : model_info["huggingface_model_id"],
        "commit_model_name" : model_info["commit_model_name"],
        "resource_info" : resource_info,
        "fine_tuning_config" : fine_tuning_config,
        "model_datasets" : model_dataset_parse,
        "model_config_file_list" : config_file_parse,
        "latest_commit_info" : {
            "id" : latest_commit_info["id"],
            "name" : latest_commit_info["name"]
        }
        # "fine_tuning_log" : log_parser
    }

async def running_fine_tuning(model_id : int, model_dataset_id : int, instance_id : int, instance_count : int,\
    gpu_count : int, fine_tuning_config : FineTuningConfig = FineTuningConfig()) -> True:
    
    # TODO
    # 1. 현재 commit 중인지 fine tuning 중인지 확인 
    
    # 2. cluster auto case 로 실행 할 수 있는 리스트 받아서 해당 case 로 pod info 생성 
    
    # 3. pod info에 추가 
    redis_client = await get_redis_client_async()
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    
    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    fine_tuning_status = None
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
    
    # redis 에서 상태값 가져와서 확인 없으면 db 값으로 진행 
    # TODO 
    # 추후 redis 상태값으로 변경
    if model_info["commit_status"] == TYPE.KUBE_POD_STATUS_RUNNING:
        raise Exception(f"Error: Model is commit")
    
    # if any(status not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR] 
    #    for status in [fine_tuning_status, model_info["latest_fine_tuning_status"]]):
    if  model_info["latest_fine_tuning_status"] not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR] :
        raise Exception(f"Error: Model is already running")
    
    commit_model_info = await db_model.get_commit_model(commit_id=model_info["latest_commit_id"])
    
    #  latest_checkpoint가 비어 있는지 확인 
    latest_checkpoint_path = PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    if await is_folder_empty(latest_checkpoint_path):
        commit_model_path = PATH.JF_MODEL_COMMIT_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])\
            + "/{}".format(commit_model_info["name"])
        await common.async_copy_directory_contents(commit_model_path, latest_checkpoint_path)
    
    # model_dataset_info = await db_model.get_model_dataset(model_dataset_id=model_dataset_id)
    
    used_cluster_case = dict()
    gpu_cluster_auto = False
    if gpu_count > 1:
        gpu_cluster_auto = True
        gpu_cluster_info = await common.get_gpu_cluster_info(instance_id=instance_id, redis_client=redis_client)
        gpu_cluster_cases = await common.get_auto_gpu_cluster(redis_client=redis_client, instance_id=instance_id, gpu_count=gpu_count, gpu_cluster_info=gpu_cluster_info)
        # gpu_cluster_cases = sorted(gpu_cluster_cases, key=lambda x:x["gpu_count"])
        used_cluster_case = gpu_cluster_cases[0] # TODO 가장 좋은 cluster 유형만 선택
    
    pod_info = FineTuningPodInfo(
        model_id=model_id,
        model_name=model_info["name"],
        commit_id=model_info["latest_commit_id"],
        commit_name=commit_model_info["name"],
        workspace_id=model_info["workspace_id"],
        workspace_name=model_info["workspace_name"],
        instance_count=instance_count,
        model_dataset_id=model_dataset_id,
        image_name=settings.FINE_TUNING_IMAGE, #"192.168.1.150:30500/jfb-system/fine_tuning:0.2.0",
        owner_id=model_info["create_user_id"],
        gpu_count=gpu_count,
        gpu_cluster_auto=gpu_cluster_auto,
        gpu_auto_cluster_case=used_cluster_case,
        instance_id=instance_id,
        resource_type=TYPE.RESOURCE_TYPE_GPU,
        pod_type=TYPE.FINE_TUNING_TYPE,
        fine_tuning_config=fine_tuning_config,
    )
    # Model 상태값 수정
    await db_model.update_model_fine_tuning_status(status=TYPE.KUBE_POD_STATUS_PENDING, model_id=model_id, steps_per_epoch=0)
    await db_model.update_model_fine_tuning_instance(instance_id=instance_id, instance_count=instance_count, \
        gpu_count=gpu_count, model_id=model_id, fine_tuning_config=fine_tuning_config.model_dump_json())
    
    print(pod_info)
    topic = topic_key.SCHEDULER_TOPIC
    # if project_tool_info.gpu_count > 0:
    #     topic = topic_key.PROJECT_TOPIC.format(project_info["id"], "GPU")
    # else:
    #     topic = topic_key.PROJECT_TOPIC.format(project_info["id"], "CPU")
    
    producer = AIOKafkaProducer(
    bootstrap_servers=settings.JF_KAFKA_DNS,
    value_serializer=lambda v: v.encode('utf-8'),  # 문자열 값을 바이트로 직렬화
    # key_serializer=lambda v: v.encode('utf-8')    # 문자열 키를 바이트로 직렬화
    )
    # 프로듀서 시작
    await producer.start()
    try:
        # 메시지 보내기
        message = pod_info.model_dump_json()
        await producer.send_and_wait(topic, value=message)
    finally:
        # 프로듀서 종료
        await producer.stop()
    
    return True

async def stop_fine_tuning(model_id : int):
    
    model_info = await db_model.get_model(model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    fine_tuning_repo = TYPE.FINE_TUNING_REPO_NAME.format(model_id)
    # helm 삭제
    res, message = await delete_helm_repo(helm_repo_name=fine_tuning_repo, workspace_id=model_info["workspace_id"])
    await db_model.update_model_fine_tuning_status(status=TYPE.KUBE_POD_STATUS_STOP, model_id=model_id)
    tmp_path = PATH.JF_MODEL_TMP_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    # checkpoint- 폴더 하위 정보 위치 이동 
    if not await move_checkpoint_files_to_parent(tmp_path):
        # 체크포인트가 없다면 commit하지 않음
        return False, "not exist checkpoint"
    
    latest_checkpoint_path = PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(MODEL_NAME=model_info["name"])
    tmp_model_path = PATH.JF_POD_MODEL_TMP_MODEL_PATH.format(MODEL_NAME=model_info["name"])
    # latest 폴더 비우기
    res , message = await load_or_stop_helm(workspace_id=model_info["workspace_id"], model_id=model_id, latest_checkpoint_path=latest_checkpoint_path, tmp_model_path=tmp_model_path)
    if res:
        await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=model_info["latest_commit_id"], commit_type=TYPE.COMMIT_TYPE_STOP)
        return res, "success"
    return res, message

async def get_efk_fine_tuning_logs(model_id : int, pod_name : str, count : int = 100, is_all : bool = True):
    request_log_data = {
            "modelId" : model_id,
            "podName" : pod_name,
            "count" : count, # 최근 1000개,
            "offset" : 0
        }
    logs = {}
    if is_all:
        # logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/all", data=request_log_data)
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/all", data=request_log_data)
        
    else: 
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/figure", data=request_log_data)
    return logs 

async def get_fine_tuning_system_log(model_id : int, count : int = 100, is_download : bool = False):
    model_info = await db_model.get_model(model_id=model_id)
    if model_info["start_datetime"]:
        base_pod_name, unique_pod_name, container_name = PodName(workspace_name=model_info["workspace_id"], item_name=model_id, \
            item_type=TYPE.FINE_TUNING_TYPE, start_datetime=model_info["start_datetime"]).get_all()
        logs = await get_efk_fine_tuning_logs(model_id=model_id, pod_name=unique_pod_name, count=count)
        if logs:
            logs_line = [log['fields']['log'] for log in logs["logs"]] 
            if is_download:
                return await common.text_response_generator_async(data_str="\n".join(logs_line) , filename="[FINETUNING]{}_system.log".format(model_info["name"]))
            return "\n".join(logs_line) 
    return ""

async def upload_fine_tuning_configuration(file: UploadFile, model_id : int):
    
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    sanitize_filename = common.sanitize_filename(filename=file.filename)
    model_config_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=sanitize_filename)
    file_size = 0
    with open(model_config_path, "wb") as f:
        contents = await file.read()
        file_size = len(contents)
        f.write(contents)
    
    await db_model.create_fine_tuning_config_file(file_name=sanitize_filename, model_id=model_id, size=file_size)
    
    
    return True


async def get_fine_tuning_result_logs(model_id : int):
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    log_parser, _ = await parse_tensorboard_scalars_async(log_dir=log_path)
    return log_parser

def calculate_remaining_time_with_ema(
    start_time, current_time, current_step, total_steps, ema_factor=0.9, last_time_per_step=None
):
    """
    지수 이동 평균(EMA)을 사용하여 스텝당 소요 시간을 계산하고 잔여 시간을 추정합니다.

    Args:
        start_time (datetime.datetime): 학습 시작 시간 (datetime 객체).
        current_time (float): 현재 시간 (UNIX timestamp).
        current_step (int): 현재까지 완료된 스텝 수.
        total_steps (int): 학습 전체 스텝 수.
        ema_factor (float, optional): EMA 계수 (0.0 ~ 1.0). 기본값은 0.9.
        last_time_per_step (float, optional): 이전 스텝당 소요 시간.

    Returns:
        tuple: (잔여 시간, 새로운 EMA 기반 스텝당 소요 시간)
    """
    if current_step <= 0 or total_steps <= current_step:
        raise ValueError("현재 스텝은 0보다 커야 하며, 총 스텝보다 작아야 합니다.")

    # datetime 객체를 UNIX timestamp로 변환
    start_time_unix = start_time.timestamp()

    # 경과 시간 계산
    elapsed_time = current_time - start_time_unix

    # 스텝당 소요 시간 계산 (EMA 적용)
    current_time_per_step = elapsed_time / current_step
    if last_time_per_step is not None:
        time_per_step = ema_factor * last_time_per_step + (1 - ema_factor) * current_time_per_step
    else:
        time_per_step = current_time_per_step

    # 잔여 스텝 계산
    remaining_steps = total_steps - current_step

    # 잔여 시간 계산
    remaining_time = remaining_steps * time_per_step

    return remaining_time, time_per_step



async def sse_get_fine_tuning_result_graph(model_id : int, request : Request):
        old_history = None
        old_datetime = datetime.datetime.now()
        try:
            while True:
                if await request.is_disconnected():
                    break
                current_datetime = datetime.datetime.now()
                try:
                    model_info = await db_model.get_model(model_id=model_id)
                    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
                    log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
                    
                    result = None
                    if model_info["steps_per_epoch"]:
                        try:
                            log_parser, _ = await parse_tensorboard_scalars_async(log_dir=log_path)
                            # 파싱 결과가 비어있지 않은 경우에만 사용
                            if log_parser and len(log_parser) > 0:
                                result = {
                                    "graph" : log_parser
                                }
                            else:
                                # 파싱 결과가 비어있으면 이전 결과 유지
                                result = None
                        except Exception as parse_error:
                            # 파싱 실패 시 로그만 남기고 이전 결과 유지
                            traceback.print_exc()
                            print(f"Failed to parse tensorboard logs: {parse_error}")
                            result = None
                    
                    # result가 None이면 이전 결과 유지
                    if result is None:
                        if old_history is not None:
                            # 이전 결과가 있으면 유지
                            result = old_history
                        else:
                            # 이전 결과도 없으면 빈 그래프 반환
                            result = {
                                "graph" : {}
                            }
                    
                    # 결과가 변경된 경우에만 전송 (빈 데이터와 데이터 사이의 불필요한 전환 방지)
                    if result != old_history:
                        old_history = result
                        old_datetime = current_datetime
                        yield f"data: {json.dumps(result)}\n\n"
                    elif (current_datetime - old_datetime).total_seconds() >=30:
                        # 30초마다 하트비트 전송 (이전 결과 전송)
                        old_datetime = current_datetime
                        if old_history is not None:
                            yield f"data: {json.dumps(old_history)}\n\n"
                    
                except Exception as loop_error:
                    # 루프 내부 예외 처리 (DB 조회 실패 등)
                    traceback.print_exc()
                    print(f"Exception in SSE loop: {loop_error}")
                    # 예외 발생 시 이전 결과 유지 또는 빈 결과 반환
                    if old_history is None:
                        old_history = {
                            "graph" : {}
                        }
                
                await asyncio.sleep(1)
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            pass


async def sse_get_fine_tuning_time(model_id : int, request : Request):
    old_history = None
    last_time_per_step = None
    old_datetime = datetime.datetime.now()
    try:
        while True:
            if await request.is_disconnected():
                break
            current_datetime = datetime.datetime.now()
            model_info = await db_model.get_model(model_id=model_id)
            workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
            log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
            config_json =model_info.get("latest_fine_tuning_config") if model_info.get("latest_fine_tuning_config") else "{}"
            config = json.loads(config_json)
            
            if model_info["steps_per_epoch"]:
                total_step = model_info["steps_per_epoch"] * config["num_train_epochs"]
                _, latest_steps = await parse_tensorboard_scalars_async(log_dir=log_path)
                latest_step = latest_steps
                if latest_steps:
                    remaining_time, new_time_per_step = calculate_remaining_time_with_ema(
                        start_time=datetime.datetime.strptime(model_info["start_datetime"], TYPE.TIME_DATE_FORMAT),
                        current_time=datetime.datetime.now().timestamp(),
                        current_step=latest_step,
                        total_steps=total_step,
                        ema_factor=0.9,
                        last_time_per_step=last_time_per_step  # 이전 EMA 값
                    )
                    last_time_per_step = new_time_per_step
                    result = {
                        "total_epoch" : config.get("num_train_epochs", 0),
                        "start_datetime" : model_info["start_datetime"],
                        "progress_epoch" : latest_step//total_step,
                        "percent" : round((latest_step/total_step) * 100, 2),
                        "remaining_time" : remaining_time,
                    }
                else:
                    result = {
                        "total_epoch" : config.get("num_train_epochs", 0),
                        "start_datetime" : model_info["start_datetime"],
                        "progress_epoch" : 0,
                        "percent" : 0,
                        "remaining_time" : None
                    }
            else:
                result = {
                    "total_epoch" : config.get("num_train_epochs", 0),
                    "start_datetime" : model_info["start_datetime"],
                    "progress_epoch" : 0,
                    "percent" : 0,
                    "remaining_time" : None
                }
            if result != old_history:
                old_history = result
                old_datetime = current_datetime
                yield f"data: {json.dumps(result)}\n\n"
            elif (current_datetime - old_datetime).total_seconds() >=30:
                old_datetime = current_datetime
                yield f"data: {json.dumps(old_history)}\n\n"
            await asyncio.sleep(1)
    except Exception as e:
        # 예외 처리 및 로그 남기기
        traceback.print_exc()
        print(f"Exception in SSE stream: {e}")
    finally:
        # 연결이 끊어졌을 때의 후속 처리
        pass


async def sse_get_fine_tuning_status(model_id : int, request : Request):
        old_history = None
        old_datetime = datetime.datetime.now()
        try:
            redis_client = await get_redis_client_async()
            while True:
                current_datetime = datetime.datetime.now()
                model_info = await db_model.get_model(model_id=model_id)
                if await request.is_disconnected():
                    break
                model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
                if model_pod_status:
                    model_pod_status = json.loads(model_pod_status)
                else:
                    model_pod_status = {}
                fine_tuning_status = None
                fine_tuning_reason = None
                if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
                    if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
                        fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
                        fine_tuning_reason = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["reason"]
                    if model_info["latest_fine_tuning_status"] == TYPE.KUBE_POD_STATUS_STOP:
                        fine_tuning_status = TYPE.KUBE_POD_STATUS_STOP
                        fine_tuning_reason = "User stop"
                res = {
                    "fine_tuning_status" : {
                        "status" :   fine_tuning_status if fine_tuning_status else model_info["latest_fine_tuning_status"],
                        "reason" : fine_tuning_reason,
                    },
                    "commit_status" : {
                        "status" : model_info["commit_status"],
                        "type" : model_info["commit_type"],
                        "reason" : "",
                    },
                }
                if res != old_history:
                    old_history = res
                    old_datetime = current_datetime
                    yield f"data: {json.dumps(res)}\n\n"
                elif (current_datetime - old_datetime).total_seconds() >=30:
                    old_datetime = current_datetime
                    yield f"data: {json.dumps(old_history)}\n\n"
                
                await asyncio.sleep(1)
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            pass