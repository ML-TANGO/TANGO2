# convert — 플랫폼 소유 llama.cpp 양자화·포팅 컨테이너 (SP-4 / v0.4 3.9)

**플랫폼이 소유·구현**하는 양자화/GGUF 포팅/프루닝 컨테이너. `examples/mock-convert-plugin`
의 고정출력 mock 을 대체하는 **실로직** 본체다.

> ⚠️ 협력기관 제공물이 아님. 배포만 `external_container` launch 메커니즘을 재사용한다
> (SP-4 J-1: `fb_porting` 신규 서비스 회피). SP-1 계약을 그대로 따르므로 플랫폼/FE/
> lineage/다운로드 와이어링은 변경 없이 동작한다 — 컨테이너만 mock → 본 이미지로 교체.

## 실로직

베이스 `ghcr.io/ggml-org/llama.cpp:full` (convert_hf_to_gguf.py + llama-quantize +
torch(cpu)/transformers/gguf) 위에 SP-1 FastAPI 래퍼(`app.py`)만 얹음.

1. (옵션) **프루닝** — transformers 로 모델 로드 → Linear 가중치 |w| 하위 `prune_sparsity`(기본 0.5) 0 처리 → 재저장. ⚠️ unstructured 라 GGUF(dense) 용량은 안 줄어듦(spec RT-Optimization §9 "실이득 작음"). 실로직은 있되 효과 제한 — 추후 structured/2:4 로 교체 가능.
2. **HF merged 모델 → f16 GGUF** — `convert_hf_to_gguf.py /model --outtype f16`.
3. **타겟 양자화** — `llama-quantize f16.gguf out.gguf {Q4_K_M|Q5_K_M|Q6_K}`.
4. **포팅 패키지**(`/output`) — `<model>.<q>.gguf` + inference.py + run.sh + config.json + metadata.json. ⑬ 코드 수정 UI 없음(다운로드만).

```json
// params.json
{ "target_quant": "q5", "model_name": "my-llm", "prune": false, "prune_sparsity": 0.5 }
```

## 빌드·등록

```bash
# 1) 이미지 빌드 (buildkitd 없음 → docker build + nerdctl load)
cd apps/convert
docker build -t docker.io/acrylaaai/convert-llamacpp:1.0.0 .
docker save docker.io/acrylaaai/convert-llamacpp:1.0.0 | nerdctl --namespace=k8s.io load

# 2) manifest 등록 (JSON 엔벨로프)
#    POST /api/v1/manifests  {"manifest_yaml": "<manifest.yaml raw>"}

# 3) 플랫폼 전환: llm_model 의 CONVERT_MANIFEST_NAME=convert-llamacpp (env)
#    → 모델 '양자화' 액션이 이 컨테이너로 convert job 발행.
```

## mock 과의 관계

| | `examples/mock-convert-plugin` | `apps/convert` (본체) |
|---|---|---|
| 로직 | 고정출력(stub) | 실 llama.cpp 변환 |
| 용도 | GPU/모델 없는 환경의 와이어링 검증 | 운영 양자화 |
| 이미지 | acrylaaai/mock-convert-plugin | acrylaaai/convert-llamacpp |

계약(job_type=convert, /model 입력, /output 패키지, SP-1 endpoint)이 동일하므로
`CONVERT_MANIFEST_NAME` env 만 바꾸면 무중단 전환.
