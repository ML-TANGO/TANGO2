# mock-generate-plugin

생성형 데이터 파이프라인(**WBS 1.1 / v0.4 3.3**) BE 스캐폴드용 **mock 외부 컨테이너**.
고려대 LLM1/LLM2(프롬프트·데이터 생성) 모듈 **수령 전**에 파이프라인 end-to-end
(생성 노드 → 전처리 → 학습)를 검증하기 위한 고정 출력 컨테이너다.

- 계약: `../hello-plugin/external-container-spec.md` (SP-1)

## 동작
- `job_type: generate` (신규) → fb_scheduler chart 가 `work_func_type=generation`,
  `pod_type=generation` 라벨 부착 → fb_monitoring 이 GPU 귀속(`label_job_id` 키).
- `/run` 호출 시 `/output/result.jsonl` 에 VLM instruction 레코드를 `count` 개 생성:
  ```json
  {"image": "images/sample_1.jpg", "instruction": "이 이미지를 설명하시오.", "output": "[mock] 생성된 설명 1"}
  ```
- params: `count`(기본 10) · `instruction` · `image_prefix`.

## 파이프라인 연동 (fb_pipeline generation 노드)
generation task 의 `built_in_params`(JSON) 에 manifest 참조 + 생성 파라미터:
```json
{
  "manifest_name": "mock-generate",
  "manifest_version": "1.0.0",
  "params": {"count": 20, "instruction": "이 이미지를 설명하시오."},
  "output_subdir": "generation/pipeline-<id>-<task>"
}
```
fb_pipeline 런타임이 `POST /api/v1/jobs` → `GET /api/v1/jobs/{id}` 폴링으로 실행한다
(`apps/fb_pipeline/helm/pipe/code/pipeline.py` `execute_generation`).

## 빌드·등록 (배포 단계)
```bash
# 1) 이미지 빌드 (로컬 containerd k8s.io 네임스페이스)
cd examples/mock-generate-plugin
nerdctl --namespace=k8s.io build -t docker.io/acrylaaai/mock-generate-plugin:1.0.0 .

# 2) manifest 등록 (fb_external_container)
curl -X POST http://<external-container-svc>/api/v1/manifests \
     -H 'Content-Type: application/json' --data-binary @manifest.yaml   # 또는 BFF 경유

# 3) 파이프라인 generation 노드 생성 후 실행 → /output/result.jsonl 확인
```

> 고려대 LLM1/LLM2 컨테이너 도착 시: 동일 계약(manifest endpoints·job_type)으로
> 이 컨테이너만 교체하면 파이프라인/모니터링 변경 없이 동작.
