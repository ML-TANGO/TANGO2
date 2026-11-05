"""Edge 워커 노드 + 커스텀 레이블 DB (SP-8 / 수용계획서 3.1).

remoteManager 가 관리하는 엣지 디바이스(인스턴스 없는 단일 노드)를 플랫폼 노드
테이블에 등록·상태추적. fb_resource 의 sync(pymysql) DB 패턴(db_node)을 그대로 따른다.
모든 쿼리 파라미터화.
"""
import traceback
from utils.msa_db.db_base import get_db


# ── 스키마 보정 ──────────────────────────────────────────────────────────────

def ensure_edge_worker_schema():
    """기동 시 `edge_worker` 의 후행 추가 컬럼을 멱등 보정한다.

    schema.sql 두 파일은 `CREATE TABLE IF NOT EXISTS` 안쪽이라 **이미 테이블이 있는
    기존 설치에는 새 컬럼이 생기지 않는다.** 이 리포에는 마이그레이션 러너가 없어
    (`apps/*/migrations/*.sql` 은 아무도 실행하지 않는다) 그 간극을 메우는 장치가 없었고,
    `last_heartbeat_at` 없이 새 코드가 올라가면 heartbeat UPDATE 가 실패해
    `record_heartbeat` 가 전건 거부된다 → last_seen 정지 → 300초 후 전 디바이스 offline.

    seed_manifests 와 같은 규율: **멱등**(`ADD COLUMN IF NOT EXISTS`, MariaDB)이고
    **never fatal**(실패는 로그만 — 스키마 보정 실패가 서비스 CrashLoop 이 되면 안 된다).
    컬럼을 추가만 하며 기존 컬럼·데이터는 건드리지 않는다.
    """
    # 컬럼명·타입은 하드코딩 리터럴만 — 외부 입력 불가(SQLi 방어 + 리팩터 안전망).
    _ADDITIVE = (
        ("last_heartbeat_at", "DATETIME DEFAULT NULL AFTER last_heartbeat_json"),
        ("deploy_observed_at", "DATETIME DEFAULT NULL AFTER last_heartbeat_at"),
        ("deploy_lineage_id", "INT(11) DEFAULT NULL AFTER deploy_observed_at"),
        ("deploy_error", "VARCHAR(512) DEFAULT NULL AFTER deploy_lineage_id"),
        ("deploy_playground_id", "INT(11) DEFAULT NULL AFTER deploy_error"),
    )
    # DDL 이 오래 걸릴 수 있는 자리다(Galera TOI · metadata lock 대기). 상한을 두지
    # 않으면 "never fatal" 과 무관하게 기동 자체가 붙잡힌다.
    _DDL_TIMEOUT_SEC = 10
    result = {"applied": [], "failed": []}
    for col, decl in _ADDITIVE:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                # MariaDB 세션 문장 시간 제한(초). 미지원 엔진이면 무시되게 별도 try.
                try:
                    cur.execute(f"SET SESSION max_statement_time={_DDL_TIMEOUT_SEC}")
                except Exception:
                    pass
                cur.execute(
                    f"ALTER TABLE edge_worker ADD COLUMN IF NOT EXISTS {col} {decl}"
                )
                conn.commit()
                result["applied"].append(col)
        except Exception as e:
            traceback.print_exc()
            # 실패를 반환값에 뭉개지 않는다. 이전 판본은 실패 시 빈 목록을 돌려줘
            # 호출자가 "이미 컬럼이 있어 할 일 없음" 과 구분할 수 없었고, 그래서
            # 한 번의 일시적 실패가 INFO 로 묻힌 채 컬럼 없는 서비스가 계속 살아
            # heartbeat 전건 실패가 지속될 수 있었다(2026-09-11 리뷰).
            result["failed"].append({"column": col, "error": f"{type(e).__name__}: {e}"})
    return result


# ── edge_worker ─────────────────────────────────────────────────────────────

def insert_edge_worker(device_id, name, device_type, remote_manager_url):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO edge_worker
                    (device_id, name, device_type, remote_manager_url)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (device_id, name, device_type, remote_manager_url))
            conn.commit()
            return cur.lastrowid
    except Exception:
        traceback.print_exc()
        return None


def get_edge_worker(worker_id=None, device_id=None, name=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # 제공된 필터만으로 조회(NULL OR 비교 회피).
            if worker_id is not None:
                cur.execute("SELECT * FROM edge_worker WHERE id=%s", (worker_id,))
            elif device_id is not None:
                cur.execute("SELECT * FROM edge_worker WHERE device_id=%s", (device_id,))
            elif name is not None:
                cur.execute("SELECT * FROM edge_worker WHERE name=%s", (name,))
            else:
                return None
            return cur.fetchone()
    except Exception:
        traceback.print_exc()
        return None


def get_edge_worker_list():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM edge_worker ORDER BY id DESC")
            return cur.fetchall() or []
    except Exception:
        traceback.print_exc()
        return []


def delete_edge_worker(worker_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM edge_worker WHERE id=%s", (worker_id,))
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def update_edge_worker_status(worker_id, conn_status, last_seen=None,
                              cpu_cores=None, mem_total=None, gpu_info=None,
                              container_count=None, deploy_model=None,
                              deploy_version=None, deploy_state=None,
                              deploy_observed_at=None, deploy_lineage_id=None,
                              deploy_error=None):
    """remoteManager /metrics 폴링 결과로 상태/자원/배포 갱신. None 필드는 건드리지 않음."""
    # SET 절 컬럼명은 아래 하드코딩 리터럴만 — 외부 입력 불가(SQLi 방어 + 리팩터 안전망).
    _ALLOWED = {"last_seen", "cpu_cores", "mem_total", "gpu_info",
                "container_count", "deploy_model", "deploy_version", "deploy_state",
                "deploy_observed_at", "deploy_lineage_id", "deploy_error"}
    try:
        sets = ["conn_status=%s"]
        params = [conn_status]
        for col, val in (
            ("last_seen", last_seen), ("cpu_cores", cpu_cores), ("mem_total", mem_total),
            ("gpu_info", gpu_info), ("container_count", container_count),
            ("deploy_model", deploy_model), ("deploy_version", deploy_version),
            ("deploy_state", deploy_state),
            # 호출자가 **실제로 배포를 관측했을 때만** 넘긴다. 폴링 실패(offline 표시)
            # 처럼 아무것도 못 본 경로는 넘기지 않아야 신선도가 거짓으로 갱신되지 않는다.
            ("deploy_observed_at", deploy_observed_at),
            # 이 워커가 내려받도록 **인가된** 아티팩트(quantize_lineage.id). 디바이스
            # 다운로드는 이 값만 허용하므로, 배포를 지시한 경로에서만 새긴다.
            ("deploy_lineage_id", deploy_lineage_id),
            # 비동기 배포 실패 사유. 에이전트가 /metrics 로만 알려주는 값이라 여기
            # 새기지 않으면 화면에는 'error' 만 뜨고 왜 실패했는지 알 길이 없다.
            ("deploy_error", deploy_error),
        ):
            if val is not None:
                assert col in _ALLOWED, f"unexpected column: {col}"
                sets.append(f"{col}=%s")
                params.append(val)
        params.append(worker_id)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE edge_worker SET {', '.join(sets)} WHERE id=%s", params)
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def update_edge_worker_token(worker_id, token_hash, token_prefix, token_expires_at):
    """노드별 Bearer 토큰 발급/rotation — 해시/prefix/만료 저장(평문 미저장)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE edge_worker SET edge_token_hash=%s, token_prefix=%s, "
                "token_expires_at=%s WHERE id=%s",
                (token_hash, token_prefix, token_expires_at, worker_id),
            )
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def update_edge_worker_heartbeat(worker_id, last_heartbeat_json, last_seen,
                                 deploy_model=None, deploy_observed_at=None):
    """디바이스 heartbeat 수신 → 원본 저장 + last_seen/last_heartbeat_at 갱신 + online 표시.

    last_heartbeat_at 은 **이 경로에서만** 갱신된다(디바이스 푸시 전용). last_seen 은
    refresh(/metrics 폴링)·deploy 도 갱신하는 '생존 증거'라, 30초 throttle 을 last_seen
    에 걸면 UI 새로고침 한 번이 디바이스의 다음 heartbeat 를 429 로 튕긴다.

    deploy_model 은 디바이스가 보고한 model_loaded 의 대사값이다. None 이면 컬럼을
    건드리지 않는다 — 빈 보고는 "배포 없음" 이 아니라 "정보 없음" 이며(에이전트
    재시작으로 휘발), 그 판정은 호출측(edge_service.record_heartbeat)이 이미 했다.
    """
    try:
        # SET 절은 아래 하드코딩 리터럴만 — 외부 입력이 컬럼명이 될 수 없다.
        # 자매 함수 update_edge_worker_status 와 동일하게 화이트리스트를 코드로
        # 강제한다(주석만으로는 리팩터가 변수를 끼워 넣는 회귀를 막지 못한다).
        _ALLOWED = {"deploy_model", "deploy_observed_at"}
        sets = ["conn_status='online'", "last_seen=%s", "last_heartbeat_at=%s",
                "last_heartbeat_json=%s"]
        params = [last_seen, last_seen, last_heartbeat_json]
        for col, val in (("deploy_model", deploy_model),
                         ("deploy_observed_at", deploy_observed_at)):
            if val is None:
                continue
            assert col in _ALLOWED, f"unexpected column: {col}"
            sets.append(f"{col}=%s")
            params.append(val)
        params.append(worker_id)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE edge_worker SET {', '.join(sets)} WHERE id=%s", params)
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def update_edge_worker_lineage(worker_id, lineage_id):
    """다운로드 인가(deploy_lineage_id)만 단독 갱신 — None 이면 인가 해제.

    update_edge_worker_status 와 분리한 이유: 그쪽은 conn_status 를 **항상** 덮어쓰고
    None 을 skip 으로 해석해 인가를 해제할 수단이 없다. 인가는 `/ops` 를 보내기 **전에**
    새겨야 하는데(에이전트가 202 직후 곧바로 내려받으러 온다), 그 시점에 연결상태까지
    건드리면 아직 관측하지 않은 값을 쓰는 것이 된다.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE edge_worker SET deploy_lineage_id=%s WHERE id=%s",
                        (lineage_id, worker_id))
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def update_edge_worker_playground(worker_id, playground_id):
    """이 워커가 마지막으로 성공 배포한 온디바이스 배포(playground) — None 이면 비운다.
    배포 목록 카드 상태·상세 선택 복원용 표시 정보다(아티팩트 인가와 무관)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE edge_worker SET deploy_playground_id=%s WHERE id=%s",
                        (playground_id, worker_id))
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def get_edge_playground(playground_id):
    """온디바이스 배포 행 단건(id, workspace_id, deploy_type) — 배포 요청의 playground_id 검증용.
    get_quantize_lineage 와 같은 크로스 스키마 읽기(소비자 쪽 db 모듈, 읽기 전용, 스키마명 리터럴)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, workspace_id, deploy_type FROM jonathan_llm.playground WHERE id=%s",
                (playground_id,),
            )
            return cur.fetchone()
    except Exception:
        traceback.print_exc()
        return None


def get_quantize_lineage(lineage_id):
    """SP-4 양자화 산출물(quantize_lineage) 단건 — 엣지 배포가 내려보낼 아티팩트.

    `jonathan_llm` 은 llm_model 도메인이지만 그쪽 db_model 은 async(aiomysql)라
    sync 인 엣지 경로에서 쓸 수 없다. 이 리포의 관례대로 **소비자 쪽 db 모듈이
    크로스 스키마 읽기를 든다**(db_workspace·db_dashboard 가 이미 jonathan_llm.model
    을 같은 방식으로 읽는다). 읽기 전용이며 스키마명은 하드코딩 리터럴이다.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, source_model_id, workspace_id, quantization_type, "
                "gguf_path, status FROM jonathan_llm.quantize_lineage WHERE id=%s",
                (lineage_id,),
            )
            return cur.fetchone()
    except Exception:
        traceback.print_exc()
        return None


def list_edge_workers_by_lineage(lineage_id):
    """이 lineage 를 다운로드 인가(deploy_lineage_id)로 들고 있는 워커들 — 양자화 이력 삭제 가드용.

    다른 조회와 달리 예외를 삼키지 않는다: 빈 목록이 "쓰는 워커 없음" 으로 읽혀 배포 중인
    아티팩트가 지워지면 안 된다(가드는 fail-closed). 인가는 stop 뒤에도 남으므로 상태는
    호출부가 deploy_state 로 거른다.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, device_id, deploy_state FROM edge_worker WHERE deploy_lineage_id=%s",
            (lineage_id,),
        )
        return cur.fetchall() or []


# ── custom_label (노드 + 엣지워커 공용, 키-값) ────────────────────────────────

def upsert_custom_label(target_type, target_id, label_key, label_value=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO custom_label (target_type, target_id, label_key, label_value)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE label_value=VALUES(label_value)
            """
            cur.execute(sql, (target_type, target_id, label_key, label_value))
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def get_custom_labels(target_type=None, target_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if target_type and target_id:
                cur.execute(
                    "SELECT * FROM custom_label WHERE target_type=%s AND target_id=%s ORDER BY id",
                    (target_type, target_id),
                )
            else:
                cur.execute("SELECT * FROM custom_label ORDER BY id")
            return cur.fetchall() or []
    except Exception:
        traceback.print_exc()
        return []


def delete_custom_label(label_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM custom_label WHERE id=%s", (label_id,))
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False


def delete_custom_labels_for(target_type, target_id):
    """대상(노드/엣지워커) 삭제 시 그 대상의 모든 커스텀 레이블 제거(orphan 방지)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM custom_label WHERE target_type=%s AND target_id=%s",
                (target_type, target_id),
            )
            conn.commit()
            return True
    except Exception:
        traceback.print_exc()
        return False
