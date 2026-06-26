import requests
import os
from typing import Dict, Union
from pathlib import Path
from datetime import datetime
import pytz
import json
import sys
import subprocess
import time
import base64
import json
import shutil
import traceback

sys.path.append("/")
import utils.msa_db.db_collect as collect_db
import utils.msa_db.db_collect_history as history_db
import utils.msa_db.db_deployment as deploy_db

COLLECT_CYCLE=int(os.getenv("COLLECT_CYCLE",60)) # (cycle * cycle unit) convert to second
COLLECT_ID=os.getenv("COLLECT_ID",None)
DEPLOYMENT_ID=int(os.getenv("DEPLOYMENT_ID",0))
DATA_PATH = os.getenv("DATA_PATH", None)
LIMIT_SIZE = int(os.getenv("LIMIT_SIZE", 0))
NAMESPACE = os.getenv("NAMESPACE",None)
HELM_NAME = os.getenv("HELM_NAME",None)

##deployment mount point
##dataset mount point
    
def disk_usage(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    return result.split('\t')[0]

def collect_data(target_path : Path, destination_path : Path):
    try:
        if target_path.exists() and target_path.is_dir():
            input_path=target_path.joinpath('input')
            if input_path.exists():
                for item in input_path.iterdir():  # input 디렉토리 내의 모든 파일/폴더를 순회
                    if item.is_file():  # 파일인 경우
                        input_destination_path=destination_path.joinpath("input/")
                        input_destination_path.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(item), str(input_destination_path))  # 파일 이동
                # shutil.move(str(input_path), str(destination_path))

            output_path=target_path.joinpath("output")
            if output_path.exists():
                for item in output_path.iterdir():  # input 디렉토리 내의 모든 파일/폴더를 순회
                    if item.is_file():  # 파일인 경우
                        output_destination_path=destination_path.joinpath("output/")
                        output_destination_path.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(item), str(output_destination_path))  # 파일 이동
                # shutil.move(str(output_path), str(destination_path))
            return True
    except Exception as e:
        traceback.print_exc()
        raise e
    
# Example usage
if __name__ == "__main__":
    if COLLECT_ID:
        data_path = Path("/jf-data").joinpath(DATA_PATH)
        main_path = Path("/jf-main")
        collect_info=collect_db.get_collect_info(collect_id=COLLECT_ID)
        while(True):
            relative_path = Path(DATA_PATH)
            server_time = datetime.now()
            local_timezone = pytz.timezone("Asia/Seoul")
            current_time = server_time.astimezone(local_timezone)
            current_time = current_time.strftime("%Y-%m-%d_%H:%M:%S")
            for collect in json.loads(collect_info['collect_information_list']):
                # deployment_id
                # deployment Path 
                # if db_collect_info is None:
                #     continue
                message = ""
                status_code=0
                try:
                    if collect_data(target_path=main_path.joinpath(collect['name']), destination_path=data_path.joinpath(current_time)):
                        history_db.insert_history(collect_id=COLLECT_ID,
                                        collect_info=json.dumps(collect),
                                        status=200,
                                        path=str(relative_path.joinpath(current_time)))
                except Exception as e:
                    history_db.insert_history(collect_id=COLLECT_ID,
                                    collect_info=json.dumps(collect),
                                    status=500,
                                    status_message=str(e),
                                    path=None)

                # result={
                #         "collect_id" : COLLECT_ID,
                #         "collect_info" : collect,
                #         "status" : status_code,
                #         "status_message" : message,
                #         "relative_path" : str(relative_path.joinpath(file_name))
                #     }
                # print(f"[collect/publicApi] {json.dumps(result)}", file=sys.stdout)
                

            if LIMIT_SIZE:
                if disk_usage(data_path) >= LIMIT_SIZE:
                    command=f"helm uninstall {HELM_NAME} -n {NAMESPACE}"
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    ) 
                    print(result.stdout)
                    history_db.insert_history(collect_id=COLLECT_ID,
                                          collect_info=json.dumps({}),
                                          status=0,
                                          status_message="Storage Usage Exceeded",
                                          path=None)
                    
            time.sleep(COLLECT_CYCLE)
            # time.sleep(10)
        