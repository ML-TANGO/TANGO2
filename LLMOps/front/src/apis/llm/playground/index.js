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

// 배포 타겟 통합 read-model(cluster/edge/standalone) — deployment_envelope 정규화 목록.
export const getDeploymentTargets = async (workspace_id) => {
  const res = await callApi({
    url: 'playgrounds/targets',
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
  deploy_type = 'cluster',
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
      deploy_type,
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

// 이중모델 추론 세션 동시 배포(WBS 추론 4.2) — 프롬프트생성 모델(LLM1) + 추론 모델(LLM2)을
// 한 세션으로 co-provision. BE 가 부모(추론)/자식(프롬프트생성) playground 2개를 올리고 링크.
// 반환 result: { session_playground_id, prompt_gen_playground_id }. 상태는 status/{session_playground_id} 폴링.
export const postDualSession = async ({
  workspace_id,
  name,
  prompt_gen_model_id,
  inference_model_id,
  model_instance_id,
  prompt_gen_commit_id,
  inference_commit_id,
  model_instance_count,
  model_gpu_count,
}) => {
  const res = await callApi({
    url: 'playgrounds/dual-session',
    method: 'post',
    body: {
      workspace_id: +workspace_id,
      name,
      prompt_gen_model_id: +prompt_gen_model_id,
      inference_model_id: +inference_model_id,
      model_instance_id: +model_instance_id,
      prompt_gen_commit_id: prompt_gen_commit_id ? +prompt_gen_commit_id : null,
      inference_commit_id: inference_commit_id ? +inference_commit_id : null,
      model_instance_count: +(model_instance_count ?? 1),
      model_gpu_count: +(model_gpu_count ?? 1),
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
  prompt_gen_playground_id,
  system_prompt,
  dual_examples,
}) => {
  let reqbody = {};

  reqbody['playground_id'] = +playground_id;
  reqbody['test_type'] = test_type;
  reqbody['session_id'] = session_id;

  if (test_type === 'external') {
    reqbody['external_payload'] = external_payload;
  } else if (test_type === 'question') {
    reqbody['test_question'] = test_question;
    // 이중모델 추론(SP-7): LLM1(프롬프트 생성기) playground id. 지정 시 BE 가 LLM1→LLM2 체인.
    // (이중 세션은 서버가 자동 파생하므로 미지정 가능.)
    if (prompt_gen_playground_id) {
      reqbody['prompt_gen_playground_id'] = +prompt_gen_playground_id;
    }
    // 예시기반 최적화(WBS 4.2): 시스템 지침 + few-shot 예시를 LLM1 에 주입.
    if (system_prompt) {
      reqbody['system_prompt'] = system_prompt;
    }
    if (Array.isArray(dual_examples) && dual_examples.length) {
      reqbody['dual_examples'] = dual_examples;
    }
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

// 이중모델 데이터셋 일괄 추론(WBS 4.3 배치) — N 샘플에 LLM1→LLM2 체인 + BLEU/ROUGE 채점.
// prompt_gen 은 BE 가 세션 링크에서 자동 파생. 반환 result: {samples, summary, has_reference, ...}.
export const postDualBatch = async ({
  playground_id,
  test_dataset_id,
  test_dataset_filename,
  sample_count,
  metrics,
  session_id,
  system_prompt,
  dual_examples,
}) => {
  const res = await callApi({
    url: 'playgrounds/dual-batch',
    method: 'post',
    body: {
      playground_id: +playground_id,
      test_dataset_id: +test_dataset_id,
      test_dataset_filename,
      sample_count: sample_count ?? 5,
      metrics: metrics ?? null,
      session_id,
      system_prompt: system_prompt || null,
      dual_examples:
        Array.isArray(dual_examples) && dual_examples.length ? dual_examples : null,
    },
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
