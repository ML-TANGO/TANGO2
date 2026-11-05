import { useState, useEffect, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import PortForwardingInputBox from './PortForwardingInputBox';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

function usePortForwardingInputBox({ toolType, toolId, visualStatus, type }) {
  const { t } = useTranslation();
  const [portForwardingList, setPortForwardingList] = useState([]);
  const [portForwardingWarning, setPortForwardingWarning] = useState('');
  const [portForwardingError, setPortForwardingError] = useState('');
  const [defaultPortForwardingList, setDefaultPortForwardingList] =
    useState(null); // 추가할 리스트 기본 포맷
  const [targetPortRange, setTargetPortRange] = useState([0, 65535]);
  const [nodePortRange, setNodePortRange] = useState([30000, 32767]);
  const [protocolList, setProtocolList] = useState([]);
  const [systemDefaultPortObj, setSystemDefaultPortObj] = useState({}); // 시스템 기본 포트 리스트
  const [nodePortUseList, setNodePortUseList] = useState([]);
  const [isToolRunning, setIsToolRunning] = useState(false);

  useEffect(() => {
    getPortForwardingInfo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * 포트포워딩 리스트 입력 포맷에 맞춰 가공
   *
   * @param {object} portForwardingInfo
   */
  const setPortForwardingState = (portForwardingInfo) => {
    const portForwardingList = portForwardingInfo?.map(
      ({
        id,
        name,
        protocol: p,
        target_port: targetPort,
        node_port: nodePort,
        description,
        system_definition: systemDefinition,
        service_type: serviceType,
        training_tool_id: trainingToolId,
        status,
      }) => {
        return {
          id,
          name,
          protocol: { label: p, value: p },
          targetPort: String(targetPort),
          nodePort: nodePort ? String(nodePort) : '',
          description,
          systemDefinition,
          serviceType,
          trainingToolId,
          status,
        };
      },
    );
    setPortForwardingList(portForwardingList);
  };

  /**
   * 포트포워딩 리스트 API 전송 포맷으로 변경
   *
   * @param {object} portForwardingList
   * @returns portList
   */
  const makeResultJson = (portForwardingList) => {
    const portList = portForwardingList?.map(
      ({
        id,
        name,
        protocol,
        targetPort,
        nodePort,
        description,
        systemDefinition,
        serviceType,
        status,
      }) => {
        return {
          id,
          name,
          protocol: protocol.value,
          target_port: Number(targetPort),
          node_port: nodePort !== '' ? Number(nodePort) : null,
          description,
          system_definition: systemDefinition,
          service_type: serviceType || 'NodePort',
          status,
        };
      },
    );
    return portList;
  };

  // 포트포워딩 설정 옵션 가져오기
  const getPortForwardingInfo = async () => {
    let url = 'options/port-forwarding?';

    if (type === 'EDIT_TRAINING_TOOL') {
      url += `training_tool_id=${toolId}`;
    } else if (type === 'CREATE_TRAINING_TOOL') {
      url += `training_tool_type=${toolType}`;
    }
    const response = await callApi({
      url,
      method: 'get',
    });

    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      const {
        target_port_range: targetPortRange,
        node_port_range: nodePortRange,
        port_protocol_list: protocolListInfo,
        default_port_list: defaultPortList,
        node_ports_in_use_list: nodePortUseList,
        training_tool_running: isToolRunning,
      } = result;

      const newPortData = result.default_port_list;
      const newForwardingInfo = [];

      newPortData?.forEach((infoList) => {
        newForwardingInfo.push({
          name: infoList.name,
          target_port: infoList.port,
          status: newPortData.length > 0 ? 1 : 0,
          system_definition: 1,
          service_type: infoList.type,
          protocol: infoList.protocol,
          description: infoList?.description
            ? infoList?.description
            : 'Default',
        });
      });
      setPortForwardingState(newForwardingInfo);
      // protocolListInfo select 컴포넌트에 맞게 가공
      const protocolOptions = protocolListInfo.map((v) => {
        return { label: v, value: v };
      });

      // default Port list에서 name을 key값으로 가지는 object로 가공
      const defaultPortInfo = {};
      defaultPortList.map(({ name, port, protocol }) => {
        return (defaultPortInfo[name] = { port, protocol });
      });

      setTargetPortRange(targetPortRange);
      setNodePortRange(nodePortRange);
      setProtocolList(protocolOptions);
      setSystemDefaultPortObj(defaultPortInfo);
      setNodePortUseList(nodePortUseList);
      setIsToolRunning(isToolRunning);

      // 포트포워딩 리스트 디폴트 값 설정
      setDefaultPortForwardingList({
        name: '',
        protocol: protocolOptions[0],
        targetPort: '',
        nodePort: '',
        description: '',
        systemDefinition: 0,
        serviceType: '',
        status: 1,
      });
    } else {
      toast.error(message);
      return {};
    }
  };

  /**
   * 포트포워딩 입력 폼 추가
   */
  const addPortForwardingList = () => {
    const newPortForwardingList = [...portForwardingList];
    newPortForwardingList.push({ ...defaultPortForwardingList });
    setPortForwardingList(newPortForwardingList);
    setPortForwardingError(portForwardingError || null);
  };

  /**
   * 포트포워딩 입력 폼 삭제
   *
   * @param {number} idx
   */
  const removePortForwardingList = (idx) => {
    let newPortForwardingList = [...portForwardingList];
    newPortForwardingList = [
      ...newPortForwardingList.slice(0, idx),
      ...newPortForwardingList.slice(idx + 1, newPortForwardingList.length),
    ];
    setPortForwardingList(newPortForwardingList);

    if (newPortForwardingList.length === 0) {
      setPortForwardingError('');
    } else {
      setPortForwardingError(
        portForwardingListValidate(newPortForwardingList)[0],
      );
    }
  };

  /**
   * 포트포워딩 입력 이벤트 핸들러
   *
   * @param {object} e
   * @param {number} idx
   * @param {string} inputName
   */
  const portForwardingInputHandler = (e, idx, inputName) => {
    const newPortForwardingList = [...portForwardingList];
    const targetList = newPortForwardingList[idx];

    if (inputName === 'protocol') {
      targetList.protocol = e;
    } else if (inputName === 'status') {
      targetList.status = Number(!targetList.status);
    } else {
      const { name, value } = e.target;
      targetList[name] = value;
    }
    // 유효성 체크 (에러, 경고)
    const messageArray = portForwardingListValidate(newPortForwardingList);
    const errorMessage = messageArray[0];
    const warningMessage = messageArray[1];

    setPortForwardingList(newPortForwardingList);
    setPortForwardingWarning(warningMessage);
    setPortForwardingError(errorMessage);
  };

  /**
   * 포트포워딩 폼 유효성 체크
   *
   * @returns [errorMessage, warningMessage]
   */
  const portForwardingListValidate = (portForwardingList) => {
    // 포트포워딩 리스트 내 같은 key에 대한 value 중복체크
    const uniqueCheck = (key, value, type) => {
      let isUnique = false;
      const checkList = portForwardingList.filter(
        (list) =>
          (type === 'string' && list[key] !== '' && list[key] === value) ||
          (type === 'number' &&
            list[key] !== '' &&
            Number(list[key]) === Number(value)),
      );
      if (checkList.length === 1) {
        isUnique = true;
      }
      return isUnique;
    };

    const regExpName = /^[a-z0-9]+(-[a-z0-9]+)*$/;
    const regExpNum = /^[0-9]+$/;
    const errorMessageList = [];
    const warningMessageList = [];
    portForwardingList.forEach(
      ({ name, protocol, targetPort, nodePort, systemDefinition }) => {
        let error = '';
        let warning = '';

        // 시스템 정의 포트
        if (systemDefinition) {
          if (systemDefaultPortObj[name].protocol !== protocol.value) {
            warning = `${warning} ${t('protocol.warning.message')}`;
          }
          if (systemDefaultPortObj[name].port !== Number(targetPort)) {
            warning = `${warning} ${t('targetPort.warning.message')}`;
          }
        } else {
          // name (시스템 정의 포트시 이름은 변경할 수 없기 때문에 검사할 필요 없음)
          if (name === '') {
            error = `${error} ${t('portName.empty.message')}`;
          } else if (
            !name.match(regExpName) ||
            name.match(regExpName)[0] !== name
          ) {
            error = `${error} ${t('portNameRule.message')}`;
          } else if (!uniqueCheck('name', name, 'string')) {
            error = `${error} ${t('portName.duplicate.message')}`;
          }
        }
        // targetPort
        if (targetPort === '') {
          error = `${error} ${t('targetPort.empty.message')}`;
        } else if (
          !targetPort.match(regExpNum) ||
          targetPort.match(regExpNum)[0] !== targetPort
        ) {
          error = `${error} ${t('portRule.message', {
            type: 'Target',
            from: targetPortRange[0],
            to: targetPortRange[1],
          })}`;
        } else if (
          Number(targetPort) < targetPortRange[0] ||
          Number(targetPort) > targetPortRange[1]
        ) {
          error = `${error} ${t('portRule.message', {
            type: 'Target',
            from: targetPortRange[0],
            to: targetPortRange[1],
          })}`;
        }
        // nodePort
        if (nodePort !== '') {
          if (
            !nodePort.match(regExpNum) ||
            nodePort.match(regExpNum)[0] !== nodePort
          ) {
            error = `${error} ${t('portRule.message', {
              type: 'Node',
              from: nodePortRange[0],
              to: nodePortRange[1],
            })}`;
          } else if (
            Number(nodePort) < nodePortRange[0] ||
            Number(nodePort) > nodePortRange[1]
          ) {
            error = `${error} ${t('portRule.message', {
              type: 'Node',
              from: nodePortRange[0],
              to: nodePortRange[1],
            })}`;
          } else if (!uniqueCheck('nodePort', nodePort, 'number')) {
            error = `${error} ${t('port.duplicate.message', {
              type: 'Node',
            })}`;
          } else if (nodePortUseList.includes(Number(nodePort))) {
            if (isToolRunning) {
              error = `${error} ${t('nodePort.warning.message', {
                list: nodePortUseList.join(', '),
              })}`;
            } else {
              warning = `${t('nodePort.warning.message', {
                list: nodePortUseList.join(', '),
              })}`;
            }
          }
        }
        errorMessageList.push(error.trim());
        warningMessageList.push(warning.trim());
      },
    );

    // 메시지 앞에 인덱스 붙이는 함수
    /**
     *
     * @param {array} list
     * @returns {string} message
     */
    const addIndexToMessage = (list) => {
      let message = '';
      list.forEach((item, idx) => {
        let messageWithIndex = '';
        if (item !== '') {
          messageWithIndex = `${t('lineIndex.message', {
            index: idx + 1,
          })} ${item}`;
        }
        if (message !== '') {
          message = `${message}\n${messageWithIndex}`;
        } else {
          message = messageWithIndex;
        }
      });
      return message;
    };

    const errorMessage = addIndexToMessage(errorMessageList);
    const warningMessage = addIndexToMessage(warningMessageList);

    return [errorMessage, warningMessage];
  };

  function renderPortForwardingInput() {
    return (
      <PortForwardingInputBox
        portForwardingList={portForwardingList}
        protocolList={protocolList}
        targetPortRange={targetPortRange}
        nodePortRange={nodePortRange}
        nodePortUseList={nodePortUseList}
        warningMessage={portForwardingWarning}
        errorMessage={portForwardingError}
        addInputForm={addPortForwardingList}
        removeInputForm={removePortForwardingList}
        inputHandler={portForwardingInputHandler}
        visualStatus={visualStatus}
      />
    );
  }

  const result = useMemo(
    () => ({
      portForwardingList: makeResultJson(portForwardingList),
      isValid: portForwardingError === '',
    }),
    [portForwardingList, portForwardingError],
  );

  return [result, setPortForwardingState, renderPortForwardingInput];
}

export default usePortForwardingInputBox;
