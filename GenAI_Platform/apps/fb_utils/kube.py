from utils import common

class PodName():
    def __init__(self, workspace_name, item_name, item_type, sub_item_name=None, sub_flag=None, start_datetime : str = None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C |
        sub_item_name (str) (optional) : for unique. Job name, Hps name, or id
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        self.base_pod_name = "" # base name
        self.unique_pod_name = "" # [unique name] = [base name]-[sub-flag]
        self.container_name = "" # no hash [unique name]

        self.set_base_pod_name(workspace_name=workspace_name, item_name=item_name, sub_item_name=sub_item_name, item_type=item_type, start_datetime=start_datetime)
        self.set_unique_pod_name(base_pod_name=self.base_pod_name, sub_flag=sub_flag)
        self.set_container_name(workspace_name=workspace_name, item_name=item_name, item_type=item_type, sub_flag=sub_flag)


    def set_base_pod_name(self, workspace_name, item_name, item_type, sub_item_name=None, start_datetime : str = None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C |
        sub_item_name (str) (optional) : Job name, Hps name ...
        """
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if start_datetime:
            name = "{}-{}-{}-{}".format(name, item_name, item_type, start_datetime)
        if sub_item_name is not None:
            if not start_datetime:
                name = "{}-{}".format(name, sub_item_name)
            else:
                name = "{}-{}-{}".format(name, sub_item_name, start_datetime)
        base_pod_name = "{}".format(common.gen_pod_name_hash(name.replace("-","0")))
        self.base_pod_name =  base_pod_name

    def set_unique_pod_name(self, base_pod_name, sub_flag=None):
        """
        base_pod_name (str) : from create_base_pod_name(). (hash)
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        if sub_flag is None:
            self.unique_pod_name = "{}-{}".format(base_pod_name, 0)
        else:
            self.unique_pod_name = "{}-{}".format(base_pod_name, sub_flag)

    def set_container_name(self, workspace_name, item_name, item_type, sub_flag=None):
        """
        workspace_name (str) : workspace name
        item_name (str) : training | deployment
        item_type (str) : TRAINING_ITEM_A | TRAINING_ITEM_B | TRAINING_ITEM_C |
        sub_flag (str) (optional) : item id (training_tool_id, deployment_worker_id, group_index-training_index)..
        """
        name = "{}-{}-{}".format(workspace_name, item_name, item_type)
        if sub_flag is not None:
            name = "{}-{}".format(name, sub_flag)

        self.container_name = name

    def get_all(self):
        return self.base_pod_name, self.unique_pod_name, self.container_name

    def get_base_pod_name(self):
        return self.base_pod_name