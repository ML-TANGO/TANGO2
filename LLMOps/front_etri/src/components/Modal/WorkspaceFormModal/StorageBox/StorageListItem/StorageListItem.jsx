import { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Atom
import { InputNumber } from '@tango/ui-react';

// Components
import { Checkbox } from '@tango/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './StorageListItem.module.scss';
const cx = classNames.bind(style);

function StorageListItem({
  idx,
  model,
  total = 0,
  selected,
  free = 0,
  // onChange,
  // gpuDetailSelectedOptions = [],
  checkboxHandler,
  onChangeInputValue,
  type,
}) {
  const { t } = useTranslation();

  return (
    <li key={idx}>
      <div className={cx('list-item')}>
        <div className={cx('check')}>
          <Checkbox
            value={idx}
            label={model}
            customLabelStyle={{
              padding: '0 0 0 3px',
              fontSize: '14px',
            }}
            name='gpuModel'
            checked={selected}
            onChange={() => {
              checkboxHandler({ idx, type });
              //  onChange('gpu', idx);
              // onChange('gpu', idx);
            }}
          />
        </div>
        {/* <div>{t('ea.label', { count: total })}</div> */}
        <div>{total}</div>
        <div>{total}</div>
        {/* <div>{t('ea.label', { count: free })}</div> */}
        {/* <ArrowButton
            isUp={!showServerList}
            color='blue'
            onClick={() => {
              setShowServerList(!showServerList);
            }}
          >
            <span className={cx('server-selected')}>
              <span>{t('selected.label')}</span>
              <span className={cx('fixed')}>
                ({selectedCount}/{records?.length})
              </span>
            </span>
          </ArrowButton> */}
        <InputNumber
          name='workspaceInput'
          placeholder={`${t('currentAvailableCount')} : ${free}`}
          min={1}
          max={free}
          // customSize={{ marginLeft: '8px', width: '9rem' }}
          onChange={(e) => {
            let inputValue = e.value;
            if (e.value > free) {
              inputValue = free;
            }
            // ? inputValue
            onChangeInputValue({
              idx,
              type,
              value: inputValue,
            });
          }}
          // disableIcon={true}
          // bottomTextExist={true}
        />
      </div>
    </li>
  );
}

export default StorageListItem;
