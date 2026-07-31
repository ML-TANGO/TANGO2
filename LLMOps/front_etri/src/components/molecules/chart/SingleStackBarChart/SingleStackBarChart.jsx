import { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

// d3 chart
import Chart from '@src/d3chart/singleStackBarChart';

// CSS module
import classNames from 'classnames/bind';
import style from './SingleStackBarChart.module.scss';
const cx = classNames.bind(style);

let chart;
/**
 * 단일 막대그래프 컴포넌트
 * @param {{data: [{ label: string, value: number, color: string }]}} data 차트 렌더링을 위한 데이터
 * @component
 * @example
 *  const data = [ { label: 'a', value: 2, color: '#f00' }, { label: 'b', value: 2 } ];
 *  return (
 *    <SingleStackBarChart data={data} />
 *  )
 *
 *
 * ----
 */
function SingleStackBarChart({ data }) {
  const chartRef = useRef();

  useEffect(() => {
    if (!chart) {
      chart = new Chart(chartRef.current, data);
    } else {
      chart.updateData(data);
    }
  }, [data]);

  useEffect(() => {
    return () => {
      chart = undefined;
    };
  }, []);

  return <div className={cx('chart')} ref={chartRef}></div>;
}

SingleStackBarChart.propTypes = {
  data: PropTypes.array.isRequired,
};

export default SingleStackBarChart;
