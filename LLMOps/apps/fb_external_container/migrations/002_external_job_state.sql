-- 002_external_job_state.sql — SP-Ext.3 BFF JobTracker persistence
--
-- Run after 001_initial.sql, as the application DB user:
--   mysql -h $DB_HOST -u $DB_USER -p $DB_NAME < 002_external_job_state.sql
--
-- Purpose: BFF (fb_external_container) restart 시 in-flight 한 partner
-- job 의 상태를 복원하기 위한 테이블. ``JobTracker`` 가 async job 을
-- INSERT 하고 terminal (completed / failed / cancelled) 도달 시 **status 만
-- 갱신해 tombstone 으로 남긴다** (DELETE 하지 않는다 — 재시작 후 조회가 404
-- 대신 터미널 상태를 답해야 호출자가 폴링을 멈춘다). ``startup_recovery()``
-- 는 non-terminal row 만 JobRecord 로 재구성해 polling task 를 재시작하고,
-- 보존기간(7일) 지난 tombstone 은 ``prune_terminal()`` 이 정리한다.
-- execution_mode=sync (infer 서빙) 은 persist 대상이 아니다 (lifecycle
-- ``_db_persist`` 참조) — 재시작 후 추적 상실은 호출자 측에서 흡수한다.
--
-- ``model_id`` 는 ``jonathan_llm.model.id`` 를 application-level 으로
-- reference 한다 (cross-schema FK 회피, 운영 안정성 우선).

CREATE TABLE IF NOT EXISTS external_job_state (
    job_id            VARCHAR(64)  NOT NULL,
    model_id          INT(11)      DEFAULT NULL,
    workspace_id      INT(11)      NOT NULL,
    manifest_name     VARCHAR(128) NOT NULL,
    manifest_version  VARCHAR(64)  NOT NULL,
    manifest_json     LONGTEXT     NOT NULL,
    namespace         VARCHAR(128) NOT NULL,
    pod_name          VARCHAR(128) NOT NULL,
    helm_release      VARCHAR(128) NOT NULL,
    service_url       VARCHAR(256) NOT NULL,
    timeout_seconds   INT(11)      NOT NULL,
    params_json       LONGTEXT     NOT NULL,
    partner_job_id    VARCHAR(128) DEFAULT NULL,
    status            VARCHAR(32)  NOT NULL DEFAULT 'pending',
    output_subdir     VARCHAR(256) DEFAULT NULL,
    effective_gpu     INT(11)      NOT NULL DEFAULT 0,
    started_at        DATETIME     NOT NULL,
    updated_at        DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id),
    INDEX idx_status (status),
    INDEX idx_workspace (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
