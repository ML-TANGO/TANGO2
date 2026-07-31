import { InputNumber } from '@tango/ui-react';

import React, { useRef, useState } from 'react';

import classNames from 'classnames/bind';
import style from './RangeBar.module.scss';

const cx = classNames.bind(style);
const originColor = 'rgba(45, 118, 248, 1)';
const changedColor = 'rgba(59, 171, 255, 1)';

function RangeBar({
  range,
  handleRangeBar,
  label,
  labelIcon,
  setting,
  unit,
  min = 0,
  max,
  step,
  bottomText = false,
  isDisabled = false,
}) {
  // range, label, input
  const [leftBarColor, setLeftBarColor] = useState(originColor);

  const formatNumber = (value) => {
    return Number.isInteger(value) ? value : parseFloat(value);
  };

  const changeLeftBarColor = (color) => {
    setLeftBarColor(color);
  };
  return (
    <div className={cx('container', isDisabled && 'disabled')}>
      <div className={cx('top')}>
        <div className={cx('title')}>
          {label}
          {labelIcon && (
            <img
              src={labelIcon}
              alt='label-icon'
              style={{ marginLeft: '8px' }}
            />
          )}
        </div>
        <InputNumber
          customSize={{
            maxWidth: '90px',
            minWidth: '48px',
            height: '28px',
            fontSize: '13px',
            fontFamily: 'SpoqaM',
            textAlign: 'center',
            color: '#747474',
            textOverflow: 'ellipsis',
          }}
          className={cx(`${range[setting] === 0 ? 'zero-num' : 'normal'}`)}
          value={formatNumber(range[setting])}
          onChange={(e) =>
            handleRangeBar({ setting, value: e.target.value, max })
          }
          min={min}
          max={max}
          placeholder={max}
          step={step}
          isDisabled={isDisabled}
          disableIcon
        />
      </div>
      <div className={cx('range-input', 'dis')}>
        <div className={cx('custom-bar')}>
          <div
            className={cx('left-bar')}
            style={{
              width: `${(range[setting] / max) * 100}%`,
              backgroundColor: isDisabled ? '#dbdbdb' : leftBarColor,
              opacity: isDisabled && '0.5',
            }}
          ></div>
          <div
            className={cx('right-bar')}
            style={{
              width: `${100 - (range[setting] / max) * 100}%`,
              backgroundColor: isDisabled && '#dbdbdb',
              borderColor: isDisabled && '#f9fafb',
              opacity: isDisabled && '0.5',
            }}
          ></div>
        </div>
        <input
          type='range'
          step={step}
          id={setting}
          min={0}
          max={max}
          disabled={isDisabled}
          value={range[setting]}
          onChange={(e) => handleRangeBar({ setting, value: e.target.value })}
          onMouseOver={() => changeLeftBarColor(changedColor)}
          onMouseOut={() => changeLeftBarColor(originColor)}
          onMouseDown={() => changeLeftBarColor(changedColor)}
          onMouseUp={() => changeLeftBarColor(originColor)}
        />
        {bottomText && (
          <div className={cx('bottom-text')}>
            <div>{min}</div>
            <div>{max}</div>
          </div>
        )}

        {/* <div className={cx('percent-text')}>
          <span>0%</span>
          <span>100%</span>
        </div> */}
      </div>
    </div>
  );
}

export default RangeBar;
