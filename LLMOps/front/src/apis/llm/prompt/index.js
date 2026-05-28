import { callApi } from '@src/network';

export const postPromptCommit = async ({
  prompt_id,
  commit_name,
  commit_message,
  system_message,
  user_message,
}) => {
  const res = await callApi({
    url: 'prompts/commit',
    method: 'post',
    body: {
      prompt_id: +prompt_id,
      commit_name,
      commit_message,
      system_message,
      user_message,
    },
  });
  return res;
};

export const getPrompts = async (workspaceId) => {
  const res = await callApi({
    url: 'prompts',
    method: 'get',
    params: {
      workspace_id: workspaceId,
    },
  });
  return res;
};

export const deletePrompts = async (id) => {
  const res = await callApi({
    url: `prompts/${id}`,
    method: 'delete',
  });
  return res;
};

export const postPrompts = async ({
  workspace_id,
  name,
  description,
  access,
  owner_id,
}) => {
  const res = await callApi({
    url: 'prompts',
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

export const getPromptItemInfo = async (promptId, commitId) => {
  const res = await callApi({
    url: 'prompts/item',
    method: 'get',
    params: {
      prompt_id: promptId,
      commit_id: commitId,
    },
  });
  return res;
};

export const getPromptTemplate = async (promptId, commitId) => {
  const res = await callApi({
    url: 'prompts/template',
    method: 'get',
    params: {
      prompt_id: promptId,
      commit_id: commitId,
    },
  });
  return res;
};

export const getPromptList = async (promptId) => {
  const res = await callApi({
    url: 'prompts/commit',
    method: 'get',
    params: {
      prompt_id: promptId,
    },
  });
  return res;
};

export const postPromptBookMark = async (promptId) => {
  const res = await callApi({
    url: 'prompts/bookmark',
    method: 'post',
    body: {
      prompt_id: promptId,
    },
  });
  return res;
};

export const deletePromptBookMark = async (promptId) => {
  const res = await callApi({
    url: 'prompts/bookmark',
    method: 'delete',
    body: {
      prompt_id: promptId,
    },
  });
  return res;
};

export const putPromptsDescription = async (promptId, description) => {
  const res = await callApi({
    url: 'prompts/description',
    method: 'put',
    body: {
      prompt_id: promptId,
      description,
    },
  });
  return res;
};

export const getPromptOwner = async (workspace_id) => {
  const res = await callApi({
    url: `prompts/users?workspace_id=${workspace_id}`,
    method: 'get',
  });

  return res;
};
