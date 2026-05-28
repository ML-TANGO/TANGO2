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