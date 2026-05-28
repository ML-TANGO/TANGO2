import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './PublicApiSelect.module.scss';

const cx = classNames.bind(style);

// 특정 단어가 포함된 결과만 필터링하는 함수
const filterByKeyword = (dataArray, keyword) => {
  if (dataArray.length === 0) return [];
  return dataArray.filter((item) => item.name.includes(keyword));
};

const calValueNameList = (valueList) => {
  if (valueList.length === 0) return [];
  const shallowList = valueList.slice();
  const nameList = shallowList.map((el) => el.name);
  return nameList;
};

const calValueText = (valueList, placeholder) => {
  const nameList = calValueNameList(valueList);
  if (nameList.length === 0) return placeholder;

  const joinList = nameList.join(', ');
  return joinList;
};

export default function PublicApiSelect({
  label = '데이터',
  placeholder = '사용하실 데이터를 선택하세요.',
  valueList = [],
  options = [],
  handleSelected,
  ...rest
}) {
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  const filterList = filterByKeyword(options, searchValue);
  const valueNameList = calValueNameList(valueList);
  const valueTextList = calValueText(valueList, placeholder);

  return (
    <div className={cx('cont')}>
      <h2 className={cx('title')}>공공 API 데이터 목록</h2>
      <div className={cx('dropdown-outer-cont')} {...rest}>
        <div
          className={cx('dropdown-cont', isOpen && 'open')}
          onClick={() => setIsOpen((prev) => !prev)}
        >
          <span className={cx('label')}>{label}</span>
          <span
            className={cx('selected-item', valueList.length > 0 && 'selected')}
          >
            {valueTextList}
          </span>
          <img
            className={cx('arrow-img')}
            src={'/src/static/images/icon/00-ic-basic-arrow-04-down.svg'}
            alt='dropdown-arrow-icon'
          />
        </div>
        {isOpen && (
          <div className={cx('open-cont')}>
            <div className={cx('search-cont')}>
              <div className={cx('input-cont')}>
                <InputText
                  leftIcon={'/src/static/images/icon/ic-search.svg'}
                  disableLeftIcon={false}
                  value={searchValue}
                  placeholder={t('name.label')}
                  onChange={(e) => setSearchValue(e.target.value)}
                  customStyle={{ height: '32px' }}
                />
              </div>
            </div>
            <ul className={cx('list-cont')}>
              {filterList.map((el) => {
                return (
                  <li
                    className={cx(
                      'item-cont',
                      valueNameList.includes(el.name) && 'selected',
                    )}
                    key={el.id}
                    onClick={() => handleSelected(el)}
                  >
                    <img
                      className={cx('icon')}
                      src={'/src/static/images/icon/fold-file-icon.svg'}
                      alt='file-icon'
                    />
                    <span className={cx('item-name-txt')}>{el.name}</span>
                    <span className={cx('scope-txt')}>{el.backname}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
