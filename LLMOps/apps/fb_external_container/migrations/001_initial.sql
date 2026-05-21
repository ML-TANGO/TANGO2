-- 001_initial.sql — fb_external_container schema (SP-Ext.3)
--
-- Run as the application DB user on the platform's MariaDB:
--   mysql -h $DB_HOST -u $DB_USER -p $DB_NAME < 001_initial.sql
--
-- ADR 0003 v2 + SP-1 v2 §6 (manifest spec) — one row per (name, version).
-- Hybrid pairs share a non-NULL pair_id UUID; singletons leave pair_id NULL.

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
