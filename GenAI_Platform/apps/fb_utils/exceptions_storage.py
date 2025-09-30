from utils.exceptions import CustomError
Location = "storage"

class CreateWorkspaceError(CustomError):
    def __init__(self, message="Create Workspace Error", location=Location):
        self.message = message
        self.location = location
        self.code = '001'

class MountImageError(CustomError):
    def __init__(self, message="Mount Image Error", location=Location):
        self.message = message
        self.location = location
        self.code = '002'

class UMountImageError(CustomError):
    def __init__(self, message="UMount Image Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '003'

class ResizeImageError(CustomError):
    def __init__(self, message="Resize Image Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '004'

class RemoveImageError(CustomError):
    def __init__(self, message="Remove Image Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '005'

class RemoveMountpointError(CustomError):
    def __init__(self, message="Remove Mountpoint Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '006'

class FstabExtractError(CustomError):
    def __init__(self, message="Fstab Extract Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '007'

class NotExistImageLimitError(CustomError):
    def __init__(self, message="Not Exist Image Limit Error.", location=Location):
        self.message = message
        self.location = location
        self.code = '008'
