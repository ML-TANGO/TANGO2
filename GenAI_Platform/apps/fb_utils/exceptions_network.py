from utils.exceptions import CustomError
Location = 'networks'



class NetworkGroupCategoryInvalidError(CustomError):
    def __init__(self, message="Invalid Category", location=Location):
        self.message = message
        self.location = location
        self.code = '000'
class NetworkGroupCheckError(CustomError):
    def __init__(self, message="There aren't enough nodes to test.", location=Location):
        self.message = message
        self.location = location
        self.code = '001'

class NetworkGroupContainerInterfaceDuplicateError(CustomError):
    def __init__(self, message="Network group container interface name duplicate.", location=Location):
        self.message = message
        self.location = location
        self.code = '002'

class NetworkGroupNameDuplicateError(CustomError):
    def __init__(self, message="Network group name duplicate.", location=Location):
        self.message = message
        self.location = location
        self.code = '003'

class NetworkGroupContainerInterfacePortDuplicateError(CustomError):
    def __init__(self, message="Network group container interface port index duplicate.", location=Location):
        self.message = message
        self.location = location
        self.code = '004'

class NetworkGroupContainerInterfaceEmptyError(CustomError):
    def __init__(self, message="Network group container interface is empty.", location=Location):
        self.message = message
        self.location = location
        self.code = '005'