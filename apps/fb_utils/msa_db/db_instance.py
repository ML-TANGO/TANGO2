from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import execute_query, select_query
import traceback

def get_instance(instance_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT i.*, rg.name gpu_name
                FROM instance i
                LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                WHERE i.id = %s
            """
            cur.execute(sql, (instance_id, ))
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_all_instances():
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT i.*, rg.name gpu_name
                FROM instance i
                LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
            """
            cur.execute(sql)
            res = cur.fetchall()
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
                add_sql.append("pt.request_status = 1")

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
                FROM project_hps h
                INNER JOIN project p ON p.id = h.project_id
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

def init_workspace_instance(instance_id_list=None):
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


def get_workspcae_instance_alloc_info():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # sql= """
            #     SELECT 
            #         wi.id AS workspace_instance_id, wi.workspace_id, wi.instance_allocate,
            #         i.id AS instance_id, i.instance_name, i.instance_count, i.instance_type, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, i.npu_allocate,
            #         COALESCE(rg.id, 0) AS resource_group_id, COALESCE(rg.name, 'No Resource Group') AS resource_group_name,
            #         w.id AS workspace_id, w.name AS workspace_name
            #     FROM 
            #         workspace_instance wi
            #     JOIN 
            #         instance i ON wi.instance_id = i.id
            #     LEFT JOIN 
            #         resource_group rg ON i.gpu_resource_group_id = rg.id
            #     JOIN 
            #         workspace w ON wi.workspace_id = w.id;
            # """
            sql="""
                SELECT 
                    COALESCE(wi.id, 0) AS workspace_instance_id, COALESCE(wi.instance_allocate,0) AS instance_allocate,
                    i.instance_name, i.instance_count, i.instance_type, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, i.npu_allocate,
                    COALESCE(w.id, 0) AS workspace_id, COALESCE(w.name, '') AS workspace_name
                FROM 
                    workspace_instance wi
                JOIN 
                    instance i ON wi.instance_id = i.id  
                JOIN 
                    workspace w ON wi.workspace_id = w.id;
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
        return False