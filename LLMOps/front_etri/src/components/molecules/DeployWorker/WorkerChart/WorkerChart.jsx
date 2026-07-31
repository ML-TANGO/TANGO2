// i18n
import { useTranslation } from 'react-i18next';

// import DeployLineChart from '@src/components/molecules/DeployChart/DeployLineChart';
import Chart from 'react-apexcharts';
import { WorkerChartDataChange } from './WorkerChartDataChange';

// CSS Module
import classNames from 'classnames/bind';
import style from './WorkerChart.module.scss';
const cx = classNames.bind(style);

function WorkerChart({ data, selectedGraph }) {
  const { t } = useTranslation();
  const reconcData = WorkerChartDataChange(data, selectedGraph, t);

  return (
    <div className={cx('chart-area')}>
      <div>
        {reconcData && reconcData.options && reconcData.series && (
          <Chart
            options={reconcData.options}
            series={reconcData.series}
            type='line'
            height={456}
          />
        )}
      </div>
    </div>
  );
}

export default WorkerChart;
