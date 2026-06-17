// Utils
import { PureComponent } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';

import Hangul from '@src/koreaUtils';

// Components
import TrainingFormModal from '@src/components/Modal/TrainingFormModal';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

// 연합 학습 유무
const IS_FL = import.meta.env.VITE_REACT_APP_IS_FEDERATED_LEARNING === 'true';

class TrainingFormModalContainer extends PureComponent {
  _MODE = import.meta.env.VITE_REACT_APP_MODE;
  // 드론 챌린지 모드 여부
  _IS_DNADRONECHALLENGE =
    import.meta.env.VITE_REACT_APP_SERVICE_LOGO === 'DNA+DRONE' &&
    import.meta.env.VITE_REACT_APP_IS_CHALLENGE === 'true';

  state = {
    validate: false, // 모달의 submit 버튼 활성/비활성 여부 상태 값
    trainingId: '', // Training id 값
    // trainingType: this._IS_DNADRONECHALLENGE ? 'advanced' : 'built-in', // Training Type
    trainingType: this._IS_DNADRONECHALLENGE ? 'advanced' : 'built-in', // Training Type
    trainingTypeOptions: [
      {
        label: 'Built-in',
        value: 'built-in',
        disabled: this._IS_DNADRONECHALLENGE,
      },
      {
        label: 'Custom',
        value: 'advanced',
      },
    ], // Training Type 선택 옵션
    trainingName: '', // Training Name 값
    trainingNameError: null, // Training Name 인풋 에러 텍스트
    trainingDesc: '', // Training Description 값
    trainingDescError: null, // Training Description 인풋 에러 텍스트
    workspace: null, // 선택한 Workspace 값
    workspaceOptions: [], // Workspace 선택 옵션
    builtInFilterOptions: [],
    builtInFilter: null,
    builtInModelOptions: [], // Built-in TrainingPage 선택 옵션
    builtInModelSearchResult: null, // Built-in TrainingPage 검색 데이터
    builtInModel: null, // Built-in TrainingPage 값
    modelTypeValue: 0,
    selectedCategory: { name: '', value: null },
    selectedModel: { name: '', value: null },

    huggingFaceToken: '',
    selectedHuggingFaceModel: { name: '', url: null },

    instanceModels: [], // ? new
    gpuUsage: '', // 사용할 GPU(GPU usage) 수 값
    modelType: 0, // cpu or gpu 선택 값
    maxGpuUsageCountForRandom: 0, // 사용 가능한 GPU 수 (GPU 모델 랜덤)
    gpuTotalCountForRandom: 0, // 모든 GPU 수 (GPU 모델 랜덤)
    maxGpuUsageCount: 0, // 사용 가능한 GPU 수
    minGpuUsage: 0, // 반드시 사용해야할 최소 GPU 수
    maxGpuUsage: 10000, // 반드시 넘으면 안되는 최대 GPU 수
    gpuTotalCount: 0, // 모든 GPU 수
    isGuranteedGpu: false, // GPU 보장 여부
    dockerImage: null, // 선택한 Docker Image 값
    dockerImageOptions: [], // DOcker Image 옵션
    gpuModelTypeOptions: [
      { label: 'random.label', value: 0 },
      { label: 'specificModel.label', value: 1 },
    ],
    cpuModelTypeOptions: [
      { label: 'random.label', value: 0 },
      { label: 'specificModel.label', value: 1 },
    ],
    modelTypeOptions: [
      {
        label: 'gpuModel.label',
        value: 0,
      },
      { label: 'cpuModel.label', value: 1 },
    ],
    // config의 옵션으로 모델 특정 기능을 숨기는 경우, 디폴트 값이 반드시 무작위가 되어야 하므로,
    // 아래 디폴트 값 0(무작위)을 1(모델 특정)로 바꾸면 안됨
    gpuModelType: 0,
    cpuModelType: 0,
    gpuModelListOptions: [], // GPU 모델 선택 옵션
    gpuModelList: null, // 선택한 GPU 모델 리스트
    cpuModelList: [], // 선택한 CPU 모델 리스트 (노드)
    cpuModelInfo: [],
    gpuModelInfo: [],
    resourceTypeReadOnly: false,
    isMigModel: false, // 선택한 gpu model 리스트에 MIG 모델 포함 여부
    accessTypeOptions: [
      // Access Type 선택 옵션
      { label: 'Public', value: 1 },
      { label: 'Private', value: 0 },
    ],
    accessType: 1, // 선택한 Access Type 값
    trainingStatus: '',
    ownerOptions: [], // Owner 선택 옵션
    owner: null, // 선택한 Owner 값
    userList: [], // 유저 멀티 선택 옵션
    selectedList: [], // 선택된 유저 값
    tmpSelectedList: [],
    thumbnailList: [],
    permissionLevel: -1,
    //* slider 관련 state
    //gpu
    gpuSliderSwitch: false,
    gpuSelectedOptions: [],
    gpuInputValues: [],
    prevGpuSelectedOptions: [],
    gpuDetailSelectedOptions: [],
    gpuTotalValue: 1,
    gpuRamTotalValue: 1,
    gpuDetailValue: 1,
    gpuRamDetailValue: 1,
    gpuTotalSliderMove: false,
    gpuSwitchStatus: false,
    gpuAndRamSliderValue: {
      cpu: 1,
      ram: 1,
    },
    //cpu
    sliderSwitchStatus: false,
    cpuSwitchStatus: false,
    cpuSliderMove: false,
    cpuSelectedOptions: [],
    detailSelectedOptions: [],
    cpuTotalValue: 1,
    ramTotalValue: 1,
    cpuDetailValue: 1,
    ramDetailValue: 1,
    totalSliderMove: false,
    cpuAndRamSliderValue: {
      cpu: 1,
      ram: 1,
    },
    // footerMessage
    footerMessage: '',
  };

  async componentDidMount() {
    let newState = {};

    let {
      type,
      data: { data: trainingData },
    } = this.props;

    let currentWorkspaceId = this.props.data.workspaceId;

    // 워크스페이스 설정
    if (this.props.data.workspaceId) {
      // 유저 페이지에서 프로젝트 생성
      newState.workspace = { value: this.props.data.workspaceId };
    } else {
      // 어드민 페이지에서 프로젝트 생성
      const { workspaceListInfo } = await this.getAdminTrainingInfo();
      // workspace 목록 조회
      if (workspaceListInfo) {
        newState.workspaceOptions = workspaceListInfo.map(({ id, name }) => ({
          label: name,
          value: id,
        }));
      }
    }

    if (type === 'EDIT_TRAINING') {
      const response = await callApi({
        url: `projects/update-option?workspace_id=${currentWorkspaceId}&project_id=${trainingData.id}`,
        method: 'get',
      });

      const { result, status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        const {
          gpu_model: gpuModel,
          docker_image_list: dockerImageListInfo,
          permission_level: permissionLevel,
          project_info: projectInfo,
          instances: instanceModels,
          user_list: userListInfo,
        } = result;

        const newInstances = [];

        if (instanceModels && instanceModels.length > 0) {
          instanceModels.forEach((v, i) => {
            newInstances.push({
              cpu: v?.cpu_allocate,
              gpu: v?.gpu_allocate,
              ram: v?.ram_allocate,
              id: v?.instance_id,
              name: v?.instance_name,
              total: v?.instance_allocate,
              groupId: v?.gpu_resource_group_id,
            });
          });
        }

        let selectedOptions = [];
        let initialInputValues = [];
        if (newInstances.length > 0) {
          const initialValues = this.gpuGetHandler(newInstances);
          selectedOptions.push(...initialValues.selectedOptions);
          initialInputValues.push(...initialValues.initialInputValues);
        }
        // id 값으로 필요한 이름 찾기 workspace, owner, dockerImage

        const {
          id: trainingId,
          type: trainingType,
          name: trainingName,
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          image_id: dockerImageId,
          image_name: dockerImageName,
          instance_allocate: instanceAllocate,
          instance_id: instanceId,
          description: trainingDesc,
          access: accessType,

          status: trainingStatus,
        } = trainingData;

        let selectedList = [];

        const selectedUsers = projectInfo?.secreted_user;

        if (selectedUsers && selectedUsers.length > 0) {
          selectedList = selectedUsers.map(
            ({ user_name: label, id: value }) => ({
              label,
              value,
            }),
          );
        }

        const { userList, ownerOptions } = this.parseStateData({
          userListInfo,
          selectedListInfo: selectedList,
        });
        newState.userList = userList;
        newState.ownerOptions = ownerOptions;

        if (newInstances.length > 0) {
          // 초기 input value값 넣기
          this.setState(
            {
              gpuSelectedOptions: selectedOptions,
              gpuInputValues: initialInputValues,
            },
            () => {
              newInstances.forEach((v, i) => {
                if (instanceId === v.id) {
                  this.checkboxHandler({
                    idx: i,
                    flag: true,
                    initialValue: selectedOptions,
                  });

                  this.onChangeGpuInputValue({
                    idx: i,
                    value: instanceAllocate,
                    initialValue: initialInputValues,
                  });
                }
              });
            },
          );
        }

        const {
          create_user_id: ownerId,
          create_user_name: ownerName,
          category,
          huggingface_model_id,
          huggingface_token,
          built_in_model,
        } = projectInfo;

        currentWorkspaceId = workspaceId;
        const workspace = { label: workspaceName, value: workspaceId };
        const dockerImage = { label: dockerImageName, value: dockerImageId };
        const owner = { label: ownerName, value: ownerId };

        const calType = (category, built_in_model) => {
          if (!category) return 0;
          if (category && built_in_model) return 1;
          return 2;
        };
        const modelTypeValue = calType(category, built_in_model);

        newState = {
          ...newState,
          // ...gpuState,
          // cpuModelList,
          modelTypeValue,
          selectedCategory: {
            name: category,
            value: category,
          },
          selectedModel: {
            name: built_in_model,
            value: built_in_model,
          },
          huggingFaceToken: huggingface_token,
          selectedHuggingFaceModel: {
            name: huggingface_model_id,
            url: huggingface_model_id,
          },
          trainingId,
          trainingName,
          trainingNameError: '',
          trainingType,
          workspace,
          trainingDesc: !trainingDesc ? '' : trainingDesc,
          trainingDescError: trainingDesc ? '' : null,
          gpuModelType: gpuModel ? 1 : 0,
          dockerImage,
          owner,
          instanceModels: newInstances,
          selectedList,
          accessType,
          trainingStatus,
          permissionLevel,
          ...this.parseStateData({
            dockerImageListInfo,
          }),
        };
      } else {
        errorToastMessage(error, message);
      }
    } else if (type === 'CREATE_TRAINING') {
      // Training 옵션 정보 조회
      const {
        builtInModelListInfo,
        dockerImageListInfo,
        thumbnailList,
        gpuStatusInfo,
        gpuModelStatusInfo,
        cpuModelStatusInfo,
        userListInfo = [],
        builtInFilterListInfo,
        instanceModels,
      } = await this.getTrainingInfo(currentWorkspaceId);

      // 컴포넌트 state에 맞게 데이터 파싱
      newState = {
        ...newState,
        cpuModelInfo: cpuModelStatusInfo,
        gpuModelInfo: gpuModelStatusInfo,
        thumbnailList,
        instanceModels,
        builtInFilter: { label: 'all.label', value: 'all' },
        ...this.parseStateData({
          builtInModelListInfo,
          dockerImageListInfo,
          gpuStatusInfo,
          gpuModelStatusInfo,
          builtInFilterListInfo,
        }),
      };
      let selectedList = [];

      this.gpuGetHandler(instanceModels);
      const loginUserName = sessionStorage.getItem('user_name');
      const ownerTmp = userListInfo.filter(
        ({ name }) => name === loginUserName,
      );

      if (ownerTmp.length === 1) {
        const owner = { label: ownerTmp[0].name, value: ownerTmp[0].id };
        newState.owner = owner;
      }

      // jay park

      const { userList, ownerOptions } = this.parseStateData({
        userListInfo,
        selectedListInfo: selectedList,
      });
      newState.userList = userList;
      newState.ownerOptions = ownerOptions;
    }

    // 연합 학습 유무에 따라 학습 유형 변경
    if (IS_FL) {
      let newTraningTypeOptions = this.state.trainingTypeOptions;
      newTraningTypeOptions.splice(1, 0, {
        label: 'builtInFederatedLearning.label',
        value: 'federated-learning',
      });
      newState.trainingTypeOptions = newTraningTypeOptions;
    }
    this.setState(newState);
  }

  componentDidUpdate() {
    const {
      trainingName,
      dockerImage,
      gpuSelectedOptions,
      gpuInputValues,
      modelTypeValue,
      selectedCategory,
      selectedModel,
      selectedHuggingFaceModel,
    } = this.state;

    if (!trainingName) {
      this.setState({
        footerMessage: `${this.props.t('trainingName.placeholder')}`,
      });
      return;
    }

    if (trainingName) {
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

      const regType = !forbiddenChars.test(trainingName);
      if (!regType) {
        this.setState({
          footerMessage: `${this.props.t('newNameRule.message')}`,
        });
        return;
      }
    }

    if (gpuSelectedOptions.length > 0) {
      const gpuValidate = this.checkGpuInputValues(
        gpuSelectedOptions,
        gpuInputValues,
      );
      if (!gpuValidate) {
        this.setState({
          footerMessage: `${this.props.t('trainingInstance.error.message')}`,
        });
        return;
      }
    }

    if (modelTypeValue > 0) {
      if (!selectedCategory.value) {
        this.setState({
          footerMessage: '카테고리를 선택해 주세요.',
        });
        return;
      }
    }

    if (modelTypeValue === 1) {
      if (!selectedModel.value) {
        this.setState({
          footerMessage: '모델을 선택해 주세요.',
        });
        return;
      }
    }

    if (modelTypeValue === 2) {
      if (!selectedHuggingFaceModel.url) {
        this.setState({
          footerMessage: '모델을 선택해 주세요.',
        });
        return;
      }
    }

    this.setState({ footerMessage: '' });
  }

  // cpu get
  cpuGetHandler = (cpuModelStatusInfo = []) => {
    const newState = {};
    // cpu 기본 state 깔기
    if (cpuModelStatusInfo?.length > 0) {
      let selectedOptions = [];
      let detailSelectedOption = [];
      let selectedItemBucket = [];
      let nodeObj = {};
      const cpuObj = {};
      const ramObj = {};
      let cpuPerPod = 1;
      let ramPerPod = 1;
      cpuModelStatusInfo.forEach(({ node_list: nodeList }, idx) => {
        nodeObj = {};
        selectedItemBucket = [];
        selectedOptions.push({ [idx]: false });
        if (nodeList?.length > 0) {
          nodeList.forEach(({ resource_info }) => {
            selectedItemBucket.push(false);
            const {
              cpu_cores_limit_per_pod: cpuPod,
              ram_limit_per_pod: ramPod,
            } = resource_info;

            if (cpuPerPod < cpuPod) {
              cpuPerPod = cpuPod;
            }

            if (ramPerPod < ramPod) {
              ramPerPod = ramPod;
            }
          });

          newState.cpuAndRamSliderValue = { cpu: cpuPerPod, ram: ramPerPod };

          nodeList.forEach((v, i) => (nodeObj[i] = 1)); //최솟값 넣기

          detailSelectedOption.push({ [idx]: selectedItemBucket });
          cpuObj[idx] = nodeObj;
          ramObj[idx] = nodeObj;
        }
      });
      newState.cpuDetailValue = cpuObj;
      newState.ramDetailValue = ramObj;
      newState.cpuSelectedOptions = selectedOptions;
      newState.detailSelectedOptions = detailSelectedOption;
    }

    return newState;
  };

  onChangeGpuInputValue = ({ idx, value, initialValue = [] }) => {
    const { state } = this;

    const { gpuInputValues: instanceValues } = state;

    const newState = {};

    const instanceValue = [];

    if (instanceValues.length === 0) {
      instanceValue.push(...initialValue);
    } else {
      instanceValue.push(...instanceValues);
    }

    this.checkboxHandler({ idx, flag: !!value });

    const newGpuInputValue = instanceValue.map((v, index) => {
      return index === idx ? value : '';
    });

    newState.gpuInputValues = newGpuInputValue;

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  totalValueHandler = (v, option, type) => {
    if (v === 0 || v < 0) {
      v = 1;
    }
    const newState = {};
    newState.gpuTotalValue = v;

    this.setState(newState);
    this.totalValueChange(v, option, type);
  };

  /** ================================================================================
   * API START
   ================================================================================ */

  // Training Options 가져오기, workspaceId가 없으면 빈 Info들을 반환
  getTrainingInfo = async (workspaceId) => {
    if (!workspaceId) {
      return {
        builtInModelListInfo: [],
        dockerImageListInfo: [],
        gpuStatusInfo: { gpuTotal: 0, gpuFree: 0 },
        gpuModelStatusInfo: [],
        cpuModelStatusInfo: [],
        userListInfo: [],
      };
    }

    const response = await callApi({
      url: `projects/option?workspace_id=${workspaceId}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status !== STATUS_SUCCESS) {
      errorToastMessage(error, message);
      return {};
    }

    const {
      built_in_model_kind_list: builtInFilterListInfo,
      built_in_model_list: builtInModelListInfo,
      built_in_model_thumbnail_image_info: thumbnailList,
      docker_image_list: dockerImageListInfo,
      gpu_usage_status: gpuUsageStatus,
      gpu_model_status: gpuModelStatus,
      cpu_model_status: cpuModelStatus,
      instances,
      user_list: userListInfo,
      // gpu_resource_status: gpuModels,
    } = result;

    const newInstances = [];

    if (instances && instances.length > 0) {
      instances.forEach((v, i) => {
        newInstances.push({
          cpu: v?.cpu_allocate,
          gpu: v?.gpu_allocate,
          groupId: v?.gpu_resource_group_id,
          id: v?.instance_id,
          total: v?.instance_allocate,
          ram: v?.ram_allocate,
          name: v?.instance_name,
        });
      });
    }

    const gpuStatusInfo = gpuUsageStatus
      ? {
          gpuTotal: gpuUsageStatus.total_gpu,
          gpuFree: gpuUsageStatus.free_gpu,
          isGuranteedGpu: gpuUsageStatus.guaranteed_gpu === 1,
        }
      : { gpuTotal: 0, gpuFree: 0 };
    return {
      builtInModelListInfo: builtInModelListInfo || [],
      dockerImageListInfo: dockerImageListInfo || [],
      thumbnailList: thumbnailList || [],
      gpuStatusInfo: gpuStatusInfo || { gpuTotal: 0, gpuFree: 0 },
      gpuModelStatusInfo: gpuModelStatus || [],
      cpuModelStatusInfo: cpuModelStatus || [],
      userListInfo: userListInfo || [],
      builtInFilterListInfo: builtInFilterListInfo || [],
      instanceModels: newInstances || [],
    };
  };

  detailCpuValueHandler = (idx, id, value, option) => {
    const { cpuDetailValue, ramDetailValue, totalSliderMove } = this.state;
    const newState = {};

    if (value === 0 || value < 0) {
      value = 1;
    }
    newState.totalSliderMove = false;

    // setTotalSliderMove(false);
    if (!totalSliderMove) {
      if (option === 'cpu') {
        const copiedDetailValue = JSON.parse(JSON.stringify(cpuDetailValue));
        copiedDetailValue[idx][id] = value;

        newState.cpuDetailValue = copiedDetailValue;
      } else if (option === 'ram') {
        const copiedDetailValue = JSON.parse(JSON.stringify(ramDetailValue));
        copiedDetailValue[idx][id] = value;

        newState.ramDetailValue = copiedDetailValue;
      }
    }
    this.setState(newState);
  };

  modifyInstanceValues = (index) => {
    const { gpuInputValues } = this.state;

    let newArr = gpuInputValues.map((value, idx) => {
      return idx === index ? value : '';
    });

    return newArr;
  };

  updateFailurePopup = () => {
    const { openConfirm, t, closeModal } = this.props;
    closeModal('EDIT_TRAINING');
    openConfirm({
      title: 'failUpdateTraining.label',
      content: 'failUpdateTraining.message',
      submit: {
        text: 'confirm.label',
      },

      notice: t('deleteDeploymentPopup.content.message'),
    });
  };

  checkboxHandler = ({ idx, flag, initialValue = [] }) => {
    const { gpuSelectedOptions: instanceOptions, gpuInputValues } = this.state;
    // console.log('gpuInputValues', gpuInputValues);
    let selectedInstance = [];

    if (instanceOptions.length === 0) {
      selectedInstance.push(...initialValue);
    } else {
      selectedInstance.push(...instanceOptions);
    }

    let newFlag = !Object.values(selectedInstance[idx])[0];

    if (typeof flag === 'boolean') {
      newFlag = flag;
    }
    let prevSelectedOptions = selectedInstance.slice(0, idx);
    let currSelectedOptions = {
      [idx]: newFlag,
    };
    let nextSelectedOptions = selectedInstance.slice(
      idx + 1,
      selectedInstance.length,
    );

    const newState = {};

    if (!newFlag) {
      const newGpuInputValues = [...gpuInputValues];
      newGpuInputValues[idx] = '';
      newState.gpuInputValues = newGpuInputValues;
    } else {
      const newGpuValues = [...gpuInputValues].map((inputVal, index) => '');
      newState.gpuInputValues = newGpuValues;
    }

    const newSelectedOptions = [
      ...prevSelectedOptions,
      currSelectedOptions,
      ...nextSelectedOptions,
    ];

    function updateCheckboxes(arr = [], index) {
      if (
        !Array.isArray(arr) ||
        typeof index !== 'number' ||
        index < 0 ||
        index >= arr.length
      ) {
        throw new Error('Invalid input');
      }

      if (Object.values(arr[index])[0] === true) {
        arr.forEach((obj, i) => {
          if (i !== index) {
            let key = Object.keys(obj)[0];
            obj[key] = false;
          }
        });
      }
      return arr;
    }

    newState.gpuSelectedOptions = updateCheckboxes(newSelectedOptions, idx);
    // newState.gpuInputValues = this.modifyInstanceValues(idx);

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // Admin의 Training Options 가져오기
  getAdminTrainingInfo = async () => {
    const response = await callApi({
      url: 'options/trainings',
      method: 'get',
    });

    const { result, status, message, error } = response;
    if (status !== STATUS_SUCCESS) {
      errorToastMessage(error, message);
      return {};
    }

    const { workspace_list: workspaceListInfo } = result;
    return { workspaceListInfo };
  };

  // state 포맷에 맞게 데이터를 파싱
  parseStateData = ({
    builtInModelListInfo,
    builtInFilterListInfo,
    dockerImageListInfo,
    gpuStatusInfo,
    gpuModelStatusInfo,
    selectedListInfo = [],
    userListInfo,
  }) => {
    const resultState = {};
    if (builtInModelListInfo) {
      resultState.builtInModelOptions = builtInModelListInfo.map(
        ({
          id,
          created_by: createdBy,
          kind,
          name,
          docker_image_id: dockerImageId,
          description: desc,
          horovod_training_multi_gpu_mode: multiGpuModeHorovod,
          nonhorovod_training_multi_gpu_mode: multiGpuModeNonHorovod,
          enable_to_train_with_gpu: enableGpu, // 0 | 1
          enable_to_train_with_cpu: enableCpu, // 0 | 1
          run_docker_name: runDockerName,
          training_status: trainingStatus, // 0 | 1 | -1
          thumbnail_path: thumbnailImageInfo,
        }) => ({
          id,
          createdBy,
          kind,
          name,
          title: name,
          desc,
          disabled: (!enableGpu && !enableCpu) || trainingStatus !== 1,
          enableGpu,
          enableCpu,
          multiGpuMode: multiGpuModeHorovod || multiGpuModeNonHorovod,
          dockerImageId,
          runDockerName,
          thumbnailImageInfo,
        }),
      );
    }
    if (builtInFilterListInfo) {
      const builtInFilterOptions = builtInFilterListInfo.map(
        ({ kind, created_by: createdBy }) => {
          return {
            label: kind,
            value: kind,
            createdBy,
          };
        },
      );
      builtInFilterOptions.unshift({ label: 'all.label', value: 'all' });
      resultState.builtInFilterOptions = builtInFilterOptions;
    }
    if (dockerImageListInfo) {
      resultState.dockerImageOptions = dockerImageListInfo.map(
        ({ id, name }) => ({ label: name, value: id }),
      );
    }
    if (gpuStatusInfo) {
      resultState.maxGpuUsageCountForRandom = gpuStatusInfo.gpuFree;
      resultState.gpuTotalCountForRandom = gpuStatusInfo.gpuTotal;
      resultState.isGuranteedGpu = gpuStatusInfo.isGuranteedGpu;
    }
    if (gpuModelStatusInfo) {
      resultState.gpuModelListOptions = gpuModelStatusInfo.map((v) => ({
        ...v,
        selected: false,
        node_list: v.node_list.map((n) => ({
          ...n,
          selected: false,
        })),
      }));
    }
    if (userListInfo) {
      const userName = sessionStorage.getItem('user_name');
      resultState.ownerOptions = userListInfo.map(({ id, name }) => ({
        label: name,
        value: id,
      }));
      resultState.userList = userListInfo
        .filter(({ id, name }) => {
          let isSelected = false;
          for (let i = 0; i < selectedListInfo.length; i += 1) {
            if (id === selectedListInfo[i].value) {
              isSelected = true;
              break;
            }
          }
          return !(name === userName || isSelected);
        })
        .map(({ id, name }) => ({ label: name, value: id }));
    }

    return resultState;
  };

  instanceSubmitHandler = () => {
    const { state } = this;

    const { gpuSelectedOptions, gpuInputValues, instanceModels } = state;

    const instance = {};

    gpuSelectedOptions.forEach((v, i) => {
      const value = Object.values(v)[0];

      if (
        value === true &&
        gpuInputValues[i] >= 0 &&
        typeof gpuInputValues[i] === 'number'
      ) {
        instance.resource_name = instanceModels[i].name;
        instance.allocate = gpuInputValues[i];
        instance.resource_group_id = instanceModels[i].gpu_resource_group_id;
        instance.id = instanceModels[i].id;
      }
    });

    return instance;
  };

  // 프로젝트 생성/수정
  onSubmit = async (callback) => {
    const { type, t, data } = this.props;

    const url = 'projects';
    let method = 'POST';
    const {
      trainingName,
      trainingType,
      workspace,
      accessType,
      owner,
      tmpSelectedList: selectedList,
      trainingId,
      trainingDesc: description,
      builtInModel,
      dockerImageOptions,
      // new props
      gpuModelType,
      cpuModelList,
      selectedCategory,
      selectedModel,
      selectedHuggingFaceModel,
      huggingFaceToken,
    } = this.state;

    if (
      (data?.data?.status?.training !== 'stop' ||
        data?.data?.status?.workbench !== 'stop') &&
      type === 'EDIT_TRAINING'
    ) {
      // popup
      this.updateFailurePopup();

      return;
    }

    const instance = this.instanceSubmitHandler();
    let body = {
      project_name: trainingName,
      // project_type: trainingType,
      project_type: 'advanced',
      workspace_id: workspace.value,
      owner_id: owner.value,
      access: accessType,
      description,
      // gpu_count: 1,
    };

    if (selectedCategory.value) {
      body['category'] = selectedCategory.name;
    }

    if (selectedModel.value) {
      body['project_type'] = 'built-in';
      body['built_in_model'] = selectedModel.name;
      body['huggingface_model_id'] = selectedModel.value;
    }

    if (selectedHuggingFaceModel.name) {
      body['project_type'] = 'huggingface';
      body['huggingface_model_id'] = selectedHuggingFaceModel.name;
    }

    if (huggingFaceToken) {
      body['huggingFaceToken'] = huggingFaceToken;
    }

    if (Object.keys(instance).length > 0) {
      body.instance_allocate = instance.allocate;
      body.instance_id = instance.id;
      body.gpu_resource_group_id = instance.gpu_resource_group_id;
    }

    if (trainingType !== 'federated-learning') {
      const gpuModelNodeListJson = {};
      if (gpuModelType === 1) {
        cpuModelList.map((v) => {
          if (v.length > 0) {
            v.map(({ name, model }, idx) => {
              if (idx === 0) {
                gpuModelNodeListJson[model] = [name];
              } else {
                gpuModelNodeListJson[model].push(name);
              }
              return gpuModelNodeListJson[model];
            });
          }
          return gpuModelNodeListJson;
        });
      }

      // if (trainingType === 'built-in') {
      let dockerImageId;

      for (let i = 0; i < dockerImageOptions.length; i += 1) {
        const { label: dockerName, value } = dockerImageOptions[i];
        // if (
        //   builtInModel.runDockerName === null &&
        //   dockerName === 'jf-default'
        // ) {
        //   dockerImageId = value;
        //   break;
        // } else if (
        //   builtInModel.runDockerName !== null &&
        //   dockerName === builtInModel.runDockerName
        // ) {
        //   dockerImageId = value;
        //   break;
        // }

        // if (value === dockerImage.value) {
        //   body.docker_image_id = dockerImage.value;
        // }
      }
      if (builtInModel && builtInModel.id) {
        body.built_in_model_id = builtInModel.id;
      } else {
        // body.built_in_model_id = null;
      }

      body = {
        ...body,
        // node_name_gpu,
        // node_name_cpu,
        // gpu_model: gpuModelType === 1 ? gpuModelNodeListJson : null,
        // gpu_count: modelType === 1 ? 0 : parseInt(gpuUsage, 10),
      };
    }

    if (type === 'EDIT_TRAINING') {
      method = 'PUT';
      body.project_id = trainingId;
    }

    // accessType이 private 일 때 users_id 추가
    if (accessType === 0) {
      body.users_id = selectedList.map(({ value }) => value);
    }

    // if (trainingType === 'built-in') {
    //   let dockerImageId;
    //   for (let i = 0; i < dockerImageOptions.length; i += 1) {
    //     const { label: dockerName, value } = dockerImageOptions[i];
    //     if (
    //       builtInModel.runDockerName === null &&
    //       dockerName === 'jf-default'
    //     ) {
    //       dockerImageId = value;
    //       break;
    //     } else if (
    //       builtInModel.runDockerName !== null &&
    //       dockerName === builtInModel.runDockerName
    //     ) {
    //       dockerImageId = value;
    //       break;
    //     }
    //   }
    //   body.built_in_model_id = builtInModel.id;
    //   body.docker_image_id = dockerImageId;
    // } else if (trainingType === 'advanced') {
    //   body.docker_image_id = dockerImage.value;
    // }
    const response = await callApi({ url, method, body });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      if (type === 'CREATE_TRAINING') {
        console.log('create training success');
        // defaultSuccessToastMessage('create');
      } else {
        console.log('update training success');
        // defaultSuccessToastMessage('update');
      }
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  /** ================================================================================
   * API END
   ================================================================================ */

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

  // 라디오 버튼 이벤트 핸들러 (Training Type)
  radioBtnHandler = (name, value) => {
    const { modelType, gpuUsage, builtInModel } = this.state;
    const newState = {};
    if (!builtInModel) {
      newState.resourceTypeReadOnly = false;
    }
    if (name === 'trainingType') {
      newState[name] = value;
      newState.builtInFilter = null;
      newState.builtInModel = null;

      newState.minGpuUsage = 0;
      newState.maxGpuUsage = 10000;
    } else if (name === 'gpuModelType') {
      newState[name] = parseInt(value, 10);
      const { gpuModelList, isMigModel } = this.state;

      if (
        (!gpuModelList || gpuModelList.length === 0) &&
        parseInt(value) === 1
      ) {
        // newState.gpuUsageError = null;
      } else if (isMigModel) {
        // newState.gpuUsage = 1;
        // newState.gpuUsageError = '';
      }
    } else if (name === 'cpuModelType') {
      newState[name] = parseInt(value, 10);
    } else {
      newState[name] = name === 'accessType' ? parseInt(value, 10) : value;
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  modelRadioBtnHandler = (name) => {
    const { gpuUsage } = this.state;
    const newState = {};

    if (name === 1) {
      newState.modelType = 1;
    } else if (name === 0) {
      newState.modelType = 0;
      // if (gpuUsage === '' || gpuUsage === null || gpuUsage === 0) {
      //   newState.gpuUsageError = null;
      // }
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  calDuplicateTrainingName = async (projectName, workspaceId) => {
    if (!projectName || !workspaceId) return;
    const res = await callApi({
      url: `projects/duplicate-name?project_name=${projectName}&workspace_id=${workspaceId}`,
      method: 'get',
    });
  };

  // 텍스트 인풋 이벤트 핸들러 (Training Name)
  textInputHandler = async (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]:
        name === 'gpuUsage' && typeof value === 'number'
          ? parseInt(value, 10)
          : value,
      [`${name}Error`]: null,
    };

    if (name === 'trainingName') {
      const { data } = this.props;
      const { workspaceId } = data;

      await this.calDuplicateTrainingName(value, workspaceId);
    }

    const validate = this.validate(name, value);
    if (validate) {
      newState[`${name}Error`] = validate;
    } else if (name === 'trainingDesc' && value.trim() === '') {
      newState[`${name}Error`] = null;
    } else {
      newState[`${name}Error`] = '';
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 넘버 인풋 이벤트 핸들러
  numberInputHandler = (e) => {
    const { name, value } = e;

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

  sliderCheckHandler = (type) => {
    const { gpuSelectedOptions, cpuSelectedOptions } = this.state;
    if (!type) {
      // 0 gpu
      let check = 0;
      gpuSelectedOptions.forEach((v) => {
        Object.values(v).forEach((boolean) => {
          if (boolean) {
            check++;
          }
        });
      });
      return check;
    } else if (type) {
      // 1 cpu
    }
  };

  gpuGetHandler = (list = []) => {
    const newState = {};
    // gpu 기본 state 깔기
    let selectedOptions = [];

    let selectedItemValue = [];
    const initialInputValues = [];
    if (list?.length > 0) {
      list.forEach(({ records }, idx) => {
        selectedItemValue = [];
        selectedOptions.push({ [idx]: false });
        initialInputValues.push('');
        if (records?.length > 0) {
          records.forEach(() => {
            selectedItemValue.push(false);
          });
        }
      });

      newState.gpuSelectedOptions = selectedOptions;
      newState.gpuInputValues = initialInputValues;
    }
    this.setState(newState, () => {});
    return { selectedOptions, initialInputValues };
  };

  // 셀렉트 박스 이벤트 핸들러 (Workspace)
  selectInputHandler = async (name, value) => {
    let newState = {
      [name]: value,
    };
    if (name === 'workspace') {
      // 유저 목록 설정
      const { workspace } = this.state;
      const { value: newWorkspace } = value;
      if (workspace && workspace.value === newWorkspace) return;
      // Training Info 업데이트
      const trainingInfoData = await this.getTrainingInfo(newWorkspace);
      const trainingInfoState = this.parseStateData(trainingInfoData);

      const cpuData = trainingInfoData?.cpuModelStatusInfo;
      const gpuData = trainingInfoData?.gpuModelStatusInfo;

      newState = {
        ...newState,
        ...trainingInfoState,
        ...this.gpuGetHandler(gpuData),
        ...this.cpuGetHandler(cpuData),
        thumbnailList: trainingInfoData?.thumbnailList,
        cpuModelInfo: cpuData,
      };

      // 선택된 옵션 초기화
      newState.builtInModel = null;
      newState.owner = null;
      newState.dockerImage = null;
      newState.gpuUsage = '';
      // newState.gpuUsageError = null;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 유저 멀티 셀렉트 이벤트 핸들러
  multiSelectHandler = ({ selectedList }) => {
    this.setState({ tmpSelectedList: selectedList }, () => {
      this.submitBtnCheck();
    });
  };

  // 모델 선택 이벤트 핸들러
  selectBuiltInModelHandler = (builtInModel) => {
    let newState = { builtInModel };
    if (builtInModel.enableGpu === 0) {
      // GPU 사용이 안될때 gpuUsage 값을 0으로
      newState.gpuUsage = 0;
      // newState.gpuUsageError = '';
      newState.minGpuUsage = 0;
      newState.resourceTypeReadOnly = true;
      if (builtInModel.enableCpu) {
        newState.modelType = 1;
      }

      newState.maxGpuUsage = 0;
    } else if (builtInModel.enableCpu === 0) {
      // CPU 사용이 안될때 gpuUsage 값을 1 이상으로
      newState.resourceTypeReadOnly = true;
      newState.gpuUsage = 1;
      // newState.gpuUsageError = '';
      newState.minGpuUsage = 0;
      newState.maxGpuUsage = 10000;
      if (builtInModel.enableGpu) {
        newState.modelType = 0;
      }
      newState.modelType = 0;
    } else {
      newState.modelType = 0;
      newState.resourceTypeReadOnly = false;
      newState.gpuUsage = '';
      newState.minGpuUsage = 0;
      newState.maxGpuUsage = 10000;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // GPU 모델 선택 이벤트 핸들러
  selectGpuModelHandler = (type, idx, nodeIdx) => {
    const { gpuModelListOptions, gpuUsage, cpuModelList } = this.state;

    let { gpuModelList } = this.state;
    let cpuModelListOptions = gpuModelListOptions[idx].node_list;
    let newState = {};

    gpuModelListOptions[idx].selected = !gpuModelListOptions[idx].selected;
    // GPU 모델 선택/선택해제시 CPU 모델 전체 선택/선택해제
    cpuModelListOptions = cpuModelListOptions.map((v) => {
      return {
        ...v,
        selected: gpuModelListOptions[idx].selected,
      };
    });
    gpuModelListOptions[idx].node_list = cpuModelListOptions;

    cpuModelList[idx] = cpuModelListOptions.filter(({ selected }) => selected);
    gpuModelList = gpuModelListOptions.filter(({ selected }) => selected);

    newState = {
      cpuModelList,
      ...this.gpuModelState(gpuModelListOptions, gpuModelList, gpuUsage),
    };

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // GPU 모델 관련 상태 정의
  gpuModelState = (options, gpuModelList, gpuUsage) => {
    const { gpuModelType, gpuTotalCountForRandom, maxGpuUsageCountForRandom } =
      this.state;
    let migCount = 0;
    let totalCount = 0;
    let avalCount = 0;

    gpuModelList.map(({ type, node_list: nodeList }) => {
      if (type === 'mig') {
        migCount += 1;
      }
      nodeList.map(({ total, aval, selected }) => {
        if (selected) {
          totalCount += total;
          avalCount += aval;
        }
        return true;
      });
      return true;
    });

    if (gpuTotalCountForRandom < totalCount) {
      totalCount = gpuTotalCountForRandom;
    }

    if (maxGpuUsageCountForRandom < avalCount) {
      avalCount = maxGpuUsageCountForRandom;
    }

    let gpuCount = gpuUsage;

    const gpuState = {
      gpuModelListOptions: options,
      gpuModelList,
      isMigModel: migCount > 0,
      maxGpuUsageCount: avalCount,
      gpuTotalCount: totalCount,
      gpuUsage: gpuCount,
    };

    return gpuState;
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'trainingName') {
      // const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

      const regType = !forbiddenChars.test(value);
      if (value === '') {
        return 'trainingName.empty.message';
      }
      // if (!value.match(regType1) || value.match(regType1)[0] !== value) {
      //   return 'nameRule.message';
      // }
      if (!regType) {
        return 'newNameRule.message';
      }
    } else if (name === 'gpuUsage') {
      if (value === '') {
        return 'gpuUsage.empty.message';
      }
    } else if (name === 'selectedList') {
      if (value.length === 0) {
        return 'userSelectedList.empty.message';
      }
    }
    return null;
  };

  checkGpuInputValues(gpuCheckValue, inputValue) {
    for (let i = 0; i < gpuCheckValue.length; i++) {
      const value = Object.values(gpuCheckValue[i])[0];

      if (
        value === true &&
        inputValue[i] >= 0 &&
        typeof inputValue[i] === 'number'
      ) {
        return true;
      }
    }
    return false;
  }

  submitBtnCheck = (toggleChange) => {
    // submit 버튼 활성/비활성
    const { type } = this.props;

    const { state } = this;
    const {
      trainingNameError,
      owner,
      trainingType,
      gpuSelectedOptions,
      gpuInputValues,
    } = state;
    const validateState = { validate: false };
    const stateKeys = Object.keys(state);

    let validateCount = 0;

    if (trainingType === 'federated-learning') {
      if (trainingNameError === '') {
        this.setState({ validate: true });
      }
    } else {
      for (let i = 0; i < stateKeys.length; i += 1) {
        const key = stateKeys[i];
        if (
          key.indexOf('Error') !== -1 &&
          state[key] !== '' &&
          key !== 'trainingDescError' &&
          key !== 'dockerImageError'
        ) {
          validateCount += 1;
        }
      }
      if (!owner) {
        validateCount += 1;
      }
      if (type === 'EDIT_TRAINING') {
        if (toggleChange !== 'toggle' && validateCount === 0) {
          validateState.validate = true;
          this.setState(validateState);
        }
      }

      if (gpuSelectedOptions.length > 0) {
        const gpuValidate = this.checkGpuInputValues(
          gpuSelectedOptions,
          gpuInputValues,
        );
        if (!gpuValidate) {
          validateCount += 1;
        }
      }

      if (type === 'CREATE_TRAINING') {
        // if (!dockerImage) {
        //   validateCount += 1;
        // }

        if (validateCount === 0) {
          validateState.validate = true;
        }
        this.setState(validateState);
      }
    }
  };

  onBuiltInModelSearch = (e) => {
    let searchValue = e.target.value;
    searchValue = searchValue.toLowerCase();
    let modelOption = this.state.builtInModelOptions;

    modelOption.forEach((item) => {
      if (item.name) {
        const dis_name = Hangul.make(item.name, true);
        Object.assign(item, { dis_name });
      }
      if (item.desc) {
        const dis_desc = Hangul.make(item.desc, true);
        Object.assign(item, { dis_desc });
      }
    });

    const result = modelOption.filter((item) => {
      const { name, desc, dis_name, dis_desc } = item;
      return (
        name?.toLowerCase().includes(searchValue) ||
        desc?.toLowerCase().includes(searchValue) ||
        dis_name?.toLowerCase().includes(searchValue) ||
        dis_desc?.toLowerCase().includes(searchValue)
      );
    });
    this.setState({ builtInModelSearchResult: result });
  };

  handleModelTypeValue = (e) => {
    this.setState({
      selectedCategory: {
        name: '',
        value: null,
      },
    });
    this.setState({
      selectedModel: {
        name: '',
        value: null,
      },
    });
    this.setState({ modelTypeValue: +e.target.value });
  };

  handleCategoryValue = (v) => {
    this.setState({ selectedCategory: v });
  };

  handleModelValue = (v) => {
    this.setState({ selectedModel: v });
  };

  handleHuggingFaceValue = (v) => {
    this.setState({ selectedHuggingFaceModel: v });
  };

  handleHuggingFaceToken = (v) => {
    this.setState({ huggingFaceToken: v });
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  render() {
    const {
      state,
      props,
      radioBtnHandler,
      textInputHandler,
      numberInputHandler,
      selectInputHandler,
      multiSelectHandler,
      selectBuiltInModelHandler,
      selectGpuModelHandler,
      onBuiltInModelSearch,
      onSubmit,
      modelRadioBtnHandler,
      checkboxHandler,
      detailCpuValueHandler,
      detailGpuValueHandler,
      totalValueHandler,
      totalSliderHandler,
      sliderSwitchHandler,
      onChangeGpuInputValue,
      handleModelTypeValue,
      handleCategoryValue,
      handleModelValue,
      handleHuggingFaceValue,
      handleHuggingFaceToken,
    } = this;
    return (
      <TrainingFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        numberInputHandler={numberInputHandler}
        radioBtnHandler={radioBtnHandler}
        selectInputHandler={selectInputHandler}
        multiSelectHandler={multiSelectHandler}
        selectBuiltInModelHandler={selectBuiltInModelHandler}
        selectGpuModelHandler={selectGpuModelHandler}
        onBuiltInModelSearch={onBuiltInModelSearch}
        onSubmit={onSubmit}
        modelRadioBtnHandler={modelRadioBtnHandler}
        handleModelTypeValue={handleModelTypeValue}
        handleCategoryValue={handleCategoryValue}
        handleModelValue={handleModelValue}
        handleHuggingFaceValue={handleHuggingFaceValue}
        handleHuggingFaceToken={handleHuggingFaceToken}
        // * ---- slider props
        checkboxHandler={checkboxHandler}
        detailCpuValueHandler={detailCpuValueHandler}
        detailGpuValueHandler={detailGpuValueHandler}
        totalValueHandler={totalValueHandler}
        totalSliderHandler={totalSliderHandler}
        sliderSwitchHandler={sliderSwitchHandler}
        onChangeGpuInputValue={onChangeGpuInputValue}
      />
    );
  }
}

export default connect(null, {
  closeModal,
  openConfirm,
})(withTranslation()(TrainingFormModalContainer));
