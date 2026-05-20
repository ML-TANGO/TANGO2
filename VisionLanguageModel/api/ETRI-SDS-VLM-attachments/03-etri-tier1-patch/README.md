# ETRI eva-vlm-backend:1.0.0 — Tier 1 패치 (acryl 2026-05-19 갱신)

`docs/superpowers/reviews/2026-05-12-ETRI-SDS-VLM-API-review.md` §11 의 Tier 1
4건 + 1.0.0 cluster 탑재 검증 중 발견한 4건 추가, 총 8건 패치 후보.

## 검증된 fix (3건, Tier 1 원래 4건 중 #1~#3)

| # | 항목 | 패치 위치 | 클러스터 검증 결과 |
|---|---|---|---|
| **Tier1 #1** | `flash-attn` 미설치 | `Dockerfile.fork` 의 `pip install flash-attn==2.7.0.post2 --no-build-isolation` | base image 의 torch 2.5.1+cu124 + nvcc 12.4 에서 source build 정상 (~5~10분) |
| **Tier1 #2** | `train_manager.py:134` `_monitor_log` deadlock | `train_manager.patch` (unified diff) | **before**: subprocess 5초 만에 죽어도 `/train/status` 가 영원히 `running`. **after**: 9초 안에 `failed` + 종료 코드 노출 ✅ |
| **Tier1 #3** | subprocess 자식 그룹 격리 부재 | `train_manager.patch` 의 `start_new_session=True` | uvicorn 부모가 SIGTERM 받을 때 자식 그룹 정리 가능 |

## 1.0.0 후속 검증 중 추가 발견 (5건)

| # | 항목 | 권장 fix | 영향도 |
|---|---|---|---|
| **Tier1 #4** | HTTP 200 일관 — `global_exception_handler` 는 이미 500 반환 | 일부 RuntimeError 경로 (예: `train_manager.start()` 의 "이미 실행 중" 응답) 의 HTTP status 점검 권장 | 일부 ETRI 측 fix, 단 platform `ETRIAdapter` 가 HTTP 200 + `status:"ERROR"` body 도 흡수하도록 작성되어 단기는 cover 가능 |
| **Tier1 #5** | startup model load 시 `projector.bin` 부재로 traceback 출력 | 두 옵션:<br>(a) `model_manager.load()` 에서 사전 `os.path.exists` 체크 후 graceful skip<br>(b) `EVA_SKIP_INITIAL_LOAD=1` env-gate (학습 컨테이너에서 set) | **service 영향 0** (이미 try/except 로 graceful). 단순 운영자 log 가 조용해짐 |
| **Tier1 #6** | `/app/vlm/demo/` Gradio 데모 production-ready 아님 | `requirements.txt` 에 `gradio` 추가 + `demo/run.sh` 의 PYTHON 경로 (`/home/ywlee/...`) → `python3` + `demo/app.py` 의 `DEFAULT_DATASET_PATH/DEFAULT_LLM_MODEL` hard-coded local path → env 화 | demo image 자체 띄우려면 필요. 현재 platform UI 는 자체 frontend (flightbase-fe) 로 모니터링 — demo 는 ETRI 자체 개발 검증용. |
| **Tier1 #7** | torch CVE-2025-32434 mitigation 으로 `CLIPVisionModel.from_pretrained` 가 ValueError | base image 의 torch 를 **v2.6+ 로 업그레이드**, 또는 HF Hub 로부터 model 의 safetensors 형식 강제 다운로드 (`use_safetensors=True`) | **학습 launch 가 vision encoder 로드 단계에서 차단됨** — Tier 1 #1~3 이 fix 돼도 진짜 학습 안 시작. 핵심 blocker. |
| **Tier1 #8** | TensorBoard scalar 미출력 (`report_to = "wandb" or "none"`) | `train.py.tensorboard.patch` — `report_to` 에 `["tensorboard"]` 추가 + `requirements.txt` 에 `tensorboard>=2.14` 추가 | platform 의 frontend graph (loss/lr/eval curve) 가 외부 학습에도 동작하려면 필요. ETRI 의 W&B 와 공존 가능 (둘 다 list 에 추가). |

## 클러스터 자체 검증 환경

- ETRI image: `docker.io/yvvyee/eva-vlm-backend:1.0.0` (digest `sha256:4f0fd975...`)
- Base: nvidia/cuda:12.4.1 + python 3.11 + torch 2.5.1+cu124
- 검증 cluster: K8s v1.30 single-node, GPU 2x RTX A6000
- 검증 namespace: jonathan-system-3
- platform stack: fb_external_container (manifest+lifecycle) + fb_scheduler (helm install) + llm_model BFF (SSE relay to flightbase-fe)

## platform 측 통합 상태 (참고)

ETRI 측 fix 무관하게 platform 측에서 다음이 이미 완성됨:

- ETRI `/train`, `/train/status`, `/train/stop` 모두 정상 호출 (Tier1 #2 patch 적용 시 진짜 status 갱신 확인됨)
- ETRI 의 응답 schema (`{result: {job_id, message}}` 의 nested job_id 추출 등) 흡수
- flightbase-fe 의 internal LLM fine-tuning SSE 훅 (`useSSEStatus`, `useSSEFinetuningTime`, `useSSEGraph`, `FineTuningSystemLogModal`) 이 외부 학습용 BFF endpoint 와도 호환되도록 schema 통일
- Tier1 #7 (torch CVE) 또는 #8 (TensorBoard) 가 fix 되면 graph 차트도 자동 채워짐

## 권장 적용 순서 (ETRI 측)

1. **#7 (torch CVE) 최우선**: 학습 자체가 막힘. base image upgrade 또는 safetensors 강제.
2. **#1~#3 (Tier 1 본래 3건)**: 우리 측 패치 그대로 채택 권장. 검증 완료.
3. **#8 (TensorBoard)**: ETRI 의 W&B 운용 영향 없이 추가 가능.
4. **#4~#6**: 운영 cosmetic, ETRI 우선순위에 따라.

## 파일 목록

| 파일 | 내용 |
|---|---|
| `train_manager.original.py` | ETRI 1.0.0 원본 |
| `train_manager.patched.py` | Tier1 #2 + #3 적용 결과 |
| `train_manager.patch` | unified diff (27 line, +22/-5) |
| `train.py.tensorboard.patch` | Tier1 #8 reference patch |
| `Dockerfile.fork` | acryl 측 fork image 빌드 reference (Tier1 #1~#3 적용) |
| `README.md` | 이 문서 |

## 사용한 패치 적용 방법 (개발자 참조)

```bash
# 1. Tier1 #2+#3 patch 적용
patch -p0 < train_manager.patch
# 또는 train_manager.py 를 train_manager.patched.py 로 교체

# 2. Tier1 #1 (flash-attn) — Dockerfile 의 RUN 단계 추가
RUN pip install --no-cache-dir 'ninja>=1.11' 'packaging>=23.0' \
    && pip install --no-cache-dir 'flash-attn==2.7.0.post2' --no-build-isolation

# 3. Tier1 #7 (torch CVE) — 두 선택지
# (a) torch 2.6+ 로 업그레이드
RUN pip install --no-cache-dir 'torch>=2.6' 'transformers' 'peft' 'accelerate'

# (b) 또는 safetensors 강제 (vision_encoder.py 의 from_pretrained 호출 수정)
# self.model = CLIPVisionModel.from_pretrained(model_name, torch_dtype=torch_dtype, use_safetensors=True)

# 4. Tier1 #8 (TensorBoard) — train.py patch 적용
patch -p0 < train.py.tensorboard.patch
# + requirements.txt 에 추가:
echo 'tensorboard>=2.14' >> /app/requirements.txt
```
