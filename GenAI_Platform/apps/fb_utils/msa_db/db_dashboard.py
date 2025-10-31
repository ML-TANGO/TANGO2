import traceback
import json
import time
from datetime import date, datetime, timedelta
from threading import Timer
import os.path
import sqlite3
import pwd
import crypt
import os
import pymysql
import json
import time
from collections import OrderedDict
import re
from utils.msa_db.db_base import get_db
from utils import common


def get_user_dashboard_info(workspace_id):

    try:
        with get_db() as conn:

            cur = conn.cursor()

            info = {}
            sql = """SELECT *
                FROM workspace
                WHERE id = {}""".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchone()
            info['description'] = res['description']
            info['name'] = res['name']

            cur_time_ts = time.time()
            start_datetime_ts = common.date_str_to_timestamp(res["start_datetime"])
            print(start_datetime_ts)
            end_datetime_ts = common.date_str_to_timestamp(res["end_datetime"])
            info['status'] = "Unknwon"
            info['period'] = res["start_datetime"] + " ~ " + res["end_datetime"]
            info['start_datetime'] = res["start_datetime"]
            info['end_datetime'] = res["end_datetime"]
            # info['guaranteed_gpu'] = res["guaranteed_gpu"]
            owner_id = res['manager_id']

            if cur_time_ts < start_datetime_ts or cur_time_ts > end_datetime_ts:
                info['status'] = "Reserved" if cur_time_ts < start_datetime_ts else "Expired"
            else :
                info['status'] = "Active"

            sql = """SELECT uw.user_id, name
                FROM user u
                INNER JOIN user_workspace uw ON u.id = uw.user_id
                WHERE workspace_id = {}""".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
            users=[]
            for _res in res:
                if _res['user_id'] == owner_id:
                    info['owner'] = _res['name']
                else:
                    users.append(_res['name'])
            info['users'] = users

            return info
    except Exception as e:
        traceback.print_exc()
        return info



def get_user_dashboard_total_count(workspace_id, user_id):
    try:
        total_count= []
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT *
                FROM record_workspace_variation
                WHERE workspace_id = {} AND log_create_datetime
                BETWEEN '{}' AND '{}'""".format(workspace_id, date.today().strftime("%Y-%m-%d"), (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))

            cur.execute(sql)
            log_res = cur.fetchone()

            image_sql = """SELECT COUNT(*)
                FROM image i
                LEFT JOIN image_workspace iw ON i.id = iw.image_id
                WHERE workspace_id = {} OR access = 1""".format(workspace_id)

            cur.execute(image_sql)
            res = cur.fetchone()
            if log_res is not None:
                total_count.append({'name':"Docker Images", 'total':res['COUNT(*)'] , 'variation': str(int(res['COUNT(*)']) - int(log_res['image_count'])) })
            else:
                total_count.append({'name':"Docker Images", 'total':res['COUNT(*)'] , 'variation':0})

            dataset_sql = """SELECT COUNT(*)
                FROM dataset
                WHERE workspace_id = {}""".format(workspace_id, user_id)

            cur.execute(dataset_sql)
            res = cur.fetchone()
            if log_res is not None:
                total_count.append({'name':"Datasets", 'total':res['COUNT(*)'] , 'variation': str(int(res['COUNT(*)']) - int(log_res['dataset_count'])) })
            else:
                total_count.append({'name':"Datasets", 'total':res['COUNT(*)'] , 'variation':0})

            training_sql = """SELECT COUNT(*)
                FROM training
                WHERE workspace_id = {}""".format(workspace_id)

            cur.execute(training_sql)
            res = cur.fetchone()
            if log_res is not None:
                total_count.append({'name':"Trainings", 'total':res['COUNT(*)'] , 'variation': str(int(res['COUNT(*)']) - int(log_res['training_count'])) })
            else:
                total_count.append({'name':"Trainings", 'total':res['COUNT(*)'] , 'variation':0})

            deployment_sql = """SELECT COUNT(*)
                FROM deployment
                WHERE workspace_id = {}""".format(workspace_id)

            cur.execute(deployment_sql)
            res = cur.fetchone()
            if log_res is not None:
                total_count.append({'name':"Deployments", 'total':res['COUNT(*)'] , 'variation': str(int(res['COUNT(*)']) - int(log_res['deployment_count'])) })
            else:
                total_count.append({'name':"Deployments", 'total':res['COUNT(*)'] , 'variation':0})

            if log_res is None:
                fields = ['workspace_id', 'training_count', 'dataset_count', 'image_count', 'deployment_count']
                sql = """INSERT INTO {} ({})
                    VALUES ({})""".format('record_workspace_variation', ', '.join(fields), ', '.join(['%s']*len(fields)))

                val = (str(workspace_id), str(total_count[0]['total']), str(total_count[1]['total']), str(total_count[2]['total']), str(total_count[3]['total']))
                cur.execute(sql, val)

                conn.commit()

            return total_count

    except Exception as e:
        traceback.print_exc()
        return total_count



def get_workspace(workspace_name=None, workspace_id=None):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT w.*, u.name as manager_name
                FROM workspace w
                INNER JOIN user u ON w.manager_id = u.id"""

            if workspace_name is not None:
                sql += f" WHERE w.name = '{workspace_name}'"
            elif workspace_id is not None:
                sql += f" WHERE w.id = {workspace_id}"
            cur.execute(sql)
            res = cur.fetchone()

    except:
        traceback.print_exc()
    return res


def get_workspace_list():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT w.*
            FROM workspace w
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []




def get_workspace_instance_list(workspace_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT wi.instance_allocate, i.*, rg.name as gpu_resource_group_name
            FROM workspace_instance wi
            JOIN instance i ON wi.instance_id = i.id
            LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
            WHERE wi.workspace_id = {workspace_id}
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return None




def get_admin_dashboard_total_count():
    mappings=[
            ['Workspaces', 'workspace', 'workspace_count'],
            ['Trainings', 'project', 'training_count'],
            ['Deployments', 'deployment', 'deployment_count'],
            ['Docker Images', 'image', 'image_count'],
            ['Datasets', 'datasets', 'dataset_count'],
            ['Nodes', 'node', 'node_count'],
            #['Users', 'user', 'total_user_count'],
            ]
    try:
        with get_db() as conn:
            cur = conn.cursor()

        #     sql = """SELECT *
		# FROM record_all_workspaces_variation
		# WHERE log_create_datetime BETWEEN '{}' AND '{}'""".format(
        #                 date.today().strftime("%Y-%m-%d"),
        #                 (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))

        #     cur.execute(sql)
        #     log_res = cur.fetchone()

            total_count= []
            for table_name in mappings:
                sql = """SELECT count(*)
                    FROM {} """.format(table_name[1])

                cur.execute(sql)
                res = cur.fetchone()

                # if log_res is not None:
                #     total_count.append({'name':table_name[0], 'total':res['count(*)'] , 'variation': str(int(res['count(*)']) - int(log_res[table_name[2]])) })
                # else:
                total_count.append({'name':table_name[0], 'total':res['count(*)'] , 'variation': 0 })

            # if log_res is None:
            #     fields = [table_name[2] for table_name in mappings]
            #     sql = """INSERT INTO {} ({})
            #         VALUES ({})""".format('record_all_workspaces_variation', ', '.join(fields), ', '.join(['%s']*len(fields)))

            #     val = ([str(count['total']) for count in total_count])
            #     cur.execute(sql, val)

            #     conn.commit()

            return total_count
    except Exception as e:
        traceback.print_exc()



def get_project_tool_active_list(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT pt.*
            FROM project_tool pt
            WHERE pt.project_id='{project_id}' and pt.request_status=1
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_project_job_list(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT t.*
            FROM training t
            WHERE t.project_id='{project_id}' and t.end_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []


def get_project_job_pending_list(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT t.*
            FROM training t
            WHERE t.project_id='{project_id}' and t.end_datetime IS NULL and t.start_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_project_hps_pending_list(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT h.*
            FROM hps h
            JOIN hps_group hg ON h.hps_group_id = hg.id
            WHERE hg.project_id='{project_id}' and h.end_datetime IS NULL and h.start_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_project_hps_list(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT h.*
            FROM hps h
            LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
            WHERE hg.project_id='{project_id}' and h.end_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_deployment_worker_list(deployment_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT dw.*
            FROM deployment_worker dw
            WHERE dw.deployment_id='{deployment_id}' and dw.end_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_deployment_worker_pending_list(deployment_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT dw.*
            FROM deployment_worker dw
            WHERE dw.deployment_id='{deployment_id}' and dw.end_datetime IS NULL and dw.start_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []