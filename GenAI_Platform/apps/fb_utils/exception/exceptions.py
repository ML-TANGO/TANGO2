import pymysql
import json
from inspect import getmembers, isclass
import sys

Location = 'public'

class RemoteError(RuntimeError):
    pass


class CustomError(Exception):
    """For CustomException"""
    code = 0
    location = ""
    message = ""
    options = dict()

    def __init__(self, message="", location="public", code=0):
        self.message = message
        self.location = location
        self.code = code
        super().__init__(message)

    def __str__(self):
        # 실제 메시지가 있으면 그것을 반환하고, 없으면 기본값 반환
        return self.message if self.message else "CustomExceptionCase"

    def response(self, redirect=False, status=0, message=None, result=None):
        return {
            'status' : status,
            'result' : result,
            'error' : {
                'code' : self.code,
                'location' : self.location,
                'message' : self.message,
                'options' : self.options
            }
            #            'message' : message if message is not None else self.message,
        }

class MissingHeaderError(CustomError):
    def __init__(self, message="Missing header.", location= Location):
        self.message = message
        self.location = location
        self.code = '001'


class ItemNotExistError(CustomError):
    def __init__(self, message="Item Not Exist.", location= Location):
        self.message = message
        self.location = location
        self.code = '002'
    
    def __str__(self):
        return self.message

    def response(self, redirect=False):
        return {"message": self.message, "redirect": redirect}


class DuplicateKeyError(pymysql.err.IntegrityError, CustomError):
    def __init__(self, message="Duplicate name.", location= Location):
        self.message = message
        self.location = location
        self.code = '003'


class InaccessibleWorkspaceError(CustomError):
    def __init__(self, message = "This workspace is inaccessible.", location= Location):
        self.message = message
        self.location = location
        self.code = '004'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class InaccessibleDatasetError(CustomError):
    def __init__(self, message="This dataset is inaccessible.", location= Location):
        self.message = message
        self.location = location
        self.code = '005'

    def response(self, redirect=False):
        return {"message": self.message, "redirect": redirect}


class InaccessibleTrainingError(CustomError):
    def __init__(self, message = "This training is inaccessible.", location= Location):
        self.message = message
        self.location = location
        self.code = '006'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class InaccessibleDeploymentError(CustomError):
    def __init__(self, message = "This deployment is inaccessible.",location = Location):
        self.message = message
        self.location = location
        self.code = '007'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class InaccessibleAdminError(CustomError):
    def __init__(self,message = "This Page is inaccessible.", location = Location):
        self.message = message
        self.location = location
        self.code = '008'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class KubernetesServiceError(CustomError):
    # kubernetes.client.exceptions.ApiException
    def __init__(self, api_e, location = Location):
        api_e_body = json.loads(api_e.body)
        error_message = "error-code[{}] - {}".format(str(api_e.status), api_e_body["details"]["causes"][0]["message"])
        self.message = error_message
        self.location = location
        self.code = '009'


class InaccessibleImageError(CustomError):
    def __init__(self, message = "This image is inaccessible.", location = Location):
        self.message = message
        self.location = location
        self.code = '010'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class InvalidGPUPerPodError(CustomError):
    def __init__(self, message = "Correct the number of gpu per pod", location = Location):
        self.message = message
        self.location = location
        self.code = '011'

class AlreadyRunningItemError(CustomError):
    def __init__(self, message = "Already running item", location = Location):
        self.message = message
        self.location = location
        self.code = '012'
        
class AlreadyRunningItemError(CustomError):
    def __init__(self, message = "Already running item", location = Location):
        self.message = message
        self.location = location
        self.code = '012'


class InaccessibleSampleError(CustomError):
    def __init__(self, message = "This sample isaccessible.", location = Location):
        self.message = message
        self.location = location
        self.code = '000'


# CustomErrorList = (
# DuplicateKeyError, TrainingAlreadyRunningError, InaccessibleWorkspaceError, InaccessibleTrainingError, CustomError,
# ItemNotExistError, InaccessibleDatasetError, InaccessibleImageError)

from utils.exception.exceptions_dataset import *
from utils.exception.exceptions_image import *
from utils.exception.exceptions_dashboard import *
from utils.exception.exceptions_project import *
from utils.exception.exceptions_workspace import *
from utils.exception.exceptions_deployment import *
from utils.exception.exceptions_network import *
from utils.exception.exceptions_storage import *
from utils.exception.exceptions_user import *
# from utils.exception.exceptions_records import *


CustomErrorList = ()
ImportErrorList = []

ExceptList = getmembers(sys.modules['utils.exception.exceptions'], isclass)

for key,value in ExceptList:
    if key == 'CustomError' or key == 'RemoteError':
        continue
    ImportErrorList.append(value)

CustomErrorList = CustomErrorList + tuple(ImportErrorList)
import traceback
def get_exception_list():
    try:
        from operator import itemgetter

        exception_list = {}
        for element in CustomErrorList:
            try:
                error = element()
                if exception_list.get(error.location) is None:
                    exception_list[error.location] = []
                exception_list[error.location].append(
                    {
                        "class_name" : error.__class__.__name__,
                        "code" : error.code,
                        "location" : error.location,
                        "message" : error.message
                    }
                )
            except:
                pass
        print(exception_list.items())
        for element in exception_list:
            exception_list[element].sort( key= lambda x: x['code'])
        return exception_list
    except:
        traceback.print_exc()
            