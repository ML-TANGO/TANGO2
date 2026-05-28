# Future Work: Scheduler improvements related to fine-tuning admission

이번 플랜([2026-04-21-scheduler-fine-tuning-admission-guard-plan.md](superpowers/plans/2026-04-21-scheduler-fine-tuning-admission-guard-plan.md))이 다루지 않은 항목 정리.

## 1. `msa_jfb.instance` 에 진짜 ceiling 컬럼 추가

현재 스키마에는 `instance_allocate` 가 없다. `get_models_sync` SQL의 `m.instance_count as instance_allocate` 는 잘못된 의미 매핑이어서 제거(이번 플랜 Task 1).

앞으로 per-instance 동시 실행 상한을 DB로 명시하려면:
- `ALTER TABLE msa_jfb.instance ADD COLUMN max_instance_count INT DEFAULT 1;`
- `scheduler.py::process_instance_queue_item` line 992-994의 `instance["instance_allocate"]` 참조는 별도 경로(아마 `workspace_instance` JOIN)로 공급되므로 그쪽 쿼리와 함께 정합성 확인 필요.
- 현재는 K8s node budget guard(Task 4)가 실질적 상한 역할을 하므로 시급하진 않음.

## 2. Scheduler의 cross-model 합산을 `process_item_type` admission에도 반영

`scheduler.py:721-725`에서 이미 `workspace_instance_used_resource[inst_id]` 로 동일 instance_id를 쓰는 모든 모델 합산을 계산하지만, **`process_item_type` 단계의 admission에는 미사용**(로그 전용). 반면 `process_instance_queue_item` 의 line 996-1005에서는 같은 dict를 실제 게이트로 사용. 단계 간 일관성 정리 필요.

## 3. 파인튜닝 pod의 `requests.cpu = 0` 재검토

`apps/fb_scheduler/helm_chart/fine_tuning/templates/pod.yaml:133` 에서 `requests: cpu: 0`. 이 때문에 K8s scheduler 입장에서 cpu 예산은 무제한처럼 보임. 19 cores 학습 프로세스가 `requests=0`로 들어가면 노드 cpu 경합 시 타 workload 우선순위 보장이 약화. Guaranteed QoS 포기가 의도적인지 확인 필요.

## 4. Node budget 조회 캐싱

`_fine_tuning_node_budget_guard`는 매 스케줄 틱마다 `v1.read_node` + `v1.list_pod_for_all_namespaces` 호출. 단일 노드 + 파인튜닝 드문 트리거 환경에서는 무시할 만하지만, 다수 노드/다수 대기 파인튜닝 환경에선 API 서버 부하가 될 수 있음. 필요 시 짧은 TTL(e.g. 5초) in-process 캐시 추가.

## 5. 하드코딩 Hugging Face 토큰 (별도 plan 필요 — critical)

`apps/fb_utils/settings.py:174`의 `HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", <리터럴>)` 에서 default fallback으로 **실제 HF access 토큰이 하드코딩**되어 있음(리터럴 값은 본 문서에 기재하지 않음 — 유출 경로 최소화 목적. 필요 시 git blame/log로 확인).

- 리터럴 토큰이 git history에 공개됨. `llm_run.py:223` 을 통해 파인튜닝 pod env로 주입되므로 env var 미설정 deploy는 유출 토큰을 실사용.
- Codex adversarial review가 critical로 지적한 사항이며 본 plan 범위에서 제외(사용자 결정). 별도 plan으로 추적 필요:
  1. HF 대시보드에서 기존 토큰 revoke(외부 액션)
  2. 새 토큰 발급 후 K8s Secret/Helm values/env var로 주입
  3. `settings.py:174` default 값을 `""`로 교체(fail-closed)
  4. 노출 리터럴이 repo 어디에도 남지 않았는지 토큰 prefix 기반 `grep`으로 검증(prefix는 별도 채널로 공유)
  5. (선택) values/Secret 이행 파이프라인 표준화

순서상 (2)번 완료 후 (3)번, (1)번은 (3)번 이후 마지막으로 — 운영 중단 방지.

## 6. 별개 이슈 링크

- 파인튜닝 OOM → 대시보드 표시 불일치: [`2026-04-21-fine-tuning-oom-dashboard-leak-plan.md`](superpowers/plans/2026-04-21-fine-tuning-oom-dashboard-leak-plan.md)
- 파인튜닝 stop API 리소스 leak: [`2026-04-21-fine-tuning-stop-resource-leak-plan.md`](superpowers/plans/2026-04-21-fine-tuning-stop-resource-leak-plan.md)
