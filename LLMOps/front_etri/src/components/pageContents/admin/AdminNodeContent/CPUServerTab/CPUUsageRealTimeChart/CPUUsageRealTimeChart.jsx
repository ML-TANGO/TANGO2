import { useEffect, useState, useCallback, useMemo } from 'react';

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
import style from './CPUUsageRealTimeChart.module.scss';
const cx = classNames.bind(style);

let lineChart;

function CPUUsageRealTimeChart() {
  const { t } = useTranslation();

  const allocSeries = useMemo(
    () => [
      {
        align: 'LEFT',
        x: 'date',
        y: 'alloc',
        color: '#e57373',
        label: t('cpuAllocation.label'),
      },
      {
        align: 'RIGHT',
        x: 'date',
        y: 'cpuAllocRate',
        color: '#7986cb',
        label: `${t('cpuAllocationRate.label')}(%)`,
        domain: [0, 100],
      },
    ],
    [t],
  );

  const utilizationRateSeries = useMemo(
    () => [
      {
        align: 'LEFT',
        x: 'date',
        y: 'cpuUsageRate',
        color: '#e57373',
        label: `${t('cpuUsageRate.label')}(%)`,
        domain: [0, 100],
      },
      {
        align: 'RIGHT',
        x: 'date',
        y: 'cpuAllocRate',
        color: '#7986cb',
        label: `${t('cpuAllocationRate.label')}(%)`,
        domain: [0, 100],
      },
    ],
    [t],
  );

  const podUsageRateSeries = useMemo(
    () => [
      {
        align: 'LEFT',
        x: 'date',
        y: 'podUsageRate',
        color: '#e57373',
        label: `${t('podUsageRate.label')}(%)`,
        domain: [0, 100],
      },
      {
        align: 'RIGHT',
        x: 'date',
        y: 'cpuAllocRate',
        color: '#7986cb',
        label: `${t('cpuAllocationRate.label')}(%)`,
        domain: [0, 100],
      },
    ],
    [t],
  );

  const options = [
    { label: t('cpuUsageRate.label'), value: 'USAGE' },
    { label: t('cpuAllocation.label'), value: 'ALLOC' },
    { label: t('podUsageRate.label'), value: 'POD_USAGE' },
  ];
  const [selected, setSelected] = useState(options[0]);

  const selectHandler = (opt) => {
    setSelected(opt);
  };

  const getChartData = useCallback(async () => {
    const res = await callApi({
      url: 'nodes/cpu_history',
      method: 'get',
    });
    const { result, status, message } = res;

    if (status === STATUS_SUCCESS) {
      const { history_list: history } = result;
      let newData = history.map(({ cpu, time }) => ({
        date: time,
        alloc: cpu.alloc,
        cpuUsageRate: cpu.usage_rate,
        cpuAllocRate: cpu.alloc_rate,
        podUsageRate: cpu.pod_usage_rate,
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
      eleId: 'cpu-usage-chart',
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

    if (selected.value === 'USAGE') {
      lineChart.setSeries(utilizationRateSeries);
    } else if (selected.value === 'ALLOC') {
      lineChart.setSeries(allocSeries);
    } else if (selected.value === 'POD_USAGE') {
      lineChart.setSeries(podUsageRateSeries);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let series = [];
    if (selected.value === 'USAGE') {
      series = utilizationRateSeries;
    } else if (selected.value === 'ALLOC') {
      series = allocSeries;
    } else if (selected.value === 'POD_USAGE') {
      series = podUsageRateSeries;
    }
    lineChart.setSeries(series);
    lineChart.draw();
  }, [allocSeries, podUsageRateSeries, selected, utilizationRateSeries]);

  return (
    <div className={cx('cpu-usage-chart')}>
      <div className={cx('controller')}>
        <Selectbox
          size='small'
          list={options}
          selectedItem={selected}
          onChange={selectHandler}
        />
      </div>
      <div id='cpu-usage-chart'></div>
    </div>
  );
}

export default CPUUsageRealTimeChart;
