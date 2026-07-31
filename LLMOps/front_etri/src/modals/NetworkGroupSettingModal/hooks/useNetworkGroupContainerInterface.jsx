import { useState, useMemo } from 'react';

// Utils
import { errorToastMessage } from '@src/utils';

// Components
import NetworkGroupContainerInterfaceForm from '@src/components/modalContents/NetworkGroupSettingModalContent/NetworkGroupContainerInterfaceForm';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const useNetworkGroupContainerInterface = () => {
  const [containerInterfaceList, setContainerInterfaceList] = useState([]);
  const [nameError, setNameError] = useState([]);
  const [networkGroupId, setNetworkGroupId] = useState(null);

  const setContainerInterfaceState = (state, networkGroupId) => {
    const containerInterfaces = state.network_group_container_interfaces.map(
      ({
        id,
        port_index: portIndex,
        interface: interfaceName,
        node_interface_list: nodeInterfaceList,
        is_deletable: isDeletable,
      }) => {
        return {
          id,
          portIndex,
          interfaceName,
          nodeInterfaceList,
          isDeletable,
          isEdit: false,
        };
      },
    );
    const missMatchList = state.miss_match_port_index_list.map(
      ({ port_index: portIndex, node_interface_list: nodeInterfaceList }) => {
        return {
          id: -1,
          portIndex,
          interfaceName: '',
          nodeInterfaceList,
          isDeletable: nodeInterfaceList.length === 0,
          isEdit: true,
        };
      },
    );
    setContainerInterfaceList([...containerInterfaces, ...missMatchList]);
    const length = containerInterfaces.length + missMatchList.length;
    setNameError(Array.from({ length }, () => ''));
    setNetworkGroupId(networkGroupId);
  };

  /**
   * 새로운 인터페이스 입력 폼 생성
   */
  const onCreate = () => {
    let newContainerInterfaceList = containerInterfaceList
      ? [...containerInterfaceList]
      : [];

    // portIndex 오름차순으로 정렬 후 빠진 숫자 찾기
    const temp = [...newContainerInterfaceList].sort(
      (a, b) => a.portIndex - b.portIndex,
    );
    let newPortIndex = temp.length + 1;
    for (let i = 0; i < temp.length; i++) {
      if (temp[i].portIndex !== i + 1) {
        newPortIndex = i + 1;
        break;
      }
    }
    newContainerInterfaceList.push({
      id: -1,
      portIndex: newPortIndex,
      interfaceName: '',
      nodeInterfaceList: null,
      isDeletable: true,
      isEdit: true,
    });
    setContainerInterfaceList(newContainerInterfaceList);
    setNameError([...nameError, '']);
  };

  /**
   * 컨테이너 인터페이스 이름 중복 체크
   */
  const checkNameDuplicated = async (idx, currentName, prevName) => {
    const newNameError = nameError ? [...nameError] : [];
    const response = await callApi({
      url: `networks/network-container-interface-duplicate?interface=${currentName}&network_group_id=${networkGroupId}`,
      method: 'GET',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (!result) {
        newNameError[idx] = 'other';
        setNameError(newNameError);
      } else {
        // 내부 중복 검사
        newNameError[idx] = '';
        for (let i = 0; i < containerInterfaceList.length; i++) {
          if (i !== idx) {
            if (containerInterfaceList[i].interfaceName === currentName) {
              newNameError[i] = 'inner';
              newNameError[idx] = 'inner';
            }
          }
        }
        // 기존에 중복된 이름 있었으면 수정된 이름 반영하여 에러 삭제
        let duplicateCount = 0;
        let duplicateIdx = -1;
        for (let i = 0; i < containerInterfaceList.length; i++) {
          if (containerInterfaceList[i].interfaceName === prevName) {
            duplicateCount++;
            duplicateIdx = i;
          }
        }
        if (duplicateCount === 1) {
          if (newNameError[duplicateIdx] !== 'other') {
            newNameError[duplicateIdx] = '';
          }
        }
        setNameError(newNameError);
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 컨테이너 인터페이스 이름 변경
   * @param {number} idx
   * @param {string} interfaceName
   */
  const onEdit = (idx, interfaceName) => {
    let prevName = containerInterfaceList[idx].interfaceName;
    let newContainerInterfaceList = [...containerInterfaceList];
    const list = newContainerInterfaceList[idx];
    list.interfaceName = interfaceName;
    list.isEdit = false;
    setContainerInterfaceList(newContainerInterfaceList);

    // 이름 중복검사
    checkNameDuplicated(idx, interfaceName, prevName);
  };

  /**
   * 컨테이너 인터페이스 이름 변경 모드로 전환
   * @param {number} idx
   */
  const onEditMode = (idx) => {
    let newContainerInterfaceList = [...containerInterfaceList];
    const list = newContainerInterfaceList[idx];
    list.isEdit = true;
    setContainerInterfaceList(newContainerInterfaceList);
  };

  /**
   * 컨테이너 인터페이스 현황에서 아이템 삭제
   * @param {number} idx 목록 인덱스 값
   */
  const onDelete = (idx) => {
    const deleteName = containerInterfaceList[idx].interfaceName;
    let newContainerInterfaceList = [...containerInterfaceList];
    newContainerInterfaceList.splice(idx, 1);
    setContainerInterfaceList(newContainerInterfaceList);
    const newNameError = [...nameError];
    newNameError.splice(idx, 1);
    /**
     * 같은 이름 찾아서 내부에서 중복된 이름이 한개면 에러 삭제
     * 여러개거나 외부 중복이면 그대로 놔둠
     */
    let duplicateCount = 0;
    let duplicateIdx = -1;
    for (let i = 0; i < newContainerInterfaceList.length; i++) {
      if (newContainerInterfaceList[i].interfaceName === deleteName) {
        duplicateCount++;
        duplicateIdx = i;
      }
    }
    if (duplicateCount === 1) {
      if (newNameError[duplicateIdx] !== 'other') {
        newNameError[duplicateIdx] = '';
      }
    }

    setNameError(newNameError);
  };

  const renderContainerInterfaceForm = () => {
    return (
      <NetworkGroupContainerInterfaceForm
        containerInterfaceList={containerInterfaceList}
        onCreate={onCreate}
        onEdit={onEdit}
        onDelete={onDelete}
        onEditMode={onEditMode}
        nameError={nameError}
      />
    );
  };

  const result = useMemo(
    () => ({
      isValid: nameError.filter((v) => v !== '').length === 0,
      containerInterfaceList,
    }),
    [nameError, containerInterfaceList],
  );

  return [result, setContainerInterfaceState, renderContainerInterfaceForm];
};

export default useNetworkGroupContainerInterface;
