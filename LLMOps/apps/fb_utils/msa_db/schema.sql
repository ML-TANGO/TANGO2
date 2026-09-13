CREATE TABLE IF NOT EXISTS `user` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32) UNIQUE,
    `uid`                   INT(11),
    `password`              LONGTEXT NOT NULL,
    `user_type`             INT(11) NOT NULL,
    `login_counting`        INT(5) DEFAULT 0,
    `nickname`              VARCHAR(32),
    `job`                   VARCHAR(50),
    `email`                 VARCHAR(50),
    `team`                  VARCHAR(50),
    `create_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `usergroup` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(50) UNIQUE,
    `description`           VARCHAR(1000),
    `create_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `user_usergroup` (
    `usergroup_id`          INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    PRIMARY KEY(`usergroup_id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`usergroup_id`) REFERENCES `msa_jfb`.`usergroup` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `user_register` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32) UNIQUE,
    `password`              LONGTEXT NOT NULL,
    `nickname`              VARCHAR(32),
    `job`                   VARCHAR(50),
    `email`                 VARCHAR(50),
    `team`                  VARCHAR(50),
    `create_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `gpu_cuda_info` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
	`model`	            VARCHAR(50) NOT	NULL,
    `architecture`      VARCHAR(50) NOT NULL,
    `cuda_core`         INT(11) NOT NULL,
    PRIMARY KEY(`id`),
    UNIQUE KEY(`model`)
);

CREATE TABLE IF NOT EXISTS `node` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
	`name`	            VARCHAR(50) NOT	NULL,
    `ip`                VARCHAR(100) NOT NULL,
    `role`              VARCHAR(50) NOT NULL,
    `status`            VARCHAR(50) DEFAULT "Not ready",
    `create_datetime`	VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `resource_group` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
    `name`              VARCHAR(100) UNIQUE,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `node_gpu` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
    `node_id`           INT(11)	NOT NULL,
    `resource_group_id`	INT(11)	NOT NULL,
	`gpu_memory`	    INT(11)	NOT NULL,
	`gpu_uuid`	        VARCHAR(200) DEFAULT NULL,
    PRIMARY KEY(`id`),
    UNIQUE KEY(`gpu_uuid`),
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`resource_group_id`) REFERENCES `msa_jfb`.`resource_group` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `node_cpu` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
    `node_id`           INT(11)	NOT NULL,
    `resource_group_id`	INT(11)	NOT NULL,
	`core`	            INT(11)	NOT NULL,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`resource_group_id`) REFERENCES `msa_jfb`.`resource_group` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `node_ram` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
    `node_id`           INT(11)	NOT NULL,
	`size`	            BIGINT(20) NOT	NULL,
    `type`	            VARCHAR(50) NOT	NULL,
    `model`	            VARCHAR(50) NOT	NULL,
    `speed`	            VARCHAR(50) NOT	NULL,
    `manufacturer`      VARCHAR(50) NOT	NULL,
    `count`	            INT(11) NOT	NULL,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `node_npu` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
    `node_id`           INT(11)	NOT NULL,
    `resource_group_id`	INT(11)	NOT NULL,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`resource_group_id`) REFERENCES `msa_jfb`.`resource_group` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `storage` (
	`id`	INT	NOT NULL AUTO_INCREMENT,
    `name`  VARCHAR(50) NOT NULL,
	`ip`	VARCHAR(50)	NOT NULL,
	`type`	VARCHAR(50)	NOT NULL,
	`data_sc`	VARCHAR(50)	NULL,
    `main_sc`	VARCHAR(50)	NULL,
	`mountpoint`	VARCHAR(100) NULL,
    `size`  BIGINT(20),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`name`)
);

create TABLE IF NOT EXISTS `instance` (
    `id`                    INT(11)	NOT NULL AUTO_INCREMENT,
    `instance_name`         VARCHAR(50),
    `instance_count`        INT(11),
    `instance_type`         VARCHAR(50),
    `gpu_resource_group_id` INT(11),
    `gpu_allocate`          FLOAT(11) DEFAULT 0,
    `cpu_allocate`          FLOAT(11) DEFAULT 0,
    `ram_allocate`          FLOAT(11) DEFAULT 0,
    `npu_allocate`          FLOAT(11) DEFAULT 0,
    PRIMARY KEY(`id`),
    UNIQUE KEY(`instance_name`)
);

CREATE TABLE IF NOT EXISTS `node_instance` (
	`node_id`	                INT(11)	NOT NULL,
	`instance_id`	            INT(11)	NOT NULL,
	`instance_allocate`	        INT(11)	NOT NULL,
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`instance_id`) REFERENCES `msa_jfb`.`instance` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- SP-8 / 수용계획서 3.1 — Edge 워커 노드 (인스턴스 없는 단일 노드, K8s join 안 함).
-- remoteManager(K8s-free 브리지) 가 관리하는 엣지 디바이스(ORIN/RPi/PC)를 플랫폼
-- 노드 테이블에 등록. 상태는 remoteManager /metrics 폴링으로 갱신.
CREATE TABLE IF NOT EXISTS `edge_worker` (
    `id`                 INT(11) NOT NULL AUTO_INCREMENT,
    `device_id`          VARCHAR(128) NOT NULL,          -- 식별
    `name`               VARCHAR(128),
    `device_type`        VARCHAR(32),                    -- orin / rpi-hailo / pc-gpu ...
    `remote_manager_url` VARCHAR(512) NULL,              -- remoteManager centralagent endpoint (SP-8 §4/D1: heartbeat-only 디바이스는 NULL 허용)
    `conn_status`        VARCHAR(16) DEFAULT 'offline',  -- 연결상태 online/offline
    `last_seen`          DATETIME DEFAULT NULL,          -- heartbeat
    `deploy_model`       VARCHAR(128) DEFAULT NULL,      -- 배포상태: 모델명
    `deploy_version`     VARCHAR(64) DEFAULT NULL,       -- 버전
    `deploy_state`       VARCHAR(16) DEFAULT NULL,       -- running / stopped / error
    `cpu_cores`          INT(11) DEFAULT NULL,           -- [협의] 자원
    `mem_total`          BIGINT DEFAULT NULL,
    `gpu_info`           VARCHAR(256) DEFAULT NULL,
    `container_count`    INT(11) DEFAULT NULL,
    `edge_token_hash`    VARCHAR(128) DEFAULT NULL,      -- 노드별 Bearer token sha256 (평문 미저장)
    `token_prefix`       VARCHAR(16) DEFAULT NULL,       -- 토큰 식별 prefix (표시용)
    `token_expires_at`   DATETIME DEFAULT NULL,          -- 토큰 만료 (발급+90일)
    `last_heartbeat_json` TEXT DEFAULT NULL,             -- 최근 heartbeat 원본 (자원/지연/에러)
    -- 디바이스 heartbeat 수신 시각 — last_seen 과 분리한다. last_seen 은 '생존 증거'라
    -- refresh(/metrics 폴링)·deploy 도 갱신하는데, 30초 throttle 을 그 값에 걸면 UI
    -- 새로고침 한 번이 디바이스의 다음 heartbeat 를 429 로 튕긴다(2026-09-11 재현).
    -- throttle 은 이 컬럼(디바이스 푸시만 갱신)을 기준으로 판단해야 한다.
    `last_heartbeat_at`  DATETIME DEFAULT NULL,
    `create_datetime`    DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_datetime`    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    UNIQUE KEY `uq_edge_device` (`device_id`)
);

-- SP-8 자유 텍스트 커스텀 레이블 (키-값, value 옵션 → 태그 겸용). 클러스터 노드 +
-- 엣지 워커 공용(target_type 으로 구분). "이 서버는 DB" 같은 운영 메모.
CREATE TABLE IF NOT EXISTS `custom_label` (
    `id`              INT(11) NOT NULL AUTO_INCREMENT,
    `target_type`     VARCHAR(16) NOT NULL,             -- 'node' | 'edge_worker'
    `target_id`       VARCHAR(128) NOT NULL,            -- node name 또는 edge device_id
    `label_key`       VARCHAR(64) NOT NULL,
    `label_value`     VARCHAR(255) DEFAULT NULL,
    `create_datetime` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(`id`),
    UNIQUE KEY `uq_custom_label` (`target_type`, `target_id`, `label_key`)
);

CREATE TABLE IF NOT EXISTS `workspace` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`name`	                VARCHAR(100) NOT	NULL,
	`description`	        LONGTEXT DEFAULT NULL,
	`create_datetime`	    VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
	`start_datetime`	    VARCHAR(50) NULL,
	`end_datetime`	        VARCHAR(50) NULL,
	`path`	                LONGTEXT DEFAULT NULL,
	`manager_id`	        INT(11)	NOT NULL,
    `cpu_core`              INT(11) DEFAULT 4,
    `ram`                   INT(11) DEFAULT 50,
    `data_storage_size`  BIGINT NOT NULL,
    `data_storage_id`  INT(11) NOT NULL,
    `data_storage_lock`  INT(1) DEFAULT 0,
    `main_storage_size`  BIGINT NOT NULL,
    `main_storage_id`  INT(11) NOT NULL,
    `main_storage_lock`  INT(1) DEFAULT 0,
    `use_marker`         TINYINT(1) DEFAULT 0,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`manager_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `workspace_instance` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`workspace_id`		    INT(11) NOT NULL,
	`instance_id`	        INT(11),
	`instance_allocate`	    INT(11),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`instance_id`) REFERENCES `msa_jfb`.`instance` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `workspace_request` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`name`	                VARCHAR(100),
	`description`	        LONGTEXT DEFAULT NULL,
	`create_datetime`	    VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
	`start_datetime`	    VARCHAR(50) NULL,
	`end_datetime`	        VARCHAR(50) NULL,
	`path`	                LONGTEXT DEFAULT NULL,
	`manager_id`	        INT(11)	NOT NULL,
    `cpu_core`              INT(11) DEFAULT 4,
    `ram`                   INT(11) DEFAULT 50,
    `data_storage_size`     BIGINT,
    `data_storage_id`       INT(11),
    `main_storage_size`     BIGINT,
    `main_storage_id`       INT(11),
    `user_list`             JSON,
    `allocate_instance_list`    JSON,
    `type`                  VARCHAR(50),
    `workspace_id`          INT(11),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`manager_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `workspace_resource` (
	`workspace_id`	        INT(11)	NOT NULL AUTO_INCREMENT,
    `tool_cpu_limit`        DOUBLE NOT NULL,
    `tool_ram_limit`        DOUBLE NOT NULL,
    `job_cpu_limit`         DOUBLE NOT NULL,
    `job_ram_limit`         DOUBLE NOT NULL,
    `hps_cpu_limit`         DOUBLE NOT NULL,
    `hps_ram_limit`         DOUBLE NOT NULL,
    `deployment_cpu_limit`  DOUBLE NOT NULL,
    `deployment_ram_limit`  DOUBLE NOT NULL,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `user_workspace` (
    `workspace_id`          INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    `favorites`             INT(11) DEFAULT 0,
    PRIMARY KEY(`workspace_id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `datasets` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
	`workspace_id`	    INT(11)	NOT NULL,
	`name`	            VARCHAR(100)	NULL,
	`create_user_id`	INT(11)	NULL,
	`access`	        INT(1)	NULL,
    `description`	    LONGTEXT DEFAULT NULL,
    `filebrowser`       INT(11) DEFAULT 0,
	`create_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
	`modify_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ###############################################################
CREATE TABLE IF NOT EXISTS `login_session` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `user_id`               INT(11) NOT NULL,
    `token`                 LONGTEXT NOT NULL,
    `last_call_datetime`    VARCHAR(20) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `image` (
    `id`                    INT(11) NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `user_id`               INT(11) NOT NULL,
    `name`                  VARCHAR(100) NOT NULL,
    `real_name`             VARCHAR(200),
    `file_path`             VARCHAR(200),
    `status`                INT(11) DEFAULT 0,
    `fail_reason`           VARCHAR(300),
    `type`                  INT(11) DEFAULT 0,
    `access`                INT(11) DEFAULT 0,
    `size`                  FLOAT(11) DEFAULT NULL,
    `iid`                   VARCHAR(50) DEFAULT NULL,
    `docker_digest`         VARCHAR(200) DEFAULT NULL,
    `libs_digest`           VARCHAR(300) DEFAULT NULL,
    `description`           VARCHAR(1000) DEFAULT NULL,
    `upload_filename`       VARCHAR(300) DEFAULT NULL,
    `create_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(20) DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE KEY unique_key (`name`),
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `image_workspace` (
    `image_id`              INT(11) NOT NULL,
    `workspace_id`          INT(11) NOT NULL,
    PRIMARY KEY(`image_id`,`workspace_id`),
    CONSTRAINT FOREIGN KEY (`image_id`)     REFERENCES `msa_jfb`.`image`     (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ###############################################################
CREATE TABLE IF NOT EXISTS `project` (
	`id`	            INT(11)	NOT NULL AUTO_INCREMENT,
	`workspace_id`	    INT(11)	NOT NULL,
    `type`              VARCHAR(20) NOT NULL,
    `category`          VARCHAR(100),
    `built_in_model`    VARCHAR(100),
    `huggingface_token` LONGTEXT,
    `huggingface_model_id` LONGTEXT,
	`name`	            VARCHAR(200) NOT NULL,
	`create_user_id`	INT(11)	NULL,
	`access`	        TINYINT(1)	NULL,
    `description`	    LONGTEXT DEFAULT NULL,
    `instance_id`       INT(11) NULL,
    `instance_allocate` INT(11) NULL,
    `job_cpu_limit`     DOUBLE DEFAULT 0,
    `job_ram_limit`     DOUBLE DEFAULT 0,
    `hps_cpu_limit`     DOUBLE DEFAULT 0,
    `hps_ram_limit`     DOUBLE DEFAULT 0,
    `tool_cpu_limit`    DOUBLE DEFAULT 0,
    `tool_ram_limit`    DOUBLE DEFAULT 0,
	`create_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`workspace_id`, `name`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `project_bookmark`(
    `project_id`         INT(11),
    `user_id`            INT(11),
    constraint foreign key (`project_id`) references `msa_jfb`.`project` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `project_job` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`	        INT(11)	NOT NULL,
	`create_user_id`	    INT(11) NOT	NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
	`name`	                varchar(100) NOT NULL,
    `run_code`              LONGTEXT,
    `distributed_framework` VARCHAR(20)	NULL,  
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_count`             INT(11),
    `pod_count`             INT(11) DEFAULT 1,
    `parameter`             LONGTEXT,
    `resource_group_id`     INT(11) NULL,
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
	`create_datetime`	    VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `end_status`            VARCHAR(50),
    `dataset_data_path`     LONGTEXT,
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    -- UNIQUE KEY(`project_id`, `name`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `training` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`	        INT(11)	NOT NULL,
	`create_user_id`	    INT(11) NOT	NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
	`name`	                varchar(100) NOT NULL,
    `run_code`              LONGTEXT,
    `distributed_framework` VARCHAR(20)	NULL,  
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_count`             INT(11),
    `pod_count`             INT(11) DEFAULT 1,
    `parameter`             LONGTEXT,
    `resource_group_id`     INT(11) NULL,
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
	`create_datetime`	    VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `end_status`            VARCHAR(50),
    `dataset_data_path`     LONGTEXT,
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    -- UNIQUE KEY(`project_id`, `name`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `user_project` (
    `project_id`          INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    `favorites`             INT(11) DEFAULT 0,
    PRIMARY KEY(`project_id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `project_tool` (
    `id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`		    INT(11) NOT NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
	`tool_type`	            INT(11)	NOT NULL,
    `tool_index`            INT(11),
    `tool_password`         LONGTEXT,
    `gpu_count`             INT(11) DEFAULT 0,
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_select`            JSON,
    `pod_count`             INT(11) DEFAULT 1,
    `request_status`        TINYINT DEFAULT 0,
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS `project_hps` (
    `id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`	        INT(11)	NOT NULL,
	`create_user_id`	    INT(11) NOT	NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
    `dataset_data_path`     LONGTEXT,
	`name`	                varchar(100),
    `run_code`              LONGTEXT,
    `parameter`             LONGTEXT,
    `fixed_parameter`       LONGTEXT,
    `target_metric`         VARCHAR(100),
    `built_in_search_count` INT(11) DEFAULT 0,
    `gpu_count`             INT(11),
    `pod_count`             INT(11) DEFAULT 1,
    `resource_group_id`     INT(11) NULL,
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
	`create_datetime`	    VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `end_status`            VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,

    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`resource_group_id`) REFERENCES `msa_jfb`.`resource_group` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `deployment`(
    `id`                    INT(11)	NOT NULL AUTO_INCREMENT,
    `workspace_id`          INT(11),
    `name`                  varchar(100),
    `description`           varchar(1000),
    `create_datetime`       VARCHAR(50) DEFAULT current_timestamp(), 
    `access`                INT(11),
    `user_id`               INT(11),
    -- resource
    `instance_id`           INT(11),
    `instance_allocate`     INT(11),
    `instance_type`         varchar(20),
    `gpu_per_worker`        INT(11) default 0,
    `gpu_cluster_auto`      TINYINT DEFAULT 0,
    `gpu_auto_cluster_case`     longtext,
    -- 학습
    `model_type`            varchar(50), -- custom, built-in, huggingface
    `project_id`            INT(11),
    `training_id`            INT(11), -- job_id or hps_id
    `training_type`           VARCHAR(32), -- job or hps
    -- 새모델
    `huggingface_model_id`  varchar(1000),
    `huggingface_model_token`  varchar(1000),
    `built_in_model_id`               INT(11), -- 새모델 + 빌트인
    `model_category`               varchar(50), -- 새모델 + 빌트인
    `is_new_model`           TINYINT(1) NOT NULL DEFAULT 0, -- 새모델 + 빌트인
    -- 배포
    `environments`          longtext,
    `command`               longtext,
    `image_id`              INT(11),
    `api_path`              varchar(100),
    `deployment_cpu_limit`     DOUBLE DEFAULT 0,
    `deployment_ram_limit`     DOUBLE DEFAULT 0,
    `llm`                  INT(11) DEFAULT 0,
    PRIMARY KEY(`id`),
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade,
    constraint foreign key (`workspace_id`) references `msa_jfb`.`workspace` (`id`) on update cascade on delete cascade,
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `deployment_worker`(
    `id`                INT(11)	NOT NULL AUTO_INCREMENT,
    `deployment_id`     INT(11),
    `description`       longtext,
    `instance_id`       INT(11),
    `gpu_per_worker`    INT(11),
    `instance_type`     varchar(20),
    `gpu_cluster_auto`  TINYINT DEFAULT 0,
    `project_id`        INT(11),
    `command`           longtext,
    `environments`      longtext,
    `image_id`          INT(11),
    `pod_count`         INT(11) DEFAULT 1,
    `create_datetime`   VARCHAR(50) default current_timestamp(),
    `start_datetime`    VARCHAR(50),
    `end_datetime`      VARCHAR(50),
    PRIMARY KEY(`id`),
    constraint deployment_worker_id_uindex unique (id),
    constraint foreign key (deployment_id) references deployment (id) on update cascade on delete cascade,
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);

-- SP-Deployment(D6) §12: 클러스터 배포 API 게시 상태. 키 원본은 저장 안 함(Kong 보관, fetch).
CREATE TABLE IF NOT EXISTS `deployment_api` (
    `deployment_id`     INT(11) NOT NULL COMMENT '게시 대상 클러스터 배포(deployment.id)',
    `api_consumer`      VARCHAR(128) NOT NULL COMMENT 'Kong consumer username (dep-{deployment_id})',
    `api_route_id`      VARCHAR(64) COMMENT 'Kong route id (path /deployment/{api_path})',
    `enabled`           TINYINT(1) NOT NULL DEFAULT 1 COMMENT '게시 활성(1)/해제(0)',
    `published_at`      VARCHAR(50) DEFAULT current_timestamp(),
    `update_datetime`   DATETIME DEFAULT current_timestamp() ON UPDATE current_timestamp(),
    PRIMARY KEY(`deployment_id`),
    constraint foreign key (`deployment_id`) references `deployment` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `deployment_data_form` (
    `deployment_id`             INT(11) NOT NULL,
    `location`                  VARCHAR(11) NOT NULL COMMENT 'data location in API (body, args, file ...)',
    `method`                    VARCHAR(11) NOT NULL COMMENT 'api call method',
    `api_key`                   VARCHAR(100) NOT NULL COMMENT 'api key',
    `value_type`                VARCHAR(100) NOT NULL COMMENT 'api_key value',
    `category`                  VARCHAR(100) COMMENT 'input form category. ex) Image, Video, Audio .. ',
    `category_description`      VARCHAR(1000) COMMENT 'category description. File format ( png, jpg ...) , size ...',
    UNIQUE KEY unique_key (`deployment_id`, `api_key`),
    CONSTRAINT FOREIGN KEY (`deployment_id`) REFERENCES `msa_jfb`.`deployment` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `deployment_bookmark`(
    `deployment_id`         INT(11),
    `user_id`               INT(11),
    constraint foreign key (`deployment_id`) references `msa_jfb`.`deployment` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `user_deployment` (
    `deployment_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`deployment_id`),
    CONSTRAINT FOREIGN KEY (`deployment_id`) REFERENCES `msa_jfb`.`deployment` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `notification_history` (
    `id`                INT(11)	NOT NULL AUTO_INCREMENT,
    `user_id`           INT(11) NOT NULL,
    `type`              VARCHAR(50) NOT NULL,
    `message`           VARCHAR(100) NOT NULL,
    `read`              TINYINT(1) NOT NULL DEFAULT 0,
    `message_info`      JSON,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `workspace_nodes` (
    `workspace_id`                  INT(11)	NOT NULL,
    `node_id`                       INT(11) NOT NULL,
    UNIQUE KEY unique_key (`workspace_id`, `node_id`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`node_id`) REFERENCES `msa_jfb`.`node` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `workspace_basic_cost` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `time_unit`                  VARCHAR(50) NOT NULL,
    `time_unit_cost`             INT(11) NOT NULL,
    `members`                    INT(11) NOT NULL,
    `add_member_cost`            INT(11) NOT NULL,
    `out_bound_network`          JSON,
    `create_datetime`            datetime default current_timestamp(),
    `active`                     TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `instance_cost_plan` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `name`                       VARCHAR(50) NOT NULL,
    `instance_list`              JSON,
    `time_unit`                  VARCHAR(50) NOT NULL,
    `time_unit_cost`             INT(11) NOT NULL,
    `create_datetime`            datetime default current_timestamp(),
    `type`                       VARCHAR(50) NOT NULL,
    `active`                     TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `storage_cost_plan` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `name`                       VARCHAR(50) NOT NULL,
    `source`                     VARCHAR(50) NOT NULL,
    `size_unit`                  VARCHAR(50) NOT NULL,
    `size`                       INT(11) NOT NULL,
    `storage_id`                 INT(11) NOT NULL,
    `cost`                       INT(50) NOT NULL,
    `create_datetime`            datetime default current_timestamp(),
    `active`                     TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `pipeline` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `type`                       VARCHAR(50) NOT NULL DEFAULT "advanced",
    `built_in_type`              VARCHAR(100),
    `built_in_sub_type`          VARCHAR(100),
    `built_in_specification`     LONGTEXT,
    `built_in_data_type`         VARCHAR(50),
    `built_in_preprocessing_list`JSON,
    `name`                       VARCHAR(100) NOT NULL,
    `description`                LONGTEXT,
    `access`                     INT(11) NOT NULL DEFAULT 1,
    `owner_id`                   INT(11) NOT NULL,
    `create_user_id`             INT(11) NOT NULL,  
    `workspace_id`               INT(11) NOT NULL,
    `dataset_id`                 INT(11),
    `graph`                      JSON,
    `start_dataset_size`         BIGINT(20) DEFAULT 0,
    `latest_history_id`          INT(11),
    `create_datetime`            DATETIME DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`            DATETIME DEFAULT CURRENT_TIMESTAMP() ON UPDATE CURRENT_TIMESTAMP(),
    `start_datetime`             VARCHAR(50),
    `end_datetime`               VARCHAR(50),
    `retraining_count`           INT(11) DEFAULT 0,
    `retraining_type`            VARCHAR(20),
    `retraining_unit`            VARCHAR(20),
    `retraining_value`           INT(11) DEFAULT 0,
    `retraining_wait_start_time` VARCHAR(50),
    PRIMARY KEY(`id`),
    unique key(`name`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`owner_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `pipeline_bookmark`(
    `pipeline_id`         INT(11),
    `user_id`            INT(11),
    constraint foreign key (`pipeline_id`) references `msa_jfb`.`pipeline` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `user_pipeline` (
    `pipeline_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`pipeline_id`),
    CONSTRAINT FOREIGN KEY (`pipeline_id`) REFERENCES `msa_jfb`.`pipeline` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS `pipeline_task` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `task_type`                  VARCHAR(20) NOT NULL,
    `task_item_type`             VARCHAR(50) NOT NULL,
    `project_training_type`      VARCHAR(20),
    `pipeline_id`                INT(11),
    `task_item_id`               INT(11) COMMENT "project, deployment id",
    `image_id`                   INT(11),
    `gpu_count`                  INT(11) DEFAULT 0,
    `run_code`                   LONGTEXT,
    `parameter`                  LONGTEXT,
    `built_in_params`            LONGTEXT,
    `status`                     VARCHAR(50) DEFAULT "done",
    `start_datetime`             VARCHAR(50),
    `end_datetime`               VARCHAR(50),
    `task_item_job_id`           INT(11) COMMENT "training, worker id",
    `task_item_job_str_id`       VARCHAR(64) COMMENT "external container job id (str/uuid) — generation 노드용",
    `dataset_data_path`          LONGTEXT,
    `x_index`                    INT(11) DEFAULT 0,
    `y_index`                    INT(11) DEFAULT 0,
    `x_position`                 INT(11) DEFAULT 0, 
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`pipeline_id`) REFERENCES `msa_jfb`.`pipeline` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `pipeline_history` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `pipeline_id`                INT(11),
    `pipeline_tasks`             JSON,
    `pipeline_graph`             JSON,
    `increase_dataset_size`      BIGINT(20) DEFAULT 0,
    `retraining_count`           INT(11) DEFAULT 0,
    `end_status`                 VARCHAR(50),
    `error_log`                  LONGTEXT,
    `start_user_id`              INT(11),
    `start_datetime`             VARCHAR(50),
    `end_datetime`               VARCHAR(50),
    `is_retraining_setting`      TINYINT DEFAULT 0,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`pipeline_id`) REFERENCES `msa_jfb`.`pipeline` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 데이터 합성 프레임워크 단독 UI P1 (v0.4 3.3 / SP-7)
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

CREATE TABLE IF NOT EXISTS `collect` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `name`                       VARCHAR(100) NOT NULL,
    `description`                LONGTEXT,
    `dataset_id`                 INT(11),
    `dataset_path`               VARCHAR(50),
    `instance_id`                INT(11),
    `collect_method`             VARCHAR(50) NOT NULL,
    `collect_cycle`              INT(11),
    `collect_cycle_unit`         VARCHAR(50),
    `collect_storage_limit`      TINYINT(1) NOT NULL DEFAULT 0,
    `collect_storage_size`       BIGINT(20),
    `collect_storage_unit`       VARCHAR(50),
    `collect_information_list`    JSON,
    `create_datetime`            datetime default current_timestamp(),
    `start_datetime`             datetime,
    `end_datetime`               datetime,
    `access`                     TINYINT(1) NOT NULL DEFAULT 0,
    `owner_id`                   INT(11) NOT NULL,
    `workspace_id`               INT(11),
    `instance_count`             INT(11),
    `bookmark`                   TINYINT(1) NOT NULL DEFAULT 0,
    `members`                    VARCHAR(100),
    `status`                     VARCHAR(50),
    PRIMARY KEY(`id`),
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `collect_public_api` (
    `id`                        INT(11) NOT NULL AUTO_INCREMENT,
    `url`                       LONGTEXT,
    `name`                      VARCHAR(50) NOT NULL,
    `providing_organization`    VARCHAR(50),
    `detail_url`                LONGTEXT,
    `method`                    VARCHAR(50) NOT NULL ,
    `data_type`                 VARCHAR(50),
    `jsonData`                  JSON,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `collect_history` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `collect_id`                 INT(11) NOT NULL,
    `collect_information`         JSON,
    `create_datetime`            datetime default current_timestamp(),
    `status`                     INT(11) ,
    `status_message`             LONGTEXT ,
    `path`                       LONGTEXT ,
    PRIMARY KEY(`id`)
);


CREATE TABLE IF NOT EXISTS `preprocessing` (
    `id`                         INT(11) NOT NULL AUTO_INCREMENT,
    `workspace_id`	    INT(11)	NOT NULL,
    `type`              VARCHAR(20) NOT NULL,
	`name`	            VARCHAR(100)	NULL,
    `built_in_data_type`VARCHAR(50),
    `built_in_data_tf`  VARCHAR(100),
	`owner_id`	INT(11)	NULL,
	`access`	        TINYINT(1)	NULL,
    `description`	    LONGTEXT DEFAULT NULL,
    `instance_id`       INT(11) NULL,
    `instance_allocate` INT(11) NULL,
    `job_cpu_limit`     DOUBLE DEFAULT 0,
    `job_ram_limit`     DOUBLE DEFAULT 0,
    `tool_cpu_limit`    DOUBLE DEFAULT 0,
    `tool_ram_limit`    DOUBLE DEFAULT 0,
	`create_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`workspace_id`, `name`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`owner_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS `preprocessing_tool` (
    `id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`preprocessing_id`		    INT(11) NOT NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
	`tool_type`	            INT(11)	NOT NULL,
    `tool_index`            INT(11),
    `tool_password`         LONGTEXT,
    `gpu_count`             INT(11) DEFAULT 0,
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_select`            JSON,
    `pod_count`             INT(11) DEFAULT 1,
    `request_status`        TINYINT DEFAULT 0,
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`preprocessing_id`) REFERENCES `msa_jfb`.`preprocessing` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `preprocessing_job` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`preprocessing_id`	        INT(11)	NOT NULL,
	`create_user_id`	    INT(11) NOT	NULL,
    `image_id`              INT(11),
    `dataset_id`            INT(11),
    `dataset_data_path`     LONGTEXT,
	`name`	                VARCHAR(100)	NULL,
    `run_code`              LONGTEXT NOT NULL,
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_count`             INT(11),
    `pod_count`             INT(11) DEFAULT 1,
    `parameter`             LONGTEXT,
    `resource_group_id`     INT(11) NULL,
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
	`create_datetime`	    VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `end_status`            VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    -- UNIQUE KEY(`project_id`, `name`),
    CONSTRAINT FOREIGN KEY (`preprocessing_id`) REFERENCES `msa_jfb`.`preprocessing` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`dataset_id`) REFERENCES `msa_jfb`.`datasets` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `preprocessing_bookmark`(
    `preprocessing_id`         INT(11),
    `user_id`            INT(11),
    constraint foreign key (`preprocessing_id`) references `msa_jfb`.`preprocessing` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `user_preprocessing` (
    `preprocessing_id`          INT(11) NOT NULL,
    `user_id`               INT(11) NOT NULL,
    PRIMARY KEY(`preprocessing_id`,`user_id`),
    CONSTRAINT FOREIGN KEY (`preprocessing_id`) REFERENCES `msa_jfb`.`preprocessing` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS `analyzer` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(100),
    `description`           LONGTEXT,
    `workspace_id`          INT(11) NOT NULL,
    `create_user_id`        INT(11),
    `create_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `latest_commit_id`      INT(11),
    `access`                INT(11),
    `owner_id`              INT(11),
    `instance_id`           INT(11),
    `instance_allocate`     INT(11),
    `graph_cpu_limit`       DOUBLE NOT NULL,
    `graph_ram_limit`       DOUBLE NOT NULL,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    constraint foreign key (`instance_id`) references `msa_jfb`.`instance` (`id`) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `analyzer_graph` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32),
    `description`           LONGTEXT,
    `workspace_id`          INT(11) NOT NULL,
    `create_user_id`        INT(11),
    `create_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `analyzer_id`           INT(11),
    `dataset_id`            INT(11),
    `file_path`             VARCHAR(100),
    `graph_type`            INT(11),
    `column`                VARCHAR(50),
    `graph_data`            LONGTEXT,
    `start_datetime`        DATETIME,
    `end_datetime`          DATETIME,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`analyzer_id`) REFERENCES `msa_jfb`.`analyzer` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS `analyzer_bookmark`(
    `analyzer_id`         INT(11),
    `user_id`               INT(11),
    constraint foreign key (`analyzer_id`) references `msa_jfb`.`analyzer` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);


CREATE TABLE IF NOT EXISTS `user_analyzer` (
    `analyzer_id` INT(11) NOT NULL,
    `user_id`    INT(11) NOT NULL,
    PRIMARY KEY(`user_id`,`analyzer_id`),
    CONSTRAINT FOREIGN KEY (`analyzer_id`) REFERENCES `msa_jfb`.`analyzer` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `built_in_model` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(200) NOT NULL,
    `category`              VARCHAR(100) NOT NULL,
    `task`                  VARCHAR(100) NOT NULL,
    `token`                 LONGTEXT,
    `huggingface_model_id`  LONGTEXT,
    `huggingface_git_url`   LONGTEXT,
    `readme`                LONGTEXT,
    `user_parameter`        LONGTEXT,
    `system_parameter`      LONGTEXT,
    `deploy_parameter`      LONGTEXT,
    `target_metric`         VARCHAR(200) NOT NULL,
    `resource_type`         VARCHAR(50) NOT NULL,
    `image`                 LONGTEXT,
    PRIMARY KEY(`id`)
);

CREATE TABLE IF NOT EXISTS `built_in_model_data_form` (
    `built_in_model_id`         INT(11) NOT NULL,
    `location`                  VARCHAR(11) NOT NULL COMMENT 'data location in API (body, args, file ...)',
    `method`                    VARCHAR(11) NOT NULL COMMENT 'api call method',
    `api_key`                   VARCHAR(100) NOT NULL COMMENT 'api key',
    `value_type`                VARCHAR(100) NOT NULL COMMENT 'api_key value',
    `category`                  VARCHAR(100) COMMENT 'input form category. ex) Image, Video, Audio .. ',
    `category_description`      VARCHAR(1000) COMMENT 'category description. File format ( png, jpg ...) , size ...',
    UNIQUE KEY unique_key (`built_in_model_id`, `api_key`),
    CONSTRAINT FOREIGN KEY (`built_in_model_id`) REFERENCES `msa_jfb`.`built_in_model` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS `project_tool_port` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `project_tool_id`       INT(11) NOT NULL,
    `port`                  INT(11) NOT NULL,
    `protocol`              ENUM('TCP', 'UDP') NOT NULL DEFAULT 'TCP',
    `description`           LONGTEXT,
    `create_user_name`      VARCHAR(100) NOT NULL,
    `ingress_path`          VARCHAR(100) NOT NULL,
    `created_datetime`      VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`project_tool_id`, `port`, `protocol`),
    CONSTRAINT FOREIGN KEY (`project_tool_id`) REFERENCES `msa_jfb`.`project_tool` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `project_tool_port_history` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `project_id`            INT(11) NOT NULL,
    `project_name`          VARCHAR(100) NOT NULL,
    `workspace_id`          INT(11) NOT NULL,
    `workspace_name`        VARCHAR(100) NOT NULL,
    `project_item_id`       INT(11) NOT NULL,
    `project_item_type`     ENUM('vscode', 'jupyter', 'shell') NOT NULL,
    `create_user_name`      VARCHAR(100) NOT NULL,
    `action_type`           ENUM('add', 'delete') NOT NULL,
    `port`                  INT(11) NOT NULL,
    `protocol`              ENUM('TCP', 'UDP') NOT NULL DEFAULT 'TCP',
    `ingress_path`          VARCHAR(100) NOT NULL,
    `description`           LONGTEXT,
    `created_datetime`      VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`)
);

-- fb_external_container 매니페스트 레지스트리 (SP-Ext.3 / ADR 0003 v2 + SP-1 v2 §6).
-- (name, version) 당 1 row. Hybrid 페어는 pair_id UUID 를 공유하고 단독 등록은 NULL 로 둔다.
-- 조회처: db_pipeline.py, db_synthesis.py (같은 msa_jfb DB 라 직접 SELECT).
-- 쓰기는 fb_external_container 의 MariaDBManifestRegistry.
-- ⚠️ 없으면 BFF 가 DB 연결에 성공해 MariaDB 레지스트리로 승격된 뒤 모든 매니페스트
--   쿼리가 실패한다 (in-memory 폴백은 연결 실패에만 걸린다 — main.py:89 참조).
CREATE TABLE IF NOT EXISTS external_container_manifest (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(63)  NOT NULL,
    version           VARCHAR(63)  NOT NULL,
    api_version       VARCHAR(63)  NOT NULL DEFAULT 'tango.acryl.ai/v1',
    job_type          VARCHAR(31)  NOT NULL,
    execution_mode    VARCHAR(31)  NOT NULL,
    image             VARCHAR(255) NOT NULL,
    service_family    VARCHAR(63),
    contract_version  VARCHAR(63),
    pair_id           CHAR(36),
    raw_yaml          TEXT         NOT NULL,
    raw_json          JSON         NOT NULL,
    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_name_version (name, version),
    INDEX idx_service_family (service_family),
    INDEX idx_pair_id (pair_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BFF JobTracker 상태 영속 (SP-Ext.3). BFF 재시작 시 in-flight partner job 을 복원한다.
-- terminal 도달 시 DELETE 하지 않고 status 만 갱신해 tombstone 으로 남긴다 (재시작 후
-- 조회가 404 대신 터미널 상태를 답해야 호출자가 폴링을 멈춘다). startup_recovery() 는
-- non-terminal row 만 복원하고, 보존기간 지난 tombstone 은 prune_terminal() 이 정리한다.
-- execution_mode=sync (infer 서빙) 은 persist 대상이 아니다 (lifecycle._db_persist 참조).
-- model_id 는 jonathan_llm.model.id 를 application-level 로 참조한다 (cross-schema FK 회피).
CREATE TABLE IF NOT EXISTS external_job_state (
    job_id            VARCHAR(64)  NOT NULL,
    model_id          INT(11)      DEFAULT NULL,
    workspace_id      INT(11)      NOT NULL,
    manifest_name     VARCHAR(128) NOT NULL,
    manifest_version  VARCHAR(64)  NOT NULL,
    manifest_json     LONGTEXT     NOT NULL,
    namespace         VARCHAR(128) NOT NULL,
    pod_name          VARCHAR(128) NOT NULL,
    helm_release      VARCHAR(128) NOT NULL,
    service_url       VARCHAR(256) NOT NULL,
    timeout_seconds   INT(11)      NOT NULL,
    params_json       LONGTEXT     NOT NULL,
    partner_job_id    VARCHAR(128) DEFAULT NULL,
    status            VARCHAR(32)  NOT NULL DEFAULT 'pending',
    output_subdir     VARCHAR(256) DEFAULT NULL,
    effective_gpu     INT(11)      NOT NULL DEFAULT 0,
    started_at        DATETIME     NOT NULL,
    updated_at        DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id),
    INDEX idx_status (status),
    INDEX idx_workspace (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;