import { InputNumber } from '@tango/ui-react';

import React, { useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import classNames from 'classnames/bind';
import style from './RangeBar.module.scss';

const cx = classNames.bind(style);

const originColor = 'rgba(45, 118, 248, 1)';
const changedColor = 'rgba(59, 171, 255, 1)';

const RangeBar = ({
  range,
  handleRangeBar,
  label,
  setting,
  unit,
  max,
  step,
}) => {
  const [leftBarColor, setLeftBarColor] = useState(originColor);

  const changeLeftBarColor = (color) => {
    setLeftBarColor(color);
  };

  const formatNumber = (value) => {
    return Number.isInteger(value) ? value : parseFloat(value).toFixed(3);
  };

  const inputRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  return (
    <div className={cx('container')}>
      <div className={cx('header')}>
        <span className={cx('resource')}>{label}</span>
        <div className={cx('count')}>
          <div
            ref={inputRef}
            onMouseEnter={() => setIsShowTooltip(true)}
            onMouseLeave={() => setIsShowTooltip(false)}
          >
            <InputNumber
              customSize={{
                maxWidth: '51px',
                minWidth: '32px',
                height: '28px',
                fontSize: '13px',
                fontFamily: 'SpoqaM',
                textAlign: 'center',
                color: '#747474',
                textOverflow: 'ellipsis',
              }}
              className={cx(`${range[setting] === 0 ? 'zero-num' : 'normal'}`)}
              value={formatNumber(range[setting])}
              onChange={(e) => handleRangeBar(setting, e.target.value, max)}
              min={0}
              max={max}
              placeholder={max}
              step={step}
              disableIcon
            />
          </div>
          {(formatNumber(range[setting]) + '').length > 4 && (
            <TooltipPortal
              direction='bottom'
              targetRef={inputRef}
              isShowTooltip={isShowTooltip}
            >
              <DarkTooltip
                direction='bottom'
                content={
                  <div
                    style={{
                      display: 'flex',
                      minWidth: '32px',
                      fontFamily: 'SpoqaM',
                      fontSize: '10px',
                      justifyContent: 'center',
                    }}
                  >
                    {formatNumber(range[setting])}
                  </div>
                }
              />
            </TooltipPortal>
          )}
          <span>{unit}</span>
        </div>
      </div>
      <div className={cx('range-input')}>
        <div className={cx('custom-bar')}>
          <div
            className={cx('left-bar')}
            style={{
              width: `${(range[setting] / max) * 100}%`,
              backgroundColor: leftBarColor,
            }}
          ></div>
          <div
            className={cx('right-bar')}
            style={{
              width: `${100 - (range[setting] / max) * 100}%`,
            }}
          ></div>
        </div>
        <input
          type='range'
          step={step}
          id={setting}
          min={0}
          max={max}
          value={range[setting]}
          onChange={(e) => handleRangeBar(setting, e.target.value)}
          onMouseOver={() => changeLeftBarColor(changedColor)}
          onMouseOut={() => changeLeftBarColor(originColor)}
          onMouseDown={() => changeLeftBarColor(changedColor)}
          onMouseUp={() => changeLeftBarColor(originColor)}
        />
        <div className={cx('percent-text')}>
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
};

export default RangeBar;
