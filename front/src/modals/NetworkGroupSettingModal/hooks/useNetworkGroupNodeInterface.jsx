import { useState, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Utils
import { errorToastMessage } from '@src/utils';

// Components
import NetworkGroupNodeInterfaceForm from '@src/components/modalContents/NetworkGroupSettingModalContent/NetworkGroupNodeInterfaceForm';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const useNetworkGroupNodeInterface = () => {
  const { t } = useTranslation();
  const [selectedNode, setSelectedNode] = useState({});
  const [nodeList, setNodeList] = useState([]);
  const [interfaceList, setInterfaceList] = useState([]);
  const [nodeInterfaceList, setNodeInterfaceList] = useState([]);
  const [networkGroupId, setNetworkGroupId] = useState(null);
  const [loading, setLoading] = useState(false);

  const setNodeInterfaceState = (state, networkGroupId) => {
    setNodeList(state.node_list);
    const nodeInterfaces = state.node_interfaces.map(
      ({
        id,
        node_id: nodeId,
        node_name: nodeName,
        interface: interfaceName,
        port_index: portIndex,
      }) => {
        return { id, nodeId, nodeName, interfaceName, portIndex };
      },
    );
    setNodeInterfaceList(nodeInterfaces);
    setNetworkGroupId(networkGroupId);
  };

  /**
   * 노드 목록에서 선택시 인터페이스 목록 불러오기
   * @param {number} id 노드 아이디
   * @param {string} name 노드 이름
   */
  const getInterfaces = async (id, name) => {
    setLoading(true);
    setSelectedNode({ id, name });
    const response = await callApi({
      url: `networks/node-interfaces?node_id=${id}&network_group_id=${networkGroupId}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result) {
        setInterfaceList(result);
      }
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  /**
   * 노드 인터페이스 추가 (현황 목록으로 이동)
   * @param {string} interfaceName 인터페이스 이름
   */
  const onAdd = (interfaceName) => {
    const newNodeInterfaceList = nodeInterfaceList
      ? [...nodeInterfaceList]
      : [];
    // 중복 체크
    const duplicated = newNodeInterfaceList.filter(
      ({ nodeName, interfaceName: selectedInterface }) =>
        nodeName === selectedNode.name && interfaceName === selectedInterface,
    ).length;
    if (duplicated > 0) {
      toast.error(t('network.nodeInterface.duplicate.message'));
      return false;
    }
    // portIndex 계산
    const count = newNodeInterfaceList.filter(
      ({ nodeName }) => nodeName === selectedNode.name,
    ).length;
    newNodeInterfaceList.push({
      id: -1, // 추가된거 구분용
      nodeId: selectedNode.id,
      nodeName: selectedNode.name,
      interfaceName,
      portIndex: count + 1,
    });
    setNodeInterfaceList(newNodeInterfaceList);
  };

  /**
   * 노드 인터페이스 현황에서 아이템 삭제
   * @param {number} idx 노드-인터페이스 목록 인덱스 값
   * @param {number} nodeId 삭제한 아이템의 노드 아이디
   */
  const onDelete = (idx, nodeId) => {
    let newNodeInterfaceList = [...nodeInterfaceList];
    newNodeInterfaceList.splice(idx, 1);
    for (let i = idx; i < newNodeInterfaceList.length; i++) {
      if (newNodeInterfaceList[i].nodeId === nodeId) {
        newNodeInterfaceList[i].portIndex--;
      }
    }
    setNodeInterfaceList(newNodeInterfaceList);
  };

  const renderNodeInterfaceForm = () => {
    return (
      <NetworkGroupNodeInterfaceForm
        selectedNodeName={selectedNode.name}
        nodeList={nodeList}
        interfaceList={interfaceList}
        nodeInterfaceList={nodeInterfaceList}
        getInterfaces={getInterfaces}
        onAdd={onAdd}
        onDelete={onDelete}
        loading={loading}
      />
    );
  };

  const result = useMemo(
    () => ({
      isValid: true,
      nodeInterfaceList,
    }),
    [nodeInterfaceList],
  );

  return [result, setNodeInterfaceState, renderNodeInterfaceForm];
};

export default useNetworkGroupNodeInterface;
