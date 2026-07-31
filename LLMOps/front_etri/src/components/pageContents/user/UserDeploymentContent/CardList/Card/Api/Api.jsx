import { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

// i18n
import { useTranslation } from 'react-i18next';

// Utils
import { CopyToClipboard } from 'react-copy-to-clipboard';

// Components
import { toast } from '@src/components/Toast';

// CSS Module
import classNames from 'classnames/bind';
import style from './Api.module.scss';
const cx = classNames.bind(style);

function Api({ apiAddress }) {
  const { t } = useTranslation();
  const popup = useRef(null);
  const [isOpen, setIsOpen] = useState(false);

  const onCopy = () => {
    toast.success(t('copyToClipboard.success.message'));
  };

  const popupHandler = () => {
    setIsOpen(!isOpen);
  };

  const handleClick = (e) => {
    // PopupMenu를 제외한 요소 클릭 시 popupHandler 이벤트 실행
    if (
      popup.current &&
      !ReactDOM.findDOMNode(popup.current).contains(e.target)
    ) {
      setIsOpen(false);
    }
  };

  // 클릭 이벤트 관련 라이프 사이클
  useEffect(() => {
    // PopupMenu 컴포넌트가 마운트 될 때 documemnt에 팝업 닫기 이벤트 추가
    document.addEventListener('click', handleClick, false);
    return () => {
      // 현재 컴포넌트가 언마운트 되면 handleClick 이벤트 제거
      document.removeEventListener('click', handleClick, false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [popup]);

  return (
    <div className={cx('api-info')} ref={popup}>
      <button
        className={cx('btn', !apiAddress && 'readonly', isOpen && 'active')}
        onClick={popupHandler}
      >
        API
      </button>
      {isOpen && apiAddress && (
        <div className={cx('popup')}>
          <label className={cx('label')}>{t('apiAddress.label')}</label>
          <div className={cx('value-box')}>
            <span className={cx('value', 'api')} title={apiAddress}>
              {apiAddress || '-'}
            </span>
            {apiAddress && (
              <CopyToClipboard text={apiAddress} onCopy={onCopy}>
                <button
                  className={cx('copy-btn')}
                  title={t('copyToClipboard.message')}
                ></button>
              </CopyToClipboard>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Api;
