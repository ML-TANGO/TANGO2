import info from '@src/static/images/icon/00-ic-gray-info.svg';
import React, { useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import classNames from 'classnames/bind';
import style from './InstanceInfo.module.scss';

const cx = classNames.bind(style);

const unit = {
  second: '초',
};

const InstanceInfo = ({
  name,
  type,
  cost,
  time_unit,
  cpu,
  gpu,
  ram,
  id,
  handleSelectedInstance,
  selectedInstance,
}) => {
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

  const isSelected = selectedInstance.some((instance) => instance.id === id);

  return (
    <div
      className={cx('container', isSelected && 'selected')}
      onClick={() => handleSelectedInstance(id)}
    >
      <div className={cx('left-content')}>
        <span className={cx('name')}>{name}</span>
        <img
          ref={iconRef}
          src={info}
          alt='info'
          onMouseEnter={() => showTooltip(true)}
          onMouseLeave={() => hideTooltip(false)}
        />
        <span className={cx('type')}>{type}</span>
      </div>
      {isSelected && (
        <div className={cx('right-content')}>
          <span>가격</span>
          <div className={cx('cost')}>
            <span>{cost.toLocaleString()}</span>
            <span>원</span>
            <span>/</span>
            <span>{unit[time_unit]}</span>
          </div>
        </div>
      )}

      <TooltipPortal
        direction='top'
        targetRef={iconRef}
        isShowTooltip={isVisible}
      >
        <DarkTooltip
          direction='top'
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
    </div>
  );
};

export default InstanceInfo;
