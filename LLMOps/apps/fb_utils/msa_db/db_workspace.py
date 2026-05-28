from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from utils import settings

from typing import List

import traceback


async def get_workspace_instance(workspace_id : int, instance_id : int):
    sql = """
        SELECT wi.*, i.gpu_allocate 
        FROM workspace_instance wi
        JOIN instance i ON wi.instance_id = i.id
        WHERE workspace_id = %s and instance_id = %s
    """
    res = await select_query(query=sql, params=(workspace_id, instance_id), fetch_type="one")
    return res

def get_basic_workspace_list():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT * FROM workspace
                """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res
    

def insert_workspace(manager_id:int, workspace_name:str, start_datetime:str, end_datetime:str, description:str, path:str, data_storage_size:str, main_storage_size:str, data_storage_id: int, main_storage_id: int, use_marker: int = 0):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            fields = ['manager_id', 'name','start_datetime', 'end_datetime', 'description', 'path', 'data_storage_size', 'main_storage_size', 'data_storage_id','main_storage_id', 'use_marker']
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('workspace', ', '.join(fields), ', '.join(['%s']*len(fields)))

            cur.execute(sql, (manager_id, workspace_name, start_datetime, end_datetime, description, path, data_storage_size, main_storage_size, data_storage_id,main_storage_id, use_marker))

            conn.commit()
            workspace_id = cur.lastrowid
        return workspace_id
    except:
        traceback.print_exc()
        return False
    
# def insert_workspace_request(manager_id:int, workspace_name:str, start_datetime:str, end_datetime:str, description:str, path:str, data_storage_size:str, main_storage_size:str, data_storage_id: int, main_storage_id: int, user_list : str, allocate_instance_list : str,
#                              workspace_id: int = None, type: str = None):
def insert_workspace_request(**kwargs):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # fields = ['manager_id', 'name','start_datetime', 'end_datetime', 'description', 'path', 'data_storage_size', 'main_storage_size', 'data_storage_id','main_storage_id', 'user_list', 'allocate_instance_list']
            # sql = """INSERT INTO {} ({})
            #     VALUES ({})""".format('workspace_request', ', '.join(fields), ', '.join(['%s']*len(fields)))

            # cur.execute(sql, (manager_id, workspace_name, start_datetime, end_datetime, description, path, data_storage_size, main_storage_size, data_storage_id,main_storage_id, user_list, allocate_instance_list))

            columns = ','.join([key if key != "workspace_name" else "name" for key in kwargs.keys()])
            values = ', '.join(['%s'] * len(kwargs))
            insert_values = [None if val is None else val for val in kwargs.values()]

            sql = f"INSERT INTO workspace_request ({columns}) VALUES ({values})"
            cur.execute(sql, (insert_values))
            conn.commit()
            
            workspace_id = cur.lastrowid
        return workspace_id
    except:
        traceback.print_exc()
        return False    

def update_workspace_storage_size(workspace_id: int , data_storage_id: int, main_storage_id: int, data_storage_size: int, main_storage_size: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = """
                UPDATE workspace SET
                data_storage_id = %s, main_storage_id = %s, data_storage_size = %s, main_storage_size = %s
                WHERE id = %s
            """
            cur.execute(sql, (data_storage_id, main_storage_id, data_storage_size, main_storage_size, workspace_id))
            
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_workspace(manager_id: int, workspace_id: int , start_datetime: str, end_datetime: str, description: str):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                UPDATE workspace SET
                manager_id = %s, start_datetime = %s, end_datetime = %s, description = %s
                WHERE id = %s
            """
            cur.execute(sql, (manager_id, start_datetime, end_datetime, description, workspace_id))

            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False
def update_workspace_use_marker(workspace_id: int, use_marker: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = """
                UPDATE workspace SET
                use_marker = %s
                WHERE id = %s
            """
            cur.execute(sql, (use_marker, workspace_id))
            
            conn.commit()
        return True
    except Exception as e:
        # use_marker 컬럼이 없는 경우를 체크
        if "Unknown column 'use_marker'" in str(e):
            print(f"use_marker column does not exist in workspace table. Skipping use_marker update for workspace_id: {workspace_id}")
            return True  # 컬럼이 없어도 성공으로 처리
        else:
            traceback.print_exc()
            return False

def update_workspace_quota(workspace_id: int , data_storage_lock: int= None, main_storage_lock: int= None):
    # lock 0 : 정상
    # lock 1 : 경고 80%~
    # lock 2 : 삭제 및 기능 제한 090%
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                UPDATE workspace 
            """
            if data_storage_lock is not None:
                sql+=f"SET data_storage_lock = {data_storage_lock}"
            if main_storage_lock is not None:
                sql+=f"SET main_storage_lock = {main_storage_lock}"

            sql+=f" WHERE id = {workspace_id}"
            print(sql)
            cur.execute(sql)

            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False
    
async def get_workspace_resource_new(workspace_id : int):
    res = []
    sql = """SELECT wr.* 
        FROM workspace_resource wr
        WHERE wr.workspace_id=%s
        """
    res = await select_query(query=sql, params=(workspace_id,), fetch_type="one")
    return res

# async def get_workspace_async(workspace_name : str = None, workspace_id : int = None):
#     try:
#         sql = """
#             SELECT w.*, u.name as manager_name
#             FROM workspace w
#             INNER JOIN user u ON w.manager_id = u.id"""
#         if workspace_name is not None:
#             sql += f" WHERE w.name = '{workspace_name}'"
#         elif workspace_id is not None:
#             sql += f" WHERE w.id = {workspace_id}"
#         res = await select_query(query=sql, fetch_type='one')
#         return res
#     except Exception as e:
#         traceback.print_exc()
#     return {}

async def get_workspace_async(workspace_name : str = None, workspace_id : int = None):
    try:
        sql = """
            SELECT w.*, u.name as manager_name, s_main.name main_storage_name, s_data.name data_storage_name
                FROM workspace w
                INNER JOIN user u ON w.manager_id = u.id
                INNER JOIN storage s_main ON s_main.id = w.main_storage_id 
                INNER JOIN storage s_data ON s_data.id = w.data_storage_id 
            """
        if workspace_name is not None:
            sql += f" WHERE w.name = '{workspace_name}'"
        elif workspace_id is not None:
            sql += f" WHERE w.id = {workspace_id}"
        res = await select_query(query=sql, fetch_type='one')
        return res
    except Exception as e:
        traceback.print_exc()
        return {}

def get_workspace(workspace_name=None, workspace_id=None):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT w.*, u.name as manager_name, s_main.name main_storage_name, s_data.name data_storage_name
                FROM workspace w
                INNER JOIN user u ON w.manager_id = u.id
                INNER JOIN storage s_main ON s_main.id = w.main_storage_id 
                INNER JOIN storage s_data ON s_data.id = w.data_storage_id 
                """

            if workspace_name is not None:
                sql += f" WHERE w.name = '{workspace_name}'"
            elif workspace_id is not None:
                sql += f" WHERE w.id = {workspace_id}"
            cur.execute(sql)
            res = cur.fetchone()

    except:
        traceback.print_exc()
    return res

def get_workspace_requests():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT wr.*, u.name as manager_name
                FROM workspace_request wr
                INNER JOIN user u ON wr.manager_id = u.id"""
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_workspace_request(request_workspace_id : int = None, request_workspace_name=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT wr.*
                FROM workspace_request wr"""
                
            if request_workspace_name is not None:
                sql += f" WHERE wr.name = '{request_workspace_name}'"
            elif request_workspace_id is not None:
                sql += f" WHERE wr.id='{request_workspace_id}'"
            
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def delete_workspace_request(request_workspace_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM workspace_request WHERE id = {request_workspace_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False



def get_workspace_list(page : int=None, size: int=None, search_key: str=None, search_value: str=None, user_id: int=None, sort: int=None):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT DISTINCT w.*, u.name as manager_name
            FROM workspace w
            INNER JOIN user as u ON w.manager_id = u.id
            INNER JOIN user_workspace uw ON uw.workspace_id = w.id"""
            
            if search_key != None and search_value != None:
                sql += " and " if "where" in sql else " where "
                if search_key == "name":
                    sql += " w.{} like '%{}%' ".format(search_key, search_value)
                elif search_key == "user_id":
                    sql += " w.manager_id = {} or uw.user_id = {} ".format(search_value, search_value)
                else:
                    sql += " {} = {} ".format(search_key, search_value)
            
            if user_id is not None:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += "and "
                sql += " w.id in (select workspace_id from user_workspace WHERE user_id={}) ".format(user_id,user_id)        
            
            if sort is not None:
                if sort == "created_datetime":
                    sql += " ORDER BY w.create_datetime desc "
                elif sort == "last_run_datetime":
                    sql += " ORDER BY p.last_run_datetime desc "
            else :
                sql += " ORDER BY w.create_datetime desc, w.id asc "

            if page is not None and size is not None:
                sql += " limit {}, {} ".format((page-1)*size, size)
            
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def delete_workspace(workspace_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM workspace WHERE id = {workspace_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False


async def get_workspace_item_count_async(workspace_id : int):
    try:
        res = {}
        sql = """
            SELECT (SELECT COUNT(*) FROM datasets d WHERE d.workspace_id = w.id) AS datasets,
                   (SELECT COUNT(*) FROM project p WHERE p.workspace_id = w.id) AS trainings,
                   (SELECT COUNT(*) FROM deployment dp WHERE dp.workspace_id = w.id) AS deployments,
                   (SELECT COUNT(*) FROM image i 
                    LEFT JOIN image_workspace iw ON i.id = iw.image_id 
                    WHERE (i.access = 1) OR (i.access = 0 AND iw.workspace_id = %s)) AS images
            """
        params = [workspace_id]

        if settings.LLM_USED:
            sql += """,
            (SELECT COUNT(*) FROM jonathan_llm.model m WHERE m.workspace_id = w.id) AS models,
            (SELECT COUNT(*) FROM jonathan_llm.playground pg WHERE pg.workspace_id = w.id) AS playgrounds,
            (SELECT COUNT(*) FROM jonathan_llm.prompt pt WHERE pt.workspace_id = w.id) AS prompts,
            (SELECT COUNT(*) FROM jonathan_llm.rag r WHERE r.workspace_id = w.id) AS rags
            """

        sql += """
            FROM workspace w 
            WHERE w.id = %s
        """
        params.append(workspace_id)
        res = await select_query(sql, params, FetchType.ONE)
        return res 
    except Exception as e:
        traceback.print_exc()
        return {}


def get_workspace_item_count(workspace_id: int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT (SELECT COUNT(*) FROM datasets d WHERE d.workspace_id = w.id) AS datasets,
                   (SELECT COUNT(*) FROM project p WHERE p.workspace_id = w.id) AS trainings,
                   (SELECT COUNT(*) FROM deployment dp WHERE dp.workspace_id = w.id) AS deployments,
                   (SELECT COUNT(*) FROM image i 
                    LEFT JOIN image_workspace iw ON i.id = iw.image_id 
                    WHERE (i.access = 1) OR (i.access = 0 AND iw.workspace_id = %s)) AS images
            """
            params = [workspace_id]

            if settings.LLM_USED:
                sql += """,
                (SELECT COUNT(*) FROM jonathan_llm.model m WHERE m.workspace_id = w.id) AS models,
                (SELECT COUNT(*) FROM jonathan_llm.playground pg WHERE pg.workspace_id = w.id) AS playgrounds,
                (SELECT COUNT(*) FROM jonathan_llm.prompt pt WHERE pt.workspace_id = w.id) AS prompts,
                (SELECT COUNT(*) FROM jonathan_llm.rag r WHERE r.workspace_id = w.id) AS rags
                """

            sql += """
                FROM workspace w 
                WHERE w.id = %s
            """
            params.append(workspace_id)

            cur.execute(sql, params)
            res = cur.fetchone()
        
        return res
    except Exception as e:
        traceback.print_exc()
    
    return res


# def get_workspace_instance_manage(workspace_id : int):
#     try:
#         res = None
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#             SELECT SUM(wim.type_instance_allocate) as instance_allocate, wim.type, i.gpu_allocate
#             FROM workspace_instance_manage wim
#             JOIN workspace_instance wi ON wi.id = wim.workspace_instance_id
#             JOIN instance i ON i.id = wi.instance_id
#             WHERE wi.workspace_id = {workspace_id}
#             GROUP BY wim.type
#             """
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except Exception as e:
#         traceback.print_exc()
#     return res

def insert_user_workspace(workspace_id, user_id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT IGNORE into user_workspace(workspace_id, user_id) values (%s,%s)"
            cur.execute(sql, (workspace_id, user_id))
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False

def get_workspace_users(workspace_id=None):
    res = []
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """SELECT u.id, u.name as user_name, uw.favorites, uw.workspace_id as workspace_id
                FROM user_workspace uw
                INNER JOIN user u ON uw.user_id = u.id
            """
            if workspace_id is not None:
                sql += "WHERE workspace_id = {}".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_memory_count():
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT SUM(size) as total
                FROM node_ram
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

# def get_allocated_memory_count(workspace_id : int = None):
#     try:
#         with get_db() as conn:

#             cur = conn.cursor()
#             sql = f"""
#                 SELECT SUM(allocate) as allocated
#                 FROM workspace_resource 
#                 WHERE resource_type = '{ResourceType.MEMORY.value}'"""
#             if workspace_id:
#                 sql += f" AND workspace_id != {workspace_id}"
#             cur.execute(sql)
#             res = cur.fetchone()
#         return res
#     except:
#         traceback.print_exc()
#     return res

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


# def get_cpu_models_count():
#     res = []
#     try:
#         with get_db() as conn:

#             cur = conn.cursor()
#             sql = """
#                 SELECT rg.name as resource_name, SUM(nc.core) as core
#                 FROM node_cpu nc
#                 JOIN resource_group rg ON rg.id = nc.resource_group_id
#                 GROUP BY nc.resource_group_id, rg.name
#             """

#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res





def get_gpu_allocate_models_count(workspace_id : int = None):
    """
    모든 워크스페이스에 할당된 GPU 자원별 할당량
    """
    res = []
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = f"""
                SELECT rg.name as resource_name, SUM(wr.allocate) as allocated
                FROM workspace_resource wr
                JOIN resource_group rg ON rg.id = wr.resource_group_id"""
            if workspace_id:
                sql += f" AND wr.workspace_id != {workspace_id}"
            sql += " GROUP BY wr.resource_group_id"
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res

# def get_cpu_allocate_models_count(workspace_id : int = None):
#     """
#     모든 워크스페이스에 할당된 CPU 자원별 할당량
#     """
#     res = []
#     try:
#         with get_db() as conn:

#             cur = conn.cursor()
#             sql = f"""
#                 SELECT  rg.name as resource_name, SUM(wr.allocate) as allocated
#                 FROM workspace_resource wr
#                 JOIN resource_group rg ON rg.id = wr.resource_group_id
#                 WHERE resource_type = '{ResourceType.CPU.value}'"""
#             if workspace_id:
#                 sql += f" AND wr.workspace_id != {workspace_id}"
#             sql += " GROUP BY wr.resource_group_id"
#             cur.execute(sql)
#             res = cur.fetchall()
#         return res
#     except:
#         traceback.print_exc()
#     return res

def update_favorites(user_id, workspace_id, action):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "UPDATE user_workspace set favorites = {} where user_id = {} and workspace_id = {}".format(action, user_id, workspace_id)
            cur.execute(sql)
            conn.commit()

        return True
    except Exception as e:
        print(e)
        return False
    
    
def insert_user_workspace_s(workspaces_id: list, users_id: list):
    # workspaces_id = [[1,2,3],[1],[],[1,3]]
    # users_id = [1,2,3]
    try:
        with get_db() as conn:

            cur = conn.cursor()

            rows = []
            for i in range(len(workspaces_id)):
                for workspace_id in workspaces_id[i]:
                    rows.append((workspace_id,users_id[i]))
            sql = "INSERT into user_workspace(workspace_id,user_id) values (%s,%s)"
            # cur.execute(sql, (workspace_id, user_id))
            cur.executemany(sql, rows)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def delete_user_workspace_s(workspaces_id: list, users_id: list):
    # workspaces_id = [[1,2,3],[1],[],[1,3]]
    # users_id = [1,2,3]
    try:
        with get_db() as conn:

            cur = conn.cursor()

            rows = []
            for i in range(len(workspaces_id)):
                for workspace_id in workspaces_id[i]:
                    rows.append((workspace_id,users_id[i]))
            sql = "DELETE from user_workspace where workspace_id = %s and user_id = %s"
            # cur.execute(sql, (workspace_id, user_id))
            cur.executemany(sql, rows)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
    
    
def get_user_workspace(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT w.id, w.name as workspace_name
                FROM user_workspace uw
                INNER JOIN workspace w ON uw.workspace_id = w.id
                WHERE uw.user_id in (%s) OR w.manager_id in (%s)"""

            cur.execute(sql, (user_id,user_id))
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


# instance ===========================================================================================
def get_instance_list():
    """
    instance_allocate: workspace_instance 들의 instance_allocate를 합산하여 하나의 인스턴스에 총 사용량을 보여줌
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT i.*,  rg.name resource_name,
                            COALESCE(SUM(wi.instance_allocate), 0) as instance_allocate
                    FROM instance i
                    LEFT JOIN workspace_instance wi ON wi.instance_id = i.id
                    LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                    GROUP BY i.id"""
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res
    
def get_workspace_instance_list(workspace_id):
    """resource_group은 left join (gpu 설정 안한 경우 group_id 없는 경우도 있음)
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""SELECT wi.instance_id, wi.instance_allocate, i.cpu_allocate, i.ram_allocate, i.gpu_allocate, rg.name as resource_name, i.instance_type, i.instance_name
                    FROM workspace_instance wi
                    INNER JOIN instance i ON i.id = wi.instance_id
                    LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                    WHERE wi.workspace_id='{workspace_id}'
                    """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_workspace_image_list(workspace_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT i.real_name
            FROM image_workspace iw 
            JOIN image i ON i.id = iw.image_id
            WHERE iw.workspace_id=%s
            """
            cur.execute(sql, (workspace_id))
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res
            

def get_workspace_instance_min(workspace_id):
    """resource_group은 left join (gpu 설정 안한 경우 group_id 없는 경우도 있음)
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""SELECT min(i.cpu_allocate) min_cpu_allocate, min(i.ram_allocate) min_ram_allocate
                    FROM workspace_instance wi
                    INNER JOIN instance i ON i.id = wi.instance_id
                    LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                    WHERE wi.workspace_id='{workspace_id}'
                    """
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res


def insert_workspace_instance(workspace_id, allocate_instances : List[dict]):
    """
    allocate_instances : [{
        "instance_id" : int,
        "allocate" : str,
    }]
    """
    try:
        param_list = [(workspace_id, item["instance_id"], item["instance_allocate"]) for item in allocate_instances]
        with get_db() as conn:
            cur = conn.cursor()
            sql = """INSERT INTO workspace_instance (workspace_id, instance_id, instance_allocate)
            VALUES (%s, %s, %s)"""
            cur.executemany(sql, param_list)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def delete_workspace_instance(workspace_id=None, instance_id=None, instance_id_list=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if instance_id == "all":
                sql = "DELETE FROM workspace_instance WHERE workspace_id=%s"
                cur.execute(sql, (workspace_id))
            elif instance_id is not None and workspace_id is not None:
                sql = """DELETE FROM workspace_instance
                        WHERE workspace_id=%s AND instance_id=%s"""
                cur.execute(sql, (workspace_id, instance_id))
            elif instance_id_list is not None and len(instance_id_list) > 0 and workspace_id is not None:
                # injection?
                format_strings = ','.join(['%s'] * len(instance_id_list))
                sql = f"""DELETE FROM workspace_instance
                        WHERE workspace_id=%s AND instance_id in ({format_strings})"""
                cur.execute(sql, [workspace_id] + instance_id_list)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def udpate_workspace_instance(workspace_id, allocate_instances : List[dict]):
    try:
        param_list = [(item["instance_allocate"], item["instance_id"], workspace_id) for item in allocate_instances]
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE workspace_instance set instance_allocate = %s
                    WHERE instance_id=%s AND workspace_id=%s"""
            cur.executemany(sql, (param_list))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def reset_workspace_deployment_instance(workspace_id, instance_id_list=[]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE deployment set instance_id=NULL, instance_allocate=0,
            deployment_cpu_limit=0, deployment_ram_limit=0
            WHERE workspace_id=%s"""
            params = [workspace_id]
            
            if instance_id_list and len(instance_id_list) > 0:
                sql += " and instance_id in %s"
                params.append(tuple(instance_id_list))
                
            cur.execute(sql, tuple(params))
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
        
def reset_workspace_project_instance(workspace_id, instance_id_list=[]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE project set instance_id=NULL, instance_allocate=0, 
            job_cpu_limit=0, job_ram_limit=0, tool_cpu_limit=0, tool_ram_limit=0,
            hps_cpu_limit=0, hps_ram_limit=0
            WHERE workspace_id=%s"""
            params = [workspace_id]
            
            if instance_id_list and len(instance_id_list) > 0:
                sql += " and instance_id in %s"
                params.append(tuple(instance_id_list))
                
            cur.execute(sql, tuple(params))
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

def reset_workspace_collect_instance(workspace_id, instance_id_list=[]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE collect set instance_id=NULL, instance_allocate=0
            WHERE workspace_id=%s"""
            params = [workspace_id]
            
            if instance_id_list and len(instance_id_list) > 0:
                sql += " and instance_id in %s"
                params.append(tuple(instance_id_list))
                
            cur.execute(sql, tuple(params))
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

def reset_workspace_preprocessing_instance(workspace_id, instance_id_list=[]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE preprocessing set instance_id=NULL, instance_allocate=0,
            job_cpu_limit=0, job_ram_limit=0, tool_cpu_limit=0, tool_ram_limit=0
            WHERE workspace_id=%s"""
            params = [workspace_id]
            
            if instance_id_list and len(instance_id_list) > 0:
                sql += " and instance_id in %s"
                params.append(tuple(instance_id_list))
                
            cur.execute(sql, tuple(params))
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

def reset_workspace_analyzer_instance(workspace_id, instance_id_list=[]):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE analyzer set instance_id=NULL, instance_allocate=0
            WHERE workspace_id=%s"""
            params = [workspace_id]
            
            if instance_id_list and len(instance_id_list) > 0:
                sql += " and instance_id in %s"
                params.append(tuple(instance_id_list))
                
            cur.execute(sql, tuple(params))
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

def get_workspace_instance_allocate(workspace_id):
    """특정 워크스페이스에 할당된 인스턴스 총 개수"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT instance_allocate
                   FROM workspace_instance wi
                   WHERE workspace_id=%s"""
            cur.execute(sql, (workspace_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        return 0
    
    
def get_workspace_allocate_instance(workspace_id, instance_id):
    """특정 워크스페이스의 특정 인스턴스 할당 개수"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT instance_allocate
                   FROM workspace_instance wi
                   WHERE workspace_id=%s and instance_id=%s"""
            cur.execute(sql, (workspace_id, instance_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        return {"instance_allocate" : 0}

    
    
    

def get_sum_instance_allocate(instance_id):
    """모든 워크스페이스에 할당된 인스턴스 총 개수"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT SUM(wi.instance_allocate) as all_instance_allocate
                   FROM workspace_instance wi
                   WHERE instance_id=%s"""
            cur.execute(sql, (instance_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        return 0

def get_sum_instance_allocate_except_workspace_id(instance_id, workspace_id):
    """입력된 워크스페이스 id를 제외하고 워크스페이스에 할당된 인스턴스 총 개수"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT SUM(wi.instance_allocate) as using_instance
                   FROM workspace_instance wi
                   WHERE instance_id=%s AND workspace_id !=%s"""
            cur.execute(sql, (instance_id, workspace_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        return 0

# resource ===========================================================================================



def get_workspace_resource(workspace_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT wr.* 
                    FROM workspace_resource wr
                    WHERE wr.workspace_id=%s
                    """
            cur.execute(sql, (workspace_id))
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
        return None

def insert_workspace_resource(workspace_id, tool_cpu_limit, tool_ram_limit,
    job_cpu_limit, job_ram_limit, hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """INSERT INTO workspace_resource (workspace_id, tool_cpu_limit, tool_ram_limit, job_cpu_limit, job_ram_limit,
            hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (workspace_id, tool_cpu_limit, tool_ram_limit, job_cpu_limit, job_ram_limit, hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_workspace_resource(workspace_id, tool_cpu_limit, tool_ram_limit,
    job_cpu_limit, job_ram_limit, hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE workspace_resource
            SET tool_cpu_limit=%s, tool_ram_limit=%s, job_cpu_limit=%s, job_ram_limit=%s, hps_cpu_limit=%s, hps_ram_limit=%s, deployment_cpu_limit=%s, deployment_ram_limit=%s
            WHERE workspace_id=%s"""
            cur.execute(sql, (tool_cpu_limit, tool_ram_limit, job_cpu_limit, job_ram_limit, hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit, workspace_id))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return None
    
def update_workspace_project_deployment_resource_limit(workspace_id, cpu_limit, ram_limit):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """UPDATE deployment
            SET deployment_cpu_limit=%s, deployment_ram_limit=%s
            WHERE workspace_id=%s"""
            cur.execute(sql, (cpu_limit, ram_limit, workspace_id))
            conn.commit()
    
            sql = """UPDATE project
            SET job_cpu_limit=%s, job_ram_limit=%s, tool_cpu_limit=%s, tool_ram_limit=%s
            WHERE workspace_id=%s"""
            cur.execute(sql, (cpu_limit, ram_limit, cpu_limit, ram_limit, workspace_id))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    

# def get_all_user_in_workspace(
#     workspace_id: int
# ) -> bool:
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()
#             sql = """
#             SELECT user_id
#             FROM user_workspace
#             WHERE workspace_id = %s
#             """
#             cur.execute(sql, (workspace_id,))
#             users = cur.fetchall()
#         return users
#     except:
#         traceback.print_exc()
#         return []