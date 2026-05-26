import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

import Spinner from '@src/components/atoms/Spinner';

import classNames from 'classnames/bind';
import style from './DoubleDropdown.module.scss';

import DropdownArrowIcon from '@src/static/images/icon/00-ic-basic-arrow-04-down.svg';
import SearchIcon from '@src/static/images/icon/ic-search.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';

const cx = classNames.bind(style);

const filterByKeyword = (dataArray, keyword) => {
  if (dataArray.length === 0) return [];
  return dataArray.filter((item) => item.name.includes(keyword));
};

const DoubleDropdown = ({
  isFetching = false,
  icon = IconSmile,
  isOpen,
  handleIsOpen,
  label,
  placeholder,
  options,
  value,
  handleSelected,
  visibilityLabel,
  visiblityList,
  visibilityValue,
  handleVisibility,
  outerStyle,
  innerStyle,
}) => {
  const { t } = useTranslation();

  const [searchValue, setSearchValue] = useState('');
  const filterList = filterByKeyword(options, searchValue);

  return (
    <div className={cx('dropdown-outer-cont')}>
      <div
        className={cx('dropdown-cont', isOpen && 'open')}
        onClick={() => handleIsOpen(!isOpen)}
        style={outerStyle}
      >
        <span className={cx('label')}>{label}</span>
        <span className={cx('selected-item', value.id && 'selected')}>
          {value.name ?? placeholder}
        </span>
        <img
          className={cx('arrow-img', isOpen && 'reverse')}
          src={DropdownArrowIcon}
          alt='dropdown-arrow-icon'
        />
      </div>
      {isOpen && (
        <div className={cx('open-cont')} style={innerStyle}>
          <div className={cx('search-cont')}>
            <div className={cx('input-cont')}>
              <InputText
                leftIcon={SearchIcon}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                customStyle={{ height: '32px' }}
              />
            </div>
            {visiblityList.length > 0 && (
              <div className={cx('toggle-cont')}>
                <span className={cx('label')}>{visibilityLabel}</span>
                <div className={cx('toggle')}>
                  {visiblityList.map((el) => {
                    return (
                      <div
                        key={el.value}
                        className={cx(
                          'item',
                          visibilityValue.value === el.value && 'selected',
                        )}
                        onClick={() => handleVisibility(el)}
                      >
                        {el.label}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          <ul className={cx('list-cont')}>
            {isFetching && (
              <div className={cx('nodata')}>
                <Spinner />
              </div>
            )}
            {!isFetching &&
              filterList.map((el) => {
                return (
                  <li
                    className={cx(
                      'item-cont',
                      value.id === el.id && 'selected',
                    )}
                    key={el.id}
                    onClick={() => handleSelected(el)}
                  >
                    <div className={cx('flex-cont')}>
                      <img className={cx('icon')} src={icon} alt='icon' />
                      <span className={cx('item-name-txt')}>{el.name}</span>
                    </div>
                    <span className={cx('scope-txt')}>{el.owner}</span>
                  </li>
                );
              })}
            {!isFetching && filterList.length === 0 && (
              <div className={cx('no-data')}>
                <span>{t('noData.message')}</span>
              </div>
            )}
          </ul>
        </div>
      )}
    </div>
  );
};

export default DoubleDropdown;
