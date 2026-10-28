-- 001_generation_node.sql — WBS 1.1 생성형 데이터 파이프라인 노드 (v0.4 3.3)
--
-- 라이브 DB(msa_jfb) 에 적용. schema.sql 변경은 신규 설치에만 반영되므로,
-- 기존 배포 클러스터에는 이 ALTER 를 수동 1회 실행해야 generation 노드가 동작한다.
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p msa_jfb < 001_generation_node.sql
--
-- 대상: apps/fb_pipeline/helm/pipe/code/db.py 의 update_pipeline_task_str /
-- update_pipeline_task_reset 가 참조하는 신규 컬럼. 미적용 시 generation 태스크
-- 실행이 "Unknown column 'task_item_job_str_id'" 로 즉시 실패한다.
--
-- external container job id 는 문자열(uuid 계열) — 기존 task_item_job_id INT(11)
-- 에 못 담으므로 별도 VARCHAR 컬럼 사용.
--
-- MariaDB 10.0+ 의 IF NOT EXISTS 로 idempotent (재실행 안전).

ALTER TABLE `pipeline_task`
  ADD COLUMN IF NOT EXISTS `task_item_job_str_id` VARCHAR(64)
    COMMENT 'external container job id (str/uuid) — generation 노드용'
    AFTER `task_item_job_id`;
