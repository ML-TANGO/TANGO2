from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import execute_query, select_query
import traceback

def get_instance_info(instance_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM instance
                WHERE id = %s
            """
            cur.execute(sql, (instance_id, ))
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_deployment_list_in_instance(instance_id_list=None, running=True):
    """instance_id를 사용하여 동작중인 worker 리스트 조회"""
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT d.*
                FROM deployment_worker dw
                INNER JOIN deployment d ON d.id = dw.deployment_id
            """
            add_sql = []
            if running == True:
                add_sql.append("dw.end_datetime IS NULL")

            if instance_id_list is not None and len(instance_id_list) > 0:
                instance_id = [str(id) for id in instance_id_list]
                instance_id = ','.join(instance_id)
                add_sql.append(f"d.instance_id IN ({instance_id})")

            if len(add_sql) > 0:
                tmp = ' AND '.join(add_sql)
                sql += f"WHERE {tmp}"

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_tool_list_in_instance(instance_id_list=None, running=True):
    """instance_id를 사용하여 동작중인 tool 리스트 조회"""
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT pt.*
                FROM project_tool pt
                INNER JOIN project p ON p.id = pt.project_id
            """
            add_sql = []
            if running == True:
                add_sql.append("pt.end_datetime IS NULL")

            if instance_id_list is not None and len(instance_id_list) > 0:
                instance_id = [str(id) for id in instance_id_list]
                instance_id = ','.join(instance_id)
                add_sql.append(f"p.instance_id IN ({instance_id})")

            if len(add_sql) > 0:
                tmp = ' AND '.join(add_sql)
                sql += f"WHERE {tmp}"

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_job_list_in_instance(instance_id_list=None, running=True):
    """instance_id를 사용하여 동작중인 job 리스트 조회"""
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT t.*
                FROM training t
                INNER JOIN project p ON p.id = t.project_id
            """
            add_sql = []
            if running == True:
                add_sql.append("t.end_datetime IS NULL")

            if instance_id_list is not None and len(instance_id_list) > 0:
                instance_id = [str(id) for id in instance_id_list]
                instance_id = ','.join(instance_id)
                add_sql.append(f"p.instance_id IN ({instance_id})")

            if len(add_sql) > 0:
                tmp = ' AND '.join(add_sql)
                sql += f"WHERE {tmp}"

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_hps_list_in_instance(instance_id_list=None, running=True):
    """instance_id를 사용하여 동작중인 hps 리스트 조회"""
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT h.*
                FROM hps h
                LEFT JOIN hps_group hg ON hg.id = h.hps_group_id
                INNER JOIN project p ON p.id = hg.project_id
            """
            add_sql = []
            if running == True:
                add_sql.append("h.end_datetime IS NULL")

            if instance_id_list is not None and len(instance_id_list) > 0:
                instance_id = [str(id) for id in instance_id_list]
                instance_id = ','.join(instance_id)
                add_sql.append(f"p.instance_id IN ({instance_id})")

            if len(add_sql) > 0:
                tmp = ' AND '.join(add_sql)
                sql += f"WHERE {tmp}"

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def init_workspace_instnace(instance_id_list=None):
    """workspace_instance 테이블에서 instance_id가 있는 row는 삭제"""
    if len(instance_id_list) == 0:
        return True
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "DELETE FROM workspace_instance WHERE instance_id in ({})".format(
                ','.join(str(e) for e in instance_id_list))
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def init_deployment_instance(instance_id_list=None):
    """deployment 테이블에서 instance_id, instane_allocate 초기화 NULL로 초기화"""
    if len(instance_id_list) == 0:
        return True
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE deployment SET instance_id=NULL, instance_allocate=0 WHERE instance_id in ({})".format(
                ','.join(str(e) for e in instance_id_list))
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def init_training_instance(instance_id_list=None):
    """project 테이블에서 instance_id, instane_allocate 초기화 NULL로 초기화"""

    if len(instance_id_list) == 0:
        return True
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE project SET instance_id=NULL, instance_allocate=0 WHERE instance_id in ({})".format(
                ','.join(str(e) for e in instance_id_list))
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
