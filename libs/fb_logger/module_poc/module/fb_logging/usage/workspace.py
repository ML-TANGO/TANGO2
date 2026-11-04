def create_workspace(self, username, workspace):
    """
    Logs a workspace creation event.

    Args:
        username (str): The user who created the workspace.
        workspace (str): The workspace created.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "workspace", "action": "create"})
    
# def delete_workspace(self, username, workspace):
#     """
#     Logs a workspace deletion event.

#     Args:
#         username (str): The user who deleted the workspace.
#         workspace (str): The workspace deleted.
#     """
#     self.usage(data={"user": username, "workspace": workspace, "task": "workspace", "action": "delete"})

def update_workspace(self, username, workspace):
    """
    Logs a workspace update event.

    Args:
        username (str): The user who updated the workspace.
        workspace (str): The workspace updated.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "workspace", "action": "update"})