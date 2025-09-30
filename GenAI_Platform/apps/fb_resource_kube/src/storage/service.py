
from utils.resource import CustomResource, response, token_checker
# import utils.db as db
from utils.resource import response
from utils.PATH import JF_WS_DIR
# from utils.lock import jf_scheduler_lock
from utils.TYPE import *
import traceback
import json
import os
import subprocess

"""

    return example

    {
    "result": {
        "list": [
            {
                "id": 1,
                "physical_name": "/jfbcore",
                "logical_name": "MAIN_STORAGE",
                "size": 1967316500480,
                "fstype": "overlay",
                "description": "A",
                "active": 0,
                "create_lock": 0,
                "share": 1,
                "create_datetime": "2023-01-10 06:39:19",
                "usage": {
                    "device": "/dev/sdc2",
                    "fstype": "ext4",
                    "size": 1967316500480,
                    "used": 1544403525632,
                    "avail": 322903203840,
                    "pcent": "83%"
                },
                "workspaces": [
                    {
                        "workspace_name": "eddy-ws",
                        "workspace_used": "364879133344",
                        "workspace_avail": 322903171072,
                        "workspace_pcent": "83%",
                        "recent_sync_time": "2023-10-26 00:41:46"
                    }
                ]
            },
            {
                "id": 2,
                "physical_name": "sdb1",
                "logical_name": "sdb1",
                "size": 3936818806784,
                "fstype": "ext4",
                "description": "A",
                "active": 0,
                "create_lock": 1,
                "share": 1,
                "create_datetime": "2023-01-10 09:07:53",
                "usage": {
                    "device": "/dev/sdb1",
                    "fstype": "ext4",
                    "size": 3936818806784,
                    "used": 23448604672,
                    "avail": 3713314172928,
                    "pcent": "1%"
                },
                "workspaces": []
            },
        ],
        "total": {
            "total_size": 9840954114048,
            "total_used": 2138992750592,
            "total_pcent": "21%"
        }
    },
    "message": null,
    "status": 1
}

{
    "result": {
        "id": 1,
        "physical_name": "/jfbcore",
        "logical_name": "MAIN_STORAGE",
        "size": 1967316500480,
        "fstype": "overlay",
        "description": "A",
        "active": 0,
        "create_lock": 0,
        "share": 1,
        "create_datetime": "2023-01-10 06:39:19",
        "used": 1544406188032,
        "workspace": {
            "workspace_name": "iitp-test",
            "workspace_used": "24509989273",
            "workspace_avail": 322900541440,
            "workspace_pcent": "83%",
            "recent_sync_time": "2023-10-26 02:21:42"
        }
    },
    "message": null,
    "status": 1
}
"""

WORKSPACE_NAME="workspace_name"
WORKSPACE_SIZE="workspace_size"
WORKSPACE_USED="workspace_used"
WORKSPACE_AVAIL="workspace_avail"
WORKSPACE_PCENT="workspace_pcent"
ALLOCATION_PCENT="allocation_pcent"
RECENT_SYNC_TIME="recent_sync_time"

MAIN_STORAGE_ID = 1
MAIN_STORAGE = "MAIN_STORAGE"



storage={
            "id": 1,
            "physical_name": "/data",
            "logical_name": "MAIN_STORAGE",
            "size": 0, #byte int
            "fstype": "overlay",
            "description": "",
            "active": 0,
            "create_lock": 0,
            "share": 1
        }

def get_device_info(path="/data"):
    disk_info = list(filter(None, subprocess.run(["df -T --block-size=1 {}".format(path)],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8').stdout.split('\n')[1].split(' ')))

    return {
            "device" : disk_info[0],
            "fstype" : disk_info[1],
            "size" : int(disk_info[2]),
            "used" : int(disk_info[3]),
            "avail" : int(disk_info[4]),
            "pcent" : disk_info[5]
        }

def get_workspace_usage_list():
    try:
        global storage
        workspaces=[]

        ws_list = db.get_workspace_list()
        device_info = get_device_info()
        storage['size'] = device_info['size']
        storage['usage'] = device_info
        for ws in ws_list:
            ws_usage = int(subprocess.run(["du -b -s {} ".format(os.path.join(JF_WS_DIR,ws['workspace_name']))],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8').stdout.split('\t')[0])
            workspaces.appen(
                {
                    WORKSPACE_NAME : ws['workspace_name'],
                    WORKSPACE_USED : str(ws_usage),
                    WORKSPACE_AVAIL : device_info['avail'],
                    WORKSPACE_PCENT : str(int((ws_usage/device_info['size'])*100))+"%",
                    RECENT_SYNC_TIME : None
                }
            )
        storage['workspaces']= workspaces

        return response(status=1, result={"list":storage})
    except:
        traceback.print_exc()
        return response(status=0, result={})

#사용자 page 스토리지 사용량 표시
def get_workspace_usage(workspace_id):
    workspace_info = db.get_workspace(workspace_id=workspace_id)
    workspace_usage=subprocess.run(["du -b -s {} ".format(os.path.join(JF_WS_DIR,workspace_info['workspace_name']))],stdout= subprocess.PIPE,shell=True,encoding = 'utf-8').stdout.split('\t')[0]
    device_info = get_device_info()
    return response(status=1,
                    result={
                        "id": 1,
                        "physical_name": "/data",
                        "logical_name": "MAIN_STORAGE",
                        "size": device_info['size'],
                        "fstype": "overlay",
                        "description": "",
                        "active": 0,
                        "create_lock": 0,
                        "share": 1,
                        "create_datetime": "2023-01-10 06:39:19",
                        "used": device_info['used'],
                        "workspace": {
                            "workspace_name": workspace_info['workspace_name'],
                            "workspace_used": workspace_usage,
                            "workspace_avail": device_info['avail'],
                            "workspace_pcent": str(int((device_info['used']/device_info['size'])*100))+"%",
                            "recent_sync_time": "2023-10-26 02:21:42"
                        }
                    }
                )