import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import * as echarts from 'echarts';
import { useEffect, useRef } from 'react';

import classNames from 'classnames/bind';
import style from './BasicLineChart.module.scss';

const cx = classNames.bind(style);

const BasicLineChart = ({ title, steps, values, stepsPerEpoch }) => {
  const chartRef = useRef(null);

  useEffect(() => {
    const chartInstance = echarts.init(chartRef.current);
    const minY = Math.min(...values);
    // const minY = Math.max(Math.min(...values) - 0.1, 0);
    const options = {
      // title: { text: title },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: steps },
      yAxis: {
        type: 'value',
        min: minY,
        axisLabel: {
          formatter: (value) => value.toFixed(2), // 소수점 두 자리로 제한
        },
      },
      grid: {
        top: 24,
        right: 24,
        bottom: 24,
        left: 24,
        containLabel: true,
      },
      series: [
        {
          type: 'line',
          data: values,
          smooth: true,
          lineStyle: { width: 2 },
          itemStyle: { color: '#002f77' },
        },
      ],
    };

    chartInstance.setOption(options);

    return () => {
      chartInstance.dispose();
    };
  }, [title, steps, values]);

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>
        <div className={cx('name')}>{title}</div>
      </div>
      <div ref={chartRef} className={cx('graph')} />
      <div className={cx('step')}>
        <img src={InfoIcon} alt='icon' />1 Epoch = {stepsPerEpoch} steps
      </div>
    </div>
  );
};

export default BasicLineChart;
