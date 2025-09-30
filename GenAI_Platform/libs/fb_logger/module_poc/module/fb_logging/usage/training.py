def create_training(self, username, workspace, training_name, training_type):
    """
    Logs a training creation event.

    Args:
        username (str): The user who created the training.
        workspace (str): The workspace where the training was created.
        training_name (str): The name of the training created.
        training_type (str): The type of the training created. builtin or custom.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "training",
                     "task_name": f"[{training_type}] {training_name}",
                     "action": "create"})

def delete_training(self, username, workspace, training_name, training_type):
    """
    Logs a training deletion event.

    Args:
        username (str): The user who deleted the training.
        workspace (str): The workspace where the training was deleted.
        training_name (str): The name of the training deleted.
        training_type (str): The type of the training deleted. builtin or custom.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "training",
                     "task_name": f"[{training_type}] {training_name}",
                     "action": "delete"})

def update_training(self, username, workspace, training_name, training_type):
    """
    Logs a training update event.

    Args:
        username (str): The user who updated the training.
        workspace (str): The workspace where the training was updated.
        training_name (str): The name of the training updated.
        training_type (str): The type of the training updated. builtin or custom.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "training",
                     "task_name": f"[{training_type}] {training_name}",
                     "action": "update"})