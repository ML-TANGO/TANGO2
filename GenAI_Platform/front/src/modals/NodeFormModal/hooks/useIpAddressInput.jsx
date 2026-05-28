import { useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components
import IPAddressInputForm from '@src/components/modalContents/NodeFormModalContent/IPAddressInputForm';
import { toast } from '@src/components/Toast';

// Network
import {
  callApi,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
  STATUS_SUCCESS,
} from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

/**
 * 노드 생성, 수정 모달에서 IP 주소 입력 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'ADD_NODE' | 'EDIT_NODE'} type 노드 모달의 타입
 * @returns {[
 *  {
 *    ipAddress: string,
 *    serverInfo: {
 *      ethernetOptions: [ { label: string, value: 'string' } ],
 *      partitionOptions: [ { label: string, value: 'string' } ],
 *      maxCpuResource: number,
 *      numGpuResource: number,
 *      maxRamResource: number,
 *    } | undefined,
 *    error: string | undefined,
 *    loading: boolean,
 *    isValid: boolean,
 *  },
 *  (nodeData: {
 *    cpu_cores_limit_per_gpu: number,
 *    cpu_cores_limit_per_pod: number,
 *    device_info: {
 *      num_gpus: number,
 *      cpu: string,
 *      cpu_cores: number,
 *      ram: number,
 *    },
 *    ephemeral_storage_limit: string,
 *    ip: string,
 *    is_cpu_server: 1 | 0,
 *    is_gpu_server: 1 | 0,
 *    nerwork_interfaces: [ string, string ],
 *    no_use_server: number,
 *    ram_limit_per_gpu: number,
 *    ram_limit_per_pod: number,
 *  }) => (),
 *  () => JSX.Element,
 * ]}
 * 리턴 값(배열)의 첫번째 인덱스 값은 입력한 IP 주소 및 해당 서버 정보를 리턴한다.
 * 두번째 인덱스 값은 IP 주소를 입력하고 해당 서버 정보를 가져오기 위한 컴포넌트를 화면에 렌더링하는 함수이다.
 *
 * @component
 * @example
 *
 * const [
 *  ipAddressState, // IP Address 관련 컴포넌트 상태 및 서버 정보 요청 결과 값
 *  setIpInputState, // 노드 수정 모달에서 해당 노드의 정보를 미리 설정하기 위한 함수
 *  renderIpAddressInputForm, // IP Address 인풋 및 불러오기 버튼 렌더링 함수
 * ] = useIpAddressInput();
 *
 * return (
 *  <>
 *    {renderIpAddressInputForm()}
 *  </>
 * );
 *
 */
const useIpAddressInput = (type) => {
  const { t } = useTranslation();

  // Component State
  const [ipAddress, setIpAddress] = useState('');
  const [ipAddressError, setIpAddressError] = useState();
  const [serverInfo, setServerInfo] = useState();
  const [loading, setLoading] = useState(false);

  // Events
  const inputHandler = (e) => {
    const { value } = e.target;

    // ip 값 변경
    setIpAddress(value);

    if (serverInfo) {
      setServerInfo(undefined);
    }

    // 유효성 검증
    let error = '';
    const regType1 = /^[0-9\\.]*$/;
    const regType2 =
      /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    if (value === '') {
      error = 'ip.empty.message';
    }
    if (!regType1.test(value)) {
      error = 'ipRule.message';
    }
    if (!regType2.test(value)) {
      error = 'ip.error.message';
    }
    setIpAddressError(error);
  };

  // Parse
  const parseServerInfoData = (serverInfoData) => {
    const {
      network_interfaces: networkInterfaces,
      device_info: deviceInfo,
      partitions,
    } = serverInfoData;

    const parseData = {};

    if (networkInterfaces) {
      const ethernetOptions = networkInterfaces.map((val) => ({
        label: val,
        value: val,
      }));
      ethernetOptions.unshift({ label: 'None', value: null });
      parseData.ethernetOptions = ethernetOptions;
    }

    if (deviceInfo) {
      const {
        cpu_cores: cpuCores,
        num_gpus: numGPUs,
        ram: maxRamResource,
      } = deviceInfo;

      parseData.maxCpuResource = Number(cpuCores);
      parseData.numGpuResource = Number(numGPUs);
      parseData.maxRamResource = maxRamResource;
    }

    if (partitions) {
      const partitionOptions =
        partitions &&
        partitions.map((p) => {
          return {
            ...p,
            label: `${p.name} - ( ${p.used}GB / ${p.total}GB, ${p.fstype} )`,
            value: p.name,
          };
        });

      parseData.partitionOptions = partitionOptions;
    }

    return parseData;
  };

  // API request
  /**
   * 네트워크 정보 조회 api
   */
  const getNetworkInfo = async () => {
    // 로딩 컴포넌트 활성화
    setLoading(true);

    // 서버 정보 API 호출
    const response = await callApi({
      url: `nodes/node_info?ip=${ipAddress}`,
      method: 'get',
    });

    const { result, status, message, error } = response;
    // 로딩 컴포넌트 비활성화
    setLoading(false);

    if (status === STATUS_SUCCESS) {
      // API 성공
      const { network_interfaces: networkInterfaces, device_info: deviceInfo } =
        result;
      if (networkInterfaces && deviceInfo) {
        // 서버 정보 가져오기 성공
        setServerInfo(parseServerInfoData(result));
        // toast.success(t('node.getServerInfo.success.message'));
      } else {
        // 입력한 IP에 대한 서버 정보가 없는 경우
        setServerInfo(undefined);
        toast.error(t('node.getServerInfo.fail.message'));
      }
    } else if (status === STATUS_FAIL) {
      // 서버 정보 가져오기 실패
      errorToastMessage(error, message);
      setServerInfo(undefined);
    } else if (status === STATUS_INTERNAL_SERVER_ERROR) {
      // 서버 정보 가져오기 실패 (서버 에러)
      toast.error(message);
      setServerInfo(undefined);
    } else {
      // 서버 정보 가져오기 실패 (알 수 없음)
      toast.error(message);
      setServerInfo(undefined);
    }
  };

  /**
   * 노드 수정 모달에서 노드 생성 시 입력한 값을 컴포넌트 State에 셋팅하는 함수
   *
   * @param {{
   *  cpu_cores_limit_per_gpu: number,
   *  cpu_cores_limit_per_pod: number,
   *  device_info: {
   *    num_gpus: number,
   *    cpu: string,
   *    cpu_cores: number,
   *    ram: number,
   *  },
   *  ephemeral_storage_limit: string,
   *  ip: string,
   *  is_cpu_server: 1 | 0,
   *  is_gpu_server: 1 | 0,
   *  nerwork_interfaces: [ string, string ],
   *  no_use_server: number,
   *  ram_limit_per_gpu: number,
   *  ram_limit_per_pod: number,
   * }} nodeData /node/${nodeId} api(노드 상세 조회)의 조회 결과
   */
  const setIpInputState = (nodeData) => {
    const { ip } = nodeData;

    setIpAddress(ip);
    setIpAddressError('');
    setServerInfo(parseServerInfoData(nodeData));
  };

  // IP Address 컴포넌트 렌더링 함수
  const renderIpAddressInput = () => {
    return (
      <IPAddressInputForm
        ipAddress={ipAddress}
        inputHandler={inputHandler}
        ipAddressError={ipAddressError}
        getNetworkInfo={getNetworkInfo}
        type={type}
      />
    );
  };

  const result = useMemo(
    () => ({
      ipAddress,
      serverInfo,
      loading,
      isValid: serverInfo !== undefined && ipAddressError === '',
    }),
    [loading, serverInfo, ipAddress, ipAddressError],
  );

  return [result, setIpInputState, renderIpAddressInput];
};

export default useIpAddressInput;
