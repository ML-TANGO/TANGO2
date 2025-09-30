from utils.exceptions import CustomError
Location = "workspace"

class WorkspaceNameInvalidError(CustomError):
    def __init__(self, message="Workspace Name Invalid", location=Location):
        self.message = message
        self.location = location
        self.code = '001'

class WorkspaceNameDuplicatedError(CustomError):
    def __init__(self, message="Workspace Name Duplicated", location=Location):
        self.message = message
        self.location = location
        self.code = '002'

class WorkspaceNotExistError(CustomError):
    def __init__(self, message="Workspace Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '003'

class RunningWorkspaceDeleteError(CustomError):
    def __init__(self, message="Workspace running.", location=Location):
        # 동작중인 Pod, 대기중인 Queue 가 없어야만 삭제 가능
        self.message = message
        self.location = location
        self.code = '004'
class OutOfSerivceWOrkspace(CustomError):
    def __init__(self, message="out of service", location=Location):
        # 동작중인 Pod, 대기중인 Queue 가 없어야만 삭제 가능
        self.message = message
        self.location = location
        self.code = '005'

    def response(self, redirect=True):
        return {"message": self.message, "redirect": redirect}


class WorkspaceNameChangeNotSupportedError(CustomError):
    def __init__(self, message="Workspace Name Change Not Supported.", location=Location):
        # UI를 통해서는 보기 어려운 케이스. (API를 직접 Request 하는 경우에만 볼만한)
        self.message = message
        self.location = location
        self.code = '000'

