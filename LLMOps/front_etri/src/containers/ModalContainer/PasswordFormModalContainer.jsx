import { PureComponent } from 'react';
import { connect } from 'react-redux';

// Action
import { closeModal } from '@src/store/modules/modal';

// Components
import PasswordFormModal from '@src/components/Modal/PasswordFormModal';

// utils
import {
  encrypt,
  errorToastMessage,
  defaultSuccessToastMessage,
} from '@src/utils';

// network
import { callApi, STATUS_SUCCESS } from '@src/network';

class PasswordFormModalContainer extends PureComponent {
  state = {
    validate: false, // 수정 버튼 활성/비활성 여부 상태 값
    password: '',
    newPassword: '',
    confirm: '',
    passwordError: null,
    newPasswordError: null,
    confirmError: null,
  };

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

  // 텍스트 인풋 이벤트 핸들러
  textInputHandler = async (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };
    const validate = await this.validate(name, value);
    if (validate) {
      newState[`${name}Error`] = validate;
    } else {
      newState[`${name}Error`] = '';
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증
  validate = async (name, value) => {
    const { state } = this;
    if (name === 'newPassword') {
      // 숫자, 대소문자영어, 특수문자 포함 8자리 이상 20자리 이하 비밀번호 정규식 -> 영어로
      const regType2 = /^(?=.*[A-Za-z])(?=.*[0-9])(?=.*[~!@#$%^&*<>?]).{8,20}$/;
      if (!regType2.test(value)) {
        return 'passwordRule.message';
      }
      if (state.confirm !== '') {
        if (state.confirm === value) {
          this.setState({
            confirmError: '',
          });
        } else {
          return 'passwordNotMatch.message';
        }
      }
    } else if (name === 'confirm') {
      if (value !== state.newPassword) {
        return 'passwordNotMatch.message';
      }
    }
    return null;
  };

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성
    const { state } = this;
    const stateKeys = Object.keys(state);
    let validateCount = 0;
    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];
      if (key.indexOf('Error') !== -1) {
        if (state[key] !== '') {
          validateCount += 1;
        }
      }
    }
    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
  };

  // submit 버튼 클릭 이벤트
  onSubmit = async (callback) => {
    const { type } = this.props;
    const { password, newPassword } = this.state;

    let body = {};
    body = {
      password: encrypt(password),
      new_password: encrypt(newPassword),
    };

    const response = await callApi({
      url: 'users/password',
      method: 'put',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      if (callback) callback();
      defaultSuccessToastMessage('change');
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const { state, props, textInputHandler, onSubmit } = this;
    return (
      <PasswordFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default connect(null, { closeModal })(PasswordFormModalContainer);
