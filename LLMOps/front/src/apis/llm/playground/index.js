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

const normalizeResource = (role, configured, instance) => ({
  role,
  instanceId: configured?.model_instance_id ?? instance?.instance_id ?? null,
  instanceName: instance?.instance_name ?? null,
  instanceCount:
    configured?.model_instance_count ?? instance?.instance_allocate ?? 1,
  gpuCount: configured?.model_gpu_count ?? instance?.gpu_count ?? null,
});

const normalizeComponent = (role, playgroundId, detail, resource) => {
  const model = detail?.model || {};
  const modelId = model.model_allm_id ?? model.model_hf_id ?? null;
  const modelName = model.model_allm_name ?? model.model_hf_id ?? null;
  return {
    role,
    playgroundId: playgroundId ? +playgroundId : null,
    modelId,
    modelName,
    modelCommitId: model.model_allm_commit_id ?? null,
    modelCommitName: model.model_allm_commit_name ?? model.commit ?? null,
    modelType: model.model_type ?? (modelId ? 'commit' : ''),
    trainingType: model.training_type ?? '',
    description: model.description ?? null,
    access: model.access,
    createDatetime: model.create_datetime ?? null,
    updateDatetime: model.update_datetime ?? null,
    // 역할별 생성 파라미터. 중지 상태에서 재구성할 때 저장값을 그대로 되살려야 하므로
    //   정규화 모델에 실어 보낸다(상세 API가 model_parameter 를 5키로 내려준다).
    params: detail?.model_parameter ?? null,
    resource,
  };
};

// 상세 API의 단일/이중 응답을 배포 상세 shell이 소비하는 한 형태로 좁힌다.
// 이중 자원은 configure/start 사이에도 유지되는 model.dual.resources가 우선이며,
// 기존 배포 행은 컴포넌트별 GET /playgrounds/{id}의 instance 정보로 폴백한다.
export const normalizePlaygroundDetail = ({
  detail,
  childDetail = null,
  overallStatus = 'stop',
  statusComponents = [],
}) => {
  const mode = detail?.dual?.mode === 'dual' ? 'dual' : 'single';
  const configuredResources = new Map(
    (detail?.dual?.resources || []).map((resource) => [
      resource.role,
      resource,
    ]),
  );

  const resources =
    mode === 'dual'
      ? [
          normalizeResource(
            'prompt_gen',
            configuredResources.get('prompt_gen'),
            childDetail?.info_instance?.model,
          ),
          normalizeResource(
            'inference',
            configuredResources.get('inference'),
            detail?.info_instance?.model,
          ),
        ]
      : [normalizeResource(null, null, detail?.info_instance?.model)];

  const components =
    mode === 'dual'
      ? [
          normalizeComponent(
            'prompt_gen',
            detail?.dual?.prompt_gen_playground_id,
            childDetail,
            resources[0],
          ),
          normalizeComponent(
            'inference',
            detail?.info?.id,
            detail,
            resources[1],
          ),
        ]
      : [normalizeComponent(null, detail?.info?.id, detail, resources[0])];
  const componentStatus = new Map(
    statusComponents.map((component) => [component.role, component.status]),
  );
  const componentsWithStatus = components.map((component) => ({
    ...component,
    status: componentStatus.get(component.role || 'single') ?? overallStatus,
  }));

  const isStopped = overallStatus === 'stop';
  const isDeploying = ['installing', 'pending'].includes(overallStatus);
  const isRunning = overallStatus === 'running';
  const isConfigured = componentsWithStatus.every(
    (component) => component.modelId,
  );

  return {
    id: detail?.info?.id ?? null,
    mode,
    info: detail?.info || null,
    components: componentsWithStatus,
    resources,
    overallStatus,
    capabilities: {
      // 사용자 결정의 단일 UI 계약: 완전히 stop인 세션만 구성 편집 가능.
      canEditConfig: isStopped,
      canStart: isStopped && isConfigured,
      canStop: isRunning || isDeploying,
      canRestart: isRunning,
      // 이중은 playground 합성 route가 LLM1→LLM2를 보존하므로 raw LLM2 우회 없이 게시 가능하다.
      canPublish: isRunning && !!detail?.info?.deployment_id,
    },
    rawDetail: detail,
  };
};

export const getNormalizedPlaygroundDetail = async (
  playgroundId,
  workspaceId,
) => {
  const detailResponse = await getDetailPlayground(playgroundId);
  if (
    detailResponse.status !== STATUS_SUCCESS ||
    !detailResponse.result?.info?.id
  ) {
    throw new Error(
      detailResponse.message || '요청한 배포를 찾을 수 없습니다.',
    );
  }
  const detail = detailResponse.result;
  if (
    workspaceId != null &&
    String(detail.info.workspace_id) !== String(workspaceId)
  ) {
    throw new Error('현재 워크스페이스에 속한 배포가 아닙니다.');
  }

  const childId = detail.dual?.prompt_gen_playground_id;
  // 상태는 aggregate+components 한 번으로 받고, child 상세는 모델/모니터링 메타용으로만 조회한다.
  const [statusResponse, childResponse] = await Promise.all([
    getPlaygroundStatusSync(playgroundId),
    childId ? getDetailPlayground(childId) : Promise.resolve(null),
  ]);
  if (statusResponse.status !== STATUS_SUCCESS) {
    throw new Error(
      statusResponse.message || '배포 상태를 확인할 수 없습니다.',
    );
  }
  if (
    childId &&
    (childResponse?.status !== STATUS_SUCCESS ||
      !childResponse?.result?.info?.id ||
      String(childResponse.result.info.workspace_id) !==
        String(detail.info.workspace_id))
  ) {
    throw new Error('이중모델 세션의 LLM1 연결 정보를 확인할 수 없습니다.');
  }

  return normalizePlaygroundDetail({
    detail,
    childDetail: childResponse?.result || null,
    overallStatus: statusResponse.result?.status || 'stop',
    statusComponents: statusResponse.result?.components || [],
  });
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

// 배포/파드 상태 단발 조회(폴링용). status/{id} 는 SSE 스트림이라 폴링에 부적합 → status-sync 사용.
// 반환 result: { status: 'running'|'installing'|'pending'|'stop', init_deployment: bool }
// skipDual=true → 이중 세션에서 부모(LLM2) 단독 상태(기본은 부모+자식 합산).
export const getPlaygroundStatusSync = async (
  playgroundId,
  skipDual = false,
) => {
  const res = await callApi({
    url: `playgrounds/status-sync/${playgroundId}`,
    method: 'get',
    params: skipDual ? { skip_dual: true } : undefined,
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
  prompt_gen_gpu_count,
  inference_gpu_count,
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
      prompt_gen_gpu_count: +(prompt_gen_gpu_count ?? 1),
      inference_gpu_count: +(inference_gpu_count ?? 1),
    },
  });
  return res;
};

// 이중모델 세션 '셸' 생성(단일 postPlayground 대칭) — 모델/자원 없이 세션 행만.
// LLM1/LLM2·GPU 선택과 실제 배포는 상세(/dual-deploy)의 postDualProvision 에서.
// 반환 result: { session_playground_id }.
export const postDualShell = async ({
  workspace_id,
  name,
  description,
  access,
  owner_id,
  user_id,
}) => {
  const res = await callApi({
    url: 'playgrounds/dual-session/shell',
    method: 'post',
    body: {
      workspace_id: +workspace_id,
      name,
      description,
      access,
      owner_id,
      users_id: user_id,
    },
  });
  return res;
};

const dualOptionsBody = ({
  playground_id,
  prompt_gen_model_id,
  inference_model_id,
  model_instance_id,
  prompt_gen_commit_id,
  inference_commit_id,
  prompt_gen_gpu_count,
  inference_gpu_count,
  prompt_gen_params,
  inference_params,
}) => ({
  playground_id: +playground_id,
  prompt_gen_model_id: +prompt_gen_model_id,
  inference_model_id: +inference_model_id,
  model_instance_id: +model_instance_id,
  prompt_gen_commit_id: prompt_gen_commit_id ? +prompt_gen_commit_id : null,
  inference_commit_id: inference_commit_id ? +inference_commit_id : null,
  prompt_gen_gpu_count: +(prompt_gen_gpu_count ?? 1),
  inference_gpu_count: +(inference_gpu_count ?? 1),
  // 역할별 playground 행에 따로 저장되는 생성 파라미터를 구성 저장 단계까지 보존한다.
  prompt_gen_params: prompt_gen_params ?? null,
  inference_params: inference_params ?? null,
});

export const putDualOptions = async (options) => {
  const res = await callApi({
    url: 'playgrounds/dual-session/options',
    method: 'put',
    body: dualOptionsBody(options),
  });
  return res;
};

export const postDualStart = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/dual-session/start',
    method: 'post',
    body: { playground_id: +playgroundId },
  });
  return res;
};

export const postDualRestart = async (playgroundId) => {
  const res = await callApi({
    url: 'playgrounds/dual-session/restart',
    method: 'post',
    body: { playground_id: +playgroundId },
  });
  return res;
};

// 이중모델 셸 배포 실행(단일 postPlaygroundDeployStart 대칭) — LLM1/LLM2·인스턴스·모델별 GPU 로
// 자식(프롬프트생성) 신규 배포 + 부모(셸) bind+start + 링크. 반환 result: { session_playground_id, prompt_gen_playground_id }.
export const postDualProvision = async ({
  playground_id,
  prompt_gen_model_id,
  inference_model_id,
  model_instance_id,
  prompt_gen_commit_id,
  inference_commit_id,
  prompt_gen_gpu_count,
  inference_gpu_count,
}) => {
  const res = await callApi({
    url: 'playgrounds/dual-session/provision',
    method: 'post',
    body: {
      playground_id: +playground_id,
      prompt_gen_model_id: +prompt_gen_model_id,
      inference_model_id: +inference_model_id,
      model_instance_id: +model_instance_id,
      prompt_gen_commit_id: prompt_gen_commit_id ? +prompt_gen_commit_id : null,
      inference_commit_id: inference_commit_id ? +inference_commit_id : null,
      prompt_gen_gpu_count: +(prompt_gen_gpu_count ?? 1),
      inference_gpu_count: +(inference_gpu_count ?? 1),
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
    // 이중 LLM2 가 외부 SDS(VLM)면 image/ais/output_type 동봉 — BE 가 custom_prompt=LLM1출력으로 연결.
    if (external_payload) {
      reqbody['external_payload'] = external_payload;
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

// ── 프롬프트 최적화(fewshot-prompt-optimizer) ──────────────────────────────
// few-shot 예시로 시스템 프롬프트를 최적화한다(external job, 수 분 소요).
// 완료된 최적화를 활성(active)으로 지정하면 이후 직접 추론에 서버가 주입한다.

export const postPromptOptimization = async ({
  playground_id,
  examples,
  dataset_id,
  dataset_filename,
  sample_count,
  metric = 'token_f1',
  rounds = 0,
  proposer_playground_id = null,
}) => {
  const res = await callApi({
    url: `playgrounds/${playground_id}/prompt-optimization`,
    method: 'post',
    body: {
      examples,
      dataset_id,
      dataset_filename,
      sample_count,
      metric,
      rounds,
      // ⚠️ body 를 키로 **열거**하는 구조라, 여기 빠진 파라미터는 호출부가 넘겨도
      //    조용히 사라진다. VLM(SDS) 최적화는 이 값이 없으면 BE 가 거부하므로
      //    누락 시 "UI 로는 실행 자체가 안 되는" 무증상 결함이 된다.
      proposer_playground_id,
    },
  });
  return res;
};

// 추론 화면 토글 전용 read-model — 진행 상태·최신 실행·활성 산출물을 한 번에 준다.
//   effective=false 는 "적용은 돼 있는데 배포 모델이 바뀌어 실제로는 주입되지 않는"
//   상태다. 목록만으로는 알 수 없어(is_active=1 만 보임) 토글이 거짓말을 하게 된다.
export const getPromptOptimizationState = async (playground_id) => {
  const res = await callApi({
    url: `playgrounds/${playground_id}/prompt-optimization/state`,
    method: 'get',
  });
  return res;
};

export const getPromptOptimizations = async (playground_id) => {
  const res = await callApi({
    url: `playgrounds/${playground_id}/prompt-optimizations`,
    method: 'get',
  });
  return res;
};

// 상세는 playground 스코프 필수 — system_prompt 는 사용자 데이터라 id 단독 조회를 막는다.
export const getPromptOptimization = async ({
  playground_id,
  optimization_id,
}) => {
  const res = await callApi({
    url: `playgrounds/${playground_id}/prompt-optimizations/${optimization_id}`,
    method: 'get',
  });
  return res;
};

// optimization_id: null 이면 활성 해제(최적화 미적용으로 복귀).
export const putPromptOptimizationActive = async ({
  playground_id,
  optimization_id,
}) => {
  const res = await callApi({
    url: `playgrounds/${playground_id}/prompt-optimization/active`,
    method: 'put',
    body: { optimization_id },
  });
  return res;
};
