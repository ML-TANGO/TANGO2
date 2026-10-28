# RTST Runtime Engine

## 1. 개요

Jetson Orin의 Linux·Kubernetes 환경을 위한 실시간 스케줄러,
서비스 장애복구, Triton·LLM 계측·모니터링 코드입니다.

## 2. 주요 내용

| 구성 | 기능 |
|---|---|
| 스케줄러 | cgroup별 실행 등급과 CPU 역할을 제어하는 `scx_rtst_orin` |
| 장애복구 | active 장애 감지·실행 차단 후 backup으로 서비스 경로 전환 |
| Triton 모니터링 | 기존 Triton의 추론·큐·E2E 지연과 CPU·GPU 지표 수집 |
| LLM 모니터링 | TensorRT-Edge-LLM 내부 계측과 Prometheus·Grafana 연계 |

## 3. 폴더 구성

```text
Runtime_System/Runtime_Engine/
├── scheduler/              # RTST 스케줄러 소스와 독립 빌드 도구
├── failover/               # 장애복구 구현과 실행 예제
├── monitoring/             # Prometheus·Grafana·OTel·Tempo 서버 설정
│   └── llm-stages/          # Orin의 Edge-LLM 계측·실행기·exporter
└── Timestamp/              # 기존 자산
```

## 4. 설정 및 실행

스케줄러는 Linux 6.12/PREEMPT_RT·sched_ext·cgroup v2를 사용합니다.
교차 빌드는 Linux 빌드 호스트에서, 실행은 대상 Orin에서 수행합니다.
아래 명령은 필요한 SDK·이미지·모델과 장비 설정을 준비한 환경의 예제입니다.

### 스케줄러

대상 커널 소스·BTF와 ARM64 sysroot, bpftool을 준비해 빌드합니다.

```bash
cd scheduler
KSRC=/path/to/kernel-6.12 \
KOUT=/path/to/kernel-build \
SYSROOT=/path/to/aarch64-sysroot \
BPFTOOL=/path/to/bpftool bash ./build.sh
```

출력은 `build/build/bin/scx_rtst_orin`입니다. 바이너리를 AGX로 복사한 뒤
아래처럼 실행합니다. 12코어 AGX의 예입니다.

```bash
sudo ./scx_rtst_orin run --rt-cpu 4 \
  --online-mask 0xfff --shared-mask 0xfef --background-mask 0xfe0
```

상세 설정은 [scheduler/README.md](scheduler/README.md)를 참고합니다.

### 장애복구

Kubernetes·containerd·iptables-nft·Python 3.12와
`rtst-rttools:orin-k1` 이미지를 준비합니다. `service.yaml`의 노드명과
실행기의 노드 설정을 맞춥니다. 기본 NX 환경의 실행 예입니다.

```bash
cd failover
TC2_NODE_NAME=mic711-rt TC2_NODE_IP=10.2.58.155 \
  ./run-service-integration.sh "$HOME/tango2-evidence/UNIQUE_ID" demo hang
```

### Triton 모니터링

기존 Triton 서버의 `:8002/metrics`를 수집해 전처리·추론·후처리,
입출력·큐·E2E 지연과 CPU·GPU 지표를 표시합니다.
`monitoring/prometheus/targets/triton/targets.json`에 서버 주소를 지정합니다.

```json
[
  {"targets": ["TRITON_ADDRESS:8002"], "labels": {"service": "triton"}}
]
```

기존 `monitoring/grafana/provisioning/dashboards/boards/triton.json` 대시보드를
사용합니다. 지연 summary는 Triton의 `--metrics-config=summary_latencies=true`로
활성화하고, 대시보드의 모델명·분위수를 서버 설정에 맞춥니다.

### LLM 모니터링

TensorRT-Edge-LLM `1ac0f2b` 버전의 소스 사본에 계측 후크를 넣고
전용 실행기를 빌드합니다. CUDA·TensorRT·runtime 빌드 입력과 모델 엔진은
별도로 준비합니다.

```bash
cd monitoring/llm-stages
bash ./build.sh /path/to/build-input
```

빌드한 `runner`·`BUILD.sha256`은 AGX의
`/home/rtst/tango2-llm-stages/bin/`에, 관측 소스는 같은 위치의 `source/`에
배치합니다. 기본 설정은 `rtst` 계정·비대화형 sudo와 아래 모델 경로를 사용합니다.
AGX에서 시료를 준비하고 exporter·상시 추론을 시작합니다.

```bash
cd /home/rtst/tango2-llm-stages
export LD_LIBRARY_PATH=/usr/local/cuda/targets/sbsa-linux/lib:/usr/lib/aarch64-linux-gnu
export EDGELLM_PLUGIN_PATH=/home/rtst/TensorRT-Edge-LLM/build/libNvInfer_edgellm_plugin.so
bin/runner prepare /home/rtst/work/engines/qwen3-1.7b workload.json
sudo install -m 0644 source/tango2-llm-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tango2-llm-exporter tango2-llm-continuous
```

### 모니터링 서버

별도 Linux 서버에서 Prometheus가 Triton의 `:8002/metrics`와 Orin LLM의
`:9464/metrics`를 수집하고 Grafana가 표시합니다. 서버에는 target JSON과
dashboard JSON을 배치합니다.
target·dashboard는 30초 간격으로 자동 반영됩니다.

기존 공용 서버는 `/opt/monitoring`에서 운영합니다. Grafana는 3000,
Prometheus는 9090 포트입니다. 최초 설치와 파일 배치는
[monitoring/README.md](monitoring/README.md)를 참고합니다.
