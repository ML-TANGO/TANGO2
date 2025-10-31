from utils.exceptions import CustomError
Location = 'images'

# GET /image/, /image/<string:image_id>
class GetImageError(CustomError):
    def __init__(self, message = None, location = Location):
        self.message = message
        self.location = location
        self.code = '001'

# GET /tag
class GetAdminImageError(CustomError):
    def __init__(self, message="Get admin Image Error", location = Location):
        self.message = message
        self.location = location
        self.code = '002'

# GET /ngc
class GetNgcImageError(CustomError):
    def __init__(self, message="Ngc image error", location = Location):
        self.message = message
        self.location = location
        self.code = '003'

# GET /ngc/tags
class GetNgcImageTagError(CustomError):
    def __init__(self, message="Tag error", location = Location):
        self.message = message
        self.location = location
        self.code = '004'

# POST /pull build tar ngc tag commit copy
class PostImageError(CustomError):
    def __init__(self, message = None, location = Location):
        self.message = message
        self.location = location
        self.code = '005'

# POST /pull build tar ngc tag commit copy
class CreateImageError(CustomError):
    def __init__(self, message="Create Image error", location = Location):
        self.message = message
        self.location = location
        self.code = '006'

# POST /pull build tar ngc tag commit copy
class InstallImageError(CustomError):
    def __init__(self, message=None, location = Location, reason=None):
        self.message = "Install Image Error : {}".format(reason)
        self.location = location
        self.code = '007'

# POST /pull build tar ngc tag commit copy
class NotExistWorkspaceError(CustomError):
    def __init__(self, message=None, location = Location, workspace_id=None):
        self.message = 'Workspace of requested id {} does not exist.'.format(workspace_id)
        self.location = location
        self.code = '008'

# POST /tag /copy /ngc, GET /history
class NotExistImageError(CustomError):
    def __init__(self, message=None, location = Location, image_name=None):
        self.message = "{} does not exist.".format(image_name) if image_name is not None else "Image does Not Exist"
        self.location = location
        self.code = '009'

# POST /build, /tar
class SaveFileForImageError(CustomError):
    def __init__(self, message = None, location = Location):
        self.message = message
        self.location = location
        self.code = '010'

# POST /build, /tar
class WritablePathError(CustomError):
    def __init__(self, message=None, location = Location, path=None):
        self.message = '{} is not writable. check permission.'.format(path)
        self.location = location
        self.code = '011'

# PUT /image
class UpdateImageError(CustomError):
    def __init__(self, message = None, location = Location):
        self.message = message
        self.location = location
        self.code = '012'

# DELETE /image
class DeleteImageError(CustomError):
    def __init__(self, message = None, location = Location):
        self.message = message
        self.location = location
        self.code = '013'

# POST /pull build tar ngc tag commit copy
class ValidImageNameEmptyError(CustomError):
    def __init__(self, message="Image name could not be empty", location = Location):
        self.message = message
        self.location = location
        self.code = '014'

# POST /pull build tar ngc tag commit copy
class VaildImageNameDuplicatedError(CustomError):
    def __init__(self, message="Duplicate image name", location = Location):
        self.message = message
        self.location = location
        self.code = '015'

# POST /pull /ngc /tag
class ValidImageUrlProtocolError(CustomError):
    def __init__(self, message="Invalid url format. Remove http scheme.", location = Location):
        self.message = message
        self.location = location
        self.code = '016'

# POST /pull /ngc /tag
class ValidImageUrlFormatError(CustomError):
    def __init__(self, message="Invalid url format", location = Location):
        self.message = message
        self.location = location
        self.code = '017'

# POST /build /tar
class ValidTypeError(CustomError):
    def __init__(self, message="Upload image type error", location = Location):
        self.message = message
        self.location = location
        self.code = '018'

# class VaildTypeTarError(CustomError):
#     def __init__(self, message="Only tar files are allowed.", location = Location):
#         self.message = message
#         self.location = location
#         self.code = '400'

class LauncherError(CustomError):
    def __init__(self, message="Launcher Error", location = Location):
        self.message = message
        self.location = location
        self.code = '019'

# GET /image, DELETE /image
class ImagePermissionError(CustomError):
    def __init__(self, message="Check Permission Image", location = Location):
        self.message = message
        self.location = location
        self.code = '020'