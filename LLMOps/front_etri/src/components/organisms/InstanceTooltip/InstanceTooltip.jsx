// import { Tooltip } from '@tango/ui-react';

import Tooltip from '@src/components/atoms/Tooltip';

import classNames from 'classnames/bind';
import style from './InstanceTooltip.module.scss';

const cx = classNames.bind(style);

const calDefaultToZero = (num) => {
  if ([undefined, null, ''].includes(num)) return 0;
  return num;
};

const calVgpu = (instanceType, gpuName, tooltipGpuAllocate) => {
  if (instanceType === 'CPU') return '-';
  return `${gpuName} x ${calDefaultToZero(tooltipGpuAllocate)}EA`;
};

const InstanceTooltip = ({
  title = 'Instance Spec',
  instanceType,
  gpuName,
  gpuAllocateNum,
  cpuAllocateNum,
  ramAllocateNum,
  contentAlign,
  contentsCustomStyle = { minWidth: '120px' },
  iconCustomStyle = {},
}) => {
  const vGpu = calVgpu(instanceType, gpuName, gpuAllocateNum);
  const vCpu = `${calDefaultToZero(cpuAllocateNum)} cores`;
  const vRam = `${calDefaultToZero(ramAllocateNum)} GB`;

  return (
    <div
      style={{
        position: 'relative',
        zIndex: 1000,
        display: 'inline-block',
      }}
    >
      <Tooltip
        contents={
          <div className={cx('tooltip-wrapper')}>
            <div className={cx('header')}>
              <label>{title}</label>
            </div>
            <div className={cx('item')}>
              <span>vGPU: </span>
              <span>{vGpu}</span>
            </div>
            <div className={cx('item')}>
              <span>vCPU: </span>
              <span>{vCpu}</span>
            </div>
            <div className={cx('item')}>
              <span>RAM: </span>
              <span>{vRam}</span>
            </div>
          </div>
        }
        iconCustomStyle={{
          width: '20px',
          height: '20px',
          marginLeft: '4px',
          verticalAlign: 'text-top',
          ...iconCustomStyle,
        }}
        contentsAlign={contentAlign}
        contentsCustomStyle={{
          ...contentsCustomStyle,
          border: '0.5px solid #DEE9FF',
          borderRadius: '10px',
          boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
          padding: '20px 24px',
        }}
      />
    </div>
  );
};

export default InstanceTooltip;
