import { DateRangePicker } from '@jonathan/ui-react';

import { DATE_FORM, today } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';

import classNames from 'classnames/bind';
import style from './PeriodResource.module.scss';

const cx = classNames.bind(style);

const PeriodResource = () => {
  const { t } = useTranslation();
  const [periodResource, setPeriodResourceInterval] = useState(0);
  const [periodPastDay, setPeriodPastDay] = useState(0);
  const [from, setFrom] = useState(today(DATE_FORM));
  const [to, setTo] = useState(today(DATE_FORM));

  const periodResourceList = [
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

  const periodPastDayList = [
    {
      label: '지난 7일',
      value: 0,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: '지난 30일',
      value: 1,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
  ];

  const periodResourceRadioBtnHandler = (name, value) => {
    setPeriodResourceInterval(Number(value));
  };

  const periodPastDayRadioBtnHandler = (name, value) => {
    setPeriodPastDay(Number(value));
  };

  const onSubmitDateRange = (from, to) => {
    setFrom(dayjs(from).format(DATE_FORM));
    setTo(dayjs(to).format(DATE_FORM));
  };

  return (
    <div className={cx('period-resource-graph-box')}>
      <div className={cx('header')}>
        <div className={cx('left-content')}>
          <span className={cx('title')}>기간별 자원 사용 현황</span>
          <div className={cx('option-box')}>
            <FbRadio
              name='periodResource'
              options={periodResourceList}
              value={periodResource}
              onChange={(e) => {
                periodResourceRadioBtnHandler(
                  'periodResource',
                  e.currentTarget.value,
                );
              }}
              isLabelColor
            />
          </div>
        </div>
        <div className={cx('right-content')}>
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
                  position: 'absolute',
                  left: '-100px',
                  width: '280px',
                },
              },
            }}
            // minDate={dayjs(createDatetime).format(DATE_FORM)}
            maxDate={today(DATE_FORM)}
            submitLabel='set.label'
            cancelLabel='cancel.label'
            t={t}
          />
          <FbRadio
            name='periodPastDay'
            options={periodPastDayList}
            value={periodPastDay}
            onChange={(e) => {
              periodPastDayRadioBtnHandler(
                'periodPastDay',
                e.currentTarget.value,
              );
            }}
            isLabelColor
          />
        </div>
      </div>
      <div className={cx('graph-container')}></div>
    </div>
  );
};

export default PeriodResource;
