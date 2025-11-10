import zipfile
import tarfile
from pathlib import Path
import os
import traceback
import sys
sys.path.append("/")
from utils.redis import get_redis_client
from utils.redis_key import DATASET_UPLOAD_LIST
from utils.common import change_own
from datetime import datetime

import json
import time

target=Path(os.getenv("TARGET"))
destination_path=Path(os.getenv("DESTINATION"))
extention = os.getenv("EXTENTION")
redis_key = os.getenv("REDIS_KEY")
redis_sub_key = os.getenv("REDIS_SUB_KEY")
header_user = os.getenv("HEADER_USER")
job_name = os.getenv("JOB_NAME")
dataset_id = os.getenv("DATASET_ID")
dataset_name = os.getenv("DATASET_NAME")
workspace_id = os.getenv("WORKSPACE_ID")
workspace_name = os.getenv("WORKSPACE_NAME")
user_id = os.getenv("UPLOAD_USER")

# decompress_info = None

def get_redis():
    max_attempts = 5
        
        # 연결 시도
    attempt = 0
    while attempt < max_attempts:
        try:
            # Redis 클라이언트 초기화
            redis = get_redis_client()
            
            # 연결 성공 시, 함수를 종료하고 Redis 객체 반환
            return redis
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}. Retrying...")
            # 연결 실패 시, 일정 시간 대기 후 다시 시도
            time.sleep(2)
            attempt += 1
        
        # 모든 시도가 실패한 경우, 예외를 발생시키기
        raise Exception("Failed to connect to Redis after several attempts")

redis = get_redis()

print(target)
try:
    
    filename = target.name
    filename = filename.split('.')[0]
    print(filename)
    destination_path.mkdir(parents=True, exist_ok=True)
    upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')

    if extention == '.tar':
                compress_obj = tarfile.open(name=target)
                compress_list = compress_obj.getmembers()
    elif extention == '.zip':
        compress_obj = zipfile.ZipFile(target)
        compress_list = compress_obj.infolist()

    total=len(compress_list)
    # print(compress_list)
    curr=0
    for member in compress_list:
        curr+=1
        # percent = (curr/total) * 100
        decompress_info=redis.hget(redis_key, redis_sub_key)
        if decompress_info is not None:
             decompress_info=json.loads(decompress_info)
             decompress_info['upload_size'] = int(curr)
        else:
            decompress_info={
                            'total_size' : int(total),
                            'upload_size' : int(curr),
                            'datetime' : upload_start_time,
                            'type' : "object",
                            'path' : redis_sub_key,
                            'status' : "running",
                            'job' : job_name,
                            'complete' : False,
                            'dataset_id':dataset_id,
                            'dataset_name':dataset_name,
                            'workspace_id' : workspace_id,
                            'workspace_name' : workspace_name,
                            'upload_user' : user_id,
                            'progress' : 0
                        }
            redis.hset(DATASET_UPLOAD_LIST,redis_sub_key,redis_key)
        redis.hset(redis_key, redis_sub_key, json.dumps(decompress_info))
        compress_obj.extract(member=member,path=destination_path)
        # target = member.filename.encode('cp437').decode('euc-kr')
        # target = Path(destination_path).joinpath(target)
        # Path(destination_path).joinpath(member.filename).rename(target)

    compress_obj.close()
    change_own(path=destination_path, headers_user=header_user)
except:
    decompress_info = redis.hset(redis_key, redis_sub_key)
    if decompress_info is None:
        decompress_info={
            'total_size' : 100,
            'upload_size' : 0,
            'datetime' : upload_start_time,
            'type' : "object",
            'path' : filename,
            'status' : "error",
            'job' : job_name,
            'complete' : False,
            'dataset_id':dataset_id,
            'dataset_name':dataset_name,
            'workspace_id' : workspace_id,
            'workspace_name' : workspace_name,
            'upload_user' : user_id,
            'progress' : 0
        }
    else:
        decompress_info=json.loads(decompress_info)
        decompress_info['status']="error"
    redis.hset(redis_key, redis_sub_key, json.dumps(decompress_info))
    traceback.print_exc()
    