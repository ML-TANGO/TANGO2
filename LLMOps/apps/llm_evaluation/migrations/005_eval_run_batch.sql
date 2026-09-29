-- 005_eval_run_batch.sql
--
-- Live DB migration: benchmark executions (batches) — "one execution = one result card".
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 005_eval_run_batch.sql
--
-- In-cluster (dev), the same file can be piped into the MariaDB pod:
--   kubectl exec -i -n tango-dev-mariadb <mariadb-pod> -- \
--     sh -c 'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" jonathan_llm' \
--     < apps/llm_evaluation/migrations/005_eval_run_batch.sql
--
-- Why: 정답 대조(lm-eval) 실행 한 번이 여러 런(eval_result)을 띄운다 — 고른 GPU 수만큼 런을 나누고
-- 런마다 벤치마크를 여러 개 담는다(설계 LLMOps/docs/2026-09-28-lmeval-benchmark-scorer-design.md
-- §13·§14). eval_run_batch 가 그 실행 한 번을, eval_run_batch_member 가 실행 ↔ 런(+ 런이 담은
-- 벤치마크 목록)을 잇는다. 런이 담은 벤치마크를 여기 두는 이유: eval_result.metric_set 은
-- VARCHAR(255)라 17개를 담으면 272자로 잘려 목록의 정본이 못 된다.
-- 테이블이 없는 DB 에서도 화면은 뜬다(llm_evaluation _project_batches 가 조회 실패를 [] 로 받는다 —
-- 그때는 런마다 카드 한 장). 적용하면 그 뒤에 띄운 실행부터 카드 한 장으로 묶인다(백필 없음).
--
-- Do not rerun devops/gaip_maraidb/mariadb-init for this change on a live
-- cluster: that init job rebuilds jonathan_llm.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS + 컬럼 존재를 information_schema 로 확인하고 없을 때만
-- ADD 한다. 초안 테이블(두 컬럼 이전)을 이미 만든 DB(dev)도 이 파일 하나로 정본과 같아진다.
-- 정본 DDL = apps/fb_utils/llm_db/schema.sql (mariadb-init schema_llm.sql 과 같다).

CREATE TABLE IF NOT EXISTS `eval_run_batch` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `eval_project_id`   INT(11) NOT NULL,
    `workspace_id`      INT(11) NOT NULL,
    `source_model_id`   INT(11) NOT NULL,
    `checkpoint`        VARCHAR(255),
    `sample_limit`      INT(11),
    `launch_failures`   JSON,
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    KEY `idx_run_batch_project` (`eval_project_id`),
    CONSTRAINT FOREIGN KEY (`eval_project_id`) REFERENCES `jonathan_llm`.`eval_project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `eval_run_batch_member` (
    `batch_id`          INT(11) NOT NULL,
    `job_str_id`        VARCHAR(128) NOT NULL,
    `position`          INT(11) NOT NULL DEFAULT 0,
    `benchmarks`        JSON,
    PRIMARY KEY(`batch_id`, `job_str_id`),
    UNIQUE KEY `uq_run_batch_member_job` (`job_str_id`),
    CONSTRAINT FOREIGN KEY (`batch_id`) REFERENCES `jonathan_llm`.`eval_run_batch` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`job_str_id`) REFERENCES `jonathan_llm`.`eval_result` (`job_str_id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 초안 테이블 보정 ① eval_run_batch.launch_failures (런치에 실패한 벤치마크 [{benchmark, error}])
SET @run_batch_failures_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_run_batch'
      AND COLUMN_NAME = 'launch_failures'
);
SET @run_batch_failures_sql := IF(
    @run_batch_failures_exists = 0,
    'ALTER TABLE `eval_run_batch` ADD COLUMN `launch_failures` JSON AFTER `sample_limit`',
    'SELECT 0'
);
PREPARE run_batch_failures_stmt FROM @run_batch_failures_sql;
EXECUTE run_batch_failures_stmt;
DEALLOCATE PREPARE run_batch_failures_stmt;

-- 초안 테이블 보정 ② eval_run_batch_member.benchmarks (런이 담은 벤치마크 id 목록)
SET @run_batch_member_benchmarks_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_run_batch_member'
      AND COLUMN_NAME = 'benchmarks'
);
SET @run_batch_member_benchmarks_sql := IF(
    @run_batch_member_benchmarks_exists = 0,
    'ALTER TABLE `eval_run_batch_member` ADD COLUMN `benchmarks` JSON AFTER `position`',
    'SELECT 0'
);
PREPARE run_batch_member_benchmarks_stmt FROM @run_batch_member_benchmarks_sql;
EXECUTE run_batch_member_benchmarks_stmt;
DEALLOCATE PREPARE run_batch_member_benchmarks_stmt;
