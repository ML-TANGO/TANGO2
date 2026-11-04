-- 004_eval_project_description.sql
--
-- Live DB migration: the evaluation project gets a user-written description.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 004_eval_project_description.sql
--
-- In-cluster (dev), the same file can be piped into the MariaDB pod:
--   kubectl exec -i -n tango-dev-mariadb <mariadb-pod> -- \
--     sh -c 'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" jonathan_llm' \
--     < apps/llm_evaluation/migrations/004_eval_project_description.sql
--
-- Why: 평가 프로젝트 목록 카드만 모델·배포 카드와 결이 달랐다. 모델·배포는 본문에
-- 설명을 싣고 상태는 메타행에 두는데, 평가는 설명 컬럼이 아예 없어 본문 슬롯에 상태
-- 텍스트를 넣었고 그 결과 카드 하단이 비었다. 컬럼을 만들어 그 자리를 되찾는다.
--
-- 길이는 배포(playground.description)와 같은 VARCHAR(5000) 로 맞췄다 — 카드 본문에
-- 들어가는 같은 성격의 값이고, 요청 dto(EvalProjectCreateBody.description)의
-- max_length 도 이 값에 맞춰 두어 DB 에서 조용히 잘리지 않게 한다.
-- NULL 허용 + 기본 NULL: 설명은 선택 입력이고 기존 행이 이미 있다(백필 없음 — 빈
-- 설명은 화면이 플레이스홀더로 세운다).
--
-- Do not rerun devops/gaip_maraidb/mariadb-init for this change on a live
-- cluster: that init job rebuilds jonathan_llm.
--
-- Idempotent: 컬럼 존재 여부를 information_schema 로 확인하고 없을 때만 ADD 하므로
-- 재적용이 no-op 이고, eval_project 가 아직 없을 때도 no-op 이다(001 또는 스키마
-- 초기화가 테이블을 만든다).

SET @eval_project_description_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_project'
      AND COLUMN_NAME = 'description'
);

-- 테이블이 없으면 COUNT(*) 가 0 이라 ADD 로 갈 수 있으므로 테이블 존재도 함께 본다.
SET @eval_project_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'eval_project'
);

-- 컬럼 순서는 정본 스키마와 같게 name 뒤에 둔다(SELECT * 사용처는 없지만, 두 DDL 을
-- 눈으로 대조할 때 순서가 어긋나 있으면 같은 컬럼인지 확인이 느려진다).
SET @eval_project_description_sql := IF(
    @eval_project_table_exists = 1 AND @eval_project_description_exists = 0,
    'ALTER TABLE `eval_project` ADD COLUMN `description` VARCHAR(5000) DEFAULT NULL AFTER `name`',
    'SELECT 0'
);

PREPARE eval_project_description_stmt FROM @eval_project_description_sql;
EXECUTE eval_project_description_stmt;
DEALLOCATE PREPARE eval_project_description_stmt;
