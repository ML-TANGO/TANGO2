# hps, create_group, create_task, delete

def create_hps_group(self, username, workspace, hps_name, training_name):
    """
    Logs a hyperparameter search group creation event.

    Args:
        username (str): The user who created the hyperparameter search.
        workspace (str): The workspace where the hyperparameter search was created.
        hps_name (str): The name of the hyperparameter search created.
        training_name (str): The name of the parent training.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "hyperparamsearch",
                     "task_name": f"{training_name} / {hps_name}",
                     "action": "create"})

def create_hps_task(self, username, workspace, hps_name, training_name, task_idx):
    """
    Logs a hyperparameter search task creation event.

    Args:
        username (str): The user who created the hyperparameter search task.
        workspace (str): The workspace where the hyperparameter search task was created.
        hps_name (str): The name of the parent hyperparameter search.
        training_name (str): The name of the parent training.
        task_idx (int): The index of the task created.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "hyperparamsearch",
                     "task_name": f"{training_name} / {hps_name}[{task_idx}]",
                     "action": "create"})

def delete_hps(self, username, workspace, hps_name, training_name):
    """
    Logs a hyperparameter search deletion event.

    Args:
        username (str): The user who deleted the hyperparameter search.
        workspace (str): The workspace where the hyperparameter search was deleted.
        hps_name (str): The name of the hyperparameter search deleted.
        training_name (str): The name of the parent training.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "hyperparamsearch",
                     "task_name": f"{training_name} / {hps_name}",
                     "action": "delete"})