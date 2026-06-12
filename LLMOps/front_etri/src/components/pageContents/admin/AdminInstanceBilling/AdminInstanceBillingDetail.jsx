import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './AdminInstanceBillingDetail.module.scss';

const cx = classNames.bind(style);

const timeUnit = {
  hour: '시간당',
  minute: '분당',
  day: '일',
  month: '월',
};

const AdminInstanceBillingDetail = ({ data }) => {
  const { t } = useTranslation();

  const { instance_list, name, time_unit, time_unit_cost } = data;

  return (
    <div className={cx('container')}>
      <div className={cx('header')}>
        <span className={cx('package-name')}>{name}</span>
        <div className={cx('cost')}>
          <span className={cx('unit')}>{timeUnit[time_unit]}</span>
          <span className={cx('money')}>{time_unit_cost} 원</span>
        </div>
      </div>
      <div className={cx('gray-line')}></div>
      <span className={cx('title')}>패키지 구성</span>
      <div className={cx('instance-table')}>
        <div className={cx('type')}>
          <div className={cx('name')}>인스턴스 이름</div>
          <div className={cx('spec')}>인스턴스 사양</div>
          <div className={cx('domain')}>출처</div>
          <div className={cx('cost')}>운영 비용</div>
        </div>
        {instance_list.map(({ source, instance_id, instance_allocate }) => (
          <div className={cx('info')} key={instance_id}>
            <div className={cx('name')}>{instance_id}</div>
            <div className={cx('spec')}>{instance_allocate}</div>
            <div className={cx('domain')}>{source}</div>
            <div className={cx('cost')}>운영 비용</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AdminInstanceBillingDetail;
