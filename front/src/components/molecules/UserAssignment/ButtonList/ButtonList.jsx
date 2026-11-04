import React from 'react';

import ArrowButton from '../ArrowButton';

// CSS Module
import classNames from 'classnames/bind';
import style from './ButtonList.module.scss';

const cx = classNames.bind(style);

export default function ButtonList() {
  return (
    <div className={cx('btn-cont')}>
      <ArrowButton
        ariaLabel={'모두 선택 버튼'}
        src={'/images/icon/ic-angle-right-all.svg'}
      />
      <ArrowButton
        ariaLabel={'선택 버튼'}
        src={'/images/icon/ic-angle-right.svg'}
      />
      <ArrowButton
        ariaLabel={'선택 제거 버튼'}
        src={'/images/icon/ic-angle-left.svg'}
      />
      <ArrowButton
        ariaLabel={'모두 선택 제거 버튼'}
        src={'/images/icon/ic-angle-left-all.svg'}
      />
    </div>
  );
}
