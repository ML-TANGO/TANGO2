import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputNumber, InputText } from '@tango/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';
import ParameterSetting from '@src/components/molecules/ParameterSetting';

import {
  getTrainingBuiltinOptionsList,
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { downloadBlob, STATUS_SUCCESS } from '@src/network';

import { calTypeReturnTitle } from '../AddAiPipeLinepreprocessModal/AddAiPipeLinepreprocessModal';
import NewStyleModalFrame from '../NewStyleModalFrame';
import useHposParameter from './hooks/useHpsParameter';
import HpsParameter from './HpsParameter/HpsParameter';

import {
  calSelectedInstanceInfo,
  getDockerImageList,
  getPipeLineProjectOptions,
  getRunCodeOptions,
} from './util';

// CSS Module
import classNames from 'classnames/bind';
import style from './AIPipeLineTrainingModal.module.scss';

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
  trainCode: null,
  parameter: '',
};

const calValidate = (
  state,
  selectedProjectInfo,
  selectData,
  gpuValue,
  builtInParams,
) => {
  const { project, dockerImage, trainCode, parameter } = state;

  // ** 공통
  if (!project) return '프로젝트를 선택해 주세요.';

  // ** 커스텀
  if (!selectedProjectInfo.id || selectedProjectInfo.type === 'advanced') {
    if (!dockerImage) return '도커 이미지를 선택해 주세요.';
    if (!trainCode) return '학습 코드를 선택해 주세요.';
    // if (!parameter) return '파라미터를 입력해 주세요.';
    return '';
  }

  // ** 빌트인
  if (!selectData.name) return '사용하실 데이터셋를 선택해 주세요.';
  if (!gpuValue) return 'GPU 할당량을 입력해 주세요.';
  if (!builtInParams.every((param) => param.value))
    return '파라미터를 입력해 주세요.';

  return '';
};

const methodOptions = [
  {
    label: 'Job',
    value: 0,
  },
  { label: 'HPS', value: 1 },
];

export const getFetchBuiltOptions = async (
  id,
  setBuiltInParams,
  setBuiltInDataType,
) => {
  const { result, message, status } = await getTrainingBuiltinOptionsList(id);

  if (status !== STATUS_SUCCESS) {
    toast.error(message);
    return;
  } else {
    const { built_in_params, built_in_data_type } = result;

    if (built_in_params) {
      const params = built_in_params.map((v) => ({ label: v, value: '' }));
      setBuiltInParams(params);
    }
    setBuiltInDataType(built_in_data_type);
  }
};

export default function AIPipeLineTrainingModal({ type, data }) {
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

  const {
    fixParam,
    handleFixParamInfo,
    deleteFixParam,
    addFixParam,
    searchParam,
    handleParamInfo,
    deleteParamInfo,
    addSearchParam,
  } = useHposParameter();

  const [options, setOptions] = useState(initialOptions);
  const { projectOptions, dockerImageOptions, trainCodeOptions } = options;

  const [state, setState] = useState(initialState);
  const { project, dockerImage, gpuValue, trainCode, parameter } = state;

  const selectedProjectInfo = calSelectedInstanceInfo(projectOptions, project);
  const handleInput = useCallback((inputType, value, setState) => {
    setState((prev) => {
      const newState = {
        ...prev,
        [inputType]: value,
      };

      if (inputType === 'project') {
        newState.trainCode = null;
        setSelectedDataset({ id: '', name: '' });
      }

      return newState;
    });
  }, []);

  const [selectedMethod, setSelectedMethod] = useState(0);
  const handleMethodOptions = useCallback((e) => {
    setSelectedMethod(+e.target.value);
  }, []);

  const downloadReadme = async () => {
    const result = await downloadBlob({
      url: `options/built-in-model/readme/download?project_id=${project}`,
    });

    const blobUrl = window.URL.createObjectURL(
      new Blob([result], { type: 'application/octet-stream' }),
    );
    const link = document.createElement('a');
    link.href = blobUrl;
    link.setAttribute('download', `데이터 참고.md`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
  };

  const handleSumbmit = async (body) => {
    const { pipeline_id, task_item_id } = body;
    if (!pipeline_id || !task_item_id)
      return toast.error('아이디가 존재하지 않습니다.');

    if (isSerial) {
      const serialBody = {
        pipeline_id: pipelineId,
        task_type: 'project',
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

  // ** 학습 작업 추가 Built-in
  const title = calTypeReturnTitle(selectedProjectInfo.type, '학습 작업 추가');

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

  const submitBuiltIn = builtInParams.reduce((acc, item) => {
    acc[item.label] = item.value;
    return acc;
  }, {});

  const submit = {
    text: t('add.label'),
    func: () =>
      handleSumbmit({
        pipeline_id: +pipelineId,
        task_item_id: +project,
        task_type: 'project',
        task_item_type: selectedProjectInfo.type,
        project_training_type: selectedMethod === 0 ? 'job' : 'hps',
        dataset_data_path: selectData.name,
        run_code: trainCode,
        parameter,
        image_id: `${dockerImage}`,
        gpu_count: +gpuValue,
        built_in_params: submitBuiltIn,
        x_index,
        y_index,
      }),
  };
  const footerMessage = calValidate(
    state,
    selectedProjectInfo,
    selectData,
    gpuValue,
    builtInParams,
  );
  const validate = !footerMessage;

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
      'project',
      'projectOptions',
      setOptions,
    );
    getDockerImageList(workspaceId, 'dockerImageOptions', setOptions);
  }, [workspaceId]);

  useEffect(() => {
    if (!project) return;
    getRunCodeOptions(project, 'project', 'trainCodeOptions', setOptions);
  }, [project]);

  return (
    <NewStyleModalFrame
      title={title}
      type={type}
      cancel={{
        text: t('cancel.label'),
        func: () => dispatch(closeModal(type)),
      }}
      submit={submit}
      isResize={true}
      isMinimize={true}
      validate={validate}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel
        labelText={'학습 프로젝트'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Dropdown
          value={project}
          list={projectOptions}
          handleOptionClick={(info) =>
            handleInput('project', info.value, setState)
          }
          placeholder={'학습 프로젝트를 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
      <div className={cx('border')} />
      <InputBoxWithLabel
        labelText={'작업 유형'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Radio
          options={methodOptions}
          value={selectedMethod}
          onChange={handleMethodOptions}
          isLabelColor={true}
        />
      </InputBoxWithLabel>
      {(selectedProjectInfo.type === 'advanced' || !selectedProjectInfo.id) && (
        <>
          <div className={cx('flex-cont')}>
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
                style={{ width: '269px', height: '36px', padding: '16px' }}
              />
            </InputBoxWithLabel>
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
                min={0}
                max={selectedProjectInfo.gpu_allocategpu_allocate}
                value={gpuValue}
                placeholder={`사용 가능: ${selectedProjectInfo.gpu_allocate}`}
                onChange={(e) => {
                  handleInput('gpuValue', +e.target.value, setState);
                }}
              />
            </InputBoxWithLabel>
          </div>
          {gpuValue > 1 && (
            <InputBoxWithLabel
              labelText={t('gpuClusterCategory.label')}
              labelSize='large'
              disableErrorMsg
              style={{ marginBottom: '32px' }}
            >
              <Radio
                options={[
                  {
                    label: '1-GPU 서버 x2 [추천] 즉시 학습 시작 가능',
                    value: 0,
                  },
                ]}
                customStyle={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
                value={0}
                isLabelColor={true}
              />
            </InputBoxWithLabel>
          )}
          <InputBoxWithLabel
            labelText={'학습 코드'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(EX) src/deploy.py'
            disableErrorMsg
            style={{ marginBottom: '24px' }}
          >
            <Dropdown
              value={trainCode}
              list={trainCodeOptions}
              handleOptionClick={(info) =>
                handleInput('trainCode', info.value, setState)
              }
              placeholder={'학습 코드를 선택하세요.'}
              style={{ width: '100%', height: '36px', padding: '16px' }}
            />
          </InputBoxWithLabel>
          {selectedMethod === 0 && (
            <InputBoxWithLabel
              labelText={'파라미터'}
              labelSize='large'
              optionalSize='medium'
              optionalText='(EX) --use-compression --checkpoint version{v} ...'
              disableErrorMsg
            >
              <InputText
                size='medium'
                onChange={(e) => {
                  handleInput('parameter', e.target.value, setState);
                }}
                value={parameter}
                name='parameter'
                placeholder={'파라미터를 입력하세요.'}
              />
            </InputBoxWithLabel>
          )}
          {selectedMethod === 1 && (
            <HpsParameter
              fixParam={fixParam}
              handleFixParamInfo={handleFixParamInfo}
              deleteFixParam={deleteFixParam}
              addFixParam={addFixParam}
              searchParam={searchParam}
              handleParamInfo={handleParamInfo}
              deleteParamInfo={deleteParamInfo}
              addSearchParam={addSearchParam}
            />
          )}
        </>
      )}
      {selectedProjectInfo.id && selectedProjectInfo.type !== 'advanced' && (
        <>
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
          <p className={cx('data-message')}>
            [안내] 데이터는 파일만 선택 가능합니다.
          </p>
          <p className={cx('readme-label')}>데이터 참고 README 파일</p>
          <div className={cx('readme-btn-cont')}>
            <span>사용 데이터 참고.md</span>
            <button>
              <img
                src='/src/static/images/icon/00-ic-data-download.svg'
                alt='다운로드 버튼'
                onClick={downloadReadme}
              />
            </button>
          </div>
          <InputBoxWithLabel
            labelText={'GPU 할당'}
            labelSize='large'
            optionalSize='medium'
            optionalText={`${selectedProjectInfo.resource_name}`}
            disableErrorMsg
            style={{ marginBottom: '24px' }}
          >
            <InputNumber
              valueAlign={'left'}
              max={selectedProjectInfo.gpu_allocate}
              value={gpuValue}
              placeholder={`사용 가능: ${selectedProjectInfo.gpu_allocate}`}
              onChange={(e) => {
                handleInput('gpuValue', +e.value, setState);
              }}
            />
          </InputBoxWithLabel>
          {gpuValue > 1 && (
            <InputBoxWithLabel
              labelText={t('gpuClusterCategory.label')}
              labelSize='large'
              disableErrorMsg
            >
              <Radio
                options={[
                  {
                    label: '1-GPU 서버 x2 [추천] 즉시 학습 시작 가능',
                    value: 0,
                  },
                ]}
                customStyle={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
                value={0}
                isLabelColor={true}
              />
            </InputBoxWithLabel>
          )}
          {selectedMethod === 0 && (
            <ParameterSetting
              builtInParams={builtInParams}
              handleParams={handleParams}
            />
          )}
          {selectedMethod === 1 && (
            <InputBoxWithLabel
              labelText={'검색 횟수 입력'}
              labelSize='large'
              optionalSize='medium'
              optionalText={
                <span className={cx('blue-txt')}>권장 횟수: 39</span>
              }
              disableErrorMsg
              style={{ marginBottom: '24px' }}
            >
              <InputNumber
                valueAlign={'left'}
                min={0}
                max={selectedProjectInfo.gpu_allocategpu_allocate}
                value={gpuValue}
                placeholder={'검색 횟수를 입력하세요'}
                onChange={(e) => {
                  handleInput('gpuValue', +e.target.value, setState);
                }}
                disableIcon
                customSize={{ padding: '11px 12px' }}
              />
            </InputBoxWithLabel>
          )}
        </>
      )}
    </NewStyleModalFrame>
  );
}
