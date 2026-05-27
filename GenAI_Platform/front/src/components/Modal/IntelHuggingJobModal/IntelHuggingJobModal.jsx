import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputNumber, InputText } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';

import { closeModal } from '@src/store/modules/modal';
import { callApi, downloadBlob, STATUS_SUCCESS } from '@src/network';

import NameInput from '../DataCollectModal/NameInput/NameInput';
import useNameInput from '../DataCollectModal/NameInput/useNameInput';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { copyToClipboardWithToast } from '@src/utils';

import classNames from 'classnames/bind';
import style from './IntelHuggingJobModal.module.scss';

const cx = classNames.bind(style);

const calFooterMessage = (name, selectDataset, selectData, builtInParams) => {
  if (!name) return 'JOB 이름을 입력해 주세요.';
  if (!selectDataset.id) return '데이터셋을 선택해 주세요.';
  if (!selectData.name) return '데이터를 선택해 주세요.';

  const emptyBuiltinParams = builtInParams.find((item) => item.value === '');
  if (emptyBuiltinParams) return '파라미터 값을 입력해 주세요.';
  return '';
};

export default function IntelHuggingJobModal({ data, type }) {
  const { t } = useTranslation();
  const { workspaceId, tid, gpuCount, gpuModel } = data;
  const dispatch = useDispatch();

  // ** [API 이름] **
  const labelText = useMemo(() => {
    return t('jobName.label');
  }, [t]);
  const placeholder = useMemo(() => {
    return t('jobName.placeholder');
  }, [t]);
  const { name, isError, handleName } = useNameInput();

  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });
  const [builtInParams, setBuiltInParams] = useState([]);
  const [builtInType, setBuiltInType] = useState('');

  const [clusterInfo, setClusterInfo] = useState([]);

  const [gpuValue, setGpuValue] = useState(null);
  const handleGpuValue = useCallback((e) => {
    setGpuValue(+e.target.value);
  }, []);

  const handleCopy = useCallback(() => {
    const text = document.querySelector(`.${cx('url')}`).innerText; // Select the <p> tag's text
    copyToClipboardWithToast(text);
  }, []);

  const handleParams = (params, value) => {
    setBuiltInParams((prevParams) =>
      prevParams.map((param) =>
        param.label === params ? { ...param, value } : param,
      ),
    );
  };

  const downloadReadme = async () => {
    console.log('tid : ', tid);
    const result = await downloadBlob({
      url: `options/built-in-model/readme/download?project_id=${tid}`,
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

  const footerMessage = calFooterMessage(
    name,
    selectDataset,
    selectData,
    builtInParams,
  );

  const submit = {
    text: t('create.label'),
    func: async () => {
      const copyList = builtInParams.slice();
      const transformParams = copyList.reduce((acc, item) => {
        acc[item.label] = item.value;
        return acc;
      }, {});

      const { status, message } = await callApi({
        url: 'projects/trainings',
        method: 'post',
        body: {
          project_id: +tid,
          training_name: name,
          dataset_id: selectDataset.id,
          dataset_data_path: selectData.fullPath,
          gpu_count: gpuValue,
          gpu_cluster_auto: gpuValue > 1 ? true : false,
          gpu_auto_select:
            gpuValue > 1
              ? {
                  gpu_count: clusterInfo[0].gpu_count,
                  status: clusterInfo[0].status,
                  server: clusterInfo[0].server,
                }
              : {},
          gpu_cluster_case_old: gpuValue > 1 ? clusterInfo : [],
          built_in_param: transformParams,
        },
      });
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        dispatch(closeModal(type));
      }
    },
  };

  const cancel = {
    text: t('cancel.label'),
    func: () => {},
  };

  const [huggingUrl, setHuggingUrl] = useState('');
  useEffect(() => {
    const getbuiltInParmas = async () => {
      const { result, message, status } = await callApi({
        url: `options/project/job?project_id=${tid}`,
        method: 'get',
      });

      if (status === STATUS_SUCCESS) {
        if (result.built_in_params) {
          const transformList = result.built_in_params.map((str) => {
            return {
              label: str,
              value: null,
            };
          });
          setBuiltInParams(transformList);
        }

        if (result.huggingface_model_url) {
          setHuggingUrl(result.huggingface_model_url);
        }

        setBuiltInType(result.project_type);
      } else {
        toast.error(message);
      }
    };
    getbuiltInParmas();
  }, [tid]);

  useEffect(() => {
    if (gpuValue < 2) return;
    const getGpuClusterAutoInfo = async () => {
      const { result, message, status } = await callApi({
        url: '/projects/gpu-cluster-auto',
        params: {
          project_id: tid,
          gpu_count: gpuValue,
        },
      });
      if (status === STATUS_SUCCESS) {
        setClusterInfo(result);
      } else {
        toast.error(message);
      }
    };
    getGpuClusterAutoInfo();
  }, [gpuValue, tid]);

  return (
    <NewStyleModalFrame
      submit={submit}
      cancel={cancel}
      type={type}
      validate={!footerMessage}
      isResize={true}
      isMinimize={true}
      title={t('jobCreate.label')}
      footerMessage={footerMessage}
      customStyle={{
        width: '664px',
      }}
    >
      <NameInput
        value={name}
        labelText={labelText}
        placeholder={placeholder}
        isError={isError}
        handleName={handleName}
      />
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
      {builtInType === 'huggingface' && (
        <>
          <p className={cx('notice-message')}>
            [안내] 데이터는 파일만 선택 가능합니다.
          </p>
          <p className={cx('data-url-p')}>데이터 참고 페이지 URL</p>
          <div className={cx('copy-cont')}>
            <p className={cx('url')}>{huggingUrl}</p>
            <button className={cx('copy-btn')} onClick={handleCopy}>
              <img
                className={cx('copy-img')}
                src='/src/static/images/icon/copy-icon2.svg'
                alt='copy-icon'
              />
            </button>
          </div>
        </>
      )}
      {builtInType === 'built-in' && (
        <>
          <p className={cx('notice-message')}>
            [안내] 데이터는 파일만 선택 가능합니다.
          </p>
          <p className={cx('data-url-p')}>데이터 참고 README 파일</p>
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
        </>
      )}
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('gpuAllocation.label')}
          labelSize='large'
          disableErrorMsg
          optionalText={gpuModel}
          optionalSize='large'
          style={{ marginBottom: '32px' }}
        >
          <InputNumber
            placeholder={`사용 가능: ${gpuCount}`}
            value={gpuValue}
            onChange={handleGpuValue}
            customStyle={{ fontSize: '14px' }}
            max={gpuCount}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      {gpuValue > 1 && (
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('gpuClusterCategory.label')}
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              options={[
                { label: '1-GPU 서버 x2 [추천] 즉시 학습 시작 가능', value: 0 },
              ]}
              customStyle={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
              onChange={(e) => {}}
              value={0}
              isLabelColor={true}
            />
          </InputBoxWithLabel>
        </div>
      )}
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('파라미터 설정')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
          style={{ marginTop: '32px' }}
        >
          <div className={cx('parameter-box')}>
            <div className={cx('param-header')}>
              <div className={cx('desc-text')}>파라미터 항목명</div>
              <div className={cx('desc-text')}>파라미터 값</div>
            </div>
            <div className={cx('param-list')}>
              {builtInParams.length === 0 && (
                <div className={cx('empty-info')}>
                  데이터를 추가하시면 해당 데이터 대한 파라미터가 표시됩니다.
                </div>
              )}
              {builtInParams.map(({ label, value }, index) => (
                <div className={cx('list-box')} key={index}>
                  <div className={cx('label')}>{label}</div>
                  <div className={cx('input')}>
                    <InputText
                      placeholder={t('파라미터 값을 입력하세요')}
                      onChange={(e) => handleParams(label, e.target.value)}
                      name='workspace'
                      value={value}
                      status={
                        builtInParams[index].value === '' ? 'error' : 'default'
                      }
                      options={{ maxLength: 50 }}
                      // autoFocus={false}
                      customStyle={{ fontSize: '13px' }}
                      disableLeftIcon
                      disableClearBtn
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
}
