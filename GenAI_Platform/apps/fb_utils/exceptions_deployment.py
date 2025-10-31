from utils.exceptions import CustomError

Location = "deployment"


class DeploymentTemplateGroupNameExistError(CustomError):
    def __init__(self, message="Deployment Template Group Name Already Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '001'
class DeploymentNameExistError(CustomError):
    def __init__(self, message="Deployment Name Already Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '002'

class DeploymentNameInvalidError(CustomError):
    def __init__(self, message="Deployment Name Invalid", location = Location):
        self.message = message
        self.location = location
        self.code = '003'

class DeploymentOwnerIDNotExistError(CustomError):
    def __init__(self, message="Deployment Owner ID Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '004'

class DeploymentUserIDNotExistError(CustomError):
    def __init__(self, message="Deployment User ID Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '005'

class DeploymentNoUserInWorkspaceError(CustomError):
    def __init__(self, message="Deployment User Not In Workspace", location = Location):
        self.message = message
        self.location = location
        self.code = '006'

class DeploymentNoOwnerInWorkspaceError(CustomError):
    def __init__(self, message="Deployment Owner Not In Workspace", location = Location):
        self.message = message
        self.location = location
        self.code = '007'

class DeploymentDataFormDBInsertError(CustomError):
    def __init__(self, message="Deployment Data Form DB Insert Error", location = Location):
        self.message = message
        self.location = location
        self.code = '008'

class DeploymentDBUpdateInputTypeError(CustomError):
    def __init__(self, message="Deployment DB Update Input Type Error", location = Location):
        self.message = message
        self.location = location
        self.code = '009'

class DeploymentUserDBInsertError(CustomError):
    def __init__(self, message="Deployment User DB Insert Error", location = Location):
        self.message = message
        self.location = location
        self.code = '010'

class DeploymentDBDeleteUserError(CustomError):
    def __init__(self, message="Deployment DB Delete user", location = Location):
        self.message = message
        self.location = location
        self.code = '011'

class DeploymentTemplateDBInsertError(CustomError):
    def __init__(self, message="Deployment Template DB Insert", location = Location):
        self.message = message
        self.location = location
        self.code = '012'

class DeploymentTemplateDBUpdateError(CustomError):
    def __init__(self, message="Deployment Template DB Update", location = Location):
        self.message = message
        self.location = location
        self.code = '013'

class DeploymentTemplateDBDeleteError(CustomError):
    def __init__(self, message="Deployment Template DB Delete", location = Location):
        self.message = message
        self.location = location
        self.code = '014'

class CreateDeploymentDBInsertError(CustomError):
    def __init__(self, message="Deployment Create DB Insert", location = Location):
        self.message = message
        self.location = location
        self.code = '015'


class UpdateDeploymentDBInsertError(CustomError):
    def __init__(self, message="Deployment Update DB Insert", location = Location):
        self.message = message
        self.location = location
        self.code = '016'

class DeploymentRunSchedulerError(CustomError):
    def __init__(self, message="Deployment Run No Resource", location = Location):
        self.message = message
        self.location = location
        self.code = '017'

class DeploymentWorkerDescriptionDBUpdateError(CustomError):
    def __init__(self, message="Deployment Worker description DB update", location = Location):
        self.message = message
        self.location = location
        self.code = '018'

class DeleteDeploymentNotExistError(CustomError):
    def __init__(self, message="Deployment Delete ID Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '019'

class DeleteDeploymentFolderError(CustomError):
    def __init__(self, message="Deployment Delete Folder Error", location = Location):
        self.message = message
        self.location = location
        self.code = '020'

class DeleteDeploymentDBError(CustomError):
    def __init__(self, message="Deployment Delete DB Delete Error", location = Location):
        self.message = message
        self.location = location
        self.code = '021'

class StopDeploymentWorkerNotExistError(CustomError):
    def __init__(self, message="Deployment Worker Stop Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '022'

class DeploymentCheckpointNotExistError(CustomError):
    def __init__(self, message="Deployment Checkpoint Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '023'

class DeploymentAbnormalHistoryCSVNotExistError(CustomError):
    def __init__(self, message="Deployment Abnormal History CSV Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '024'

class DeploymentWorkerLogDirNotExistError(CustomError):
    def __init__(self, message="Worker Log Directory Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '025'

class DeploymentWorkerDirNotExistError(CustomError):
    def __init__(self, message="Worker Directory Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '026'

class DeploymentNoLogError(CustomError):
    def __init__(self, message="Deployment Log Not Exist in Input Time Range", location = Location):
        self.message = message
        self.location = location
        self.code = '027'

class DeploymentGraphLogTimeRangeError(CustomError):
    def __init__(self, message="Deployment graph log time range", location = Location):
        self.message = message
        self.location = location
        self.code = '028'

class DeploymentNoWorkerInTimeRangeError(CustomError):
    def __init__(self, message="No worker in input time range", location = Location):
        self.message = message
        self.location = location
        self.code = '029'

class DeploymentBookmarkDBInsertError(CustomError):
    def __init__(self, message="Deployment Bookmark DB Insert Error", location = Location):
        self.message = message
        self.location = location
        self.code = '030'

class DeploymentBookmarkDBDeleteError(CustomError):
    def __init__(self, message="Deployment Bookmark DB Delete Error", location = Location):
        self.message = message
        self.location = location
        self.code = '031'

class DeploymentAPIPathNotAllowedError(CustomError):
    def __init__(self, message="Deployment API Path Not Allowed", location = Location):
        self.message = message
        self.location = location
        self.code = '032'

class DeploymentAPIPathDBInsertError(CustomError):
    def __init__(self, message="Deployment DB Insert API Path Error", location = Location):
        self.message = message
        self.location = location
        self.code = '033'

class WorkerDBInsertError(CustomError):
    def __init__(self, message="Deployment Worker DB Insert Error", location = Location):
        self.message = message
        self.location = location
        self.code = '034'

class WorkerRunTypeUndefinedError(CustomError):
    def __init__(self, message="Deployment Worker Run Type Undefined", location = Location):
        self.message = message
        self.location = location
        self.code = '035'

class DeploymentCreatePodError(CustomError):
    def __init__(self, message="Deployment Create Pod Error", location = Location):
        self.message = message
        self.location = location
        self.code = '036'

class DeploymentSelectTrainingNotExistError(CustomError):
    def __init__(self, message="Deployment Select Training Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '037'

class DeleteDeploymentWorkerDBError(CustomError):
    def __init__(self, message="Deployment Worker DB Delete Error", location = Location):
        self.message = message
        self.location = location
        self.code = '038'

class DeploymentTemplateGroupDBInsertError(CustomError):
    def __init__(self, message="Deployment Template Group DB Insert", location = Location):
        self.message = message
        self.location = location
        self.code = '039'

class DeploymentTemplateNameExistError(CustomError):
    def __init__(self, message="Deployment Template Name Already Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '040'

class DeploymentTemplateGroupNotExistError(CustomError):
    def __init__(self, message="Deployment Template Group Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '041'

class DeploymentTemplateGroupDBUpdateError(CustomError):
    def __init__(self, message="Deployment Template Group DB Update Error", location = Location):
        self.message = message
        self.location = location
        self.code = '042'

class DeploymentTemplateGroupDBDeleteError(CustomError):
    def __init__(self, message="Deployment Template Group DB Delete Error", location = Location):
        self.message = message
        self.location = location
        self.code = '043'

class DeploymentTemplateNotExistError(CustomError):
    def __init__(self, message="Deployment Template Not Exist", location = Location):
        self.message = message
        self.location = location
        self.code = '044'

class DeploymentSelectBuiltInModelNotExistError(CustomError):
    def __init__(self, message="Deployment Select Built In Model Not Exist.", location = Location):
        self.message = message
        self.location = location
        self.code = '045'

class DeploymentSelectJobNotExistError(CustomError):
    def __init__(self, message="Deployment Select Job Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '046'

class DeploymentSelectHPSNotExistError(CustomError):
    def __init__(self, message="Deployment Select HPS Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '047'

class DeploymentSelectDatasetNotExistError(CustomError):
    def __init__(self, message="Deployment Select Dataset Not Exist.", location=Location):
        self.message = message
        self.location = location
        self.code = '048'




# class CreateDeploymentError(CustomError):
#     def __init__(self, message="", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '000'

# class CreateDeploymentError(CustomError):
#     def __init__(self, message="Create Deployment Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '001'

# class RunDeploymentError(CustomError):
#     def __init__(self, message="Run Deployment Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '002'

# class GetDeploymentError(CustomError):
#     def __init__(self, message="Get Deployment Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '003'

# class GetDeploymentListError(CustomError):
#     def __init__(self, message="Get Deployment List Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '004'

# class UpdateDeploymentError(CustomError):
#     def __init__(self, message="Update Deployment Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '005'

# class DeleteDeploymentError(CustomError):
#     def __init__(self, message="Delete Deployment Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '006'

# class FileNotExistsError(CustomError):
#     def __init__(self, message="File Not Exists Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '007'

# class CheckpointError(CustomError):
#     def __init__(self, message="Checkpoint Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '008'

# class LogDownloadError(CustomError):
#     def __init__(self, message="Log Download Error", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '009'

# class DeploymentDashboardStatusError(CustomError):
#     def __init__(self, message="", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '009'

# class DeploymentDashboardHistoryError(CustomError):
#     def __init__(self, message="", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '009'
