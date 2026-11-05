import { useCallback, useEffect, useState } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

// Components
import MultiCheckSelect from '@src/components/molecules/MutliCheckSelect';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const TrainingMultiCheckSelectContainer = ({
  submit,
  selectedOptions,
  groupType,
  group,
  reset,
  chipList,
  readOnly,
  t,
}) => {
  const [trainingOptions, setTrainingOptions] = useState([]);
  const [trainingList, setTrainingList] = useState([]);
  const [selected, setSelected] = useState(null);

  // Training 옵션 목록 조회
  const getTrainingOptions = useCallback(
    async (gid) => {
      const response = await callApi({
        url: `options/records?${groupType.value}_id=${gid}`,
        method: 'get',
      });
      const { result, status, message } = response;
      if (status === STATUS_SUCCESS) {
        const { training_list: tOptions } = result;
        setTrainingList(tOptions);
        if (tOptions.length > 0) {
          setTrainingOptions([
            { label: 'all.label', value: 'all', checked: false },
            ...tOptions.map(({ id, name }) => ({
              label: name,
              value: id,
              checked: false,
            })),
          ]);
        }
      } else {
        toast.error(message);
      }
    },
    [groupType],
  );

  const onSubmit = useCallback(
    (opt) => {
      const newOpt = opt.filter(({ checked }) => checked);
      setTrainingOptions(opt);
      submit('trainingOption', newOpt);
      setSelected({ label: `${t('training.label')} (${newOpt.length})` });
    },
    [setTrainingOptions, submit, t],
  );

  const updateTrainingOptions = (newOptions) => {
    setTrainingOptions(newOptions);
  };

  // useEffect(() => {
  //   if (group) getTrainingOptions(group.value);
  // }, [getTrainingOptions, group]);

  useEffect(() => {
    const tList = trainingList.map(({ id, name }) => ({
      label: name,
      value: id,
      checked: false,
    }));
    let isAll = true;
    let checkCount = 0;
    const newTraingOptions = tList.map((opt) => {
      let checked = false;
      for (let i = 0; i < selectedOptions.length; i += 1) {
        const { value: selectedVal, checked: selectedChecked } =
          selectedOptions[i];
        if (selectedVal === opt.value && selectedChecked) {
          checked = true;
          checkCount += 1;
          break;
        }
      }
      const newOpt = { ...opt, checked };
      if (!checked) isAll = false;
      return newOpt;
    });
    if (newTraingOptions.length > 0)
      updateTrainingOptions([
        { label: t('all.label'), value: 'all', checked: isAll },
        ...newTraingOptions,
      ]);
    setSelected(
      checkCount !== 0
        ? { label: `${t('training.label')} (${checkCount})` }
        : null,
    );
  }, [selectedOptions, trainingList, t]);

  useEffect(() => {
    setSelected(null);
  }, [reset]);

  useEffect(() => {
    if (chipList.length === 0) setSelected(null);
  }, [chipList, setSelected]);
  return (
    <MultiCheckSelect
      name='training'
      options={trainingOptions}
      placeholder='selectTraining.placeholder'
      sizeType='small'
      selected={selected}
      onSubmit={onSubmit}
      disabledErrorText
      readOnly={readOnly}
      search
    />
  );
};

export default withTranslation()(TrainingMultiCheckSelectContainer);
