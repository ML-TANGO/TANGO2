import { InputNumber, InputText } from '@tango/ui-react';

import tooltipIcon from '@images/icon/00-gray-tooltip-icon.svg';
import RefreshIcon from '@images/icon/ic-refresh.svg';
import React, { useEffect, useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

// CSS Module
import classNames from 'classnames/bind';
import style from './ModelRangeBar.module.scss';

const cx = classNames.bind(style);

const ModelRangeBar = React.memo(
  ({
    label,
    value = 0,
    min = 0,
    max = 100,
    step = 1,
    tooltipContent,
    onChange,
    disabled,
    handleRefresh,
  }) => {
    const tooltipRef = useRef(null);
    const [isShowTooltip, setIsShowTooltip] = useState(false);
    const [tempValue, setTempValue] = useState(String(value)); // InputNumber용 임시 값

    const handleBlur = () => {
      const numericValue = parseFloat(tempValue);

      // 숫자로 변환 가능한 경우 검증
      if (!isNaN(numericValue)) {
        const clampedValue = Math.min(Math.max(numericValue, min), max);
        setTempValue(clampedValue.toString()); // 검증된 숫자를 문자열로 저장
        if (clampedValue !== value) {
          onChange({ target: { value: clampedValue } }, label); // 상위 전달
        }
      } else {
        // 숫자가 아니면 초기 값으로 복원
        setTempValue(value.toString());
      }
    };

    useEffect(() => {
      setTempValue(value.toString()); // 외부 value 변경 시 tempValue 동기화
    }, [value]);

    return (
      <div className={cx('scroll-cont')}>
        <div className={cx('scroll-header')}>
          <div className={cx('label-cont')}>
            <span className={cx('label-txt')}>{label}</span>
            {handleRefresh && (
              <img
                className={cx('reset-img')}
                src={RefreshIcon}
                alt='refresh-icon'
                onClick={() => handleRefresh(label)}
              />
            )}
            {tooltipContent && (
              <>
                <img
                  ref={tooltipRef}
                  src={tooltipIcon}
                  alt='tooltip-icon'
                  onMouseEnter={() => setIsShowTooltip(true)}
                  onMouseLeave={() => setIsShowTooltip(false)}
                />
                <TooltipPortal
                  direction='bottom'
                  targetRef={tooltipRef}
                  isShowTooltip={isShowTooltip}
                >
                  <DarkTooltip
                    direction='bottom'
                    tooltipColor='#c1c1c1'
                    content={
                      <div
                        style={{
                          display: 'flex',
                          minWidth: '32px',
                          fontFamily: 'SpoqaM',
                          fontSize: '10px',
                          justifyContent: 'center',
                          color: '#fff',
                        }}
                      >
                        {tooltipContent}
                      </div>
                    }
                  />
                </TooltipPortal>
              </>
            )}
          </div>
          <InputText
            size='small'
            disableIcon
            customStyle={{
              width: '64px',
              textAlign: 'center',
              padding: 0,
              color: '#c1c1c1',
            }}
            step={step}
            value={tempValue}
            min={undefined} // min/max 제한 제거 (실제 제한은 handleBlur에서 수행)
            max={undefined}
            onChange={(e) => setTempValue(e.target.value)} // 입력 중에는 tempValue 업데이트
            onBlur={handleBlur}
            isReadOnly={disabled}
          />
        </div>
        <div className={cx('slider-cont')}>
          <input
            className={cx('slider', disabled && 'disabled')}
            type='range'
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(e, label)}
          />
        </div>
        <div className={cx('minmax-cont')}>
          <span>{min}</span>
          <span>{max}</span>
        </div>
      </div>
    );
  },
);

export default ModelRangeBar;
