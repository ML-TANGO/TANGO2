import os
import subprocess
import sys
import pathlib
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils.redis import get_redis_client
from utils.common import change_own
from utils.redis_key import DATASET_UPLOAD_LIST
from datetime import datetime
import json
import git
import githublfs
import traceback
import time

git_repo_url = os.getenv("GIT_REPO_URL")
repo_path = os.getenv("GIT_REPO_PATH")
redis_key = os.getenv("REDIS_KEY")
headers_user = os.getenv("HEADER_USER")
git_access = os.getenv("GIT_ACCESS")
git_id = os.getenv("GIT_ID")
git_access_token = os.getenv("GIT_ACCESS_TOKEN")
git_cmd = os.getenv("GIT_CMD")
upload_path = os.getenv("UPLOAD_PATH")
job_name = os.getenv("JOB_NAME")
dataset_id = os.getenv("DATASET_ID")
dataset_name = os.getenv("DATASET_NAME")
workspace_id = os.getenv("WORKSPACE_ID")
workspace_name = os.getenv("WORKSPACE_NAME")
user_id = os.getenv("UPLOAD_USER")

if git_cmd == "clone":
    if upload_path is None:
        progress_sub_key=git_repo_url.split('/')[-1]
    else:
        progress_sub_key=upload_path+git_repo_url.split('/')[-1]

    upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')

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

class ReceivingObjectsProgressPrinter(git.RemoteProgress):
    def __init__(self):
        super().__init__()
        self.prev_percent = -1

    def update(self, op_code, cur_count, max_count=None, message=''):
        global redis_key
        global upload_info
        # Check if we're in the "Receiving objects" stage
        if op_code & self.OP_MASK == self.RECEIVING:
            if max_count:
                percent = int((cur_count / max_count) * 100)
                if percent != self.prev_percent:
                    # print(f"Receiving objects: {percent}% ({cur_count}/{max_count})")
                    self.prev_percent = percent

                    if upload_info is not None:
                        upload_info['upload_size']=int(cur_count)
                    else:
                        upload_info={
                                    'total_size' : int(max_count),
                                    'upload_size' : int(cur_count),
                                    'datetime' : upload_start_time,
                                    'type' : "object",
                                    'path' : progress_sub_key,
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
                        redis.hset(DATASET_UPLOAD_LIST,progress_sub_key,redis_key)
                    redis.hset(redis_key,progress_sub_key,json.dumps(upload_info))
                    print(redis.hget(redis_key, progress_sub_key))
            # else:
            #     print(f"Receiving objects: {cur_count} - {message.strip()}")
def clone():
    try:

        global repo_path
        # Ensure the directory exists
        # if not os.path.exists(repo_path):
        #     os.makedirs(repo_path)

        # Format the repository URL to include the token for authentication if private
        if git_access == "private" and git_access_token:
            repo_url_with_token = git_repo_url.replace("https://", f"https://{git_access_token}@")
        else:
            repo_url_with_token = git_repo_url
        print(repo_path)
        repo_path=repo_path+'/'+git_repo_url.split('/')[-1]
        # Clone the repository using githublfs
        git.Repo.clone_from(repo_url_with_token, repo_path, progress=ReceivingObjectsProgressPrinter())

        # Initialize LFS and pull LFS files
        subprocess.run(['git', 'lfs', 'install'], cwd=repo_path, check=True)
        subprocess.run(['git', 'lfs', 'pull'], cwd=repo_path, check=True)
        change_own(path=repo_path, headers_user=headers_user)
        return {"status": "success", "message": f"Repository cloned to {repo_path}"}
    except Exception as e:
        # Handle any other exceptions
        redis.hdel(redis_key,progress_sub_key)
        traceback.print_exc()
        raise Exception(status_code=500, detail=str(e))

def pull():
    try:
        # Check if the directory exists
        if not os.path.exists(repo_path):
            raise Exception("Repository directory does not exist.")

        # Ensure the directory is a Git repository
        if not os.path.exists(os.path.join(repo_path, ".git")):
            raise Exception("Directory is not a Git repository.")

        # Perform the pull operation using GitPython
        repo = git.Repo(git_repo_url)
        origin = repo.remote(name='origin')
        if git_access == "private" and git_access_token:
            # Set the remote URL with the token for authentication
            remote_url_with_token = origin.url.replace("https://", f"https://{git_access_token}@")
            origin.set_url(remote_url_with_token)

        origin.pull()

        return {"status": "success", "message": f"Repository at {repo_path} has been pulled successfully"}
    except git.exc.GitError as e:
        # Handle GitPython errors
        traceback.print_exc()
        raise Exception(f"Git error: {e}")
    except Exception as e:
        traceback.print_exc()
        # Handle any other exceptions
        raise Exception(str(e))

try:

    if git_cmd == "clone":
        clone()
    elif git_cmd == "pull":
        pull()
    else:
        print(f"Unkown command {git_cmd}")
except:
    upload_info = redis.hget(redis_key, progress_sub_key)
    if upload_info is None:
        upload_info={
            'total_size' : 100,
            'upload_size' : 0,
            'datetime' : upload_start_time,
            'type' : "object",
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