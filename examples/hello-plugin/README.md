# hello-plugin — 외부 컨테이너 템플릿

Tango 플랫폼의 **외부 컨테이너 인터페이스 계약(SP-1 v1)** 을 준수하는 최소 예제입니다.
협력기관이 새 컨테이너를 만들 때 이걸 fork 해서 시작점으로 쓰세요. 계약 전문은
[`external-container-spec.md`](external-container-spec.md).

## 무엇을 보여주나

- **표준 HTTP endpoint**: `/health`(readiness) · `/live`(liveness) · `/info` ·
  `/run` · `/jobs/{id}`(async 상태) · `/jobs/{id}/cancel`
- **async 작업 lifecycle**: `/run` 이 `202 + job_id` 반환 → 플랫폼이 `/jobs/{id}` polling →
  완료/실패/취소
- **입력 규약**: `/run` body 의 `params` (없으면 `/input/params.json` fallback)
- **출력 규약**: `/output/` 파일 + **stdout JSON Lines**(실시간 progress/error)
- **플랫폼 주입 env**: `JF_*` (item_id, job_type, execution_mode, params/output path, port)
- **보안**: non-root(UID 1000) + readOnlyRootFilesystem 호환(write 는 `/output`,`/tmp` 만)

## 파일

```
hello-plugin/
├── manifest.yaml         # 플랫폼 등록용 매니페스트 (tango.acryl.ai/v1)
├── app.py                # FastAPI — 표준 endpoint + 데모 작업(_run_job)
├── requirements.txt
├── Dockerfile            # non-root / readOnlyRootFS 호환 (spec §7.1)
├── params.example.json   # /run body 또는 /input/params.json 예시
└── README.md
```

## 로컬에서 실행 / 테스트

```bash
pip install -r requirements.txt
export JF_OUTPUT_PATH=./out && mkdir -p ./out          # /output 대신 로컬 쓰기 경로
JF_OUTPUT_PATH=./out python app.py                      # JF_PORT 도 존중 (또는 uvicorn --app-dir . app:app --port 8000)

# 다른 터미널에서
curl localhost:8000/health                                  # {"status":"ready"}
curl localhost:8000/info
# /run body = params dict 를 그대로 (플랫폼 generic adapter 와 동일). envelope {"params":{...}} 도 허용.
JOB=$(curl -s -XPOST localhost:8000/run -H 'Content-Type: application/json' \
      -d '{"name":"tango","steps":5}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
curl localhost:8000/jobs/$JOB                                # 진행 상태 polling (running→completed)
curl -XPOST localhost:8000/jobs/$JOB/cancel                  # 취소 (선택)
```
실행 중 stdout 에 `{"event":"progress",...,"percent":...}` JSON Lines 가 흘러나오는 것을 확인하세요.
산출물은 `./out/result.json`, `./out/metrics.json`.

### Docker

```bash
docker build -t hello-plugin:1.0.0 .
# /output 은 write 대상이라 반드시 mount (컨테이너는 UID 1000, readOnlyRootFS 가정).
mkdir -p ./out
docker run --rm -p 8000:8000 -v "$(pwd)/out:/output" hello-plugin:1.0.0
# 포트 변경 테스트: -e JF_PORT=9000 -p 9000:9000 (ENTRYPOINT 가 ${JF_PORT} 존중)
```

## 플랫폼에 등록 + 실행

1. 이미지를 접근 가능한 registry 로 push 하고 `manifest.yaml` 의 `spec.image` 를 그 ref 로 수정.
2. 매니페스트 등록 (운영자):
   ```bash
   curl -XPOST <fb_external_container>/api/v1/manifests \
     -H 'Content-Type: application/json' \
     -d "$(python3 -c 'import json,sys;print(json.dumps({"manifest_yaml":open("manifest.yaml").read()}))')"
   ```
3. 실행 (BFF):
   ```bash
   curl -XPOST <llm_model_bff>/api/external/jobs -H 'Content-Type: application/json' \
     -d '{"manifest_name":"hello-plugin","manifest_version":"1.0.0","workspace_id":1,
          "params":{"name":"tango","steps":5}}'
   ```
   플랫폼이 pod 를 띄우고 `/run` 호출 → `/jobs/{id}` 로 추적합니다.

## 내 컨테이너로 바꾸기 (fork 가이드)

1. **`app.py` 의 `_run_job()` 내부만** 자기 작업으로 교체 (학습/추론/전처리 등).
   endpoint·입출력·stdout·output 규약은 그대로 둡니다. (`/run` body 는 params dict 를
   그대로 받음 — envelope 아님. stdout 이벤트는 spec §4.2: progress/metric/log/error.)
2. **`manifest.yaml`** 수정하고, **`app.py` 의 `CAPABILITIES` 를 manifest.capabilities 와 일치**시킵니다(`/info` 가 그대로 반영):
   - `metadata`(name/version/vendor/contact), `spec.image`
   - `job_type`/`execution_mode`(sync 면 `/run` 이 200+결과 직접 반환 — `jobs` endpoint 불필요)
   - `resources`(GPU 필요 시 `gpu>0` + `gpu_memory`), `inputs`(dataset/base_model required), `secrets.required`
   - `capabilities.estimated_startup_seconds`(모델 로딩 시간 고려)
3. **GPU 컨테이너**면 `Dockerfile` base 를 `nvidia/cuda:...-runtime` 으로. CUDA/torch 는
   배포 클러스터 driver 호환 버전으로(운영 측 조정).
4. **모델 로딩**이 있으면 `/health` 가 로딩 중 `503 {"status":"loading"}`, 완료 후 `200` 을
   반환하도록. (`/live` 는 로딩과 무관하게 항상 `200`)
5. **멀티GPU 학습**이면 가시 GPU 수(`NVIDIA_VISIBLE_DEVICES` UUID 개수)≥2 일 때
   `torchrun --nproc_per_node=N` 으로 실행하고, 종료 시 `dist.barrier()`+`destroy_process_group()`
   호출 (spec §3.2).

## 규약 체크리스트 (등록 전)

- [ ] async 면 endpoints 에 `info/health/run/jobs` 모두 존재, `jobs`/`cancel` 에 `{id}` 포함
- [ ] `/health` readiness, `/live` liveness 분리
- [ ] 동적 파라미터는 `/run` body 또는 `/input/params.json` (환경변수로 X)
- [ ] 산출물은 `/output/` 아래에만, 진행상황은 stdout JSON Lines
- [ ] 에러는 `{"event":"error","code":"E_...","fatal":true}` (코드 `E_SCREAMING_SNAKE`)
- [ ] Dockerfile: `USER 1000`, write 는 mount 영역만, `PYTHONUNBUFFERED=1`
- [ ] `spec.capabilities.estimated_startup_seconds` 명시 (HTTP 컨테이너)
