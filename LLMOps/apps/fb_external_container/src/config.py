"""Service configuration via pydantic-settings.

Env vars follow the JF_* and platform conventions already used by other
fb_* services (see apps/fb_utils/settings.py). New names introduced here
are documented inline.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MariaDB (manifest registry, job state). The aliases match the
    # platform's existing `jfb-settings` ConfigMap so this service can use
    # `envFrom: configMapRef: jfb-settings` without per-key remapping.
    db_host: str = Field(default="localhost", alias="JF_DB_HOST")
    db_port: int = Field(default=3306, alias="JF_DB_PORT")
    db_user: str = Field(default="root", alias="JF_DB_USER")
    # jfb-settings stores the password under JF_DB_PW (not _PASSWORD).
    db_password: str = Field(default="", alias="JF_DB_PW")
    db_name: str = Field(default="msa_jfb", alias="JF_DB_NAME")

    # fb_scheduler s2s endpoint — launch / cleanup trigger. Override per env
    # via JF_FB_SCHEDULER_URL when the scheduler lives outside jonathan-system.
    fb_scheduler_url: str = Field(
        default="http://jfb-app-scheduler-svc.jonathan-system.svc.cluster.local:80",
        alias="JF_FB_SCHEDULER_URL",
    )

    # llm_model BFF — auto commit hook target. terminal=COMPLETED 시
    # POST {llm_model_bff_url}/api/models/{model_id}/external-commit 호출.
    # Override per env via JF_LLM_MODEL_BFF_URL.
    llm_model_bff_url: str = Field(
        default="http://jfb-llm-model-svc.jonathan-system.svc.cluster.local:80",
        alias="JF_LLM_MODEL_BFF_URL",
    )

    # HTTP client to partner pods (cluster-internal ClusterIP).
    # Timeout is intentionally generous: SP-1 v2 §5.3 allows sync /run up to
    # 5 minutes and partner /info responses can be slow during cold-start.
    partner_http_timeout_seconds: float = 300.0

    # Polling cadence for async jobs (SP-Ext.8). 5s is the floor; lifecycle
    # raises this back off as partner runtime stretches.
    poll_interval_seconds: float = 5.0

    log_level: str = "INFO"

    # populate_by_name lets tests / direct construction also use the field
    # name (db_host=...) instead of the alias.
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
