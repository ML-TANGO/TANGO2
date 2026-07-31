import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';

import WorkspaceUsageTable from './WorkspaceUsageTable';

import classNames from 'classnames/bind';
import style from './SummaryContent.module.scss';

const cx = classNames.bind(style);

const SummaryContent = () => {
  const { t } = useTranslation();

  const [cloudType, setCloudType] = useState(0);
  const [priceOption, setPriceOption] = useState([
    { label: '매출', value: 'sale', isCheck: true },
    { label: '순이익', value: 'profit', isCheck: true },
    { label: 'on-promises 사용 전력량', value: 'onPromise', isCheck: true },
    { label: '퍼블릭 클라우드 운영 비용', value: 'publicCloud', isCheck: true },
  ]);

  const cloudTypeList = [
    {
      label: '전체',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'On-premises',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: '퍼블릭 클라우드 전체',
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

  const radioBtnHandler = (name, value) => {
    setCloudType(Number(value));
  };

  const getCurrentMonth = () => {
    const today = new Date();
    const month = today.getMonth() + 1;
    return month;
  };

  const currentMonth = getCurrentMonth();

  return (
    <div className={cx('container')}>
      <div className={cx('cost-summary')}>
        <div className={cx('month-info-box')}>
          <div className={cx('info')}>
            <div className={cx('title')}>
              {currentMonth}월 {t('month.sale.label')}
            </div>
            <div className={cx('value', 'sale')}>0,000,000</div>
          </div>
          <div className={cx('divider-line')}></div>
          <div className={cx('info')}>
            <div className={cx('title')}>
              {currentMonth}월 {t('month.cost.label')}
            </div>
            <div className={cx('value', 'cost')}>0,000,000</div>
          </div>
          <div className={cx('divider-line')}></div>
          <div className={cx('info')}>
            <div className={cx('title')}>
              {currentMonth}월 {t('month.profit.label')}
            </div>
            <div className={cx('value', 'profit')}>0,000,000</div>
          </div>
        </div>
        <div className={cx('month-public-cloud')}>
          <div className={cx('title')}>
            {currentMonth}월 {t('month.public.cloud.label')}
          </div>
          <div className={cx('value', 'naver')}>NAVER CLOUD</div>
        </div>
      </div>

      <div className={cx('day-profit-graph-box')}>
        <div className={cx('header')}>
          <div className={cx('left-content')}>
            <span className={cx('title')}>일별 손익 현황</span>
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
                    className={cx(
                      'price-option-label',
                      !isCheck && 'not-select',
                    )}
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
                radioBtnHandler('cloudType', e.currentTarget.value);
              }}
              isLabelColor
            />
          </div>
        </div>
        <div className={cx('graph-container')}></div>
      </div>
      <WorkspaceUsageTable />
    </div>
  );
};

export default SummaryContent;
