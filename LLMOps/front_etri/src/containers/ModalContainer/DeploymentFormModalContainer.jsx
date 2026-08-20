import { createRef, PureComponent } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

import Hangul from '@src/koreaUtils';
import { cloneDeep } from 'lodash';

// Components
import DeploymentFormModal from '@src/components/Modal/DeploymentFormModal';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// Utils
import { errorToastMessage } from '@src/utils';

class DeploymentFormModalContainer extends PureComponent {
  _MODE = import.meta.env.VITE_REACT_APP_MODE;
  _isMount = false;

  state = {
    validate: false, // 모달의 submit 버튼 활성/비활성 여부 상태 값
    deploymentId: '', // Deployment id 값
    deploymentOptions: [
      { label: 'CPU', value: 'cpu' },
      { label: 'GPU', value: 'gpu' },
    ], // Deployment Type 선택 옵션
    deploymentName: '', // Deployment Name 값
    deploymentNameError: null, // Deployment Name 인풋 에러 텍스트
    deploymentDesc: '', // Deployment Description 값
    workspace: null, // workspace 값
    workspaceError: null, // workspace 인풋 에러 텍스트
    workspaceOptions: [], // workspace 옵션
    deploymentDescError: null, // Deployment Description 인풋 에러 텍스트
    footerMessage: '',

    deploymentType: 'built-in', // 배포 유형 값
    deploymentTypeOptions: [
      {
        label: 'Built-in',
        value: 'built-in',
        icon: '/images/icon/00-ic-data-built-in-yellow.svg',
      },
      {
        label: 'Custom',
        value: 'custom',
        icon: '/images/icon/00-ic-data-custom-yellow.svg',
      },
    ], // 배포 유형 옵션

    builtInType: null,
    builtInTypeOptions: [
      { label: 'user-trained', value: 'custom' },
      { label: 'pre-trained', value: 'default' },
    ],
    selectedBuiltInTypeIdx: undefined,
    dockerImageSelectedItemIdx: null,
    // Built-in 모델 옵션
    builtInUserTrainedModelOptions: [], // user-trained (Custom)
    builtInPreTrainedModelOptions: [], // pre-trained (Default)

    // Custom 모델 옵션
    customModelOptions: [],

    builtInFilter: null,
    builtInFilterOptions: [],
    modelOptions: [],

    // 커스텀 배포 - 실행코드
    instanceType: 'gpu',
    instanceTypeOptions: [
      { label: 'CPU', value: 'cpu' },
      { label: 'GPU', value: 'gpu' },
    ],
    gpuModelTypeOptions: [
      { label: 'random.label', value: 0 },
      { label: 'specificModel.label', value: 1 },
    ],
    gpuModelType: 0, // 무작위 선택이 디폴트 (변경 불가)
    gpuModelListOptions: [], // GPU 모델 선택 옵션
    gpuModelList: null, // 선택한 GPU 모델 리스트
    cpuModelList: [], // 선택한 CPU 모델 리스트 (노드)
    isMigModel: false, // 선택한 gpu model 리스트에 MIG 모델 포함 여부
    dockerImageOptions: [],
    dockerImage: null,
    dockerImageError: null,
    gpuCount: 0,
    gpuUsage: '', // 사용할 GPU(GPU usage) 수 값
    gpuTotal: 0, // 사용가능한 gpu 수 값
    gpuFree: 0,
    maxGpuUsageCount: { gpuDeploymentTotal: 0, gpuServiceTotal: 0 }, // 사용 가능한 GPU 수
    accessTypeOptions: [
      // Access Type 선택 옵션
      { label: 'Public', value: 1 },
      { label: 'Private', value: 0 },
    ],
    deploymentStatus: '',
    accessType: 1, // 선택한 Access Type 값
    ownerOptions: [], // Owner 선택 옵션
    owner: null, // 선택한 Owner 값
    userList: [], // 유저 멀티 선택 옵션
    selectedList: [], // 선택된 유저 값
    tmpSelectedList: [],
    permissionLevel: -1,
    isTrainingModelDeleted: false,
    // * slider gpu
    sliderIsValidate: true,
    instanceModels: [],
    gpuList: [],
    instanceList: [],
    gpuInputValues: [],
    gpuSelectedOptions: [],
    modelType: 0,
    gpuUsageStatus: '',
    gpuDetailSelectedOptions: [],
    gpuTotalValue: 1,
    gpuRamTotalValue: 1,
    gpuDetailValue: 1,
    gpuRamDetailValue: 1,
    gpuTotalSliderMove: false,
    gpuSliderMove: false,
    gpuAndRamSliderValue: {
      cpu: 1,
      ram: 1,
    },
    initialGpuCount: 0,
    prevGpuCount: 0,
    // * slider cpu
    cpuModelStatus: [],
    cpuModelType: 0, // 무작위 선택이 디폴트 (변경 불가)
    cpuSwitchStatus: false,
    cpuSliderMove: false,
    cpuSelectedOptions: [],
    detailSelectedOptions: [],
    cpuTotalValue: 1,
    ramTotalValue: 1,
    cpuDetailValue: 1,
    ramDetailValue: 1,
    cpuAndRamSliderValue: { cpu: 1, ram: 1 },
    selectedDeploymentType: null,
    trainingList: [],
    originTrainingList: [],
    trainingSelectedType: {
      label: 'all.label',
      value: 'all',
    },
    trainingSelectedOwner: {
      label: 'all.label',
      value: 'allOwner',
    },
    toolSelectedOwner: {
      label: 'all.label',
      value: 'toolAll',
    },

    trainingInputValue: '',
    trainingSelectTab: 0,
    trainingType: '',
    selectedTraining: null,
    selectedTrainingData: null,
    jobList: null,
    jobId: '',
    jobDetailList: null,
    jobDetailOpenList: [],
    hpsList: null,
    hpsDetailList: null,
    hpsDetailOpenList: [],
    hpsLogTable: [],
    selectedHpsId: '',
    selectedHpsScore: '',
    selectedHps: null,
    trainingToolTab: 0,
    selectedTool: null,
    selectedToolType: null,
    customLan: 'python',
    customFile: '',
    customParam: '',
    customList: [],
    originCustomList: [],
    customSearchValue: '',
    hpsLogList: [],
    hpsModelList: [],
    originHpsModelList: [],
    originJobModelList: [],
    jobModelList: [],
    selectedLogId: '',
    customRuncode: '',
    variablesValues: [{ key: '', value: '' }],
    selectedType: null,
    toolSearchValue: '',
    toolModelSearchValue: '',
    hpsModelSelectValue: '',
    jobModelSelectValue: '',
    trainingTypeArrow: {
      train: false,
      tool: false,
      model: false,
      variable: false,
      hps: false,
      hpsModel: false,
      jobModel: false,
    },
    templateData: [],
    makeNewGroup: false,
    clickedDataList: null,
    clickedTemplateLists: null,
    groupSelect: false,
    newGroupName: '',
    newGroupDescription: '',
    groupNameError: false,
    templateId: null,
    templateNewName: '',
    templateNewDescription: '',
    templateNameError: false,
    templateOpenStatus: false,
    customListStatus: null,
    modelList: [],
    originModelList: [],
    modelSearchValue: '',
    modelCategorySelect: { value: 'all' },
    modelSelectStatus: true,
    selectedModel: null, // 배포 유형 - built-in 모델 선택된 값
    jsonData: {}, // 배포유형 - 설정값입력
    jsonDataError: false,
    showSelectAgain: false,
    editModalTemplateId: null,
    editOriginSelectedModel: null,
    defaultGroupName: null,
    defaultTemplateName: null,
    groupData: null,
    deploymentTemplateType: null,
    jsonRef: createRef(),
    deploymentNoGroupSelected: false,
    tangoTraining: { name: '', value: 0 }, // tango 2개, hugging 2개 만들어야함,
    tangoModel: { name: '', value: 0 }, // tango 2개, hugging 2개 만들어야함,
    huggingTraining: { name: '', value: 0 },
    huggingModel: { name: '', value: 0 },

    //
    modelSelectType: 1,
    modelSelectOptions: [
      { label: 'Custom', value: 1 },
      { label: 'Tango Intelligence', value: 0 },
      { label: 'Hugging Face', value: 2 },
    ],
    tangoIntelligenceType: 1,
    tangoIntelligenceOptions: [
      { label: 'importNewModel.label', value: 1 },
      { label: 'loadFromTraining.label', value: 0 },
    ],
    huggingFaceToken: '',
  };

  async componentDidMount() {
    const {
      type,
      data: { deploymentId, workspaceName },
    } = this.props;

    let newState = {};

    if (type === 'EDIT_DEPLOYMENT') {
      this._isMount = false;
      const response = await callApi({
        url: `deployments/${deploymentId}`,
        method: 'get',
      });

      const { result, status, message, error } = response;

      let type = result.deployment_template_type;

      this.setState({
        showSelectAgain: true,
        modelSelectStatus: false,
        tangoIntelligenceType: result?.is_new_model ? 1 : 0,
      });

      let { workspaceId } = this.props.data;

      if (result?.model_type === 'custom') {
        newState.modelSelectType = 1;
      } else if (result?.model_type === 'built-in') {
        newState.modelSelectType = 0;
      } else if (result?.model_type === 'huggingface') {
        newState.modelSelectType = 2;
      }

      const modelType = result?.model_type;
      if (modelType === 'built-in' || modelType === 'huggingface') {
        // modelType에 따라 newState의 키 결정
        const trainingKey =
          modelType === 'built-in' ? 'tangoTraining' : 'huggingTraining';
        const modelKey =
          modelType === 'built-in' ? 'tangoModel' : 'huggingModel';

        // is_new_model 값에 따라 사용할 필드 결정
        const trainingField = result.is_new_model
          ? 'model_category'
          : 'project_name';
        const modelField = result.is_new_model ? 'model_name' : 'training_name';

        if (result?.[trainingField]) {
          newState[trainingKey] = { name: result[trainingField], value: 0 };
        }
        if (result?.[modelField]) {
          newState[modelKey] = { name: result[modelField], value: 0 };
        }
      }

      // 배포 모달 옵션 정보 조회
      if (!workspaceId && result.workspace_id) {
        workspaceId = result.workspace_id;
      }
      const optionRes = await this.getOptions(workspaceId);
      const { trained_built_in_model_list: trainedBuiltInList } = optionRes;
      const { built_in_model_list: builtInModelList } = optionRes;

      const { cpuModelStatus } = this.parseOption(optionRes);
      newState.cpuModelStatus = cpuModelStatus;
      if (status === STATUS_SUCCESS) {
        // deployment data
        const {
          deployment_name: deploymentName,
          description: deploymentDesc,
          deployment_type: deploymentType,
          workspace_id: workspaceId,
          training_id: trainingModelId,
          built_in_model_id: builtInModelId,
          checkpoint,
          // gpu_model: gpuModel,
          gpu_count: gpuUsage,

          user_id: ownerId,
          users: selectedUsers,
          docker_image_id: dockerImageId,
          access: accessType,
          node_name_detail: prevSliderData,
          instance_list: instanceModels,
          instance: prevSelectedInstance,
          deployment_template_type: deploymentTemplateType,
          deployment_template_id: editModalTemplateId,
          deployment_template: editOriginSelectedModel,
          permission_level: permissionLevel,
        } = result;

        this.setState({
          workspace: { label: result.workspace_id, value: result.workspace_id },
        });

        if (trainedBuiltInList && trainedBuiltInList.length > 0) {
          trainedBuiltInList.forEach((v) => {
            if (v.id === result.training_id) {
              newState.selectedModel = v;
            }
          });
        }

        // 배포 모달의 옵션 정보 조회
        const optionRes = await this.getOptions(workspaceId);
        const {
          builtInUserTrainedModelOptions,
          builtInPreTrainedModelOptions,
          customModelOptions,
          ownerOptions,
          gpuTotal,
          gpuFree,
          dockerImageOptions,
          builtInFilterOptions,
          gpuModelListOptions,
          gpuList,
          newInstance,
        } = this.parseOption(optionRes);

        if (prevSelectedInstance && newInstance?.length > 0) {
          const { id: instanceId, instance_allocate: instanceAllocate } =
            prevSelectedInstance;

          let index = 0;
          newInstance.forEach((gpuModel, i) => {
            if (gpuModel.id === instanceId) {
              index = i;
              this.checkboxHandler({ idx: index, flag: true });
              this.onChangeGpuInputValue({
                idx: index,
                value: instanceAllocate,
              });
            }
          });
        }

        newState.prevGpuCount = gpuUsage;
        newState.deploymentTemplateType = deploymentTemplateType;
        newState.prevSliderData = prevSliderData;
        newState.instanceModels = instanceModels;
        newState.deploymentType = deploymentType;
        newState.deploymentId = deploymentId;
        newState.deploymentName = deploymentName;
        newState.deploymentNameError = '';
        newState.deploymentDesc = deploymentDesc;
        newState.deploymentDescError = '';
        newState.workspace = { label: workspaceId, value: workspaceId };
        newState.workspaceError = '';
        newState.workspaceOptions = [{ label: workspaceName, value: 0 }];
        newState.workspace = { label: workspaceName, value: 0 };
        newState.gpuCount = gpuUsage;
        newState.editModalTemplateId = editModalTemplateId;
        newState.editOriginSelectedModel = editOriginSelectedModel;
        newState.permissionLevel = permissionLevel;
        newState.gpuList = gpuList;
        newState.instanceList = newInstance;

        newState.builtInUserTrainedModelOptions =
          builtInUserTrainedModelOptions;
        newState.builtInPreTrainedModelOptions = builtInPreTrainedModelOptions;
        // 커스텀 모델 옵션 (배포 타입이 Custom)
        newState.customModelOptions = customModelOptions;
        const { model } = this.findModelAndBuiltInType(
          newState,
          deploymentType,
          trainingModelId || builtInModelId,
        );

        newState.model = model;

        newState.builtInFilterOptions = builtInFilterOptions;

        const checkpointArr = checkpoint ? checkpoint.split('/') : [];
        const targetCheckpoint = checkpointArr
          .slice(2, checkpointArr.length)
          .join('/');

        if (model) {
          if (
            editOriginSelectedModel.job_name ||
            editOriginSelectedModel.hps_name
          ) {
            this.getTrainingTypeData('usertrained', workspaceId);
          }
          if (
            deploymentType === 'built-in' &&
            deploymentTemplateType === 'usertrained'
          ) {
            newState.trainingType = 'built-in';
            newState.selectedDeploymentType = 'usertrained';
            newState.selectedTraining = editOriginSelectedModel.training_name;
            newState.trainingTypeArrow = {
              train: false,
              tool: false,
              model: false,
              hps: false,
              hpsModel: false,
              jobModel: false,
            };
            if (model.kind) {
              newState.builtInFilter = { label: model.kind, value: model.kind };
            }
            let jobList = '';
            let hpsList = '';

            if (
              editOriginSelectedModel.job_name ||
              editOriginSelectedModel.hps_name
            ) {
              const { jobListItem, hpsListItem } = await this.getJobList(
                editOriginSelectedModel,
                editOriginSelectedModel.training_name,
                true,
              );
              jobList = jobListItem;
              hpsList = hpsListItem;
            }

            const splitedChekcpoint =
              editOriginSelectedModel.checkpoint?.split('/');
            newState.checkpoint = splitedChekcpoint?.at(-1);

            if (editOriginSelectedModel.training_type === 'hps') {
              const hpsName = editOriginSelectedModel.hps_name;
              const hpsId = editOriginSelectedModel.hps_id;
              const hpsIdx = editOriginSelectedModel.hps_group_index;
              newState.trainingToolTab = 1;
              newState.trainingType = 'built-in';

              let hpsLogTable = [];
              hpsList.forEach((v, i) => {
                if (v.hps_name === hpsName) {
                  v.hps_group_list.forEach((model) => {
                    if (model.hps_id === hpsId) {
                      hpsLogTable = model.hps_number_info;
                    }
                  });
                }
              });

              // this.toolSelectHandler({
              //   type: 'HPS',
              //   name: hpsName,
              //   jobId: hpsId,
              //   detailNumber: hpsIdx + 1,
              //   hpsLogTable: hpsLogTable,
              //   hpsCheckpoint: hpsLogTable.max_item.checkpoint_list,
              // });

              newState.hpsModelSelectValue = splitedChekcpoint.at(-1);
            } else if (editOriginSelectedModel.training_type === 'job') {
              newState.jobModelSelectValue = splitedChekcpoint.at(-1);
              const jobName = editOriginSelectedModel.job_name;
              const jobId = editOriginSelectedModel.job_id;
              const jobIdx = editOriginSelectedModel.job_group_index;
              let checkpoint = [];
              jobList.forEach((v, i) => {
                if (v.job_name === jobName) {
                  v.job_group_list.forEach((model) => {
                    if (model.job_id === jobId) {
                      checkpoint = model.checkpoint_list;
                    }
                  });
                }
              });
              // this.toolSelectHandler({
              //   type: 'JOB',
              //   name: jobName,
              //   jobId: jobId,
              //   detailNumber: jobIdx + 1,
              //   jobCheckpoint: checkpoint,
              // });
              newState.trainingToolTab = 0;
              newState.trainingType = 'built-in';
            }
          } else if (deploymentType === 'custom') {
            await this.getJobList(
              editOriginSelectedModel,
              editOriginSelectedModel.training_name,
            );
            await this.getCustomList(editOriginSelectedModel);
            if (
              editOriginSelectedModel?.environments &&
              editOriginSelectedModel?.environments.length > 0
            ) {
              newState.variablesValues = editOriginSelectedModel.environments;
            }

            newState.trainingTypeArrow = {
              train: false,
              tool: false,
              model: false,
              variable: false,
              hps: false,
              hpsModel: false,
              jobModel: false,
            };
            newState.selectedTraining = editOriginSelectedModel.training_name;
            newState.selectedDeploymentType = 'usertrained';
            newState.trainingType = 'advanced';
            if (editOriginSelectedModel.command) {
              if (editOriginSelectedModel.command.arguments) {
                newState.customParam =
                  editOriginSelectedModel.command.arguments;
              }
              if (editOriginSelectedModel.command.binary) {
                newState.customLan = editOriginSelectedModel.command.binary;
              }
              if (editOriginSelectedModel.command.script) {
                newState.customFile = editOriginSelectedModel.command.script;
              }
            }
          }

          const { enableCpu, enableGpu } = model;
          // Job group setting

          // Group number setting
          if (newState.jobGroup) {
            // Checkpoint setting
            if (newState.groupNumber) {
              const { checkpointList = [] } = newState.groupNumber;
              newState.checkpointOptions = checkpointList.map(
                ({ name: checkpointTarget }) => {
                  if (checkpointTarget === targetCheckpoint) {
                    newState.checkpoint = {
                      label: checkpointTarget,
                      value: checkpointTarget,
                    };
                  }
                  return {
                    label: checkpointTarget,
                    value: checkpointTarget,
                  };
                },
              );
            }
          }

          // instance option setting
          newState.instanceTypeOptions = [
            { label: 'CPU', value: 'cpu', disabled: enableCpu === 0 },
            { label: 'GPU', value: 'gpu', disabled: enableGpu === 0 },
          ];
        }

        // 학습 모델이 삭제됐으면 아이콘을 보여줍니다.
        if (!newState.checkpoint) {
          newState.isTrainingModelDeleted = true;
        }

        // Instance Type setting
        newState.instanceType = 'gpu';

        // GPU usage setting
        newState.gpuUsage = gpuUsage;

        // DockerImage setting
        newState.dockerImage = dockerImageId;
        const dockerImage = dockerImageOptions.filter(
          ({ value }) => dockerImageId === value,
        )[0];
        newState.dockerImageOptions = dockerImageOptions;
        newState.dockerImage = dockerImage;
        // newState.dockerImageError = deploymentType === 'built-in' ? '' : null;

        // AccessType setting
        newState.accessType = accessType;

        // owner setting
        const targetOwnerOptions = [...ownerOptions];
        const ownerTmp = targetOwnerOptions.filter(
          ({ value }) => value === ownerId,
        )[0];
        const owner = !ownerTmp ? null : ownerTmp;
        newState.owner = owner;
        newState.ownerOptions = ownerOptions;

        // users setting
        const users = [...ownerOptions];
        const userList = [];
        const selectedList = [];
        for (let i = 0; i < users.length; i += 1) {
          const userItem = users[i];
          const { value: userId } = userItem;
          let flag = false;
          for (let j = 0; j < selectedUsers.length; j += 1) {
            const { id: selectedUserId } = selectedUsers[j];
            if (userId === selectedUserId) {
              flag = true;
              break;
            }
          }
          if (flag) {
            selectedList.push(userItem);
          } else {
            userList.push(userItem);
          }
        }
        newState.userList = userList;
        newState.selectedList = selectedList;
        newState.gpuTotal = gpuTotal;
        newState.gpuFree = gpuFree;

        newState.selectedBuiltInTypeIdx = 0;
        // newState = {
        //   ...newState,

        //   gpuModelType: gpuModel ? 1 : 0,
        // };

        this.deploymentTypeHandler(type === 'custom' ? 'usertrained' : type);
      } else {
        errorToastMessage(error, message);
      }
      this.setState(newState, () => this.submitBtnCheck());
    } else if (type === 'CREATE_DEPLOYMENT') {
      const {
        workspaceId,
        fromTraining,
        jobIdx,
        jobName,
        modelName,
        dockerImageName,
      } = this.props.data;

      newState.trainingTypeArrow = {
        train: true,
        tool: true,
        model: true,
        variable: true,
        hps: false,
        hpsModel: true,
        jobModel: true,
      };
      // 배포 모달 옵션 정보 조회
      const optionRes = await this.getOptions(workspaceId);
      const {
        builtInUserTrainedModelOptions,
        builtInPreTrainedModelOptions,
        customModelOptions,
        ownerOptions,
        workspaceOptions,
        gpuTotal,
        gpuFree,
        dockerImageOptions,
        builtInFilterOptions,
        gpuModelListOptions,
        cpuModelStatus,
        gpuList,
        newInstance,
      } = this.parseOption(optionRes);

      if (fromTraining) {
        this.setState({ selectedDeploymentType: 'usertrained' });
        const getTrainingList = await this.getTrainingTypeData('usertrained');
        let prevSelectedModel = [];
        getTrainingList?.usertrained_training_list.forEach((v) => {
          if (v.training_name === modelName) {
            prevSelectedModel = v;
          }
        });
        if (prevSelectedModel?.deployment_type === 'built-in') {
          const { jobListItem } = await this.getJobList(
            prevSelectedModel,
            modelName,
          );
          newState.trainingTypeArrow = {
            train: false,
            tool: false,
            model: true,
            variable: true,
            hps: false,
            hpsModel: true,
            jobModel: true,
          };
          let getJobItem = [];
          jobListItem.forEach((v) => {
            if (v?.job_name === jobName) {
              getJobItem = v;
            }
          });
          // this.toolSelectHandler({
          //   type: 'JOB',
          //   name: getJobItem.job_name,
          //   jobId: getJobItem.job_group_list[jobIdx]?.job_id,
          //   detailNumber: getJobItem.job_group_list.length - jobIdx,
          //   jobCheckpoint: getJobItem.job_group_list[jobIdx]?.checkpoint_list,
          // });
        }
      }

      newState.cpuModelStatus = cpuModelStatus;
      newState.gpuList = gpuList;
      newState.instanceList = newInstance;

      if (workspaceId) {
        // isUserModal 변수에 값이 있을 경우 유저 화면에서 배포 생성
        const { deploymentType } = this.state; // 현재 선택된 배포 타입
        const loginUserName = sessionStorage.getItem('user_name'); // 로그인한 유저의 이름

        // 학습 모델 옵션 설정
        newState.builtInUserTrainedModelOptions =
          builtInUserTrainedModelOptions;
        newState.builtInPreTrainedModelOptions = builtInPreTrainedModelOptions;
        newState.customModelOptions = customModelOptions; // 커스텀 모델 옵션 (배포 타입이 Custom)
        newState.builtInFilterOptions = builtInFilterOptions;

        // 도커이미지(docker image) 초기 설정 - 초기 도커 이미지를 jf-default로 설정
        let dockerImage = dockerImageOptions.filter(
          ({ label }) => label === 'jf-default',
        )[0];

        // 빠른 배포 생성 시 도커이미지 받아온걸로 설정
        if (fromTraining) {
          dockerImage = dockerImageOptions.filter(
            ({ label }) => label === dockerImageName,
          )[0];
        }
        newState.dockerImageOptions = dockerImageOptions;
        newState.dockerImage =
          deploymentType === 'built-in' ? dockerImage : null;

        let selectedIdx = 0;
        dockerImageOptions.forEach((v, i) => {
          if (dockerImage) {
            if (dockerImage.value === v.value) {
              selectedIdx = i;
            }
          } else {
            dockerImage = dockerImageOptions.filter(
              ({ label }) => label === 'jf_test',
            )[0];
          }
        });

        newState.dockerImageSelectedItemIdx = selectedIdx;
        // newState.dockerImageError = deploymentType === 'built-in' ? '' : null;

        // 소유자(owner) 설정 - 초가 owner를 로그인한 유저로 설정(변경 가능)
        const owner = ownerOptions.filter(
          ({ label }) => loginUserName === label,
        )[0];
        newState.owner = owner;
        newState.ownerOptions = ownerOptions;

        // 사용자(User) 초기 설정
        newState.userList = ownerOptions;

        // 워크스페이스 초기 설정 - 유저 화면에서는 workspace 인풋 제공하지 않음
        newState.workspace = { label: '', value: parseInt(workspaceId, 10) };
        newState.workspaceError = '';

        // 사용가능한 GPU 수 설정
        newState.gpuTotal = gpuTotal;
        newState.gpuFree = gpuFree;

        // GPU model setting
        newState.gpuModelListOptions = gpuModelListOptions;
        if (this.props.data.checkpoint) {
          const selectedModel = [];
          builtInUserTrainedModelOptions?.forEach((v) => {
            if (v.title === this.props.data.modelName) {
              selectedModel.push(v);
              newState.model = v;
            }
          });
        }
      } else {
        // 어드민 페이지에서 트레이닝 생성
        newState.workspaceOptions = workspaceOptions;
      }

      this.setState(newState, () => {
        if (this.props.data.checkpoint) {
          const userType = { label: 'user-trained', value: 'custom' };
          this.selectInputHandler('builtInType', userType);
          if (
            this.props.data.checkpoint &&
            newState.model?.jobList?.length > 0
          ) {
            this.state.model.jobList.forEach((v, i) => {
              if (this.props.data.jobName === v.name) {
                const newJobGroup = {
                  groupList: v.group_list,
                  value: v.id,
                  label: v.name,
                };
                this.selectInputHandler('jobGroup', newJobGroup);
                v.group_list.forEach((value) => {
                  if (this.props.data.jobIdx === value.name) {
                    const newGroupNumber = {
                      checkpointList: value.checkpoint_list,
                      label: value.name,
                      value: value.id,
                    };
                    this.selectInputHandler('groupNumber', newGroupNumber);
                  }
                });
              }
            });
          }
        }
      });
    }
  }

  componentDidUpdate() {
    const {
      deploymentName,
      gpuSelectedOptions,
      gpuInputValues,
      tangoTraining,
      tangoModel,
      huggingTraining,
      huggingModel,
      modelSelectType,
    } = this.state;

    if (!deploymentName) {
      this.setState({
        footerMessage: `${this.props.t('deploymentName.empty.message')}`,
      });
      return;
    } else if (gpuSelectedOptions.length > 0) {
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

      //? tangoTraining: { name: '', value: 0 }, // tango 2개, hugging 2개 만들어야함,
      //? tangoModel: { name: '', value: 0 }, // tango 2개, hugging 2개 만들어야함,
      //? huggingTraining: { name: '', value: 0 },
      //? huggingModel: { name: '', value: 0 },
    }
    if (modelSelectType === 0) {
      if (tangoTraining.name === '') {
        this.setState({
          footerMessage: `${this.props.t('selecteModel.placeholder')}`,
        });
        return;
      } else if (tangoModel.name === '') {
        this.setState({
          footerMessage: `${this.props.t('selecteModel.placeholder')}`,
        });
        return;
      }
    } else if (modelSelectType === 2) {
      if (huggingTraining.name === '') {
        this.setState({
          footerMessage: `${this.props.t('selecteModel.placeholder')}`,
        });
        return;
      } else if (huggingModel.name === '') {
        this.setState({
          footerMessage: `${this.props.t('selecteModel.placeholder')}`,
        });
        return;
      }
    }
    this.setState({ footerMessage: '' });
  }

  trainingSelectHandler = (name) => {
    const newState = {};
    newState.selectedTraining = name;
    this.setState(newState);
  };

  gpuGetHandler = (list = []) => {
    const newState = {};
    // gpu 기본 state 깔기
    if (list?.length > 0) {
      let selectedOptions = [];

      let selectedItemValue = [];
      const initialInputValues = [];

      list.forEach((v, idx) => {
        selectedItemValue = [];
        selectedOptions.push({ [idx]: false });
        initialInputValues.push('');
      });

      newState.gpuSelectedOptions = selectedOptions;
      newState.gpuInputValues = initialInputValues;
    }
    this.setState(newState);
  };

  getTrainingTypeData = async (type, wid) => {
    let workspaceId = this.props.data.workspaceId;
    if (this.state.workspace) {
      workspaceId = this.state.workspace.value;
    }
    if (!this.state.workspace && !workspaceId && wid) {
      workspaceId = wid;
    }
    const newState = {};

    const response = await callApi({
      url: `options/deployments/templates?workspace_id=${workspaceId}&deployment_template_type=${type}`,
      method: 'get',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      newState.trainingList = result;
      newState.originTrainingList = result;
    } else {
      errorToastMessage(error, message);
    }
    this.setState(newState);
    return result;
  };

  /** ================================================================================
   * API START
   ================================================================================ */

  // Deployment 생성을 위한 옵션 정보 조회
  getOptions = async (workspaceId) => {
    const response = await callApi({
      url: `deployments/options${
        workspaceId ? `?workspace_id=${workspaceId}` : ''
      }`,
      method: 'get',
    });

    const { result, status, message } = response;

    if (status === STATUS_SUCCESS) {
      return result;
    }
    toast.error(message);
    return {};
  };

  gpuSubmitHandler = () => {
    const { state } = this;

    const { gpuSelectedOptions, gpuInputValues, instanceList } = state;

    const gpu = {};

    gpuSelectedOptions.forEach((v, i) => {
      const value = Object.values(v)[0];

      if (
        value === true &&
        gpuInputValues[i] >= 0 &&
        typeof gpuInputValues[i] === 'number'
      ) {
        gpu.gpuId = instanceList[i].id;
        gpu.gpuCount = gpuInputValues[i];
        gpu.name = instanceList[i].name;
        gpu.type = instanceList[i].type.toLowerCase();
      }
    });

    return gpu;
  };

  // 배포 생성/수정
  onSubmit = async (callback) => {
    const { type } = this.props;
    const url = 'deployments';
    let method = 'POST';
    const {
      deploymentName,
      gpuUsage,
      instanceType,
      accessType,
      owner,
      tmpSelectedList: selectedList,
      deploymentId,
      deploymentDesc: description,
      workspace,
      dockerImage,
      gpuModelType,
      cpuModelList,
      selectedDeploymentType, // 4가지중 어떤거 선택했느지
      trainingToolTab, // Job 0 인지 Hps 1 인지
      jobId,
      jobModelSelectValue, // job - 체크포인트
      hpsModelSelectValue, // hps - 체크포인트
      selectedTrainingData,
      selectedHpsId,
      selectedLogId,
      selectedModel,
      jsonData,
      templateOpenStatus,
      templateNewName,
      makeNewGroup,
      templateNewDescription,
      newGroupDescription,
      editModalTemplateId,
      editOriginSelectedModel,
      clickedDataList,
      defaultGroupName,
      defaultTemplateName,
      trainingType,
      customLan,
      customFile,
      customParam,
      variablesValues,
      templateId,
      modelSelectType,
      tangoTraining,
      tangoModel,
      huggingTraining,
      huggingModel,
      huggingFaceToken,
      tangoIntelligenceType,
    } = this.state;

    const {
      gpuCount,
      gpuId,
      name: instanceName,
      type: instance_type,
    } = this.gpuSubmitHandler();

    const gpuModelNodeListJson = {};
    if (gpuModelType === 1) {
      cpuModelList.map((v) => {
        if (v.length > 0) {
          v.map(({ name, model: m }, idx) => {
            if (idx === 0) {
              gpuModelNodeListJson[m] = [name];
            } else {
              gpuModelNodeListJson[m].push(name);
            }
            return gpuModelNodeListJson[m];
          });
        }
        return gpuModelNodeListJson;
      });
    }

    // const { node_name_gpu, node_name_cpu } = this.getSliderData();

    const determineModelSelectType = (type) => {
      if (type === 1) {
        return 'custom';
      } else if (type === 0) {
        return 'built-in';
      } else if (type === 2) {
        return 'huggingface';
      }
      return ''; // 기본값
    };

    //? tangoTraining
    //? tangoModel
    //? huggingTraining
    //? huggingModel
    const body = {
      workspace_id: workspace.value,
      deployment_name: deploymentName,
      // deployment_type: deploymentType,
      owner_id: owner.value,
      access: accessType,
      description,
      gpu_model: gpuModelType === 1 ? gpuModelNodeListJson : null,
      model_type: determineModelSelectType(modelSelectType),
      is_new_model_type: tangoIntelligenceType === 1,
      //새모델 가져오기 일때 True, 학습에서 불러오기 False
    };

    // 인텔리젼스 학습에서 가져오기
    if (modelSelectType === 0 && tangoIntelligenceType === 0) {
      body.project_id = tangoTraining.value;
      body.training_id = tangoModel.value;
      body.training_type = tangoModel.type;
    }

    // 인텔리젼스 새모델 가져오기
    if (modelSelectType === 0 && tangoIntelligenceType === 1) {
      body.model_category = tangoTraining.value;
      body.huggingface_model_id = tangoModel.value;
    }

    // 허깅 학습에서 가져오기
    if (modelSelectType === 2 && tangoIntelligenceType === 0) {
      body.project_id = huggingTraining.value;
      body.training_id = huggingModel.value;
      body.training_type = huggingModel.type;
    }

    // 허깅 새모델 가져오기
    if (modelSelectType === 2 && tangoIntelligenceType === 1) {
      body.model_category = huggingTraining.name;
      body.huggingface_model_id = huggingModel.name;
      body.huggingface_model_token = huggingFaceToken;
    }

    if (instance_type === 'cpu') {
      body.instance_type = instance_type;
      body.instance_allocate = gpuCount;
    }

    if (gpuCount && gpuId) {
      body.instance_allocate = gpuCount;
      body.instance_id = gpuId;
      body.instance_name = instanceName;
      body.instance_type = instance_type;
    }

    if (templateOpenStatus) {
      body.deployment_template_name = templateNewName || defaultTemplateName;
      if (templateNewDescription)
        body.deployment_template_description = templateNewDescription;
      body.deployment_template_name = templateNewName || defaultTemplateName;
      if (makeNewGroup) {
        body.deployment_template_group_name =
          templateNewName || defaultGroupName;
        if (newGroupDescription) {
          body.deployment_template_group_description = newGroupDescription;
        }
      } else if (clickedDataList) {
        body.deployment_template_group_id = clickedDataList.id;
      }
    }

    if (type === 'EDIT_DEPLOYMENT') {
      method = 'PUT';
      body.deployment_id = deploymentId;
      // 수정 -> 템플릿 추가
      if (
        selectedDeploymentType === 'pretrained' &&
        editOriginSelectedModel.built_in_model_id ===
          selectedModel.built_in_model_id &&
        !templateOpenStatus
      ) {
        body.deployment_template_id = editModalTemplateId;
      }
    } else {
      if (templateId !== null) {
        body.deployment_template_id = templateId;
      }
    }

    // accessType이 private 일 때 users_id 추가
    if (accessType === 0) {
      body.users_id = selectedList.map(({ value }) => value);
    }
    const response = await callApi({ url, method, body });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      console.log('success deployment');
      if (callback) callback();
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

  // 라디오 버튼 이벤트 핸들러 (Deployment Type)
  radioBtnHandler = (e) => {
    const { name, value } = e.target;

    const newState = {
      [name]:
        name === 'accessType' ||
        name === 'gpuModelType' ||
        name === 'modelSelectType' ||
        name === 'tangoIntelligenceType'
          ? parseInt(value, 10)
          : value,
    };
    if (name === 'deploymentType') {
      const { dockerImageOptions } = this.state;

      // 도커이미지 설정
      const dockerImage = dockerImageOptions.filter(
        ({ label }) => label === 'jf-default',
      )[0];

      // newState.trainingModel = null;
      newState.checkpoint = null;
      newState.checkpointOptions = [];

      if (value === 'built-in') {
        newState.dockerImage = dockerImage;
        // newState.dockerImageError = '';
      } else {
        newState.dockerImageSelectedItemIdx = null;
        newState.dockerImage = null;
        //  newState.dockerImageError = null;
      }
    }

    if (name === 'instanceType') {
      newState.gpuUsage = value === 'cpu' ? 0 : 1;

      if (value !== 'cpu') {
        newState.gpuUsage = '';

        newState.gpuModelType = 1;
      } else {
        newState.gpuModelType = 0;
      }
    }

    if (name === 'gpuModelType') {
      if (parseInt(value, 10) === 0) {
        newState.gpuUsage = 1;
      }
    }

    if (name === 'tangoIntelligenceType') {
      newState.tangoTraining = { name: '', value: 0 };
      newState.tangoModel = { name: '', value: 0 };
      newState.huggingTraining = { name: '', value: 0 };
      newState.huggingModel = { name: '', value: 0 };
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 텍스트 인풋 이벤트 핸들러 (Deployment Name)
  textInputHandler = (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]:
        name === 'gpuUsage' && typeof value === 'number'
          ? parseInt(value, 10)
          : value,
      [`${name}Error`]: null,
    };

    const validate = this.validate(name, value);
    if (validate) {
      newState[`${name}Error`] = validate;
    } else if (name === 'deploymentDesc' && value.trim() === '') {
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

  getCustomList = async (training) => {
    this.setState({ customListStatus: true, customList: [] });
    const newState = {};
    setTimeout(() => {
      this.setState({ customListStatus: false });
    }, 2000);
    const response = await callApi({
      url: `options/deployments/templates/custom?training_id=${training?.training_id}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      newState.customList = result.run_code_list;
      newState.originCustomList = result.run_code_list;
    } else {
      errorToastMessage(error, message);
    }
    this.setState(newState);
  };

  getJobList = async (train, name, token) => {
    const newState = {};
    const jobDetailLength = [];
    const hpsDetailLength = [];
    newState.toolSearchValue = '';

    newState.deploymentType = train.deployment_type;

    if (train.deployment_type === 'built-in') {
      newState.dockerImage = this.state.dockerImageOptions.filter(
        (data) => data.value === train.docker_image_id,
      )[0];
    }

    newState.selectedTool = null;
    newState.selectedToolType = null;
    newState.toolModelSearchValue = '';
    newState.hpsModelSelectValue = '';
    newState.jobModelSelectValue = '';
    newState.selectedModel = train;
    newState.selectedHpsScore = '';
    newState.jobModelSelectValue = '';
    newState.hpsModelSelectValue = '';

    newState.jobModelList = [];
    newState.hpsLogList = [];
    newState.hpsModelList = [];
    newState.jobList = null;
    newState.jobDetailList = null;
    newState.jobDetailOpenList = [];
    newState.hpsList = null;
    newState.hpsDetailList = null;
    newState.hpsDetailOpenList = [];
    newState.trainingToolTab = 0;
    newState.selectedTool = null;

    newState.customLan = 'python';
    newState.customFile = '';
    newState.customParam = '';

    newState.customSearchValue = '';

    newState.customRuncode = '';
    newState.variablesValues = [{ name: '', value: '' }];

    this.trainingSelectHandler(name);

    newState.selectedTrainingData = train;

    this.setState({ trainingType: train.training_type });

    if (train.enable_to_deploy_with_gpu && !train.deployment_multi_gpu_mode) {
      newState.gpuUsage = 1;
    }

    if (train.training_type && !token) {
      this.templateIdReset();
    }

    const response = await callApi({
      url: `options/deployments/templates/usertrained?training_id=${train?.training_id}`,
      method: 'get',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { job_list, hps_list } = result;

      job_list.forEach((v) => {
        jobDetailLength.push({ arrow: false });
      });
      hps_list.forEach((v) => {
        hpsDetailLength.push({ arrow: false });
      });
      newState.jobList = job_list;
      newState.hpsList = hps_list;
      newState.originJobList = job_list;
      newState.originHpsList = hps_list;
      newState.jobDetailOpenList = jobDetailLength;
      newState.hpsDetailOpenList = hpsDetailLength;
      this.setState(newState, () => {
        this.submitBtnCheck();
      });
      return {
        jobListItem: job_list,
        hpsListItem: hps_list,
        jobDetailOpenListItem: jobDetailLength,
        hpsDetailOpenListItem: hpsDetailLength,
      };
    } else {
      newState.jobList = [];
      newState.hpsList = [];

      errorToastMessage(error, message);
      this.setState(newState, () => {
        this.submitBtnCheck();
      });
    }
  };

  handleBuiltInValue = (value, type) => {
    const newState = {
      [type]: value,
    };
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 셀렉트 박스 이벤트 핸들러 (Workspace, Training TrainingPage)
  selectInputHandler = async (name, value) => {
    const { type } = this.props;
    const { dockerImageOptions } = this.state;
    const newState = {
      [name]: value,
      [`${name}Error`]: value ? '' : null,
    };
    if (name === 'dockerImage') {
      let selectedIdx = 0;
      dockerImageOptions.forEach((v, i) => {
        if (value.value === v.value) {
          selectedIdx = i;
        }
      });
      newState.dockerImageSelectedItemIdx = selectedIdx;
    }
    if (name === 'workspace') {
      this.backBtnHandler();

      // 배포 모달 옵션 정보 조회
      const optionRes = await this.getOptions(value.value);
      const {
        // built-in 모델 옵션
        builtInUserTrainedModelOptions,
        builtInPreTrainedModelOptions,
        // 커스텀 모델 옵션
        customModelOptions,
        ownerOptions,
        gpuTotal,
        gpuFree,
        dockerImageOptions,
        builtInFilterOptions,
        cpuModelStatus,
        gpuModelListOptions,
      } = this.parseOption(optionRes);

      // 학습 모델 옵션 설정
      newState.cpuModelStatus = cpuModelStatus;
      newState.gpuModelListOptions = gpuModelListOptions;
      newState.builtInUserTrainedModelOptions = builtInUserTrainedModelOptions;
      newState.builtInPreTrainedModelOptions = builtInPreTrainedModelOptions;
      newState.customModelOptions = customModelOptions; // 커스텀 모델 옵션 (배포 타입이 Custom)
      newState.builtInFilterOptions = builtInFilterOptions;

      // 도커이미지(docker image) 초기 설정 - 초기 도커 이미지를 jf-default로 설정
      const dockerImage = dockerImageOptions.filter(
        ({ label }) => label === 'jf-default',
      )[0];
      newState.dockerImageOptions = dockerImageOptions;
      newState.dockerImage = dockerImage;
      // newState.dockerImageError = deploymentType === 'built-in' ? '' : null;
      // 소유자(owner) 설정
      newState.owner = null;
      newState.ownerOptions = ownerOptions;

      // 사용자(User) 초기 설정
      newState.userList = ownerOptions;

      // 사용가능한 GPU 수 설정
      newState.gpuTotal = gpuTotal;
      newState.gpuFree = gpuFree;

      // 모델 관련 정보 초기화
      newState.groupNumber = null;
      newState.checkpoint = null;
    } else if (name === 'trainingModel') {
      newState.groupNumber = null;
      newState.checkpoint = null;
      newState.isTrainingModelDeleted = false;
    }
    if (this.props.data.checkpoint) {
      const selectedModel = [];
      this.state.builtInUserTrainedModelOptions?.forEach((v) => {
        if (v.title === this.props.data.modelName) {
          selectedModel.push(v);
          newState.model = v;
        }
      });
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

  trainingSearch = (e) => {
    let { value } = e?.target;
    const { originTrainingList } = this.state;

    const newState = {};

    if (value === '') {
    } else {
      //원래없었어요
      const newListData = [];

      const trainingSearchData = JSON.parse(
        JSON.stringify(originTrainingList?.usertrained_training_list),
      );

      trainingSearchData.forEach((v) => {
        if (
          v.training_name.indexOf(value) !== -1 ||
          v.training_description.indexOf(value) !== -1
        ) {
          newListData.push(v);
        }
      });

      newState.trainingList = {
        built_in_model_kind_list: originTrainingList.built_in_model_kind_list,
        built_in_model_thumbnail_image_info:
          originTrainingList.built_in_model_thumbnail_image_info,
        usertrained_training_list: newListData,
      };
    }
    this.setState(newState);

    // 이름, 설명, 카테고리
  };

  // 유효성 검증
  validate = (name, value) => {
    const newState = {};

    if (name === 'deploymentName') {
      // const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

      const regType = !forbiddenChars.test(value);
      if (value === '') {
        return 'deploymentName.empty.message';
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
      } else if (this.state.gpuTotal !== 0 && value > this.state.gpuTotal) {
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

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    const { type } = this.props;
    const { state } = this;
    const {
      owner,
      gpuSelectedOptions,
      gpuInputValues,
      modelSelectType,
      tangoTraining,
      tangoModel,
      huggingTraining,
      huggingModel,
    } = state;
    const stateKeys = Object.keys(state);
    const validateState = { validate: false };
    let validateCount = 0;
    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];
      if (
        key.indexOf('Error') !== -1 &&
        state[key] !== '' &&
        key !== 'deploymentDescError' &&
        key !== 'templateNameError' &&
        key !== 'groupNameError' &&
        key !== 'dockerImageError' &&
        key !== 'jsonDataError'
      ) {
        validateCount += 1;
      }
    }

    if (!owner) {
      validateCount += 1;
    }

    if (gpuSelectedOptions.length > 0) {
      const gpuValidate = this.checkGpuInputValues(
        gpuSelectedOptions,
        gpuInputValues,
      );
      if (!gpuValidate) {
        // 인스턴스 선택 안함
        validateCount += 1;
      }
    }

    if (modelSelectType === 0) {
      if (tangoTraining.name === '' || tangoModel.name === '') {
        validateCount += 1;
      }
    }

    if (modelSelectType === 2) {
      if (huggingTraining.name === '' || huggingModel.name === '') {
        validateCount += 1;
      }
    }

    if (validateCount === 0) {
      if (this.state.sliderIsValidate) {
        validateState.validate = true;
      }
    }

    this.setState(validateState);
  };

  modelTypeHandler = (type, multiGpuMode) => {
    const { gpuModelType, cpuModelType, gpuUsage } = this.state;
    const newState = {};
    if (type === 0) {
      newState.instanceType = 'gpu';
      if (gpuModelType === 0) {
        if (multiGpuMode === 0) {
          newState.gpuUsage = 1;
        }
        newState.sliderIsValidate = true;
      } else {
        this.resourceTypeHandler(type, 1);
      }
    }
    newState.modelType = type;
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  trainingTypeArrowCustomHandler = (type, bool) => {
    const { trainingTypeArrow } = this.state;
    let newArrow = {
      ...trainingTypeArrow,
      [type]: bool,
    };

    this.setState({ trainingTypeArrow: newArrow });
  };

  trainingTypeArrowHandler = (type) => {
    const { trainingTypeArrow } = this.state;
    let newArrow = {
      ...trainingTypeArrow,
      [type]: !trainingTypeArrow[type],
    };

    this.setState({ trainingTypeArrow: newArrow });
  };

  // resource Type Check Hanlder
  resourceTypeHandler = (type, model) => {
    const { gpuSelectedOptions, cpuSelectedOptions } = this.state;
    const newState = {};
    type = Number(type);
    model = Number(model);
    const isTrue = (checkbox = []) => {
      if (checkbox.length > 0) {
        const checkTrue = checkbox.filter((check) => check);
        return checkTrue.length > 0;
      }
    };
    if (type === 0) {
      if (model === 1) {
        gpuSelectedOptions.forEach((e, i) => {
          const check = isTrue(Object.values(e));
          if (check) {
            newState.sliderIsValidate = true;
          }
          if (
            gpuSelectedOptions.length - 1 === i &&
            !check &&
            !newState?.sliderIsValidate
          ) {
            newState.sliderIsValidate = false;
          }
        });
      } else {
        newState.sliderIsValidate = true;
      }
    }
    if (type === 1) {
      if (model === 1) {
        if (cpuSelectedOptions.length > 0) {
          cpuSelectedOptions.forEach((e, i) => {
            const check = isTrue(Object.values(e));
            if (check) {
              newState.sliderIsValidate = true;
            }
            if (
              cpuSelectedOptions.length - 1 === i &&
              !check &&
              !newState?.sliderIsValidate
            ) {
              newState.sliderIsValidate = false;
            }
          });
        } else {
          newState.sliderIsValidate = false;
        }
      } else {
        newState.sliderIsValidate = true;
      }
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 다시 선택
  backBtnHandler = () => {
    const newState = {};
    newState.selectedDeploymentType = null;

    // Deployment Type 관련 state 모두 초기화
    newState.toolSearchValue = '';
    newState.selectedTraining = '';
    newState.toolModelSearchValue = '';
    newState.hpsModelSelectValue = '';
    newState.jobModelSelectValue = '';
    newState.trainingSelectedType = {
      label: 'all.label',
      value: 'all',
    };
    newState.selectedTool = null;
    newState.selectedToolType = null;
    newState.trainingTypeArrow = {
      train: true,
      tool: true,
      model: true,
      variable: true,
      hps: false,
      hpsModel: true,
      jobModel: true,
    };

    newState.trainingSelectedOwner = {
      label: 'all.label',
      value: 'allOwner',
    };
    newState.selectedHpsScore = '';
    newState.selectedHps = null;
    newState.trainingToolTab = 0;
    newState.selectedTool = null;
    newState.jobList = null;
    newState.jobDetailList = null;
    newState.jobDetailOpenList = [];
    newState.hpsList = null;
    newState.hpsDetailList = null;
    newState.hpsDetailOpenList = [];
    newState.trainingToolTab = 0;
    newState.customLan = 'python';
    newState.customFile = '';
    newState.customParam = '';
    newState.customSearchValue = '';
    newState.customRuncode = '';
    newState.variablesValues = [{ name: '', value: '' }];
    newState.trainingInputValue = '';
    newState.templateNewName = '';
    newState.templateNewDescription = '';
    newState.newGroupName = '';
    newState.newGroupDescription = '';
    newState.clickedDataList = null;
    newState.groupSelect = false;
    newState.templateNameError = false;
    newState.groupNameError = false;
    newState.makeNewGroup = false;
    newState.templateOpenStatus = false;
    newState.selectedModel = null;
    newState.modelSelectStatus = true;
    newState.clickedTemplateLists = null;
    newState.clickedGroupDataList = null;
    newState.jsonData = {};
    newState.dockerImage = this.state.dockerImageOptions.filter(
      ({ label }) => label === 'jf-default',
    )[0];
    newState.deploymentType = 'built-in';

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 배포 유형 선택 핸들러
  deploymentTypeHandler = async (type) => {
    const { t } = this.props;
    const { workspaceId } = this.props.data;
    if (!workspaceId && !this.state.workspace) {
      toast.info(t('workspaceFirst.toast.message'));
      return;
    }
    const newState = {};
    newState.selectedDeploymentType = type;

    switch (type) {
      case 'usertrained':
        this.getTrainingTypeData(type);
        break;
      case 'pretrained':
        this.getBuiltInModelList(type);
        break;
      case 'sandbox':
        newState.selectedModel = null;
        newState.deploymentType = 'custom';
        break;
      default:
        break;
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  onChangeGpuInputValue = ({ idx, value, initialValue = [] }) => {
    // 그리고 여기도 동일하게 idx와 allocate를 value에 넣는다.

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

  checkboxHandler = ({ idx, flag }) => {
    const { gpuSelectedOptions, gpuUsage, gpuInputValues } = this.state;

    let newFlag = !Object.values(gpuSelectedOptions[idx])[0];

    if (typeof flag === 'boolean') {
      newFlag = flag;
    }
    let prevSelectedOptions = gpuSelectedOptions.slice(0, idx);
    let currSelectedOptions = {
      [idx]: newFlag,
    };
    let nextSelectedOptions = gpuSelectedOptions.slice(
      idx + 1,
      gpuSelectedOptions.length,
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

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  parseOption = (option) => {
    const {
      built_in_model_kind_list: builtInFilterList = [],
      built_in_model_list: builtInModelList = [],
      trained_built_in_model_list: trainedBuiltInModelList = [],
      trained_custom_model_list: customModelList = [],
      user_list: ownerOptions = [],
      workspace_list: workspaceOptions = [],
      docker_image_list: dockerImageOptions = [],
      gpu_usage_status: gpuUsageStatus,
      gpu_model_status: gpuModelStatus = [],
      cpu_model_status: cpuModelStatus = [],
      gpu_status_deployment_list: gpuList = [],
      gpu_status_deployment_worker_list: gpuWorkerList = [],
      instance_list: instanceList = [],
    } = option;

    let gpuFree = 0;
    let gpuTotal = 0;
    if (gpuUsageStatus) {
      const { free_gpu: gpuFreeVal, total_gpu: gpuTotalVal } = gpuUsageStatus;
      gpuFree = gpuFreeVal;
      gpuTotal = gpuTotalVal;
    }

    // Custom 모델 옵션(Selectbox에 input에 적합한 형태로 변경)
    const customModelOptions = customModelList.map(
      ({ name: label, id: value, run_code_list: runCodeList }) => ({
        label,
        value,
        isDisable: runCodeList?.length < 1,
      }),
    );

    // Built-in 모델 옵션
    const builtInUserTrainedModelOptions = []; // user-trained (Custom)
    const builtInPreTrainedModelOptions = []; // pre-trained (Default)

    let newInstance = [];

    if (instanceList.length > 0) {
      newInstance = instanceList.map((v) => {
        return {
          id: v?.id,
          cpu: v?.cpu_allocate,
          gpu: v?.gpu_allocate,
          ram: v?.ram_allocate,
          name: v?.name,
          total: v?.instance_total,
          type: v?.instance_type,
        };
      });
    }

    // built-in의 user-trained 모델 옵션 필터링
    for (let i = 0; i < trainedBuiltInModelList.length; i += 1) {
      const {
        name: label,
        id: value,
        job_list: jobList,
        docker_image_id: dockerImageId,
        built_in_model_name: modelName,
        deployment_multi_gpu_mode: multiGpuMode, // 0 | 1
        enable_to_deploy_with_gpu: enableGpu, // 0 | 1
        enable_to_deploy_with_cpu: enableCpu, // 0 | 1
        deployment_status: deploymentStatus, // 0 | 1 | -1
      } = trainedBuiltInModelList[i];
      const item = {
        isTrained: true,
        title: label,
        name: modelName,
        label,
        id: value,
        value,
        jobList,
        disabled: !jobList || deploymentStatus !== 1,
        dockerImageId,
        multiGpuMode,
        enableGpu,
        enableCpu,
      };
      builtInUserTrainedModelOptions.push(item);
    }

    // built-in의 pre-trained 모델 옵션 필터링
    for (let i = 0; i < builtInModelList.length; i += 1) {
      const {
        id,
        created_by: createdBy,
        kind,
        name,
        docker_image_id: dockerImageId,
        description: desc,
        exist_default_checkpoint: existDefaultCheckpoint,
        deployment_multi_gpu_mode: multiGpuMode,
        enable_to_deploy_with_gpu: enableGpu,
        enable_to_deploy_with_cpu: enableCpu,
        deployment_status: deploymentStatus, // 0 | 1 | -1
      } = builtInModelList[i];
      const item = {
        id,
        createdBy,
        kind,
        name,
        title: name,
        desc,
        disabled: !existDefaultCheckpoint || deploymentStatus !== 1,
        enableGpu,
        enableCpu,
        multiGpuMode,
        dockerImageId,
      };
      builtInPreTrainedModelOptions.push(item);
    }

    const builtInModelOptions = [];
    const parseBuiltInModelList = [];
    for (let i = 0; i < trainedBuiltInModelList.length; i += 1) {
      const {
        name: label,
        id: value,
        job_list: jobList,
        docker_image_id: dockerImageId,
      } = trainedBuiltInModelList[i];
      const item = {
        label,
        value,
        jobList,
        disabled: !jobList,
        dockerImageId,
      };
      builtInModelOptions.push(item);
      parseBuiltInModelList.push(item);
    }

    // 빌트인 모델 카테고리 옵션
    const builtInFilterOptions = builtInFilterList.map(
      ({ kind, created_by: createdBy }) => {
        return {
          label: kind,
          value: kind,
          createdBy,
        };
      },
    );
    builtInFilterOptions.unshift({ label: 'all.label', value: 'all' });
    this.gpuGetHandler(newInstance);

    return {
      gpuTotal,
      gpuFree,
      // Built-in 모델 옵션
      builtInUserTrainedModelOptions,
      builtInPreTrainedModelOptions,
      // 커스텀 모델 옵션
      customModelOptions,
      trainedBuiltInModelList: parseBuiltInModelList,
      builtInModelOptions,
      gpuList,
      newInstance,
      cpuModelStatus, // slider에 쓸 cpu 데이터
      ownerOptions: ownerOptions.map(
        ({ user_name: label, user_id: value }) => ({
          label,
          value,
        }),
      ),
      workspaceOptions: workspaceOptions.map(({ name: label, id: value }) => ({
        label,
        value,
      })),
      dockerImageOptions: dockerImageOptions.map(
        ({ name: label, id: value }) => ({ label, value }),
      ),
      builtInFilterOptions,
      gpuModelListOptions: gpuModelStatus.map((v) => ({
        ...v,
        selected: false,
        node_list: v.node_list.map((n) => ({
          ...n,
          selected: false,
        })),
      })),
    };
  };

  // 모델 옵션에서 모델 id로 해당 모델 찾기
  findModelAndBuiltInType = (
    {
      builtInUserTrainedModelOptions,
      builtInPreTrainedModelOptions,
      customModelOptions,
    },
    deploymentType,
    modelId,
  ) => {
    let modelArr = [];
    if (deploymentType === 'built-in') {
      modelArr = builtInPreTrainedModelOptions.filter(
        ({ id }) => modelId === id,
      );
      if (modelArr.length === 0) {
        modelArr = builtInUserTrainedModelOptions.filter(
          ({ id }) => modelId === id,
        );
      }
    } else {
      modelArr = customModelOptions.filter(({ value }) => modelId === value);
    }
    return {
      model: modelArr[0],
    };
  };

  checkGroupNameDuplicate = async (value) => {
    const { workspaceId } = this.props.data;
    const resp = await callApi({
      url: `options/deployments/templates/check-group-name?deployment_template_group_name=${value}&workspace_id=${workspaceId}`,
      method: 'GET',
    });
    const newState = {};
    if (resp.result.is_duplicated) {
      newState.groupNameError = 'template.duplicate.name.label';
    } else {
      newState.groupNameError = false;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  checkTemplateNameDuplicate = async (value) => {
    const { workspaceId } = this.props.data;
    const resp = await callApi({
      url: `options/deployments/templates/check-name?deployment_template_name=${value}&workspace_id=${workspaceId}`,
      method: 'GET',
    });
    const newState = {};
    if (resp.result.is_duplicated) {
      newState.templateNameError = 'template.duplicate.name.label';
    } else {
      newState.templateNameError = false;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  templateValidate = (value) => {
    const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
    if (value === '') {
      return false;
    }
    if (!value.match(regType1) || value.match(regType1)[0] !== value) {
      return true;
    }
    return null;
  };

  getBuiltInModelList = async (type) => {
    let workspaceId = this.props.data.workspaceId;

    if (this.state.workspace) {
      workspaceId = this.state.workspace.value;
    }

    const response = await callApi({
      url: `options/deployments/templates?workspace_id=${workspaceId}&deployment_template_type=${type}`,
      method: 'GET',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      result.pretrained_built_in_model_list?.forEach((item) => {
        if (item.built_in_model_name) {
          const dis_name = Hangul.make(item.built_in_model_name);
          Object.assign(item, { dis_name });
        }
        if (item.built_in_model_description) {
          const dis_desc = Hangul.make(item.built_in_model_description);
          Object.assign(item, { dis_desc });
        }
      });
      this.setState({ modelList: result, originModelList: result });
      return result;
    } else {
      errorToastMessage(error, message);
    }
  };

  // 템플릿 id 초기화
  templateIdReset = () => {
    this.setState({ templateId: null });
  };

  getDockerImageId = async (id) => {
    const response = await callApi({
      url: `options/deployments/templates/docker-image-id?built_in_model_id=${id}`,
      method: 'get',
    });
    const { result, status } = response;
    if (status === STATUS_SUCCESS) {
      return result.docker_image_id;
    }
  };

  setData = async (data) => {
    const templateData = data.deployment_template;
    const type = data.deployment_template_type;
    const builtInModelid = data.deployment_template.built_in_model_id;
    const newState = {};
    if (templateData.deployment_type === 'built-in') {
      const dockerImageId = await this.getDockerImageId(builtInModelid);
      const { dockerImageOptions } = this.state;
      let filteredSelectedModel = {};
      if (type === 'usertrained') {
        filteredSelectedModel =
          this.state.modelList.usertrained_training_list?.filter(
            (d) => d.built_in_model_id === builtInModelid,
          )[0];
      } else if (type === 'pretrained') {
        filteredSelectedModel =
          this.state.modelList.pretrained_built_in_model_list?.filter(
            (d) => d.built_in_model_id === builtInModelid,
          )[0];
      }
      newState.selectedModel = filteredSelectedModel;

      if (filteredSelectedModel.enable_to_deploy_with_gpu) {
        newState.gpuUsage = 1;
      }
      newState.dockerImage = dockerImageOptions.filter(
        ({ value }) => dockerImageId === value,
      )[0];
    }
    if (type === 'usertrained' || type === 'custom') {
      newState.trainingTypeData = 'usertrained';

      if (templateData.deployment_type === 'built-in') {
        newState.trainingType = 'built-in';
        newState.selectedDeploymentType = 'usertrained';
        newState.selectedTraining = templateData.training_name;
        const { jobListItem, hpsListItem } = await this.getJobList(
          templateData,
          templateData.training_name,
        );

        const splitedChekcpoint = templateData.checkpoint.split('/');
        if (templateData.training_type === 'hps') {
          const hpsName = templateData.hps_name;
          const hpsId = templateData.hps_id;
          const hpsIdx = templateData.hps_group_index;
          newState.trainingToolTab = 1;
          newState.trainingType = 'built-in';

          let hpsLogTable = [];
          hpsListItem.forEach((v, i) => {
            if (v.hps_name === hpsName) {
              v.hps_group_list.forEach((model) => {
                if (model.hps_id === hpsId) {
                  hpsLogTable = model.hps_number_info;
                }
              });
            }
          });

          this.toolSelectHandler({
            type: 'HPS',
            name: hpsName,
            jobId: hpsId,
            detailNumber: hpsIdx + 1,
            hpsLogTable: hpsLogTable,
            hpsCheckpoint: hpsLogTable.max_item.checkpoint_list,
          });

          newState.hpsModelSelectValue = splitedChekcpoint.at(-1);
        } else if (templateData.training_type === 'job') {
          newState.jobModelSelectValue = splitedChekcpoint.at(-1);

          const jobName = templateData.job_name;
          const jobId = templateData.job_id;
          const jobIdx = templateData.job_group_index;
          let checkpoint = [];
          jobListItem.forEach((v, i) => {
            if (v.job_name === jobName) {
              v.job_group_list.forEach((model) => {
                if (model.job_id === jobId) {
                  checkpoint = model.checkpoint_list;
                }
              });
            }
          });
          this.toolSelectHandler({
            type: 'JOB',
            name: jobName,
            jobId: jobId,
            detailNumber: jobIdx + 1,
            jobCheckpoint: checkpoint,
          });
          newState.trainingToolTab = 0;
          newState.trainingType = 'built-in';
        }
        this.setState(newState, () => {
          this.submitBtnCheck();
        });
      }
      if (templateData.deployment_type === 'custom') {
        await this.getJobList(templateData, templateData.training_name);
        this.getCustomList(templateData);
        if (
          templateData?.environments &&
          templateData?.environments.length > 0
        ) {
          newState.variablesValues = templateData.environments;
        }

        newState.selectedTraining = templateData.training_name;
        newState.trainingType = 'advanced';
        newState.selectedDeploymentType = 'usertrained';

        if (templateData.command) {
          if (templateData.command.arguments) {
            newState.customParam = templateData.command.arguments;
          }
          if (templateData.command.binary) {
            newState.customLan = templateData.command.binary;
          }
          if (templateData.command.script) {
            newState.customFile = templateData.command.script;
          }
        }
      }
      this.deploymentTypeHandler(type === 'custom' ? 'usertrained' : type);
    } else if (
      type === 'pretrained' &&
      templateData.deployment_type !== 'built-in'
    ) {
      newState.selectedModel = data.deployment_template;
    } else if (type === 'sandbox') {
      newState.selectedModel = data.deployment_template;
      newState.jsonData = data.deployment_template;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  handleHuggingFaceToken = (v) => {
    this.setState({ huggingFaceToken: v });
  };

  render() {
    const {
      state,
      props,
      radioBtnHandler,
      textInputHandler,
      numberInputHandler,
      selectInputHandler,
      multiSelectHandler,
      modelTypeHandler,
      resourceTypeHandler,
      checkboxHandler,
      deploymentTypeHandler,
      trainingSearch,
      backBtnHandler,
      getJobList,
      getCustomList,
      toolSelectHandler,
      trainingSelectHandler,
      onSubmit,
      trainingTypeArrowHandler,
      getBuiltInModelList,
      onChangeGpuInputValue,
      handleBuiltInValue,
      handleHuggingFaceToken,
    } = this;

    return (
      <DeploymentFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        numberInputHandler={numberInputHandler}
        radioBtnHandler={radioBtnHandler}
        selectInputHandler={selectInputHandler}
        multiSelectHandler={multiSelectHandler}
        modelTypeHandler={modelTypeHandler}
        resourceTypeHandler={resourceTypeHandler}
        checkboxHandler={checkboxHandler}
        deploymentTypeHandler={deploymentTypeHandler}
        trainingSearch={trainingSearch}
        backBtnHandler={backBtnHandler}
        getJobList={getJobList}
        toolSelectHandler={toolSelectHandler}
        trainingSelectHandler={trainingSelectHandler}
        getCustomList={getCustomList}
        onSubmit={onSubmit}
        trainingTypeArrowHandler={trainingTypeArrowHandler}
        getBuiltInModelList={getBuiltInModelList}
        onChangeGpuInputValue={onChangeGpuInputValue}
        handleBuiltInValue={handleBuiltInValue}
        handleHuggingFaceToken={handleHuggingFaceToken}
      />
    );
  }
}

export default withTranslation()(DeploymentFormModalContainer);
