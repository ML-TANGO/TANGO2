// Components
import { ButtonV2 } from '@jonathan/ui-react';

import CloseIcon from '@src/static/images/icon/00-ic-popup-close.svg';
import { Fragment, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useDeleteConfirmMessage from '@src/hooks/useDeleteConfirmMessage';

import classNames from 'classnames/bind';
// CSS module
import style from './ConfirmPopup.module.scss';

const cx = classNames.bind(style);

function ConfirmPopup({
  cancel,
  submit,
  title,
  content,
  notice,
  confirmMessage,
  close,
  testid,
  contentCustomStyle = {},
  isSubmitCloseFunc = true,
}) {
  const { t } = useTranslation();
  const [deleteConfirmMessageState, renderDeleteConfirmMessage] =
    useDeleteConfirmMessage(notice, confirmMessage);

  // ** ref 못씀 Button 컴포넌트 구조 잘못됐음 **
  const [isLoading, setIsLoading] = useState(false);
  const handleSubmit = async (e, submit, isSubmitCloseFunc, isLoading) => {
    if (submit.func) {
      setIsLoading(true);
      await submit.func(e);
    }

    setIsLoading(false);
    if (isSubmitCloseFunc) close();
  };

  const handleClose = () => {
    close();
    if (cancel.func) {
      cancel.func();
    }
  };

  useEffect(() => {
    const listener = (e) => {
      if (
        (deleteConfirmMessageState.isValid && e.key === 'Enter') ||
        e.key === 'NumpadEnter'
      ) {
        close();
        if (submit.func) {
          submit.func(e);
        }
      }
    };
    document.addEventListener('keydown', listener);
    return () => {
      document.removeEventListener('keydown', listener);
    };
  }, [close, deleteConfirmMessageState.isValid, submit]);

  return (
    <div className={cx('shadow')}>
      <div className={cx('popup')} data-testid={testid}>
        <div className={cx('popup-content')}>
          <img
            className={cx('popup-close-btn')}
            src={CloseIcon}
            alt='closeBtn'
            onClick={handleClose}
          />
          <h2 className={cx('title')}>{t(title)}</h2>
          <div className={cx('content')} style={contentCustomStyle}>
            {t(content, { name: confirmMessage })
              .split('\n\n')
              .map((text, i) => (
                <Fragment key={i}>
                  {text.split('\n').map((txt, idx) => {
                    return (
                      <Fragment key={idx}>
                        {txt}
                        <br />
                      </Fragment>
                    );
                  })}
                  {t(content).split('\n\n').length - 1 !== i && (
                    <div style={{ height: '12px' }} />
                  )}
                </Fragment>
              ))}
            {confirmMessage && (
              <div className={cx('confirm-message-input')}>
                {renderDeleteConfirmMessage()}
              </div>
            )}
          </div>
        </div>
        <div className={cx('popup-footer')}>
          {cancel && (
            <ButtonV2
              label={t(cancel.text)}
              type='clear'
              size='l'
              colorType='gray'
              onClick={handleClose}
            />
          )}
          {submit && (
            <ButtonV2
              size='l'
              colorType='red'
              label={t(submit.text)}
              onClick={(e) => {
                handleSubmit(e, submit, isSubmitCloseFunc, isLoading);
              }}
              isLoading={isLoading}
              disabled={!deleteConfirmMessageState.isValid}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default ConfirmPopup;
