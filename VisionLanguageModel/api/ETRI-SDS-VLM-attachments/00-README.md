# ETRI SDS-VLM 검토 회신 — 1차 첨부 자료 (2026-05-19 갱신)

본 압축 파일은 [아크릴 → ETRI] SDS-VLM MSA 코드 검토 회신 **1차 메일**과
함께 송부되는 첨부 자료입니다.

## 1차 메일 범위

**우선 처리 대상**: 컨테이너 동작 자체에 영향을 주는 6건 (메일 §1)

- #1·#2·#3 은 아크릴 측 클러스터에서 patch 작성·동작 검증 완료
  (`04-etri-tier1-patch/` 디렉토리에 unified diff + patched 소스 + Dockerfile 변경분 동봉)
- #4 는 일부 path 의 HTTP 상태 코드 점검 권장
- **#5 (torch CVE-2025-32434) 는 학습 launch 의 최우선 blocker** — A1~A4 패치 적용 후에도 vision encoder 로드 단계에서 차단됨이 우리 검증으로 확인
- #6 (TensorBoard 활성화) 은 플랫폼 모니터링 UI 자동 연동에 필요

플랫폼 연동·정합 사항(manifest 양식, PVC 마운트 표준, 데이터셋 패키징,
체크포인트 매핑, infer pod 모델 reload 흐름 등)은 **아크릴 측 플랫폼 탑재
검증을 완료한 뒤** 양식과 함께 별도로 안내드릴 예정입니다 (5월 말 ~ 6월 초).

## 파일 목록

| # | 파일 | 용도 |
|---|---|---|
| 01 | `01-SDS-VLM-detail-for-ETRI.md` | 40건 finding · 권장 해결안 · 코드 예시. **1차 패치는 §A (Tier 1, A5 포함) 부분 + §B5 (TensorBoard) + §G (P2 cosmetic) 참고 부탁드립니다**. §E1/§E2/§F1/§H 등 정합·협의 사항은 아크릴 측 검증 후 양식과 함께 재안내 예정이므로, 현 시점에는 참고만 부탁드립니다. |
| 02 | `02-Tango-MSA-탑재-가이드.md` | 조나단 GenAI 플랫폼 MSA 표준 (`/health`, `/info`, `/run`, helm chart 작성법 등 기본 contract). |
| 03 | `03-errors.yaml` | `E_VLM_*` 에러 코드 정의 (응답 본문 형식 참고용). |
| **04** | **`04-etri-tier1-patch/`** (디렉토리) | **2026-05-19 추가**. 메일 §1 의 #1·#2·#3 (`A1`/`A2`/`A3`) + #6 (`B5` TensorBoard) 의 후보 patch. 아크릴 측 클러스터에서 #1~#3 동작 검증 완료. ETRI 측에서 그대로 채택 또는 코드 스타일 재작성 모두 가능. 내부 `README.md` 에 적용 방법 안내. |

## 권장 읽는 순서

1. **메일 본문** — §1 우선 처리 사항 6건 확인
2. **`01-SDS-VLM-detail-for-ETRI.md` 의 §A (Tier 1, A1~A5)** — 각 finding 의 file:line · 권장 해결안 · 코드 예시. **A5 (torch CVE) 가 학습 launch 의 최우선 blocker**.
3. **`04-etri-tier1-patch/`** — A1·A2·A3 + B5 의 후보 patch (그대로 채택 가능)
4. **`01-SDS-VLM-detail-for-ETRI.md` 의 §B5** — TensorBoard 활성화 권장 사유 + patch
5. **`03-errors.yaml`** — 에러 응답 본문 형식 참고용
6. **`01-SDS-VLM-detail-for-ETRI.md` 의 §G (P2 cosmetic)** — startup noise / Gradio demo
7. **`02-Tango-MSA-탑재-가이드.md`** — 기본 contract 참고 (향후 단계용)

> ⚠️ `01-SDS-VLM-detail-for-ETRI.md` 의 §E·§F·§H 등 정합·협의 항목은 아크릴
> 측 플랫폼 탑재 검증 진행 중인 사안으로, 검증 결과에 따라 양식이 조정될
> 수 있습니다. 1차 단계에서는 §A (Tier 1) + §B5 + §G 부분 위주로 참고
> 부탁드리며, 나머지 항목은 2차 안내 시 확정된 양식으로 다시 송부드리겠습니다.

## 권장 적용 순서 (ETRI 측)

1. **A5 (torch CVE) 최우선**: 학습 자체가 막힘. base image upgrade 또는 safetensors 강제.
2. **A1~A4, D1~D3 (Tier 1)**: A1·A2·A3 는 동봉 patch 그대로 채택 가능. 나머지는 detail 의 권장 해결안 참고.
3. **B5 (TensorBoard)**: ETRI 의 W&B 운용 영향 없이 추가 가능.
4. **B1~B4 (Tier 2)**: HTTP 상태 코드 / probe 분리 / lock / body size cap.
5. **G1~G2 (P2 cosmetic)**: ETRI 우선순위에 따라.

## 아크릴 측 플랫폼 통합 상태 (참고)

- ETRI `/train`, `/train/status`, `/train/stop` 모두 정상 호출 (A2 patch 적용 시 진짜 status 갱신 확인됨)
- ETRI 의 응답 schema (`{result: {job_id, message}}` 의 nested job_id 추출 등) 흡수
- flightbase-fe 의 internal LLM fine-tuning SSE 훅 (`useSSEStatus`, `useSSEFinetuningTime`, `useSSEGraph`, `FineTuningSystemLogModal`) 이 외부 학습용 BFF endpoint 와도 호환되도록 schema 통일 (frontend 변경 없이 재사용 가능)
- A5 (torch CVE) 또는 B5 (TensorBoard) 가 fix 되면 graph 차트도 자동 채워짐

## 후속 안내 예정

- 2차 메일 (5월 말 ~ 6월 초): manifest 양식 (eva-vlm-infer.yaml /
  eva-vlm-train.yaml), PVC 마운트 + JF_* 환경변수 표준, dataset 패키징 양식,
  4-phase 체크포인트 매핑, infer pod reload + 인증 방식 등 확정된 양식 송부.

## 문의

회신 메일의 발신자에게 답신 또는 추가 자료 요청 부탁드립니다.
