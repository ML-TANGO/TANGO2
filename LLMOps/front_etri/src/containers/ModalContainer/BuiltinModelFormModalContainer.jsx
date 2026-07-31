import { PureComponent } from 'react';
import { cloneDeep } from 'lodash';

// i18n
import { withTranslation } from 'react-i18next';

// Components
import BuiltinModelFormModal from '@src/components/Modal/BuiltinModelFormModal';
import { toast } from '@src/components/Toast';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, upload, STATUS_SUCCESS } from '@src/network';

class BuiltinModelFormModalContainer extends PureComponent {
  _isMounted = false;

  _MODE = import.meta.env.VITE_REACT_APP_MODE;

  state = {
    /** 기능 */
    validate: false, // 모달의 submit 버튼 활성/비활성 여부 상태 값
    validateTraining: false, // 학습 가능 활성/비활성 여부 상태 값
    validateDeployment: false, // 배포 가능 활성/비활성 여부 상태 값
    inputTypeOptions: [
      { label: 'selectFromList.label', value: 0 },
      { label: 'enterNew.label', value: 1 },
    ],
    booleanTypeOptions: [
      { label: 'support.label', value: 'true' },
      { label: 'notSupport.label', value: 'false' },
    ],
    jsonFileName: '', // import json file name
    jsonData: {}, // import json file data
    isEnterJson: false,
    /** 기본 정보 */
    modelId: null, // 모델 id
    inputTypeModelType: 0,
    newModelType: '', // 새로 입력한 모델 유형
    newModelTypeError: '',
    modelType: null, // 모델 유형
    modelTypeOptions: [], // 모델 유형 선택 옵션
    modelTypeError: null,
    filteredModelTypeOptions: [], // 생성자로 필터한 모델 유형 선택 옵션
    creator: 'JF', // 생성자 (JF|other)
    creatorOptions: [
      { label: 'JF', value: 'JF' },
      { label: 'other.label', value: 'other' },
    ], // 생성자 선택 옵션
    otherCreator: '', // JF 외에 생성자 이름
    otherCreatorError: '',
    modelName: '', // 모델 이름
    modelNameError: null,
    modelDesc: '', // 모델 설명
    inputTypeModelDirectory: 0,
    newModelDirectory: '', // 새로 입력한 모델 저장 폴더
    newModelDirectoryError: '',
    modelDirectory: null, // 목록에서 선택한 모델 저장 폴더
    modelDirectoryOptions: [], // 모델 저장 폴더 선택 옵션
    modelDirectoryBlacklist: [], // 모델 저장 폴더 선택 불가 목록
    modelDirectoryError: null,
    dockerImage: null, // 도커이미지 (run_docker_name)
    dockerImageOptions: [], // 도커이미지 선택 옵션
    dockerImageError: null,
    isThumbnail: false, // 썸네일 유무
    thumbnail: null, // 썸네일 파일 객체
    thumbnailImage: '', // 썸네일 이미지 src (view용)
    thumbnailPath: '', // 썸네일 파일 이름 (view용)
    /** 학습 정보 */
    trainingStatus: -1, // 학습 활성화 상태
    modelAlgorithm: '', // 모델 알고리즘 이름 ex) RNN LSTM
    trainingDataDesc: '', // 사용하는 학습 데이터 간단 설명
    newFolderIndex: 1,
    newFileIndex: 1,
    trainingInputDataForm: [], // 학습 데이터 입력 폼 목록
    defaultTrainingInputDataDirForm: null, // 학습 데이터 입력 디폴트 폼 - 폴더
    defaultTrainingInputDataFileForm: null, // 학습 데이터 입력 디폴트 폼 - 파일
    trainingParameters: [], // 학습 파라미터 목록
    defaultTrainingParameters: {
      name: '',
      value: '',
      description: '',
    }, // 학습 파라미터 디폴트
    evaluationIndex: '', // 평가 지표
    trainingRunCommand: '', // 학습 실행 기본(필수) 명령어
    trainingParserList: [
      {
        // 체크포인트 저장 폴더 경로 입력받을 Parser
        label: 'checkpointSaveDirPathParser',
        value: '',
        placeholder: 'weight_save_dir',
        error: '',
        optional: false,
      },
      {
        // 학습에 사용할 GPU 개수 입력받을 Parser
        label: 'trainingNumOfGpuParser',
        value: '',
        placeholder: 'gpu',
        error: '',
        optional: true,
      },
    ],
    isEnableCpuTraining: 'true', // CPU로 학습 가능 여부
    isEnableGpuTraining: 'true', // GPU로 학습 가능 여부
    isHorovodTrainingMultiGpu: 'true', // Horovod 적용 멀티 GPU 사용 (false 시 GPU 사용 1개 최대)
    isNonhorovodTrainingMultiGpu: 'true', // Horovod 미적용 내장 기능으로 멀티 GPU 사용
    isEnableRetraining: 'false', // 재학습(이어하기) 가능 여부
    retrainingParserList: [
      {
        // 학습코드에서 체크포인트 폴더 경로 입력받을 Parser
        label: 'checkpointLoadDirPathParser',
        value: '',
        placeholder: 'weight_dir_path',
        optional: true,
      },
      {
        // 학습코드에서 특정 체크포인트를 지정한 경로를 입력받을 Parser
        label: 'checkpointLoadFilePathParser',
        value: '',
        placeholder: 'weight_file_path',
        optional: true,
      },
    ],
    isMarkerLabeling: 'false', // 마커 사용 가능 여부
    isAutoLabeling: 'false', // 오토라벨링 사용 가능 여부
    /** 배포 정보 */
    deploymentStatus: -1, // 배포 활성화 상태
    defaultDeploymentInputForm: null, // 배포 입력 디폴트 폼
    deploymentInputForm: [], // 배포 입력 폼 목록
    deploymentOutputTypes: [
      // 배포 결과 유형
      {
        label: 'Text',
        subtext: ['deploymentOutputTypes.text.message'],
        value: 'text',
        checked: false,
      },
      {
        label: 'Image',
        subtext: ['deploymentOutputTypes.image.message'],
        value: 'image',
        checked: false,
      },
      {
        label: 'Audio',
        subtext: ['deploymentOutputTypes.audio.message'],
        value: 'audio',
        checked: false,
      },
      {
        label: 'Video',
        subtext: ['deploymentOutputTypes.video.message'],
        value: 'video',
        checked: false,
      },
      /* {
        label: 'Bar Chart',
        subtext: ['deploymentOutputTypes.barchart.message'],
        value: 'barchart',
        checked: false,
      }, */
      {
        label: 'Column Chart',
        subtext: ['deploymentOutputTypes.columnchart.message'],
        value: 'columnchart',
        checked: false,
      },
      {
        label: 'Pie Chart',
        subtext: ['deploymentOutputTypes.piechart.message'],
        value: 'piechart',
        checked: false,
      },
      {
        label: 'Table',
        subtext: ['deploymentOutputTypes.table.message'],
        value: 'table',
        checked: false,
      },
      {
        label: '3D Object Model',
        subtext: ['deploymentOutputTypes.obj.message'],
        value: 'obj',
        checked: false,
      },
      {
        label: 'other.label',
        subtext: ['deploymentOutputTypes.enterOther.message'],
        value: 'other',
        checked: false,
      },
    ],
    otherDeploymentOutputTypes: '', // 배포 결과 유형 기타
    otherDeploymentOutputTypesError: '',
    isExistDefaultCheckpoint: 'true', // 미리 학습된 체크포인트 존재 여부
    deploymentRunCommand: '', // 배포 실행 기본(필수) 명령어
    deploymentParserList: [
      {
        // 배포코드에서 체크포인트 폴더 경로 입력받을 Parser
        label: 'checkpointLoadDirPathParser',
        value: '',
        placeholder: 'weight_dir_path',
        optional: true,
      },
      {
        // 배포코드에서 특정 체크포인트를 지정한 경로를 입력받을 Parser
        label: 'checkpointLoadFilePathParser',
        value: '',
        placeholder: 'weight_file_path',
        optional: false,
      },
      {
        // 배포에 사용할 GPU 개수 입력받을 Parser
        label: 'deploymentNumOfGpuParser',
        value: '',
        placeholder: 'gpu',
        optional: true,
      },
    ],
    isEnableCpuDeployment: 'true', // CPU로 배포 가능 여부
    isEnableGpuDeployment: 'true', // GPU로 배포 가능 여부
    isDeploymentMultiGpu: 'false', // 배포 멀티 GPU 사용
  };

  async componentDidMount() {
    this._isMounted = true;
    const {
      type,
      data: { data: modelData },
    } = this.props;

    // 선택 옵션 설정
    await this.setOptions(type);

    if (type === 'EDIT_BUILTIN_MODEL') {
      this.setState({ modelId: modelData.id });
      this.jsonToForm(modelData);
    }
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  /** ================================================================================
   * API START
   ================================================================================ */

  /**
   * Model 선택 항목 가져오기
   */
  getOptions = async () => {
    const response = await callApi({
      url: 'options/built_in_models',
      method: 'get',
    });
    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      return result;
    }
    toast.error(message);
    return {};
  };

  /**
   * Model 선택 항목 세팅하기
   */
  setOptions = async (type) => {
    const options = await this.getOptions();

    let modelTypeOptions = options.built_in_model_kind_list || [];
    let modelDirectoryOptions = options.built_in_model_path_list || [];
    let dockerImageOptions = options.docker_image_list || [];

    modelTypeOptions = [
      ...modelTypeOptions.map(({ kind, kind_kr, created_by: creator }) => {
        let label = kind;
        if (kind_kr) {
          label = `${label} | ${kind_kr}`;
        }
        return {
          label,
          value: { kind, kind_kr, creator },
        };
      }),
    ];

    const filteredModelTypeOptions = modelTypeOptions.filter(
      ({ value: { creator } }) => creator === this.state.creator,
    );

    modelDirectoryOptions = [
      ...modelDirectoryOptions.map(({ name, generable }) => ({
        label: name,
        value: name,
        isDisable: !generable,
      })),
    ];

    const modelDirectoryBlacklist = modelDirectoryOptions
      .filter(({ isDisable }) => isDisable)
      .map(({ value }) => {
        return value;
      });

    dockerImageOptions = [
      ...dockerImageOptions.map((item) => ({
        label: item,
        value: item,
      })),
    ];

    const {
      defaultTrainingInputDataDirForm,
      defaultTrainingInputDataFileForm,
    } = this.getTrainingInputDataForm();

    let trainingInputDataForm = [];
    if (type === 'CREATE_BUILTIN_MODEL') {
      trainingInputDataForm.push(cloneDeep(defaultTrainingInputDataDirForm));
    }

    const { trainingParameters, defaultTrainingParameters } =
      this.getTrainingParameters();

    const { deploymentInputForm, defaultDeploymentInputForm } =
      this.getDeploymentInputForm();

    const newState = {
      modelTypeOptions,
      filteredModelTypeOptions,
      modelDirectoryOptions,
      modelDirectoryBlacklist,
      dockerImageOptions,
      trainingInputDataForm,
      defaultTrainingInputDataDirForm,
      defaultTrainingInputDataFileForm,
      trainingParameters,
      defaultTrainingParameters,
      deploymentInputForm,
      defaultDeploymentInputForm,
    };

    this.setState(newState);
  };

  /**
   * 학습 데이터 입력 리스트 flat하게 작업
   * children 있을 경우 바깥으로 빼기
   * @param {object} list
   */
  flattenList = (list) => {
    const newList = list;
    let prevTrainingInputDataForm = this.state.trainingInputDataForm;

    for (let i = 0; i < newList.length; i++) {
      prevTrainingInputDataForm.push(newList[i]);
      this.setState({ trainingInputDataForm: prevTrainingInputDataForm });
      if (newList[i].children) {
        this.flattenList(newList[i].children);
      }
    }
  };

  /**
   * JSON 파일을 Input Form 데이터 형태로 변환
   *
   * @param {Object} json
   */
  jsonToForm = (json) => {
    const modelData = json;

    const {
      defaultTrainingInputDataDirForm,
      trainingParameters,
      defaultTrainingParameters,
      deploymentInputForm,
      defaultDeploymentInputForm,
    } = this.state;

    let prevTrainingInputDataForm = [];
    try {
      if (modelData.training_input_data_form_list) {
        let newList = modelData.training_input_data_form_list;
        this.flattenList(newList);
        const trainingInputDataForm = [...this.state.trainingInputDataForm];
        // 루트 중복시 디폴트 루트 제거
        if (trainingInputDataForm.length > 1) {
          if (
            trainingInputDataForm[0].depth === 0 &&
            trainingInputDataForm[1].depth === 0
          ) {
            trainingInputDataForm.shift();
          }
        }
        prevTrainingInputDataForm = trainingInputDataForm.map(
          ({
            depth,
            type: t,
            name,
            category,
            category_description: categoryDesc,
            argparse,
            children,
            full_path: fullPath,
          }) => {
            let tempFullPath = ['/'];
            if (depth !== 0) {
              tempFullPath = fullPath.split('/');
              if (tempFullPath[0] === '') {
                tempFullPath[0] = '/';
              }
            }
            return {
              depth,
              type: t,
              name,
              error: '',
              category,
              categoryDesc: categoryDesc || '',
              argparse: argparse || '',
              children,
              fullPath: tempFullPath,
            };
          },
        );
      } else {
        prevTrainingInputDataForm.push(
          cloneDeep(defaultTrainingInputDataDirForm),
        );
      }
      if (prevTrainingInputDataForm.length < 1) {
        prevTrainingInputDataForm.push(
          cloneDeep(defaultTrainingInputDataDirForm),
        );
      }
    } catch (e) {
      toast.error(e);
      prevTrainingInputDataForm.push(
        cloneDeep(defaultTrainingInputDataDirForm),
      );
    }

    let prevDeploymentInputForm = [];
    try {
      if (modelData.deployment_input_data_form_list) {
        prevDeploymentInputForm = modelData.deployment_input_data_form_list.map(
          ({
            method,
            location,
            api_key: apiKey,
            value_type: valueType,
            category,
            category_description: categoryDesc,
          }) => {
            return {
              method,
              location,
              apiKey,
              valueType,
              category,
              categoryDesc: categoryDesc || '',
            };
          },
        );
      } else {
        prevDeploymentInputForm = deploymentInputForm;
      }
      if (prevDeploymentInputForm.length < 1) {
        prevDeploymentInputForm.push(cloneDeep(defaultDeploymentInputForm));
      }
    } catch (e) {
      toast.error(e);
      prevDeploymentInputForm.push(cloneDeep(defaultDeploymentInputForm));
    }

    let prevTrainingParameters = [];
    try {
      if (modelData.parameters) {
        prevTrainingParameters = Object.keys(modelData.parameters).map(
          (key) => {
            return {
              ...prevTrainingParameters,
              name: key,
              value: modelData.parameters[key],
              description: modelData.parameters_description
                ? modelData.parameters_description[key] || ''
                : '',
            };
          },
        );
      } else {
        prevTrainingParameters = trainingParameters;
      }
      if (prevTrainingParameters.length < 1) {
        prevTrainingParameters.push(cloneDeep(defaultTrainingParameters));
      }
    } catch (e) {
      toast.error(e);
      prevTrainingParameters.push(cloneDeep(defaultTrainingParameters));
    }

    const trainingParserList = [
      {
        label: 'checkpointSaveDirPathParser',
        value: modelData.checkpoint_save_path_parser || '',
        placeholder: 'weight_save_dir',
        optional: false,
      },
      {
        label: 'trainingNumOfGpuParser',
        value: modelData.training_num_of_gpu_parser || '',
        placeholder: 'gpu',
        optional: true,
      },
    ];

    const retrainingParserList = [
      {
        label: 'checkpointLoadDirPathParser',
        value: modelData.checkpoint_load_dir_path_parser_retraining || '',
        placeholder: 'weight_dir_path',
        optional: true,
      },
      {
        label: 'checkpointLoadFilePathParser',
        value: modelData.checkpoint_load_file_path_parser_retraining || '',
        placeholder: 'weight_file_path',
        optional: true,
      },
    ];

    const deploymentParserList = [
      {
        label: 'checkpointLoadDirPathParser',
        value: modelData.checkpoint_load_dir_path_parser || '',
        placeholder: 'weight_dir_path',
        optional: true,
      },
      {
        label: 'checkpointLoadFilePathParser',
        value: modelData.checkpoint_load_file_path_parser || '',
        placeholder: 'weight_file_path',
        optional: modelData.exist_default_checkpoint || false,
      },
      {
        label: 'deploymentNumOfGpuParser',
        value: modelData.deployment_num_of_gpu_parser || '',
        placeholder: 'gpu',
        optional: true,
      },
    ];

    let { deploymentOutputTypes, otherDeploymentOutputTypes } = this.state;
    try {
      if (modelData.deployment_output_types) {
        const outputTypeList = []; // 목록에 없는 값 확인할 때 비교용
        const matchTypes = modelData.deployment_output_types;
        deploymentOutputTypes = deploymentOutputTypes.map((i) => {
          const item = { ...i };
          outputTypeList.push(item.value);
          if (matchTypes.indexOf(item.value) !== -1) {
            item.checked = !item.checked;
            return item;
          }
          return item;
        });

        outputTypeList.pop(); // 'other' 제거
        for (let i = 0; i < matchTypes.length; i += 1) {
          if (outputTypeList.indexOf(matchTypes[i]) === -1) {
            // 기존 결과유형이랑 매치되는 값이 없는 값이 있으면 그 외 항목 체크 후 직접 입력란에 값 넣기
            deploymentOutputTypes[
              deploymentOutputTypes.length - 1
            ].checked = true;
            otherDeploymentOutputTypes = matchTypes[i];
          }
        }
      }
    } catch (e) {
      toast.error(e);
    }

    let newState = {};

    newState = {
      ...newState,
      creator: modelData.created_by
        ? modelData.created_by === 'JF'
          ? modelData.created_by
          : 'other'
        : 'other',
      otherCreator: modelData.created_by
        ? modelData.created_by !== 'JF'
          ? modelData.created_by
          : ''
        : '',
      otherCreatorError: modelData.created_by ? '' : null,
      modelTypeError: '',
      newModelType: modelData.kind || '',
      newModelTypeError: modelData.kind ? '' : null,
      modelName: modelData.name || '',
      modelNameError: modelData.name ? '' : null,
      modelDesc: modelData.description || '',
      modelDirectoryError: '',
      newModelDirectory: modelData.path || '',
      newModelDirectoryError: modelData.path ? '' : null,
      dockerImage: modelData.run_docker_name
        ? {
            label: modelData.run_docker_name,
            value: modelData.run_docker_name,
          }
        : null,
      dockerImageError: modelData.run_docker_name ? '' : null,
      thumbnailImage: modelData.thumbnail_image || '',
      thumbnailPath: modelData.thumbnail_path || '',
      isThumbnail: !!(modelData.thumbnail_image && modelData.thumbnail_path),
      trainingStatus: modelData.training_status,
      modelAlgorithm: modelData.model || '',
      trainingDataDesc: modelData.train_data || '',
      trainingInputDataForm: prevTrainingInputDataForm,
      evaluationIndex: modelData.evaluation_index ?? '',
      trainingParameters: prevTrainingParameters,
      trainingRunCommand: modelData.training_py_command || '',
      trainingParserList,
      isEnableCpuTraining: modelData.enable_to_train_with_cpu
        ? 'true'
        : 'false',
      isEnableGpuTraining: modelData.enable_to_train_with_gpu
        ? 'true'
        : 'false',
      isHorovodTrainingMultiGpu: modelData.horovod_training_multi_gpu_mode
        ? 'true'
        : 'false',
      isNonhorovodTrainingMultiGpu: modelData.nonhorovod_training_multi_gpu_mode
        ? 'true'
        : 'false',
      isEnableRetraining: modelData.enable_retraining ? 'true' : 'false',
      retrainingParserList,
      isMarkerLabeling: modelData.marker_labeling ? 'true' : 'false',
      isAutoLabeling: modelData.auto_labeling ? 'true' : 'false',
      deploymentStatus: modelData.deployment_status,
      deploymentInputForm: prevDeploymentInputForm,
      deploymentOutputTypes,
      otherDeploymentOutputTypes,
      deploymentRunCommand: modelData.deployment_py_command || '',
      deploymentParserList,
      isExistDefaultCheckpoint: modelData.exist_default_checkpoint
        ? 'true'
        : 'false',
      isEnableCpuDeployment: modelData.enable_to_deploy_with_cpu
        ? 'true'
        : 'false',
      isEnableGpuDeployment: modelData.enable_to_deploy_with_gpu
        ? 'true'
        : 'false',
      isDeploymentMultiGpu: modelData.deployment_multi_gpu_mode
        ? 'true'
        : 'false',
    };

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  /**
   * JSON File Read
   */
  onReadFile = (e) => {
    // JSON File read
    const file = e.target.files[0];
    const fileReader = new FileReader();
    fileReader.onload = async () => {
      try {
        const json = JSON.parse(fileReader.result);
        this.setState({
          jsonFileName: file.name,
          jsonData: json,
          isEnterJson: false,
        });
      } catch (error) {
        toast.error('JSON format error');
      }
    };
    fileReader.readAsText(file);
  };

  /**
   * JSON import
   */
  onImportJson = () => {
    const { jsonData } = this.state;
    this.setState(
      {
        inputTypeModelType: 1,
        inputTypeModelDirectory: 1,
        isEnterJson: true,
      },
      this.jsonToForm(jsonData),
    );
  };

  onSubmit = async (callback) => {
    const { type } = this.props;
    const url = 'built_in_models/list';
    let method = 'POST';
    const {
      modelId,
      creator,
      otherCreator,
      inputTypeModelType,
      modelType,
      newModelType,
      modelName,
      modelDesc,
      inputTypeModelDirectory,
      modelDirectory,
      newModelDirectory,
      dockerImage,
      thumbnail,
      isThumbnail,
      /** 학습 정보 */
      validateTraining, // 학습 필수값 입력 여부
      trainingStatus, // 학습 활성화 여부
      modelAlgorithm, // 모델 알고리즘 이름 (model) ex) RNN LSTM
      trainingDataDesc, // 사용하는 학습 데이터 간단 설명 (train_data)
      trainingInputDataForm, // 학습 데이터 입력 폼 목록
      trainingParameters, // 학습 파라미터
      evaluationIndex, // 평가 지표
      trainingRunCommand, // 학습 실행 기본 명령어
      trainingParserList, // 학습 명령어 파서 목록
      isEnableCpuTraining, // CPU로 학습 가능 여부
      isEnableGpuTraining, // GPU로 학습 가능 여부
      isEnableRetraining, // 재학습(이어하기) 가능 여부
      retrainingParserList, // 재학습 명령어 파서 목록
      isHorovodTrainingMultiGpu, // Horovod 적용 멀티 GPU 사용 (false 시 GPU 사용 1개 최대)
      isNonhorovodTrainingMultiGpu, // Horovod 미적용 내장 기능으로 멀티 GPU 사용
      isMarkerLabeling, // 마커 사용 가능 여부
      isAutoLabeling, // 오토라벨링 사용 가능 여부
      /** 배포 정보 */
      validateDeployment, // 배포 필수값 입력 여부
      deploymentStatus, // 배포 활성화 여부
      deploymentInputForm, // 배포 입력 폼 목록
      deploymentOutputTypes, // 배포 결과 유형
      otherDeploymentOutputTypes, // 배포 결과 유형 (직접 입력 내용)
      deploymentRunCommand, // 배포 실행 기본 명령어
      deploymentParserList, // 배포 명령어 파서 목록
      isExistDefaultCheckpoint, // 미리 학습된 체크포인트 존재 여부
      isEnableCpuDeployment, // CPU로 배포 가능 여부
      isEnableGpuDeployment, // GPU로 배포 가능 여부
      isDeploymentMultiGpu, // 배포 멀티 GPU 사용
    } = this.state;

    // trainingInputDataForm 가공
    const newTrainingInputDataForm = [];
    trainingInputDataForm.map(
      ({ type: t, depth, category, categoryDesc, argparse, fullPath }) => {
        return newTrainingInputDataForm.push({
          type: t,
          name: depth === 0 ? '/' : fullPath.join('/').substr(1),
          category,
          category_description: categoryDesc,
          argparse,
        });
      },
    );

    // trainingParameters 가공
    const parameters = {};
    const parametersDescription = {};
    trainingParameters.map(({ name, value, description: desc }) => {
      if (name !== '') {
        parameters[name] = value;
        parametersDescription[name] = String(desc);
      }
      return { parameters, parametersDescription };
    });

    // deploymentInputForm 가공
    const newDeploymentInputForm = [];
    deploymentInputForm.map(
      ({ method: m, location, apiKey, valueType, category, categoryDesc }) => {
        return newDeploymentInputForm.push({
          method: m,
          location,
          api_key: apiKey,
          value_type: valueType,
          category,
          category_description: categoryDesc,
        });
      },
    );

    // deploymentOutputTypes 가공
    const newDeploymentOutputTypes = [];
    deploymentOutputTypes.map(({ value, checked }) => {
      if (checked) {
        if (value === 'other') {
          newDeploymentOutputTypes.push(otherDeploymentOutputTypes);
        } else {
          newDeploymentOutputTypes.push(value);
        }
      }
      return newDeploymentOutputTypes;
    });

    // trainingParserList 가공
    const newTrainingParserList = {};
    trainingParserList.map(({ label, value }) => {
      newTrainingParserList[label] = value;
      return { ...newTrainingParserList };
    });

    // retrainingParserList 가공
    const newRetrainingParserList = {};
    retrainingParserList.map(({ label, value }) => {
      newRetrainingParserList[label] = value;
      return { ...newRetrainingParserList };
    });

    // deploymentParserList 가공
    const newDeploymentParserList = {};
    deploymentParserList.map(({ label, value }) => {
      newDeploymentParserList[label] = value;
      return { ...newDeploymentParserList };
    });

    // 선택항목 값 있으면 추가
    let body = {};

    if (modelDesc !== '') {
      body.description = modelDesc;
    }

    if (trainingDataDesc !== '') {
      body.train_data = trainingDataDesc;
    }

    if (modelAlgorithm !== '') {
      body.model = modelAlgorithm;
    }

    if (evaluationIndex !== '') {
      body.evaluation_index = evaluationIndex;
    }

    if (Object.keys(parameters).length > 0) {
      body.parameters = parameters;
      body.parameters_description = parametersDescription;
    }

    if (newTrainingParserList.trainingNumOfGpuParser !== '') {
      body.training_num_of_gpu_parser =
        newTrainingParserList.trainingNumOfGpuParser;
    }

    if (newRetrainingParserList.checkpointLoadDirPathParser !== '') {
      body.checkpoint_load_dir_path_parser_retraining =
        newRetrainingParserList.checkpointLoadDirPathParser;
    }

    if (newRetrainingParserList.checkpointLoadFilePathParser !== '') {
      body.checkpoint_load_file_path_parser_retraining =
        newRetrainingParserList.checkpointLoadFilePathParser;
    }

    if (newDeploymentParserList.checkpointLoadDirPathParser !== '') {
      body.checkpoint_load_dir_path_parser =
        newDeploymentParserList.checkpointLoadDirPathParser;
    }

    if (newDeploymentParserList.deploymentNumOfGpuParser !== '') {
      body.deployment_num_of_gpu_parser =
        newDeploymentParserList.deploymentNumOfGpuParser;
    }

    // 필수항목 추가

    if (type === 'EDIT_BUILTIN_MODEL') {
      method = 'PUT';
      body.id = modelId;
      body.kind = newModelType;
      body.path = newModelDirectory;
    } else {
      body.kind =
        inputTypeModelType === 0 ? modelType.value.kind : newModelType;
      body.path =
        inputTypeModelDirectory === 0
          ? modelDirectory.value
          : newModelDirectory;
    }

    body = {
      ...body,
      created_by: creator === 'other' ? otherCreator : creator,
      name: modelName,
      run_docker_name: dockerImage.value,
      training_status:
        trainingStatus && validateTraining ? 1 : validateTraining ? 0 : -1,
      training_input_data_form_list: newTrainingInputDataForm,
      training_py_command: trainingRunCommand,
      checkpoint_save_path_parser:
        newTrainingParserList.checkpointSaveDirPathParser,
      enable_to_train_with_cpu: isEnableCpuTraining === 'true',
      enable_to_train_with_gpu: isEnableGpuTraining === 'true',
      horovod_training_multi_gpu_mode: isHorovodTrainingMultiGpu === 'true',
      nonhorovod_training_multi_gpu_mode:
        isNonhorovodTrainingMultiGpu === 'true',
      enable_retraining: isEnableRetraining === 'true',
      marker_labeling: isMarkerLabeling === 'true',
      auto_labeling: isAutoLabeling === 'true',
      deployment_status:
        deploymentStatus && validateDeployment
          ? 1
          : validateDeployment
          ? 0
          : -1,
      deployment_input_data_form_list: newDeploymentInputForm,
      deployment_output_types: newDeploymentOutputTypes,
      deployment_py_command: deploymentRunCommand,
      checkpoint_load_file_path_parser:
        newDeploymentParserList.checkpointLoadFilePathParser,
      exist_default_checkpoint: isExistDefaultCheckpoint === 'true',
      enable_to_deploy_with_cpu: isEnableCpuDeployment === 'true',
      enable_to_deploy_with_gpu: isEnableGpuDeployment === 'true',
      deployment_multi_gpu_mode: isDeploymentMultiGpu === 'true',
    };

    const form = new FormData();
    form.append('built_in_model_json', JSON.stringify(body));

    if (thumbnail) {
      form.append('thumbnail', thumbnail);
    }

    form.append('is_thumbnail', `${isThumbnail}`); // string으로 보내기

    const response = await upload({
      url,
      method,
      form,
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      if (message === 'Unsupported file format') {
        errorToastMessage(error, message);
      } else if (type === 'CREATE_BUILTIN_MODEL') {
        defaultSuccessToastMessage('create');
      } else {
        defaultSuccessToastMessage('update');
      }
      return true;
    }
    toast.error(message);

    return false;
  };

  /** ================================================================================
   * API END
   ================================================================================ */

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

  // 라디오 버튼 이벤트 핸들러
  radioBtnHandler = (e) => {
    const { name, value } = e.target;
    const newState = {
      [name]: name.indexOf('inputType') !== -1 ? parseInt(value, 10) : value,
    };

    if (name === 'creator') {
      const { modelTypeOptions, newModelType, otherCreator } = this.state;
      if (value === 'other') {
        newState.inputTypeModelType = 1;
        newState.filteredModelTypeOptions = modelTypeOptions;
        newState.modelType = null;
        newState.modelTypeError = '';
        if (otherCreator === '') {
          newState.otherCreatorError = null;
        }
        // 학습, 배포 가능/불가능 Default값 모두 false로 설정
        newState.isEnableCpuTraining = 'false';
        newState.isEnableGpuTraining = 'false';
        newState.isHorovodTrainingMultiGpu = 'false';
        newState.isNonhorovodTrainingMultiGpu = 'false';
        newState.isEnableRetraining = 'false';
        newState.isExistDefaultCheckpoint = 'false';
        newState.isEnableCpuDeployment = 'false';
        newState.isEnableGpuDeployment = 'false';
        newState.isDeploymentMultiGpu = 'false';
      } else {
        const filteredModelTypeOptions = modelTypeOptions.filter(
          ({ value: { creator } }) => creator === value,
        );
        if (newModelType === '') {
          newState.inputTypeModelType = 0;
          newState.modelTypeError = null;
        }
        newState.filteredModelTypeOptions = filteredModelTypeOptions;
        newState.modelType = null;
        newState.otherCreatorError = '';
        // 학습, 배포 가능/불가능 약속된 Default값 설정
        newState.isEnableCpuTraining = 'true';
        newState.isEnableGpuTraining = 'true';
        newState.isHorovodTrainingMultiGpu = 'true';
        newState.isNonhorovodTrainingMultiGpu = 'true';
        newState.isEnableRetraining = 'false';
        newState.isExistDefaultCheckpoint = 'true';
        newState.isEnableCpuDeployment = 'true';
        newState.isEnableGpuDeployment = 'true';
        newState.isDeploymentMultiGpu = 'false';
      }
    } else if (name === 'inputTypeModelType') {
      const { modelType, newModelType } = this.state;
      if (Number(value) === 0) {
        if (modelType === null) {
          newState.modelTypeError = null;
        }
        newState.newModelTypeError = '';
      } else {
        if (newModelType === '') {
          newState.newModelTypeError = null;
        }
        newState.modelTypeError = '';
      }
    } else if (name === 'inputTypeModelDirectory') {
      const { modelDirectory, newModelDirectory } = this.state;
      if (Number(value) === 0) {
        if (modelDirectory === null) {
          newState.modelDirectoryError = null;
        }
        newState.newModelDirectoryError = '';
      } else {
        if (newModelDirectory === '') {
          newState.newModelDirectoryError = null;
        }
        newState.modelDirectoryError = '';
      }
    } else if (name === 'isEnableGpuTraining') {
      // GPU 학습이 불가능이면 Multi GPU 학습 모두 불가능으로 변경
      if (value === 'false') {
        newState.isHorovodTrainingMultiGpu = 'false';
        newState.isNonhorovodTrainingMultiGpu = 'false';
      }
    } else if (
      // Multi GPU 학습이 가능이면 GPU 학습도 가능으로 변경
      name === 'isHorovodTrainingMultiGpu' ||
      name === 'isNonhorovodTrainingMultiGpu'
    ) {
      if (value === 'true') {
        newState.isEnableGpuTraining = 'true';
      }
    } else if (name === 'isEnableGpuDeployment') {
      // GPU 배포가 불가능이면 Multi GPU 배포도 불가능으로 변경
      if (value === 'false') {
        newState.isDeploymentMultiGpu = 'false';
      }
    } else if (name === 'isDeploymentMultiGpu') {
      // Multi GPU 배포가 가능이면 GPU 배포도 가능으로 변경
      if (value === 'true') {
        newState.isEnableGpuDeployment = 'true';
      }
    } else if (name === 'isMarkerLabeling') {
      // 마커가 불가능이면 오토라벨링도 불가능으로 변경
      if (value === 'false') {
        newState.isAutoLabeling = 'false';
      }
    } else if (name === 'isAutoLabeling') {
      // 오토라벨링이 가능이면 마커도 가능으로 변경
      if (value === 'true') {
        newState.isMarkerLabeling = 'true';
      }
    } else if (name === 'isExistDefaultCheckpoint') {
      /**
       * default checkpoint => checkpointLoadFilePathParser
       * 있으면 => 선택사항
       * 없으면 => 필수입력
       */
      const prevDeploymentParserList = this.state.deploymentParserList;
      if (value === 'true') {
        prevDeploymentParserList[1] = {
          ...prevDeploymentParserList[1],
          optional: true,
        };
      } else {
        prevDeploymentParserList[1] = {
          ...prevDeploymentParserList[1],
          optional: false,
        };
        newState.deploymentParserList = prevDeploymentParserList;
      }
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

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

  // 셀렉트 박스 이벤트 핸들러
  selectInputHandler = async (name, value) => {
    const newState = {
      [name]: value,
      [`${name}Error`]: '',
    };

    const validate = this.validate(name, value);

    if (name === 'modelType') {
      if (validate) {
        newState.modelTypeError = validate;
      }
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 파일 인풋 이벤트 핸들러
  fileInputHandler = (e) => {
    if (e.length > 0) {
      const fReader = new FileReader();
      const thumbnail = e[0];

      fReader.addEventListener(
        'load',
        () => {
          const newState = {};
          newState.thumbnailImage = fReader.result;
          newState.thumbnailPath = thumbnail.name;
          newState.thumbnail = thumbnail;
          newState.isThumbnail = true;
          this.setState(newState, () => {
            this.submitBtnCheck();
          });
        },
        false,
      );
      fReader.readAsDataURL(thumbnail);
    }
  };

  // 썸네일 삭제
  removeThumbnail = () => {
    const newState = {};
    newState.thumbnailImage = '';
    newState.thumbnailPath = '';
    newState.thumbnail = null;
    newState.isThumbnail = false;
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 스위치 버튼 이벤트 핸들러
  switchHandler = async (type) => {
    let newState = {};
    if (type === 'training') {
      const { trainingStatus } = this.state;
      newState = {
        trainingStatus: !trainingStatus,
      };
    } else if (type === 'deployment') {
      const { deploymentStatus } = this.state;
      newState = {
        deploymentStatus: !deploymentStatus,
      };
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 파서 입력 이벤트 핸들러
  parserInputHandler = (e, type) => {
    const { name, value } = e.target;
    let newState = {};
    if (type === 'training') {
      const { trainingParserList: prevTrainingParserList } = this.state;
      const trainingParserList = prevTrainingParserList.map((i) => {
        const item = { ...i };
        if (name === item.label) {
          item.value = value;
          return item;
        }
        return item;
      });

      newState = { trainingParserList };
    } else if (type === 'retraining') {
      const { retrainingParserList: prevRetrainingParserList } = this.state;
      const retrainingParserList = prevRetrainingParserList.map((i) => {
        const item = { ...i };
        if (name === item.label) {
          item.value = value;
          return item;
        }
        return item;
      });

      newState = { retrainingParserList };
    } else {
      // type === 'deployment'
      const { deploymentParserList: prevDeploymentParserList } = this.state;
      const deploymentParserList = prevDeploymentParserList.map((i) => {
        const item = { ...i };
        if (name === item.label) {
          item.value = value;
          return item;
        }
        return item;
      });

      newState = { deploymentParserList };
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 학습 데이터 입력 폼 디폴트 값 설정
  getTrainingInputDataForm = () => {
    const defaultTrainingInputDataDirForm = {
      depth: 0,
      type: 'dir',
      name: '/',
      error: '',
      category: '',
      categoryDesc: '',
      argparse: '',
      fullPath: ['/'],
    };
    const defaultTrainingInputDataFileForm = {
      type: 'file',
      error: '',
      category: '',
      categoryDesc: '',
      argparse: '',
    };
    return {
      defaultTrainingInputDataDirForm,
      defaultTrainingInputDataFileForm,
    };
  };

  /**
   * 학습 데이터 입력 폼 추가
   *
   * @param {string} type dir/file
   * @param {Number} depth 0, 1, 2, ...
   * @param {Number} idx 0, 1, 2, ...
   */
  addTrainingInputDataForm = (type, depth, idx) => {
    const { t } = this.props;
    const targetDepth = Number(depth);
    const targetIdx = Number(idx);

    let {
      trainingInputDataForm,
      defaultTrainingInputDataDirForm,
      defaultTrainingInputDataFileForm,
      newFolderIndex,
      newFileIndex,
    } = this.state;

    let topFullPath = [];
    for (let i = targetIdx; i >= 0; i--) {
      if (trainingInputDataForm[i].depth === targetDepth - 1) {
        topFullPath = [...trainingInputDataForm[i].fullPath];
        break;
      }
    }

    if (type === 'dir') {
      topFullPath[targetDepth] = `${t('newFolderName.label', {
        idx: newFolderIndex,
      })}`;
      defaultTrainingInputDataDirForm = {
        ...defaultTrainingInputDataDirForm,
        depth: targetDepth,
        name: `${t('newFolderName.label', { idx: newFolderIndex })}`,
        fullPath: topFullPath,
      };
      trainingInputDataForm = [
        ...trainingInputDataForm.slice(0, targetIdx + 1),
        defaultTrainingInputDataDirForm,
        ...trainingInputDataForm.slice(
          targetIdx + 1,
          trainingInputDataForm.length,
        ),
      ];
      this.setState({ newFolderIndex: newFolderIndex + 1 });
    } else {
      topFullPath[targetDepth] = `${t('newFileName.label', {
        idx: newFileIndex,
      })}`;
      defaultTrainingInputDataFileForm = {
        ...defaultTrainingInputDataFileForm,
        depth: targetDepth,
        name: `${t('newFileName.label', { idx: newFileIndex })}`,
        fullPath: topFullPath,
      };
      trainingInputDataForm = [
        ...trainingInputDataForm.slice(0, targetIdx + 1),
        defaultTrainingInputDataFileForm,
        ...trainingInputDataForm.slice(
          targetIdx + 1,
          trainingInputDataForm.length,
        ),
      ];
      this.setState({ newFileIndex: newFileIndex + 1 });
    }

    this.setState({ trainingInputDataForm }, () => {
      this.submitBtnCheck();
    });
  };

  /**
   * 학습 데이터 입력 폼 삭제
   *
   * @param {string} type dir/file
   * @param {Number} depth 0, 1, 2, ...
   * @param {Number} idx 0, 1, 2, ...
   */
  removeTrainingInputDataForm = (type, depth, idx) => {
    const targetDepth = Number(depth);
    const targetIdx = Number(idx);
    let trainingInputDataForm = [...this.state.trainingInputDataForm];

    if (type === 'file') {
      // 파일은 하위 경로가 없으므로 자기것만 삭제
      trainingInputDataForm = [
        ...trainingInputDataForm.slice(0, targetIdx),
        ...trainingInputDataForm.slice(
          targetIdx + 1,
          trainingInputDataForm.length,
        ),
      ];
    } else {
      // 폴더는 하위 폴더/파일 모두 삭제
      let lastIndex = targetIdx + 1;
      const targetFullPath = trainingInputDataForm[targetIdx].fullPath[depth];
      for (let i = targetIdx + 1; i < trainingInputDataForm.length; i++) {
        const fp = trainingInputDataForm[i].fullPath[depth];
        if (
          trainingInputDataForm[i].depth > targetDepth &&
          fp === targetFullPath
        ) {
          lastIndex = i + 1;
        } else {
          break;
        }
      }
      trainingInputDataForm = [
        ...trainingInputDataForm.slice(0, targetIdx),
        ...trainingInputDataForm.slice(lastIndex, trainingInputDataForm.length),
      ];
    }

    this.setState({ trainingInputDataForm }, () => {
      this.submitBtnCheck();
    });
  };

  // 학습 데이터 입력 이벤트 핸들러
  trainingInputDataFormHandler = (e, idx) => {
    const { name, value } = e.target;

    const trainingInputDataForm = [...this.state.trainingInputDataForm];
    const inputData = trainingInputDataForm[idx];

    if (name.indexOf('type') !== -1) {
      inputData.type = value;
    } else if (name.indexOf('name') !== -1) {
      const depth = Number(inputData.depth);
      inputData.name = value;
      inputData.fullPath[depth] = value;

      for (let i = idx + 1; i < trainingInputDataForm.length; i++) {
        if (trainingInputDataForm[i].depth > depth) {
          // depth가 큰 하위 레벨에서 fullPath 변경
          trainingInputDataForm[i].fullPath[depth] = value;
        } else {
          break;
        }
      }
    } else {
      inputData[name] = value;
    }

    this.setState({ trainingInputDataForm }, () => {
      this.submitBtnCheck();
    });
  };

  // 학습 파라미터 입력 폼
  getTrainingParameters = () => {
    const trainingParameters = [];
    const defaultTrainingParameters = {
      name: '',
      value: '',
      description: '',
    };
    trainingParameters.push(cloneDeep(defaultTrainingParameters));
    return { trainingParameters, defaultTrainingParameters };
  };

  // 학습 파라미터 입력 폼 추가
  addTrainingParametersForm = () => {
    const { defaultTrainingParameters } = this.state;
    const trainingParameters = [...this.state.trainingParameters];
    trainingParameters.push({ ...defaultTrainingParameters });
    this.setState({ trainingParameters }, () => {
      this.submitBtnCheck();
    });
  };

  // 학습 파라미터 입력 폼 삭제
  removeTrainingParametersForm = (idx) => {
    let trainingParameters = [...this.state.trainingParameters];
    trainingParameters = [
      ...trainingParameters.slice(0, idx),
      ...trainingParameters.slice(idx + 1, trainingParameters.length),
    ];

    this.setState({ trainingParameters }, () => {
      this.submitBtnCheck();
    });
  };

  // 학습 파라미터 입력 이벤트 핸들러
  trainingParametersFormHandler = (e, idx) => {
    const { name, value } = e.target;

    const trainingParameters = [...this.state.trainingParameters];
    const parameters = trainingParameters[idx];
    parameters[name] = value;

    this.setState({ trainingParameters }, () => {
      this.submitBtnCheck();
    });
  };

  // 배포 테스트 입력 폼
  getDeploymentInputForm = () => {
    const deploymentInputForm = [];
    const defaultDeploymentInputForm = {
      method: 'POST',
      location: '',
      apiKey: '',
      valueType: '',
      category: '',
      categoryDesc: '',
    };
    deploymentInputForm.push(cloneDeep(defaultDeploymentInputForm));
    return { deploymentInputForm, defaultDeploymentInputForm };
  };

  // 배포 테스트 입력 폼 추가
  addDeploymentInputForm = () => {
    const { defaultDeploymentInputForm } = this.state;
    const deploymentInputForm = [...this.state.deploymentInputForm];
    deploymentInputForm.push({ ...defaultDeploymentInputForm });
    this.setState({ deploymentInputForm }, () => {
      this.submitBtnCheck();
    });
  };

  // 배포 테스트 입력 폼 삭제
  removeDeploymentInputForm = (idx) => {
    let deploymentInputForm = [...this.state.deploymentInputForm];
    deploymentInputForm = [
      ...deploymentInputForm.slice(0, idx),
      ...deploymentInputForm.slice(idx + 1, deploymentInputForm.length),
    ];

    // location 재설정
    for (let i = 0; i < deploymentInputForm.length; i++) {
      this.setLocationByCategory(
        i,
        deploymentInputForm[i].category,
        deploymentInputForm,
      );
    }

    this.setState({ deploymentInputForm }, () => {
      this.submitBtnCheck();
    });
  };

  // 배포 테스트 입력 폼 이벤트 핸들러
  deploymentInputFormHandler = (e, idx) => {
    const { name, value } = e.target;

    const deploymentInputForm = [...this.state.deploymentInputForm];
    const inputData = deploymentInputForm[idx];
    if (name.indexOf('method') !== -1) {
      inputData.method = value;
    } else if (name.indexOf('location') !== -1) {
      inputData.location = value;
    } else if (name.indexOf('categoryDesc') !== -1) {
      inputData.categoryDesc = value;
    } else if (name.indexOf('category') !== -1) {
      inputData.category = value;
      // 카테고리 선택에 따라 Location 선택 변경
      this.setLocationByCategory(idx, value, deploymentInputForm);
    } else {
      inputData[name] = value;
    }

    this.setState({ deploymentInputForm }, () => {
      this.submitBtnCheck();
    });
  };

  /**
   * 카테고리 선택에 따라 Location 선택 변경
   * - 카테고리 image / canvas-image / audio / video / csv: location file
   * - 카테고리 text
   *   - 추가를 통해 text 외 image 등 다른 카테고리와 같이 받는 경우 : location form
   *   - text 만 받는 경우 : location body
   * - 카테고리 canvas-coordinate: location form
   *
   * @param {number} idx input 인덱스
   * @param {string} category input 카테고리 값
   * @param {objecet} inputForm
   *
   */
  setLocationByCategory = (idx, category, inputForm) => {
    const newInputForm = [...inputForm];
    switch (category) {
      case 'text':
        newInputForm[idx].location = 'body';
        break;
      case 'image':
      case 'audio':
      case 'video':
      case 'csv':
      case 'canvas-image':
        newInputForm[idx].location = 'file';
        break;
      case 'canvas-coordinate':
        newInputForm[idx].location = 'form';
        break;
      default:
        newInputForm[idx].location = 'body';
    }

    if (newInputForm.length > 1) {
      let textIndex = [];
      for (let i = 0; i < newInputForm.length; i++) {
        if (newInputForm[i].category === 'text') {
          textIndex.push(i);
        }
      }

      if (newInputForm.length !== textIndex.length) {
        for (let i = 0; i < textIndex.length; i++) {
          newInputForm[textIndex[i]].location = 'form';
        }
      } else {
        for (let i = 0; i < textIndex.length; i++) {
          newInputForm[textIndex[i]].location = 'body';
        }
      }
    }
  };

  // 배포 결과유형 체크 핸들러
  deploymentOutputTypesHandler = (index) => {
    const { deploymentOutputTypes: prevDeploymentOutputTypes } = this.state;
    let otherError = '';
    const deploymentOutputTypes = prevDeploymentOutputTypes.map((v, i, arr) => {
      const value = { ...v };
      if (i === index) {
        value.checked = !v.checked;
        if (index === arr.length - 1) {
          // other
          if (value.checked) {
            otherError = null;
          }
        }
        return value;
      }
      return value;
    });

    this.setState(
      { deploymentOutputTypes, otherDeploymentOutputTypesError: otherError },
      () => {
        this.submitBtnCheck();
      },
    );
  };

  // 유효성 검증
  validate = (name, value) => {
    if (name === 'otherCreator') {
      if (value === '') {
        return 'creator.empty.message';
      }
    } else if (name === 'modelType') {
      if (value === '') {
        return 'modelType.empty.message';
      }
    } else if (name === 'newModelType') {
      if (value === '') {
        return 'newModelType.empty.message';
      }
    } else if (name === 'modelName') {
      if (value === '') {
        return 'modelName.empty.message';
      }
    } else if (name === 'modelDirectory') {
      if (value === '') {
        return 'modelDirectory.empty.message';
      }
    } else if (name === 'newModelDirectory') {
      if (value === '') {
        return 'newModelDirectory.empty.message';
      }
      const { modelDirectoryBlacklist } = this.state;
      if (modelDirectoryBlacklist.indexOf(value) !== -1) {
        return 'modelDirectoryBlacklist.message';
      }
    } else if (name === 'dockerImage') {
      if (value === '') {
        return 'dockerImage.empty.message';
      }
    } else if (name === 'otherDeploymentOutputTypes') {
      if (value === '') {
        return 'enterOther.empty.message';
      }
    }
    return null;
  };

  /**
   * 학습 활성화 가능 여부 확인
   */
  trainingCheck = () => {
    const {
      trainingInputDataForm,
      trainingRunCommand,
      trainingParserList,
      trainingParameters,
      isEnableRetraining,
      retrainingParserList,
    } = this.state;

    let validateCount = 0;

    // 학습 데이터 입력 형식 확인
    if (trainingInputDataForm) {
      if (trainingInputDataForm.length < 1) {
        validateCount += 1;
      } else {
        const fileReg = /(?=.*[:?*<>#$%&()/"|\\\s])/;
        for (let idx = 0; idx < trainingInputDataForm.length; idx += 1) {
          const name = trainingInputDataForm[idx].name;
          const depth = trainingInputDataForm[idx].depth;
          const type = trainingInputDataForm[idx].type;
          const fullPath = trainingInputDataForm[idx].fullPath.join('/');
          trainingInputDataForm[idx].error = '';
          if (name === '') {
            validateCount += 1;
            if (type === 'dir') {
              trainingInputDataForm[idx].error = 'folderName.empty.message';
            } else {
              trainingInputDataForm[idx].error = 'fileName.empty.message';
            }
          } else if (depth !== 0 && name.match(fileReg)) {
            validateCount += 1;
            if (type === 'dir') {
              trainingInputDataForm[idx].error = 'folderNameRule.message';
            } else {
              trainingInputDataForm[idx].error = 'fileNameRule.message';
            }
          } else {
            let parentIdx = 0;
            for (let i = idx; i > 0; i--) {
              if (trainingInputDataForm[i].depth < depth) {
                parentIdx = i;
                break;
              }
            }
            for (let i = parentIdx + 1; i < trainingInputDataForm.length; i++) {
              // 같은 폴더 같은 depth에서 이름 중복 체크
              if (
                i !== idx &&
                trainingInputDataForm[i].type === type &&
                trainingInputDataForm[i].depth === depth &&
                trainingInputDataForm[i].fullPath.join('/') === fullPath
              ) {
                validateCount += 1;
                trainingInputDataForm[idx].error =
                  'trainingInputDataName.duplicate.message';
                break;
              } else {
                trainingInputDataForm[idx].error = '';
              }
            }
          }
        }

        this.setState({
          trainingInputDataForm: [...trainingInputDataForm],
        });
      }
    }

    // 학습 실행 필수 명령어 확인
    if (trainingRunCommand === '') {
      validateCount += 1;
    }

    // 체크포인트를 저장할 디렉토리 경로 입력용 파서 확인
    if (trainingParserList[0].value === '') {
      validateCount += 1;
    }

    // 재학습시 특정 체크포인트를 지정한 파일 경로 입력용 파서
    if (
      isEnableRetraining === 'true' &&
      retrainingParserList[0].value === '' &&
      retrainingParserList[1].value === ''
    ) {
      validateCount += 1;
    }

    // 학습 파라미터 확인 (필수는 아니지만 이름-기본값이 있는지 확인)
    if (trainingParameters) {
      if (trainingParameters.length === 1) {
        const { name, value } = trainingParameters[0];
        if (name !== '' && (value === '' || value === null)) {
          validateCount += 1;
        }
      } else {
        for (let i = 0; i < trainingParameters.length; i += 1) {
          const { name, value } = trainingParameters[i];
          if (name === '' || value === '' || value === null) {
            validateCount += 1;
          }
        }
      }
    }

    const validateState = { validateTraining: false };
    if (validateCount === 0) {
      validateState.validateTraining = true;
    }

    this.setState(validateState);
  };

  /**
   * 배포 활성화 가능 여부 확인
   */
  deploymentCheck = () => {
    const {
      deploymentInputForm,
      deploymentOutputTypes,
      isExistDefaultCheckpoint,
      deploymentRunCommand,
      deploymentParserList,
    } = this.state;

    let validateCount = 0;

    // 배포 서비스 테스트 입력값 형식 확인
    if (deploymentInputForm) {
      if (deploymentInputForm.length < 1) {
        validateCount += 1;
      } else {
        let canvasImageCount = 0;
        let canvasCoordinateCount = 0;
        for (let i = 0; i < deploymentInputForm.length; i += 1) {
          const { apiKey, valueType, category } = deploymentInputForm[i];
          if (apiKey === '' || valueType === '' || category === '') {
            validateCount += 1;
          }
          if (category === 'canvas-image') {
            canvasImageCount += 1;
          } else if (category === 'canvas-coordinate') {
            canvasCoordinateCount += 1;
          }
        }
        // canvas-image, canvas-coordinate 쌍 있는지 체크하기
        if (canvasImageCount !== canvasCoordinateCount) {
          validateCount += 1;
        }
      }
    }

    // 배포된 서비스의 결과 유형 확인
    if (deploymentOutputTypes) {
      let checkedCount = 0;
      for (let i = 0; i < deploymentOutputTypes.length; i += 1) {
        if (deploymentOutputTypes[i].checked) {
          checkedCount += 1;
        }
      }
      if (checkedCount === 0) {
        validateCount += 1;
      }
    }

    // 배포 실행 필수 명령어 확인
    if (deploymentRunCommand === '') {
      validateCount += 1;
    }

    // 디폴트 체크포인트 없을 때
    // 특정 체크포인트를 지정한 파일 경로 입력용 파서 확인
    if (
      isExistDefaultCheckpoint === 'false' &&
      deploymentParserList[1].value === ''
    ) {
      validateCount += 1;
    }

    const validateState = { validateDeployment: false };
    if (validateCount === 0) {
      validateState.validateDeployment = true;
    }

    this.setState(validateState);
  };

  // submit 버튼 활성/비활성 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성
    const { state } = this;
    const stateKeys = Object.keys(state);

    let validateCount = 0;
    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];
      if (key.indexOf('Error') !== -1 && state[key] !== '') {
        validateCount += 1;
      }
    }
    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
    this.trainingCheck();
    this.deploymentCheck();
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
      selectInputHandler,
      switchHandler,
      fileInputHandler,
      removeThumbnail,
      trainingParametersFormHandler,
      addTrainingInputDataForm,
      removeTrainingInputDataForm,
      trainingInputDataFormHandler,
      addTrainingParametersForm,
      removeTrainingParametersForm,
      addDeploymentInputForm,
      removeDeploymentInputForm,
      deploymentInputFormHandler,
      deploymentOutputTypesHandler,
      parserInputHandler,
      onSubmit,
      onReadFile,
      onImportJson,
    } = this;
    return (
      <BuiltinModelFormModal
        {...state}
        {...props}
        textInputHandler={textInputHandler}
        radioBtnHandler={radioBtnHandler}
        selectInputHandler={selectInputHandler}
        switchHandler={switchHandler}
        fileInputHandler={fileInputHandler}
        removeThumbnail={removeThumbnail}
        addTrainingInputDataForm={addTrainingInputDataForm}
        removeTrainingInputDataForm={removeTrainingInputDataForm}
        trainingInputDataFormHandler={trainingInputDataFormHandler}
        addTrainingParametersForm={addTrainingParametersForm}
        removeTrainingParametersForm={removeTrainingParametersForm}
        trainingParametersFormHandler={trainingParametersFormHandler}
        addDeploymentInputForm={addDeploymentInputForm}
        removeDeploymentInputForm={removeDeploymentInputForm}
        deploymentInputFormHandler={deploymentInputFormHandler}
        deploymentOutputTypesHandler={deploymentOutputTypesHandler}
        parserInputHandler={parserInputHandler}
        onSubmit={onSubmit}
        onReadFile={onReadFile}
        onImportJson={onImportJson}
      />
    );
  }
}

export default withTranslation()(BuiltinModelFormModalContainer);
