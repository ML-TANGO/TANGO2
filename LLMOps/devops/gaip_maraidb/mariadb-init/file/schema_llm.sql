CREATE DATABASE IF NOT EXISTS `jonathan_llm`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE `jonathan_llm`;

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
    -- 아래 4개는 운영 DB 에 라이브 ALTER 로만 적용돼 있고 이 파일에 역반영이 안 돼 있었다
    -- (이 플랫폼엔 마이그레이션 러너가 없다). 신규 설치 시 db_model.get_model/get_models 가
    -- "Unknown column 'm.training_type'" 로 실패한다.
    `training_type`             VARCHAR(16) NOT NULL DEFAULT 'internal',
    `external_manifest_name`    VARCHAR(128) DEFAULT NULL,
    `external_manifest_version` VARCHAR(32) DEFAULT NULL,
    `external_job_id`           VARCHAR(128) DEFAULT NULL,
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

CREATE TABLE IF NOT EXISTS `user_model` (
    `model_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`model_id`),
    CONSTRAINT FOREIGN KEY (`model_id`) REFERENCES `jonathan_llm`.`model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

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

-- SP-4 양자화·포팅 lineage (v0.4 3.9). apps/fb_utils/llm_db/schema.sql 미러
-- (fresh-install 정합 — 라이브 DB 에는 수동 적용됨).
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

-- 평가 프로젝트 관리 (2026-07-07). apps/fb_utils/llm_db/schema.sql 미러
-- (라이브 DB 에는 수동 적용됨). 관리 단위 = 프로젝트(유형·이름),
-- 1:N 으로 eval_result(run)를 묶는다.
-- 2026-08-24: 모델·데이터셋 잠금 해제 — 런이 고른다(model_id 는 옛 프로젝트 보존용 NULL 허용).
--   라이브 DB 는 apps/llm_evaluation/migrations/002_eval_project_model_nullable.sql 로 적용.
-- 2026-08-27: eval_type 3분할 — 'reference'(정답 대조) | 'judge'(LLM 심사) | 'expert'
--   (전문가). 구 'benchmark' 를 채점 주체 기준으로 쪼갠 것이며 컬럼 타입은 그대로다.
--   ⚠️ 데이터 마이그레이션 없음 — 기존 런/프로젝트는 전부 지우고 새로 뽑는다.
--   ⚠️ model_id 의 FK 는 **ON DELETE SET NULL** 이다(2026-08-27 리뷰 HIGH). 잠금이
--   박혀 있던 시절에는 프로젝트=한 모델이라 CASCADE 가 맞았지만, 이제 한 프로젝트에
--   여러 모델의 런이 쌓인다 — CASCADE 로 두면 원래 모델을 지울 때 다른 모델의 런까지
--   프로젝트째 사라진다. 신규 프로젝트는 어차피 NULL 로 시작하므로 SET NULL 이 그
--   상태로 수렴하는 것이고, 라이브 DB 는 migrations/003 이 같은 규칙으로 바꾼다.
-- 2026-08-27: description 신설(목록 카드 본문). 배포(playground.description)와 같은
--   VARCHAR(5000), 선택 입력이라 NULL 허용. 라이브 DB 는 migrations/004 로 적용.
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

-- SP-5 자동평가 결과 (v0.4 3.8). apps/fb_utils/llm_db/schema.sql 미러.
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

-- P3 전문가 평가(sample-level 인간 채점). 세션 = eval_result row(metric_set='expert').
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

-- 프롬프트 최적화(fewshot-prompt-optimizer) 결과 영속.
-- apps/fb_utils/llm_db/schema.sql 미러 (fresh-install 정합 — 라이브 DB 에는
-- apps/llm_playground/migrations/001_prompt_optimization.sql 로 수동 적용됨).
-- playground FK 라 위 playground 정의 뒤에 와야 한다.
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
    --   강제한다(활성 전환 시 같은 playground 의 기존 활성을 해제).
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


-- ================================================================
-- llm_data_pipeline — 학습 데이터 파이프라인 (apps/llm_data_pipeline/migrations/001 과 동일)
-- ================================================================

-- 데이터셋 — 파이프라인 하나가 곧 데이터셋 하나다.
CREATE TABLE IF NOT EXISTS `llm_dp_dataset` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`      INT(11) NOT NULL,
    `name`              VARCHAR(128) NOT NULL,
    `description`       VARCHAR(1000),
    -- draft: 만들었지만 데이터 없음 / running: 파이프라인 도는 중
    -- active: 릴리스된 버전 있음 / archived: 더 쓰지 않음
    `state`             VARCHAR(16) NOT NULL DEFAULT 'draft',
    -- generic(편집 가능) | sds_colreg(구성 고정)
    `preset`            VARCHAR(32) NOT NULL DEFAULT 'generic',
    `create_user`       VARCHAR(64),
    -- 노드 간 연결(엣지). 노드 행이 아니라 그래프에 속하는 정보라 여기에 둔다.
    -- [[출발 index, 도착 index], ...] · 비어 있으면 선형(0→1→2…)으로 본다.
    `flow`              JSON,
    -- 이 파이프라인이 소유한 작업 데이터셋(플랫폼 dataset). 노드 산출물(_runs/_preview)과
    -- 릴리스가 여기 쌓인다. 소스 데이터셋은 RO 로만 읽고 절대 쓰지 않는다 — 원본 오염과
    -- "남이 소스를 지우면 산출물도 같이 사라지는" 문제를 동시에 피한다.
    `work_dataset_id`   INT(11),
    `work_dataset_name` VARCHAR(128),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_dataset_ws_name` (`workspace_id`, `name`),
    KEY `ix_dp_dataset_ws` (`workspace_id`),
    CONSTRAINT `fk_dp_dataset_ws` FOREIGN KEY (`workspace_id`)
        REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 원본 데이터(이미지 · PDF · 문서 등). 실패한 것도 남긴다 — 왜 실패했는지가 정보다.
CREATE TABLE IF NOT EXISTS `llm_dp_asset` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    `name`              VARCHAR(255) NOT NULL,
    `path`              VARCHAR(1024),
    `kind`              VARCHAR(32),
    `size_bytes`        BIGINT,
    -- registered | duplicate | failed
    `status`            VARCHAR(16) NOT NULL DEFAULT 'registered',
    `fail_reason`       VARCHAR(255),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    KEY `ix_dp_asset_dataset` (`dataset_id`),
    KEY `ix_dp_asset_status` (`dataset_id`, `status`),
    CONSTRAINT `fk_dp_asset_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 파이프라인 노드. node_index 가 순서이며, 저장은 항상 전체 교체다
-- (한 노드만 고치면 나머지 인덱스가 어긋나므로).
CREATE TABLE IF NOT EXISTS `llm_dp_node` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    `preset`            VARCHAR(32) NOT NULL DEFAULT 'generic',
    `node_index`        INT(11) NOT NULL,
    -- data|prep|filter|synth|gate|src|join|calc|gen|out
    `kind`              VARCHAR(16) NOT NULL,
    `name`              VARCHAR(64) NOT NULL,
    -- [[기능명, 파라미터표시값], ...]
    `steps`             JSON,
    `config`            JSON,
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_node_order` (`dataset_id`, `node_index`),
    CONSTRAINT `fk_dp_node_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 생성된 학습 레코드(질문 · 답 + 심사 점수).
CREATE TABLE IF NOT EXISTS `llm_dp_record` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    -- 사람이 읽고 공유하는 키. 예: vdf-0009855
    `record_key`        VARCHAR(64) NOT NULL,
    `capability`        VARCHAR(32),
    `split`             VARCHAR(16),
    `question`          TEXT,
    `answer`            TEXT,
    -- {"align":0.61,"imgdep":0.88,"answer":0.44,"unique":0.71}
    `scores`            JSON,
    `judge_comment`     VARCHAR(2000),
    `taxonomy`          VARCHAR(32),
    -- pending | approved | edited | rejected
    `review_state`      VARCHAR(16) NOT NULL DEFAULT 'pending',
    `asset_ref`         VARCHAR(255),
    -- 계보: 생성 모델 · 프롬프트 · 심사 모델 · 원본 데이터
    `lineage`           JSON,
    -- 4축 중 가장 낮은 점수. scores JSON 에서 매번 뽑으면 정렬이 인덱스를 못 타므로
    -- 기록 시점에 계산해 둔다(레코드의 실질 품질 = 최저 축).
    `worst_score`       DECIMAL(4,3),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_record_key` (`dataset_id`, `record_key`),
    KEY `ix_dp_record_review` (`dataset_id`, `review_state`),
    KEY `ix_dp_record_cap` (`dataset_id`, `capability`),
    KEY `ix_dp_record_tax` (`dataset_id`, `taxonomy`),
    KEY `ix_dp_record_worst` (`dataset_id`, `worst_score`),
    CONSTRAINT `fk_dp_record_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 사람 검수 이력. 레코드의 현재 상태와 별개로 판정 기록을 계속 쌓는다
-- (같은 레코드를 다시 판정할 수 있고, 그 근거가 다음 생성 프롬프트를 고칠 재료다).
CREATE TABLE IF NOT EXISTS `llm_dp_review` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `record_id`         INT(11) NOT NULL,
    -- approved | edited | rejected
    `verdict`           VARCHAR(16) NOT NULL,
    `taxonomy`          VARCHAR(32),
    `edited_question`   TEXT,
    `edited_answer`     TEXT,
    `reviewer`          VARCHAR(64),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    KEY `ix_dp_review_record` (`record_id`),
    CONSTRAINT `fk_dp_review_record` FOREIGN KEY (`record_id`)
        REFERENCES `llm_dp_record` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 데이터셋 버전(릴리스 스냅샷). 어떤 모델 · 프롬프트 · 임계값으로 만들었는지를
-- 함께 남겨야 나중에 "그때는 왜 통과율이 낮았나"를 설명할 수 있다.
CREATE TABLE IF NOT EXISTS `llm_dp_version` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    `version`           VARCHAR(32) NOT NULL,
    `record_count`      INT(11) DEFAULT 0,
    `pass_rate`         INT(11) DEFAULT 0,
    `human_reviewed`    INT(11) DEFAULT 0,
    `gen_model`         VARCHAR(64),
    `judge_model`       VARCHAR(64),
    `prompt_name`       VARCHAR(64),
    `thresholds`        JSON,
    `mix`               JSON,
    `split`             JSON,
    `split_by`          VARCHAR(32),
    -- 이 버전에 담긴 레코드들이 어느 실행에서 나왔는지. ["run-a1b2","run-c3d4"]
    -- run 과 version 은 직교한다(1 run → N version, N run → 1 version). 이게 없으면
    -- "이 버전이 어떻게 나왔나"에 답할 수 없다. 레코드 쪽은 lineage JSON 에 run_id 로 남는다.
    `source_runs`       JSON,
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_version` (`dataset_id`, `version`),
    CONSTRAINT `fk_dp_version_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 노드 실행 이력. 노드 잡은 산출물을 작업 데이터셋에 파일로만 남기므로, 화면이
-- 진행 상태를 물어볼 데가 없고 다음 노드가 상류 산출물을 찾을 수도 없다. 이 테이블이
-- 그 둘을 대신한다(실행 1건 = 노드 1개의 한 번 실행).
-- 잡을 띄울 때 running 으로 넣고, 폴링 리콘사일러가 funnel.json 을 보고 done 으로
-- 마감한다. 산출물이 없는데 잡이 끝나 있으면 failed 로 닫는다.
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

-- 파이프라인이 소유한 VLM 서빙(자동 배포·회수). 카탈로그의 모델 id 는 이름표일 뿐
-- 실행 중인 서빙을 가리키지 않으므로, 무엇을 왜 띄웠는지를 여기에 적어 두고
-- 리콘사일러가 유휴 상태를 보고 내린다. 소유 기록이 없으면 실패 시 GPU 가 영영 잠긴다.
CREATE TABLE IF NOT EXISTS `llm_dp_serving` (
    `id`                INT(11) NOT NULL AUTO_INCREMENT,
    `dataset_id`        INT(11) NOT NULL,
    -- generator | judge. 한 파이프라인은 역할당 하나만 쥔다(생성 모델 == 심사 모델은
    -- 맹점이 겹쳐 게이트가 무의미해지므로 상위에서 이미 차단된다).
    `role`              VARCHAR(16) NOT NULL,
    -- constants.GENERATION_MODELS 의 id (qwen8b, intern3 …)
    `model_id`          VARCHAR(32) NOT NULL,
    -- 실제로 띄운 저장소 경로. 카탈로그가 바뀌어도 이 배포가 무엇이었는지 남는다.
    `hf_id`             VARCHAR(255),
    -- 플랫폼 playground. 배포·중지·상태 조회는 전부 이 id 로 기존 경로를 탄다.
    `playground_id`     INT(11),
    -- 추론 URL 조립용(배포의 api_path). 노드에는 완성된 URL 만 넘긴다.
    `api_path`          VARCHAR(255),
    -- pending | ready | failed | released
    `status`            VARCHAR(16) NOT NULL DEFAULT 'pending',
    `error_reason`      VARCHAR(1000),
    `create_datetime`   DATETIME DEFAULT CURRENT_TIMESTAMP(),
    -- 마지막으로 노드가 이 서빙을 쓴 시각. 유휴 판정 = 회수 시점의 근거.
    `last_used_datetime` DATETIME,
    `release_datetime`  DATETIME,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dp_serving_role` (`dataset_id`, `role`),
    -- 리콘사일러가 매 주기 살아 있는 것만 훑는다.
    KEY `ix_dp_serving_status` (`status`),
    CONSTRAINT `fk_dp_serving_dataset` FOREIGN KEY (`dataset_id`)
        REFERENCES `llm_dp_dataset` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
