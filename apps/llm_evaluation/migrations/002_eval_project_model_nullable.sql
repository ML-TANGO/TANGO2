-- 002_eval_project_model_nullable.sql
--
-- Live DB migration: the evaluation project no longer locks a model.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 002_eval_project_model_nullable.sql
--
-- In-cluster (dev), the same file can be piped into the MariaDB pod:
--   kubectl exec -i -n tango-dev-mariadb <mariadb-pod> -- \
--     sh -c 'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" jonathan_llm' \
--     < apps/llm_evaluation/migrations/002_eval_project_model_nullable.sql
--
-- What changes: a project used to be created against a locked model+dataset and
-- every run inherited them. Now a project only fixes eval_type and name, and the
-- model/dataset are chosen per run (eval_result already carries source_model_id /
-- dataset_id per run, so no new column is needed). Only the NOT NULL on
-- eval_project.model_id has to be released — the FK to `model` stays and keeps
-- working on a nullable column, so old projects with a locked model still resolve.
--
-- dataset_ids is already nullable, so nothing to do there.
--
-- Do not rerun devops/gaip_maraidb/mariadb-init for this change on a live
-- cluster: that init job rebuilds jonathan_llm.
--
-- Idempotent: the column change is guarded through information_schema, so the
-- file is safe to reapply after the first successful run (and is a no-op when
-- eval_project does not exist yet — 001 or the schema init creates it).

SET @eval_project_model_nullable := (
    SELECT `IS_NULLABLE`
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_project'
      AND COLUMN_NAME = 'model_id'
);

-- IF() on a NULL condition falls to the else branch, so a missing table/column
-- lands on the no-op statement instead of preparing NULL.
SET @eval_project_model_sql := IF(
    @eval_project_model_nullable = 'NO',
    'ALTER TABLE `eval_project` MODIFY COLUMN `model_id` INT(11) NULL',
    'SELECT 0'
);

PREPARE eval_project_model_stmt FROM @eval_project_model_sql;
EXECUTE eval_project_model_stmt;
DEALLOCATE PREPARE eval_project_model_stmt;
