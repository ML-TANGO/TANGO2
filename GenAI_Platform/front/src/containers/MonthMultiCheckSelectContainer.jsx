import { useState, useCallback, useEffect } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Components
import MultiCheckSelect from '@src/components/molecules/MutliCheckSelect';

const INIT_STATE = new Array(12)
  .fill(null)
  .map((d, i) => ({ label: `${i + 1}`, value: i + 1, checked: false }));

const MonthMultiCheckSelectContainer = ({
  submit,
  selectedOptions,
  reset,
  chipList,
  readOnly,
  t,
}) => {
  const [monthOptions, setMonthOptions] = useState([
    { label: 'all.label', value: 'all', checked: false },
    ...INIT_STATE,
  ]);
  const [selected, setSelected] = useState(null);
  const onSubmit = useCallback(
    (opt) => {
      const newOpt = opt.filter(({ checked }) => checked);
      setMonthOptions(opt);
      submit('monthOption', newOpt);
      setSelected({ label: `month(${newOpt.length}}).label` });
    },
    [setMonthOptions, submit],
  );

  const updateMonthOptions = (newMonthOptions) => {
    setMonthOptions(newMonthOptions);
  };

  useEffect(() => {
    let isAll = true;
    let checkCount = 0;
    const newMonthOptions = INIT_STATE.map((opt) => {
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
    updateMonthOptions([
      { label: t('all.label'), value: 'all', checked: isAll },
      ...newMonthOptions,
    ]);
    setSelected(
      checkCount !== 0 ? { label: `month(${checkCount}).label` } : null,
    );
  }, [selectedOptions, t]);

  useEffect(() => {
    setSelected(null);
  }, [reset]);

  useEffect(() => {
    if (chipList && chipList.length === 0) setSelected(null);
  }, [chipList, setSelected]);

  return (
    <MultiCheckSelect
      name='month'
      options={monthOptions}
      placeholder='selectMonth.placeholder'
      sizeType='small'
      selected={selected}
      onSubmit={onSubmit}
      readOnly={readOnly}
      disabledErrorText
    />
  );
};

export default withTranslation()(MonthMultiCheckSelectContainer);
