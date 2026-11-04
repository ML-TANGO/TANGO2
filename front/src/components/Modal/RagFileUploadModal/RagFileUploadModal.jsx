import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { handleSetRagState } from '@src/store/modules/llmRag';
// Actions
import { closeModal } from '@src/store/modules/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';
import RagFile from './RagFile';

import classNames from 'classnames/bind';
import style from './RagFileUploadModal.module.scss';

const cx = classNames.bind(style);

// 문서 업로드,  이전 파일 이름과 비교해서 업로드
const uplopadDocList = (files, dispatch, currentSetting) => {
  const prevDocList = currentSetting.doc_list || [];
  const newFiles = files.filter(
    (newFile) =>
      !prevDocList.some((existingFile) => existingFile.name === newFile.name),
  );
  const updatedDocList = [...prevDocList, ...newFiles];
  dispatch(
    handleSetRagState({
      type: 'setting',
      setting: {
        ...currentSetting,
        doc_list: updatedDocList,
      },
    }),
  );
};

const isCalFooterMessage = (file) => {
  if (!file || file.length === 0) return 'llm.rag.upload.warn.message';

  return null;
};

const RagFileUploadModal = ({ data, type }) => {
  const dispatch = useDispatch();

  const { setting } = useSelector((state) => state.llmRag, shallowEqual);

  const [file, setFile] = useState([]);
  const [loading, setLoading] = useState(false);

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

  // 파일 이름 _ 변경
  const replaceFileName = (str) => {
    return str.replace(/[ :?*<>#$%&()/|"\\]/g, '_');
  };

  const footerMessage = isCalFooterMessage(file);

  return (
    <NewStyleModalFrame
      title={t('fileUpload.label')}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: () => {
          //
          // uploadConfiguration();
          uplopadDocList(file, dispatch, setting);
          dispatch(closeModal('RAG_FILE_UPLOAD'));
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
          labelText={`RAG ${t('file.label')}`}
          // optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
          className={cx('label')}
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
          <RagFile
            onUpload={handleFileUpload}
            disabled={false}
            buttonLabel={t('docs.select.label')}
            customStyle={{ marginTop: '24px' }}
            multiple={true}
          />
          <div className={cx('message')}>{t('llm.rag.upload.message')}</div>
          {file.length > 0 && (
            <>
              <div className={cx('border')} />
              <div className={cx('file-wrapper')}>
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
              </div>
            </>
          )}
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default RagFileUploadModal;
