import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

import {
  getLlmModels,
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './AddAIPipeLineLlmDeployModal.module.scss';

const cx = classNames.bind(style);

// 배포 타겟 — BE execute_llm_deploy 가 deploy_target 으로 분기.
// cluster=Playground 배포(계약 #4), edge=타겟 디바이스(SP-6, 양자화 GGUF 전제, P3).
const TARGET_OPTIONS = [
  { label: '클러스터 (Playground 배포)', value: 'cluster' },
  { label: '타겟 디바이스 (엣지)', value: 'edge' },
];

const initialState = {
  modelId: null,
  deployTarget: 'cluster',
};

export default function AddAIPipeLineLlmDeployModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspaceId, pipelineId, x_index, y_index, handleResetData, isSerial } =
    data;

  const [models, setModels] = useState([]);
  const [state, setState] = useState(initialState);
  const { modelId, deployTarget } = state;

  const handleInput = (key, value) =>
    setState((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    (async () => {
      const { result, status, message } = await getLlmModels(workspaceId);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
        return;
      }
      setModels(result || []);
    })();
  }, [workspaceId]);

  const modelOptions = useMemo(
    () => models.map((m) => ({ label: m.name, value: m.id })),
    [models],
  );

  const footerMessage = !modelId ? '배포할 모델을 선택해 주세요.' : '';
  const validate = !footerMessage;

  const handleSubmit = async () => {
    if (!modelId) return;

    if (isSerial) {
      const { status: serialStatus, message: serialMessage } =
        await putPipelinesAddSerial({
          pipeline_id: pipelineId,
          task_type: 'llm_deploy',
          y_index_base: y_index - 1,
        });
      if (serialStatus !== STATUS_SUCCESS) {
        toast.error(serialMessage);
        return;
      }
    }

    const body = {
      pipeline_id: +pipelineId,
      task_item_id: +modelId, // llm_deploy = LLM 모델 바인딩(서버가 워크스페이스/소유 검증)
      task_type: 'llm_deploy',
      task_item_type: 'advanced',
      run_code: null,
      parameter: '',
      image_id: null,
      gpu_count: 0,
      built_in_params: {
        // BE execute_llm_deploy → deploy_target 분기 (cluster #4 / edge P3 배선 예정)
        deploy_target: deployTarget,
      },
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
      title={<h1 className={cx('title')}>LLM 배포 작업 추가</h1>}
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
        labelText={'대상 모델'}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={modelId}
          list={modelOptions}
          handleOptionClick={(info) => handleInput('modelId', info.value)}
          placeholder={'배포할 모델을 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'배포 타겟'}
        labelSize='large'
        disableErrorMsg
      >
        <Dropdown
          value={deployTarget}
          list={TARGET_OPTIONS}
          handleOptionClick={(info) => handleInput('deployTarget', info.value)}
          placeholder={'배포 타겟'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
}
