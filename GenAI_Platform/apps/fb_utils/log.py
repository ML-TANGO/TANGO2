
from enum import Enum
from utils.msa_db import db_user
from utils.msa_db import db_workspace


class LogParam:
    class Task(Enum):
        def __str__(self):
            return self.value
        DATASET='dataset'
        IMAGE='image'
        TRAINING='training'
        DEPLOYMENT='deployment'
        WORKSPACE='workspace'
        USER='user'

    class Action(Enum):
        def __str__(self):
            return self.value
        CREATE='create'
        UPDATE='update'
        DELETE='delete'

def logging_history(task, action, task_name=None, user_id=None, user_name=None, workspace_id=None, workspace_name=None, update_details=None):
    """
    :param task: string, one of workspace, training, job, hyperparams, image, or dataset
    :param action: string, one of add, create, update, delete, auto_labeling, download, uploadData or deleteDate
    :param user: user_id or user_name
    :param workspace: workspace_id or workspace_name
    :param task_name: string, name of task
    :param update_details: stirng, updated detailed information
    """
    user = db_user.get_user(user_id=user_id).get('name') if user_id else user_name if user_name else None
    workspace = db_workspace.get_workspace(workspace_id=workspace_id).get('name') if workspace_id else workspace_name if workspace_name else None

    print(f'[JFB/USAGE] {{"user": "{user}", "task": "{task}", "action": "{action}", "workspace": "{workspace}", "task_name": "{task_name}", "update_details": "{update_details}"}}')

async def logging_history_async(task, action, task_name=None, user_id=None, user_name=None, workspace_id=None, workspace_name=None, update_details=None):
    """
    :param task: string, one of workspace, training, job, hyperparams, image, or dataset
    :param action: string, one of add, create, update, delete, auto_labeling, download, uploadData or deleteDate
    :param user: user_id or user_name
    :param workspace: workspace_id or workspace_name
    :param task_name: string, name of task
    :param update_details: stirng, updated detailed information
    """
    user_info = await db_user.get_user_async(user_id=user_id)
    user = user_info.get("name") if user_id else user_name if user_name else None
    workspace_info = await db_workspace.get_workspace_async(workspace_id=workspace_id)
    workspace = workspace_info.get('name') if workspace_id else workspace_name if workspace_name else None

    print(f'[JFB/USAGE] {{"user": "{user}", "task": "{task}", "action": "{action}", "workspace": "{workspace}", "task_name": "{task_name}", "update_details": "{update_details}"}}')
