// example

import axios from 'axios';

import { callApi, download, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

export const getPlayground = async (workspace_id) => {
  const res = await callApi({
    url: 'playgrounds',
    method: 'get',
    params: {
      workspace_id,
    },
  });
  return res;
};

export const postPlayground = async ({
  workspace_id,
  name,
  description,
  access,
  owner_id,
  user_id,
}) => {
  const res = await callApi({
    url: 'playgrounds',
    method: 'post',
    body: {
      workspace_id,
      name,
      description,
      access,
      owner_id,
      users_id: user_id,
    },
  });
  return res;
};

export const getDetailPlayground = async (playgroundId) => {
  const res = await callApi({
    url: `playgrounds/${playgroundId}`,
    method: 'get',
  });
  return res;
};

export const getPlaygroundModels = async (workspaceId, search, isMine) => {
  const res = await callApi({
    url: `playgrounds/model?workspace_id=${workspaceId}&search=${search}&is_mine=${isMine}`,
    method: 'get',
  });
  return res;
};

export const postPlaygroundHugging = async ({ keyword, token, isMine }) => {
  const res = await callApi({
    url: 'playgrounds/model/huggingface',
    method: 'post',
    body: {
      model_name: keyword,
      huggingface_token: token,
      private: isMine,
    },
  });
  return res;
};

export const getPlaygroundRagList = async (workspaceId) => {
  const res = await callApi({
    url: `playgrounds/rag?workspace_id=${workspaceId}`,
    method: 'get',
  });
  return res;
};

export const putPlaygroundOptions = async (body) => {
  const { status, error, message } = await callApi({
    url: 'playgrounds/options',
    method: 'put',
    body,
  });

  if (status !== STATUS_SUCCESS) {
    errorToastMessage(error, message);
  }
};

export const getPlaygroundPrompt = async (workspaceId) => {
  const res = await callApi({
    url: `playgrounds/prompt?workspace_id=${workspaceId}`,
    method: 'get',
  });
  return res;
};

export const getPlaygroundVersion = async (prompt_id) => {
  const res = await callApi({
    url: `playgrounds/prompt/commit?prompt_id=${prompt_id}`,
    method: 'get',
  });
  return res;
};

export const putDescription = async ({ playgroundId, description }) => {
  const res = await callApi({
    url: 'playgrounds/description',
    method: 'put',
    body: {
      playground_id: playgroundId,
      description,
    },
  });

  return res;
};

export const putPlaygrounds = async (body) => {
  const res = await callApi({
    url: 'playgrounds',
    method: 'put',
    body,
  });
  return res;
};

export const getPlaygroundDeploymentList = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/instance',
    method: 'get',
    params: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const getPlaygroundStatus = async (playgroundId) => {
  const res = await callApi({
    url: `playgrounds/status/${playgroundId}`,
    method: 'get',
  });
  return res;
};

export const postPlaygroundDeployStart = async ({
  playground_id,
  model_instance_id,
  model_instance_count,
  model_gpu_count,
  embedding_instance_id,
  embedding_instance_count,
  embedding_gpu_count,
  reranker_instance_id,
  reranker_instance_count,
  reranker_gpu_count,
  restart,
}) => {
  const res = await callApi({
    url: 'playgrounds/start',
    method: 'post',
    body: {
      playground_id,
      embedding_gpu_count,
      embedding_instance_count,
      embedding_instance_id,
      model_gpu_count,
      model_instance_count,
      model_instance_id,
      reranker_gpu_count,
      reranker_instance_count,
      reranker_instance_id,
      restart,
    },
  });

  return res;
};

export const postPlaygroundsStop = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/stop',
    method: 'post',
    body: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const getPlaygroundTestOptions = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/test/options',
    method: 'get',
    params: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const getPlaygroundTestDataset = async (dataset_id) => {
  const res = await callApi({
    url: 'playgrounds/test/dataset',
    method: 'get',
    params: {
      dataset_id,
    },
  });
  return res;
};

export const getPlaygroundTestLog = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/test/log',
    method: 'get',
    params: {
      playground_id: +playgroundId,
    },
  });
  return res;
};

export const deletePlayground = async (id) => {
  const res = await callApi({
    url: `playgrounds/${id}`,
    method: 'delete',
  });
  return res;
};

export const postPlaygroundTestChat = async ({
  playground_id,
  test_type,
  test_dataset_id,
  test_dataset_filename,
  test_question,
  session_id,
  external_payload,
}) => {
  let reqbody = {};

  reqbody['playground_id'] = +playground_id;
  reqbody['test_type'] = test_type;
  reqbody['session_id'] = session_id;

  if (test_type === 'external') {
    reqbody['external_payload'] = external_payload;
  } else if (test_type === 'question') {
    reqbody['test_question'] = test_question;
  } else {
    reqbody['test_dataset_id'] = test_dataset_id;
    reqbody['test_dataset_filename'] = test_dataset_filename;
  }

  const res = await callApi({
    url: 'playgrounds/test',
    method: 'post',
    body: reqbody,
  });
  return res;
};

export const postBookmark = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/bookmark',
    method: 'post',
    body: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const deletePlaygroundBookmark = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/bookmark',
    method: 'delete',
    body: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const getPlaygroundTestLogDownload = async (playgroundId) => {
  const res = await download({
    url: `playgrounds/test/download?playground_id=${playgroundId}`,
    method: 'get',
    responseType: 'blob',
  });
  return res;
};

export const getMonitoringId = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/monitoring',
    method: 'get',
    params: {
      playground_id: playgroundId,
    },
  });
  return res;
};

export const getPlaygroundOwner = async (workspace_id) => {
  const res = await callApi({
    url: `playgrounds/users?workspace_id=${workspace_id}`,
    method: 'get',
  });

  return res;
};

export const getPlaygroundCheckAccel = async () => {
  try {
    const res = await axios.get(
      'http://115.71.36.50/api/playgrounds/check-accel',
    );
    return res;
  } catch (error) {
    console.log('error : ', error);
    // toast.error(error.message);
    return { data: { result: 'error' } };
  }
};

export const postPlaygroundStartAccel = async () => {
  const res = await axios.post(
    'http://115.71.36.50/api/playgrounds/start-accel',
  );
  return res;
};

export const postPlaygroundStopAccel = async () => {
  const { data } = await axios.post(
    'http://115.71.36.50/api/playgrounds/stop-accel',
  );

  return data;
};
