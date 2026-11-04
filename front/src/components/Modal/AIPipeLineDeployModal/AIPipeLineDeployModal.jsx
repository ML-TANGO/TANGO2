import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputNumber, InputText } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import {
  postPipelinesTask,
  putPipelinesAddSerial,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { calTypeReturnTitle } from '../AddAiPipeLinepreprocessModal/AddAiPipeLinepreprocessModal';
import NewStyleModalFrame from '../NewStyleModalFrame';

import {
  calSelectedInstanceInfo,
  getDockerImageList,
  getPipeLineProjectOptions,
  getRunCodeOptions,
} from '../AIPipeLineTrainingModal/util';

import classNames from 'classnames/bind';
import style from './AIPipeLineDeployModal.module.scss';

const cx = classNames.bind(style);

const initialOptions = {
  projectOptions: [],
  dockerImageOptions: [],
  deployCodeOptions: [],
};

const initialState = {
  project: null,
  dockerImage: null,
  gpuValue: 0,
  deployCode: null,
  parameter: '',
};

const calValidate = (state, selectedProjectInfo) => {
  const { project, dockerImage, deployCode, parameter } = state;

  // ** 공통
  if (!project) return '프로젝트를 선택해 주세요.';

  if (selectedProjectInfo.type === 'custom') {
    if (!dockerImage) return '도커 이미지를 선택해 주세요.';
    if (!deployCode) return '배포 코드를 선택해 주세요.';
    // if (!parameter) return '파라미터를 입력해 주세요.';
  }
  return '';
};

export default function AIPipeLineDeployModal({ type, data }) {
  const { t } = useTranslation();
  const {
    workspaceId,
    pipelineId,
    x_index,
    y_index,
    handleResetData,
    isSerial,
  } = data;
  const dispatch = useDispatch();

  const [options, setOptions] = useState(initialOptions);
  const { projectOptions, dockerImageOptions, deployCodeOptions } = options;

  const [state, setState] = useState(initialState);
  const { project, dockerImage, gpuValue, deployCode, parameter } = state;
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

  const handleSumbmit = async (body) => {
    const { pipeline_id, task_item_id } = body;
    if (!pipeline_id || !task_item_id)
      return toast.error('아이디가 존재하지 않습니다.');

    if (isSerial) {
      const serialBody = {
        pipeline_id: pipelineId,
        task_type: 'deployment',
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

  // ! 배포 built-in
  const title = calTypeReturnTitle(selectedProjectInfo.type, '배포 작업 추가');
  const footerMessage = calValidate(state, selectedProjectInfo);
  const validate = !footerMessage;

  const submit = {
    text: t('add.label'),
    func: () =>
      handleSumbmit({
        pipeline_id: +pipelineId,
        task_item_id: +project,
        task_type: 'deployment',
        task_item_type:
          selectedProjectInfo.type === 'custom'
            ? 'advanced'
            : selectedProjectInfo.type,
        run_code: deployCode,
        parameter,
        image_id: `${dockerImage}`,
        gpu_count: +gpuValue,
        x_index,
        y_index,
      }),
  };

  useEffect(() => {
    getPipeLineProjectOptions(
      workspaceId,
      'deployment',
      'projectOptions',
      setOptions,
    );
    getDockerImageList(workspaceId, 'dockerImageOptions', setOptions);
  }, [workspaceId]);

  useEffect(() => {
    if (!project) return;
    getRunCodeOptions(project, 'deployment', 'deployCodeOptions', setOptions);
  }, [dispatch, project]);

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
        labelText={'프로젝트'}
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
          placeholder={'프로젝트를 선택하세요.'}
          style={{ width: '100%', height: '36px', padding: '16px' }}
        />
      </InputBoxWithLabel>
      {(!selectedProjectInfo.id || selectedProjectInfo.type === 'custom') && (
        <>
          <div
            style={{
              width: '100%',
              height: '1px',
              backgroundColor: '#dbdbdb',
              margin: '32px 0',
            }}
          />
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
                max={selectedProjectInfo.gpu_allocate}
                value={gpuValue}
                placeholder={`사용 가능: ${selectedProjectInfo.gpu_allocate}`}
                onChange={(e) =>
                  handleInput('gpuValue', +e.target.value, setState)
                }
              />
            </InputBoxWithLabel>
          </div>
          <InputBoxWithLabel
            labelText={'배포 코드'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(EX) src/deploy.py'
            disableErrorMsg
            style={{ marginBottom: '24px' }}
          >
            <Dropdown
              value={deployCode}
              list={deployCodeOptions}
              handleOptionClick={(info) =>
                handleInput('deployCode', info.value, setState)
              }
              placeholder={'배포 코드를 선택하세요.'}
              style={{ width: '100%', height: '36px', padding: '16px' }}
            />
          </InputBoxWithLabel>
          <InputBoxWithLabel
            labelText={'파라미터'}
            labelSize='large'
            optionalSize='medium'
            optionalText='(EX) --use-compression --checkpoint version{v} ...'
            disableErrorMsg
            style={{ marginBottom: '24px' }}
          >
            <InputText
              size='medium'
              onChange={(e) => {
                handleInput('parameter', e.target.value, setState);
              }}
              name='parameter'
              placeholder={'파라미터를 입력하세요.'}
              value={parameter}
            />
          </InputBoxWithLabel>
        </>
      )}
    </NewStyleModalFrame>
  );
}
