// Components
import { InputText } from '@jonathan/ui-react';

import { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
// i18n
import { useTranslation } from 'react-i18next';

import downIcon from './imgs/down.png';
// Icons
import upIcon from './imgs/up.png';

// CSS module
import classNames from 'classnames/bind';
import style from './TitleSelect.module.scss';

const cx = classNames.bind(style);

const TitleSelect = ({
  placeholder,
  options,
  selected,
  onChange,
  readOnly,
  searchable = false,
}) => {
  const { t } = useTranslation();

  // 상태 값 정의
  const [optionStatus, setOptionStatus] = useState(false);
  const [keyword, setKeyword] = useState('');

  // 셀렉트 박스 ref 정의
  const selectRef = useRef(null);

  const onSearch = (e) => {
    setKeyword(e.target.value);
  };

  // 화면 클릭 이벤트
  const handleClick = (e) => {
    if (
      selectRef.current &&
      !ReactDOM.findDOMNode(selectRef.current).contains(e.target)
    ) {
      setOptionStatus(false);
    }
  };

  // 옵션 드랍 다운 이벤트
  const dropDownHandler = () => {
    setOptionStatus(!optionStatus);
  };

  // 라이프 사이클 메서드 정의
  useEffect(() => {
    // 클릭 이벤트 바인드
    document.addEventListener('click', handleClick, false);
    return () => {
      // 컴포넌트 언마운트 시 이벤트리스너 삭제
      document.removeEventListener('click', handleClick, false);
    };
  }, []);
  return (
    <div className={cx('input-wrap', optionStatus && 'active')} ref={selectRef}>
      <label
        className={cx('label')}
        onClick={() => {
          if (!readOnly) dropDownHandler();
        }}
      >
        {selected ? (
          t(selected.label)
        ) : (
          <span className={cx('placeholder')}>{placeholder}</span>
        )}
        <i className={cx('icon')}>
          <img src={optionStatus ? upIcon : downIcon} alt='아이콘' />
        </i>
      </label>
      {optionStatus && (
        <div className={cx('select-options')}>
          {searchable && (
            <div className={cx('search-box')}>
              <InputText
                size='medium'
                value={keyword}
                placeholder={t(placeholder)}
                onChange={onSearch}
                leftIcon='/images/icon/ic-search.svg'
                disableLeftIcon={false}
                disableClearBtn={true}
              />
            </div>
          )}
          <ul className={cx('option-list')}>
            {options
              .filter((opt) => opt.label.indexOf(keyword) !== -1)
              .map((option, idx) => (
                <li key={idx}>
                  <button
                    key={idx}
                    className={cx('option', option.disabled && 'disabled')}
                    onClick={() => {
                      if (!readOnly && !option.disabled) {
                        dropDownHandler();
                        onChange(option);
                      }
                    }}
                  >
                    {option.label}
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
};
export default TitleSelect;
