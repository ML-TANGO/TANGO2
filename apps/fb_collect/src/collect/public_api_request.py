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

sys.path.append("/")
import utils.msa_db.db_collect as collect_db
import utils.msa_db.db_collect_history as history_db


COLLECT_CYCLE=int(os.getenv("COLLECT_CYCLE",60)) # (cycle * cycle unit) convert to second
COLLECT_ID=os.getenv("COLLECT_ID",None)

DATA_PATH = os.getenv("DATA_PATH", None)
LIMIT_SIZE = int(os.getenv("LIMIT_SIZE", 0))
NAMESPACE = os.getenv("NAMESPACE",None)
HELM_NAME = os.getenv("HELM_NAME",None)

def get_collect_info_list():
    file_path = "/collect_config/json-data"
    with open(file_path, "r") as file:
        base64_data = file.read().strip()  # ............ Base64 ............ ......... ......

    # Base64 .........
    decoded_data = base64.b64decode(base64_data).decode("utf-8")  # UTF-8... .........

    # JSON ......
    json_data = json.loads(decoded_data)
    return json_data

COLLECT_INFO = get_collect_info_list() #@os.getenv("COLLECT_INFO",None)



def send_request(
    api_url: str,
    method: str,
    data_type: str = "json",
    params: Dict[str, Union[str, int]] = None,
    data: Dict[str, Union[str, int]] = None
):
    """
    Sends an API request with the specified parameters.

    :param api_url: API endpoint URL
    :param api_key: API key for authentication
    :param method: HTTP method (GET or POST)
    :param data_type: 'json' or 'form' for POST requests
    :param params: Parameters for GET requests
    :param data: Data for POST requests (JSON or form-data)
    :return: Response object
    """
    # headers = {
    #     "Authorization": f"Bearer {api_key}",
    #     "Content-Type": "application/json" if data_type == "json" else "application/x-www-form-urlencoded",
    # }

    try:
        if method.upper() == "GET":
            response = requests.get(api_url, params=params) # headers=headers, 
        elif method.upper() == "POST":
            if data_type == "json":
                response = requests.post(api_url, json=data) # headers=headers, 
            elif data_type == "form":
                response = requests.post(api_url, data=data) # headers=headers, 
            else:
                raise ValueError("Invalid data_type. Must be 'json' or 'form'.")
        else:
            raise ValueError("Invalid method. Must be 'GET' or 'POST'.")

        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    
def disk_usage(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    try:
        return int(result.split('\t')[0])
    except ValueError:
        return 0

# Example usage
if __name__ == "__main__":
    if COLLECT_ID:
        data_path = Path("/jf-data").joinpath(DATA_PATH)
        collect_info=collect_db.get_collect_info(collect_id=COLLECT_ID)
        while(True):
            relative_path = Path(DATA_PATH)
            server_time = datetime.now()
            local_timezone = pytz.timezone("Asia/Seoul")
            current_time = server_time.astimezone(local_timezone)
            current_time = current_time.strftime("%Y-%m-%d_%H:%M:%S")
            for collect in json.loads(collect_info['collect_information_list']):
                # collect_info = db_collect_info.get_info(id=collect_info_id)
                # if db_collect_info is None:
                #     continue
                message = ""
                status_code=0
                if collect['method'].upper() == "GET":
                    res = send_request(
                        api_url=collect["url"],
                        method="GET",
                        params=collect["jsonData"]
                    )
                else:
                    res = send_request(
                        api_url=collect["url"],
                        method="POST",
                        data_type = collect["data_type"],
                        data=json.loads(collect["jsonData"])
                    )
                if res:
                    if res.status_code == 200:
                        if collect.get('return_type',None):
                            file_name = f"{collect['name']}_{current_time}.{collect['return_type']}"
                        else:
                            file_name = f"{collect['name']}_{current_time}"
                        with open(data_path.joinpath(file_name), "wb+") as file:
                            file.write(res.content)
                        status_code=res.status_code
                        history_db.insert_history(collect_id=COLLECT_ID,
                                          collect_info=json.dumps(collect),
                                          status=status_code,
                                          path=str(relative_path.joinpath(file_name)))
                    else:
                        message=res.text
                        status_code=res.status_code
                        history_db.insert_history(collect_id=COLLECT_ID,
                                          collect_info=json.dumps(collect),
                                          status=status_code,
                                          status_message=message,
                                          path=None)

                result={
                        "collect_id" : COLLECT_ID,
                        "collect_info" : collect,
                        "status" : status_code,
                        "status_message" : message,
                        "relative_path" : str(relative_path.joinpath(file_name))
                    }
                print(f"[collect/publicApi] {json.dumps(result)}", file=sys.stdout)
                

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
        