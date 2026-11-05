import { PureComponent } from 'react';
import { connect } from 'react-redux';

// Components
import FileFormModal from '@src/components/Modal/FileFormModal';
import { toast } from '@src/components/Toast';

import { openConfirm } from '@src/store/modules/confirm';
// Action
import { closeModal } from '@src/store/modules/modal';

// Network
import { STATUS_SUCCESS, upload } from '@src/network';
// Utils
import { defaultSuccessToastMessage, extractPath } from '@src/utils';

class FileFormModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    this.state = {
      validate: false,
      datasetId: '',
      datasetName: '',
      workspaceId: '',
      orginFileName: '',
      fileName: '',
      fileNameError: null,
      accessType: '',
      loc: '',
    };
  }

  componentDidMount() {
    const { data: datasetData } = this.props;
    const {
      datasetId,
      datasetName,
      workspaceId,
      workspaceName,
      accessType,
      loc,
    } = datasetData;
    const {
      data: {
        data: { name: fileName },
      },
    } = this.props;
    this.setState({
      datasetId,
      datasetName,
      orginFileName: fileName,
      fileName,
      fileNameError: '',
      workspaceId,
      workspaceName,
      accessType,
      loc,
    });
  }

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

  // 텍스트 인풋 이벤트 핸들러
  textInputHandler = (e) => {
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
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'fileName') {
      const fileReg = /(?=.*[:?*<>#$%&()/"|\\\s])/;
      if (value === '') {
        return 'fileName.empty.message';
      }
      if (value.match(fileReg)) {
        return 'fileNameRule.message';
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
    const {
      datasetId,
      datasetName,
      workspaceId,
      loc,
      orginFileName,
      fileName,
      accessType,
    } = this.state;

    const form = new FormData();
    form.append('dataset_id', datasetId);
    const newLoc = extractPath(loc);
    if (newLoc && newLoc !== '/') {
      form.append('path', extractPath(loc));
    }

    form.append('new_name', fileName);
    form.append('data', orginFileName);

    // 업데이트하는 코드이다
    const response = await upload({
      url: `datasets/${datasetId}/files/update`,
      method: 'put',
      form,
    });
    const { status, message } = response;
    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      defaultSuccessToastMessage('update');
      if (callback) callback();
      return true;
    }
    toast.error(message);
    return false;
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const { state, props, textInputHandler, onSubmit } = this;
    return (
      <FileFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default connect(null, { closeModal, openConfirm })(
  FileFormModalContainer,
);
