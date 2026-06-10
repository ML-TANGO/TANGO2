import { useState, useEffect } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useNetworkGroupBasicInfo from './hooks/useNetworkGroupBasicInfo';
import useNetworkGroupNodeInterface from './hooks/useNetworkGroupNodeInterface';
import useNetworkGroupContainerInterface from './hooks/useNetworkGroupContainerInterface';
import useNetworkGroupIpRange from './hooks/useNetworkGroupIpRange';

// Components
import NetworkGroupSettingModalContent from '@src/components/modalContents/NetworkGroupSettingModalContent/NetworkGroupSettingModalContent';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

/**
 * 네트워크 설정 모달
 * @param {{
 *  type: 'CREATE_NETWORK_GROUP' | 'NETWORK_GROUP_SETTING',
 *  data: {
 *    cancel: {
 *      text: string
 *    },
 *    submit: {
 *      func: () => {},
 *      text: string,
 *    },
 *    data: row,
 *  }
 * }} props
 * @returns
 */
function NetworkGroupSettingModal({ type, data: modalData }) {
  const { t } = useTranslation();
  // 설정 모달일 때 탭 옵션
  const targetOptions = [
    { label: t('network.tab.groupInfo.label'), value: 'basic' },
    { label: t('network.tab.nodeInterface.label'), value: 'node' },
    { label: t('network.tab.containerInterface.label'), value: 'container' },
    { label: t('network.tab.ipRange.label'), value: 'ip' },
  ];
  const [target, setTarget] = useState(targetOptions[0]);
  const [networkGroupId, setNetworkGroupId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [basicInfo, setBasicInfo, renderBasicInfoForm] =
    useNetworkGroupBasicInfo(type);
  const [nodeInterface, setNodeInterface, renderNodeInterfaceForm] =
    useNetworkGroupNodeInterface();
  const [
    containerInterface,
    setContainerInterface,
    renderContainerInterfaceForm,
  ] = useNetworkGroupContainerInterface();
  const [ipRange, setIpRange, renderIpRangeForm] = useNetworkGroupIpRange();

  /**
   * 버튼 활성화 여부 체크
   * @returns boolean
   */
  const isValidate = () => {
    if (type === 'CREATE_NETWORK_GROUP') {
      return basicInfo.isValid;
    } else {
      // 수정 모달 탭별 확인
      if (target.value === 'basic') {
        return basicInfo.isValid;
      } else if (target.value === 'node') {
        return nodeInterface.isValid;
      } else if (target.value === 'container') {
        return containerInterface.isValid;
      } else {
        return ipRange.isValid;
      }
    }
  };

  /**
   * 네트워크 그룹 데이터 가져오기
   */
  const getData = async (id) => {
    setIsLoading(true);
    const response = await callApi({
      url: `networks/network-group-modal?network_group_id=${id}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result) {
        setNodeInterface(result.network_group_node_interface, id);
        setContainerInterface(result.network_group_container_interface, id);
        setIpRange(result.ip_range, id);
      }
    } else {
      errorToastMessage(error, message);
    }
    setIsLoading(false);
  };

  /**
   * 네트워크 그룹 기본 정보 추가/수정
   * @param {Function} callback API 호출 후 실행할 콜백함수
   */
  const onBasicInfoUpdate = async (callback) => {
    const { name, category, speed, description } = basicInfo;

    let method = 'post';
    let body = {
      name,
      speed,
      description,
    };

    if (type === 'NETWORK_GROUP_SETTING') {
      body = { ...body, network_group_id: networkGroupId };
      method = 'put';
    } else {
      body = { ...body, category };
    }

    const response = await callApi({
      url: 'networks/network-group',
      method,
      body,
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      if (type === 'NETWORK_GROUP_SETTING') {
        defaultSuccessToastMessage('update');
      } else {
        defaultSuccessToastMessage('create');
      }
      if (callback) callback();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 네트워크 그룹 노드 인터페이스 수정
   * @param {Function} callback API 호출 후 실행할 콜백함수
   */
  const onNodeInterfaceUpdate = async (callback) => {
    const { nodeInterfaceList } = nodeInterface;

    const tempList = nodeInterfaceList.map(({ id, nodeId, interfaceName }) => {
      return { id, node_id: nodeId, interface: interfaceName };
    });

    let body = {
      network_group_id: networkGroupId,
      node_interfaces: tempList,
    };

    const response = await callApi({
      url: 'networks/network-group-node-interfaces',
      method: 'post',
      body,
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('update');
      getData(networkGroupId);
      if (callback) callback();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 네트워크 그룹 컨테이너 인터페이스 수정
   * @param {Function} callback API 호출 후 실행할 콜백함수
   */
  const onContainerInterfaceUpdate = async (callback) => {
    const { containerInterfaceList } = containerInterface;

    const tempList = containerInterfaceList.map(
      ({ id, portIndex, interfaceName, nodeInterfaceList }) => {
        return {
          id,
          network_group_id: networkGroupId,
          port_index: portIndex,
          interface: interfaceName,
          node_interface_list: nodeInterfaceList,
        };
      },
    );

    let body = {
      network_group_id: networkGroupId,
      node_interfaces: tempList,
    };

    const response = await callApi({
      url: 'networks/network-group-container-interfaces',
      method: 'post',
      body,
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('update');
      getData(networkGroupId);
      if (callback) callback();
    } else {
      errorToastMessage(error, message);
    }
  };

  const onIpRangeUpdate = async (callback) => {
    const { ip, subnetMask, ipRangeStart, ipRangeEnd } = ipRange;

    const newIp = ip.map((v) => {
      if (v) {
        return (v = Number(v));
      } else {
        return (v = 0);
      }
    });

    const body = {
      network_group_id: networkGroupId,
      ip_range: newIp.join('.'),
      subnet_mask: subnetMask.value,
      ip_range_start: ipRangeStart.join('.'),
      ip_range_end: ipRangeEnd.join('.'),
    };

    const response = await callApi({
      url: 'networks/network-group-cni',
      method: 'post',
      body,
    });
    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('update');
      getData(networkGroupId);
      if (callback) callback();
    } else {
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    if (type === 'NETWORK_GROUP_SETTING') {
      /** 기본정보 받아온거 설정 */
      const { id, name, category, speed, description } = modalData.data;
      setNetworkGroupId(id);
      setBasicInfo({ name, category, speed, description });
      getData(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <NetworkGroupSettingModalContent
      type={type}
      modalData={modalData}
      targetOptions={targetOptions}
      target={target}
      setTarget={setTarget}
      isLoading={isLoading}
      renderBasicInfoForm={renderBasicInfoForm}
      onBasicInfoUpdate={onBasicInfoUpdate}
      renderNodeInterfaceForm={renderNodeInterfaceForm}
      onNodeInterfaceUpdate={onNodeInterfaceUpdate}
      renderContainerInterfaceForm={renderContainerInterfaceForm}
      onContainerInterfaceUpdate={onContainerInterfaceUpdate}
      renderIpRangeForm={renderIpRangeForm}
      onIpRangeUpdate={onIpRangeUpdate}
      isValidate={isValidate()}
    />
  );
}

export default NetworkGroupSettingModal;
