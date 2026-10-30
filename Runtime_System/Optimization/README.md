# Optimization — 배포탑재 파이프라인

**실행 환경에 최적화되는 신경망 실행 이미지 생성 기술**

`deploy.yaml` 한 장으로 모델 경량화 · 포맷 변환 · 실행 코드 생성 · 배포 이미지 생성까지

---

## 목차

- [1. 개요](#1-개요)
- [2. 세부 기술 내용](#2-세부-기술-내용)
- [3. 폴더 구조](#3-폴더-구조)
- [4. 설정 및 실행 방법](#4-설정-및-실행-방법)

---

## 1. 개요

학습이 완료된 신경망 모델을 실행 환경별 최적 형태로 자동 변환·포장하여, 즉시 기동 가능한 실행 이미지로 산출하는 파이프라인입니다.

기존에는 양자화 도구, 포맷 변환 도구, 서빙 프레임워크 설정을 각각 따로 수행하고 그 사이를 수작업으로 이어야 했습니다. 이 과정에서 도구마다 입력 형식이 다르고 실행 엔진마다 허용하는 양자화 방식이 달라, 변환을 모두 끝낸 뒤에야 조합이 불가능하다는 사실을 발견하는 일이 잦았습니다.

이 파이프라인은 전 과정을 `deploy.yaml` 하나로 선언하고, 실행 전에 조합의 타당성을 먼저 검증합니다. 모델과 설정 파일을 입력하면 정리부터 산출물 저장까지 일곱 단계가 순차 수행되어, `Data/Output/<service>` 아래에 바로 사용 가능한 산출물이 남습니다.

### 1.1 설계 원칙

- **실행 전 검증** — 실행 엔진이 요구하는 모델 포맷과 그 경로에서 허용되는 양자화 방식을 선언적 제약표로 정의합니다. 불가능한 조합은 수 시간짜리 변환이 끝난 뒤가 아니라 설정 검증 시점에 사유와 함께 차단됩니다.
- **단계별 산출물 분리** — 각 단계의 결과를 용도별 임시 폴더(`tmp_model` / `tmp_code` / `tmp_image`)에 나누어 쌓고, 최종 산출물만 `Output`에 남깁니다. `--keep-tmp`로 중간 결과를 보존해 단계별 확인이 가능합니다.
- **계획 선확인** — `--dry-run`으로 실제 변경 없이 해석된 설정과 수행될 단계 구성을 먼저 확인할 수 있습니다.
- **서비스 타입별 템플릿** — 서비스 형태마다 실행 코드 원본을 `Data/<SERVICE>-template`으로 분리해 두어, 코드 생성 로직을 바꾸지 않고 템플릿 추가만으로 새 서비스 타입을 지원합니다.

### 1.2 전체 흐름

```
deploy.yaml  +  학습된 신경망 모델
      |
      v
 ① 정리  →  ② 모델 변환  →  ③ 모델 경량화  →  ④ 실행 코드 생성
                  |               |                  |
             tmp_model       tmp_model           tmp_code
                                                      |
                                                      v
                              ⑦ 임시 정리  ←  ⑥ 산출물 저장  ←  ⑤ 이미지 빌드
                                                      |              |
                                              Output/<service>   tmp_image
```

| 단계 | 수행 조건 | 담당 모듈 | 산출 위치 |
|---|---|---|---|
| ① 정리 | 항상 | `pipeline.py` | — |
| ② 모델 변환 | 입력 포맷 ≠ 엔진 요구 포맷 | `model_converter` | `tmp_model/<service>` |
| ③ 모델 경량화 | `use_optimization: yes` | `model_optimizer` | `tmp_model/<service>` |
| ④ 실행 코드 생성 | 항상 | `code_generator` | `tmp_code/<service>` |
| ⑤ 이미지 빌드 | `deploy_method ≠ raw` | `image_builder` | `tmp_image/<service>` |
| ⑥ 산출물 저장 | 항상 | `pipeline.py` | `Output/<service>` |
| ⑦ 임시 정리 | `--keep-tmp` 미지정 시 | `pipeline.py` | — |

---

## 2. 세부 기술 내용

### 2.1 설정 검증과 실행 계획 (`yaml_parser.py`)

`deploy.yaml`을 파싱하여 dataclass 구조로 변환하고, 구조·값·엔진 호환성의 세 층위로 검증한 뒤 실행 계획(`Plan`)을 산출합니다. 핵심은 `ENGINE_SPECS` 제약표로, 실행 엔진마다 요구하는 모델 포맷과 허용되는 양자화 방식을 선언합니다.

| 실행 엔진 | 모델 포맷 | 허용 양자화 | 비고 |
|---|---|---|---|
| `vllm` | safetensors | none / awq / gptq / rtn | LLM 서빙 기본 선택지 |
| `trtllm` | safetensors | none / fp8 / nvfp4 | NVIDIA ModelOpt 경유 |
| `llama.cpp` | gguf | none / rtn | 가중치 양자화는 `gguf_outtype`으로 지정 |
| `pytorch` | safetensors | none / rtn | transformers 직접 실행 |
| `tensorrt` | onnx | none | 인코더 전용(CLIP, ViT 등) |

이 제약표가 실행 전에 걸러내는 대표적인 조합입니다.

- `llama.cpp`는 GGUF 자체 양자화 타입을 사용하므로, AWQ·GPTQ로 패킹된 체크포인트를 `convert_hf_to_gguf.py`가 읽지 못합니다.
- TensorRT는 엔진 빌드 시점에 INT8 캘리브레이션을 수행하므로, 사전 양자화를 거치면 파일 크기는 그대로인 채 정확도만 손실됩니다.
- AWQ·GPTQ 체크포인트는 패킹된 int4 가중치라 ONNX export 대상이 되지 않습니다.

### 2.2 프루닝 (`model_optimizer/pruner.py`)

| 방식 | 판단 기준 | 캘리브레이션 | 특성 |
|---|---|---|---|
| `unstructural` | 가중치 절댓값 | 불필요 | 정확도 손실 최소. 흩어진 0이라 속도 이득 없음 |
| `nm_pattern` | 그룹 내 절댓값 | 불필요 | 2:4 등 반정형. sparse tensor core 가속 대상 |
| `structural` | 출력 채널 L2 노름 | 불필요 | 채널 단위 제거. 50% 초과 시 손실 급증 |
| `wanda` | \|W\| × ‖X_j‖ | **필수** | 입력 활성값 반영. 같은 희소도에서 정확도 유지 |

> **주의** — 세 방식 모두 가중치를 0으로 만드는 마스킹이며 텐서 shape은 변하지 않습니다. 따라서 파일 크기와 메모리 사용량은 줄지 않습니다. 실제 이득을 보려면 희소 연산을 지원하는 런타임이나 n:m 패턴이 필요합니다. 산출물의 `pruning_config.json`에 이 점이 기록됩니다.

Wanda는 원 논문이 레이어를 순차 처리하여 앞 레이어의 프루닝 결과를 뒤 레이어 활성값에 반영하는 반면, 본 구현은 원본 모델로 한 번에 활성 통계를 수집하는 단순화된 방식입니다.

### 2.3 양자화 (`model_optimizer/optimizer.py`)

| 방식 | 비트 | 캘리브레이션 | 특성 |
|---|---|---|---|
| `rtn` | 4 / 8 | 불필요 | 직접 구현. CPU 가능하나 fake-quant라 크기 미감소 |
| `gptq` | 4 / 8 | 필수 | `gptqmodel` 사용. 2차 근사 기반. GPU 권장 |
| `awq` | 4 / 8 | 필수 | `llm-compressor` 사용. activation-aware. GPU 필수 |
| `fp8` | 8 고정 | 필수 | NVIDIA ModelOpt. per-tensor. Hopper(sm89) 이상 |
| `nvfp4` | 4 고정 | 필수 | NVIDIA ModelOpt. 블록 16 고정. Blackwell(sm100) 이상 |

FP8·NVFP4는 비트 수, 그룹 크기, zero-point를 방식이 고정하므로 설정으로 지정해도 무시되며, 검증 단계에서 경고가 출력됩니다. 또한 실행 GPU의 compute capability를 사전 점검하여 가속 불가 환경에서 조용히 느려지는 상황을 방지합니다.

프루닝과 양자화를 함께 지정하면 프루닝 → 양자화 순으로 수행되며, 중간 산출물은 각 단계가 끝나는 즉시 제거되어 `tmp_model/<service>`에 최종 결과만 남습니다.

### 2.4 포맷 변환 (`model_converter/model_converter.py`)

PyTorch, safetensors, GGUF, ONNX 간 변환을 수행합니다. 입력은 HF 형식 디렉토리이며, 출력 포맷은 목표 엔진이 결정합니다. GGUF 변환은 이미지에 내장된 llama.cpp의 `convert_hf_to_gguf.py`를 호출하고, ONNX export는 optimum을 사용하며 CLIP 계열은 비전 인코더를 자동 판별합니다.

변환 후에는 원본과 변환 결과에 같은 입력을 넣어 출력의 수치 일치를 검증합니다. 입력과 출력 포맷이 같은 경우에도 실행에 필요한 파일만 선별 복사하여 산출물을 정리하며, 이때 양자화 메타데이터(`quantize_config.json`, `hf_quant_config.json` 등)와 파이프라인 기록(`pruning_config.json`)이 함께 보존됩니다. 이 메타데이터가 누락되면 런타임이 양자화된 체크포인트임을 인식하지 못해 로드에 실패합니다.

파이프라인은 입력 포맷과 엔진 요구 포맷을 비교해 변환 필요 여부를 스스로 판정하며, 변환 단계 수행 여부는 `--enable-convert`로 제어합니다.

### 2.5 실행 코드 생성 (`code_generator/codegen.py`)

서비스 타입에 따라 두 가지 방식으로 실행 코드를 구성합니다.

**템플릿 기반** — `Data/<SERVICE>-template` 폴더를 `tmp_code/<service>`로 복사합니다. 서비스마다 고유한 실행 스크립트·설치 절차·정적 자원을 그대로 가져오는 방식으로, 서비스 타입 추가가 템플릿 폴더 추가만으로 끝납니다. 앞 단계에서 변환·경량화된 모델이 있으면 `model/` 하위에 함께 묶습니다.

| 서비스 타입 | 템플릿 폴더 | 성격 |
|---|---|---|
| `sds` | `Data/SDS-template` | 스트리밍 데이터 서비스 |
| `sdf` | `Data/SDF-template` | 함수 호출형 서비스 |
| `sdm` | `Data/SDM-template` | 모델 서빙 서비스 |

**엔진 래퍼 생성** — 엔진 기반 서비스는 `codegen.py`가 `engine.py`·`app.py`·`runtime.json`·`requirements.txt`를 생성합니다. 코드 템플릿을 정적으로 두고 달라지는 값을 모두 `runtime.json`으로 분리하는 것이 설계의 핵심으로, 모델 경로나 포트 변경이 설정 한 줄 수정으로 끝나고 `MODEL_DIR` 환경변수로 모델 경로만 덮어쓸 수도 있습니다.

모든 엔진은 `Engine(cfg).generate(prompt, **kw) -> str` 단일 인터페이스를 따릅니다. 구동 방식은 `invoke_time`으로 정합니다.

| `invoke_time` | 형태 | 엔드포인트 / 입출력 |
|---|---|---|
| `user` | FastAPI 서버 | `/health`, `/generate`, `/v1/chat/completions` |
| `period` | 워커 루프 | `inbox/` → `outbox/` → `done/` (고정 주기) |
| `event` | 워커 루프 | `inbox/` 감시 (단주기 폴링) |

### 2.6 배포 이미지 생성 (`image_builder/imagebuild.py`)

| `deploy_method` | 생성물 | 대상 |
|---|---|---|
| `raw` | 이미지 생성 없이 통과 (실행 코드만 산출) | 베어메탈 직접 실행 |
| `docker` | `Dockerfile`, `docker-compose.yaml`, `.dockerignore`, `build.sh` | 단일 호스트 |
| `k3s` / `k8s` | 위 항목 + `deployment.yaml`, `service.yaml`, `pvc.yaml`, `deploy.sh` | 클러스터 |

실행 코드가 생성물과 같은 폴더로 복사되어, 그 자리에서 바로 빌드 가능한 자립형 빌드 컨텍스트를 이룹니다. `--build-image`를 지정하면 docker로 컨테이너 이미지 실물까지 빌드하여 `<service>-image.tar`로 저장합니다.

모델 파일은 이미지에 굽지 않고 볼륨으로 마운트하는 것을 기본으로 합니다. 수 GB 모델을 이미지에 넣으면 빌드·푸시·롤아웃이 모두 느려지고, 같은 이미지로 모델만 교체하는 운용이 어려워지기 때문입니다. 이미지에 포함하려면 생성된 `Dockerfile` 하단의 주석 처리된 `COPY` 구문을 활성화합니다.

`storage_class`는 `local`을 local-path, `nfs`를 nfs, `aws`를 gp3 스토리지 클래스의 PVC로 매핑합니다. `minio`는 PVC 대상이 아니므로 `emptyDir`로 구성되며, 모델을 내려받는 initContainer를 추가해야 한다는 안내가 생성물의 README에 포함됩니다. 모델 로딩이 길어질 수 있어 `startupProbe`를 최대 10분으로 설정합니다.

---

## 3. 폴더 구조

### 3.1 저장소 구조

```
Optimization/
├── pipeline.py              파이프라인 드라이버 (주 진입점)
├── yaml_parser.py           설정 파싱 / 검증 / 실행 계획 산출
│
├── model_optimizer/         경량화
│   ├── optimizer.py           양자화 (rtn/gptq/awq/fp8/nvfp4)
│   └── pruner.py              프루닝 (unstructural/structural/wanda)
│
├── model_converter/         포맷 변환
│   ├── model_converter.py     pytorch/safetensors/gguf/onnx 상호 변환
│   └── requirements.txt       변환 전용 의존성
│
├── code_generator/          실행 코드 생성
│   └── codegen.py             engine.py / app.py / runtime.json 생성
│
├── image_builder/           배포 이미지 생성
│   └── imagebuild.py          Dockerfile / k8s 매니페스트 / systemd 생성
│
├── Data/                    입력 템플릿과 산출물 (3.2 참조)
│
├── deploy.yaml              기본 설정 파일
├── deploy.sds.yaml          서비스 타입 예시 — SDS + llama.cpp (ARM)
├── deploy.vllm.yaml         엔진별 예시 — vLLM + GPTQ
├── deploy.trtllm.yaml       엔진별 예시 — TensorRT-LLM + FP8
├── deploy.llamacpp.yaml     엔진별 예시 — llama.cpp + GGUF (ARM/K3s)
├── deploy.pytorch.yaml      엔진별 예시 — PyTorch + RTN (주기 구동)
├── deploy.tensorrt.yaml     엔진별 예시 — TensorRT/ONNX (이벤트 구동)
├── deploy.pruning.yaml      엔진별 예시 — 프루닝 + 양자화 병행
│
├── requirements.txt         파이프라인 코어 의존성
├── requirements-quant.txt   양자화 추가 의존성 (GPU 환경)
├── Dockerfile               파이프라인 전체 실행 이미지
└── dockercompose.yaml       파이프라인 / 개별 도구 실행 정의
```

### 3.2 Data 폴더

파이프라인의 입력 템플릿과 산출물이 모여 있는 작업 공간입니다. 위치는 `-d/--data-dir`로 바꿀 수 있습니다.

```
Data/
├── SDS-template/            서비스 타입별 실행 코드 원본 (입력)
├── SDF-template/
├── SDM-template/
│
├── tmp_model/<service>/     변환·경량화 중간 산출물   ← 수행 후 삭제
├── tmp_code/<service>/      실행 코드 + 모델          ← 수행 후 삭제
├── tmp_image/<service>/     배포 이미지 구성물        ← 수행 후 삭제
│
└── Output/<service>/        최종 산출물
```

`tmp_*` 세 폴더는 마지막 단계에서 자동 제거됩니다. `--keep-tmp`를 주면 보존되어 단계별 결과를 확인할 수 있습니다.

`Output/<service>`에는 이미지 빌드를 수행한 경우 **배포 이미지 구성물**이, `deploy_method: raw`인 경우 **실행 코드와 모델**이 저장됩니다. 같은 이름의 폴더가 이미 있으면 모두 제거한 뒤 새로 만듭니다.

---

## 4. 설정 및 실행 방법

### 4.1 요구 환경

- Linux (x86_64), Python 3.11 이상
- Docker 및 Docker Compose (컨테이너 실행 시)
- NVIDIA GPU 및 CUDA — GPTQ, AWQ, FP8, NVFP4 양자화와 GPU 추론에 필요
- RTN 양자화와 프루닝, 설정 검증은 CPU만으로도 동작

### 4.2 설치

**컨테이너 사용 (권장)**

```bash
# 기본 빌드 (llama.cpp 컴파일 포함, 최초 수 분 소요)
docker compose build

# GPTQ / AWQ / FP8 양자화까지 포함
docker compose build --build-arg INSTALL_QUANT=true
```

**직접 설치**

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 양자화 기능 사용 시 (GPU 환경)
pip install -r requirements-quant.txt
```

### 4.3 설정 파일 작성

`deploy.yaml`에 입력 모델, 목표 엔진, 서비스 타입, 경량화 방식, 배포 방식을 기술합니다. `deploy.*.yaml` 예시 파일에서 엔진별·서비스별로 허용되는 값의 조합을 확인할 수 있습니다.

```yaml
input_model: ./Data/models/qwen2.5-1.5b-instruct
input_format: safetensors          # pytorch | safetensors

code_generation:
  target_engine: llama.cpp         # vllm | trtllm | llama.cpp | pytorch | tensorrt
  service_info:
    service_type: sds              # sds | sdf | sdm
    spec:
      invoke_time: user            # user | period | event
      service_ip: 0.0.0.0
      service_port: 8080
  use_optimization: yes
  use_prompt_engineering: no
  use_RAG: no

image_build:
  deploy_method: k3s               # raw | docker | k3s | k8s
  build_info:
    app_name: sds-demo
    image_file: sds-demo:latest
    target_arch: arm               # x86 | arm
    replicas_num: 1
    target_port: 8080
    storage_class: local           # local | minio | nfs | aws

optimization:
  gguf_outtype: q8_0               # llama.cpp 타깃의 가중치 양자화 타입
  quant_info:
    quant_method: rtn              # awq | gptq | rtn | fp8 | nvfp4 | none
    bits: 8
    group_size: 128
    zero_point: true
  calibration_info:                # awq / gptq / fp8 / nvfp4 / wanda 에 필수
    dataset_path: ./Data/calib/calib.txt
    sample_sentence_number: 512
    max_len_tokens_per_sentence: 2048
```

### 4.4 파이프라인 실행

```bash
# 1) 설정 검증 + 단계 계획만 확인 (실제 변경 없음)
python pipeline.py deploy.sds.yaml --dry-run

# 2) 전체 수행
python pipeline.py deploy.sds.yaml

# 3) 모델 변환 단계까지 수행
python pipeline.py deploy.sds.yaml --enable-convert

# 4) 중간 산출물 보존 (단계별 확인용)
python pipeline.py deploy.sds.yaml --keep-tmp

# 5) 컨테이너 이미지 실물까지 빌드
python pipeline.py deploy.sds.yaml --build-image

# 6) Data 폴더 위치 지정
python pipeline.py deploy.sds.yaml -d /work/Data

# 7) 검증 경고도 실패로 처리
python pipeline.py deploy.sds.yaml --strict
```

컨테이너로 실행할 경우 동일한 인자를 compose 서비스에 전달합니다.

```bash
docker compose run --rm pipeline deploy.sds.yaml --dry-run
UID=$(id -u) GID=$(id -g) docker compose run --rm pipeline deploy.sds.yaml
```

### 4.5 개별 모듈 실행

각 모듈은 독립 CLI로도 동작합니다.

```bash
# 프루닝
python model_optimizer/pruner.py ./models/qwen -o ./res/p \
    --method wanda --sparsity 0.5 --dataset ./calib/calib.txt

# 양자화
python model_optimizer/optimizer.py ./models/qwen -o ./res/q \
    --method gptq --bits 4 --group-size 128 --dataset ./calib/calib.txt

# 포맷 변환
python model_converter/model_converter.py \
    -if safetensors -i ./models/qwen -of gguf -o ./res/qwen

# 실행 코드 생성 / 배포 이미지 생성
python code_generator/codegen.py deploy.yaml -o ./res/service
python image_builder/imagebuild.py deploy.yaml -o ./res/image
```

### 4.6 산출물 사용

산출물은 `Data/Output/<service>`에 저장됩니다.

**`deploy_method: raw`** — 실행 코드와 모델이 그대로 들어 있습니다. 서비스 템플릿의 설치 스크립트를 실행해 기동합니다.

```bash
cd Data/Output/sds
./setup_orin.sh              # 템플릿이 제공하는 설치 절차
```

**`docker` / `k3s` / `k8s`** — 빌드 컨텍스트가 구성되어 있습니다.

```bash
cd Data/Output/sds

# Docker
./build.sh && docker compose up -d

# Kubernetes / K3s
./build.sh          # 레지스트리를 쓴다면 이후 push
./deploy.sh
```

요청 구동(`user`) 서비스의 동작 확인은 다음과 같습니다.

```bash
curl localhost:8080/health

curl -X POST localhost:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "안녕하세요", "max_tokens": 64}'
```

주기/이벤트 구동 서비스는 공유 폴더의 `inbox/`에 `.txt` 또는 `{"prompt": "..."}` 형식의 `.json`을 넣으면 처리되며, 결과는 `outbox/`에 `.json`으로 생성되고 처리된 입력은 `done/`으로 이동합니다.

### 4.7 종료 코드

| 코드 | 의미 | 상황 | 대응 |
|---|---|---|---|
| `0` | 성공 | 모든 단계 정상 완료 | — |
| `1` | 단계 실패 | 변환·양자화 등 실행 중 오류 | 로그의 실패 단계 확인 후 재실행 |
| `2` | 설정 오류 | 검증 실패, 입력 모델·Data 폴더 없음 | `deploy.yaml` 또는 경로 수정 |

### 4.8 알려진 제약

- 프루닝은 마스킹 방식이므로 모델 파일 크기와 메모리 사용량이 줄지 않습니다.
- RTN 양자화는 fake-quant 저장이라 파일 크기가 감소하지 않습니다. 실제 압축은 GPTQ, AWQ, 또는 llama.cpp 경로의 `gguf_outtype`을 사용합니다.
- TensorRT 경로는 ONNX export까지 수행하며, `.plan` 엔진 빌드는 배포 대상 장비에서 별도로 수행해야 합니다. TensorRT 엔진은 GPU 아키텍처와 라이브러리 버전에 종속됩니다.
- 서비스 타입은 `Data/<SERVICE>-template` 폴더가 준비된 타입에 대해 동작합니다.
- RAG 관련 설정은 스키마에 정의되어 있으며 연동 모듈은 별도 제공됩니다.
