import { PureComponent } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';
import { toast } from 'react-toastify';

import axios from 'axios';
import { cloneDeep } from 'lodash';

// Components
import JobCreateFormModal from '@src/components/Modal/JobCreateFormModal';

import { getDatasetList } from '@src/apis/flightbase/trainings';
import { openConfirm } from '@src/store/modules/confirm';
// Action
import { closeModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// utils
import { errorToastMessage } from '@src/utils';

const API_HOST_ENV = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

class JobCreateFormModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    const { t } = this.props;

    this._MODE = import.meta.env.VITE_REACT_APP_MODE;
    this.state = {
      userId: '', // 유저 id 값
      validate: false, // Create 버튼 활성/비활성 여부 상태 값
      builtInModelName: '', // built in model 이름 값
      builtName: '',
      trainingType: '', // training type 값
      name: '', // job or HPS name
      nameError: null, // 이름 유효성 검증 텍스트
      datasetList: [],
      selectedDataset: null,
      dataset: null, // dataset 이름 값
      datasetRootCategory: '-', // dataset root category 값
      datasetError: null, // dataset 이름 유효성 검증 텍스트
      datasetOptions: [{ label: t('noSelectDataset.label'), value: '/' }],
      dataTrainingForm: [], // model dataset type
      datasetCategoryList: [],
      runcodeOptions: [],
      runcodeName: null,
      runcodeNameError: null,
      hpsResultOptions: [
        { label: 'load.label', value: 0 },
        { label: 'new.label', value: 1 },
      ],
      hpsResult: 0,
      loadFile: null,
      loadFileOptions: [],
      saveFile: '',
      // saveFileError: null,
      searchMethod: null,
      searchMethodOptions: [],
      initPoint: '3',
      searchCount: '',
      interval: '',
      hpsParameter: [],
      hpsParameterError: null,
      defaultHpsParameter: null,
      staticParameterInfo: {},
      imageOptions: [],
      selectedImage: null,
      parameterValues: [],
      gpuModels: [],
      defaultParameter: null,
      parameterError: '',
      additionalFeatures: [],
      newDatasetList: [],
      modelInfo: [],
      modelType: 0, // cpu or gpu 선택 값
      gpuSelectedOptions: [],
      gpuInputValues: [],
      gpuAllocate: '',
      selectedInstance: {},
      // *
      retrainingOption: {},
      checkpointList: [],
      checkpoint: null,
      // * deploymentType
      trainingToolTab: 0,
      jobDetailOpenList: [],
      hpsDetailOpenList: [],
      selectedTool: null,
      hpsLogTable: [],
      selectedHpsScore: '',
      selectedToolType: null,
      toolSearchValue: '',
      toolSelectedOwner: {
        label: 'all.label',
        value: 'toolAll',
      },
      selectedHpsId: '',
      selectedLogId: '',
      toolModelSearchValue: '',
      hpsModelSelectValue: '',
      hpsModelList: [],
      jobModelList: [],
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
      footerMessage: '',
      gpuClusterOption: [
        {
          label: 'autoSetting',
          value: 1,
          descStatus: true,
          desc: this.props.t('autoSetting.desc'),
        },
        {
          label: 'manualSetting',
          value: 0,
          descStatus: false,
          desc: this.props.t('manualSetting.desc'),
        },
      ],
      gpuClusterSelectedOption: 1, // GPU 클러스터 옵션 0: 수동설정, 1: 자동설정
      gpuClusterList: [], // GPU 클러스터 리스트,
      distributionLearningOption: [
        { label: 'Nccl', value: 1 },
        { label: 'MPI', value: 2 },
        { label: 'etc.label', value: 0, disabled: true },
      ],
      distributionLearningSelectedOption: 1,
      selectedGpuList: [],
      gpuUsingError: '',
      gpuClusterType: [], //GPU 클러스터 유형 리스트
      selectedGpuClusterType: 0, // Gpu 클러스터 유형 라디오 버튼,
      distributedConfigFileList: [],
      selectedDistributedConfigFile: null,
      podGpuGcd: 0, // pod별 GPU 수
      originalGpuClusterList: null,
      trainingInfo: null,
    };
  }

  paramTypeOptions = [
    {
      label: this.props.t('staticValue.label'),
      value: 0,
      labelStyle: { marginRight: '20px' },
    },
    {
      label: this.props.t('searchRange.label'),
      value: 1,
      labelStyle: { marginRight: '20px' },
    },
  ];

  async componentDidMount() {
    const {
      data: modalData,
      groupId,
      builtName,
      trainingInfo,
    } = this.props.data;

    this.setState(
      {
        data: modalData,
        builtName,
      },
      async () => {
        await this.newGetInfo(groupId);
      },
    );

    this.setState({
      trainingInfo,
    });
  }

  componentDidUpdate() {
    const {
      selectedImage,
      name,
      runcodeName,
      gpuAllocate,
      gpuClusterSelectedOption,
      selectedGpuList,
      gpuModels,
    } = this.state;
    const { type: modalType } = this.props;

    const validations = [
      {
        condition: !name,
        message:
          modalType === 'CREATE_JOB'
            ? `${this.props.t('jobName.placeholder')}`
            : `${this.props.t('hpsName.placeholder')}`,
      },
      {
        condition: !selectedImage,
        message: `${this.props.t('dockerImage.empty.message')}`,
      },
      {
        condition:
          (gpuAllocate === undefined || typeof gpuAllocate !== 'number') &&
          gpuModels.instanceType === 'GPU',
        message: `${this.props.t('node.settingModal.gpuAllocate.errorMsg')}`,
      },
      {
        condition:
          gpuAllocate > 1 &&
          gpuClusterSelectedOption === 0 &&
          selectedGpuList.length !== gpuAllocate &&
          gpuModels.instanceType === 'GPU',
        message: `${this.props.t('gpuCountCheck.error')}`,
      },
      {
        condition: !runcodeName,
        message: `${this.props.t('runCode.placeholder')}`,
      },
    ];

    for (const { condition, message } of validations) {
      if (condition) {
        this.setState({ footerMessage: message });
        return;
      }
    }

    this.setState({ footerMessage: '' });
  }

  /** ================================================================================
   * API START
   ================================================================================ */

  newGetInfo = async (hpsGroupId) => {
    const { type: modalType } = this.props;
    const { data: modalData, groupId, builtName } = this.props.data;
    const { data } = this.state;

    let url = '';

    const FROM_HPS =
      modalType === 'CREATE_HPS_GROUP' || modalType === 'ADD_HPS';

    if (FROM_HPS) {
      url = `projects/hps-option?project_id=${data.tid}${
        hpsGroupId ? `&hps_group_id=${hpsGroupId}` : ''
      }`;
    } else {
      url = `options/project/job?project_id=${modalData?.tid}`;

      const { result, status, message } = await getDatasetList(+data.wid);
      if (status === STATUS_SUCCESS) {
        this.setState({
          datasetList: result,
        });
      } else {
        toast.error(message);
      }
    }

    const response = await callApi({
      url,
      method: 'GET',
    });
    const { status, result, message, error } = response;

    if (status !== STATUS_SUCCESS) {
      // 틀리면 바로 예외
      errorToastMessage(error, message);
      return;
    }

    const newModelInfo = result?.model_info;
    this.setState({ modelInfo: newModelInfo });

    this.setState({ newDatasetList: result.dataset_list });

    let hpsGroupData = {};
    const { hps_group_info: hpsInfo } = result;
    if (modalType === 'ADD_HPS') {
      // hpsGroupData = this.parseHPSGroupData(hpsInfo);
    }

    const {
      retraining_option: retrainingOptions,
      dataset_list: datasetList,
      image_list: imageList,
      run_code_list: runCodeList,
      built_in_model_name: builtInModelName,
      project_type: trainingType,
      parameters_info: defaultParameter,
      gpu_options: gpuOptions = {},
      model_info: modelInfo,
      instance_info: instanceInfo,
      //! load_file_list: loadFileList,
      method_list: methodList = [],
    } = result;

    const imageOptions = imageList.map(({ name, id }) => ({
      label: name,
      value: id,
    }));

    const defaultSelectImage = imageOptions.find(
      (el) => el.label === 'jf-default',
    );

    const selectedImage = hpsInfo
      ? {
          name: hpsInfo?.default_image.name,
          value: hpsInfo?.default_image.id,
        }
      : defaultSelectImage;

    const { dataset: prevDataset } = hpsGroupData;

    let newInstance = {};
    if (instanceInfo) {
      newInstance.name = instanceInfo?.resource_name;
      newInstance.total = instanceInfo?.total;
      newInstance.used = instanceInfo?.used;
      newInstance.instanceType = instanceInfo?.instance_type;
    }

    let defaultDataset = null;

    const {
      datasetOptions: prevDatasetOptions,
      runcodeOptions: prevRunCodeOptions,
      imageOptions: prevImageOptions,
    } = this.state;

    const additionalFeatures = [
      {
        name: 'gpu_acceleration',
        label: 'gpuAcceleration.label',
        subtext: ['gpuAcceleration.message'],
        value: 1,
        checked: false,
        readOnly: !gpuOptions.gpu_acceleration,
        disabled: !gpuOptions.gpu_acceleration,
      },
      {
        name: 'unified_memory',
        label: 'unifiedMemory.label',
        subtext: ['unifiedMemory.message'],
        value: 1,
        checked: false,
        readOnly: !gpuOptions.unified_memory,
        disabled: !gpuOptions.unified_memory,
      },
      {
        name: 'rdma',
        label: 'rdmaViaInfiniBand.label',
        subtext: ['rdmaViaInfiniBand.message'],
        value: 1,
        checked: false,
        readOnly: !gpuOptions.rdma,
        disabled: !gpuOptions.rdma,
      },
    ];

    // Load file, Save file 설정
    let loadFileOptions = [];
    let loadFile = null;
    let saveFile = '';
    let initPoint = '3';

    if (hpsGroupData.prevSaveFile) {
      const { prevSaveFile } = hpsGroupData;
      loadFile = { label: prevSaveFile, value: prevSaveFile };
      [saveFile] = prevSaveFile.split('.');
      initPoint = '0';
    }

    //! Seach method 설정
    let searchMethod = null;
    if (methodList && methodList.length > 0) {
      const [searchMethodItem] = methodList;
      searchMethod = hpsGroupData.defaultSearchMethod || searchMethodItem.value;
      if (hpsGroupData.numOfSearchParam > 1) methodList[2].disabled = true;
    }

    this.setState(
      {
        selectedImage, // temporary code
        imageOptions: [...prevImageOptions, ...imageOptions],
        dataset: trainingType === 'built-in' ? null : defaultDataset,
        datasetError:
          trainingType === 'advanced' || trainingType === 'basic' ? '' : null,
        builtInModelName,
        // dataTrainingForm,
        // datasetRootCategory,
        gpuModels: newInstance,
        trainingType,
        // runcodeName,
        additionalFeatures,
        parameterValues:
          trainingType === 'built-in' ? [defaultParameter] : [{ val: '' }],
        defaultParameter,
        loadFileOptions,
        loadFile,
        saveFile,
        initPoint,
        searchMethodOptions: methodList,
        searchMethod,
        // hpsParameter,
        // defaultHpsParameter,
        staticParameterInfo: hpsGroupData.parameterInfo,
        validate: modalType === 'ADD_HPS',

        //! checkpointList: checkpointOption,
        retrainingOption: retrainingOptions,
      },
      () => {
        if (modalType === 'ADD_HPS' && trainingType === 'built-in')
          this.searchSelectHandler(
            defaultDataset,
            'dataset',
            hpsGroupData.defaultCategoryData,
          );
      },
    );
  };

  /** ================================================================================
   * API END
   ================================================================================ */

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

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

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성
    const { state } = this;
    const { type: modalType } = this.props;
    const stateKeys = Object.keys(state);
    const {
      hpsParameter,
      gpuAllocate,
      selectedGpuList,
      gpuClusterSelectedOption,
      gpuModels,
    } = state;
    let validateCount = 0;

    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];

      if (key?.indexOf('Error') !== -1) {
        if (
          state[key] !== '' &&
          key !== 'runcodeNameError' &&
          key !== 'hpsParameterError' &&
          key !== 'gpuUsingError'
        ) {
          validateCount += 1;
        }
        if (
          modalType === 'CREATE_HPS_GROUP' &&
          state[key] !== '' &&
          key === 'hpsParameterError' &&
          key !== 'gpuUsingError'
        ) {
          validateCount += 1;
        }
      }
    }

    //  // 데이터셋 카테고리
    //   if (trainingType === 'built-in') {
    //     if (datasetCategoryList.length === 0) {
    //       validateCount += 1;
    //     }
    //     for (let i = 0; i < datasetCategoryList.length; i += 1) {
    //       const { name, selected } = datasetCategoryList[i];
    //       if (name !== '/' && !selected) validateCount += 1;
    //     }
    //   }

    if (
      gpuClusterSelectedOption === 0 &&
      gpuAllocate > 1 &&
      gpuAllocate !== selectedGpuList.length &&
      gpuModels.instanceType === 'GPU'
    ) {
      validateCount += 1;
    }

    if (typeof gpuAllocate !== 'number' && gpuModels.instanceType === 'GPU') {
      validateCount += 1;
    }

    // HPS 생성 모달일 때
    if (modalType === 'CREATE_HPS_GROUP') {
      // if (this.hpsParameterValidate(hpsParameter)) validateCount += 1;
    }

    if (!state.selectedImage) {
      validateCount += 1;
    }

    if (!state.runcodeName) {
      validateCount += 1;
    }
    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
  };

  // submit 버튼 클릭 이벤트
  onSubmit = async (callback, parserList) => {
    const { type } = this.props;
    const {
      name: jobNames,
      dataset,
      selectedDataset,
      runcodeName,
      data,
      selectedImage,
      parameterValues,
      additionalFeatures,
      trainingType,
      datasetCategoryList,
      modelType,
      gpuAllocate,
      selectedGpuList, // 자동이면 빈 배열, 수동이면 값 넣어서 보냄
      distributionLearningSelectedOption, // 1이면 NCLL 0이면 "" 빈 문자열
      gpuClusterSelectedOption, // 1이면 자동, 0이면 수동
      selectedGpuClusterType, // 선택된 GPU 클러스터 유형 index
      gpuClusterType, // gpu 클러스터 리스트
      selectedDistributedConfigFile, // 선택된 분산학습 호스트 설정 파일 {label, value}
      originalGpuClusterList, // 서버에서 받은 Node gpu 데이터값
    } = this.state;

    const jobs = [];

    const jobCheckpointBodys = {};

    const body = {};

    if (gpuAllocate > 1) {
      body.gpu_cluster_auto = gpuClusterSelectedOption === 1 ? true : false;
      body.distributed_framework =
        distributionLearningSelectedOption === 1 ? 'NCCL' : 'MPI';
      body.distributed_config_path = selectedDistributedConfigFile.label;

      const { gpu_count, status, server } =
        gpuClusterType[selectedGpuClusterType];

      if (gpuClusterSelectedOption === 1) {
        // GPU 클러스터 자동설정
        body.gpu_auto_select = { gpu_count, server, status };
        body.gpu_cluster_case_old = gpuClusterType.map(
          ({ gpu_count, server, status }) => ({ gpu_count, server, status }),
        );
      } else {
        // GPU 클러스터 수동설정
        body.gpu_select = selectedGpuList;
        body.pod_per_gpu = gpu_count;
        body.gpu_cluster_list_old = originalGpuClusterList;
      }
    }

    for (let i = 0; i < parameterValues.length; i += 1) {
      let parameter = '';
      if (trainingType === 'built-in') {
        parameter = JSON.parse(JSON.stringify(parserList));

        const ObjKeyArr = Object.keys(parameterValues[i]);

        // [batch_size, data, dropuput_rate ....];
        for (let j = 0; j < ObjKeyArr.length; j += 1) {
          const keyItem = ObjKeyArr[j];
          parameter[keyItem] = parameterValues[i][keyItem].default_value;
        }

        for (let j = 0; j < datasetCategoryList.length; j += 1) {
          const { argparse, selected, name } = datasetCategoryList[j];
          // eslint-disable-next-line no-continue
          if (!selected && name !== '/') continue;
          if (name === '/') {
            parameter[argparse] = '/user_dataset/';
          } else {
            parameter[argparse] = `/user_dataset/${selected.name}`;
          }
        }
      } else {
        const { val } = parameterValues[i];
        parameter = val;
      }

      const type = modelType === 1 ? 'cpu' : 'gpu';

      // training_id: parseInt(data?.tid, 10),

      // if (dataset?.value !== '/') {
      //   body.dataset_id = dataset?.value;
      // }
      body.dataset_id = selectedDataset.id;
      body.project_id = parseInt(data?.tid, 10);
      body.training_name = jobNames;
      body.image_id = selectedImage?.value;

      body.run_code = runcodeName?.value;
      body.parameter = parameter;
      // body.resource_type = type;

      if (typeof gpuAllocate === 'number') {
        body.gpu_count = gpuAllocate;
        // body.resource_group_id = instance.resource_group_id;
        // body.resource_name = instance.resource_name;
        // body.gpu_resource_group_id = instance.gpu_resource_group_id;
      }

      // 참고용 코드
      // for (let j = 0; j < additionalFeatures.length; j += 1) {
      //   const { name, checked, value } = additionalFeatures[j];
      //   param[name] = checked ? value : 0;
      // }
      // jobs.push(param);
    }

    const response = await callApi({
      url: 'projects/trainings',
      method: 'POST',
      body,
    });

    const { status, message, error, result } = response;
    // result가 false로 넘어오면 클러스터 유형이 변경됐다는 모달을 띄어주면 된다
    if (!result) {
      this.props.openConfirm({
        title: 'gpuClusterCategory.label',
        content: 'gpuTypePopupfirst.desc',
        submit: {
          text: 'confirm.label',
        },
        cancel: {
          text: 'cancel.label',
        },
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      });

      this.fetchGpuClusterType();

      return false;
    }

    if (status === STATUS_SUCCESS) {
      this.props.closeModal(type);
      if (callback) callback();
      console.log('success training');
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  // 파라미터 인풋 추가 이벤트 핸들러
  onAdd = () => {
    const { trainingType, defaultParameter } = this.state;
    const parameterValues = [...this.state.parameterValues];
    if (parameterValues.length > 9) return;
    parameterValues.push(
      trainingType === 'built-in' ? { ...defaultParameter } : { val: '' },
    );
    const parameterError = '';
    this.setState(
      {
        parameterValues,
        parameterError,
      },
      () => {
        this.submitBtnCheck();
      },
    );
  };

  // 파라미터 인풋 삭제 이벤트 핸들러
  onRemove = (idx) => {
    let parameterValues = [...this.state.parameterValues];
    parameterValues = [
      ...parameterValues.slice(0, idx),
      ...parameterValues.slice(idx + 1, parameterValues.length),
    ];
    const validate = this.validate('parameters', parameterValues);
    let parameterError = '';
    if (validate) {
      parameterError = validate;
    }
    this.setState({
      parameterValues,
      parameterError,
    });
  };

  // Basic Advanced 타입일 때 파라미터 변경 이벤트 핸들러
  onChangeParameter = (e, idx) => {
    const { value } = e.target;
    const number = parseInt(idx, 10);
    const parameterValues = [...this.state.parameterValues];
    parameterValues[number].val = value;
    this.setState({
      parameterValues,
    });
  };

  // 빌트인 타입일 때 파라미터 변경 이벤트 핸들러
  onChangeBuiltInParameter = (e, idx, key) => {
    const { value } = e.target;
    const parameterValues = [...this.state.parameterValues];
    const params = parameterValues[idx][key];
    parameterValues[idx][key] = { ...params, default_value: value };
    this.setState({
      parameterValues,
    });
  };

  // 셀렉트 박스 핸들러
  selectInputHandler = (name, value) => {
    const newState = {
      [name]: value.value === null ? null : value,
    };
    if (name === 'loadFile') {
      const [saveFileName] = value.value ? value.value.split('.') : [''];
      newState.saveFile = saveFileName;
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 데이터셋 셀렉트 박스 이벤트 핸들러
  searchSelectHandler = (selected, name, defaultCategoryData) => {
    const { trainingType, dataset } = this.state;
    if (dataset && dataset.value === selected.value) return;
    const newState = {
      [name]: selected,
      [`${name}Error`]: '',
    };
    if (
      trainingType === 'built-in' &&
      name === 'dataset' &&
      selected.label !== 'None'
    ) {
      const validate = this.validate(name, selected);
      // 데이터셋 카테고리별 옵션
      let datasetError = '';
      if (validate) {
        datasetError = validate;
      }

      newState.datasetError = datasetError;
    }

    this.setState(newState, () => this.submitBtnCheck());
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  /** ================================================================================
   * Validate START
   ================================================================================ */

  // 유효성 검증
  validate = (name, value) => {
    const { type: modalType } = this.props;
    if (name === 'name') {
      // const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
      if (value === '') {
        return `${
          modalType === 'CREATE_JOB'
            ? 'jobName.empty.message'
            : 'hpsName.empty.message'
        }`;
      }
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

      const regType = !forbiddenChars.test(value);

      if (!regType) {
        return 'newNameRule.message';
      }
      // if (!value.match(regType1) || value.match(regType1)[0] !== value) {
      //   return 'nameRule.message';
      // }
    } else if (name === 'dataset') {
      if (!value.generable) {
        const {
          unsatisfied: { dir, file },
        } = value;
        const { t } = this.props;
        return `${t('datasetFormRule.error.message')} ( Dir: ${
          dir.length !== 0 ? dir.join(',') : ' - '
        } File: ${file.length !== 0 ? file.join(',') : ' - '} )`;
      }
    } else if (name === 'parameters') {
      if (value.length === 0) {
        return 'parameter.empty.message';
      }
    } else if (name === 'saveFile') {
      if (value === '') {
        return 'save file을 입력하세요';
      }
    } else if (name === 'hpsParameter') {
      // const hpsValidate = this.hpsParameterValidate(value);
      // if (hpsValidate) {
      //   return hpsValidate;
      // }
    }
    return null;
  };

  onChangeGpuInputValue = (v) => {
    this.setState({ gpuAllocate: v, selectedGpuList: [] }, async () => {
      this.submitBtnCheck();
      await this.fetchGpuClusterType();
      await this.fetchNodeGpuList();
    });
  };

  handleGpuClusterOption = (value) => {
    this.setState(
      { gpuClusterSelectedOption: parseInt(value, 10), selectedGpuList: [] },
      async () => {
        this.submitBtnCheck();
        await this.fetchGpuClusterType();
        await this.fetchNodeGpuList();
      },
    );
  };

  handleDistributionLearningOption = (value) => {
    this.setState({ distributionLearningSelectedOption: parseInt(value, 10) });
  };

  handleSelectedGpuCluster = ({ nodeName, gpu_uuid, used, originUsed }) => {
    const { gpuAllocate, selectedGpuList } = this.state;

    // 0 사용가능, 1 사용중, 2 선택 완료
    if (gpuAllocate === selectedGpuList.length && used !== 2) {
      return;
    }

    this.setState(
      (prevState) => {
        const updatedGpuClusterList = prevState.gpuClusterList.map(
          (cluster) => {
            return {
              ...cluster,
              gpuList: cluster.gpuList.map((gpu) => {
                if (gpu.gpu_uuid === gpu_uuid) {
                  return {
                    ...gpu,
                    used: gpu.used === 0 || gpu.used === 1 ? 2 : originUsed,
                  };
                }
                return gpu;
              }),
            };
          },
        );

        let updatedselectedGpuList = [...prevState.selectedGpuList];

        if (used === 0 || used === 1) {
          updatedselectedGpuList.push({
            node_name: nodeName,
            gpu_uuid,
          });
        } else {
          updatedselectedGpuList = updatedselectedGpuList.filter(
            (gpu) => !(gpu.node_name === nodeName && gpu.gpu_uuid === gpu_uuid),
          );
        }

        return {
          gpuClusterList: updatedGpuClusterList,
          selectedGpuList: updatedselectedGpuList,
        };
      },
      () => {
        this.submitBtnCheck();
        this.checkSelectedUsedGpu();
        this.calculatePodGpuCount();
        this.fetchNodeGpuList();
      },
    );
  };

  checkSelectedUsedGpu = () => {
    const { selectedGpuList, gpuClusterList } = this.state;
    const uuid = selectedGpuList.map(({ gpu_uuid }) => gpu_uuid);
    let usedCount = 0;

    gpuClusterList.forEach(({ gpuList }) => {
      gpuList.forEach(({ gpu_uuid, originUsed }) => {
        if (uuid.includes(gpu_uuid) && originUsed === 1) {
          usedCount += 1;
          this.setState({
            gpuUsingError: `${this.props.t('gpuUsing.warning')}`,
          });
        }
      });
    });

    if (usedCount === 0) {
      this.setState({
        gpuUsingError: '',
      });
    }
  };

  handleGpuClusterType = (value) => {
    this.setState({
      selectedGpuClusterType: parseInt(value, 10),
    });
  };

  checkIsGpuClusterTypeDiff = (prevGpuCluster, curGpuCluster) => {
    const sortFn = (a, b) => {
      if (a.gpu_count !== b.gpu_count) {
        return a.gpu_count - b.gpu_count;
      } else {
        return a.server - b.server;
      }
    };

    const sortedPrev = [...prevGpuCluster].sort(sortFn);
    const sortedCur = [...curGpuCluster].sort(sortFn);

    if (sortedPrev.length !== sortedCur.length) {
      return false;
    }

    for (let i = 0; i < sortedPrev.length; i++) {
      const prevItem = sortedPrev[i];
      const curItem = sortedCur[i];

      if (
        prevItem.gpu_count !== curItem.gpu_count ||
        prevItem.server !== curItem.server ||
        prevItem.status !== curItem.status
      ) {
        return false;
      }
    }

    return true;
  };

  fetchGpuClusterType = async () => {
    const { data: modalData } = this.props.data;
    const { gpuAllocate, gpuClusterSelectedOption } = this.state;

    if (gpuAllocate > 1 && gpuClusterSelectedOption === 1) {
      const response = await callApi({
        url: `projects/gpu-cluster-auto?project_id=${modalData?.tid}&gpu_count=${gpuAllocate}`,
        method: 'GET',
      });
      const { status, result } = response;

      if (status === STATUS_SUCCESS) {
        this.updateGpuClusterType(result);
      }
    }
  };

  handleDistributedConfigFileSelect = (value) => {
    this.setState({ selectedDistributedConfigFile: value });
  };

  calculatePodGpuCount = () => {
    const { gpuClusterList } = this.state;
    const podGpuCount = {};

    gpuClusterList.forEach(({ nodeName, gpuList }) => {
      podGpuCount[nodeName] = 0;
      gpuList.forEach(({ used }) => {
        if (used === 2) {
          podGpuCount[nodeName] += 1;
        }
      });
    });

    function gcd(a, b) {
      while (b !== 0) {
        let temp = b;
        b = a % b;
        a = temp;
      }
      return a;
    }

    // 배열의 숫자들의 최대공약수를 구하는 함수
    function findGCD(arr) {
      if (arr.length === 0) return 0;

      let result = arr[0];

      for (let i = 1; i < arr.length; i++) {
        result = gcd(result, arr[i]);

        if (result === 1) {
          return 1;
        }
      }

      return result;
    }

    const totalCount = findGCD(Object.values(podGpuCount));
    this.setState({ podGpuGcd: totalCount });
  };

  fetchNodeGpuList = async () => {
    // 이 함수가 현재 gpu할당, 클러스터 설정일때만 불러오고 있는데 처음으로 받을때 gpu_select를 빈배열로 보여주고
    // 만약 gpuAllocate하고, selectedGpuList갯수가 같으면 그때 gpu_select에 넣어서 보내서 갱신을 해주면 된다.
    const { data: modalData } = this.props.data;
    const { gpuAllocate, gpuClusterSelectedOption, selectedGpuList } =
      this.state;

    if (
      gpuClusterSelectedOption === 1 ||
      gpuAllocate < 2 ||
      (gpuAllocate !== selectedGpuList.length && selectedGpuList.length > 0)
    )
      return;

    const uuid = selectedGpuList.map(({ gpu_uuid }) => gpu_uuid);

    const response = await callApi({
      url: `projects/gpu-cluster`,
      method: 'POST',
      body: {
        project_id: Number(modalData?.tid),
        gpu_count: gpuAllocate,
        gpu_select: selectedGpuList.length > 0 ? selectedGpuList : [],
      },
    });

    const { status, result } = response;
    const { gpu_cluster_list, gpu_cluster_cases } = result;

    if (gpu_cluster_list) {
      const nodes = Object.keys(gpu_cluster_list);
      const list = [];

      nodes.forEach((node) => {
        list.push({
          nodeName: node,
          gpuList: gpu_cluster_list[node].map(
            ({ gpu_name, gpu_uuid, used }) => ({
              gpu_name,
              gpu_uuid,
              used: uuid.includes(gpu_uuid) ? 2 : used,
              originUsed: used,
            }),
          ),
        });
      });

      this.setState({
        gpuClusterList: list,
        originalGpuClusterList: gpu_cluster_list,
      });
    }

    if (gpu_cluster_cases) {
      this.updateGpuClusterType(gpu_cluster_cases);
    }
  };

  updateGpuClusterType = (gpuClusterTypeList) => {
    const { gpuClusterType: prevGpuCluster } = this.state;

    const gpuClusterType = gpuClusterTypeList.map(
      ({ gpu_count, server, status }, index) => ({
        label: `${gpu_count}-GPU PODx${server}`,
        value: index,
        desc: status
          ? `${this.props.t('gpuRecommandTime.desc')}`
          : `${this.props.t('gpuWarningTime.desc')}`,
        descStatus: status,
        gpu_count,
        server,
        status,
      }),
    );

    const isSameGpuClusterType = this.checkIsGpuClusterTypeDiff(
      prevGpuCluster,
      gpuClusterType,
    );

    if (
      prevGpuCluster.length &&
      gpuClusterType.length &&
      !isSameGpuClusterType
    ) {
      this.props.openConfirm({
        title: 'gpuClusterCategory.label',
        content: 'gpuTypePopupfirst.desc',
        submit: {
          text: 'confirm.label',
        },
        cancel: {
          text: 'cancel.label',
        },
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      });
    }

    this.setState({
      gpuClusterType,
      selectedGpuClusterType: 0,
    });
  };

  handleDatasetList = (v) => {
    console.log(v);
    this.setState({
      selectedDataset: v,
    });
  };

  /** ================================================================================
   * Parse END
   ================================================================================ */

  render() {
    const {
      state,
      props,
      textInputHandler,
      onSubmit,
      onAdd,
      onChangeParameter,
      onChangeBuiltInParameter,
      onRemove,
      selectInputHandler,
      searchSelectHandler,
      onChangeGpuInputValue,
      handleGpuClusterOption,
      handleDistributionLearningOption,
      handleSelectedGpuCluster,
      handleGpuClusterType,
      handleDistributedConfigFileSelect,
      handleDatasetList,
    } = this;
    return (
      <JobCreateFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        onChangeParameter={onChangeParameter}
        onChangeBuiltInParameter={onChangeBuiltInParameter}
        selectInputHandler={selectInputHandler}
        onSubmit={onSubmit}
        onAdd={onAdd}
        onRemove={onRemove}
        searchSelectHandler={searchSelectHandler}
        onChangeGpuInputValue={onChangeGpuInputValue}
        handleGpuClusterOption={handleGpuClusterOption}
        handleDistributionLearningOption={handleDistributionLearningOption}
        handleSelectedGpuCluster={handleSelectedGpuCluster}
        handleGpuClusterType={handleGpuClusterType}
        handleDistributedConfigFileSelect={handleDistributedConfigFileSelect}
        handleDatasetList={handleDatasetList}
      />
    );
  }
}

export default connect(null, { closeModal, openConfirm })(
  withTranslation()(JobCreateFormModalContainer),
);
