import { DateRangePicker } from '@tango/ui-react';

import { DATE_FORM, today } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';

import classNames from 'classnames/bind';
import style from './DetailCsvDownload.module.scss';

const cx = classNames.bind(style);

const timeTypeList = [
  {
    label: 'all.label',
    value: 0,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: 'timeRange.label',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

const DetailCsvDownload = () => {
  const { t } = useTranslation();

  const [timeType, setTimeType] = useState(0);
  const [priceType, setPriceType] = useState('default');
  const [from, setFrom] = useState(today(DATE_FORM));
  const [to, setTo] = useState(today(DATE_FORM));

  const onSubmitDateRange = (from, to) => {
    setFrom(dayjs(from).format(DATE_FORM));
    setTo(dayjs(to).format(DATE_FORM));
  };

  const radioBtnHandler = (name, value) => {
    setTimeType(Number(value));
  };

  const [priceOption, setPriceOption] = useState([
    { label: '요금제 변경 이력', value: 'default', isCheck: true },
    {
      label: '워크스페이스별 요금제 변경 이력',
      value: 'workspace',
      isCheck: false,
    },
  ]);

  const handlePriceOption = (value) => {
    setPriceType(value);
    setPriceOption((prevOptions) =>
      prevOptions.map((option) => ({ ...option, isCheck: !option.isCheck })),
    );
  };

  return (
    <div className={cx('container')}>
      <span className={cx('desc')}>
        지정한 시간의 CSV 파일을 다운로드 합니다.
      </span>
      <div className={cx('time-box')}>
        <div className={cx('radio-container')}>
          <FbRadio
            name='timeType'
            options={timeTypeList}
            value={timeType}
            onChange={(e) => {
              radioBtnHandler('timeType', e.currentTarget.value);
            }}
            isLabelColor
          />
        </div>

        {timeType === 1 && (
          <DateRangePicker
            from={from}
            to={to}
            onSubmit={onSubmitDateRange}
            calendarSize='small'
            customStyle={{
              globalForm: {
                position: 'static',
              },
              splitType: {
                inputForm: {
                  width: '260px',
                },
              },
            }}
            // minDate={dayjs(createDatetime).format(DATE_FORM)}
            maxDate={today(DATE_FORM)}
            submitLabel='set.label'
            cancelLabel='cancel.label'
            t={t}
          />
        )}
      </div>
      <div className={cx('option-box')}>
        {priceOption.map(({ label, value, isCheck }) => (
          <div className={cx('option')} key={label}>
            <input
              className={cx('checkbox')}
              type='checkbox'
              checked={isCheck}
              onChange={() => handlePriceOption(value)}
            />
            <span className={cx('price-option-label')}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DetailCsvDownload;
