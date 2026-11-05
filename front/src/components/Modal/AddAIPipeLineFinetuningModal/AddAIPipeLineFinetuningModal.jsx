import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

import {
  getLlmModels,
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { getFineTuningConfig, getInstancesList } from '@src/apis/llm/model';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './AddAIPipeLineFinetuningModal.module.scss';

const cx = classNames.bind(style);

const GPU_OPTIONS = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
];

// external(SDS 등)=external_container manifest 학습 / internal=llm_model 내부 FT.
const isExternalModel = (m) =>
  m?.training_type === 'external' && !!m?.external_manifest_name;

const initialState = {
  modelId: null,
  gpuCount: 1,
  instanceId: null,
};

export default function AddAIPipeLineFinetuningModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const {
    workspaceId,
    pipelineId,
    x_index,
    y_index,
    handleResetData,
    isSerial,
    dataset_info,
  } = data;

  const [models, setModels] = useState([]);
  const [instanceOptions, setInstanceOptions] = useState([]);
  // internal 모델 선택 시 모델 바인딩 데이터셋 + 기본 config (getFineTuningConfig).
  const [internalInfo, setInternalInfo] = useState(null);
  const [state, setState] = useState(initialState);
  const { modelId, gpuCount, instanceId } = state;

  const handleInput = (key, value) =>
    setState((prev) => ({ ...prev, [key]: value }));

  // 워크스페이스 단위: 전체 LLM 모델 + 인스턴스 목록(internal FT 용).
  useEffect(() => {
    (async () => {
      const { result, status, message } = await getLlmModels(workspaceId);
      if (status === STATUS_SUCCESS) setModels(result || []);
      else toast.error(message);
    })();
    (async () => {
      const { result, status } = await getInstancesList(workspaceId);
      if (status === STATUS_SUCCESS) {
        setInstanceOptions(
          (result || []).map((i) => ({
            label: i.instance_name || i.resource_name,
            value: i.instance_id,
          })),
        );
      }
    })();
  }, [workspaceId]);

  const selectedModel = useMemo(
    () => models.find((m) => m.id === modelId),
    [models, modelId],
  );
  const isExternal = isExternalModel(selectedModel);

  // internal 모델 선택 시 모델 바인딩 데이터셋 + 기본 config 로드. external 이면 클리어.
  useEffect(() => {
    if (!selectedModel || isExternal) {
      setInternalInfo(null);
      return;
    }
    // 새 모델 config 로딩 전 stale 클리어 — 로딩 중 footer 가 invalid 가 되어 stale
    // model_dataset_id 로 제출되는 것을 차단(codex HIGH). 로드 완료 시 채워짐.
    setInternalInfo(null);
    let alive = true;
    (async () => {
      const { result, status } = await getFineTuningConfig(modelId);
      if (!alive) return;
      if (status === STATUS_SUCCESS) {
        const ds = (result?.model_datasets || [])[0] || null;
        setInternalInfo({
          modelDatasetId: ds?.id ?? null,
          datasetName: ds?.dataset_name ?? null,
          fineTuningConfig: result?.fine_tuning_config || null,
        });
      } else {
        setInternalInfo({ modelDatasetId: null, datasetName: null });
      }
    })();
    return () => {
      alive = false;
    };
  }, [modelId, isExternal]);

  const modelOptions = useMemo(
    () => models.map((m) => ({ label: m.name, value: m.id })),
    [models],
  );

  const manifestLabel = isExternal
    ? `${selectedModel.external_manifest_name} (${selectedModel.external_manifest_version})`
    : '-';

  const calFooterMessage = () => {
    if (!modelId) return '파인튜닝할 LLM 모델을 선택해 주세요.';
    if (isExternal) return '';
    // internal — internalInfo 로딩 중(null)이면 invalid(stale 제출 차단, codex HIGH).
    if (!internalInfo) return '모델 정보를 불러오는 중입니다.';
    if (!internalInfo.modelDatasetId)
      return '모델에 연결된 데이터셋이 없어 내부 파인튜닝을 실행할 수 없습니다.';
    if (!instanceId) return '학습 인스턴스를 선택해 주세요.';
    return '';
  };
  const footerMessage = calFooterMessage();
  const validate = !footerMessage;

  const handleSubmit = async () => {
    if (!selectedModel) return;
    // internal 제출 가드 — config 로딩 중/데이터셋·인스턴스 누락 시 stale 제출 차단(codex HIGH).
    if (!isExternal && (!internalInfo?.modelDatasetId || !instanceId)) return;

    if (isSerial) {
      const { status: serialStatus, message: serialMessage } =
        await putPipelinesAddSerial({
          pipeline_id: pipelineId,
          task_type: 'finetuning',
          y_index_base: y_index - 1,
        });
      if (serialStatus !== STATUS_SUCCESS) {
        toast.error(serialMessage);
        return;
      }
    }

    const builtInParams = isExternal
      ? {
          mode: 'external',
          manifest_name: selectedModel.external_manifest_name,
          manifest_version: selectedModel.external_manifest_version,
          // 1차=전체 학습 트리거(레시피/하이퍼파라미터는 manifest 기본값).
          params: {},
        }
      : {
          mode: 'internal',
          // 내부 FT 는 모델 바인딩 LLM 데이터셋 사용(파이프라인 데이터셋과 별개 — 후속 매핑).
          model_dataset_id: internalInfo?.modelDatasetId,
          instance_id: instanceId,
          instance_count: 1,
          gpu_count: +gpuCount,
          // fine_tuning_config 생략 시 BE 기본값. 모델 기존 config 가 있으면 그대로.
          ...(internalInfo?.fineTuningConfig
            ? { fine_tuning_config: internalInfo.fineTuningConfig }
            : {}),
        };

    const body = {
      pipeline_id: +pipelineId,
      task_item_id: +selectedModel.id, // finetuning = LLM 모델 바인딩(서버가 워크스페이스/소유 검증)
      task_type: 'finetuning',
      task_item_type: 'advanced',
      run_code: null,
      parameter: '',
      image_id: null,
      gpu_count: +gpuCount,
      built_in_params: builtInParams,
      x_index,
      y_index,
    };

    const { status, message } = await postPipelinesTask(body);
    if (status === STATUS_SUCCESS) {
      await handleResetData();
      dispatch(closeModal(type));
    } else {
      toast.error(message);
    }
  };

  return (
    <NewStyleModalFrame
      title={<h1 className={cx('title')}>파인튜닝 작업 추가</h1>}
      type={type}
      cancel={{
        text: t('cancel.label'),
        func: () => dispatch(closeModal(type)),
      }}
      submit={{ text: t('create.label'), func: handleSubmit }}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel
        labelText={'LLM 모델'}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={modelId}
          list={modelOptions}
          handleOptionClick={(info) => handleInput('modelId', info.value)}
          placeholder={'학습할 LLM 모델을 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      {isExternal ? (
        <>
          <InputBoxWithLabel
            labelText={'학습 모듈'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(외부 컨테이너 manifest)'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <InputText size='medium' value={manifestLabel} disabled />
          </InputBoxWithLabel>

          <InputBoxWithLabel
            labelText={'입력 데이터셋'}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <InputText
              size='medium'
              value={dataset_info?.name ?? '-'}
              disabled
            />
          </InputBoxWithLabel>
        </>
      ) : (
        modelId && (
          <>
            <InputBoxWithLabel
              labelText={'학습 데이터셋'}
              labelSize='large'
              optionalSize='medium'
              optionalText='(모델 연결 데이터셋)'
              disableErrorMsg
              style={{ marginBottom: '32px' }}
            >
              <InputText
                size='medium'
                value={internalInfo?.datasetName ?? '-'}
                disabled
              />
            </InputBoxWithLabel>

            <InputBoxWithLabel
              labelText={'학습 인스턴스'}
              labelSize='large'
              disableErrorMsg
              style={{ marginBottom: '32px' }}
            >
              <Dropdown
                value={instanceId}
                list={instanceOptions}
                handleOptionClick={(info) =>
                  handleInput('instanceId', info.value)
                }
                placeholder={'학습 인스턴스를 선택하세요.'}
                style={{ width: '100%', height: '36px', padding: '16px' }}
              />
            </InputBoxWithLabel>
          </>
        )
      )}

      <InputBoxWithLabel labelText={'GPU 할당'} labelSize='large' disableErrorMsg>
        <Dropdown
          value={gpuCount}
          list={GPU_OPTIONS}
          handleOptionClick={(info) => handleInput('gpuCount', info.value)}
          placeholder={'GPU 개수'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
}
