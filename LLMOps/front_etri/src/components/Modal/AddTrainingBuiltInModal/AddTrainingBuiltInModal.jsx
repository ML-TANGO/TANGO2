import React, { useCallback, useEffect, useState } from 'react';

import { InputNumber } from '@tango/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';
import ParameterSetting from '@src/components/molecules/ParameterSetting';

import NewStyleModalFrame from '../NewStyleModalFrame';

import {
  calSelectedInstanceInfo,
  getPipeLineProjectOptions,
} from '../AIPipeLineTrainingModal/util';

// CSS Module
import classNames from 'classnames/bind';
import style from './AddTrainingBuiltInModal.module.scss';

const cx = classNames.bind(style);

const initialOptions = {
  projectOptions: [],
  dockerImageOptions: [],
  trainCodeOptions: [],
};

const initialState = {
  project: null,
  dockerImage: null,
  gpuValue: 0,
  deployCode: null,
  parameter: '',
};

export default function AddTrainingBuiltInModal({ data, type }) {
  const { workspaceId } = data;

  const [options, setOptions] = useState(initialOptions);
  const { projectOptions, dockerImageOptions, trainCodeOptions } = options;

  const [state, setState] = useState(initialState);
  const { project, dockerImage, gpuValue, deployCode, parameter } = state;

  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });

  const [builtInParams, setBuiltInParams] = useState([]);
  const handleParams = (params, value) => {
    setBuiltInParams((prevParams) =>
      prevParams.map((param) =>
        param.label === params ? { ...param, value } : param,
      ),
    );
  };

  const selectedProjectInfo = calSelectedInstanceInfo(projectOptions, project);

  const handleInput = useCallback((inputType, value, setState) => {
    setState((prev) => {
      const newState = {
        ...prev,
        [inputType]: value,
      };

      if (inputType === 'project') {
        newState.deployCode = null;
      }

      return newState;
    });
  }, []);

  useEffect(() => {
    getPipeLineProjectOptions(
      workspaceId,
      'project',
      'projectOptions',
      setOptions,
    );
  }, [workspaceId]);

  return (
    <NewStyleModalFrame
      title={'학습 작업 추가 (대기 중)'}
      type={type}
      cancel={{
        text: '취소',
      }}
      submit={{
        text: '추가',
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
      footerMessage={''}
    >
      <InputBoxWithLabel
        labelText={'학습 프로젝트'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={null}
          list={projectOptions}
          handleOptionClick={() => {}}
          placeholder={'학습 프로젝트를 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
      <div className={cx('border')} />
      <InputBoxWithLabel
        labelText={'데이터셋 및 데이터'}
        labelSize='large'
        disableErrorMsg
        optionalSize='large'
      >
        <NewDatasetSearch
          workspaceId={workspaceId}
          selectData={selectData}
          setSelectedData={setSelectedData}
          selectDataset={selectDataset}
          setSelectedDataset={setSelectedDataset}
        />
      </InputBoxWithLabel>
      <p className={cx('dataset-message')}>
        [안내] 데이터는 파일만 선택 가능합니다.
      </p>
      <InputBoxWithLabel
        labelText={'GPU 할당'}
        labelSize='large'
        optionalSize='medium'
        optionalText={`${selectedProjectInfo.resource_name}`}
        disableErrorMsg
        style={{ marginBottom: '24px' }}
      >
        <InputNumber
          customSize={{ width: '269px' }}
          valueAlign={'left'}
          max={selectedProjectInfo.gpu_allocate}
          value={gpuValue}
          placeholder={`사용 가능: ${selectedProjectInfo.gpu_allocate}`}
          onChange={(e) => handleInput('gpuValue', +e.target.value, setState)}
        />
      </InputBoxWithLabel>
      <ParameterSetting
        builtInParams={builtInParams}
        handleParams={handleParams}
      />
    </NewStyleModalFrame>
  );
}
