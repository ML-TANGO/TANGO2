import { PureComponent, createRef } from 'react';
import { connect } from 'react-redux';
// Actions
import { closeModal } from '@src/store/modules/modal';

// Components
import FileUploadFormModal from '@src/components/Modal/FileUploadFormModal';

// Utils
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  extractPath,
} from '@src/utils';

// Network
import { upload, STATUS_SUCCESS } from '@src/network';

class FileUploadFormModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    this.state = {
      validate: false, // Create 버튼 활성/비활성 여부 상태 값
      files: [],
      folders: [],
      filesError: null,
      uploadTypeOptions: [
        { label: 'file.label', value: 0 },
        { label: 'folder.label', value: 1 },
      ],
      uploadType: 0,
    };
    this.progressRef = createRef();
  }

  // 인풋 파일 이벤트 핸들러
  fileInputHandler = (newFiles) => {
    const { files: prevFiles } = this.state;
    const files = [...prevFiles, ...newFiles];
    const newState = {
      files,
      filesError: null,
    };
    const validate = this.validate('files', files);
    if (validate) {
      newState.filesError = validate;
    } else {
      newState.filesError = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 인풋 파일(폴더) 이벤트 핸들러
  folderInputHandler = (newFiles) => {
    const { files: prevFiles } = this.state;
    const files = [...prevFiles, ...newFiles];
    const folders = [];
    for (let i = 0; i < files.length; i += 1) {
      const { webkitRelativePath } = files[i];
      const folderName = webkitRelativePath.split('/')[0];
      // eslint-disable-next-line no-continue
      if (folders.indexOf(folderName) > -1) continue;
      folders.push(folderName);
    }
    const newState = {
      files,
      filesError: null,
      folders,
    };
    const validate = this.validate('files', files);
    if (validate) {
      newState.filesError = validate;
    } else {
      newState.filesError = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 라디오 버튼 이벤트 핸들러
  radioBtnHandler = (e) => {
    const { name, value } = e.target;
    const newState = { [name]: parseInt(value, 10) };
    if (name === 'uploadType') {
      newState.folders = [];
      newState.files = [];
      newState.filesError = null;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 인풋 파일 삭제 이벤트 핸들러
  onRemoveFiles = (idx) => {
    const { files } = this.state;
    const newFiles = [
      ...files.slice(0, idx),
      ...files.slice(idx + 1, files.length),
    ];
    const newState = {
      files: newFiles,
      filesError: null,
    };
    const validate = this.validate('files', newFiles);
    if (validate) {
      newState.filesError = validate;
    } else {
      newState.filesError = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  onRemoveFolder = (name, idx) => {
    const { files: prevFiles, folders } = this.state;
    const files = [];
    for (let i = 0; i < prevFiles.length; i += 1) {
      const file = prevFiles[i];
      const { webkitRelativePath } = prevFiles[i];
      const folderName = webkitRelativePath.split('/')[0];
      if (folderName !== name) {
        files.push(file);
      }
    }
    const newState = {
      folders: [
        ...folders.slice(0, idx),
        ...folders.slice(idx + 1, folders.length),
      ],
      files,
      filesError: null,
    };
    const validate = this.validate('files', files);
    if (validate) {
      newState.filesError = validate;
    } else {
      newState.filesError = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'files') {
      if (value.length === 0) {
        return 'file.empty.message';
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

    // workspaceId가 없는 경우에만 workspace 유효성 검증
    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }
    this.setState(validateState);
  };

  onSubmit = async (callback) => {
    const { files: doc, uploadType } = this.state;
    const { datasetId, loc, workspaceId, workspaceName, datasetName } =
      this.props.data;
    const form = new FormData();
    form.append('dataset_id', datasetId);
    if (extractPath(loc)) form.append('path', extractPath(loc));
    // form.append('workspace_id', workspaceId);
    // form.append('workspace_name', workspaceName);
    // form.append('dataset_name', datasetName);
    // form.append('type', uploadType);
    for (let i = 0; i < doc.length; i += 1) {
      // safari에서 폴더 경로 인식을 못함 formdata에 넣을 때 세번째 파라미터로 경로 및 파일명 지정
      // 지우지마세요!!
      const { webkitRelativePath, name: fileName } = doc[i];
      if (!doc[i].prev) {
        form.append('doc', doc[i], webkitRelativePath || fileName);
      }
    }

    const response = await upload({
      url: `datasets/${datasetId}/files`,
      method: 'put',
      form,
      progressCallback: (progress) => {
        const progressTarget = this.progressRef.current;
        if (progressTarget) {
          progressTarget.innerText = `Files are uploading... ${progress}%`;
        }
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      this.props.closeModal('UPLOAD_FILE');
      defaultSuccessToastMessage('upload');
      if (callback) callback();
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  render() {
    const {
      state,
      props,
      fileInputHandler,
      folderInputHandler,
      radioBtnHandler,
      onRemoveFiles,
      onRemoveFolder,
      onSubmit,
      progressRef,
    } = this;
    return (
      <FileUploadFormModal
        {...state}
        {...props}
        fileInputHandler={fileInputHandler}
        folderInputHandler={folderInputHandler}
        radioBtnHandler={radioBtnHandler}
        onRemoveFiles={onRemoveFiles}
        onRemoveFolder={onRemoveFolder}
        onSubmit={onSubmit}
        progressRef={progressRef}
      />
    );
  }
}

export default connect(null, { closeModal })(FileUploadFormModalContainer);
