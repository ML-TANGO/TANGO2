import { PureComponent } from 'react';
import { withTranslation } from 'react-i18next';

// Components
import UesrGroupFormModal from '@src/components/Modal/UserGroupFormModal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

class UserGroupFormModalContainer extends PureComponent {
  state = {
    validate: false,
    name: '',
    prevName: '',
    nameError: null,
    description: '',
    prevDescription: '',
    userList: [],
    selectedList: [], // 초기 선택된 유저 목록
    tmpSelectedList: [], // 선택된 Users 값 생성 수정시 파라미터로 쓰임
    prevSelectedUser: {},
    footerMessage: '',
  };

  async componentDidMount() {
    const { type } = this.props;
    const newState = {};
    // get user options
    const userList = this.parseUserOptions(await this.getGroupOptions());
    if (type === 'EDIT_USER_GROUP') {
      const { name, nameError, description, selectedList, prevSelectedUser } =
        await this.getGroupInfo();
      newState.name = name;
      newState.nameError = nameError;
      newState.prevName = name;
      newState.description = description;
      newState.prevDescription = description;
      newState.selectedList = selectedList;
      newState.prevSelectedUser = prevSelectedUser;
    }
    newState.userList = userList;
    this.setState(newState);
  }

  componentDidUpdate() {
    const { name } = this.state;

    if (!name) {
      this.setState({
        footerMessage: `${this.props.t('groupName.empty.message')}`,
      });
      return;
    }

    this.setState({ footerMessage: '' });
  }

  getGroupInfo = async () => {
    const {
      data: {
        data: { id: groupId },
      },
    } = this.props;
    const url = `users/group/${groupId}`;
    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { name, description, group_user_list: selectedList } = result;
      const prevSelectedUser = {};
      for (let i = 0; i < selectedList.length; i += 1) {
        prevSelectedUser[selectedList[i].id] = true;
      }
      return {
        name,
        nameError: '',
        description: description || '',
        selectedList: this.parseUserOptions(selectedList),
        prevSelectedUser,
      };
    }
    errorToastMessage(error, message);
    return {};
  };

  getGroupOptions = async () => {
    const url = 'users/group/option';
    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { user_list: userList } = result;
      return userList;
    }
    errorToastMessage(error, message);
    return [];
  };

  // 텍스트 인풋 이벤트 핸들러
  inputHandler = (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]: value,
      [`${name}Error`]: value === '' ? 'groupName.empty.message' : '',
    };
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  multiSelectHandler = ({ selectedList }) => {
    this.setState({ tmpSelectedList: selectedList }, () => {
      this.submitBtnCheck();
    });
  };

  parseUserOptions = (list) =>
    list.map(({ name: label, id: value }) => ({ label, value }));

  onSubmit = async (callback) => {
    const { type } = this.props;
    const url = 'users/group';
    let method = 'POST';
    const { name, description, tmpSelectedList } = this.state;

    const body = {
      usergroup_name: name,
      description,
      user_id_list: tmpSelectedList.map(({ value }) => value),
    };

    if (type === 'EDIT_USER_GROUP') {
      method = 'PUT';
      const {
        data: {
          data: { id: groupId },
        },
      } = this.props;
      body.usergroup_id = groupId;
    }
    const response = await callApi({ url, method, body });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      if (type === 'CREATE_USER_GROUP') {
        defaultSuccessToastMessage('create');
      } else {
        defaultSuccessToastMessage('update');
      }
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  // submit 버튼 활성 여부 체크 함수
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

    const { type: modalType } = this.props;
    if (modalType === 'EDIT_USER_GROUP' && validateState.validate) {
      const {
        name,
        prevName,
        description,
        prevDescription,
        tmpSelectedList,
        prevSelectedUser,
      } = this.state;
      let userChange = false;
      for (let i = 0; i < tmpSelectedList.length; i += 1) {
        if (!prevSelectedUser[tmpSelectedList[i].value]) {
          userChange = true;
        }
      }
      if (tmpSelectedList.length !== Object.keys(prevSelectedUser).length) {
        userChange = true;
      }

      if (name === prevName && description === prevDescription && !userChange)
        validateState.validate = false;
    }

    this.setState(validateState);
  };

  render() {
    const { props, state, inputHandler, multiSelectHandler, onSubmit } = this;
    return (
      <UesrGroupFormModal
        {...state}
        {...props}
        inputHandler={inputHandler}
        multiSelectHandler={multiSelectHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default withTranslation()(UserGroupFormModalContainer);
