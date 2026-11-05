# Future Work: Scheduler improvements related to fine-tuning admission

2026-04-21 파인튜닝 admission guard 작업(노드 예산 기반 guard 추가, 파인튜닝 모델 조회 SQL 의 `instance_allocate` alias 제거)이 다루지 않은 항목 정리. 최종 점검: 2026-10-28.

코드 위치 기준: 스케줄러 본체는 `apps/fb_scheduler/src/scheduler/scheduler.py`, 노드 예산 조회는 `apps/fb_utils/kube.py`. (줄 번호는 자주 바뀌므로 함수 이름으로 적는다.)

| # | 항목 | 상태 |
|---|---|---|
| 1 | `msa_jfb.instance` 진짜 ceiling 컬럼 | 미착수 |
| 2 | cross-model 합산을 `process_item_type` admission 에 반영 | 미착수 |
| 3 | 파인튜닝 pod `requests.cpu = 0` 재검토 | 미착수 |
| 4 | Node budget 조회 캐싱 | 미착수 |
| 5 | 하드코딩 Hugging Face 토큰 | **해결** |
| 6 | 별개 이슈 | 아래 참고 |

## 1. `msa_jfb.instance` 에 진짜 ceiling 컬럼 추가

현재 스키마에는 `instance_allocate` 가 없다. 파인튜닝 모델 조회(`apps/fb_utils/llm_db/db_model.py::get_models_sync`)의 `m.instance_count as instance_allocate` 는 잘못된 의미 매핑이어서 제거했다.

- 지금은 `process_item_type` 이 `instance_allocate → instance_count → 1` 순으로 폴백한다(파인튜닝 모델은 `instance_allocate` 를 공급하지 않음).
- `process_instance_queue_item` 은 `instance["instance_allocate"]` 를 그대로 참조한다. 이 값은 별도 경로(아마 `workspace_instance` JOIN)로 공급되므로 그쪽 쿼리와 함께 정합성 확인 필요.
- per-instance 동시 실행 상한을 DB로 명시하려면:
  - `ALTER TABLE msa_jfb.instance ADD COLUMN max_instance_count INT DEFAULT 1;`
- 현재는 K8s node budget guard(`_fine_tuning_node_budget_guard`)가 실질적 상한 역할을 하므로 시급하진 않음.

## 2. Scheduler의 cross-model 합산을 `process_item_type` admission에도 반영

`process_item_type` 에서 이미 `workspace_instance_used_resource[inst_id]` 로 동일 instance_id를 쓰는 모든 모델의 사용량을 합산하지만, **같은 함수의 admission 비교에는 미사용**(로그 전용 — 비교는 item 단위 사용량으로 한다). 반면 `process_instance_queue_item` 에서는 같은 dict를 실제 게이트로 사용. 단계 간 일관성 정리 필요.

## 3. 파인튜닝 pod의 `requests.cpu = 0` 재검토

`apps/fb_scheduler/helm_chart/fine_tuning/templates/pod.yaml` 의 `resources.requests` 에서 `cpu: 0`. 이 때문에 K8s scheduler 입장에서 cpu 예산은 무제한처럼 보임. 19 cores 학습 프로세스가 `requests=0`로 들어가면 노드 cpu 경합 시 타 workload 우선순위 보장이 약화. Guaranteed QoS 포기가 의도적인지 확인 필요.

## 4. Node budget 조회 캐싱

`_fine_tuning_node_budget_guard` 는 매 스케줄 틱마다 `apps/fb_utils/kube.py::get_node_request_budget` 을 통해 `v1.read_node` + `v1.list_pod_for_all_namespaces`(해당 노드 필터)를 호출한다. 단일 노드 + 파인튜닝 드문 트리거 환경에서는 무시할 만하지만, 다수 노드/다수 대기 파인튜닝 환경에선 API 서버 부하가 될 수 있음. 필요 시 짧은 TTL(e.g. 5초) in-process 캐시 추가.

## 5. 하드코딩 Hugging Face 토큰 — 해결

`apps/fb_utils/settings.py` 의 `HUGGINGFACE_TOKEN` 기본값은 이제 빈 문자열이다(`os.getenv("HUGGINGFACE_TOKEN", "")`, fail-closed).

- 토큰은 values 의 `global.jfb.settings.huggingface.token` → ConfigMap `jfb-settings` 의 `HUGGINGFACE_TOKEN` 환경변수로만 주입된다(`devops/INSTALL.md`).
- 값을 비워 두면 기동 시 HF login 을 건너뛴다(오프라인/폐쇄망 설치 지원). gated/private 저장소를 쓸 때만 입력한다.

## 6. 별개 이슈

- 파인튜닝 OOM → 대시보드 자원 집계 불일치: 2026-04-21 수정 — 대시보드가 OOMKilled 파인튜닝 Pod을 자원 집계에서 제외하고, 모니터링이 helm uninstall 실패 시 Pod 과 Helm release Secret 을 정리한다(`apps/fb_dashboard`, `apps/fb_monitoring`).
- 파인튜닝 stop API 리소스 leak: 별도 추적 항목. 중지 흐름 단위 테스트는 `apps/llm_model/tests/test_stop_fine_tuning.py`.
