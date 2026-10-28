-- 학습 데이터 파이프라인 — 노드 실행 이력.
--
-- 왜 필요한가: 노드 잡은 산출물을 작업 데이터셋에 **파일로만** 남긴다. 그래서
--   (1) 화면이 "지금 돌고 있는지 · 끝났는지 · 몇 건이 남았는지" 를 물어볼 데가 없고,
--   (2) 다음 노드가 상류 산출물을 찾으려면 파일시스템을 훑어야 했다.
-- 이 테이블이 그 둘을 대신한다. 실행 1건 = 노드 1개의 한 번 실행.
--
-- 적재 방식: 잡을 띄울 때 running 으로 넣고, 폴링 리콘사일러가 산출물(funnel.json)을
-- 보고 done 으로 마감한다. 산출물이 없는데 잡이 끝나 있으면 failed 로 닫는다
-- (preprocessing_job.name 이 job_name 과 같아 그쪽 상태를 되짚을 수 있다).
--
-- 적용:
--   mysql ... jonathan_llm < 002_llm_dp_run.sql

CREATE TABLE IF NOT EXISTS `llm_dp_run` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    -- r{YYYYMMDDHHMMSS}-{hex}. 실행마다 새로 발급돼 이전 산출물을 덮지 않는다.
    `run_id`            VARCHAR(32) NOT NULL,
    `node_index`        INT(11) NOT NULL,
    -- preprocess | filter | generate | gate | sds_video | sds_ais | sds_join
    `stage`             VARCHAR(24) NOT NULL,
    -- 스케줄러가 띄운 잡 이름. preprocessing_job.name 과 같은 값이라, 산출물이
    -- 없을 때 실패인지 아직 도는 중인지를 그쪽에서 확인하는 열쇠가 된다.
    `job_name`          VARCHAR(128),
    -- running | done | failed
    `status`            VARCHAR(16) NOT NULL DEFAULT 'running',
    -- 미리보기 실행은 표본만 돌린 결과라 다음 노드의 입력으로 쓰면 안 된다.
    `dry_run`           TINYINT NOT NULL DEFAULT 0,
    -- 작업 데이터셋 기준 상대경로(_runs/<run_id>/<node_index>).
    `out_dir`           VARCHAR(255) NOT NULL,
    `in_count`          INT(11),
    `out_count`         INT(11),
    `dropped_count`     INT(11),
    -- 노드가 남긴 funnel.json 전체. 단계별 in/out/dropped 가 들어 있어 화면이
    -- 노드 안에서 무엇이 얼마나 걸러졌는지를 그린다.
    `funnel`            JSON,
    `error_reason`      VARCHAR(1000),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    `end_datetime`      DATETIME,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_run` (`dataset_id`, `run_id`, `node_index`),
    -- 리콘사일러가 매 주기 running 만 훑는다.
    KEY `ix_dp_run_status` (`status`),
    -- 상류 탐색: 그 노드의 가장 최근 done 실행 1건.
    KEY `ix_dp_run_node` (`dataset_id`, `node_index`, `status`, `id`),
    CONSTRAINT `fk_dp_run_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
