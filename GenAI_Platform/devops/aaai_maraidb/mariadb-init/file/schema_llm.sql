CREATE DATABASE IF NOT EXISTS `jonathan_llm`;
USE `jonathan_llm`;

CREATE TABLE IF NOT EXISTS `playground` (
    `id`                    INT(11) NOT NULL AUTO_INCREMENT,
    `name`                  VARCHAR(32),
    `workspace_id`          INT(11),
    `create_user_id`        INT(11),
    `access`                INT(11),
    `description`           VARCHAR(5000),
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
