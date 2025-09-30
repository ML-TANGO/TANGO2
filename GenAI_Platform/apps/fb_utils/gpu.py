import utils.common as common
import utils.kube as kube
from utils.kube import kube_data
from utils.TYPE import  DEPLOYMENT_TYPE #, TRAINING_TYPE
# import utils.db as db
import re
import os
import traceback
from utils.TYPE import *
import time
import datetime
from functools import wraps
from typing import List, Dict



def get_workspace_aval_gpu(workspace_id, start_datetime, end_datetime, guaranteed_gpu=1):
    try:
        workspace_list = db.get_workspace_list()
        guarantee_workspace_list = [ workspace for workspace in workspace_list if workspace["guaranteed_gpu"] == 1]
        not_guarantee_workspace_list = [ workspace for workspace in workspace_list if workspace["guaranteed_gpu"] == 0]

        res_count = kube.get_allocated_gpu_count(start_datetime=start_datetime, end_datetime=end_datetime, update_workspace_id=workspace_id
                                                , workspace_list=guarantee_workspace_list)

        gpu_total = res_count["resource_total"]
        gpu_total_used = res_count["alloc_total"]

        not_guarantee_max = 0
        if guaranteed_gpu == 1:
            not_guarantee_max = get_not_guaranteed_max_gpu_from_workspace_list(workspace_list=not_guarantee_workspace_list, update_workspace_id=workspace_id,
                                            start_datetime=start_datetime, end_datetime=end_datetime)

        return {"gpu_total_used":gpu_total_used, "gpu_total":gpu_total, "gpu_free":gpu_total-gpu_total_used-not_guarantee_max}
    except :
        traceback.print_exc()
        raise

def get_not_guaranteed_max_gpu_from_workspace_list(workspace_list, update_workspace_id=None, start_datetime=None, end_datetime=None):
    def within_rage_check(base_start_datetime_ts, base_end_datetime_ts, target_start_datetime_ts, target_end_datetime_ts):
        if ((base_start_datetime_ts <= target_start_datetime_ts and target_start_datetime_ts < base_end_datetime_ts)
            or (base_start_datetime_ts < target_end_datetime_ts and target_end_datetime_ts <= base_end_datetime_ts)
            or (base_start_datetime_ts <= target_start_datetime_ts and target_end_datetime_ts <= base_end_datetime_ts)
            or (base_start_datetime_ts >= target_start_datetime_ts and target_end_datetime_ts >= base_end_datetime_ts)):
            return True
        return False

    select_start_datetime_ts = common.date_str_to_timestamp(start_datetime)
    select_end_datetime_ts = common.date_str_to_timestamp(end_datetime)
    max_gpu = 0
    for workspace in workspace_list:
        # Update 시
        if workspace["id"] == update_workspace_id:
            continue

        workspace_start_datetime_ts = common.date_str_to_timestamp(workspace["start_datetime"])
        workspace_end_datetime_ts = common.date_str_to_timestamp(workspace["end_datetime"])

        if within_rage_check(workspace_start_datetime_ts, workspace_end_datetime_ts, select_start_datetime_ts, select_end_datetime_ts):
            total = int(workspace['gpu_deployment_total'])+int(workspace['gpu_training_total'])
            max_gpu = max(max_gpu, total)

    # print("TEST ", start_datetime, end_datetime, max_gpu)
    return max_gpu