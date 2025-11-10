import traceback
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils import TYPE

async def get_playground_list(workspace_id=None):
    sql = """
    SELECT p.id, p.name, p.workspace_id, p.create_user_id, p.description, p.access, p.deployment, p.model, p.rag, p.prompt,
    DATE_FORMAT(p.create_datetime, %s) create_datetime, DATE_FORMAT(p.update_datetime, %s) update_datetime
    FROM playground p
    """
    if workspace_id is not None:
        sql += " WHERE p.workspace_id='{}' ".format(workspace_id)
    sql += """ ORDER BY id DESC """

    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL))
    return res

async def get_playground(playground_id):
    """
    p.id, p.name, p.workspace_id, p.create_user_id, p.description,
        p.model, p.model_parameter, p.rag, p.prompt, p.deployment, p.accelerator,
    """
    sql = """
        SELECT p.*, 
        DATE_FORMAT(p.create_datetime, %s) create_datetime, DATE_FORMAT(p.update_datetime, %s) update_datetime,
        w.name workspace_name, s.name workspace_main_storage_name
        FROM jonathan_llm.playground p
        LEFT JOIN msa_jfb.workspace w ON w.id = p.workspace_id
        LEFT JOIN msa_jfb.storage s ON s.id = w.main_storage_id
        WHERE p.id=%s
        """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, playground_id), fetch_type=FetchType.ONE)
    return res

async def insert_playground(workspace_id, create_user_id, name, description, access):
    try:
        sql = """INSERT into playground (workspace_id, create_user_id, name, description, access)
                    VALUES (%s,%s,%s,%s,%s)"""
        playground_id = await commit_query(query=sql, params=(workspace_id, create_user_id, name, description, access))
        return True, playground_id
    except:
        traceback.print_exc()
        return False, None

async def update_playground(playground_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            columns.append(f"{column}=%s")
            values.append(value)
        columns_str = ", ".join(columns)
        values.append(playground_id)

        sql = f"""
                UPDATE playground p SET {columns_str}
                WHERE p.id = %s
                """
        await commit_query(query=sql, params=values)
        return True  
    except:
        traceback.print_exc()
        return False

async def delete_playground(id_list):
    if len(id_list) == 0:
        return True
    try:
        sql = """
            DELETE FROM playground
            WHERE id in ({})""".format(','.join(str(e) for e in id_list))
        await commit_query(query=sql)
        return True
    except:
        traceback.print_exc()
        return False


# ================================================================================================================

async def get_playground_url(playground_id):
    sql = """
        SELECT p.id, p.name, p.workspace_id, JSON_EXTRACT(p.deployment, '$.deployment_playground_id') AS deployment_id, msad.api_path
        FROM jonathan_llm.playground p
        LEFT JOIN msa_jfb.deployment msad ON msad.id = JSON_EXTRACT(p.deployment, '$.deployment_playground_id')
        WHERE p.id=%s
        """
    res = await select_query(sql, params=(playground_id), fetch_type=FetchType.ONE)
    return res

async def get_test_log_list(playground_id):
    sql = """
        SELECT pt.*
        FROM playground_test pt
        WHERE pt.playground_id=%s
        """
    res = await select_query(sql, playground_id)
    return res

async def delete_playground_test(playground_id):
    try:
        sql = """
            DELETE FROM playground_test WHERE playground_id=%s"""
        await commit_query(query=sql, params=(playground_id))
        return True
    except:
        traceback.print_exc()
        return False

# ================================================================================================================

async def get_user_playground_bookmark_list(user_id):
    sql = """SELECT playground_id FROM playground_bookmark WHERE user_id=%s"""
    res = await select_query(sql, params=(user_id,))
    return res

async def insert_playground_bookmark(playground_id, user_id):
    try:
        sql = """INSERT into playground_bookmark (playground_id, user_id) VALUES (%s,%s)"""
        await commit_query(query=sql, params=(playground_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

async def delete_playground_bookmark(playground_id, user_id):
    try:
        sql = """DELETE FROM playground_bookmark WHERE playground_id=%s AND user_id=%s"""
        await commit_query(query=sql, params=(playground_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

# ================================================================================================================
        
async def insert_user_playground_list(playgrounds_id, users_id):
    try:
        rows = []
        for i in range(len(playgrounds_id)):
            rows.append((playgrounds_id[i],users_id[i]))
        sql = "INSERT IGNORE into user_playground(playground_id, user_id) values (%s,%s)"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

async def delete_user_playground(playgrounds_id, users_id):
    try:
        rows = []
        for i in range(len(playgrounds_id)):
            rows.append((playgrounds_id[i],users_id[i]))
        sql = "DELETE from user_playground where playground_id = %s and user_id = %s"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e   

async def get_user_playground_list(playground_id=None):
    res = []
    try:
        sql = """
            SELECT up.*, u.name user_name
            FROM user_playground up
            INNER JOIN msa_jfb.user u ON u.id = up.user_id
        """
        if playground_id is not None:
            sql = f"{sql} where up.playground_id='{playground_id}'"
        res = await select_query(sql,)
    except:
        traceback.print_exc()
    return res