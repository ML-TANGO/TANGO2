import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { Badge, ButtonV2 } from '@jonathan/ui-react';

import DeployDetailShell, {
  DeployDetailSection,
} from '@src/components/pageContents/llm/DeployDetail/DeployDetailShell';
import PlaygroundInstanceSettingInfo from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundInstanceSettingInfo';
import PlaygroundModel from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundModel';
import PlaygroundMonitoring from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundMonitoring';
import PlaygroundModelParameterSetting from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundModelParameterSetting';
import {
  getNormalizedPlaygroundDetail,
  getPlaygroundDeploymentList,
  postDualRestart,
  postPlaygroundsStop,
} from '@src/apis/llm/playground';
import useIntervalCall from '@src/hooks/useIntervalCall';
import { loadModalComponent } from '@src/modal';
import { startPath } from '@src/store/modules/breadCrumb';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DualDeployDetail.module.scss';

const cx = classNames.bind(style);

// 서버(service.DUAL_DEFAULT_MODEL_PARAMS)와 같은 기본값. 사용자가 손대지 않으면 종전과 동일하게 배포된다.
const DEFAULT_MODEL_PARAMS = Object.freeze({
  temperature: 0.7,
  top_p: 1.0,
  top_k: -1,
  repetition_penalty: 1.0,
  max_new_tokens: 512,
});

const EMPTY_INSTANCE_INFO = {
  instance_name: '-',
  instance_allocate: 0,
  gpu_allocate: 0,
  gpu_available: true,
  cpu_allocate: 0,
  cpu_available: true,
  ram_allocate: 0,
  ram_available: true,
};

const toModelCardValue = (component) => ({
  model_type: component?.modelType ?? (component?.modelId ? 'commit' : ''),
  serving_system: 'vllm',
  model_huggingface_id:
    component?.modelType === 'huggingface' ? component.modelName : '',
  model_allm_id: component?.modelId ?? '',
  model_allm_name: component?.modelName ?? '',
  model_allm_commit_id: component?.modelCommitId ?? '',
  model_allm_commit_name: component?.modelCommitName ?? '',
  training_type: component?.trainingType ?? '',
  description: component?.description,
  commit: component?.modelCommitName,
  access: component?.access,
  create_datetime: component?.createDatetime,
  update_datetime: component?.updateDatetime,
});

const DualDeployDetail = () => {
  const match = useRouteMatch();
  const history = useHistory();
  const dispatch = useDispatch();
  const { id: workspaceId, pid } = match.params;
  const editorsHydratedRef = useRef(false);

  const [deployment, setDeployment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailError, setDetailError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [promptModel, setPromptModel] = useState(null);
  const [promptModelData, setPromptModelData] = useState(null);
  const [promptCommit, setPromptCommit] = useState(null);
  const [inferenceModel, setInferenceModel] = useState(null);
  const [inferenceModelData, setInferenceModelData] = useState(null);
  const [inferenceCommit, setInferenceCommit] = useState(null);
  const [instances, setInstances] = useState([]);
  const [instanceId, setInstanceId] = useState(null);
  const [promptGpuCount, setPromptGpuCount] = useState(1);
  const [inferenceGpuCount, setInferenceGpuCount] = useState(1);
  // 역할별 생성 파라미터 — 부모(LLM2)/자식(LLM1)이 각각 playground 행이라 서버도 따로 저장한다.
  //   배포 시점에 서빙 컨테이너로 주입되므로 canEdit(중지 상태) 게이트를 모델 선택과 공유한다.
  const [promptParams, setPromptParams] = useState(DEFAULT_MODEL_PARAMS);
  const [inferenceParams, setInferenceParams] = useState(DEFAULT_MODEL_PARAMS);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Deployment' } }]));
    loadModalComponent('IMPORT_MODEL_PLAYGROUND');
    loadModalComponent('PLAYGROUND_DEPLOY');
  }, [dispatch]);

  const hydrateEditors = useCallback((normalized) => {
    if (editorsHydratedRef.current) return;
    const prompt = normalized.components.find(
      (component) => component.role === 'prompt_gen',
    );
    const inference = normalized.components.find(
      (component) => component.role === 'inference',
    );
    const promptResource = normalized.resources.find(
      (resource) => resource.role === 'prompt_gen',
    );
    const inferenceResource = normalized.resources.find(
      (resource) => resource.role === 'inference',
    );
    setPromptModel(prompt?.modelId ?? null);
    setPromptModelData(toModelCardValue(prompt));
    setPromptCommit(prompt?.modelCommitId ?? null);
    setInferenceModel(inference?.modelId ?? null);
    setInferenceModelData(toModelCardValue(inference));
    setInferenceCommit(inference?.modelCommitId ?? null);
    setInstanceId(
      promptResource?.instanceId ?? inferenceResource?.instanceId ?? null,
    );
    setPromptGpuCount(promptResource?.gpuCount ?? 1);
    setInferenceGpuCount(inferenceResource?.gpuCount ?? 1);
    // 저장된 역할별 파라미터 복원 — 없으면(미구성 셸) 기본값 유지.
    //   null 필드는 기본값으로 메워 rangebar 가 undefined 를 받지 않게 한다.
    const mergeParams = (saved) =>
      saved
        ? Object.fromEntries(
            Object.entries(DEFAULT_MODEL_PARAMS).map(([key, fallback]) => [
              key,
              saved[key] ?? fallback,
            ]),
          )
        : DEFAULT_MODEL_PARAMS;
    setPromptParams(mergeParams(prompt?.params));
    setInferenceParams(mergeParams(inference?.params));
    editorsHydratedRef.current = true;
  }, []);

  const load = useCallback(async () => {
    try {
      const normalized = await getNormalizedPlaygroundDetail(pid, workspaceId);
      if (normalized.mode !== 'dual') {
        throw new Error('이 경로는 이중모델 배포 상세 전용입니다.');
      }
      setDeployment(normalized);
      hydrateEditors(normalized);
      setDetailError('');
    } catch (error) {
      setDetailError(error.message || '배포 상세를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
    // 배포 시작 뒤에도 상세에 머무르므로 상태와 편집 가능 여부를 계속 갱신한다.
    return true;
  }, [pid, workspaceId, hydrateEditors]);

  // 형제 화면(InferenceMenu·InferenceDetail)과 같은 폴링 훅. raw setInterval 은
  //   (a) 탭을 백그라운드로 돌려도 계속 요청하고 (b) 왕복이 주기보다 길면 요청이 겹쳤다.
  //   이 훅은 state.tab.isActive 로 정지하고 await 후 대기라 겹침이 구조적으로 없다.
  useIntervalCall(load, 5000);

  useEffect(() => {
    // 단일 배포 모달과 같은 playground instance 계약을 사용해 화면/서버의 용량 기준을 맞춘다.
    getPlaygroundDeploymentList(pid).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        setInstances(Array.isArray(res.result) ? res.result : []);
      }
    });
  }, [pid]);

  const selectedInstanceData = instances.find(
    (instance) => String(instance.instance_id) === String(instanceId),
  );
  const promptResource = deployment?.resources.find(
    (resource) => resource.role === 'prompt_gen',
  );
  const inferenceResource = deployment?.resources.find(
    (resource) => resource.role === 'inference',
  );
  const hasConfiguredResource = instanceId != null;
  const resourceInfoModel = hasConfiguredResource
    ? {
        ...EMPTY_INSTANCE_INFO,
        ...selectedInstanceData,
        instance_id: instanceId,
        instance_name:
          selectedInstanceData?.instance_name ??
          promptResource?.instanceName ??
          inferenceResource?.instanceName ??
          '-',
        instance_allocate:
          promptResource?.instanceCount ??
          inferenceResource?.instanceCount ??
          selectedInstanceData?.instance_allocate ??
          0,
      }
    : EMPTY_INSTANCE_INFO;

  // LLM2 는 외부 SDS 도 허용되는데, 외부 배포 경로는 model_parameter 를 전혀 읽지 않는다.
  //   → 조용히 무시되는 입력을 만들지 않도록 파라미터 편집을 막고 사유를 표기한다.
  //   LLM1 은 내부 텍스트 모델만 허용되므로(BE 강제) 항상 적용된다.
  const isInferenceExternal =
    (inferenceModelData?.training_type ?? '') === 'external';

  const handlePromptParamChange = useCallback((key, val) => {
    setPromptParams((prev) => ({ ...prev, [key]: val }));
  }, []);
  const handleInferenceParamChange = useCallback((key, val) => {
    setInferenceParams((prev) => ({ ...prev, [key]: val }));
  }, []);
  const handlePromptModelChange = useCallback((model) => {
    setPromptModelData(model);
    setPromptModel(model.model_allm_id || null);
    setPromptCommit(model.model_allm_commit_id || null);
  }, []);
  const handleInferenceModelChange = useCallback((model) => {
    setInferenceModelData(model);
    setInferenceModel(model.model_allm_id || null);
    setInferenceCommit(model.model_allm_commit_id || null);
  }, []);

  const canEdit = !!deployment?.capabilities.canEditConfig && !actionLoading;
  const sameModel =
    promptModel != null && String(promptModel) === String(inferenceModel);
  const canDeploy = canEdit && !!promptModel && !!inferenceModel && !sameModel;
  const isConfigured = deployment?.components.every(
    (component) => component.modelId,
  );

  const handleDeploy = () => {
    if (!canDeploy) return;
    dispatch(
      openModal({
        modalType: 'PLAYGROUND_DEPLOY',
        modalData: {
          mode: 'dual',
          playgroundId: pid,
          canEdit,
          options: {
            prompt_gen_model_id: promptModel,
            inference_model_id: inferenceModel,
            prompt_gen_commit_id: promptCommit,
            inference_commit_id: inferenceCommit,
            prompt_gen_params: promptParams,
            inference_params: inferenceParams,
            isInferenceExternal,
          },
          resources: {
            instanceId,
            promptGpuCount,
            inferenceGpuCount,
          },
          onSuccess: async (resource) => {
            setInstanceId(resource.instanceId);
            setPromptGpuCount(resource.promptGpuCount);
            setInferenceGpuCount(resource.inferenceGpuCount);
            await load();
          },
        },
      }),
    );
  };

  const handleStop = async () => {
    if (!deployment?.capabilities.canStop || actionLoading) return;
    setActionLoading(true);
    try {
      const response = await postPlaygroundsStop(pid);
      if (response.status !== STATUS_SUCCESS) {
        errorToastMessage(response.error, response.message);
        return;
      }
      await load();
    } catch (error) {
      errorToastMessage(null, '이중모델 배포 중지 중 오류가 발생했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestart = async () => {
    if (!deployment?.capabilities.canRestart || actionLoading) return;
    setActionLoading(true);
    try {
      const response = await postDualRestart(pid);
      if (response.status !== STATUS_SUCCESS) {
        errorToastMessage(response.error, response.message);
        return;
      }
      await load();
    } catch (error) {
      errorToastMessage(null, '이중모델 재시작 중 오류가 발생했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const actions = (
    <>
      <ButtonV2
        colorType='skyblue'
        label='추론으로 이동'
        disabled={deployment?.overallStatus !== 'running' || actionLoading}
        onClick={() =>
          history.push(`/user/workspace/${workspaceId}/inference/${pid}`)
        }
      />
      <ButtonV2
        colorType='blue'
        label='재시작'
        disabled={!deployment?.capabilities.canRestart || actionLoading}
        onClick={handleRestart}
      />
      <ButtonV2
        colorType='red'
        label='중지'
        disabled={!deployment?.capabilities.canStop || actionLoading}
        isLoading={actionLoading && !!deployment?.capabilities.canStop}
        onClick={handleStop}
      />
      <ButtonV2
        colorType='blue'
        label={isConfigured ? '재구성 후 배포' : '배포'}
        disabled={!canDeploy}
        onClick={handleDeploy}
      />
    </>
  );

  const info = deployment?.info;
  const sections = {
    INFO: (
      <DeployDetailSection title='Information'>
        <dl className={cx('info-grid')}>
          <div>
            <dt>설명</dt>
            <dd>{info?.description || '-'}</dd>
          </div>
          <div>
            <dt>접근 범위</dt>
            <dd>{info?.access ? 'Public' : 'Private'}</dd>
          </div>
          <div>
            <dt>소유자</dt>
            <dd>{info?.owner || '-'}</dd>
          </div>
          <div>
            <dt>접근 사용자</dt>
            <dd>{(info?.users || []).join(', ') || '-'}</dd>
          </div>
          <div>
            <dt>생성일</dt>
            <dd>{info?.create_datetime || '-'}</dd>
          </div>
          <div>
            <dt>최근 수정일</dt>
            <dd>{info?.update_datetime || '-'}</dd>
          </div>
        </dl>
      </DeployDetailSection>
    ),
    MODEL: (
      /* 단일 배포 상세와 같은 PlaygroundFrame 카드 3열 — LLM1 | LLM2 | 자원 정보.
         자원 편집은 배포 모달이 소유해 탭에는 저장된 read-model만 보인다. */
      <div className={cx('model-cont')}>
        <div className={cx('role-col')}>
          <PlaygroundModel
            workspaceId={workspaceId}
            title='LLM1 · 프롬프트 생성 모델'
            value={promptModelData}
            onChange={handlePromptModelChange}
            disabled={!canEdit}
            allmOnly
            allowExternal={false}
            showServingEngine={false}
          />
          <p className={cx('note')}>
            LLM1은 내부 텍스트 모델과 체크포인트만 선택할 수 있습니다.
          </p>
          <PlaygroundModelParameterSetting
            title='LLM1 생성 파라미터'
            value={promptParams}
            onChange={handlePromptParamChange}
            defaults={DEFAULT_MODEL_PARAMS}
            disabled={!canEdit}
            isReady={!!promptModel}
            emptyText='프롬프트 생성 모델을 선택하면 파라미터가 활성화됩니다.'
          />
        </div>

        <div className={cx('role-col')}>
          <PlaygroundModel
            workspaceId={workspaceId}
            title='LLM2 · 추론 모델'
            value={inferenceModelData}
            onChange={handleInferenceModelChange}
            disabled={!canEdit}
            allmOnly
            showServingEngine={false}
          />
          <p className={cx('note')}>
            LLM2는 내부 모델과 외부 SDS 모델을 모두 선택할 수 있습니다.
          </p>
          {sameModel && (
            <p className={cx('warn')}>
              프롬프트 생성 모델과 추론 모델은 서로 달라야 합니다.
            </p>
          )}
          <PlaygroundModelParameterSetting
            title='LLM2 생성 파라미터'
            value={inferenceParams}
            onChange={handleInferenceParamChange}
            defaults={DEFAULT_MODEL_PARAMS}
            disabled={!canEdit || isInferenceExternal}
            isReady={!!inferenceModel && !isInferenceExternal}
            emptyText={
              isInferenceExternal
                ? '외부 SDS 모델은 생성 파라미터가 적용되지 않습니다.'
                : '추론 모델을 선택하면 파라미터가 활성화됩니다.'
            }
          />
        </div>

        <PlaygroundInstanceSettingInfo
          title='자원 정보'
          model={resourceInfoModel}
          status={hasConfiguredResource ? deployment?.overallStatus : '-'}
          immediatelyStatus={selectedInstanceData?.immediately_status ?? true}
          allocations={
            hasConfiguredResource
              ? [
                  {
                    role: 'LLM1',
                    gpuCount: promptGpuCount,
                    badgeType: 'gray',
                  },
                  {
                    role: 'LLM2',
                    gpuCount: inferenceGpuCount,
                    badgeType: 'blue',
                  },
                ]
              : undefined
          }
        />
      </div>
    ),
    MONITOR: (
      <div className={cx('form')}>
        {deployment?.components.map((component) => (
          <DeployDetailSection
            key={component.role}
            title={
              component.role === 'prompt_gen'
                ? 'LLM1 · 프롬프트 생성 모니터링'
                : 'LLM2 · 추론 모니터링'
            }
            badge={
              <Badge
                type={component.role === 'prompt_gen' ? 'gray' : 'blue'}
                size='sm'
                label={component.role === 'prompt_gen' ? 'LLM1' : 'LLM2'}
              />
            }
          >
            <PlaygroundMonitoring
              workspaceId={workspaceId}
              playgroundId={component.playgroundId}
            />
          </DeployDetailSection>
        ))}
      </div>
    ),
  };

  return (
    <DeployDetailShell
      deployment={deployment}
      loading={loading}
      error={detailError}
      onBack={() =>
        history.push(`/user/workspace/${workspaceId}/llmplayground`)
      }
      actions={actions}
      sections={sections}
      monitorDisabled={deployment?.overallStatus !== 'running'}
    />
  );
};

export default DualDeployDetail;
