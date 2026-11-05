import json
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class RegisterEdgeWorkerModel(BaseModel):
    # device_id 는 서버가 자동 생성(edge-<hex>) — 클라이언트 입력 없음(물리장비 heartbeat id는
    # 등록 후 Step2 에서 확인). 사람이 식별하는 유일 키는 name(필수·중복 불가, 서비스에서 체크).
    name: str = Field(..., min_length=1, max_length=128)
    device_type: Optional[str] = Field(default=None, max_length=32)
    # heartbeat push 모델에선 선택(remoteManager pull/deploy 경로에서만 사용). 값이 있으면 URL 검증.
    remote_manager_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://.+")


class DeployEdgeModel(BaseModel):
    # SP-6 / 3.10 — 양자화 패키지(GGUF)를 Edge 워커에 배포. image=기관 제공 Edge 실행 이미지.
    image: str = Field(..., min_length=1, max_length=512, pattern=r"^[A-Za-z0-9._:/@\-]+$")
    model_name: Optional[str] = Field(default=None, max_length=128)
    model_version: Optional[str] = Field(default=None, max_length=64)
    # SP-4 포팅 패키지 GGUF 경로(워크스페이스 NFS 상대경로). remoteManager 로 전달.
    gguf_path: Optional[str] = Field(default=None, max_length=512, pattern=r"^[A-Za-z0-9._/\-]+$")
    # SP-4 양자화 산출물 id(quantize_lineage.id). 이 값이 있으면 BE 가 **DB 에서**
    # 경로·워크스페이스를 해석해 아티팩트 URL 을 발급한다 — 클라이언트가 준 gguf_path
    # 문자열은 신뢰 체인에서 빠진다(gguf_path 는 하위호환 표시용으로만 남는다).
    # 없으면 종전대로 문자열만 전달(디바이스에 파일이 이미 있다고 가정).
    lineage_id: Optional[int] = Field(default=None, ge=1)
    # 이 배포를 낸 온디바이스 배포(playground, deploy_type='edge') id. 성공 시 워커에 새겨
    # 배포 목록 카드 상태·상세 재진입 선택 복원에 쓴다. 없으면 워커의 연결 표시를 비운다.
    playground_id: Optional[int] = Field(default=None, ge=1)
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


class HeartbeatModel(BaseModel):
    """기관 디바이스 → 플랫폼 자원/상태 보고 (규격 v1.0). 30초 주기."""
    timestamp: Optional[str] = Field(default=None, max_length=64)
    cpu_pct: Optional[float] = None
    gpu_pct: Optional[float] = None
    gpu_mem_gb: Optional[float] = Field(default=None, ge=0, le=1048576)
    gpu_mem_used_gb: Optional[float] = Field(default=None, ge=0, le=1048576)
    disk_gb: Optional[float] = Field(default=None, ge=0, le=1073741824)
    disk_used_gb: Optional[float] = Field(default=None, ge=0, le=1073741824)
    model_loaded: Optional[str] = Field(default=None, max_length=128)
    inference_count_total: Optional[int] = Field(default=None, ge=0, le=1000000000000)
    inference_latency_p50_ms: Optional[float] = Field(default=None, ge=0, le=3600000)
    inference_latency_p99_ms: Optional[float] = Field(default=None, ge=0, le=3600000)
    last_error: Optional[str] = Field(default=None, max_length=512)

    @field_validator("cpu_pct", "gpu_pct")
    @classmethod
    def _clamp_pct(cls, v):
        if v is None:
            return v
        return max(0.0, min(100.0, float(v)))
