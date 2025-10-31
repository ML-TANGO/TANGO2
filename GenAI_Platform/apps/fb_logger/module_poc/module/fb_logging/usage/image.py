def create_image(self, username, workspace, image_name, create_method):
    """
    Logs an image creation event.

    Args:
        username (str): The user who created the image.
        workspace (str): The workspace where the image was created.
        image_name (str): The name of the image created.
        create_method (str): The method used to create the image.
    """
    self.usage(data={"user": username,
                     "workspace": workspace,
                     "task": "image",
                     "task_name": f"{create_method} / {image_name}",
                     "action": "create"})

def delete_image(self, username, workspace, image_name):
    """
    Logs an image deletion event.

    Args:
        username (str): The user who deleted the image.
        workspace (str): The workspace where the image was deleted.
        image_name (str): The name of the image deleted.
    """
    self.usage(data={"user": username, "workspace": workspace,
                     "task": "image", "task_name": image_name, "action": "delete"})

def update_image(self, username, workspace, image_name):
    """
    Logs an image update event.

    Args:
        username (str): The user who updated the image.
        workspace (str): The workspace where the image was updated.
        image_name (str): The name of the image updated.
    """
    self.usage(data={"user": username, "workspace": workspace,
                     "task": "image", "task_name": image_name, "action": "update"})

