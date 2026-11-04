from utils.exception.exceptions import CustomError

Location = "built_in_model"

class BuiltInModelNoInfo(CustomError):
    def __init__(self, message="Built In Model No Info", location = Location):
        self.message = message
        self.location = location
        self.code = '001'

class BuiltInModelNameAlreadyExist(CustomError):
    def __init__(self, message="Built In Model Name Already Exists", location = Location):
        self.message = message
        self.location = location
        self.code = '002'

class BuiltInModelThumbnailFileFormatUnsupported(CustomError):
    def __init__(self, message="Built In Model Thumbnail File Format Unsupported", location = Location):
        self.message = message
        self.location = location
        self.code = '003'