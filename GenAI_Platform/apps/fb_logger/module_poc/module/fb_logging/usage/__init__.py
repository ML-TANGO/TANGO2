# do nothing
def nono(self, username, workspace, image_name):
    """
    Logs an image creation event.

    Args:
        username (str): The user who created the image.
        workspace (str): The workspace where the image was created.
        image_name (str): The name of the image created.
    """
    self.usage(data={"user": username, "workspace": workspace, "task_name": image_name, "action": "create"})