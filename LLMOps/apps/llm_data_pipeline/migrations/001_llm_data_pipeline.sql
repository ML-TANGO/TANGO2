-- llm_data_pipeline — 학습 데이터 파이프라인 신규 테이블 6종.
--
-- 기존 테이블을 ALTER 하지 않는다(운영 중 스키마 변경 회피). 전부 신규 생성이라
-- 적용 실패해도 기존 서비스에 영향이 없다.
--
-- 적용 (마이그레이션 러너가 없으므로 수동):
--   kubectl -n jonathan-mariadb exec -i <mariadb-pod> -- \
--     mysql -u root -p jonathan_llm < 001_llm_data_pipeline.sql
--
-- 신규 설치 경로에는 devops/gaip_maraidb/mariadb-init/file/schema_llm.sql 에도
-- 같은 DDL 이 들어가야 한다(init 은 이 파일을 읽지 않는다).

USE `jonathan_llm`;

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
