from utils.exception.exceptions import CustomError
Location = 'user'

class GetAdminDashboardError(CustomError):
    def __init__(self, message = "Get admin dashboard info Error", location = Location):
        self.message = message
        self.location = location
        self.code = '001'