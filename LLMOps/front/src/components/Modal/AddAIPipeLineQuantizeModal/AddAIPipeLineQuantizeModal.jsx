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
import style from './AddAIPipeLineQuantizeModal.module.scss';

const cx = classNames.bind(style);

// llama.cpp GGUF 양자화 타입 (SP-4). target_quant 는 BE convert job 으로 전달.
const QUANT_OPTIONS = [
  { label: 'Q4_K_M (4-bit, 권장)', value: 'Q4_K_M' },
  { label: 'Q5_K_M (5-bit)', value: 'Q5_K_M' },
  { label: 'Q6_K (6-bit)', value: 'Q6_K' },
];

const initialState = {
  modelId: null,
  targetQuant: 'Q4_K_M',
};

export default function AddAIPipeLineQuantizeModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspaceId, pipelineId, x_index, y_index, handleResetData, isSerial } =
    data;

  const [models, setModels] = useState([]);
  const [state, setState] = useState(initialState);
  const { modelId, targetQuant } = state;

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

  const footerMessage = !modelId ? '양자화할 모델을 선택해 주세요.' : '';
  const validate = !footerMessage;

  const handleSubmit = async () => {
    if (!modelId) return;

    if (isSerial) {
      const { status: serialStatus, message: serialMessage } =
        await putPipelinesAddSerial({
          pipeline_id: pipelineId,
          task_type: 'quantize',
          y_index_base: y_index - 1,
        });
      if (serialStatus !== STATUS_SUCCESS) {
        toast.error(serialMessage);
        return;
      }
    }

    const body = {
      pipeline_id: +pipelineId,
      task_item_id: +modelId, // quantize = LLM 모델 바인딩(서버가 워크스페이스/소유 검증)
      task_type: 'quantize',
      task_item_type: 'advanced',
      run_code: null,
      parameter: '',
      image_id: null,
      gpu_count: 0, // convert(llama.cpp)=CPU job
      built_in_params: {
        // BE execute_quantize → llm_model /quantize (target_device/prune 는 후속 4.5/4.7)
        target_quant: targetQuant,
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
      title={<h1 className={cx('title')}>양자화 작업 추가</h1>}
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
          placeholder={'양자화할 학습 완료 모델을 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'양자화 타입'}
        labelSize='large'
        optionalSize='medium'
        optionalText='(GGUF)'
        disableErrorMsg
      >
        <Dropdown
          value={targetQuant}
          list={QUANT_OPTIONS}
          handleOptionClick={(info) => handleInput('targetQuant', info.value)}
          placeholder={'양자화 비트'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
}
