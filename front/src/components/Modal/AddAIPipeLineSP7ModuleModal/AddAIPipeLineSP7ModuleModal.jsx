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
import style from './AddAIPipeLineSP7ModuleModal.module.scss';

const cx = classNames.bind(style);

// 프롬프트 최적화 방식 = 고려대 LLM1 단일 UI (선택만 — 알고리즘은 컨테이너 안). v0.4 3.3 / SP-7.
const OPTIMIZE_OPTIONS = [
  { label: 'OPRO (메타프롬프트)', value: 'OPRO' },
  { label: 'APE (프롬프트 유도)', value: 'APE' },
  { label: 'PROMPTBOOSTING (앙상블)', value: 'PROMPTBOOSTING' },
];

const GPU_OPTIONS = [
  { label: '0', value: 0 },
  { label: '1', value: 1 },
  { label: '2', value: 2 },
];

// 모듈별 UI/카피 구성. 3-모듈 전부 external_container manifest 노드(고려대 컨테이너)이고
// task_type 만 다르므로 1개 모달을 moduleKind 로 분기. (SP-7 Phase 2 scaffolding)
const MODULE_CONFIG = {
  prompt_gen: {
    title: '프롬프트 생성 (LLM1) 작업 추가',
    moduleLabel: '프롬프트 생성 모듈',
    promptLabel: '메타프롬프트',
    promptKey: 'meta_prompt',
    promptPlaceholder: '메타프롬프트(작업 설명·예시)를 입력하세요.',
    showOptimize: true,
  },
  data_gen: {
    title: '데이터 생성 (LLM2) 작업 추가',
    moduleLabel: '데이터 생성 모듈',
    promptLabel: '데이터 생성 프롬프트',
    promptKey: 'gen_prompt',
    promptPlaceholder: '데이터(라벨/주석) 생성 프롬프트를 입력하세요.',
    showOptimize: false,
  },
  algo_call: {
    title: '알고리즘 호출 (LLM3) 작업 추가',
    moduleLabel: '알고리즘 호출 모듈',
    promptLabel: 'API 호출 프롬프트',
    promptKey: 'call_prompt',
    promptPlaceholder: '학습 알고리즘/타겟 환경 호출 프롬프트를 입력하세요.',
    showOptimize: false,
  },
};

const initialState = {
  manifest: null, // "name@@version"
  optimize: 'OPRO',
  prompt: '',
  gpuCount: 0,
};

const calValidate = (state, cfg) => {
  if (!state.manifest) return `${cfg.moduleLabel}(manifest)을 선택해 주세요.`;
  return '';
};

export default function AddAIPipeLineSP7ModuleModal({ type, data, moduleKind }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { pipelineId, x_index, y_index, handleResetData, isSerial, dataset_info } =
    data;

  const cfg = MODULE_CONFIG[moduleKind] ?? MODULE_CONFIG.prompt_gen;

  const [manifestOptions, setManifestOptions] = useState([]);
  const [state, setState] = useState(initialState);
  const { manifest, optimize, prompt, gpuCount } = state;

  const handleInput = (key, value) =>
    setState((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    // SP-7 3-모듈 manifest 는 전부 external_container generate job 계열 — 생성 노드와
    // 동일 목록 재사용(고려대 컨테이너 수령 전 mock 도 generate 로 등록). 차후 job_type
    // 분기가 필요하면 module 별 옵션 엔드포인트로 확장.
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

  const footerMessage = calValidate(state, cfg);
  const validate = !footerMessage;

  const handleSubmit = async () => {
    const [manifestName, manifestVersion] = (manifest || '').split('@@');

    if (isSerial) {
      await putPipelinesAddSerial({
        pipeline_id: pipelineId,
        task_type: moduleKind,
        y_index_base: y_index - 1,
      });
    }

    // params 는 컨테이너로 verbatim passthrough(알고리즘은 고려대 컨테이너 소관).
    const params = { [cfg.promptKey]: prompt };
    if (cfg.showOptimize) {
      params.optimize_method = optimize;
    }

    const body = {
      pipeline_id: +pipelineId,
      task_item_id: 0, // SP-7 모듈 노드는 backing item 테이블 없음 (nominal)
      task_type: moduleKind,
      task_item_type: 'advanced',
      run_code: null,
      parameter: '',
      image_id: null,
      gpu_count: +gpuCount,
      built_in_params: {
        manifest_name: manifestName,
        manifest_version: manifestVersion,
        params,
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
      title={<h1 className={cx('title')}>{cfg.title}</h1>}
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
        labelText={cfg.moduleLabel}
        labelSize='large'
        optionalSize='medium'
        optionalText='(고려대 컨테이너)'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={manifest}
          list={manifestOptions}
          handleOptionClick={(info) => handleInput('manifest', info.value)}
          placeholder={`${cfg.moduleLabel}(컨테이너)을 선택하세요.`}
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

      {cfg.showOptimize && (
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
      )}

      <InputBoxWithLabel
        labelText={cfg.promptLabel}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          size='medium'
          value={prompt}
          onChange={(e) => handleInput('prompt', e.target.value)}
          placeholder={cfg.promptPlaceholder}
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
