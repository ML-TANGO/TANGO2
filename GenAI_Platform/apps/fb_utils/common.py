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
from utils.exceptions import *
import utils.settings as settings

import hashlib
import re
sys.path.insert(0, os.path.abspath('..'))
from utils.TYPE import *
# from utils.common_data import *
import inspect

from collections import defaultdict
from typing import List
from functools import reduce, lru_cache, cache, wraps

global_lock = threading.Lock()  # lock for job_queue
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


def make_nested_dict():
    return defaultdict(make_nested_dict)

def dec_round(x,y):
    return float(round(Decimal(x),y))

# def log_function_call(function):
#     @functools.wraps(function)
#     def wrapped(*args, **kwargs):
#         try:
#             enabled = settings.ENABLE_LOG_FUNCTION_CALL
#         except:
#             enabled = False
#         if enabled:
#             temp_list = [ temp_element for temp_element in args] + ["{}={}".format(temp_key, kwargs[temp_key]) for temp_key in kwargs.keys()]
#             print ('CALLED: ', function.__name__ + '(' + ', '.join([repr(temp_element) for temp_element in temp_list])+')')
#             print (function.__name__, '(', *args, *["{}={}".format(temp_key, kwargs[temp_key]) for temp_key in kwargs.keys()], ')')
#             temp_time = time.time()
#             res = function(*args, **kwargs)
#             elapsed = time.time() - temp_time
#             print ('ELAPSED of '+ function.__name__ + ':', elapsed)
#             return res
#         else:
#             return function(*args, **kwargs)
#     return wrapped

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


# def execute_command_ssh(address, username, password, key_file_name, command, error_raise=False, key_login=settings.LAUNCHER_KEY_LOGIN, std_callback=(None, {})):
#     """ Throws IOError when host down or something.
#     ssh key login 주석 추가 & def execute_command_ssh(address, username, *password, command): 함수 파라미터 설정 - 패스워드를 사용 안할 경우

#     std_callback
#         1. tuple(function, **kwargs) : kwargs 가 없는 경우라도, tuple 형식이어야 함. (function,)
#         2. function(std_out, std_err, **kwargs) : callback 할 함수 - input으로 std_out, std_err 2개의 arguments를 받는 함수이어야 함. 2개의 key가 없을 시, TypeError
#         3. kwargs : callback 함수에서 사용하는 key, value (std_out, std_err 외의 추가적인 keyword arguments)
#         example - launch_on_host(..., std_callback=(function,)) or launch_on_host(..., std_callback=(function, {key : value, ...}))
#     """
#     address = address.split(':')
#     if len(address) == 1:
#         hostname = address[0]
#         port = settings.LAUNCHER_SSH_PORT
#     elif len(address) == 2:
#         hostname = address[0]
#         port = address[1]
#     else: #IPv6 case or typo or something
#         raise ValueError('Unsuppoted address {}'.format(':'.join(address)))

#     client = paramiko.SSHClient()
#     client.load_system_host_keys()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     try:
#         if key_login:
#             client.connect(hostname, port=port, username=username, key_filename=key_file_name)
#         else:
#             client.connect(hostname, port=port, username=username, password=password)
#         '''
#         if pwd:
#             client.connect(hostname, port=port, username=username, password=password)
#         else:
#             client.connect(hostname, port=port, username=username, key_filename='/jfbcore/jf-bin/launcher_bins/{private 키 파일명}')
#         '''
#     except paramiko.ssh_exception.SSHException as sshe: # tcp timeout
#         if error_raise:
#             raise sshe
#         traceback.print_exc()
#         return None, None
#     _, stdout, stderr = client.exec_command(command)

#     if std_callback[0]:
#         # kwargs 없는 경우
#         if len(std_callback) < 2:
#             std_callback += (dict(),)

#         # check arguments
#         if not any(i in inspect.getfullargspec(std_callback[0]).args for i in ["std_out", "std_err"]):
#             raise TypeError("{} missing 2 required argument function: 'std_out', 'std_err'".format(std_callback[0].__name__))
#         elif "std_out" not in inspect.getfullargspec(std_callback[0]).args:
#             raise TypeError("{} missing 1 required argument: 'std_out'".format(std_callback[0].__name__))
#         elif "std_err" not in inspect.getfullargspec(std_callback[0]).args:
#             raise TypeError("{} missing 1 required argument: 'std_err'".format(std_callback[0].__name__))

#         tmp_stdout, tmp_stderr = list(), list()
#         while True:
#             # stdout
#             if stdout.channel.recv_ready():
#                 line_out = stdout.readline().strip()
#                 tmp_stdout.append(line_out)
#             else:
#                 line_out = None

#             # stderr
#             if stderr.channel.recv_stderr_ready():
#                 line_err = stderr.readline().strip()
#                 tmp_stderr.append(line_err)
#             else:
#                 line_err = None

#             # callback
#             std_callback[0](std_out=line_out, std_err=line_err, **std_callback[1])

#             # break
#             if stdout.channel.exit_status_ready() == True and stdout.channel.recv_ready() == False and stderr.channel.recv_stderr_ready() == False:
#                 # flush
#                 line_out = stdout.read().decode('utf-8')
#                 line_err = stderr.read().decode('utf-8')
#                 std_callback[0](std_out=line_out, std_err=line_err, **std_callback[1])
#                 tmp_stdout.append(line_out)
#                 tmp_stderr.append(line_err)
#                 break
#         result_stdout, result_stderr = '\n'.join(tmp_stdout).encode('utf-8'), '\n'.join(tmp_stderr).encode('utf-8')
#     else:
#         result_stdout, result_stderr = stdout.read(), stderr.read()

#     client.close()
#     return result_stdout, result_stderr

# #@log_function_call
# def launch_on_host(cmd, ignore_stderr=False, host=None, std_callback=(None, {})):
#     """Launch a command on host using launcher system.

#     Launcher system runs the command with a root privillage.
#     But it could excute only a few limited programs which
#     are in LAUNCHER_BINS_DIR. Also launcher is not a sudoer.
#     So it is safe from attacks atempting to run other
#     dangerous commands.

#     The ip of the host should be given by command line argument --jf-ip
#     or passed by param host.

#     std_callback
#         1. tuple(function, **kwargs) : kwargs 가 없는 경우라도, tuple 형식이어야 함. (function,)
#         2. function(std_out, std_err, **kwargs) : callback 할 함수 - input으로 std_out, std_err 2개의 arguments를 받는 함수이어야 함. 2개의 key가 없을 시, TypeError
#         3. kwargs : callback 함수에서 사용하는 key, value (std_out, std_err 외의 추가적인 keyword arguments)
#         example - launch_on_host(..., std_callback=(function,)) or launch_on_host(..., std_callback=(function, {key : value, ...}))
#     """
#     if host is None:
#         host = get_args().jf_ip
#         if host is None:
#             raise KeyError('CLI argument --jf-ip not given.')

#     result_stdout, result_stderr = execute_command_ssh(
#                                         address=host,
#                                         username=settings.LAUNCHER_ID,
#                                         password=settings.LAUNCHER_PW,
#                                         key_file_name=settings.LAUNCHER_PRIVATE_KEY,
#                                         command=cmd,
#                                         std_callback=std_callback
#                                     )

#     if result_stdout is None:
#         return None
#     else:
#         result_stdout = result_stdout.decode('utf-8')
#     if result_stderr is not None:
#         result_stderr = result_stderr.decode('utf-8')
#     if not ignore_stderr and result_stderr is not None and len(result_stderr) > 0:
#         raise RemoteError(result_stderr)
#     return result_stdout, result_stderr

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

# def get_pod_gpu_list(pod_name):
#     arr = []
#     try:
#         nvidia_info, *_ = launch_on_host("kubectl exec {} -- nvidia-smi -q -x".format(pod_name),ignore_stderr=True) # 0.5 ~ 0.6 초 소요
#         if 'NotFound' in nvidia_info:
#             return {"num_gpus": len(arr), "list": arr}

#         nvidia_info = ET.fromstring(nvidia_info)
#         for r in nvidia_info:
#             # if e1.tag == 'attached_gpus':
#             # print(e1.text);
#             if r.tag == 'gpu':
#                 info = {
#                     "num": int(r.find('minor_number').text),
#                     "model": r.find('product_name').text,
#                     "mem_total": r.find('fb_memory_usage').find('total').text,
#                     "mem_used": r.find('fb_memory_usage').find('used').text,
#                     "mem_free": r.find('fb_memory_usage').find('free').text,
#                     "gpu_util": r.find('utilization').find('gpu_util').text,
#                     "mem_util": r.find('utilization').find('memory_util').text,
#                     "temperature": r.find('temperature').find('gpu_temp').text,
#                 }
#                 arr.append(info)
#     except Exception as e:
#         print('Error:',e)
#         #traceback.print_exc()
#     arr.sort(key=lambda a: a["num"], reverse=False)
#     return {"num_gpus": len(arr), "list": arr}

# def get_pod_cpu_model_name(pod_name):
#     cpu_model_name = None
#     try:
#         cpu_model_name, *_ = launch_on_host("kubectl exec {} -- cat /proc/cpuinfo".format(pod_name), ignore_stderr=True)
#         for line in cpu_model_name.split("\n"):
#             if "model name" in line:
#                 cpu_model_name = re.sub( ".*model name.*:", "", line,1)
#                 while (cpu_model_name[0] == " "):
#                     cpu_model_name = cpu_model_name[1:]
#                 return cpu_model_name
#     except Exception as e:
#         traceback.print_exc()
#     return cpu_model_name

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

def get_date_time(timestamp=None, date_format="%Y-%m-%d %H:%M:%S"):
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
        "%Y-%m-%d %H:%M:%S"
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

def write_user_info(base, target, users=[]):
    os.system('mkdir -p {target}'.format(target=target))
    for i, user in enumerate(users):
        if i == 0:
            os.system('cat {base}/passwd | grep ^{user}: >  {target}/passwd'.format(base=base, user=user, target=target))
            os.system('cat {base}/shadow | grep ^{user}: >  {target}/shadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/gshadow | grep ^{user}: >  {target}/gshadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/group | grep ^{user}: >  {target}/group'.format(base=base, user=user, target=target))
        else :
            os.system('cat {base}/passwd | grep ^{user}: >>  {target}/passwd'.format(base=base, user=user, target=target))
            os.system('cat {base}/shadow | grep ^{user}: >>  {target}/shadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/gshadow | grep ^{user}: >>  {target}/gshadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/group | grep ^{user}: >>  {target}/group'.format(base=base, user=user, target=target))

def apply_user_info(base, target):
    # ALL COPY
    #TODO 정리 필요
    if os.system("ls {target}/  > /dev/null 2>&1".format(target=target)) == 0:
        os.system('cat {base}/passwd > {target}/passwd'.format(base=base, target=target))
        os.system('cat {base}/shadow > {target}/shadow'.format(base=base, target=target))
        os.system('cat {base}/gshadow > {target}/gshadow'.format(base=base, target=target))
        os.system('cat {base}/group > {target}/group'.format(base=base, target=target))
        return True
    else:
        return False



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


def log_access(contents):
    try:
        cur_time = time.gmtime()
        contents['time']=cur_time
        log_filename='{}/{}.log'.format(settings.JF_LOG_DIR, time.strftime('%Y%m%d', cur_time))

        with open(log_filename, 'a') as fout:
            fout.write(json.dumps(contents)+'\n')
    except:
        traceback.print_exc()


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

    status = "unknwon"
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

# def parameter_str_to_dict(parameter, flag=" "):
#     def cut_space(str_):
#         if len(str_) == 0:
#             # --param --param2 a --param3 b
#             return str_
#         if str_[-1] == " ":
#             return cut_space(str_[:-1])
#         else:
#             return str_

#     parameter_dict = {}
#     for item in parameter.split("--"):
#         item = item.split(flag)
#         if len(item) < 2:
#             continue
#         param, value = item[:2]
#         if param == "":
#             continue
#         parameter_dict[param] = cut_space(value)
#     return parameter_dict

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

# def get_worker_requests(ip, path="", timeout=settings.JF_WORKER_CONNECT_TIMEOUT, headers:dict={}, params:dict={}):
#     from utils.settings import JF_WORKER_PORT
#     import requests
#     get_status = False
#     message = ""
#     try:
#         res = requests.get('http://{}:{}/worker/{}'.format(ip, JF_WORKER_PORT, path), timeout=timeout, headers=headers, params=params)
#         get_status = True
#     except requests.exceptions.ConnectionError as rece:
#         res = None
#         message = str(rece)
#         # print("WORKER ", ip , "Connection error")
#     except ConnectionRefusedError as cre:
#         res = None
#         message = str(cre)
#         # print("WORKER ", ip , "Connection error")
#         # traceback.print_exc()
#     except requests.exceptions.ReadTimeout as rert:
#         res = None
#         message = str(rert)
#         print("WORKER ", ip , "Connection timeout")
#     except Exception as e:
#         res = None
#         message = str(e)
#         traceback.print_exc()

#     return {
#         "get_status": get_status,
#         "result": res,
#         "message": message
#     }

# def post_worker_requests(ip, path="", timeout=settings.JF_WORKER_CONNECT_TIMEOUT, headers:dict={}, params:dict={}):
#     from settings import JF_WORKER_PORT, JF_WORKER_CONNECT_TIMEOUT
#     import requests
#     get_status = False
#     message = ""
#     try:
#         res = requests.post('http://{}:{}/worker/{}'.format(ip, JF_WORKER_PORT, path), timeout=timeout, headers=headers, json=params)
#         get_status = True
#     except requests.exceptions.ConnectionError as rece:
#         res = None
#         message = str(rece)
#         # print("WORKER ", ip , "Connection error")
#     except ConnectionRefusedError as cre:
#         res = None
#         message = str(cre)
#         # print("WORKER ", ip , "Connection error")
#         # traceback.print_exc()
#     except requests.exceptions.ReadTimeout as rert:
#         res = None
#         message = str(rert)
#         print("WORKER ", ip , "Connection timeout")
#     except Exception as e:
#         res = None
#         message = str(e)
#         traceback.print_exc()

#     return {
#         "get_status": get_status,
#         "result": res,
#         "message": message
#     }

def get_worker_device_info(ip):

    # Worker router.py /device_info 참조
    worker_response = get_worker_requests(ip=ip, path="device_info")
    get_status = worker_response["get_status"]
    res = worker_response["result"]

    device_info = None
    if res is None:
        pass
    elif res.status_code == 200:
        get_status = True
        device_info = json.loads(res.text)['result']

    return get_status, device_info

def get_worker_network_interfaces(ip):
    # res = requests.get('http://{}:{}/worker/network_interfaces'.format(ip, JF_WORKER_PORT))
    worker_response = get_worker_requests(ip=ip, path="network_interfaces")
    get_status = worker_response["get_status"]
    res = worker_response["result"]

    interfaces = None
    if res is None:
        pass
    elif res.status_code == 200:
        get_status = True
        interfaces = json.loads(res.text)['result']

    return get_status, interfaces

def new_get_worker_network_interfaces(ip):
    worker_response = get_worker_requests(ip=ip, path="network-interfaces-new", timeout=10)
    get_status = worker_response["get_status"]
    res = worker_response["result"]

    interfaces = None
    if res is None:
        pass
    elif res.status_code == 200:
        get_status = True
        interfaces = json.loads(res.text)['result']

    return get_status, interfaces

def get_worker_mem_usage(ip):
    # from settings import JF_WORKER_PORT
    # import requests
    # res = requests.get('http://{}:{}/worker/mem_usage'.format(ip, JF_WORKER_PORT))
    worker_response = get_worker_requests(ip=ip, path="mem_usage")
    get_status = worker_response["get_status"]
    res = worker_response["result"]

    mem_usage = None
    if res is None:
        pass
    elif res.status_code == 200:
        get_status = True
        if json.loads(res.text).get('result') is not None:
            mem_usage = json.loads(res.text).get('result')
        else :
            #FOR OLD VERSION WORKER
            mem_usage = json.loads(res.text)

    return get_status, mem_usage

def get_worker_cpu_usage(ip):
    # from settings import JF_WORKER_PORT
    # import requests
    # res = requests.get('http://{}:{}/worker/mem_usage'.format(ip, JF_WORKER_PORT))
    worker_response = get_worker_requests(ip=ip, path="cpu_usage")
    get_status = worker_response["get_status"]
    res = worker_response["result"]

    mem_usage = None
    if res is None:
        pass
    elif res.status_code == 200:
        get_status = True
        if json.loads(res.text).get('result') is not None:
            mem_usage = json.loads(res.text).get('result')
        else :
            #FOR OLD VERSION WORKER
            mem_usage = json.loads(res.text)

    return get_status, mem_usage


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
    return round(byte_size/float(1024*1024*1024), 2)


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

def log_critical_error(message):
    """
    message (str) : 사용자 선언 error message or traceback.format_exc()
    """
    import datetime
    import json
    # 치명적 오류를 LOG에 남기기 위해..
    # save date-time, custom-message, error
    print("Saved CRITIAL ERROR LOG")
    log_info = {
        "datetime": str(datetime.datetime.now()),
        "message": message
    }
    with open(CRITIAL_ERROR_LOG, "w") as fw:
        fw.write(json.dumps(log_info))

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


def csv_response_generator_old(data_list=None, separator=",", data_str=None, filename="mycsv"):
    """
    data_list(list): csv data list data form
    ex) [
        [header_1, header_2, header_3],
        [data_1_a, data_2_a, data_3_a],
        [data_1_b, "", data_3_b],
        ...
    ]
    separator(str): default (",") csv separator
    data_str(str): csv data string data form (if this var exist. ignore data_list and seprator)

    -->
    seprator = ","
    ex)
    header_1,header_2,header_3\n
    data_1_a,data_2_a,data_3_a\n

    seprator = "-"
    header_1-header_2-header_3\n
    data_1_a-data_2_a-data_3_a\n
    """
    from flask import make_response

    csv_data = None

    if data_str is None:
        for i, data in enumerate(data_list):
            if type(data) == type([]):
                data_list[i] = separator.join(str(d) for d in data)
            else :
                continue

        csv_data= "\n".join(str(data) for data in data_list)

    else:
        csv_data = data_str



    download_response = make_response(csv_data)
    download_response.headers['Content-Disposition'] = 'attachment; filename={}.csv'.format(filename)
    download_response.mimetype='text/csv'
    return download_response

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


def path_convert(full_path, old_path, new_path):
    """
    Description : HOST PATH -> POD PATH | POD PATH -> HOST PATH 변환을 위한

    Args :
        full_path (str) : 변경 하려고 하는 경로 (run_code로 저장되어있는 값) /jf-training-home/src/training-deployment-example/deployment.sh
        old_path (str) : 변경 되려는 값 - /jf-training-home  = JF_TRAINING_POD_PATH
        new_path (str) : 변경 하려는 값 - /jf-data/workspaces/robert-ws/trainings/custom-d-test/ = JF_TRAINING_PATH
    """
    if full_path[0:len(old_path)] == old_path:
        full_path = full_path.replace(old_path, new_path, 1)

    return full_path

def gpu_model_to_dumps(gpu_model):
    """
        Description : Training / Deployment 생성 전 GPU Model 선택 하는 부분에서 전달 받은 GPU Model 정보 값을 DB에 저장할 수 있도록 dumps 변환 하는 부분
                     None 은 dumps 로 넣을 경우 'null' 이나 DB 에는 NULL 값으로 저장할 수 있도록 함
    """
    try:
        if gpu_model is not None:
            gpu_model = json.dumps(gpu_model)
    except Exception as e:
        traceback.print_exc()
        return gpu_model
    return gpu_model

def dict_to_db_insert_form(dict_data):
    rows = tuple(dict_data.values())
    keys = ",".join([ str(k) for k in dict_data.keys() ])
    values = ",".join(["%s"] * len(rows))
    return rows, keys, values

from multiprocessing import Process, Queue

class Multiprocessor():

    def __init__(self):
        self.processes = []
        self.queue = Queue()

    @staticmethod
    def _wrapper(func, queue, args, kwargs):
        ret = func(*args, **kwargs)
        queue.put(ret)

    def run(self, func, *args, **kwargs):
        args2 = [func, self.queue, args, kwargs]
        p = Process(target=self._wrapper, args=args2)
        self.processes.append(p)
        p.start()

    def wait(self):
        rets = []
        for p in self.processes:
            ret = self.queue.get()
            rets.append(ret)
            print("append done")
        for p in self.processes:
            p.join()
            print("join done")
            p.terminate()
            print("terminate done")
        return rets

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


def parsing_node_name(node_name):
    """
        Description : 자원 선택 시 정보를 저장하는 node_name 영역의 정보를 parsing해서 CPU/GPU 선택별 제한 정보, ALL 옵션에 대한 정보 내려주는 함수

        Return :
            {
                "node_name_cpu": {...},
                "node_name_cpu_all": {...} or None,
                "node_name_gpu": {...},
                "node_name_gpu_all": {...} or None
            }
            ex)
            {
                'node_name_cpu':
                {
                    'jf-node-02-all': {
                        'cpu_cores_limit_per_pod': 5,
                        'ram_limit_per_pod': 2,
                        'cpu_cores_limit_per_gpu': 5,
                        'ram_limit_per_gpu': 2
                    },
                    {
                    'jf-node-02-cpu': {
                        'cpu_cores_limit_per_pod': 5,
                        'ram_limit_per_pod': 2
                    }
                },
                'node_name_cpu_all': {
                    'cpu_cores_limit_per_pod': 5,
                    'ram_limit_per_pod': 2,
                    'cpu_cores_limit_per_gpu': 5,
                    'ram_limit_per_gpu': 2
                },
                'node_name_gpu': {
                    'jf-node-02-all': {
                        'cpu_cores_limit_per_pod': 5,
                        'ram_limit_per_pod': 2,
                        'cpu_cores_limit_per_gpu': 5,
                        'ram_limit_per_gpu': 2
                    },
                    'jf-node-02-gpu': {
                        'cpu_cores_limit_per_gpu': 5,
                        'ram_limit_per_gpu': 2
                    }
                },
                'node_name_gpu_all': {
                    'cpu_cores_limit_per_pod': 5,
                    'ram_limit_per_pod': 2,
                    'cpu_cores_limit_per_gpu': 5,
                    'ram_limit_per_gpu': 2
                }
            }
    """
    # CPU NODE - RES
    # GPU NODE - RES
    # CPU ALL - RES
    # GPU ALL - RES
    if node_name == None:
        node_name = {}
    NODE_LIMIT_ALL_KEY = "@all"

    node_name_cpu = {}
    node_name_gpu = {}
    node_cpu_all = None
    node_gpu_all = None

    for key, value in node_name.items():

        if NODE_CPU_LIMIT_PER_POD_DB_KEY in value and NODE_MEMORY_LIMIT_PER_POD_DB_KEY in value:
            if key == NODE_LIMIT_ALL_KEY:
                node_cpu_all = value
            else:
                node_name_cpu[key] = value

        if NODE_CPU_LIMIT_PER_GPU_DB_KEY in value and NODE_MEMORY_LIMIT_PER_GPU_DB_KEY in value:
            if key == NODE_LIMIT_ALL_KEY:
                node_gpu_all = value
            else:
                node_name_gpu[key] = value



    return {
        "node_name_cpu": node_name_cpu,
        "node_name_cpu_all": node_cpu_all,
        "node_name_gpu": node_name_gpu,
        "node_name_gpu_all": node_gpu_all
    }

def combine_node_name(node_name_cpu, node_name_gpu, node_name=None):
    if node_name_cpu is None:
        node_name_cpu = {}

    if node_name_gpu is None:
        node_name_gpu = {}

    if node_name is None:
        node_name = {}

    for key, value in node_name_cpu.items():
        if node_name.get(key) is None:
            node_name[key] = value
        else:
            node_name[key].update(value)

    for key, value in node_name_gpu.items():
        if node_name.get(key) is None:
            node_name[key] = value
        else:
            node_name[key].update(value)

    return node_name


PROTOCOL_IPV4 = "ipv4"
PROTOCOL_IPV6 = "ipv6"

def get_worker_ip_check_by_interface(node_ip: dict, interface: str, headers: dict = {}) -> str:
    """
    Description: 해당 node의 network interface가 가지거 있는 ip 가져오기

    Args:
        node_ip (dict):
        interface (str):
        headers (_type_):

    Returns:
        str: ip
    """

    result = get_worker_requests(ip=node_ip, path="ip-check?interface={}".format(interface), headers=headers)
    if result["get_status"]:
        res_data = json.loads(result["result"].text)
        if res_data["status"] == 1:
            return res_data["result"]
    return ""


def get_worker_ping_check_by_interface(client_ip: str, server_interface_ip: str, interface : str, headers:dict={}) -> bool:
    """
    Description: interface에 해당하는 다른 node의 대역폭 check

    Args:
        client_ip (str): interface 대역폭을 확인하는 client node
        server_ip (str): 같은 대역폭인지 확인하려는 server node의 interface ip
        interface (str): client node의 interface
        headers (_type_):

    Returns:
        bool: 같은 대역폭이면 true
    """
    params = {
        "node_ip" : server_interface_ip,
        "interface" : interface
    }
    result = get_worker_requests(ip=client_ip, path="node-ping-check", timeout=0.2, headers=headers, params=params)
    if result["get_status"]:
        res_data = json.loads(result["result"].text)
        if res_data["status"] == 1:
            return res_data["result"]
    return False


def get_worker_ubuntu_package_check(node_ip : str, package_name : str) -> int:
    """
    Description: 해당 node의 ubuntu 패키지 check(없으면 download)

    Args:
        node_ip (str): check해볼 node의 ip

    Returns:
        int: 성공하면 0, 실패하면 1이상의 값
    """
    result = get_worker_requests(ip=node_ip, path="ubuntu-package-download?package_name={}".format(package_name), timeout=30)
    if result["get_status"]:
        res_data = json.loads(result["result"].text)
        if res_data["status"] == 1:
            return res_data["result"]
    return 1

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

def get_optimal_gpus(data, num_gpus):
    nodes = defaultdict(list)
    for item in data:
        nodes[item["node_name"]].append(item["gpu_uuid"])

    # 노드를 내림차순으로 정렬하는 GPU 수를 기준으로 노드 정렬
    sorted_nodes = sorted(nodes.items(), key=lambda x: len(x[1]), reverse=True)

    result = []
    remaining_gpus = num_gpus

    for node, gpus in sorted_nodes:
        if remaining_gpus <= 0:
            break

        # 노드에 요청을 수행할 수 있는 충분한 GPU가 있으면 필요한 것만 가져갑니다
        if len(gpus) >= remaining_gpus:
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus[:remaining_gpus]])
            remaining_gpus = 0
        else:
            # 그렇지 않으면 이 노드에서 모든 GPU를 가져가고 다음 노드로 계속 이동합니다
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus])
            remaining_gpus -= len(gpus)

    return result


def gpu_clustering(gpus : List[dict]):
    """
    요청된 node 별 gpu 개수에 따라 최대공약수로 pod 별 할당 gpu 계산
    """
    # 노드를 기준으로 데이터를 그룹화
    grouped_data = defaultdict(list)
    for item in gpus:
        grouped_data[item["node_name"]].append(item["gpu_uuid"])

    # 노드별 GPU UUID 개수를 셈
    node_counts = {node: len(uuids) for node, uuids in grouped_data.items()}

    # 최대 공약수를 계산하는 함수
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    # 여러 숫자의 최대 공약수를 계산하는 함수
    def gcd_multiple(numbers):
        return reduce(gcd, numbers)

    # 노드별 GPU UUID 개수 리스트
    counts = list(node_counts.values())

    # 최대 공약수 계산
    max_gcd = gcd_multiple(counts)

    # 최대 공약수에 맞춰 GPU UUID를 분리
    result = []
    for node, uuids in grouped_data.items():
        chunks = [uuids[i:i + max_gcd] for i in range(0, len(uuids), max_gcd)]
        for chunk in chunks:
            result.append({"node_name": node, "gpu_uuids": chunk})
    return result

def list_files_in_directory(directory_path):
    """
    Given a directory path, this function returns a list of all the files in the directory.
    :param directory_path: The path to the directory
    :return: A list of file names in the directory
    """
    try:
        # List all files and directories in the specified path
        file_list = []
        with os.scandir(directory_path) as entries:
            for entry in entries:
                if entry.is_file():
                    file_list.append(entry.name)
        return file_list
    except FileNotFoundError:
        print(f"The directory {directory_path} does not exist.")
        return []
    except PermissionError:
        print(f"Permission denied to access the directory {directory_path}.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def get_gpu_auto_select(redis_client, gpu_count : int, pod_count : int, instance_id : int):
    data = get_gpu_cluster_info_sync(instance_id=instance_id, redis_client=redis_client)
    # print(data, file=sys.stderr)
    # 결과를 저장할 리스트
    result = []

    # 가능한 GPU 목록을 만들기
    available_gpus = {}
    for node, gpus in data.items():
        available_gpus[node] = [gpu for gpu in gpus if gpu["used"]==0]

    # 필요한 GPU의 총 수
    total_required_gpus = pod_count * gpu_count

    # 사용할 수 있는 GPU가 충분한지 확인
    allocated_gpus = 0
    for node, gpus in available_gpus.items():
        while len(gpus) >= gpu_count and allocated_gpus < total_required_gpus:
            for i in range(gpu_count):
                result.append({
                    "node_name": node,
                    "gpu_uuid": gpus[i]['gpu_uuid']
                })
            gpus = gpus[gpu_count:]
            allocated_gpus += gpu_count

        if allocated_gpus >= total_required_gpus:
            break

    if allocated_gpus < total_required_gpus:
        raise ValueError("사용 가능한 GPU가 충분하지 않습니다.")

    return result

def get_gpu_auto_select_new(gpu_count: int, pod_count: int, gpu_data: list):
    # 결과를 저장할 리스트
    result = []

    # GPU를 노드 이름별로 그룹화
    available_gpus = {}
    for gpu_info in gpu_data:
        node_name = gpu_info['node_name']
        gpu_uuid = gpu_info['gpu_uuid']
        if node_name not in available_gpus:
            available_gpus[node_name] = []
        available_gpus[node_name].append(gpu_uuid)

    # 필요한 GPU의 총 수
    total_required_gpus = pod_count * gpu_count

    # 사용할 수 있는 GPU를 할당
    allocated_gpus = 0
    for node_name, gpus in available_gpus.items():
        if len(gpus) < gpu_count: # 해당 노드에 pod에 같이 할당 할 수 있는 gpu 개수가 부족할 경우 pass
            continue
        while allocated_gpus < total_required_gpus and gpus:
            for _ in range(gpu_count):
                if gpus and allocated_gpus < total_required_gpus:
                    result.append({'node_name': node_name, 'gpu_uuid': gpus.pop(0)})
                    allocated_gpus += 1

        # 필요한 GPU의 수에 도달하면 루프 종료
        if allocated_gpus >= total_required_gpus:
            break

    # 필요한 GPU가 충분하지 않은 경우 예외 발생
    if allocated_gpus < total_required_gpus:
        return []

    return result


def get_ttl_hash(seconds=3600):
    """Calculate hash value for TTL caching.
    Args:        seconds (int, optional): Expiration time in seconds. Defaults to 3600.
    Returns:
        int: Hash value.
    """
    utime = datetime.now().timestamp()
    return round(utime / (seconds + 1))

def ttl_cache(ttl_seconds=3600, use_cache=True):

    """A decorator for TTL cache functionality.

    Adds `use_cache` argument to functions, enabling toggle of caching.

    Args:
        ttl_seconds (int, optional): Expiration time in seconds. Defaults to 3600.

        use_cache (bool, optional): Whether caching is enabled by default. Defaults to True.

    """
    def ttl_cache_deco(func):
        """Accepts a function and returns a version of it with TTL cache functionality."""
        # Create a function with cache functionality and add dummy argument
        @lru_cache(maxsize=None)
        def cached_dummy_func(*args, ttl_dummy, **kwargs):
            del ttl_dummy
            return func(*args, **kwargs)

        # Create a function that automatically calculates hash value and inputs it to the dummy argument
        @wraps(func)

        def ttl_cached_func(*args, use_cache=use_cache, **kwargs):

            if not use_cache:

                ttl_cached_func.cache_offset += 1

            hash = get_ttl_hash(ttl_seconds) + ttl_cached_func.cache_offset

            return cached_dummy_func(*args, ttl_dummy=hash, **kwargs)


        ttl_cached_func.cache_offset = 0


        return ttl_cached_func
    return ttl_cache_deco


# async def post_request(url, data):
#     async with aiohttp.ClientSession() as session:
#         async with session.post(url, json=data) as response:
#             # 응답을 JSON으로 파싱합니다.
#             response_data = await response.json()
#             # print(response_data)
#             return response_data

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