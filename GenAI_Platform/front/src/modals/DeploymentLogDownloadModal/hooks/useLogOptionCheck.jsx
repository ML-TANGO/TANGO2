import { useState, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import LogOptionCheckForm from '@src/components/modalContents/DeploymentLogDownloadModalContent/LogOptionCheckForm';

const useLogOptionCheck = () => {
  const { t } = useTranslation();
  const [logOptions, setLogOptions] = useState([
    { label: t('logNginx.label'), checked: true },
    { label: t('logApi.label'), checked: true },
  ]);

  const handleCheckbox = (idx) => {
    logOptions[idx].checked = !logOptions[idx].checked;
    setLogOptions([...logOptions]);
  };

  const result = useMemo(
    () => ({
      logOptions,
      isValid: logOptions.filter(({ checked }) => checked).length > 0,
    }),
    [logOptions],
  );

  const renderLogOptionCheck = () => (
    <LogOptionCheckForm options={logOptions} handleCheckbox={handleCheckbox} />
  );

  return [result, renderLogOptionCheck];
};

export default useLogOptionCheck;
