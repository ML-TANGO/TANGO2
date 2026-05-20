# SDS-VLM MSA API — 상세 리뷰 결과 (ETRI 전달용)

- **작성일**: 2026-05-13
- **용도**: 회신 메일 첨부 — P0/P1/P2 finding 36건 · 해결안 · 코드 예시 · ETRI 측 Tier 별 작업 항목
- **참고 spec**: SP-1 외부 컨테이너 계약 v2 (`docs/external-container-spec.md`, 2026-05-13 갱신)
- **검토 방법**: Claude 1차 리뷰 + OpenAI Codex (gpt-5.5) 독립 cross-review + 독립 Claude agent fresh review + docker pull yvvyee/eva-vlm-backend:1.0.0 직접 실증 (flash-attn ImportError 등)

---

## 그룹 A. PoC 부팅 차단 사항 (4건, Tier 1)

### A1. flash-attn 패키지 누락 — 실증 확인 완료

- **위치**: `model/vlm_v2.py:323,330` 이 `attn_implementation="flash_attention_2"`를 강제하지만 `api/requirements.txt` 에 flash-attn 이 없음.
- **실증 결과** (`docker pull yvvyee/eva-vlm-backend:1.0.0` 후 직접 검증):
  ```
  # docker run --rm yvvyee/eva-vlm-backend:1.0.0 python -c "import flash_attn"
  ModuleNotFoundError: No module named 'flash_attn'

  # transformers 5.3.0 + attn_implementation="flash_attention_2" 강제 시:
  ImportError: FlashAttention2 has been toggled on, but it cannot be used due
  to the following error: the package flash_attn seems to be not installed.
  ```
- **lifespan 시퀀스**: `projector.bin` 존재 확인 → `build_model()` 진입 → `LlamaForCausalLM.from_pretrained(..., attn_implementation="flash_attention_2")` → 위 ImportError. fallback 없음.
- **해결**: requirements 에 flash-attn 추가, 또는 `vlm_v2.py` 에 sdpa/eager fallback. RTX 5090 + bf16 + transformers 5.3 조합의 wheel 빌드는 ETRI 환경에서 검증되셨을 테니 wheel pin 정보 공유 부탁드립니다.

### A2. 학습 작업 종료 deadlock

- **위치**: `train_manager.py:134-137` 의 `asyncio.gather(process.wait(), _monitor_log(job))`.
- **문제**: `_monitor_log` 는 `while job.status == "running"` 루프인데, status 는 gather 완료 후에야 변경. 학습 subprocess 가 정상 종료해도 monitor 가 루프를 못 빠져나와 gather 가 영원히 await → `/train/status` 가 영원히 running, `_running_job_id` 점유로 다음 학습 영구 차단됨 (pod 재시작 외 복구 불가).
- **해결**: monitor 루프 종료 조건을 `process.returncode` 와 연동.

### A3. /train/stop 의 자식 프로세스 그룹 격리 부재

- **위치**: `train_manager.py:125-130`.
- **문제**: 자식 프로세스를 새 process group 으로 시작하지 않아, SIGTERM 이 부모 Python 만 죽이고 DeepSpeed/torchrun 자식들이 GPU 를 점유한 채 남음. 다음 학습은 OOM 또는 CUDA device busy 로 실패.
- **해결**: subprocess 생성 시 `start_new_session=True` 옵션 + 중지 시 `os.killpg(os.getpgid(pid), SIGTERM)` 으로 process group 전체에 시그널 송신.

### A4. 동시 /train 요청 race

- **위치**: `train_manager.py:69-74` 의 `has_running_job`.
- **문제**: `status == "running"` 만 체크하는데, `start()` 에서 `_running_job_id` 설정 직후 status 는 아직 "pending". 두 번째 `/train` 이 ms 단위로 도착하면 통과 → 단일 GPU 에 두 학습 충돌 → 즉시 CUDA OOM.
- **해결**: `has_running_job` 을 `_running_job_id is not None` 으로 변경.

### A5. torch.load CVE-2025-32434 mitigation — CLIPVisionModel.from_pretrained 차단 🔴

- **2026-05-19 cluster 탑재 검증 중 발견**. A1~A4 패치 적용 후에도 학습 launch 가 vision encoder 로드 단계에서 100% 차단되어 우선순위 최상.
- **위치**: `model/vision_encoder.py:53` 의 `CLIPVisionModel.from_pretrained(model_name, torch_dtype=...)`.
- **현상**:
  ```
  ValueError: Due to a serious vulnerability issue in `torch.load`, even with
  `weights_only=True`, we now require users to upgrade torch to at least v2.6
  in order to use the function. This version restriction does not apply when
  loading files with safetensors.
  See https://nvd.nist.gov/vuln/detail/CVE-2025-32434
  ```
- **원인**: base image 의 `torch==2.5.1+cu124`. transformers 가 `.bin` 형식 체크포인트를 load 할 때 weights_only=True 라도 v2.6+ 강제. CLIP weight 가 `.bin` 으로 mirror 되면 적용됨.
- **해결** (두 옵션, 운영 환경에서는 (a) 권장):
  - **(a) base image 의 torch 업그레이드**:
    ```dockerfile
    RUN pip install --no-cache-dir 'torch>=2.6' 'transformers' 'peft' 'accelerate'
    ```
  - **(b) safetensors 강제** (HF Hub 에 safetensors 버전 있는 모델만 동작):
    ```python
    # vision_encoder.py:53 + 동일하게 LLM 로드 부분도
    self.model = CLIPVisionModel.from_pretrained(model_name, torch_dtype=torch_dtype, use_safetensors=True)
    ```

---

## 그룹 B. API 계약/멀티테넌시 (4건, Tier 2)

### B1. 에러 응답 HTTP 상태 코드 — 일부 경로가 여전히 200 반환 (2026-05-19 실측 갱신)

`global_exception_handler` 는 500 으로 수정되어 있고 (확인 감사드립니다), FastAPI 의 body validation 경로 (422) 도 정상이지만, 다음 3 경로가 1.0.0 image 직접 호출 결과 여전히 200 반환:

| 경로 | 현행 응답 (실측) | 권장 |
|---|---|---|
| `POST /train` (이미 실행 중) | HTTP **200** + `{"status":"error","code":"RESOURCE_EXHAUSTED","message":"이미 실행 중인 학습..."}` | **409 Conflict** 또는 **429 Too Many Requests** |
| `GET /train/status?job_id=<미존재>` | HTTP **200** + `{"status":"failed","message":"job_id ... 를 찾을 수 없습니다"}` | **404 Not Found** |
| `POST /train/stop?job_id=<미존재>` | HTTP **200** + `{"status":"error","message":"'job_id를 찾을 수 없습니다: ...'"}` | **404 Not Found** |

`API_SCHEMA.md §6` 표는 400/404/429/500/503 으로 명시되어 있어 명세-구현 불일치이며, Kong 의 회로 차단·재시도·모니터링이 위 3 경로에서 정상 동작하지 않습니다. "실패한 job" 과 "없는 job" 을 클라이언트가 구분할 수 없는 issue 도 #2 에 해당.

- **해결**:
  ```python
  # train_manager.start() 의 RuntimeError 를 잡는 곳
  if self.has_running_job:
      raise HTTPException(status_code=429, detail={
          "code": "RESOURCE_EXHAUSTED",
          "message": "이미 실행 중인 학습 작업이 있습니다: ..."
      })

  # /train/status 의 미존재 job_id
  job = self._jobs.get(job_id)
  if job is None:
      raise HTTPException(status_code=404, detail={
          "code": "JOB_NOT_FOUND",
          "message": f"job_id '{job_id}' 를 찾을 수 없습니다"
      })

  # /train/stop 의 미존재 job_id
  # 동일 패턴
  ```
- **참고**: 우리 측 BFF (`apps/fb_external_container/src/adapter/etri_vlm.py`) 가 HTTP 200 + body 의 status:"ERROR" 도 흡수하도록 작성되어 단기적으로는 cover 가능. 단 정합·재시도 정책의 안전을 위해 ETRI 측 fix 권장.

### B2. /health probe 의미 분리 필요

- `model_loaded=False` 일 때도 200 을 반환합니다. `external-container-spec.md §5.2` 의 probe semantics 분리 의무에 따라 미준비 시 503, 가능하면 `/live` (liveness 전용) 분리 부탁드립니다.
- 그렇지 않으면 cold-start 2~5분 동안 K8s 가 트래픽을 흘려보내거나, 반대로 liveness probe 가 pod 를 restart 시켜 무한 루프.

### B3. /run 과 /deploy 의 cross-endpoint 동시성 충돌

- FastAPI 의 sync route (`def`, not `async def`) 는 threadpool 에서 병렬 실행됩니다. `/deploy` 가 `_unload()` 로 `self._model = None` 으로 만든 직후 `/run` 이 `generate()` 를 호출하면 AttributeError 또는 CUDA illegal memory access 로 프로세스 사망.
- **해결**: `ModelManager` 에 `threading.RLock` 하나를 두고 infer/load/unload 를 같은 락으로 직렬화.

### B4. Request body size cap 부재

- `image_base64` / `ais_rows` / `max_new_tokens` 어디에도 상한 없음. 1GB base64 페이로드, PIL decompression bomb (작은 PNG 가 디코딩 후 수십 GB), `max_new_tokens=1000000` 같은 입력으로 즉시 OOM 또는 GPU 영구 점유 가능.
- **해결**: Pydantic Field `max_length` / `max_items` / `le` 제약 + FastAPI body size 미들웨어 + `PIL.Image.MAX_IMAGE_PIXELS` 설정.

### B5. TensorBoard scalar 미출력 — `report_to = "wandb" or "none"` (모니터링 연동)

- **2026-05-19 cluster 탑재 검증 중 발견**. 플랫폼 측 frontend (flightbase-fe) 의 학습 그래프 UI 가 internal LLM 학습용으로 `parse_tensorboard_scalars_async` 통해 `output_dir/runs/...` 의 event 파일을 읽는데, 외부 학습도 같은 path 로 자동 연동되려면 ETRI 의 trainer 가 TensorBoard scalar 를 출력해야 합니다.
- **위치**: `train.py:362`.
- **현 상태**:
  ```python
  report_to = "wandb" if args.wandb_project else "none"
  ```
- **해결**: ETRI 의 `VLMTrainer` 가 HuggingFace `Trainer` 의 thin wrapper 이므로 `TrainingArguments.report_to` 에 `"tensorboard"` 만 추가하면 `train/loss`, `train/learning_rate`, `train/grad_norm`, `eval/loss` 등 표준 scalar 가 자동 출력됩니다. W&B 와 공존 가능 (둘 다 list 에 추가):
  ```python
  report_to: list[str] = []
  if args.wandb_project: report_to.append("wandb")
  if not getattr(args, "no_tensorboard", False): report_to.append("tensorboard")
  if not report_to: report_to = "none"
  ```
  + `requirements.txt` 에 `tensorboard>=2.14` 추가.
- **이점**: phase 별 (`projector` / `lora` / `lora_marine` / `lora_sds`) 로 별도 `output_dir/runs/{timestamp}/` 디렉토리에 자연스럽게 multi-run 저장 → flightbase-fe 의 그래프 컴포넌트가 phase 별 metric 모두 시각화 가능.

---

## 그룹 C. 보안 / 운영 (3건)

### C1. 인증/멀티테넌시 — 아크릴 측 확정 사항 회신

아래 운영 모델로 가져가려 합니다 (확정):

**(1) 멀티테넌시: 워크스페이스 단위 helm install**
- 각 워크스페이스마다 별도 eva-vlm pod 인스턴스 (1 ws = 1 pod = 1 GPU)
- helm release 명에 workspace_id 포함, NFS 경로도 워크스페이스 PVC 기반
- Flightbase 의 `acryl.ai/appType: user` 어노테이션 모델과 일관
- **ETRI 측 요청**: helm env 로 `EVA_WORKSPACE_ID` 주입 + 모든 request body 의 workspace_id 가 env 값과 일치하는지 검증 (~5 줄 미들웨어)

**(2) 인증: Kong gateway only**
- 외부 인증/토큰 검증은 모두 Kong 게이트웨이에서 처리
- eva-vlm pod 내부에 별도 토큰 검증 로직 불필요 (v1 비대상)
- **ETRI 측 요청**: `service.yaml` 의 type 을 `NodePort` → `ClusterIP` 로 변경 (NodePort 30080 제거, helm 차트 1 줄 수정)
- **아크릴 측 작업**: Kong 라우팅 + NetworkPolicy 로 cluster 내부 cross-workspace 호출까지 차단 예정

### C2. Path traversal 가드 부재

- `checkpoint_name` / `output_checkpoint_name` / `data_path` / `projector_path` / `resume_lora_path` / `llm_model_path` / `marine_data_path` / `image_dir` 모두 request 입력값이 `os.path.join` 으로 들어가, `"../../etc/passwd"` 또는 절대경로로 NFS 어디든 접근 가능. 컨테이너가 root 사용자로 실행되고 있어 (Dockerfile 에 USER directive 없음) 영향이 큼.
- **해결**: 그룹 F1 의 dataset_id 추상화로 자연 해결 (ETRI 추가 작업 없음).

### C3. DeepSpeed CUDA op JIT compilation

- `train_manager` 가 `train.py` 에 `--deepspeed scripts/zero2.json` 을 전달하는데, DeepSpeed 는 첫 사용 시 fused Adam 등 CUDA C++ extension 을 JIT 컴파일합니다. 컴파일 시 `/root/.cache/torch_extensions` 에 쓰기 필요. 향후 플랫폼이 `readOnlyRootFilesystem` 을 적용하면 모든 학습 실패.
- **해결**: Dockerfile 에서 `DS_BUILD_OPS=1` 환경변수로 사전 빌드, 또는 `TORCH_EXTENSIONS_DIR=/tmp/torch_extensions` 환경변수 추가.

---

## 그룹 D. Silent 동작 결함 (3건, Tier 1)

### D1. model_manager.py:270 — `Path` import 누락
- `Path(entry.path).rglob("*")` 호출하지만 `from pathlib import Path` 가 없어 NameError 발생. 바깥 try/except 가 빈 리스트로 swallow → `/models` 응답이 항상 빈 리스트라 체크포인트 관리 워크플로우 자체가 무용지물.
- **해결**: `from pathlib import Path` 한 줄 추가.

### D2. train_manager.py:142 — `progress_pct_value` 필드 없음
- `job.progress_pct_value = 100.0` 은 `TrainJob` 에 없는 필드. `progress_pct` 는 `@property` (computed)라 학습 완료 시 progress 가 100% 로 표시되지 않음.
- **해결**: `job.current_step = job.total_steps` 로 변경하면 property 가 자동 100.0 반환.

### D3. schemas 에 정의되어 있지만 train.py 에 전달 안 되는 인자 4개
- `lora_r`, `lora_alpha`, `max_steps` (lora_marine 분기), `sds_scenario` (lora_sds), `zero_stage` (모든 분기). 사용자가 보낸 값이 조용히 무시됨.
- **해결**: `_build_command` 에 해당 분기 추가, 또는 schemas 에서 제거.

---

## 그룹 G. 운영 cosmetic (2건, P2 — 2026-05-19 추가)

`/app/vlm/demo/` Gradio frontend 처럼 ETRI 자체 검증·시연 목적의 source 가 image 에 들어 있으나 production 환경 (NFS mount, K8s pod) 에서 그대로 동작하지 않는 항목들. 서비스 동작·플랫폼 통합에는 영향이 없어 ETRI 측 우선순위에 따라 처리하시면 됩니다.

### G1. startup model load 시 `projector.bin` 부재로 traceback 출력

- **위치**: `app.py:49` lifespan + `model_manager.py:189`.
- **현상**: 학습 컨테이너 (eva-vlm-train, 추론 미사용) 시작 시마다 stdout 에 다음 traceback 노출:
  ```
  [Eva] 초기 모델 로드 실패 (추론 불가, 다른 엔드포인트는 정상):
  Traceback (most recent call last):
    File "/app/app.py", line 49, in lifespan
      manager.load()
    ...
    raise FileNotFoundError(f"projector.bin 없음: {projector_file}")
  ```
- **영향**: service 동작 0 (try/except 로 graceful 처리되어 `/health`, `/info`, `/train` 정상). 단 운영자 log noisy.
- **해결** (선택):
  - **(a) graceful skip**:
    ```python
    # model_manager.load() 의 첫 줄에 추가
    projector_file = os.path.join(ckpt_path, "projector.bin")
    if not os.path.exists(projector_file):
        self._load_error = f"projector.bin missing — model load skipped"
        return
    ```
  - **(b) env-gate**: `EVA_SKIP_INITIAL_LOAD=1` 환경변수 시 `load()` skip. 학습 컨테이너의 helm chart 가 이 env 를 set 하도록 (플랫폼 측 변경 0).

### G2. `/app/vlm/demo/` Gradio frontend production-ready 아님

- **위치**: `/app/vlm/demo/{app.py, run.sh, screenshot.png}`.
- **현상**: image 에 Gradio source + screenshot 가 포함되어 있으나, image 안에서 그대로 `bash /app/vlm/demo/run.sh` 실행 불가:
  - `gradio` 패키지 미설치 (`pip show gradio` → not found)
  - `demo/run.sh` 의 `PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python` (ETRI 개발자 local path)
  - `demo/app.py` 의 `DEFAULT_DATASET_PATH = "/home/ywlee/dev/TANGO2_main/SDS/dataset/20260227"`, `DEFAULT_LLM_MODEL = "/home/ywlee/Llama-3.1-8B-Instruct"` 같은 hard-coded local path
- **영향**: ETRI 자체 검증·시연 목적이면 fix 필요. 플랫폼 측은 자체 frontend (flightbase-fe) 에서 학습 모니터링하므로 필수 아님.
- **해결** (선택):
  - `requirements.txt` 에 `gradio==6.14.0` 추가
  - `demo/run.sh` 의 `PYTHON` → `python3`
  - `demo/app.py` 의 hard-coded path → env 변수 (예: `EVA_DATASET_PATH`, `EVA_LLM_MODEL_PATH` 같이 기존 EVA_* 환경변수 컨벤션 따름)

---

## 그룹 E. 플랫폼 표준 manifest.yaml + URL 컨벤션

### E1. 두 manifest 로 분리 작성 부탁드립니다 (eva-vlm-infer + eva-vlm-train)

SDS-VLM 처럼 추론(sync) + 학습(async, long-running) 두 성격을 가진 서비스는 SP-1 외부 컨테이너 계약 v2 의 `execution_mode: sync|async` 구분에 맞춰 두 manifest 로 분리해 등록합니다. 같은 Docker 이미지를 두 manifest 가 참조하되, 컨테이너 실행 시 entrypoint 만 다르게 (uvicorn 추론 서버 vs 학습 launcher) 분리.

```yaml
# eva-vlm-infer.yaml — 영구 배포 (워크스페이스당 1개 상주)
apiVersion: tango.acryl.ai/v1
kind: ExternalContainer
metadata:
  name: eva-vlm-infer
  version: 1.0.0
spec:
  image: docker.io/yvvyee/eva-vlm-backend:1.0.0   # Phase 2 트리거 시 이전
  job_type: infer                                  # SP-1 spec 에 신규 추가
  execution_mode: sync
  port: 8000
  endpoints:
    info: /info
    health: /health          # readiness (B2 픽스 후 미준비 시 503)
    live: /live              # liveness (신설)
    run: /run                # 추론 (image_base64 + AIS params, F2 참고)
  capabilities:
    estimated_startup_seconds: 300
    supported_models: [llama-3.1-8b, qwen3-8b]
  resources: { gpu: 1, memory: 32Gi, cpu: 8 }
  secrets: { required: [] }
  workspace_scope: per-workspace

# eva-vlm-train.yaml — 학습 launch 시 새 pod (lifecycle 1회)
apiVersion: tango.acryl.ai/v1
kind: ExternalContainer
metadata:
  name: eva-vlm-train
  version: 1.0.0
spec:
  image: docker.io/yvvyee/eva-vlm-backend:1.0.0   # 같은 이미지
  job_type: train
  execution_mode: async
  port: 8000
  endpoints:
    info: /info
    health: /health
    run: /train                          # POST → 202 + {"job_id": "..."}
    jobs: /train/status?job_id={id}      # ETRI 기존 URL 유지 시 (E2 (B) 안)
    # cancel URL: /train/stop?job_id={id}
  capabilities:
    estimated_startup_seconds: 300
    estimated_duration_seconds: 7200
    timeout_seconds: 21600
  resources: { gpu: 1, memory: 32Gi, cpu: 8 }
  secrets: { required: [] }
  workspace_scope: per-workspace
```

**/deploy 처리 (학습 결과 reload 흐름)** — 자세한 내용은 본 문서 §H 참고.

두 manifest 분리 후 학습 완료된 체크포인트를 infer pod 의 모델로 swap 하는 흐름이 필요합니다. ETRI 의 현 `/deploy` endpoint (`app.py:296-337`, `ModelManager.switch_checkpoint()` 호출) 가 정확히 이 역할이므로 그대로 활용하는 방향입니다:

```
train pod 학습 완료 → /output 에 체크포인트 저장 → pod 종료
  → 플랫폼이 jonathan_llm.commit_model 테이블에 자동 commit
  → 플랫폼이 eva-vlm-infer pod 의 POST /deploy 자동 호출
     (인자: {"checkpoint_name": "...", "workspace_id": "...", "project_id": "..."})
  → eva-vlm-infer pod 의 deploy_checkpoint() 가 switch_checkpoint() 실행
  → 새 체크포인트로 모델 reload 완료
```

ETRI 측 추가 코드는 원칙적으로 없으나, `/deploy` endpoint 가 멱등성·동시성·실패 응답·loaded checkpoint 식별 4가지 조건을 충족하는지 확인이 필요합니다. 자세한 내용 + 플랫폼 측 상태 머신 설계는 §H 참고. 본 흐름이 ETRI 의 원래 의도와 일치하는지 1회 회신 또는 정합 미팅에서 확인 부탁드립니다.

**shared fields for hybrid manifest pair**: 두 manifest (`eva-vlm-infer` + `eva-vlm-train`) 가 같은 코드베이스/이미지에서 파생되므로 다음 필드들은 두 manifest 에 동일하게 명시 부탁드립니다 (양측 일관성 검증용):

- `metadata.provider`: ETRI
- `spec.service_family`: eva-vlm
- `spec.contract_version`: 1.0.0 (또는 SP-1 v2 version)
- `spec.image.digest`: sha256:... (image tag 만이 아니라 digest 까지)
- `spec.model_artifact_format`: projector.bin + LoRA adapter (선택)
- `spec.checkpoint_namespace`: sds-marine (또는 워크스페이스별 prefix)

플랫폼이 두 manifest 가 paired 인지, image digest mismatch 또는 version skew 가 없는지 launch 시 검증합니다.

**manifest 제출 절차**: 두 manifest 를 작성하신 뒤 ML-TANGO/TANGO2 repo 에 PR (예: `VisionLanguageModel/manifests/` 디렉토리 신설) 또는 이메일 첨부로 보내주시면 검토 후 fb_scheduler 측에 등록.

**/info 응답 ↔ manifest 일치 의무**: SP-1 spec §5.1 에 따라 두 컨테이너의 `GET /info` 응답이 각각의 manifest metadata + capabilities 와 1:1 일치해야 fb_scheduler launch 후 introspection 검증 통과. 두 pod entrypoint 별로 분기 부탁드립니다.

### E2. async 컨테이너 URL 정책 — 두 가지 중 선택

SP-1 v2 spec 의 async endpoint 정책을 명확화했습니다 (`docs/external-container-spec.md §5.4 / §6` 갱신).

`GET /jobs/{job_id}` + `POST /jobs/{job_id}/cancel` 패턴을 표준으로 권장하지만, 협력기관에서 자체 엔드포인트를 쓰시고자 하면 manifest 의 endpoints 정의를 작성해 주시면 그것으로 사용 가능. 플랫폼 측 interface layer 가 컨테이너별 호출 + dto normalize 담당하므로 ETRI 환경에 가장 편한 쪽으로 결정 부탁.

**(A) Default 표준 패턴 따름**
```
GET  /jobs/{job_id}
POST /jobs/{job_id}/cancel
```
- manifest 의 `endpoints.{jobs, cancel}` 필드 생략 가능
- 통합 작업 가장 빠름
- ETRI `app.py` 라우터 재작업 ~30줄 + `API_SCHEMA.md` 갱신 필요

**(B) ETRI 자체 URL 유지** (현 코드 그대로)
```
GET  /train/status?job_id={id}
POST /train/stop?job_id={id}
```
- `manifest.yaml` endpoints 에 URL 템플릿 명시 필요 (E1 의 train manifest 양식 참고)
- ETRI 라우터 변경 0. 플랫폼 측에서 컨테이너별 client class 작성

어느 쪽을 택하시든 학습 시작 시 응답 코드는 `202 Accepted + {"job_id": "..."}` 로 맞춰 주시면 좋겠습니다 (현재 200 OK).

**응답 shape strict 정책** (URL 자유와는 별개로 응답 본문 형태는 표준 준수):

URL 컨벤션은 (A)/(B) 자유이지만, 응답 본문의 형태는 SP-1 v2 §5.4 에 명시된 정규화된 shape 을 따라 주시면 플랫폼 BFF 의 컨테이너별 quirk 흡수가 깔끔하게 가능합니다.

```json
{
  "job_id": "...",                                      // 필수
  "status": "running|completed|failed|cancelled",       // 필수 (enum)
  "progress": 0.5,                                      // 선택 (0~1)
  "result": {...},                                      // 선택 (completed 시)
  "error": {"code": "...", "message": "..."}           // 선택 (failed 시)
}
```

추가 권장:
- `code` 는 `apps/fb_utils/errors.yaml` 에 등록된 `E_VLM_*` 코드 사용 (회신 후 별도 PR)
- `progress` 가 정수 step / total_steps 비율이면 0~1 로 정규화 부탁
- `result` 안에 model_version_id, checkpoint_name, training_metrics 등 자유 추가 가능 (BFF 가 dto 정규화 시 활용)

URL 이 자유여도 응답 shape 이 다르면 BFF 의 협력기관별 client class 부담이 큽니다. 향후 SDF/SDM 등 협력기관이 늘어날 경우 URL 보다 응답 shape 의 표준 준수가 더 중요해집니다.

**API_SCHEMA.md 갱신 항목 (체크리스트)**:
- [ ] §1 서비스 개요 — 두 컨테이너로 분리되었음 명시 (infer + train)
- [ ] §3 GET /info — description placeholder ("...") 실제 string 으로
- [ ] §4 학습 시작 응답 — 200 → 202 Accepted (job_id 응답)
- [ ] §5 POST /deploy — `params.vision_model_name`·`llm_model_path` 옵션 필드 명시
- [ ] §6 에러 코드 표 — HTTP 상태 코드 매핑 (B1 픽스 반영) + UNAUTHORIZED(401) / FORBIDDEN(403) / TIMEOUT(408) 항목 추가
- [ ] §2 인프라 사전 준비 — NFS 경로를 SP-1 v2 표준 (`/model`, `/dataset/{name}`, `/output`, `/built_in_checkpoint`) 으로 교체
- [ ] §3 환경변수 표 — `EVA_*` → `JF_*` 매핑 (SP-1 v2 표준)
- [ ] URL 정책 (A/B) 결정에 따라 §4 학습 endpoints 갱신

---

## 그룹 F. 데이터·이미지·레지스트리 컨벤션

### F1. PVC 마운트 / 환경변수 — SP-1 v2 표준 적용

아크릴 플랫폼의 외부 컨테이너 표준 마운트 컨벤션 (`docs/external-container-spec.md §3.1-3.2`) 을 따라 부탁드립니다. helm chart 의 `nfs.server: <IP>` 직접 마운트 부분은 제거하고, 워크스페이스 PVC (`{workspace_namespace}-main-pvc`, `{workspace_namespace}-data-pvc`) 를 마운트하는 형태로 재작성. 컨테이너 내부에서는 아래 표준 경로/환경변수로 자원 접근:

| 컨테이너 내부 경로 | RO/RW | 용도 |
|---|---|---|
| `/model` | RW | 모델 가중치 + 학습 결과 저장 |
| `/dataset/{JF_DATASET_NAME}` | RO | 입력 데이터셋 (단일 dataset) |
| `/input/params.json` | RO | 동적 파라미터 (TrainParams) |
| `/output` | RW | 학습 결과물 (로그, metrics 등) |
| `/built_in_checkpoint` | RO | 이전 phase 학습 결과 (선택) |

환경변수 (플랫폼이 launch 시 자동 주입):
```
JF_MODEL_PATH=/model
JF_MODEL_NAME=<llama-3.1-8b 같은 식별자>
JF_DATASET_PATH=/dataset
JF_DATASET_NAME=<선택된 데이터셋 이름>
JF_HUGGINGFACE_TOKEN=<token>          (필요 시 — 아래 HF 토큰 정책 참고)
JF_INPUT_PATH=/input
JF_OUTPUT_PATH=/output
JF_JOB_TYPE=train
JF_PARAMS_PATH=/input/params.json
JF_PORT=8000
```

**ETRI 측 정합 작업** (헬름 차트 + 환경변수 + 경로 인자):

**(a)** `helm chart values.yaml` 의 `backend.volumes` 를 워크스페이스 PVC 기반으로 교체. 워크스페이스 PVC 명명 컨벤션 (`{ws_ns}-main-pvc`, `{ws_ns}-data-pvc`) 은 별도 가이드 공유 가능.

**(b)** 환경변수를 `EVA_*` 에서 `JF_*` 표준으로 매핑 (둘 다 지원, `JF_*` 우선 적용도 좋습니다):
```
EVA_LLM_MODEL_PATH    → JF_MODEL_PATH      (/model)
EVA_CHECKPOINT_PATH   → JF_OUTPUT_PATH     또는 /built_in_checkpoint
EVA_CHECKPOINTS_ROOT  → JF_OUTPUT_PATH     (/output)
```

**(c)** `/train` 요청의 raw path 인자를 표준 환경변수 기반으로 정합:
```
data_path / image_dir              → JF_DATASET_NAME (env)
projector_path / resume_lora_path  → /built_in_checkpoint 트리 안에서 해석
output_checkpoint_name             → JF_OUTPUT_PATH 단일 디렉토리 + 메타데이터
sds_scenario, phase, num_epochs 등 → /input/params.json 으로 읽기
```

dataset_id ↔ JF_DATASET_NAME 매핑 흐름:
ETRI 측은 fb_dataset 의 dataset_id 를 직접 다루실 필요 없습니다. 사용자가 UI 에서 데이터셋을 선택 → 플랫폼이 manifest 의 `inputs.dataset` 명세 + 사용자 선택값을 기반으로 워크스페이스 PVC 의 해당 dataset subPath 를 자동 mount + `JF_DATASET_NAME` 환경변수 자동 주입. ETRI 컨테이너는 `os.environ['JF_DATASET_NAME']` 만 읽고 `/dataset/{JF_DATASET_NAME}/` 디렉토리에서 학습 데이터 접근.

**(c')** HuggingFace 토큰 처리 (확인 부탁):
본 레포 HF 토큰 정책(commit `6331ab9ac`)상 `JF_HUGGINGFACE_TOKEN` 이 empty string 또는 None 이어도 컨테이너 부팅이 정상 진행되어야 합니다 (오프라인/Nexus mirror 모드 보장). ETRI 환경에서 이미 그렇게 동작하실 가능성이 높지만, `manager.load()` 의 HF 다운로드 분기에서 token 없음을 graceful 처리 (raise 대신 fallback) 되어 있는지 확인만 부탁드립니다.

**(d)** 데이터셋 단일 mount 제약:
SP-1 v2 는 단일 dataset mount 만 지원합니다. 현재 SDS-VLM 4-phase 파이프라인이 image + AIS + output_text 3 종을 사용하시는데, 한 데이터셋 디렉토리 안 multi-file 로 패키징 부탁드립니다:
```
/dataset/sds-marine-20260227/
  image/00001/input_image.png
  ais/00001/input_data.csv
  output/00001/output_*.txt
  metadata.json
```
(데이터셋 준비 스크립트와 깊게 연관되므로 1회 회의에서 같이 정해도 좋겠습니다.)

**(e)** 4-phase 파이프라인 (projector → lora → lora_marine → lora_sds) 의 phase 간 의존성:
- 각 phase 의 학습 결과는 `/output` 으로 저장
- 다음 phase 학습 시 fb_scheduler 가 이전 phase 의 `/output` 을 새 pod 의 `/built_in_checkpoint` 으로 RO mount 주입
- phase 정보는 `/input/params.json` 안에 phase 필드 + 이전 phase checkpoint 식별자로 전달

위 (a)~(e) 는 SP-1 외부 컨테이너 계약 v2 정합 작업입니다. 양측 협의가 필요한 부분이 섞여 있어 1회 정합 미팅에서 세부 매핑을 같이 잡으면 빠를 것 같습니다.

### F2. 추론 이미지 페이로드 — ETRI image_base64 유지 + size cap + EXIF

ETRI 의 현 `image_base64` (JSON body) 구조는 그대로 유지하셔도 됩니다. 플랫폼 측 BFF (`apps/llm_model/external_vlm/clients/eva_vlm.py`) 가 사용자 multipart 요청을 받아 base64 로 변환 후 ETRI 컨테이너에 전달하는 형태로 normalize 합니다.

단 size cap + EXIF orientation 처리는 추가 부탁드립니다 (~5줄):

```python
# schemas.py:
class RunParams(BaseModel):
    image_base64: str = Field(..., max_length=7_000_000)  # ≈5MB image
    ais_rows: List[AISRow] = Field(..., max_items=64)
    max_new_tokens: int    = Field(512, ge=1, le=4096)
    repetition_penalty: float = 1.1
    do_sample: bool = False

# model_manager.infer():
from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = 32_000_000   # decompression bomb 방지
img = ImageOps.exif_transpose(
          Image.open(io.BytesIO(base64.b64decode(image_base64)))
      ).convert('RGB')
```

### F3. fine_tuning_job 테이블 — ETRI 부담 0

학습 작업 상태는 우리 측에서 `jonathan_llm.fine_tuning_job` 테이블에 신규 저장 예정. 우리 측 (`apps/llm_model` 확장 모듈) 가 ETRI 의 `/train/status` (또는 `/jobs/{id}`) 를 주기적으로 polling 해 DB 에 기록하며, F1 의 `/output` 디렉토리에 저장된 결과물은 `jonathan_llm.commit_model` 으로 자동 commit. ETRI 는 현재처럼 in-memory + `/train/status` API 만 정확히 제공해 주시면 됩니다 (DB 의존성 추가 부담 없음).

단 A2 deadlock 픽스 후 `/train/status` 가 completed/failed 상태로 안정적으로 전이되어야 polling 이 깔끔합니다.

### F4. 컨테이너 레지스트리 — 1차 현 상태 유지, Phase 2 이전

오픈소스 프로젝트 특성상 1차 PoC 단계에서는 `yvvyee/eva-vlm-backend` 그대로 사용하셔도 됩니다. 다만 개인 계정 의존이 ETRI 인사 이동 시 push 권한·이미지 보존 리스크가 있어, 아래 Phase 2 트리거 중 먼저 도달하는 시점에 조직 계정으로 이전 검토 부탁:

- (a) 계약 안정화 완료 (1차 PoC 통합 완료) 시점
- (b) SDF/SDM 등 추가 외부 컨테이너 진입 시점
- (c) 2026-11 (6 개월 경과)

이전 대상 후보:
- `ghcr.io/ml-tango/eva-vlm:x.y.z` (오픈소스 프로젝트 owner 정합, 권장)
- `docker.io/acrylaaai/eva-vlm:x.y.z` (Flightbase 다른 MSA 컨벤션)

---

## 그룹 G. PoC 통합 완료 acceptance 체크리스트

ETRI 패치 + 아크릴 측 fb_scheduler 확장 + 통합 후, 아래 8개 시나리오가 모두 통과하면 1차 PoC 통합 완료로 판단하려 합니다. 1회 정합 미팅에서 세부 조정 가능.

- [ ] **G1**. eva-vlm-infer pod helm install → 5분 이내 `/health` 가 200 + "healthy" 응답 (모델 로드 완료 검증)
- [ ] **G2**. `GET /info` 응답이 `eva-vlm-infer.yaml` manifest 의 metadata·capabilities 와 1:1 일치 (introspection 검증)
- [ ] **G3**. `POST /run` 추론 1건 (image_base64 + AIS rows JSON) → 200 OK + RunResponse JSON 응답 (latency 30초 이내)
- [ ] **G4**. eva-vlm-train pod helm install 성공 (fb_scheduler 가 manifest 기반으로 launch)
- [ ] **G5**. `POST /run` (train pod) → 202 Accepted + job_id 응답 → polling → completed 상태 도달
- [ ] **G6**. 학습 완료 → `/output` 의 결과물이 `jonathan_llm.commit_model` 에 자동 commit + eva-vlm-infer pod 의 모델 reload 정상 동작
- [ ] **G7**. cancel 요청 → 학습 중지 + GPU 자원 즉시 해제 (자식 프로세스 그룹 정리, A3 픽스 검증)
- [ ] **G8**. workspace-A 사용자가 workspace-B 의 eva-vlm pod 에 cluster 내부 호출 시 NetworkPolicy 로 차단 (멀티테넌시 격리 검증)

---

## ETRI 측 To-Do Tier 별 요약 (2026-05-19 갱신)

| Tier | 분류 | 항목 | 추정 부담 |
|---|---|---|---|
| **Tier 0** | **학습 launch 차단 (Must-do, 최우선)** | **A5** (torch CVE-2025-32434) | ~1줄 또는 base image upgrade |
| **Tier 1** | 직접 코드 패치 — PoC 부팅·안정성 (Must-do) | A1~A4, D1~D3 (7건) — **A1·A2·A3 은 아크릴 측 검증된 patch bundle 동봉** | ~25줄 |
| **Tier 2** | 직접 코드 패치 — API 계약 (Should-do) + 모니터링 연동 | B1~B4 (4건) + **B5 TensorBoard** (모니터링 연동) | ~60줄 |
| **Tier 3** | helm chart + manifest 정합 | C1, E1, E2, F1, F2 (5건) | ~50줄 + helm chart 재작성 |
| **Tier 4** | 결정만 부탁 — 작업은 아크릴 측 | E2 (A/B 선택), /deploy reload 메커니즘 (i/ii) | 0줄 |
| **Tier 5** | ETRI 작업 없음 (참고) | C2, C3, F3, F4 | 0줄 |
| **Tier 6** | 운영 cosmetic (P2, optional) | G1 (startup noise), G2 (Gradio demo) | ~5~10줄 |

**총 ETRI 코드 변경량**: ~135줄 + base image torch 업그레이드 + helm chart 재작성. 1회 정합 미팅 후 ETRI 측 1주 작업 → 아크릴 측 통합 1~2주 (병렬).

### 핵심 변경 사항 (2026-05-19)

- **A5 (torch CVE) 가 가장 우선** — A1~A4 패치 적용 후에도 학습 launch 가 vision encoder 로드 단계에서 차단됨이 아크릴 측 클러스터 검증으로 확인됨. base image 의 torch 2.5.1 → 2.6+ 업그레이드 또는 `use_safetensors=True` 강제.
- **A1·A2·A3 patch bundle 동봉** — `etri-tier1-patch/` 디렉토리에 unified diff + patched 소스 + Dockerfile 변경분. 아크릴 측 클러스터에서 동작 검증 완료. ETRI 측에서 그대로 채택 또는 코드 스타일 재작성 모두 가능.
- **B5 (TensorBoard) 신규** — 플랫폼 frontend 의 학습 그래프 자동 연동에 필요. 5줄 patch + `tensorboard>=2.14` 의존성. W&B 와 공존 가능.
- **그룹 G 신설 (P2 cosmetic)** — G1 (startup noise) + G2 (Gradio demo production-ready).

### 각 Tier 완료 기준 요약

- **Tier 1**: 컨테이너 부팅 5분 내 `/health` 200, 학습 1건 시작 → 완료 → `/train/status` completed 도달
- **Tier 2**: 잘못된 요청 시 4xx/5xx 정상 반환, 동시 `/run` + cross-endpoint 충돌 없음
- **Tier 3**: helm install 시 워크스페이스 PVC 자동 마운트, `JF_*` 환경변수로 자원 접근, `/info` 응답이 manifest 와 일치

---

## 그룹 H. /deploy 멱등성·상태 머신·플랫폼↔Pod 인증 (협의 사항)

두 manifest 분리 (#3) + commit_model → infer pod `/deploy` 자동 호출 흐름 (§E1 끝부분, 메일 §3 (2)) 의 안전성을 위해 양측이 합의해야 할 사항입니다. 외부 cross-model 검토(OpenAI Codex)에서 가장 위험한 부분으로 지적되어 별도 섹션으로 분리했습니다.

### H1. 학습 완료 → reload 흐름의 9가지 실패 시나리오

```
[학습 완료]                                  [발생 가능 실패]
train pod 학습 완료                          (1) /output 의 artifact 가 partial / fsync 안 됨
→ /output 저장                               (2) commit_model 성공 후 artifact 손상 발견
→ pod 종료
                                             (3) commit worker 가 중복 polling → 중복 commit
[commit]
플랫폼 commit_model INSERT
                                             (4) infer pod 이 다른 reload 중 (concurrent)
[deploy 호출]                                (5) infer pod restart 사이 race
플랫폼 → POST eva-vlm-infer/deploy           (6) /deploy 응답 200 후 model load 비동기 실패
                                             (7) Kong 우회 직접 호출 → auth/log/rate-limit 우회
[reload]
ModelManager.switch_checkpoint()             (8) 오래된 training job 의 late retry 가
                                                 새 모델 덮어쓰기
                                             (9) /deploy 가 멱등 X → 중복 swap 시 모델 흔들림
```

### H2. `/deploy` 인터페이스 강화 요청 (ETRI 확인)

ETRI 의 현 `/deploy` endpoint (app.py:296-337) 가 아래 4가지를 충족하는지 확인 부탁드립니다. 충족하지 않는 경우 협의 후 보강:

```python
# 요청 인자 (현 schemas.DeployRequest + 추가):
{
  "workspace_id": "...",
  "project_id": "...",
  "params": {
    "checkpoint_name": "sds_lora_ko_compact_v3",   # 필수
    "model_version_id": 142,                       # 신규 권장 (DB 의 commit_model.id)
    "source_job_id": "abc12345",                   # 신규 권장 (어떤 학습의 결과인지)
    "idempotency_key": "...",                      # 신규 권장
    "vision_model_name": "...",                    # 기존 옵션
    "llm_model_path": "..."                        # 기존 옵션
  }
}

# 응답 (현 DeployResponse + 추가):
{
  "status": "success" | "error",
  "deployment_id": "...",                          # 신규 권장 (요청별 고유)
  "loaded_checkpoint_name": "sds_lora_ko_compact_v3",  # 신규 권장 (실제 로드된 것)
  "loaded_model_version_id": 142,
  "code": "...",                                   # error 시
  "message": "..."                                 # error 시
}
```

**4가지 멱등성/안전성 조건**:

1. **멱등성**: 같은 `checkpoint_name` (또는 `idempotency_key`) 로 재호출 시 중복 swap 안 일어남. 첫 호출 결과 그대로 응답.
2. **동시성 직렬화**: 두 개의 다른 `checkpoint_name` 으로 동시 호출 시 직렬화 또는 후행 거부 (409 Conflict). 둘이 동시에 load 시도하는 일 없음.
3. **실패 응답**: 체크포인트 load 실패 시 명시적 4xx/5xx 응답 (현재 HTTP 200 + status:"error" 일 가능성 — A1 픽스와 연동).
4. **확인 가능**: 응답에 `loaded_checkpoint_name` 포함되어 호출자가 정확히 어떤 체크포인트가 로드됐는지 확인 가능.

### H3. 플랫폼 측 상태 머신

플랫폼이 commit_model insert ~ infer pod reload 완료까지 추적할 상태 머신:

```
[ DB row commit_model 신규 추가 ]
            ↓
        committed
            ↓ (commit worker 가 deploy 호출)
        deploy_requested
            ↓ (POST /deploy 응답 수신)
   deploying ─┬─→ deployed       (success)
              └─→ deploy_failed  (load 실패)
```

`monotonic version` 보호: 한 model_id 의 latest_committed_version 이 v3 인 상태에서 v2 의 늦은 retry 가 들어오면 거부. 오래된 학습 결과로 덮어쓰기 방지.

### H4. 플랫폼 → Pod 직접 호출의 인증 보강

decision #2 (Kong gateway only + ClusterIP) 는 외부 인증 경로로는 충분하나, 플랫폼이 cluster 내부에서 직접 infer pod 의 `/deploy` 를 호출하는 경우는 Kong 을 우회하므로 별도 보호 필요:

- **NetworkPolicy**: eva-vlm-infer pod 의 ingress 허용 caller 를 platform namespace 의 specific service account 로 제한
- **Signed internal header**: 플랫폼이 호출 시 `X-Tango-Internal-Signature: <HMAC of body + timestamp>` 같은 헤더 부여, infer pod 이 검증
- **request_id propagation**: `X-Request-ID` 또는 W3C `traceparent` 헤더로 audit log 추적 가능

이 부분은 1회 정합 미팅에서 양측 디테일 잡으면 좋겠습니다. 단순한 ClusterIP 만으로 internal mutation 호출이 안전하다고 가정하면 cluster 내 다른 워크로드가 mutation 가능.

---

## 그룹 I. 다음 단계 SP-1 spec 보강 — API contract gaps (협의 미팅 후 정리)

본 통합 진행과 별개로, SP-1 외부 컨테이너 계약 v2 가 다음 사항을 명시적으로 다루도록 보강 예정입니다. ETRI SDS-VLM 통합 경험을 첫 케이스로 spec 에 반영하며, 향후 SDF/SDM/Learning 등 추가 협력기관 진입 시 onboarding 부담을 줄이는 것이 목표입니다.

1. **Error envelope 표준화**: `{code, message, details, retryable, request_id}` 안정적 shape
2. **HTTP status 규칙**: business error 는 절대 HTTP 200 사용 안 함 (4xx/5xx)
3. **Idempotency keys**: `/train`, `/deploy`, `/jobs/{id}/cancel` 의 idempotency 보장 패턴
4. **Request ID propagation**: `X-Request-ID` 또는 W3C `traceparent` 헤더 표준
5. **Timeout contract**: startup timeout, polling interval, deploy timeout, model load timeout 의 권장값
6. **Retry contract**: 어떤 작업이 retry safe 인지 명시
7. **Status transition state machine**: allowed job states, terminal states, transition rules
8. **Artifact readiness**: `/output` 가 "complete" 로 간주되는 시점 정의
9. **Checkpoint naming/versioning rules**: 협력기관별 자유 vs 표준 컨벤션
10. **Concurrent operation rules**: train+deploy / deploy+infer / cancel+complete 동시 발생 시 동작
11. **Health vs Live 정확한 semantics**: readiness vs liveness 분리 의무
12. **Version negotiation**: `contract_version`, container version, model format version
13. **Resource reporting**: GPU memory, startup time, max image size, max request size manifest 명시
14. **Observability**: 로그 포맷, 메트릭 표준, progress source, failure 분류 taxonomy
15. **Security boundary**: 내부 mutation endpoint 호출 권한 (H4 와 연동)
16. **Shared manifest fields for hybrid pair**: provider, service_family, contract_version, image_digest, model_artifact_format, checkpoint_namespace (E1 끝부분 참고)

ETRI 측에서 이 16개 항목 중 SDS-VLM 통합 시점에 우선 적용이 필요한 부분 있으면 알려주시고, 나머지는 통합 PoC 완료 후 SP-1 spec v2.1 갱신 시 반영하겠습니다.
