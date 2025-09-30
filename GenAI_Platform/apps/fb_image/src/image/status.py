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
from utils import settings
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

IMAGE_UPLOAD_TYPE_STR = {
    0 : "built-in", 1 : "pull", 2 : "tar", 3 : "build", 4 : "tag", 5 : "ngc", 6 : "commit", 7 : "copy",
}

IMAGE_NAMSPACE = f"{settings.JF_SYSTEM_NAMESPACE}-image"

def status_check():
    while True:
        try:
            image_list = db_image.get_image_list()
            for info in image_list:
                print("-------status-------")
                image_id = info.get("id")
                if info.get("status") == IMAGE_STATUS_INSTALLING:
                    try:
                        print("id", image_id)
                        # job check
                        job_info = batchV1Api.read_namespaced_job(name=f'{IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{str(info.get("id"))}', namespace=IMAGE_NAMSPACE)
                        if job_info.status.succeeded and job_info.status.succeeded >= 1:
                            time.sleep(5)

                            real_name = info.get("real_name")
                            registry = real_name.split('/')[0]
                            tmp_repository = real_name.replace(registry + "/", "").split(":")
                            repository = tmp_repository[0]
                            tag = tmp_repository[1]
                            headers = { "Accept" : "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.index.v1+json"}
                            url = f"http://{registry}/v2/{repository}/manifests/{tag}"

                            response = requests.get(url, headers=headers)
                            if response.status_code == 200:
                                response_json = response.json()
                                layers = response_json.get('layers', [])
                                image_size = sum(layer['size'] for layer in layers)
                                digest = response.headers.get('Docker-Content-Digest')
                                if digest.startswith("sha256:"):
                                    tmp_iid = digest[7:20] # iid아닌데 iid 값이 의미가 없는 것 같아서 digest 잘라서 넣음 (로컬이면 의미가 있는데,,,)
                                db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_READY, "size" : image_size, "iid" : tmp_iid, "docker_digest" : digest})
                            else:
                                db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_FAILED})

                            try:
                                # helm 삭제
                                subprocess.check_output([f'helm uninstall -n {IMAGE_NAMSPACE} {IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{str(info.get("id"))}'], shell=True, stderr=subprocess.PIPE)
                            except Exception as e:
                                pass

                            try:
                                # library
                                helm_image_library(image_id, info.get("real_name"))
                            except Exception as e:
                                pass

                        elif job_info.status.failed and job_info.status.failed >= 1:
                            db_image.update_image_data(image_id=info.get("id"), data={"status": IMAGE_STATUS_FAILED})

                    except client.rest.ApiException as e:
                        # job이 없는 경우 # 설치 전이라 안뜬 경우도 있음
                        print("not exist job", image_id)
                        # print("-----fail-----")
                        # print(f'{IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{image_id}')
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
        if f'{settings.JF_SYSTEM_NAMESPACE}.svc.cluster.local' in settings.JF_DB_HOST:
            jf_db_host = settings.JF_DB_HOST
        else:
            jf_db_host = settings.JF_DB_HOST.split('.')[0] + f'.{settings.JF_SYSTEM_NAMESPACE}.svc.cluster.local'

        os.chdir("/app/helm/")
        command = f"helm install image-library-{image_id} \
                -n {settings.JF_SYSTEM_NAMESPACE}-image --create-namespace \
                --set common.imageId='{image_id}' \
                --set common.imageName='{image_real_name}' \
                --set common.systemRegistryUrl='{settings.DOCKER_REGISTRY_URL}' \
                --set common.systemNamespace='{settings.JF_SYSTEM_NAMESPACE}' \
                --set db.JF_DB_HOST='{jf_db_host}' \
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
                        job_info = batchV1Api.read_namespaced_job(name=f'{IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{str(info.get("id"))}', namespace=IMAGE_NAMSPACE)
                        if (job_info.status.succeeded and job_info.status.succeeded >= 1) or (job_info.status.failed and job_info.status.failed >= 1):
                            subprocess.check_output([f'helm uninstall -n {IMAGE_NAMSPACE} {IMAGE_UPLOAD_TYPE_STR[info.get("type")]}-{str(info.get("id"))}'], shell=True, stderr=subprocess.PIPE)

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
