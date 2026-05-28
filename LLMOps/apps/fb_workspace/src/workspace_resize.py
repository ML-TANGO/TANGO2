import os
from pathlib import Path
import shutil
import sys
import time
from workspace.helm import create_workspace_pvc, delete_workspace_pvc
# sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import traceback
import threading
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__)))))

from utils.msa_db import db_workspace, db_storage  
from utils import common
from utils.redis import get_redis_client
from utils.redis_key import STORAGE_LIST_RESOURCE, GPU_INFO_RESOURCE, WORKSPACE_RESOURCE_QUOTA, WORKSPACE_PODS_STATUS, WORKSPACE_INSTANCE_QUEUE, WORKSPACE_INSTANCE_PENDING_POD, WORKSPACE_ITEM_PENDING_POD
from utils.exception.exceptions import *
from utils import  PATH, settings
from utils import notification_key
from utils.log import logging_history, LogParam


temp_dir_path = "/move_data"

workspace_id = os.getenv("WORKSPACE_ID")
workspace_name = os.getenv("WORKSPACE_NAME")
workspcae_namespace = workspace_name
main_sc = os.getenv("MAIN_SC")
main_storage_request = int(os.getenv("MAIN_STORAGE_REQUEST"))
data_sc = os.getenv("DATA_SC")
data_storage_request = int(os.getenv("DATA_STORAGE_REQUEST"))
temp_folder = Path("/temp_folder")
temp_folder.mkdir(parents=True, exist_ok=True)

def run_threads_in_parallel(jobs):
    """스레드 리스트를 받아서 병렬 실행 후 모두 종료될 때까지 대기"""
    threads = []
    for target_fn, args in jobs:
        t = threading.Thread(target=target_fn, args=args)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

def copy_data(source_folder: Path, destination_folder: Path):
    try:
        print(f"복사 시작: {source_folder} -> {destination_folder}")
        for item in source_folder.iterdir():
            src_path = item
            dst_path = destination_folder.joinpath(item.name)

            if item.is_file():
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        print(f"복사 완료: {source_folder} -> {destination_folder}")
    except Exception as e:
        traceback.print_exc()
        print(f"복사 실패: {source_folder} -> {destination_folder}")
        return False

def resize_workspace(main_storage_path, data_storage_path ):
    try:
        global main_storage_request, data_storage_request

        main_tmp_path=temp_folder.joinpath("main") 
        main_tmp_path.mkdir(parents=True, exist_ok=True)
        data_tmp_path=temp_folder.joinpath("data")
        data_tmp_path.mkdir(parents=True, exist_ok=True)


        # 1. 기존 데이터를 임시 폴더로 백업 (병렬 처리)

        
        run_threads_in_parallel([
            (copy_data,(main_storage_path, main_tmp_path)),
            (copy_data,(data_storage_path, data_tmp_path))
        ])
        print("원본 데이터 백업 완료")

        delete_workspace_pvc(workspace_id=workspace_id)

        create_workspace_pvc(workspace_id=workspace_id,
                             workspace_name=workspace_name,
                             main_sc=main_sc,
                             main_storage_request=main_storage_request,
                             data_sc=data_sc,
                             data_storage_request=data_storage_request)
        db_workspace.update_workspace_storage_size(workspace_id=workspace_id, main_storage_size=main_storage_request, data_storage_size=data_storage_request)

        
        # 3. 임시 폴더에서 새 PVC로 복사 (병렬 처리)
        run_threads_in_parallel([
            (copy_data,(main_tmp_path, main_storage_path)),
            (copy_data,(data_tmp_path, data_storage_path))
        ])

        print("새 PVC로 데이터 복사 완료 (병렬)")
        
    except Exception as e:
        traceback.print_exc()
        return False
        # print(f"오류가 발생했습니다: {str(e)}")
    
def get_workspace_info():
    max_attempts = 5
        
        # 연결 시도
    attempt = 0
    while attempt < max_attempts:
        try:
            # DB 클라이언트 초기화
            workspace_info = db_workspace.get_workspace(workspace_id=workspace_id)
            
            # 연결 성공 시, 함수를 종료하고 DB 정보
            if workspace_info:
                return workspace_info
            else:
                Exception
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}. Retrying...")
            # 연결 실패 시, 일정 시간 대기 후 다시 시도
            time.sleep(2)
            attempt += 1
        
        # 모든 시도가 실패한 경우, 예외를 발생시키기
    raise Exception("Failed to connect to DB after several attempts")
    
# workspace_info = db_workspace.get_workspace(workspace_id=workspace_id)
workspace_info=get_workspace_info()
print(workspace_info)
main_storage_info = db_storage.get_storage(storage_id=workspace_info['main_storage_id'])
data_storage_info = db_storage.get_storage(storage_id=workspace_info['data_storage_id'])
main_storage_path = Path(PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=main_storage_info['name'], WORKSPACE_NAME=workspace_info['name']))
data_storage_path = Path(PATH.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=data_storage_info['name'], WORKSPACE_NAME=workspace_info['name']))

resize_workspace(main_storage_path=main_storage_path, data_storage_path=data_storage_path)
# resize_workspace(source_path=data_storage_path,storage_type="data")
