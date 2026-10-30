# Runtime_System

**학습된 신경망을 실제 운영 환경에 올려 실행하기까지의 런타임 구성 요소**

TANGO 2 의 세 축 가운데 하나로, 플랫폼 클러스터 바깥에서 **배포 대상 하드웨어**를 직접 다루는 영역입니다. LLMOps 가 모델을 만들어 내면, Runtime_System 이 그 모델을 단말과 서버에서 **실제로 돌아가게** 만듭니다.

---

## 목차

- [1. 개요](#1-개요)
- [2. 전체 시나리오](#2-전체-시나리오)
- [3. 구성 요소](#3-구성-요소)
- [4. 폴더 구조](#4-폴더-구조)
- [5. 어디서부터 보면 되는가](#5-어디서부터-보면-되는가)
- [6. 참고](#6-참고)

---

## 1. 개요

학습이 끝난 신경망은 그대로는 운영 환경에서 쓸 수 없습니다. 실행 엔진이 읽을 수 있는 포맷으로 바꿔야 하고, 대상 장치의 제한된 연산·메모리에 맞게 줄여야 하며, 이를 구동할 실행 코드와 배포 형상이 필요합니다. 올린 뒤에는 성능을 끌어내고 상태를 관찰하며 장애에 대응해야 합니다.

Runtime_System 은 이 전 과정을 세 구성 요소로 나누어 담당합니다.

| 구성 요소 | 역할 | 주 대상 |
|---|---|---|
| **Optimization** | 모델 변환 · 경량화 · 실행 코드 및 배포 이미지 생성 | 공통 (선행 단계) |
| **Runtime_Engine** | 실시간 스케줄링 · 장애복구 · 계측 · 모니터링 | 엣지 단말 (Jetson Orin) |
| **workload_deploy** | 모델 분할 · 자동 확장 · 원격 노드 관리 | 서버 / Kubernetes 클러스터 |

**Optimization 이 배포 가능한 산출물을 만들고, 대상 환경에 따라 Runtime_Engine 또는 workload_deploy 가 그 산출물을 실제로 실행·운영합니다.**

---

## 2. 전체 시나리오

```
                    학습된 신경망 모델  +  deploy.yaml
                                │
                                ▼
                     ┌────────────────────┐
                     │    Optimization    │   모델 변환 · 경량화
                     │                    │   실행 코드 · 배포 이미지 생성
                     └─────────┬──────────┘
                               │
                ┌──────────────┴───────────────┐
                │                              │
         [ 단말 배포 ]                   [ 서버 배포 ]
                │                              │
                ▼                              ▼
     ┌──────────────────────┐      ┌──────────────────────┐
     │    Runtime_Engine    │      │   workload_deploy    │
     │                      │      │                      │
     │ · 실시간 스케줄링     │      │ · 모델 분할 추론      │
     │ · 서비스 장애복구     │      │ · 자동 확장 · 선점    │
     │ · 계측 · 모니터링     │      │ · 원격 노드 관리      │
     └──────────────────────┘      └──────────────────────┘
                │                              │
                ▼                              ▼
       Jetson Orin 에서 실행          Kubernetes 클러스터에서 서비스
```

### 2.1 단말 배포 경로

엣지 단말에 신경망 응용을 올려 실행하는 경우입니다.

1. **Optimization** 이 모델을 단말 실행 엔진이 요구하는 포맷으로 변환하고 경량화합니다. 함께 실행 코드와 설치 구성물을 산출합니다.
2. 산출물을 Orin 으로 옮기고, **Runtime_Engine** 의 결과물을 설치합니다.
3. Runtime_Engine 이 cgroup 단위 실행 등급으로 실시간성을 확보하고, 추론 구간을 계측·수집하며, active 장애 시 backup 으로 서비스 경로를 전환합니다.

### 2.2 서버 배포 경로

서버나 클러스터에서 서비스하는 경우입니다.

1. **Optimization** 이 모델을 변환·경량화하고 컨테이너 이미지와 배포 매니페스트를 산출합니다.
2. **workload_deploy** 의 `remoteManager` 로 이미지를 빌드·푸시하고 대상 노드에 배포하거나, 생성된 매니페스트를 클러스터에 적용합니다.
3. `k8s_autoscaling` 이 부하에 따라 Pod 수를 조정하고 우선순위에 따라 자원을 배분하며, 필요 시 `Parallell_Inference` 로 모델을 분할해 분산 추론합니다.

---

## 3. 구성 요소

### 3.1 Optimization — 모델 변환 · 경량화 · 생성

`deploy.yaml` 한 장으로 경량화부터 배포 이미지 생성까지 전 과정을 자동 수행하는 파이프라인입니다.

| 기능 | 내용 |
|---|---|
| 모델 변환 | PyTorch · Safetensors · GGUF · ONNX 상호 변환, 변환 전후 수치 일치 검증 |
| 모델 경량화 | 정수 양자화(RTN · GPTQ · AWQ · FP8 · NVFP4), 가중치 희소화 |
| 실행 코드 생성 | vLLM · TensorRT-LLM · llama.cpp · PyTorch · TensorRT 대상 코드 생성 |
| 배포 이미지 생성 | Dockerfile · docker-compose · Kubernetes/K3s 매니페스트 · systemd 유닛 |
| 실행 전 검증 | 엔진별 요구 포맷과 허용 양자화를 제약표로 정의해 불가 조합을 사전 차단 |

산출물은 `Data/Output/<service>` 에 쌓이며, 단말 배포와 서버 배포 양쪽의 입력이 됩니다.

→ [`Optimization/README.md`](./Optimization/README.md)

### 3.2 Runtime_Engine — 단말 실시간 실행과 관측

Jetson Orin 의 Linux · Kubernetes 환경을 위한 실시간 스케줄러, 서비스 장애복구, Triton · LLM 계측·모니터링 코드입니다.

| 하위 구성 | 역할 |
|---|---|
| `scheduler` | cgroup별 실행 등급과 CPU 역할을 제어하는 `scx_rtst_orin` |
| `failover` | active 장애 감지·실행 차단 후 backup 으로 서비스 경로 전환 |
| `monitoring` | Triton 의 추론·큐·E2E 지연과 CPU·GPU 지표 수집 (Prometheus · Grafana · OTel · Tempo) |
| `monitoring/llm-stages` | TensorRT-Edge-LLM 내부 계측과 전용 실행기 · exporter |
| `Timestamp` | 기존 자산 |

스케줄러는 Linux 6.12/PREEMPT_RT · sched_ext · cgroup v2 를 전제로 하며, **교차 빌드는 Linux 빌드 호스트에서, 실행은 대상 Orin 에서** 수행합니다. 모니터링 서버는 별도 Linux 서버에서 Prometheus(9090)·Grafana(3000)로 운영합니다.

→ [`Runtime_Engine/README.md`](./Runtime_Engine/README.md)

### 3.3 workload_deploy — 서버 배포와 운영

분산 추론 모델 분할, Kubernetes 자동 확장·우선순위 스케줄링, 원격 노드 컨테이너 관리 도구 모음입니다.

| 하위 구성 | 역할 |
|---|---|
| `Parallell_Inference` | PyTorch 모델(주로 torchvision CNN)을 클라이언트/서버 두 부분으로 분할해 각각 ONNX 로 내보내는 유틸 |
| `k8s_autoscaling` | CPU · 메모리 · API 요청률 기반 HPA 자동 확장과 PriorityClass 선점 스케줄링 구성·평가 자료 |
| `remoteManager` | Go 기반 Control Plane + CLI. 여러 원격 노드의 Docker 컨테이너를 중앙에서 pull · create · start · stop · delete 하고, `build.yaml` 로부터 Dockerfile 을 생성해 이미지 빌드 → Harbor push → 노드 배포까지 수행 |

→ [`workload_deploy/README.md`](./workload_deploy/README.md)

---

## 4. 폴더 구조

```
Runtime_System/
├── README.md                     이 문서
│
├── Optimization/                 모델 변환 · 경량화 · 실행 코드 및 배포 이미지 생성
│   ├── pipeline.py                 파이프라인 드라이버
│   ├── yaml_parser.py              설정 파싱 / 검증 / 실행 계획
│   ├── model_optimizer/            양자화 · 프루닝
│   ├── model_converter/            포맷 변환
│   ├── code_generator/             실행 코드 생성
│   ├── image_builder/              배포 이미지 생성
│   └── Data/                       서비스 템플릿과 산출물
│
├── Runtime_Engine/               단말 실시간 실행 · 장애복구 · 관측
│   ├── scheduler/                  RTST 스케줄러 소스와 독립 빌드 도구
│   ├── failover/                   장애복구 구현과 실행 예제
│   ├── monitoring/                 Prometheus · Grafana · OTel · Tempo 설정
│   │   └── llm-stages/               Edge-LLM 계측 · 실행기 · exporter
│   └── Timestamp/                  기존 자산
│
└── workload_deploy/              서버 배포 · 확장 · 노드 관리
    ├── Parallell_Inference/        모델 분할 및 ONNX 내보내기
    ├── k8s_autoscaling/            HPA 자동 확장 · 우선순위 스케줄링
    └── remoteManager/              원격 노드 컨테이너 관리 (Control Plane + CLI)
```

---

## 5. 어디서부터 보면 되는가

| 하려는 일 | 보아야 할 곳 |
|---|---|
| 학습된 모델을 배포 가능한 형태로 만들고 싶다 | `Optimization/` |
| 모델을 더 가볍게 만들고 싶다 (양자화 · 희소화) | `Optimization/model_optimizer/` |
| 다른 실행 엔진용 포맷으로 바꾸고 싶다 | `Optimization/model_converter/` |
| **엣지 단말에 올려 실행하고 싶다** | `Optimization/` → `Runtime_Engine/` |
| 단말에서 실시간성을 확보하고 싶다 | `Runtime_Engine/scheduler/` |
| 단말 서비스의 장애에 대비하고 싶다 | `Runtime_Engine/failover/` |
| 추론 지연과 자원 사용을 계측·시각화하고 싶다 | `Runtime_Engine/monitoring/` |
| **서버·클러스터에 배포해 서비스하고 싶다** | `Optimization/` → `workload_deploy/` |
| 이미지를 빌드해 여러 노드에 배포하고 싶다 | `workload_deploy/remoteManager/` |
| 부하에 따라 자동 확장하고 싶다 | `workload_deploy/k8s_autoscaling/` |
| 모델을 나누어 분산 추론하고 싶다 | `workload_deploy/Parallell_Inference/` |

---

## 6. 참고

**모니터링 스택이 두 벌입니다.** 대상 환경이 달라 설정과 운영 주체가 분리되어 있습니다.

| 구분 | 대상 | 구성 | 접근 |
|---|---|---|---|
| `Runtime_Engine/monitoring` | Orin 단말 | 별도 Linux 서버의 Prometheus · Grafana | Grafana 3000 / Prometheus 9090 |
| `workload_deploy/k8s_autoscaling/prometheus` | Kubernetes 클러스터 | kube-prometheus-stack (Helm) | Grafana 30300 / Prometheus 30090 (NodePort) |

**아키텍처가 섞인 환경을 전제합니다.** 단말은 ARM64(Jetson Orin), 클러스터는 amd64 와 arm64 노드가 함께 있습니다. Optimization 의 `target_arch` 설정과 멀티 아키텍처 이미지 빌드가 이 때문에 필요합니다.

---

## 관련 문서

- 상위 저장소 개요 — [`../README.md`](../README.md)
- 플랫폼(LLMOps) 구성 — [`../LLMOps/`](../LLMOps/)
