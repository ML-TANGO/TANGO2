import { useState, useEffect } from 'react';

// Custom Hooks
import useIpAddressInput from './hooks/useIpAddressInput';
import useServerResourceSettingInput from './hooks/useServerResourceSettingInput';

// Components
import NodeFormModalContent from '@src/components/modalContents/NodeFormModalContent';
import { toast } from '@src/components/Toast';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

/**
 * 노드 생성, 수정 모달 컴포넌트
 * 모달의 상태 관리 및 이벤트 정의
 * src/containers/ModalContainer/ModalContainer.jsx에서 사용
 * @param {{
 *  type: 'ADD_NODE' | 'EDIT_NODE',
 *  data: {
 *    cancel: {
 *      func: () = {},
 *      text: string
 *    },
 *    submit: {
 *      func: () => {},
 *      text: string,
 *    },
 *    nodeId: number,
 *  }
 * }} props 첫 번째 인자로 모달 타입을 받으며 타입에 따라 생성, 수정 또는 CPU or GPU 또는 Storage에 따라 작동 및 제공 UI가 다름
 * 사용 법은 /src/containers/ModalContainer/ModalContainer.jsx에서 확인
 *
 */
function NodeFormModal({ type, data: modalData }) {
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [modalType, setModalType] = useState(null);
  const [addNodeMinNum, setAddNodeMinNum] = useState(0);
  const [cpuServerInitialValue, setCpuServerInitialValue] = useState({
    cores: 0,
    ram: 0,
  });

  // Custom Hooks
  // IP 주소 입력 폼 커스텀 훅
  const [ipAddressState, setIpInputState, renderIpAddressInputForm] =
    useIpAddressInput(type);

  const { serverInfo } = ipAddressState;

  // 서버 리소스 설정 입력 폼 커스텀 훅
  const [
    serverModeState,
    setServerResourceInputState,
    renderServerModeInput,
    renderServerSettingInput,
    cpuServerSliderGage,
  ] = useServerResourceSettingInput(
    serverInfo && serverInfo.maxCpuResource,
    serverInfo && serverInfo.numGpuResource,
    serverInfo && serverInfo.maxRamResource,
    deviceInfo && deviceInfo,
    cpuServerInitialValue && cpuServerInitialValue,
    modalType && modalType,
    addNodeMinNum && addNodeMinNum,
  );

  // 모든 인풋 유효성 검증 여부 (true 일 경우 저장 버튼 활성화)
  const isValidate = ipAddressState.isValid && serverModeState.isValid;

  // 노드 생성 api 호출
  const onSubmit = async (callback) => {
    const { ipAddress } = ipAddressState;
    const { ethernetOptions } = serverInfo;
    const {
      selectedMode,
      gpuModeCpuRsc,
      cpuModeCpuRsc,
      gpuModeRam,
      cpuModeRam,
      selectedRscOverdistributingGPUServer,
      temporarySizeLimit,
    } = serverModeState;

    const isCpuServer =
      selectedMode.filter(({ value }) => value === 'cpu').length > 0 ? 1 : 0;
    const isGpuServer =
      selectedMode.filter(({ value }) => value === 'gpu').length > 0 ? 1 : 0;

    const coresItem = cpuServerSliderGage?.filter(
      (el) => el?.label === 'Cores',
    );
    const ramItem = cpuServerSliderGage?.filter((el) => el?.label === 'RAM');

    const cpuCoresPercent =
      coresItem[0]?.percent > 500 ? 500 : coresItem[0]?.percent;
    const ramPercent = ramItem[0]?.percent > 500 ? 500 : ramItem[0]?.percent;

    const cpuCoresLockPerPod = coresItem[0].percent >= 550 ? 0 : 1;

    const ramLockPerPod = ramItem[0].percent >= 550 ? 0 : 1;

    const cpuCoresLockPerGpu =
      selectedRscOverdistributingGPUServer.filter(
        ({ value }) => value === 'cpu',
      ).length > 0
        ? 1
        : 0;
    const ramLockPerGpu =
      selectedRscOverdistributingGPUServer.filter(
        ({ value }) => value === 'ram',
      ).length > 0
        ? 1
        : 0;

    let body = {
      ip: ipAddress,
    };

    // GPU/CPU Node
    body = {
      ...body,
      interfaces: ethernetOptions
        .map(({ value }) => value)
        .filter((val) => val !== null),
      is_cpu_server: isCpuServer,
      is_gpu_server: isGpuServer,
      cpu_cores_limit_per_pod: Number(cpuModeCpuRsc),
      cpu_cores_limit_per_gpu: Number(gpuModeCpuRsc),
      ram_limit_per_pod: Number(cpuModeRam),
      ram_limit_per_gpu: Number(gpuModeRam),
      ephemeral_storage_limit: Number(temporarySizeLimit),
      cpu_cores_lock_per_pod: cpuCoresLockPerPod,
      cpu_cores_lock_percent_per_pod: cpuCoresPercent,
      cpu_cores_lock_per_gpu: cpuCoresLockPerGpu,
      ram_lock_per_pod: ramLockPerPod,
      ram_lock_percent_per_pod: ramPercent,
      ram_lock_per_gpu: ramLockPerGpu,
    };

    let method;
    if (type.indexOf('ADD') !== -1) {
      method = 'POST';
    } else if (type.indexOf('EDIT') !== -1) {
      method = 'PUT';
      body.id = modalData.nodeId;
    }

    const url = 'nodes';
    const response = await callApi({ url, method, body });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      if (type.indexOf('ADD') !== -1) {
        defaultSuccessToastMessage('create');
      } else {
        defaultSuccessToastMessage('update');
      }
      callback();
      return true;
    } else {
      errorToastMessage(error, message);
      return false;
    }
  };
  // LifeCycle
  useEffect(() => {
    if (type.indexOf('EDIT') !== -1) {
      setModalType('EDIT');
      // 노드 정보 조회
      const getNodeInfo = async () => {
        const response = await callApi({
          url: `nodes/${modalData.nodeId}`,
          method: 'get',
        });
        const { result, status, message, error } = response;
        if (status === STATUS_SUCCESS) {
          const {
            ram_lock_percent_per_pod: initialRAMPercent,
            cpu_cores_lock_percent_per_pod: initialCoresPercent,
          } = result;
          setIpInputState(result);
          setServerResourceInputState(result);
          setCpuServerInitialValue({
            cores: initialCoresPercent,
            ram: initialRAMPercent,
          });
          setDeviceInfo(result?.device_info);
        } else if (status === STATUS_FAIL) {
          errorToastMessage(error, message);
        } else {
          toast.error('Fail');
        }
      };
      getNodeInfo();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (type.indexOf('ADD') !== -1 && serverInfo) {
      setModalType('ADD');
      const { maxRamResource, maxCpuResource } = serverInfo;
      setAddNodeMinNum({
        cores: maxCpuResource,
        ram: maxRamResource,
      });
    }
  }, [serverInfo, type]);

  return (
    <NodeFormModalContent
      modalData={modalData}
      type={type}
      renderIpAddressInputForm={renderIpAddressInputForm}
      renderServerModeInput={renderServerModeInput}
      renderServerSettingInput={renderServerSettingInput}
      loading={ipAddressState.loading}
      isGetServerInfo={ipAddressState.serverInfo !== undefined}
      isValidate={isValidate}
      onSubmit={onSubmit}
    />
  );
}

export default NodeFormModal;
