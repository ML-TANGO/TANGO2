# mock-convert-plugin

양자화·포팅(**SP-4 / v0.4 3.9**) convert 컨테이너 **mock**.
플랫폼 소유 llama.cpp convert 컨테이너의 mock — 실제 변환 이미지 도착 전 플랫폼 측
convert job 와이어링(학습 후 양자화 → 포팅 패키지 다운로드)을 end-to-end 검증한다.

- 계약: `../hello-plugin/external-container-spec.md` (SP-1)

## 동작
- `job_type: convert`, `execution_mode: async` (학습 후 1회성 변환).
  - ※ SP-4 설계는 batch를 가정했으나, 플랫폼 계약상 **batch=HTTP 서버 없는 run-and-exit**(k8s Job watch)이고
    본 mock은 HTTP 서버(/run+poll) 기반이라 **async**로 둔다(generate와 동일·검증된 launch/poll/`/output` 와이어링).
    실제 llama.cpp 컨테이너를 run-and-exit로 만들 경우 batch 전환 가능(플랫폼 batch watch 지원 시).
- 입력: merged 모델(`/model`) + params(`target_quant`=q4/q5/q6, `model_name`).
- `/run` → `/output` 에 **포팅 패키지** 고정 생성:
  - `<model>.<quant>.gguf` (mock 헤더 + 압축비 반영 크기)
  - `inference.py` · `run.sh` · `config.json` · `metadata.json`
- ⑬ 코드 수정 UI 없음 — **패키지 다운로드 전용**.

## 파이프라인 연동 (플랫폼 convert job)
1. 학습 완료 모델에서 **'양자화' 버튼**(명시 트리거) → quantize 모달(Q4/Q5/Q6 + target_device).
2. 플랫폼이 merged 모델 경로를 `/model` 로 주입 + `POST /api/v1/jobs`(job_type=convert).
3. `GET /api/v1/jobs/{id}` 폴링 → 완료 시 `/output` 포팅 패키지 회수 → 다운로드.

```json
// params.json 예시
{ "target_quant": "q5", "model_name": "my-llm" }
```

## 빌드·등록 (배포 단계)
```bash
# 1) 이미지 빌드 (로컬 containerd k8s.io 네임스페이스)
cd examples/mock-convert-plugin
nerdctl --namespace=k8s.io build -t docker.io/acrylaaai/mock-convert-plugin:1.0.0 .

# 2) manifest 등록 (fb_external_container)
curl -X POST http://<external-container-svc>/api/v1/manifests \
     -H 'Content-Type: application/json' --data-binary @manifest.yaml   # 또는 BFF 경유

# 3) 학습 모델에서 양자화 실행 → /output 포팅 패키지 다운로드 확인
```

> 실제 llama.cpp 컨테이너 도착/제작 시: 동일 계약(job_type=convert, /output 패키지)으로
> 이 컨테이너만 교체하면 플랫폼/와이어링 변경 없이 동작.
