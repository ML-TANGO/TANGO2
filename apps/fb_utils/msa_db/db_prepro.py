from utils.msa_db.db_base import get_db, pymysql
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List


import traceback




######################
# SELECT
######################
async def get_preprocessing_all():
    try:
        sql = """
        SELECT *
        FROM preprocessing
        """
        res = await select_query(sql)
        return res
    except Exception as e:
        traceback.print_exc()
        return []


async def get_preprocessing_users_auth(preprocessing_id: int):
    sql = """
        SELECT u.id, u.name as user_name
        FROM user_preprocessing up
        JOIN user u ON u.id = up.user_id
        WHERE up.preprocessing_id = %s"""
    res = await select_query(sql, params=(preprocessing_id,))
    return res

async def get_favorite_preprocessing(preprocessing_id : int, user_id : int):
    sql = """
        SELECT * FROM preprocessing_bookmark
        WHERE preprocessing_id = %s AND user_id = %s
    """
    res = await select_query(sql, params=(preprocessing_id, user_id), fetch_type=FetchType.ONE)
    
    return res is not None 

def get_job_simple(preprocessing_job_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT pj.*, p.instance_id
            FROM preprocessing_job pj
            JOIN preprocessing p ON p.id = pj.preprocessing_id
            WHERE pj.id = {preprocessing_job_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def get_job_is_running(preprocessing_id : int ):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM preprocessing_job
                WHERE preprocessing_id = {preprocessing_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
                """ 
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_preprocessing_tools_sync(preprocessing_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT pt.*, i.name as image_name
            FROM preprocessing_tool pt
            LEFT JOIN image i ON i.id = pt.image_id
            WHERE preprocessing_id = {preprocessing_id} AND pt.start_datetime IS NOT NULL AND pt.end_datetime IS NULL
            """
            
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

# db_user - def get_user로 변경함(klod)
# async def get_user(user_name : str = None, user_id : int = None):
#     try:
#         sql = f"""
#         SELECT id, name, user_type
#         FROM user"""
#         params = None
#         if user_id:
#             sql += " WHERE id = %s"
#             params = (user_id, )
#         elif user_name:
#             sql += " WHERE name = %s"
#             params = (user_name, )
#         res = await select_query(query=sql, params=params, fetch_type=FetchType.ONE)    
        
#         return res
#     except Exception as e:
#         traceback.print_exc()
#     return None


async def get_user_preprocessing_bookmark_list(user_id):
    try:
        sql = """
            SELECT * FROM preprocessing_bookmark WHERE user_id = %s
        """
        res = await select_query(query=sql, params=(user_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []
    
async def get_user_preprocessing_list_by_instance_id(workspace_id : int, instance_id : int):
    try:
        sql = """
            SELECT p.* FROM preprocessing p
            WHERE p.workspace_id = %s AND p.instance_id = %s
        """
        res = await select_query(query=sql, params=(workspace_id, instance_id))
        return res
    except Exception as e:
        traceback.print_exc()
        return []


def get_preprocessing_list_by_instance_not_null(workspace_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT p.*, i.cpu_allocate, i.ram_allocate
            FROM preprocessing p
            LEFT JOIN instance i ON i.id = p.instance_id
            WHERE p.workspace_id = %s and p.instance_id IS NOT NULL"""
            cur.execute(sql, (workspace_id,))
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return []


def get_preprocessing_list_sync(search_key=None, size=None, page=None, search_value=None, workspace_id=None, sort=None, preprocessing_type=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT DISTINCT p.*, u.name as owner_name, rg.name as resource_name, w.name as workspace_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate, it.instance_type
            FROM preprocessing p
            LEFT JOIN user u ON u.id = p.owner_id
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


            if preprocessing_type is not None:
                if not "where" in sql:
                    sql += "where "
                else:
                    sql += "and "
                sql += "p.type ='{}' ".format(preprocessing_type)

            if sort is not None:
                if sort == "created_datetime":
                    sql += " ORDER BY p.create_datetime desc"
                elif sort == "last_run_datetime":
                    sql += " ORDER BY p.last_run_datetime desc"

            if page is not None and size is not None:
                sql += " limit {}, {}".format((page-1)*size, size)
            cur.execute(sql)
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return []


async def get_preprocessing_list(search_key=None, size=None, page=None, search_value=None, workspace_id=None, sort=None, preprocessing_type=None):
    try:
        sql = """
            SELECT DISTINCT p.*, u.name as owner_name, rg.name as resource_name, w.name as workspace_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate, it.instance_type
            FROM preprocessing p
            LEFT JOIN user u ON u.id = p.owner_id
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


        if preprocessing_type is not None:
            if not "where" in sql:
                sql += "where "
            else:
                sql += "and "
            sql += "p.type ='{}' ".format(preprocessing_type)

        if sort is not None:
            if sort == "created_datetime":
                sql += " ORDER BY p.create_datetime desc"
            elif sort == "last_run_datetime":
                sql += " ORDER BY p.last_run_datetime desc"

        if page is not None and size is not None:
            sql += " limit {}, {}".format((page-1)*size, size)
        res = await select_query(sql, fetch_type='all')
        return res
    except Exception as e:
        traceback.print_exc()
        return []
    
async def get_preprocessing_tool_by_request(preprocessing_id : int):
    try:
        sql = """
        SELECT *
        FROM preprocessing_tool
        WHERE preprocessing_id = %s AND request_status = 1
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []
    
async def get_preprocessing_tools(preprocessing_id : int):
    try:
        sql = """
        SELECT pt.*, i.name as image_name
        FROM preprocessing_tool pt
        LEFT JOIN image i ON i.id = pt.image_id
        WHERE preprocessing_id = %s
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []


async def get_jobs_is_running(preprocessing_id : int = None):
    try:
        sql = """
        SELECT * FROM preprocessing_job WHERE preprocessing_id = %s AND start_datetime IS NOT NULL AND end_datetime IS NULL
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []    
    
async def get_jobs_is_request(preprocessing_id : int = None):
    try:
        sql = """
        SELECT * FROM preprocessing_job WHERE preprocessing_id = %s AND end_datetime IS NULL
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []    

async def get_jobs_simple(preprocessing_id : int):
    try:
        sql = """
        SELECT *
        FROM preprocessing_job
        WHERE preprocessing_id = %s
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []

async def get_jobs(preprocessing_id : int = None, search_key=None, size=None, page=None, search_value=None, sort=None, order_by="DESC" ):
    try:
        sql = """
        SELECT pj.*, i.name as image_name, u.name as runner_name, p.workspace_id, rg.name as resource_name, d.name as dataset_name
        FROM preprocessing_job pj
        LEFT JOIN preprocessing p ON p.id = pj.preprocessing_id
        LEFT JOIN resource_group rg ON rg.id = pj.resource_group_id
        LEFT JOIN datasets d ON d.id = pj.dataset_id
        LEFT JOIN image i ON i.id = pj.image_id
        LEFT JOIN user u ON u.id = pj.create_user_id
        """
        if search_key is not None and search_value is not None:
            search_value = '"%{}%"'.format(search_value)
            sql += "where {} like {} ".format(search_key, search_value)

        if preprocessing_id is not None:
            if "where" not in sql:
                sql += "where "
            else:
                sql += "and "
            sql += "pj.preprocessing_id = {}".format(preprocessing_id)

        if sort is not None:
            if sort == "start_datetime":
                sql += " ORDER BY pj.start_datetime {order_by}, pj.id".format(order_by=order_by)
            elif sort == "end_datetime":
                sql += " ORDER BY pj.end_datetime {order_by}, pj.id".format(order_by=order_by)
            elif sort == "id":
                sql += " ORDER BY pj.id {order_by}".format(order_by=order_by)
        else :
            sql += " ORDER BY pj.create_datetime {order_by}, pj.id".format(order_by=order_by)

        if page is not None and size is not None:
            sql += " limit {}, {}".format((page-1)*size, size)
        res = await select_query(sql)
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_preprocessing_simple_sync(preprocessing_id : int = None, preprocessing_name : str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT p.*
            FROM preprocessing p
            """
            if preprocessing_id:
                sql += " WHERE p.id = %s"
                cur.execute(sql, (preprocessing_id,))
            elif preprocessing_name:
                sql += " WHERE p.name = %s"
                cur.execute(sql, (preprocessing_name,))
            res = cur.fetchone()
            return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_preprocessing_simple(preprocessing_id : int = None, preprocessing_name : str = None):
    try:
        sql = """
        SELECT p.*
        FROM preprocessing p
        """
        if preprocessing_id:
            sql += " WHERE p.id = %s"
            res = await select_query(sql, params=(preprocessing_id,), fetch_type=FetchType.ONE)
        elif preprocessing_name:
            sql += " WHERE p.name = %s"
            res = await select_query(sql, params=(preprocessing_name,), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None


async def get_category_name(category_id : int, category_type : str):
    try:
        sql = f"""
        SELECT name FROM {category_type} WHERE id = {category_id}
        """
        res = await select_query(sql, fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None


async def get_preprocessing(workspace_id : int = None, preprocessing_id : int = None, preprocessing_name : str = None):
    try:
        sql = """
        SELECT p.*, u.name as owner_name, w.name as workspace_name, rg.name as resource_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate, it.instance_type, it.gpu_resource_group_id
        FROM preprocessing p
        LEFT JOIN user u ON u.id = p.owner_id
        LEFT JOIN workspace w ON w.id = p.workspace_id
        LEFT JOIN instance it ON it.id = p.instance_id 
        LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
        """
        if preprocessing_id:
            sql += " WHERE p.id = %s"
            res = await select_query(sql, params=(preprocessing_id,), fetch_type=FetchType.ONE)
        elif preprocessing_name:
            sql += " WHERE p.workspace_id =%s AND p.name = %s"
            res = await select_query(sql, params=(workspace_id, preprocessing_name), fetch_type=FetchType.ONE)
        else:
            res = await select_query(sql, fetch_type="all")
        return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_workspace_name_and_id_list():
    try:
        sql = """
        SELECT w.id, w.name
        FROM workspace w
        """
        res = await select_query(sql)
        return res
    except Exception as e:
        traceback.print_exc()
        return []

async def get_workspace_instances(workspace_id : int):
    try:
        sql = """
        SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
        FROM workspace_instance wi
        JOIN instance i ON i.id = wi.instance_id
        LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
        WHERE wi.workspace_id = %s
        """
        res = await select_query(sql, params=(workspace_id, ))
        return res 
    except Exception as e:
        traceback.print_exc()
        return []

async def get_workspace_dataset_list(workspace_id : int):
    try:
        sql = """
        SELECT d.id, d.name
        FROM datasets d
        WHERE d.workspace_id = %s
        """
        res = await select_query(sql, params=(workspace_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []

async def get_workspace_image_list(workspace_id :int = None):
    try:
        sql = """
        SELECT i.id, i.name
        FROM image i
        LEFT JOIN image_workspace iw ON iw.image_id = i.id
        WHERE i.status =2 and ( (i.access = 1) or (i.access = 0 and iw.workspace_id = %s) )
        """
        res = await select_query(sql, params=(workspace_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []

async def get_workspace_user_name_and_id_list(workspace_id : int):
    try:
        sql = """
        SELECT u.id, u.name
        from user_workspace uw
        inner join user u on uw.user_id = u.id
        where workspace_id = %s
        """
        res = await select_query(sql, params=(workspace_id, ))
        return res  
    except Exception as e:
        traceback.print_exc()
        return []

async def get_preprocessing_private_users(preprocessing_id : int):
    try:
        sql = """
        SELECT u.id, u.name as user_name
        FROM user_preprocessing up
        JOIN preprocessing p ON p.id = up.preprocessing_id
        JOIN user u ON  u.id = up.user_id
        WHERE up.preprocessing_id = %s AND u.id != p.owner_id
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []

async def get_preprocessing_tool_by_type(preprocessing_id : int, tool_type : int):
    try:
        sql = """
        SELECT *
        FROM preprocessing_tool
        WHERE preprocessing_id = %s AND tool_type = %s
        ORDER BY id DESC
        LIMIT 1
        """
        res = await select_query(sql, params=(preprocessing_id, tool_type), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_preprocessing_user_list(preprocessing_id : int):
    try:
        sql = """
        SELECT u.id, u.name as user_name
        FROM user_preprocessing up
        JOIN user u ON u.id = up.user_id
        WHERE up.preprocessing_id = %s
        """
        res = await select_query(sql, params=(preprocessing_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_preprocessing_tool_sync(preprocessing_tool_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT pt.*, p.name as preprocessing_name, w.name as workspace_name, p.workspace_id, p.owner_id, u.name as owner_name, 
            i.real_name as image_real_name, p.workspace_id, p.instance_id, it.instance_type as resource_type, rg.name as resource_name
            FROM preprocessing_tool pt
            JOIN preprocessing p ON p.id = pt.preprocessing_id
            LEFT JOIN instance it ON it.id = p.instance_id
            LEFT JOIN resource_group rg ON it.gpu_resource_group_id = rg.id
            JOIN workspace w ON w.id = p.workspace_id
            JOIN user u ON u.id = p.owner_id
            LEFT JOIN image i ON pt.image_id = i.id
            WHERE pt.id = {preprocessing_tool_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
            return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_preprocessing_tool(preprocessing_tool_id : int):
    try:
        sql = f"""
        SELECT pt.*, p.name as preprocessing_name, w.name as workspace_name, p.owner_id, u.name as owner_name, 
        i.real_name as image_real_name, p.workspace_id, p.instance_id, it.instance_type as resource_type, rg.name as resource_name
        FROM preprocessing_tool pt
        JOIN preprocessing p ON p.id = pt.preprocessing_id
        LEFT JOIN instance it ON it.id = p.instance_id
        LEFT JOIN resource_group rg ON it.gpu_resource_group_id = rg.id
        JOIN workspace w ON w.id = p.workspace_id
        JOIN user u ON u.id = p.owner_id
        LEFT JOIN image i ON pt.image_id = i.id
        WHERE pt.id = {preprocessing_tool_id}
        """
        res = await select_query(sql, fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None

async def get_job(job_id : int):
    try:
        sql = f"""
            SELECT pj.*, p.workspace_id
            FROM preprocessing_job pj
            JOIN preprocessing p ON p.id = pj.preprocessing_id
            WHERE pj.id = {job_id}
        """
        res = await select_query(sql, fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None
    


######################
# INSERT
######################

async def insert_preprocessing_users(preprocessing_id : int, user_ids : List[int]):
    try:
        if not user_ids:
            return True
        insert_data =[(preprocessing_id, user_id)  for user_id in user_ids]
        fields = ['preprocessing_id', 'user_id']
        sql = """INSERT IGNORE INTO {} ({})
            VALUES ({})""".format('user_preprocessing', ', '.join(fields), ', '.join(['%s']*len(fields)))
        await commit_query(query=sql, params=insert_data, execute="many")
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def create_preprocessing(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO preprocessing ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_preprocessing_private_user(preprocessing_id : int, user_id : int):
    try:
        sql = """
        INSERT INTO user_preprocessing (user_id, preprocessing_id)
        VALUES (%s, %s)
        """
        res = await commit_query(query=sql, params=(user_id, preprocessing_id))
        return res
    except Exception as e:
        traceback.print_exc()
        return False

async def create_preprocessing_tool(**kwargs) -> int:
    try:
        fields = kwargs.keys()
        values = kwargs.values()
        sql = """
            INSERT INTO preprocessing_tool ({})
            VALUES({})
        """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
        await commit_query(query=sql, params=list(values))
        return True
    except Exception as e:
        traceback.print_exc()
        return False
    

async def create_favorite_preprocessing(**kwargs):
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO preprocessing_bookmark ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res


async def create_preprocessing_job(**kwargs):
    try:
        fields = kwargs.keys()
        values = kwargs.values()
        sql = """
            INSERT INTO preprocessing_job ({})
            VALUES({})
        """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
        res = await commit_query(query=sql, params=list(values))
        return res
    except Exception as e:
        traceback.print_exc()
        return False

######################
# UPDATE
######################

async def delete_favorite_preprocessing(preprocessing_id: int, user_id : int) -> bool:
    sql="DELETE FROM preprocessing_bookmark WHERE preprocessing_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(preprocessing_id, user_id))
    return True

# async def delete_model_user_list(preprocessing_id : int, user_id : int) -> bool:
#     sql="DELETE FROM preprocessing_model WHERE preprocessing_id=%s AND user_id=%s"
#     await commit_query(query=sql, params=(preprocessing_id, user_id))
#     return True

def update_preprocessing_job_pending_reason(reason : str, preprocessing_job_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE preprocessing_job SET pending_reason = '{reason}', start_datetime = null
            """
            sql += f" WHERE id = {preprocessing_job_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_preprocessing_job_datetime(preprocessing_job_id : int, start_datetime: str = None, end_datetime : str = None, error_reason : str= "", end_status : str = "", pod_count : int = 1):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE preprocessing_job SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null, pending_reason = null"
                sql += f", pod_count = {pod_count}"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}'"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            if end_status:
                sql += f", end_status = '{end_status}'"
            sql += f" WHERE id = {preprocessing_job_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False


def update_preprocessing_tool_pending_reason(reason : str, preprocessing_tool_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE preprocessing_tool SET pending_reason = '{reason}'
            """
            sql += f" WHERE id = {preprocessing_tool_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_preprocessing_tool_datetime(preprocessing_tool_id : int, start_datetime: str = None, end_datetime : str = None, error_reason: str = "", pod_count : int = 1):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE preprocessing_tool SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null, pending_reason = null"
                sql += f", pod_count = {pod_count}"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}', request_status = 0, pending_reason = null"
            if error_reason:
                sql += f", error_reason = '{error_reason}'"
            sql += f" WHERE id = {preprocessing_tool_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def update_preprocessing_tool_request(preprocessing_tool_id : int, request_status : int, gpu_count : int, gpu_cluster_auto : bool, image_id : int, gpu_select : str, \
    tool_password : str, dataset_id : int):
    try:
        sql = """
                UPDATE preprocessing_tool SET request_status = %s, gpu_count = %s, gpu_cluster_auto = %s, dataset_id = %s,
                image_id = %s, gpu_select = %s, start_datetime = NULL, end_datetime = NULL , tool_password=%s, pending_reason = null, error_reason = null
                WHERE id = %s
            """
        data = (request_status, gpu_count, gpu_cluster_auto, dataset_id, image_id, gpu_select, tool_password, preprocessing_tool_id)
        
        res = await commit_query(sql, data)
        return True
    except:
        traceback.print_exc()
        return False

async def update_preprocessing_tool_request_status(request_status : int, preprocessing_tool_id: int):
    try:
        sql = f"""
                UPDATE preprocessing_tool SET request_status = {request_status} WHERE id = {preprocessing_tool_id}
            """
        res = await commit_query(sql)
        return True
    except:
        traceback.print_exc()
        return False



# async def get_dataset_async(dataset_id : int):
#     try:
        
#         sql = f"""
#         SELECT d.*, w.name as workspace_name
#         FROM datasets d 
#         JOIN workspace w ON w.id = d.workspace_id
#         WHERE d.id = %s
#         """
#         res = await select_query(sql, params=(dataset_id,), fetch_type=FetchType.ONE)
#         return res
#     except:
#         traceback.print_exc()
#         return False
 
async def update_preprocessing(preprocessing_id : int, access : int, description : str, instance_id: int, instance_allocate: int, owner_id : int,
                             job_cpu_limit : float, job_ram_limit : float, tool_cpu_limit : float, tool_ram_limit : float, update_datetime : str):
    params = [access, description, instance_id, instance_allocate, owner_id, job_cpu_limit, job_ram_limit, tool_cpu_limit, tool_ram_limit, update_datetime, preprocessing_id]
    sql = """
        UPDATE preprocessing SET
        access = %s,
        description = %s,
        instance_id = %s,
        instance_allocate = %s,
        owner_id = %s,
        job_cpu_limit = %s,
        job_ram_limit = %s,
        tool_cpu_limit = %s,
        tool_ram_limit = %s,
        update_datetime = %s
        WHERE id = %s
    """
    await commit_query(query=sql, params=params)
    return True       

######################
# DELETE
######################

def delete_job(job_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM preprocessing_job WHERE id = {job_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def delete_preprocessing(preprocessing_id : int):
    try:
        
        sql = """
            DELETE FROM preprocessing WHERE id = %s
        """
        await commit_query(query=sql, params=(preprocessing_id, ))
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def delete_tool(preprocessing_tool_id : int):
    try:
        sql = f"""
                DELETE FROM preprocessing_tool WHERE id = {preprocessing_tool_id}
            """
        await commit_query(sql)
        return True
    except:
        traceback.print_exc()
        return False


async def delete_preprocessing_users(preprocessing_id : int , user_ids : List[int]):
    try:
        if not user_ids:
            # user_ids가 비어있으면 전체 삭제
            sql = f"""
                DELETE FROM user_preprocessing WHERE preprocessing_id = {preprocessing_id}
            """
        else:
            user_ids_str = ','.join(map(str, user_ids))
            sql = f"""
                DELETE FROM user_preprocessing WHERE preprocessing_id = {preprocessing_id} and user_id in ({user_ids_str})
            """
        await commit_query(sql)
        return True
    except:
        traceback.print_exc()
        return False











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



    


def get_project(workspace_id : int = None, project_id : int = None, project_name : str = None):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT p.*, u.name as create_user_name, w.name as workspace_name, rg.name as resource_name, i.gpu_allocate, 
            i.gpu_resource_group_id, s.name as storage_name, i.instance_type, i.instance_name, 
            i.cpu_allocate as  instance_cpu, i.ram_allocate as instance_ram, i.instance_count
            FROM project p
            JOIN user u ON u.id = p.create_user_id
            JOIN workspace w ON w.id = p.workspace_id
            JOIN storage s ON w.main_storage_id = s.id
            LEFT JOIN instance i ON i.id = p.instance_id
            LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id"""
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


# def get_project_list(search_key=None, size=None, page=None, search_value=None, workspace_id=None, user_id=None, sort=None, project_type=None):
#     res = None
#     try:
#         with get_db() as conn:
#         # with get_db() as conn:

#             cur = conn.cursor()
#             sql = """
#                 SELECT DISTINCT p.*, u.name as create_user_name, rg.name as resource_name, w.name as workspace_name, it.gpu_allocate, it.instance_name, it.cpu_allocate, it.ram_allocate
#                 FROM project p
#                 LEFT JOIN user u ON u.id = p.create_user_id
#                 LEFT JOIN workspace w ON w.id = p.workspace_id
#                 LEFT JOIN instance it ON it.id = p.instance_id 
#                 LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
#                 LEFT JOIN user_project up ON up.project_id = p.id
#             """

#             if search_key is not None and search_value is not None:
#                 if search_key == "user_id":
#                     sql += " where u.id = {} or up.user_id = {} ".format(search_value, search_value)
#                 else :
#                     search_value = '"%{}%"'.format(search_value)
#                     sql += " where t.{} like {} ".format(search_key, search_value)


#             if workspace_id is not None:
#                 if not "where" in sql:
#                     sql += " where "
#                 else:
#                     sql += "and "
#                 sql += "w.id = {} ".format(workspace_id)


#             if project_type is not None:
#                 if not "where" in sql:
#                     sql += "where "
#                 else:
#                     sql += "and "
#                 sql += "p.type ='{}' ".format(project_type)
#             #access 0 이여도 화면상에는 보이도록
#             # if user_id is not None:
#             #     if not "where" in sql:
#             #         sql += " where "
#             #     else:
#             #         sql += "and "
#             #     sql += " (up.user_id={} or p.access=1) ".format(user_id)

#             if sort is not None:
#                 if sort == "created_datetime":
#                     sql += " ORDER BY p.create_datetime desc"
#                 elif sort == "last_run_datetime":
#                     sql += " ORDER BY p.last_run_datetime desc"

#             if page is not None and size is not None:
#                 sql += " limit {}, {}".format((page-1)*size, size)
#             cur.execute(sql)
#             res = cur.fetchall()

#     except:
#         traceback.print_exc()
#     return res



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
    
def insert_project(workspace_id : int, project_type: int, project_name: str, create_user_id:int, access:int, description:str, 
                instance_id: int, instance_allocate: int):
    project_id = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            fields = ['workspace_id', 'type', 'name', 'create_user_id', 'access', 'description', 'instance_id', 'instance_allocate']
            insert_data = [workspace_id, project_type, project_name, create_user_id, access, description, instance_id, instance_allocate]
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('project', ', '.join(fields), ', '.join(['%s']*len(fields)))
            cur.execute(sql, insert_data)

            conn.commit()
            project_id = cur.lastrowid
        return project_id
    except:
        traceback.print_exc()
        return project_id


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



def update_project_tool_datetime(project_tool_id : int, start_datetime: str = None, end_datetime : str = None, pod_count : int = 1):
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
            sql += f", pod_count = {pod_count}"
            sql += f" WHERE id = {project_tool_id}"
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
                SELECT t.*, w.name as workspace_name, p.name as project_name, p.workspace_id, p.instance_id
                FROM training t
                JOIN project p ON p.id = t.project_id
                JOIN workspace w ON w.id = p.workspace_id
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

def get_hps_group(name : str = None, project_id : int = None, hps_group_id : int = None ):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT hg.*, w.name as workspace_name, p.name as project_name, p.workspace_id,
                p.create_user_id, u.name as create_user_name, p.type, p.instance_id, i.instance_type
                FROM hps_group hg
                JOIN project p ON p.id = hg.project_id
                JOIN instance i ON i.id = p.instance_id
                JOIN workspace w ON w.id = p.workspace_id
                JOIN user u ON u.id = p.create_user_id"""
            if name and project_id:
                sql += f" WHERE hg.project_id = {project_id} AND hg.name = '{name}'"   
            elif hps_group_id:
                sql += f" WHERE hg.id = {hps_group_id}" 
            
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res


def insert_hps_group(project_id : int, hps_group_name : str, run_code: str, run_parameter : str, image_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = ['project_id', 'run_code', 'run_parameter', 'name', 'image_id']
            insert_data = [project_id, run_code, run_parameter, hps_group_name, image_id]
            
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('hps_group', ', '.join(fields), ', '.join(['%s']*len(fields)))

            cur.execute(sql, insert_data)

            conn.commit()
            hps_group_id = cur.lastrowid
        return hps_group_id
    except:
        traceback.print_exc()
        return res
    

def insert_hps(hps_info : dict):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = list(hps_info.keys())
            insert_data = list(hps_info.values())
            sql = """INSERT INTO {} ({})
                VALUES ({})""".format('hps', ', '.join(fields), ', '.join(['%s']*len(fields)))
            cur.execute(sql, insert_data)

            conn.commit()
            hps_id = cur.lastrowid
        return hps_id
    except:
        traceback.print_exc()
        return res 
    
    
def update_project_hps_datetime(hps_id : int, start_datetime: str = None, end_datetime : str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE hps SET
            """
            if start_datetime:
                sql += f" start_datetime = '{start_datetime}', end_datetime = null"
            if end_datetime:
                sql += f" end_datetime = '{end_datetime}'"
            sql += f" WHERE id = {hps_id}"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
    
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
    
def get_hps_workspace(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT  h.*
                FROM hps h
                LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
                LEFT JOIN project p ON p.id = hg.project_id
                LEFT JOIN workspace w ON w.id = p.workspace_id
                WHERE w.id = {workspace_id}
                """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_hps_group_list(project_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT  hg.*, i.name as docker_image_name, w.name as workspace_name, p.name as project_name, 
                rg.name as resource_name, s.name as storage_name, it.instance_name, p.workspace_id, hg.project_id
                FROM hps_group hg
                LEFT JOIN project p ON p.id = hg.project_id
                LEFT JOIN instance it ON it.id = p.instance_id
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN image i ON i.id = hg.image_id
                LEFT JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN storage s ON s.id = w.main_storage_id
                WHERE hg.project_id = {project_id}
                ORDER BY hg.id DESC
                """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res
    pass

def get_hps_list_request(project_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT  h.*
                FROM hps h
                LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
                LEFT JOIN project p ON p.id = hg.project_id
                WHERE p.id = {project_id} AND end_datetime IS NULL
                """
                
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res

def get_hps_list_by_project(project_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT  h.*
                FROM hps h
                LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
                LEFT JOIN project p ON p.id = hg.project_id
                WHERE p.id = {project_id}
                """
                
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_hps_list(hg_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT  h.*, i.name as docker_image_name, u.name as create_user_name, w.name as workspace_name, p.name as project_name, 
                rg.name as resource_name, s.name as storage_name, it.instance_name, p.workspace_id, hg.project_id
                FROM hps h
                LEFT JOIN hps_group hg ON h.hps_group_id = hg.id
                LEFT JOIN project p ON p.id = hg.project_id
                LEFT JOIN instance it ON it.id = p.instance_id
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN image i ON i.id = hg.image_id
                LEFT JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN storage s ON s.id = w.main_storage_id
                LEFT JOIN user u ON u.id = h.create_user_id
                WHERE h.hps_group_id = {hg_id}
                ORDER BY h.id DESC
                """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res


def get_hps_info_list(hps_id_list : List[int] = [], project_id : int = None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = """
                SELECT h.*, hg.name, hg.project_id, w.name as workspace_name, p.name as project_name, p.workspace_id
                FROM hps h
                JOIN hps_group hg ON hg.id = h.hps_group_id 
                JOIN project p ON p.id = hg.project_id
                JOIN workspace w ON w.id = p.workspace_id"""
            if hps_id_list:
                hps_id_list = [str(id) for id in hps_id_list]
                hps_id_list = ','.join(hps_id_list)
                sql += " WHERE h.id in ({})".format(hps_id_list)
            else:
                sql += f" WHERE hg.project_id = {project_id}"
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res
    
def delete_hps(hps_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM hps WHERE id = {hps_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def get_hps_list_by_group_id(hps_group_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = f"""
                SELECT h.*
                FROM hps h
                WHERE h.hps_group_id = {hps_group_id}
                """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return res

def delete_hps_group(hps_group_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM hps_group WHERE id = {hps_group_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
    
def get_last_hps_group_index(hps_group_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = f"""
                SELECT MAX(hps_group_index) AS max_index
                FROM hps h
                WHERE h.hps_group_id = {hps_group_id}
                GROUP BY h.hps_group_id
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

def get_hps(hps_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = f"""
                SELECT h.*, w.name as workspace_name, p.name as project_name, hg.name as hps_group_name, w.id as workspace_id, p.id as project_id, hg.run_parameter, s.name as storage_name
                FROM hps h
                JOIN hps_group hg ON h.hps_group_id = hg.id
                JOIN project p ON p.id = hg.project_id
                JOIN workspace w ON w.id = p.workspace_id
                JOIN storage s ON s.id = w.main_storage_id
                WHERE h.id = {hps_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res



# def get_user_project_bookmark_list(user_id):
#     res = []
#     try:
#         with get_db() as conn:
#             cur = conn.cursor()

#             sql = """
#                 SELECT *
#                 FROM project_bookmark
#                 WHERE user_id = {}
#             """.format(user_id)

#             cur.execute(sql)
#             res = cur.fetchall()
#     except Exception as e:
#         traceback.print_exc()
#         return []
#     return res

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