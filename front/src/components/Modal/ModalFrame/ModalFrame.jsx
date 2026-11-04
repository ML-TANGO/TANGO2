// Components
import { useCallback, useEffect, useRef, useState } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

import { Button, Loading } from '@jonathan/ui-react';

// Actions
import { closeModal } from '@src/store/modules/modal';
// HOC
import EnterSubmitHOC from '@src/hoc/EnterSubmitHOC';

import classNames from 'classnames/bind';
// CSS module
import style from './ModalFrame.module.scss';

const cx = classNames.bind(style);

const hocParam = {};

const ModalFrame = ({
  children,
  submit,
  submitBtnTestId,
  cancel,
  closeModal: close,
  type,
  validate,
  prev,
  next,
  nextValidate,
  totalStep,
  currentStep,
  customStyle,
  isResize = false,
  isMinimize = false,
  isLoading = false,
  title,
  headerTitle,
  footerMessage,
  isHideScreenFromProps,
  isClose,
  t,
}) => {
  const modalRef = useRef();
  const [modalHeight, setModalHeight] = useState(0);
  const [newCustomStyle, setNewCustomStyle] = useState(customStyle);
  const [loading, setLoading] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [isHideScreen, setIsHideScreen] = useState(false);
  const [hideScreenList, setHideScreenList] = useState([]);
  const [showScreenList, setShowScreenList] = useState([]);

  const keyboardHandler = useCallback(
    (event) => {
      if (event.keyCode === 27) {
        close(type);
      }
    },
    [close, type],
  );

  useEffect(() => {
    document.addEventListener('keydown', keyboardHandler);
  }, [keyboardHandler]);

  hocParam.onSubmitEvent = (e) => {
    if (e === undefined) {
      return null;
    }
    if (submit.func && !loading && validate) {
      setLoading(true);
      const response = submit.func();
      if (response) {
        response.then((result) => {
          if (result) {
            close(type);
          } else {
            setLoading(false);
          }
        });
      } else {
        setLoading(false);
      }
    }
  };

  hocParam.onPrevStep = () => {
    if (prev.func && !loading) {
      setLoading(true);
      prev.func();
      const response = prev.func();
      if (response) {
        response.then(() => {
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    }
  };

  hocParam.onNextStep = () => {
    if (next.func && !loading) {
      setLoading(true);
      next.func();
      const response = next.func();
      if (response) {
        response.then(() => {
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    }
  };

  hocParam.onFullScreen = () => {
    hocParam.onMaximizeScreen();
    setIsFullScreen(true);
  };

  hocParam.onDefaultScreen = () => {
    hocParam.onMaximizeScreen();
    setIsFullScreen(false);
  };

  hocParam.onMinimizeScreen = () => {
    setIsHideScreen(true);
    setIsFullScreen(false);
  };

  hocParam.onMaximizeScreen = () => {
    setIsHideScreen(false);
  };

  hocParam.onHandleClick = (event) => {
    if (event.detail === 2) {
      if (isHideScreen) {
        setIsHideScreen(false);
      }
    }
  };

  useEffect(() => {
    let newCustomStyle = { ...customStyle };
    const bodyEle = document.getElementsByTagName('body')[0];
    const hideScreenList = document.getElementsByClassName('hide-screen') || [];
    const showScreenList = document.getElementsByClassName('show-screen') || [];

    if (isHideScreen) {
      if (showScreenList.length > 0) {
        bodyEle.style.overflow = 'hidden';
      } else {
        bodyEle.style.overflow = 'auto';
      }

      let rightStyle = '';
      for (let i = 0; i < hideScreenList.length; i++) {
        if (modalRef.current === hideScreenList[i]) {
          rightStyle = `calc(48px + ${i * 300}px)`;
        }
      }
      newCustomStyle = {
        ...newCustomStyle,
        right: rightStyle,
        opacity: 1,
      };
    } else {
      if (modalHeight === 40) {
        const modalHeight = Number(modalRef.current.offsetHeight);
        setModalHeight(modalHeight);
      }
      bodyEle.style.overflow = 'hidden';
      newCustomStyle = {
        ...newCustomStyle,
        opacity: 1,
      };
    }

    setHideScreenList(hideScreenList);
    setShowScreenList(showScreenList);
    setNewCustomStyle(newCustomStyle);
  }, [
    isFullScreen,
    isHideScreen,
    customStyle,
    modalHeight,
    showScreenList,
    hideScreenList,
  ]);

  useEffect(() => {
    if (modalRef && !isLoading) {
      const modalHeight = Number(modalRef.current.offsetHeight);
      setModalHeight(modalHeight);
    }
  }, [children, isLoading]);

  useEffect(() => {
    // 워커 설정 - hide상태에서 버튼 클릭시 다시 모달 뜨게
    if (typeof isHideScreenFromProps === 'boolean') {
      setIsHideScreen(false);
    }
  }, [isHideScreenFromProps]);

  return (
    <div id={title} className={cx('shadow', isHideScreen && 'hide')}>
      <div
        className={`${cx(
          'modal',
          title,
          isHideScreen && 'hide',
          isFullScreen && 'full',
        )} ${isHideScreen ? 'hide-screen' : 'show-screen'} ${
          isFullScreen && 'full-screen'
        }`}
        style={newCustomStyle}
        ref={modalRef}
      >
        <div className={cx('modal-handler')}>
          <>
            {isMinimize &&
              (isHideScreen ? (
                <img
                  title={t('maximizeScreen.label')}
                  src='/images/icon/ic-maximize-modal.svg'
                  alt='maximize'
                  onClick={hocParam.onMaximizeScreen}
                />
              ) : (
                <img
                  title={t('minimizeScreen.label')}
                  src='/images/icon/ic-minimize-modal.svg'
                  alt='minimize'
                  onClick={hocParam.onMinimizeScreen}
                />
              ))}
            {isResize &&
              !isHideScreen &&
              (isFullScreen ? (
                <img
                  title={t('defaultScreen.label')}
                  src='/images/icon/ic-default-size-modal.svg'
                  alt='default'
                  onClick={hocParam.onDefaultScreen}
                />
              ) : (
                <img
                  title={t('fullScreen.label')}
                  src='/images/icon/ic-full-size-modal.svg'
                  alt='fullscreen'
                  onClick={hocParam.onFullScreen}
                />
              ))}
            {isMinimize && (
              <img
                className={cx('close-icon')}
                title={`${t('close.label')} (Esc)`}
                src='/images/icon/ic-close-modal.svg'
                alt='close'
                onClick={() => close(type)}
              />
            )}
            {isClose && (
              <img
                className={cx('close-icon')}
                title={`${t('close.label')} (Esc)`}
                src='/images/icon/ic-close-modal.svg'
                alt='close'
                onClick={() => close(type)}
              />
            )}
          </>
        </div>
        {headerTitle && !isHideScreen && (
          <div className={cx('modal-header')}>
            <div className={cx('header-title')}>{headerTitle}</div>
          </div>
        )}
        {!isHideScreen ? (
          <>
            <div
              className={cx(
                'modal-content',
                isFullScreen && 'full',
                headerTitle && 'modal-header-content',
              )}
            >
              {children}
            </div>
            <div className={cx('modal-footer')}>
              {(prev || next) && (
                <div className={cx('left')}>
                  {prev && (
                    <Button
                      type='primary'
                      size='medium'
                      disabled={Number(currentStep) === 1}
                      onClick={hocParam.onPrevStep}
                    >
                      {t(prev.text)}
                    </Button>
                  )}
                  {next && (
                    <Button
                      type='primary'
                      size='medium'
                      disabled={totalStep === currentStep} // 다음 버튼 활성화 여부 체크 안함
                      // disabled={totalStep === currentStep || !nextValidate} // 다음 버튼 활성화 여부 체크 함
                      onClick={hocParam.onNextStep}
                    >
                      {t(next.text)}
                    </Button>
                  )}
                </div>
              )}
              <div className={cx('notice-message')}>{footerMessage}</div>

              <div className={cx('right')}>
                {cancel && (
                  <Button
                    type='none-border'
                    size='medium'
                    onClick={() => {
                      close(type);
                      if (cancel.func) {
                        cancel.func();
                      }
                    }}
                  >
                    {t(cancel.text)}
                  </Button>
                )}
                {submit && (
                  <Button
                    type='primary'
                    size='medium'
                    loading={loading}
                    disabled={!validate}
                    onClick={(e) => {
                      hocParam.onSubmitEvent(e);
                      close(type);
                    }}
                    data-testid={submitBtnTestId}
                  >
                    {t(submit.text)}
                  </Button>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className={cx('modal-title')} onClick={hocParam.onHandleClick}>
            {title}
          </div>
        )}
        {isLoading && (
          <div className={cx('loading')}>
            <Loading type='circle' size='large' />
          </div>
        )}
      </div>
    </div>
  );
};

export default withTranslation()(
  connect(null, { closeModal })(EnterSubmitHOC(hocParam)(ModalFrame)),
);
