-- 003_eval_project_model_fk_set_null.sql
--
-- Live DB migration: eval_project.model_id must not cascade-delete the project.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 003_eval_project_model_fk_set_null.sql
--
-- In-cluster (dev), the same file can be piped into the MariaDB pod:
--   kubectl exec -i -n tango-dev-mariadb <mariadb-pod> -- \
--     sh -c 'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" jonathan_llm' \
--     < apps/llm_evaluation/migrations/003_eval_project_model_fk_set_null.sql
--
-- Why: while a project locked one model (pre 2026-08-24), ON DELETE CASCADE was
-- correct — the project could only ever hold that model's runs, so deleting the
-- model made the project meaningless. After 002 released the lock, a project
-- accumulates eval_result rows for *several* models and model_id is only a
-- vestigial "first model" pointer. Under CASCADE, deleting that first model
-- silently destroys the whole project and every other model's evaluation
-- history with it (eval_result -> eval_expert_rating -> ..._history all cascade
-- from eval_project). SET NULL degrades the vestigial pointer instead, which is
-- exactly the state new projects already start in (create_eval_project passes
-- model_id = NULL). Found by the 2026-08-27 review.
--
-- Ordering: 002 must have run first — SET NULL is only valid on a nullable
-- column. If model_id is still NOT NULL this file leaves the FK untouched
-- rather than failing halfway.
--
-- Idempotent: keyed on the current DELETE_RULE, so re-applying after a
-- successful run is a no-op, and it is also a no-op when eval_project does not
-- exist yet (schema init / 001 creates it).

-- 이름을 조회해서 쓴다 — 제약 이름은 스키마 초기화 시점에 MariaDB 가 붙이므로
-- (dev 는 eval_project_ibfk_1) 설치마다 다를 수 있다. CASCADE 인 것만 잡는다.
SET @eval_project_fk := (
    SELECT rc.`CONSTRAINT_NAME`
    FROM information_schema.REFERENTIAL_CONSTRAINTS rc
    WHERE rc.`CONSTRAINT_SCHEMA` = DATABASE()
      AND rc.`TABLE_NAME` = 'eval_project'
      AND rc.`REFERENCED_TABLE_NAME` = 'model'
      AND rc.`DELETE_RULE` = 'CASCADE'
    LIMIT 1
);

SET @eval_project_model_nullable := (
    SELECT `IS_NULLABLE`
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_project'
      AND COLUMN_NAME = 'model_id'
);

-- 컬럼이 아직 NOT NULL 이면 건드리지 않는다(002 선행 필요). IF() 는 NULL 조건에서
-- else 로 떨어지므로 테이블·컬럼이 없어도 no-op 으로 착지한다.
SET @eval_project_fk_ok := IF(
    @eval_project_fk IS NOT NULL AND @eval_project_model_nullable = 'YES', 1, 0);

SET @eval_project_fk_drop := IF(
    @eval_project_fk_ok = 1,
    CONCAT('ALTER TABLE `eval_project` DROP FOREIGN KEY `', @eval_project_fk, '`'),
    'SELECT 0'
);
PREPARE eval_project_fk_drop_stmt FROM @eval_project_fk_drop;
EXECUTE eval_project_fk_drop_stmt;
DEALLOCATE PREPARE eval_project_fk_drop_stmt;

SET @eval_project_fk_add := IF(
    @eval_project_fk_ok = 1,
    CONCAT('ALTER TABLE `eval_project` ADD CONSTRAINT `', @eval_project_fk,
           '` FOREIGN KEY (`model_id`) REFERENCES `model` (`id`)',
           ' ON UPDATE CASCADE ON DELETE SET NULL'),
    'SELECT 0'
);
PREPARE eval_project_fk_add_stmt FROM @eval_project_fk_add;
EXECUTE eval_project_fk_add_stmt;
DEALLOCATE PREPARE eval_project_fk_add_stmt;
