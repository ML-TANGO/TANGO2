import { useState, useEffect } from 'react';

// Components
import ToolPasswordChangeModalContent from '@src/components/modalContents/ToolPasswordChangeModalContent';

// Utils
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  encrypt,
} from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

function ToolPasswordChangeModal({ type, data: modalData }) {
  const { toolId, isReset } = modalData;
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [userIdError, setUserIdError] = useState(null);
  const [passwordError, setPasswordError] = useState(null);
  const [passwordConfirmError, setPasswordConfirmError] = useState(null);
  const [validate, setValidate] = useState(false);

  const textInputHandler = (e) => {
    const { name, value } = e.target;
    if (name === 'id') {
      const validate = checkValidate('id', value);
      if (validate) {
        setUserIdError(validate);
      } else {
        setUserIdError('');
      }
      setUserId(value);
    } else if (name === 'password') {
      const validate = checkValidate('password', value);
      if (validate) {
        setPasswordError(validate);
      } else {
        setPasswordError('');
      }
      setPassword(value);
    } else if (name === 'passwordConfirm') {
      const validate = checkValidate('passwordConfirm', value);
      if (validate) {
        setPasswordConfirmError(validate);
      } else {
        setPasswordConfirmError('');
      }
      setPasswordConfirm(value);
    }
  };

  const checkValidate = (name, value) => {
    if (name === 'password') {
      if (value === '') {
        return 'password.empty.message';
      }
      if (passwordConfirm !== '') {
        if (passwordConfirm === value) {
          setPasswordConfirmError('');
        } else {
          return 'passwordNotMatch.message';
        }
      }
    } else if (name === 'passwordConfirm') {
      if (value === '') {
        return 'password.empty.message';
      }
      if (value !== password) {
        return 'passwordNotMatch.message';
      } else {
        setPasswordError('');
      }
    } else if (name === 'id') {
      if (value === '') {
        return 'userID.empty.message';
      }
    }
  };

  const onSubmit = async (callback) => {
    const body = {
      training_tool_id: toolId,
      new_password: encrypt(password),
    };
    if (isReset) {
      body.user_id = userId;
    } else {
      body.protocol = window.location.protocol.replace(':', '');
    }

    const response = await callApi({
      url: 'trainings/filebrowser-pw-change',
      method: isReset ? 'post' : 'put',
      body,
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      if (isReset) {
        defaultSuccessToastMessage('change');
      } else {
        defaultSuccessToastMessage('create');
      }
      callback();
    } else {
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    if (passwordError === '' && passwordConfirmError === '') {
      if (isReset) {
        if (userId !== '') {
          setValidate(true);
        } else {
          setValidate(false);
        }
      } else {
        setValidate(true);
      }
    } else {
      setValidate(false);
    }
  }, [userId, passwordError, passwordConfirmError, isReset]);

  return (
    <ToolPasswordChangeModalContent
      type={type}
      modalData={modalData}
      validate={validate}
      userId={userId}
      password={password}
      userIdError={userIdError}
      passwordError={passwordError}
      passwordConfirmError={passwordConfirmError}
      textInputHandler={textInputHandler}
      onSubmit={onSubmit}
    />
  );
}

export default ToolPasswordChangeModal;
