from utils.msa_db.db_base import get_db, pymysql
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
import traceback

# async --------------------------------------------------------------------------------

async def get_built_in_model(category : str , name : str):
    sql = """
        SELECT * FROM built_in_model WHERE category = %s AND name = %s
    """
    res = await select_query(sql, params=(category, name), fetch_type="one")
    return res

async def get_built_in_model_by_huggingface_model_id(huggingface_model_id : str):
    sql = """
        SELECT * FROM built_in_model WHERE huggingface_model_id = %s
    """
    res = await select_query(sql, params=(huggingface_model_id), fetch_type="one")
    return res

async def get_built_in_model_image_info_by_real_name(real_name : str):
    sql = """
        SELECT * FROM image WHERE real_name = %s
    """
    res = await select_query(sql, params=(real_name, ), fetch_type="one")
    return res


# sync --------------------------------------------------------------------------------

def get_built_in_model_sync(category : str , name : str):
    sql = """
        SELECT * FROM built_in_model WHERE category = %s AND name = %s
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, (category, name))
        res = cur.fetchone()
    return res

def get_built_in_model_by_huggingface_model_id_sync(huggingface_model_id : str):
    sql = """
        SELECT * FROM built_in_model WHERE huggingface_model_id = %s
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, huggingface_model_id)
        res = cur.fetchone()
    return res

def get_built_in_model_image_info_by_real_name_sync(real_name : str):
    sql = """
        SELECT * FROM image WHERE real_name = %s
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, real_name)
        res = cur.fetchone()
    return res
