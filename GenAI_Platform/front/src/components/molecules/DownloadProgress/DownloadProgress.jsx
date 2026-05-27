import { useState, useRef, useEffect } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { Button } from '@jonathan/ui-react';

// Actions
import { closeDownloadProgress } from '@src/store/modules/download';

// CSS Module
import classNames from 'classnames/bind';
import style from './DownloadProgress.module.scss';
const cx = classNames.bind(style);

function DownloadProgress({ downloadProgress }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const popupRef = useRef(null);

  // State
  const [progress, setProgress] = useState(0);
  const [fileTitle, setFileTitle] = useState('Loading...');

  // LifeCycle
  useEffect(() => {
    window.onbeforeunload = function (e) {
      var dialogText = 'Dialog text here';
      e.returnValue = dialogText;
      return dialogText;
    };

    const { current: popupEle } = popupRef;
    // 애니메이션
    setTimeout(() => {
      if (popupEle) {
        popupEle.style.bottom = '0px';
        popupEle.style.opacity = '1';
      }
    }, 1);
    return () => {
      window.onbeforeunload = null;
      if (popupEle) {
        popupEle.style.top = '0';
        popupEle.style.opacity = '0';
      }
    };
  }, []);

  const titleHandler = (title) => {
    if (title) {
      if (title?.length > 1) {
        const newTitle = `${title[0]} 외 ${title?.length - 1}개`;
        setFileTitle(newTitle);
      } else {
        const newTitle = title[0];
        setFileTitle(newTitle);
      }
    }
  };

  useEffect(() => {
    setProgress(downloadProgress[0]);
    titleHandler(downloadProgress[1]);
  }, [downloadProgress]);

  return (
    <div className={cx('download-progress-status')} ref={popupRef}>
      <div className={cx('top')}>
        <div className={cx('title')}>{fileTitle}</div>
        <Button
          type='secondary'
          size='x-small'
          disabled={downloadProgress[0] < 100}
          onClick={() => {
            dispatch(closeDownloadProgress());
          }}
        >
          {t('close.label')}
        </Button>
      </div>
      <div className={cx('progress-box')}>
        <div className={cx('progress-item')}>
          <div className={cx('progress-info')}>
            <span className={cx('rate')}>{progress}%</span>
            <span className={cx('name')}>download</span>
          </div>
          <div className={cx('progress')}>
            <div className={cx('bar')} style={{ width: `${progress}%` }}></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DownloadProgress;
