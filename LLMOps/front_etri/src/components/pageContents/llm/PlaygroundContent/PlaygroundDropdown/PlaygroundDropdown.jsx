import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@tango/ui-react';

import Spinner from '@src/components/atoms/Spinner';

import classNames from 'classnames/bind';
import style from './PlaygroundDropdown.module.scss';

import DropdownArrowIcon from '@src/static/images/icon/00-ic-basic-arrow-04-down.svg';
import SearchIcon from '@src/static/images/icon/ic-search.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';

const cx = classNames.bind(style);

// 특정 단어가 포함된 결과만 필터링하는 함수
const filterByKeyword = (dataArray, keyword) => {
  if (dataArray.length === 0) return [];
  return dataArray.filter((item) => item.name.includes(keyword));
};

const PlaygroundDropdown = ({
  isFetching = false,
  label = '모델',
  icon = IconSmile,
  placeholder = '사용하실 모델을 선택해 주세요.',
  options = [],
  value,
  handleSelected = () => {},
  visibilityLabel,
  visiblityList = [],
  visibilityValue,
  handleVisibility = () => {},
  ...rest
}) => {
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  const filterList = filterByKeyword(options, searchValue);

  return (
    <div className={cx('dropdown-outer-cont')} {...rest}>
      <div
        className={cx('dropdown-cont', isOpen && 'open')}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <span className={cx('label')}>{label}</span>
        <span className={cx('selected-item', value.id && 'selected')}>
          {value.name ?? placeholder}
        </span>
        <img
          className={cx('arrow-img')}
          src={DropdownArrowIcon}
          alt='dropdown-arrow-icon'
        />
      </div>
      {isOpen && (
        <div className={cx('open-cont')}>
          <div className={cx('search-cont')}>
            <div className={cx('input-cont')}>
              <InputText
                value={searchValue}
                leftIcon={SearchIcon}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                onChange={(e) => {
                  setSearchValue(e.target.value);
                }}
                customStyle={{ height: '32px' }}
              />
            </div>
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
          </div>
          <ul className={cx('list-cont')}>
            {isFetching && (
              <div className={cx('spinner')}>
                <Spinner />
              </div>
            )}
            {filterList.map((el) => {
              return (
                <li
                  className={cx(
                    'item-cont',
                    value.id === el.id && 'selected',
                    el?.disabled && 'disabled',
                  )}
                  key={el.id}
                  onClick={() => {
                    if (el?.disabled) return;
                    handleSelected(el);
                  }}
                >
                  <img
                    className={cx('icon', el?.disabled && 'disabled')}
                    src={icon}
                    alt='smile-icon'
                  />
                  <span
                    className={cx('item-name-txt', el?.disabled && 'disabled')}
                  >
                    {el.name}
                  </span>
                  <span className={cx('scope-txt')}>{el.backname}</span>
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

export default PlaygroundDropdown;
