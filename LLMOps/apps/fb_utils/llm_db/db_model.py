from utils import TYPE
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils.llm_db.db_base import get_db
from typing import List


import json
import traceback

#==========================================
# select
#==========================================

async def get_model_user_list(model_id : int):
    try:
        sql = """
            SELECT um.user_id, u.name as user_name FROM user_model um 
            LEFT JOIN msa_jfb.user u ON u.id = um.user_id 
            WHERE um.model_id = %s
        """
        res = await select_query(sql, params=(model_id,))
        return res
    except Exception as e:
        traceback.print_exc()
        return []


async def get_workspace_user_name_and_id_list_async(workspace_id: int):
    sql = """
        SELECT u.id, u.name
        from msa_jfb.user_workspace uw
        inner join msa_jfb.user u on uw.user_id = u.id
        where uw.workspace_id = %s
    """
    res = await select_query(sql, params=(workspace_id,))
    return res

async def get_favorite_model(model_id : int, user_id : int):
    sql = """
        SELECT * FROM model_bookmark
        WHERE model_id = %s AND user_id = %s
    """
    res = await select_query(sql, params=(model_id, user_id), fetch_type=FetchType.ONE)
    
    return res is not None 

async def get_favorite_models(user_id : int):
    sql = """
        SELECT * FROM model_bookmark
        WHERE user_id = %s
    """
    res = await select_query(sql, params=(user_id,))
    
    return res

async def get_instance_list(workspace_id : int) -> List[dict]:
    
    sql = """
        SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
        FROM msa_jfb.workspace_instance wi
        JOIN msa_jfb.instance i ON i.id = wi.instance_id
        LEFT JOIN msa_jfb.resource_group rg ON i.gpu_resource_group_id = rg.id
        WHERE wi.workspace_id = %s
    """
    res = await select_query(sql, params=(workspace_id, ))
    return res


def get_model_sync(model_id : int) -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id, 
                m.gpu_count, m.instance_id, m.huggingface_git,
                m.latest_fine_tuning_config,
                m.latest_fine_tuning_status,
                m.commit_status,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
                DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
                w.name as workspace_name, u.name as create_user_name,
                i.instance_name
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
                WHERE m.id = %s
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, model_id))
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
        return None
    return res

async def get_model_simple(model_id: int) -> dict:
    try:
        sql = """
            SELECT m.id, m.name, m.description, m.huggingface_model_id, m.commit_model_name, m.access, m.create_user_id, u.name as create_user_name
            FROM model m 
            LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
            WHERE m.id = %s
        """
        res = await select_query(sql, params=(model_id, ), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None


async def get_model(model_id : int) -> dict:
    sql = """
        SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id, m.steps_per_epoch,
        m.gpu_count, m.instance_id, m.huggingface_git, m.huggingface_model_id, m.commit_model_name, m.commit_type,
        m.latest_fine_tuning_config,
        m.latest_fine_tuning_status,
        m.latest_commit_id,
        m.commit_status, m.pod_count, m.instance_count,
        m.training_type, m.external_manifest_name, m.external_manifest_version, m.external_job_id,
        m.domain,
        DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
        DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
        DATE_FORMAT(m.start_datetime, %s) AS start_datetime,
        w.name as workspace_name, u.name as create_user_name,
        i.instance_name
        FROM model m
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL,TYPE.TIME_DATE_FORMAT_SQL, model_id), fetch_type=FetchType.ONE)
    return res


def get_models_sync(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
                m.latest_fine_tuning_status, m.instance_id, m.gpu_count, m.instance_count,
                m.commit_status, m.pod_count,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime, 
                w.name as workspace_name, u.name as create_user_name,
                i.cpu_allocate, i.ram_allocate, i.gpu_allocate
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
                LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
                WHERE m.workspace_id = %s
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return res

def get_all_models_sync() -> List[dict]:
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
                m.latest_fine_tuning_status,
                m.commit_status,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime, 
                w.name as workspace_name, u.name as create_user_name
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL))
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return res


async def get_models(workspace_id : int) -> List[dict]:
    sql = """
        SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
        m.latest_fine_tuning_status, m.access,
        m.commit_status,
        DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
        DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
        w.name as workspace_name, u.name as create_user_name
        FROM model m
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.workspace_id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL,TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
    return res

async def get_models_option(workspace_id : int, model_name : str = None, create_user_id : int = None) -> List[dict]:
    sql = """
        SELECT m.id, m.name, u.name as create_user_name,
               m.training_type,
               m.external_manifest_name,
               m.external_manifest_version,
               m.domain
        FROM model m
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.workspace_id = %s
    """
    values = [workspace_id]
    if model_name:
        sql += " AND m.name LIKE %s"
        values.append(f"%{model_name}%")
    if create_user_id:
        sql += " AND m.create_user_id=%s"
        values.append(create_user_id)
    res = await select_query(sql, params=values)
    return res

async def get_commit_models(model_id : int)-> List[dict]:
    sql = """
        SELECT cm.id, cm.name, cm.model_id, cm.workspace_id, 
        cm.commit_message, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, 
        cm.fine_tuning_config, cm.model_description,
        w.name as workspace_name, u.name as create_user_name, m.name as model_name, m.huggingface_model_id
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        LEFT JOIN msa_jfb.user mu ON mu.id = m.create_user_id
        WHERE m.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, model_id))
    return res


async def get_commit_models_option(model_id : int, commit_name : str = None)-> List[dict]:
    sql = """
        SELECT cm.id, cm.name, u.name as create_user_name, m.name as model_name, cm.fine_tuning_config, 
                m.description, m.access, m.create_datetime, m.update_datetime
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE m.id = %s
    """
    values = [model_id]
    if commit_name:
        sql += " AND cm.name LIKE %s"
        values.append(f"%{commit_name}%")
    res = await select_query(sql, params=values)
    return res

async def get_commit_models_by_workspace(workspace_id : int) -> List[dict]:
    sql = """
        SELECT cm.*, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, 
        w.name as workspace_name, u.name as create_user_name, m.name as model_name
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE cm.workspace_id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
    return res

async def get_commit_model(commit_id : int) -> dict:
    sql = """
        SELECT cm.id, cm.name, cm.commit_message, cm.model_description, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, cm.fine_tuning_config, cm.steps_per_epoch,
        w.name as workspace_name, u.name as create_user_name, m.name as model_name, m.huggingface_git, m.huggingface_model_id, m.id as model_id
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE cm.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, commit_id), fetch_type=FetchType.ONE)
    return res

async def get_workspace_model(workspace_id : int) -> dict:
    sql = """
    SELECT w.*, s.name as main_storage_name, sd.name as data_storage_name
    FROM msa_jfb.workspace w
    LEFT JOIN msa_jfb.storage s ON s.id = w.main_storage_id
    LEFT JOIN msa_jfb.storage sd ON sd.id = w.data_storage_id
    WHERE w.id = %s
    """
    res = await select_query(sql, params=(workspace_id, ), fetch_type=FetchType.ONE)
    return res

async def check_model_by_model_name(model_name: str, workspace_id:int) -> dict:
    sql = """
        SELECT * FROM model WHERE name = %s and workspace_id = %s
    """
    res = await select_query(query=sql, params=(model_name, workspace_id ), fetch_type=FetchType.ONE)
    return res

async def check_commit_model_by_name(commit_name : str , model_id : int):
    sql = """
        SELECT * FROM commit_model WHERE name = %s and model_id = %s
    """
    res = await select_query(query=sql, params=(commit_name, model_id), fetch_type=FetchType.ONE)
    return res

def get_model_dataset_sync(model_dataset_id : int ) -> dict:
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT ftd.id, ftd.training_data_path, d.name as dataset_name, d.access, s.name as data_storage_name, w.name as workspace_name
                FROM fine_tuning_dataset ftd
                JOIN model m ON m.id = ftd.model_id
                JOIN msa_jfb.datasets d ON d.id = ftd.dataset_id
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                JOIN msa_jfb.storage s ON s.id = w.data_storage_id
                WHERE ftd.id = %s
            """
            cur.execute(sql, (model_dataset_id, ))
            res = cur.fetchone()
            return res
    except Exception as e:
        traceback.print_exc()
        return res


async def get_model_dataset(model_dataset_id : int) -> dict:
    
    res = await select_query(sql, params=(model_dataset_id, ), fetch_type=FetchType.ONE)
    return res

async def get_model_datasets(model_id : int) -> List[dict]:
    sql = """
        SELECT ftd.id, ftd.training_data_path, d.name as dataset_name, d.access, s.name as data_storage_name, w.name as workspace_name
        FROM fine_tuning_dataset ftd
        JOIN model m ON m.id = ftd.model_id
        JOIN msa_jfb.datasets d ON d.id = ftd.dataset_id
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        JOIN msa_jfb.storage s ON s.id = w.data_storage_id
        WHERE ftd.model_id = %s
    """
    res = await select_query(sql, params=(model_id, ))
    return res

async def get_fine_tuning_config_files(model_id : int) -> List[dict]:
    sql = """
        SELECT ftc.id, ftc.file_name, ftc.size
        FROM fine_tuning_config_file ftc
        WHERE ftc.model_id = %s
    """
    res = await select_query(sql, params=(model_id, ))
    return res

async def get_fine_tuning_config_file(model_config_id : int) -> dict:
    sql = """
        SELECT ftc.id, ftc.file_name, ftc.size, ftc.model_id
        FROM fine_tuning_config_file ftc
        WHERE ftc.id = %s
    """
    res = await select_query(sql, params=(model_config_id, ), fetch_type=FetchType.ONE)
    return res

async def get_dataset_model(dataset_id : int) -> dict:
    sql = """
    SELECT d.*
    FROM msa_jfb.datasets d
    JOIN msa_jfb.user u ON u.id = d.create_user_id
    WHERE d.id = %s
    """
    res = await select_query(query=sql, params=(dataset_id, ), fetch_type=FetchType.ONE)
    return res

async def get_datasets(workspace_id : int, create_user_id : int = None, dataset_name : str =None) -> List[dict]:
    sql = """
        SELECT d.id, d.name, d.access, u.name as create_user_name, d.workspace_id
        FROM msa_jfb.datasets d
        JOIN msa_jfb.user u ON u.id = d.create_user_id
        WHERE d.workspace_id = %s
    """
    params = [workspace_id]
    if create_user_id is not None:
        sql += " AND d.create_user_id = %s"
        params.append(create_user_id)
    if dataset_name is not None:
        sql += " AND d.name LIKE %s"
        params.append(f"%{dataset_name}%")
    res = await select_query(sql, params=params)
    return res

# async def get_instance_list(workspace_id : int):
#     sql = """
#         SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
#         FROM workspace_instance wi
#         JOIN instance i ON i.id = wi.instance_id
#         LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
#         WHERE wi.workspace_id = %s
#     """
#     res = await select_query(sql, params=(workspace_id,))
#     return res

#==========================================
# insert 
#==========================================
async def create_model(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO model ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res


async def create_commit_model(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO commit_model ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_fine_tuning_dataset(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO fine_tuning_dataset ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_fine_tuning_config_file(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO fine_tuning_config_file ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_favorite_model(**kwargs):
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO model_bookmark ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_model_user_list(model_id : int, user_list : List[int]):
    try:
        if not user_list:
            return True
        # 파라미터화 — f-string 인터폴레이션(SQLi 패턴) 제거.
        placeholders = ",".join(["(%s, %s)"] * len(user_list))
        sql = "INSERT INTO user_model (model_id, user_id) VALUES " + placeholders
        params = [v for uid in user_list for v in (model_id, uid)]
        res = await commit_query(query=sql, params=params)
        return res
    except Exception as e:
        traceback.print_exc()
        return False

#==========================================
# delete
#==========================================

async def delete_model(model_id : int) -> bool:
    sql="DELETE FROM model WHERE id=%s"
    await commit_query(query=sql, params=(model_id,))
    return True
async def delete_commit_model(commit_model_id : int) -> bool:
    sql="DELETE FROM commit_model WHERE id=%s"
    await commit_query(query=sql, params=(commit_model_id,))
    return True
async def delete_model_dataset(model_dataset_id : int) -> bool:
    sql="DELETE FROM fine_tuning_dataset WHERE id=%s"
    await commit_query(query=sql, params=(model_dataset_id,))
    return True
async def delete_model_configuration(model_config_id : int) -> bool:
    sql="DELETE FROM fine_tuning_config_file WHERE id=%s"
    await commit_query(query=sql, params=(model_config_id,))
    return True

async def delete_favorite_model(model_id: int, user_id : int) -> bool:
    sql="DELETE FROM model_bookmark WHERE model_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(model_id, user_id))
    return True

async def delete_model_user_list(model_id : int, user_id : int) -> bool:
    sql="DELETE FROM user_model WHERE model_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(model_id, user_id))
    return True

#==========================================
# update
#==========================================

def update_model_commit_status_sync(commit_status : str, model_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = "UPDATE model SET commit_status = %s WHERE id = %s"
            cur.execute(sql, (commit_status, model_id))

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def update_model_external_job(model_id : int, external_job_id : str) -> int:
    """Bind a partner-container job_id onto an external training_type model.

    Called from service.bind_external_job right after the BFF returns a
    fresh job_id from POST /api/external/jobs. Idempotent: always overwrites
    the latest job_id (재학습 시 새 job_id 로 교체).
    """
    sql = """
        UPDATE model
        SET external_job_id = %s
        WHERE id = %s AND training_type = 'external'
    """
    res = await commit_query(query=sql, params=(external_job_id, model_id))
    return res


async def update_model_commit_status(commit_status : str, model_id : int, latest_commit_id : int, commit_type : str):
    sql = "UPDATE model SET commit_status = %s, latest_commit_id = %s, commit_type = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(commit_status, latest_commit_id, commit_type, model_id))
    return True

async def update_model_commit_id(latest_commit_id : int, model_id : int):
    sql = "UPDATE model SET latest_commit_id = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(latest_commit_id, model_id))
    return True

def update_model_fine_tuning_status_sync(status : str, model_id : int, start_datetime :str = None, end_datetime : str = None, pod_count : int = 0):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE model SET latest_fine_tuning_status = %s "
            data = [status]
            if start_datetime:
                sql += ", start_datetime = %s"
                data.append(start_datetime)
            elif end_datetime:
                sql += ", end_datetime = %s"
                data.append(end_datetime)
            if pod_count:
                sql += ", pod_count = %s"
                data.append(pod_count)
            sql += " WHERE id = %s"
            data.append(model_id)
            cur.execute(sql, data)

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def update_model_fine_tuning_status(status : str, model_id : int, steps_per_epoch : int = None):
    sql = "UPDATE model SET latest_fine_tuning_status = %s "
    paramse = [status]
    if steps_per_epoch:
        sql += ", steps_per_epoch = %s"
        paramse.append(steps_per_epoch)
    sql += " WHERE id = %s"
    paramse.append(model_id)
    res = await commit_query(query=sql, params=paramse)
    return True

async def update_model_fine_tuning_instance(instance_id : int, instance_count : int, gpu_count : int, model_id : int, fine_tuning_config : str):
    sql = "UPDATE model SET instance_id = %s, instance_count= %s, gpu_count = %s, latest_fine_tuning_config = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(instance_id, instance_count, gpu_count, fine_tuning_config, model_id))
    return True

async def update_model_description(model_id : int, description : str):
    sql = "UPDATE model SET description = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(description, model_id))
    return True

async def update_model(model_id : int, description : str, access : str, create_user_id : int):
    sql = "UPDATE model SET description = %s, access = %s, create_user_id = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(description, access, create_user_id, model_id))
    return True


# ── SP-4 양자화·포팅 lineage (v0.4 3.9) ──────────────────────────────────────

async def insert_quantize_lineage(source_model_id : int, workspace_id : int,
                                  job_str_id : str, quantization_type : str,
                                  target_device : str = None, prune : bool = False) -> int:
    """양자화 시도 1건 기록(launch 시점). 재양자화 시 새 row(history 보존)."""
    sql = """
        INSERT INTO quantize_lineage
            (source_model_id, workspace_id, job_str_id, quantization_type,
             target_device, prune, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'running')
    """
    return await commit_query(query=sql, params=(
        source_model_id, workspace_id, job_str_id, quantization_type,
        target_device, 1 if prune else 0,
    ))


async def complete_quantize_lineage(job_str_id : str, gguf_path : str,
                                    source_model_id : int = None) -> bool:
    """convert 완료 시 lineage 마감. running 행만 갱신 — 실패/취소 행을 completed 로
    덮어쓰지 않도록 가드(`status='running'`). source_model_id 주면 교차모델 마킹 차단."""
    sql = """
        UPDATE quantize_lineage
        SET status = 'completed', gguf_path = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [gguf_path, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def update_quantize_lineage_status(job_str_id : str, status : str,
                                         source_model_id : int = None) -> bool:
    """convert 실패/취소 시 lineage 상태 갱신(running 일 때만). idempotent.

    완료(completed)는 complete_quantize_lineage 가 담당 — 여기선 failed/cancelled 만.
    이게 없으면 실패한 양자화가 이력에 영원히 'running' 으로 남는다.
    source_model_id 주면 다른 모델/워크스페이스의 job 을 마킹하지 못하게 바인딩.
    """
    sql = """
        UPDATE quantize_lineage
        SET status = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [status, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def list_quantize_lineage(source_model_id : int) -> list:
    """원본 모델의 양자화 이력(최신순) — lineage 조회(원본+양자화 파라미터)."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, quantization_type,
               target_device, prune, gguf_path, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM quantize_lineage
        WHERE source_model_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, source_model_id),
                             fetch_type=FetchType.ALL)
    return res or []


# ── SP-5 자동평가 결과 (v0.4 3.8) ────────────────────────────────────────────

async def insert_eval_result(source_model_id : int, workspace_id : int,
                             job_str_id : str, dataset_id : int = None,
                             dataset_name : str = None, metric_set : str = None) -> int:
    """평가 시도 1건 기록(launch 시점, status=running). 재평가 시 새 row(이력 보존)."""
    sql = """
        INSERT INTO eval_result
            (source_model_id, workspace_id, job_str_id, dataset_id,
             dataset_name, metric_set, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'running')
    """
    return await commit_query(query=sql, params=(
        source_model_id, workspace_id, job_str_id, dataset_id,
        dataset_name, metric_set,
    ))


async def complete_eval_result(job_str_id : str, metrics_json : str,
                               source_model_id : int = None) -> bool:
    """평가 완료 시 메트릭 마감. running 행만 갱신 — 실패/취소 행을 completed 로
    덮어쓰지 않도록 가드. source_model_id 주면 교차모델 마킹 차단."""
    sql = """
        UPDATE eval_result
        SET status = 'completed', metrics = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [metrics_json, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def set_eval_result_metrics(job_str_id : str, metrics_json : str,
                                  source_model_id : int = None) -> bool:
    """metrics 만 갱신(상태 불변, running 행 한정). 전문가 평가(A4)가 start 시점에 생성한
    샘플(_samples)을 영속해 재로드 안정성을 확보하기 위함 — 실 모델출력은 비결정적이라
    매 조회마다 재생성하면 사람이 채점한 출력과 표시 출력이 달라진다. complete_eval_result
    (status→completed)와 달리 status 는 running 으로 둔다."""
    sql = """
        UPDATE eval_result
        SET metrics = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [metrics_json, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def update_eval_result_status(job_str_id : str, status : str,
                                    source_model_id : int = None) -> bool:
    """평가 실패/취소 시 상태 갱신(running 일 때만). idempotent.

    완료(completed)는 complete_eval_result 가 담당 — 여기선 failed/cancelled 만.
    source_model_id 주면 다른 모델/워크스페이스의 job 을 마킹하지 못하게 바인딩.
    """
    sql = """
        UPDATE eval_result
        SET status = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [status, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def list_eval_results(source_model_id : int) -> list:
    """모델의 평가 이력(최신순) — 비교표·best 배지 조회용."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE source_model_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, source_model_id),
                             fetch_type=FetchType.ALL)
    return res or []


async def get_eval_result_by_job(job_str_id : str, source_model_id : int = None):
    """job_str_id 로 eval_result 단건 조회 — 직접호출(judge) 결과 폴링용(컨테이너/NFS 미경유).
    source_model_id 주면 교차모델 조회 차단."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY id DESC LIMIT 1"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return (res or [None])[0]


# 메트릭 방향(best 판정). 모르는 키는 max 기본(벤치마크 점수 대부분 higher=better).
# perplexity 만 낮을수록 우수. (llm_model self-metric + llm_evaluation 벤치마크 공용)
_EVAL_METRIC_DIRECTION = {
    "bleu": "max", "rouge1": "max", "rouge2": "max", "rougel": "max", "rouge": "max",
    "perplexity": "min", "auc": "max", "f1": "max", "accuracy": "max", "dice": "max",
}


def _flatten_eval_metrics(metrics) -> dict:
    """비교표용 flat numeric 메트릭 추출.
    벤치마크(nested {scores, averages, ...})는 averages(메트릭→평균)를 사용,
    self-metric(SP-5)은 top-level flat numeric 을 사용 → 혼재 이력을 동일 shape 로(§14.12).
    _ 접두 내부키·비수치·bool 은 제외."""
    if isinstance(metrics, dict) and isinstance(metrics.get("averages"), dict):
        source = metrics["averages"]    # 벤치마크 평탄화
    else:
        source = metrics if isinstance(metrics, dict) else {}
    return {k: v for k, v in source.items()
            if not str(k).startswith("_") and isinstance(v, (int, float))
            and not isinstance(v, bool)}


def build_eval_comparison(rows: list) -> dict:
    """eval_result rows → 비교표 shape ``{metric_keys, best, runs}`` (§14.12).

    self-metric(SP-5)·벤치마크·judge(후속) 런을 한 비교표에 누적. 벤치마크의 nested
    metrics 는 averages 로 평탄화. best 는 completed 런 중 메트릭별 방향(min/max) 최적값.
    llm_model / llm_evaluation 두 서비스가 동일 로직을 쓰도록 공용화(분기 drift 방지).
    """
    runs = []
    metric_keys = set()
    for r in rows:
        metrics = r.get("metrics")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except (TypeError, json.JSONDecodeError):
                metrics = None
        clean = _flatten_eval_metrics(metrics)
        metric_keys.update(clean.keys())
        runs.append({
            "id": r["id"], "job_id": r.get("job_str_id"), "dataset_id": r.get("dataset_id"),
            "dataset_name": r.get("dataset_name"), "metric_set": r.get("metric_set"),
            "status": r.get("status"), "create_datetime": r.get("create_datetime"),
            # 교차모델 비교(④)용 라벨. 단일모델 호출은 한 모델이라 무시되는 잉여 필드.
            # model_name 은 eval_result 에 없어 호출자가 row 에 주입할 때만 채워진다.
            "model_id": r.get("source_model_id"), "model_name": r.get("model_name"),
            "metrics": clean,
        })
    best = {}
    for key in metric_keys:
        direction = _EVAL_METRIC_DIRECTION.get(str(key).lower(), "max")
        candidates = [(run["id"], run["metrics"][key]) for run in runs
                      if run["status"] == "completed" and key in run["metrics"]]
        if not candidates:
            continue
        best[key] = (min if direction == "min" else max)(candidates, key=lambda x: x[1])[0]
    return {"metric_keys": sorted(metric_keys), "best": best, "runs": runs}


# ── P3 전문가 평가 (sample-level 인간 채점) ──────────────────────────────────

async def insert_expert_rating(source_model_id : int, job_str_id : str, sample_idx : int,
                               verdict : str, input : str = None, output : str = None,
                               reference : str = None, rater_user : str = None,
                               comment : str = None) -> int:
    """전문가 채점 1건 upsert — (job_str_id, sample_idx) 유니크라 재채점 시 갱신."""
    sql = """
        INSERT INTO eval_expert_rating
            (source_model_id, job_str_id, sample_idx, input, output, reference,
             rater_user, verdict, comment)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            verdict = VALUES(verdict), comment = VALUES(comment),
            rater_user = VALUES(rater_user), create_datetime = CURRENT_TIMESTAMP
    """
    return await commit_query(query=sql, params=(
        source_model_id, job_str_id, sample_idx, input, output, reference,
        rater_user, verdict, comment))


async def list_expert_ratings(job_str_id : str, source_model_id : int = None) -> list:
    """세션(job_str_id)의 전문가 채점 목록(sample_idx 순). source_model_id 주면 교차모델 차단."""
    sql = """
        SELECT id, source_model_id, job_str_id, sample_idx, input, output, reference,
               rater_user, verdict, comment,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_expert_rating
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY sample_idx ASC"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return res or []


async def insert_expert_rating_history(source_model_id : int, job_str_id : str,
                                       sample_idx : int, verdict : str,
                                       comment : str = None, rater_user : str = None) -> int:
    """전문가 채점 이력 1건(append-only, 감사추적). 메인 eval_expert_rating 은
    (job_str_id, sample_idx) upsert 라 '현재' verdict 만 남지만, 누가 언제 어떻게 채점/재채점
    했는지는 이 테이블에 채점 이벤트마다 누적해 불변 보존한다."""
    sql = """
        INSERT INTO eval_expert_rating_history
            (source_model_id, job_str_id, sample_idx, rater_user, verdict, comment)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    return await commit_query(query=sql, params=(
        source_model_id, job_str_id, sample_idx, rater_user, verdict, comment))


async def list_expert_rating_history(job_str_id : str, source_model_id : int = None) -> list:
    """세션(job_str_id)의 전문가 채점 이력(시간순). source_model_id 주면 교차모델 차단."""
    sql = """
        SELECT id, source_model_id, job_str_id, sample_idx, rater_user, verdict, comment,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_expert_rating_history
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY id ASC"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return res or []