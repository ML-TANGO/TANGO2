import { callApi, network } from '@src/network';

export const getRag = async (workspaceId) => {
  const res = await callApi({
    url: `rags?workspace_id=${workspaceId}`,
    method: 'get',
  });
  return res;
};

export const postRag = async ({
  workspace_id,
  name,
  description,
  access,
  owner_id,
}) => {
  const res = await callApi({
    url: 'rags',
    method: 'post',
    body: {
      workspace_id,
      name,
      description,
      access,
      owner_id,
    },
  });
  return res;
};

export const putRagDescription = async ({ ragId, description }) => {
  const res = await callApi({
    url: 'rags/description',
    method: 'put',
    body: {
      rag_id: ragId,
      description,
    },
  });
  return res;
};

export const deleteRag = async ({ ragId }) => {
  const res = await callApi({
    url: `rags/${ragId.join(',')}`,
    method: 'delete',
  });
  return res;
};

export const postRagBookmark = async ({ ragId }) => {
  const res = await callApi({
    url: 'rags/bookmark',
    method: 'post',
    body: {
      rag_id: ragId,
    },
  });
  return res;
};

export const deleteRagBookmark = async ({ ragId }) => {
  const res = await callApi({
    url: 'rags/bookmark',
    method: 'delete',
    body: {
      rag_id: ragId,
    },
  });
  return res;
};

export const getRagSetting = async (ragId) => {
  const res = await callApi({
    url: `rags/${ragId}`,
    method: 'get',
  });
  return res;
};

export const getRagSystemLogDownload = async (ragId, type) => {
  const res = await network.callApiWithPromise({
    url: `rags/system-log-download/${ragId}?deployment_type=${type}`,
    method: 'GET',
  });
  return res;
};

export const postRagHuggingFace = async ({ name, token, privateValue }) => {
  const res = await callApi({
    url: 'rags/option/huggingface-models',
    method: 'post',
    body: {
      model_name: name,
      huggingface_token: token,
      private: privateValue,
    },
  });
  return res;
};

export const postOptionHuggingfaceTokenCheck = async (token) => {
  const res = await callApi({
    url: 'rags/option/huggingface-token-check',
    method: 'post',
    body: JSON.stringify(token),
  });
  return res;
};

export const postRagSetting = async ({
  ragId,
  chunk,
  embeddingId,
  embeddingToken,
  rerankerId,
  rerankerToken,
  oldFiles,
  newFiles,
}) => {
  const body = {
    rag_id: ragId,
    chunk_len: chunk,
    embedding_huggingface_model_id: embeddingId,
    embedding_huggingface_model_token: embeddingToken,
    reranker_huggingface_model_id: rerankerId,
    reranker_huggingface_model_token: rerankerToken,
    old_doc_id_list: oldFiles,
    new_doc_file_name_list: newFiles,
  };
  const res = await callApi({
    url: 'rags/setting',
    method: 'post',
    body,
  });
  return res;
};

export const getRagRetrievalInstance = async (ragId) => {
  const res = await callApi({
    url: `rags/retrieval/instance?rag_id=${ragId}`,
    method: 'get',
  });
  return res;
};

export const getRagSystemLog = async (ragId) => {
  const res = await callApi({
    url: `rags/system-log?rag_id=${ragId}`,
    method: 'get',
  });
  return res;
};

export const getRagOptionInstance = async (ragId) => {
  const res = await callApi({
    url: `rags/option/instance?rag_id=${ragId}`,
    method: 'get',
  });
  return res;
};

export const postRagDeployment = async ({
  ragId,
  embeddingId,
  embeddingCount,
  embeddingGpuCount,
  rerankerId,
  rerankerCount,
  rerankerGpuCount,
  type,
}) => {
  const res = await callApi({
    url: 'rags/deployment',
    method: 'post',
    body: {
      rag_id: ragId,
      embedding_instance_id: embeddingId,
      embedding_instance_count: embeddingCount,
      embedding_gpu_count: embeddingGpuCount,
      reranker_instance_id: rerankerId,
      reranker_instance_count: rerankerCount,
      reranker_gpu_count: rerankerGpuCount,
      deployment_type: type,
    },
  });
  return res;
};

export const deleteRagDeployment = async ({ ragId, type }) => {
  const res = await callApi({
    url: 'rags/deployment',
    method: 'delete',
    body: {
      rag_id: ragId,
      deployment_type: type,
    },
  });
  return res;
};

export const postRagRetrievalTest = async ({ ragId, input, chunk }) => {
  const res = await callApi({
    url: 'rags/retrieval/test',
    method: 'post',
    body: {
      rag_id: ragId,
      input,
      max_chunk: chunk,
    },
  });
  return res;
};

export const postRagDocuments = async ({ files, ragId }) => {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append('files', file);
  });

  formData.append('rag_id', ragId);

  const res = await callApi({
    url: 'rags/documents',
    method: 'post',
    body: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return res;
};

export const getRagDocuments = async (ragId) => {
  const res = await callApi({
    url: `rags/documents/${ragId}`,
    method: 'get',
  });
  return res;
};

export const deleteRagDocuments = async ({ ragId, list }) => {
  const res = await callApi({
    url: 'rags/documents',
    method: 'delete',
    body: {
      rag_id: ragId,
      id_list: list,
    },
  });
  return res;
};

export const getRagsOwner = async (workspace_id) => {
  const res = await callApi({
    url: `rags/users?workspace_id=${workspace_id}`,
    method: 'get',
  });

  return res;
};
