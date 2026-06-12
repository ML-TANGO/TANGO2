import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputNumber, InputText } from '@tango/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';
import { callApi, downloadBlob, STATUS_SUCCESS } from '@src/network';

import useTrainingGpuResource from '../HpsCustomModal/useTrainingGpuResource';
import NewStyleModalFrame from '../NewStyleModalFrame';
import DownloadIcon from './gray-download.svg';

import { copyToClipboard } from '@src/utils';

import classNames from 'classnames/bind';
import style from './HpsBuiltinModal.module.scss';

const cx = classNames.bind(style);

const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const HpsBuiltinModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { submit, cancel, workspaceId, trainId } = data;

  const [hpsName, setHpsName] = useState('');
  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });
  const [searchCount, setSearchCount] = useState('');
  const [instanceType, setInstanceType] = useState('');
  const [projectType, setProjectType] = useState('');
  const [huggingUrl, setHuggingUrl] = useState('');

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

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        project_id: Number(trainId),
        name: hpsName,
        dataset_id: selectDataset.id,
        dataset_data_path: selectData.fullPath,
        built_in_search_count: Number(searchCount),
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

      const { status } = response;

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('HPS_BUILT_IN_CREATE'));
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
      const {
        instance_info,
        project_type,
        huggingface_model_url = '',
      } = result;

      const { resource_name, instance_type, total } = instance_info;

      setInstanceType(instance_type);
      setGpuInfo({
        name: resource_name,
        max: total,
        used: '',
      });
      setProjectType(project_type);
      setHuggingUrl(huggingface_model_url);
    }
  };

  // hugging face일때만 빌트인일때는 다운로드
  const copyLink = async () => {
    const text = document.querySelector(`.${cx('url')}`).innerText; // Select the <p> tag's text

    copyToClipboard(text);
    toast.success('copy success');
  };

  const downloadReadme = async () => {
    const result = await downloadBlob({
      url: `options/built-in-model/readme/download?project_id=${trainId}`,
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

  const handleFooterMessage = () => {
    const validationMessages = [
      {
        condition: !hpsName || nameExg.test(hpsName),
        message: 'HPS 이름을 입력해 주세요',
      },
      { condition: !selectDataset.name, message: '데이터셋을 선택해 주세요' },
      { condition: !selectData.name, message: '데이터를 선택해 주세요' },
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
      { condition: !searchCount, message: '검색 입력 횟수를 입력해 주세요' },
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
    if (!hpsName) {
      validateCount += 1;
    }

    if (instanceType === 'GPU' && typeof gpuInfo.used !== 'number') {
      validateCount += 1;
    }
    if (!selectData.name || !selectDataset.name) {
      validateCount += 1;
    }
    if (
      gpuClusterSelectedOption === 0 &&
      gpuInfo.used > 1 &&
      gpuInfo.used !== selectedGpuList.length
    ) {
      validateCount += 1;
    }
    if (searchCount === '') {
      validateCount += 1;
    }
    if (validateCount !== 0) {
      setValidate(false);
      return;
    }
    setValidate(true);
  }, [
    gpuInfo,
    gpuClusterSelectedOption,
    selectedGpuList,
    instanceType,
    selectData,
    selectDataset,
    searchCount,
    hpsName,
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
    selectedGpuList,
    submitBtnCheck,
    gpuClusterSelectedOption,
    selectedGpuList,
    hpsName,
    selectData,
    selectDataset,
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
            name='hps'
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
          labelText={t('데이터셋 및 데이터')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <NewDatasetSearch
            workspaceId={workspaceId}
            selectData={selectData}
            setSelectedData={setSelectedData}
            selectDataset={selectDataset}
            setSelectedDataset={setSelectedDataset}
            // canFileSelect={false}
          />
          <div className={cx('message')}>
            {/* [안내] 데이터는 폴더만 선택 가능합니다. */}
          </div>
          <div className={cx('read-me-text')}>
            {projectType === 'built-in'
              ? '데이터 참고 README 파일'
              : '데이터 참고 페이지 URL'}
          </div>
          <div className={cx('read-me-download')}>
            <span className={cx('url')}>
              {projectType === 'built-in'
                ? '사용 데이터 참고.md'
                : `${huggingUrl}`}
            </span>
            <img
              className={cx('icon')}
              src={
                projectType === 'built-in'
                  ? DownloadIcon
                  : '/src/static/images/icon/copy-icon2.svg'
              }
              width={16}
              height={16}
              alt='icon'
              onClick={projectType === 'built-in' ? downloadReadme : copyLink}
            />
          </div>
        </InputBoxWithLabel>
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
          labelText={`검색 입력 횟수`}
          labelSize='large'
          disableErrorMsg
          labelDescText={'권장 횟수: 39'}
          labelDescStyle={{
            color: '#2D76F8',
            fontSize: '14px',
            marginLeft: '8px',
          }}
        >
          <InputText
            placeholder={t('검색 횟수를 입력하세요')}
            onChange={(e) => setSearchCount(e.target.value)}
            name='search'
            value={searchCount}
            // status={nameExg.test(hpsName) ? 'error' : 'default'}
            options={{ maxLength: 50 }}
            autoFocus={false}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default HpsBuiltinModal;
