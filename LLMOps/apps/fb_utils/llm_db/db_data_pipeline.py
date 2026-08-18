"""학습 데이터 파이프라인 DB 접근 (llm_data_pipeline 서비스 전용).

`jonathan_llm` 의 llm_dp_* 6테이블만 다룬다. db_rag / db_playground 와 같은 형태로
select_query / commit_query 를 그대로 쓰고, 실패는 호출부가 판단하도록 올려보낸다.
"""
import json

import aiomysql

from utils.llm_db.db_base_async import db_config, select_query, commit_query
from utils import TYPE

_TS = TYPE.TIME_DATE_FORMAT_SQL


def _loads(value, default):
    """JSON 컬럼은 드라이버에 따라 str 로도 dict 로도 온다. 둘 다 받아준다."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# ── 데이터셋 ────────────────────────────────────────────────────────────────
async def list_datasets(workspace_id=None):
    """워크스페이스의 데이터셋 목록.

    레코드 수 · 미검수 수 · 최신 버전은 목록 화면이 매번 보여주는 값이라 여기서 한 번에
    집계한다(화면이 N+1 로 다시 묻지 않게).
    """
    sql = """
        SELECT d.id, d.workspace_id, d.name, d.description, d.state, d.preset,
               d.create_user,
               DATE_FORMAT(d.create_datetime, %s) AS create_datetime,
               DATE_FORMAT(d.update_datetime, %s) AS update_datetime,
               (SELECT COUNT(*) FROM jonathan_llm.llm_dp_asset a
                 WHERE a.dataset_id = d.id AND a.status = 'registered') AS asset_count,
               (SELECT COUNT(*) FROM jonathan_llm.llm_dp_record r
                 WHERE r.dataset_id = d.id) AS record_count,
               (SELECT COUNT(*) FROM jonathan_llm.llm_dp_record r
                 WHERE r.dataset_id = d.id AND r.review_state = 'pending') AS unreviewed_count,
               (SELECT v.version FROM jonathan_llm.llm_dp_version v
                 WHERE v.dataset_id = d.id ORDER BY v.id DESC LIMIT 1) AS latest_version,
               (SELECT v.pass_rate FROM jonathan_llm.llm_dp_version v
                 WHERE v.dataset_id = d.id ORDER BY v.id DESC LIMIT 1) AS latest_pass_rate
        FROM jonathan_llm.llm_dp_dataset d
    """
    params = [_TS, _TS]
    if workspace_id is not None:
        sql += " WHERE d.workspace_id = %s"
        params.append(workspace_id)
    sql += " ORDER BY d.id DESC"
    return await select_query(sql, params=params)


async def get_dataset(dataset_id):
    sql = """
        SELECT d.id, d.workspace_id, w.name AS workspace_name, d.name, d.description,
               d.state, d.preset, d.create_user, d.flow,
               d.work_dataset_id, d.work_dataset_name,
               DATE_FORMAT(d.create_datetime, %s) AS create_datetime,
               DATE_FORMAT(d.update_datetime, %s) AS update_datetime
        FROM jonathan_llm.llm_dp_dataset d
        LEFT JOIN msa_jfb.workspace w ON w.id = d.workspace_id
        WHERE d.id = %s
    """
    row = await select_query(sql, params=[_TS, _TS, dataset_id], fetch_type="one")
    if row:
        row["flow"] = _loads(row.get("flow"), [])
    return row


async def create_dataset(workspace_id, name, description, preset, create_user):
    sql = """
        INSERT INTO jonathan_llm.llm_dp_dataset
            (workspace_id, name, description, state, preset, create_user)
        VALUES (%s, %s, %s, 'draft', %s, %s)
    """
    return await commit_query(sql, params=[workspace_id, name, description, preset, create_user])


async def dataset_name_exists(workspace_id, name):
    """워크스페이스 안에서 이름이 이미 쓰였는지. UNIQUE 위반을 드라이버까지 보내면
    에러 메시지에 테이블·제약조건명이 실려 나가므로 미리 막는다."""
    sql = ("SELECT id FROM jonathan_llm.llm_dp_dataset "
           "WHERE workspace_id = %s AND name = %s")
    return await select_query(sql, params=[workspace_id, name], fetch_type="one") is not None


async def update_dataset(dataset_id, name=None, description=None, state=None):
    """지정된 필드만 바꾼다. 하나도 없으면 쿼리를 보내지 않는다."""
    sets, params = [], []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if state is not None:
        sets.append("state = %s")
        params.append(state)
    if not sets:
        return 0
    params.append(dataset_id)
    sql = f"UPDATE jonathan_llm.llm_dp_dataset SET {', '.join(sets)} WHERE id = %s"
    return await commit_query(sql, params=params)


async def delete_dataset(dataset_id):
    """자식(asset·node·record·review·version)은 FK ON DELETE CASCADE 로 함께 지워진다."""
    sql = "DELETE FROM jonathan_llm.llm_dp_dataset WHERE id = %s"
    return await commit_query(sql, params=[dataset_id])


# ── 원본 데이터(asset) ──────────────────────────────────────────────────────
async def list_assets(dataset_id, status=None, limit=100, offset=0):
    sql = """
        SELECT id, dataset_id, name, path, kind, size_bytes, status, fail_reason,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM jonathan_llm.llm_dp_asset
        WHERE dataset_id = %s
    """
    params = [_TS, dataset_id]
    if status is not None:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY id ASC LIMIT %s OFFSET %s"
    params += [int(limit), int(offset)]
    return await select_query(sql, params=params)


async def get_asset_summary(dataset_id):
    """업로드 요약 — 전체 · 등록 · 중복 · 실패. 화면 상단 숫자가 이 한 줄에서 나온다."""
    sql = """
        SELECT COUNT(*) AS total,
               SUM(status = 'registered') AS registered,
               SUM(status = 'duplicate')  AS duplicate,
               SUM(status = 'failed')     AS failed
        FROM jonathan_llm.llm_dp_asset
        WHERE dataset_id = %s
    """
    return await select_query(sql, params=[dataset_id], fetch_type="one")


async def get_asset_failures(dataset_id):
    """실패를 사유별로 묶는다. 같은 사유가 수십 건이면 하나씩 보여줄 이유가 없다."""
    sql = """
        SELECT fail_reason AS reason, COUNT(*) AS count
        FROM jonathan_llm.llm_dp_asset
        WHERE dataset_id = %s AND status = 'failed'
        GROUP BY fail_reason
        ORDER BY count DESC
    """
    return await select_query(sql, params=[dataset_id])


async def count_assets(dataset_id):
    """등록된 원본 수. 레코드의 asset_ref 로 세면 '아직 생성 안 한 원본' 이 보이지 않아
    '데이터 없음' 과 '생성 부족' 을 구분할 수 없다."""
    sql = ("SELECT COUNT(*) AS n FROM jonathan_llm.llm_dp_asset "
           "WHERE dataset_id = %s AND status = 'registered'")
    row = await select_query(sql, params=[dataset_id], fetch_type="one")
    return int((row or {}).get("n") or 0)


async def insert_assets(dataset_id, rows):
    """rows = [(name, path, kind, size_bytes, status, fail_reason), ...]"""
    if not rows:
        return 0
    sql = """
        INSERT INTO jonathan_llm.llm_dp_asset
            (dataset_id, name, path, kind, size_bytes, status, fail_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    params = [(dataset_id,) + tuple(r) for r in rows]
    return await commit_query(sql, params=params, execute="many")


# ── 파이프라인 노드 ─────────────────────────────────────────────────────────
async def get_flow(dataset_id):
    """노드를 순서대로 돌려준다. steps/config 는 JSON 이라 파싱해서 넘긴다."""
    sql = """
        SELECT id, dataset_id, preset, node_index, kind, name, steps, config
        FROM jonathan_llm.llm_dp_node
        WHERE dataset_id = %s
        ORDER BY node_index ASC
    """
    rows = await select_query(sql, params=[dataset_id]) or []
    for r in rows:
        r["steps"] = _loads(r.get("steps"), [])
        r["config"] = _loads(r.get("config"), {})
    return rows


async def replace_flow(dataset_id, preset, nodes, flow=None):
    """노드 체인과 엣지를 통째로 갈아 끼운다.

    부분 수정 대신 전체 교체인 이유: 노드 순서(node_index)와 연결이 서로 얽혀 있어
    한 노드만 고치면 나머지 인덱스가 어긋난다. 화면도 항상 전체를 보낸다.

    DELETE 와 INSERT 를 **한 트랜잭션**에서 처리한다. 따로 커밋하면 INSERT 가 실패했을 때
    기존 구성이 복구 불가능하게 사라진다.
    """
    conn = await aiomysql.connect(**db_config)
    try:
        await conn.begin()
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM jonathan_llm.llm_dp_node WHERE dataset_id = %s", (dataset_id,))
            if nodes:
                await cur.executemany(
                    """
                    INSERT INTO jonathan_llm.llm_dp_node
                        (dataset_id, preset, node_index, kind, name, steps, config)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [(dataset_id, preset, i, n.get("kind"), n.get("name"),
                      json.dumps(n.get("steps", []), ensure_ascii=False),
                      json.dumps(n.get("config", {}), ensure_ascii=False))
                     for i, n in enumerate(nodes)],
                )
            # 엣지는 노드가 아니라 그래프의 속성이라 데이터셋 행에 둔다.
            await cur.execute(
                "UPDATE jonathan_llm.llm_dp_dataset SET preset = %s, flow = %s WHERE id = %s",
                (preset, json.dumps(flow or [], ensure_ascii=False), dataset_id))
        await conn.commit()
        return len(nodes or [])
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.ensure_closed()


# ── 레코드 ──────────────────────────────────────────────────────────────────
async def list_records(dataset_id, review_state=None, taxonomy=None,
                       order="score_asc", limit=50, offset=0):
    """검수 큐.

    기본 정렬이 '점수 낮은 순'인 이유: 사람 시간이 가장 비싸므로 위험한 것부터 본다.
    scores JSON 에서 최저 축 값을 뽑아 정렬 키로 쓴다.
    """
    sql = """
        SELECT id, dataset_id, record_key, capability, split, question, answer,
               scores, judge_comment, taxonomy, review_state, asset_ref,
               worst_score,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM jonathan_llm.llm_dp_record
        WHERE dataset_id = %s
    """
    params = [_TS, dataset_id]
    if review_state is not None:
        sql += " AND review_state = %s"
        params.append(review_state)
    if taxonomy is not None:
        sql += " AND taxonomy = %s"
        params.append(taxonomy)

    if order == "score_asc":
        # worst_score 가 NULL(=아직 채점 안 됨) 인 것을 맨 앞에 둔다. 미평가를 통과로
        # 취급하면 위험한 것부터 본다는 정렬의 목적이 무너진다.
        sql += " ORDER BY worst_score IS NOT NULL ASC, worst_score ASC, id ASC"
    elif order == "random":
        sql += " ORDER BY RAND()"
    else:
        sql += " ORDER BY taxonomy ASC, id ASC"

    sql += " LIMIT %s OFFSET %s"
    params += [int(limit), int(offset)]

    rows = await select_query(sql, params=params) or []
    for r in rows:
        r["scores"] = _loads(r.get("scores"), {})
    return rows


async def get_record(record_id):
    sql = """
        SELECT id, dataset_id, record_key, capability, split, question, answer,
               scores, judge_comment, taxonomy, review_state, asset_ref, lineage,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM jonathan_llm.llm_dp_record
        WHERE id = %s
    """
    row = await select_query(sql, params=[_TS, record_id], fetch_type="one")
    if row:
        row["scores"] = _loads(row.get("scores"), {})
        row["lineage"] = _loads(row.get("lineage"), {})
    return row


async def get_record_by_key(dataset_id, record_key):
    """화면은 사람이 읽는 키(vdf-0009855)로 이동하므로 그 경로도 열어둔다."""
    sql = "SELECT id FROM jonathan_llm.llm_dp_record WHERE dataset_id = %s AND record_key = %s"
    row = await select_query(sql, params=[dataset_id, record_key], fetch_type="one")
    return row["id"] if row else None


async def get_review_stats(dataset_id):
    sql = """
        SELECT COUNT(*) AS total,
               SUM(review_state = 'pending')  AS pending,
               SUM(review_state = 'approved') AS approved,
               SUM(review_state = 'edited')   AS edited,
               SUM(review_state = 'rejected') AS rejected
        FROM jonathan_llm.llm_dp_record
        WHERE dataset_id = %s
    """
    return await select_query(sql, params=[dataset_id], fetch_type="one")


async def get_taxonomy_distribution(dataset_id):
    sql = """
        SELECT taxonomy, COUNT(*) AS count
        FROM jonathan_llm.llm_dp_record
        WHERE dataset_id = %s AND taxonomy IS NOT NULL AND taxonomy <> ''
        GROUP BY taxonomy
        ORDER BY count DESC
    """
    return await select_query(sql, params=[dataset_id])


async def get_coverage(dataset_id):
    """데이터 유형별 레코드 수 + 원본 데이터 수.

    둘을 함께 세는 이유: 레코드가 적을 때 원본이 없어서인지(업로드 필요) 원본은 있는데
    생성이 안 된 것인지(생성 조건 문제)가 갈린다.
    """
    sql = """
        SELECT r.capability,
               COUNT(*) AS record_count,
               COUNT(DISTINCT r.asset_ref) AS asset_count
        FROM jonathan_llm.llm_dp_record r
        WHERE r.dataset_id = %s
        GROUP BY r.capability
    """
    return await select_query(sql, params=[dataset_id])


async def get_gate_fail_distribution(dataset_id, thresholds):
    """축별 미달 건수. 어느 축이 가장 많이 걸리는지가 다음에 고칠 곳을 알려준다.

    점수가 없는 축(미평가)도 미달로 센다 — 채점되지 않은 레코드를 통과로 두면
    통과율이 실제보다 좋게 나온다.
    """
    out = {}
    for axis, th in thresholds.items():
        sql = """
            SELECT COUNT(*) AS count
            FROM jonathan_llm.llm_dp_record
            WHERE dataset_id = %s
              AND COALESCE(JSON_EXTRACT(scores, CONCAT('$.', %s)), -1) < %s
        """
        row = await select_query(sql, params=[dataset_id, axis, float(th)], fetch_type="one")
        out[axis] = (row or {}).get("count", 0) or 0
    return out


async def count_gate_failed(dataset_id, thresholds):
    """어느 한 축이라도 미달인 **레코드 수**(합집합).

    축별 건수의 최대값을 쓰면 서로 다른 축에서 떨어진 레코드가 빠져 통과율이 부풀고,
    합을 쓰면 여러 축에서 떨어진 레코드가 중복 계산된다. 둘 다 틀리므로 합집합을 센다.
    """
    if not thresholds:
        return 0
    clauses, params = [], [dataset_id]
    for axis, th in thresholds.items():
        clauses.append("COALESCE(JSON_EXTRACT(scores, CONCAT('$.', %s)), -1) < %s")
        params += [axis, float(th)]
    sql = ("SELECT COUNT(*) AS count FROM jonathan_llm.llm_dp_record "
           "WHERE dataset_id = %s AND (" + " OR ".join(clauses) + ")")
    row = await select_query(sql, params=params, fetch_type="one")
    return int((row or {}).get("count") or 0)


async def insert_records(dataset_id, rows):
    """rows = [(record_key, capability, split, question, answer, scores dict,
                judge_comment, taxonomy, asset_ref, lineage dict), ...]"""
    if not rows:
        return 0
    sql = """
        INSERT INTO jonathan_llm.llm_dp_record
            (dataset_id, record_key, capability, split, question, answer,
             scores, judge_comment, taxonomy, asset_ref, lineage, worst_score, review_state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
    """
    params = []
    for r in rows:
        (key, cap, split, q, a, scores, judge, tax, asset_ref, lineage) = r
        # 최저 축을 기록 시점에 뽑아 둔다 — 검수 큐 정렬이 매번 JSON 을 평가하지 않게.
        vals = [v for v in (scores or {}).values() if isinstance(v, (int, float))]
        params.append((
            dataset_id, key, cap, split, q, a,
            json.dumps(scores or {}, ensure_ascii=False), judge, tax, asset_ref,
            json.dumps(lineage or {}, ensure_ascii=False),
            min(vals) if vals else None,
        ))
    return await commit_query(sql, params=params, execute="many")


# ── 검수 ────────────────────────────────────────────────────────────────────
async def insert_review(record_id, verdict, taxonomy, edited_question, edited_answer, reviewer):
    """판정을 이력으로 남기고 레코드의 현재 상태를 함께 갱신한다.

    이력을 따로 쌓는 이유: 같은 레코드를 다시 판정할 수 있고, 누가 언제 왜 그렇게
    판단했는지가 나중에 프롬프트를 고칠 때의 근거가 된다.
    """
    sql = """
        INSERT INTO jonathan_llm.llm_dp_review
            (record_id, verdict, taxonomy, edited_question, edited_answer, reviewer)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    review_id = await commit_query(
        sql, params=[record_id, verdict, taxonomy, edited_question, edited_answer, reviewer])

    sets = ["review_state = %s", "taxonomy = %s"]
    params = [verdict, taxonomy]
    # 수정 후 승인이면 본문을 수정본으로 갈아 끼운다 — 학습에 나가는 건 수정본이다.
    if verdict == "edited":
        if edited_question is not None:
            sets.append("question = %s")
            params.append(edited_question)
        if edited_answer is not None:
            sets.append("answer = %s")
            params.append(edited_answer)
    params.append(record_id)
    await commit_query(
        f"UPDATE jonathan_llm.llm_dp_record SET {', '.join(sets)} WHERE id = %s", params=params)
    return review_id


async def list_reviews(record_id):
    sql = """
        SELECT id, record_id, verdict, taxonomy, edited_question, edited_answer, reviewer,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM jonathan_llm.llm_dp_review
        WHERE record_id = %s
        ORDER BY id DESC
    """
    return await select_query(sql, params=[_TS, record_id])


# ── 버전 ────────────────────────────────────────────────────────────────────
async def list_versions(dataset_id):
    sql = """
        SELECT id, dataset_id, version, record_count, pass_rate, human_reviewed,
               gen_model, judge_model, prompt_name, thresholds, mix, split, split_by,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM jonathan_llm.llm_dp_version
        WHERE dataset_id = %s
        ORDER BY id ASC
    """
    rows = await select_query(sql, params=[_TS, dataset_id]) or []
    for r in rows:
        r["thresholds"] = _loads(r.get("thresholds"), {})
        r["mix"] = _loads(r.get("mix"), {})
        r["split"] = _loads(r.get("split"), {})
    return rows


async def find_platform_dataset_id(workspace_id, name):
    """플랫폼 데이터셋(msa_jfb.datasets) id 를 이름으로 찾는다.

    작업 데이터셋 생성이 동시 호출로 실패했을 때(이미 있음) 승자의 id 를 얻는 경로.
    """
    sql = "SELECT id FROM msa_jfb.datasets WHERE workspace_id = %s AND name = %s"
    row = await select_query(sql, params=[workspace_id, name], fetch_type="one")
    return (row or {}).get("id")


async def get_workspace_storage_name(workspace_id):
    """워크스페이스의 data 스토리지 이름. 데이터셋 실경로가 /jf-data/{이것}/data/... 다."""
    sql = """
        SELECT s.name
        FROM msa_jfb.workspace w
        JOIN msa_jfb.storage s ON s.id = w.data_storage_id
        WHERE w.id = %s
    """
    row = await select_query(sql, params=[workspace_id], fetch_type="one")
    return (row or {}).get("name")


async def set_work_dataset(dataset_id, work_dataset_id, work_dataset_name):
    """파이프라인이 소유한 작업 데이터셋을 기록한다(최초 1회).

    이미 값이 있으면 덮지 않는다 — 동시 실행이 각자 데이터셋을 만들었더라도 먼저 쓴
    쪽이 정본이고, 뒤늦은 쪽은 아래 재조회에서 그 값을 그대로 쓴다.
    """
    sql = """
        UPDATE jonathan_llm.llm_dp_dataset
        SET work_dataset_id = %s, work_dataset_name = %s
        WHERE id = %s AND work_dataset_id IS NULL
    """
    return await commit_query(sql, params=[work_dataset_id, work_dataset_name, dataset_id])


async def get_source_runs(dataset_id):
    """이 데이터셋 레코드들이 나온 실행 id 목록(중복 제거).

    레코드의 lineage JSON 에 run_id 로 남는다. 버전을 만들 때 이 목록을 스냅샷해
    "이 버전이 어느 실행에서 나왔나"를 나중에 되짚을 수 있게 한다.
    """
    sql = """
        SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(lineage, '$.run_id')) AS run_id
        FROM jonathan_llm.llm_dp_record
        WHERE dataset_id = %s
          AND JSON_EXTRACT(lineage, '$.run_id') IS NOT NULL
    """
    rows = await select_query(sql, params=[dataset_id], fetch_type="all") or []
    return sorted({r["run_id"] for r in rows if r.get("run_id")})


async def create_version(dataset_id, version, record_count, pass_rate, human_reviewed,
                         gen_model, judge_model, prompt_name, thresholds, mix, split,
                         split_by, source_runs=None):
    sql = """
        INSERT INTO jonathan_llm.llm_dp_version
            (dataset_id, version, record_count, pass_rate, human_reviewed,
             gen_model, judge_model, prompt_name, thresholds, mix, split, split_by,
             source_runs)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    return await commit_query(sql, params=[
        dataset_id, version, record_count, pass_rate, human_reviewed,
        gen_model, judge_model, prompt_name,
        json.dumps(thresholds or {}, ensure_ascii=False),
        json.dumps(mix or {}, ensure_ascii=False),
        json.dumps(split or {}, ensure_ascii=False),
        split_by,
        json.dumps(source_runs or [], ensure_ascii=False),
    ])


async def version_exists(dataset_id, version):
    sql = "SELECT id FROM jonathan_llm.llm_dp_version WHERE dataset_id = %s AND version = %s"
    row = await select_query(sql, params=[dataset_id, version], fetch_type="one")
    return row is not None
