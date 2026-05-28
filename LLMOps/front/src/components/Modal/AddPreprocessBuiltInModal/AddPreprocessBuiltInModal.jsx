import React, { useState } from 'react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';
import ParameterSetting from '@src/components/molecules/ParameterSetting';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './AddPreprocessBuiltInModal.module.scss';

const cx = classNames.bind(style);

export default function AddPreprocessBuiltInModal({ data, type }) {
  const { workspaceId } = data;

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

  return (
    <NewStyleModalFrame
      title={'AI 파이프라인 프로젝트 생성 (대기 중)'}
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
        labelText={'전처리 프로젝트'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={null}
          list={[]}
          handleOptionClick={() => {}}
          placeholder={'전처리 프로젝트를 선택하세요.'}
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
      <p className={cx('warn-message')}>
        [안내] 확장자 “.csv”, “.txt” 데이터 파일만 선택 가능합니다.
      </p>
      <ParameterSetting
        builtInParams={builtInParams}
        handleParams={handleParams}
      />
    </NewStyleModalFrame>
  );
}
