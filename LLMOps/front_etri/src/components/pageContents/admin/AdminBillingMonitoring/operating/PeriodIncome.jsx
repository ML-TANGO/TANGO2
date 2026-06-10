import { DateRangePicker } from '@jonathan/ui-react';

import { DATE_FORM, today } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';

import classNames from 'classnames/bind';
import style from './PeriodIncome.module.scss';

const cx = classNames.bind(style);

const PeriodIncome = () => {
  const { t } = useTranslation();
  const [periodPastDay, setPeriodPastDay] = useState(0);
  const [from, setFrom] = useState(today(DATE_FORM));
  const [to, setTo] = useState(today(DATE_FORM));
  const [cloudOption, setCloudOption] = useState([
    { label: '전체', value: 'all', isCheck: true },
    { label: 'On-premises', value: 'onPremises', isCheck: true },
    { label: '퍼블릭 클라우드 전체', value: 'publicCloud', isCheck: true },
    { label: 'NAVER CLOUD', value: 'naverCloud', isCheck: true },
    { label: 'Azure', value: 'azure', isCheck: true },
    { label: 'AWS', value: 'aws', isCheck: true },
  ]);

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

  const periodPastDayRadioBtnHandler = (name, value) => {
    setPeriodPastDay(Number(value));
  };

  const onSubmitDateRange = (from, to) => {
    setFrom(dayjs(from).format(DATE_FORM));
    setTo(dayjs(to).format(DATE_FORM));
  };

  const handleCloudOption = (value) => {
    setCloudOption((prevOptions) => {
      let updatedOptions;

      if (value === 'all') {
        // 'all'이 선택되면 모든 옵션의 isCheck를 'all'의 isCheck와 동일하게 설정
        const allChecked = !prevOptions.find((option) => option.value === 'all')
          .isCheck;
        updatedOptions = prevOptions.map((option) => ({
          ...option,
          isCheck: allChecked,
        }));
      } else if (value === 'publicCloud') {
        // 'publicCloud'가 선택되면 하위 클라우드 옵션도 동일하게 설정
        const publicCloudChecked = !prevOptions.find(
          (option) => option.value === 'publicCloud',
        ).isCheck;
        updatedOptions = prevOptions.map((option) => {
          if (['naverCloud', 'azure', 'aws'].includes(option.value)) {
            return { ...option, isCheck: publicCloudChecked };
          }
          if (option.value === 'publicCloud') {
            return { ...option, isCheck: publicCloudChecked };
          }
          return option;
        });
      } else if (['naverCloud', 'azure', 'aws'].includes(value)) {
        // 개별 클라우드 옵션 선택 시
        updatedOptions = prevOptions.map((option) =>
          option.value === value
            ? { ...option, isCheck: !option.isCheck }
            : option,
        );

        // 모든 하위 클라우드 옵션이 선택되었는지 확인하고 publicCloud 업데이트
        const allSubCloudsChecked = updatedOptions
          .filter((option) =>
            ['naverCloud', 'azure', 'aws'].includes(option.value),
          )
          .every((option) => option.isCheck);

        updatedOptions = updatedOptions.map((option) =>
          option.value === 'publicCloud'
            ? { ...option, isCheck: allSubCloudsChecked }
            : option,
        );
      } else {
        // 개별 옵션 선택 시
        updatedOptions = prevOptions.map((option) =>
          option.value === value
            ? { ...option, isCheck: !option.isCheck }
            : option,
        );
      }

      // 모든 옵션이 선택되었는지 확인하고 'all' 업데이트
      const allChecked = updatedOptions.every(
        (option) => option.value === 'all' || option.isCheck,
      );
      updatedOptions = updatedOptions.map((option) =>
        option.value === 'all' ? { ...option, isCheck: allChecked } : option,
      );

      return updatedOptions;
    });
  };

  return (
    <div className={cx('period-income-graph-box')}>
      <div className={cx('header')}>
        <div className={cx('left-content')}>
          <span className={cx('title')}>기간별 수익 및 지출 현황</span>
          <div className={cx('option-box')}>
            {cloudOption.map(({ label, value, isCheck }) => (
              <div className={cx('option')} key={label}>
                <input
                  className={cx('checkbox')}
                  type='checkbox'
                  checked={isCheck}
                  onChange={() => handleCloudOption(value)}
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
          <FbRadio
            name='periodIncomeDay'
            options={periodPastDayList}
            value={periodPastDay}
            onChange={(e) => {
              periodPastDayRadioBtnHandler(
                'periodIncomeDay',
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

export default PeriodIncome;
