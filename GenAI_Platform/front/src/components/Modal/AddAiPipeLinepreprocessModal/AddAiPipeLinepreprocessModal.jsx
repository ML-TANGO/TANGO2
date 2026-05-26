import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';
import ParameterSetting from '@src/components/molecules/ParameterSetting';
import { toast } from '@src/components/Toast';

import {
  getBuiltinOptionsList,
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import {
  calSelectedInstanceInfo,
  getDockerImageList,
  getPipeLineProjectOptions,
  getRunCodeOptions,
} from '../AIPipeLineTrainingModal/util';

// CSS module
import classNames from 'classnames/bind';
import style from './AddAiPipeLinepreprocessModal.module.scss';

const cx = classNames.bind(style);

const initialOptions = {
  preprocessOptions: [],
  dockerImageOptions: [],
  precodeOptions: [],
};

const initialState = {
  preproject: null,
  dockerImage: null,
  precode: null,
  parameter: '',
};

const PipeLineTitle = ({ title, src, type }) => {
  return (
    <div className={cx('title-cont')}>
      <h1 className={cx('title')}>{title}</h1>
      {src && (
        <div className={cx('type-cont')}>
          <img src={src} alt='데이터 타입 이미지' />
          <span>{type}</span>
        </div>
      )}
    </div>
  );
};

const calTypeTxt = (type) => {
  if (['advanced', 'custom'].includes(type)) return 'Custom';
  if (type === 'built-in') return 'Jonathan Intelligence';
  return 'Hugging face';
};

export const calTypeImg = (type) => {
  if (['advanced', 'custom'].includes(type))
    return '/src/static/images/icon/ic-allm-model.svg';
  if (type === 'built-in') return '/src/static/images/icon/jonathan-intell.svg';
  return '/src/static/images/icon/hugging-face.svg';
};

export const calTypeReturnTitle = (type, title) => {
  if (!type) return <PipeLineTitle title={title} src={null} type={null} />;

  const typeText = calTypeTxt(type);
  const typeImg = calTypeImg(type);

  return <PipeLineTitle title={title} src={typeImg} type={typeText} />;
};

const calValidate = (
  state,
  selectedProjectInfo,
  selectDataset,
  selectData,
  builtInParams,
) => {
  const { preproject, dockerImage, precode, parameter } = state;

  // ** 공통
  if (!preproject) return '전처리 프로젝트를 선택해 주세요.';

  // ** custom 일 경우
  if (selectedProjectInfo.type === 'advanced' || !selectedProjectInfo.id) {
    if (!dockerImage) return '도커 이미지를 선택해 주세요.';
    if (!precode) return '전처리기 코드를 선택해 주세요.';
    // if (!parameter) return '파라미터를 입력해 주세요.';
    return '';
  }

  // ** 빌트인일 경우
  if (!selectDataset.id) return '데이터셋을 선택해 주세요.';
  if (!selectData.name) return '데이터를 선택해 주세요.';
  if (!builtInParams.every((param) => param.value))
    return '파라미터를 입력해 주세요.';
  return '';
};

export const getFetchBuiltOptions = async (
  id,
  setBuiltInParams,
  setBuiltInDataType,
) => {
  const { result, message, status } = await getBuiltinOptionsList(id);

  if (status !== STATUS_SUCCESS) {
    toast.error(message);
    return;
  } else {
    const { built_in_params, built_in_data_type } = result;
    const params = built_in_params.map((v) => ({ label: v, value: '' }));
    setBuiltInParams(params);
    setBuiltInDataType(built_in_data_type);
  }
};

export default function AddAiPipeLinepreprocessModal({ type, data }) {
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

  const [options, setOptions] = useState(initialOptions);
  const { preprocessOptions, precodeOptions, dockerImageOptions } = options;

  const [state, setState] = useState(initialState);
  const { preproject, dockerImage, precode, parameter } = state;

  const selectedProjectInfo = calSelectedInstanceInfo(
    preprocessOptions,
    preproject,
  );

  const handleInput = useCallback((inputType, value, setState) => {
    setState((prev) => {
      const newState = {
        ...prev,
        [inputType]: value,
      };

      if (inputType === 'preproject') {
        newState.precode = null;
      }

      return newState;
    });
  }, []);

  const handleSumbmit = async (body) => {
    const { pipeline_id, task_item_id } = body;
    if (!pipeline_id || !task_item_id)
      return toast.error('아이디가 존재하지 않습니다.');

    if (isSerial) {
      const serialBody = {
        pipeline_id: pipelineId,
        task_type: 'preprocessing',
        y_index_base: y_index - 1,
      };
      await putPipelinesAddSerial(serialBody);
    }

    const { status, message } = await postPipelinesTask(body);
    if (status === STATUS_SUCCESS) {
      await handleResetData();
      dispatch(closeModal(type));
    } else {
      toast.error(message);
    }
  };

  // ! 빌트인일 경우
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
  const [builtInDataType, setBuiltInDataType] = useState('');

  // ** 타이플, 메세지, 유효성 검사
  const title = calTypeReturnTitle(
    selectedProjectInfo.type,
    '데이터 전처리 작업 추가',
  );
  const footerMessage = calValidate(
    state,
    selectedProjectInfo,
    selectDataset,
    selectData,
    builtInParams,
  );
  const validate = !footerMessage;

  const sumbmitBuiltInParams = builtInParams.reduce((acc, cur) => {
    acc[cur.label] = cur.value;
    return acc;
  }, {});

  const submit = {
    text: t('create.label'),
    func: () =>
      handleSumbmit({
        pipeline_id: +pipelineId,
        run_code: precode,
        image_id: `${dockerImage}`,
        parameter,
        task_item_id: +preproject,
        task_type: 'preprocessing',
        task_item_type: selectedProjectInfo.type,
        dataset_data_path: selectData.name,
        built_in_params: sumbmitBuiltInParams,
        x_index,
        y_index,
      }),
  };

  useEffect(() => {
    if (!selectedProjectInfo.id) return;
    if (selectedProjectInfo.type === 'advanced') return;

    setSelectedDataset({ id: dataset_info.id, name: dataset_info.name });
    getFetchBuiltOptions(
      selectedProjectInfo.id,
      setBuiltInParams,
      setBuiltInDataType,
    );
  }, [dataset_info.id, dataset_info.name, selectedProjectInfo]);

  useEffect(() => {
    getPipeLineProjectOptions(
      workspaceId,
      'preprocessing',
      'preprocessOptions',
      setOptions,
    );
    getDockerImageList(workspaceId, 'dockerImageOptions', setOptions);
  }, [workspaceId]);

  useEffect(() => {
    if (!preproject) return;
    getRunCodeOptions(
      preproject,
      'preprocessing',
      'precodeOptions',
      setOptions,
    );
  }, [preproject]);

  return (
    <NewStyleModalFrame
      title={title}
      type={type}
      cancel={{
        text: t('cancel.label'),
        func: () => dispatch(closeModal(type)),
      }}
      submit={submit}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel
        labelText={'전처리 프로젝트'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={preproject}
          list={preprocessOptions}
          handleOptionClick={(info) =>
            handleInput('preproject', info.value, setState)
          }
          placeholder={'전처리 프로젝트를 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
      <div
        style={{
          width: '100%',
          height: '1px',
          backgroundColor: '#dbdbdb',
          margin: '32px 0',
        }}
      />
      {(selectedProjectInfo.type === 'advanced' ||
        !selectedProjectInfo.type) && (
        <>
          <InputBoxWithLabel
            labelText={'도커 이미지'}
            labelSize='large'
            optionalSize='medium'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <Dropdown
              value={dockerImage}
              list={dockerImageOptions}
              handleOptionClick={(info) =>
                handleInput('dockerImage', info.value, setState)
              }
              placeholder={'도커 이미지를 선택하세요.'}
              style={{ width: '100%', height: '36px', padding: '16px' }}
            />
          </InputBoxWithLabel>
          <InputBoxWithLabel
            labelText={'전처리기 코드'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(EX) src/parse_video.py'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <Dropdown
              value={precode}
              list={precodeOptions}
              handleOptionClick={(info) => {
                handleInput('precode', info.value, setState);
              }}
              placeholder={'실행할 코드를 선택하세요.'}
              style={{ width: '100%', height: '36px', padding: '16px' }}
            />
          </InputBoxWithLabel>
          <InputBoxWithLabel
            labelText={'파라미터'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(EX) --cpu 1 --max-length 10m ...'
            disableErrorMsg
          >
            <InputText
              size='medium'
              onChange={(e) => {
                handleInput('parameter', e.target.value, setState);
              }}
              value={parameter}
              name='projectName'
              placeholder={'파라미터를 입력하세요.'}
            />
          </InputBoxWithLabel>
        </>
      )}
      {selectedProjectInfo.type && selectedProjectInfo.type !== 'advanced' && (
        <>
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
              firstDisabled={true}
            />
          </InputBoxWithLabel>
          <p className={cx('warn-message')}>
            [안내] 확장자 “.csv”, “.txt” 데이터 파일만 선택 가능합니다.
          </p>
          <ParameterSetting
            builtInParams={builtInParams}
            handleParams={handleParams}
          />
        </>
      )}
    </NewStyleModalFrame>
  );
}
