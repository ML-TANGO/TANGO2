from utils.resource import response
# import utils.db as db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_workspace as ws_db
import utils.msa_db.db_storage as storage_db
import utils.msa_db.db_user as user_db
from utils.PATH import JF_DATA_DATASET_PATH
import utils.crypt as cryptUtil
from utils.exception.exceptions import *
from utils.access_check import *
from utils.settings import *
import tarfile
from shutil import *
from pathlib import Path, PurePath
from utils.PATH import *
import time
from datetime import datetime
# from starlette.responses import FileResponse
from fastapi.responses import StreamingResponse, FileResponse
import mimetypes

def download(body, headers_user = None):
    try :
        if not DATASET_DOWNLOAD_ALLOW :
            return response(status = 0 , message = "Download is not supported.")
        user_id = user_db.get_user_id(headers_user)
        # user_id = user_id['id']
        dataset_info = dataset_db.get_dataset(body.dataset_id)
        workspace_info = ws_db.get_workspace(workspace_id=dataset_info['workspace_id'])
        storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
        dataset_dir = Path(JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'], ACCESS= dataset_info['access'], DATASET_NAME=dataset_info['name']))

        if body.path is not None:
            dataset_dir = dataset_dir.joinpath(body.path)

        if len(body.download_files) > 1:
            now = datetime.now()
            formatted_time = now.strftime("%Y-%m-%d-%H:%M:%S")
            tar_path = dataset_dir.joinpath(headers_user+'-'+str(formatted_time)+".tar")

            # TAR 파일 열기 (쓰기 모드로)
            with tarfile.open(tar_path, "w:gz") as tar:
                # 현재 디렉토리의 모든 파일과 서브디렉토리 추가
                for data in body.download_files:
                    tar.add(dataset_dir.joinpath(data), arcname=dataset_dir.joinpath(data).relative_to(dataset_dir))
            download_path=tar_path
        
        else:
            download_path = dataset_dir.joinpath(body.download_files[0])
            if download_path.is_dir():
                tar_path=download_path.with_name(download_path.name).with_suffix(".tar")
                with tarfile.open(tar_path, "w") as tar:
                    tar.add(download_path, arcname=tar_path.relative_to(dataset_dir))
                download_path=tar_path
                print(111111111111111111111111111111111111111111111)
        
        print(download_path.name)
        print(download_path)
        if not download_path.exists():
            return response(status = 0 , message = f"{body.download_files} not found.")
        return FileResponse(download_path, media_type=mimetypes.guess_type(download_path.name)[0], filename=download_path.name)
       
    except:
        traceback.print_exc()
        # raise DownloadError