import { useEffect, useState, useRef, useCallback } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Icons
import upIcon from './imgs/up.png';
import downIcon from './imgs/down.png';
import checkIconGray from '@src/static/images/icon/00-ic-basic-check-gray.svg';
import checkIconBlue from '@src/static/images/icon/00-ic-basic-check-blue.svg';

// Components
import { Tooltip } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './SearchSelect.module.scss';
const cx = classNames.bind(style);

const SearchSelect = ({
  label,
  selected,
  onSelect,
  placeholder = '',
  readOnly,
  options = [],
  status,
  isLowercase,
  disabledErrorText = false,
  error,
  t,
  iconAlign = 'LEFT',
  checkBox = false,
  customStyle,
}) => {
  const [optionOpen, setOptionOpen] = useState(false);
  const [keyword, setKeyword] = useState('');
  const inputRef = useRef(null);
  const selectedRef = useRef(null);
  const [checkVisible, setCheckVisible] = useState(false);
  const handleClick = useCallback((e) => {
    if (e.target !== selectedRef.current && e.target !== inputRef.current) {
      setOptionOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dropDownHandler = useCallback(() => {
    if (!readOnly) setOptionOpen(!optionOpen);
  }, [optionOpen, readOnly]);

  const onSearch = useCallback((e) => {
    setKeyword(e.target.value);
  }, []);

  useEffect(() => {
    document.addEventListener('click', handleClick, false);

    return () => {
      document.removeEventListener('click', handleClick, false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (checkBox) {
      if (optionOpen) {
        setCheckVisible(false);
      } else {
        setCheckVisible(true);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optionOpen]);

  return (
    <div className={cx('fb', 'input', 'input-wrap')} style={customStyle}>
      {label && <label className={cx('fb', 'label')}>{t(label)}</label>}
      <div className={cx('search-select', readOnly && 'read-only')}>
        <div
          className={cx(
            'fb',
            'input',
            'input-wrap',
            optionOpen ? 'success' : status,
          )}
        >
          <div className={cx('input-wrap', 'search-input-box')}>
            <i className={cx('icon')}>
              <img src={optionOpen ? upIcon : downIcon} alt='아이콘' />
            </i>
            <div
              className={cx('selected', checkVisible && 'div-check-box')}
              onClick={() => {
                inputRef.current.focus();
              }}
              ref={selectedRef}
            >
              {selected && !optionOpen ? selected.label : ''}
            </div>
            {checkVisible && (
              <img
                className={cx('input-check-icon')}
                src={
                  status !== 'error' && selected ? checkIconBlue : checkIconGray
                }
                alt='icon'
              />
            )}
            {placeholder === 'noMatchFile.message' && !selected?.label && (
              <span
                className={cx(
                  'tooltip-box',
                  t('noMatchFileDetail.message').length > 50 && 'tooltip-eng',
                )}
              >
                <Tooltip contents={t('noMatchFileDetail.message')}>
                  <img
                    src='/images/icon/00-ic-alert-warning-yellow.svg'
                    alt='warning'
                  />
                </Tooltip>
              </span>
            )}
            <input
              className={cx(
                'input-box',
                checkVisible && 'check-box',
                isLowercase && 'lowercase',
              )}
              type='text'
              placeholder={!optionOpen && !selected ? t(placeholder) : ''}
              onFocus={dropDownHandler}
              onChange={onSearch}
              value={optionOpen ? keyword : ''}
              readOnly={readOnly}
              ref={inputRef}
            />
          </div>
          {!disabledErrorText && (
            <span className={cx('error')}>{error && t(error)}</span>
          )}
        </div>
        {optionOpen && (
          <ul className={cx('select-options')}>
            {options
              .filter(
                ({ label: labelItem }) => labelItem.indexOf(keyword) !== -1,
              )
              .map((option, idx) => {
                return (
                  <li
                    key={idx}
                    className={cx(
                      'option',
                      option.disabled && 'disabled',
                      checkVisible && 'check-box',
                    )}
                    onClick={() => {
                      if (!readOnly && !option.disabled) {
                        // if (!readOnly) {
                        dropDownHandler();
                        onSelect(option);
                      }
                    }}
                  >
                    {iconAlign && iconAlign === 'RIGHT' ? (
                      <>
                        {option.label}
                        <span className={cx('icon-right')}>
                          {option.Icon && <option.Icon />}
                          {option.StatusIcon && <option.StatusIcon />}
                        </span>
                      </>
                    ) : (
                      <>
                        {option.Icon && <option.Icon />}
                        {option.StatusIcon && <option.StatusIcon />}
                        {option.label}
                      </>
                    )}
                  </li>
                );
              })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default withTranslation()(SearchSelect);
