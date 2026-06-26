"""데이터 합성 프레임워크 — synthesis_project DB 레이어 (P1, WBS 3.3 / SP-7)."""
from datetime import datetime

from utils.msa_db.db_base_async import select_query, commit_query, FetchType


async def create_synthesis_project(**kwargs) -> int:
    fields = list(kwargs.keys())
    values = list(kwargs.values())
    sql = "INSERT INTO synthesis_project ({}) VALUES({})".format(
        ",".join(fields), ",".join(["%s"] * len(fields))
    )
    return await commit_query(query=sql, params=values)


async def list_generate_manifests():
    # 생성(generate) 외부 컨테이너 manifest 목록 — 합성 모듈 선택 드롭다운용.
    # external_container_manifest 는 같은 msa_jfb DB.
    sql = """
        SELECT name, version, execution_mode,
               JSON_UNQUOTE(JSON_EXTRACT(raw_json, '$.metadata.description')) AS description
        FROM external_container_manifest
        WHERE job_type = 'generate'
        ORDER BY name, version
    """
    return await select_query(sql)


async def get_synthesis_projects(workspace_id: int):
    sql = "SELECT * FROM synthesis_project WHERE workspace_id = %s ORDER BY id DESC"
    return await select_query(sql, params=(workspace_id,))


async def get_synthesis_project(project_id: int):
    sql = "SELECT * FROM synthesis_project WHERE id = %s"
    return await select_query(sql, params=(project_id,), fetch_type=FetchType.ONE)


async def delete_synthesis_project(project_id: int):
    sql = "DELETE FROM synthesis_project WHERE id = %s"
    return await commit_query(query=sql, params=(project_id,))


async def update_synthesis_project(project_id: int, **kwargs):
    if not kwargs:
        return 0
    kwargs["update_datetime"] = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    sets = ",".join(f"{k}=%s" for k in kwargs)
    sql = f"UPDATE synthesis_project SET {sets} WHERE id=%s"
    return await commit_query(query=sql, params=list(kwargs.values()) + [project_id])


async def update_synthesis_run(project_id: int, job_str_id: str, output_subdir: str, status: str = "running"):
    now = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    sql = (
        "UPDATE synthesis_project SET job_str_id=%s, output_subdir=%s, status=%s, "
        "update_datetime=%s WHERE id=%s"
    )
    return await commit_query(query=sql, params=(job_str_id, output_subdir, status, now, project_id))


async def update_synthesis_status(project_id: int, status: str, result_count: int = None):
    now = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    if result_count is not None:
        sql = "UPDATE synthesis_project SET status=%s, result_count=%s, update_datetime=%s WHERE id=%s"
        return await commit_query(query=sql, params=(status, result_count, now, project_id))
    sql = "UPDATE synthesis_project SET status=%s, update_datetime=%s WHERE id=%s"
    return await commit_query(query=sql, params=(status, now, project_id))


# ── 프롬프트 후보 큐레이션 영속 (synthesis_candidate, P3) ──

async def list_synthesis_candidates(project_id: int):
    sql = "SELECT * FROM synthesis_candidate WHERE project_id = %s ORDER BY score DESC, id ASC"
    return await select_query(sql, params=(project_id,))


async def get_synthesis_candidate(candidate_id: int):
    sql = "SELECT * FROM synthesis_candidate WHERE id = %s"
    return await select_query(sql, params=(candidate_id,), fetch_type=FetchType.ONE)


async def insert_synthesis_candidate(project_id: int, prompt: str, score: float,
                                     method: str, iteration: int, status: str = "candidate"):
    now = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    sql = ("INSERT INTO synthesis_candidate "
           "(project_id, prompt, score, method, iteration, status, create_datetime) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s)")
    return await commit_query(query=sql, params=(project_id, prompt, score, method, iteration, status, now))


async def update_synthesis_candidate_status(candidate_id: int, status: str):
    sql = "UPDATE synthesis_candidate SET status=%s WHERE id=%s"
    return await commit_query(query=sql, params=(status, candidate_id))


async def delete_open_synthesis_candidates(project_id: int):
    # 채택/폐기 이력은 보존, 미결정(candidate) 만 제거(재생성용).
    sql = "DELETE FROM synthesis_candidate WHERE project_id=%s AND status='candidate'"
    return await commit_query(query=sql, params=(project_id,))


async def max_synthesis_candidate_iteration(project_id: int) -> int:
    sql = "SELECT COALESCE(MAX(iteration),0) AS m FROM synthesis_candidate WHERE project_id=%s"
    row = await select_query(sql, params=(project_id,), fetch_type=FetchType.ONE)
    return (row or {}).get("m", 0) or 0
