def create_deployment(self, username, workspace, deployment_name):
    """
    Logs a deployment creation event.

    Args:
        username (str): The user who created the deployment.
        workspace (str): The workspace where the deployment was created.
        deployment_name (str): The name of the deployment created.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "deployment", "task_name": deployment_name, "action": "create"})
    
def delete_deployment(self, username, workspace, deployment_name):
    """
    Logs a deployment deletion event.

    Args:
        username (str): The user who deleted the deployment.
        workspace (str): The workspace where the deployment was deleted.
        deployment_name (str): The name of the deployment deleted.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "deployment", "task_name": deployment_name, "action": "delete"})
    
def update_deployment(self, username, workspace, deployment_name):
    """
    Logs a deployment update event.

    Args:
        username (str): The user who updated the deployment.
        workspace (str): The workspace where the deployment was updated.
        deployment_name (str): The name of the deployment updated.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "deployment", "task_name": deployment_name, "action": "update"})