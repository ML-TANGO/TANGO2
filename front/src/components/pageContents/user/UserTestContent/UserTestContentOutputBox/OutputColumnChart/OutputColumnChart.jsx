import ColumnChart from '@src/components/molecules/chart/ColumnChart';

import classNames from 'classnames/bind';
import style from './OutputColumnChart.module.scss';
const cx = classNames.bind(style);

const OutputColumnChart = ({ idx, output }) => {
  return (
    <div className={cx('result-chart')}>
      <label className={cx('title')}>{Object.keys(output)}</label>
      <ColumnChart
        tagId={`${'columnchart'}_${idx}`}
        data={output[Object.keys(output)[0]]}
        customStyle={{
          width: '100%',
          minWidth: '420px',
          height: '420px',
        }}
      />
    </div>
  );
};

export default OutputColumnChart;
