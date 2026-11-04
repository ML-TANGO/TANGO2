def create_job(self, username, workspace, job_name, training_name):
    """
    Logs a job creation event.

    Args:
        username (str): The user who created the job.
        workspace (str): The workspace where the job was created.
        job_name (str): The name of the job created.
        training_name (str): The name of the parent training.
    """
    self.usage(data={"user": username, 
                     "workspace": workspace, 
                     "task": "job",
                     "task_name": f"{training_name} / {job_name}", 
                     "action": "create"})
    
def delete_job(self, username, workspace, job_name, training_name):
    """
    Logs a job deletion event.

    Args:
        username (str): The user who deleted the job.
        workspace (str): The workspace where the job was deleted.
        job_name (str): The name of the job deleted.
        training_name (str): The name of the parent training.
    """
    self.usage(data={"user": username, 
                     "workspace": workspace, 
                     "task": "job",
                     "task_name": f"{training_name} / {job_name}", 
                     "action": "delete"})