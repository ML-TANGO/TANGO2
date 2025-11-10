import sys
from scp import SCPClient
import paramiko
import os
import pathlib
import json
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import time
import traceback
from pathlib import Path
import threading
from utils.redis import get_redis_client
from utils.redis_key import DATASET_UPLOAD_LIST
from utils.common import change_own
from utils.crypt import front_cipher

# 환경 변수 기본값 설정
ip = os.getenv("IP", "127.0.0.1")
username = os.getenv("USER_NAME", "default_user")
password = os.getenv("PASSWD", "default_password")
password = front_cipher.decrypt(password)
target_path = os.getenv("TARGET", "/default/path")
destination = os.getenv("DESTINATION", "/default/destination")
redis_key = os.getenv("REDIS_KEY", "default_redis_key")
header_user = os.getenv("HEADER_USER", "default_header_user")
upload_path = os.getenv("UPLOAD_PATH", "/default/upload_path")
job_name = os.getenv("JOB_NAME", "default_job_name")
dataset_id = os.getenv("DATASET_ID", "default_dataset_id")
dataset_name = os.getenv("DATASET_NAME", "default_dataset_name")
workspace_id = os.getenv("WORKSPACE_ID", "default_workspace_id")
workspace_name = os.getenv("WORKSPACE_NAME", "default_workspace_name")
user_id = os.getenv("UPLOAD_USER", "default_user_id")

def get_redis():
    max_attempts = 5
    attempt = 0
    while attempt < max_attempts:
        try:
            redis = get_redis_client()
            return redis
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}. Retrying...")
            time.sleep(2)
            attempt += 1
    raise Exception("Failed to connect to Redis after several attempts")

redis = get_redis()
upload_list = []

if upload_path is None:
    progress_sub_key = ""
else:
    progress_sub_key = upload_path

upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')

def progress(filename, size, sent):
    global progress_sub_key
    redis_sub_key = progress_sub_key + str(Path(filename.decode('utf-8')).relative_to(destination))
    upload_info = redis.hget(redis_key, redis_sub_key)
    if upload_info is not None:
        upload_info = json.loads(upload_info)
        upload_info['upload_size'] = sent
    else:
        upload_info = {
            'total_size': size,
            'upload_size': sent,
            'datetime': upload_start_time,
            'type': "size",
            'path': redis_sub_key,
            'status': "running",
            'job': job_name,
            'complete': False,
            'dataset_id': dataset_id,
            'dataset_name': dataset_name,
            'workspace_id': workspace_id,
            'workspace_name': workspace_name,
            'upload_user': user_id,
            'progress': 0
        }
    redis.hset(redis_key, redis_sub_key, json.dumps(upload_info))

def download_file(data_path, data_name):
    with SCPClient(ssh.get_transport(), progress=progress) as scp:
        destination_path = f"{destination}"
        scp.get(data_path, destination_path, recursive=True)
        change_own(path=destination_path, headers_user=header_user)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username=username, password=password)
    except paramiko.AuthenticationException as e:
        print("Authentication failed. Please check your username and password.")
        print(f"Details: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during SSH connection: {e}")
        raise

    _, stdout, _ = ssh.exec_command(f"ls -d {target_path}")
    data_list = [line.strip() for line in stdout.readlines()]
    if data_list:
        for data in data_list:
            data_name = Path(data).name
            download_file(data, data_name)
    else:
        raise FileNotFoundError(f"Not found {target_path}")

    ssh.close()
    print("\nDownload complete.")
except FileNotFoundError as e:
    print(e.args[0])
except Exception as e:
    progress_sub_key = e.args[0] if e.args else "unknown_error"
    traceback.print_exc()
    upload_info = redis.hget(redis_key, progress_sub_key)
    if upload_info is None:
        upload_info = {
            'total_size': 100,
            'upload_size': 0,
            'datetime': upload_start_time,
            'type': "size",
            'path': progress_sub_key,
            'status': "error",
            'job': job_name,
            'complete': False,
            'dataset_id': dataset_id,
            'dataset_name': dataset_name,
            'workspace_id': workspace_id,
            'workspace_name': workspace_name,
            'upload_user': user_id,
            'progress': 0
        }
        redis.hset(redis_key, progress_sub_key, json.dumps(upload_info))
    else:
        upload_info = json.loads(upload_info)
        upload_info['status'] = "error"
        redis.hset(redis_key, progress_sub_key, json.dumps(upload_info))

