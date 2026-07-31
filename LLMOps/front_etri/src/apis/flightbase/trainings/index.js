import { callApi } from '@src/network';

export const getDatasetList = async (workspace_id) => {
  const res = await callApi({
    url: 'options/preprocessing/dataset',
    method: 'get',
    params: {
      workspace_id,
    },
  });
  return res;
};
