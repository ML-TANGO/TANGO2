// i18n
import { InputDate } from '@jonathan/ui-react';

import { useTranslation } from 'react-i18next';

// Components
import Radio from '@src/components/atoms/input/Radio';

// CSS Module
import classNames from 'classnames/bind';
import style from './TimeSettingInputForm.module.scss';

const cx = classNames.bind(style);

function TimeSettingInputForm({
  option,
  maxDate,
  endDate,
  radioBtnHandler,
  onChangeDateHandler,
}) {
  const { t } = useTranslation();
  const optionList = [
    { label: t('all.label'), value: 'all', disabled: false },
    { label: t('timeRange.label'), value: 'range', disabled: false },
  ];
  return (
    <div className={cx('time-setting-form')}>
      <div className={cx('notice')}>
        {option === 'all'
          ? t('allLogDelete.message')
          : t('selectedTimeLogDelete.message')}
      </div>
      <div className={cx('radio-box')}>
        <Radio options={optionList} value={option} onChange={radioBtnHandler} />
      </div>
      {option === 'range' && (
        <div className={cx('date-box')}>
          <InputDate
            value={endDate}
            onChange={onChangeDateHandler}
            max={maxDate}
            customSize={{ width: '218px' }}
          />
        </div>
      )}
    </div>
  );
}

export default TimeSettingInputForm;
