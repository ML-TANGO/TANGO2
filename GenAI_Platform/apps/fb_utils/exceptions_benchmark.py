from utils.exceptions import CustomError

Location = 'benchmark'
Location_db = 'db_benchmark'


class AlreadyThreadRunningError(CustomError):
    def __init__(self, message="These cells are already testing", location = Location):
        self.message = message
        self.location = location
        self.code = '001'

class DataDoesNotExistError(CustomError):
    def __init__(self, message="Data does not exist.", location = Location):
        self.message = message
        self.location = location
        self.code = '002'