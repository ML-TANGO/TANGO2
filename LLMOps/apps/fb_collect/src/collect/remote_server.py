import sys
from scp import SCPClient
import paramiko
import os
from pathlib import Path
import traceback
import time
import subprocess
import json
from datetime import datetime
import pytz
import pymysql
from pymysql.cursors import DictCursor

# 환경 변수 설정
COLLECT_ID=os.getenv("COLLECT_ID",None)
DATA_PATH = os.getenv("DATA_PATH", None)
LIMIT_SIZE = int(os.getenv("LIMIT_SIZE", 0))
NAMESPACE = os.getenv("NAMESPACE",None)
HELM_NAME = os.getenv("HELM_NAME",None)
COLLECT_CYCLE=int(os.getenv("COLLECT_CYCLE",60))

# 데이터베이스 설정
DB_HOST = os.getenv("JF_DB_HOST", None)
DB_PORT = int(os.getenv("JF_DB_PORT", 0))
DB_USER = os.getenv("JF_DB_USER", "root")
DB_PW = os.getenv("JF_DB_PW", None)
DB_NAME = os.getenv("JF_DB_NAME", "msa_jfb")
DB_CHARSET = os.getenv("JF_DB_CHARSET", "utf8")

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PW,
        db=DB_NAME,
        charset=DB_CHARSET,
        cursorclass=DictCursor
    )

def get_collect_info(collect_id=None, name=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT c.*
                    FROM collect c
                    LEFT JOIN instance i ON c.instance_id = i.id
                    """
                if collect_id is not None:
                    sql += "WHERE c.id = %s"
                    cur.execute(sql, (collect_id,))
                    return cur.fetchone()
                if name is not None:
                    sql += "WHERE c.name = %s"
                    cur.execute(sql, (name,))
                    return cur.fetchone()
    except Exception as e:
        print(f"Error in get_collect_info: {e}")
        return None

def insert_history(collect_id, collect_info, status, status_message=None, path=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO collect_history
                    (collect_id, collect_information, status, status_message, path)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(sql, (collect_id, collect_info, status, status_message, path))
                conn.commit()
                return cur.lastrowid
    except Exception as e:
        print(f"Error in insert_history: {e}")
        return None

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
data_path = Path("/jf-data")

def disk_usage(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    print(result)
    try:
        return int(result.split('\t')[0])
    except ValueError:
        return 0

def download_file(target_path : Path, destination_path : Path):
    global ssh
    with SCPClient(ssh.get_transport()) as scp:
        if not destination_path.exists():
            destination_path.mkdir(parents=True, exist_ok=True)
        scp.get(target_path, destination_path, recursive=True)

if __name__ == "__main__":
    while(True):
        if COLLECT_ID:
            collect_info=get_collect_info(collect_id=COLLECT_ID)
            while(True):
                relative_path = Path(DATA_PATH)
                server_time = datetime.now()
                local_timezone = pytz.timezone("Asia/Seoul")
                current_time = server_time.astimezone(local_timezone)
                current_time = current_time.strftime("%Y-%m-%d_%H:%M:%S")
                # SSH 연결 설정
                collect_info['collect_information_list'] = json.loads(collect_info['collect_information_list'])
                
                for collect in collect_info['collect_information_list']:
                    ssh.connect(collect['ip'], username=collect['user'], password=collect['passwd'])

                    _, stdout, _ = ssh.exec_command(f"ls -d {collect['path']}")
                    data_list = [line.strip() for line in stdout.readlines()]
                    if data_list:
                        try:
                            for data in data_list:
                                target_path = Path(collect['path']).joinpath(data)
                                destination_path=Path(f"{data_path.joinpath(relative_path)}/{current_time}/")
                                
                                download_file(target_path,destination_path)
                                insert_history(collect_id=COLLECT_ID,
                                    collect_info=json.dumps(collect),
                                    status=200,
                                    path=f"{relative_path}/{current_time}"
                                )
                                
                                result={
                                    "collect_id" : COLLECT_ID,
                                    "collect_info" : collect,
                                    "status" : 200,
                                    "relative_path" : f"{relative_path}/{current_time}"
                                }
                                print(f"[collect/remoteServer] {json.dumps(result)}", file=sys.stdout)

                        except:
                            insert_history(collect_id=COLLECT_ID,
                                    collect_info=json.dumps(collect),
                                    status=500,
                                    status_message=f"SCP Connection error")
                    else:
                        insert_history(collect_id=COLLECT_ID,
                                    collect_info=json.dumps(collect),
                                    status=404,
                                    status_message=f"Not found {target_path}")
                
                ssh.close()

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
                        insert_history(collect_id=COLLECT_ID,
                                            collect_info=json.dumps({}),
                                            status=0,
                                            status_message="Storage Usage Exceeded",
                                            path=None)
                        

                time.sleep(COLLECT_CYCLE)