import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import * as echarts from 'echarts';
import { useEffect, useRef } from 'react';

import classNames from 'classnames/bind';
import style from './BasicLineChart.module.scss';

const cx = classNames.bind(style);

const BasicLineChart = ({
  title,
  steps,
  values,
  stepsPerEpoch,
  checkpoints,
}) => {
  const chartRef = useRef(null);

  useEffect(() => {
    const chartInstance = echarts.init(chartRef.current);
    const minY = Math.min(...values);

    // ⑩ 체크포인트 점 마킹 (SP-5 / 3.8) — 저장된 ckpt step 을 수직 점선으로 표시.
    // 그래프 steps 는 다운샘플링되므로 각 ckpt 를 가장 가까운 category step 으로 매핑
    // (정확히 일치하는 category 가 없으면 markLine 이 안 그려지므로).
    const ckptMarks = [];
    if (
      Array.isArray(checkpoints) &&
      checkpoints.length &&
      Array.isArray(steps) &&
      steps.length
    ) {
      const seen = new Set();
      checkpoints.forEach((c) => {
        let nearest = steps[0];
        let best = Math.abs(Number(steps[0]) - Number(c));
        for (let i = 1; i < steps.length; i += 1) {
          const d = Math.abs(Number(steps[i]) - Number(c));
          if (d < best) {
            best = d;
            nearest = steps[i];
          }
        }
        if (!seen.has(nearest)) {
          seen.add(nearest);
          ckptMarks.push({ xAxis: nearest });
        }
      });
    }

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
          ...(ckptMarks.length
            ? {
                markLine: {
                  symbol: 'none',
                  silent: true,
                  lineStyle: { color: '#1aa260', type: 'dashed', width: 1 },
                  label: { show: false },
                  data: ckptMarks,
                },
              }
            : {}),
        },
      ],
    };

    chartInstance.setOption(options);

    return () => {
      chartInstance.dispose();
    };
  }, [title, steps, values, checkpoints]);

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>
        <div className={cx('name')}>{title}</div>
      </div>
      <div ref={chartRef} className={cx('graph')} />
      {/* 값을 모를 때(external 학습 초반·엔진이 아직 기록 전) 힌트 자체를 숨긴다 —
          예전엔 '1 Epoch =  steps'/'1 Epoch = 0 steps' 로 빈 라벨이 보였다. */}
      {stepsPerEpoch ? (
        <div className={cx('step')}>
          <img src={InfoIcon} alt='icon' />1 Epoch = {stepsPerEpoch} steps
        </div>
      ) : null}
    </div>
  );
};

export default BasicLineChart;
