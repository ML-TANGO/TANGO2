import json
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class RegisterEdgeWorkerModel(BaseModel):
    # device_id 는 식별자(파일/레이블 아님)지만 안전 문자만.
    device_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._\-]+$")
    name: Optional[str] = Field(default=None, max_length=128)
    device_type: Optional[str] = Field(default=None, max_length=32)
    sdx_domain: Optional[str] = Field(default=None, max_length=64)
    remote_manager_url: str = Field(..., min_length=1, max_length=512, pattern=r"^https?://.+")


class DeployEdgeModel(BaseModel):
    # SP-6 / 3.10 — 양자화 패키지(GGUF)를 Edge 워커에 배포. image=기관 제공 Edge 실행 이미지.
    image: str = Field(..., min_length=1, max_length=512, pattern=r"^[A-Za-z0-9._:/@\-]+$")
    model_name: Optional[str] = Field(default=None, max_length=128)
    model_version: Optional[str] = Field(default=None, max_length=64)
    # SP-4 포팅 패키지 GGUF 경로(워크스페이스 NFS 상대경로). remoteManager 로 전달.
    gguf_path: Optional[str] = Field(default=None, max_length=512, pattern=r"^[A-Za-z0-9._/\-]+$")
    params: Optional[dict] = None

    @field_validator("gguf_path")
    @classmethod
    def _no_traversal(cls, v):
        # 정규식이 '.'·'/'를 허용하므로 '..'·절대경로·빈 컴포넌트를 별도 차단(경로조작).
        if v is None:
            return v
        if v.startswith("/"):
            raise ValueError("gguf_path must be a relative path")
        if any(p in ("", ".", "..") for p in v.split("/")):
            raise ValueError("gguf_path must not contain '.', '..', or empty path components")
        return v

    @field_validator("params")
    @classmethod
    def _cap_params(cls, v):
        # remoteManager 로 그대로 전달 → admin DoS(과대/심층) 방지로 직렬화 크기 제한.
        if v is not None and len(json.dumps(v)) > 4096:
            raise ValueError("params too large (max 4096 bytes)")
        return v


class CustomLabelModel(BaseModel):
    target_type: str = Field(..., pattern=r"^(node|edge_worker)$")
    # node 이름 / edge device_id — 안전 문자만(orphan/이상 데이터 방지).
    target_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._/\-]+$")
    label_key: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._/\-]+$")
    label_value: Optional[str] = Field(default=None, max_length=255)
