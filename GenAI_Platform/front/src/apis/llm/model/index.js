import { callApi } from '@src/network';

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
