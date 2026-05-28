import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputNumber } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';
import useDatasetResource from './useDatasetResource';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DatasetResourceModal.module.scss';

const cx = classNames.bind(style);

const TOOL_NAME = { shell: 'Shell', vscode: 'VSCode', jupyter: 'Jupyter Lab' };
const TOOL_LOGO = { shell: 'ssh', vscode: 'vscode', jupyter: 'jupyter' };

const DatasetResourceModal = ({ data, type }) => {
  const { submit, cancel, tool, preprocessing_id, preprocessing_tool_id } =
    data;

  const dispatch = useDispatch();
  const { t } = useTranslation();

  const [dockerImage, setDockerImage] = useState({ label: '', value: '' });
  const [dockerList, setDockerList] = useState([]);
  const [dataset, setDataset] = useState({ label: '', value: '' });
  const [datasetList, setDatasetList] = useState([]);
  const [instanceType, setInstanceType] = useState('');
  const [validate, setValidate] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');

  const {
    gpuInfo,
    gpuClusterList,
    gpuClusterSelectedOption,
    podGpuGcd,
    gpuUsingError,
    gpuClusterType,
    selectedGpuClusterType,
    originalGpuClusterList,
    selectedGpuList,
    handleGpuCnt,
    handleGpuClusterOption,
    handleSelectedGpuCluster,
    handleGpuClusterType,
    fetchGpuClusterType,
    setGpuInfo,
  } = useDatasetResource({ preprocessing_id });

  const handleDocker = ({ label, value }) => {
    setDockerImage({ label, value });
  };

  const handleDataset = ({ label, value }) => {
    setDataset({ label, value });
  };

  const submitBtnCheck = useCallback(() => {
    let validateCount = 0;
    if (!dockerImage.value || !dataset.value) {
      validateCount += 1;
    }
    if (instanceType === 'GPU' && typeof gpuInfo.used !== 'number') {
      validateCount += 1;
    }
    if (
      gpuClusterSelectedOption === 0 &&
      gpuInfo.used > 1 &&
      gpuInfo.used !== selectedGpuList.length
    ) {
      validateCount += 1;
    }
    if (validateCount !== 0) {
      setValidate(false);
      return;
    }
    setValidate(true);
  }, [
    dockerImage,
    dataset,
    gpuInfo,
    gpuClusterSelectedOption,
    selectedGpuList,
    instanceType,
  ]);

  const handleFooterMessage = () => {
    const validationMessages = [
      { condition: !dockerImage.value, message: '도커 이미지를 선택해 주세요' },
      { condition: !dataset.value, message: '데이터셋을 선택해 주세요' },
      {
        condition: instanceType === 'GPU' && typeof gpuInfo.used !== 'number',
        message: 'GPU 개수를 입력해 주세요',
      },
      {
        condition:
          gpuClusterSelectedOption === 0 &&
          gpuInfo.used > 1 &&
          gpuInfo.used !== selectedGpuList.length,
        message: 'GPU를 선택해 주세요',
      },
    ];

    const invalid = validationMessages.find(({ condition }) => condition);

    if (invalid) {
      setFooterMessage(invalid.message);
      return;
    }

    setFooterMessage('');
  };

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        preprocessing_tool_id,
        dataset_id: dataset.value,
        action: 'on',
        docker_image_id: dockerImage.value,
        ...(instanceType === 'GPU' && { gpu_count: gpuInfo.used }),
      };

      if (parseInt(gpuInfo.used) > 1) {
        body.gpu_cluster_auto = gpuClusterSelectedOption === 1 ? true : false;

        const { gpu_count, status, server } =
          gpuClusterType[selectedGpuClusterType];

        if (gpuClusterSelectedOption === 1) {
          // GPU 클러스터 자동설정
          body.gpu_auto_select = { gpu_count, server, status };
          body.gpu_cluster_case_old = gpuClusterType.map(
            ({ gpu_count, server, status }) => ({ gpu_count, server, status }),
          );
        } else {
          // GPU 클러스터 수동설정
          body.gpu_select = selectedGpuList;
          body.pod_per_gpu = gpu_count;
          body.gpu_cluster_list_old = originalGpuClusterList;
        }
      }

      const response = await callApi({
        url: 'preprocessing/tool/run',
        method: 'PUT',
        body,
      });

      const { status, message, error, result } = response;

      if (!result) {
        dispatch(
          openConfirm({
            title: 'gpuClusterCategory.label',
            content: 'gpuTypePopupfirst.desc',
            submit: {
              text: 'confirm.label',
            },
            cancel: {
              text: 'cancel.label',
            },
            contentCustomStyle: {
              color: 'rgba(116, 116, 116, 1)',
            },
          }),
        );

        fetchGpuClusterType();

        return false;
      }

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('DATASET_RESOURCE'));
        return true;
      }

      errorToastMessage(error, message);
      return false;
    },
  };

  const titleGPUComponent = () => (
    <div className={cx('title-container')}>
      <span>GPU 할당</span>
      <div className={cx('logo')}>
        <img
          width={24}
          height={24}
          src={`/images/icon/ic-${TOOL_LOGO[tool]}.svg`}
          alt='logo'
        />
        <span>{TOOL_NAME[tool]}</span>
      </div>
    </div>
  );

  const titleCPUComponent = () => (
    <div className={cx('title-container')}>
      <span>CPU 할당</span>
    </div>
  );

  const gpuClusterOption = [
    {
      label: 'autoSetting',
      value: 1,
      desc: t('autoSetting.desc'),
      descStatus: true,
    },
    {
      label: 'manualSetting',
      value: 0,
      desc: t('manualSetting.desc'),
      descStatus: false,
    },
  ];

  const fetchToolOption = async () => {
    const response = await callApi({
      url: `preprocessing/option/tool?preprocessing_id=${preprocessing_id}&preprocessing_tool_id=${preprocessing_tool_id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const {
        dataset_list,
        image_list,
        instance_info,
        instance_type,
        project_gpu_total,
        tool_gpu_count,
      } = result;

      const { resource_name, total } = instance_info;
      const imageList = image_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));
      const datasetList = dataset_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));
      setDockerList(imageList);
      setDatasetList(datasetList);
      setInstanceType(instance_type);
      setGpuInfo({
        name: resource_name,
        max: total,
        used: '',
      });
    }
  };

  useEffect(() => {
    fetchToolOption();
  }, []);

  useEffect(() => {
    handleFooterMessage();
    submitBtnCheck();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    gpuInfo,
    dockerImage,
    dataset,
    selectedGpuList,
    submitBtnCheck,
    gpuClusterSelectedOption,
    selectedGpuList,
  ]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={instanceType === 'GPU' ? titleGPUComponent() : titleCPUComponent()}
      customStyle={{ maxHeight: '750px' }}
      validate={validate}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('docker image')}`}
          labelSize='large'
          disableErrorMsg
        >
          <GrayDropDown
            list={dockerList}
            value={dockerImage}
            handleSelectOption={handleDocker}
            placeholder={t('dockerImage.placeholder')}
            isCloseBorder={false}
            listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
          />
        </InputBoxWithLabel>
        <div className={cx('dataset-gpu-box')}>
          <div className={cx('dataset-gpu')}>
            <div className={cx('dataset-box')}>
              <InputBoxWithLabel
                labelText={`${t('dataset')}`}
                labelSize='large'
                disableErrorMsg
              >
                <GrayDropDown
                  list={datasetList}
                  value={dataset}
                  handleSelectOption={handleDataset}
                  placeholder={t('dataset.placeholder')}
                  isCloseBorder={false}
                  listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('gpu-box')}>
              {instanceType === 'GPU' && (
                <InputBoxWithLabel
                  labelText={`GPU ${t('allocateGpu.label')}`}
                  labelSize='large'
                  disableErrorMsg
                  optionalText={gpuInfo.name}
                >
                  <InputNumber
                    name='gpu'
                    placeholder={`${t('currentAvailableCount')} : ${
                      gpuInfo.max === '' ? '0' : gpuInfo.max
                    }`}
                    min={0}
                    max={gpuInfo.max}
                    value={gpuInfo.used}
                    onChange={(e) => {
                      if (`${gpuInfo.max}` === '0') return;
                      let inputValue = e.value;

                      if (e.value > gpuInfo.max) {
                        inputValue = gpuInfo.max;
                      }
                      handleGpuCnt({ value: inputValue });
                    }}
                    isReadOnly={`${gpuInfo.max}` === '0'}
                    disabled={`${gpuInfo.max}` === '0'}
                    customSize={{ width: '100%' }}
                  />
                </InputBoxWithLabel>
              )}
            </div>
          </div>
          <div className={cx('desc', gpuInfo.used > 1 && 'warning')}>
            {(gpuInfo.used === '' || gpuInfo.used < 2) && (
              <>
                <span>
                  [권장] 개발 도구에는 GPU를 할당하지 않는 것을 권장 드립니다.
                </span>
                <span>GPU를 이용한 학습의 경우 JOB 기능을 사용해주세요.</span>
              </>
            )}
            {gpuInfo.used > 1 && (
              <>
                <span>
                  [주의] 개발 도구에 할당된 GPU는 다른 개발도구나, JOB 등에서
                  활용 불가합니다.
                </span>
                <span>
                  사용 완료 후, 반드시 개발 도구를 종료하여 GPU 할당을
                  해제해주시길 바랍니다.
                </span>
              </>
            )}
          </div>
        </div>
        <div className={cx(`${gpuInfo.used > 1 ? 'gpu-rows' : 'no-content'}`)}>
          {/* {gpuInfo.used > 1 && (
            <div className={cx('single-row', 'option')}>
              <InputBoxWithLabel
                labelText={t('gpuClusterOption')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={gpuClusterOption}
                  customStyle={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                  onChange={(e) =>
                    handleGpuClusterOption(e.currentTarget.value)
                  }
                  value={gpuClusterSelectedOption}
                  isShowAllDesc={false}
                  isLabelColor={true}
                />
              </InputBoxWithLabel>
            </div>
          )} */}

          {/* * GPU 클러스터 선택 리스트 GPU 할당 2개 이상일때 보여줘야한다. */}
          {gpuInfo.used > 1 && gpuClusterSelectedOption === 0 && (
            <div className={cx('single-row')}>
              <GpuNodeSelectBox
                gpuClusterList={gpuClusterList}
                handleSelectedGpuCluster={handleSelectedGpuCluster}
                podGpuGcd={podGpuGcd}
                isShowPodGpuGcd={true}
                gpuUsingError={gpuUsingError}
              />
            </div>
          )}

          {gpuInfo.used > 1 && gpuClusterType.length ? (
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('gpuClusterCategory.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={gpuClusterType}
                  customStyle={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                  onChange={(e) => handleGpuClusterType(e.currentTarget.value)}
                  value={selectedGpuClusterType}
                  isLabelColor={true}
                />
              </InputBoxWithLabel>
            </div>
          ) : (
            <div></div>
          )}
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default DatasetResourceModal;
