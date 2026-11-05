import { callApi, download } from '@src/network';

export const getPipeline = async (workspaceId) => {
  const res = await callApi({
    url: 'pipelines',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
    },
  });
  return res;
};

export const getOwnerList = async (workspaceId) => {
  const res = await callApi({
    url: 'projects/option',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
    },
  });
  return res;
};

export const getOptionsPipeline = async (workspaceId, pipelineId) => {
  const res = await callApi({
    url: 'options/pipeline',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
      pipeline_id: pipelineId,
    },
  });
  return res;
};

export const getOptionsPreprocessingDataType = async (type) => {
  const res = await callApi({
    url: `options/preprocessing/built-in-tfs?data_type=${type}`,
    method: 'get',
  });
  return res;
};

export const getTrainDatasetList = async (workspaceId) => {
  const res = await callApi({
    url: 'pipelines/option/datasets',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
    },
  });
  return res;
};

export const putDataset = async (pipelineId, datasetId) => {
  const res = await callApi({
    url: 'pipelines/dataset',
    method: 'put',
    body: {
      pipeline_id: +pipelineId,
      dataset_id: +datasetId,
    },
  });
  return res;
};

export const postPipeline = async (body) => {
  const res = await callApi({
    url: 'pipelines',
    method: 'post',
    body,
  });
  return res;
};

export const getPipelineDetail = async (pipelineId) => {
  const res = await callApi({
    url: `pipelines/setting/${pipelineId}`,
    method: 'get',
  });
  return res;
};

export const getPipelineOptionItems = async (workspaceId, taskType) => {
  const res = await callApi({
    url: 'pipelines/option/items',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
      task_type: taskType,
    },
  });
  return res;
};

export const getPipelineOptionImages = async (workspaceId) => {
  const res = await callApi({
    url: 'pipelines/option/images',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
    },
  });
  return res;
};

// 생성형 데이터 파이프라인 노드용 외부 컨테이너 manifest 목록 (job_type=generate). WBS 1.2
export const getGenerationManifests = async () => {
  const res = await callApi({
    url: 'pipelines/option/generation-manifests',
    method: 'get',
  });
  return res;
};

// GenAI 통합 파이프라인 파인튜닝/양자화 노드용 워크스페이스 LLM 모델 목록.
// 반환: [{ id, name, training_type, domain, external_manifest_name, external_manifest_version }]
export const getLlmModels = async (workspaceId) => {
  const res = await callApi({
    url: 'pipelines/option/llm-models',
    method: 'get',
    params: {
      workspace_id: +workspaceId,
    },
  });
  return res;
};

export const deletePipeLines = async (pipelineId) => {
  const res = await callApi({
    url: `pipelines`,
    method: 'delete',
    body: pipelineId,
  });
  return res;
};

export const getPipelineRunCode = async (projectId, taskType) => {
  const res = await callApi({
    url: `pipelines/option/run-code?task_item_id=${projectId}&task_type=${taskType}`,
    method: 'get',
  });
  return res;
};

export const postPipelinesTask = async (body) => {
  const res = await callApi({
    url: 'pipelines/task',
    method: 'post',
    body,
  });
  return res;
};

export const putPipelinesAddSerial = async (body) => {
  const res = await callApi({
    url: 'pipelines/add-serial',
    method: 'put',
    body,
  });
  return res;
};

export const putPipelinesTask = async (body) => {
  const res = await callApi({
    url: 'pipelines/task',
    method: 'put',
    body,
  });
  return res;
};

export const putPipelinesGraph = async (body) => {
  const res = await callApi({
    url: 'pipelines/graph',
    method: 'put',
    body,
  });
  return res;
};

export const deletePipelinesTask = async (body) => {
  const res = await callApi({
    url: 'pipelines/task',
    method: 'delete',
    body,
  });
  return res;
};

export const putPipelineRetrain = async (body) => {
  const res = await callApi({
    url: 'pipelines/retraining',
    method: 'put',
    body,
  });
  return res;
};

export const postPipelineRun = async (pipelineId) => {
  const res = await callApi({
    url: 'pipelines/run',
    method: 'post',
    body: pipelineId,
  });
  return res;
};

export const putPipelinesDeleteRow = async (body) => {
  const res = await callApi({
    url: 'pipelines/delete-serial',
    method: 'put',
    body,
  });
  return res;
};

// SP-7 Jump(노드 재실행) — 해당 노드+후행만 단일패스 재실행. 상위 노드는 유지.
export const postPipelineRerunTask = async (taskId) => {
  const res = await callApi({
    url: `pipelines/task/${taskId}/rerun`,
    method: 'post',
  });
  return res;
};

export const postPipelineStop = async (pipelineId) => {
  const res = await callApi({
    url: 'pipelines/stop',
    method: 'post',
    body: pipelineId,
  });
  return res;
};

export const getPipelineLog = async (taskId) => {
  if (!taskId) return '-';
  const res = await callApi({
    url: 'pipelines/task/system-log',
    method: 'get',
    params: {
      task_id: +taskId,
    },
  });
  return res;
};

export const getPipelineSystemLogdownload = async (taskId) => {
  const res = await download({
    url: `pipelines/task/system-log/download?task_id=${taskId}`,
    method: 'get',
    responseType: 'blob',
  });
  return res;
};

export const getPipelineInfoApi = async (pipeline_id) => {
  const res = await callApi({
    url: `pipelines/info/${pipeline_id}`,
    method: 'get',
  });
  return res;
};

export const getPipelineHistoryApi = async (pipeline_id) => {
  const res = await callApi({
    url: `pipelines/history/${pipeline_id}`,
    method: 'get',
  });

  return res;
};

export const getPipelineHistoryDetail = async (pipeline_id) => {
  const res = await callApi({
    url: `pipelines/history/detail/${pipeline_id}`,
    method: 'get',
  });
  return res;
};

export const putPipelineBookmark = async (id) => {
  const res = await callApi({
    url: 'pipelines/bookmark',
    method: 'put',
    body: id,
  });
  return res;
};

export const putPipelines = async ({
  pipeline_id,
  description,
  access,
  owner_id,
  users_id,
}) => {
  const res = await callApi({
    url: 'pipelines',
    method: 'put',
    body: {
      pipeline_id,
      description,
      access,
      owner_id,
      users_id,
    },
  });
  return res;
};

export const getBuiltinOptionsList = async (id) => {
  return await callApi({
    url: `options/preprocessing/job?preprocessing_id=${id}`,
    method: 'get',
  });
};

export const getTrainingBuiltinOptionsList = async (id) => {
  return await callApi({
    url: `options/project/job?project_id=${id}`,
    method: 'get',
  });
};
