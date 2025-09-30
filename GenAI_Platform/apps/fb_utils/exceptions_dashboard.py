from utils.exceptions import CustomError
Location = 'dashboard'

class GetAdminDashboardError(CustomError):
    def __init__(self, message = "Get admin dashboard info Error", location = Location):
        self.message = message
        self.location = location
        self.code = '001'

class GetUserDashboardError(CustomError):
    def __init__(self, message = "Get user dashboard info Error", location = Location):
        self.message = message
        self.location = location
        self.code = '002'