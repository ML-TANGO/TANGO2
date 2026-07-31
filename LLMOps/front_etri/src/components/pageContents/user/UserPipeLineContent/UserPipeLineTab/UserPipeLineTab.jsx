import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserPipeLineTab.module.scss';

const cx = classNames.bind(style);

export default function UserPipeLineTab({ tabList, selectedTab, handleTab }) {
  return (
    <ul className={cx('tab-list')}>
      {tabList.map((el) => (
        <li
          className={cx('tab-item', selectedTab === el.value && 'selected')}
          key={el.value}
          onClick={() => handleTab(el.value)}
        >
          {el.label}
        </li>
      ))}
    </ul>
  );
}
