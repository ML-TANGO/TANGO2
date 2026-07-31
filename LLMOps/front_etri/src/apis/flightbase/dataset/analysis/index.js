import { callApi } from '@src/network';

export const analysisGet = async (workspace_id) => {
  const res = await callApi({
    url: `analyzer?workspace_id=${workspace_id}`,
    method: 'get',
  });
  return res;
};

export const getOptionsAnalyzer = async (workspace_id) => {
  const res = await callApi({
    url: `options/analyzer?workspace_id=${workspace_id}`,
    method: 'get',
  });
  return res;
};

export const postAnalyzer = async ({
  name,
  description,
  owner_id,
  instance_id,
  instance_allocate,
  workspace_id,
  access,
  users_id,
}) => {
  const res = await callApi({
    url: `analyzer`,
    method: 'post',
    body: {
      name,
      description,
      owner_id,
      instance_id,
      instance_allocate,
      workspace_id,
      access,
      users_id,
    },
  });
  return res;
};

export const putAnalyzer = async ({
  id,
  name,
  description,
  owner_id,
  instance_id,
  instance_allocate,
  workspace_id,
  access,
}) => {
  const res = await callApi({
    url: `analyzer`,
    method: 'put',
    body: {
      id,
      name,
      description,
      owner_id,
      instance_id,
      instance_allocate,
      workspace_id,
      access,
    },
  });
  return res;
};

export const deleteAnalyzer = async ({ id }) => {
  const res = await callApi({
    url: `analyzer/${id}`,
    method: 'delete',
  });
  return res;
};

export const getAnalyzerInfo = async (analyzer_id) => {
  const res = await callApi({
    url: `analyzer/info/${analyzer_id}`,
    method: 'get',
  });
  return res;
};

export const getOptionsAnalyzerDataset = async (wId) => {
  const res = await callApi({
    url: `options/analyzer/dataset?workspace_id=${wId}`,
    method: 'get',
  });
  return res;
};

export const getOptionsAnalyzerData = async (datasetId, search) => {
  let url = `options/analyzer/data?dataset_id=${datasetId}`;

  if (search && search !== '') {
    url += `&search=${search}`;
  }
  const res = await callApi({
    url,
    method: 'get',
  });
  return res;
};

export const getOptionsAnalyzerColumn = async (path, id) => {
  const res = await callApi({
    url: `options/analyzer/column?file_path=${path}&dataset_id=${id}`,
    method: 'get',
  });
  return res;
};

export const postAnalyzerGraph = async ({
  analyzer_id,
  name,
  description,
  workspace_id,
  data_path,
  graph_type,
  column,
  file_path,
  dataset_id,
}) => {
  const res = await callApi({
    url: `analyzer/graph`,
    method: 'post',
    body: {
      analyzer_id,
      name,
      description,
      workspace_id,
      data_path,
      graph_type,
      column,
      file_path,
      dataset_id,
    },
  });
  return res;
};

export const deleteAnalyzerGraph = async ({ analyzer_id, graph_id_list }) => {
  const res = await callApi({
    url: `analyzer/graph`,
    method: 'delete',
    body: {
      analyzer_id,
      graph_id_list, // [1,2,3,4]
    },
  });
  return res;
};

export const getAnalyzerGraph = async (analyzer_id) => {
  const res = await callApi({
    url: `analyzer/graph/${analyzer_id}`,
    method: 'get',
  });
  return res;
};

export const postAnalyzerBookmark = async ({ analyzer_id }) => {
  const res = await callApi({
    url: `analyzer/bookmark`,
    method: 'post',
    body: {
      analyzer_id,
    },
  });
  return res;
};

export const deleteAnalyzerBookmark = async ({ analyzer_id }) => {
  const res = await callApi({
    url: `analyzer/bookmark`,
    method: 'delete',
    body: {
      analyzer_id,
    },
  });
  return res;
};
