import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './ExpandRow.module.scss';

const cx = classNames.bind(style);

const ExpandRow = ({
  name,
  manager,
  total_fee,
  total_time,
  month_fee,
  month_time,
}) => {
  const { t } = useTranslation();

  const info = [
    { type: t('recordTime.label'), value: total_time },
    { type: t('month.time.label'), value: month_time },
    {
      type: t('total.manage.fee.label'),
      value: `${total_fee.toLocaleString()} 원`,
    },
    {
      type: t('month.manage.fee.label'),
      value: `${month_fee.toLocaleString()} 원`,
    },
  ];

  return (
    <div className={cx('expand-row')}>
      <div className={cx('expand-header')}>
        <span className={cx('name')}>{name}</span>
        <span className={cx('manager')}>{manager}</span>
      </div>
      <div className={cx('expand-info')}>
        {info.map(({ type, value }) => (
          <div className={cx('info')} key={type}>
            <span className={cx('type')}>{type}</span>
            <span className={cx('value')}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ExpandRow;
