import { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, Checkbox, InputText } from '@jonathan/ui-react';

// Utils
import { arrayToTranslationString } from '@src/utils';

// CSS module
import style from './MultiCheckSelect.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function MultiCheckSelect({
  label,
  name,
  placeholder,
  sizeType, // large, small
  status = '', // value 유효성 상태 'success': 유효성 검증 완료, 'error': 유효성 검증 실패
  options: optionsData = [],
  selected,
  onSubmit,
  disabledErrorText = false,
  error,
  readOnly,
  optional,
  search,
  customStyle = { width: '240px' },
}) {
  const { t } = useTranslation();
  // 상태 값 정의
  const [optionStatus, setOptionStatus] = useState(false);
  const [disabledSubmit, setDisabledSubmit] = useState(false);
  const [options, setOptions] = useState(
    JSON.parse(JSON.stringify(optionsData)),
  );

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
  const dropDownHandler = useCallback(() => {
    setOptionStatus(!optionStatus);
  }, [setOptionStatus, optionStatus]);

  const onCheck = useCallback(
    (idx) => {
      const prevOptions = [...options];
      const { checked, value } = { ...options[idx] };
      if (value === 'all' && !checked) {
        const tmpOptions = [...options].map((opt) => ({
          ...opt,
          checked: true,
        }));
        setOptions(tmpOptions);
        onValidCheck(tmpOptions);
      } else if (value === 'all' && checked) {
        const tmpOptions = [...options].map((opt) => ({
          ...opt,
          checked: false,
        }));
        setOptions(tmpOptions);
        onValidCheck(tmpOptions);
      } else {
        prevOptions[idx].checked = !checked;
        let flag = true;
        for (let i = 0; i < prevOptions.length; i += 1) {
          const { value: val, checked: checkedItem } = prevOptions[i];
          if (val !== 'all' && !checkedItem) {
            flag = false;
            break;
          }
        }
        for (let i = 0; i < prevOptions.length; i += 1) {
          const { value: val } = prevOptions[i];
          if (val === 'all') prevOptions[i].checked = flag;
        }
        setOptions(prevOptions);
        onValidCheck(prevOptions);
      }
    },
    [options, setOptions],
  );

  /**
   * 선택된게 없을 때 confirm 버튼 비활성화
   */
  const onValidCheck = (options) => {
    if (options.filter(({ checked }) => checked).length === 0) {
      setDisabledSubmit(true);
    } else {
      setDisabledSubmit(false);
    }
  };

  const catchOnSubmit = useCallback(() => {
    onSubmit(options);
  }, [options, onSubmit]);

  // 라이프 사이클 메서드 정의
  useEffect(() => {
    // 클릭 이벤트 바인드
    document.addEventListener('click', handleClick, false);
    return () => {
      // 컴포넌트 언마운트 시 이벤트리스너 삭제
      document.removeEventListener('click', handleClick, false);
    };
  }, []);

  useEffect(() => {
    setOptions(JSON.parse(JSON.stringify(optionsData)));
  }, [optionStatus, optionsData, setOptions]);
  return (
    <div className={cx('input-wrap')} style={customStyle}>
      {label && (
        <label className={cx('label')}>
          {t(label)}
          {optional && (
            <span className={cx('optional')}>- {t('optional.label')}</span>
          )}
        </label>
      )}
      <div
        ref={selectRef}
        className={cx(
          'fb',
          'select',
          readOnly && 'read-only',
          sizeType && sizeType,
        )}
      >
        <div
          className={cx(
            'select-controller',
            optionStatus && 'active',
            status,
            selected && 'success',
          )}
        >
          <label>
            <input
              type='text'
              className={cx('input-item')}
              onFocus={() => {
                if (!readOnly) dropDownHandler();
              }}
              value={selected ? (t ? t(selected.label) : selected.label) : ''}
              onChange={() => {}}
              placeholder={!selected ? t(placeholder) : ''}
              readOnly={readOnly}
            />
          </label>
          <i className={cx('icon')}>
            <img src='/images/icon/filter.svg' alt='아이콘' />
          </i>
        </div>
        {optionStatus && (
          <div className={cx('popup')}>
            <div className={cx('select-options')}>
              {search && (
                <div className={cx('search-box')}>
                  <InputText
                    size='small'
                    placeholder={t('search.placeholder')}
                    value={keyword}
                    onChange={onSearch}
                    leftIcon='/images/icon/ic-search.svg'
                    disableLeftIcon={false}
                    disableClearBtn={true}
                  />
                </div>
              )}
              <ul className={cx('option-list')}>
                {options.map((option, idx) => {
                  const value = arrayToTranslationString(option.label, t);
                  return value.indexOf(keyword) !== -1 ? (
                    <li className={cx('option')} key={idx}>
                      <Checkbox
                        name={name}
                        customStyle={{
                          margin: '10px 0 10px 12px',
                        }}
                        customLabelStyle={{ paddingBottom: '1px' }}
                        checked={option.checked}
                        disabled={option.disabled}
                        onChange={() => {
                          onCheck(idx);
                        }}
                        value={option.value}
                        label={value}
                      />
                    </li>
                  ) : null;
                })}
              </ul>
            </div>
            <div className={cx('popup-footer')}>
              <Button
                onClick={() => {
                  dropDownHandler();
                }}
                type='none-border'
                size='small'
                customStyle={{ marginRight: '8px' }}
                // disabled={readOnly}
              >
                {t('cancel.label')}
              </Button>
              <Button
                onClick={() => {
                  catchOnSubmit();
                  dropDownHandler();
                }}
                type='primary'
                size='small'
                disabled={disabledSubmit}
              >
                {t('confirm.label')}
              </Button>
            </div>
          </div>
        )}
      </div>
      {!disabledErrorText && (
        <span className={cx('error')}>{error && t(error)}</span>
      )}
    </div>
  );
}

export default MultiCheckSelect;
