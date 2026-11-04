import traceback
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils import TYPE

async def get_playground_list(workspace_id=None):
    sql = """
    SELECT p.id, p.name, p.workspace_id, p.create_user_id, p.description, p.access, p.deploy_type, p.deployment, p.model, p.rag, p.prompt,
    DATE_FORMAT(p.create_datetime, %s) create_datetime, DATE_FORMAT(p.update_datetime, %s) update_datetime
    FROM playground p
    """
    if workspace_id is not None:
        sql += " WHERE p.workspace_id='{}' ".format(workspace_id)
    sql += """ ORDER BY id DESC """

    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL))
    return res

async def get_running_playground_candidates(workspace_id, model_id=None, commit_id=None):
    """배포 선택 UI 용 후보 조회 — 워크스페이스 + (선택) 모델·커밋으로 **SQL 에서** 좁힌다.

    왜 별도 쿼리인가. get_playground_list 는 워크스페이스 전체를 돌려주고 호출자가 행마다
    get_playground_status 를 부른다(N+1). 그 상태 조회는 redis·kube·외부 잡 트래커까지
    두드리므로 행 수에 그대로 비례한다. "이 모델을 서빙 중인 배포"를 찾는 데 워크스페이스의
    모든 배포 상태를 실측할 이유가 없다 → 상태를 묻기 **전에** 후보를 줄인다.

    필터 가능한 범위는 playground.model JSON 이 실제로 담고 있는 것으로 정해진다
    (update_playground_options 가 유일한 writer):
      model_type / model_huggingface_id / model_allm_id / model_allm_commit_id /
      model_info / serving_system / dual{...}
    playground 테이블엔 model_id 컬럼이 없고 플랫폼 모델·커밋 id 는 **문자열로** JSON 에
    들어간다(str(model_id)) → JSON_UNQUOTE 로 꺼내 문자열 비교한다.
    HuggingFace 직접 배포는 model_allm_id 가 NULL 이라 model_id 필터에 잡히지 않는다(정상 —
    플랫폼 모델을 평가 대상으로 고르는 화면이 이 필터의 소비자다).

    이중 세션의 자식(prompt_child)은 제외한다 — 목록에 노출되지 않는 내부 행이고,
    단독으로 추론 대상이 될 수 없다(부모가 세션의 대표).
    deployment IS NULL(한 번도 배포한 적 없음)도 뺀다 — 상태가 언제나 stop 이라 물어볼
    필요가 없다. **중지된 배포는 여기서 걸러지지 않는다**(중지 후에도 deployment JSON 이
    재배포용으로 남는다) → running 판정은 호출자가 상태 실측으로 한다.
    """
    sql = """
    SELECT p.id, p.name, p.workspace_id, p.create_user_id, p.description, p.access,
           p.deploy_type, p.deployment, p.model,
           DATE_FORMAT(p.create_datetime, %s) create_datetime,
           DATE_FORMAT(p.update_datetime, %s) update_datetime
    FROM playground p
    WHERE p.workspace_id = %s
      AND p.deployment IS NOT NULL
      AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(p.model, '$.dual.role')), '') <> 'prompt_child'
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, workspace_id]
    if model_id is not None:
        sql += " AND JSON_UNQUOTE(JSON_EXTRACT(p.model, '$.model_allm_id')) = %s "
        params.append(str(model_id))
    if commit_id is not None:
        sql += " AND JSON_UNQUOTE(JSON_EXTRACT(p.model, '$.model_allm_commit_id')) = %s "
        params.append(str(commit_id))
    sql += " ORDER BY p.id DESC "
    return await select_query(sql, params=tuple(params))


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

async def insert_playground(workspace_id, create_user_id, name, description, access, deploy_type='cluster'):
    try:
        sql = """INSERT into playground (workspace_id, create_user_id, name, description, access, deploy_type)
                    VALUES (%s,%s,%s,%s,%s,%s)"""
        playground_id = await commit_query(query=sql, params=(workspace_id, create_user_id, name, description, access, deploy_type))
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

async def clear_playground_external_job_id(playground_id, expected_job_id, deployment_json):
    """deployment JSON 을 **현재 external_job_id 가 기대값일 때만** 교체(compare-and-swap).

    호출자가 행을 다시 읽어 비교하더라도 그 read 와 write 사이에 재배포가 끼어들 수
    있다(TOCTOU). 그 창에서 blind write 를 하면 방금 기록된 **새** job id 까지 지워
    막 뜬 배포가 고아가 되고 UI 는 '중지'로 되돌아간다. 조건을 SQL 에 실어 그 창을 없앤다.

    commit_query 가 rowcount 를 돌려주지 않아 "정말 지웠는지"는 알 수 없다 —
    호출자는 이 반환값을 성공/실패가 아니라 "예외 없이 시도했다"로만 해석해야 한다.
    """
    try:
        sql = """
                UPDATE playground SET deployment=%s
                WHERE id=%s
                  AND JSON_UNQUOTE(JSON_EXTRACT(deployment, '$.external_job_id')) = %s
                """
        await commit_query(query=sql, params=(deployment_json, playground_id,
                                              str(expected_job_id)))
        return True
    except:
        traceback.print_exc()
        return False


async def delete_playground(id_list):
    if len(id_list) == 0:
        return True
    try:
        # id 를 SQL 에 직접 보간하면 인젝션(`1 OR 1=1` → 전 행 삭제)이 되므로 placeholder 바인딩.
        # 개수만 문자열로 조립하고 값은 전부 params 로 넘긴다(라우트에서 int 로 정규화되지만
        # 보상 정리 등 내부 호출자도 있으므로 여기서도 int() 로 한 번 더 좁힌다).
        ids = [int(e) for e in id_list]
        placeholders = ','.join(['%s'] * len(ids))
        sql = """
            DELETE FROM playground
            WHERE id in ({})""".format(placeholders)
        await commit_query(query=sql, params=tuple(ids))
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


async def get_playground_inference_target(playground_id):
    """직접 추론 URL과 저장된 이중 세션 LLM1 링크를 한 번에 조회한다."""
    # 평가가 이중 여부를 확인하려고 상세 API를 한 번 더 호출하면 단일 평가도 느려지므로,
    # 기존 URL 조회와 같은 JOIN에서 링크까지 함께 읽는 별도 additive helper를 둔다.
    sql = """
        SELECT p.id, p.name, p.workspace_id,
               JSON_EXTRACT(p.deployment, '$.deployment_playground_id') AS deployment_id,
               msad.api_path,
               JSON_EXTRACT(p.model, '$.dual.prompt_gen_playground_id') AS prompt_gen_playground_id
        FROM jonathan_llm.playground p
        LEFT JOIN msa_jfb.deployment msad
          ON msad.id = JSON_EXTRACT(p.deployment, '$.deployment_playground_id')
        WHERE p.id=%s
        """
    return await select_query(
        query=sql, params=(playground_id,), fetch_type=FetchType.ONE)


async def get_edge_deploy_target(playground_id):
    """온디바이스(edge) 배포를 띄운 디바이스와 그 모델 — 상세 재진입 시 선택 복원용.

    연결(deploy_playground_id)은 fb_resource 가 배포 성공 시 edge_worker 에 새긴다 — 여기선 읽기만
    한다(위 get_playground_url 의 msa_jfb.deployment 조인과 같은 크로스 스키마 읽기).
    ⚠️ lineage id 는 내보내지 않는다 — 워커 목록이 다운로드 인가 정찰을 막으려 감추는 값이고,
    상세 라우트엔 배포별 접근 검사가 없다. 모델은 배포와 같은 워크스페이스 산출물일 때만(아니면 NULL).
    여러 디바이스면 running 을 먼저, 그다음 최근 관측 순. 연결된 워커가 없으면 None.
    """
    sql = """
        SELECT w.id AS worker_id, l.source_model_id AS model_id
        FROM msa_jfb.edge_worker w
        JOIN jonathan_llm.playground p ON p.id = w.deploy_playground_id
        LEFT JOIN jonathan_llm.quantize_lineage l
               ON l.id = w.deploy_lineage_id AND l.workspace_id = p.workspace_id
        WHERE w.deploy_playground_id = %s
        ORDER BY (w.deploy_state = 'running') DESC, w.deploy_observed_at DESC, w.id DESC
        LIMIT 1
        """
    return await select_query(query=sql, params=(playground_id,), fetch_type=FetchType.ONE)


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
