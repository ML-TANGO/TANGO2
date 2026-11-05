import { PureComponent } from 'react';
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

// Components
import UserFormModal from '@src/components/Modal/UserFormModal';

// Action
import { closeModal } from '@src/store/modules/modal';
// network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';

// utils
import {
  defaultSuccessToastMessage,
  encrypt,
  errorToastMessage,
  isMailValidate,
} from '@src/utils';

let userNameSearchTimer;
const passwordType = /^(?=.*[A-Za-z])(?=.*[0-9])(?=.*[~!@#$%^&*<>?]).{8,20}$/;
class UserFormModalContainer extends PureComponent {
  state = {
    userId: '',
    validate: false, // Create 버튼 활성/비활성 여부 상태 값
    name: '',
    password: '',
    email: null,
    nickname: null,
    confirm: '',
    usergroup: null,
    position: null,
    nameError: null,
    passwordError: null,
    confirmError: null,
    readOnlyTxt: '',
    userTypeOptions: [
      { label: 'User', value: 3 },
      { label: 'Training Manager', value: 2 },
      { label: 'Workspace Manager', value: 1 },
      { label: 'Admin', value: 0 },
    ],
    userGroupOptions: [],
    userGroup: { label: 'None', value: null },
    userType: 3,
    footerMessage: '',
  };

  async componentDidMount() {
    const { type, data } = this.props;
    const userGroupOptions = await this.getGroupOptions();
    if (type === 'EDIT_USER') {
      const { data: userData } = data;
      const groupId = await this.getUserInfo(userData.id);
      let userGroup;
      if (groupId) {
        [userGroup] = userGroupOptions.filter(({ value }) => groupId === value);
      }

      this.setState({
        userId: userData.id,
        name: userData.name,
        email: userData.email,
        nickname: userData.nickname,
        usergroup: userData.team,
        position: userData.job,

        nameError: '',
        readOnlyTxt: 'edit',
        userGroupOptions,
        userGroup: groupId ? userGroup : { label: 'None', value: null },
        passwordError: '',
        confirmError: '',
      });
    } else {
      this.setState({
        readOnlyTxt: 'create',
        userGroupOptions,
      });
    }
  }

  componentDidUpdate() {
    const { name, password, email, nickname, confirm, usergroup, position } =
      this.state;

    if (!name) {
      this.setState({
        footerMessage: `${this.props.t('userID.empty.message')}`,
      });
      return;
    }

    if (!password) {
      this.setState({
        footerMessage: `${this.props.t('password.empty.message')}`,
      });
      return;
    }

    if (!confirm) {
      this.setState({
        footerMessage: `${this.props.t('checkpassword.error.message')}`,
      });
      return;
    }

    if (!email) {
      this.setState({
        footerMessage: `${this.props.t('email.empty.message')}`,
      });
      return;
    }

    if (!nickname) {
      this.setState({
        footerMessage: `${this.props.t('nickname.empty.message')}`,
      });
      return;
    }

    if (!usergroup) {
      this.setState({
        footerMessage: `${this.props.t('usergroup.empty.message')}`,
      });
      return;
    }

    if (!position) {
      this.setState({
        footerMessage: `${this.props.t('position.empty.message')}`,
      });
      return;
    }

    this.setState({ footerMessage: '' });
  }

  /** ================================================================================
   * API START
   ================================================================================ */
  getUserInfo = async (userId) => {
    const url = `users/${userId}`;
    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { group_id: groupId } = result;
      return groupId;
    }
    errorToastMessage(error, message);
    return null;
  };

  getGroupOptions = async () => {
    const url = 'users/option';
    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { usergroup_list: userGroupOptions } = result;
      return [
        { label: 'None', value: null },
        ...userGroupOptions.map(({ name: label, id: value }) => ({
          label,
          value,
        })),
      ];
    }
    errorToastMessage(error, message);
    return [];
  };

  /** ================================================================================
   * API END
   ================================================================================ */

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

    const validate = this.validate(name, value);
    if (validate) {
      newState[`${name}Error`] = validate;
    } else {
      newState[`${name}Error`] = '';
    }
    if (name === 'name') {
      // Username Search Timer 로직
      if (userNameSearchTimer) {
        clearTimeout(userNameSearchTimer);
      }
      userNameSearchTimer = setTimeout(async () => {
        const nameRegType = /^[a-z0-9]+(-[a-z0-9]+)*$/;
        const searchState = {};

        if (nameRegType.test(value)) {
          const duplicate = await this.duplicated(value);
          if (duplicate.status === STATUS_FAIL) {
            searchState.nameError = 'userID.duplicate.message';
            this.setState(searchState);
          }
        }
      }, 250);
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  duplicated = async (value) => {
    const response = await callApi({
      url: `users/check/${value}`,
      method: 'GET',
    });
    return response;
  };

  // 유효성 검증
  validate = (name, value) => {
    const { state } = this;
    if (name === 'name') {
      const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
      if (value === '') {
        return 'userID.empty.message';
      }
      if (!value.match(regType1) || value.match(regType1)[0] !== value) {
        return 'nameRule.message';
      }
      if (value.length < 3) {
        return 'userIdRule.message';
      }
    } else if (name === 'password') {
      // 숫자, 대소문자영어, 특수문자 포함 8자리 이상 20자리 이하 비밀번호 정규식 -> 영어로
      if (!passwordType.test(value)) {
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
      if (value !== state.password) {
        return 'passwordNotMatch.message';
      }

      if (passwordType.test(value) && value === state.password) {
        this.setState({
          confirmError: '',
          passwordError: '',
        });
      }
    } else if (name === 'email') {
      const isValidateEmail = isMailValidate(value);
      if (!isValidateEmail) return 'emailNotMatch.message';
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

    const { email, position, usergroup } = state;
    if (!email || !position || !usergroup) validateState.validate = false;

    this.setState(validateState);
  };

  searchSelectHandler = (selected, name) => {
    const newState = {
      [name]: selected,
    };

    this.setState(newState, () => this.submitBtnCheck());
  };

  // submit 버튼 클릭 이벤트
  onSubmit = async (callback) => {
    const { type } = this.props;
    const {
      userId,
      name,
      password,
      userType,
      usergroup,
      email,
      nickname,
      position,
      userGroup,
    } = this.state;

    let body = {};
    let method = '';

    if (type === 'EDIT_USER') {
      method = 'PUT';
      body = {
        select_user_id: userId,
        usergroup_id: userGroup.value ? userGroup.value : 0,
        nickname,
        job: position,
        email,
        team: usergroup,
      };
      if (password !== '') body.new_password = encrypt(password);
    } else {
      method = 'POST';
      body = {
        new_user_name: name,
        user_type: userType,
        nickname,
        email,
        team: usergroup,
        job: position,
        usergroup_id: userGroup.value,
      };
      if (password !== '') body.password = encrypt(password);
    }

    const response = await callApi({
      url: 'users',
      method,
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      if (callback) callback();
      if (type === 'EDIT_USER') {
        defaultSuccessToastMessage('update');
      } else {
        defaultSuccessToastMessage('create');
      }
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const { state, props, textInputHandler, searchSelectHandler, onSubmit } =
      this;
    return (
      <UserFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        searchSelectHandler={searchSelectHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default connect(null, { closeModal })(
  withTranslation()(UserFormModalContainer),
);
