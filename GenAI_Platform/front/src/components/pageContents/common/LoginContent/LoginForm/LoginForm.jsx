import queryString from 'query-string';
import { useEffect, useReducer } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { dataScopeLoginRequest, loginRequest } from '@src/store/modules/auth';
import { closeHeaderPopup } from '@src/store/modules/headerOptions';
import { closeModal, openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './LoginForm.module.scss';

const cx = classNames.bind(style);

const CUSTOM_COLOR = import.meta.env.VITE_REACT_APP_PRIMARY_COLOR;
// * 대구 TP에서 사용하는 dataScope로 이동하는 boolean 값입니다.
const isDataScope = import.meta.env.VITE_REACT_APP_IS_DATASCOPE;

const isOtp = import.meta.env.VITE_REACT_APP_IS_OTP;
const { id: loginId } = queryString.parse(window.location.search);

const formReducer = (state, action) => {
  switch (action.type) {
    case 'INPUT_CHANGE':
    case 'DOUBLE_CLICK':
    case 'ISLOGIN':
      return {
        ...state,
        [action.field]: action.value,
      };
    case 'PASSWORDSHOWN':
      return {
        ...state,
        [action.field]: !action.value,
      };
    default:
      return state;
  }
};

function LoginForm() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { resMessage: error } = useSelector(({ auth }) => auth);

  // * 공지할 내용 있으면 여기에 적기 (1줄당 55자 이내로 작성)
  const notice = '';
  const initialState = {
    userName: '',
    password: '',
    otp: '',
    isClick: false,
    isLogined: false,
    passwordShown: false,
  };
  const [formState, reducerDispatch] = useReducer(formReducer, initialState);
  const { userName, password, otp, isClick, isLogined, passwordShown } =
    formState;

  useEffect(() => {
    dispatch(closeHeaderPopup());
  }, [dispatch]);

  const handleInputChange = (field) => (e) => {
    reducerDispatch({
      type: 'INPUT_CHANGE',
      field,
      value: e.target.value,
    });
  };

  // * 중복 클릭 방지
  const handleDoubleClick = (value) => {
    reducerDispatch({
      type: 'DOUBLE_CLICK',
      field: 'isClick',
      value: value,
    });
  };

  // * 로그인 유무 체크
  const handleIsLogin = (value) => {
    reducerDispatch({
      type: 'ISLOGIN',
      field: 'isLogined',
      value: value,
    });
  };

  // * FlightBase Login
  const onLogin = (e) => {
    e.preventDefault();
    if (isClick) return; // 중복 클릭 방지
    handleDoubleClick(true);

    const reqParam = {
      user_name: userName,
      password,
      otp,
    };

    const res = dispatch(loginRequest(reqParam));
    if (res) {
      handleDoubleClick(false);
      handleIsLogin(res.logined);
    }
  };

  const signupModalOpen = (e) => {
    e.preventDefault();
    dispatch(
      openModal({
        modalType: 'SIGNUP_MODAL',
        modalData: {
          submit: {
            text: 'update.label',
            func: () => {
              dispatch(closeModal('SIGNUP_MODAL'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          t,
        },
      }),
    );
  };

  // * DataScope Login
  const dataScopeLogin = async (e) => {
    e.preventDefault();
    await dataScopeLoginRequest(userName, password, dispatch);
    handleIsLogin(false);
  };

  // * enter 눌렀을 때 조건 함수
  const onKeyDownEnterFunc = (e) => {
    if (e.key === 'Enter' && !isLogined && !isDataScope) onLogin(e);
  };

  return (
    <form className={cx('login-form')}>
      <div className={cx('login-inner-box')}>
        <div
          className={cx('welcome')}
          style={CUSTOM_COLOR && { color: CUSTOM_COLOR }}
        >
          {t('welcome.message')}
        </div>
        {notice !== '' ? (
          <div className={cx('notice-box')}>
            <div className={cx('notice')}>
              <pre>{notice}</pre>
            </div>
          </div>
        ) : (
          <div className={cx('margin-box')}></div>
        )}
        <div className={cx('user-input')}>
          <i className={cx('user-ico')} />
          <input
            type='text'
            className={cx('login-input')}
            name='user_name'
            value={userName}
            placeholder='ID'
            onChange={handleInputChange('userName')}
            onKeyDown={(e) => onKeyDownEnterFunc(e)}
            data-testid='user-id'
            readOnly={loginId}
          />
        </div>
        <div className={cx('password-input')}>
          <i className={cx('password-ico')} />
          <input
            type={passwordShown ? 'text' : 'password'}
            autoComplete='off'
            className={cx('login-input')}
            name='password'
            value={password}
            placeholder={t('password.label')}
            onChange={handleInputChange('password')}
            onKeyDown={(e) => onKeyDownEnterFunc(e)}
            data-testid='user-pwd'
          />
          <button
            type='button'
            className={cx('show-hide-btn')}
            onClick={() =>
              reducerDispatch({
                type: 'PASSWORDSHOWN',
                field: 'passwordShown',
                value: passwordShown,
              })
            }
          >
            <img
              src={`/images/icon/00-ic-info-eye${
                passwordShown ? '' : '-off'
              }.svg`}
              alt='show'
            />
          </button>
        </div>
        {isOtp && (
          <div className={cx('password-input')}>
            <i className={cx('password-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='otp'
              value={otp}
              placeholder='OTP'
              onChange={handleInputChange('otp')}
              onKeyDown={(e) => onKeyDownEnterFunc(e)}
            />
          </div>
        )}
        <div className={cx('message')}>
          {Array.isArray(error)
            ? error.map((te, idx) => (
                <span key={idx}>
                  {te}
                  {error.length - 1 !== idx && <br />}
                </span>
              ))
            : error}
        </div>
        <div className={cx('btn-row-box')}>
          <button
            type='submit-dataScope'
            className={cx(
              'btn',
              'solid-color',
              'signup-btn',
              isDataScope && 'half-btn',
              'datascope',
            )}
            style={CUSTOM_COLOR && { backgroundColor: CUSTOM_COLOR }}
            onClick={(e) => signupModalOpen(e)}
            data-testid='login-btn'
          >
            {t('signup.label')}
          </button>
          <button
            type='submit-fb'
            className={cx('login-btn', isDataScope && 'half-btn')}
            style={CUSTOM_COLOR && { backgroundColor: CUSTOM_COLOR }}
            onClick={(e) => onLogin(e)}
            data-testid='login-btn'
          >
            {t(isDataScope ? 'flightbase.login.label' : 'login.label')}
          </button>
          {isDataScope && (
            <button
              type='submit-dataScope'
              className={cx(
                'btn',
                'solid-color',
                'login-btn',
                isDataScope && 'half-btn',
                'datascope',
              )}
              style={CUSTOM_COLOR && { backgroundColor: CUSTOM_COLOR }}
              onClick={(e) => dataScopeLogin(e)}
              data-testid='login-btn'
            >
              {t('datascope.login.label')}
            </button>
          )}
        </div>
      </div>
    </form>
  );
}

export default LoginForm;
