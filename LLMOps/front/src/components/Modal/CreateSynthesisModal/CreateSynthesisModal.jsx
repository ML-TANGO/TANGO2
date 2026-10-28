import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

import {
  createSynthesisProject,
  getSynthesisManifests,
  updateSynthesisProject,
} from '@src/apis/flightbase/synthesis';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './CreateSynthesisModal.module.scss';

const cx = classNames.bind(style);

const FIELD_OPTIONS = [
  { label: 'SDS (해양/항만)', value: 'SDS' },
  { label: 'SDF (농업/작물)', value: 'SDF' },
  { label: 'SDM (제조)', value: 'SDM' },
];

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
  name: '',
  field: 'SDS',
  manifest: null, // "name@@version"
  metaPrompt: '',
  optimize: 'OPRO',
  count: '10',
  gpuCount: 0,
};

const calValidate = (s) => {
  if (!s.name) return '프로젝트 이름을 입력해 주세요.';
  if (!s.manifest) return '생성 모듈(manifest)을 선택해 주세요.';
  return '';
};

export default function CreateSynthesisModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspaceId, handleResetData, project } = data;
  const isEdit = !!project;

  const [manifestOptions, setManifestOptions] = useState([]);
  const [state, setState] = useState(() =>
    project
      ? {
          name: project.name || '',
          field: project.field || 'SDS',
          manifest: `${project.manifest_name}@@${project.manifest_version}`,
          metaPrompt: project.params?.meta_prompt || '',
          optimize: project.params?.optimize_method || 'OPRO',
          count: String(project.params?.count ?? '10'),
          gpuCount: project.gpu_count || 0,
        }
      : initialState,
  );
  const { name, field, manifest, metaPrompt, optimize, count, gpuCount } = state;

  const handleInput = (key, value) =>
    setState((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    (async () => {
      const { result, status, message } = await getSynthesisManifests();
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
        return;
      }
      setManifestOptions(
        (result || []).map((m) => ({
          label: `${m.name} (${m.version})`,
          value: `${m.name}@@${m.version}`,
        })),
      );
    })();
  }, []);

  const footerMessage = calValidate(state);
  const validate = !footerMessage;

  const handleSubmit = async () => {
    const [manifestName, manifestVersion] = (manifest || '').split('@@');
    const params = {
      meta_prompt: metaPrompt,
      optimize_method: optimize,
      count: +count || 0,
    };
    let res;
    if (isEdit) {
      res = await updateSynthesisProject(project.id, {
        name,
        field,
        manifest_name: manifestName,
        manifest_version: manifestVersion,
        params,
        gpu_count: +gpuCount,
      });
    } else {
      res = await createSynthesisProject({
        workspace_id: +workspaceId,
        name,
        field,
        mode: 'wizard',
        manifest_name: manifestName,
        manifest_version: manifestVersion,
        params,
        gpu_count: +gpuCount,
      });
    }
    if (res.status === STATUS_SUCCESS) {
      await handleResetData();
      dispatch(closeModal(type));
    } else {
      toast.error(res.message);
    }
  };

  return (
    <NewStyleModalFrame
      title={
        <h1 className={cx('title')}>
          {isEdit ? '합성 프로젝트 설정 수정' : '합성 프로젝트 생성'}
        </h1>
      }
      type={type}
      cancel={{ text: t('cancel.label'), func: () => dispatch(closeModal(type)) }}
      submit={{ text: t('create.label'), func: handleSubmit }}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel labelText={'프로젝트 이름'} labelSize='large' disableErrorMsg style={{ marginBottom: '32px' }}>
        <InputText
          size='medium'
          value={name}
          onChange={(e) => handleInput('name', e.target.value)}
          placeholder={'합성 프로젝트 이름'}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel labelText={'분야'} labelSize='large' disableErrorMsg style={{ marginBottom: '32px' }}>
        <Dropdown
          value={field}
          list={FIELD_OPTIONS}
          handleOptionClick={(info) => handleInput('field', info.value)}
          placeholder={'분야 선택'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel labelText={'생성 모듈'} labelSize='large' disableErrorMsg style={{ marginBottom: '32px' }}>
        <Dropdown
          value={manifest}
          list={manifestOptions}
          handleOptionClick={(info) => handleInput('manifest', info.value)}
          placeholder={'생성 모듈(컨테이너)을 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel labelText={'프롬프트 최적화'} labelSize='large' optionalSize='medium' optionalText='(고려대 LLM1)' disableErrorMsg style={{ marginBottom: '32px' }}>
        <Dropdown
          value={optimize}
          list={OPTIMIZE_OPTIONS}
          handleOptionClick={(info) => handleInput('optimize', info.value)}
          placeholder={'프롬프트 최적화 방식'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel labelText={'메타프롬프트'} labelSize='large' disableErrorMsg style={{ marginBottom: '32px' }}>
        <InputText
          size='medium'
          value={metaPrompt}
          onChange={(e) => handleInput('metaPrompt', e.target.value)}
          placeholder={'메타프롬프트를 입력하세요.'}
        />
      </InputBoxWithLabel>

      <InputBoxWithLabel labelText={'생성 개수'} labelSize='large' disableErrorMsg style={{ marginBottom: '32px' }}>
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
