-- 002_prompt_optimization_error.sql
--
-- prompt_optimization 에 실패 원인 컬럼 추가.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 002_prompt_optimization_error.sql
--
-- 001 은 CREATE TABLE IF NOT EXISTS 라 **이미 만들어진 테이블에는 컬럼을 못 붙인다**.
-- 그래서 라이브 클러스터용 증분을 따로 둔다. 신규 설치 경로(mariadb-init 의
-- schema_llm.sql)에는 컬럼이 인라인으로 들어가 있으므로, 그 경로로 만든 DB 에
-- 이 파일을 또 돌려도 ADD COLUMN IF NOT EXISTS 가 흡수한다(MariaDB 확장 문법).
--
-- 왜 필요한가:
--   컨테이너는 실패를 top-level code/message 로 보내고, FewshotPromptAdapter._build_result
--   가 그걸 ExternalJobError 로 복원한다. 그런데 llm_playground 가 그 error 를 저장하지
--   않아 UI 에는 원인 없는 'failed' 만 남았다 — 어댑터를 만든 목적이 하류에서 사라진 셈.
--   여기 저장해 목록/상세에서 원인을 그대로 보여준다.

ALTER TABLE `prompt_optimization`
    ADD COLUMN IF NOT EXISTS `error_message` VARCHAR(500) DEFAULT NULL AFTER `is_active`;
