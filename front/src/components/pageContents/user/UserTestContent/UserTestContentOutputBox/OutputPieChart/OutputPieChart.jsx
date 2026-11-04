import PieChart from '@src/components/molecules/chart/PieChart';

import classNames from 'classnames/bind';
import style from './OutputPieChart.module.scss';
const cx = classNames.bind(style);

const OutputPieChart = ({ idx, output }) => {
  return (
    <div className={cx('result-chart')}>
      <label className={cx('title')}>{Object.keys(output)}</label>
      <PieChart
        tagId={`${'piechart'}_${idx}`}
        data={output[Object.keys(output)[0]]}
        customStyle={{
          width: '760px',
          minWidth: '420px',
          height: '370px',
        }}
      />
    </div>
  );
};

export default OutputPieChart;
