# TensorRT-Edge-LLM 계측·수집

특정 Edge-LLM 소스 사본에 계측 후크를 넣고 전용 `runner`로 추론합니다.
요청별 Host·GPU 구간과 스레드 CPU 실행·대기를 JSON에 기록하고,
`exporter.py`가 이를 Prometheus 지표로 제공합니다.

## 빌드

대상 runtime commit은 `1ac0f2b99642045125e1c5ac7b109434ba3b36c7`입니다.
Linux AArch64 교차 빌드 도구와 AGX의 CUDA·TensorRT·표준 라이브러리를
준비합니다. 모델·엔진과 SDK는 포함하지 않습니다.

`build-input`에는 아래 설치 경로를 유지한 빌드 입력이 필요합니다.

```text
build-input/
├── home/rtst/TensorRT-Edge-LLM/
│   ├── cpp/                  # runtime·커널 코드와 sm_87 정적 자산
│   ├── examples/utils/
│   ├── 3rdParty/             # nlohmannJson·stb·miniaudio 헤더
│   └── build/                # Core·exampleUtils 정적 라이브러리와 device-link 객체
├── usr/include/aarch64-linux-gnu/
├── usr/local/cuda/targets/sbsa-linux/
├── usr/lib/aarch64-linux-gnu/
└── lib/ld-linux-aarch64.so.1
```

```bash
bash ./build.sh /absolute/path/to/build-input
```

스크립트가 출력한 디렉터리에 `runner`, C++ 검사 프로그램과 `BUILD.sha256`이
생성됩니다. runtime 소스 사본을 수정하고 링크용 파일도 출력 경로에 만듭니다.
다른 Edge-LLM 버전에는 계측 접점을 다시 맞춰야 합니다.

## AGX 설치·실행

기본 설정은 `rtst` 계정과 비대화형 sudo를 사용합니다. 소스를
`/home/rtst/tango2-llm-stages/source/`에, `runner`·`BUILD.sha256`을
`/home/rtst/tango2-llm-stages/bin/`에 배치합니다. 원본 runtime checkout과
plugin은 `/home/rtst/TensorRT-Edge-LLM/`에, Qwen3-1.7B 엔진과 tokenizer는
아래 모델 경로에 준비합니다. 5GiB 이상 여유 공간이 필요합니다.

```bash
cd /home/rtst/tango2-llm-stages
export LD_LIBRARY_PATH=/usr/local/cuda/targets/sbsa-linux/lib:/usr/lib/aarch64-linux-gnu
export EDGELLM_PLUGIN_PATH=/home/rtst/TensorRT-Edge-LLM/build/libNvInfer_edgellm_plugin.so
bin/runner prepare /home/rtst/work/engines/qwen3-1.7b workload.json
sudo install -m 0644 source/tango2-llm-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tango2-llm-exporter tango2-llm-continuous
```

unit의 계정·경로·CPU affinity는 다른 환경에 맞춰 수정합니다. 기본 unit은
12코어 AGX에서 CPU4를 제외합니다. 이미 추론이나 지연 측정이 실행 중이면
먼저 종료합니다. 실행기는 공유 실행 잠금과 중복 실행 검사를 유지합니다.

```bash
systemctl status tango2-llm-exporter tango2-llm-continuous
curl -fsS http://localhost:9464/metrics
sudo systemctl stop tango2-llm-continuous
```

요청 원본은 `runs/`, 실행 묶음은 `campaigns/`에 저장합니다. 상시 기록은
해시 대조 후 순환 보관하므로 장기 보존할 자료는 별도로 복사합니다.
서버 연결은 [상위 monitoring 안내](../README.md)를 따릅니다.

## 검사

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
```

Host·GPU·CPU 값은 경계가 달라 합산하지 않습니다. CPU 값은 계측한 worker와
출력 consumer의 범위입니다. 워밍업·실패·취소와 누락 값은 정상 분포에서
구분합니다.
