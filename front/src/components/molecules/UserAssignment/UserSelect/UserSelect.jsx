import React from 'react';

import classNames from 'classnames/bind';
import style from './UserSelect.module.scss';

const cx = classNames.bind(style);

export default function UserSelect({
  type,
  label,
  placeholder,
  list = [],
  pickedList,
  handlePickUser,
}) {
  const [searchValue, setSearchValue] = React.useState('');

  const handleSearch = (e) => {
    setSearchValue(e.target.value);
  };

  return (
    <div className={cx('user-select-cont')}>
      <label className={cx('select-title', type)} htmlFor=''>
        {label}
      </label>
      <div className={cx('search-input-cont')}>
        <input
          className={cx('search-input')}
          type='text'
          placeholder={placeholder}
          value={searchValue}
          onChange={handleSearch}
        />
        <span className={cx('txt-count')}>0/10</span>
      </div>
      <ul className={cx('user-list')}>
        {list.map((user) => (
          <li
            key={user.id}
            className={cx('user-item', pickedList.has(user.id) && 'selected')}
            onClick={() => handlePickUser(user)}
          >
            {user.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
