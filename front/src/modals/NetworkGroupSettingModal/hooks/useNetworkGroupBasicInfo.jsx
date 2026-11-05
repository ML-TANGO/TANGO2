import { useState, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Utils
import { errorToastMessage } from '@src/utils';

import { debounce } from 'lodash';

// Components
import NetworkGroupBasicInfoForm from '@src/components/modalContents/NetworkGroupSettingModalContent/NetworkGroupBasicInfoForm';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const useNetworkGroupBasicInfo = (modalType) => {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [category, setCategory] = useState(1);
  const [speed, setSpeed] = useState('');
  const [description, setDescription] = useState('');
  const [nameError, setNameError] = useState(null);
  const [speedError, setSpeedError] = useState(null);

  // 카테고리 옵션
  const categoryOptions = [
    { label: 'infiniBand.label', value: 1 },
    { label: 'ethernet.label', value: 0 },
  ];

  // 인풋 입력 핸들러
  const inputHandler = (e) => {
    const { name, value } = e.target;
    if (name === 'name') {
      setName(value);
    } else if (name === 'category') {
      setCategory(Number(value));
    } else if (name === 'speed') {
      setSpeed(Number(value));
    } else if (name === 'description') {
      setDescription(value);
    }
    checkValidate(name, value);
  };

  /**
   * 그룹 이름 중복 체크
   */
  const checkNameDuplicated = debounce(async (value) => {
    const response = await callApi({
      url: `networks/network-group-name-duplicate?name=${value}`,
      method: 'GET',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (!result) {
        setNameError(t('network.groupName.duplicate.message'));
      }
      return result;
    } else {
      errorToastMessage(error, message);
      return false;
    }
  }, 250);

  /**
   * 인풋 유효성 체크
   * @param {string} name 인풋 이름
   * @param {*} value 인풋 값
   */
  const checkValidate = async (name, value) => {
    if (name === 'name') {
      let errorMessage = '';
      if (value === '') {
        errorMessage = t('network.groupName.empty.message');
      } else {
        // 글자수 체크
        if (value.length > 25) {
          setName(value.slice(0, 25));
        }
        // 중복 체크
        checkNameDuplicated(value);
      }
      setNameError(errorMessage);
    } else if (name === 'speed') {
      let message = '';
      if (value === '') {
        message = t('network.speed.empty.message');
      }
      setSpeedError(message);
    }
  };

  const setBasicInfoState = (state) => {
    setName(state.name);
    setCategory(state.category);
    setSpeed(state.speed);
    setDescription(state.description);
  };

  /**
   * 네트워크 그룹 기본 정보 입력 폼 렌더링 함수
   * @returns 네트워크 그룹 기본 정보 입력 폼
   */
  const renderBasicInfoForm = () => {
    return (
      <NetworkGroupBasicInfoForm
        modalType={modalType}
        name={name}
        nameError={nameError}
        category={category}
        categoryOptions={categoryOptions}
        speed={speed}
        speedError={speedError}
        description={description}
        inputHandler={inputHandler}
      />
    );
  };

  const result = useMemo(
    () => ({
      isValid:
        modalType === 'NETWORK_GROUP_SETTING'
          ? (nameError === null || nameError === '') &&
            (speedError === null || speedError === '')
          : nameError === '' && speedError === '',
      name,
      category,
      speed,
      description,
    }),
    [category, description, name, nameError, speed, speedError, modalType],
  );

  return [result, setBasicInfoState, renderBasicInfoForm];
};

export default useNetworkGroupBasicInfo;
