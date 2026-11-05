import { useState, useMemo, useEffect } from 'react';

// Utils
import { errorToastMessage } from '@src/utils';

// Components
import NetworkGroupIpRangeForm from '@src/components/modalContents/NetworkGroupSettingModalContent/NetworkGroupIpRangeForm';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { useCallback } from 'react';

const useNetworkGroupIpRange = () => {
  const [ip, setIp] = useState([null, null, null, 0]);
  const [ipRangeStart, setIpRangeStart] = useState([null, null, null, null]);
  const [ipRangeEnd, setIpRangeEnd] = useState([null, null, null, null]);
  const [subnetMask, setSubnetMask] = useState({ label: '24', value: 24 });
  const [networkGroupId, setNetworkGroupId] = useState(null);
  const [error, setError] = useState(null);
  const [validate, setValidate] = useState(false);

  const subnetMaskOption = [
    { isTitle: true, label: 'Subnet Mask Prefix', value: 0 },
    { label: '16', value: 16 },
    { label: '24', value: 24 },
  ];

  const setIpRangeState = (state, networkGroupId) => {
    setNetworkGroupId(networkGroupId);
    if (state.ip) {
      let ipArr = state.ip.split('.');
      ipArr = ipArr.map((v) => Number(v));
      setIp(ipArr);
    }
    if (state.ip_range_start) {
      let startArr = state.ip_range_start.split('.');
      startArr = startArr.map((v) => Number(v));
      setIpRangeStart(startArr);
    }
    if (state.ip_range_end) {
      let endArr = state.ip_range_end.split('.');
      endArr = endArr.map((v) => Number(v));
      setIpRangeEnd(endArr);
    }
    if (state.subnet_mask) {
      const subnetMaskObj = {
        label: state.subnet_mask.toString(),
        value: state.subnet_mask,
      };
      setSubnetMask(subnetMaskObj);
    }
  };

  /**
   * IP 입력 핸들러
   * @param {object} e 입력 이벤트
   */
  const inputHandler = (e) => {
    const { name, value } = e.target;
    const newIp = [...ip];
    const i = name.slice(2, 3) - 1;
    let newValue = value;
    if (newValue === '') {
      newValue = null;
    } else if (Number(newValue) < 0) {
      newValue = 0;
    } else if (Number(newValue) > 255) {
      newValue = 255;
    } else {
      newValue = Number(newValue);
    }
    newIp[i] = newValue;
    setIp(newIp);
    reset();
  };

  /**
   * SubnetMask prefix 값 선택
   * @param {object} value  ex){label: '16', value: 16}
   */
  const selectHandler = (value) => {
    setSubnetMask(value);
    const newIp = [...ip];
    // 16일 경우 3번째 칸 초기화
    if (value.value === 16) {
      newIp[2] = 0;
    } else if (value.value === 24) {
      newIp[2] = null;
    }
    setIp(newIp);
    reset();
  };

  /**
   * 조회 결과 초기화
   */
  const reset = () => {
    setIpRangeStart([null, null, null, null]);
    setIpRangeEnd([null, null, null, null]);
    setError(null);
  };

  /**
   * 조회 가능 여부 체크
   */
  const checkValidate = useCallback(() => {
    const newIp = [...ip];
    const subnetMaskPrefix = subnetMask.value;
    if (subnetMaskPrefix === 24) {
      let emptyCount = 0;
      for (let i = 0; i < 3; i++) {
        if (newIp[i] === null || newIp === '') {
          emptyCount++;
        }
      }
      if (emptyCount > 0) {
        setValidate(false);
      } else {
        setValidate(true);
      }
    } else if (subnetMaskPrefix === 16) {
      let emptyCount = 0;
      for (let i = 0; i < 2; i++) {
        if (newIp[i] === null || newIp === '') {
          emptyCount++;
        }
      }
      if (emptyCount > 0) {
        setValidate(false);
      } else {
        setValidate(true);
      }
    }
  }, [ip, subnetMask.value]);

  /**
   * 사용 가능한 IP 범위 조회
   */
  const getIpRange = async () => {
    let newIp = [...ip];
    newIp = newIp.map((v) => {
      if (v) {
        return (v = Number(v));
      } else {
        return (v = 0);
      }
    });
    const response = await callApi({
      url: 'networks/ip-range',
      method: 'post',
      body: {
        network_group_id: networkGroupId,
        ip: newIp.join('.'),
        subnet_mask: subnetMask.value,
      },
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result) {
        if (result.is_duplicate) {
          setError(true);
        } else {
          let startArr = result.ip_range_start.split('.');
          startArr = startArr.map((v) => Number(v));
          setIpRangeStart(startArr);
          let endArr = result.ip_range_end.split('.');
          endArr = endArr.map((v) => Number(v));
          setIpRangeEnd(endArr);
          setError(false);
        }
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  const renderIpRangeForm = () => {
    return (
      <NetworkGroupIpRangeForm
        ip={ip}
        ipRangeStart={ipRangeStart}
        ipRangeEnd={ipRangeEnd}
        subnetMaskOption={subnetMaskOption}
        subnetMask={subnetMask}
        getIpRange={getIpRange}
        error={error}
        validate={validate}
        inputHandler={inputHandler}
        selectHandler={selectHandler}
      />
    );
  };

  useEffect(() => {
    checkValidate();
  }, [checkValidate, ip, subnetMask]);

  const result = useMemo(
    () => ({
      isValid: error !== null && !error,
      ip,
      subnetMask,
      ipRangeStart,
      ipRangeEnd,
    }),
    [error, ip, subnetMask, ipRangeStart, ipRangeEnd],
  );

  return [result, setIpRangeState, renderIpRangeForm];
};

export default useNetworkGroupIpRange;
