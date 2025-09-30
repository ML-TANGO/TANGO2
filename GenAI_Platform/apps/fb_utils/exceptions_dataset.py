from utils.exceptions import CustomError

Location = 'dataset'

class CreateDatasetError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '001'

class FileUploadError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '002'

class DatasetDeleteError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '003'

class DownloadError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '004'

class DetailInformationError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '005'

class GithubConnectError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '006'

class GoogleConnectError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '007'

class SyncError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '008'

class SyncCheckError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '009'

class DecompressError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '010'

class BuiltInModelTemplateError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '011'

class PreviewError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '012'

class GetDatasetListError(CustomError):
    def __init__(self, message=None, location = Location):
        self.message = message
        self.location = location
        self.code = '013'
