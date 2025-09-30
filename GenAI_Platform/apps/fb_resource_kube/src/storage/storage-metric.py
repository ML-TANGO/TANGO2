import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import subprocess
import time
from prometheus_client  import start_http_server, Gauge, Info
import threading
import grpc
import traceback
from storage_grpc import storage_pb2
from storage_grpc import storage_pb2_grpc
from utils.msa_db import db_workspace as ws_db
from utils.msa_db import db_storage as storage_db
from utils.msa_db import db_dataset as dataset_db
from utils.msa_db import db_project as project_db
from pathlib import Path

labels=['name','storage_type']
WORKSPACE_USAGE = Gauge('workspace_usage_bytes', 'Workspace used storage in bytes', ['name','type','storage'])
DATASET_USAGE = Gauge('dataset_usage_bytes', 'Dataset used storage in bytes',['name','workspace','storage','type'])
PROJECT_USAGE= Gauge('project_usage_bytes', 'Porject used storage in bytes',['name','workspace','storage','type'])

MAIN_STORAGE_PATH = "/jf-data/main/{WORKSPACE_NAME}"
PROJECT_PATH = MAIN_STORAGE_PATH+"/projects/{PROJECT_NAME}"
DATA_STORAGE_PATH = "/jf-data/data/{WORKSPACE_NAME}"
DATASET_PATH = DATA_STORAGE_PATH+"/{ACCESS}/{DATASET_NAME}"
# storage_list = os.listdir('/jf-data')
result = []
storage_id=os.getenv("STORAGE_ID")

def set_data_storage_usage(ws_info):
    try:
        data_storage_info = storage_db.get_storage(storage_id=ws_info['data_storage_id'])
        dataset_list = dataset_db.get_dataset_list(workspace_id=ws_info['id'])

        ws_data_path = DATA_STORAGE_PATH.format(WORKSPACE_NAME=ws_info['name'])
        ws_data_usage = get_disk_usage(ip=data_storage_info['ip'], path=ws_data_path)
        try:
            if ws_data_usage is None:
                WORKSPACE_USAGE.labels(name=ws_info['name'], type='data', storage=data_storage_info['name']).set(0)
            else:
                WORKSPACE_USAGE.labels(name=ws_info['name'], type='data', storage=data_storage_info['name']).set(ws_data_usage)
        except:
            print(ws_info['name'])
            print(ws_data_usage)

        for dataset in dataset_list:
            # print(dataset)
            dataset_path = DATASET_PATH.format(WORKSPACE_NAME=ws_info['name'], ACCESS=dataset['access'], DATASET_NAME=dataset['dataset_name'])
            dataset_usage = get_disk_usage(ip=data_storage_info['ip'], path=dataset_path)
            try:
                if dataset_usage is None:
                    DATASET_USAGE.labels(name=dataset['dataset_name'], type='data', workspace=ws_info['name'], storage=data_storage_info['name']).set(0)
                else:
                    DATASET_USAGE.labels(name=dataset['dataset_name'], type='data', workspace=ws_info['name'], storage=data_storage_info['name']).set(dataset_usage)
            except:
                print(dataset['dataset_name'])
                print(dataset_usage)
    except Exception as e:
        traceback.print_exc()

def set_main_storage_usage(ws_info):
    main_storage_info = storage_db.get_storage(storage_id=ws_info['main_storage_id'])
    project_list = project_db.get_project_list(workspace_id=ws_info['id'])

    ws_main_path = MAIN_STORAGE_PATH.format(MOUNTPOINT=main_storage_info['mountpoint'],WORKSPACE_NAME=ws_info['name'])
    ws_main_usage = get_disk_usage(ip=main_storage_info['ip'], path=ws_main_path)
    try:
        if ws_main_usage is None:
            WORKSPACE_USAGE.labels(name=ws_info['name'], type='main', storage=main_storage_info['name']).set(0)
        else:
            WORKSPACE_USAGE.labels(name=ws_info['name'], type='main', storage=main_storage_info['name']).set(ws_main_usage)
    except:
        print(ws_info['name'])
        print(ws_main_usage)
    for project in project_list:
        project_path = PROJECT_PATH.format(MOUNTPOINT=main_storage_info['mountpoint'],WORKSPACE_NAME=ws_info['name'], PROJECT_NAME=project['name'])
        project_usage = get_disk_usage(ip=main_storage_info['ip'], path=project_path)
        try:
            if project_usage is None:
                PROJECT_USAGE.labels(name=project['name'], type='main', workspace=ws_info['name'], storage=main_storage_info['name']).set(0)
            else:
                PROJECT_USAGE.labels(name=project['name'], type='main', workspace=ws_info['name'], storage=main_storage_info['name']).set(project_usage)
        except:
            print(project['name'])
            print(project_usage)



def get_disk_usage(ip, path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    return result.split('\t')[0]
    # for res in result.split('\n'):
    #     print(res)
    #     if res:
    #         usage_info =res.split('\t')
    #         path=usage_info[1]
    # server_address= ip+':50051'
    # # server_address='192.168.1.23:50051'
    # with grpc.insecure_channel(server_address) as channel:
    #     stub = storage_pb2_grpc.StorageServiceStub(channel)
    #     try:
    #         response = stub.GetDiskUsage(storage_pb2.DiskUsageRequest(path=path))  # 10초 타임아웃 설정
    #         return response.usage
    #     except grpc.RpcError as e:
    #         print(f"RPC failed: {e}")
    #         return None
        # response = stub.GetDiskUsage(storage_pb2.DiskUsageRequest(path=path))
        # return response.usage

# def get_size(path, storage, s_type, ws=None):
#     result = subprocess.run(['du', '-b', path, '--max-depth=1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
#     for res in result.split('\n'):
#         if res:
#             usage_info =res.split('\t')
#             path=usage_info[1]
#             size=usage_info[0]
#             if ws is None:
#                 WORKSPACE_USAGE.labels(path=path, type=s_type, storage=storage).set(size)
#             else:
#                 if s_type == 'project':
#                      PROJECT_USAGE.labels(path=path, type=s_type, workspace=ws, storage=storage).set(size)
#                 else:
#                      DATASET_USAGE.labels(path=path, type=s_type, workspace=ws, storage=storage).set(size)


# def main_process_path(main_path,storage):
#     size = get_size(path=main_path, storage=storage, s_type='main') #ws
#     for ws in os.listdir(main_path):
#         if "archived" not in ws:
#             get_size(path=os.path.join(main_path,ws,'projects'), storage=storage, s_type='project', ws=ws)
#     #print(main_path)
#     #print(size)
#     #WORKSPACE_USAGE.labels(name=ws,storage_type='main').set(size)


# def data_process_path(data_path,storage):
#     #print(data_path)
#     get_size(path=data_path, storage=storage, s_type='data')
#     for ws in os.listdir(data_path):
# #       print(os.path.join(data_path,'1',ws))
#         if "archived" not in ws:
#             get_size(path=os.path.join(data_path,ws,'1'), storage=storage, s_type='1', ws=ws)
#             get_size(path=os.path.join(data_path,ws,'0'), storage=storage, s_type='0', ws=ws)

    #print(size)
    #WORKSPACE_USAGE.labels(name=ws,storage_type='data').set(size)

def set_up_metric():
    global storage_id
    ws_list = ws_db.get_workspace_list()
    for ws in ws_list:
        if ws['data_storage_id'] == int(storage_id):
            set_data_storage_usage(ws_info=ws)
        if ws['main_storage_id'] == int(storage_id):
            set_main_storage_usage(ws_info=ws)
        # print(ws)
        # set_storage_usage(ws_info=ws)
    # for storage in storage_list:
    #     main_path = MAIN_STORAGE_PATH.format(STORAGE_NAME=storage)
    #     data_path = DATA_STORAGE_PATH.format(STORAGE_NAME=storage)
    #     main_process_path(main_path,storage)
    #     data_process_path(data_path,storage)
        #for ws in os.listdir(main_path):
        #    if "archived" not in ws:
        #        t=threading.Thread(target=main_process_path,args=(main_path,storage,ws,))
        #        t.daemon=True
        #        t.start()
        #for ws in os.listdir(data_path):
        #    if "archived" not in ws:
        #        t=threading.Thread(target=data_process_path,args=(data_path,storage,ws,))
        #        t.daemon=True
        #        t.start()

#           print(ws)#
#           data_process_path(data_path,storage,ws)



def main():
    start_time = time.time()
    start_http_server(8000)
    while(1):
        time.sleep(5)
        set_up_metric()
    elapsed_time = time.time() - start_time
    print(f"Elapsed time: {elapsed_time:.2f} seconds")

if __name__ == '__main__':
    main()


