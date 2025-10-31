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
	`name`	                VARCHAR(50) NOT	NULL,
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
    `main_storage_size`  BIGINT NOT NULL,
    `main_storage_id`  INT(11) NOT NULL,
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
	`name`	                VARCHAR(50),
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
	`name`	            VARCHAR(20)	NULL,
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
    `token`                 VARCHAR(100) NOT NULL,
    `last_call_datetime`    VARCHAR(20) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`,`user_id`,`token`),
    CONSTRAINT FOREIGN KEY (`user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `image` (
    `id`                    INT(11) NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `user_id`               INT(11) NOT NULL,
    `name`                  VARCHAR(50) NOT NULL,
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
	`name`	            VARCHAR(20)	NULL,
	`create_user_id`	INT(11)	NULL,
	`access`	        TINYINT(1)	NULL,
    `description`	    LONGTEXT DEFAULT NULL,
    `instance_id`       INT(11) NULL,
    `instance_allocate` INT(11) NULL,
	`create_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`	VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`workspace_id`, `name`),
    CONSTRAINT FOREIGN KEY (`workspace_id`) REFERENCES `msa_jfb`.`workspace` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `project_bookmark`(
    `project_id`         INT(11),
    `user_id`            INT(11),
    constraint foreign key (`project_id`) references `msa_jfb`.`project` (`id`) on update cascade on delete cascade,
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `training` (
	`id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`	        INT(11)	NOT NULL,
	`create_user_id`	    INT(11) NOT	NULL,
    `image_id`              INT(11),
	`name`	                VARCHAR(20)	NULL,
    `run_code`              LONGTEXT NOT NULL,
    `distributed_framework` VARCHAR(20)	NULL,  
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_count`             INT(11),
    `parameter`             LONGTEXT,
    `resource_group_id`     INT(11) NULL,
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
    `loss`                  VARCHAR(50),
    `accuracy`              VARCHAR(50),
	`create_datetime`	    VARCHAR(50)	DEFAULT CURRENT_TIMESTAMP(),
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `end_status`            VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    -- UNIQUE KEY(`project_id`, `name`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
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
	`tool_type`	            INT(11)	NOT NULL,
    `tool_index`            INT(11),
    `tool_password`         LONGTEXT,
    `gpu_count`             INT(11) DEFAULT 0,
    `gpu_cluster_auto`           TINYINT DEFAULT 0,
    `gpu_select`            JSON,
    `request_status`        TINYINT DEFAULT 0,
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    `pending_reason`           LONGTEXT,
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `hps_group` (
    `id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`project_id`		    INT(11) NOT NULL,
	`run_code`	            LONGTEXT NOT NULL,
	`run_parameter`	        LONGTEXT NOT NULL,
    `name`                  VARCHAR(50),
    `image_id`              INT(11),
    `create_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `update_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY(`id`),
    UNIQUE KEY(`project_id`, `name`),
    CONSTRAINT FOREIGN KEY (`project_id`) REFERENCES `msa_jfb`.`project` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`image_id`) REFERENCES `msa_jfb`.`image` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `hps` (
    `id`	                INT(11)	NOT NULL AUTO_INCREMENT,
	`hps_group_id`		    INT(11) NOT NULL,
    `hps_group_index`       INT(11) DEFAULT 0,
    `image_name`            LONGTEXT NOT NULL,
    `method`                INT(11) NOT NULL,
    `distributed_framework` VARCHAR(20)	NULL,
    `search_parameter`      LONGTEXT NOT NULL,
    `int_parameter`         LONGTEXT NOT NULL,
    `init_points`           INT(11),
    `search_count`          INT(11),
    `search_interval`       FLOAT,
    `resource_group_id`     INT(11),
    `resource_type`         VARCHAR(10) DEFAULT "CPU",
    `gpu_count`              INT(11),
    `gpu_cluster`           TINYINT DEFAULT 0,
    `save_file_name`        VARCHAR(100) NOT NULL,
    `load_file_name`        VARCHAR(100),
    `create_user_id`        INT(11) NOT NULL,
    `create_datetime`       VARCHAR(50) DEFAULT CURRENT_TIMESTAMP(),
    `end_status`            VARCHAR(50),
    `error_reason`             LONGTEXT,
    `pending_reason`           LONGTEXT,
    `start_datetime`        VARCHAR(50),
    `end_datetime`          VARCHAR(50),
    PRIMARY KEY(`id`),
    CONSTRAINT FOREIGN KEY (`hps_group_id`) REFERENCES `msa_jfb`.`hps_group` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FOREIGN KEY (`resource_group_id`) REFERENCES `msa_jfb`.`resource_group` (`id`) ON UPDATE CASCADE,
    CONSTRAINT FOREIGN KEY (`create_user_id`) REFERENCES `msa_jfb`.`user` (`id`) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS `deployment`(
    `id`                    INT(11)	NOT NULL AUTO_INCREMENT,
    `workspace_id`          INT(11),
    `name`                  varchar(50),
    `description`           varchar(1000),
    `create_datetime`       VARCHAR(50) DEFAULT current_timestamp(), 
    `access`                INT(11),
    `user_id`               INT(11),
    `instance_id`           INT(11),
    `instance_allocate`     INT(11),
    `instance_type`         varchar(20),
    `gpu_per_worker`        INT(11) default 0,
    `gpu_cluster_auto`      TINYINT DEFAULT 0,
    `gpu_auto_cluster_case`     longtext,
    `distributed_config_file` VARCHAR(200),
    `deployment_type`       varchar(20),
    `project_id`            INT(11),
    `training_type`         varchar(20),
    `training_id`           INT(11),
    `environments`          longtext,
    `command`               longtext,
    `image_id`              INT(11),
    `hps_number`            INT(11),
    `api_path`              varchar(100),
    PRIMARY KEY(`id`),
    constraint foreign key (`user_id`) references `msa_jfb`.`user` (`id`) on update cascade on delete cascade,
    constraint foreign key (`workspace_id`) references `msa_jfb`.`workspace` (`id`) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `deployment_worker`(
    `id`                INT(11)	NOT NULL AUTO_INCREMENT,
    `deployment_id`     INT(11),
    `description`       longtext,
    `instance_id`       INT(11),
    `gpu_per_worker`    INT(11),
    `instance_type`     varchar(20),
    `deployment_type`   varchar(20),
    `training_type`     varchar(20),
    `gpu_cluster_auto`  TINYINT DEFAULT 0,
    `project_id`        INT(11),
    `training_id`       INT(11),
    `command`           longtext,
    `environments`      longtext,
    `image_id`          INT(11),
    `create_datetime`   datetime default current_timestamp(),
    `start_datetime`    VARCHAR(50),
    `end_datetime`      VARCHAR(50),
    PRIMARY KEY(`id`),
    constraint deployment_worker_id_uindex unique (id),
    constraint foreign key (deployment_id) references deployment (id) on update cascade on delete cascade
);

CREATE TABLE IF NOT EXISTS `deployment_data_form` (
    `deployment_id`             INT(11) NOT NULL,
    `location`                  VARCHAR(11) NOT NULL COMMENT 'data location in API (body, args, file ...)',
    `method`                    VARCHAR(11) NOT NULL COMMENT 'api call method',
    `api_key`                   VARCHAR(11) NOT NULL COMMENT 'api key',
    `value_type`                VARCHAR(11) NOT NULL COMMENT 'api_key value',
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