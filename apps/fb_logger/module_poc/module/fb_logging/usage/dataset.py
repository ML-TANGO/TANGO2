def create_dataset(self, username, workspace, dataset_name):
    """
    Logs a dataset creation event.

    Args:
        username (str): The user who created the dataset.
        workspace (str): The workspace where the dataset was created.
        dataset_name (str): The name of the dataset created.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "dataset", "task_name": dataset_name, "action": "create"})

def delete_dataset(self, username, workspace, dataset_name):
    """
    Logs a dataset deletion event.

    Args:
        username (str): The user who deleted the dataset.
        workspace (str): The workspace where the dataset was deleted.
        dataset_name (str): The name of the dataset deleted.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "dataset", "task_name": dataset_name, "action": "delete"})
    
def update_dataset(self, username, workspace, dataset_name):
    """
    Logs a dataset update event.

    Args:
        username (str): The user who updated the dataset.
        workspace (str): The workspace where the dataset was updated.
        dataset_name (str): The name of the dataset updated.
    """
    self.usage(data={"user": username, "workspace": workspace, "task": "dataset", "task_name": dataset_name, "action": "update"})