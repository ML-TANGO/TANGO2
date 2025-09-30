import sys
from scp import SCPClient
import paramiko
import os
import pathlib
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils.redis import get_redis_client
from utils.redis_key import DATASET_UPLOAD_LIST
from utils.common import change_own
from datetime import datetime
import json
from concurrent.futures import ThreadPoolExecutor
import time
import traceback
from pathlib import Path
import threading

ip=os.getenv("IP")
username=os.getenv("USER_NAME")
password=os.getenv("PASSWD")
target_path=os.getenv("TARGET")
destination=os.getenv("DESTINATION")
redis_key=os.getenv("REDIS_KEY")
header_user = os.getenv("HEADER_USER")
upload_path = os.getenv("UPLOAD_PATH")
job_name = os.getenv("JOB_NAME")
dataset_id = os.getenv("DATASET_ID")
dataset_name = os.getenv("DATASET_NAME")
workspace_id = os.getenv("WORKSPACE_ID")
workspace_name = os.getenv("WORKSPACE_NAME")
user_id = os.getenv("UPLOAD_USER")

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
upload_list=[]
#sub_key = upload_path+filename
# redis.delete(redis_key)
if upload_path is None:
    progress_sub_key = ""
else:
    progress_sub_key = upload_path

upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')
redis_sub_key=""
# Define progress callback function
def progress(filename, size, sent):
    global progress_sub_key
    redis_sub_key = progress_sub_key+str(Path(filename.decode('utf-8')).relative_to(destination))

    print(redis_sub_key)
    upload_info = redis.hget(redis_key,redis_sub_key)
    if upload_info is not None:
        upload_info = json.loads(upload_info)
        upload_info['upload_size']=sent
    else:
        upload_info={
            'total_size' : size,
            'upload_size' : sent,
            'datetime' : upload_start_time,
            'type' : "size",
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
    filename=filename.decode('utf-8')
    redis.hset(redis_key,redis_sub_key,json.dumps(upload_info))
    # print(redis.hgetall(redis_key))
    # sys.stdout.write("%s's progress: %.2f%%   \r" % (progress_sub_key+filename, float(sent)/float(size)*100))

def download_file(data_path, data_name):
    with SCPClient(ssh.get_transport(), progress=progress) as scp:
        destination_path = f"{destination}" # /{data_name}
        # print(destination_path)
        scp.get(data_path, destination_path,recursive=True)
        change_own(path=destination_path, headers_user=header_user)

try:

    # SSH 연결 설정
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password)

        # SCPClient 인스턴스 생성 시 progress callback 함수 전달

        # 와일드카드 패턴에 일치하는 파일 목록 가져오기
        # wildcard_pattern = '*'
    _, stdout, _ = ssh.exec_command(f"ls -d {target_path}")
    data_list = [line.strip() for line in stdout.readlines()]
    if data_list:
        threads = []
        try:
            for data in data_list:
                data_name = Path(data).name
                print(data)
                print(data_name)
            #     # 각 파일에 대해 스레드 생성 및 시작
            #     thread = threading.Thread(target=download_file, args=(data,data_name))
            #     threads.append(thread)
            #     thread.start()
            # # 모든 스레드가 종료될 때까지 기다리기
            # for thread in threads:
            #     thread.join()
        except:
            raise Exception(progress_sub_key+data_name)
    else:
        raise FileNotFoundError(f"Not found {target_path}")

    # 연결 종료
    ssh.close()

    print("\nDownload complete.")
except FileNotFoundError as e:
    print(e.args[0])
except Exception as e:
    progress_sub_key = e.args[0]
    traceback.print_exc()
    upload_info = redis.hget(redis_key,progress_sub_key)
    if upload_info is None:
        upload_info={
            'total_size' : 100,
            'upload_size' : 0,
            'datetime' : upload_start_time,
            'type' : "size",
            'path' : progress_sub_key,
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
        redis.hset(redis_key,progress_sub_key,json.dumps(upload_info))
    else:
        upload_info=json.loads(upload_info)
        upload_info['status']="error"
        redis.hset(redis_key,progress_sub_key,json.dumps(upload_info))

