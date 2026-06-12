import { PureComponent } from 'react';

// Components
import WsDescFormModal from '@src/components/Modal/WsDescFormModal';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

class WsDescFormModalContainer extends PureComponent {
  state = {
    validate: false,
    prevDescription: '',
    description: '', // Workspace 설명
    descriptionError: null, // Workspace 설명 에러
  };

  componentDidMount() {
    this.getWorkspaceDescInfo();
  }

  // 워크스페이스 설명 정보 가져오기
  getWorkspaceDescInfo = async () => {
    const { workspaceId } = this.props.data;
    const response = await callApi({
      url: `workspaces/${workspaceId}/description`,
      method: 'get',
    });
    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const { description } = result;
      this.setState({
        description,
        prevDescription: description,
      });
    } else {
      errorToastMessage(error, message);
    }
  };

  // 텍스트 인풋 이벤트 핸들러
  inputHandler = (e) => {
    const { name, value } = e.target;
    const { prevDescription } = this.state;
    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };
    if (prevDescription !== value) {
      newState.validate = true;
    }
    this.setState(newState);
  };

  // 워크스페이스 설명 수정
  onSubmit = async (callback) => {
    const { workspaceId } = this.props.data;
    const url = `workspaces/${workspaceId}/description`;
    const { description } = this.state;

    const body = {
      description,
    };
    const response = await callApi({
      url,
      method: 'PUT',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      defaultSuccessToastMessage('update');
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  render() {
    const { props, state, inputHandler, onSubmit } = this;
    return (
      <WsDescFormModal
        {...state}
        {...props}
        inputHandler={inputHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default WsDescFormModalContainer;
