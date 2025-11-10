from fastapi import APIRouter, Depends, Request, Path
from utils.resource import get_auth
from utils.settings import LOGIN_METHOD
from utils.access_check import *
from utils.settings import *

from download import model
from download import service as download_svc

download = APIRouter(
    prefix = "/download"
)

@download.get("")
def donwload_data(args : model.DownLoadModel=Depends()):
    user_name, _ = get_auth()
    args.download_files= args.download_files.split(',')
    return download_svc.download(body=args,headers_user=user_name)
    