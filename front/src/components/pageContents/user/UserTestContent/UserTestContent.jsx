import { Fragment, useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import OutputImageRealtime from './OutputImageRealtime/OutputImageRealtime';
import UserTestContentHeader from './UserTestContentHeader/UserTestContentHeader';
import UserTestContentInputBox from './UserTestContentInputBox/UserTestContentInputBox';
import UserTestContentOutputBox from './UserTestContentOutputBox/UserTestContentOutputBox';
import UserTestContentRequestBox from './UserTestContentRequestBox/UserTestContentRequestBox';

import { scrollTo } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './UserTestContent.module.scss';

const cx = classNames.bind(style);

function UserTestContent({
  serviceData: info,
  inputText,
  textInputHandler,
  selectedImage,
  selectedImageSrc,
  fileInputHandler,
  selectedVideo,
  selectedVideoSrc,
  selectedAudio,
  selectedAudioSrc,
  selectedCSV,
  selectedCSVSrc,
  selectedCanvas,
  selectedCanvasSrc,
  canvasInputHandler,
  canvasWidth,
  canvasHeight,
  canvasRef,
  runAnalysis,
  outputObj,
  outputStatus,
  loading,
  goBack,
  mouseMoveHandler,
  mouseDownHandler,
  mouseUpHandler,
}) {
  const { t } = useTranslation();
  const contentRef = useRef(null);
  const {
    name,
    api_address: apiAddress,
    data_input_form_list: inputFormList,
  } = info;
  const [outputTypeList, setOutputTypeList] = useState([]);
  const [apiUrl, setApiUrl] = useState(apiAddress);

  const inputBoxProps = {
    inputFormList,
    textInputHandler,
    inputText,
    fileInputHandler,
    selectedImage,
    selectedImageSrc,
    selectedVideo,
    selectedVideoSrc,
    selectedAudio,
    selectedAudioSrc,
    selectedCSV,
    selectedCSVSrc,
    canvasInputHandler,
    selectedCanvas,
    selectedCanvasSrc,
    canvasRef,
    canvasWidth,
    canvasHeight,
    mouseMoveHandler,
    mouseDownHandler,
    mouseUpHandler,
    apiUrl,
    info,
  };

  const outputProps = {
    outputObj,
    outputTypeList,
    outputStatus,
  };

  const requestBoxProps = {
    info,
    setApiUrl,
    apiUrl,
    runAnalysis,
    loading,
  };

  useEffect(() => {
    setApiUrl(apiAddress);
  }, [apiAddress]);

  useEffect(() => {
    if (outputObj) {
      setOutputTypeList(Object.keys(outputObj));
    } else {
      setOutputTypeList([]);
    }
  }, [outputObj]);

  useEffect(() => {
    if (outputTypeList.length > 0) {
      const ele = contentRef.current?.parentElement?.parentElement;
      scrollTo(ele, ele.scrollHeight, 600, false);
    }
  }, [outputTypeList]);

  return (
    <div id='UserTestContent' className={cx('content')} ref={contentRef}>
      {/* <PageTitle>{t('Simulation')}</PageTitle> */}
      <div className={cx('back-to-list')} onClick={() => goBack()}>
        <img
          className={cx('back-btn-image')}
          src='/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='<'
        />
        <span className={cx('back-btn-label')}>
          {t('test.backToList.label')}
        </span>
      </div>
      {/* 지능형반도체 데모 대응 */}
      {name === 'judgement-yolov6' || name === 'yolov6-judgement' ? (
        <div className={cx('realtime-box')}>
          <OutputImageRealtime />
        </div>
      ) : (
        <Fragment>
          <UserTestContentHeader info={info} />
          <div className={cx('test-box')}>
            <UserTestContentRequestBox
              {...requestBoxProps}
              {...inputBoxProps}
            />
            <UserTestContentInputBox {...inputBoxProps} />
            <UserTestContentOutputBox {...outputProps} />
          </div>
        </Fragment>
      )}
    </div>
  );
}

export default UserTestContent;
