import { callApi } from '@src/network';

export const getDashboardUser = async (workspaceId, platformType) => {
  const res = await callApi({
    url: 'dashboard/user',
    params: {
      workspace_id: workspaceId,
    },
  });
  return res;
};

export const getDashbaordUserResourceUsage = async (workspace_id) => {
  const res = await callApi({
    url: 'dashboard/user/resource-usage',
    params: {
      workspace_id,
    },
  });
  return res;
};

export const getProjectItems = async (workspaceId, platformType) => {
  const res = await callApi({
    url: 'dashboard/user/project-items',
    params: {
      workspace_id: workspaceId,
      platform_type: platformType,
    },
  });
  return res;
};
