import { PureComponent } from 'react';
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

// Components
import FolderFormModal from '@src/components/Modal/FolderFormModal';

import { openConfirm } from '@src/store/modules/confirm';
// Action
import { closeModal } from '@src/store/modules/modal';

// Network
import { STATUS_SUCCESS, upload } from '@src/network';
// Utils
import { errorToastMessage, extractPath } from '@src/utils';

class FolderFormModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    this.state = {
      validate: false,
      datasetId: '',
      datasetName: '',
      workspaceId: '',
      orginFolderName: '',
      folderName: '',
      folderNameError: null,
      accessType: '',
      loc: '',
      footerMessage: '',
      onChangedFolderName: () => {},
    };
  }

  componentDidMount() {
    const { type, data: datasetData } = this.props;
    const {
      datasetId,
      datasetName,
      workspaceId,
      workspaceName,
      accessType,
      loc,
      onChangedFolderName,
    } = datasetData;
    if (type === 'CREATE_FOLDER') {
      this.setState({
        datasetId,
        datasetName,
        folderName: '',
        folderNameError: '',
        workspaceId,
        workspaceName,
        accessType,
        loc,
      });
    } else {
      const {
        data: {
          data: { name: folderName },
        },
      } = this.props;
      this.setState({
        datasetId,
        datasetName,
        orginFolderName: folderName,
        folderName,
        folderNameError: '',
        workspaceId,
        workspaceName,
        accessType,
        loc,
        onChangedFolderName,
      });
    }
  }

  componentDidUpdate() {
    const { folderName } = this.state;

    if (!folderName) {
      this.setState({ footerMessage: this.props.t('folderName.placeholder') });
      return;
    }

    this.setState({ footerMessage: '' });
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
    if (name === 'folderName') {
      const folderReg = /(?=.*[:?*<>#$%&()/"|\\\s])/;
      if (value === '') {
        return 'folderName.empty.message';
      }
      if (value.match(folderReg)) {
        return 'folderNameRule.message';
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
      orginFolderName,
      folderName,
      accessType,
      onChangedFolderName,
    } = this.state;

    const form = new FormData();
    form.append('dataset_id', datasetId);

    if (extractPath(loc)) form.append('path', extractPath(loc));

    if (type === 'CREATE_FOLDER') {
      form.append('dir_name', folderName);
    } else {
      form.append('data', orginFolderName);
      form.append('new_name', folderName);
      onChangedFolderName(loc, orginFolderName, folderName);
    }
    let response;
    if (type === 'CREATE_FOLDER') {
      response = await upload({
        url: `datasets/${datasetId}/makedir`,
        method: 'post',
        form,
      });
    } else {
      // 업로드 api다.
      response = await upload({
        url: `datasets/${datasetId}/files/update`,
        method: 'put',
        form,
      });
    }

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      console.log('success create folder');
      if (callback) callback();
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
      <FolderFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default connect(null, { closeModal, openConfirm })(
  withTranslation()(FolderFormModalContainer),
);
