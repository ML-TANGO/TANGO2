import { callApi, downloadBlob } from '@src/network';

// 데이터 합성 프레임워크 (fb_synthesis) — P1 (v0.4 3.3 / SP-7)

export const getSynthesisProjects = async (workspaceId) => {
  return await callApi({
    url: 'synthesis',
    method: 'get',
    params: { workspace_id: +workspaceId },
  });
};

export const getSynthesisManifests = async () => {
  return await callApi({ url: 'synthesis/manifests', method: 'get' });
};

export const createSynthesisProject = async (body) => {
  return await callApi({ url: 'synthesis', method: 'post', body });
};

export const getSynthesisProject = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}`, method: 'get' });
};

export const updateSynthesisProject = async (projectId, body) => {
  return await callApi({ url: `synthesis/${projectId}`, method: 'put', body });
};

export const deleteSynthesisProject = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}`, method: 'delete' });
};

export const runSynthesis = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}/run`, method: 'post' });
};

export const getSynthesisStatus = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}/status`, method: 'get' });
};

export const getSynthesisResult = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}/result`, method: 'get' });
};

export const getPromptCandidates = async (projectId) => {
  return await callApi({
    url: `synthesis/${projectId}/prompt-candidates`,
    method: 'get',
  });
};

export const downloadSynthesisResult = async (projectId) => {
  return await downloadBlob({ url: `synthesis/${projectId}/download` });
};

export const getSynthesisLog = async (projectId) => {
  return await callApi({ url: `synthesis/${projectId}/log`, method: 'get' });
};

export const saveSynthesisDataset = async (projectId, body) => {
  return await callApi({
    url: `synthesis/${projectId}/save-dataset`,
    method: 'post',
    body,
  });
};

export const regeneratePromptCandidates = async (projectId) => {
  return await callApi({
    url: `synthesis/${projectId}/prompt-candidates/generate`,
    method: 'post',
  });
};

export const adoptPromptCandidate = async (projectId, candidateId) => {
  return await callApi({
    url: `synthesis/${projectId}/candidates/${candidateId}/adopt`,
    method: 'post',
  });
};

export const discardPromptCandidate = async (projectId, candidateId) => {
  return await callApi({
    url: `synthesis/${projectId}/candidates/${candidateId}/discard`,
    method: 'post',
  });
};
