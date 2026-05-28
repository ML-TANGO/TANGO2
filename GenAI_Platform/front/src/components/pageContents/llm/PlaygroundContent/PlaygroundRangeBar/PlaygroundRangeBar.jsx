import React, { useRef, useState } from 'react';

import { InputNumber } from '@jonathan/ui-react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import classNames from 'classnames/bind';
import style from './PlaygroundRangeBar.module.scss';

const cx = classNames.bind(style);

const PlaygroundRangeBar = React.memo(
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

    return (
      <div className={cx('scroll-cont')}>
        <div className={cx('scroll-header')}>
          <div className={cx('label-cont')}>
            <label htmlFor={`${label}-range`} className={cx('label-txt')}>
              {label}
            </label>
            {handleRefresh && (
              <button
                onClick={() => handleRefresh(label)}
                aria-label='초기화 버튼'
                disabled={disabled}
              >
                <img
                  className={cx('reset-img')}
                  src={'/src/static/images/icon/ic-refresh.svg'}
                  alt=''
                />
              </button>
            )}
            {tooltipContent && (
              <>
                <img
                  ref={tooltipRef}
                  src={'/src/static/images/icon/00-gray-tooltip-icon.svg'}
                  alt='tooltip-icon'
                  onMouseEnter={() => setIsShowTooltip(true)}
                  onMouseLeave={() => setIsShowTooltip(false)}
                  aria-label='Tooltip info'
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
          <InputNumber
            size='small'
            disableIcon
            customSize={{
              width: '64px',
              textAlign: 'center',
              padding: 0,
              color: '#c1c1c1',
            }}
            step={step}
            value={+value}
            onChange={(e) => onChange(e, label)}
            min={min}
            max={max}
            isReadOnly={disabled}
          />
        </div>
        <div className={cx('slider-cont')}>
          <input
            id={`${label}-range`}
            name={`${label}-range`}
            type='range'
            className={cx('slider', disabled && 'disabled')}
            min={min}
            max={max}
            step={step}
            value={value}
            disabled={disabled}
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

export default PlaygroundRangeBar;
