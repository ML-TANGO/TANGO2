import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './DatasetBuiltinJobCreate.module.scss';

const cx = classNames.bind(style);

const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const DATA_MESSAGE = {
  Text: '확장자 ".txt" 데이터 파일만 선택 가능합니다.',
  Image:
    '폴더 내 확장자 ".png", ".jpeg", ".jpg" 이미지 파일에 대해 전처리를 실행합니다.',
  Tabular: '확장자 ".csv", ".xlsx" 데이터 파일만 선택 가능합니다.',
  Audio: '확장자 ".wav", ".mp3", ".flac" 데이터 파일만 선택 가능합니다.',
  Video: '확장자 ".mp4", ".avi", ".mov" 데이터 파일만 선택 가능합니다.',
};

const DatasetBuiltinJobCreate = ({ data, type }) => {
  const { submit, cancel, preprocessing_id, workspaceId } = data;

  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [jobName, setJobName] = useState('');
  const [builtInParams, setBuiltInParams] = useState([]);
  const [validate, setValidate] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');
  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });
  const [builtInDataType, setBuiltInDataType] = useState('');

  const fetchOptionList = async () => {
    const response = await callApi({
      url: `options/preprocessing/job?preprocessing_id=${preprocessing_id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { built_in_params, built_in_data_type } = result;
      const params = built_in_params.map((v) => ({ label: v, value: '' }));
      setBuiltInParams(params);
      setBuiltInDataType(built_in_data_type);
    }
  };

  const handleParams = (params, value) => {
    setBuiltInParams((prevParams) =>
      prevParams.map((param) =>
        param.label === params ? { ...param, value } : param,
      ),
    );
  };

  const handleDataMessage = (dataType) => {
    if (!DATA_MESSAGE[dataType]) {
      return '파일 또는 폴더를 선택하여 데이터를 전처리할 수 있습니다.\n처리 가능한 파일 유형은 사용 중인 전처리기에 따라 다를 수 있습니다.';
    }

    return DATA_MESSAGE[dataType];
  };

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        preprocessing_id: Number(preprocessing_id),
        job_name: jobName,
        dataset_id: selectDataset.id,
        dataset_data_path: selectData.fullPath,
        built_in_param: {},
      };

      builtInParams.forEach(({ label, value }) => {
        body.built_in_param[label] = value;
      });

      const response = await callApi({
        url: 'preprocessing/jobs/run',
        method: 'post',
        body,
      });
      const { status } = response;

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('DATASET_BUILT_IN_JOB_CREATE'));
      }
    },
  };

  const handleFooterMessage = () => {
    const validationMessages = [
      {
        condition: !jobName || nameExg.test(jobName),
        message: 'JOB 이름을 입력해 주세요',
      },
      { condition: !selectDataset.id, message: '데이터셋을 선택해주세요' },
      { condition: !selectData.name, message: '데이터를 선택해주세요' },
      {
        condition: !builtInParams.every((v) => v.value),
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

  useEffect(() => {
    fetchOptionList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    handleFooterMessage();

    const isParamsValid = builtInParams.every((v) => v.value);
    if (!jobName || !isParamsValid || !selectData.name || !selectDataset.id) {
      setValidate(false);
      return;
    }

    setValidate(true);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobName, builtInParams, selectData, selectDataset]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={`JOB ${t('create.label')}`}
      customStyle={{ maxHeight: '750px' }}
      validate={validate}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`JOB ${t('name.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('jobName.placeholder')}
            onChange={(e) => setJobName(e.target.value)}
            name='workspace'
            value={jobName}
            status={nameExg.test(jobName) ? 'error' : 'default'}
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
          />
          <div className={cx('message')}>
            [안내] {handleDataMessage(builtInDataType)}
          </div>
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('파라미터 설정')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
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
                      // status={!validate ? 'error' : 'default'}
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
};

export default DatasetBuiltinJobCreate;
