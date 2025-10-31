from utils.exceptions import CustomError
Location = "training"

class TrainingNameInvalidError(CustomError):
    def __init__(self, message="Training Name Invalid", location=Location):
        self.message = message
        self.location = location
        self.code = '001'

class TrainingItemNotExistError(CustomError):
    def __init__(self, message="Training Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '002'

class TrainingNameDuplicatedError(CustomError):
    def __init__(self, message="Training Name Duplicated", location=Location):
        self.message = message
        self.location = location
        self.code = '003'

class TrainingNameChangeNotSupported(CustomError):
    def __init__(self, message="Training Name Change Not Supported.", location=Location):
        # UI를 통해서는 보기 어려운 케이스. (API를 직접 Request 하는 경우에만 볼만한)
        self.message = message
        self.location = location
        self.code = '000'

class TrainingToolFilebrowserPasswordChangeError(CustomError):
    def __init__(self, message="Filebrowser password change error because user id is wrong.", location=Location):
        # UI를 통해서는 보기 어려운 케이스. (API를 직접 Request 하는 경우에만 볼만한)
        self.message = message
        self.location = location
        self.code = '004'

class TrainingToolFilebrowserAlreadyChange(CustomError):
    def __init__(self, message="Filebrowser password already change.", location=Location):
        # UI를 통해서는 보기 어려운 케이스. (API를 직접 Request 하는 경우에만 볼만한)
        self.message = message
        self.location = location
        self.code = '005'

class TrainingJobHpsDeleteMultipleTrainingError(CustomError):
    def __init__(self, message="Job or Hps delete from multiple training. (not allow)", location=Location):
        # UI를 통해서는 보기 어려운 케이스. (API를 직접 Request 하는 경우에만 볼만한)
        self.message = message
        self.location = location
        self.code = '006'
