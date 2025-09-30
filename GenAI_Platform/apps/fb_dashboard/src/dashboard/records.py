# from utils.resource import CustomResource, token_checker
# from flask_restplus import reqparse, Resource
# import utils.common as common

# # from werkzeug.datastructures import FileStorage
# import traceback
# import os
import re
from datetime import date
from datetime import datetime
from datetime import timedelta
import time
# from flask import request

# from restplus import api
# # import utils.db as db
# from utils import common
# from utils.resource import response
# import settings
# from itertools import groupby
# import utils.kube as kube
# from utils.kube import kube_data, get_gpu_total_count

# import json

# utc_offset = settings.UTC_OFFSET

timeformat_hms_regex = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s(\d{2}):(\d{2}):(\d{2})')
timeformat_hm_regex = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s(\d{2}):(\d{2})')
timeformat_h_regex = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s(\d{2})')
timeformat_ymd_regex = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

# """
# =================================================================================================================================
# records arguments settings START
# =================================================================================================================================
# """

# # Router Function
# parser = reqparse.RequestParser()

# ns = api.namespace('records', description='레코즈 관련 API')

# # workspace 목록
# records_summary_parser_get = api.parser()

# records_workspaces_parser_get = api.parser()
# records_workspaces_parser_get.add_argument('workspace_ids', required=False, type=str, location='args', help='워크스페이스 ID')
# records_workspaces_parser_get.add_argument('year', required=False, type=str, location='args', help="서비스 검색 연도")
# records_workspaces_parser_get.add_argument('months', required=False, type=str, location='args', help="서비스 검색 월")
# records_workspaces_parser_get.add_argument('size', required=False, default=None, type=int, location='args',
#                                            help='record history List Item Size')
# records_workspaces_parser_get.add_argument('page', required=False, default=None, type=int, location='args',
#                                            help='record history Page Number')
# records_workspaces_parser_get.add_argument('task', required=False, default=None, type=str, location='args',
#                                            help='record Task')
# records_workspaces_parser_get.add_argument('action', required=False, default=None, type=str, location='args',
#                                            help='record Action')
# records_workspaces_parser_get.add_argument('search_key', required=False, default=None, type=str, location='args',
#                                            help='record Search Key "name" or "user_name"... ')
# records_workspaces_parser_get.add_argument('search_value', required=False, default=None, type=str, location='args',
#                                            help='record Search Key "name" or "user_name"... ')
# records_workspaces_parser_get.add_argument('sort', required=False, default='time_stamp', type=str, location='args',
#                                            help='sort type')
# records_workspaces_parser_get.add_argument('order', required=False, default='desc', type=str, location='args',
#                                            help='sort order')

# records_instance_parser_get = api.parser()
# records_instance_parser_get.add_argument('workspace_id', required=False, type=str, location='args', help='워크스페이스 ID')
# records_instance_parser_get.add_argument('usergroup_id', required=False, type=int, location='args',
#                                          help='user group ID')
# records_instance_parser_get.add_argument('training_ids', required=False, type=str, location='args', help='트레이닝 ID')
# records_instance_parser_get.add_argument('year', required=False, type=str, location='args', help="서비스 검색 연도")
# records_instance_parser_get.add_argument('months', required=False, type=str, location='args', help="서비스 검색 월")
# records_instance_parser_get.add_argument('size', required=False, default=None, type=int, location='args',
#                                          help='record history List Item Size')
# records_instance_parser_get.add_argument('page', required=False, default=None, type=int, location='args',
#                                          help='record history Page Number')
# records_instance_parser_get.add_argument('type', required=False, default=None, type=str, location='args',
#                                          help='record Type "name" or "user_name"... ')
# records_instance_parser_get.add_argument('usage_type', required=False, default=None, type=str, location='args',
#                                          help='record Usage Type "name" or "user_name"... ')
# # records_instance_parser_get.add_argument('search_key', required=False, default=None, type=str, location='args', help='record Search Key "name" or "user_name"... ')
# # records_instance_parser_get.add_argument('search_value', required=False, default=None, type=str, location='args', help='record Search Key "name" or "user_name"... ')
# records_instance_parser_get.add_argument('searchKey', required=False, default=None, type=str, location='args',
#                                          help='record Search Key "name" or "user_name"... ')
# records_instance_parser_get.add_argument('keyword', required=False, default=None, type=str, location='args',
#                                          help='record Search Key "name" or "user_name"... ')

# records_storage_parser_get = api.parser()
# records_storage_parser_get.add_argument('workspace_id', required=False, type=str, location='args', help='워크스페이스 ID')
# records_storage_parser_get.add_argument('year', required=False, type=str, location='args', help="서비스 검색 연도")
# records_storage_parser_get.add_argument('months', required=False, type=str, location='args', help="서비스 검색 월")
# records_storage_parser_get.add_argument('size', required=False, default=None, type=int, location='args',
#                                         help='record history List Item Size')
# records_storage_parser_get.add_argument('page', required=False, default=None, type=int, location='args',
#                                         help='record history Page Number')

# records_userdata_daily_parser_get = api.parser()
# records_userdata_daily_parser_get.add_argument('user_id', required=False, default='', type=str, location='args',
#                                                help='유저 ID')
# records_userdata_daily_parser_get.add_argument('user_name', required=False, default='', type=str, location='args',
#                                                help="유저 Name")

# records_userdata_range_parser_get= api.parser()
# records_userdata_range_parser_get.add_argument('user_id', required=False, default='', type=str, location='args',
#                                                help='유저 ID')
# records_userdata_range_parser_get.add_argument('user_name', required=False, default='', type=str, location='args',
#                                                help="유저 Name"),
# records_userdata_range_parser_get.add_argument('end_point', required=False, default='', type=str, location='args',
#                                                help="끝점")
# records_userdata_range_parser_get.add_argument('starting_point', required=False, default="", type=str, location='args',
#                                                help="시작점")


# """
# =================================================================================================================================
# records arguments settings END
# =================================================================================================================================
# """

# """
# =================================================================================================================================
# Records Function START
# =================================================================================================================================
# """


# def _add_month(date_):
#     # date_에 1달을 추가함
#     if date_.month == 12: # 12월이니 1달 더하면 다음년으로 넘어감
#         return datetime(date_.year + 1, 1, 1)
#     else:
#         return datetime(date_.year, date_.month + 1, 1)


# def _add_day(date_):
#     # date_에 1일을 추가함
#     return date_ + timedelta(days=1)


# def _date_only(datetime_):
#     # datetime_에서 시간(시, 분, 초)를 제거하고 년, 월, 일만 있는 datetime을 return함
#     return datetime(datetime_.year, datetime_.month, datetime_.day)


# def _is_last_second_of_date(datetime_):
#     # 하루의 마지막 초인지 확인함 -> datetime_에 1초를 더한 값의 날짜가 datetime_의 날짜와 같지 않은지 확인함
#     return datetime_.day != (datetime_ + timedelta(seconds=1)).day


# def _group_by_key(data=None, group_key=None):
#     # data를 group_key 기준으로 정렬함
#     groups = []
#     uniquekeys = []
#     for k, g in groupby(sorted(data, key=lambda x: x[group_key]), lambda x: x[group_key]):
#         groups.append(list(g))
#         uniquekeys.append(k)
#     return {i: j for i, j in zip(uniquekeys, groups)}

# '''
# def _set_search_dates(year=None, months=None):
# 	dates = None
# 	if year is not None:
# 		if months is not None:
# 			dates = []
# 			for month in months.split(','):
# 				dates.append(datetime(
# 					*map(int, timeformat_ymd_regex.match(year + '-' + "{:02d}".format(int(month)) + "-01").groups())))

# 		else:
# 			dates = []
# 			for i in range(12):
# 				dates.append(datetime(
# 					*map(int, timeformat_ymd_regex.match(year + '-' + "{:02d}".format(i + 1) + "-01").groups())))
# 	else:
# 		if months is not None:
# 			dates = []
# 			for month in months.split(','):
# 				dates.append(datetime(
# 					*map(int, timeformat_ymd_regex.match('2013' + '-' + "{:02d}".format(int(month)) + "-01").groups())))

# 		else:
# 			dates = []
# 			for i in range(12):
# 				dates.append(datetime(
# 					*map(int, timeformat_ymd_regex.match('2013' + '-' + "{:02d}".format(i + 1) + "-01").groups())))
# 	return dates

# '''
# def _set_search_dates(year=None, months=None):
#     # 정한 연도와 월을 기준으로 리스트를 만들어서 return함
#     # 예: [datetime.datetime(2022, 1, 1, 0, 0)]
#     dates = None
#     if year is not None:
#         if months is not None:
#             dates = []
#             for month in months.split(','):
#                 dates.append(datetime(
#                     # *map(int, timeformat_ymd_regex.match("2013" + '-' + "{:02d}".format(int(month)) + "-01").groups())))
#                     *map(int, timeformat_ymd_regex.match(year + '-' + "{:02d}".format(int(month)) + "-01").groups())))

#         else:
#             dates = []
#             for i in range(12):
#                 dates.append(datetime(
#                     *map(int, timeformat_ymd_regex.match(year + '-' + "{:02d}".format(i + 1) + "-01").groups())))
#     return dates

# """
#     NOTE:
#         각 워크스페이스의 워크스페이스 이름, 상태, 가동시간, 사용 기간, CPU 가동시간, GPU 할당량 정보,
#         전체 GPU 대비 현재 사용중인 워크스페이스의 GPU 사용률
# """
# def get_records_summary():
#     """
#     Description: Get workspaces information for admin records summary page.
#     Returns:
#         response:
#             - success
#                 {
#                     status : 0,
#                     usages : a list of workspaces information
#                 }

#             - fail
#                 {
#                     status : 0,
#                     message : string
#                 }
#     """
#     try:
#         workspaces = db.get_records_workspace_summary_usage()
#         records_of_workspaces = db.get_records_summary_usage_activation_time()
#         records_of_job = db.get_records_summary_usage_uptime_of_job_unified()
#         records_of_jupyter = db.get_records_summary_usage_uptime_of_jupyter_unified()
#         records_of_deployment = db.get_records_summary_usage_uptime_of_deployment_unified()
#         records_of_hyperparamsearch = db.get_records_summary_usage_uptime_of_hyperparamsearch_unified()

#         records_of_workspaces_by_ids = _group_by_key(data=records_of_workspaces, group_key="id")
#         job_by_worksapce_ids = _group_by_key(data=records_of_job, group_key="workspace_id")
#         jupyter_by_worksapce_ids = _group_by_key(data=records_of_jupyter, group_key="workspace_id")
#         deployment_by_worksapce_ids = _group_by_key(data=records_of_deployment, group_key="workspace_id")
#         hyperparamsearch_by_worksapce_ids = _group_by_key(data=records_of_hyperparamsearch, group_key="workspace_id")

#         records_usage_list = [job_by_worksapce_ids, jupyter_by_worksapce_ids, deployment_by_worksapce_ids,
#                               hyperparamsearch_by_worksapce_ids]
#         usages = []
#         for workspace in workspaces:
#             usage = {}
#             ws_id = workspace["id"]

#             uptime_of_cpu = timedelta(0)
#             for records_usage in records_usage_list:
#                 ws_records_usage = records_usage.get(ws_id) or []
#                 uptime_of_cpu += calculate_instance_uptime(ws_records_usage)["cpu"]  # 기록 CPU 인스턴스들의 사용시간

#             cur_ws_records = records_of_workspaces_by_ids.get(ws_id) or []
#             total_active_datetime = calculate_total_activation_time(records=cur_ws_records)  # 해당 워크스페이스의 가동시간

#             usage["status"] = get_current_status_by_time(
#                 start_time=workspace["start_datetime"],
#                 end_time=workspace["end_datetime"]
#             )

#             allocated_gpu_count = workspace['gpu_training_total'] + workspace['gpu_deployment_total']
#             currnet_workspace_gpu_info = kube.get_workspace_gpu_count(workspace_id=ws_id, workspace_list=workspaces)
#             active_gpu_count = currnet_workspace_gpu_info['training_used'] + currnet_workspace_gpu_info[
#                 'deployment_used']
#             usage['usage_rate'] = 0 if active_gpu_count == 0 else (active_gpu_count / allocated_gpu_count) * 100

#             usage['workspace_name'] = workspace['name']
#             usage['create_datetime'] = str(workspace['create_datetime'])
#             usage['start_datetime'] = str(workspace['start_datetime'])
#             usage['end_datetime'] = str(workspace['end_datetime'])
#             usage['activation_time'] = str(total_active_datetime.total_seconds())
#             usage['uptime_of_cpu'] = str((uptime_of_cpu).total_seconds())
#             usage['guaranteed_gpu'] = workspace['guaranteed_gpu']
#             usage['gpu_allocations'] = allocated_gpu_count
#             usage['active_gpu_count'] = active_gpu_count
#             # usage['usage_storage'] = 0 # storage 다 더하자 (image, dataset, training, deployment)
#             usages.append(usage)

#         return response(status=1, result=usages)

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records summary Error")

# """
#     NOTE:
#         워크스페이스는 GPU 할당만 가능하다면 시작, 종료 날짜 변경에 제약이 없음
#         시작, 종료 날짜로 GROUP BY 쿼리의 워크스페이스의 기록 rows에서 실제 가동한 시간 계산
# """
# def calculate_total_activation_time(records):
#     """
#     Description: Workspace total activation time.
#     Args :
#         records(dictionary): {index, record}
#     Returns:
#         timedelta:
#             - success
#                 total activation time
#             - fail
#                 timedelta(0)
#     """
#     if len(records) == 0:
#         return timedelta(0)

#     total_active_datetime = timedelta(0)
#     last_index = len(records) - 1
#     for index, record in enumerate(records):
#         if index == last_index:
#             next_log_time = (datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
#         else:
#             next_log_time = records[index + 1]['log_create_datetime']

#         start_time, end_time = check_active_start_end_time(
#             record['start_datetime'],
#             record['end_datetime'],
#             record['log_create_datetime'],
#             next_log_time
#         )
#         if start_time is None or end_time is None:
#             continue
#         total_active_datetime += end_time - start_time
#     return total_active_datetime


# def calculate_instance_uptime(instances, dates=None):
#     """Calculate cpu and gpu total usage time(uptime).

#     :param instances: a list of instance from record tables
#     :param dates: does not add uptime if instance is out of dates ranges
#     :return: a dict of cpu and gpu uptime
#     """
#     total_uptime_cpu = timedelta(0)
#     total_uptime_gpu = timedelta(0)

#     def _add_uptime(uptime, gpu_count, total_uptime_cpu, total_uptime_gpu):
#         """Add uptime to uptime of gpu if gpu is used, otherwise add to uptime of cpu"""
#         if gpu_count is None:
#             total_uptime_cpu += uptime
#         elif gpu_count is not None:
#             total_uptime_gpu += uptime * 1  # TODO 충북 요청 gpu_count

#         return total_uptime_cpu, total_uptime_gpu

#     if instances is not None:
#         for instance in instances:
#             gpu_count = None
#             if instance["usage_type"] in ["job", "deployment", "hyperparamsearch"]:
#                 gpu_count = None if instance["gpu_count"] == 0 else instance["gpu_count"]
#             elif instance["usage_type"] == "jupyter":  # only editor uses cpu
#                 gpu_count = None if instance["editor"] == "True" else 1

#             start_datetime, end_datetime = convert_start_and_end_time_to_datetime_format(
#                 start=instance['start_datetime'],
#                 end=instance['end_datetime']
#             )

#             if dates is None:  # 검색 필터에 월을 선택하지 않은 경우
#                 activation_time = end_datetime - start_datetime
#                 total_uptime_cpu, total_uptime_gpu = _add_uptime(activation_time, gpu_count, total_uptime_cpu,
#                                                                  total_uptime_gpu)
#             else:  # 검색 필터에 월을 선택한 경우
#                 for date in dates:

#                     # 선택된 월의 시작, 끝 선언
#                     period_start = date
#                     period_end = _add_month(date) - timedelta(seconds=1)

#                     # check if instance is overlapped with the given period(dates=months)
#                     if period_start < end_datetime and period_end > start_datetime:  # 선택된 월에 해당 인스턴스가 실행했는지 확인
#                         # 선택된 월 안에서만 uptime 계산
#                         activation_start_time = start_datetime if start_datetime > period_start else period_start
#                         activation_end_time = end_datetime if end_datetime < period_end else period_end

#                         activation_time = activation_end_time - activation_start_time
#                         total_uptime_cpu, total_uptime_gpu = _add_uptime(activation_time, gpu_count, total_uptime_cpu,
#                                                                          total_uptime_gpu)

#     return {
#         "cpu": total_uptime_cpu,
#         "gpu": total_uptime_gpu
#     }


# def get_records_workspaces(workspace_ids, year, months, size, page, task, action, search_key, search_value, sort_key,
#                            sort_value):
#     """Get workspaces information for admin records workspace page from history table.

#     :return: a list of workspaces information with action history

#     NOTE:
#         History 테이블에 저장된 rows
#         워크스페이스가 삭제되면 해당 워크스페이스 rows 는 다 삭제됨(삭제된다는 history도 없음)
#     """
#     try:
#         records_workspaces_info = []
#         res = db.get_records_workspaces_info(workspace_ids, task, action, search_key, search_value, sort_key,
#                                              sort_value)

#         for _res in res:
#             _year, _month, *_ = _res['datetime'].split('-')
#             if year is not None and not _year == year:
#                 continue
#             if months is not None and not str(int(_month)) in months.split(','):
#                 continue

#             info = {}
#             info['time_stamp'] = _res['datetime']
#             info['workspace'] = _res['workspace_name']
#             info['task'] = _res['task']
#             info['action'] = _res['action']
#             info['task_name'] = _res['task_name']
#             info['update_details'] = _res['update_details']
#             info['user'] = _res['user']

#             records_workspaces_info.append(info)

#         if page is None or size is None:
#             return response(status=1, result={"list": records_workspaces_info, "total": len(records_workspaces_info)})
#         else:
#             return response(status=1, result={"list": records_workspaces_info[(page - 1) * size:page * size],
#                                               "total": len(records_workspaces_info)})

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records Error")


# def get_workspace_active_period(records=None, dates=None):
#     """Workspace has a new period when allocated gpu count changed or
#     when there is a interval between start and end time of workspaces

#     :param records: a list of records from record_workspace db table
#     :param dates: check if workspace period is out of the given date ranges
#     :return: a list of workspace period info with allocated gpu count

#     NOTE:
#         워크스페이스 가동 기간 설정
#         - 할당된 GPU 수가 변경되면 새로운 기간으로 구분함
#         - 할단된 GPU 수가 동일할때 중간에 사용하지 않는 기간이 있다면 서로 구분함
#     """

#     active_period = []
#     prev_gpu_training = -1  # to check changes of allocated gpu count between a previous workspace and a next one
#     prev_gpu_deployment = -1

#     for record in records:
#         if record['start_datetime'] is None or record[
#             'end_datetime'] is None:  # worksapce must have start_datetime and end_datetime
#             continue

#         # record_workspace start/end datetime timestamp foramt: %Y-%m-%d %H:%M // other record's format "%Y-%m-%d %H:%M:%S"
#         if len(record['start_datetime']) == 16:
#             record['start_datetime'] += ":00"

#         if len(record['end_datetime']) == 16:
#             record['end_datetime'] += ":00"

#         period_start_time = record['start_datetime']
#         period_end_time = record['end_datetime']
#         cur_gpu_training = record['gpu_training_total']
#         cur_gpu_deployment = record['gpu_deployment_total']

#         ws_info = {
#             "for_training": cur_gpu_training,
#             "for_deployment": cur_gpu_deployment,
#             "guaranteed_gpu": record["guaranteed_gpu"],
#         }

#         if not active_period:  # first record
#             ws_info["start_datetime"] = period_start_time
#             ws_info["end_datetime"] = period_end_time
#             ws_info["period"] = period_start_time + " ~ " + period_end_time
#             active_period.append(ws_info)
#         else:
#             prev_start, prev_end = active_period[-1]["period"].split(" ~ ")

#             # 이전 기록과 할당된 GPU 수가 동일하므로 기간만 늘려줌
#             if prev_gpu_training == cur_gpu_training and prev_gpu_deployment == cur_gpu_deployment:
#                 if period_start_time < prev_end:  # ws period has been extended
#                     active_period[-1]["period"] = prev_start + " ~ " + period_end_time
#                     active_period[-1]["end_datetime"] = period_end_time

#                 elif prev_end < period_start_time:  # different ws period
#                     ws_info["start_datetime"] = period_start_time
#                     ws_info["end_datetime"] = period_end_time
#                     ws_info["period"] = period_start_time + " ~ " + period_end_time
#                     active_period.append(ws_info)
#             else:  # 할당된 GPU 수가 변경되어 새로운 기간 추가
#                 if period_start_time < prev_end:  # gpu count changed when ws was active
#                     changed_time = record["log_create_datetime"]
#                     active_period[-1]["period"] = prev_start + " ~ " + changed_time
#                     active_period[-1]["end_datetime"] = changed_time

#                     ws_info["start_datetime"] = changed_time
#                     ws_info["end_datetime"] = period_end_time
#                     ws_info["period"] = changed_time + " ~ " + period_end_time
#                     active_period.append(ws_info)

#                 elif prev_end <= period_start_time:  # different ws period
#                     ws_info["start_datetime"] = period_start_time
#                     ws_info["end_datetime"] = period_end_time
#                     ws_info["period"] = period_start_time + " ~ " + period_end_time
#                     active_period.append(ws_info)

#         prev_gpu_training = cur_gpu_training
#         prev_gpu_deployment = cur_gpu_deployment

#     if dates is None:
#         return active_period
#     else:
#         active_period_in_dates = []
#         for period in active_period:
#             for date in dates:
#                 s_date = date
#                 e_date = _add_month(s_date) - timedelta(seconds=1)
#                 ws_start, ws_end = convert_start_and_end_time_to_datetime_format(
#                     start=period["start_datetime"],
#                     end=period["end_datetime"],
#                     add_hours=utc_offset)
#                 if s_date < ws_end and ws_start < e_date:
#                     active_period_in_dates.append(period)
#                     break
#         return active_period_in_dates

# """
#     NOTE:
#         쥬피터-에디터인 경우/ GPU 사용 수가 0인 경우 CPU 사용
# """
# def _separate_by_type(instances):
#     """
#     Description: To separate into two categories(cpu, gpu) by usage type
#     (job, jupyter, deployment and hyperparamsearch) and gpu count.
#     Args :
#         instances(list): list of instances
#     Returns:
#         dict:
#             - success
#                 dict of cpu, gpu instances
#             - fail
#                 dict of cpu, gpu instances(cpu_instances and gpu_instances are empty)
#     """
#     cpu_instances = []
#     gpu_instances = []

#     for instance in instances:
#         if instance["usage_type"] == "jupyter":
#             if instance['editor'] == "True":
#                 instance['gpu_count'] = 0
#                 cpu_instances.append(instance)
#             else:
#                 instance['gpu_count'] = 1
#                 gpu_instances.append(instance)
#         else:
#             if instance['gpu_count'] == 0:
#                 cpu_instances.append(instance)
#             else:
#                 gpu_instances.append(instance)

#     return {"cpu": cpu_instances, "gpu": gpu_instances}
# # 출력 예제
# # {'cpu': [], 'gpu': [{'id': 2491, 'name': '11', 'workspace_id': 5, 'workspace_name': 'aaai-ws', 'training_id': '99', 'job_group_index': '0', 'training_name': 'test-ray', 'gpu_count': 1, 'start_datetime': datetime.datetime(2022, 2, 17, 9, 42, 8), 'end_datetime': datetime.datetime(2022, 2, 17, 9, 42, 17), 'configurations': 'NVIDIA GeForce GTX 1080 Ti', 'training_id_if_exists': '99', 'usage_type': 'job'}, {'id': 2896, 'name': 'softteacher', 'workspace_id': 5, 'training_id': 'null', '.training_id': 'null', 'type': 'built-in', 'gpu_count': 1, 'start_datetime': datetime.datetime(2022, 2, 7, 8, 18, 30), 'end_datetime': datetime.datetime(2022, 2, 7, 8, 23, 1), 'log_create_datetime': datetime.datetime(2022, 2, 7, 8, 18, 30), 'configurations': 'NVIDIA GeForce GTX 1080 Ti', 'training_id_if_exists': 'null', 'workspace_name': 'aaai-ws', 'usage_type': 'deployment'}, {'id': 2897, 'name': 'softteacher', 'workspace_id': 5, 'training_id': 'null', '.training_id': 'null', 'type': 'built-in', 'gpu_count': 1, 'start_datetime': datetime.datetime(2022, 2, 7, 8, 23, 22), 'end_datetime': datetime.datetime(2022, 2, 7, 8, 36, 27), 'log_create_datetime': datetime.datetime(2022, 2, 7, 8, 23, 22), 'configurations': 'NVIDIA GeForce GTX 1080 Ti', 'training_id_if_exists': 'null', 'workspace_name': 'aaai-ws', 'usage_type': 'deployment'}, {'id': 2898, 'name': 'poseest-hrnet', 'workspace_id': 5, 'training_id': 'null', '.training_id': 'null', 'type': 'built-in', 'gpu_count': 1, 'start_datetime': datetime.datetime(2022, 2, 7, 8, 36, 37), 'end_datetime': datetime.datetime(2022, 2, 17, 10, 6, 22), 'log_create_datetime': datetime.datetime(2022, 2, 7, 8, 36, 37), 'configurations': 'NVIDIA GeForce GTX 1080 Ti', 'training_id_if_exists': 'null', 'workspace_name': 'aaai-ws', 'usage_type': 'deployment'}, {'id': 2901, 'name': '1111', 'workspace_id': 5, 'training_id': 'null', '.training_id': 'null', 'type': 'built-in', 'gpu_count': 1, 'start_datetime': datetime.datetime(2022, 2, 17, 10, 6, 42), 'end_datetime': datetime.datetime(2022, 2, 28, 14, 59, 1), 'log_create_datetime': datetime.datetime(2022, 2, 17, 10, 6, 42), 'configurations': 'NVIDIA GeForce GTX 1080 Ti', 'training_id_if_exists': 'null', 'workspace_name': 'aaai-ws', 'usage_type': 'deployment'}]}

# def _set_cpu_daily_usage(instances, months_date=None):
#     """Set daily cpu usage with given months.

#     :param months_date: check if instance is out of the given date ranges
#     :return: a dict of cpu usage count with timeline
#     """
#     cpu_daily_usage = {}

#     def _set_cpu_count_by_date(daily_cpu_count, start_datetime, end_datetime):
#         """divide into daily usage when start date and end date are different."""
#         start_date = _date_only(start_datetime)
#         end_date = _date_only(end_datetime)
#         get_all_workspace_gpu_usage
#         if start_date == end_date:
#             if daily_cpu_count.get(start_date) is None:
#                 daily_cpu_count[start_date] = 1
#             else:
#                 daily_cpu_count[start_date] += 1

#         elif start_date < end_date:
#             while start_date <= end_date:
#                 if daily_cpu_count.get(start_date) is None:
#                     daily_cpu_count[start_date] = 1
#                 else:
#                     daily_cpu_count[start_date] += 1
#                 start_date += timedelta(days=1)

#         return daily_cpu_count

#     for instance in instances:
#         start_datetime, end_datetime = convert_start_and_end_time_to_datetime_format(
#             start=instance['start_datetime'],
#             end=instance['end_datetime'],
#             add_hours=utc_offset
#         )

#         if months_date is not None:
#             for date in months_date:
#                 cur = start_datetime if date < start_datetime else date
#                 end = end_datetime if end_datetime < _add_month(date) else _add_month(date)
#                 cpu_daily_usage = _set_cpu_count_by_date(cpu_daily_usage, cur, end)
#         else:
#             cpu_daily_usage = _set_cpu_count_by_date(cpu_daily_usage, start_datetime, end_datetime)
#     return cpu_daily_usage


# def _set_gpu_daily_usage(instances, months_date=None, search_by_dates=False):
#     """Set daily gpu usage with given months.

#     :param months_date: check if instance is out of the given date ranges
#     :return: a dict of gpu usage count with timeline
#     """
#     gpu_daily_usage = {}

#     if search_by_dates:
#         # gpu_usage_by_second = _calculate_gpu_count_from_overlap_usage_by_second(instances)
#         pass

#     # 각 인스턴스들의 날짜별 시작, 종료 시간 계산 및 gpu 수 체크
#     # 특정 월의 경우 해당 월의 범위를 넘어가면 자름
#     for instance in instances:
#         start_datetime, end_datetime = convert_start_and_end_time_to_datetime_format(
#             start=instance['start_datetime'],
#             end=instance['end_datetime'],
#             add_hours=utc_offset
#         )

#         if months_date is not None:
#             for date in months_date:
#                 cur = start_datetime if date < start_datetime else date
#                 end = end_datetime if end_datetime < _add_month(date) else _add_month(date)
#                 gpu_daily_usage = _set_gpu_count_by_date(gpu_daily_usage, cur, end, instance['gpu_count'])
#         else:
#             gpu_daily_usage = _set_gpu_count_by_date(gpu_daily_usage, start_datetime, end_datetime,
#                                                      instance['gpu_count'])

#     # 날짜별로 겹치는 인스턴스들을 체크 후 사용 구간별 gpu 사용 수 계산
#     gpu_daily_usage = _calculate_gpu_count_from_overlap_usage(gpu_daily_usage)

#     return gpu_daily_usage


# def _calculate_gpu_count_from_overlap_usage(gpu_daily_usage):
#     gpu_count_daily_usage = {}

#     # 날짜별 계산
#     for date, date_usages in gpu_daily_usage.items():
#         sorted_date_usages = sorted(date_usages, key=(lambda x: x["start"]))
#         timeline_list = set([])

#         if gpu_count_daily_usage.get("date") is None:
#             gpu_count_daily_usage[date] = []

#         # 시작, 끝 시간을 기간(구간)이 아닌 gpu 사용 변화 시점으로 보고 계산
#         for date_usage in sorted_date_usages:
#             timeline_list.add(date_usage["start"])
#             timeline_list.add(date_usage["end"])

#         if len(timeline_list) > 0:
#             timeline_list.add(date)  # to check between 00h:00m:00s and first timeline of the date
#             timeline_list = sorted(timeline_list)

#             last_index = len(timeline_list) - 1
#             for i, timeline in enumerate(timeline_list):
#                 count = 0
#                 cur_timeline = timeline  ## 현재 변화시점

#                 ## 다음 변화시점
#                 if i == last_index:  # 그날의 마지막 gpu 변화 시점
#                     if _is_last_second_of_date(timeline):  # 23:59:99 - no need to check
#                         break
#                     else:
#                         next_timeline = date + timedelta(days=1) - timedelta(seconds=1)
#                 else:
#                     next_timeline = timeline_list[i + 1]

#                 ## 현재, 다음 변화 사이 gpu 사용량 계산
#                 for usage in sorted_date_usages:  # period = cur_timeline ~ next_timeline // usage = usage["start"] ~ usage["end"]
#                     if next_timeline <= usage["start"]:
#                         break
#                     elif usage["start"] < next_timeline and cur_timeline < usage["end"]:
#                         count += usage["count"]
#                 if count > 0:
#                     gpu_count_daily_usage[date].append({
#                         "start": cur_timeline,
#                         "end": next_timeline,
#                         "count": count
#                     })

#     return gpu_count_daily_usage


# # 현재 기획에는 없는 기능
# # def _calculate_gpu_count_from_overlap_usage_by_second(instances):
# #     timeline_list = set([])
# #     timeline_by_second = []

# #     sorted_instances = sorted(instances, key=(lambda x:x["start_datetime"]))
# #     instance_usages = []
# #     for instance in sorted_instances:
# #         start, end = convert_start_and_end_time_to_datetime_format(
# #             start=instance['start_datetime'],
# #             end=instance['end_datetime'],
# #             add_hours=utc_offset
# #         )

# #         timeline_list.add(start)
# #         timeline_list.add(end)
# #         instance_usages.append({
# #             "start": start,
# #             "end": end,
# #             "_count": instance["gpu_count"]
# #         })

# #     if len(timeline_list) > 0:
# #         timeline_list = sorted(timeline_list)
# #         for i, timeline in enumerate(timeline_list[:-1]):
# #             count = 0
# #             cur_timeline = timeline
# #             next_timeline = timeline_list[i+1]

# #             for usage in instance_usages:
# #                 if next_timeline <= usage["start"]:
# #                     break
# #                 elif cur_timeline <= usage["start"] and usage["start"] < next_timeline:
# #                     count += usage["_count"]
# #                 elif usage["start"] <= cur_timeline and cur_timeline < usage["end"]:
# #                     count += usage["_count"]
# #             timeline_by_second.append({
# #                 "start": cur_timeline,
# #                 "end": next_timeline,
# #                 "count": count
# #             })

# #     return timeline_by_second


# def _set_gpu_count_by_date(daily_gpu_count, start_datetime, end_datetime, count):
#     """
#     NOTE: 시작, 끝날짜 사이 GPU 수 계산
#     """
#     start_date = _date_only(start_datetime)
#     end_date = _date_only(end_datetime)

#     if start_date == end_date:
#         if daily_gpu_count.get(start_date) is None:
#             daily_gpu_count[start_date] = []
#         daily_gpu_count[start_date].append({
#             'start': start_datetime,
#             'end': end_datetime,
#             'count': count
#         })

#     elif start_date < end_date:
#         cur_date = start_date

#         while cur_date <= end_date:
#             usage_info = {}
#             if daily_gpu_count.get(cur_date) is None:
#                 daily_gpu_count[cur_date] = []

#             if cur_date == start_date:
#                 usage_info = {
#                     'start': start_datetime,
#                     'end': start_date + timedelta(days=1) - timedelta(seconds=1),
#                     'count': count
#                 }
#             elif start_date < cur_date and cur_date < end_date:
#                 usage_info = {
#                     'start': cur_date,
#                     'end': cur_date + timedelta(days=1) - timedelta(seconds=1),
#                     'count': count
#                 }
#             elif cur_date == end_date:
#                 usage_info = {
#                     'start': end_date,
#                     'end': end_datetime,
#                     'count': count
#                 }
#             if usage_info:
#                 daily_gpu_count[cur_date].append(usage_info)
#             cur_date += timedelta(days=1)

#     return daily_gpu_count


# def get_record_period_of_available_gpu_count():
#     """Return a list of periods with available gpu count.

#     NOTE:
#         과거~현재 사용가능 GPU 수 기록
#     """
#     timeline_available_gpu = db.get_records_of_available_gpu_count()
#     available_gpu_period = []
#     for index, available_gpu_info in enumerate(timeline_available_gpu[:-1]): # o(kn) k being n - 1
#         start = available_gpu_info["update_datetime"]
#         end = timeline_available_gpu[index + 1]["update_datetime"]
#         start_datetime, end_datetime = convert_start_and_end_time_to_datetime_format(
#             start=start,
#             end=end,
#             add_hours=utc_offset
#         )
#         available_gpu_period.append({
#             "count": available_gpu_info["count"],
#             "start": start_datetime,
#             "end": end_datetime
#         })
#     last_variable = timeline_available_gpu[len(timeline_available_gpu) - 1] # o(1)
#     last_start_datetime, last_end_datetime = convert_start_and_end_time_to_datetime_format(
#         start=last_variable["update_datetime"],
#         end=None,
#         add_hours=utc_offset
#     )
#     available_gpu_period.append({"count":last_variable["count"],"start":last_start_datetime,"end":last_end_datetime})
#     return available_gpu_period

# def get_available_gpu_count_in_period(start, end):
#     """Return available_gpu_count in between given start/end time"""
#     record_period_of_available_gpu_count = get_record_period_of_available_gpu_count()
#     count = None

#     for period in reversed(record_period_of_available_gpu_count): # sql 쿼리가 asc이므로 뒤에서 부터
#         if period['start'] < end and period['end'] > start:
#             count = period['count']  # return period['count'] # 일치하는 거중 가장 나중의 count를 기준으로
#             break # 나중의 count중 일치할때 break
#     # if count is None:
#     #     # print('Admin dashboard - Available gpu count info is wrong')
#     #     pass
#     return count

def get_all_workspace_gpu_usage(days=31):
    """For gpu usage graph in Admin Dashboard page.

    :param days: to set a date range for gpu usage graph
    :return: list of gpu usage with timeline

    NOTE:
        DB내에 저장 된 특정 기간 동안의 GPU 인스턴스의 날짜별 사용량을 return함
    """
    toReturn = list()
    try:
        records_gpu = db.get_records_of_gpu_usage()[:days]
        for record_gpu in records_gpu:
            toAppend = dict()
            toAppend['used_gpu'] = record_gpu['used']
            toAppend['total_gpu'] = record_gpu['total']
            toAppend['date'] = record_gpu['DATE(record_datetime)'].strftime("%Y-%m-%d")
            if toAppend['total_gpu'] == 0:
                toAppend['usage'] = 0
            else:
                toAppend['usage'] = round((toAppend['used_gpu'] / toAppend['total_gpu'] ) * 100)
            toAppend['usage_gpu'] = toAppend['usage']
            toReturn.append(toAppend)
        return toReturn
    except:
        traceback.print_exc()
        return toReturn

def get_workspace_gpu_usage(workspace_id, days=31):
    """For gpu usage graph in User Dashboard page.

    :param workspace_id: get the workspace info with the given id
    :param days: to set a date range for gpu usage graph
    :return: list of gpu usage with timeline
    """
    toReturn = list()
    try:
        records_gpu = db.get_records_of_gpu_usage(workspace=str(workspace_id))[:days]
        for record_gpu in records_gpu:
            toAppend = dict()
            toAppend['used_gpu'] = record_gpu['used']
            toAppend['total_gpu'] = record_gpu['total']
            toAppend['date'] = record_gpu['DATE(record_datetime)'].strftime("%Y-%m-%d")
            if toAppend['total_gpu'] == 0:
                toAppend['usage'] = 0
            else:
                toAppend['usage'] = round((toAppend['used_gpu'] / toAppend['total_gpu'] ) * 100)
            toAppend['usage_gpu'] = toAppend['usage']
            toReturn.append(toAppend)
        return toReturn
    except:
        traceback.print_exc()
        return toReturn

# # 향후 필요, 현재 필요 X
def get_workspace_gpu_usage_10_mins(workspace_id, cutoff=72):
    toReturn = list()
    try:
        records_gpu = db.get_records_of_detailed_gpu_usage(workspace=str(workspace_id),offset=cutoff)
        for record_gpu in records_gpu:
            toAppend = dict()
            toAppend['used_gpu'] = record_gpu['used']
            toAppend['total_gpu'] = record_gpu['total']
            toAppend['date'] = record_gpu['record_datetime'].strftime("%Y-%m-%d %H:%M")
            if record_gpu['usage'] is not None:
                toAppend['usage'] = record_gpu['usage']
            else:
                toAppend['usage'] = 0
            toReturn.append(toAppend)
        return toReturn
    except:
        traceback.print_exc()
        return toReturn

# def record_gpu_usage():
#     """ Record GPU usage
#     """
#     used_gpu_count = 0
#     try:
#         ws_gpu_stat_dict = kube.get_workspace_gpu_count(workspace_list=db.get_workspace_list())
#         for ws_id, value in ws_gpu_stat_dict.items():
#             ws_gpu_used = value['training_used'] + value['deployment_used']
#             used_gpu_count = used_gpu_count + ws_gpu_used
#             ws_gpu_total = value['training_total'] + value['deployment_total']
#             db.record_gpu_record(ws_gpu_used, ws_gpu_total,  ws_id)
#         db.record_gpu_record(used_gpu_count, get_gpu_total_count(kube_data.get_node_list()), 'ALL')
#     except:
#         print("WS GPU STAT RECORD FAILED")
#     return used_gpu_count

# def update_gpu_usage(past_used_gpu_count = 0):
#     """ Update GPU usage
#     """
#     used_gpu_count = 0
#     try:
#         all_gpu_count = kube.get_workspace_gpu_count()
#         dict_gpu_count = {}
#         for ws_id, value in all_gpu_count.items():
#             ws_gpu_used = value['training_used'] + value['deployment_used']
#             used_gpu_count = used_gpu_count + ws_gpu_used
#             dict_gpu_count[ws_id] = ws_gpu_used
#         if past_used_gpu_count >= used_gpu_count:
#             return past_used_gpu_count
#         dict_gpu_count['ALL'] = used_gpu_count
#         db.update_gpu_records(dict_gpu_count)
#     except:
#         print("WS GPU STAT UPDATE FAILED")
#     return used_gpu_count


# def _get_instances_info(workspace_id=None, user_list=None, training_ids=None,
#                         instance_type=None, usage_type=None,
#                         dates=None, search_key=None, search_value=None,
#                         only_records=False, only_instance_by_type=False):
#     """Return instances information.

#     :param workspace_id: get instances that belong to the given workspace id
#     :param user_list:  get instances that belong to users in given user list
#     :param training_ids:  get instances that belong to training_id in given training_ids
#     :param instance_type:  get instances by instance type(cpu/gpu)
#     :param usage_type:  get instances by usage type(job/jupyter/deployment/hyperparamsearch)
#     :param dates: get instances that are in given date ranges(years, months)
#     :param search_key:  get instances by search key(workspace, training, job_deploymnet)
#     :param search_value: get instances by search value with search key
#     :param only_records: return only records for admin records instances history table if True
#     :param only_instance_by_type: return only instances for dashboard page if True
#     :return: a dict of instances, uptime_cpu/gpu, records_of_cpu/gpu, records_of_cpu/gpu_count, instances_cpu/gpu
#     """

#     instances = []
#     instance_search_kwargs = {
#         "workspace_id": workspace_id,
#         "user_list": user_list,
#         "search_key": search_key,
#         "search_value": search_value,
#     }

#     # 사용 타입별 인스턴스 사용 기록
#     if usage_type == "job":
#         instances = db.get_records_instance_uptime_of_job_unified(**instance_search_kwargs)
#     elif usage_type == "jupyter":
#         instances = db.get_records_instance_uptime_of_jupyter_unified(**instance_search_kwargs)
#     elif usage_type == "editor":
#         instances = db.get_records_instance_uptime_of_jupyter_unified(usage_type=usage_type, **instance_search_kwargs)
#     elif usage_type == "deployment":
#         instances = db.get_records_instance_uptime_of_deployment_unified(**instance_search_kwargs)
#     elif usage_type == "hyperparamsearch":
#         instances = db.get_records_instance_uptime_of_hyperparamsearch_unified(**instance_search_kwargs)
#     elif usage_type == "training":  # 삭제 예정
#         instances.extend(db.get_records_instance_uptime_of_job_unified(**instance_search_kwargs))
#         instances.extend(db.get_records_instance_uptime_of_jupyter_unified(usage_type=usage_type, **instance_search_kwargs))
#         instances.extend(db.get_records_instance_uptime_of_hyperparamsearch_unified(**instance_search_kwargs))
#     elif usage_type is None:
#         instances.extend(db.get_records_instance_uptime_of_jupyter_unified(**instance_search_kwargs))
#         instances.extend(db.get_records_instance_uptime_of_job_unified(**instance_search_kwargs))
#         instances.extend(db.get_records_instance_uptime_of_deployment_unified(**instance_search_kwargs))
#         instances.extend(db.get_records_instance_uptime_of_hyperparamsearch_unified(**instance_search_kwargs))

#     if training_ids is not None:
#         # training_ids = [int(_) for _ in training_ids.split(',')]
#         training_ids = training_ids.split(',')
#         # print("training id: ", [ins["training_id"] for ins in instances])
#         instances = [instance for instance in instances if instance["training_id"] in training_ids]

#     if only_instance_by_type or only_records:
#         if only_instance_by_type:  # for dashboard page
#             instances_by_type = _separate_by_type(instances)
#             return {
#                 "instances_cpu": instances_by_type["cpu"],
#                 "instances_gpu": instances_by_type["gpu"],
#             }
#         if only_records:  # for instance history table
#             records = get_records_by_instance_type(instances, dates=dates, usage_type=usage_type,
#                                                    instance_type=instance_type)  # change usage_type value for front side
#             return records["cpu"] + records["gpu"]

#     uptime = calculate_instance_uptime(instances, dates=dates)  # get cpu/gpu uptime by dates
#     instances_by_type = _separate_by_type(instances)
#     records = get_records_by_instance_type(instances, dates=dates, usage_type=usage_type,
#                                            instance_type=instance_type)  # change usage_type value for front side

#     return {
#         "instances": instances,
#         "uptime_cpu": uptime["cpu"],
#         "uptime_gpu": uptime["gpu"],
#         "records_of_cpu": records["cpu"],
#         "records_of_gpu": records["gpu"],
#         "records_of_cpu_count": len(records["cpu"]),
#         "records_of_gpu_count": sum([gpu["gpu_count"] for gpu in records["gpu"]]),
#         "instances_cpu": instances_by_type["cpu"],
#         "instances_gpu": instances_by_type["gpu"],
#     }


# def get_records_instance(workspace_id=None, usergroup_id=None, training_ids=None, year=None, months=None):
#     """
#     NOTE:
#         레코드-인스턴스 페이지 / 워크스페이스별, 그룹별 인스턴스 레코드
#     """
#     try:
#         records_instance_info = {}
#         dates = _set_search_dates(year=year, months=months)

#         if workspace_id is None and usergroup_id is None:
#             response(status=0, message="Workspace_id or usergroup_id is required")
#         if workspace_id is not None and usergroup_id is not None:
#             response(status=0, message="Workspace_id and usergroup_id can not be provided together")

#         active_period = []
#         user_list = None
#         if workspace_id is not None:
#             records_workspace = db.get_records_instance_activation_time(workspace_id)
#             active_period = get_workspace_active_period(records=records_workspace, dates=dates)
#         elif usergroup_id is not None:  # 그룹의 경우 그룹 유저들이 속한 모든 워크스페이스를 기준으로 함
#             users = db.get_user_list_by_group_id(usergroup_id)
#             user_list = [str(user["user_id"]) for user in users]
#             workspaces = db.get_user_workspace(", ".join(user_list))
#             workspace_id_list = [str(workspace["id"]) for workspace in workspaces]

#             records_workspace = []
#             for ws_id in workspace_id_list:
#                 records_workspace.extend(db.get_records_instance_activation_time(ws_id))
#             active_period = get_workspace_active_period(records=records_workspace, dates=dates)

#         instance_filter_kwargs = {
#             "workspace_id": workspace_id,
#             "user_list": user_list,
#             "training_ids": training_ids,
#             "dates": dates,
#         }

#         instances = _get_instances_info(**instance_filter_kwargs)
#         info = {
#             "period_gpu_allocation": active_period[::-1],
#             "uptime_cpu": str(instances["uptime_cpu"].total_seconds()),
#             "uptime_gpu": str(instances["uptime_gpu"].total_seconds()),
#             "records_of_cpu": instances["records_of_cpu_count"],
#             "records_of_gpu": instances["records_of_gpu_count"]
#         }

#         timeline = {
#             'cpu': {},
#             'gpu': {}
#         }

#         timeline['cpu'] = _set_cpu_daily_usage(instances["instances_cpu"], months_date=dates)
#         gpu_daily_usage = _set_gpu_daily_usage(instances["instances_gpu"], months_date=dates)

#         # 워크스페이스의 경우 할당된 전체 gpu 를 분모로 사용률 계산
#         if workspace_id is not None:
#             MAX_GPU_USAGE_RATE = 100
#             for date, date_usages in gpu_daily_usage.items():
#                 for gpu_usage in date_usages:
#                     for _active_period in active_period:
#                         _active_period_start, _active_period_end = convert_start_and_end_time_to_datetime_format(
#                             start=_active_period['start_datetime'],
#                             end=_active_period['end_datetime'])
#                         if _active_period_start <= gpu_usage['end'] and gpu_usage['start'] <= _active_period_end:
#                             total_gpu = _active_period['for_training'] + _active_period['for_deployment']

#                             if not total_gpu == 0:
#                                 if gpu_usage['count'] >= total_gpu:
#                                     timeline['gpu'][date] = {
#                                         "usage_gpu": MAX_GPU_USAGE_RATE,
#                                         "used_gpu": total_gpu,
#                                         "total_gpu": total_gpu}
#                                 elif gpu_usage['count'] < total_gpu:
#                                     usage = int(gpu_usage['count'] / total_gpu * 100)
#                                     if timeline['gpu'].get(date) is None:
#                                         timeline['gpu'][date] = {
#                                             "usage_gpu": usage,
#                                             "used_gpu": gpu_usage['count'],
#                                             "total_gpu": total_gpu}
#                                     elif timeline['gpu'][date]['usage_gpu'] < usage:  # 해당 날짜가 이미 존재하고 사용량이 더 큰 경우에만
#                                         timeline['gpu'][date]['usage_gpu'] = usage
#                                         timeline['gpu'][date]['used_gpu'] = gpu_usage['count']

#                                 if gpu_usage['count'] > total_gpu:  # 할당된 gpu 보다 많은 인스턴스 확인용
#                                     pass
#                                     # print("Record info is not correct. Total gpu usage count can not be over allocated gpu count.")
#                                     # print(gpu_usage)

#         # 그룹의 경우 분모 없이(usage 없이) 사용 gpu 수만 계산
#         elif usergroup_id is not None:
#             for date, date_usages in gpu_daily_usage.items():
#                 for gpu_usage in date_usages:

#                     if timeline['gpu'].get(date) is None:
#                         timeline['gpu'][date] = 0

#                     if timeline['gpu'][date] < gpu_usage['count']:
#                         timeline['gpu'][date] = gpu_usage['count']

#         add_total_gpu_usage_info = workspace_id is not None
#         if dates is not None:
#             for date in dates:
#                 days_ = (_add_month(date) - date).days
#                 timeline['cpu'] = _set_default(timeline['cpu'], date, days_)
#                 timeline['gpu'] = _set_default(timeline['gpu'], date, days_,
#                                                add_gpu_count_info=add_total_gpu_usage_info)

#             # 선택된 월을 벗어난 기록들 삭제
#             timeline['cpu'] = remove_timeline_day_if_not_in_months(timeline=timeline['cpu'], months=dates)
#             timeline['gpu'] = remove_timeline_day_if_not_in_months(timeline=timeline['gpu'], months=dates)

#         else:
#             # 가장 최근, 과거 날짜 체크 후 cpu, gpu 비교해서 기록 없는 날짜 채움
#             min_date_cpu = min(timeline['cpu'].keys(), default=datetime(year=9999, month=1, day=1))
#             max_date_cpu = max(timeline['cpu'].keys(), default=datetime(year=1, month=1, day=1))
#             min_date_gpu = min(timeline['gpu'].keys(), default=datetime(year=9999, month=1, day=1))
#             max_date_gpu = max(timeline['gpu'].keys(), default=datetime(year=1, month=1, day=1))
#             min_date = min_date_cpu if min_date_cpu < min_date_gpu else min_date_gpu
#             max_date = max_date_cpu if max_date_cpu > max_date_gpu else max_date_gpu
#             timeline['cpu'] = _set_default(timeline['cpu'], min_date, (max_date - min_date).days + 1)
#             timeline['gpu'] = _set_default(timeline['gpu'], min_date, (max_date - min_date).days + 1,
#                                            add_gpu_count_info=add_total_gpu_usage_info)

#         timeline['gpu'] = [{"date": k.strftime("%Y-%m-%d"), "usage": v} for k, v in
#                            sorted(timeline['gpu'].items(), key=(lambda x: x[0]))]
#         timeline['cpu'] = [{"date": k.strftime("%Y-%m-%d"), "usage": v} for k, v in
#                            sorted(timeline['cpu'].items(), key=(lambda x: x[0]))]

#         res_timeline = []
#         # 워크스페이스별 기록
#         if workspace_id is not None:
#             if len(timeline['cpu']) == 0:
#                 for _gpu in timeline['gpu']:
#                     res_timeline.append({"date": _gpu["date"], "usage_cpu": 0, **_gpu["usage"]})
#             elif len(timeline['gpu']) == 0:
#                 for _cpu in timeline['cpu']:
#                     res_timeline.append({"date": _cpu["date"], "usage_gpu": 0, "usage_cpu": _cpu["usage"]})
#             else:
#                 for _gpu, _cpu in zip(timeline['gpu'], timeline['cpu']):
#                     res_timeline.append({"date": _cpu["date"], "usage_cpu": _cpu["usage"], **_gpu["usage"]})
#             timeline = res_timeline

#         # 그룹별 기록
#         elif usergroup_id is not None:
#             if len(timeline['cpu']) == 0:
#                 for _gpu in timeline['gpu']:
#                     res_timeline.append({"date": _gpu["date"], "usage_cpu": 0, "usage_gpu": _gpu["usage"]})
#             elif len(timeline['gpu']) == 0:
#                 for _cpu in timeline['cpu']:
#                     res_timeline.append({"date": _cpu["date"], "usage_gpu": 0, "usage_cpu": _cpu["usage"]})
#             else:
#                 for _gpu, _cpu in zip(timeline['gpu'], timeline['cpu']):
#                     res_timeline.append({"date": _cpu["date"], "usage_cpu": _cpu["usage"], "usage_gpu": _gpu["usage"]})
#             timeline = res_timeline

#         records_instance_info['info'] = info if info is not None else {}
#         records_instance_info['timeline'] = timeline if timeline is not None else []

#         return response(status=1, result=records_instance_info)

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records instance Error")


# def convert_start_and_end_time_to_datetime_format(start=None, end=None, add_hours=0):
#     """Except for cpu and gpu usage graph, 9hrs added to time in Front-side."""
#     if(type(start) == datetime):
#         start_datetime = start
#     else:
#         start_datetime = datetime(*map(int, timeformat_hms_regex.match(start).groups()))
#     if end == None:
#         end_datetime = datetime.now().replace(microsecond=0)
#     else:
#         if (type(end) == datetime):
#             end_datetime = end
#         else:
#             end_datetime = datetime(*map(int, timeformat_hms_regex.match(end).groups()))
#     start_datetime += timedelta(hours=add_hours)
#     end_datetime += timedelta(hours=add_hours)

#     return start_datetime, end_datetime


def get_current_status_by_time(start_time=None, end_time=None):
    """Return worksapce current status by start/end time"""
    cur_time_ts = time.time()
    start_datetime_ts = date_str_to_timestamp(start_time)
    end_datetime_ts = date_str_to_timestamp(end_time)
    status = "unknwon"
    if start_datetime_ts <= cur_time_ts and cur_time_ts <= end_datetime_ts:
        status = "active"
    elif cur_time_ts < start_datetime_ts:
        status = "reserved"
    else:
        status = "expired"
    return status


def date_str_to_timestamp(date_str, date_format="%Y-%m-%d %H:%M"):
    if date_str is None:
        return 0
    if date_format == "%Y-%m-%d %H:%M":
        ts = time.mktime(datetime(*map(int, timeformat_hm_regex.match(date_str).groups())).timetuple())
    elif date_format == "%Y-%m-%d %H":
        ts = time.mktime(datetime(*map(int, timeformat_h_regex.match(date_str).groups())).timetuple())
    elif date_format == "%Y-%m-%d %H:%M:%S":
        ts = time.mktime(datetime(*map(int, timeformat_hms_regex.match(date_str).groups())).timetuple())
    else:
        try:
            ts = time.mktime(datetime.strptime(date_str, date_format).timetuple())
        except:
            traceback.print_exc()
    return ts

# # 주석 추가
# def remove_timeline_day_if_not_in_months(timeline, months):
#     for timeline_day in list(timeline.keys()):
#         is_timeline_day_in_months = False
#         for month in months:
#             if (month <= timeline_day and timeline_day < _add_month(month)):
#                 is_timeline_day_in_months = True
#                 break

#         if not is_timeline_day_in_months:
#             del timeline[timeline_day]
#     return timeline


# def check_active_start_end_time(s_str, e_str, l, nl):
#     # TODO 기존 ws는 %Y-%m-%d %H:%M 폼인데
#     # 통합 WS의 경우 %Y-%m-%d %H:%M:%S 까지 받기 때문에 우선은 두 케이스 처리 할 수 있도록 변경
#     # 추후 확인 필요

#     if timeformat_hm_regex.match(s_str):
#         s = datetime(*map(int, timeformat_hm_regex.match(s_str).groups()))
#     else:
#         s = datetime(*map(int, timeformat_hms_regex.match(s_str).groups()))

#     if timeformat_hm_regex.match(e_str):
#         e = datetime(*map(int, timeformat_hm_regex.match(e_str).groups()))
#     else:
#         e = datetime(*map(int, timeformat_hms_regex.match(e_str).groups()))

#     l = datetime(*map(int, timeformat_hms_regex.match(l).groups()))
#     nl = datetime(*map(int, timeformat_hms_regex.match(nl).groups()))

#     if s <= l and l <= e and e <= nl:
#         return l, e
#     elif s <= l and nl < e:
#         return l, nl
#     elif l <= s and e < nl:
#         return s, e
#     elif l <= s and s <= nl and nl <= e:
#         return s, nl
#     return None, None


# def _set_default(timeline, start_date, days, add_gpu_count_info=False):
#     """
#     NOTE:
#         시작, 끝 사이 기록이 없는 날짜 기본값 추가
#     """
#     for day in range(days):
#         k = start_date + timedelta(days=day)
#         if timeline.get(k) is None:
#             if add_gpu_count_info:
#                 timeline[k] = {
#                     "usage_gpu": 0,
#                     "used_gpu": 0,
#                     "total_gpu": 0,
#                     "usage": 0,
#                 }
#             else:
#                 timeline[k] = 0
#     return timeline


# def get_records_instance_history(workspace_id, training_ids, year, months, size, page, type_, usage_type, search_key,
#                                  search_value, usergroup_id=None):
#     try:
#         print("year:", year, type(year))
#         print("months:", months, type(months))
#         dates = _set_search_dates(year=year, months=months)
#         records_instance_history_info = []

#         user_list = None
#         if usergroup_id is not None:
#             users = db.get_user_list_by_group_id(usergroup_id)
#             user_list = [str(user["user_id"]) for user in users]

#         records_search_kwargs = {
#             "workspace_id": workspace_id,
#             "user_list": user_list,
#             "training_ids": training_ids,
#             "usage_type": usage_type,
#             "instance_type": type_,
#             "dates": dates,
#             "search_key": search_key,
#             "search_value": search_value,
#             "only_records": True,
#         }

#         records = _get_instances_info(**records_search_kwargs)

#         for record in records:
#             instance = "CPU:1" if record.get('gpu_count') is None else "GPU:{}".format(str(record['gpu_count']))
#             configuration = record.get('configurations') or '-'
#             stop_time = record.get('end_datetime') or '-'
#             job_deployment = record.get('name') or '-'
#             job_deployment_deleted = 1 if record.get('id') is None else 0
#             training_deleted = 1 if record.get('training_id_if_exists') is None else 0

#             # record(deployment) could be created without a training, so no training to be deleted
#             if record.get('training_name') is None:
#                 record['training_name'] = '-'
#                 training_deleted = 0

#             if record.get('job_group_index') is not None:
#                 index = record.get('job_group_index')
#                 job_deployment += f"({index})"
#             elif record.get('hps_group_index') is not None:
#                 index = record.get('hps_group_index')
#                 job_deployment += f"({index})"

#             # TODO JF만의 정책 결정 필요
#             # 인스턴스 목록 관련 가동시간 시간 * gpu_count -> 시간만 (충북 TP 요청) (21-04-05)
#             if record.get('gpu_count') is not None and int(record.get('gpu_count')) > 1:
#                 uptime = str(record['uptime'].total_seconds() / int(record.get('gpu_count')))
#             else:
#                 uptime = str(record['uptime'].total_seconds())

#             history = {
#                 "instance": instance,
#                 "configuration": configuration,
#                 "usage_type": record['usage_type'],
#                 "worksapce": record['workspace_name'],
#                 "training": record['training_name'],
#                 "training_deleted": training_deleted,
#                 "job_deployment": job_deployment,
#                 "job_deployment_deleted": job_deployment_deleted,
#                 "start_time": str(record['start_datetime']),
#                 "stop_time": str(stop_time),
#                 "uptime": uptime
#             }
#             records_instance_history_info.append(history)

#         def get_start_time(history):
#             return history.get('start_time')

#         records_instance_history_info.sort(key=get_start_time, reverse=True)

#         if page is None or size is None:
#             return response(status=1,
#                             result={"list": records_instance_history_info, "total": len(records_instance_history_info)})
#         else:
#             return response(status=1, result={"list": records_instance_history_info[(page - 1) * size:page * size],
#                                               "total": len(records_instance_history_info)})

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records instance Error")


# def get_records_by_instance_type(instances, usage_type=None, dates=None, instance_type=None):
#     """Return records after add uptime by instance type(cpu/gpu)."""
#     cpu_record = []
#     gpu_record = []

#     for instance in instances:
#         instance["uptime"] = timedelta(0)
#         gpu_count = None
#         cpu_count = None

#         if instance["usage_type"] == "jupyter":
#             if instance["editor"] == "True":
#                 instance["usage_type"] = "editor"
#                 cpu_count = 1
#             else:
#                 if usage_type == "editor":  # history table - filter - editor
#                     continue
#                 instance["usage_type"] = "training"
#                 gpu_count = 1
#         else:
#             if instance["gpu_count"] == 0:
#                 cpu_count = 1
#             else:
#                 gpu_count = instance["gpu_count"]

#         if instance_type is not None:
#             if instance_type == "cpu" and cpu_count is None:
#                 continue
#             elif instance_type == "gpu" and gpu_count is None:
#                 continue

#         start_datetime, end_datetime = convert_start_and_end_time_to_datetime_format(
#             start=instance['start_datetime'],
#             end=instance['end_datetime'],
#             add_hours=utc_offset
#         )

#         # uptime 계산
#         if dates is None:
#             activation_time = end_datetime - start_datetime
#             if activation_time > timedelta(0):
#                 if gpu_count is not None:
#                     instance["gpu_count"] = gpu_count
#                     instance['uptime'] += activation_time * gpu_count
#                     gpu_record.append(instance)
#                 else:
#                     instance["gpu_count"] = None
#                     instance['uptime'] += activation_time
#                     cpu_record.append(instance)
#         else:
#             # 특정 월이 선택된 경우 해당 월 시작, 끝을 벗어난 경우 uptime에 계산하지 않고 월 시작, 끝으로 자름
#             for s_date in dates:
#                 e_date = _add_month(s_date)
#                 start_in_the_month = start_datetime if start_datetime > s_date else s_date
#                 end_in_the_month = end_datetime if end_datetime < e_date else e_date
#                 activation_time_in_the_month = end_in_the_month - start_in_the_month

#                 if activation_time_in_the_month > timedelta(0):
#                     if gpu_count is not None:
#                         instance["gpu_count"] = gpu_count
#                         instance['uptime'] += activation_time_in_the_month * gpu_count
#                         gpu_record.append(instance)
#                     else:
#                         instance["gpu_count"] = None
#                         instance['uptime'] += activation_time_in_the_month
#                         cpu_record.append(instance)
#     return {
#         "cpu": cpu_record,
#         "gpu": gpu_record
#     }


# # 현재 정해진 기획 없음
# def get_records_storage(workspace_id, year, months):
#     try:
#         records_storage_info = {
#             "info": {},
#             "timeline": {
#                 "storage": []
#             },
#         }
#         if True:
#             info = {
#                 "period_gpu_allocation": [
#                     {"period": "2020-02-23 ~ 2020-02-24", "for_training": 1, "for_deployment": 1}
#                 ],
#                 "maximum_size_of_storage": "32.00GB",
#                 "uptime_of_storage": "1234"
#             }
#             timeline = {
#                 "storage": [{"date": "2020-06-18", "usage": 50}, {"date": "2020-06-19", "usage": 50}]
#             }

#         else:
#             info = db.get_records_storage_info()
#             timeline = db.get_records_storage_timeline()

#         records_storage_info['info'] = info if info is not None else {}
#         records_storage_info['timeline'] = timeline if timeline is not None else []

#         return response(status=1, result=records_storage_info)

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records storage Error")


# def get_records_storage_history(workspace_id, year, months, size, page):
#     try:
#         records_storage_info = {
#             "history": []
#         }
#         if True:

#             history = [
#                 {"workspace": "ws1", "size": "32.00MB",
#                  "usage_informaation": "Docker Image: 32.00MB|Dataset : 32.00MB|Training:32.00MB|Deploymen:32.00MB",
#                  "start_time": "2020-02-23 12:23:33", "stop_time": "2020-03-22 12:23:33", "uptime": "1234"}
#             ]

#         else:
#             history = db.get_records_storage_history()

#         records_storage_info['history'] = history if history is not None else []

#         return response(status=1, result=records_storage_info)

#     except:
#         traceback.print_exc()
#     return response(status=0, message="Get records storage Error")


# def get_daily_training_and_deployment_record(user_id: str = "", user_name: str = ""):
#     """ AIP301
#     :param user_id: user table id 숫자
#     :param user_name:  유저가 가입할때 선택한 유저이름
#     :return: lists of daily trainings and deployments
#     """
#     try:
#         if user_id == user_name == "":
#             trainings = db.get_daily_training_list_per_user_unified()
#             deployments = db.get_daily_deployment_list_per_user()
#             return response(status=1, result={"trainings": trainings, "deployments": deployments}, message="301")
#         if user_id != "":
#             if not user_id.isnumeric():
#                 return response(status=0, result="error", message="invalid input(not numeric)")
#             trainings = db.get_daily_training_list_per_user_unified(user_id=user_id)
#             deployments = db.get_daily_deployment_list_per_user(user_id=user_id)
#             return response(status=1, result={"trainings": trainings, "deployments": deployments},message="301")
#         else:
#             if user_name.isnumeric():
#                 return response(status=0, result="error", message="invalid input(numeric)")
#             trainings = db.get_daily_training_list_per_user_unified(user_name=user_name)
#             deployments = db.get_daily_deployment_list_per_user(user_name=user_name)
#             return response(status=1, result={"trainings": trainings, "deployments": deployments},message="301")
#     except Exception as e:
#         return response(status=0, result="error", message=str(e))

# def get_user_stat_helper(user_id: str = "", user_name: str = ""):
#     try:
#         if user_id == user_name == "": # 둘 다 ''인 경우 에러
#             return response(status=0, result="error", message="missing input")
#         elif user_id != "" and user_name == "":
#             active_deployment_list_count = len(db.get_active_deployment_list_for_records(user_id=user_id))
#             active_job_count = len(db.get_active_training_job_list_for_records_unified(user_id=user_id))
#             user_name = db.get_user_name(int(user_id))["name"]
#         elif user_id == "" and user_name != "":
#             active_deployment_list_count = len(db.get_active_deployment_list_for_records(user_name=user_name))
#             active_job_count = len(db.get_active_training_job_list_for_records_unified(user_name=user_name))
#         valid_session = False
#         if len(db.get_token_for_record(user_name=user_name)) > 0:
#             valid_session = True
#         training = active_job_count
#         if training == 0 and active_deployment_list_count > 0:
#             return {"user_name": user_name, "user_status": 2, "logged_in": valid_session}
#         elif training > 0 and active_deployment_list_count == 0:
#             return {"user_name": user_name, "user_status": 1, "logged_in": valid_session}
#         elif training > 0 and active_deployment_list_count > 0:
#             return {"user_name": user_name, "user_status": 3, "logged_in": valid_session}
#         else:
#             return {"user_name": user_name, "user_status": 0, "logged_in": valid_session}
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, result="error", message=str(e))

# def get_user_stat(user_id: str = "", user_name: str = ""):
#     """ AIP302
#     :param user_id: user table id 숫자
#     :param user_name:  유저가 가입할때 선택한 유저이름
#     :return: current user status(0=대기, 1=학습, 2=추론, 3=학습+추론)
#     """
#     try:
#         if user_id == user_name == "":
#             usernames = db.get_every_username()
#             returned = list()
#             for username in usernames:
#                 returned.append(get_user_stat_helper(user_name=username["name"]))
#         elif user_id != "" and user_name == "":
#             if not user_id.isnumeric():
#                 return response(status=0, result="error", message="invalid input(not numeric)")
#             returned = [get_user_stat_helper(user_id=user_id)]
#         elif user_id == "" and user_name != "":
#             if user_name.isnumeric():
#                 return response(status=0, result="error", message="invalid input(numeric)")
#             returned = [get_user_stat_helper(user_name=user_name)]
#         return response(status=1,result=returned,message="302")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, result="error", message=str(e))

# def get_current_system_status(user_id: str = "", user_name: str = "", starting_point:str="", end_point:str=""):
#     """ AIP303
#     :param user_id: user table id 숫자
#     :param user_name:  유저가 가입할때 선택한 유저이름
#     :param starting_point: %Y-%m-%d %H:%M:%S 포맷의 시작 시간
#     :param end_point:  %Y-%m-%d %H:%M:%S 포맷의 끝 시간(starting_point보다 과거)
#     :return: starting_point와 end_point 사이의 trainings과 deployments
#     """
#     if starting_point == "":
#         starting_point = (datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
#     if end_point == "":
#         end_point = str(datetime(*map(int, timeformat_hms_regex.match(starting_point).groups())) - timedelta(days=10))

#     if(not timeformat_hms_regex.match(starting_point)) or (not timeformat_hms_regex.match(end_point)):
#         return response(status=0, result="error", message="Invalid format/starting_point")

#     if user_id == user_name == "":
#         try:
#             gpu_count = 0
#             trainings = db.get_training_list_for_records_unified(starting_point=starting_point,end_point=end_point)
#             deployments = db.get_deployment_list_for_records_unified(starting_point=starting_point,end_point=end_point)
#             for training in trainings:
#                 gpu_count = gpu_count + int(training["gpu_count"])
#             for deployment in deployments:
#                 gpu_count = gpu_count + int(deployment["gpu_count"])
#             sys_status = ({
#                 "gpu": { "used": gpu_count}
#             })
#             return response(status=1, result={"system_status": sys_status, "training_history": trainings,
#                                               "inference_history": deployments}, message="303")
#         except Exception as e:
#             traceback.print_exc()
#             return response(status=0, result="error", message=str(e))
#     elif user_id == "" and user_name != "":
#         try:
#             if user_name.isnumeric():
#                 return response(status=0, result="error", message="invalid input(numeric)")
#             gpu_count = 0
#             trainings = db.get_training_list_for_records_unified(user_name=user_name,starting_point = starting_point, end_point=end_point)
#             deployments = db.get_deployment_list_for_records(user_name=user_name,starting_point = starting_point, end_point=end_point)
#             for training in trainings:
#                 gpu_count = gpu_count + int(training["gpu_count"])
#             for deployment in deployments:
#                 gpu_count = gpu_count + int(deployment["gpu_count"])
#             sys_status =({
#                 "gpu": { "used": gpu_count}
#             })
#             return response(status=1, result={"system_status": sys_status, "training_history": trainings,
#                                               "inference_history": deployments}, message="303")
#         except Exception as e:
#             traceback.print_exc()
#             return response(status=0, result="error", message=str(e))
#     elif user_id != "" and user_name == "":
#         try:
#             if not user_id.isnumeric():
#                 return response(status=0, result="error", message="invalid input(not numeric)")
#             gpu_count = 0
#             trainings = db.get_training_list_for_records_unified(user_id=user_id,starting_point = starting_point, end_point=end_point)
#             deployments = db.get_deployment_list_for_records(user_id=user_id,starting_point = starting_point, end_point=end_point)
#             for training in trainings:
#                 gpu_count = gpu_count + int(training["gpu_count"])
#             for deployment in deployments:
#                 gpu_count = gpu_count + int(deployment["gpu_count"])
#             sys_status = ({
#                 "gpu": { "used": gpu_count}
#             })
#             return response(status=1, result={"system_status": sys_status, "training_history": trainings,
#                                               "inference_history": deployments}, message="303")
#         except Exception as e:
#             traceback.print_exc()
#             return response(status=0, result="error", message=str(e))

# def get_user_record(user_id: str = "", user_name: str = ""):
#     """ AIP304
#     :param user_id: user table id 숫자
#     :param user_name:  유저가 가입할때 선택한 유저이름
#     :return: 현재 진행중인 training과 deployment 리스트
#     """
#     try:
#         if user_id == user_name == "":
#             return response(status=0, result="error", message="missing input")
#         elif user_id != "" and user_name == "":
#             if not user_id.isnumeric():
#                 return response(status=0, result="error", message="invalid input(not numeric)")
#             user_name = db.get_user_name(int(user_id))["name"]
#         if user_name.isnumeric():
#             return response(status=0, result="error", message="invalid input(numeric)")
#         active_deployment_list = db.get_active_deployment_list_for_records(user_name=user_name)
#         for deployment in active_deployment_list:
#             start_time = datetime(*map(int, timeformat_hms_regex.match(deployment["start_datetime"]).groups()))
#             current_time = datetime.now()
#             diff = str(current_time - start_time)
#             deployment["duration"] = diff
#         active_job_list = db.get_active_training_job_list_for_records(user_name=user_name)
#         for job in active_job_list:
#             start_time = datetime(*map(int, timeformat_hms_regex.match(job["start_datetime"]).groups()))
#             current_time = datetime.now()
#             diff = str(current_time - start_time)
#             job["duration"] = diff
#         return response(status=0, result={"training": active_job_list,"deployment": active_deployment_list}, message="304")
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, result="error", message=str(e))


# """
# =================================================================================================================================
# Records Function END
# =================================================================================================================================
# """

# """
# =================================================================================================================================
# Records Router START
# =================================================================================================================================
# """


# @ns.route('/summary', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsSummary(CustomResource):
#     @token_checker
#     @ns.expect(records_summary_parser_get)
#     def get(self):
#         args = records_summary_parser_get.parse_args()

#         response = get_records_summary()
#         # db.request_logging(self.check_user(), 'records', 'get', str(args), response['status'])
#         return self.send(response)


# @ns.route('/workspaces', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsWorkspaces(CustomResource):
#     @token_checker
#     @ns.expect(records_workspaces_parser_get)
#     def get(self):
#         args = records_workspaces_parser_get.parse_args()
#         workspace_ids = args['workspace_ids']
#         year = args['year']
#         months = args['months']
#         size = args['size']
#         page = args['page']
#         task = args['task']
#         action = args['action']
#         search_key = args['search_key']
#         search_value = args['search_value']
#         sort_key = args['sort']
#         sort_value = args['order']

#         response = get_records_workspaces(workspace_ids=workspace_ids, year=year, months=months, size=size, page=page,
#                                           task=task,
#                                           action=action, search_key=search_key, search_value=search_value,
#                                           sort_key=sort_key, sort_value=sort_value)
#         # db.request_logging(self.check_user(), 'records/'+str(workspace_id), 'get', None, response['status'])
#         return self.send(response)


# @ns.route('/instance', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsInstance(CustomResource):
#     @token_checker
#     @ns.expect(records_instance_parser_get)
#     def get(self):
#         args = records_instance_parser_get.parse_args()
#         workspace_id = args['workspace_id']
#         training_ids = args['training_ids']
#         year = args['year']
#         months = args['months']
#         usergroup_id = args["usergroup_id"]

#         from datetime import datetime
#         a = datetime.now()
#         response = get_records_instance(workspace_id=workspace_id, usergroup_id=usergroup_id, training_ids=training_ids,
#                                         year=year, months=months)
#         print('time : ', datetime.now() - a)
#         # db.request_logging(self.check_user(), 'records/'+str(workspace_id), 'get', None, response['status'])
#         return self.send(response)


# @ns.route('/instance_history', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsInstanceHistory(CustomResource):
#     @token_checker
#     @ns.expect(records_instance_parser_get)
#     def get(self):
#         args = records_instance_parser_get.parse_args()
#         workspace_id = args['workspace_id']
#         training_ids = args['training_ids']
#         year = args['year']
#         months = args['months']
#         size = args['size']
#         page = args['page']
#         type_ = args['type']
#         usage_type = args['usage_type']
#         # search_key = args['search_key']
#         # search_value = args['search_value']
#         usergroup_id = args["usergroup_id"]
#         search_key = args['searchKey']
#         search_value = args['keyword']

#         response = get_records_instance_history(workspace_id=workspace_id, training_ids=training_ids, year=year,
#                                                 months=months, size=size, page=page, type_=type_,
#                                                 usage_type=usage_type, search_key=search_key, search_value=search_value,
#                                                 usergroup_id=usergroup_id)

#         # db.request_logging(self.check_user(), 'records/'+str(workspace_id), 'get', None, response['status'])
#         return self.send(response)


# @ns.route('/storage', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsStorage(CustomResource):
#     @token_checker
#     @ns.expect(records_storage_parser_get)
#     def get(self):
#         args = records_storage_parser_get.parse_args()
#         workspace_id = args['workspace_id']
#         year = args['year']
#         months = args['months']
#         usage_type = args['usage_type']
#         size = args['size']
#         page = args['page']

#         response = get_records_storage(workspace_id=workspace_id, year=year, months=months)
#         return self.send(response)


# @ns.route('/storage_history', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsStorageHistory(CustomResource):
#     @token_checker
#     @ns.expect(records_storage_parser_get)
#     def get(self):
#         args = records_storage_parser_get.parse_args()
#         workspace_id = args['workspace_id']
#         year = args['year']
#         months = args['months']
#         size = args['size']
#         page = args['page']

#         response = get_records_storage_history(workspace_id=workspace_id, year=year, months=months, size=size,
#                                                page=page)
#         return self.send(response)


# @ns.route('/daily_training_deployment_record', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class TrainingAndDeploymentRecord(CustomResource):
#     # @token_checker
#     @ns.expect(records_userdata_daily_parser_get)
#     def get(self):
#         args = records_userdata_daily_parser_get.parse_args()
#         user_id = args['user_id']
#         user_name = args['user_name']
#         response = get_daily_training_and_deployment_record(user_id=user_id, user_name=user_name)
#         return self.send(response)


# @ns.route('/current_system_status', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class CurrentUserStatus(CustomResource):
#     # @token_checker
#     @ns.expect(records_userdata_range_parser_get)
#     def get(self):
#         args = records_userdata_range_parser_get.parse_args()
#         user_id = args['user_id']
#         user_name = args['user_name']
#         end_point = args['end_point']
#         starting_point = args['starting_point']
#         response = get_current_system_status(user_id=user_id, user_name=user_name, starting_point=starting_point, end_point=end_point)
#         return self.send(response)


# @ns.route('/user_status', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class CurrentUserStatus(CustomResource):
#     # @token_checker
#     @ns.expect(records_userdata_daily_parser_get)
#     def get(self):
#         args = records_userdata_daily_parser_get.parse_args()
#         user_id = args['user_id']
#         user_name = args['user_name']
#         response = get_user_stat(user_id=user_id, user_name=user_name) # user_id나 user_name 둘중 하나를 받도록 처리
#         return self.send(response)


# @ns.route('/user_record', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class CurrentUserStatus(CustomResource):
#     # @token_checker
#     @ns.expect(records_userdata_daily_parser_get)
#     def get(self):
#         args = records_userdata_daily_parser_get.parse_args()
#         user_id = args['user_id']
#         user_name = args['user_name']
#         response = get_user_record(user_id=user_id, user_name=user_name) # user_id나 user_name 둘중 하나를 받도록 처리
#         return self.send(response)


# """
# =================================================================================================================================
# Records Router END
# =================================================================================================================================
# """

# @ns.route('/gpu', methods=['DELETE'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class RecordsGpuDelete(CustomResource):
#     @token_checker
#     # @ns.expect()
#     def delete(self):
#         """db records_gpu에서 days 전까지 기록 삭제 (days=1일때, 2022-10-18일에 삭제할경우, 2022-10-17일부터 기록은 남아있음),
#         /jfbcore/installer_new/others/cron-delete-records-gpu.sh crontab 추가 스크립트"""
#         try:
#             db.delete_gpu_records(days=1)
#             return self.send(response(status=1, result=None, message="Delete gpu records"))
#         except Exception as e:
#             traceback.print_exc()

# def update_record_unified_end_datetime_is_null():
#     """record_unified에서 end_datetime이 null인 것 중, 비정상적으로 종료된 item의 endtime을 현재시간으로 설정"""
#     try:
#         update_subtype_id=[]
#         for i in db.get_record_unified_end_datetime():
#             subtype = i["subtype"]
#             subtype_id = i["subtype_id"]

#             if subtype == "tool":
#                 option={"training_tool_id" : subtype_id}
#             elif subtype == "job":
#                 option={"job_id" : subtype_id}
#             elif subtype == "hyperparamsearch":
#                 option={"hps_id" : subtype_id}
#             elif subtype == "deployment":
#                 option={"deployment_worker_id" : subtype_id}

#             if not kube.find_kuber_item_name_and_item(item_list=kube_data.get_pod_list(), **option):
#                 update_subtype_id.append(subtype_id)

#         if update_subtype_id:
#             db.update_record_unified_end_datetime(update_subtype_id)

#         return True
#     except Exception as e:
#         traceback.print_exc()
#         return False