import { useState, useEffect, useCallback } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Selectbox } from '@jonathan/ui-react';
import LineChart from '@src/d3chart/realtimeLineChart';
import { toast } from '@src/components/Toast';

// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

// Utils
import { sortAscending } from '@src/utils';
import { convertTimeStamp } from '@src/datetimeUtils';

// CSS Module
import classNames from 'classnames/bind';
import style from './GPUUsageRealTimeChart.module.scss';
const cx = classNames.bind(style);

let lineChart;

const gpuSeries = [
  {
    align: 'LEFT',
    x: 'date',
    y: 'gpuUsage',
    color: '#e57373',
    label: 'General',
  },
  {
    align: 'RIGHT',
    x: 'date',
    y: 'gpuUsageRate',
    color: '#7986cb',
    label: 'General Rate(%)',
    domain: [0, 100],
  },
];

const migSeries = [
  {
    align: 'LEFT',
    x: 'date',
    y: 'migUsage',
    color: '#e57373',
    label: 'MIG',
  },
  {
    align: 'RIGHT',
    x: 'date',
    y: 'migUsageRate',
    color: '#7986cb',
    label: 'MIG Rate(%)',
    domain: [0, 100],
  },
];

/**
 * GPU 실시간 그래프 컴포넌트
 *
 * @component
 * @example
 *
 * return (
 *  <GPUUsageRealTimeChart />
 * );
 */
function GPUUsageRealTimeChart() {
  const { t } = useTranslation();

  const options = [
    { label: t('gpuAllocation.label'), value: 'gpu' },
    { label: t('migAllocation.label'), value: 'mig' },
  ];

  const [selected, setSelected] = useState(options[0]);

  const selectHandler = (opt) => {
    setSelected(opt);
  };

  const getChartData = useCallback(async () => {
    const res = await callApi({
      url: 'nodes/gpu_history',
      method: 'get',
    });

    const { result, status, message } = res;

    if (status === STATUS_SUCCESS) {
      const { history_list: history } = result;
      let newData = history.map(({ general, mig, time }) => ({
        date: time,
        gpuUsage: general.used,
        gpuUsageRate: general.rate,
        migUsage: mig.used,
        migUsageRate: mig.rate,
      }));

      newData = sortAscending(newData, 'date');
      lineChart.draw(newData);
      return true;
    }
    if (status === STATUS_FAIL) {
      toast.error(message);
      return false;
    }
    toast.error(message);
    return false;
  }, []);

  useIntervalCall(getChartData);

  useEffect(() => {
    lineChart = new LineChart({
      eleId: 'gpu-usage-line-chart',
      width: 300,
      height: 200,
      isResponsive: true,
      scaleType: 'date',
      legend: true,
      xTickFormat: (ts) => convertTimeStamp(ts, 'm:ss'),
      xAxisMaxTicks: 6,
      tooltip: {
        align: 'right',
      },
    });
    lineChart.setSeries(selected.value === 'gpu' ? gpuSeries : migSeries);
    return () => lineChart.removeTooltip();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const series = selected.value === 'gpu' ? gpuSeries : migSeries;
    lineChart.setSeries(series);
    lineChart.draw();
  }, [selected]);

  return (
    <div className={cx('gpu-usage-chart')}>
      <div className={cx('controller')}>
        <Selectbox
          size='small'
          list={options}
          selectedItem={selected}
          onChange={selectHandler}
        />
      </div>
      <div id='gpu-usage-line-chart'></div>
    </div>
  );
}

export default GPUUsageRealTimeChart;
