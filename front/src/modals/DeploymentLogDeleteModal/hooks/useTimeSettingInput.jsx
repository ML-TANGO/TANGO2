import { useState, useMemo } from 'react';

// Date time Util
import { DATE_FORM, today, dayjsToString } from '@src/datetimeUtils';

// Components
import TimeSettingInputForm from '@src/components/modalContents/DeploymentLogDeleteModalContent/TimeSettingInputForm';

const useTimeSettingInput = () => {
  const maxDate = today(DATE_FORM); // today
  const [endDate, setEndDate] = useState();
  const [option, setOption] = useState('all');

  const radioBtnHandler = (e) => {
    const { value } = e.target;
    setOption(value);
  };

  const onChangeDateHandler = (e) => {
    const { value } = e.target;
    setEndDate(value);
  };

  const result = useMemo(
    () => ({
      isRange: option === 'range',
      endDate: dayjsToString(endDate, `${DATE_FORM} 00:00:00`),
      isValid: option === 'all' || endDate,
    }),
    [endDate, option],
  );

  const renderTimeSettingInput = () => (
    <TimeSettingInputForm
      option={option}
      maxDate={maxDate}
      endDate={endDate}
      radioBtnHandler={radioBtnHandler}
      onChangeDateHandler={onChangeDateHandler}
    />
  );

  return [result, renderTimeSettingInput];
};

export default useTimeSettingInput;
