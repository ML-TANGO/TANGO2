import { callApi } from '@src/network';

// llm_evaluation 서비스 (P1b) — Kong ingress /api/(evaluations).
// 벤치마크 평가 런 생성/폴링/이력/상태. (LLM-judge=P2, 전문가=P3.)

// 벤치마크 런 생성. body: { model_id, dataset_ids: number[], metric_set?: string[] }
export const runBenchmark = async (body) => {
  return await callApi({ url: 'evaluations/benchmark', method: 'post', body });
};

// 단건 평가 결과 폴링 (ready=true 시 metrics + eval_result lazy 마감).
export const getEvalResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/result`,
    method: 'get',
  });
};

// 모델의 평가 이력(비교표).
export const getEvalResults = async (modelId) => {
  return await callApi({ url: `evaluations/${modelId}/results`, method: 'get' });
};

// 교차모델 비교(④ 경량 뷰) — 여러 모델 이력 합쳐 전역 best-per-metric. modelIds: number[].
export const getEvalCompare = async (modelIds) => {
  return await callApi({
    url: 'evaluations/compare',
    method: 'get',
    params: { model_ids: (modelIds || []).join(',') },
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

// 벤치마크 대상 워크스페이스 데이터셋 목록 (fb_option, get_dataset_model 과 동일 소스).
export const getEvalDatasets = async (workspaceId) => {
  return await callApi({
    url: 'options/preprocessing/dataset',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// ── LLM-as-a-Judge (P2) ──────────────────────────────────────────────
// 가용 심판 목록(상용 3종 + 로컬) + 기준.
export const getJudges = async () => {
  return await callApi({ url: 'evaluations/judges', method: 'get' });
};

// judge 런 생성(직접호출 비동기). ⚠️ api_key/base_url = transient — 화면 state 에만, 영속 X.
// body: { model_id, dataset_ids, provider, judge_model?, api_key?, base_url?, criteria, custom_prompt? }
export const runJudge = async (body) => {
  return await callApi({ url: 'evaluations/judge', method: 'post', body });
};

// judge 런 결과 폴링(eval_result row 직접 조회 — 컨테이너/NFS 미경유).
export const getJudgeResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/judge-result`,
    method: 'get',
  });
};

// ── 전문가 평가 (P3) ──────────────────────────────────────────────────
// 세션 시작 → { job_id, samples, total }. body: { model_id, dataset_ids }
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

// 채점 제출(O/X + 코멘트). body: { sample_idx, verdict, comment? }
export const submitExpertRating = async (modelId, jobId, body) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-rating`,
    method: 'post',
    body,
  });
};

// 세션 진행/결과(상태 + 채점 목록 + 합격률).
export const getExpertResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-result`,
    method: 'get',
  });
};
