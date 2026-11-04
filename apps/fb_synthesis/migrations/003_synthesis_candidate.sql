-- WBS 3.3 / SP-7 (P3) — 프롬프트 후보 큐레이션 영속.
-- 멱등: 이미 존재하면 무시.
CREATE TABLE IF NOT EXISTS `synthesis_candidate` (
    `id`                  INT(11) NOT NULL AUTO_INCREMENT,
    `project_id`          INT(11) NOT NULL,
    `prompt`              LONGTEXT,
    `score`               FLOAT        DEFAULT 0,
    `method`              VARCHAR(50)  COMMENT 'OPRO/APE 등 최적화 방식',
    `iteration`           INT(11)      DEFAULT 0,
    `status`              VARCHAR(20)  DEFAULT 'candidate' COMMENT 'candidate/adopted/discarded',
    `create_datetime`     VARCHAR(50),
    PRIMARY KEY(`id`)
);
