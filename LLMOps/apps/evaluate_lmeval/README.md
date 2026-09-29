# evaluate-lmeval

lm-evaluation-harness 0.4.12 벤치마크 **실채점** 컨테이너(GPU 1장, vLLM). `evaluate-benchmark-mock`
(해시 점수)을 대체한다. 설계·P0 실측: `LLMOps/docs/2026-09-28-lmeval-benchmark-scorer-design.md`.

같은 이미지를 매니페스트 두 개가 쓴다.

| 매니페스트 | 벤치마크 | 비고 |
|---|---|---|
| `evaluate-lmeval` (`manifest.yaml`) | lm-eval 17종 + `custom` | 코드 실행 불가 |
| `evaluate-lmeval-code` (`manifest-code.yaml`) | `humaneval` | env `LMEVAL_ALLOW_CODE_EXEC=1` — 모델 생성 코드를 실행한다. 이 파드는 코드 벤치마크만 받는다 |

둘 다 `network.isolate: true` — egress 전면 차단, SA 토큰 없음, `/model`(RW) 미마운트.

## 계약

SP-1 외부 컨테이너(`/health` `/live` `/info` `/run` `/jobs/{id}` `/jobs/{id}/cancel`, port 8000).

- 입력 params: `benchmarks`(id 목록 — `registry.py`), `checkpoint_name`(커밋 이름 한 조각,
  `/models/checkpoints/<name>`), `limit`(태스크당 문항 상한, 선택), `datasets`(custom 은 `[0]` 이
  평가 데이터), `max_new_tokens`·`lang`(custom 선택).
- 가중치: merged 커밋은 그대로, LoRA 커밋(`adapter_config.json`)은 기반 커밋 위에
  `merge_and_unload` 해 `/tmp` 에 쓴 뒤 올린다(서빙 파드와 같은 가중치).
- 출력 `/output/metrics.json`: mock 과 같은 최상위(`results`/`averages`/`benchmark_set`/`metric_map`,
  `mock:false`) + `checkpoint` + `lmeval.benchmarks[<id>]`(지표·서브태스크·건수·경고). 점수는 0~100.
  custom 은 `/output/custom_samples.jsonl` 에 샘플별 입력/예측/정답/점수.

## 빌드·등록

```bash
./build.sh              # 빌드(스냅샷 + lm-eval 층 + 17종 데이터 적재 ≈ 1GB) → 노드 containerd 적재
PUSH=1 ./build.sh       # + docker.io push (신규 서버)
# 매니페스트: fb_external_container/manifests/ 사본이 부팅 시드로 등록된다 → BFF 재시작
kubectl -n <ns> rollout restart deploy/jfb-app-external-container
```

버전을 올릴 때: 이미지 태그 · `manifest*.yaml` version(사본 포함) · `fb_utils/settings.py`
`BENCHMARK(_CODE)_MANIFEST_VERSION` 을 함께 바꾼다(`llm_evaluation/tests/test_benchmark_catalog.py`).

## 주의

- **DROP 은 수정본(`drop_tango`)** — upstream 정답 템플릿이 필드 이름 목록을 정답으로 렌더해 0 점이
  된다(`prepare_tasks.py`). 공개 lm-eval DROP 수치와 비교할 수 없다.
- chat template 을 쓰지 않는다(리더보드 관례). custom 만 토크나이저에 템플릿이 있으면 쓰고
  `enable_thinking=False` + `<think>` 제거.
- 테스트: `python3 -m pytest tests -q` (GPU 불필요, BLEU 2건은 sacrebleu 가 있을 때만).
