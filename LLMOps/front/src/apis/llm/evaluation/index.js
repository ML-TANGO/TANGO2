import { callApi, downloadBlob } from '@src/network';

// llm_evaluation 서비스 (P1b) — Kong ingress /api/(evaluations).
// 벤치마크 평가 런 생성/폴링/이력/상태. (LLM-judge=P2, 전문가=P3.)

// ── 평가 프로젝트 (P2) ────────────────────────────────────────────────
// 프로젝트 = 평가유형 + 이름을 묶는 관리 단위. **모델·데이터셋은 프로젝트가 아니라 런이
// 고른다**(실행 시점 선택) — 한 프로젝트 안에서 모델·데이터셋을 바꿔 가며 견주는 것이
// 프로젝트의 목적이라 생성 시점에 잠글 수 없다. 옛 프로젝트는 project.model_id /
// dataset_ids 를 그대로 갖고 있고(표시용), 새 프로젝트는 null/빈 값이다.

// 프로젝트 생성(대기 상태, run 0개). body: { name, eval_type: 'reference'|'judge'|'expert',
//   workspace_id } — workspace_id 는 라우트 파라미터에서 온다(모델을 안 받으므로 서버가
//   model_id 로 도출할 수 없다). → get_project shape 반환 { project, runs }.
export const createEvalProject = async (body) => {
  return await callApi({ url: 'evaluations/projects', method: 'post', body });
};

// 워크스페이스 프로젝트 목록(최신순). 프로젝트 update_datetime 은 최근 run 생성 시각이며
// run 이 없으면 프로젝트 create_datetime 과 같다. → { workspace_id, projects: [...] }.
export const listEvalProjects = async (workspaceId) => {
  return await callApi({
    url: 'evaluations/projects',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// 프로젝트 단건(+자식 run 요약). → { project: {...}, runs: { metric_keys, best, runs } }.
export const getEvalProject = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}`,
    method: 'get',
  });
};

// 프로젝트 삭제(FK CASCADE 로 run·채점·이력 자식행 정리). → { project_id, deleted }.
export const deleteEvalProject = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}`,
    method: 'delete',
  });
};

// 프로젝트 내 run 비교(same model+dataset=apples-to-apples). → { project_id, metric_keys, best, runs }.
export const compareProjectRuns = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}/compare`,
    method: 'get',
  });
};

// ── run 생성 (P2+: 런이 대상을 지정) ──────────────────────────────────
// 전 런 계약 공통 필수: model_id(이 런이 평가할 모델), dataset_ids(정확히 1개).
// 벤치마크 런 생성. body: { project_id, model_id, dataset_ids: [id],
//   benchmarks?: [{ benchmark, metric }] } — 벤치마크→메트릭 매핑(생략 시 전체·권장 메트릭).
// LogicKor 내장 심판(컨테이너가 GPU 에 직접 올리는 심판) 후보 목록.
//   → { models: [{id,label,hf_id,size_gb}], default }.
//   ⚠️ **지금 이걸 부르는 화면은 없다** — 심판은 떠 있는 배포로 일원화했고(judge_playground_id)
//   내장 심판 경로는 BE 에 남겨 둔 채 화면에서만 감췄다(JudgeRunConfig 머리 주석).
//   그 경로를 화면에 되살릴 때 후보를 프론트에 복제하지 말고 이 응답을 그대로 렌더하라 —
//   서버 화이트리스트와 드리프트하면 캐시에 없는 심판이 화면에 떠서
//   "GPU 잡고 몇 분 뒤 실패"가 되살아난다.
export const getBenchmarkJudgeModels = async () => {
  return await callApi({ url: 'evaluations/benchmark/judge-models', method: 'get' });
};

export const runBenchmark = async (body) => {
  return await callApi({ url: 'evaluations/benchmark', method: 'post', body });
};

// 평가 추론 러너(generate) 런 생성. body: { project_id, model_id, dataset_ids: [id],
//   system_prompt?, inference_playground_id?,
//   instance_id?, instance_count?, gpu_count?, commit_id? }. running 배포 재사용 or 전용 할당(후 회수).
//   → 즉시 { job_id, allocated, system_prompt, ... }. per-sample output 은 백그라운드로 생성·영속. (P1 WIP)
export const runEvalInference = async (body) => {
  return await callApi({ url: 'evaluations/inference', method: 'post', body });
};

// 단건 평가 결과 폴링 (ready=true 시 metrics + eval_result lazy 마감).
export const getEvalResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/result`,
    method: 'get',
  });
};

// 교차모델 비교(④ 경량 뷰) — 여러 모델 이력 합쳐 전역 best-per-metric. modelIds: number[].
export const getEvalCompare = async (modelIds) => {
  return await callApi({
    url: 'evaluations/compare',
    method: 'get',
    params: { model_ids: (modelIds || []).join(',') },
  });
};

// 런 단위 교차 비교 후보(P1) — 워크스페이스 전 평가 런(프로젝트 가로지름). 각 항목에
//   project_name/model_name/checkpoint/source_* /metric_set/status/metrics 가 실려 있어
//   화면이 "어느 모델의 어느 체크포인트를 언제 돌린 런인가" 를 날짜 없이도 구분할 수 있다.
export const listEvalRuns = async (workspaceId) => {
  return await callApi({
    url: 'evaluations/runs',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// 런 단위 비교(P1) — 지목한 런들만 열로 세운다. → { runs, metric_keys, best, datasets,
//   dataset_consistent }. dataset_consistent=false 면 서로 다른 데이터셋을 섞어 본 것이라
//   화면이 경고를 띄운다(차단은 하지 않는다).
export const getEvalCompareRuns = async (workspaceId, runIds) => {
  return await callApi({
    url: 'evaluations/compare-runs',
    method: 'get',
    params: {
      workspace_id: workspaceId,
      run_ids: (runIds || []).join(','),
    },
  });
};

// 평가 실패/취소 마킹 (cancelled 면 BE 가 컨테이너도 취소).
export const markEvalStatus = async (modelId, jobId, status) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/status`,
    method: 'post',
    body: { status },
  });
};

// 평가 런 1건 삭제(이력 관리). expert 세션이면 BE 가 FK CASCADE 로 채점/이력 자식행도 정리.
export const deleteEvalRun = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}`,
    method: 'delete',
  });
};

// 벤치마크 대상 워크스페이스 데이터셋 목록 (fb_option, get_dataset_model 과 동일 소스).
export const getEvalDatasets = async (workspaceId) => {
  return await callApi({
    url: 'options/preprocessing/dataset',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// ── LLM 심사 (LLM-as-a-Judge) ────────────────────────────────────────
// 전용 엔드포인트는 없다. 심사 벤치마크(LogicKor)는 벤치마크 런이므로 생성은 runBenchmark
//   ({ benchmarks: ['logickor'], inference_playground_id, judge_playground_id, ... }),
//   결과 폴링은 getEvalResult 를 그대로 쓴다. BE 는 프로젝트 유형과 벤치마크 유형이
//   어긋나면 런 생성을 거부한다.
// 폐기(2026-08-27): runJudge(POST /evaluations/judge) · getJudges(GET /evaluations/judges) ·
//   getJudgeResult(GET /{modelId}/{jobId}/judge-result). 자유 샘플 × 기준 4종 채점은 mock
//   이었고, 외부 API 심판(키·엔드포인트 수취)은 평가가 아니라 배포 표면의 문제라 옮긴다.

// ── 전문가 평가 (P3) ──────────────────────────────────────────────────
// 세션 시작 → { job_id, total, expert_prompt, samples: [{ idx, output,
//   image/image_url/image_served, csv_rows(2D)/csv_text }] }. body: { project_id,
//   model_id, dataset_ids: [id], inference_playground_id? } — 대상은 런이 지정한다.
// expert_prompt(고정 지침)·per-sample csv_rows/csv_text 는 startExpert 시 인라인으로 내려온다
// (이미지는 별도 blob 엔드포인트 expert-image/{idx} 유지). input/reference 는 계약엔 있으나 FE 미표시.
export const startExpert = async (body) => {
  return await callApi({ url: 'evaluations/expert', method: 'post', body });
};

// 세션 샘플 + 기존 채점(재개용).
export const getExpertSamples = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-samples`,
    method: 'get',
  });
};

// 채점 제출(1~5 별점 + 코멘트). body: { sample_idx, score, score_json?, comment? }
// → { rated, total, avg_score, distribution, completed, rater_user, rated_at, rate_count }.
// score_json 은 확장 지점(다기준/구조화 피드백/선호도쌍) — 현재 UI 는 단일 score 만 전송.
export const submitExpertRating = async (modelId, jobId, body) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-rating`,
    method: 'post',
    body,
  });
};

// 세션 진행/결과(상태 + 채점 목록 + 채점 이력 + 합격률).
export const getExpertResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-result`,
    method: 'get',
  });
};

// 멀티모달 — 전문가 샘플 이미지(서버 보관 NFS 이미지) blob. jf 헤더 인증 경유라 <img src>
// 직접 GET(헤더 미탑재) 대신 blob 으로 받아 objectURL 로 렌더. URL 이미지는 FE 가 직접 렌더(미사용).
export const fetchExpertImageBlob = async (modelId, jobId, idx) => {
  return await downloadBlob({
    url: `evaluations/${modelId}/${jobId}/expert-image/${idx}`,
  });
};

// 지연 단위 VLM 실추론 — 전문가가 여는 샘플 1개를 바인드된 배포 SDS 모델로 추론해 output 을
// 실출력으로 교체·영속. → { real_output, sample }. 미바인드/비-VLM/이미 실출력/실패는 real_output=false.
export const inferExpertSample = async (modelId, jobId, sampleIdx) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-infer/${sampleIdx}`,
    method: 'post',
  });
};
