import { loadModalComponent } from '@src/modal';
import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import LLMFile from '@src/components/atoms/LLMFile';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './ConfigurationDataUploadModal.module.scss';

const cx = classNames.bind(style);

const isCalFooterMessage = (file) => {
  if (!file || file.length === 0) return 'select.file.message';

  return null;
};

const ConfigurationDataUploadModal = ({ data, type }) => {
  const { workspaceId, refresh, modelId } = data;
  const dispatch = useDispatch();

  const [loadType, setLoadType] = useState(1); // 1 , 0

  const [file, setFile] = useState([]);
  const [loading, setLoading] = useState(false);

  const [validate, setValidate] = useState(false);

  const fileInput = useRef(null);
  const triggerInputFile = () => fileInput.current.click();

  // 모달 Radio
  const radioBtnHandler = (value) => {
    const radioType = parseInt(value, 10);
    setLoadType(radioType);
    if (radioType === 0) {
    }
  };

  const handleRemoveFile = (indexToRemove) => {
    setFile((prevFiles) =>
      prevFiles.filter((_, index) => index !== indexToRemove),
    );
  };

  const { t } = useTranslation();

  const handleFileUpload = (files) => {
    // 파일 리스트 처리 예제
    console.log('Selected files:', files);
    setFile(files);
  };

  const uploadConfiguration = async () => {
    const formData = new FormData();
    setLoading(true);
    formData.append('file', file[0]);
    formData.append('model_id', modelId);

    const response = await callApi({
      url: `models/option/upload-configuration`,
      method: 'post',
      body: formData,
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      refresh();
      dispatch(closeModal('CONFIGURATION_DATA_UPLOAD'));
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  // 파일 이름 _ 변경
  const replaceFileName = (str) => {
    return str.replace(/[ :?*<>#$%&()/|"\\]/g, '_');
  };

  const footerMessage = isCalFooterMessage(file);

  useEffect(() => {
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
  }, []);

  return (
    <NewStyleModalFrame
      title={`Configuration ${t('file.select.label')}`}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: () => {
          //
          uploadConfiguration();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={file.length !== 0}
      isResize={true}
      isMinimize={true}
      isLoading={loading}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`Configuration ${t('file.label')}`}
          // optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          {/* <div className={cx('radio')}>
            <Radio
              options={accessTypeOptions}
              onChange={(e) => {
                radioBtnHandler(e.currentTarget.value);
              }}
              selectedValue={loadType}
              name='accessType'
              t={t}
            />
          </div> */}
          <LLMFile
            onUpload={handleFileUpload}
            disabled={false}
            buttonLabel={t('file.select.label')}
            customStyle={{ marginTop: '24px' }}
            message='finetuning.upload.warn.message'
          />
          <div className={cx('message')}>{t('finetuning.upload.message')}</div>
          {file.length > 0 && (
            <>
              <div className={cx('border')}></div>
              {file.map((fileItem, index) => (
                <div key={index} className={cx('file-item')}>
                  <span>{replaceFileName(fileItem.name ?? '-')}</span>

                  <img
                    src='/images/icon/close.svg'
                    alt='X'
                    onClick={() => handleRemoveFile(index)}
                  />
                </div>
              ))}
            </>
          )}
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default ConfigurationDataUploadModal;
