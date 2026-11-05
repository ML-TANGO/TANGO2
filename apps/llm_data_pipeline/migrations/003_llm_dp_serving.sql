-- 학습 데이터 파이프라인 — 파이프라인이 소유한 VLM 서빙.
--
-- 왜 필요한가: 생성·심사 노드는 VLM 추론을 해야 하는데, 카탈로그의 모델 id 는 이름표일
-- 뿐 실행 중인 서빙을 가리키지 않는다. 파이프라인이 필요한 모델을 **자동으로 띄우고
-- 끝나면 회수**하려면, "누가 무엇을 왜 띄웠는지"가 어딘가 적혀 있어야 한다.
-- 이 표가 그 소유권 장부다.
--
-- 회수(가장 중요): 배포는 GPU 를 문다. 소유 기록이 없으면 실패·중단 시 아무도 그것을
-- 내리지 않아 GPU 가 영영 잠긴다(이 프로젝트에서 유령 잡으로 같은 일을 이미 겪었다).
-- 그래서 배포를 **띄우기 전에** pending 으로 적고, 리콘사일러가 유휴 상태를 보고 내린다.
--
-- 배포 주체는 BE 다(잡이 아니다). 잡 파드가 직접 띄우면 잡이 죽는 순간 배포가 고아가 되고,
-- 잡에 플랫폼 배포 권한을 주는 경로도 새로 뚫어야 한다. BE 는 이미 리콘사일러를 갖고 있다.
--
-- 적용:
--   mysql ... jonathan_llm < 003_llm_dp_serving.sql

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
