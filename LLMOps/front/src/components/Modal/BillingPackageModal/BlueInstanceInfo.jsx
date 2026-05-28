import info from '@src/static/images/icon/00-ic-alert-info-o-blue.svg';
import React, { useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import classNames from 'classnames/bind';
import style from './BlueInstanceInfo.module.scss';

const cx = classNames.bind(style);

const unit = {
  second: '초',
};

const BlueInstanceInfo = ({ name, cost, time_unit, cpu, gpu, ram }) => {
  const iconRef = useRef(null);

  const [isVisible, setIsVisible] = useState(false);

  const showTooltip = () => {
    setIsVisible(true);
  };

  const hideTooltip = () => {
    setIsVisible(false);
  };

  const instanceDetail = [
    { type: 'vGPU', value: gpu, unit: 'EA' },
    { type: 'vCPU', value: cpu, unit: 'Cores' },
    { type: 'RAM', value: ram, unit: 'GB' },
  ];
  return (
    <span className={cx('container')}>
      <span className={cx('name')}>{name}</span>
      <img
        ref={iconRef}
        src={info}
        alt='info'
        onMouseEnter={() => showTooltip(true)}
        onMouseLeave={() => hideTooltip(false)}
        width={16}
        height={16}
      />
      <TooltipPortal
        direction='bottom'
        targetRef={iconRef}
        isShowTooltip={isVisible}
      >
        <DarkTooltip
          direction='bottom'
          tooltipColor='#C1C1C1'
          content={
            <div className={cx('tool-tip')}>
              <div className={cx('cost-box')}>
                <span className={cx('title')}>가격</span>
                <span>{cost}</span>
                <span>원 / {unit[time_unit]}</span>
              </div>
              <div className={cx('middle-line')}></div>
              {instanceDetail.map(({ type, value, unit }) => (
                <div className={cx('detail-info')} key={type}>
                  <span>{type}</span>
                  <span className={cx('value')}>{value}</span>
                  <span>{unit}</span>
                </div>
              ))}
            </div>
          }
        />
      </TooltipPortal>
    </span>
  );
};

export default BlueInstanceInfo;
