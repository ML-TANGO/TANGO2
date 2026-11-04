import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

import {
  getGenerationManifests,
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './AddAIPipeLineGenerationModal.module.scss';

const cx = classNames.bind(style);

// 프롬프트 최적화 방식 = 고려대 LLM1 단일 UI (v0.4 3.3 / SP-7 J-3).
const OPTIMIZE_OPTIONS = [
  { label: 'OPRO', value: 'OPRO' },
  { label: 'APE', value: 'APE' },
  { label: 'PROMPTBOOSTING', value: 'PROMPTBOOSTING' },
];

const GPU_OPTIONS = [
  { label: '0', value: 0 },
  { label: '1', value: 1 },
  { label: '2', value: 2 },
];

const initialState = {
  manifest: null, // "name@@version"
  optimize: 'OPRO',
  metaPrompt: '',
  count: '10',
  gpuCount: 0,
};

const calValidate = (state) => {
  if (!state.manifest) return '생성 모듈(manifest)을 선택해 주세요.';
  return '';
};

export default function AddAIPipeLineGenerationModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const {
    pipelineId,
    x_index,
    y_index,
    handleResetData,
    isSerial,
    dataset_info,
  } = data;

  const [manifestOptions, setManifestOptions] = useState([]);
  const [state, setState] = useState(initialState);
  const { manifest, optimize, metaPrompt, count, gpuCount } = state;

  const handleInput = (key, value) =>
    setState((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    (async () => {
      const { result, status, message } = await getGenerationManifests();
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
        return;
      }
      const options = (result || []).map((m) => ({
        label: `${m.name} (${m.version})`,
        value: `${m.name}@@${m.version}`,
      }));
      setManifestOptions(options);
    })();
  }, []);

  const footerMessage = calValidate(state);
  const validate = !footerMessage;

  const handleSubmit = async () => {
    const [manifestName, manifestVersion] = (manifest || '').split('@@');

    if (isSerial) {
      await putPipelinesAddSerial({
        pipeline_id: pipelineId,
        task_type: 'generation',
        y_index_base: y_index - 1,
      });
    }

    const body = {
      pipeline_id: +pipelineId,
      task_item_id: 0, // generation 노드는 backing item 테이블 없음 (nominal)
      task_type: 'generation',
      task_item_type: 'advanced',
      run_code: null,
      parameter: '',
      image_id: null,
      gpu_count: +gpuCount,
      built_in_params: {
        manifest_name: manifestName,
        manifest_version: manifestVersion,
        params: {
          meta_prompt: metaPrompt,
          optimize_method: optimize,
          count: +count || 0,
        },
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
      title={<h1 className={cx('title')}>생성 데이터 작업 추가</h1>}
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
        labelText={'생성 모듈'}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={manifest}
          list={manifestOptions}
          handleOptionClick={(info) => handleInput('manifest', info.value)}
          placeholder={'생성 모듈(컨테이너)을 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'입력 데이터셋'}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText size='medium' value={dataset_info?.name ?? '-'} disabled />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'프롬프트 최적화'}
        labelSize='large'
        optionalSize='medium'
        optionalText='(고려대 LLM1)'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={optimize}
          list={OPTIMIZE_OPTIONS}
          handleOptionClick={(info) => handleInput('optimize', info.value)}
          placeholder={'프롬프트 최적화 방식'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'메타프롬프트'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          size='medium'
          value={metaPrompt}
          onChange={(e) => handleInput('metaPrompt', e.target.value)}
          placeholder={'메타프롬프트를 입력하세요.'}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel
        labelText={'생성 개수'}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          size='medium'
          value={count}
          onChange={(e) => handleInput('count', e.target.value)}
          placeholder={'생성할 데이터 개수'}
        />
      </InputBoxWithLabel>

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
