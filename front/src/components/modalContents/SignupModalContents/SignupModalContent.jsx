import { useCallback, useReducer } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { encrypt, errorToastMessage, executeWithLogging } from '@src/utils';

// Components
import SignupModalHeader from './SignupModalHeader/SignupModalHeader';

// CSS module
import classNames from 'classnames/bind';
import style from './SignupModalContent.module.scss';

const cx = classNames.bind(style);

const CUSTOM_COLOR = import.meta.env.VITE_REACT_APP_PRIMARY_COLOR;

const initialState = {
  userId: '',
  password: '',
  confirmPassword: '',
  name: '',
  userMail: '',
  department: '',
  position: '',
  isClick: false,
  passwordShown: false,
  isDuplicate: false,
};

const formReducer = (state, action) => {
  switch (action.type) {
    case 'SERVER_MESSAGE_UPDATE': {
      return {
        ...state,
        serverMessage: action.value,
      };
    }
    case 'INPUT_CHANGE': {
      if (action.field === 'userId') {
        return {
          ...state,
          isDuplicate: false,
          serverMessage: '',
          [action.field]: action.value,
        };
      }

      return {
        ...state,
        serverMessage: '',
        [action.field]: action.value,
      };
    }

    case 'PASSWORDSHOWN':
      return {
        ...state,
        [action.field]: !action.value,
      };

    case 'CONFIRMPASSWORDSHOWN':
      return {
        ...state,
        [action.field]: !action.value,
      };
    case 'CHCEK_DUPLICATE_ID':
      return {
        ...state,
        serverMessage: '',
        [action.field]: action.value,
      };
    default:
      return state;
  }
};

const idRegex = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const passwordRegex = /^(?=.*[A-Za-z])(?=.*[0-9])(?=.*[~!@#$%^&*<>?]).{8,20}$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const calIdCheck = (id) => {
  return idRegex.test(id);
};

const calMailCheck = (email) => {
  return emailRegex.test(email);
};

const calPasswordCheck = (password) => {
  return passwordRegex.test(password);
};

// ** [계산] 유효성 검사 메세지 반환 **
const calReturnMessage = (formState, t) => {
  const {
    userId,
    password,
    confirmPassword,
    name,
    department,
    position,
    userMail,
    isDuplicate,
  } = formState;

  const idCheck = calIdCheck(userId);
  const mailCheck = calMailCheck(userMail);
  const passwordCheck = calPasswordCheck(password);

  console.log('userId : ', userId);
  console.log('userId : ', userId.length);

  if (userId.length < 3 || userId.length > 32) {
    return t('userIdRule.message');
  } else if (!idCheck) {
    return t('nameRule.message');
  } else if (!isDuplicate) {
    return t('userID.duplicateBtn.message');
  } else if (password === '' || !passwordCheck) {
    return t('passwordRule.message');
  } else if (password !== confirmPassword) {
    return t('passwordNotMatch.message');
  } else if (userMail === '' || !mailCheck) {
    return t('email.empty.message');
  } else if (!name) {
    return t('nickname.empty.message');
  } else if (!department) {
    return t('usergroup.empty.message');
  } else if (!position) {
    return t('position.empty.message');
  } else {
    return '';
  }
};

// ** [계산] 회원가입 API **
const calPostSignup = async (formState) => {
  const { userId, password, name, department, position, userMail } = formState;

  const newPassword = encrypt(password);
  const body = {
    name: userId,
    password: newPassword,
    email: userMail,
    nickname: name,
    team: department,
    job: position,
  };

  const response = await callApi({
    url: 'users/register',
    method: 'POST',
    body,
  });
  return response;
};

const SignupModalContent = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [formState, reducerDispatch] = useReducer(formReducer, initialState);
  const {
    userId,
    password,
    confirmPassword,
    confirmPasswordShown,
    passwordShown,
    name,
    department,
    position,
    userMail,
    isDuplicate,
    serverMessage,
  } = formState;

  const errorMessage = calReturnMessage(formState, t);
  const isDisabledBtn = (errorMessage, serverMessage) => {
    if (errorMessage) return true;
    if (![t('userID.duplicate.possible.message'), ''].includes(serverMessage))
      return true;
    return false;
  };

  // ** [Handler] 회원가입 모달 닫기 **
  const handleCloseModal = useCallback(() => {
    dispatch(closeModal('SIGNUP_MODAL'));
  }, [dispatch]);

  // ** [Handler] 회원가입 input 변경 **
  const handleInputChange = useCallback(
    (field) => (e) => {
      reducerDispatch({
        type: 'INPUT_CHANGE',
        field,
        value: e.target.value,
      });
    },
    [],
  );

  const handleServerMessage = useCallback((value) => {
    reducerDispatch({
      type: 'SERVER_MESSAGE_UPDATE',
      value,
    });
  }, []);

  // ** [Handler] 중복 검사 버튼 **
  const handleDuplicateCheck = useCallback(
    async (userId, t, reducerDispatch) => {
      const idCheck = calIdCheck(userId);
      if (userId.length < 3 || userId.lenght > 32) {
        handleServerMessage(t('userIdRule.message'));
        return;
      }
      if (!idCheck) {
        handleServerMessage(t('nameRule.message'));
        return;
      }

      await executeWithLogging(async () => {
        const { status, message } = await callApi({
          url: `users/check/${userId}`,
          method: 'get',
        });

        if (status === 'STATUS_FAIL') {
          reducerDispatch({
            type: 'CHCEK_DUPLICATE_ID',
            field: 'isDuplicate',
            value: false,
          });

          if (message === '이미 사용중인 ID 입니다.') {
            handleServerMessage(t('userID.duplicate.message'));
          }

          if (message === '요청 대기중인 ID입니다.') {
            handleServerMessage(t('userID.duplicate.request.message'));
          }
          return;
        }

        reducerDispatch({
          type: 'CHCEK_DUPLICATE_ID',
          field: 'isDuplicate',
          value: true,
        });
        handleServerMessage(t('userID.duplicate.possible.message'));
      });
    },
    [handleServerMessage],
  );

  // ** [handler] 회원가입 **
  const handleSignup = useCallback(
    (serverMessage, formState, t, handleCloseModal) => async (e) => {
      e.preventDefault();
      const message = calReturnMessage(formState, t);
      if (message) return;
      if (![t('userID.duplicate.possible.message'), ''].includes(serverMessage))
        return;

      const { status, errorMessage, error } = await calPostSignup(formState);

      if (status === STATUS_SUCCESS) {
        console.log('signup success');
        handleCloseModal();
        return;
      }
      errorToastMessage(error, errorMessage);
    },
    [],
  );

  return (
    <ModalTemplate
      customStyle={{
        component: {
          width: '400px',
          padding: '32px 40px',
        },
      }}
      headerRender={
        <SignupModalHeader
          t={t}
          handleCloseModal={() => handleCloseModal(dispatch)}
        />
      }
    >
      <div className={cx('wrapper')}>
        <form
          className={cx('form')}
          onSubmit={handleSignup(serverMessage, formState, t, handleCloseModal)}
        >
          <div className={cx('id-input')}>
            <i className={cx('user-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='user_id'
              value={userId}
              placeholder={'ID'}
              onChange={handleInputChange('userId')}
              data-testid='user-id'
            />
            <button
              className={cx('id-check-btn', isDuplicate && 'disabled')}
              onClick={() => handleDuplicateCheck(userId, t, reducerDispatch)}
              disabled={isDuplicate}
            >
              {t('duplicate.btn')}
            </button>
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

          <div className={cx('password-input')}>
            <i className={cx('password-ico')} />
            <input
              type={confirmPasswordShown ? 'text' : 'password'}
              autoComplete='off'
              className={cx('login-input')}
              name='confirmPassword'
              value={confirmPassword}
              placeholder={t('passwordConfirm.label')}
              onChange={handleInputChange('confirmPassword')}
              data-testid='user-pwd'
            />
            <button
              type='button'
              className={cx('show-hide-btn')}
              onClick={() =>
                reducerDispatch({
                  type: 'CONFIRMPASSWORDSHOWN',
                  field: 'confirmPasswordShown',
                  value: confirmPasswordShown,
                })
              }
            >
              <img
                src={`/images/icon/00-ic-info-eye${
                  confirmPasswordShown ? '' : '-off'
                }.svg`}
                alt='show'
              />
            </button>
          </div>

          <div className={cx('user-mail')}>
            <i className={cx('mail-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='mail'
              value={userMail}
              placeholder={t('email')}
              onChange={handleInputChange('userMail')}
              data-testid='user-mail'
            />
          </div>
          <div className={cx('user-input')}>
            <i className={cx('person-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='name'
              value={name}
              placeholder={t('name.label')}
              onChange={handleInputChange('name')}
              data-testid='user-mail'
            />
          </div>
          <div className={cx('user-input')}>
            <i className={cx('member-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='department'
              value={department}
              placeholder={t('affiliation.signup.label')}
              onChange={handleInputChange('department')}
              data-testid='department'
            />
          </div>
          <div className={cx('user-input')}>
            <i className={cx('position-ico')} />
            <input
              type='text'
              className={cx('login-input')}
              name='position'
              value={position}
              placeholder={t('position.signup.label')}
              onChange={handleInputChange('position')}
              data-testid='position'
            />
          </div>
          <div className={cx('message')}>
            {serverMessage ? serverMessage : errorMessage}
          </div>
          <button
            type='submit'
            className={cx(
              'btn',
              'solid-color',
              'signup-btn',
              isDisabledBtn(errorMessage, serverMessage) && 'disabled',
            )}
            style={CUSTOM_COLOR && { backgroundColor: CUSTOM_COLOR }}
            onClick={handleSignup(
              serverMessage,
              formState,
              t,
              handleCloseModal,
            )}
            data-testid='login-btn'
            disabled={isDisabledBtn(errorMessage, serverMessage)}
          >
            {t('signup.request.label')}
          </button>
        </form>
      </div>
    </ModalTemplate>
  );
};

export default SignupModalContent;
