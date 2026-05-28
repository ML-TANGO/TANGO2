import { memo } from 'react';
import _ from 'lodash';

// i18n
import { useTranslation } from 'react-i18next';

import { CanvasLineChart } from '@jonathan/ui-react';
import { reorganization } from './ChartDataChange';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeployDashboardHistoryChart.module.scss';
const cx = classNames.bind(style);

/**
 * @param {{
 * 90_processing_time: 0
 * 90_response_time: number,
 * 95_processing_time: number,
 * 95_response_time: number,
 * 99_processing_time: number,
 * 99_response_time: number,
 * average_cpu_usage_on_pod: number,
 * average_mem_usage_per: number,
 * average_processing_time: number,
 * average_response_time: number,
 * error_count: number,
 * error_rate: number,
 * gpu_resource: {},
 * max_processing_time: number,
 * max_response_time: number,
 * median_processing_time: number,
 * median_response_time: number,
 * min_processing_time: number,
 * min_response_time: number,
 * monitor_count: number,
 * monitor_error_count: number,
 * monitor_error_rate: number,
 * nginx_count: number,
 * nginx_error_count: number,
 * nginx_error_rate: number,
 * success_count: number,
 * time: number,
 * time_local: number,
 * worker_count: number,
 * }[]} data
 * @param {{
 *  abProcess: boolean,
 *  callCnt: boolean,
 *  cpu: boolean,
 *  gpuCore: boolean,
 *  gpuMem: boolean,
 *  processTime: boolean,
 *  ram: boolean,
 *  response: boolean,
 *  type: 'CPU' | 'RAM' | 'GPU Core' | 'GPU MEM' | 'Call Count' | 'Abnormal Process' | 'Process Time' | 'Response Time',
 *  worker: boolean | undefined,
 * }} selectedGraph
 * @param {{
 *  value: number,
 *  selected: string,
 * }} selectedGraphPer
 * 0: '중앙값', '1': 99번째 백분위, '2': 95번째 백분위, '3': 90번째 백분위 '4': 평균
 * @param {string} selectedAbnormal
 * @param {{
 *  nginx: true,
 *  api: true,
 * }} abnormalCheckOption
 */
function DeployDashboardHistoryChart({
  data = [],
  selectedGraph,
  selectedGraphPer,
  selectedAbnormal,
  abnormalCheckOption,
}) {
  const { t } = useTranslation();
  const chartData = reorganization(
    data,
    selectedGraph,
    selectedGraphPer,
    selectedAbnormal,
    abnormalCheckOption,
    t,
  );
  return (
    <div className={cx('chart-area')}>
      <div>
        {chartData && chartData.series && chartData.axis && (
          <CanvasLineChart
            id='dep-dashboard-chart'
            series={chartData.series}
            axis={chartData.axis}
            font='normal 12px SpoqaM'
            fontHeight={12}
            renderOption={{
              bottomTick: false,
              bottomText: false,
            }}
            pointSize={1}
            canvasStyle={{
              background: '#EBFBFF',
              borderRadius: '10px',
            }}
          />
        )}
      </div>
    </div>
  );
}

export default memo(DeployDashboardHistoryChart, (prev, next) => {
  const p = _.cloneDeep(prev);
  const n = _.cloneDeep(next);
  return p === n;
});
