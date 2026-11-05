# External Container Manifest 예시 (계약서 v1.1)

본 디렉토리는 `examples/hello-plugin/external-container-spec.md` (외부 컨테이너 인터페이스 계약서 v1.1) 의
**Hybrid 컨테이너 사례** manifest 작성 양식을 보여주는 참고용 예시입니다.

## 파일

| 파일 | 설명 |
|---|---|
| `eva-vlm-infer.yaml` | SDS-VLM 추론 서비스 manifest (sync, 워크스페이스당 1 pod 영구 배포) |
| `eva-vlm-train.yaml` | SDS-VLM 4-phase 파인튜닝 학습 manifest (async, 학습 1회 lifecycle) |

두 manifest 는 **같은 Docker 이미지를 참조**하되 entrypoint 와 lifecycle 만 다름.
한 코드베이스에 추론 + 학습 두 성격이 있는 Hybrid 컨테이너의 분리 등록 패턴.

## 관련 문서

- `examples/hello-plugin/external-container-spec.md` — 계약서 전문 (§6 manifest schema)
- `docs/Tango MSA 탑재 가이드.md` — 기본 contract (`/health`, `/info`, `/run`)

## 협력기관용 작성 가이드

1. 본 예시를 복사하여 `metadata.name`, `metadata.vendor`, `metadata.contact` 등 식별
   정보를 본인 서비스에 맞게 수정.
2. `spec.image` 를 본인 registry 경로로 변경 (Phase 1 PoC 는 Docker Hub 도 허용).
3. `spec.endpoints` — 본인 컨테이너의 실제 URL 을 명시. 계약서 표준 default 패턴
   (`/jobs/{id}` 등) 을 그대로 따르는 경우 해당 필드 생략 가능.
4. `spec.resources.gpu_memory`, `capabilities.estimated_*` 는 실제 측정 후 조정.
5. Hybrid (추론 + 학습) 인 경우 두 manifest 로 분리하고 `service_family`,
   `contract_version`, `model_artifact_format`, `checkpoint_namespace` 4개 필드를
   **두 manifest 에 동일 값으로** 명시 (pair 일관성 검증용).

## 검증

```bash
# YAML syntax 검증
yq eval '.' eva-vlm-infer.yaml
yq eval '.' eva-vlm-train.yaml

# 두 manifest 가 paired 인지 확인 (4개 shared field 일치)
diff <(yq eval '.spec | {service_family, contract_version, model_artifact_format, checkpoint_namespace}' eva-vlm-infer.yaml) \
     <(yq eval '.spec | {service_family, contract_version, model_artifact_format, checkpoint_namespace}' eva-vlm-train.yaml)
# (empty diff = paired OK)
```
