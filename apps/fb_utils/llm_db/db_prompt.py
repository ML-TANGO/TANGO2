import traceback
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils import TYPE


# GET ==================================================
async def get_prompt_list(workspace_id=None, like_prompt_name=None):
    """create_user_name은 프롬프트 생성 유저 네임"""
    res = []
    try:
        sql = """                
            SELECT p.id, p.name, p.description, p.workspace_id, p.create_user_id, p.latest_commit_id, p.access,
            DATE_FORMAT(p.create_datetime, %s) create_datetime,
            DATE_FORMAT(p.update_datetime, %s) update_datetime,
            u.name as create_user_name
            FROM prompt p
            LEFT JOIN msa_jfb.user u ON u.id = p.create_user_id
            """
            
        param = [TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL]
        where = []
        if workspace_id is not None:
            where.append("p.workspace_id=%s")
            param.append(workspace_id)
        if like_prompt_name is not None:
            where.append("p.name LIKE %s")
            param.append(f'%{like_prompt_name}%')
        if len(where) > 0:
            where = 'WHERE ' + ' AND '.join(where)
            sql += where

        res = await select_query(sql, params=param)
    except Exception as e:
        traceback.print_exc()
    return res

async def get_prompt(prompt_id=None):
    res = None
    try:
        sql = """
            SELECT p.id, p.name, p.description, p.workspace_id, p.create_user_id, p.latest_commit_id,
            DATE_FORMAT(p.create_datetime, %s) create_datetime,
            DATE_FORMAT(p.update_datetime, %s) update_datetime
            FROM prompt p
            WHERE id=%s
            """
        res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, prompt_id), fetch_type=FetchType.ONE)
    except Exception as e:
        traceback.print_exc()
    return res

async def get_commit_prompt_list(prompt_id=None, workspace_id=None, like_commit_name=None):
    """create_user_name은 커밋 유저 네임"""
    res = []
    try:
        sql = """
            SELECT cp.id commit_id, cp.name commit_name, cp.create_user_id commit_user_id,
            cp.prompt_description description_at_commit,
            DATE_FORMAT(cp.create_datetime, %s) commit_datetime,
            cp.system_message, cp.user_message, cp.commit_message,
            p.id prompt_id, p.name prompt_name, p.create_user_id prompt_create_user_id,
            DATE_FORMAT(p.create_datetime, %s) create_datetime,
            u.name as create_user_name,
            p.latest_commit_id, p.latest_commit_id
            FROM commit_prompt cp
            LEFT JOIN prompt p on p.id = cp.prompt_id
            LEFT JOIN msa_jfb.user u ON u.id = cp.create_user_id
            """
            
        param = [TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL]
        where = []
        if workspace_id is not None:
            where.append("p.workspace_id=%s")
            param.append(workspace_id)
            
        if prompt_id is not None:
            where.append("cp.prompt_id=%s")
            param.append(prompt_id)

        if like_commit_name is not None:
            where.append("cp.name LIKE %s")
            param.append(f'%{like_commit_name}%')

        if len(where) > 0:
            where = 'WHERE ' + ' AND '.join(where)
            sql += where
        res = await select_query(sql, params=param)
    except Exception as e:
        traceback.print_exc()
    return res

async def get_commit_prompt(commit_id):
    """
    return
        description_at_commit: commit 시점 prompt description
        create_datetime: prompt 생성시간
        commit_datetime: commit 시간
    """
    res = None
    try:
        sql = """
        SELECT cp.id commit_id, cp.name commit_name, cp.create_user_id commit_user_id,
        cp.prompt_description description_at_commit,
        DATE_FORMAT(cp.create_datetime, %s) commit_datetime,
        cp.system_message, cp.user_message, cp.commit_message,
        p.id prompt_id, p.name prompt_name, p.create_user_id prompt_create_user_id,
        DATE_FORMAT(p.create_datetime, %s) create_datetime,
        p.latest_commit_id, p.latest_commit_id
        FROM commit_prompt cp
        LEFT JOIN prompt p on p.id = cp.prompt_id
        WHERE cp.id=%s
        """
        res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, commit_id), fetch_type=FetchType.ONE)
    except Exception as e:
        traceback.print_exc()
    return res


# ==============================================================
async def insert_prompt(workspace_id, create_user_id, access, name, description=None):
    try:
        
        sql = """
        INSERT into prompt (workspace_id, create_user_id, access, name, description)
        VALUES (%s, %s, %s, %s, %s)
        """
        prompt_id = await commit_query(query=sql, params=(workspace_id, create_user_id, access, name, description))
        return True, prompt_id
    except Exception as e:
        traceback.print_exc()
        return False, None

async def update_prompt(prompt_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            columns.append(f"{column}=%s")
            values.append(value)
        columns_str = ", ".join(columns)
        values.append(prompt_id)

        sql = f"""
            UPDATE prompt SET {columns_str}
            WHERE id = %s
        """
        await commit_query(query=sql, params=(values))
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def delete_prompt(prompt_id_list):
    if len(prompt_id_list) == 0:
        return True
    try:
        sql = """
            DELETE FROM prompt
            WHERE id in ({})""".format(','.join(str(e) for e in prompt_id_list))
        await commit_query(query=sql)
        return True
    except:
        traceback.print_exc()
        return False

# ==============================================================
async def insert_prompt_template(prompt_id, name, create_user_id, prompt_description, commit_message, system_message, user_message):
    try:
        sql = """
            INSERT into commit_prompt (prompt_id, name, create_user_id, prompt_description, commit_message, system_message, user_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        last_commit_id = await commit_query(query=sql,
            params=(prompt_id, name, create_user_id, prompt_description, commit_message, system_message, user_message))
        return True, last_commit_id
    except Exception as e:
        traceback.print_exc()
        return False, None
    
# bookmark ==============================================================
async def get_user_prompt_bookmark_list(user_id):
    res = []
    try:
        sql = """SELECT prompt_id FROM prompt_bookmark WHERE user_id=%s"""
        res = await select_query(sql, params=(user_id,))
    except:
        traceback.print_exc()
    return res

async def insert_prompt_bookmark(prompt_id, user_id):
    try:
        sql = """INSERT into prompt_bookmark (prompt_id, user_id) VALUES (%s,%s)"""
        await commit_query(query=sql, params=(prompt_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

async def delete_prompt_bookmark(prompt_id, user_id):
    try:
        sql = """DELETE FROM prompt_bookmark WHERE prompt_id=%s AND user_id=%s"""
        await commit_query(query=sql, params=(prompt_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

# User list ==================================================
async def insert_user_prompt_list(prompts_id, users_id):
    try:
        print(prompts_id, users_id)
        rows = []
        for i in range(len(prompts_id)):
            rows.append((prompts_id[i],users_id[i]))
        sql = "INSERT IGNORE into user_prompt(prompt_id, user_id) values (%s,%s)"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

async def delete_user_prompt(prompts_id, users_id):
    try:
        rows = []
        for i in range(len(prompts_id)):
            rows.append((prompts_id[i],users_id[i]))
        sql = "DELETE from user_prompt where prompt_id = %s and user_id = %s"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e   

async def get_user_prompt_list(prompt_id=None):
    res = []
    try:
        sql = """
            SELECT up.*, u.name user_name
            FROM user_prompt up
            INNER JOIN msa_jfb.user u ON u.id = up.user_id
        """
        if prompt_id is not None:
            sql = f"{sql} where up.prompt_id='{prompt_id}'"
        res = await select_query(sql,)
    except:
        traceback.print_exc()
    return res
