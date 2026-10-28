-- 001_prompt_optimization.sql
--
-- 프롬프트 최적화(fewshot-prompt-optimizer) 결과 영속 테이블.
--
-- Run once against the jonathan_llm database, for example:
--   mysql -h $JF_DB_HOST -u $JF_DB_USER -p jonathan_llm < 001_prompt_optimization.sql
--
-- Do not rerun devops/gaip_maraidb/mariadb-init for this change on a live
-- cluster: that init job rebuilds jonathan_llm. This migration only adds one
-- new table (기존 테이블 변경 없음).
--
-- 왜 영속이 필요한가 (2026-07-31 실측):
--   * 컨테이너는 완료 job 을 JOB_TTL_SECONDS(기본 1h) 후 폐기하고 재시작 시 전부 잃는다.
--   * 플랫폼 external_container 의 job tracker 도 휘발성이며, job 이 terminal 이 되면
--     helm release 를 teardown 한다 — 즉 결과를 붙잡아 둘 곳이 어디에도 없다.
--   → status 가 completed 로 전이하는 순간 여기 저장해야 산출물이 남는다.
--
-- 설계: few-shot 프롬프트 최적화 통합 설계 문서(내부) §5

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
    `create_datetime` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `finish_datetime` DATETIME DEFAULT NULL,
    PRIMARY KEY(`id`),
    KEY `idx_prompt_opt_playground` (`playground_id`, `is_active`),
    KEY `idx_prompt_opt_workspace` (`workspace_id`),
    KEY `idx_prompt_opt_job` (`job_id`),
    CONSTRAINT `fk_prompt_opt_playground`
        FOREIGN KEY (`playground_id`) REFERENCES `playground` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE
);
