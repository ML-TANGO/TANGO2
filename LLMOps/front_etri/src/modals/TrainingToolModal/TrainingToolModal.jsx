import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components
import TrainingToolModalContent from '@src/components/modalContents/TrainingToolModalContent/TrainingToolModalContent';
import usePortForwardingInputBox from '@src/components/organisms/PortForwardingInputBox/usePortForwardingInputBox';
// Custom Hooks
import useResourceSettingBox from '@src/components/organisms/ResourceSettingBox/useResourceSettingBox';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

/**
 * 학습 도구 모달 컴포넌트
 * 모달의 상태 관리 및 이벤트 정의
 * src/containers/ModalContainer/ModalContainer.jsx에서 사용
 * @param {{
 *  type: 'EDIT_TRAINING_TOOL',
 *  data: any,
 * }} props
 * @returns
 */
function TrainingToolModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { toolType, toolId, trainingId } = modalData;
  const [checkOption, setCheckOption] = useState(true); // 체크박스 valid
  const [sliderData, setSliderData] = useState(null);
  const [gpuCount, setGpuCount] = useState(1);
  const [prevSliderData, setPrevSliderData] = useState(null); // 편집 초깃값
  const [gpuModels, setGpuModels] = useState(null);

  // modal title
  const [title, setTitle] = useState('');

  const [visualStatus, setVisualStatus] = useState({
    dockerImg: {},
    portInfo: {},
    resourceInfo: {},
  });

  // Component State
  const [dockerState, setDockerState] = useState({
    value: null,
    options: [{ label: 'jf-default', value: 'a' }],
  });

  // Custom Hooks
  const [
    gpuModelState,
    setGpuModelState,
    gpuSettingBoxRender,
    sliderValue,
    modelType,
    sliderIsValidate,
  ] = useResourceSettingBox({
    sliderData,
    prevSliderData,
    type,
    gpuModels,
    gpuCount,
    visualStatus,
  });
  const [
    portForwardingState,
    setPortForwardingState,
    portForwardingInputRender,
  ] = usePortForwardingInputBox({
    toolType,
    toolId,
    visualStatus,
    type,
  });
  // event Handler
  const dockerHandler = (value) => {
    setDockerState((state) => ({ ...state, value }));
  };

  // 모든 인풋 유효성 검증 여부 (true 일 경우 저장 버튼 활성화)
  const isValidate = gpuModelState.isValid && portForwardingState.isValid;

  const onSubmit = async (callback) => {
    const { node_name_gpu, node_name_cpu } = sliderValue();

    let body = {
      training_tool_id: toolId,
      gpu_count: modelType === 1 ? 0 : Number(gpuModelState.gpuUsage),
      gpu_model: gpuModelState.gpuModel,
      docker_image_id: dockerState.value.value,
      port_list: portForwardingState.portForwardingList,
      node_name_cpu,
      node_name_gpu,
    };
    let method = 'put';
    let url = 'trainings/tool';

    if (type === 'CREATE_TRAINING_TOOL') {
      const checked = checkOption ? 1 : 0;
      url = 'trainings/tool_replica';
      body = {
        training_id: trainingId,
        training_tool_type: toolType,
        port_list: portForwardingState.portForwardingList,
        gpu_count: modelType === 1 ? 0 : Number(gpuModelState.gpuUsage),
        gpu_model: gpuModelState.gpuModel,
        docker_image_id: dockerState.value.value,
        set_default: checked,
        node_name_cpu,
        node_name_gpu,
      };
      method = 'POST';
    }

    const response = await callApi({
      url,
      method,
      body,
    });

    const { message, status, error } = response;

    if (status === STATUS_SUCCESS) {
      if (type === 'CREATE_TRAINING_TOOL') {
        // toast.success(t('toolsCreate.message'));
        callback();
        return null;
      }
      // toast.success(message);
      callback();
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error('Fail');
    }
  };

  /**
   * 옵션, 선택된 데이터 설정
   * @param {object} optionData 옵션데이터
   * @param {object} selectedData 선택된 데이터
   */
  const setInitialState = (optionData, selectedData) => {
    setSliderData(optionData?.resource_info);

    if (type === 'EDIT_TRAINING_TOOL') {
      // 도커이미지 선택 넣기
      const { node_name_detail, gpu_model, gpu_count } =
        selectedData?.resource_info;

      setPrevSliderData(node_name_detail);
      setGpuCount(gpu_count);

      setGpuModels(gpu_model ? gpu_model : {});
      let dockerImageOptions = optionData?.docker_info?.docker_image_list;
      dockerImageOptions = dockerImageOptions.map(({ id, name }) => {
        return { label: name, value: id };
      });
      const dockerImageInfo = selectedData?.docker_image_info;
      const dockerValue = {
        label: dockerImageInfo.name,
        value: dockerImageInfo.id,
      };
      setDockerState({ value: dockerValue, options: dockerImageOptions });

      // GPU 설정 넣기
      const resourceInfo = optionData?.resource_info;
      const { gpu_count: gpuCount, gpu_model: gpuModel } =
        selectedData?.resource_info;

      setGpuModelState({
        resourceInfo,
        gpuCount,
        gpuModel,
      });

      // 빌트인 모델 정보 넣기
      const builtInModelInfo = optionData?.built_in_model_info;

      if (builtInModelInfo) {
        const {
          enable_to_train_with_cpu: enableCpu,
          enable_to_train_with_gpu: enableGpu,
        } = builtInModelInfo;
        setGpuModelState({
          resourceInfo,
          gpuCount,
          gpuModel,
          enableCpu,
          enableGpu,
        });
      }

      // 포트 입력 넣기
      const portForwardingInfo = selectedData?.port_info?.port_forwarding_info; //ok
      setPortForwardingState(portForwardingInfo);
    } else if (type === 'CREATE_TRAINING_TOOL') {
      // 도커이미지 선택 넣기
      let dockerImageOptions = optionData?.docker_info?.docker_image_list;
      dockerImageOptions = dockerImageOptions.map(({ id, name }) => {
        return { label: name, value: id };
      });
      const dockerImageInfo = {
        name: selectedData?.image_name,
        id: selectedData?.image_id,
      };
      const dockerValue = {
        label: dockerImageInfo.name,
        value: dockerImageInfo.id,
      };
      setDockerState({ value: dockerValue, options: dockerImageOptions });

      // GPU 설정 넣기
      const resourceInfo = optionData?.resource_info;
      const { gpu_count: gpuCount } = selectedData;
      setGpuModelState({ resourceInfo, gpuCount });
    }
  };

  // Checkbox 핸들러
  const checkOptionHandler = () => {
    setCheckOption(!checkOption);
  };

  const getVisibleOptions = async () => {
    let url = '';
    if (type === 'CREATE_TRAINING_TOOL') {
      url = `trainings/tool-type-info?training_tool_type=${toolType}`;
    } else {
      url = `trainings/tool-info?training_tool_id=${toolId}`;
    }

    const response = await callApi({
      url,
      method: 'get',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const {
        docker_image_info: dockerImg,
        port_info: portInfo,
        resource_info: resourceInfo,
      } = result;

      setVisualStatus({ dockerImg, portInfo, resourceInfo });
      if (type === 'EDIT_TRAINING_TOOL') {
        return result;
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    // 학습 도구 옵션 조회
    const getOptions = async () => {
      const response = await callApi({
        url: `options/trainings/tool?training_id=${trainingId}`,
        method: 'get',
      });

      const { result, status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        return result;
      } else if (status === STATUS_FAIL) {
        errorToastMessage(error, message);
      } else {
        toast.error('Fail');
      }
    };

    // 선택 조회
    const getSelectedData = async () => {
      let url = `trainings/${trainingId}`;
      let method = 'GET';

      const response = await callApi({
        url,
        method,
      });

      const { status, result, message, error } = response;

      if (status === STATUS_SUCCESS) {
        return result;
      } else {
        errorToastMessage(error, message);
      }
    };

    async function getData() {
      const optionData = await getOptions();

      if (type === 'CREATE_TRAINING_TOOL') {
        setTitle(t('createTrainingTool.title.label'));
        await getVisibleOptions();
        const getData = await getSelectedData();
        setInitialState(optionData, getData);
      } else {
        setTitle(t('editTrainingTool.title.label'));
        const editData = await getVisibleOptions();
        setInitialState(optionData, editData);
      }
    }
    getData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <TrainingToolModalContent
      title={title}
      onSubmit={onSubmit}
      isValidate={isValidate && sliderIsValidate}
      type={type}
      modalData={modalData}
      dockerState={dockerState}
      dockerHandler={dockerHandler}
      gpuSettingBoxRender={gpuSettingBoxRender}
      portForwardingInputRender={portForwardingInputRender}
      checkOption={checkOption}
      checkOptionHandler={checkOptionHandler}
      visualStatus={visualStatus}
    />
  );
}
export default TrainingToolModal;
