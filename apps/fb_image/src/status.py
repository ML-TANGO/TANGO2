import time
import os
import subprocess
import sys
import json
import re
import traceback
import threading
import requests
from utils.msa_db import db_image
from utils import settings, TYPE
from utils import common

from kubernetes import config, client
config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()
batchV1Api = client.BatchV1Api()

IMAGE_STATUS_PENDING = 0
IMAGE_STATUS_INSTALLING = 1
IMAGE_STATUS_READY = 2
IMAGE_STATUS_FAILED = 3
IMAGE_STATUS_DELETING = 4

IMAGE_NAMSPACE = f"{settings.JF_SYSTEM_NAMESPACE}-image"

def status_check():
    while True:
        try:
            image_list = db_image.get_image_list()
            for info in image_list:
                print("-------status-------")
                image_id = info.get("id")
                if info.get("status") == IMAGE_STATUS_INSTALLING:
                    # 설치중일 경우 status 체크
                    try:
                        print("id", image_id)
                        # job check - 이미지 생성 job 상태 확인
                        job_info = batchV1Api.read_namespaced_job(name=f'{TYPE.IMAGE_UPLOAD_INT_TO_TYPE[info.get("type")]}-{str(info.get("id"))}', namespace=IMAGE_NAMSPACE)
                        if job_info.status.succeeded and job_info.status.succeeded >= 1:
                            # job 실행 완료
                            time.sleep(5)
                        
                            # 요청 URL 생성
                            real_name = info.get("real_name")
                            registry = real_name.split('/')[0]
                            tmp_repository = real_name.replace(registry + "/", "").split(":")
                            repository = tmp_repository[0]
                            tag = tmp_repository[1]
                            headers = { "Accept" : "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.index.v1+json"}
                            url = f"{settings.DOCKER_REGISTRY_PROTOCOL}{registry}/v2/{repository}/manifests/{tag}"
                            print(url)
                            # REGISTRY/v2/REPOSITORY/manifest/TAG 요청하여 정상적으로 응답오면 레지스트리에 PUSH 완료
                            response = requests.get(url, headers=headers)
                            print(response)
                            if response.status_code == 200:
                                response_json = response.json()
                                # 이미지 정보 파싱
                                layers = response_json.get('layers', [])
                                image_size = sum(layer['size'] for layer in layers)
                                digest = response.headers.get('Docker-Content-Digest')
                                if digest.startswith("sha256:"):
                                    tmp_iid = digest[7:20] # iid아닌데 iid 값이 의미가 없는 것 같아서 digest 잘라서 넣음 (로컬이면 의미가 있는데,,,)
                                # 이미지 정보 DB 업데이트
                                db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_READY, "size" : image_size, "iid" : tmp_iid, "docker_digest" : digest})            

                                try:
                                    # library pod 실행
                                    helm_image_library(image_id, info.get("real_name"))
                                except Exception as e:
                                    pass
                            else:
                                # 이미지 업로드 실패 
                                db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_FAILED})            
                                
                            try:
                                # helm 삭제
                                subprocess.check_output([f'helm uninstall -n {IMAGE_NAMSPACE} {TYPE.IMAGE_UPLOAD_INT_TO_TYPE[info.get("type")]}-{str(info.get("id"))}'], shell=True, stderr=subprocess.PIPE)
                            except Exception as e:
                                pass
                            
                        elif job_info.status.failed and job_info.status.failed >= 1:
                            # 이미지 업로드 실패 
                            db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_FAILED})            
       
                    except client.rest.ApiException as e:
                        # job이 없는 경우 # 설치 전이라 안뜬 경우도 있음
                        print("not exist job", image_id)
                        # print("-----fail-----")
                        # print(f'{TYPE.IMAGE_UPLOAD_INT_TO_TYPE[info.get("type")]}-{image_id}')
                        # db_image.update_image_data(image_id=image_id, data={"status": IMAGE_STATUS_FAILED})
                    except Exception as e:
                        traceback.print_exc()
                        db_image.update_image_data(image_id=image_id, data={"status": IMAGE_STATUS_FAILED})
                elif info.get("status") in [IMAGE_STATUS_DELETING]:
                    # TODO registry, 실제 데이터 삭제
                    db_image.delete_image(image_id=image_id)
                time.sleep(1)
        except Exception as e:
            traceback.print_exc()
            time.sleep(3)
            pass

def helm_image_library(image_id, image_real_name):
    try:
        
        helm_name = TYPE.IMAGE_LIBRATY_HELM.format(image_id)
        os.chdir("/app/helm/")
        command = f"helm install {helm_name} \
                -n {settings.JF_SYSTEM_NAMESPACE}-image --create-namespace \
                --set common.imageId='{image_id}' \
                --set common.imageName='{image_real_name}' \
                --set common.systemRegistryUrl='{settings.SYSTEM_DOCKER_REGISTRY_URL}' \
                --set common.userRegistryUrl='{settings.DOCKER_REGISTRY_URL}' \
                --set common.systemNamespace='{settings.JF_SYSTEM_NAMESPACE}' \
                --set db.JF_DB_HOST='{settings.JF_DB_HOST}' \
                --set db.JF_DB_PORT='{settings.JF_DB_PORT}' \
                --set db.JF_DB_USER='{settings.JF_DB_USER}' \
                --set db.JF_DB_PW='{settings.JF_DB_PW}' \
                --set db.JF_DB_NAME='{settings.JF_DB_NAME}' \
                --set db.JF_DB_CHARSET='{settings.JF_DB_CHARSET}' ./image_library"

        subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except Exception as e:
        # db_image.update_image_data(image_id=image_id, data={"status": IMAGE_STATUS_FAILED})
        subprocess.check_output([f'helm uninstall -n {settings.JF_SYSTEM_NAMESPACE}-image image-library-{image_id}'], shell=True, stderr=subprocess.PIPE)
        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg

def helm_delete(): # helm 삭제
    while True:
        try:
            image_list = db_image.get_image_list()
            for info in image_list:
                image_id = info.get("id")
                print("-------helm delete-------")
                if info.get("status") in [IMAGE_STATUS_READY, IMAGE_STATUS_FAILED]:
                    try:
                        # job check -> 실행중 제외
                        job_info = batchV1Api.read_namespaced_job(name=f'{TYPE.IMAGE_UPLOAD_INT_TO_TYPE[info.get("type")]}-{str(info.get("id"))}', namespace=IMAGE_NAMSPACE)
                        if (job_info.status.succeeded and job_info.status.succeeded >= 1) or (job_info.status.failed and job_info.status.failed >= 1):
                            subprocess.check_output([f'helm uninstall -n {IMAGE_NAMSPACE} {TYPE.IMAGE_UPLOAD_INT_TO_TYPE[info.get("type")]}-{str(info.get("id"))}'], shell=True, stderr=subprocess.PIPE)
                            
                        job_info = batchV1Api.read_namespaced_job(name=f'image-library-{str(info.get("id"))}', namespace=IMAGE_NAMSPACE)
                        if (job_info.status.succeeded and job_info.status.succeeded >= 1) or (job_info.status.failed and job_info.status.failed >= 1):
                            subprocess.check_output([f'helm uninstall -n {IMAGE_NAMSPACE} image-library-{str(info.get("id"))}'], shell=True, stderr=subprocess.PIPE)
                    except Exception as e:
                        pass        
                time.sleep(1)
        except Exception as e:
            traceback.print_exc()
            time.sleep(3)
            pass

status_check_thread = threading.Thread(target=status_check)
# helm_delete_thread = threading.Thread(target=helm_delete)

status_check_thread.daemon = True
# helm_delete_thread.daemon = True

status_check_thread.start()
# helm_delete_thread.start()
status_check_thread.join()
# helm_delete_thread.join()
