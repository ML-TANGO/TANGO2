from utils.exception.exceptions import CustomError
Location = "project"

class ProjectNameInvalidError(CustomError):
    def __init__(self, message="프로젝트 이름이 유효하지 않습니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '001'

class ProjectDeployRelateError(CustomError):
    def __init__(self, message="프로젝트와 연결된 배포가 있습니다. 배포를 먼저 삭제해주세요.", location=Location):
        self.message = message
        self.location = location
        self.code = '002'

class RunningProjectError(CustomError):
    def __init__(self, message="실행 중인 프로젝트가 있습니다. 모든 작업을 종료한 후 다시 시도해주세요.", location=Location):
        self.message = message
        self.location = location
        self.code = '003'

class SavingImageError(CustomError):
    def __init__(self, message="이미지를 저장 중입니다. 잠시 후 다시 시도해주세요.", location=Location):
        self.message = message
        self.location = location
        self.code = '004'

class InvalidServiceProjectError(CustomError):
    def __init__(self, message="프로젝트에서 유효하지 않은 서비스입니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '005'

class InvalidServiceBuiltInProjectError(CustomError):
    def __init__(self, message="빌트인 프로젝트에서 유효하지 않은 서비스입니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '006'

class RunningProjectToolError(CustomError):
    def __init__(self, message="실행 중인 프로젝트 도구가 있습니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '007'

class InvalidServiceProjectToolError(CustomError):
    def __init__(self, message="프로젝트 도구에서 유효하지 않은 서비스입니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '008'

class NotSelectGpuClusterTypeError(CustomError):
    def __init__(self, message="클러스터 타입을 선택해주세요.", location=Location):
        self.message = message
        self.location = location
        self.code = '009'

class NotSelectNodeGpuError(CustomError):
    def __init__(self, message="노드 GPU를 선택해주세요.", location=Location):
        self.message = message
        self.location = location
        self.code = '010'


class ProjectCreateError(CustomError):
    def __init__(self, message="프로젝트 생성 중 오류가 발생했습니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '100'


class ProjectDeleteError(CustomError):
    def __init__(self, message="프로젝트 삭제 중 오류가 발생했습니다.", location=Location):
        self.message = message
        self.location = location
        self.code = '101'