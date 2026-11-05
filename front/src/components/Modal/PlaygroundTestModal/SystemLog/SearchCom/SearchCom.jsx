import { InputText } from '@jonathan/ui-react';

import React, { useState } from 'react';

import classNames from 'classnames/bind';
import style from './SearchCom.module.scss';

const cx = classNames.bind(style);

const RightIcon = ({ color }) => {
  return (
    <svg
      xmlns='http://www.w3.org/2000/svg'
      width='16'
      height='17'
      viewBox='0 0 16 17'
      fill='none'
    >
      <path
        d='M6.53318 2.9694L11.5332 7.9694C11.6031 8.03908 11.6586 8.12187 11.6964 8.21304C11.7343 8.3042 11.7538 8.40194 11.7538 8.50065C11.7538 8.59936 11.7343 8.6971 11.6964 8.78827C11.6586 8.87943 11.6031 8.96222 11.5332 9.0319L6.53318 14.0319C6.39228 14.1728 6.20118 14.252 6.00193 14.252C5.80267 14.252 5.61157 14.1728 5.47068 14.0319C5.32978 13.891 5.25063 13.6999 5.25063 13.5007C5.25063 13.3014 5.32978 13.1103 5.47068 12.9694L9.94005 8.50003L5.47005 4.03065C5.32915 3.88976 5.25 3.69866 5.25 3.4994C5.25 3.30015 5.32915 3.10905 5.47005 2.96815C5.61095 2.82726 5.80204 2.7481 6.0013 2.7481C6.20056 2.7481 6.39165 2.82726 6.53255 2.96815L6.53318 2.9694Z'
        fill={color}
      />
    </svg>
  );
};

const calIsSelectedItem = (selectedItem, startDateTime, inputTxt) => {
  if (!selectedItem) return false;
  const { start_datatime, input } = selectedItem;
  if (start_datatime === startDateTime && input === inputTxt) return true;
  return false;
};

export default function SearchCom({
  logData,
  selectedItem,
  handleSelectedItem,
}) {
  const [searchValue, setSearchValue] = useState('');
  const filterLogData = logData.filter((el) => {
    if (!el.input) return '';
    return el.input.includes(searchValue);
  });

  return (
    <div className={cx('search-cont')}>
      <div className={cx('search-input-cont')}>
        <InputText
          disableLeftIcon={false}
          customStyle={{ height: '40px' }}
          placeholder={'Input 내용'}
          onChange={(e) => setSearchValue(e.target.value)}
          value={searchValue}
        />
      </div>
      <ul className={cx('input-list')}>
        {filterLogData.map((el, idx) => {
          const isSelectedItem = calIsSelectedItem(
            selectedItem,
            el.start_datatime,
            el.input,
          );
          return (
            <li
              key={idx}
              className={cx('input-item', isSelectedItem && 'checked')}
              onClick={() => handleSelectedItem(el)}
            >
              <span>{el.input}</span>
              <RightIcon color={isSelectedItem ? '#2D76F8' : '#747474'} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
