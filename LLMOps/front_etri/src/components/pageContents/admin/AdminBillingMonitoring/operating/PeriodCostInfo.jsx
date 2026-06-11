import { DateRangePicker } from '@tango/ui-react';

import { DATE_FORM, today } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';

import classNames from 'classnames/bind';
import style from './PeriodCostInfo.module.scss';

const cx = classNames.bind(style);

const PeriodCostInfo = () => {
  const { t } = useTranslation();

  const [cloudType, setCloudType] = useState(0);
  const [pastPeriodType, setPastPeriodType] = useState(0);
  const [from, setFrom] = useState(today(DATE_FORM));
  const [to, setTo] = useState(today(DATE_FORM));

  const [priceOption, setPriceOption] = useState([
    { label: '매출', value: 'sale', isCheck: true },
    { label: '운영 비용', value: 'operating', isCheck: true },
    { label: '순이익', value: 'netProfit', isCheck: true },
  ]);

  const cloudTypeList = [
    {
      label: '전체',
      value: 0,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: 'On-premises',
      value: 1,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: '퍼블릭 클라우드 전체',
      value: 2,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: 'NAVER CLOUD',
      value: 3,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: 'Azure',
      value: 4,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: 'AWS',
      value: 5,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const pastPeriodList = [
    {
      label: '지난 1일',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: '지난 7일',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: '지난 30일',
      value: 2,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const handlePriceOption = (value) => {
    setPriceOption((prevOptions) =>
      prevOptions.map((option) =>
        option.value === value
          ? { ...option, isCheck: !option.isCheck }
          : option,
      ),
    );
  };

  const cloudRadioBtnHandler = (name, value) => {
    setCloudType(Number(value));
  };

  const pastPeriodRadioBtnHandler = (name, value) => {
    setPastPeriodType(Number(value));
  };

  const onSubmitDateRange = (from, to) => {
    setFrom(dayjs(from).format(DATE_FORM));
    setTo(dayjs(to).format(DATE_FORM));
  };

  return (
    <div className={cx('period-profit-graph-box')}>
      <div className={cx('header')}>
        <div className={cx('left-content')}>
          <span className={cx('title')}>기간별 손익 현황</span>
          <div className={cx('option-box')}>
            {priceOption.map(({ label, value, isCheck }) => (
              <div className={cx('option')} key={label}>
                <input
                  className={cx('checkbox')}
                  type='checkbox'
                  checked={isCheck}
                  onChange={() => handlePriceOption(value)}
                />
                <span
                  className={cx('price-option-label', !isCheck && 'not-select')}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className={cx('right-content')}>
          <FbRadio
            name='cloudType'
            options={cloudTypeList}
            value={cloudType}
            onChange={(e) => {
              cloudRadioBtnHandler('cloudType', e.currentTarget.value);
            }}
            isLabelColor
          />
        </div>
      </div>
      <div className={cx('graph-container')}>
        <div className={cx('period-section')}>
          <FbRadio
            name='pastPeriodType'
            options={pastPeriodList}
            value={pastPeriodType}
            onChange={(e) => {
              pastPeriodRadioBtnHandler(
                'pastPeriodType',
                e.currentTarget.value,
              );
            }}
            isLabelColor
          />
          <DateRangePicker
            from={from}
            to={to}
            onSubmit={onSubmitDateRange}
            calendarSize='small'
            customStyle={{
              globalForm: {
                // position: 'static',
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
        </div>
      </div>
    </div>
  );
};

export default PeriodCostInfo;
