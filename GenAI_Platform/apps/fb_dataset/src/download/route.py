from fastapi import APIRouter, Depends, Request, Path
from utils.resource import CustomResource, token_checker, def_token_checker
from utils.settings import LOGIN_METHOD
from utils.access_check import *
from utils.settings import *

from download import model
from download import service as download_svc

download = APIRouter(
    prefix = "/download"
)

@download.get("")
# @token_checker
def donwload_data(args : model.DownLoadModel=Depends()):
    cr = CustomResource()
    args.download_files= args.download_files.split(',')
    return download_svc.download(body=args,headers_user=cr.check_user())
