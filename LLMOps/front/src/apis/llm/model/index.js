import { callApi, downloadBlob } from '@src/network';

export const getModel = async (workspaceId) => {
  const res = await callApi({
    url: `models?workspace_id=${workspaceId}`,
    method: 'get',
  });
  return res;
};

export const postModel = async ({ workspace_id, name, description }) => {
  const res = await callApi({
    url: 'playgrounds',
    method: 'post',
    body: {
      workspace_id,
      name,
      description,
    },
  });
  return res;
};

export const getModelsCommitModels = async (id) => {
  const res = await callApi({
    url: `models/commit-models/${id}`,
    method: 'get',
  });
  return res;
};

// Phase 2-C — 커밋(버전)에 귀속된 체크포인트 스냅샷 레지스트리(커밋 시 commit_checkpoints 로 보존).
export const getCommitCheckpoints = async (modelId, commitId) => {
  return await callApi({
    url: `models/${modelId}/commit-models/${commitId}/checkpoints`,
    method: 'get',
  });
};

export const deleteCommitCheckpoint = async (modelId, commitId, step) => {
  return await callApi({
    url: `models/${modelId}/commit-models/${commitId}/checkpoints/${step}`,
    method: 'delete',
  });
};

// Phase 2-C promote — 커밋의 step 체크포인트를 새 버전 `<commit>-step<step>` 으로 적용(LoRA cat 재머지).
export const promoteCommitCheckpoint = async (modelId, commitId, step) => {
  return await callApi({
    url: `models/${modelId}/commit-models/${commitId}/checkpoints/${step}/promote`,
    method: 'post',
  });
};

// SDS/external 모델 체크포인트 (P1) — 여러 커밋의 per-step 체크포인트를 flat 하게
// 나열(proj → llm, step 오름차순 정렬은 BE 가 수행). commit-checkpoints 계열과
// 동일한 base(`models/...`) + 응답 envelope 을 그대로 미러링한다.
export const getExternalCheckpoints = async (modelId) => {
  return await callApi({
    url: `models/${modelId}/external-checkpoints`,
    method: 'get',
  });
};

export const deleteExternalCheckpoint = async (modelId, commitId, step) => {
  return await callApi({
    url: `models/${modelId}/external-checkpoints/${commitId}/${step}`,
    method: 'delete',
  });
};

// Best 지정 — 모델레벨 마커에 (commit_name, step) 기록(P1). 서빙 전환은 P2.
export const setBestExternalCheckpoint = async (modelId, commitId, step) => {
  return await callApi({
    url: `models/${modelId}/external-checkpoints/${commitId}/${step}/best`,
    method: 'post',
  });
};

// 서빙 시작(P2) — 현재 best 체크포인트를 실행 중 infer pod 에 in-pod 로드(재로드 1~5분 동기).
// callApi 는 timeout 미설정(무제한)이라 FE 는 스피너로 응답 대기.
export const serveExternalBestCheckpoint = async (modelId) => {
  return await callApi({
    url: `models/${modelId}/external-checkpoints/serve-best`,
    method: 'post',
  });
};

// 양자화·포팅 (SP-4 / v0.4 3.9) — 학습 완료 모델 → GGUF convert job → 포팅 패키지.
export const startQuantize = async (modelId, body) => {
  // body: { target_quant: 'q4'|'q5'|'q6', target_device?: string }
  return await callApi({
    url: `models/${modelId}/quantize`,
    method: 'post',
    body,
  });
};

// convert job 상태 폴링 — 기존 external job 상세 엔드포인트 재사용.
export const getQuantizeJob = async (jobId) => {
  return await callApi({ url: `external/jobs/${jobId}`, method: 'get' });
};

export const getQuantizePackage = async (modelId, jobId) => {
  return await callApi({
    url: `models/${modelId}/quantize/${jobId}/package`,
    method: 'get',
  });
};

export const downloadQuantizePackage = async (modelId, jobId) => {
  return await downloadBlob({
    url: `models/${modelId}/quantize/${jobId}/package/download`,
  });
};

export const downloadQuantizeFile = async (modelId, jobId, fileName) => {
  return await downloadBlob({
    url: `models/${modelId}/quantize/${jobId}/package/download?file=${encodeURIComponent(
      fileName,
    )}`,
  });
};

// 4.6 양자화 이력(원본+파라미터) 조회.
export const getQuantizeLineage = async (modelId) => {
  return await callApi({
    url: `models/${modelId}/quantize/lineage`,
    method: 'get',
  });
};

// 4.5 device → 권장 양자화 매핑 (배지/자동제안용).
export const getQuantizeDevices = async () => {
  return await callApi({ url: 'models/quantize/devices', method: 'get' });
};

// 4.6 convert 실패/취소를 lineage 에 반영 (완료는 package 조회가 마감).
export const markQuantizeLineage = async (modelId, jobId, status) => {
  return await callApi({
    url: `models/${modelId}/quantize/${jobId}/lineage-status`,
    method: 'post',
    body: { status },
  });
};

// ── SP-5 자동평가 (v0.4 3.8) ──
// body: { dataset_id: number, metric_set?: string[], max_samples?: number }
export const startEvaluate = async (modelId, body) => {
  return await callApi({
    url: `models/${modelId}/evaluate`,
    method: 'post',
    body,
  });
};

// evaluate job 상태 폴링 — 기존 external job 상세 엔드포인트 재사용.
export const getEvaluateJob = async (jobId) => {
  return await callApi({ url: `external/jobs/${jobId}`, method: 'get' });
};

// 단일 evaluate job 의 metrics.json 조회 (ready 시 BE 가 eval_result lazy 마감).
export const getEvaluateResult = async (modelId, jobId) => {
  return await callApi({
    url: `models/${modelId}/evaluate/${jobId}/result`,
    method: 'get',
  });
};

// ⑪ 평가 이력 + 메트릭별 best 마킹(비교표).
export const getEvaluateResults = async (modelId) => {
  return await callApi({
    url: `models/${modelId}/evaluate/results`,
    method: 'get',
  });
};

// evaluate 실패/취소를 eval_result 에 반영(완료는 result 조회가 마감).
export const markEvaluateStatus = async (modelId, jobId, status) => {
  return await callApi({
    url: `models/${modelId}/evaluate/${jobId}/status`,
    method: 'post',
    body: { status },
  });
};

// GenAI 통합 파이프라인 파인튜닝 노드(internal) — 모델 바인딩 데이터셋 + 기본 FT config 조회.
// 반환 result: { model_id, model_datasets:[{id, dataset_name,...}], fine_tuning_config, ... }
export const getFineTuningConfig = async (modelId) => {
  return await callApi({
    url: `models/fine-tuning?model_id=${modelId}`,
    method: 'get',
  });
};

// GenAI 통합 파이프라인 파인튜닝 노드(internal) — 워크스페이스 인스턴스 목록.
// 반환 result: [{ instance_id, instance_name, gpu_allocate, resource_name, ... }]
export const getInstancesList = async (workspaceId) => {
  return await callApi({
    url: `models/option/instances?workspace_id=${workspaceId}`,
    method: 'get',
  });
};
