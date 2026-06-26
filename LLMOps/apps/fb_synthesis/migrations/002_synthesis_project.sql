-- 002_synthesis_project.sql — 데이터 합성 프레임워크 단독 UI P1 (v0.4 3.3 / SP-7)
--
-- 라이브 DB(msa_jfb) 적용:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p msa_jfb < 002_synthesis_project.sql
--
-- 합성 프로젝트 = generate 외부 컨테이너(LLM2 데이터 생성) 단독 실행 단위.
-- P1: 단일 generate job 직접 호출(파이프라인 미경유). 3-모듈 체이닝·후보 큐레이션은 P2.
-- MariaDB 10.0+ CREATE TABLE IF NOT EXISTS 로 idempotent.

CREATE TABLE IF NOT EXISTS `synthesis_project` (
    `id`                  INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`        INT(11) NOT NULL,
    `name`                VARCHAR(255) NOT NULL,
    `field`               VARCHAR(50)  COMMENT 'SDS/SDF/SDM 등 분야',
    `description`         VARCHAR(500),
    `owner_id`            INT(11),
    `owner_name`          VARCHAR(100),
    `mode`                VARCHAR(20)  DEFAULT 'wizard' COMMENT 'wizard/canvas',
    `manifest_name`       VARCHAR(128) COMMENT 'generate 외부 컨테이너 manifest',
    `manifest_version`    VARCHAR(64),
    `params`              LONGTEXT     COMMENT 'JSON: meta_prompt/optimize_method/count/instruction',
    `gpu_count`           INT(11)      DEFAULT 0,
    `dataset_id`          INT(11)      COMMENT '입력 데이터셋',
    `output_subdir`       VARCHAR(255) COMMENT '생성 결과(result.jsonl) 하위 경로',
    `job_str_id`          VARCHAR(64)  COMMENT '현재 external generate job id',
    `status`              VARCHAR(50)  DEFAULT 'created' COMMENT 'created/running/completed/failed',
    `result_count`        INT(11)      DEFAULT 0,
    `create_datetime`     VARCHAR(50),
    `update_datetime`     VARCHAR(50),
    PRIMARY KEY(`id`)
);
