import { createRef, PureComponent } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

import { sliceUploader } from '@src/fileUpload';
import dayjs from 'dayjs';

// Components
import DatasetFormModal from '@src/components/Modal/DatasetFormModal';

import { openConfirm } from '@src/store/modules/confirm';
// Action
import { closeModal } from '@src/store/modules/modal';
import {
  addUploadInstance,
  deleteLastUploadInstance,
  openUploadList,
} from '@src/store/modules/upload';
// Network
import { callApi, STATUS_SUCCESS, upload } from '@src/network';

// Utils
import { errorToastMessage } from '@src/utils';

const isGoogleUpload =
  import.meta.env.VITE_REACT_APP_GOOGLE_API_KEY &&
  import.meta.env.VITE_REACT_APP_GOOGLE_CLIENT_ID;

class ModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    this._MODE = import.meta.env.VITE_REACT_APP_MODE;
    this.state = {
      datasetId: '',
      validate: false, // Create 버튼 활성/비활성 여부 상태 값
      name: '',
      nameError: null,
      workspaceOptions: [],
      selectedWorkspace: null,
      files: [],
      filesError: '',
      folders: [],
      removeFiles: [],
      accessTypeOptions: [
        {
          label: 'readAndWrite.label',
          value: 1,
          labelStyle: {
            fontSize: '14px',
            fontFamily: 'SpoqaM',
            marginTop: '2px',
          },
        },
        {
          label: 'readOnly.label',
          value: 0,
          labelStyle: {
            fontSize: '14px',
            fontFamily: 'SpoqaM',
            marginTop: '2px',
          },
        },
      ],
      accessType: 1,
      description: '',
      descriptionError: null,
      uploadMethod: 0,
      uploadMethodOptions: [
        { label: 'myComputerUpload.label', value: 0 },
        {
          label: 'googleDriveUpload.label',
          value: 1,
          disabled: !isGoogleUpload,
        },
        // { label: 'Drone WS', value: 2 },
        // { label: 'loadingATemplate.label', value: 3 }, // 임시추가
      ],
      builtInTemplate: 0,
      builtInModelTemplateOptions: [
        { label: 'noUseTemplate.label', value: 0 },
        {
          label: 'useTemplate.label',
          value: 1,
        },
      ],
      // Drone Ws
      droneBm: 'POL',
      droneStartDate: dayjs().subtract(7, 'd').format('YYYY-MM-DD HH:mm'),
      droneEndDate: dayjs(new Date()).format('YYYY-MM-DD HH:mm'),
      droneArea: '',
      droneAreaError: '',
      droneAccess: 'bm',
      uploadDataTypeOptions: [
        { label: 'default.label', value: 0 },
        { label: 'loadingATemplate.label', value: 1 },
      ],
      uploadDataType: 0,
      datasetTemplateList: [],
      datasetTemplate: null,
      datasetFormFiles: null,
      defaultTemplate: {
        dataForm: [
          {
            formType: 'dir',
            formName: '/',
            formDesc: 'topLevelPath.message',
          },
        ],
      },
      builtInModelFileList: [],
      builtInModelDataList: [],
      builtInModelId: 0,
      googleAccessToken: null,
      builtInModelNameList: [],
      footerMessage: '데이터셋 이름을 입력하세요',
    };
    this.progressRef = createRef();
  }

  progressRefs = [];

  async componentDidMount() {
    document.addEventListener('keydown', this.keyboardHandler);
    const workspaceOptions = await this.getWorkspaces();
    const {
      type,
      data: { data: datasetData },
    } = this.props;
    const { templateData } = this.props.data;
    if (templateData != null) {
      this.radioBtnHandler('builtInTemplate', 1);
    }
    if (type === 'EDIT_DATASET') {
      const response = await callApi({
        url: `datasets/${datasetData.id}`,
        method: 'get',
      });
      const { result, status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        const {
          id: datasetId,
          name,
          access: accessType,
          workspace_id: workspaceId,
          description,
        } = result;
        this.setState({
          datasetId,
          name,
          nameError: '',
          workspaceOptions,
          accessType: parseInt(accessType, 10),
          selectedWorkspace: workspaceOptions.filter(
            ({ value }) => value === workspaceId,
          )[0],
          filesError: '',
          description: !description ? '' : description,
          descriptionError: description ? '' : null,
        });
      } else {
        errorToastMessage(error, message);
      }
    } else if (type === 'CREATE_DATASET') {
      const { workspaceId } = this.props.data;
      if (workspaceId) {
        const id = parseInt(workspaceId, 10);
        this.setState({
          selectedWorkspace: { label: id, value: id },
        });
      } else {
        this.setState({
          workspaceOptions,
        });
      }
    }
  }

  componentDidUpdate() {
    const { name } = this.state;

    if (!name) {
      this.setState({ footerMessage: this.props.t('datasetName.placeholder') });
      return;
    }

    this.setState({ footerMessage: '' });
  }

  /** ================================================================================
   * API START
   ================================================================================ */

  getWorkspaces = async () => {
    const response = await callApi({
      url: 'workspaces',
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      return result.list.map(({ name, id }) => ({ label: name, value: id }));
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
  textInputHandler = (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };
    const validate = this.validate(name, value);
    if (validate) {
      newState[`${name}Error`] = validate;
    } else if (name === 'description' && value.trim() === '') {
      newState[`${name}Error`] = null;
    } else {
      newState[`${name}Error`] = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 셀렉트 박스 이벤트 핸들러
  selectInputHandler = (selectedWorkspace) => {
    this.setState(
      {
        selectedWorkspace,
      },
      () => {
        this.submitBtnCheck();
      },
    );
  };

  // 라디오 버튼 이벤트 핸들러
  radioBtnHandler = (name, value) => {
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

  // Template 선택 이벤트 핸들러
  selectTemplate = (template) => {
    this.setState({ datasetTemplate: template });
  };

  templateFileFolderHandler = (formList, data) => {
    if (data) {
      this.setState({
        builtInModelFileList: formList,
        builtInModelDataList: data,
      });
    } else {
      const datasetFormFiles = [];
      for (let i = 0; i < formList.length; i += 1) {
        const {
          formData: { files },
        } = formList[i];
        for (let j = 0; j < files.length; j += 1) {
          datasetFormFiles.push(files[j]);
        }
      }
      this.setState({ datasetFormFiles });
    }
  };

  builtInModelNamesHandler = (data) => {
    this.setState({ builtInModelNameList: data });
  };

  builtInModelIdHandler = (id) => {
    this.setState({ builtInModelId: id });
  };
  /**
   * Google Drive 이벤트 핸들러
   *
   * @param {object} data
   */
  googleDriveHandler = (data) => {
    this.setState({ googleDriveData: data });
  };

  googleAccessTokenHandler = (token) => {
    this.setState({ googleAccessToken: token });
  };

  // 드론 촬영시간 핸들러
  timeRangeHandler = (startDate, endDate) => {
    this.setState({
      droneStartDate: dayjs(startDate).format('YYYY-MM-DD HH:mm'),
      droneEndDate: dayjs(endDate).format('YYYY-MM-DD HH:mm'),
    });
  };

  // 드론 이벤트 핸들러
  droneOptionHandler = (e) => {
    const { name, value } = e.target;
    const newState = { [name]: value };

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'name') {
      // 정규 표현식을 사용하여 금지된 특수 문자를 검사
      const forbiddenChars =
        /[\\<>:*?"'|:;`{}()^$ &[\]#@!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

      const regType = !forbiddenChars.test(value);

      if (value === '') {
        return 'datasetName.empty.message';
      }
      if (!regType) {
        return 'newNameRule.message';
      }
    } else if (name === 'files') {
      if (value.length === 0) {
        return 'file.empty.message';
      }
      const fileReg = /(?=.*[:?*<>#$%&()/"|\\\s])/;
      for (let i = 0; i < value.length; i += 1) {
        const { name: fileName } = value[i];
        if (fileName.match(fileReg)) {
          return 'fileNameRule.message';
        }
      }
    }
    return null;
  };

  keyboardHandler = (event) => {
    const { type } = this.props;
    if (event.keyCode === 27) {
      this.props.closeModal(type);
    }
  };

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성
    const { state } = this;
    const stateKeys = Object.keys(state);
    let validateCount = 0;
    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];
      if (key !== 'descriptionError' && key.indexOf('Error') !== -1) {
        if (state[key] !== '') {
          validateCount += 1;
        }
      }
    }

    // workspaceId가 없는 경우에만 workspace 유효성 검증
    const { workspaceId } = this.props.data;
    if (!state.selectedWorkspace && !workspaceId) validateCount += 1;
    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
  };

  builtInModel = () => {
    const { builtInModelDataList, builtInModelFileList } = this.state;
    let newArray = [];
    let noDataFolderName = [];
    for (let i = 0; i < builtInModelDataList.length; i++) {
      if (builtInModelFileList[i].length !== 0) {
        noDataFolderName.push(builtInModelDataList[i].name);
        for (let j = 0; j < builtInModelFileList[i].length; j++) {
          builtInModelFileList[i][j] = Object.assign(
            builtInModelFileList[i][j],
            {
              built_in_model_id: builtInModelDataList[i].built_in_model_id,
            },
          );
        }
      }
      newArray = [...newArray, ...builtInModelFileList[i]];
    }
    return {
      datasetFormFiles: newArray,
      noDataFolderName,
    };
  };

  // submit 버튼 클릭 이벤트
  onSubmit = async (callback) => {
    const { type } = this.props;
    const {
      datasetId,
      name,
      selectedWorkspace,
      accessType,
      description,
      uploadMethod,
      builtInTemplate,
      googleDriveData,
      files: doc,
      googleAccessToken,
      builtInModelNameList,
      builtInModelFileList,
    } = this.state;
    let { datasetFormFiles, builtInModelId } = this.state;
    let noDataFolderName = null;
    let googleNoUploadedName = [];
    // 빌트인 모델 템플릿 사용해서 업로드
    if (
      builtInTemplate === 1 &&
      uploadMethod === 0 &&
      builtInModelFileList.length > 0
    ) {
      const result = this.builtInModel();
      datasetFormFiles = result.datasetFormFiles;
      noDataFolderName = result.noDataFolderName;
    }

    const form = new FormData();
    form.append('dataset_name', name);
    form.append('workspace_id', selectedWorkspace.value);
    form.append('access', accessType);
    form.append('description', description);

    const formAdd = () => {
      if (builtInTemplate === 1) {
        form.append('upload_method', 1);
        form.append('built_in_model_id', builtInModelId);
      } else {
        form.append('upload_method', 0);
      }
    };

    if (type === 'EDIT_DATASET') {
      // form.append('dataset_id', datasetId);
    }
    if (uploadMethod === 0) {
      if (type === 'CREATE_DATASET') {
        formAdd();
      }
      for (let i = 0; i < doc.length; i += 1) {
        if (!doc[i].prev) {
          form.append('doc', doc[i]);
        }
      }
      if (datasetFormFiles) {
        return this.splitUpload(
          form,
          datasetFormFiles,
          callback,
          noDataFolderName,
        );
      }
    }
    if (uploadMethod === 1) {
      if (type === 'CREATE_DATASET') {
        formAdd();
        // TODO: GitHub clone
      }
      // Google Drive
      if (googleDriveData != null) {
        let google_info = {};
        Object.assign(google_info, { access_token: googleAccessToken });
        if (googleDriveData.length > 0) {
          // 빌트인 모델 사용
          const newArray = [];
          for (let i = 0; i < builtInModelNameList.length; i++) {
            if (googleDriveData[i] != null) {
              newArray.push(googleDriveData[i]);
              googleNoUploadedName.push(builtInModelNameList[i]);
            }
          }
          Object.assign(google_info, { list: newArray });
        } else {
          // 사용 안 함
          Object.assign(google_info, { list: [googleDriveData] });
        }
        form.append('google_info', JSON.stringify(google_info));
      }
    }

    const datasetUrl =
      type === 'CREATE_DATASET' ? 'datasets' : `datasets/${datasetId}`;

    const response = await upload({
      url: datasetUrl,
      header: googleNoUploadedName.length !== 0 && {
        'Remove-List': googleNoUploadedName.toString(),
      },
      method: type === 'EDIT_DATASET' ? 'put' : 'post',
      form,
      progressCallback: (progress) => {
        if (this.progressRef.current)
          this.progressRef.current.innerText = `Files are uploading... ${progress}%`;
        for (let i = 0; i < this.progressRefs.length; i += 1) {
          if (this.progressRefs[i])
            this.progressRefs[
              i
            ].innerText = `Files are uploading... ${progress}%`;
        }
      },
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      console.log('create success dataset');

      if (callback) callback();
      return true;
    } else {
      errorToastMessage(error, message);
    }
    return false;
  };
  // 분할 업로드
  splitUpload = (form, files, callback, noDataFolderName) => {
    const { type } = this.props;
    let isUploadFlag = false; // 처음 한번 업로드 성공 시 모달창 종료
    const uploadInstance = sliceUploader({
      uploadGroupName: form.get('dataset_name'),
      data: files,
      doneFunc: callback,
      noDataFolderName: noDataFolderName,
      uploadRequest: async (
        s,
        e,
        chunk,
        fileName,
        fileSize,
        basePath,
        isEnd,
        prevResult,
        removeFolderName,
        file,
      ) => {
        form.set('doc', chunk, basePath ? `${basePath}/${fileName}` : fileName);
        if (file.built_in_model_id)
          form.set('built_in_model_id', file.built_in_model_id);

        const response = await upload({
          url: 'datasets',
          method: type === 'EDIT_DATASET' ? 'put' : 'post',
          form,
          header:
            removeFolderName.length > 0
              ? {
                  'Content-Range': `bytes ${s}-${e}/${fileSize}`,
                  'Remove-List': removeFolderName,
                }
              : {
                  'Content-Range': `bytes ${s}-${e}/${fileSize}`,
                },
          progressCallback: (progress) => {
            if (this.progressRef.current)
              this.progressRef.current.innerText = `Files are uploading... ${progress}%`;
            for (let i = 0; i < this.progressRefs.length; i += 1) {
              if (this.progressRefs[i])
                this.progressRefs[
                  i
                ].innerText = `Files are uploading... ${progress}%`;
            }
          },
        });
        const { status, message, error } = response;
        if (status === 'STATUS_SUCCESS') {
          if (isUploadFlag === false) {
            this.props.closeModal(type);
            isUploadFlag = true;
          }
          return { status: 'STATUS_SUCCESS' };
        }
        errorToastMessage(error, message);
        for (let i = 0; i < this.progressRefs.length; i += 1) {
          if (this.progressRefs[i]) this.progressRefs[i].innerText = '';
        }
        return { status: 'STATUS_FAIL', message };
      },
    });
    this.props.addUploadInstance(uploadInstance);
    this.props.openUploadList();
    const response = uploadInstance.upload();
    if (response) {
      response.then((isUpload) => {
        if (isUpload === false) {
          this.props.deleteLastUploadInstance();
        }
      });
    }
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const {
      state,
      props,
      textInputHandler,
      selectInputHandler,
      radioBtnHandler,
      onSubmit,
      selectTemplate,
      templateFileFolderHandler,
      googleDriveHandler,
      googleAccessTokenHandler,
      timeRangeHandler,
      droneOptionHandler,
      progressRefs,
      builtInModelTmemplateHandler,
      builtInModelNamesHandler,
      builtInModelIdHandler,
    } = this;
    return (
      <DatasetFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        selectInputHandler={selectInputHandler}
        radioBtnHandler={radioBtnHandler}
        onSubmit={onSubmit}
        selectTemplate={selectTemplate}
        templateFileFolderHandler={templateFileFolderHandler}
        googleDriveHandler={googleDriveHandler}
        googleAccessTokenHandler={googleAccessTokenHandler}
        timeRangeHandler={timeRangeHandler}
        droneOptionHandler={droneOptionHandler}
        progressRefs={progressRefs}
        builtInModelTmemplateHandler={builtInModelTmemplateHandler}
        builtInModelNamesHandler={builtInModelNamesHandler}
        builtInModelIdHandler={builtInModelIdHandler}
      />
    );
  }
}

export default withTranslation()(
  connect(null, {
    closeModal,
    openConfirm,
    addUploadInstance,
    openUploadList,
    deleteLastUploadInstance,
  })(ModalContainer),
);
