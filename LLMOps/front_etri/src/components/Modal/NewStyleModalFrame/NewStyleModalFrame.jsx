// Components
import { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation, withTranslation } from 'react-i18next';
import { connect, useDispatch, useSelector } from 'react-redux';

import { Button, ButtonV2, Loading } from '@tango/ui-react';

// Actions
import { closeModal } from '@src/store/modules/modal';
// HOC
import EnterSubmitHOC from '@src/hoc/EnterSubmitHOC';

import classNames from 'classnames/bind';
// CSS module
import style from './NewStyleModalFrame.module.scss';

const cx = classNames.bind(style);

const hocParam = {};

const handleClose = async (type, cancel, dispatch) => {
  if (cancel) {
    if (cancel.func) {
      await cancel.func();
    }
    dispatch(closeModal(type));
  }
  dispatch(closeModal(type));
};

const NewStyleModalFrame = ({
  children,
  type,
  // ** 타이틀과 메세지 **
  title,
  footerMessage,
  // ** 버튼 **
  submit,
  apply,
  reset,
  cancel,
  validate,
  xCloseOnly = false,
  isResize = false,
  isMinimize = false,
  isLoading = false,
  // ** ?? **
  prev,
  next,
  totalStep,
  currentStep,
  customStyle,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const modalRef = useRef();

  const { modal } = useSelector((state) => state);
  const modalKeys = Object.keys(modal);

  const [modalHeight, setModalHeight] = useState(0);
  const [newCustomStyle, setNewCustomStyle] = useState(customStyle);
  const [loading, setLoading] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [isHideScreen, setIsHideScreen] = useState(false);
  const [hideScreenList, setHideScreenList] = useState([]);
  const [showScreenList, setShowScreenList] = useState([]);

  useEffect(() => {
    const keyboardHandler = (event) => {
      if (event.keyCode === 27) {
        const type = modalKeys.at(-1);
        dispatch(closeModal(type));
      }
    };
    document.addEventListener('keydown', keyboardHandler);
    return () => document.removeEventListener('keydown', keyboardHandler);
  }, [dispatch, modalKeys]);

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
            handleClose(type, cancel, dispatch);
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
        <div className={cx('modal-handler', isHideScreen && 'hidescreen')}>
          {title && !isHideScreen && (
            <div className={cx('modal-header')}>
              <div className={cx('header-title')}>{title}</div>
            </div>
          )}
          <div className={cx('modal-btn-cont', isHideScreen && 'hidescreen')}>
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
                onClick={() => {
                  if (xCloseOnly) {
                    dispatch(closeModal(type));
                  } else {
                    handleClose(type, cancel, dispatch);
                  }
                }}
              />
            )}
          </div>
        </div>
        {!isHideScreen ? (
          <>
            <div
              className={cx(
                'modal-content',
                isFullScreen && 'full',
                title && 'modal-header-content',
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
              {reset ? (
                <>
                  {cancel && (
                    <ButtonV2
                      label={t(reset.text)}
                      size='l'
                      type='clear'
                      colorType='red'
                      onClick={() => {
                        if (reset.func) {
                          reset.func();
                        }
                      }}
                      disabled={reset.isValidate}
                    />
                  )}
                </>
              ) : (
                <div className={cx('notice-message', validate && 'blue')}>
                  {footerMessage}
                </div>
              )}
              <div className={cx('right')}>
                {cancel && (
                  <ButtonV2
                    label={t(cancel.text)}
                    size='l'
                    type='clear'
                    colorType='gray'
                    onClick={() => {
                      handleClose(type, cancel, dispatch);
                    }}
                  />
                )}
                {apply && (
                  <ButtonV2
                    label={t(apply.text)}
                    size='l'
                    colorType='skyblue'
                    onClick={() => {
                      if (apply.func) {
                        apply.func();
                      }
                    }}
                    // disabled={apply.isValidate}
                  />
                )}
                {submit && (
                  <ButtonV2
                    label={t(submit.text)}
                    type='solid'
                    size='l'
                    isLoading={loading}
                    disabled={!validate}
                    onClick={(e) => hocParam.onSubmitEvent(e)}
                  />
                )}
              </div>
            </div>
          </>
        ) : (
          <div
            className={cx('modal-title', isHideScreen && 'hidescreen')}
            onClick={hocParam.onHandleClick}
          >
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
  connect(null, { closeModal })(EnterSubmitHOC(hocParam)(NewStyleModalFrame)),
);
