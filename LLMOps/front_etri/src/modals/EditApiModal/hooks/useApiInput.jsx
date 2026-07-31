import { useState, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import ApiInputForm from '@src/components/modalContents/EditApiModalContent/ApiInputForm';

const useApiInput = (apiAddress) => {
  const { t } = useTranslation();
  const [endpoint, setEndpoint] = useState(
    apiAddress.includes('/deployment/')
      ? apiAddress.split('/deployment/')[1].replace('/', '')
      : apiAddress.split(':server_port/')[1].replace('/', ''), // 마지막에 붙는 / 없애고 보여주기
  );
  const [endpointError, setEndpointError] = useState(null);

  const textInputHandler = (e) => {
    const { value } = e.target;
    setEndpoint(value);
    checkValidate(value);
  };

  const checkValidate = (value) => {
    let message = '';
    const regType = /^[a-z0-9][a-z0-9/-]*[a-z0-9-]/;
    if (value === '') {
      message = t('endpoint.empty.message');
    } else if (!value.match(regType) || value.match(regType)[0] !== value) {
      message = t('endpointRule.message');
    }
    setEndpointError(message);
  };

  const setApiInputState = (state) => {
    setEndpointError(state.endpointError);
  };

  const result = useMemo(
    () => ({
      isValid: endpointError === '',
      endpoint,
    }),
    [endpoint, endpointError],
  );

  const renderApiInput = () => (
    <ApiInputForm
      apiAddress={apiAddress}
      endpoint={endpoint}
      endpointError={endpointError}
      textInputHandler={textInputHandler}
    />
  );

  return [result, setApiInputState, renderApiInput];
};

export default useApiInput;
