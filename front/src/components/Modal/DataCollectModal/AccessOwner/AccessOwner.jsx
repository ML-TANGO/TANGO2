import React from 'react';

import AccessTypeRadio from '@src/components/molecules/AccessOwnerSelect';

// CSS Module
import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export default function AccessOwner() {
  return (
    <div className={cx('row')}>
      <AccessTypeRadio />
    </div>
  );
}
