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
