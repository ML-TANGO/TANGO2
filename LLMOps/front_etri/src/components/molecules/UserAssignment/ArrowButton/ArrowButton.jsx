import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './ArrowButton.module.scss';

const cx = classNames.bind(style);

export default function ArrowButton({ ariaLabel, src }) {
  return (
    <button aria-label={ariaLabel} className={cx('arrow-btn')}>
      <img src={src} alt='' aria-hidden='true' />
    </button>
  );
}
