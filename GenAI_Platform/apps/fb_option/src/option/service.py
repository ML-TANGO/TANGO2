import traceback, string, os, random, json, subprocess, time, asyncio, aiofiles
import pandas as pd
from pathlib import Path
from utils import TYPE, settings, PATH, db, common, workspace_resource, TYPE_BUILT_IN
from utils.exception.exceptions import *
from utils.crypt import front_cipher
from requests.exceptions import HTTPError, ConnectionError, Timeout
from huggingface_hub import login, model_info, HfApi
from typing import List, Dict, Any
import io
from utils.msa_db import db_project

async def get_list(workspace_id=None, user_id=None):
    result = []
    try:
        pass
    except:
        traceback.print_exc()
    return result


# ==================================================================
# COMMON
# ==================================================================

def get_built_in_model_category():
    return TYPE_BUILT_IN.BUILT_IN_MODEL_CATEGORY

async def get_built_in_models(category : str):
    from utils.msa_db import db_project
    model_list = await db_project.get_built_im_model_list(category=category)
    return [{"name" : model["name"], "huggingface_model_id" : model["huggingface_model_id"]} for model in model_list]

async def get_built_in_models_project(workspace_id):
    result = []
    try:
        project_list = db_project.get_project_list(workspace_id=workspace_id, project_type=TYPE.PROJECT_TYPE_C)
        for item in project_list:
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name"),
                "access" : item.get("access"),
            })
    except:
        traceback.print_exc()
    return result

async def get_project_by_huggingface(workspace_id):
    result = []
    try:
        project_list = db_project.get_project_list(workspace_id=workspace_id, project_type=TYPE.PROJECT_TYPE_B)
        for item in project_list:
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name"),
                "access" : item.get("access"),
            })
    except:
        traceback.print_exc()
    return result

async def get_project_job_hps_list(project_id):
    result = []
    try:
        job_list = await db_project.get_trainings_new(project_id=project_id)
        hps_list = await db_project.get_hps_list(project_id=project_id)
        for item in job_list:
            if item.get("end_datetime") is None:
                continue
            result.append({
                "type" : "job",
                "id" : item.get("id"),
                "name" : item.get("name"),
                "start_datetime" : item.get("start_datetime"),
                "project_id" : item.get("project_id")
            })
        for item in hps_list:
            if item.get("end_datetime") is None:
                continue
            print(item)
            result.append({
                "type" : "hps",
                "id" : item.get("id"),
                "name" : item.get("name"),
                "start_datetime" : item.get("start_datetime"),
                "project_id" : item.get("project_id")
            })
        result = sorted(result, key=lambda x: x['project_id'])
    except:
        traceback.print_exc()
    return result

async def get_workspace_user_list(workspace_id):
    result = []
    try:
        for item in db.get_user_list_in_workspace(workspace_id=workspace_id):
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name")
            })
    except Exception as e:
        traceback.print_exc()
    return result

async def get_workspace_instance_list(workspace_id):
    result = []
    try:
        for item in db.get_workspace_instance_list(workspace_id=workspace_id):
            result.append({
                "instance_id" : item.get("instance_id"),
                "instance_name" : item.get("instance_name"),
                "gpu_name" : item.get("resource_name"),
                "gpu_allocate" : item.get("gpu_allocate"),
                "cpu_allocate" : item.get("cpu_allocate"),
                "ram_allocate" : item.get("ram_allocate"),
                "instance_total" : item.get("instance_allocate"), # 전체 총량이 아닌 워크스페이스에 할당된 총량
                # 사용가능, 할당량은 리스트 목록 조회시 확인
            })
    except Exception as e:
        traceback.print_exc()
    return result

async def get_file_list_from_src(file_extension: list, base_path : str,  ignore_folders: list = None, replace_file_path: str = TYPE.PROJECT_TYPE, search_index : int = 0):
    if type(file_extension) != list:
        file_extension = [file_extension]
        
    if ignore_folders is None:
        ignore_folders = ['datasets','.ipynb_checkpoints', 'datasets_rw', 'datasets_ro']
    
    return common.get_files_streaming(base_path=base_path, file_extension=file_extension, ignore_folders=ignore_folders, replace_file_path=replace_file_path, search_index=search_index)

async def get_file_list_from_src_old(file_extension: list, base_path : str,  ignore_folders: list = None, replace_file_path: str = TYPE.PROJECT_TYPE):
    if type(file_extension) != list:
        file_extension = [file_extension]
        
    if ignore_folders is None:
        ignore_folders = ['datasets','.ipynb_checkpoints', 'datasets_rw', 'datasets_ro']
    
    return await common.get_files(base_path=base_path, file_extension=file_extension, ignore_folders=ignore_folders, replace_file_path=replace_file_path)

async def get_built_in_model_readme_download(project_id : int):
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    if project_info["category"] and project_info["built_in_model"]:
        built_in_model_info = await db_project.get_built_in_model(category=project_info["category"], name=project_info["built_in_model"])
        return  io.BytesIO(built_in_model_info["readme"].encode("utf-8")), "{}_{}.md".format(project_info["category"], project_info["built_in_model"])
    else:
        raise Exception("not built in model project")


# ==================================================================
# DATASET
# ==================================================================
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

async def get_dataset_search_data(dataset_id : int, search_user_id : int, search : str = None):
    dataset_info = db.get_dataset(dataset_id=dataset_id)
    workspace_info = await db.get_workspace_model(workspace_id=dataset_info["workspace_id"])
    dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , \
            ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"])
    files_and_folders = await find_files_and_folders_by_extension(directory=dataset_path, extensions=TYPE.MODEL_DATA_EXTENSIONS, search_user_id=search_user_id, search=search)
    
    return files_and_folders

async def get_workspace_dataset_list(workspace_id):
    """
    데이터셋 리스트만 내려줌 (폴더, 파일은 안내려줌)
    """
    result = []
    try:
        dataset_list = await db.get_dataset_list_new(workspace_id=workspace_id)
        for item in dataset_list:
            result.append({
                "id" : item.get("id"),
                "name" : item.get("dataset_name"),
                "owner" : item.get("owner")
            })
    except Exception as e:
        traceback.print_exc()
    return result

# get_data_hierarchy_list, get_data_simple_list -------------------
async def get_dataset_data_list(dataset_id, extension_list=[], search=None, hierarchy=False):
    """
    데이터셋 아이디에 해당하는 데이터를 내려줌 (폴더, 파일 내려줌)
    extension_list: 파일 조회할 확장자 리스트 ex) extension_list=['.csv', '.txt'] / 전체 조회는 빈리스트 사용

    hierarchy
    - simple : 
        [
            {"owner": "...", "name": "folder1/folder1_1/a.txt"},
            {"owner": "klod", "name": "folder2/folder2_1/a.txt"}
        ],
    - hierarchy: 
        [{
            "type": "file",
            "owner": "...",
            "name": "playground.txt"
        },
        {
            "type": "folder",
            "owner": "...",
            "name": "test",
            "sub_list": [
                {
                    "type": "folder",
                    "owner": "...",
                    "name": "test2"
                }
            ]
        }]
    """
    result = []
    try:
        dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
        storage_name = dataset_info.get("data_storage_name")
        workspace_name = dataset_info.get("workspace_name")
        # user_uuid = int(user_id) + int(settings.USER_UUID_SET)

        directory = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, 
                                                        ACCESS=dataset_info.get("access"), DATASET_NAME=dataset_info.get("name"))

        # Check if directory exists
        if not os.path.exists(directory):
            return result
        
        if hierarchy:
            # 계층구조 
            result = await get_data_hierarchy_list(directory=directory, extension_list=extension_list, search=search, base_path=directory)
        else:
            # name을 fullPath로 출력하여 리스트로 내려줌 
            result = await get_data_simple_list(directory=directory, extension_list=extension_list, search=search)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_data_hierarchy_list(directory, extension_list, search, base_path="", max_depth=None):
    """
    디렉터리 내 파일 및 폴더를 계층 구조로 반환합니다.
    - max_depth: 탐색 깊이 제한 (None이면 무제한). 0이면 현재 디렉터리 내 항목만.
    """
    result = []
    try:
        root = Path(directory)

        def build_tree(path: Path, depth: int):
            items = []
            # 깊이 제한을 넘으면 빈 리스트 반환
            if max_depth is not None and depth > max_depth:
                return items
            for entry in sorted(path.iterdir()):
                # 검색어가 있으면 이름에 포함된 항목만
                if search and search not in entry.name:
                    continue
                if entry.is_file():
                    # 확장자 필터링
                    if extension_list and entry.suffix not in extension_list:
                        continue
                    stat = entry.stat()
                    owner = common.get_own_user(uuid=stat.st_uid) if stat.st_uid != 0 else "admin"
                    items.append({
                        "type": "file",
                        "owner": owner,
                        "name": entry.name,
                        "full_path": str(entry.relative_to(base_path)),
                    })
                elif entry.is_dir():
                    stat = entry.stat()
                    owner = common.get_own_user(uuid=stat.st_uid) if stat.st_uid != 0 else "admin"
                    sub_list = []
                    # 하위 디렉터리 탐색 (깊이 제한 체크)
                    if max_depth is None or depth < max_depth:
                        sub_list = build_tree(entry, depth + 1)
                    items.append({
                        "type": "folder",
                        "owner": owner,
                        "name": entry.name,
                        "full_path": str(entry.relative_to(base_path)),
                        "sub_list": sub_list
                    })
            return items

        result = build_tree(root, 0)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_data_simple_list(directory, extension_list, search = None):
    result = []
    try:
        if search:
            filter = f"*{search}*"
        else:
            filter = "*"
        for item in Path(directory).glob(filter):
            item_metadata = item.stat()
            item_uuid = item_metadata.st_uid
            owner = common.get_own_user(uuid=item_uuid) if item_uuid != 0 else "admin"

            if item.is_dir():
                continue
            
            if item.is_file() and len(extension_list) > 0 and item.suffix not in extension_list:
                continue

            result.append({
                "owner": owner, # item_uuid == user_uuid,
                "name" : str(item).replace(directory, "").lstrip("/"), # 파일 이름
            })
    except:
        traceback.print_exc()
    return result


async def get_data_file_list(workspace_id : int, path : str = "", item_type : str = None, dataset_id : int = None, project_id : int = None, search : str = None):
    
    if item_type == TYPE.PROJECT_TYPE:
        project_info = await db_project.get_project_new(project_id=project_id)
        workspace_info = await db.get_workspace_async(workspace_id=workspace_id)
        base_path = PATH.JF_MAIN_PROJECT_SRC_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], PROJECT_NAME=project_info["name"]) 
        directory = base_path + f"/{path}"
        result = await get_data_hierarchy_list(directory=directory, extension_list=[".sh", ".py"], search=search,base_path=base_path, max_depth=0)
        return result
    elif item_type == TYPE.ANALYZER_TYPE:
        dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
        storage_name = dataset_info.get("data_storage_name")
        workspace_name = dataset_info.get("workspace_name")
        # user_uuid = int(user_id) + int(settings.USER_UUID_SET)

        base_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, 
                                                        ACCESS=dataset_info.get("access"), DATASET_NAME=dataset_info.get("name")) 
        directory = base_path + f"/{path}"
        result = await get_data_hierarchy_list(directory=directory, extension_list=[".csv", ".json"], search=search, base_path=base_path, max_depth=0)
        return result
    else: 
        dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
        storage_name = dataset_info.get("data_storage_name")
        workspace_name = dataset_info.get("workspace_name")
        # user_uuid = int(user_id) + int(settings.USER_UUID_SET)

        base_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, 
                                                        ACCESS=dataset_info.get("access"), DATASET_NAME=dataset_info.get("name")) 
        directory = base_path + f"/{path}"
        result = await get_data_hierarchy_list(directory=directory, extension_list=[], search=search, base_path=base_path, max_depth=0)
        return result


# ==================================================================
# MODEL
# ==================================================================

async def get_categories_by_model():
    return [] #TYPE.MODEL_TASK_LIST

async def get_models_by_huggingface(model_name : str = None, huggingface_token : str = None, private : int = 0, task: str = None) -> list[str]:
    api = HfApi()
    
    if private:
        huggingface_token = front_cipher.decrypt(huggingface_token)
        models = api.list_models(limit=10, model_name=model_name, token=huggingface_token, task=task)
    else:
        models = api.list_models(limit=10, model_name=model_name, task=task)
    parse_model_ids = [{"id" : model.id, "url" : f"https://huggingface.co/{model.id}"} for model in models]
    return parse_model_ids

async def check_model_access(token: str, model_id: str = None) -> bool:
    """
    해당 Hugging Face 모델에 대해 주어진 토큰으로 접근 권한이 있는지 확인하는 함수 (비동기 버전).

    Parameters:
    model_id (str): 접근하려는 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.

    Returns:
    bool: 접근 권한이 있으면 True, 없으면 False.
    """
    loop = asyncio.get_event_loop()
    # token = front_cipher.decrypt(token)
    
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


# ==================================================================
# 조합해서 사용
# ==================================================================
async def get_analyzer_option(workspace_id):
    result = {
        "user_list" : None,
        "instance_list" : None,
    }
    try:
        result["user_list"] =  await get_workspace_user_list(workspace_id=workspace_id)
        result["instance_list"] = await get_workspace_instance_list(workspace_id=workspace_id)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_analyzer_graph_datasets_option(workspace_id):
    result = []
    try:
        result = await get_workspace_dataset_list(workspace_id=workspace_id)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_analyzer_graph_data_option(dataset_id, search):
    result = []
    try:
        result = await get_dataset_data_list(dataset_id=dataset_id, extension_list=[".csv", ".json"], search=search, hierarchy=True)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_analyzer_graph_column_option(dataset_id, file_path):
    result = []
    try:
        dataset_info = await db.get_dataset_async(dataset_id=dataset_id)
        access = dataset_info.get("access")
        storage_name = dataset_info.get("data_storage_name")
        workspace_name = dataset_info.get("workspace_name")
        dataset_name = dataset_info.get("name")
        
        # 팟 안에서 데이터셋 경로
        full_path = PATH.JF_DATA_DATASET_DATA_PATH.format(
            STORAGE_NAME=storage_name,
            WORKSPACE_NAME=workspace_name,
            ACCESS=access,
            DATASET_NAME=dataset_name,
            DATA_PATH=file_path
        )

        # 만약 full_path가 디렉터리면 바로 빈 결과 반환
        if os.path.isdir(full_path):
            return []

        # encoding 타입을 여러가지 대응하기 위해 리스트로 for loop
        encodings_to_try = ['utf-8', 'cp949', 'latin1', 'ISO-8859-1', 'cp1252']
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(full_path, engine='python', encoding=encoding, on_bad_lines='skip')
                result = df.columns.tolist()
                if result:
                    break  # 컬럼추출되면 loop 종료
            except Exception:
                # 다음 encoding 시도
                pass
    except Exception as e:
        traceback.print_exc()
    return result
 
 
# ==================================================================
# PROJECT 
# ==================================================================

async def get_project_run_code_data_stream(project_id : int, is_dist : bool = False, search_index : int = 0):
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    workspace_info = await db.get_workspace_async(workspace_id=project_info["workspace_id"])
    if not project_info["instance_id"]:
        raise Exception("Allocate the instance")
    if is_dist == False:
        file_extension = ["py", "sh"]
    else:
        file_extension = []
    training_src_path = PATH.JF_MAIN_PROJECT_SRC_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=project_info["workspace_name"], PROJECT_NAME=project_info["name"])
    return await get_file_list_from_src(file_extension=file_extension, base_path=training_src_path, search_index=search_index)


async def get_project_option(workspace_id : int, project_id : int = None, headers_user : str = None):
    from utils.msa_db import db_project
    # workspace_resources = db_project.get_workspace_resources_project(workspace_id=workspace_id)
    # project_allocate_resources = db_project.get_project_allocate_resource(workspace_id=workspace_id)
    workspace_allocate_instance = await db.get_workspace_instances(workspace_id=workspace_id)
    if workspace_allocate_instance is None:
        raise AllocateWorkspaceInstanceError
    result = {
        "user_list": await db.get_workspace_user_name_and_id_list(workspace_id),
        "instances": workspace_allocate_instance,
        "jonathan_intelligence_used" : settings.JONATHAN_INTELLIGENCE_USED
    }
    if project_id:
        project_info = await db_project.get_project_new(project_id=project_id)
        project_info["secreted_user"] = await db_project.get_project_private_users_new(project_id=project_id)
        # project_info["permission_level"] = permission_check(workspace_id=workspace_id, project_info=project_info, user=headers_user)
        result["project_info"] = project_info
        
    
    return result


async def get_project_used_gpu_count(project_id : int)-> dict:
    """
    해당 project에서 실제 사용중 과 pending에 걸려있는 gpu 수
    """
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    used_gpus = 0
    pending_gpus = 0
    project_total_gpu = project_info["gpu_allocate"] * project_info["instance_allocate"]
    # TOOL
    tools = await db_project.get_project_tools_new(project_id=project_id)
    for tool in tools:
        if tool["request_status"] == 1:
            if tool["start_datetime"]:
                used_gpus += tool["gpu_count"]
            else:
                pending_gpus += tool["gpu_count"]
    # Training
    trainings = await db_project.get_trainings_request(project_id=project_id)
    
    for training in trainings:
        if training["start_datetime"]:
            used_gpus += training["gpu_count"]
        else:
            pending_gpus += training["gpu_count"]
    
    # hps
    # hps_list = db_project.get_hps_list_request(project_id=project_id)
    # for hps in hps_list:
    #     if hps["start_datetime"]:
    #         used_gpus += hps["gpu_count"]
    #     else:
    #         pending_gpus += hps["gpu_count"]
            
    return {
            "used_gpu_count": used_gpus,
            "pending_gpu_count" : pending_gpus,
            "project_gpu_total" : project_total_gpu,
            "available_gpu_count" : project_total_gpu - used_gpus - pending_gpus
        }

async def get_project_hps_option(project_id : int):
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    workspace_info = await db.get_workspace_async(workspace_id=project_info["workspace_id"])
    
    gpu_allocate = project_info["gpu_allocate"] if project_info["gpu_allocate"] else 0
    total_gpu = gpu_allocate * project_info["instance_allocate"]
    result = {
        "dataset_list" : await get_workspace_dataset_list(workspace_id=project_info["workspace_id"]),
        "project_type":  project_info["type"], 
        "instance_info" : {},
        # "gpu_cluster_list" : {},
        "workspace_gpu_status" : {},
        }
    if project_info["gpu_allocate"]:
        # GPU
        project_gpu_used_info = await get_project_used_gpu_count(project_id=project_id)
        # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=project_info["instance_id"])
        result["instance_info"] = {
            "resource_name" : project_info["resource_name"],
            "total" : total_gpu,
            "used"  : project_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        } 
        result["workspace_gpu_status"] = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=project_info["instance_id"], workspace_id=project_info["workspace_id"])
    else:
        # CPU
        result["instance_info"] = {
            "resource_name" : None,
            "total" : None,
            "used"  : None, # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        }
        
    if project_info["type"]==TYPE.PROJECT_TYPE_A:
        docker_images = await db.get_workspace_image_list(workspace_id=project_info["workspace_id"])
        training_src_path_new = PATH.JF_MAIN_PROJECT_SRC_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=project_info["workspace_name"], PROJECT_NAME=project_info["name"])
        # run_code_list, _ = await get_file_list_from_src( base_path=training_src_path_new, file_extension=["py", "sh"])
        # result["run_code_list"] = run_code_list    
        result["image_list"] = docker_images    
            # result["project_gpu_status"] = get_project_used_gpu_count(project_id=project_id)
        
    elif project_info["type"]==TYPE.PROJECT_TYPE_C:
        pass
    elif project_info["type"]==TYPE.PROJECT_TYPE_B:
        result["huggingface_model_url"] = "https://huggingface.co/{}".format(project_info.get("huggingface_model_id"))
        pass
    return result

async def get_project_job_option(project_id : int):
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    if not project_info["instance_id"]:
        raise Exception("Allocate the instance")
    
    docker_images = db_project.get_workspace_image_list(workspace_id=project_info["workspace_id"])
    gpu_allocate = project_info["gpu_allocate"] if project_info["gpu_allocate"] else 0
    total_gpu = gpu_allocate * project_info["instance_allocate"]
    is_distributed = total_gpu >= 2 

    result = {
        "distributed_frameworks" : [],
        "project_type":  project_info["type"], 
        "instance_info" : {},
        # "gpu_cluster_list" : {},
        "workspace_gpu_status" : {},
        }
    
    
        
    if project_info["gpu_allocate"]:
        # GPU
        project_gpu_used_info = await get_project_used_gpu_count(project_id=project_id)
        result["distributed_frameworks"] = TYPE.DISTRIBUTED_FRAMEWORKS
        # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=project_info["instance_id"])
        result["instance_info"] = {
            "resource_name" : project_info["resource_name"],
            "total" : total_gpu,
            "used"  : project_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        } 
        result["workspace_gpu_status"] = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=project_info["instance_id"], workspace_id=project_info["workspace_id"])
        # result["project_gpu_status"] = get_project_used_gpu_count(project_id=project_id)
    else:
        # CPU
        result["instance_info"] = {
            "resource_name" : None,
            "total" : None,
            "used"  : None, # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        } 
        
    if project_info["type"] == TYPE.PROJECT_TYPE_A:
        docker_images = db_project.get_workspace_image_list(workspace_id=project_info["workspace_id"])
        # run_code_list, file_list = await get_file_list_from_src_old(workspace_name=project_info["workspace_name"], project_name=project_info["name"], \
        #     storage_name=project_info["storage_name"], file_extension=["py", "sh"], is_distributed=is_distributed)
        # result["distributed_config_file_list"] = file_list
        # result["run_code_list"] = run_code_list
        result["image_list"] = docker_images  
    elif project_info["type"] == TYPE.PROJECT_TYPE_C:
        # TODO
        # 모델별로 파라미터 조회할 수 있도록 수정
        
        result["built_in_params"] = [
            "batch", "num_workers" , "max_epoch", "lr"
        ]
    elif project_info["type"]==TYPE.PROJECT_TYPE_B:
        result["built_in_params"] = [
            "batch", "num_workers" , "max_epoch", "lr"
        ]
        result["huggingface_model_url"] = "https://huggingface.co/{}".format(project_info.get("huggingface_model_id"))
        pass

    return result
      
async def get_tool_option(project_id : int, project_tool_id: int) :
    from utils.msa_db import db_project
    project_info = await db_project.get_project_new(project_id=project_id)
    if not project_info:
        raise Exception("not exist project")
    project_tool_info = await db_project.get_project_tool_new(project_tool_id=project_tool_id)
    project_gpu_total = 0
    result = {
        "project_gpu_total" : project_gpu_total,
        "image_list": db_project.get_workspace_image_list(project_info["workspace_id"]),
        "instance_type" : project_info["instance_type"],
        "tool_gpu_count" :project_tool_info["gpu_count"],
        "dataset_list" : await get_workspace_dataset_list(workspace_id=project_info["workspace_id"]),
        }
    if project_info["gpu_allocate"]:
        # GPU
        project_gpu_used_info = await get_project_used_gpu_count(project_id=project_id)
        result["distributed_frameworks"] = TYPE.DISTRIBUTED_FRAMEWORKS
        total_gpu = project_info["gpu_allocate"] * project_info["instance_allocate"]
        result["project_gpu_total"] = total_gpu
        # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=project_info["instance_id"])
        result["instance_info"] = {
            "resource_name" : project_info["resource_name"],
            "total" : total_gpu,
            "used"  : project_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        } 
        result["workspace_gpu_status"] = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=project_info["instance_id"], workspace_id=project_info["workspace_id"])
        # result["project_gpu_status"] = get_project_used_gpu_count(project_id=project_id)
    else:
        # CPU
        result["instance_info"] = {
            "resource_name" : None,
            "total" : None,
            "used"  : None, # TODO 해당 값이 필요한지 의문
            "instance_type" : project_info["instance_type"]
        } 
    
    return result      

# ==================================================================
# PIPELINE
# ==================================================================
async def get_pipeline_option(workspace_id : int, pipeline_id : int = None, headers_user : str = None):
    from utils.msa_db import db_pipeline
    result = {
        "user_list": await db.get_workspace_user_name_and_id_list(workspace_id)
    }
    if pipeline_id:
        pipeline_info = await db_pipeline.get_pipeline_simple(pipeline_id=pipeline_id)
        pipeline_info["secreted_user"] = await db_project.get_project_private_users_new(pipeline_id=pipeline_id)
        # project_info["permission_level"] = permission_check(workspace_id=workspace_id, project_info=project_info, user=headers_user)
        result["pipeline_info"] = pipeline_info
        return result
    
    result["built_in_data_types"] = TYPE_BUILT_IN.PREPROCESSING_BUILT_IN_DATA_TYPES
    # result["pipeline_built_in_types"] = TYPE_BUILT_IN.PIPELINE_BUILT_IN_TYPES
    result["pipeline_built_in"] = TYPE_BUILT_IN.PIPELINE_BUILT_IN
    
    return result

async def get_pipeline_built_in_list(built_in_type : str):
    return TYPE_BUILT_IN.PIPELINE_BUILT_IN[built_in_type]
    

# ==================================================================
# PREPROCESSING
# ==================================================================

async def get_preprocessing_run_code_data_stream(preprocessing_id : int, is_dist : bool = False, search_index : int = 0):
    from utils.msa_db import db_prepro
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    workspace_info = await db.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    if not preprocessing_info["instance_id"]:
        raise Exception("Allocate the instance")
    if is_dist == False:
        file_extension = ["py", "sh"]
    else:
        file_extension = []
    training_src_path = PATH.JF_MAIN_PREPROCESSING_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=preprocessing_info["workspace_name"], PREPROCESSING_NAME=preprocessing_info["name"])
    return await get_file_list_from_src(file_extension=file_extension, base_path=training_src_path, search_index=search_index, replace_file_path=TYPE.PREPROCESSING_TYPE)

async def preprocessing_option(workspace_id : int = None, preprocessing_id : int = None):
    from utils.msa_db import db_prepro
    # if workspace_id == None:
    #     # workspace_list
    #     result = {
    #         "workspace_list" : await db_prepro.get_workspace_name_and_id_list()
    #     }
    #     return response(status=1, result=result)

    workspace_allocate_instance = await db_prepro.get_workspace_instances(workspace_id=workspace_id)
    result = {
        "user_list": db.get_user_list_in_workspace(workspace_id=workspace_id),
        "instances": workspace_allocate_instance,
        # "docker_image_list": await db_prepro.get_workspace_image_list(workspace_id),
        "built_in_data_types": TYPE_BUILT_IN.PREPROCESSING_BUILT_IN_DATA_TYPES
    }
    if preprocessing_id: # 수정용
        preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
        if preprocessing_info["access"] == 0:
            result["secreted_user"] = await db_prepro.get_preprocessing_private_users(preprocessing_id=preprocessing_id)
        result["preprocessing_info"] = preprocessing_info
    return result

def get_preprocessing_built_in_data_tfs(data_type : str):
    return TYPE_BUILT_IN.PREPROCESSING_BUILT_IN_DATA_TYPE_TFS[data_type]


async def get_preprocessing_used_gpu_count(preprocessing_id : int)-> dict:
    """
    해당 project에서 실제 사용중 과 pending에 걸려있는 gpu 수
    """
    preprocessing_info = await db.get_preprocessing(preprocessing_id=preprocessing_id)
    used_gpus = 0
    pending_gpus = 0
    preprocessing_total_gpu = preprocessing_info["gpu_allocate"] * preprocessing_info["instance_allocate"]
    # TOOL
    tools = await db.get_preprocessing_tools(preprocessing_id=preprocessing_id)
    for tool in tools:
        if tool["request_status"] == 1:
            if tool["start_datetime"]:
                used_gpus += tool["gpu_count"]
            else:
                pending_gpus += tool["gpu_count"]
    # jobs
    jobs = await db.get_jobs_is_request(preprocessing_id=preprocessing_id)
    
    for job in jobs:
        if job["start_datetime"]:
            used_gpus += job["gpu_count"]
        else:
            pending_gpus += job["gpu_count"]
            
    return {
            "used_gpu_count": used_gpus,
            "pending_gpu_count" : pending_gpus,
            "preprocessing_total_gpu" : preprocessing_total_gpu,
            "available_gpu_count" : preprocessing_total_gpu - used_gpus - pending_gpus
        }

async def preprocessing_job_option(preprocessing_id : int):
    preprocessing_info = await db.get_preprocessing(preprocessing_id=preprocessing_id)
    if not preprocessing_info["instance_id"]:
        raise Exception("Allocate the instance")
    workspace_info = await db.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    docker_images = await db.get_workspace_image_list(workspace_id=preprocessing_info["workspace_id"])
    gpu_allocate = preprocessing_info["gpu_allocate"] if preprocessing_info["gpu_allocate"] else 0
    total_gpu = gpu_allocate * preprocessing_info["instance_allocate"]
    result = {
        "image_list": docker_images, 
        "dataset_list" : await get_workspace_dataset_list(workspace_id=preprocessing_info["workspace_id"]),
        "preprocessing_type":  preprocessing_info["type"], 
        "instance_info" : {},
        # "gpu_cluster_list" : {},
        "workspace_gpu_status" : {},
        }
    if preprocessing_info["type"] == TYPE.PREPROCESSING_TYPE_A:
        # training_src_path_new = PATH.JF_MAIN_PREPROCESSING_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=preprocessing_info["workspace_name"], PREPROCESSING_NAME=preprocessing_info["name"])
        # run_code_list, _ = await get_file_list_from_src( base_path=training_src_path_new, file_extension=["py", "sh"], replace_file_path=TYPE.PREPROCESSING_TYPE)
        # result["run_code_list"] = run_code_list    
        if preprocessing_info["gpu_allocate"]:
            # GPU
            # preprocessing_gpu_used_info = await get_preprocessing_used_gpu_count(preprocessing_id=preprocessing_id)
            # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"])
            result["instance_info"] = {
                "resource_name" : preprocessing_info["resource_name"],
                "total" : total_gpu,
                # "used"  : preprocessing_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
                "instance_type" : preprocessing_info["instance_type"]
            } 
            result["workspace_gpu_status"] = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=preprocessing_info["instance_id"], workspace_id=preprocessing_info["workspace_id"])
            # result["project_gpu_status"] = get_project_used_gpu_count(preprocessing_id=preprocessing_id)
        else:
            # CPU
            result["instance_info"] = {
                "resource_name" : None,
                "total" : None,
                "used"  : None, # TODO 해당 값이 필요한지 의문
                "instance_type" : preprocessing_info["instance_type"]
            } 
    elif preprocessing_info["type"] == TYPE.PREPROCESSING_TYPE_B:
        result["built_in_params"] = TYPE_BUILT_IN.PREPROCESSING_TFS_PARAM[preprocessing_info["built_in_data_tf"]]
        result ["built_in_data_type"] = preprocessing_info["built_in_data_type"]
    
    

    return result


async def get_deployment_in_workspace(workspace_id : int):
    try:
        deployment_list = db.get_deployment_list_in_workspace(workspace_id=workspace_id)
        if deployment_list:
            return deployment_list
        return None
    except Exception as e:
        traceback.print_exc()
        raise e
