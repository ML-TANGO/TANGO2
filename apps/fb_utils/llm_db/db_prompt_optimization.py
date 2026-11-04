"""prompt_optimization CRUD — 프롬프트 최적화 결과 영속.

컨테이너(TTL 1h)와 플랫폼 job tracker 둘 다 휘발성이라, completed 전이 시점에
산출물을 여기 저장해 두지 않으면 결과가 사라진다.
스키마: apps/llm_playground/migrations/001_prompt_optimization.sql
"""

import json
import traceback

from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils import TYPE

# 목록 공통 컬럼. system_prompt/demos/examples 는 큰 값이라 목록에서 제외한다.
# error_message 는 VARCHAR(500) 로 작고, 실패 행의 원인을 목록에서 바로 보여줘야
# 사용자가 상세를 열지 않고도 재시도 여부를 판단할 수 있어 포함한다.
_LIST_COLS = """
    id, workspace_id, playground_id, model_id, commit_id, job_id, status,
    metric, model, base_score, final_score, is_active, error_message,
    DATE_FORMAT(create_datetime, %s) create_datetime,
    DATE_FORMAT(finish_datetime, %s) finish_datetime
"""

# 산출물 길이 cap. 컨테이너(협력기관 코드)가 돌려주는 텍스트는 우리가 통제하지 못하는데,
# 활성 지정되면 이후 **모든** 추론 요청 앞에 붙는다 → 폭주 시 비용·지연이 영구 증폭된다.
# 입력 예시 cap(service._PROMPT_OPT_FIELD_MAX=2000)보다 크게 잡는다: system_prompt 는
# instruction + demo 여러 쌍을 합친 텍스트라 정상값도 수 KB 가 된다.
_PROMPT_TEXT_MAX = 20000
_ERROR_TEXT_MAX = 500       # error_message 컬럼 길이와 일치(초과분은 잘라 저장)


async def insert_prompt_optimization(workspace_id, playground_id, job_id,
                                     model_id=None, commit_id=None,
                                     metric=None, examples=None, status='pending'):
    """최적화 실행 등록. 반환: (성공여부, id)."""
    try:
        sql = """INSERT INTO prompt_optimization
                 (workspace_id, playground_id, model_id, commit_id, job_id, status, metric, examples)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        new_id = await commit_query(query=sql, params=(
            workspace_id, playground_id, model_id, commit_id, job_id, status, metric,
            json.dumps(examples, ensure_ascii=False) if examples is not None else None))
        return True, new_id
    except Exception:
        traceback.print_exc()
        return False, None


async def get_prompt_optimization(optimization_id):
    """상세 — 산출물(system_prompt/instruction/demos) 포함."""
    sql = """SELECT p.*,
             DATE_FORMAT(p.create_datetime, %s) create_datetime,
             DATE_FORMAT(p.finish_datetime, %s) finish_datetime
             FROM prompt_optimization p WHERE p.id=%s"""
    return await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL,
                                           TYPE.TIME_DATE_FORMAT_SQL, optimization_id),
                              fetch_type=FetchType.ONE)


async def get_prompt_optimization_list(playground_id):
    """한 배포의 최적화 이력(최신순). 목록은 큰 텍스트 컬럼을 싣지 않는다."""
    sql = f"""SELECT {_LIST_COLS} FROM prompt_optimization
              WHERE playground_id=%s ORDER BY id DESC"""
    return await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL,
                                           TYPE.TIME_DATE_FORMAT_SQL, playground_id))


async def get_active_prompt_optimization(playground_id):
    """추론에 주입할 활성 1건. 없으면 None — 최적화 미적용 상태를 뜻한다.

    model_id/commit_id 를 함께 돌려준다: 프롬프트는 **그 모델을 상대로** 탐색된
    산출물이라, 배포 모델이 바뀌면 더 이상 유효하지 않다(호출자가 대조해 폐기).
    """
    sql = """SELECT id, system_prompt, instruction, metric, model, final_score,
                    model_id, commit_id
             FROM prompt_optimization
             WHERE playground_id=%s AND is_active=1 AND status='completed'
             ORDER BY id DESC LIMIT 1"""
    return await select_query(sql, params=(playground_id,), fetch_type=FetchType.ONE)


async def get_pending_prompt_optimizations(limit=200):
    """비종료(pending/running) 행 — 기동 시 폴링 재개용.

    결과 영속은 "완료를 본 쪽이 저장한다" 구조라, 폴링 주체가 사라지면(파드 재시작·
    사용자 이탈) 산출물이 컨테이너 TTL 과 함께 영구 유실된다. 기동 시 이 목록을
    다시 폴링해 그 구멍을 막는다(external_container 의 startup_recovery 와 같은 관행).
    """
    sql = """SELECT id, playground_id, job_id FROM prompt_optimization
             WHERE status NOT IN ('completed','failed','cancelled')
               AND job_id IS NOT NULL
             ORDER BY id DESC LIMIT %s"""
    return await select_query(sql, params=(int(limit),))


async def update_prompt_optimization_result(optimization_id, status, result=None,
                                            finished=False, error_message=None):
    """폴링 결과 반영. completed 면 산출물을 함께 저장한다(휘발 방지).

    error_message 를 받으면 함께 저장한다 — 어댑터가 컨테이너의 top-level
    code/message 를 복원해 두는데(FewshotPromptAdapter._build_result) 여기서 버리면
    UI 에 원인 없는 'failed' 만 남아 어댑터를 만든 이유가 사라진다.
    """
    try:
        cols = ["status=%s"]
        params = [status]
        if error_message is not None:
            cols.append("error_message=%s")
            params.append(str(error_message)[:_ERROR_TEXT_MAX])
        if isinstance(result, dict):
            for col in ("system_prompt", "instruction", "metric", "model"):
                if result.get(col) is not None:
                    cols.append(f"{col}=%s")
                    # 텍스트 산출물만 cap — metric/model 은 짧은 식별자다.
                    params.append(str(result[col])[:_PROMPT_TEXT_MAX]
                                  if col in ("system_prompt", "instruction")
                                  else result[col])
            for col in ("base_score", "final_score"):
                if result.get(col) is not None:
                    cols.append(f"{col}=%s")
                    params.append(float(result[col]))
            if result.get("demos") is not None:
                cols.append("demos=%s")
                params.append(json.dumps(result["demos"], ensure_ascii=False))
        if finished:
            cols.append("finish_datetime=CURRENT_TIMESTAMP")
        sql = f"UPDATE prompt_optimization SET {', '.join(cols)} WHERE id=%s"
        params.append(optimization_id)
        await commit_query(query=sql, params=tuple(params))
        return True
    except Exception:
        traceback.print_exc()
        return False


async def set_active_prompt_optimization(playground_id, optimization_id):
    """활성 지정/해제. optimization_id=None 이면 전체 해제.

    단일 활성 불변식 — 같은 playground 안에서 대상만 1, 나머지는 0.
    completed 가 아닌 행은 올리지 않는다(IF 조건의 status 가드).

    ⚠️ 반드시 **단일 UPDATE** 여야 한다. commit_query 는 호출마다 새 커넥션을 열고
    즉시 커밋하므로 "해제 → 지정" 2문으로 쪼개면 한 트랜잭션이 아니고,
    동시 요청이 끼어들면(A해제→B해제→A지정→B지정) 두 행이 함께 is_active=1 로 남아
    스키마 주석이 약속한 불변식이 깨진다. 한 문장이면 행 잠금이 문장 단위로 걸려
    그 인터리빙 자체가 불가능하다.
    """
    try:
        # id 가 NULL(=해제)이면 IF 가 항상 0 → 같은 문장으로 전체 해제까지 처리된다.
        await commit_query(
            query="""UPDATE prompt_optimization
                     SET is_active = IF(%s IS NOT NULL AND id = %s
                                        AND status = 'completed', 1, 0)
                     WHERE playground_id = %s""",
            params=(optimization_id, optimization_id, playground_id))
        return True
    except Exception:
        traceback.print_exc()
        return False
