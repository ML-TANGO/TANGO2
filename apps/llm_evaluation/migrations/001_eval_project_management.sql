-- 001_eval_project_management.sql
--
-- Live DB migration for the LLM evaluation project-management redesign.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 001_eval_project_management.sql
--
-- Do not rerun devops/gaip_maraidb/mariadb-init for this change on a live
-- cluster: that init job rebuilds jonathan_llm. This migration only adds the
-- new project table and additive columns required by the redesigned app.
--
-- MariaDB 10.0+ supports ADD COLUMN IF NOT EXISTS. The foreign-key addition is
-- guarded through information_schema so the file is safe to reapply after the
-- first successful run.

CREATE TABLE IF NOT EXISTS `eval_project` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`      INT(11) NOT NULL,
    `name`              VARCHAR(255) NOT NULL,
    `model_id`          INT(11) NOT NULL,
    `dataset_ids`       JSON,
    `eval_type`         VARCHAR(20) NOT NULL,
    `status`            VARCHAR(20) DEFAULT 'created',
    `creator`           VARCHAR(128),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT `fk_eval_project_model`
        FOREIGN KEY (`model_id`) REFERENCES `model` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE
);

ALTER TABLE `eval_result`
  ADD COLUMN IF NOT EXISTS `eval_project_id` INT(11) NULL
    AFTER `workspace_id`;

SET @eval_project_fk_exists := (
    SELECT COUNT(*)
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_result'
      AND COLUMN_NAME = 'eval_project_id'
      AND REFERENCED_TABLE_SCHEMA = DATABASE()
      AND REFERENCED_TABLE_NAME = 'eval_project'
      AND REFERENCED_COLUMN_NAME = 'id'
);

SET @eval_project_fk_sql := IF(
    @eval_project_fk_exists = 0,
    'ALTER TABLE `eval_result` ADD CONSTRAINT `fk_eval_result_project` FOREIGN KEY (`eval_project_id`) REFERENCES `eval_project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE',
    'SELECT 0'
);

PREPARE eval_project_fk_stmt FROM @eval_project_fk_sql;
EXECUTE eval_project_fk_stmt;
DEALLOCATE PREPARE eval_project_fk_stmt;

ALTER TABLE `eval_expert_rating`
  ADD COLUMN IF NOT EXISTS `score` TINYINT
    COMMENT 'Expert score from 1 to 5'
    AFTER `verdict`,
  ADD COLUMN IF NOT EXISTS `score_json` JSON
    COMMENT 'Structured future rating payload'
    AFTER `score`;

ALTER TABLE `eval_expert_rating_history`
  ADD COLUMN IF NOT EXISTS `score` TINYINT
    COMMENT 'Expert score from 1 to 5'
    AFTER `verdict`,
  ADD COLUMN IF NOT EXISTS `score_json` JSON
    COMMENT 'Structured future rating payload'
    AFTER `score`;
