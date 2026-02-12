import re
import subprocess
import xml.etree.ElementTree as ET
import base64
import traceback
import os
import stat
import shutil
import paramiko
import threading
import asyncio

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Tuple, Dict
import random
# Init random seed
temp_time_for_random_seed = int(time.time()*1000.0) ^ os.getpid()
random.seed( ((temp_time_for_random_seed&0xff000000) >> 24)
        + ((temp_time_for_random_seed&0x00ff0000) >> 8)
        + ((temp_time_for_random_seed&0x0000ff00) << 8)
        + ((temp_time_for_random_seed&0x000000ff) << 24))
import string
import json
import argparse
import functools
import pathlib
import socket
import struct
import sys
import multiprocessing
import dateutil.parser
import re
import aiohttp
from utils.exception.exceptions import *
import utils.settings as settings

import hashlib
import re
sys.path.insert(0, os.path.abspath('..'))
from utils.TYPE import *
from utils import TYPE
# from utils.common_data import *
import inspect

from collections import defaultdict
from typing import List
from functools import reduce, lru_cache, cache, wraps

# global_lock = threading.Lock()  # lock for job_queue
rand_lock = threading.Lock() # lock for random


DEFAULT_NTP_SERVER = '0.kr.pool.ntp.org'
# manager = multiprocessing.Manager()
# BENCHMARK_NETWORK_LIST = manager.list()
# BENCHMARK_NETWORK_RUNNING_INFO = manager.dict()
# PID_THREADING_DICT = manager.dict()
# KUBE_SHARE_DICT = manager.dict()
# STORAGE_USAGE_SHARE_DICT = manager.dict()
# SEMICONDUCTOR_SHARE_DICT = manager.dict()

BENCHMARK_NETWORK_LIST = list()
BENCHMARK_NETWORK_RUNNING_INFO = dict()
PID_THREADING_DICT = dict()
KUBE_SHARE_DICT = dict()
STORAGE_USAGE_SHARE_DICT = dict()
SEMICONDUCTOR_SHARE_DICT = dict()


class JfLock:
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, t, v, tb):
        self.lock.release()
        if tb is not None:
            traceback.print_exception(t, v, tb)
        return True

def get_storage_status(storage_type,workspace_info):
    if storage_type=="main":
        if workspace_info['main_storage_lock'] > 1:
            return False
        return True
    elif storage_type=="data":
        if workspace_info['data_storage_lock'] > 1:
            return False
        return True
    else:
        return False

def make_nested_dict():
    return defaultdict(make_nested_dict)

def dec_round(x,y):
    return float(round(Decimal(x),y))


def format_size(size_in_bytes):
    # Define unit conversion constants
    KB = 1024
    MB = KB * 1024
    GB = MB * 1024

    # Determine the appropriate unit for the size
    if size_in_bytes >= GB:
        size = size_in_bytes / GB
        unit = 'GB'
    elif size_in_bytes >= MB:
        size = size_in_bytes / MB
        unit = 'MB'
    elif size_in_bytes >= KB:
        size = size_in_bytes / KB
        unit = 'KB'
    else:
        size = size_in_bytes
        unit = 'bytes'

    return f"{size:.2f} {unit}"

def change_own(path,headers_user):
    import utils.msa_db.db_user as user_db
    file_list = []
    dir_list = []
    user_info = user_db.get_user_id(headers_user)
    user_id = user_info['id']
    uuid = 20000+user_id
    os.system('chown {}:{} "{}"'.format(uuid, uuid, path))
    if os.path.isfile(path):
        return
        
    tmp_file_list = os.listdir(path)
    
    for file_ in tmp_file_list:
        if not file_[0]=='.':
            if os.path.isfile(os.path.join(path,file_)) :
                file_list.append(file_)
            if os.path.isdir(os.path.join(path,file_)):
                dir_list.append(file_)
    for file_ in file_list:
        os.system('chown {}:{} "{}"'.format(uuid, uuid, os.path.join(path,file_)))
    for folder_ in dir_list:
        change_own(os.path.join(path,folder_),headers_user)

def get_own_user(uuid):
    import utils.msa_db.db_user as user_db
    user_info = user_db.get_user(uuid-20000)
    if user_info is None:
        return "unknown"
    return user_info['name']
    

def is_num(name):
    try:
        if name is not None:
            match_res = re.match(r'[0-9][0-9]*', name, re.M | re.I)
            if match_res is not None and match_res.group() == name:
                return True
    except:
        traceback.print_exc()
    return False


def is_good_user_name(name):
    try:
        if name is not None:
            match_res = re.match(r'([a-z0-9]+-?)*[a-z0-9]$', name, re.M | re.I)
            if match_res is not None and match_res.group() == name:
                return True
            else:
                print('{} {}'.format(name, match_res.group()))
        else:
            print('User == None')
    except:
        traceback.print_exc()
    return False


def is_good_name(name):
    """
        Description : Workspace, Training, Deployment + docker image 이름 생성 시 규칙
                      - 소문자, 숫자 구성에 "-" 만 허용. 
                      - 첫글자와 마지막 글자는 "-" 사용 X
                      - "-" 는 중복하여 사용 불가 ex) a-b O / a--b X

        Args :
            name (str) : 사용할 이름

        Return :
            (bool)

    """
    try:
        if name is not None:
            # front에서는 /([a-z0-9]+-?)*[a-z0-9]$/
            # match_res = re.match(
            #     r'([a-z0-9]+-?)*[a-z0-9]', name)  
            
            # MSA 변경 (다른 정규식이 더 정확하면 수정)
            match_res = re.match(r'^[\w\-.]+$', name)
            if match_res is not None and match_res.group() == name:
                return True
    except:
        traceback.print_exc()
    return False


def is_good_data_name(name):
    try:
        if name is not None:
            match_res = re.match(
                r'[\_0-9A-Za-zㄱ-ㅣ가-힣][\-_0-9A-Za-zㄱ-ㅣ가-힣]*', name, re.M | re.I)
            if match_res is not None and match_res.group() == name:
                return True
    except:
        traceback.print_exc()



def get_gpu_list():
    arr = []
    try:
        with subprocess.Popen(['nvidia-smi', '-q', '-x'], stdout=subprocess.PIPE) as p:
            out, err = p.communicate()
            out = out.decode('utf-8')
            root = ET.fromstring(out)
        for e in root:
            # if e1.tag == 'attached_gpus':
            #	print(e1.text);
            if e.tag == 'gpu':
                info = {
                    "num": int(e.find('minor_number').text),
                    "name": e.find('product_name').text,
                    "mem_total": e.find('fb_memory_usage').find('total').text,
                    "mem_used": e.find('fb_memory_usage').find('used').text,
                    "mem_free": e.find('fb_memory_usage').find('free').text,
                    "gpu_util": e.find('utilization').find('gpu_util').text,
                    "mem_util": e.find('utilization').find('memory_util').text
                }
                arr.append(info)
    except:
        traceback.print_exc()
    arr.sort(key=lambda a: a["num"], reverse=False)
    return {"num_gpus": len(arr), "list": arr}


def rm_r(path):
    """ Do rm -r `path'. Recursively delete folder and files.
    """
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)
    else:
        raise FileNotFoundError("No such file or directory: '{}'".format(path))
    
async def async_rmtree(path):
    if os.path.isdir(path) and not os.path.islink(path):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, shutil.rmtree, path
        )
        print(f"Dir {path} deleted")
    else:
        print(f"Dir {path} not exist")


async def async_clear_directory(path):
    if os.path.isdir(path) and not os.path.islink(path):
        # subprocess를 사용하여 디렉토리 내의 모든 파일 및 디렉터리 삭제
        process = await asyncio.create_subprocess_shell(
            f'rm -rf {os.path.join(path, "*")}',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            print(f"Contents of {path} deleted")
            return True
        else:
            print(f"Error deleting contents of {path}: {stderr.decode().strip()}")
            return False
    else:
        print(f"Dir {path} not exist or is not a directory")
        return False

async def async_copy_directory_contents(src, dest):
    if os.path.isdir(src) and not os.path.islink(src):
        if not os.path.exists(dest):
            os.makedirs(dest)
        # subprocess를 사용하여 src 내의 모든 파일 및 디렉터리를 dest로 복사
        process = await asyncio.create_subprocess_shell(
            f'cp -r {os.path.join(src, "*")} {dest}',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            print(f"Contents of {src} copied to {dest}")
            return True
        else:
            print(f"Error copying contents of {src} to {dest}: {stderr.decode().strip()}")
            return False
    else:
        print(f"Dir {src} not exist or is not a directory")
        return False


async def move_all_to_directory(source_dir, destination_dir):
    """
    Asynchronously moves all files and directories from the specified source directory to the specified destination directory.

    Args:
        source_dir (str): Path to the source directory containing items to move.
        destination_dir (str): Path to the destination directory where items will be moved.

    Returns:
        list: A list of new paths for each moved item if successful, or an empty list if an error occurs.
    """
    # Check if source directory exists and is a directory
    if not os.path.isdir(source_dir):
        print(f"Error: The specified source directory '{source_dir}' does not exist or is not a directory.")
        return []

    # Ensure destination directory exists
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)
        print(f"Created destination directory '{destination_dir}'.")

    moved_items = []

    # Iterate over all items in the source directory
    for item in os.listdir(source_dir):
        item_path = os.path.join(source_dir, item)
        destination_path = os.path.join(destination_dir, item)

        try:
            # Move each file or directory asynchronously
            await asyncio.to_thread(shutil.move, item_path, destination_path)
            print(f"Moved '{item_path}' to '{destination_path}'.")
            moved_items.append(destination_path)
        except Exception as e:
            print(f"Error while moving '{item_path}': {e}")

    return moved_items

async def async_delete_file(file_path : str) -> bool:
    """
    비동기적으로 파일을 삭제하는 함수

    :param file_path: 삭제할 파일의 경로
    """
    try:
        # 파일이 존재하는지 확인 후 삭제 작업을 별도의 스레드로 실행
        if os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)
            print(f"{file_path} 삭제 완료")
            return True
        else:
            print(f"{file_path} 경로에 파일이 존재하지 않습니다.")
            return False
    except Exception as e:
        print(f"파일 삭제 중 오류 발생: {e}")
    return False

def rm_rf(path, ignore_errors=False):
    """ Do rm -rf `path'. Ignores nonexistent files.
            Tries chmod to remove.
            Giving ignore_errors=True will ignore all errors.
    """
    def handle_error(func, path, exc_info):
        # Check if file access issue
        if not os.access(path, os.W_OK):
            # Try to change the permision of file
            try:
                os.chmod(path, stat.S_IWUSR)
                # call the calling function again
                func(path)
            except:
                if not ignore_errors:
                    print(''.join(traceback.format_exception(*exc_info)))
                #print(str(exc_info[0]), str(exc_info[1]))

    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=False, onerror=handle_error)
        if os.path.exists(path) and not ignore_errors:
            raise PermissionError("Failed to delete '{}'".format(path))
    elif os.path.exists(path):
        try:
            os.remove(path)
        except:
            if not ignore_errors:
                raise


def get_args():
    """Get parsed command-line arguments.

    If --jf-ip not given, this function will set to 127.0.0.1.

    Example:
        args = get_args()
        jf_ip = args.jf_ip
    """
    parser = argparse.ArgumentParser(description='...')
    parser.add_argument('--jf-ip', help='host ip')
    parser.add_argument('--jf-master-port', default=None, help='master port (default= settings)')
    parser.add_argument('--jf-worker-port', default=None, help='worker port (default= settings)')
    # Add more arguments here to use.

    args, unknown = parser.parse_known_args()
    if args.jf_ip is None:
        args.jf_ip = settings.LAUNCHER_DEFAULT_ADDR

    return args

def generate_alphanum(n=16):
    """Generate random alpha-numeric string length of `n'.

    By default, n is 16 which gives 62^16 = 4.76724 e+28 cases.
    """
    ALPHANUM = string.ascii_uppercase + string.ascii_lowercase + string.digits
    with rand_lock:
        random_str = ''.join(random.choice(ALPHANUM) for _ in range(n))
    return random_str


def ensure_path(path):
    return pathlib.Path(path).mkdir(parents=True, exist_ok=True) # ensure path exist

def writable_path(path):
    tmp_name = '.test_writable'
    path = path + '/' + tmp_name
    try:
        with open(path, 'w'):
            pass
    except PermissionError as e:
        traceback.print_exc()
        return False
    finally:
        try:
            rm_rf(path)
        except FileNotFoundError as fne:
            pass
    return True

def get_date_time(timestamp=None, date_format=TYPE.TIME_DATE_FORMAT):
    if timestamp is None:
        unixEpochStartTime = 2208988800 # January 1, 1970
        client = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        toSend = b'\x1b' + 47 * b'\0'
        t = ""
        try:
            client.sendto( toSend, (DEFAULT_NTP_SERVER, 123))
            received, address = client.recvfrom( 1024 )
            if received:
                t = struct.unpack( '!12I', received )[10]
                t -= unixEpochStartTime
        except:
            return datetime.today().strftime(date_format)
    else :
        t = timestamp
    return datetime.fromtimestamp(t).strftime(date_format) # return system time if the ntp server is unreachable


def date_str_to_timestamp(date_str, date_format="%Y-%m-%d %H:%M"):   
    """
    Description: date string to timestamp

    Args:
        date_str (str): date string. ex) "1994-09-24 09:50"
        date_format (str): datetime format . ex) "%Y-%m-%d"..... | iso8601

    Returns:
        int: timestamp (UTC 기준값)
    """

    """
    import time
    import dateutil

    # 새 방식 - (TZ 데이터를 고려하여 UTC TIMESTAMP를 가져옴)
    date_str = "2022-10-24T06:30:00+00:00"

    ts = dateutil.parser.isoparse(date_str).timestamp()
    print(ts)


    date_str = "2022-10-24T15:30:00+09:00"
    ts = dateutil.parser.isoparse(date_str).timestamp()
    print(ts)

    # 기존 방식 - (TZ 데이터에 상관 없이 UTC TIMESTAMP를 가져옴)
    date_str = "2022-10-24T06:30:00+09:00"
    timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
    print(timestamp)


    date_str = "2022-10-24T06:30:00+00:00"
    timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
    print(timestamp)

    -->
    1666593000.0
    1666593000.0
    1666593000.0
    1666593000.0
    """
    default_date_format_list = [
        "iso8601",
        "%Y-%m-%d",
        "%Y-%m-%d %H",
        "%Y-%m-%d %H:%M",
        TYPE.TIME_DATE_FORMAT
    ]
    if date_str is None:
        return 0

    timestamp = 0

    try:
        if date_format == "iso8601":
            # timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
            timestamp = dateutil.parser.isoparse(date_str).timestamp()
        else :
            # timestamp = time.mktime(datetime.strptime(date_str, date_format).timetuple())
            timestamp = datetime.timestamp(datetime.strptime(date_str, date_format))
    except:
        # for compatibility
        for date_format in default_date_format_list:
            try:
                if date_format == "iso8601":
                    # timestamp = time.mktime(dateutil.parser.isoparse(date_str).timetuple())
                    timestamp = dateutil.parser.isoparse(date_str).timestamp()
                else :
                    # timestamp = time.mktime(datetime.strptime(date_str, date_format).timetuple())
                    timestamp = datetime.timestamp(datetime.strptime(date_str, date_format))
                break
            except:
                pass

    return timestamp

SCALE = {
    "b":  10**0,
    "kb": 10**3,
    "mb": 10**6,
    "gb": 10**9,
    "tb": 10**12,
    "pb": 10**15,
    "eb": 10**18,
    "zb": 10**21,
    "yb": 10**24,
    "bb": 10**27,
}

def size_cvt(size, to):
    temp_splitted_string = re.split(r'([.\-0-9]+)', size.strip())[1:]
    if len(temp_splitted_string) < 2:
        raise ValueError('invalid size')
    number_part = temp_splitted_string[0] # number part
    from_ = temp_splitted_string[1].strip().lower() # from
    to = to.lower() # to
    if to not in SCALE.keys():
        raise ValueError('invalid size')
    converted_number = float(number_part) * SCALE[from_] / SCALE[to] # converted number

    return '%.2f%s' % (converted_number, to)



def gen_hash(text):
    # text = text + str(time.time) + str(random.random())
    text = text
    hash_ = hashlib.md5(text.encode())
    return hash_.hexdigest()

def gen_pod_name_hash(text):
    # text = text + str(time.time) + str(random.random())
    text = text
    hash_ = hashlib.md5(text.encode())
    return "h"+hash_.hexdigest()


def dict_comp(base_dict, target_dict, ignore_key_list=[]):
    match = True
    if target_dict is None:
        return False
    for k, v in base_dict.items():
        if k in ignore_key_list:
            continue
        if str(target_dict.get(k)) != str(v):
            match = False
            break
    return match

def get_add_del_item_list(new, old):
    del_item_list = list(set(old) - set(new))
    add_item_list = list(set(new) - set(old))
    return add_item_list, del_item_list

def get_workspace_status(workspace, start_datetime=None, end_datetime=None):
    # workspace from db. get_workspace get_workspaces get_workspace_list
    cur_time_ts = time.time()
    start_datetime_ts = date_str_to_timestamp(workspace["start_datetime"])
    end_datetime_ts = date_str_to_timestamp(workspace["end_datetime"])

    status = "unknown"
    if cur_time_ts < start_datetime_ts or cur_time_ts > end_datetime_ts:
        # Reserved or Expired
        status = "reserved" if cur_time_ts < start_datetime_ts else "expired"
    else :
        status = "active"

    return status

# TODO 개선 필요 
# param의 구분자를 -- 외에 - 를 사용하는 경우, 구분자가 단순 띄워쓰기인 경우 a=1 b=3 
# param과 value를 구분하는 방법의 다양함 "=", " "
# value 값의 표현 방법 - 단순 str이 아닌 띄워쓰기가 있거나 (이 경우 "aa vv" 로 묶어주는건 규칙)
# CASE 예시 
# CASE 1 --param=1 
# CASE 2 --param="aa bb cc" 
# CASE 3 --param 1 
# CASE 4 --param "qq ww ee" 
# CASE 5 --param "--aaa" 
# CASE 6 -p b
# CASE 7 param=3

def parameter_str_to_dict(parameter: str, without_first_hyphen=True, **kwargs) -> dict:
    """
    Description: 정규표현식 패턴을 사용해 파라미터(str)를 딕셔너리(dict)로 변환하여 리턴

    Args:
        parameter (str): parameter to convert
        without_first_hyphen (bool): (True) --param -> { "param" : '' } | (False) --param -> { "--param" : '' }

    Returns:
        dict: key value dictionary


    Examples:
        parameter = "  -param --param1   /jfbcore -param1 \"/jfbcore/\" -key -param    --data_root /user_dataset/  --img_dir '/user_dataset/image'  --ann_dir /user_dataset/mask  --resume-from /jf-training-home/job-checkpoints/coco-path-suffix2/0/latest.pth  --batch_size 32  --img_suffix .jpg  --iters 350  --lr 0.01  --save_interval 5000  --seg_map_suffix .png -param "
        parameter_str_to_dict(parameter)  # {'-param': ['', '', ''], '--param1': '/jfbcore', '-param1': '"/jfbcore/"', '-key': '', '--data_root': '/user_dataset/', '--img_dir': "'/user_dataset/image'", '--ann_dir': '/user_dataset/mask', '--resume-from': '/jf-training-home/job-checkpoints/coco-path-suffix2/0/latest.pth', '--batch_size': '32', '--img_suffix': '.jpg', '--iters': '350', '--lr': '0.01', '--save_interval': '5000', '--seg_map_suffix': '.png'}
    """    
    result = dict()
    if without_first_hyphen:
        matches = re.findall("([^-=\s]+[^=\s]*)([=\s]*)([\"].*?[\"]|['].*?[']|[^-\s]+\S*|)", parameter)
    else :
        matches = re.findall("(-{1,2}[^=\s]*)([=\s]*)([\"].*?[\"]|['].*?[']|[^-\s]+\S*|)", parameter)
    
    for parameter in matches:
        key, _, value = parameter
        if key in result:
            if isinstance(result[key], str):
                result[key] = [result[key]]
                result[key].append(value)
            elif isinstance(result[key], list):
                result[key].append(value)
        else:
            result[key] = value
    return result

def parameter_dict_to_list(parameter: dict):
    if parameter is None:
        return []
    parameter_list = []
    for key, value in parameter.items():
        if isinstance(value, list):
            for v in value:
                parameter_list.append({"key": key, "value": v})
        else :
            parameter_list.append({"key": key, "value": value})

    return parameter_list


def parameter_dict_to_str(parameter, flag=" "):
    parameter_str = ""
    for k,v in parameter.items():
        parameter_str += " --{k}{flag}{v} ".format(k=k, flag=flag, v=v) #  프론트에서 파라미터가 붙어서 들어와서 수정함 (2024-05-16)
    return parameter_str

def get_line_print(line_message, prefix="=============="):
    line_start = "{prefix} {message} {prefix}".format(message=line_message, prefix=prefix)
    line_end = "=" * len(line_start)
    return line_start, line_end

def run_func_with_print_line(func, line_message, prefix="==============", *args, **kwargs):
    line_start, line_end = get_line_print(line_message=line_message, prefix=prefix)
    print("\n\n")
    print(line_start)
    func(*args, **kwargs)
    print(line_end)

def gen_dict_from_list_by_key(target_list, id_key, del_keys=[], lower=False):
    temp_dict = {}
    if target_list is None:
        return temp_dict
    for item in target_list:
        id_ = item[id_key]
        if lower == True:
            id_ = id_.lower()
        if id_ not in temp_dict.keys():
            temp_dict[id_] = []
        for del_key in del_keys:
            del item[del_key]
        temp_dict[id_].append(item)
    return temp_dict

def gen_list_from_dict(target_dict, key_name):
    # {"key": {"item1":1, "item2": 2}}
    temp_list = []
    if target_dict is None:
        return target_dict
    for k, v in target_dict.items():
        temp_list.append({
            **v,
            key_name: k
        })
    return temp_list

def delete_dict_key(target_dict, del_key_list=[], save_key_list=[]):
    if len(del_key_list) and len(save_key_list):
        return None

    for del_key in del_key_list:
        try:
            del target_dict[del_key]
        except:
            pass

    for save_key in list(target_dict.keys()):
        if save_key not in save_key_list:
            try:
                del target_dict[save_key]
            except:
                pass

def delete_list_dict_key(target_list, del_key_list=[], save_key_list=[]):
    if len(del_key_list) and len(save_key_list):
        return None

    for i in range(len(target_list)):
        delete_dict_key(target_dict=target_list[i], del_key_list=del_key_list, save_key_list=save_key_list)


import re

def str_simple_converter(value):
    # kuber 일부 이름 규칙 때문에
    value = str(value).replace(" ", "-")
    new_string = re.sub(r"[^a-zA-Z0-9-_.]","", value)
    return new_string

def byte_to_gigabyte(byte_size):
    """
    바이트를 기가바이트(GB)로 변환합니다.
    SI 단위계를 사용하여 1000으로 나눕니다.
    
    Args:
        byte_size (int): 바이트 단위의 크기
        
    Returns:
        float: 기가바이트(GB) 단위로 변환된 크기 (소수점 2자리까지 반올림)
    """
    return round(byte_size/float(1000*1000*1000), 2)


def get_checkpoint_store_path(workspace_id, checkpoint_dir_path):
    pass


def resource_str_column_to_dict(res, key_list=None):
    """
    DB 결과 값 중 json 포맷인 column의 아이템을 json으로 바꿔주는 기능
    res:(return of cur.fetchone() | cur.fetchall())
    key_list:(list) default(None) = ["gpu_model", "libs_digest"]  or user define ex) ["key_a","key_b", ... ,"key_n"]
    """
    if key_list is None:
        key_list = ["gpu_model", "libs_digest", "node_name", "cni_config"] # For db column(store json str).

    if res is None:
        return res

    # bool이나 다른 예상치 못한 타입 처리
    if not isinstance(res, (dict, list)):
        return res

    def convert_str_to_json(res, key_list):
        for convert_key in key_list:
            if res.get(convert_key) is None:
                continue
            try:
                data = res[convert_key]
                if data is not None:
                    res[convert_key] = json.loads(data)
            except:
                res[convert_key] = data

    if type(res) == type({}):
        convert_str_to_json(res=res, key_list=key_list)
    else :
        for i, d in enumerate(res):
            convert_str_to_json(res=res[i], key_list=key_list)
    return res

def convert_gpu_model(gpu_model):
    # TODO 용어 개선 (2022-09-07 Yeobie) 
    # {
    #     "GTX-1080":["node1","node2"],
    #     "GTX-2080":["node3","node4"]
    # }
    # ->
    # [{"model": "GTX-1080", "node_list": ["node1", "node2"]}]

    if gpu_model is None:
        return None

    gpu_model_list = []
    for k,v in gpu_model.items():
        gpu_model_list.append({
            "model": k,
            "node_list": v
        })
    return gpu_model_list

def convert_mig_model_to_gpu_model_form(gpu_model, mig_model):
    """
        Description: MIG model명 을 GPU model과 합쳐서 내려주는 함수

        Args:
            gpu_model (str) : NVIDIA-A100-PCIE-40GB
            mig_model (str) : nvidia.com/mig-2g.10gb

        Return :
            (str) : NVIDIA-A100-PCIE-40GB|mig-2g.10gb
    """
    
    gpu_model = gpu_model + "|" + mig_model.replace(NVIDIA_GPU_BASE_LABEL_KEY,"")
    
    return gpu_model

def convert_gpu_model_to_resource_key_form(gpu_model):
    """
        Description: DB에 저장된 gpu_model key를 k8s resource 설정에서 사용하는 key 값으로 변경하는 함수

        Args:
            gpu_model (str) : ex1) NVIDIA-A100-PCIE-40GB|mig-2g.10gb
                              ex2) NVIDIA-A100-PCIE-40GB

        Return:
            (str) : ex1) nvidia.com/mig-2g.10gb ex2) nvidia.com/gpu
    """
    splited_gpu_model = gpu_model.split("|")
    if len(splited_gpu_model) > 1:
        # MIG
        resource_key = NVIDIA_MIG_GPU_RESOURCE_LABEL_KEY.format(mig_key=splited_gpu_model[-1])
    else :
        # General
        resource_key = NVIDIA_GPU_RESOURCE_LABEL_KEY

    return resource_key
    

def update_dict_key_count(dict_item, key, add_count=1, default=0, exist_only=False):
    # exist_only(True|False) = dict key have to exist. if not skip.
    if dict_item.get(key) is None:
        if exist_only == True:
            return

        dict_item[key] = default

    dict_item[key] += add_count


def convert_run_code_to_run_command(run_code, parameter=""):
    # py, sh 파일에 대해서 자동으로 실행자 연결
    # aa.py --a 1 --b 2 -> python aa.py --a 1 --b 2
    # aa.sh --a 1 --b 2 -> bash aa.sh --a 1 --b 2
    # my_bin aa.my -> my_bin aa.my

    if run_code.split(' ')[0][-3:]=='.py':
        run_command = "python -u {run_code} {parameter}".format(run_code=run_code, parameter=parameter)
    elif run_code.split(' ')[0][-3:]=='.sh':
        run_command = "bash {run_code} {parameter}".format(run_code=run_code, parameter=parameter)
    else:
        run_command = "{run_code} {parameter}".format(run_code=run_code, parameter=parameter)
    return run_command

def db_configurations_to_list(configurations):
    # DB Configurations (Jupyter, Deployment..에 있는) -> 개별 아이템 단위로 분리
    item_list= []
    parttern = re.compile(r" x.*ea")
    try:
        for item in configurations.split(","):
            if re.search(parttern, item) is not None:
                matched = re.search(parttern, item).group()
                number_of_item = int(matched.replace("x","").replace("ea",""))
            else :
                matched = ""
                number_of_item = 1
            item_list += [item.replace(matched,"")] * number_of_item
    except:
        pass
    return item_list

def configuration_list_to_db_configuration_form(configuration_list):
    
    configuration_items = list(set(configuration_list))
    for i in range(len(configuration_items)):
        count = configuration_list.count(configuration_items[i])
        if count > 1:
            configuration_items[i] = configuration_items[i] + " x {}ea".format(count)

    config = ",".join(configuration_items)
    return config


from fastapi import FastAPI, Response
from typing import List, Optional

def csv_response_generator(
    data_list: Optional[List[List[str]]] = None, 
    separator: str = ",", 
    data_str: Optional[str] = None, 
    filename: str = "mycsv"
) -> Response:
    """
    data_list(list): csv data list data form
    ex) [
        [header_1, header_2, header_3],
        [data_1_a, data_2_a, data_3_a],
        [data_1_b, "", data_3_b],
        ...
    ]
    separator(str): default (",") csv separator 
    data_str(str): csv data string data form (if this var exist. ignore data_list and separator)

    -->
    separator = ","
    ex)
    header_1,header_2,header_3\n
    data_1_a,data_2_a,data_3_a\n

    separator = "-"
    header_1-header_2-header_3\n
    data_1_a-data_2_a-data_3_a\n
    """
    csv_data = None

    if data_str is None and data_list is not None:
        formatted_list = [
            separator.join(map(str, data)) for data in data_list
        ]
        csv_data = "\n".join(formatted_list)
    else:
        csv_data = data_str

    headers = {
        'Content-Disposition': f'attachment; filename={filename}.csv',
        'Content-Type': 'text/csv'
    }

    return Response(content=csv_data, headers=headers)

async def text_response_generator_async(data_str, filename="default.txt"):
    """
    Description : txt file response 

    Args : 
        data_str (str) : text에 담기는 데이터

    Returns :
        (response) : text 다운로드용 response 
    """
    #from flask import make_response
    #download_response = make_response(data_str)
    #download_response.headers['Content-Disposition'] = 'attachment; filename=mytxt.txt'
    #download_response.mimetype='text/plain'
    #return download_response
    headers = {
        'Content-Disposition': f"attachment; filename={filename}",
    }
    from fastapi import Response as FastResponse 
    response = FastResponse(data_str, headers=headers)
    return response  

def text_response_generator(data_str, filename="default.txt"):
    """
    Description : txt file response 

    Args : 
        data_str (str) : text에 담기는 데이터

    Returns :
        (response) : text 다운로드용 response 
    """
    #from flask import make_response
    #download_response = make_response(data_str)
    #download_response.headers['Content-Disposition'] = 'attachment; filename=mytxt.txt'
    #download_response.mimetype='text/plain'
    #return download_response
    headers = {
        'Content-Disposition': f"attachment; filename={filename}",
    }
    from fastapi import Response as FastResponse 
    response = FastResponse(data_str, headers=headers)
    return response    
    

    
def load_json_file(file_path, retry_count=100, sleep=0.01, return_default=None,  *args, **kwargs):
    for i in range(retry_count):
        try:
            with open(file_path, "r") as f:
                data = f.read()
                data = json.loads(data)
            return data
        except FileNotFoundError:
            # print("FILE {} NOT FOUND".format(file_path))
            return return_default
        except json.decoder.JSONDecodeError:
            time.sleep(sleep)
            # print("JSON None ROUND {}".format(i))
            pass
    # print("JSON ENCODE ERROR")
    return return_default


def load_json_file_to_list(file_path, retry_count=100, sleep=0.01, return_default=None):
    
    for i in range(retry_count):
        json_list = []
        try:
            f = open(file_path, "r")
            for _, d in enumerate(f):
                json_list.append(json.loads(d))

            return json_list
        except FileNotFoundError:
            # print("FILE {} NOT FOUND".format(file_path))
            return return_default
        except json.decoder.JSONDecodeError:
            time.sleep(sleep)
            # print("JSON None ROUND {}".format(i))
            pass

    return json_list


def gib_to_bytes(gib):
    """
    Convert Gibibytes (GiB) to Bytes.

    Parameters:
    gib (float): Size in Gibibytes.

    Returns:
    int: Size in Bytes.
    """
    bytes_in_gib = 2 ** 30
    return gib * bytes_in_gib

def gb_to_bytes(gb):
    """
    Convert Gigabytes (GB) to Bytes.
    GB는 10^9 (1,000,000,000) 바이트를 사용합니다.
    예: 1 GB = 1,000,000,000 bytes

    Parameters:
    gb (float): Size in Gigabytes.

    Returns:
    int: Size in Bytes.
    """
    bytes_in_gb = 10 ** 9
    return gb * bytes_in_gb

def convert_to_bytes(size, unit):
    """
    Convert a size and unit (e.g., 1, "GB") to bytes.

    Args:
        size (float or int): The numeric size.
        unit (str): The unit of the size (e.g., "B", "KB", "MB", "GB", "TB").

    Returns:
        int: The size in bytes.

    Raises:
        ValueError: If the unit is not recognized.
    """
    # Define the conversion factors
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4
    }

    unit = unit.upper()  # Ensure the unit is case-insensitive

    if unit in units:
        return int(size * units[unit])
    else:
        raise ValueError(f"Invalid unit: {unit}")

def helm_parameter_encoding(params:str):
    #TODO 암호화 하는것도 가능
    """
        # 암호화 키 (16, 24, 32 바이트 길이) 해당 길이를 무조건 지켜야함함
        from Crypto.Cipher import AES
        key = b'jonathanjonathan' #
        iv = b'jonathanjonathan'  # 16바이트 길이
        cipher = AES.new(key, AES.MODE_CFB, iv=iv)
        collect_info_tmp = cipher.encrypt(json.dumps(nested_dict).encode('utf-8').encode('base64'))
    """
    #helm 을 통해서 전달 받은 pod내부에서 디코딩하는 Code
    """
    Origin data Convert Code

    try:
        res = base64.b64decode(params).decode("utf-8")
        ~~~~~
    except:
        ~~~~

    """
    try:
        result=""
        result = base64.b64encode(params.encode('utf-8')).decode('utf-8')
        return result
    except:
        return False

def get_flightbase_db_env():
    try:
        res={
            "JF_DB_CHARSET" : settings.JF_DB_CHARSET,
            "JF_DUMMY_DB_NAME" : settings.JF_DUMMY_DB_NAME,
            "JF_DB_NAME" : settings.JF_DB_NAME,
            "JF_DB_PW" : settings.JF_DB_PW,
            "JF_DB_USER" : settings.JF_DB_USER,
            "JF_DB_UNIX_SOCKET" : settings.JF_DB_UNIX_SOCKET,
            "JF_DB_PORT" : settings.JF_DB_PORT,
            "JF_DB_HOST" : settings.JF_DB_HOST
        }
        return res
    except:
        return False


def convert_to_seconds(num : int, unit : str):
    """
    Convert a size and unit (e.g., 1, "hour") to seconds.

    Args:
        size (float or int): The numeric size.
        unit (str): The unit of the time (e.g., "second", "minute", "hour", "day", "month").

    Returns:
        int: The size in seconds.

    Raises:
        ValueError: If the unit is not recognized.
    """
    # Define the conversion factors
    units = {
        "SECOND": 1,
        "MINUTE": 60,
        "HOUR": 3600,
        "DAY": 86400,
        "MONTH": 2592000  # Assuming 30 days in a month
    }

    unit = unit.upper()  # Ensure the unit is case-insensitive

    if unit in units:
        return int(num * units[unit])
    else:
        raise ValueError(f"Invalid unit: {unit}")

def convert_unit_num(value : str, target_unit : str=None, return_num : bool=False):
    """
    Description: 단위 변환 함수 1개
    Atgs:
        value (str) : 입력값(숫자 + 단위)
        target_unit (str) : 변경 단위 (m, "", k, M, G, T, P, E, Ki, Mi, Gi, Ti, Pi, Ei)
        return_num (bool) : 단위 없이 숫자만 결과값으로 반환
    Return:
        return_num : True -> float (숫자)
        return_num : False -> str (숫자 + 단위)
    """
    try:
        dec_units = {'m' : -1, '': 0, 'k' : 1, 'M' : 2,'G' : 3, 'T' : 4, 'P' : 5,'E' : 6}
        bin_units = {'Ki' : 1, 'Mi' : 2,'Gi' : 3, 'Ti' : 4, 'Pi' : 5, 'Ei' : 6}

        if target_unit is None:
            target_unit = ""

        # nun, unit
        unit = re.sub(r'[0-9.]+', '', str(value))
        num = str(value).replace(unit, "")

        # byte  
        if unit in dec_units.keys():
            byte = float(num) * (1000 ** dec_units[unit])
        else:
            byte = float(num) * (1024 ** bin_units[unit])

        # target_unit
        if target_unit in dec_units.keys():
            res = byte / (1000 ** dec_units[target_unit])
        else:
            res = byte / (1024 ** bin_units[target_unit])

        res = int(res)
        if return_num:
            return res
        return str(res) + target_unit
    except Exception as e:
        traceback.print_exc()
        return False

def convert_unit_list(value : list, target_unit : str=None, _sum : bool=False, _mul : bool=False):
    """
    Description: 단위 변환 함수 리스트 + 계산
    Args:
        value (list) : string(숫자 + 단위) - ex) ["1k", "1M", "1G"]
        target_unit (str) 변경 단위 - ex) "M"
        _sum (bool) : 리스트 합산하여 결과값 반환
        _mul (bool) : 리스트 곱하여 결과값 반환
    """
    if _sum and _mul:
        # 합, 곱 모두 다하는 경우는 없음
        return False
    if _sum:
        res = str(sum([convert_unit_num(value=i, target_unit=target_unit, return_num=True) for i in value])) + target_unit
    elif _mul:
        res = str(eval('*'.join([str(convert_unit_num(value=i, target_unit=target_unit, return_num=True)) for i in value]))) + target_unit
    else:
        res = [convert_unit_num(value=i, target_unit=target_unit) for i in value]
    return res

# def check_ngc_version():
#     """
#     Description: ngc launcher binary 현재 사용중인 버전이 최신버전인지 체크
    
#     Returns:
#         dict:
#             최신 버전인 경우, {"result" : True, "version" : current_version}
#             아닌 경우, {"result" : False, "current_version" : current_version, "latest_version" : latest_version}
#     """
#     out, _ = launch_on_host(cmd="ngc --version  --format_type json", ignore_stderr=True)
#     current_version = out.split()[2]

#     out, _ = launch_on_host(cmd="ngc version info --format_type json", ignore_stderr=True)
#     latest_version = json.loads(out)["versionId"]

#     if current_version == latest_version:
#         res = {"result" : True, "version" : current_version}
#     else:
#         res = {"result" : False, "current_version" : current_version, "latest_version" : latest_version}

#     return res

def execute_command_terminmal(command, std_callback=None, **kwargs):
    """
    Description: terminal에서 command를 실행시켜 실시간으로 내용을 출력하는 함수
                 출력 내용에서 \r이 있는 경우, 일부내용이 잘리는 경우가 있을 수 있음
    Args:
        command (str) : 터미널에서 실행할 명령어
        std_callbakc(func) : 이 함수를 실행하여 출력내용을 넘겨받을 callback 함수
                             함수에는 std_out, std_err 파라미터가 필수로 있어야함
                             EX) def _callback(std_out=None, std_err=None, param=None):
                                    if std_out:
                                        print(std_out)
                                    if std_err:
                                        print(std_err)
    """
    # package
    import sh # 1.14.3

    # check arguments
    if not any(i in inspect.getfullargspec(std_callback).args for i in ["std_out", "std_err"]):
        raise TypeError("{} missing 2 required argument function: 'std_out', 'std_err'".format(std_callback.__name__))
    elif "std_out" not in inspect.getfullargspec(std_callback).args:
        raise TypeError("{} missing 1 required argument: 'std_out'".format(std_callback.__name__))
    elif "std_err" not in inspect.getfullargspec(std_callback).args:
        raise TypeError("{} missing 1 required argument: 'std_err'".format(std_callback.__name__))

    cmd = command.split()[0]
    option = command.split()[1:]
    
    def _process_output(line):
        std_callback(std_out=line.strip(), **kwargs)
        
    def _process_error(line):
        std_callback(std_err=line.strip(), **kwargs)

    sh.Command(cmd)(option, _out=_process_output, _err=_process_error)

def check_func_running_time(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        start_r = time.perf_counter()
        start_p = time.process_time()   
        # 함수 실행
        ret = f(*args, **kwargs)
        end_r = time.perf_counter()
        end_p = time.process_time()
        elapsed_r = end_r - start_r
        elapsed_p = end_p - start_p

        print(f'{f.__name__} elapsed: {elapsed_r:.6f}sec (real) / {elapsed_p:.6f}sec (cpu)')
        return ret
    return wrap

async def get_gpu_cluster_info(instance_id : int, redis_client = None) -> dict:
    from utils.msa_db import db_node
    from utils import redis_key
    instance_node_list = db_node.get_node_instance_list(instance_id=instance_id)
    instance_node_names = [node["node_name"] for node in instance_node_list]
    gpu_name = instance_node_list[0]["gpu_name"]
    # redis_con = get_redis_client(role="slave")
    gpu_info = json.loads(await redis_client.get(redis_key.GPU_INFO_RESOURCE))
    gpu_parse = dict()
    for node_name, gpus in gpu_info.items():
        if node_name in instance_node_names:
            for gpu_uuid, gpu_info in gpus.items():
                if gpu_info["model_name"] == gpu_name:
                    if gpu_parse.get(node_name, None):
                        gpu_parse[node_name].append({
                            "gpu_name" : gpu_name,
                            "gpu_uuid" : gpu_uuid,
                            "used" : gpu_info["used"],
                        })
                    else:
                        gpu_parse[node_name] = [{
                            "gpu_name" : gpu_name,
                            "gpu_uuid" : gpu_uuid,
                            "used" : gpu_info["used"],
                        }]
    return gpu_parse

def get_gpu_cluster_info_sync(instance_id : int, redis_client = None) -> dict:
    from utils.msa_db import db_node
    from utils import redis_key
    instance_node_list = db_node.get_node_instance_list(instance_id=instance_id)
    instance_node_names = [node["node_name"] for node in instance_node_list]
    gpu_name = instance_node_list[0]["gpu_name"]
    # redis_con = get_redis_client(role="slave")
    gpu_info = json.loads(redis_client.get(redis_key.GPU_INFO_RESOURCE))
    gpu_parse = dict()
    for node_name, gpus in gpu_info.items():
        if node_name in instance_node_names:
            for gpu_uuid, gpu_info in gpus.items():
                if gpu_info["model_name"] == gpu_name:
                    if gpu_parse.get(node_name, None):
                        gpu_parse[node_name].append({
                            "gpu_name" : gpu_name,
                            "gpu_uuid" : gpu_uuid,
                            "used" : gpu_info["used"],
                        })
                    else:
                        gpu_parse[node_name] = [{
                            "gpu_name" : gpu_name,
                            "gpu_uuid" : gpu_uuid,
                            "used" : gpu_info["used"],
                        }]
    return gpu_parse


async def get_auto_gpu_cluster(redis_client, instance_id : int, gpu_count: int, gpu_cluster_info : dict = {}):
    
    if gpu_cluster_info:
        data = gpu_cluster_info
    else:
        data = await get_gpu_cluster_info(instance_id=instance_id, redis_client=redis_client)
    global_gpu_count = gpu_count
    divisors = [] # 요청된 gpu 수를 가지고 나올 수 있는 pod별 gpu개수의 경우의 수
    for i in range(1, global_gpu_count + 1):
        if global_gpu_count % i == 0:
            divisors.append(i)
    divisors = sorted(divisors, reverse=True)
    gpus_per_node = {} # node 당 gpu 개수
    available_gpus_per_node = {} # 사용할 수 있는 node당 gpu 개수
    max_gpu = 0 # node의 gpu수(가장 많은)
    for node, gpus in data.items():
        gpus_per_node[node] =  len(gpus)
        available_gpus_per_node[node] = sum(1 for gpu in gpus if gpu['used'] == 0)
        max_gpu = max(len(gpus),max_gpu)
    
    real_divisors = [] # 실제 요청될 수 있는 pod별 gpu개수의 경우의 수
    for divisor in divisors:
        if max_gpu < divisor: # 가용할 수 있는 gpu 
            continue
        pod_count = global_gpu_count // divisor # 가상의 개수 
        real_pod_count = 0 # 실제로 뜰 수 있는 pod 개수 
        for node, gpu_count in gpus_per_node.items():
            if gpu_count < divisor:
                continue
            real_pod_count += gpu_count // divisor
            
        if real_pod_count < pod_count:
            continue
        real_divisors.append(divisor)
    result = []
    for real_divisor in real_divisors:
        pod_count = global_gpu_count // real_divisor # 가상의 개수 
        real_pod_count = 0 # 실제로 뜰 수 있는 pod 개수 
        for node, gpu_count in available_gpus_per_node.items():
            if gpu_count < real_divisor:
                continue
            real_pod_count += gpu_count // real_divisor
            
        if real_pod_count < pod_count:
            result.append({"gpu_count" : real_divisor, "server" : pod_count, "status" : False})
        else:
            result.append({"gpu_count" : real_divisor, "server" : pod_count, "status" : True})
    
    return result

def make_nested_dict():
    return defaultdict(make_nested_dict)

def defaultdict_to_dict(d):
    if isinstance(d, defaultdict):
        return {k: defaultdict_to_dict(v) for k, v in d.items()}
    else:
        return d

async def post_request(url, data):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                response.raise_for_status()  # HTTP 에러 상태 코드(4xx, 5xx)를 예외로 처리
                try:
                    response_data = await response.json()
                    return response_data
                except aiohttp.ContentTypeError:
                    # 서버 응답이 JSON이 아닐 경우 발생하는 예외 처리
                    print(f"Failed to decode JSON from {url}")
                    return None
    except aiohttp.ClientError as e:
        # 네트워크 관련 오류 (예: 연결 실패, 타임아웃 등)
        print(f"Client error occurred: {e}")
        return None
    except asyncio.TimeoutError:
        # 요청이 타임아웃된 경우
        print(f"Request to {url} timed out")
        return None
    except Exception as e:
        # 그 외 다른 예외들
        print(f"An unexpected error occurred: {e}")
        return None
def post_request_sync(url, data):
    try:
        import requests
        response = requests.post(url, json=data)
        response.raise_for_status()  # HTTP 에러 상태 코드(4xx, 5xx)를 예외로 처리
        try:
            response_data = response.json()  # JSON 응답을 파싱
            return response_data
        except requests.exceptions.JSONDecodeError:
            # 서버 응답이 JSON이 아닐 경우 발생하는 예외 처리
            print(f"Failed to decode JSON from {url}")
            return None
    except requests.exceptions.RequestException as e:
        # 네트워크 관련 오류 (예: 연결 실패, 타임아웃 등)
        print(f"Client error occurred: {e}")
        return None
    except Exception as e:
        # 그 외 다른 예외들
        print(f"An unexpected error occurred: {e}")
        return None


def sanitize_filename(filename: str) -> str:
    """
    정규 표현식을 사용하여 ?*<>#$%&()/"|\ 및 공백을 _ 로 대체
    """
    sanitized = re.sub(r'[?*<>#$%&()/"|\s]', '_', filename)
    return sanitized


from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from utils import PATH
from itertools import islice

async def get_files_streaming(
    base_path: str,
    file_extension: list = [],
    ignore_folders: list = [],
    search_index: int = 1,
    search_count: int = 100,
    replace_file_path: str = TYPE.PROJECT_TYPE
):
    loop = asyncio.get_running_loop()

    def filter_files(search_index):
        count = 0
        for index, path in islice(enumerate(Path(base_path).rglob('*')), search_index, None):
            search_index -= 1
            if index != 0 and index == search_index:  # search_index보다 작은 경우 건너뜀
                continue
            if any(ignored in str(path) for ignored in ignore_folders):
                continue
            if path.is_file():
                if file_extension and path.suffix.lstrip('.') not in file_extension:
                    continue
                if count >= search_count:  # search_count만큼만 반환
                    break
                count += 1
                yield index, path  # 인덱스와 파일 경로 반환

    with ThreadPoolExecutor() as pool:
        for index, path in await loop.run_in_executor(pool, lambda: filter_files(search_index)):
            if replace_file_path == TYPE.PROJECT_TYPE:
                file_path = str(path).replace(base_path, PATH.JF_PROJECT_BASE_HOME_POD_PATH)
            elif replace_file_path == TYPE.PREPROCESSING_TYPE:
                file_path = str(path).replace(base_path, PATH.JF_PREPROCESSING_BASE_HOME_POD_PATH)
            else:
                file_path = str(path)

            data = {
                "file_path": file_path,
                "index": index + 1
            }

            yield f"data: {json.dumps(data)}\n\n"  # 스트리밍 즉시 반환


# TODO
# 해당 함수 삭제 예정
async def get_files(base_path, file_extension, ignore_folders, is_full_path=False, replace_file_path = TYPE.PROJECT_TYPE):
    run_code_list = []
    file_list = []
    loop = asyncio.get_running_loop()

    def filter_files():
        files = []
        for path in Path(base_path).rglob('*'):
            if any(ignored in str(path) for ignored in ignore_folders):
                continue
            if path.is_file():
                files.append(path)
        return files

    with ThreadPoolExecutor() as pool:
        files = await loop.run_in_executor(pool, filter_files)
        
        for path in files:
            # if not is_full_path:
            if replace_file_path == TYPE.PROJECT_TYPE:
                file_path = str(path).replace(base_path, PATH.JF_PROJECT_BASE_HOME_POD_PATH)
            elif replace_file_path == TYPE.PREPROCESSING_TYPE:
                file_path = str(path).replace(base_path, PATH.JF_PREPROCESSING_BASE_HOME_POD_PATH)
                
            if path.suffix.lstrip('.') in file_extension:
                run_code_list.append(file_path)
            else:
                file_list.append(file_path)
    
    return run_code_list, file_list



def escape_special_chars(command):
    # 특수 기호 목록
    special_chars = ['(', ')', '"', '\'', '&', '|', ';', '<', '>', '$', '`', '\\', ","]

    # 특수 기호 앞에 \를 붙여주는 함수
    def escape_char(match):
        return '\\' + match.group(0)

    # 정규식을 사용하여 특수 기호를 찾아 이스케이프 처리
    escaped_command = re.sub(r'([{}])'.format(''.join(re.escape(c) for c in special_chars)), escape_char, command)
    return escaped_command


def calculate_elapsed_time(start_time: str, end_time: str, time_format: str = TYPE.TIME_DATE_FORMAT) -> int:
    """
    주어진 시작 시간과 종료 시간의 차이를 초 단위로 반환하는 함수.

    :param start_time: 시작 시간 (예: "2025-02-02 23:07:08")
    :param end_time: 종료 시간 (예: "2025-02-02 23:26:08")
    :param time_format: 시간 형식 (기본값: "%Y-%m-%d %H:%M:%S")
    :return: 경과 시간 (초)
    """
    start = datetime.strptime(start_time, time_format)
    end = datetime.strptime(end_time, time_format)
    elapsed_time = (end - start).total_seconds()
    return int(elapsed_time)
