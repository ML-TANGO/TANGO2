from utils.msa_db.db_base import get_db, pymysql
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List


import traceback

async def get_project_all():
    sql = """
    SELECT * FROM project
    """
    res = await select_query(sql, fetch_type="all")
    return res

async def get_workspace_instance(workspace_id : int, instance_id : int):
    sql = """
        SELECT wi.*, i.gpu_allocate 
        FROM workspace_instance wi
        JOIN instance i ON wi.instance_id = i.id
        WHERE workspace_id = %s and instance_id = %s
    """
    res = await select_query(query=sql, params=(workspace_id, instance_id), fetch_type="one")
    return res


async def get_deployment_by_instance_id(instance_id : int, workspace_id : int):
    sql = """
            SELECT *
            FROM deployment
            WHERE workspace_id = %s AND instance_id = %s
        """
    res = await select_query(query=sql, params=(workspace_id, instance_id))
    return res
    
async def get_deployment_by_project_id(project_id : int):
    """
    check_related_deployment에서 쓰는거라 model_type이 huggingface, built-in인 것만 조회
    """
    sql = """
            SELECT *
            FROM deployment d
            WHERE d.project_id = %s AND  (d.model_type = 'huggingface' OR d.model_type = 'built-in')
        """
    res = await select_query(query=sql, params=(project_id))
    return res
    

async def get_deployment_worker_request(deployment_id : int):
    sql = """
        SELECT *
        FROM deployment_worker
        WHERE deployment_id = %s AND end_datetime IS NULL
    """
    res = await select_query(query=sql, params=(deployment_id,))
    return res

async def get_project_by_instance_id(instance_id : int, workspace_id : int):
    sql = """
        SELECT *
        FROM project
        WHERE workspace_id = %s AND instance_id = %s
    """
    res = await select_query(query=sql, params=(workspace_id, instance_id))
    return res


def get_project_access_check(user_id : int, project_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT * 
                FROM user_project
                WHERE project_id = {project_id} and user_id = {user_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
        return None
    return res


def get_training_tool_only(project_tool_id=None, project_id=None, tool_type=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            if project_tool_id is not None:
                sql = """
                    SELECT *
                    FROM project_tool
                    WHERE id = {}
                """.format(project_tool_id)
            elif project_id is not None and tool_type is not None:
                sql = """
                    SELECT *
                    FROM project_tool
                    WHERE project_id = {} and tool_type = {}
                """.format(project_id, tool_type)


            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
        return None
    return res


def get_workspace_trainings(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT t.id, t.project_id, t.name, u.name as create_user_name, t.create_datetime, t.start_datetime, t.end_datetime, t.end_status, t.resource_type, i.name as image_name, t.project_id, p.name as project_name
                FROM training t
                JOIN project p ON p.id = t.project_id
                LEFT JOIN image i ON i.id = t.image_id
                LEFT JOIN user u ON u.id = t.create_user_id
                WHERE p.workspace_id = {workspace_id}
                ORDER BY t.create_datetime desc
                LIMIT 5
            """.format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_workspace_hps(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT h.id, h.hps_group_index, hg.name, u.name as create_user_name, h.create_datetime, h.start_datetime, h.end_datetime, h.end_status, h.resource_type, h.image_name, hg.project_id, p.name as project_name
                FROM hps h
                JOIN hps_group hg ON hg.id = h.hps_group_id
                JOIN project p ON p.id = hg.project_id
                LEFT JOIN user u ON u.id = h.create_user_id
                WHERE p.workspace_id = {workspace_id}
                ORDER BY h.create_datetime desc
                LIMIT 5
            """.format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

async def get_instance_info_new(instance_id : int):
    sql = f"""
            SELECT gpu_allocate, cpu_allocate, ram_allocate, instance_type
            FROM instance
            WHERE id = {instance_id}
            """
    res = await select_query(sql, fetch_type="one")
    return res


def get_instance_info(instance_id : int):
    try:
        res = {}
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT gpu_allocate, cpu_allocate, ram_allocate, instance_type
            FROM instance
            WHERE id = {instance_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_workspace_user_name_and_id_list(workspace_id: int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT u.id, u.name
                from user_workspace uw
                inner join user u on uw.user_id = u.id
                where workspace_id = {}
            """.format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_workspace_image_list(workspace_id: int = None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT id, name
                FROM image i
                LEFT JOIN image_workspace iw ON iw.image_id = i.id
                WHERE i.status =2 and ( (i.access = 1) or (i.access = 0 and iw.workspace_id = {workspace_id}) )
            """

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

async def get_workspace_new(workspace_id : int):
    sql = """
    SELECT w.*, s.name as main_storage_name
    FROM workspace w
    LEFT JOIN storage s ON s.id = w.main_storage_id
    WHERE w.id = %s
    """
    res = await select_query(sql, params=(workspace_id, ), fetch_type="one")
    return res

def get_workspace(workspace_id : int):
    try:
        res = {}
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT w.*, s.name as main_storage_name
            FROM workspace w
            LEFT JOIN storage s ON s.id = w.main_storage_id
            WHERE w.id = {workspace_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_workspace_name_and_id_list():
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT w.id, w.name
                FROM workspace w
            """

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_workspace_instances_project(workspace_id : int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wim.instance_allocate
            FROM workspace_instance_manage wim
            JOIN instance i ON i.id = wim.instance_id
            JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
            WHERE wim.workspace_id = {workspace_id} AND type = 'project'
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_workspace_instances(workspace_id : int):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
            FROM workspace_instance wi
            JOIN instance i ON i.id = wi.instance_id
            LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
            WHERE wi.workspace_id = {workspace_id}
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def get_workspace_instance_manage(workspace_id : int, instance_id : int, type : str = "project"):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wim.type_instance_allocate as instance_allocate
            FROM workspace_instance_manage wim
            JOIN workspace_instance wi ON wim.workspace_instance_id = wi.id
            JOIN instance i ON i.id = wi.instance_id
            JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
            WHERE wi.workspace_id = {workspace_id} AND type = '{type}' AND i.id = {instance_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def get_project_allocate_resource(workspace_id : int):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT i.id, i.gpu_resource_group_id, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wim.type_instance_allocate as instance_allocate, rg.name as resource_name
                FROM workspace_instance_manage wim
                JOIN workspace_instance wi ON wi.id = wim.workspace_instance_id
                JOIN instance i ON i.id = wi.instance_id
                JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                WHERE wi.workspace_id = {workspace_id} AND wim.type = "project"
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def get_project_allocated_resource(workspace_id : int, project_id : int = None):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT rg.name as resource_name, SUM(p.instance_allocate) as allocated, i.gpu_resource_group_id as resource_group_id
            FROM project p
            JOIN instance i ON i.id = p.instance_id
            JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
            WHERE p.workspace_id = {workspace_id}
            """
            if project_id:
                sql += f" AND p.id != {project_id}"
            sql += f" GROUP BY i.gpu_resource_group_id"
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

async def get_user_new(user_name : str = None, user_id : int = None):
    sql = f"""
    SELECT id, name, user_type
    FROM user"""
    params = None
    if user_id:
        sql += " WHERE id = %s"
        params = (user_id, )
    elif user_name:
        sql += " WHERE name = %s"
        params = (user_name, )
    res = await select_query(query=sql, params=params, fetch_type="one")    
    
    return res

def get_user(user_name : str = None, user_id : int = None):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT id, name, user_type
            FROM user"""
            if user_id:
                sql += f" WHERE id = {user_id}"
            elif user_name:
                sql += f" WHERE name = '{user_name}'"
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


async def get_workspace_in_user_permission(workspace_id : int):
    sql = f"""
            SELECT u.id, u.name as user_name
            FROM user_workspace uw
            JOIN user u ON u.id = uw.user_id
            WHERE uw.workspace_id = {workspace_id} 
            """
    res = await select_query(sql)
    return res

def get_workspace_in_user(user_id : int, workspace_id : int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT *
            FROM user_workspace
            WHERE workspace_id = {workspace_id} AND user_id = {user_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_user_name(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT name
                FROM user
                WHERE id = {}""".format(user_id)

            cur.execute(sql)
            res = cur.fetchone()

    except:
        traceback.print_exc()
    return res


async def get_built_im_model_list(category : str):
    sql = f"""
    SELECT * FROM built_in_model WHERE category = '{category}'
    """
    res = await select_query(sql, fetch_type='all')
    return res


async def get_project_tools_new(project_id : int):
    sql = f"""
    SELECT pt.*, i.name as image_name
    FROM project_tool pt
    LEFT JOIN image i ON i.id = pt.image_id
    WHERE project_id = {project_id}
    """
    res = await select_query(sql, fetch_type='all')
    return res

def get_project_tools(project_id : int, is_running : bool = False):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT pt.*, i.name as image_name
            FROM project_tool pt
            LEFT JOIN image i ON i.id = pt.image_id
            WHERE project_id = {project_id}
            """
            if is_running: # 동작 중
                sql += " AND pt.start_datetime IS NOT NULL AND pt.end_datetime IS NULL"
            
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_workspace_tools(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT *
            FROM project_tool pt
            JOIN project p ON p.id = pt.project_id
            JOIN workspace w ON p.workspace_id = w.id
            WHERE w.id = {workspace_id}
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


async def get_workspace_manager_new(workspace_id : int):
    sql = """
            SELECT u.name as manager_name, w.manager_id
            FROM workspace w
            JOIN user u ON u.id = w.manager_id
            WHERE w.id = %s"""
    res = await select_query(sql, params=(workspace_id,), fetch_type="one")
    return res

def get_workspace_manager(workspace_id : int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT u.name as manager_name, w.manager_id
            FROM workspace w
            JOIN user u ON u.id = w.manager_id
            WHERE w.id = {workspace_id}"""
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


async def get_project_simple(project_id : int):
    sql = """
        SELECT p.id, p.name, p.instance_id, p.instance_allocate, p.type, p.description
        FROM project p
        WHERE p.id = %s
    """
    res = await select_query(sql, params=(project_id,), fetch_type="one")
    return res

async def get_built_in_model(category : str , name : str):
    sql = """
        SELECT * FROM built_in_model WHERE category = %s AND name = %s
    """
    res = await select_query(sql, params=(category, name), fetch_type="one")
    return res
async def get_built_in_model_image_info_by_real_name(real_name : str):
    sql = """
        SELECT * FROM image WHERE real_name = %s
    """
    res = await select_query(sql, params=(real_name, ), fetch_type="one")
    return res


async def get_project_new(workspace_id : int = None, project_id : int = None, project_name : str = None):
    sql = """
    SELECT p.*, u.name as create_user_name, w.name as workspace_name, rg.name as resource_name, i.gpu_allocate, i.gpu_resource_group_id, s.name as storage_name, 
    i.instance_type, i.instance_name, i.cpu_allocate as  instance_cpu, i.ram_allocate as instance_ram, i.instance_count
    FROM project p
    JOIN user u ON u.id = p.create_user_id
    JOIN workspace w ON w.id = p.workspace_id
    JOIN storage s ON w.main_storage_id = s.id
    LEFT JOIN instance i ON i.id = p.instance_id
    LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id"""
    params = None
    if project_id:
        sql += " WHERE p.id = %s"
        params = (project_id,)
    elif project_name:
        sql += " WHERE p.workspace_id =%s AND p.name = %s"
        params = (workspace_id, project_name)
    res = await select_query(sql, params=params, fetch_type="one")
    return res
    


def get_project(workspace_id : int = None, project_id : int = None, project_name : str = None):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT p.*, u.name as create_user_name, w.name as workspace_name, rg.name as resource_name, i.gpu_allocate, 
            i.gpu_resource_group_id, s.name as storage_name, i.instance_type, i.instance_name, 
            i.cpu_allocate as  instance_cpu, i.ram_allocate as instance_ram, i.instance_count,
            b.id built_in_model_id, img.id built_in_model_image_id
            FROM project p
            JOIN user u ON u.id = p.create_user_id
            JOIN workspace w ON w.id = p.workspace_id
            JOIN storage s ON w.main_storage_id = s.id
            LEFT JOIN instance i ON i.id = p.instance_id
            LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
            LEFT JOIN built_in_model b ON (b.name = p.built_in_model AND b.category = p.category)
            LEFT JOIN image img ON img.real_name = b.image""" # 파이프라인 배포에서 사용 built_in_model_image_id
            if project_id:
                sql += f" WHERE p.id = {project_id}"
            elif project_name:
                sql += f" WHERE p.workspace_id ={workspace_id} AND p.name = '{project_name}'"
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


async def get_project_list_new(search_key=None, size=None, page=None, search_value=None, workspace_id=None, user_id=None, sort=None, project_type=None):
    sql = """
        SELECT DISTINCT p.*, u.name as create_user_name, rg.name as resource_name, w.name as workspace_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate, it.instance_type
        FROM project p
        LEFT JOIN user u ON u.id = p.create_user_id
        LEFT JOIN workspace w ON w.id = p.workspace_id
        LEFT JOIN instance it ON it.id = p.instance_id 
        LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
        LEFT JOIN user_project up ON up.project_id = p.id
    """

    if search_key is not None and search_value is not None:
        if search_key == "user_id":
            sql += " where u.id = {} or up.user_id = {} ".format(search_value, search_value)
        else :
            search_value = '"%{}%"'.format(search_value)
            sql += " where t.{} like {} ".format(search_key, search_value)


    if workspace_id is not None:
        if not "where" in sql:
            sql += " where "
        else:
            sql += "and "
        sql += "w.id = {} ".format(workspace_id)


    if project_type is not None:
        if not "where" in sql:
            sql += "where "
        else:
            sql += "and "
        sql += "p.type ='{}' ".format(project_type)
    #access 0 이여도 화면상에는 보이도록
    # if user_id is not None:
    #     if not "where" in sql:
    #         sql += " where "
    #     else:
    #         sql += "and "
    #     sql += " (up.user_id={} or p.access=1) ".format(user_id)

    if sort is not None:
        if sort == "created_datetime":
            sql += " ORDER BY p.create_datetime desc"
        elif sort == "last_run_datetime":
            sql += " ORDER BY p.last_run_datetime desc"

    if page is not None and size is not None:
        sql += " limit {}, {}".format((page-1)*size, size)
    res = await select_query(sql, fetch_type='all')
    return res


def get_project_list_by_instance_not_null(workspace_id : int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT p.*, i.cpu_allocate, i.ram_allocate
            FROM project p
            LEFT JOIN instance i ON i.id = p.instance_id
            WHERE p.workspace_id = %s and p.instance_id IS NOT NULL"""
            cur.execute(sql, (workspace_id, ))
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def get_project_list(search_key=None, size=None, page=None, search_value=None, workspace_id=None, user_id=None, sort=None, project_type=None):
    res = None
    try:
        with get_db() as conn:
        # with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT DISTINCT p.*, u.name as create_user_name, rg.name as resource_name, w.name as workspace_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate
                FROM project p
                LEFT JOIN user u ON u.id = p.create_user_id
                LEFT JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN instance it ON it.id = p.instance_id 
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN user_project up ON up.project_id = p.id
            """

            if search_key is not None and search_value is not None:
                if search_key == "user_id":
                    sql += " where u.id = {} or up.user_id = {} ".format(search_value, search_value)
                else :
                    search_value = '"%{}%"'.format(search_value)
                    sql += " where t.{} like {} ".format(search_key, search_value)


            if workspace_id is not None:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += "and "
                sql += "w.id = {} ".format(workspace_id)


            if project_type is not None:
                if not "where" in sql:
                    sql += "where "
                else:
                    sql += "and "
                sql += "p.type ='{}' ".format(project_type)
            #access 0 이여도 화면상에는 보이도록
            # if user_id is not None:
            #     if not "where" in sql:
            #         sql += " where "
            #     else:
            #         sql += "and "
            #     sql += " (up.user_id={} or p.access=1) ".format(user_id)

            if sort is not None:
                if sort == "created_datetime":
                    sql += " ORDER BY p.create_datetime desc"
                elif sort == "last_run_datetime":
                    sql += " ORDER BY p.last_run_datetime desc"

            if page is not None and size is not None:
                sql += " limit {}, {}".format((page-1)*size, size)
            cur.execute(sql)
            res = cur.fetchall()

    except:
        traceback.print_exc()
    return res

async def delete_project_new(project_id : int):
    sql = """
        DELETE FROM project WHERE id = %s
    """
    await commit_query(query=sql, params=(project_id, ))
    return True

def delete_project(project_id: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM project WHERE id = {project_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
async def insert_projet_new(workspace_id : int, project_type: int, project_name: str, create_user_id:int, access:int, description:str, 
                instance_id: int, instance_allocate: int, job_cpu_limit : float, job_ram_limit : float, tool_cpu_limit : float, tool_ram_limit: float):
    fields = ['workspace_id', 'type', 'name', 'create_user_id', 'access', 'description', 'instance_id', 'instance_allocate', 'job_cpu_limit', 'job_ram_limit', 'tool_cpu_limit', 'tool_ram_limit']
    insert_data = [workspace_id, project_type, project_name, create_user_id, access, description, instance_id, instance_allocate, job_cpu_limit, job_ram_limit, tool_cpu_limit, tool_ram_limit]
    sql = """INSERT INTO {} ({})
        VALUES ({})""".format('project', ', '.join(fields), ', '.join(['%s']*len(fields)))
    
    res = await commit_query(query=sql, params=insert_data)
    return res 
    
async def create_project(**kwargs):
    try:
        fields = kwargs.keys()
        values = kwargs.values()
        sql = """
            INSERT INTO project ({})
            VALUES({})
        """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
        res = await commit_query(query=sql, params=list(values))
        return res
    except Exception as e:
        traceback.print_exc()
        return False



def update_all_project_resource(workspace_id : int, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            if value is not None:
                columns.append(f"{column}=%s")
                values.append(value)
        columns_str = ", ".join(columns)
        values.append(workspace_id)

        with get_db() as conn:
            cur = conn.cursor()
            sql = f""" UPDATE project SET {columns_str} WHERE workspace_id=%s"""
            cur.execute(sql, values)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


def update_project_resource(project_id: int, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            if value is not None:
                columns.append(f"{column}=%s")
                values.append(value)
        columns_str = ", ".join(columns)
        values.append(project_id)

        with get_db() as conn:
            cur = conn.cursor()
            sql = f""" UPDATE project SET {columns_str} WHERE id=%s"""
            cur.execute(sql, values)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


async def update_project_new(project_id : int, project_name : str, access : int, description : str, instance_id: int, instance_allocate: int, owner_id : int, hps_ram_limit : int , hps_cpu_limit : int,
                             job_cpu_limit : float, job_ram_limit : float, tool_cpu_limit : float, tool_ram_limit : float):
    params = [project_name, access, description, instance_id, instance_allocate, owner_id, job_cpu_limit, job_ram_limit, tool_cpu_limit, tool_ram_limit, hps_ram_limit, hps_cpu_limit, project_id]
    sql = """
        UPDATE project SET
        name = %s,
        access = %s,
        description = %s,
        instance_id = %s,
        instance_allocate = %s,
        create_user_id = %s,
        job_cpu_limit = %s,
        job_ram_limit = %s,
        tool_cpu_limit = %s,
        tool_ram_limit = %s,
        hps_ram_limit = %s,
        hps_cpu_limit = %s
        WHERE id = %s
    """
    await commit_query(query=sql, params=params)
    return True

def delete_project_users(project_id : int , user_ids : List[int]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            user_ids_str = ','.join(map(str, user_ids))
            sql = f"""
                DELETE FROM user_project WHERE project_id = {project_id} and user_id in ({user_ids_str})
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def delete_project_users_new(project_id : int):
    """Delete all users from a project (async version)"""
    sql = f"""DELETE FROM user_project WHERE project_id = {project_id}"""
    await commit_query(query=sql)
    return True

def insert_project_tools(project_id: int, tool_list : List[int]):
    from utils import TYPE
    try:
        with get_db() as conn:
            cur = conn.cursor()
            insert_data =[(project_id, tool_type_id)  for tool_type_id in tool_list]
            fields = ['project_id', 'tool_type']
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('project_tool', ', '.join(fields), ', '.join(['%s']*len(fields)))

            cur.executemany(sql, insert_data)

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def delete_tool(project_tool_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM project_tool WHERE id = {project_tool_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
def get_project_tool_by_type(project_id : int, tool_type : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM project_tool
                WHERE project_id = {project_id} AND tool_type = {tool_type}
                ORDER BY id DESC
                LIMIT 1
                """
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res
 
def insert_project_tool(project_id : int, project_tool_type:int, tool_index: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                INSERT INTO project_tool (project_id, tool_type, tool_index) VALUES ({project_id}, {project_tool_type}, {tool_index})
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def insert_project_users_new(project_id : int, user_ids : List[int]):
    insert_data =[(project_id, user_id)  for user_id in user_ids]
    fields = ['project_id', 'user_id']
    sql = """INSERT INTO {} ({})
        VALUES ({})""".format('user_project', ', '.join(fields), ', '.join(['%s']*len(fields)))
    await commit_query(query=sql, params=insert_data, execute="many")
    return True
    
def insert_project_users(project_id : int, user_ids : List[int]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            insert_data =[(project_id, user_id)  for user_id in user_ids]
            fields = ['project_id', 'user_id']
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('user_project', ', '.join(fields), ', '.join(['%s']*len(fields)))

            cur.executemany(sql, insert_data)

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def get_project_users(project_id : int, not_owner : bool = False):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT DISTINCT u.id, u.name AS user_name
                FROM user_project up
                JOIN user u ON u.id = up.user_id
                JOIN project p ON p.id = up.project_id
                WHERE up.project_id = {project_id}"""
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


async def get_project_private_users_new(project_id : int):
    sql = f"""
    SELECT u.id, u.name AS user_name
    FROM user_project up
    JOIN project p ON p.id = up.project_id
    JOIN user u ON  u.id = up.user_id
    WHERE up.project_id = {project_id} AND u.id != p.create_user_id"""

    res = await select_query(sql)
    return res


def get_project_private_users(project_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT u.id, u.name AS user_name
                FROM user_project up
                JOIN project p ON p.id = up.project_id
                JOIN user u ON  u.id = up.user_id
                WHERE up.project_id = {project_id} AND u.id != p.create_user_id"""
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


async def get_project_users_auth_new(project_id, include_owner=True):
    sql = """
        SELECT DISTINCT u.id, u.name AS user_name
        FROM user_project up
        JOIN project p ON p.id = up.project_id
        LEFT JOIN user_workspace uw ON p.workspace_id = uw.workspace_id and p.access= 1
        JOIN user u ON  u.id = uw.user_id OR u.id = up.user_id
        WHERE up.project_id = %s"""
    if include_owner == False:
        sql += " AND (u.id != p.create_user_id)"
    res = await select_query(sql, params=(project_id,))
    return res

def get_project_users_auth(project_id, include_owner=True):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT DISTINCT u.id, u.name AS user_name
                FROM user_project up
                JOIN project p ON p.id = up.project_id
                LEFT JOIN user_workspace uw ON p.workspace_id = uw.workspace_id and p.access= 1
                JOIN user u ON  u.id = uw.user_id OR u.id = up.user_id
                WHERE up.project_id = {project_id}"""
            if include_owner == False:
                sql += " AND (u.id != p.create_user_id)"
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


async def get_project_tool_new(project_tool_id : int):
    sql = f"""
    SELECT pt.*, p.name as project_name, w.name as workspace_name, p.workspace_id, p.create_user_id as owner_id, u.name as owner_name, 
    i.real_name as image_real_name, p.workspace_id, p.instance_id, it.instance_type as resource_type, rg.name as resource_name
    FROM project_tool pt
    JOIN project p ON p.id = pt.project_id
    LEFT JOIN instance it ON it.id = p.instance_id
    LEFT JOIN resource_group rg ON it.gpu_resource_group_id = rg.id
    JOIN workspace w ON w.id = p.workspace_id
    JOIN user u ON u.id = p.create_user_id
    LEFT JOIN image i ON pt.image_id = i.id
    WHERE pt.id = {project_tool_id}
    """
    res = await select_query(sql, fetch_type="one")
    return res

def get_project_tool(project_tool_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT pt.*, p.name as project_name, w.name as workspace_name, p.create_user_id as owner_id, u.name as owner_name, 
                i.real_name as image_real_name, p.workspace_id, p.instance_id, it.instance_type as resource_type, rg.name as resource_name
                FROM project_tool pt
                JOIN project p ON p.id = pt.project_id
                LEFT JOIN instance it ON it.id = p.instance_id
                LEFT JOIN resource_group rg ON it.gpu_resource_group_id = rg.id
                JOIN workspace w ON w.id = p.workspace_id
                JOIN user u ON u.id = p.create_user_id
                LEFT JOIN image i ON pt.image_id = i.id
                WHERE pt.id = {project_tool_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

def update_tool_password(project_tool_id : int, new_password : str):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_tool SET tool_password = '{new_password}'
                WHERE id = {project_tool_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_project_tool_request(project_tool_id : int, request_status : int, gpu_count : int, gpu_cluster_auto : bool, image_id : int, gpu_select : str, \
    tool_password : str): #, dataset_id : int):
    try:
        gpu_cluster_auto = int(gpu_cluster_auto)
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE project_tool SET request_status = %s, gpu_count = %s, gpu_cluster_auto = %s, 
                image_id = %s, gpu_select = %s, start_datetime = NULL, end_datetime = NULL , tool_password=%s, pending_reason = null
                WHERE id = %s
            """
            data = (request_status, gpu_count, gpu_cluster_auto, image_id, gpu_select, tool_password, project_tool_id)
            cur.execute(sql,data)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def update_project_tool_gpu(project_tool_id : int, gpu_count : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_tool SET gpu_count = {gpu_count}
            """
            sql += f" WHERE id = {project_tool_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_project_tool_request_status(request_status : int, project_tool_id: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_tool SET request_status = {request_status} WHERE id = {project_tool_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_project_tool_datetime(project_tool_id : int, start_datetime: str = None, end_datetime : str = None, pod_count : int = 1, error_reason : str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE project_tool SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null, pending_reason = null"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}', request_status = 0, pending_reason = null"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            sql += f", pod_count = {pod_count}"
            sql += f" WHERE id = {project_tool_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def update_project_tool_pending_reason(reason : str, project_tool_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_tool SET pending_reason = '{reason}'
            """
            sql += f" WHERE id = {project_tool_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_project_hps_pending_reason(reason : str, hps_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_hps SET pending_reason = '{reason}', start_datetime = null
            """
            sql += f" WHERE id = {hps_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_project_training_pending_reason(reason : str, training_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE training SET pending_reason = '{reason}', start_datetime = null
            """
            sql += f" WHERE id = {training_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

    
def get_workspace_datasets(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT d.id, d.name, d.access, w.name as workspace_name
                FROM datasets d 
                JOIN workspace w ON w.id = d.workspace_id
                WHERE d.workspace_id = {workspace_id}
                """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res

async def get_dataset_async(dataset_id : int):
    sql = f"""
    SELECT d.*, w.name as workspace_name
    FROM datasets d 
    JOIN workspace w ON w.id = d.workspace_id
    WHERE d.id = %s
    """
    res = await select_query(sql, params=(dataset_id,), fetch_type=FetchType.ONE)
    return res

# def get_dataset(dataset_id : int):
#     res = None
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT *
#                 FROM datasets
#                 WHERE id = {dataset_id}
#                 """
#             cur.execute(sql)
#             res = cur.fetchone()
#         return res
#     except:
#         traceback.print_exc()
#     return res


def get_image_info(image_id : int ):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM image
                WHERE id = {image_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

def update_project_hps_datetime(hps_id : int, start_datetime: str = None, end_status : str = None, end_datetime : str = None, pod_count : int = 1, error_reason : str = ""):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE project_hps SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null, pending_reason = null, error_reason = null"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}'"
            if end_status:
                sql += f", end_status = '{end_status}'"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            sql += f", pod_count = {pod_count}"
            sql += f" WHERE id = {hps_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False


def update_project_training_datetime(training_type :str ,training_id : int, start_datetime: str = None, end_status : str = None, end_datetime : str = None, pod_count : int = 1, error_reason : str = ""):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE {training_type} SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null, pending_reason = null, error_reason = null"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}'"
            if end_status:
                sql += f", end_status = '{end_status}'"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            sql += f", pod_count = {pod_count}"
            sql += f" WHERE id = {training_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    

async def create_project_training(**kwargs) -> int:
    try:
        fields = kwargs.keys()
        values = kwargs.values()
        sql = """
            INSERT INTO training ({})
            VALUES({})
        """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
        res = await commit_query(query=sql, params=list(values))
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def insert_project_training(project_id : int, create_user_id : int, image_id : int,
                            training_name : str, run_code : str , parameter: str,  resource_type:str, 
                            gpu_count : int = 0, gpu_cluster_auto : bool = False, resource_group_id : int = None,
                            distributed_framework : str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = ['project_id', 'create_user_id', 'image_id', "name", "run_code", "parameter", "resource_type", "gpu_count", "gpu_cluster_auto"]
            insert_data = [project_id, create_user_id, image_id, training_name, run_code, parameter, resource_type, gpu_count, int(gpu_cluster_auto)]
            if resource_group_id:
                fields += ["resource_group_id"]
                insert_data += [resource_group_id]
            if distributed_framework:
                fields += ["distributed_framework"]
                insert_data += [distributed_framework]
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('training', ', '.join(fields), ', '.join(['%s']*len(fields)))
            cur.execute(sql, insert_data)

            conn.commit()
            training_id = cur.lastrowid
        return training_id
    except:
        traceback.print_exc()
        return None
    
async def check_duplicate_training(project_id: int, training_name: str):
    """학습 작업 이름 중복 확인"""
    res = None
    try:
        # PyMySQL의 escape_string 사용
        escaped_name = pymysql.escape_string(training_name)
        
        sql = f"""
            SELECT *
            FROM training
            WHERE name = '{escaped_name}' AND project_id = {project_id}
            """
        res = await select_query(sql, fetch_type="one")
        return res
    except Exception as e:
        traceback.print_exc()
        print(f"Error checking duplicate training: {e}")
        return None

def check_duplicate_project(workspace_id: int, project_name: str):
    """프로젝트 이름 중복 확인
    
    Args:
        workspace_id (int): 워크스페이스 ID
        project_name (str): 확인할 프로젝트 이름
        
    Returns:
        dict or None: 중복된 프로젝트가 있으면 프로젝트 정보, 없으면 None
    """
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM project
                WHERE name = %s AND workspace_id = %s
                """
            cur.execute(sql, (project_name, workspace_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        print(f"Error checking duplicate project: {e}")
    return res


async def get_training_new(training_id : int):
    sql = """
    SELECT t.*, w.name as workspace_name, p.name as project_name, p.workspace_id, p.instance_id
    FROM training t
    JOIN project p ON p.id = t.project_id
    JOIN workspace w ON w.id = p.workspace_id
    WHERE t.id = %s
    """
    res = await select_query(sql, params=(training_id,), fetch_type="one")
    return res

def get_training(training_id :int ):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT t.*, w.name as workspace_name, p.name as project_name, p.workspace_id, p.instance_id, p.category, p.built_in_model built_in_model_name, b.id built_in_model_id
                FROM training t
                JOIN project p ON p.id = t.project_id
                JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN built_in_model b ON b.name = p.built_in_model AND b.category = p.category
                WHERE t.id = {training_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

def get_training_infos(training_id_list : List[int] = [], project_id :int = None ):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT t.*, w.name as workspace_name, p.name as project_name
                FROM training t
                JOIN project p ON p.id = t.project_id
                JOIN workspace w ON w.id = p.workspace_id"""
            if training_id_list:
                training_id_list = [str(id) for id in training_id_list]
                training_id_list = ','.join(training_id_list)
                sql += " WHERE t.id in ({})".format(training_id_list)
            else:
                sql += f" WHERE t.project_id = {project_id}"
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res


def delete_training(training_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM training WHERE id = {training_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
async def get_trainings_request(project_id : int ):
    sql = """
    SELECT *
    FROM training
    WHERE project_id = %s AND end_datetime IS NULL
    """
    res = await select_query(query=sql, params=(project_id,))
    return res
    


async def get_trainings_new(project_id : int = None, search_key=None, size=None, page=None, search_value=None, sort=None, order_by="DESC" ):
    sql = f"""
        SELECT t.*, i.name as image_name, u.name as runner_name, p.workspace_id, rg.name as resource_name, d.name as dataset_name
        FROM training t
        LEFT JOIN project p ON p.id = t.project_id
        LEFT JOIN resource_group rg ON rg.id = t.resource_group_id
        LEFT JOIN datasets d ON d.id = t.dataset_id
        LEFT JOIN image i ON i.id = t.image_id
        LEFT JOIN user u ON u.id = t.create_user_id
        """
    if search_key is not None and search_value is not None:
        search_value = '"%{}%"'.format(search_value)
        sql += "where {} like {} ".format(search_key, search_value)

    if project_id is not None:
        if "where" not in sql:
            sql += "where "
        else:
            sql += "and "
        sql += "t.project_id = {}".format(project_id)

    if sort is not None:
        if sort == "start_datetime":
            sql += " ORDER BY t.start_datetime {order_by}, t.id".format(order_by=order_by)
        elif sort == "end_datetime":
            sql += " ORDER BY t.end_datetime {order_by}, t.id".format(order_by=order_by)
        elif sort == "id":
            sql += " ORDER BY t.id {order_by}".format(order_by=order_by)
    else :
        sql += " ORDER BY t.create_datetime {order_by}, t.id".format(order_by=order_by)

    if page is not None and size is not None:
        sql += " limit {}, {}".format((page-1)*size, size)
        
    res = await select_query(sql)
    return res


async def get_project_tool_is_running(project_id : int):
    try:
        sql = f"""
            SELECT *
            FROM project_tool
            WHERE project_id = {project_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
        """
        res = await select_query(sql)
        return res
    except:
        return res

async def get_project_job_is_running(project_id : int):
    try:
        sql = f"""
            SELECT *
                FROM training 
                WHERE project_id = {project_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
        """
        res = await select_query(sql)
        return res
    except:
        return res
    
async def get_project_hps_is_running(project_id : int):
    try:
        sql = f"""
            SELECT *
                FROM project_hps 
                WHERE project_id = {project_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
        """
        res = await select_query(sql)
        return res
    except:
        return res


def get_training_is_running(project_id : int ):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM training 
                WHERE project_id = {project_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
                """ 
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res

def get_hps_is_running(project_id : int ):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM project_hps 
                WHERE project_id = {project_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
                """ 
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_trainings(project_id : int = None, search_key=None, size=None, page=None, search_value=None, sort=None, order_by="DESC" ):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT t.*, i.name as image_name, u.name as runner_name, p.workspace_id, rg.name as resource_name
                FROM training t
                LEFT JOIN project p ON p.id = t.project_id
                LEFT JOIN resource_group rg ON rg.id = t.resource_group_id
                LEFT JOIN image i ON i.id = t.image_id
                LEFT JOIN user u ON u.id = t.create_user_id
                """
            if search_key is not None and search_value is not None:
                search_value = '"%{}%"'.format(search_value)
                sql += "where {} like {} ".format(search_key, search_value)

            if project_id is not None:
                if "where" not in sql:
                    sql += "where "
                else:
                    sql += "and "
                sql += "t.project_id = {}".format(project_id)

            if sort is not None:
                if sort == "start_datetime":
                    sql += " ORDER BY t.start_datetime {order_by}, t.id".format(order_by=order_by)
                elif sort == "end_datetime":
                    sql += " ORDER BY t.end_datetime {order_by}, t.id".format(order_by=order_by)
                elif sort == "id":
                    sql += " ORDER BY t.id {order_by}".format(order_by=order_by)
            else :
                sql += " ORDER BY t.create_datetime {order_by}, t.id".format(order_by=order_by)

            if page is not None and size is not None:
                sql += " limit {}, {}".format((page-1)*size, size)    
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_gpu_models_count():
    res = []
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT rg.name as resource_name, COUNT(*) as total
                FROM node_gpu ng
                JOIN resource_group rg ON rg.id = ng.resource_group_id
                GROUP BY ng.resource_group_id, rg.name
            """

            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


# def get_hps_group(name : str = None, project_id : int = None, hps_group_id : int = None ):
#     res = None
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT hg.*, w.name as workspace_name, p.name as project_name, p.workspace_id,
#                 p.create_user_id, u.name as create_user_name, p.type, p.instance_id, i.instance_type
#                 FROM hps_group hg
#                 JOIN project p ON p.id = hg.project_id
#                 JOIN instance i ON i.id = p.instance_id
#                 JOIN workspace w ON w.id = p.workspace_id
#                 JOIN user u ON u.id = p.create_user_id"""
#             if name and project_id:
#                 sql += f" WHERE hg.project_id = {project_id} AND hg.name = '{name}'"   
#             elif hps_group_id:
#                 sql += f" WHERE hg.id = {hps_group_id}" 
            
#             cur.execute(sql)
#             res = cur.fetchone()
#         return res
#     except:
#         traceback.print_exc()
#     return res


# def insert_hps_group(project_id : int, hps_group_name : str, run_code: str, run_parameter : str, image_id : int):
#     res = None
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             fields = ['project_id', 'run_code', 'run_parameter', 'name', 'image_id']
#             insert_data = [project_id, run_code, run_parameter, hps_group_name, image_id]
            
#             sql = """INSERT INTO {} ({})
#                 VALUES ({})""".format('hps_group', ', '.join(fields), ', '.join(['%s']*len(fields)))

#             cur.execute(sql, insert_data)

#             conn.commit()
#             hps_group_id = cur.lastrowid
#         return hps_group_id
#     except:
#         traceback.print_exc()
#         return res
    

# def insert_hps(hps_info : dict):
#     res = None
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             fields = list(hps_info.keys())
#             insert_data = list(hps_info.values())
#             sql = """INSERT INTO {} ({})
#                 VALUES ({})""".format('hps', ', '.join(fields), ', '.join(['%s']*len(fields)))
#             cur.execute(sql, insert_data)

#             conn.commit()
#             hps_id = cur.lastrowid
#         return hps_id
#     except:
#         traceback.print_exc()
#         return res 
    
    
# def update_project_hps_datetime(hps_id : int, start_datetime: str = None, end_datetime : str = None):
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = """
#                 UPDATE hps SET
#             """
#             if start_datetime:
#                 sql += f" start_datetime = '{start_datetime}', end_datetime = null"
#             if end_datetime:
#                 sql += f" end_datetime = '{end_datetime}'"
#             sql += f" WHERE id = {hps_id}"
#             cur.execute(sql)
#             conn.commit()
#         return True
#     except:
#         traceback.print_exc()
#         return False
    
    
def update_project_item_datetime(item_id : int, item_type : str, start_datetime: str = None, end_datetime : str = None, end_status : str = None, error_reason : str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE {item_type} SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null"
            if end_datetime and end_status:
                sql += f" end_datetime = '{end_datetime}', end_status= '{end_status}'"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            sql += f" WHERE id = {item_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
# def get_hps_workspace(workspace_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  h.*
#                 FROM hps h
#                 LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
#                 LEFT JOIN project p ON p.id = hg.project_id
#                 LEFT JOIN workspace w ON w.id = p.workspace_id
#                 WHERE w.id = {workspace_id}
#                 """
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res


# def get_hps_group_list(project_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  hg.*, i.name as docker_image_name, w.name as workspace_name, p.name as project_name, 
#                 rg.name as resource_name, s.name as storage_name, it.instance_name, p.workspace_id, hg.project_id
#                 FROM hps_group hg
#                 LEFT JOIN project p ON p.id = hg.project_id
#                 LEFT JOIN instance it ON it.id = p.instance_id
#                 LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
#                 LEFT JOIN image i ON i.id = hg.image_id
#                 LEFT JOIN workspace w ON w.id = p.workspace_id
#                 LEFT JOIN storage s ON s.id = w.main_storage_id
#                 WHERE hg.project_id = {project_id}
#                 ORDER BY hg.id DESC
#                 """
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res
#     pass

# def get_hps_list_request(project_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  h.*
#                 FROM hps h
#                 LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
#                 LEFT JOIN project p ON p.id = hg.project_id
#                 WHERE p.id = {project_id} AND end_datetime IS NULL
#                 """
                
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res

# def get_hps_list_by_project(project_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  h.*
#                 FROM hps h
#                 LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
#                 LEFT JOIN project p ON p.id = hg.project_id
#                 WHERE p.id = {project_id}
#                 """
                
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res


# def get_hps_list(hg_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  h.*, i.name as docker_image_name, u.name as create_user_name, w.name as workspace_name, p.name as project_name, 
#                 rg.name as resource_name, s.name as storage_name, it.instance_name, p.workspace_id, hg.project_id
#                 FROM hps h
#                 LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
#                 LEFT JOIN project p ON p.id = hg.project_id
#                 LEFT JOIN instance it ON it.id = p.instance_id
#                 LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
#                 LEFT JOIN image i ON i.id = hg.image_id
#                 LEFT JOIN workspace w ON w.id = p.workspace_id
#                 LEFT JOIN storage s ON s.id = w.main_storage_id
#                 LEFT JOIN user u ON u.id = h.create_user_id
#                 WHERE h.hps_group_id = {hg_id}
#                 ORDER BY h.id DESC
#                 """
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res


# def get_hps_info_list(hps_id_list : List[int] = [], project_id : int = None):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
            
#             sql = """
#                 SELECT h.*, hg.name, hg.project_id, w.name as workspace_name, p.name as project_name, p.workspace_id
#                 FROM hps h
#                 JOIN hps_group hg ON hg.id = h.hps_group_id 
#                 JOIN project p ON p.id = hg.project_id
#                 JOIN workspace w ON w.id = p.workspace_id"""
#             if hps_id_list:
#                 hps_id_list = [str(id) for id in hps_id_list]
#                 hps_id_list = ','.join(hps_id_list)
#                 sql += " WHERE h.id in ({})".format(hps_id_list)
#             else:
#                 sql += f" WHERE hg.project_id = {project_id}"
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res
    
# def delete_hps(hps_id : int):
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 DELETE FROM hps WHERE id = {hps_id}
#             """
#             cur.execute(sql)
#             conn.commit()
#         return True
#     except:
#         traceback.print_exc()
#         return False
    
# def get_hps_list_by_group_id(hps_group_id : int):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
            
#             sql = f"""
#                 SELECT h.*
#                 FROM hps h
#                 WHERE h.hps_group_id = {hps_group_id}
#                 """
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res

# def delete_hps_group(hps_group_id : int):
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 DELETE FROM hps_group WHERE id = {hps_group_id}
#             """
#             cur.execute(sql)
#             conn.commit()
#         return True
#     except:
#         traceback.print_exc()
#         return False
    
    
# def get_last_hps_group_index(hps_group_id : int):
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
            
#             sql = f"""
#                 SELECT MAX(hps_group_index) AS max_index
#                 FROM hps h
#                 WHERE h.hps_group_id = {hps_group_id}
#                 GROUP BY h.hps_group_id
#                 """
#             cur.execute(sql)
#             res = cur.fetchone()
#         return res
#     except:
#         traceback.print_exc()
#     return res

# def get_hps(hps_id : int):
#     res = None
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
            
#             sql = f"""
#                 SELECT h.*, w.name as workspace_name, p.name as project_name, hg.name as hps_group_name, w.id as workspace_id, p.id as project_id, hg.run_parameter, s.name as storage_name
#                 FROM hps h
#                 JOIN hps_group hg ON h.hps_group_id = hg.id
#                 JOIN project p ON p.id = hg.project_id
#                 JOIN workspace w ON w.id = p.workspace_id
#                 JOIN storage s ON s.id = w.main_storage_id
#                 WHERE h.id = {hps_id}
#                 """
#             cur.execute(sql)
#             res = cur.fetchone()
#         return res
#     except:
#         traceback.print_exc()
#     return res

async def get_user_project_bookmark_list_new(user_id):
    res = []
    sql = """
        SELECT *
        FROM project_bookmark
        WHERE user_id = {}
    """.format(user_id)
    res = await select_query(sql)
    return res

def get_user_project_bookmark_list(user_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT *
                FROM project_bookmark
                WHERE user_id = {}
            """.format(user_id)

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
        return []
    return res

def insert_project_bookmark(project_id, user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                INSERT INTO project_bookmark (project_id, user_id)
                VALUES (%s,%s)
            """
            cur.execute(sql, (project_id, user_id))
            conn.commit()
        return True, ""
    except pymysql.err.IntegrityError as ie:
        raise Exception("Already bookmarked")
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_project_bookmark(project_id, user_id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
                DELETE FROM project_bookmark WHERE project_id = %s AND user_id = %s
                """
            cur.execute(sql, (project_id, user_id))
            conn.commit()

        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def get_built_in_model_parameter(model_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT DISTINCT bmp.parameter, bmp.parameter_description, bmp.default_value
                    FROM built_in_model_parameter bmp
                    WHERE bmp.built_in_model_id = {}
                """.format(model_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res



# ===========================================================
# HPS
# ===========================================================

async def create_project_hps(**kwargs) -> int:
    try:
        fields = kwargs.keys()
        values = kwargs.values()
        sql = """
            INSERT INTO project_hps ({})
            VALUES({})
        """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
        res = await commit_query(query=sql, params=list(values))
        return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_hps_detail(hps_id : int):
    try:
        sql = f"""
            SELECT ph.*, p.name as project_name, p.workspace_id, w.name as workspace_name
            FROM project_hps ph
            LEFT JOIN project p ON p.id = ph.project_id
            LEFT JOIN workspace w ON p.workspace_id = w.id
            WHERE ph.id = {hps_id}
        """
        res = await select_query(sql,fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None
    
def get_hps(hps_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT ph.*, p.name project_name, p.built_in_model, p.category, b.id built_in_model_id
                FROM project_hps ph
                LEFT JOIN project p ON p.id = ph.project_id
                LEFT JOIN built_in_model b ON b.name = p.built_in_model AND b.category = p.category
                WHERE ph.id = {hps_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

async def get_hps_list(project_id : int):
    try:
        sql = """
            SELECT ph.id, ph.name, ph.create_datetime, ph.start_datetime, ph.end_datetime, ph.resource_type, ph.run_code, ph.parameter, ph.fixed_parameter,
            ph.gpu_count, ph.built_in_search_count, i.name as image_name, d.name as dataset_name, ph.dataset_data_path, ph.end_status, ph.error_reason, ph.target_metric,
            ph.project_id
            FROM project_hps ph
            LEFT JOIN image i ON ph.image_id = i.id
            LEFT JOIN datasets d ON d.id = ph.dataset_id
            WHERE ph.project_id = %s
            ORDER BY ph.id DESC
            
        """
        res = await select_query(sql, params=(project_id,))
        return res
    except Exception as e:
        traceback.print_exc()
        return []
    
    
async def delete_hps(hps_id : int):
    try:
        sql = f"""
        DELETE FROM project_hps WHERE id = {hps_id}
        """
        res = await commit_query(query=sql)
        return True
    except Exception as e:
        traceback.print_exc()
        return False
    

async def get_project_tool_port_list(project_tool_id : int):
    try:
        sql = """
            SELECT * FROM project_tool_port WHERE project_tool_id = %s
        """
        res = await select_query(sql, params=(project_tool_id,))
        return res
    except Exception as e:  
        traceback.print_exc()
        return []

async def insert_project_tool_port(project_tool_id : int, port : int, protocol : str, description : str, create_user_name : str, ingress_path : str):
    try:
        sql = """
            INSERT INTO project_tool_port (project_tool_id, port, protocol, description, create_user_name, ingress_path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        res = await commit_query(query=sql, params=(project_tool_id, port, protocol, description, create_user_name, ingress_path))
        return res
    except Exception as e:
        traceback.print_exc()
        return None
    
async def delete_project_tool_port(project_tool_id : int, port : int, protocol : str):
    try:
        sql = """
            DELETE FROM project_tool_port WHERE project_tool_id = %s AND port = %s AND protocol = %s
        """
        res = await commit_query(query=sql, params=(project_tool_id, port, protocol))
        return res
    except Exception as e:
        traceback.print_exc()
        return None
async def delete_project_tool_port_all(project_tool_id : int):
    try:
        sql = """
            DELETE FROM project_tool_port WHERE project_tool_id = %s
        """
        res = await commit_query(query=sql, params=(project_tool_id,))
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def insert_project_tool_port_history(
        project_id : int, project_name : str, workspace_id : int, workspace_name : str,
        project_item_id : int, project_item_type : str, create_user_name : str, action_type : str, 
        port : int, protocol : str, description : str, ingress_path : str):
    try:
        sql = """
            INSERT INTO project_tool_port_history (
                project_id, project_name, workspace_id, workspace_name, 
                project_item_id, project_item_type, create_user_name, 
                action_type, port, protocol, description, ingress_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        res = await commit_query(query=sql, params=(
            project_id, project_name, workspace_id, workspace_name, 
            project_item_id, project_item_type, create_user_name, 
            action_type, port, protocol, description, ingress_path))
        return res
    except Exception as e:
        traceback.print_exc()
        return None
    
