# SDS-VLM MSA — API 인터페이스 명세

> **[아크릴 전달용 문서]**  
> 본 문서는 SDS-VLM 서비스를 Tango GenAI Platform(조나단)에 통합할 때 필요한  
> **학습 / 배포 / 추론** 전 과정의 API 스키마 및 연동 절차를 정의합니다.

---

## 1. 서비스 개요

| 항목 | 내용                                     |
|---|----------------------------------------|
| 서비스명 | `eva-vlm`                              |
| 버전 | `1.1.0`                                |
| 포트 | `8000`                                 |
| Ingress 경로 | `/msa/eva-vlm` (플랫폼 담당자와 협의 후 확정)      |
| 베이스 이미지 | `nvidia/cuda:12.8.0-devel-ubuntu24.04` |

### 전체 엔드포인트 요약

| 엔드포인트 | 메서드 | 조나단 MSA 표준 | 설명 |
|---|---|---|---|
| `/health` | GET | ✅ 필수 | 서비스·모델 상태 확인 |
| `/info` | GET | ✅ 필수 | 서비스 메타정보 |
| `/run` | POST | ✅ 필수 | **추론** — 이미지+AIS → 텍스트 |
| `/jobs/{job_id}` | GET | ✅ 표준 (E2-A) | **학습 진행 조회** — 플랫폼 표준 URL |
| `/jobs/{job_id}/cancel` | POST | ✅ 표준 (E2-A) | **학습 중지** — 플랫폼 표준 URL |
| `/train` | POST | 확장 | **학습 시작** — 비동기, HTTP 202, job_id 반환 |
| `/train/status` | GET | 확장 (레거시) | 학습 진행 조회 — 하위 호환 유지 |
| `/train/stop` | POST | 확장 (레거시) | 학습 중지 — 하위 호환 유지 |
| `/models` | GET | 확장 | **체크포인트 목록** |
| `/deploy` | POST | 확장 | **배포(체크포인트 전환)** |

---

## 2. 인프라 사전 준비

### NFS 볼륨 구조

플랫폼 NFS 스토리지에 아래 경로가 준비되어 있어야 합니다.

```
/nfs/eva/
├── models/
│   ├── llm/
│   │   └── Llama-3.1-8B-Instruct/   ← LLM 가중치 (~16GB)
│   ├── checkpoints/                  ← 학습 결과 체크포인트 저장 위치
│   │   ├── sds_lora_ko_compact/      ← 예시 (projector.bin + LoRA)
│   │   └── ...
│   └── hf_cache/                    ← (선택) CLIP 오프라인 캐시
└── data/
    └── sds/                         ← SDS 학습 데이터셋
        └── 20260227/
            ├── 00001/
            │   ├── input_image.png
            │   ├── input_data.csv
            │   └── output_*.txt
            └── ...
```

### 필수 환경 변수

| 변수명 | 예시 | 설명 |
|---|---|---|
| `EVA_LLM_MODEL_PATH` | `/models/llm/Llama-3.1-8B-Instruct` | LLM 경로 (필수) |
| `EVA_CHECKPOINT_PATH` | `/models/checkpoints/sds_lora_ko_compact` | 초기 체크포인트 (필수) |
| `EVA_CHECKPOINTS_ROOT` | `/models/checkpoints` | 체크포인트 탐색 루트 |
| `EVA_VISION_MODEL_NAME` | `openai/clip-vit-large-patch14-336` | 비전 인코더 |
| `EVA_DEVICE` | `cuda:0` | 추론 디바이스 |

---

## 3. 표준 엔드포인트

### GET /health

**Response**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-12T10:00:00+00:00",
  "model_loaded": true,
  "device": "cuda:0",
  "vram_used_gb": 18.4
}
```

`status` 값: `"healthy"` | `"loading"` | `"error"`

> 모델 로드 시간 ~2분 → `initialDelaySeconds: 120` 이상 설정 필요

---

### GET /info

**Response**
```json
{
  "name": "eva-vlm",
  "version": "1.0.0",
  "description": "...",
  "capabilities": [
    "maritime-vlm-training",
    "checkpoint-management",
    "maritime-situation-description",
    "navigational-advice",
    "ais-image-fusion",
    "colreg-reasoning"
  ],
  "vision_model": "openai/clip-vit-large-patch14-336",
  "llm_model": "/models/llm/Llama-3.1-8B-Instruct",
  "checkpoint": "/models/checkpoints/sds_lora_ko_compact",
  "output_types": [
    "영문 해상상황묘사",
    "한글 해상상황묘사",
    "영문 항해조력메시지",
    "한글 항해조력메시지",
    "간결 항해조력메시지"
  ]
}
```

---

### POST /run — 추론

**Request**
```json
{
  "workspace_id": "ws-abc123",
  "project_id": "proj-def456",
  "params": {
    "image_base64": "<base64 PNG/JPG>",
    "ais_rows": [
      {
        "ship_id": 0, "my_ship": 1,
        "latitude": 34.45, "longitude": 127.73,
        "knot": 17.5, "heading": 141.0,
        "length": 93, "width": 28, "draft": 3
      },
      {
        "ship_id": 1, "my_ship": 0,
        "latitude": 34.44, "longitude": 127.73,
        "knot": 20.1, "heading": 115.0,
        "length": 134, "width": 24, "draft": 4,
        "bbox_x": 975, "bbox_y": 318, "bbox_width": 408, "bbox_height": 263
      }
    ],
    "output_type": "간결 항해조력메시지",
    "max_new_tokens": 512,
    "repetition_penalty": 1.1,
    "do_sample": false
  }
}
```

`output_type` 선택지: `"영문 해상상황묘사"` | `"한글 해상상황묘사"` | `"영문 항해조력메시지"` | `"한글 항해조력메시지"` | `"간결 항해조력메시지"`

**Response (성공)**
```json
{
  "status": "success",
  "result": {
    "output_type": "간결 항해조력메시지",
    "text": "우현 전방 타선(ID:1) 접근 중...",
    "inference_time_sec": 12.3,
    "active_checkpoint": "/models/checkpoints/sds_lora_ko_compact"
  }
}
```

---

## 4. 확장 엔드포인트 — 학습

### POST /train — 학습 시작

SDS-VLM의 학습 파이프라인을 비동기로 실행합니다. 즉시 `job_id`를 반환하고 백그라운드에서 학습을 진행합니다.

**Request**
```json
{
  "workspace_id": "ws-abc123",
  "project_id": "proj-def456",
  "params": {
    "phase": "lora_sds",
    "llm_model_path": "/models/llm/Llama-3.1-8B-Instruct",
    "output_checkpoint_name": "sds_lora_ko_compact_v2",
    "data_path": "/data/sds/sds_train_ko_compact.json",
    "image_dir": "/data/sds/20260227",
    "projector_path": "/models/checkpoints/clip_llama31_lora_marine/projector.bin",
    "resume_lora_path": "/models/checkpoints/clip_llama31_lora_marine",
    "sds_scenario": "ko_compact",
    "num_epochs": 10,
    "batch_size": 1,
    "grad_accum": 2,
    "learning_rate": 0.0002,
    "zero_stage": 2
  }
}
```

**params.phase 선택지**

| phase | 학습 스크립트 | 주요 입력 | 설명                   |
|---|---|---|----------------------|
| `projector` | `train.py` | `data_path`, `image_dir` | Phase 1: 프로젝터 사전학습   |
| `lora` | `train.py` | `data_path`, `image_dir`, `projector_path` | Phase 2: CC3M LoRA   |
| `lora_marine` | `train_text_lora.py` | `marine_data_path`, `resume_lora_path` | Phase 3: 해양 텍스트 계속학습 |
| `lora_sds` | `train.py` | `data_path`, `image_dir`, `projector_path`, `resume_lora_path` | Phase 4: SDS 특화 LoRA |

**Response (성공, HTTP 202 Accepted)**
```json
{
  "status": "success",
  "result": {
    "job_id": "a1b2c3d4",
    "message": "Phase 'lora_sds' 학습이 시작됐습니다. GET /jobs/a1b2c3d4 로 진행 상황을 확인하세요."
  }
}
```

---

### GET /jobs/{job_id} — 학습 진행 조회 (표준 URL)

조나단 플랫폼 표준 URL입니다. 기존 `/train/status?job_id=` 와 동일한 응답을 반환합니다.

**Response**
```json
{
  "job_id": "a1b2c3d4",
  "status": "running",
  "phase": "lora_sds",
  "progress_pct": 42.5,
  "current_step": 34,
  "total_steps": 80,
  "current_loss": 0.3821,
  "elapsed_sec": 387.2,
  "output_dir": "/models/checkpoints/sds_lora_ko_compact_v2",
  "error": null
}
```

`status` 값: `"pending"` | `"running"` | `"completed"` | `"failed"` | `"stopped"`

---

### POST /jobs/{job_id}/cancel — 학습 중지 (표준 URL)

조나단 플랫폼 표준 URL입니다. 기존 `/train/stop?job_id=` 와 동일하게 동작합니다.

**Response**
```json
{
  "status": "success",
  "job_id": "a1b2c3d4",
  "message": "학습 작업이 중지됐습니다."
}
```

---

### GET /train/status?job_id={job_id} — 학습 진행 조회 (레거시)

> **하위 호환 유지용.** 신규 연동은 `GET /jobs/{job_id}` 사용 권장.

**Response**
```json
{
  "job_id": "a1b2c3d4",
  "status": "running",
  "phase": "lora_sds",
  "progress_pct": 42.5,
  "current_step": 34,
  "total_steps": 80,
  "current_loss": 0.3821,
  "elapsed_sec": 387.2,
  "output_dir": "/models/checkpoints/sds_lora_ko_compact_v2",
  "error": null
}
```

`status` 값: `"pending"` | `"running"` | `"completed"` | `"failed"` | `"stopped"`

---

### POST /train/stop?job_id={job_id} — 학습 중지 (레거시)

> **하위 호환 유지용.** 신규 연동은 `POST /jobs/{job_id}/cancel` 사용 권장.

**Response**
```json
{
  "status": "success",
  "job_id": "a1b2c3d4",
  "message": "학습 작업이 중지됐습니다."
}
```

---

## 5. 확장 엔드포인트 — 배포

### GET /models — 체크포인트 목록

NFS 체크포인트 루트를 스캔하여 `projector.bin`이 있는 유효한 체크포인트 목록을 반환합니다.

**Response**
```json
{
  "checkpoints_root": "/models/checkpoints",
  "active_checkpoint": "/models/checkpoints/sds_lora_ko_compact",
  "checkpoints": [
    {
      "name": "clip_llama31_lora",
      "path": "/models/checkpoints/clip_llama31_lora",
      "has_lora": true,
      "size_mb": 432.1,
      "created_at": "2026-04-15T08:30:00+00:00",
      "is_active": false
    },
    {
      "name": "sds_lora_ko_compact",
      "path": "/models/checkpoints/sds_lora_ko_compact",
      "has_lora": true,
      "size_mb": 438.7,
      "created_at": "2026-05-01T14:20:00+00:00",
      "is_active": true
    }
  ]
}
```

---

### POST /deploy — 체크포인트 전환(배포)

학습 완료된 체크포인트를 추론 엔진에 로드합니다. 기존 모델을 GPU에서 해제하고 새 체크포인트를 적재합니다.

> **주의:** 로드 시간 ~2분 소요. 로드 중 `/run` 추론은 `SERVICE_UNAVAILABLE` 응답.

**Request**
```json
{
  "workspace_id": "ws-abc123",
  "project_id": "proj-def456",
  "params": {
    "checkpoint_name": "sds_lora_ko_compact_v2"
  }
}
```

**Response (성공)**
```json
{
  "status": "success",
  "checkpoint_path": "/models/checkpoints/sds_lora_ko_compact_v2",
  "device": "cuda:0",
  "vram_used_gb": 18.6,
  "message": "체크포인트 'sds_lora_ko_compact_v2' 로드 완료."
}
```

---

## 6. 에러 코드

| 코드 | HTTP | 설명 |
|---|---|---|
| `INVALID_PARAMS` | 400 | 필수 필드 누락 또는 형식 오류 |
| `NOT_FOUND` | 404 | 지정한 체크포인트/job_id 없음 |
| `RESOURCE_EXHAUSTED` | 429 | 이미 학습 중 (GPU 1장 환경 제약) |
| `SERVICE_UNAVAILABLE` | 503 | 모델 로드 미완료 또는 전환 중 |
| `INTERNAL_ERROR` | 500 | 내부 오류 |

---

## 7. 조나단 UI 연동을 위한 아크릴 작업 범위

SDS-VLM의 학습/배포/추론을 조나단 대시보드에서 직접 제어하려면 아크릴 측 UI 작업이 필요합니다.

| 조나단 UI 화면 | 에바 연동 내용 | 호출 API |
|---|---|---|
| 학습 프로젝트 | SDS-VLM 학습 시작/중지/진행률 표시 | `POST /train`, `GET /jobs/{job_id}`, `POST /jobs/{job_id}/cancel` |
| 모델 관리 | 체크포인트 목록 및 현재 활성 모델 표시 | `GET /models` |
| 배포 | 체크포인트 선택 후 서비스 적용 | `POST /deploy` |
| 플레이그라운드 | 이미지+AIS 입력 → 추론 결과 | `POST /run` |

---

## 8. Helm Chart 설치 명령

```bash
helm install eva-vlm-1 ./helm_chart/ \
  -n tango-eva --create-namespace \
  --set metadata.namespace=tango-eva \
  --set metadata.workspace_id=<워크스페이스_ID> \
  --set metadata.project_id=<프로젝트_ID> \
  --set metadata.pod_name=eva-vlm-1 \
  --set labels.helm_name=eva-vlm-1 \
  --set backend.image=yvvyee/eva-vlm-backend:1.1.0 \
  --set "backend.env.EVA_LLM_MODEL_PATH=/models/llm/Llama-3.1-8B-Instruct" \
  --set "backend.env.EVA_CHECKPOINT_PATH=/models/checkpoints/sds_lora_ko_compact" \
  --set "backend.env.EVA_CHECKPOINTS_ROOT=/models/checkpoints" \
  --set backend.volumes[0].nfs.server=<NFS_SERVER_IP> \
  --set backend.volumes[0].nfs.path=/nfs/eva/models \
  --set ingress.enabled=true
```

---
