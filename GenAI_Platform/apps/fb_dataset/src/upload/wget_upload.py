import wget
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils.redis import get_redis_client
from utils.redis_key import DATASET_UPLOAD_LIST
import requests
from urllib.parse import urlparse, unquote
from utils.common import change_own
from datetime import datetime
import json
import time
# 다운로드할 URL
# url = "http://example.com/path/to/download/file.zip"

# # 다운로드 경로
# output_path = "/path/to/save/file.zip"
upload_url=os.getenv("DOWNLOAD_URL")
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

parsed_url = urlparse(upload_url)
filename = os.path.basename(parsed_url.path)
if upload_path is None:
    redis_sub_key = filename
else:
    redis_sub_key = upload_path+filename

upload_info=None
# 커스텀 진행 상황 표시 함수

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

# time.sleep(20)


# def custom_bar(current, total, width=80):
#     percent = int((current / total) * 100)
#     # filled_length = int(width * current // total)
#     # bar = '=' * filled_length + '-' * (width - filled_length)
#     redis.hset(redis_key,filename,"{}".format(percent))
#     # print('\r%s |%s| %3.2f%% %s' % ('Downloading:', bar, percent, '% done'), end='\r')

# # 파일 다운로드
# wget.download(upload_url, destination, bar=custom_bar)
upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')
def download_file_streaming(url, destination):
    """
    스트리밍 형식으로 파일을 다운로드합니다.

    :param url: 다운로드할 파일의 URL
    :param filename: 다운로드 받은 파일의 이름
    """
    response = requests.get(url, stream=True)
    file_size = int(response.headers.get('Content-Length', -1))
    # global upload_info
    # 응답이 성공적으로 이루어졌는지 확인
    if response.status_code == 200:
        # upload_start_time = datetime.now().strftime('%y:%m:%d %H:%M:%S')
        upload_size=0
        with open(destination, 'ab+') as file:
            for chunk in response.iter_content(chunk_size= 1048576):
                if chunk:
                    file.write(chunk)
                    upload_size += len(chunk)
                    upload_info = redis.hget(redis_key,redis_sub_key)
                    if upload_info is not None:
                        upload_info=json.loads(upload_info)
                        upload_info['upload_size']=upload_size
                    else:
                        upload_info={
                            'total_size' : file_size,
                            'upload_size' : upload_size,
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
                    print(upload_info)
                    redis.hset(redis_key,redis_sub_key,json.dumps(upload_info))
                    # redis.hset(DATASET_UPLOAD_LIST,redis_sub_key,redis_key)
        print(f"{filename} 다운로드 완료.")
    else:
        print(f"다운로드 실패: {response.status_code}")

redis = get_redis()
# 사용 예제
# url = 'http://example.com/large_file.zip'
# filename = 'downloaded_file.zip'
destination=os.path.join(destination,filename)
try:
    download_file_streaming(upload_url, destination)
    change_own(path=destination, headers_user=header_user)
    print("\nDownload complete!")
except:
    upload_info = redis.hget(redis_key,redis_sub_key)
    if upload_info is None:
        upload_info={
            'total_size' : 100,
            'upload_size' : 0,
            'datetime' : upload_start_time,
            'type' : "size",
            'path' : redis_sub_key,
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
        redis.hset(redis_key,redis_sub_key,json.dumps(upload_info))
    else:
        upload_info=json.loads(upload_info)
        upload_info['status']="error"
        redis.hset(redis_key,redis_sub_key,json.dumps(upload_info))

