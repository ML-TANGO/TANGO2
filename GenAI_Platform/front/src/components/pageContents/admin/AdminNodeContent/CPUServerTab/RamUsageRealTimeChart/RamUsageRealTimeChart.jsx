import { useState, useEffect, useCallback, useMemo } from 'react';

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
import style from './RamUsageRealTimeChart.module.scss';
const cx = classNames.bind(style);

let lineChart;

function GPUUsageRealTimeChart() {
  const { t } = useTranslation();

  const allocSeries = useMemo(
    () => [
      {
        align: 'LEFT',
        x: 'date',
        y: 'alloc',
        color: '#e57373',
        label: t('ramAllocation.label'),
      },
      {
        align: 'RIGHT',
        x: 'date',
        y: 'ramAllocRate',
        color: '#7986cb',
        label: `${t('ramAllocationRate.label')}(%)`,
        domain: [0, 100],
      },
    ],
    [t],
  );

  const usageSeries = useMemo(
    () => [
      {
        align: 'LEFT',
        x: 'date',
        y: 'ramUsageRate',
        color: '#e57373',
        label: `${t('ramUsageRate.label')}(%)`,
        domain: [0, 100],
      },
      {
        align: 'RIGHT',
        x: 'date',
        y: 'ramAllocRate',
        color: '#7986cb',
        label: `${t('ramAllocationRate.label')}(%)`,
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
        y: 'ramAllocRate',
        color: '#7986cb',
        label: `${t('ramAllocationRate.label')}(%)`,
        domain: [0, 100],
      },
    ],
    [t],
  );

  const options = [
    { label: t('ramUsageRate.label'), value: 'USAGE' },
    { label: t('ramAllocation.label'), value: 'ALLOC' },
    { label: t('podUsageRate.label'), value: 'POD_USAGE' },
  ];

  const [selected, setSelected] = useState(options[0]);

  const selectHandler = (opt) => {
    setSelected(opt);
  };

  const getChartData = useCallback(async () => {
    const res = await callApi({
      url: 'nodes/ram_history',
      method: 'get',
    });
    const { result, status, message } = res;

    if (status === STATUS_SUCCESS) {
      const { history_list: history } = result;
      let newData = history.map(({ ram, time }) => ({
        date: time,
        alloc: ram.alloc,
        ramUsageRate: ram.usage_rate,
        ramAllocRate: ram.alloc_rate,
        podUsageRate: ram.pod_usage_rate,
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
      eleId: 'ram-usage-line-chart',
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
      lineChart.setSeries(usageSeries);
    } else if (selected.value === 'ALLOC') {
      lineChart.setSeries(allocSeries);
    } else if (selected.value === 'POD_USAGE') {
      lineChart.setSeries(podUsageRateSeries);
    }

    getChartData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let series = [];
    if (selected.value === 'USAGE') {
      series = usageSeries;
    } else if (selected.value === 'ALLOC') {
      series = allocSeries;
    } else if (selected.value === 'POD_USAGE') {
      series = podUsageRateSeries;
    }
    lineChart.setSeries(series);
    lineChart.draw();
  }, [allocSeries, podUsageRateSeries, selected, usageSeries]);

  return (
    <div className={cx('ram-usage-chart')}>
      <div className={cx('controller')}>
        <Selectbox
          size='small'
          list={options}
          selectedItem={selected}
          onChange={selectHandler}
        />
      </div>
      <div id='ram-usage-line-chart'></div>
    </div>
  );
}

export default GPUUsageRealTimeChart;
