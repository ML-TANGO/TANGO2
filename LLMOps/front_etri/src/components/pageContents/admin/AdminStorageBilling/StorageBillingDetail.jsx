import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './StorageBillingDetail.module.scss';

const cx = classNames.bind(style);

const StorageBillingDetail = ({ data }) => {
  const { t } = useTranslation();

  const { cost, name, size, size_unit, source } = data;

  const infoList = [
    { type: '스토리지', value: '임시 스토리지' },
    { type: '할당 용량', value: `${size} ${size_unit}` },
    { type: '읽기 속도', value: `데이터없음` },
    { type: '쓰는 속도', value: `데이터 없음` },
    { type: '출처', value: `${source}` },
  ];

  return (
    <div className={cx('container')}>
      <div className={cx('header')}>
        <span className={cx('name')}>{name}</span>
        <div className={cx('cost-info')}>
          <span className={cx('text')}>월별 구독료</span>
          <span className={cx('cost')}>{cost.toLocaleString()} 원</span>
        </div>
      </div>
      <div className={cx('package')}>
        <span className={cx('name')}>패키지 구성</span>
        <div className={cx('info-list')}>
          {infoList.map(({ type, value }, index) => (
            <div className={cx('info')} key={index}>
              <span className={cx('type')}>{type}</span>
              <span className={cx('value')}>{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={cx('workspace')}>
        <span className={cx('title')}>워크스페이스 할당 현황</span>
      </div>
    </div>
  );
};

export default StorageBillingDetail;
