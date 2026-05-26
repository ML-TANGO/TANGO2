import { callApi } from '@src/network';

export const getUsers = async (workspaceId) => {
  const res = await callApi({
    url: 'options/users',
    method: 'get',
    params: {
      workspace_id: workspaceId,
    },
  });
  return res;
};
