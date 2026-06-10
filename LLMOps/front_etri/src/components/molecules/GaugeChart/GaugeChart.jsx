// chart
import Chart from 'react-gauge-chart';

// CSS Module
import classNames from 'classnames/bind';
import style from './GaugeChart.module.scss';
const cx = classNames.bind(style);

function GaugeChart({ tagId, average }) {
  return (
    <Chart
      id={tagId}
      className={cx('chart')}
      nrOfLevels={100}
      arcsLength={[0.7, 0.2, 0.1]}
      colors={['#02e366', '#ffc500', '#fa4e57']}
      percent={average / 100}
      arcPadding={0.03}
      textColor='#121619'
      needleBaseColor='#3e3e3e'
      needleColor='#747474'
      marginInPercent={0.01}
      cornerRadius={4}
      fontSize='24px'
    />
  );
}

export default GaugeChart;
