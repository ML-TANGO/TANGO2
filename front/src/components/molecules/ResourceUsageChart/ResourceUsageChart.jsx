import { memo } from 'react';
// chart
import GaugeChart from '../GaugeChart';

// CSS Module
import classNames from 'classnames/bind';
import style from './ResourceUsageChart.module.scss';
const cx = classNames.bind(style);

function ResourceUsageChart({
  tagId,
  data = { min: 0, max: 0, average: 0 },
  size,
}) {
  const { min, max, average } = data;
  return (
    <div className={cx('chart')}>
      <GaugeChart tagId={tagId} average={average} />
      <div className={cx('text-box')}>
        {size && <div className={cx('size')}>{size}</div>}
        <div className={cx('min-max')}>
          <span
            className={cx(
              'min',
              min > 90 ? 'warning' : min > 70 ? 'caution' : '',
            )}
          >{`min ${parseFloat(min?.toFixed(2))}%`}</span>
          <span className={cx('divide')}>|</span>
          <span
            className={cx(
              'max',
              max > 90 ? 'warning' : max > 70 ? 'caution' : '',
            )}
          >{`max ${parseFloat(max?.toFixed(2))}%`}</span>
        </div>
      </div>
    </div>
  );
}

export default memo(ResourceUsageChart, (prev, next) => {
  const { min: prevMin, max: prevMax, average: prevAverage } = prev.data;
  const { min: nextMin, max: nextMax, average: nextAverage } = next.data;
  if (
    prevMin === nextMin &&
    prevMax === nextMax &&
    prevAverage === nextAverage
  ) {
    return true;
  }

  return false;
});
