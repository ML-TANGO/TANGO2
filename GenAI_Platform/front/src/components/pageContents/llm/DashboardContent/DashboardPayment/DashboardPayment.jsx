import React from 'react';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardPayment.module.scss';

const cx = classNames.bind(style);

export default function DashboardPayment() {
  const { t } = useTranslation();
  return (
    <div className={cx('payment-cont')}>
      <h3 className={cx('title')}>Payment</h3>
      <div className={cx('content')}>
        <p className={cx('nodata')}>{t('nopay.desc')}</p>
      </div>
    </div>
  );
}
