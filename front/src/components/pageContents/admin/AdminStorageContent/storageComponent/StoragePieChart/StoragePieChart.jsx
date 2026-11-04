import React from 'react';

import CircleGauge from '@src/components/molecules/CircleGauge';

import classNames from 'classnames/bind';
import style from './StoragePieChart.module.scss';

const cx = classNames.bind(style);

const StoragePieChart = React.memo(
  ({
    title,
    percentage,
    labelList = [],
    handleClickCount = () => {},
    ...rest
  }) => {
    return (
      <div className={cx('node-pie-chart')} {...rest}>
        <p className={cx('title')} onClick={handleClickCount}>
          {title}
        </p>
        <div className={cx('content-cont')}>
          <div className={cx('chart-cont')}>
            <CircleGauge percentage={percentage} />
            <div className={cx('percent-txt')}>{percentage}%</div>
          </div>
          <div className={cx('label-cont')}>
            {labelList &&
              labelList.map((labelInfo, idx) => {
                return (
                  <div className={cx('row')} key={idx}>
                    <span className={cx('label')}>{labelInfo.label}</span>
                    <span className={cx('value')}>{labelInfo.value}</span>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    );
  },
);

export default StoragePieChart;
