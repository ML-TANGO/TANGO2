import { createRef, PureComponent } from 'react';
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

// Components
import DockerImageFormModal from '@src/components/Modal/DockerImageFormModal';

import { openConfirm } from '@src/store/modules/confirm';
// Action
import { closeModal } from '@src/store/modules/modal';
import { addUploadInstance, openUploadList } from '@src/store/modules/upload';

// Network
import { callApi, STATUS_SUCCESS, upload } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

function msToHMS(ms) {
  // 1- Convert to seconds:
  let seconds = ms / 1000;
  // 2- Extract hours:
  const hours = parseInt(seconds / 3600, 10); // 3,600 seconds in 1 hour
  seconds %= 3600; // seconds remaining after extracting hours
  // 3- Extract minutes:
  const minutes = parseInt(seconds / 60, 10); // 60 seconds in 1 minute
  // 4- Keep only seconds not extracted to minutes:
  seconds %= 60;
  return `${hours}:${minutes}:${Math.floor(seconds)}`;
}

let startTime;
let isSubmit = false;
class ModalContainer extends PureComponent {
  _isMounted = false;
  callCount = 0;
  speedAverage = 0;
  constructor(props) {
    super(props);
    this._MODE = import.meta.env.VITE_REACT_APP_MODE;
    this.state = {
      imageId: '',
      validate: false, // Create 버튼 활성/비활성 여부 상태 값
      name: '',
      nameError: null,
      imageName: '',
      imageNameError: null,
      imageDesc: '',
      imageDescError: null,
      dockerUrl: '',
      dockerUrlError: null,
      dockerTag: null,
      dockerTagError: null,
      dockerTagOptions: [],
      dockerTagNodeIp: [],
      dockerNGC: null,
      dockerNGCError: null,
      dockerNGCOptions: [],
      dockerNGCOptionsLoading: false,
      dockerNGCVersion: null,
      dockerNGCVersionError: null,
      dockerNGCVersionOptions: [],
      dockerNGCVersionOptionsLoading: false,
      // prev workspace data start
      workspace: null,
      workspaceOptions: [],
      commitComment: '',
      commitCommentError: null,
      // prev workspace data end
      // new workspace data start
      wsList: [], // 멀티 셀렉트를 위한 워크스페이스 목록 (초기값)
      prevSelectedWsList: [], // 멀티 셀렉트를 위한 선택된 워크스페이스 목록 (초기값)
      selectedWsList: [], // 멀티 셀렉트를 통해 선택된 워크스페이스 목록
      selectedWsListError: null, // 멀티 셀렉트를 통해 선택된 워크스페이스 목록
      // new workspace data end
      files: '',
      filesError: null,
      removeFiles: [],
      uploadTypeOptions: [
        {
          label: 'Pull',
          value: 1,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
        {
          label: 'Dockerfile build',
          value: 3,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
        {
          label: 'Tar',
          value: 2,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
        {
          label: 'NGC',
          value: 5,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
        {
          label: 'Commit',
          value: 6,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
      ],
      uploadType: 1,
      releaseTypeOptions: [
        {
          label: 'workspace.label',
          value: 0,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
        {
          label: 'global.label',
          value: 1,
          labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        },
      ],
      releaseType: 0,
      // callCount: 0,
      footerMessage: '',
    };
    this.progressRef = createRef();
  }
  async componentDidMount() {
    this._isMounted = true;
    document.addEventListener('keydown', this.keyboardHandler);

    const {
      type,
      data: { data: imageData },
      auth,
    } = this.props;

    const { type: userType } = auth;
    if (userType === 'ADMIN' && type === 'CREATE_DOCKER_IMAGE') {
      // 처음부터 Admin이면서 생성 시 commit버튼 안 보이게
      let { uploadTypeOptions } = this.state;
      uploadTypeOptions = uploadTypeOptions.filter(
        (option) => option.value !== 6,
      );
      this.setState({ uploadTypeOptions });
    }
    const workspaceOptions = await this.getWorkspaces();
    if (type === 'EDIT_DOCKER_IMAGE' || type === 'DUPLICATE_DOCKER_IMAGE') {
      const response = await callApi({
        url: `images/${imageData.id}`,
        method: 'GET',
      });
      const { result, status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        let {
          id: imageId,
          image_name: imageName,
          desc,
          workspace,
          type: uploadType,
          access: releaseType,
          description: imageDesc,
          file_path: dockerUrl,
          iid,
          upload_filename: uploadFileName,
        } = result;

        if (type === 'DUPLICATE_DOCKER_IMAGE') {
          imageDesc = `This is copied docker image based on (${imageName})`;
          imageName = '';
          if (uploadType === 4) {
            const { uploadTypeOptions } = this.state;
            const newUploadTypeOptions = [...uploadTypeOptions];
            if (userType !== 'ADMIN') {
              newUploadTypeOptions.push({
                label: 'Tag',
                value: 4,
                disabled: true,
              });
            }
            this.setState({ uploadTypeOptions: newUploadTypeOptions });
          }
        }

        // workspace
        const wsList = [];
        const prevSelectedWsList = [];

        for (let i = 0; i < workspaceOptions?.length; i += 1) {
          const workspaceItem = workspaceOptions[i];
          const { value } = workspaceItem;
          let flag = false;
          for (let j = 0; j < workspace?.length; j += 1) {
            const { workspace_id: workspaceId } = workspace[j];
            if (workspaceId === value) {
              flag = true;
              break;
            }
          }
          if (flag) {
            prevSelectedWsList.push(workspaceItem);
          } else {
            wsList.push(workspaceItem);
          }
        }
        // upload type disabled
        let { uploadTypeOptions } = this.state;

        const newUploadTypeOptions = [...uploadTypeOptions].map(
          ({ value, label, disabled }) =>
            value !== uploadType
              ? { label, value, disabled: true }
              : { label, value, disabled },
        );
        // if (userType === 'ADMIN') {
        //   newUploadTypeOptions.push({
        //     label: 'Tag',
        //     value: 4,
        //     disabled: uploadType !== 4 && type === 'EDIT_DOCKER_IMAGE',
        //   });
        // }
        this.setState({
          imageId,
          imageName,
          desc,
          uploadType,
          uploadTypeOptions: newUploadTypeOptions,
          releaseType: parseInt(releaseType, 10),
          imageDesc: !imageDesc ? '' : imageDesc,
          imageDescError: imageDesc ? '' : null,
          wsList,
          prevSelectedWsList,
          dockerUrl,
          dockerTag: {
            label: `${uploadFileName} [${iid}]`,
            value: { name: uploadFileName, id: iid },
          },
          files: [{ name: dockerUrl }],
        });
      } else {
        errorToastMessage(error, message);
      }
    } else {
      // Upload Docker Image
      const currentPath = window.location.pathname;
      if (!currentPath.includes('workbench')) {
        this.getNGCOptions();
      }

      const { workspaceId, dockerImage, isCommit } = this.props.data;

      const { uploadTypeOptions } = this.state;
      const newUploadTypeOptions = [...uploadTypeOptions];
      if (isCommit) {
        let imageDesc = `This is committed docker image based on (${
          dockerImage || '-'
        })`;
        this.setState({ imageDesc, uploadType: 6 });
      }
      if (userType === 'ADMIN') {
        newUploadTypeOptions.push({
          label: 'Tag',
          value: 4,
          disabled: false,
        });
        // this.getTagOptions();
      }
      if (workspaceId) {
        // workspaceId 값이 있으면 유저 페이지에서 생성
        const selectedWsList = [];
        for (let i = 0; i < workspaceOptions.length; i += 1) {
          const workspaceItem = workspaceOptions[i];
          const { value } = workspaceItem;
          if (value === parseInt(workspaceId, 10)) {
            selectedWsList.push(workspaceItem);
          }
        }

        // workspace
        const wsList = [];
        const prevSelectedWsList = [];
        for (let i = 0; i < workspaceOptions.length; i += 1) {
          const workspaceItem = workspaceOptions[i];
          const { value } = workspaceItem;
          if (parseInt(workspaceId, 10) === value) {
            prevSelectedWsList.push(workspaceItem);
          } else {
            //if (type === 'DUPLICATE_DOCKER_IMAGE')
            wsList.push(workspaceItem);
          }
        }

        this.setState({
          wsList,
          selectedWsList,
          prevSelectedWsList,
          uploadTypeOptions: newUploadTypeOptions,
        });
      } else {
        // workspaceId 값이 없으면 어드민 페이지에서 생성
        this.setState({
          wsList: workspaceOptions,
          uploadTypeOptions: newUploadTypeOptions,
        });
      }
    }
  }

  componentDidUpdate() {
    const {
      imageName,
      uploadType,
      dockerUrl,
      files,
      dockerNGC,
      dockerNGCVersion,
      releaseType,
      selectedWsList,
    } = this.state;
    const { type } = this.props;

    const validations = [
      {
        condition: !imageName,
        message: this.props.t('dockerImageName.placeholder'),
      },
      {
        condition:
          uploadType === 1 && !dockerUrl && type === 'CREATE_DOCKER_IMAGE',
        message: this.props.t('dockerImageUrl.empty.message'),
      },
      {
        condition: (uploadType === 3 || uploadType === 2) && !files.length,
        message: this.props.t('dockerImageUpload.error.message'),
      },
      {
        condition:
          uploadType === 5 && !dockerNGC && type === 'CREATE_DOCKER_IMAGE',
        message: this.props.t('dockerNgcName.error.message'),
      },
      {
        condition:
          uploadType === 5 &&
          !dockerNGCVersion &&
          type === 'CREATE_DOCKER_IMAGE',
        message: this.props.t('dockerNgcVersion.error.message'),
      },
      {
        condition: releaseType === 0 && !selectedWsList.length,
        message: this.props.t('workspaceSelectedList.empty.message'),
      },
    ];

    for (let validation of validations) {
      if (validation.condition) {
        this.setState({ footerMessage: validation.message });
        return;
      }
    }

    this.setState({ footerMessage: '' });
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  /** ================================================================================
   * API START
   ================================================================================ */

  // 워크스페이스 목록 조회
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

  // 어드민 전용 Tag 목록 조회 및 세팅
  // getTagOptions = async () => {
  //   const response = await callApi({
  //     url: 'images/tag',
  //     method: 'GET',
  //   });

  //   const { status, result, message, error } = response;
  //   if (status === STATUS_SUCCESS) {
  //     const dockerTagOptions = result.map(({ name, id, node_ip: nodeIP }) => {
  //       return {
  //         label: `${name} [${id} | ${nodeIP}]`,
  //         value: { name, id },
  //       };
  //     });
  //     this.setState({ dockerTagOptions });
  //     this.setState({ dockerTagNodeIp: result });
  //   } else {
  //     errorToastMessage(error, message);
  //   }
  // };

  // NGC Tag 이름 목록 조회 및 세팅
  getNGCOptions = async () => {
    this.setState({
      dockerNGCError: 'dockerNGC.loading.message',
      dockerNGCOptionsLoading: true,
    });
    const response = await callApi({
      url: 'images/ngc',
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const dockerNGCOptions = result.map(
        ({ name, publisher, ngc_image_name: ngcImageName }) => ({
          label: `[${publisher}] ${name}`,
          value: ngcImageName,
        }),
      );
      this.setState({
        dockerNGCOptions,
        dockerNGCError: '',
        dockerNGCOptionsLoading: false,
      });
    } else {
      this.setState({ dockerNGCError: 'dockerNGC.erorr.message' });
      errorToastMessage(error, message);
    }
  };

  // NGC Tag 버전 목록 조회
  getNGCVersionOptions = async (imageName) => {
    this.setState({
      dockerNGCVersionError: 'dockerNGCVersion.loading.message',
      dockerNGCVersionOptionsLoading: true,
    });
    const response = await callApi({
      url: `images/ngc/tags?ngc_image_name=${imageName}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const options = result.map(({ url, tag }) => ({
        label: tag,
        value: url,
      }));
      this.setState({
        dockerNGCVersionError: '',
        dockerNGCVersionOptionsLoading: false,
      });
      return options;
    }
    this.setState({ dockerNGCVersionError: 'dockerNGCVersion.erorr.message' });
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
    } else if (name === 'imageDesc' && value.trim() === '') {
      newState[`${name}Error`] = null;
    } else {
      newState[`${name}Error`] = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 인풋 파일 이벤트 핸들러
  fileInputHandler = (newFiles) => {
    // const { files: prevFiles } = this.state;
    // const files = [...prevFiles, ...newFiles];
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

  // 셀렉트 인풋 핸들러
  selectInputHandler = (name, value) => {
    this.setState(
      {
        [name]: value,
        [`${name}Error`]: '',
      },
      async () => {
        if (name === 'dockerNGC') {
          const { dockerNGC } = this.state;
          this.setState(
            {
              dockerNGCVersion: null,
              dockerUrl: '',
              dockerNGCError: '',
              dockerNGCVersionOptions: [],
              dockerNGCVersionError: null,
            },
            () => {
              this.submitBtnCheck();
            },
          );
          const versionOptions = await this.getNGCVersionOptions(
            dockerNGC.value,
          );
          this.setState({ dockerNGCVersionOptions: versionOptions });
        } else if (name === 'dockerNGCVersion') {
          const { dockerNGCVersion } = this.state;
          this.setState(
            {
              dockerUrl: dockerNGCVersion.value,
              dockerUrlError: '',
            },
            () => {
              this.submitBtnCheck();
            },
          );
        }
        this.submitBtnCheck();
      },
    );
  };

  // 인풋 파일 삭제 이벤트 핸들러
  onRemove = (idx, isPrev) => {
    const { files } = this.state;
    const newFiles = [
      ...files.slice(0, idx),
      ...files.slice(idx + 1, files.length),
    ];
    const newState = {
      files: newFiles,
      filesError: null,
      removeFiles: [],
    };
    if (isPrev) {
      newState.removeFiles.push(files[idx].name);
    }
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

  // 라디오 버튼 이벤트 핸들러
  radioBtnHandler = (name, value) => {
    this.setState({
      [name]: parseInt(value, 10),
    });
    if (value === '1' && name === 'releaseType') {
      // 공개 범위에서 전체를 누를 때 여기로 들어옵니다
      this.setState({ releaseType: 1, selectedWsListError: '' }, () =>
        this.submitBtnCheck(),
      );
    }

    if (name === 'uploadType') {
      let newState = {
        dockerUrl: '',
        dockerUrlError: null,
        dockerNGC: null,
        dockerNGCVersion: null,
        dockerNGCVersionOptions: [],
        files: [],
        filesError: null,
        dockerTag: null,
        dockerTagError: null,
      };
      // 변경될 때 기존 값 초기화
      const val = parseInt(value, 10);
      if (val === 1) {
        this.setState({ dockerUrl: '', dockerUrlError: null });
      } else if (val === 2 || val === 3) {
        this.setState({ files: [], filesError: null });
      } else if (val === 5) {
        if (!this.state.dockerNGCOptionsLoading) {
          newState.dockerNGCError = '';
        }
        this.setState(newState);
      } else if (val === 4) {
        this.setState({ dockerTag: null, dockerTagError: null });
      }
      this.setState(newState, () => this.submitBtnCheck()); // * 그냥 모든 상태 초기화
    }

    this.submitBtnCheck(); // * 생성버튼 활성화 비활성화 함수
  };

  // 멀티 셀렉트 이벤트 핸들러
  multiSelectHandler = ({ selectedList: selectedWsList }) => {
    const validate = this.validate('selectedWsList', selectedWsList);
    const newState = {
      selectedWsList,
      selectedWsListError: !validate ? '' : validate,
    };
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'imageName') {
      // const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;
      const regType = !forbiddenChars.test(value);
      if (value === '') {
        return 'dockerImageName.empty.message';
      }
      if (!regType) {
        return 'newNameRule.message';
      }
    } else if (name === 'files') {
      if (value.length === 0) {
        return 'file.empty.message';
      }
    } else if (name === 'dockerUrl') {
      const regType1 = /^[A-Za-z0-9./:_-]*$/;
      if (value.length === 0) {
        return 'dockerImageUrl.empty.message';
      }
      if (!regType1.test(value)) {
        return 'dockerImageUrl.erorr.message';
      }
    } else if (name === 'selectedWsList') {
      if (value.length === 0) {
        return 'workspaceSelectedList.empty.message';
      }
    }
    return null;
  };

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성

    const { state, props } = this;
    const stateKeys = Object.keys(state);
    let validateCount = 0;

    // 업로드 타입 일 경우에는 uploadType에 따라 validateCount를 증가시킨다.
    if (props.type === 'DUPLICATE_DOCKER_IMAGE') {
      if (state.imageName === '') {
        // 에러 길이로
        validateCount += 1;
      }
    }
    if (props.type === 'CREATE_DOCKER_IMAGE') {
      if (state.uploadType === 4) {
        if (state.dockerTag === null || state.imageName === '')
          validateCount += 1;
      }

      for (let i = 0; i < stateKeys.length; i += 1) {
        const key = stateKeys[i];
        if (
          state.uploadType === 6 &&
          key === 'imageNameError' &&
          state[key] !== ''
        ) {
          validateCount += 1;
        }
        if (
          state.uploadType === 1 &&
          (key === 'imageNameError' || key === 'dockerUrlError')
        ) {
          if (state[key] !== '') {
            validateCount += 1;
          }
        } else if (
          (state.uploadType === 2 || state.uploadType === 3) &&
          (key === 'imageNameError' || key === 'filesError')
        ) {
          if (state[key] !== '') {
            validateCount += 1;
          }
        } else if (
          state.uploadType === 5 &&
          (key === 'imageNameError' ||
            key === 'dockerNGCError' ||
            key === 'dockerNGCVersionError' ||
            key === 'dockerUrlError')
        ) {
          if (state[key] !== '') {
            validateCount += 1;
          }
        }
      }
    }

    const { selectedWsList, releaseType } = state;

    // 유저가 ReleaseType을 Workspace로 두고 생성할 시 validate.
    if (selectedWsList.length === 0 && releaseType === 0) {
      validateCount += 1;
    }

    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
  };

  keyboardHandler = (event) => {
    const { type } = this.props;
    if (event.keyCode === 27) {
      this.props.closeModal(type);
    }
  };

  // submit 버튼 클릭 이벤트
  onSubmit = async (callback) => {
    const { type } = this.props;
    let method = 'POST';
    const {
      imageId,
      imageName,
      imageDesc,
      uploadType,
      dockerTag,
      releaseType,
      dockerUrl,
      files: doc,
      selectedWsList,
      commitComment,
    } = this.state;
    if (isSubmit) return;
    isSubmit = true;

    // 업로드 중 생성 버튼 비활성화
    const validateState = { validate: false };
    this.setState(validateState);

    if (
      (uploadType === 3 || uploadType === 2) &&
      type !== 'DUPLICATE_DOCKER_IMAGE'
    ) {
      // Dockerfile build, Tar 수정
      startTime = new Date().getTime();
      if (
        (type === 'CREATE_DOCKER_IMAGE' && uploadType === 2) ||
        uploadType === 3
      ) {
        const fileSize = doc[0].size;
        const chunkSize = 1024 * 1024 * 20;
        this.uploadTarFile(fileSize, chunkSize, callback);
      } else {
        this.splitUpload(callback);
      }
      isSubmit = false;
      return;
    }
    let url = 'images';
    let body = {};
    let value = [];
    const form = new FormData();
    let response;

    for (let i = 0; i < selectedWsList.length; i += 1) {
      value.push(selectedWsList[i].value);
      form.append('workspace_id_list', selectedWsList[i].value); // 리스트로 변경
    }
    form.append('image_name', imageName);
    form.append('access', releaseType);
    form.append('description', imageDesc);
    if (type === 'EDIT_DOCKER_IMAGE') {
      // 도커이미지 수정
      method = 'PUT';
      body.image_id = imageId;
      body.workspace_id_list = value;
      body.image_name = imageName;
      body.access = releaseType;
      body.description = imageDesc;
      response = await callApi({
        url,
        method,
        body,
        progressCallback: (progress) => {
          if (this.progressRef.current) {
            this.progressRef.current.innerText = `Files are uploading...${progress} % `;
          }
        },
      });
    } else if (type === 'CREATE_DOCKER_IMAGE') {
      // 도커이미지 생성
      body.workspace_id = value;
      if (uploadType === 1) {
        url += '/pull';
        form.append('url', dockerUrl);
      } else if (uploadType === 4) {
        let nodeIpArr = this.state.dockerTagNodeIp.filter(
          (item) => item.name === dockerTag?.value?.name,
        );
        const nodeIp = nodeIpArr[0]?.node_ip;
        url += '/tag';
        form.append('node_ip', nodeIp);
        form.append('selected_image_id', dockerTag.value.id);
        form.append('selected_image_name', dockerTag.value.name);
      } else if (uploadType === 5) {
        url += '/ngc';
        form.append('selected_image_url', dockerUrl);
      } else if (uploadType === 6) {
        url += '/commit';
        form.append('training_tool_id', this.props.data.toolId);
        form.append('message', commitComment);
      }

      response = await upload({
        url,
        method,
        form,
        progressCallback: (progress) => {
          if (this.progressRef.current) {
            this.progressRef.current.innerText = `Files are uploading...${progress} % `;
          }
        },
      });
    } else if (type === 'DUPLICATE_DOCKER_IMAGE') {
      url += '/copy';
      form.append('image_id', imageId);
      response = await upload({
        url,
        method,
        form,
        progressCallback: (progress) => {
          if (this.progressRef.current) {
            this.progressRef.current.innerText = `Files are uploading...${progress} % `;
          }
        },
      });
    }
    const { status, message, error } = response;
    if (
      status === STATUS_SUCCESS ||
      (status === STATUS_SUCCESS && uploadType !== 2)
    ) {
      this.props.closeModal(type);
      if (callback) callback();
      if (type === 'CREATE_DOCKER_IMAGE') {
        console.log('CREATE_DOCKER_IMAGE_SUCCESS');
      } else {
        console.log('UPDATE_DOCKER_IMAGE_SUCCESS');
      }
    } else {
      errorToastMessage(error, message);
    }
    isSubmit = false;
  };

  // 분할 업로드
  splitUpload = async (callback) => {
    // Dockerfile build랑 tar 업로드 및 수정
    const { type } = this.props;
    const {
      imageName,
      imageDesc,
      uploadType,
      releaseType,
      files: doc,
      selectedWsList,
      imageId,
    } = this.state;

    let url = 'images';
    let method = 'PUT';
    let body = {
      image_id: imageId,
      image_name: imageName,
      description: imageDesc,
      access: releaseType,
    };
    let response;
    if (type === 'CREATE_DOCKER_IMAGE') {
      method = 'POST';
      const form = new FormData();
      form.append('image_name', imageName);
      form.append('access', releaseType);
      form.append('description', imageDesc);
      for (let i = 0; i < selectedWsList.length; i += 1) {
        const { value } = selectedWsList[i];
        form.append('workspace_id_list', value); // list로 변경
      }
      if (uploadType === 3) {
        url += '/build';
        form.append('file', doc[0]);
      }
      response = await upload({
        url,
        method,
        form,
        progressCallback: (progress) => {
          if (this.progressRef.current) {
            this.progressRef.current.innerText = `Files are uploading...${progress} % `;
          }
        },
      });
    } else if (type === 'EDIT_DOCKER_IMAGE') {
      let bucket = [];
      for (let i = 0; i < selectedWsList.length; i += 1) {
        bucket.push(selectedWsList[i].value);
      }

      body.workspace_id_list = bucket;
      response = await callApi({
        url,
        method,
        body,
      });
    }
    const { status, message, error } = response;
    if (
      status === STATUS_SUCCESS ||
      (status === STATUS_SUCCESS && uploadType !== 2)
    ) {
      this.props.closeModal(type);
      if (callback) callback();
    } else {
      errorToastMessage(error, message);
    }
    isSubmit = false;
  };

  uploadFile = async (url, form, fileSize, endSize, chunkSize) => {
    const response = await upload({
      url,
      method: 'POST',
      form,
    });

    return response;
  };

  uploadInfo = (fileSize, sTime, chunkSize) => {
    const eTime = new Date().getTime();
    const progress = Math.floor(
      ((chunkSize * this.callCount) / fileSize) * 100,
    );
    if (this.progressRef.current) {
      const uploadedSize = (chunkSize * this.callCount) / (1024 * 1024);
      let speedTime = 0;
      if (eTime - startTime === 0) speedTime = 1;
      else speedTime = eTime - sTime;
      const speed = chunkSize / 1024 / speedTime;
      this.speedAverage += speed;
      const averageSpeed = this.speedAverage / this.callCount;
      const t = msToHMS(
        ((fileSize - uploadedSize * 1024 * 1024) /
          (1024 * 1024) /
          averageSpeed) *
          1000,
      );
      const progressTime = msToHMS(eTime - startTime);
      let dotProgress = '';
      const dotFlag = this.callCount % 3;
      if (dotFlag === 0) dotProgress = '.';
      else if (dotFlag === 1) dotProgress = '..';
      else if (dotFlag === 2) dotProgress = '...';

      this.progressRef.current.innerHTML = `<p style = 'font-size: 12px;'> Files are uploading${dotProgress}</p> `;
      this.progressRef.current.innerHTML += `<p style = 'font-size: 12px;'> Size : ${uploadedSize}MB / ${Math.floor(
        fileSize / (1024 * 1024),
      )}MB(${progress} %)</p> `;
      this.progressRef.current.innerHTML += `<p style = 'font-size: 12px;'> Speed : ${Math.floor(
        speed,
      )}MB / s</p> `;
      this.progressRef.current.innerHTML += `<p style = 'font-size: 12px;'> Average speed : ${Math.floor(
        averageSpeed,
      )}MB / s</p> `;
      this.progressRef.current.innerHTML += `<p style = 'font-size: 12px;'> Remaining time : ${t}</p> `;
      this.progressRef.current.innerHTML += `<p style = 'font-size: 12px;'> Progress time : ${progressTime}</p> `;
    }
  };

  uploadFormData = async (
    url,
    makeForm,
    file,
    chunkSize,
    count,
    fileName,
    callback,
    chunk_file_name,
  ) => {
    const { type } = this.props;
    const form = makeForm();
    const fileSize = file.size;
    const start = chunkSize * this.callCount;
    const sTime = new Date().getTime();
    let end = chunkSize * (this.callCount + 1);
    this.callCount += 1;
    if (end >= fileSize) {
      form.append('end_of_file', true);
      end = fileSize;
      form.append('file', file.slice(start, end), fileName);
      form.append('chunk_file_name', chunk_file_name);

      const response = await this.uploadFile(
        url,
        form,
        fileSize,
        end,
        chunkSize,
      );
      const { status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        if (chunkSize * this.callCount > fileSize) {
          isSubmit = false;
          if (callback) callback();

          this.props.closeModal(type);
          return;
        }
      } else {
        errorToastMessage(error, message);
        isSubmit = false;
      }
      return;
    }

    form.append('file', file.slice(start, end), fileName);
    if (count !== 0) {
      form.append('chunk_file_name', chunk_file_name);
    }
    const response = await this.uploadFile(url, form, fileSize, end, chunkSize);
    this.uploadInfo(fileSize, sTime, chunkSize);

    const { chunk_file_name: _chunk_file_name } = response.result;

    this.uploadFormData(
      url,
      makeForm,
      file,
      chunkSize,
      this.callCount,
      fileName,
      callback,
      _chunk_file_name,
    );
  };

  uploadTarFile = (fileSize, chunkSize, callback) => {
    const {
      imageName,
      imageDesc,
      uploadType,
      releaseType,
      files: doc,
      selectedWsList,
    } = this.state;
    let url = 'images/';
    if (uploadType === 3) {
      url += 'build';
    } else if (uploadType === 2) {
      url += 'tar';
    } else {
      return;
    }

    // form 객체가 데이터를 쌓지 않도록 함수를 통해 form 객체를 새로 생성
    const makeFormData = () => {
      const form = new FormData();
      if (uploadType === 3) {
        // Tar 타입
        // url += 'build';
        // form.append('file', doc[0]);
      } else if (uploadType === 2) {
        // Dockerfile build 타입
        // url += 'tar';
      }
      form.append('image_name', imageName);
      form.append('access', releaseType);
      form.append('description', imageDesc);
      for (let i = 0; i < selectedWsList.length; i += 1) {
        const { value } = selectedWsList[i];
        form.append('workspace_id_list', value);
      }
      return form;
    };
    this.uploadFormData(
      url,
      makeFormData,
      doc[0],
      chunkSize,
      0,
      doc[0].name,
      callback,
    );
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const {
      state,
      props,
      textInputHandler,
      fileInputHandler,
      selectInputHandler,
      radioBtnHandler,
      multiSelectHandler,
      onSubmit,
      onRemove,
      progressRef,
    } = this;
    return (
      <DockerImageFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        fileInputHandler={fileInputHandler}
        selectInputHandler={selectInputHandler}
        radioBtnHandler={radioBtnHandler}
        multiSelectHandler={multiSelectHandler}
        onSubmit={onSubmit}
        onRemove={onRemove}
        progressRef={progressRef}
        isCommit={props.data.isCommit}
      />
    );
  }
}

export default connect(({ auth }) => ({ auth }), {
  closeModal,
  openConfirm,
  addUploadInstance,
  openUploadList,
})(withTranslation()(ModalContainer));
