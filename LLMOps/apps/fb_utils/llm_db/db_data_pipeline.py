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
                judge_comment, taxonomy, asset_ref, lineage dict), ...]

    같은 레코드를 다시 심사하면 **덮어쓴다**(uk_dp_record_key 기준 upsert). 새 행을
    쌓으면 재심사 한 번에 데이터셋이 두 배가 되고 통과율 집계가 옛 점수와 섞인다.

    덮어쓰지 않는 컬럼이 셋 있다:
      - review_state / taxonomy : 사람이 검수하며 남긴 판정과 오류 분류다. 재심사는
        점수를 다시 매기는 일이지 사람의 판단을 지우는 일이 아니다.
      - split : 학습/검증 분할은 구성·분할 단계가 정하므로 심사가 건드릴 것이 아니다.
    id 가 유지되므로 llm_dp_review 의 참조도 그대로 살아 있다.
    """
    if not rows:
        return 0
    sql = """
        INSERT INTO jonathan_llm.llm_dp_record
            (dataset_id, record_key, capability, split, question, answer,
             scores, judge_comment, taxonomy, asset_ref, lineage, worst_score, review_state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        ON DUPLICATE KEY UPDATE
            capability    = VALUES(capability),
            question      = VALUES(question),
            answer        = VALUES(answer),
            scores        = VALUES(scores),
            judge_comment = VALUES(judge_comment),
            asset_ref     = VALUES(asset_ref),
            lineage       = VALUES(lineage),
            worst_score   = VALUES(worst_score)
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


async def list_records_for_release(dataset_id):
    """릴리스에 담을 후보 전량. list_records 와 달리 **lineage 를 포함**한다 —
    분할 기준(문서 ID·이미지)과 manifest 의 source_runs 가 거기서 나온다.
    검수 큐가 아니므로 정렬·페이징 없이 id 순으로 전량을 준다.
    """
    sql = """
        SELECT id, record_key, capability, split, question, answer, scores,
               judge_comment, taxonomy, review_state, asset_ref, lineage, worst_score
        FROM jonathan_llm.llm_dp_record
        WHERE dataset_id = %s
        ORDER BY id ASC
    """
    rows = await select_query(sql, params=[dataset_id]) or []
    for r in rows:
        r["scores"] = _loads(r.get("scores"), {})
        r["lineage"] = _loads(r.get("lineage"), {})
    return rows


async def set_record_splits(assignments):
    """[(split, record_id), ...] 를 한 번에 반영. 릴리스가 확정한 분할을 레코드에 새긴다.

    분할을 레코드에 쓰는 이유: 파일만 나눠 두면 재릴리스·재검수 때 어느 레코드가 어느
    쪽이었는지 알 수 없고, 같은 문서가 train 과 test 로 갈리는 누수를 검증할 수 없다.
    """
    if not assignments:
        return 0
    sql = "UPDATE jonathan_llm.llm_dp_record SET split = %s WHERE id = %s"
    return await commit_query(sql, params=list(assignments), execute="many")


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


async def list_work_dataset_ids(workspace_id):
    """이 워크스페이스의 파이프라인이 **산출물을 쌓는** 데이터셋 id 목록.

    소스 선택 목록에서 빼기 위한 것이다. 그대로 노출하면 사용자가 파이프라인의 출력을
    자기 입력으로 골라 자기 산출물을 다시 먹이는 순환을 만들 수 있다. 이름 규칙(dp-)이
    아니라 이 컬럼으로 걸러야 사용자가 데이터셋 이름을 바꿔도 정확하다.
    """
    sql = """
        SELECT work_dataset_id FROM jonathan_llm.llm_dp_dataset
        WHERE workspace_id = %s AND work_dataset_id IS NOT NULL
    """
    rows = await select_query(sql, params=[workspace_id]) or []
    return [r["work_dataset_id"] for r in rows]


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


# ── 노드 실행 이력 ───────────────────────────────────────────────────────────
async def create_run(dataset_id, run_id, node_index, stage, job_name, dry_run, out_dir):
    """잡을 띄우는 시점에 running 으로 남긴다.

    잡이 끝난 뒤에 기록하면 그 사이 화면이 "아무 일도 없음"을 보게 되고, 잡이 죽으면
    실행 자체가 흔적 없이 사라진다. 시작을 먼저 적고 끝을 나중에 채우는 이유다.
    """
    sql = """
        INSERT INTO jonathan_llm.llm_dp_run
            (dataset_id, run_id, node_index, stage, job_name, status, dry_run, out_dir)
        VALUES (%s, %s, %s, %s, %s, 'running', %s, %s)
    """
    return await commit_query(sql, params=[
        dataset_id, run_id, node_index, stage, job_name, 1 if dry_run else 0, out_dir])


async def set_run_job(run_pk, job_name):
    """잡 이름을 나중에 채운다.

    서빙 준비를 기다렸다 잡을 띄우는 경로에서, 실행 이력은 사용자가 버튼을 누른 즉시
    만들고(안 그러면 클릭이 아무 일도 안 한 것처럼 보인다) 잡 이름은 실제로 띄운 뒤에
    채운다. 비어 있는 job_name = "아직 띄우지 않았다" 라는 뜻이고, 리콘사일러가 그
    상태로 너무 오래 있는 실행을 판별하는 근거가 된다.
    """
    sql = "UPDATE jonathan_llm.llm_dp_run SET job_name = %s WHERE id = %s"
    return await commit_query(sql, params=[job_name, run_pk])


async def list_running_runs(limit=200):
    """리콘사일러가 마감할 후보. 오래된 것부터 본다(먼저 시작한 게 먼저 끝난다)."""
    sql = """
        SELECT id, dataset_id, run_id, node_index, stage, job_name, dry_run, out_dir,
               create_datetime
        FROM jonathan_llm.llm_dp_run
        WHERE status = 'running'
        ORDER BY id ASC
        LIMIT %s
    """
    return await select_query(sql, params=[limit]) or []


async def finish_run(run_pk, status, in_count=None, out_count=None, dropped_count=None,
                     funnel=None, error_reason=None):
    """실행을 done/failed 로 마감한다.

    status 를 조건에 넣어 running 인 행만 갱신한다 — 리콘사일러가 여러 번 돌아도
    이미 마감된 실행의 카운트를 덮어쓰지 않는다.
    """
    sql = """
        UPDATE jonathan_llm.llm_dp_run
        SET status = %s, in_count = %s, out_count = %s, dropped_count = %s,
            funnel = %s, error_reason = %s, end_datetime = NOW()
        WHERE id = %s AND status = 'running'
    """
    return await commit_query(sql, params=[
        status, in_count, out_count, dropped_count,
        json.dumps(funnel, ensure_ascii=False) if funnel is not None else None,
        (error_reason or None), run_pk])


async def latest_done_run(dataset_id, node_index):
    """그 노드의 가장 최근 성공 실행. 다음 노드의 입력이 된다.

    미리보기(dry_run)는 표본만 돌린 결과라 제외한다 — 상류로 쓰면 하류가 조용히
    일부 데이터만 처리하고도 정상으로 보인다.
    """
    sql = """
        SELECT id, run_id, node_index, stage, out_dir, in_count, out_count, dropped_count
        FROM jonathan_llm.llm_dp_run
        WHERE dataset_id = %s AND node_index = %s AND status = 'done' AND dry_run = 0
        ORDER BY id DESC
        LIMIT 1
    """
    return await select_query(sql, params=[dataset_id, node_index], fetch_type="one")


async def list_runs(dataset_id, node_index=None, limit=50):
    """데이터셋의 실행 이력(최신순). node_index 를 주면 그 노드만."""
    where = ["dataset_id = %s"]
    params = [dataset_id]
    if node_index is not None:
        where.append("node_index = %s")
        params.append(node_index)
    params.append(limit)
    sql = f"""
        SELECT id, dataset_id, run_id, node_index, stage, job_name, status, dry_run,
               out_dir, in_count, out_count, dropped_count, funnel, error_reason,
               create_datetime, end_datetime
        FROM jonathan_llm.llm_dp_run
        WHERE {' AND '.join(where)}
        ORDER BY id DESC
        LIMIT %s
    """
    rows = await select_query(sql, params=params) or []
    for r in rows:
        r["funnel"] = _loads(r.get("funnel"), None)
        r["dry_run"] = bool(r.get("dry_run"))
    return rows


async def get_job_end_state(job_name):
    """스케줄러가 남긴 잡 종료 상태. 산출물이 없을 때 '아직 도는 중'과 '죽었다'를 가른다.

    llm_dp_* 밖(msa_jfb.preprocessing_job)을 읽는 유일한 함수다. 실행 이력을 우리
    테이블에 중복 적재하지 않고, 종료 판정만 원본에서 빌려 온다.
    """
    sql = """
        SELECT end_datetime, end_status, error_reason
        FROM msa_jfb.preprocessing_job
        WHERE name = %s
        ORDER BY id DESC
        LIMIT 1
    """
    return await select_query(sql, params=[job_name], fetch_type="one")


async def latest_runs_by_node(dataset_id):
    """노드별 가장 최근 실행 1건. 캔버스가 노드마다 따로 물어보지 않게 한 번에 준다.

    미리보기(dry_run)도 포함한다 — 방금 미리보기를 돌렸는데 화면이 아무 반응이 없으면
    사용자는 실행이 안 된 줄 안다. 대신 dry_run 을 실어 보내 화면이 구분해 표시한다.
    """
    sql = """
        SELECT r.id, r.run_id, r.node_index, r.stage, r.status, r.dry_run, r.out_dir,
               r.in_count, r.out_count, r.dropped_count, r.funnel, r.error_reason,
               r.create_datetime, r.end_datetime
        FROM jonathan_llm.llm_dp_run r
        JOIN (
            SELECT node_index, MAX(id) AS id
            FROM jonathan_llm.llm_dp_run
            WHERE dataset_id = %s
            GROUP BY node_index
        ) m ON r.id = m.id
    """
    rows = await select_query(sql, params=[dataset_id]) or []
    out = {}
    for r in rows:
        r["funnel"] = _loads(r.get("funnel"), None)
        r["dry_run"] = bool(r.get("dry_run"))
        out[r["node_index"]] = r
    return out


async def get_run(dataset_id, run_id):
    """실행 단건. run_id 는 실행마다 새로 발급되므로 데이터셋 안에서 유일하다."""
    sql = """
        SELECT id, dataset_id, run_id, node_index, stage, job_name, status, dry_run,
               out_dir, in_count, out_count, dropped_count, funnel, error_reason,
               create_datetime, end_datetime
        FROM jonathan_llm.llm_dp_run
        WHERE dataset_id = %s AND run_id = %s
        ORDER BY id DESC
        LIMIT 1
    """
    row = await select_query(sql, params=[dataset_id, run_id], fetch_type="one")
    if row:
        row["funnel"] = _loads(row.get("funnel"), None)
        row["dry_run"] = bool(row.get("dry_run"))
    return row


# ── 파이프라인이 소유한 VLM 서빙 ─────────────────────────────────────────────
async def upsert_serving(dataset_id, role, model_id, hf_id):
    """역할(generator|judge)당 하나. 배포를 **띄우기 전에** pending 으로 자리를 잡는다.

    먼저 적는 이유: 배포 도중 프로세스가 끊기면 GPU 만 물고 아무도 모르는 배포가 남는다.
    기록이 먼저 있으면 리콘사일러가 그것을 발견해 정리할 수 있다.
    """
    sql = """
        INSERT INTO jonathan_llm.llm_dp_serving
            (dataset_id, role, model_id, hf_id, status, last_used_datetime)
        VALUES (%s, %s, %s, %s, 'pending', NOW())
        ON DUPLICATE KEY UPDATE
            -- 모델이 바뀌었으면 기존 배포는 더 쓸 수 없다 → 다시 준비 상태로.
            -- ⚠️ 이 줄이 model_id 대입보다 **먼저** 와야 한다. MariaDB 는 ON DUPLICATE KEY
            -- UPDATE 의 대입을 좌→우로 평가하고 오른쪽 항은 이미 갱신된 값을 읽으므로,
            -- model_id 를 먼저 덮으면 model_id = VALUES(model_id) 가 항상 참이 되어
            -- 이 가드가 죽는다 — 심사 모델만 바꿨을 때 장부가 옛 배포를 ready 로 물고
            -- 있어 잡이 그 죽은 주소로 간다.
            status = IF(model_id = VALUES(model_id) AND status = 'ready', 'ready', 'pending'),
            model_id = VALUES(model_id), hf_id = VALUES(hf_id),
            last_used_datetime = NOW(),
            error_reason = NULL, release_datetime = NULL
    """
    return await commit_query(sql, params=[dataset_id, role, model_id, hf_id])


async def get_serving(dataset_id, role):
    sql = """
        SELECT id, dataset_id, role, model_id, hf_id, playground_id, api_path, status,
               error_reason, create_datetime, last_used_datetime, release_datetime
        FROM jonathan_llm.llm_dp_serving
        WHERE dataset_id = %s AND role = %s
    """
    return await select_query(sql, params=[dataset_id, role], fetch_type="one")


async def list_servings(dataset_id):
    sql = """
        SELECT id, role, model_id, hf_id, playground_id, api_path, status, error_reason,
               create_datetime, last_used_datetime, release_datetime
        FROM jonathan_llm.llm_dp_serving
        WHERE dataset_id = %s
        ORDER BY role
    """
    return await select_query(sql, params=[dataset_id]) or []


async def set_serving(serving_id, status=None, playground_id=None, api_path=None,
                      error_reason=None, released=False):
    """상태 전이. 지정한 칸만 바꾼다 — 준비 중에 playground_id 만 채우는 경우가 있다."""
    sets, params = [], []
    if status is not None:
        sets.append("status = %s"); params.append(status)
    if playground_id is not None:
        sets.append("playground_id = %s"); params.append(playground_id)
    if api_path is not None:
        sets.append("api_path = %s"); params.append(api_path)
    if error_reason is not None:
        sets.append("error_reason = %s"); params.append(error_reason[:1000])
    if released:
        sets.append("release_datetime = NOW()")
    if not sets:
        return 0
    params.append(serving_id)
    sql = f"UPDATE jonathan_llm.llm_dp_serving SET {', '.join(sets)} WHERE id = %s"
    return await commit_query(sql, params=params)


async def touch_serving(dataset_id, role):
    """노드가 이 서빙을 쓸 때마다 찍는다. 유휴 판정 = 회수 시점의 근거."""
    sql = ("UPDATE jonathan_llm.llm_dp_serving SET last_used_datetime = NOW() "
           "WHERE dataset_id = %s AND role = %s")
    return await commit_query(sql, params=[dataset_id, role])


async def list_live_servings():
    """아직 GPU 를 물고 있는 서빙 전량(회수 후보). released/failed 는 이미 내려간 것."""
    sql = """
        SELECT id, dataset_id, role, model_id, playground_id, api_path, status,
               create_datetime, last_used_datetime
        FROM jonathan_llm.llm_dp_serving
        WHERE status IN ('pending', 'ready')
        ORDER BY id ASC
    """
    return await select_query(sql) or []
