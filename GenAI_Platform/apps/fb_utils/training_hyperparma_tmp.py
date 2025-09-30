import traceback
import json
from utils import settings
from utils import db
from utils.PATH import JF_TRAINING_HPS_LOG_DIR_NAME

def get_hyperparam_log_file_path(hps_id, workspace_name=None, training_name=None, log_type="jflog"):
    base_path = settings.JF_WS_DIR
    log_name = "{}.{}".format(hps_id, log_type)
    if workspace_name is None or training_name is None:
        res = db.get_hyperparamsearch(hps_id)
        workspace_name = res["workspace_name"]
        training_name = res["training_name"]

    log_path = "{base_path}/{workspace_name}/trainings/{training_name}/{default_hps_log_path}/{log_name}".format(
        base_path=base_path,
        workspace_name=workspace_name,
        training_name=training_name,
        default_hps_log_path=JF_TRAINING_HPS_LOG_DIR_NAME,
        log_name=log_name
        )
    return log_path

def get_hyperparam_log_sub_file_path(hps_id, workspace_name=None, training_name=None):
    base_path = settings.JF_WS_DIR
    if workspace_name is None or training_name is None:
        res = db.get_hyperparamsearch(hps_id=hps_id)
        workspace_name = res["workspace_name"]
        training_name = res["training_name"]

    log_path = "{base_path}/{workspace_name}/trainings/{training_name}/{default_hps_log_path}/{hps_id}".format(
        base_path=base_path,
        workspace_name=workspace_name,
        training_name=training_name,
        default_hps_log_path=JF_TRAINING_HPS_LOG_DIR_NAME,
        hps_id=hps_id
        )
    return log_path


def get_hyperparam_log_file_data(hps_id, workspace_name=None, training_name=None, log_type="jflog"):
    import time
    """
    Args :
        log_type(str): "json" - main log 로 n_iter 별 input, target 값 저장하는 로그 데이터  | "jflog"
    """
    log_item_list = []
    try:
        log_path = get_hyperparam_log_file_path(hps_id=hps_id, workspace_name=workspace_name, training_name=training_name, log_type=log_type)
        with open(log_path, "r") as j:
            while True:
                try:
                    iteration = next(j)
                except StopIteration:
                    break
                iteration = json.loads(iteration)
                log_item_list.append(iteration)
    except FileNotFoundError as fnf:
        pass
    except Exception as e:
        traceback.print_exc()
    return log_item_list


def get_hyperparam_num_of_last_log_item(log_item_list, current_hps_id):
    item_hps_id = []
    for log_item in log_item_list:
        item_hps_id.append(log_item.get("hps_id"))
    # print(len(log_item_list), len(item_hps_id), item_hps_id.count(current_hps_id))
    num_of_last_log_item = len(log_item_list) - item_hps_id.count(str(current_hps_id))

    return num_of_last_log_item
