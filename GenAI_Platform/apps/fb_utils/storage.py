# from queue import Queue
# from .common import launch_on_host
# from utils.settings import CPU_POD_RUN_ON_ONLY_CPU_NODES, CPU_NODES, NO_USE_NODES, JF_WORKER_PORT, \
#     NODE_DB_IP_AUTO_CHAGE_TO_KUBER_INTERNAL_IP, FILESYSTEM_OPTION
# import subprocess
# import json
# import re
# import os
# from pprint import pprint

# divide_by = float(1 << 30)
# workspace_storage_type = -1

# WORKSPACE_NAME="workspace_name"
# WORKSPACE_SIZE="workspace_size"
# WORKSPACE_USED="workspace_used"
# WORKSPACE_AVAIL="workspace_avail"
# WORKSPACE_PCENT="workspace_pcent"
# ALLOCATION_PCENT="allocation_pcent"
# RECENT_SYNC_TIME="recent_sync_time"

# MAIN_STORAGE_ID = 1
# MAIN_STORAGE = "MAIN_STORAGE"



# # For debugging

# import sys

# class debug_context():
#     """ Debug context to trace any function calls inside the context """

#     def __init__(self, name):
#         self.name = name

#     def __enter__(self):
#         print('Entering Debug Decorated func')
#         # Set the trace function to the trace_calls function
#         # So all events are now traced
#         sys.settrace(self.trace_calls)

#     def __exit__(self, *args, **kwargs):
#         # Stop tracing all events
#         sys.settrace = None

#     def trace_calls(self, frame, event, arg):
#         # We want to only trace our call to the decorated function
#         if event != 'call':
#             return
#         elif frame.f_code.co_name != self.name:
#             return
#         # return the trace function to use when you go into that
#         # function call
#         return self.trace_lines

#     def trace_lines(self, frame, event, arg):
#         # If you want to print local variables each line
#         # keep the check for the event 'line'
#         # If you want to print local variables only on return
#         # check only for the 'return' event
#         if event not in ['line', 'return']:
#             return
#         co = frame.f_code
#         func_name = co.co_name
#         line_no = frame.f_lineno
#         filename = co.co_filename
#         local_vars = frame.f_locals
#         print ('  {0} {1} {2} locals: {3}'.format(func_name,
#                                                   event,
#                                                   line_no,
#                                                   local_vars))


# def debug_decorator(func):
#     """ Debug decorator to call the function within the debug context """
#     def decorated_func(*args, **kwargs):
#         with debug_context(func.__name__):
#             return_value = func(*args, **kwargs)
#         return return_value
#     return decorated_func




# def init_storage_type():
#     global workspace_storage_type
#     FS_OPT = -1
#     if FILESYSTEM_OPTION == "MFS":
#         FS_OPT = 1
#     elif FILESYSTEM_OPTION == "Local":
#         FS_OPT = 2
#     elif FILESYSTEM_OPTION == "NFS":
#         FS_OPT = 3
#     print("Initial FILESYSTEM_OPTION: " + str(FS_OPT))
#     if FS_OPT != -1:
#         workspace_storage_type = FS_OPT
#     else:  # MFS or NFS
#         try:
#             ws_mnt_stat = json.loads(launch_on_host("mfs_util get_workspace_mnt_stat")[0])[0]
#             total = float(''.join(filter(str.isdigit, (re.sub('[^\d|\.]', '', ws_mnt_stat[1])))))
#             if total != 0:
#                 if "mfsmaster" in ws_mnt_stat[0]:  # MFS
#                     workspace_storage_type = 1
#                 else:
#                     workspace_storage_type = 3  # NFS
#             else:
#                 workspace_storage_type = 2
#         except Exception as e:  # Local
#             workspace_storage_type = 2
#     print("New FILESYSTEM_OPTION: " + str(workspace_storage_type))


# """workspace에 storage quota를 설정함

# :param workspace_name workspace 이름
# :param quota: quota 설정값(6GB라면 6을 입력)
# :param unit: quota 설정값의 단위(6GB라면 G를 입력)
# :returns: 설정된 quota의 용량
# """


# def set_workspace_quota(workspace_name, quota, unit):
#     quota = int(quota) * 1.074
#     result, error = launch_on_host("mfssetquota -S " + str(
#         quota) + unit + " /jfbcore/jf-data/workspaces/" + workspace_name + """ | grep "size" | grep -v "real""")
#     return result


# """총 스토리지 용량을 불러옴

# :returns: 노드를 모두 포함한 총 스토리지 용량(GB 기준, iec)
# """


# def get_total_disk_size():
#     print("Test")
#     result, error = launch_on_host("""mfscli -H mfsmaster -SIN """)
#     returned_size = 0
#     for line in result.splitlines():
#         if re.search(r'total', line):
#             returned_size = float(line.split()[4])
#     converted = returned_size / 1073741824
#     return converted


# """총 사용 가능한 용량을 불러옴

# :returns: 노드를 모두 포함한 총 사용 가능한 스토리지 용량(GB 기준, iec)
# """


# def get_free_disk_size():
#     # todo
#     result, error = launch_on_host("""mfscli -H mfsmaster -SIN """)
#     returned_size = 0
#     for line in result.splitlines():
#         if re.search(r'free', line):
#             returned_size = float(line.split()[4])
#             print(returned_size)
#     converted = returned_size / 1073741824
#     return converted


# """총 사용된 스토리지 용량을 불러옴

# :returns: 노드를 모두 포함한 총 사용된 스토리지 용량(GB 기준, iec)
# """


# def get_used_disk_size():
#     # todo
#     free = get_free_disk_size()
#     total = get_total_disk_size()
#     return round(total - free, 2)


# def get_total_storage_usage():
#     try:
#         json_res = launch_on_host("mfs_util list_chunk")[0]
#         res = json.loads(json_res)
#         result = {}
#         for key, value in res.items():
#             result["all"] = {
#                 "total": round((value[1] / divide_by), 2),
#                 "used": round((value[0] / divide_by), 2),
#             }
#             if (key == "total"):
#                 break
#         print(result)
#         return result
#     except:
#         result = {}
#         result["all"] = {
#             "total": float(0),
#             "used": float(0)
#         }
#         return result


# """workspace에 설정된 quota 정보를 불러옴

# :param workspace_name workspace 이름
# :returns: 설정된 quota의 용량('hard_limit')과 현재 사용 용량('size') 같은 정보가 담긴 dictionary object
# """


# def get_workspace_quota(workspace_name):
#     result, error = launch_on_host("mfsgetquota -h /jfbcore/jf-data/workspaces/" + workspace_name)
#     dictToReturn = dict()
#     for line in result.splitlines()[1:]:
#         splitLine = line.replace(" ", '').split('|')
#         if splitLine[0] != 'size':
#             dictToReturn[splitLine[0]] = splitLine[1]
#         else:
#             dictToReturn[splitLine[0]] = splitLine[1]
#             dictToReturn['soft_limit'] = splitLine[2]
#             dictToReturn['hard_limit'] = splitLine[3]
#     return dictToReturn


# def get_usage_per_workspace(ws_input='ALL'):
#     from glob import glob
#     from pathlib import Path
#     things_to_check = ['trainings', 'deployments', 'datasets']

#     def process_subfolder(ws_loc):
#         toReturn = dict()
#         for thing_to_check in things_to_check:
#             toAdd = dict()
#             list_of_folder_to_check = glob(ws_loc + '/' + thing_to_check + '/*', recursive=False)
#             for folder_to_check in list_of_folder_to_check:
#                 if folder_to_check != '':
#                     toAdd[folder_to_check] = sum(file.stat().st_size for file in Path(folder_to_check).rglob('*'))
#             toReturn[thing_to_check] = [
#                 sum(file.stat().st_size for file in Path(ws_loc + '/' + thing_to_check).rglob('*')), toAdd]
#         return toReturn

#     toReturn = dict()
#     if ws_input == 'ALL':
#         list_of_ws = glob("/jfbcore/jf-data/workspaces/*", recursive=False)
#         for ws_loc in list_of_ws:
#             ws_name = ws_loc.split('/')[4]
#             toReturn[ws_name] = [sum(file.stat().st_size for file in Path(ws_loc).rglob('*')),
#                                  process_subfolder(ws_loc)]
#     else:
#         ws_loc = "/jfbcore/jf-data/workspaces/" + ws
#         toReturn[ws_input] = dict()
#         process_subfolder(ws_loc)
#     return toReturn





# ========================================================
# MSA 추가
# ========================================================
import traceback
# import utils.db as db
from utils.PATH import JF_STORAGE_MOUNTPOINT_PATH
from utils.common import AllPathInfo
def get_storage_info(storage_info):
    try:
        if storage_info['physical_name'] == '/jfbcore':
            storage_path = storage_info['physical_name']
        else : #MountPoint로 디스크 사용량 검색
            storage_path = JF_STORAGE_MOUNTPOINT_PATH.format(device_name = storage_info['physical_name'])
        return AllPathInfo(storage_path).get_device_info()
    except:
        traceback.print_exc()
        # return response(status = 0, result = None)
        return None


def get_storage_list():
    try:
        storage_list = db.get_storage_list()
        for storage in storage_list :
            storage['usage'] = get_storage_info(storage)  # (23.10.16) usage 부분 값이 None
            print("=============================")
            print(f"storage: {storage}")
            print(f"storage['usage']: {storage['usage']}")
            print("=============================")
            if storage['share'] == 0 :
                storage['usage']['allocate_used'] = db.get_storage_allocation_size(storage_id = storage['id'])['allocate_size']
                if storage['usage']['allocate_used'] is None :
                    storage['usage']['allocate_pcent'] = "0%"
                    storage['usage']['allocate_used'] = 0
                else :
                    allocation_pcent = (storage['usage']['allocate_used']/storage['size'])*100
                    storage['usage']['allocate_pcent'] = "{}%".format(1 if allocation_pcent < 1 else allocation_pcent)

        return storage_list
    except:
        traceback.print_exc()
        # return response(status = 0, result = None)
        return None