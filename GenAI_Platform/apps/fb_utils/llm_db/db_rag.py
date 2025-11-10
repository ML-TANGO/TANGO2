import traceback
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils.llm_db.db_base import get_db
from utils import TYPE

# GET ==================================================
async def get_rag_list(workspace_id=None, like_rag_name=None):
    res = []
    try:
        sql = """                
            SELECT r.id, r.name, r.description, r.workspace_id, r.create_user_id, r.access, 
            r.chunk_len, r.embedding_huggingface_model_id, r.reranker_huggingface_model_id,
            DATE_FORMAT(r.create_datetime, %s) create_datetime, DATE_FORMAT(r.update_datetime, %s) update_datetime,
            r.retrieval_embedding_deployment_id, r.retrieval_reranker_deployment_id,
            r.retrieval_embedding_run, r.retrieval_reranker_run,
            r.test_embedding_deployment_id, r.test_reranker_deployment_id,
            r.test_embedding_run, r.test_reranker_run,
            COUNT(rd.id) AS docs_total_count, SUM(rd.size) AS docs_total_size,
            u.name as create_user_name
            FROM jonathan_llm.rag r
            LEFT JOIN jonathan_llm.rag_docs rd ON rd.rag_id = r.id
            LEFT JOIN msa_jfb.user u ON u.id = r.create_user_id
            """

        param = [TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL]
        where = []
        if workspace_id is not None:
            where.append("r.workspace_id=%s")
            param.append(workspace_id)

        if like_rag_name is not None:
            where.append("r.name LIKE %s")
            param.append(f'%{like_rag_name}%')
        if len(where) > 0:
            where = 'WHERE ' + ' AND '.join(where)
            sql += where

        sql  += " GROUP BY r.id "
        res = await select_query(sql, params=param)
    except Exception as e:
        traceback.print_exc()
    return res


async def get_rag(rag_id=None):
    res = None
    try:
        sql = """                
            SELECT r.id, r.name, r.description, r.workspace_id, w.name workspace_name, r.create_user_id, r.chunk_len, 
            r.embedding_huggingface_model_id, r.reranker_huggingface_model_id,
            r.embedding_huggingface_model_token, r.reranker_huggingface_model_token,
            r.retrieval_embedding_deployment_id, r.retrieval_reranker_deployment_id,
            r.retrieval_embedding_run, r.retrieval_reranker_run,
            r.test_embedding_deployment_id, r.test_reranker_deployment_id,
            r.test_embedding_run, r.test_reranker_run, r.rag_result,
            s.name data_main_name,
            DATE_FORMAT(r.create_datetime, %s) create_datetime,
            DATE_FORMAT(r.update_datetime, %s) update_datetime,
            COUNT(rd.id) AS docs_total_count, SUM(rd.size) AS docs_total_size,
            u.name as create_user_name
            FROM jonathan_llm.rag r
            LEFT JOIN jonathan_llm.rag_docs rd ON rd.rag_id = r.id
            LEFT JOIN msa_jfb.user u ON u.id = r.create_user_id
            LEFT JOIN msa_jfb.workspace w ON w.id = r.workspace_id
            LEFT JOIN msa_jfb.storage s ON s.id = w.main_storage_id
            """
        if rag_id is not None:
            sql += "WHERE r.id='{}'  ".format(rag_id)

        sql  += "GROUP BY r.id "
        res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL), fetch_type=FetchType.ONE)
    except Exception as e:
        traceback.print_exc()
    return res

async def insert_rag(workspace_id, create_user_id, name, description, access):
    try:
        sql = """INSERT into rag (workspace_id, create_user_id, name, description, access)
                    VALUES (%s,%s,%s,%s,%s)"""
        last_insert_id = await commit_query(query=sql, params=(workspace_id, create_user_id, name, description, access))
        return True, last_insert_id
    except:
        traceback.print_exc()
        return False, None

async def update_rag(rag_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            columns.append(f"{column}=%s")
            values.append(value)
        columns_str = ", ".join(columns)
        values.append(rag_id)

        sql = f"""
                UPDATE rag r SET {columns_str}
                WHERE r.id = %s
                """
        await commit_query(query=sql, params=values)
        return True  
    except:
        traceback.print_exc()
        return False

async def delete_rag(id_list):
    if len(id_list) == 0:
        return True
    try:
        sql = """
            DELETE FROM rag
            WHERE id in ({})""".format(','.join(str(e) for e in id_list))
        await commit_query(query=sql)
        return True
    except:
        traceback.print_exc()
        return False
# Bookmark ==================================================
async def insert_rag_bookmark(rag_id, user_id):
    try:
        sql = """INSERT into rag_bookmark (rag_id, user_id) VALUES (%s, %s)"""
        await commit_query(query=sql, params=(rag_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

async def delete_rag_bookmark(rag_id, user_id):
    try:
        sql = """DELETE FROM rag_bookmark WHERE rag_id=%s AND user_id=%s"""
        await commit_query(query=sql, params=(rag_id, user_id))
        return True
    except:
        traceback.print_exc()
        return False

async def get_rag_bookmark_list(user_id):
    try:
        sql = """SELECT * FROM rag_bookmark WHERE user_id=%s"""
        res = await select_query(sql, params=(user_id,))
        return res
    except:
        traceback.print_exc()
        return []

# User list ==================================================

async def insert_user_rag_list(rags_id, users_id):
    try:
        rows = []
        for i in range(len(rags_id)):
            rows.append((rags_id[i],users_id[i]))
        sql = "INSERT IGNORE into user_rag(rag_id, user_id) values (%s,%s)"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

async def delete_user_rag(rags_id, users_id):
    try:
        rows = []
        for i in range(len(rags_id)):
            rows.append((rags_id[i],users_id[i]))
        sql = "DELETE from user_rag where rag_id = %s and user_id = %s"
        await commit_query(query=sql, params=(rows), execute="many")
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e   

async def get_user_rag_list(rag_id=None):
    res = []
    try:
        sql = """
            SELECT up.*, u.name user_name
            FROM user_rag up
            INNER JOIN msa_jfb.user u ON u.id = up.user_id
        """
        if rag_id is not None:
            sql = f"{sql} where up.rag_id='{rag_id}'"
        res = await select_query(sql,)
    except:
        traceback.print_exc()
    return res

# Docs ==================================================
async def get_rag_doc_list(rag_id=None):
    res = []
    try:
        sql = """                
            SELECT r.id as rag_id, r.name, r.description,
            rd.id doc_id, rd.name doc_name, rd.size, rd.status, rd.progress,
            rd.create_user_id create_user_id,
            DATE_FORMAT(rd.create_datetime, %s) create_datetime
            FROM jonathan_llm.rag_docs rd
            LEFT JOIN jonathan_llm.rag r ON rd.rag_id = r.id
            """
        if rag_id is not None:
            sql += "WHERE r.id='{}' ".format(rag_id)
        res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL))
    except Exception as e:
        traceback.print_exc()
    return res

async def get_rag_doc(doc_id=None):
    res = None
    try:
        sql = """                
            SELECT r.id as rag_id, r.name, r.description,
            rd.id doc_id, rd.name doc_name, rd.size ,
            rd.create_user_id create_user_id,
            DATE_FORMAT(rd.create_datetime, %s) create_datetime
            FROM jonathan_llm.rag_docs rd
            LEFT JOIN jonathan_llm.rag r ON rd.rag_id = r.id
            """
        if doc_id is not None:
            sql += "WHERE rd.id='{}' ".format(doc_id)
        res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL), fetch_type=FetchType.ONE)
    except Exception as e:
        traceback.print_exc()
    return res

async def update_rag_docs(rag_id, docs_id_list):
    try:
        if len(docs_id_list) < 0:
            sql = "delete FROM rag_docs WHERE rag_id=%s"
        else:
            value = [rag_id] + docs_id_list
            placeholders = ','.join(['%s'] * len(docs_id_list))
            sql = f"delete FROM rag_docs WHERE rag_id=%s AND id NOT IN ({placeholders})"
        await commit_query(query=sql, params=(value))
        return True  
    except:
        traceback.print_exc()
        return False

async def delete_rag_docs(rag_id, id_list=None):
    try:
        sql = """DELETE FROM rag_docs WHERE rag_id=%s"""
        if id_list and len(id_list):
            sql += " AND id in ({})".format(','.join(str(e) for e in id_list))

        await commit_query(query=sql, params=rag_id)
        return True
    except:
        traceback.print_exc()
        return False

async def insert_rag_doc(rag_id, name, user_id, size=None):
    try:
        sql = """INSERT into rag_docs (rag_id, create_user_id, name, size) VALUES (%s, %s, %s, %s)"""
        await commit_query(query=sql, params=(rag_id, user_id, name, size))
        return True
    except:
        traceback.print_exc()
        return False

async def update_rag_doc_status(doc_id, status):
    try:
        sql = """UPDATE rag_docs SET status=%s WHERE id=%s"""
        await commit_query(query=sql, params=(status, doc_id))
        return True
    except:
        traceback.print_exc()
        return False
    
async def start_rag_doc_upload(rag_id, input_file_name, new_file_name, size):
    try:
        sql = """UPDATE rag_docs SET status=1, name=%s, size=%s
                WHERE rag_id=%s AND status=0 AND name=%s
                LIMIT 1"""
        await commit_query(query=sql, params=(new_file_name, size, rag_id, input_file_name))

        sql = "SELECT id FROM rag_docs WHERE rag_id=%s AND status=1 AND name=%s"
        res = await select_query(sql, params=(rag_id, new_file_name), fetch_type=FetchType.ONE)
        return True, res.get("id")
    except:
        traceback.print_exc()
        return False, None
    
async def uploading_rag_doc(id, progress):
    try:
        sql = """UPDATE rag_docs SET progress=%s WHERE id=%s"""
        await commit_query(query=sql, params=(progress, id))
        return True
    except:
        traceback.print_exc()
        return False

async def finish_rag_doc_upload(id):
    try:
        sql = """UPDATE rag_docs SET status=2 WHERE id=%s"""
        await commit_query(query=sql, params=(id))
        return True
    except:
        traceback.print_exc()
        return False



# Deployment ==================================================
async def insert_rag_worker(rag_id, instance_id):
    try:
        sql = """INSERT into rag_worker (rag_id, instance_id) VALUES (%s, %s)"""
        res = await commit_query(query=sql, params=(rag_id, instance_id))
        return {
            "result": True,
            "id": res,
            "message": ""
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "result": False,
            "id": None,
            "message": e
        }
    
# async def get_rag_worker(rag_worker_id):
#     sql = """SELECT * FROM rag_worker WHERE id=%s"""
#     res = await select_query(sql, params=(rag_worker_id,))
#     return res  

async def update_end_datetime_rag(rag_id):
    try:
        sql = """UPDATE rag_worker SET end_datetime=CURRENT_TIMESTAMP() WHERE rag_id=%s"""
        await commit_query(query=sql, params=(rag_id))
        return True
    except:
        traceback.print_exc()
        return False

async def get_latest_deployment_worker(deployment_id):
    try:
        sql = """SELECT dw.*, d.api_path
                FROM msa_jfb.deployment_worker dw
                LEFT JOIN msa_jfb.deployment d ON d.id = dw.deployment_id
                WHERE dw.deployment_id=%s
                ORDER BY dw.id DESC
                LIMIT 1"""
        res = await select_query(sql, params=(deployment_id,), fetch_type=FetchType.ONE)
        return res
    except:
        traceback.print_exc()
        return None


# Deployment ==================================================

def get_rag_list_sync(workspace_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if workspace_id is None:
                cur.execute("SELECT * FROM rag")
            else:
                cur.execute("SELECT * FROM rag WHERE workspace_id=%s", (workspace_id,))
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_rag_worker_sync(rag_worker_id):
    try:
        with get_db() as conn:
            cur = conn.cursor() 
            cur.execute("SELECT * FROM rag_worker WHERE id=%s", (rag_worker_id,))
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

