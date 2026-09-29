-- DB charset: utf8mb4 (4-byte UTF-8, 이모지 지원)
-- ALTER DATABASE `jonathan_llm` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `playground` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32),
    `workspace_id`          INT(11),
    `create_user_id`        INT(11),
    `access`                INT(11),
    `description`           VARCHAR(5000),
    `deploy_type`           VARCHAR(16) DEFAULT 'cluster',
    `create_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
    `deployment`            JSON,
    `model`                 JSON,
    `model_parameter`       JSON,
    `rag`                   JSON,
    `prompt`                JSON,
    `accelerator`           VARCHAR(32),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `playground_test` (
    `id`                        INT(11) NOT NULL AUTO_INCREMENT,
    `playground_id`             INT(11),
    `type`                      VARCHAR(32),
    `input`                     LONGTEXT,
    `output`                    VARCHAR(5000),
    `model`                     LONGTEXT,
    `rag`                       LONGTEXT,
    `prompt`                    LONGTEXT,
    `start_datetime`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    `end_datetime`              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `playground_bookmark` (
    `playground_id` INT(11),
    `user_id` INT(11),
    CONSTRAINT FOREIGN KEY (`playground_id`) REFERENCES `jonathan_llm`.`playground` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `model` (
    `id`                        INT(11) NOT NULL AUTO_INCREMENT,
    `name`                      VARCHAR(32) NOT NULL,
    `description`               LONGTEXT,
    `workspace_id`              INT(11) NOT NULL,
    `create_user_id`            INT(11),
    `access`                    INT(11) DEFAULT 1,
    `instance_id`               INT(11),
    `instance_count`            INT(11) DEFAULT 0,
    `gpu_count`                 INT(11) DEFAULT 0,
    `pod_count`                 INT(11) DEFAULT 1,
    `latest_fine_tuning_config` JSON,
    `latest_fine_tuning_status` VARCHAR(20) DEFAULT "stop",
    `latest_commit_id`          INT(11),
    `steps_per_epoch`           INT(11) DEFAULT 0,
    `commit_status`             VARCHAR(20),
    `commit_type`               VARCHAR(20),
    `huggingface_model_id`      LONGTEXT,
    `huggingface_token`         LONGTEXT,
    `huggingface_git`           LONGTEXT not Null,
    `start_datetime`            DATETIME,
    `end_datetime`              DATETIME,
    `commit_model_name`         LONGTEXT,
    `domain`                    VARCHAR(16) DEFAULT NULL,
    `load_type`                 VARCHAR(32) DEFAULT NULL,
    `create_datetime`           DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_datetime`           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`instance_id`) REFERENCES `msa_jfb`.`instance` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `user_model` (
    `model_id`          INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    PRIMARY KEY(`model_id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- SP-4 양자화·포팅 lineage (v0.4 3.9). model 테이블을 건드리지 않고 양자화 이력을
-- 별도 추적: 원본 모델 1개에 대해 재양자화 시도마다 1 row (history 보존).
CREATE TABLE IF NOT EXISTS `quantize_lineage` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `source_model_id`   INT(11) NOT NULL,
    `workspace_id`      INT(11) NOT NULL,
    `job_str_id`        VARCHAR(128) NOT NULL,
    `quantization_type` VARCHAR(16) NOT NULL,
    `target_device`     VARCHAR(64),
    `prune`             TINYINT(1) DEFAULT 0,
    `gguf_path`         VARCHAR(512),
    `status`            VARCHAR(20) DEFAULT 'running',
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    UNIQUE KEY `uq_quantize_job` (`job_str_id`),
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 평가 프로젝트 관리 (2026-07-07). 관리 단위 = 프로젝트(유형·이름).
-- 1:N 으로 eval_result(run)를 묶는다(eval_result.eval_project_id FK). model 뒤·eval_result
-- 앞에 정의(인라인 FK 순서: model → eval_project → eval_result). 삭제 캐스케이드:
-- project → result → expert rating/history 전 체인.
-- 2026-08-24: 모델·데이터셋 잠금 해제 — 무엇을 평가하는지는 **런**이 고른다
-- (eval_result.source_model_id/dataset_id 가 런 단위 정본). 그래서 workspace_id 는
-- 더 이상 모델에서 파생되지 않고 생성 요청이 직접 준다. model_id/dataset_ids 는
-- 잠금이 박혀 있던 옛 프로젝트의 값을 보존하려고 남긴 컬럼이며 신규 생성은 NULL 이다.
-- 2026-08-27: eval_type 3분할 — 'reference'(정답 대조) | 'judge'(LLM 심사) | 'expert'
--   (전문가). 구 'benchmark' 안에 채점 주체가 다른 둘(정답이 데이터에 있는 결정론적 채점
--   과 심판 LLM 채점)이 섞여 있어 결과 화면에서 구분이 불가능했다. 정본은 llm_evaluation
--   constants.EVAL_TYPES 이고, 컬럼은 VARCHAR(20) 그대로라 스키마 변경이 없다.
--   ⚠️ 데이터 마이그레이션은 만들지 않았다 — 기존 런/프로젝트는 전부 지우고 새로 뽑는다.
--   ⚠️ model_id 의 FK 는 **ON DELETE SET NULL** 이다(2026-08-27 리뷰 HIGH). 잠금이
--   박혀 있던 시절에는 프로젝트=한 모델이라 CASCADE 가 맞았지만, 이제 한 프로젝트에
--   여러 모델의 런이 쌓인다 — CASCADE 로 두면 원래 모델을 지울 때 다른 모델의 런까지
--   프로젝트째 사라진다. 신규 프로젝트는 어차피 NULL 로 시작하므로 SET NULL 이 그
--   상태로 수렴하는 것이고, 라이브 DB 는 migrations/003 이 같은 규칙으로 바꾼다.
-- 2026-08-27: description 신설 — 목록 카드가 모델·배포 카드와 같은 결이 되도록
--   본문 슬롯에 넣을 설명을 갖는다(없으면 화면이 플레이스홀더). 길이는 배포
--   (playground.description)와 같은 VARCHAR(5000) 로 맞췄고, 선택 입력 + 기존 행이
--   있으므로 NULL 허용/기본 NULL. 라이브 DB 는 migrations/004 로 적용.
CREATE TABLE IF NOT EXISTS `eval_project` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`      INT(11) NOT NULL,
    `name`              VARCHAR(255) NOT NULL,
    `description`       VARCHAR(5000) DEFAULT NULL,
    `model_id`          INT(11),
    `dataset_ids`       JSON,
    `eval_type`         VARCHAR(20) NOT NULL,
    `status`            VARCHAR(20) DEFAULT 'created',
    `creator`           VARCHAR(128),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

-- SP-5 자동평가 결과 (v0.4 3.8). model 테이블을 건드리지 않고 평가 이력을
-- 별도 추적: 모델 1개를 여러 데이터셋/메트릭으로 평가하면 시도마다 1 row.
-- 비교표·best 배지는 source_model_id 로 묶어 조회. metrics 는 자유 JSON
-- (BLEU/ROUGE/perplexity + SDM 도메인 키 AUC/Dice 등 그대로 수용).
-- 2026-07-07: eval_project_id 추가(프로젝트 1:N run 링크, 레거시 런은 NULL).
CREATE TABLE IF NOT EXISTS `eval_result` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `source_model_id`   INT(11) NOT NULL,
    `workspace_id`      INT(11) NOT NULL,
    `eval_project_id`   INT(11),
    `job_str_id`        VARCHAR(128) NOT NULL,
    `dataset_id`        INT(11),
    `dataset_name`      VARCHAR(255),
    `metric_set`        VARCHAR(255),
    `metrics`           JSON,
    `status`            VARCHAR(20) DEFAULT 'running',
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    UNIQUE KEY `uq_eval_job` (`job_str_id`),
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`eval_project_id`) REFERENCES `jonathan_llm`.`eval_project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ⚠️ 라이브 DB 수동 적용(llm_db 마이그레이션 러너 없음 — quantize_lineage 와 동일 절차).
-- fresh-install 은 위 CREATE 로 반영되지만 기존 DB 에는 아래를 수동 실행(DO NOT auto-run):
--   (1) CREATE TABLE IF NOT EXISTS `eval_project` ( ... 위 정의와 동일 ... );
--   (2) ALTER TABLE `eval_result`
--         ADD COLUMN `eval_project_id` INT(11) NULL AFTER `workspace_id`,
--         ADD CONSTRAINT `fk_eval_result_project` FOREIGN KEY (`eval_project_id`)
--           REFERENCES `eval_project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE;

-- P3 전문가 평가(sample-level 인간 채점). 세션 = eval_result row(job_str_id, metric_set='expert').
-- (job_str_id, sample_idx) 유니크 → 재채점 upsert. 합격률은 집계 후 eval_result.metrics 로.
CREATE TABLE IF NOT EXISTS `eval_expert_rating` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `source_model_id`   INT(11) NOT NULL,
    `job_str_id`        VARCHAR(128) NOT NULL,
    `sample_idx`        INT(11) NOT NULL,
    `input`             TEXT,
    `output`            TEXT,
    `reference`         TEXT,
    `rater_user`        VARCHAR(128),
    `verdict`           VARCHAR(8) NOT NULL,
    `comment`           TEXT,
    `score`             TINYINT,      -- 전문가 별점 1~5 (D2). 신규 기본. `verdict` 는 이 값에서 파생.
    `score_json`        JSON,         -- 확장 지점(다기준/구조화 피드백·플라이휠, 무스키마 확장)
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    UNIQUE KEY `uq_expert_sample` (`job_str_id`, `sample_idx`),
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`job_str_id`) REFERENCES `jonathan_llm`.`eval_result` (`job_str_id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- P3 전문가 평가 채점 이력(append-only, 감사추적). 메인 eval_expert_rating 은
-- (job_str_id, sample_idx) upsert 라 '현재' verdict 만 유지 → 재채점 시 누가 언제 무엇을
-- 바꿨는지 소실. 이 테이블에 채점 이벤트마다 1 row 누적(불변 이력).
CREATE TABLE IF NOT EXISTS `eval_expert_rating_history` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `source_model_id`   INT(11) NOT NULL,
    `job_str_id`        VARCHAR(128) NOT NULL,
    `sample_idx`        INT(11) NOT NULL,
    `rater_user`        VARCHAR(128),
    `verdict`           VARCHAR(8) NOT NULL,
    `comment`           TEXT,
    `score`             TINYINT,      -- 전문가 별점 1~5 (D2). `verdict` 는 파생.
    `score_json`        JSON,         -- 확장 지점(무스키마 확장)
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    KEY `idx_expert_hist` (`job_str_id`, `sample_idx`),
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`job_str_id`) REFERENCES `jonathan_llm`.`eval_result` (`job_str_id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 벤치마크 실행(묶음) — "한 번의 실행 = 결과 카드 1장" 의 단위(2026-09-29). 벤치마크마다 런(eval_result)
-- 이 하나씩이고, 함께 실행한 런들을 이 행이 묶는다. 멤버는 매핑 테이블로 두어 런을 지우면
-- FK CASCADE 로 멤버십도 함께 사라진다(멤버가 0 이 된 묶음은 목록에서 빠진다).
-- 체크포인트·문항 상한은 묶음 전체에 한 값이다(run_benchmark_batch 가 체크포인트를 한 번만 푼다).
-- ⚠️ 라이브 DB 는 수동 적용(llm_db 마이그레이션 러너 없음) — 아래 두 CREATE 를 그대로 실행한다.
CREATE TABLE IF NOT EXISTS `eval_run_batch` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `eval_project_id`   INT(11) NOT NULL,
    `workspace_id`      INT(11) NOT NULL,
    `source_model_id`   INT(11) NOT NULL,
    `checkpoint`        VARCHAR(255),
    `sample_limit`      INT(11),
    `launch_failures`   JSON,          -- 런치에 실패한 벤치마크 [{benchmark, error}] — 요청한 전부가 카드에 보이게
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    KEY `idx_run_batch_project` (`eval_project_id`),
    CONSTRAINT FOREIGN KEY (`eval_project_id`) REFERENCES `jonathan_llm`.`eval_project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`source_model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `eval_run_batch_member` (
    `batch_id`          INT(11) NOT NULL,
    `job_str_id`        VARCHAR(128) NOT NULL,
    `position`          INT(11) NOT NULL DEFAULT 0,   -- 고른 순서(결과 화면의 벤치마크 순서)
    `benchmarks`        JSON,                         -- 이 런이 담은 벤치마크 id 목록(한 런 = 여러 벤치마크, metric_set 은 255자에서 잘린다)
    PRIMARY KEY(`batch_id`, `job_str_id`),
    UNIQUE KEY `uq_run_batch_member_job` (`job_str_id`),
    CONSTRAINT FOREIGN KEY (`batch_id`) REFERENCES `jonathan_llm`.`eval_run_batch` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`job_str_id`) REFERENCES `jonathan_llm`.`eval_result` (`job_str_id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `commit_model` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  LONGTEXT,
    `model_id`              INT(11),
    `create_user_id`        INT(11),
    `steps_per_epoch`           INT(11) DEFAULT 0,
    `workspace_id`          INT(11) NOT NULL,
    `fine_tuning_config`    JSON,
    `commit_message`        LONGTEXT,
    `model_description`     LONGTEXT,
    `commit_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `model_bookmark` (
    `model_id`              INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    UNIQUE KEY(`model_id`, `user_id` ),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `fine_tuning_dataset` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`            INT(11) NOT NULL,
    `model_id`              INT(11),
    `training_data_path`    LONGTEXT,
    `commit_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `fine_tuning_config_file` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `file_name`             LONGTEXT,
    `model_id`              INT(11),
    `size`                  BIGINT(20) DEFAULT 0,
    `commit_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `prompt` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32),
    `description`           LONGTEXT,
    `workspace_id`          INT(11) NOT NULL,
    `create_user_id`        INT(11),
    `create_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `latest_commit_id`      INT(11),
    `access`                INT(11),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `prompt_bookmark` (
    `prompt_id` INT(11),
    `user_id` INT(11),
    CONSTRAINT FOREIGN KEY (`prompt_id`) REFERENCES `jonathan_llm`.`prompt` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `commit_prompt` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32),
    `prompt_id`             INT(11) NOT NULL,
    `prompt_description`    VARCHAR(5000),
    `create_user_id`        INT(11),
    `create_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    `system_message`        LONGTEXT,
    `user_message`          LONGTEXT,
    `commit_message`        LONGTEXT,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`prompt_id`) REFERENCES `jonathan_llm`.`prompt` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS `rag` (
    `id`                                INT(11) NOT NULL AUTO_INCREMENT,
    `name`                              VARCHAR(32),
    `description`                       LONGTEXT,
    `workspace_id`                      INT(11) NOT NULL,
    `chunk_len`                         INT(11),
    `embedding_huggingface_model_id`    VARCHAR(1000) UNIQUE,
    `embedding_huggingface_model_token` VARCHAR(1000) UNIQUE,
    `reranker_huggingface_model_id`     VARCHAR(1000) UNIQUE,
    `reranker_huggingface_model_token`  VARCHAR(1000) UNIQUE,
    `test_embedding_deployment_id`      INT(11),
    `test_reranker_deployment_id`       INT(11),
    `retrieval_embedding_deployment_id` INT(11),
    `retrieval_reranker_deployment_id`  INT(11),
    `test_embedding_run`                TINYINT(1) DEFAULT 0,
    `test_reranker_run`                 TINYINT(1) DEFAULT 0,
    `retrieval_embedding_run`           TINYINT(1) DEFAULT 0,
    `retrieval_reranker_run`            TINYINT(1) DEFAULT 0,
    `create_user_id`                    INT(11),
    `access`                            INT(11),
    `create_datetime`                   DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_datetime`                   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `rag_result`                        LONGTEXT,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `rag_docs` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `rag_id`                INT(11) NOT NULL,
    `name`                  VARCHAR(500),
    `size`                  FLOAT(11) DEFAULT 0,
    `status`                INT(11) DEFAULT 0,
    `progress`               INT(11) DEFAULT 0,
    `create_user_id`        INT(11),
    `create_datetime`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`rag_id`) REFERENCES `jonathan_llm`.`rag` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `rag_bookmark` (
    `rag_id`                INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    CONSTRAINT FOREIGN KEY (`rag_id`) REFERENCES `jonathan_llm`.`rag` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);



CREATE TABLE IF NOT EXISTS `user_playground` (
    `playground_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`playground_id`),
    CONSTRAINT FOREIGN KEY (`playground_id`) REFERENCES `jonathan_llm`.`playground` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- (중복 정의 제거) `user_model` 은 위(모델 테이블 블록)에서 이미 정의됨.
-- CREATE TABLE IF NOT EXISTS 라 두 번째 정의는 dead 였고 PK 컬럼 순서만 달라 혼란 유발.

CREATE TABLE IF NOT EXISTS `user_rag` (
    `rag_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`rag_id`),
    CONSTRAINT FOREIGN KEY (`rag_id`) REFERENCES `jonathan_llm`.`rag` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `user_prompt` (
    `prompt_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`prompt_id`),
    CONSTRAINT FOREIGN KEY (`prompt_id`) REFERENCES `jonathan_llm`.`prompt` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 프롬프트 최적화(fewshot-prompt-optimizer) 결과 영속.
-- 컨테이너는 완료 job 을 JOB_TTL_SECONDS(기본 1h) 후 폐기하고, 플랫폼 external_container
-- job tracker 도 terminal 시 helm release 를 teardown 한다 — 결과를 붙잡아 둘 곳이
-- 여기밖에 없다. status 가 completed 로 전이하는 순간 저장한다.
-- 소비 코드: apps/fb_utils/llm_db/db_prompt_optimization.py
CREATE TABLE IF NOT EXISTS `prompt_optimization` (
    `id`              INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`    INT(11) NOT NULL,
    -- 최적화 대상 배포(playground). 삭제되면 이력도 함께 정리한다.
    `playground_id`   INT(11) NOT NULL,
    -- 실행 시점 스냅샷(재현·표시용) — playground.model JSON 에서 파생.
    `model_id`        INT(11) DEFAULT NULL,
    `commit_id`       INT(11) DEFAULT NULL,
    -- external_container 가 발급한 플랫폼 job id.
    `job_id`          VARCHAR(64) DEFAULT NULL,
    `status`          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|running|completed|failed
    `metric`          VARCHAR(32) DEFAULT NULL,   -- 컨테이너가 실제로 사용한 metric
    `model`           VARCHAR(255) DEFAULT NULL,  -- 컨테이너가 감지한 model id
    -- ★ 핵심 산출물. 추론 주입에 쓰이는 텍스트.
    `system_prompt`   TEXT,
    `instruction`     TEXT,
    `demos`           JSON,
    `base_score`      DOUBLE DEFAULT NULL,
    `final_score`     DOUBLE DEFAULT NULL,
    -- 입력 예시(재현용).
    `examples`        JSON,
    -- 추론에 주입될 1건. playground 당 최대 1건 — 단일 활성 불변식은 애플리케이션에서
    --   강제한다(활성 전환 시 같은 playground 의 기존 활성을 해제). MariaDB 에는
    --   "0 은 중복 허용, 1 은 유일" 을 그대로 표현하는 부분 UNIQUE 가 없다.
    `is_active`       TINYINT(1) NOT NULL DEFAULT 0,
    -- 실패 원인. 어댑터가 컨테이너의 top-level code/message 를 복원해 주는데 저장하지
    --   않으면 UI 에 원인 없는 'failed' 만 남는다(진단 불가).
    `error_message`   VARCHAR(500) DEFAULT NULL,
    `create_datetime` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `finish_datetime` DATETIME DEFAULT NULL,
    PRIMARY KEY(`id`),
    KEY `idx_prompt_opt_playground` (`playground_id`, `is_active`),
    KEY `idx_prompt_opt_workspace` (`workspace_id`),
    KEY `idx_prompt_opt_job` (`job_id`),
    CONSTRAINT `fk_prompt_opt_playground`
        FOREIGN KEY (`playground_id`) REFERENCES `jonathan_llm`.`playground` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE
);

