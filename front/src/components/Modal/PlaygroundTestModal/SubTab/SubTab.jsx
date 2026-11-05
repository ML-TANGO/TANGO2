import React from 'react';

// CSS module
import classNames from 'classnames/bind';
import style from './SubTab.module.scss';

const cx = classNames.bind(style);

export default function SubTab({
  tabOptions = [],
  tabValue = null,
  onClick,
  ...rest
}) {
  return (
    <ul className={cx('tab-list')} {...rest}>
      {tabOptions.map((tab) => {
        const { label, value } = tab;
        return (
          <li
            key={label}
            className={cx('tab-item', value === tabValue && 'selected')}
            onClick={() => onClick(value)}
          >
            {label}
          </li>
        );
      })}
    </ul>
  );
}
