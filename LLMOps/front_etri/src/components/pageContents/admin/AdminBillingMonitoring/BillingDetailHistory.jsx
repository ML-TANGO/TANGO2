import React from 'react';

import classNames from 'classnames/bind';
import style from './BillingDetailHistory.module.scss';

const cx = classNames.bind(style);

const BillingDetailHistory = () => {
  return (
    <div className={cx('history-container')}>
      <div className={cx('fee-history-box')}>
        <div className={cx('header')}>요금제 관리 이력</div>
        <div className={cx('content')}></div>
      </div>
      <div className={cx('workspace-history-box')}>
        <div className={cx('header')}>
          워크스페이스 요금제 가입 및 변경 이력
        </div>
        <div className={cx('content')}></div>
      </div>
    </div>
  );
};

export default BillingDetailHistory;
