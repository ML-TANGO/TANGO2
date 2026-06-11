import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputNumber, InputText } from '@tango/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import InfiniteScrollDropDown from '@src/components/molecules/InfiniteScrollDropDown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';
import FixParamOption from './FixParamOption';
import SearchParamOption from './SearchParamOption';
import useTrainingGpuResource from './useTrainingGpuResource';

import classNames from 'classnames/bind';
import style from './HpsCustomModal.module.scss';

const cx = classNames.bind(style);
const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const HpsCustomModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { submit, cancel, workspaceId, trainId } = data;

  const [hpsName, setHpsName] = useState('');
  const [dockerImage, setDockerImage] = useState({ label: '', value: '' });
  const [dockerList, setDockerList] = useState([]);
  const [dataset, setDataset] = useState({ label: '', value: '' });
  const [datasetList, setDatasetList] = useState([]);
  const [actionCode, setActionCode] = useState({ label: '', value: '' });
  const [searchParam, setSearchParam] = useState([
    { name: '', type: 0, min: '', max: '', count: '', id: 1 },
  ]);
  const [fixParam, setFixParam] = useState([{ name: '', param: '', id: 1 }]);
  const [searchId, setSearchId] = useState(2);
  const [fixId, setFixId] = useState(2);
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
  } = useTrainingGpuResource({ trainId });

  const handleDocker = ({ label, value }) => {
    setDockerImage({ label, value });
  };

  const handleDataset = ({ label, value }) => {
    setDataset({ label, value });
  };

  const handleActionCode = ({ label, value }) => {
    setActionCode({ label, value });
  };

  const addFixParam = () => {
    setFixParam((prev) => [...prev, { name: '', param: '', id: fixId }]);
    setFixId((prev) => prev + 1);
  };

  const handleFixParamInfo = ({ id, info, value }) => {
    setFixParam((prev) =>
      prev.map((v) => (v.id === id ? { ...v, [info]: value } : { ...v })),
    );
  };

  const deleteFixParam = (id) => {
    setFixParam((prev) => prev.filter((v) => v.id !== id));
  };

  const addSearchParam = () => {
    setSearchParam((prev) => [
      ...prev,
      { name: '', type: 0, min: '', max: '', count: '', id: searchId },
    ]);
    setSearchId((prev) => prev + 1);
  };

  const handleParamInfo = ({ id, info, value }) => {
    setSearchParam((prev) =>
      prev.map((v) => (v.id === id ? { ...v, [info]: value } : { ...v })),
    );
  };

  const deleteParamInfo = (id) => {
    setSearchParam((prev) => prev.filter((v) => v.id !== id));
  };

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        project_id: Number(trainId),
        image_id: dockerImage.value,
        name: hpsName,
        run_code: actionCode.value,
        dataset_id: dataset.value,
        fixed_parameter: fixParam.map(({ name, param }) => ({
          name,
          value: param,
        })), // name, value
        parameter: searchParam.map(({ name, max, min, count, type }) => ({
          name,
          type: type === 0 ? 'int' : 'float',
          min: Number(min),
          max: Number(max),
          step: Number(count),
        })),
        // built_in_search_count: '',
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
        url: 'projects/hps',
        method: 'post',
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
        dispatch(closeModal('HPS_CUSTOM_CREATE'));
      }
    },
  };

  const fetchHpsOption = async () => {
    const response = await callApi({
      url: `options/project/hps?project_id=${trainId}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { image_list, instance_info, dataset_list } = result;

      const { resource_name, instance_type, total } = instance_info;
      const dockerList = image_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));
      const datasetList = dataset_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));

      setDockerList(dockerList);
      setDatasetList(datasetList);
      setInstanceType(instance_type);
      setGpuInfo({
        name: resource_name,
        max: total,
        used: '',
      });
    }
  };

  const handleFooterMessage = () => {
    const isValidParam = fixParam.every(({ param, name }) => param && name);
    const isValidParam1 = searchParam.every(
      ({ name, max, min, count }) => name && max && min && count,
    );
    const validationMessages = [
      {
        condition: !hpsName || nameExg.test(hpsName),
        message: 'HPS 이름을 입력해 주세요',
      },
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
      { condition: !actionCode.label, message: '실행 코드를 선택해주세요' },
      {
        condition: !isValidParam || !isValidParam1,
        message: '파라미터 값을 입력해 주세요',
      },
    ];

    const invalid = validationMessages.find(({ condition }) => condition);

    if (invalid) {
      setFooterMessage(invalid.message);
      return;
    }

    setFooterMessage('');
  };

  const submitBtnCheck = useCallback(() => {
    let validateCount = 0;
    const isValidParam = fixParam.every(({ param, name }) => param && name);
    const isValidParam1 = searchParam.every(
      ({ name, max, min, count }) => name && max && min && count,
    );
    if (
      !dockerImage.value ||
      !dataset.value ||
      !hpsName ||
      !actionCode.label ||
      !isValidParam ||
      !isValidParam1
    ) {
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
    hpsName,
    actionCode,
    fixParam,
    searchParam,
  ]);

  useEffect(() => {
    fetchHpsOption();
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
    hpsName,
    fixParam,
    searchParam,
  ]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={`HPS ${t('create.label')}`}
      customStyle={{ maxHeight: '750px' }}
      validate={validate}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`HPS ${t('name.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('hpsName.placeholder')}
            onChange={(e) => setHpsName(e.target.value)}
            name='workspace'
            value={hpsName}
            status={nameExg.test(hpsName) ? 'error' : 'default'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
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
        <InputBoxWithLabel
          labelText={`${t('runCode.label')}`}
          labelSize='large'
          disableErrorMsg
          optionalText='(EX) src/denoise.py'
        >
          <InfiniteScrollDropDown
            placeholder={t('runCode.placeholder')}
            handleSelectOption={handleActionCode}
            value={actionCode}
            tid={Number(trainId)}
            listCustomStyle={{ maxHeight: '170px', overflow: 'auto' }}
            isCloseBorder={false}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('검색 파라미터 설정')}`}
          labelSize='large'
          disableErrorMsg
        >
          <div className={cx('search-param-box')}>
            <div className={cx('range-param')}>
              <span className={cx('header-text')}>고정 파라미터</span>
              {fixParam.map(({ name, id, param }, index) => (
                <FixParamOption
                  key={id}
                  name={name}
                  id={id}
                  param={param}
                  handleFixParamInfo={handleFixParamInfo}
                  deleteFixParam={deleteFixParam}
                  isLast={index === fixParam.length - 1}
                />
              ))}

              <div className={cx('add-btn', 'bottom-line')}>
                <span>+</span>
                <span onClick={addFixParam}>고정파라미터 추가</span>
              </div>
              <span className={cx('header-text')}>범위 파라미터</span>
              {searchParam.map(({ id, name, max, min, count, type }, index) => (
                <SearchParamOption
                  key={id}
                  id={id}
                  name={name}
                  max={max}
                  min={min}
                  count={count}
                  type={type}
                  handleParamInfo={handleParamInfo}
                  deleteParamInfo={deleteParamInfo}
                  isLast={index === searchParam.length - 1}
                />
              ))}
              <div className={cx('add-btn')} onClick={addSearchParam}>
                <span>+</span>
                <span>파라미터 추가</span>
              </div>
            </div>
          </div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default HpsCustomModal;
