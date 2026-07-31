import { callApi } from '@src/network';

export const collectOptions = async (workspace_id) => {
  const res = await callApi({
    url: `collect/options?workspace_id=${workspace_id}`,
    method: 'get',
  });
  return res;
};

export const getCollectOtionsDirList = async (datasetId) => {
  const res = await callApi({
    url: 'collect/options/dir-list',
    method: 'get',
    params: {
      dataset_id: datasetId,
    },
  });
  return res;
};

export const postDeleteCollectCard = async (collectCardId) => {
  const res = await callApi({
    url: `collect/delete/${collectCardId}`,
    method: 'post',
  });
  return res;
};

export const postUpdateCollectCard = async (collectCardId) => {
  const res = await callApi({
    url: `collect/update/${collectCardId}`,
    method: 'post',
  });
  return res;
};

export const postCollectFavorite = async (collectCardId) => {
  const res = await callApi({
    url: 'collect/start',
    body: {
      id: collectCardId,
    },
  });
  return res;
};

export const postCollect = async (body) => {
  const res = await callApi({
    url: 'collect',
    method: 'post',
    body,
  });

  return res;
};

export const puCollect = async (id, body) => {
  const res = await callApi({
    url: `collect/update/${id}`,
    method: 'post',
    body,
  });
  return res;
};

export const getCollectList = async (workspace_id) => {
  const res = await callApi({
    url: 'collect',
    method: 'get',
    params: {
      workspace_id,
    },
  });
  return res;
};

export const getCollectInfo = async (workspace_id, id) => {
  const res = await callApi({
    url: 'collect/collect-info',
    method: 'get',
    params: {
      workspace_id,
      id,
    },
  });
  return res;
};

export const postCollectStart = async (id) => {
  const res = await callApi({
    url: `collect/start`,
    method: 'post',
    body: {
      id,
    },
  });
  return res;
};

export const postCollectStop = async (id) => {
  const res = await callApi({
    url: 'collect/stop',
    method: 'post',
    body: {
      id,
    },
  });
  return res;
};

export const getCollectHistory = async (id) => {
  const res = await callApi({
    url: `collect/history`,
    method: 'get',
    params: {
      id,
    },
  });
  return res;
};

export const postCollectBookMark = async (id, isBookMark) => {
  const res = await callApi({
    url: `collect/bookmark`,
    method: 'post',
    body: {
      id,
      bookmark: isBookMark,
    },
  });
  return res;
};

export const postCollectUpdate = async (id) => {
  const res = await callApi({
    url: `collect/update`,
    method: 'post',
    body: {
      id,
    },
  });
  return res;
};

export const getCollectPublicData = async () => {
  const res = await callApi({
    url: 'collect/public-api',
    method: 'get',
  });
  return res;
};

export const deleteCollectData = async (id, historyId) => {
  const res = await callApi({
    url: `collect/history/delete`,
    method: 'post',
    body: {
      id,
      history_id: historyId,
    },
  });
  return res;
};

export const deleteCollectDataAll = async (id) => {
  const res = await callApi({
    url: `collect/history/delete`,
    method: 'post',
    body: {
      id,
    },
  });
  return res;
};
