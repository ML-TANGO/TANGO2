import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import MultipleTimeSeriesChart from '@src/components/molecules/chart/MultipleTimeSeriesChart';

import { callApi } from '@src/network';
import { executeWithLogging } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ResourceUsageGraph.module.scss';

const cx = classNames.bind(style);

const calGetGraphOptions = (t) => {
  return [
    { label: t('all.label'), value: 'all' },
    { label: 'GPU', value: 'gpu' },
    { label: 'CPU', value: 'cpu' },
    { label: 'RAM', value: 'ram' },
  ];
};

const calGetAxisSeriesArr = (t) => {
  return [
    {
      dateX: 'timestamp',
      valueY: 'gpu',
      tooltipText: `GPU ${t('usage.label')}: {gpu}`,
      maxValue: 300,
      opposite: false,
      legendLabel: 'GPU',
      color: '#00c775',
    },
    {
      dateX: 'timestamp',
      valueY: 'cpu',
      tooltipText: `CPU ${t('usage.label')}: {cpu}`,
      legendLabel: 'CPU',
      color: '#ffab0e',
    },
    {
      dateX: 'timestamp',
      valueY: 'ram',
      tooltipText: `RAM ${t('usage.label')}: {ram}`,
      legendLabel: 'RAM',
      color: '#2d76f8',
    },
  ];
};

const ResourceUsageGraph = ({ workspaceId, isLoading, dateState }) => {
  const { t } = useTranslation();

  const [expand, setExpand] = useState(true);
  const [graphMenu, setGraphMenu] = useState({
    label: 'all.label',
    value: 'all',
  });

  const graphOptions = useMemo(() => {
    return calGetGraphOptions(t);
  }, [t]);

  const axisSeriesArr = useMemo(() => {
    return calGetAxisSeriesArr(t);
  }, [t]);

  const handleShowGraph = useCallback(() => {
    setExpand((prev) => !prev);
  }, []);

  const [graphData, setGraphData] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const getGraphData = async () => {
      if (!workspaceId) return;

      executeWithLogging(async () => {
        const { result } = await callApi({
          url: 'records/utilization/figure',
          method: 'get',
          params: {
            workspace_id: workspaceId !== 9999 ? workspaceId : null,
            start_datetime: dateState.startDate,
            end_datetime: dateState.endDate,
            aggregation: 'minute',
          },
          signal,
        });
        setGraphData(result);
      });
    };

    getGraphData();

    return () => controller.abort();
  }, [workspaceId, dateState]);

  return (
    <div className={cx('graph-cont')}>
      <div className={cx('menu')}>
        {graphOptions.map(({ label, value }) => (
          <div
            key={value}
            className={cx('menu-item', value === graphMenu.value && 'selected')}
            onClick={() => setGraphMenu({ label, value })}
          >
            {t(label)}
          </div>
        ))}
      </div>
      <div
        className={cx('chart-box')}
        style={{ height: expand ? '508px' : 'auto' }}
      >
        <div
          className={cx('title')}
          style={{ marginBottom: expand ? '32px' : '24px' }}
          onClick={handleShowGraph}
        >
          <label>
            {graphMenu.value === 'all'
              ? t('resource.label')
              : graphMenu.value.toUpperCase()}{' '}
            {t('maximumUsageByDaily.title.label')}
          </label>
          <button className={cx('chart-hide-btn')}>
            <img
              src='/images/icon/angle-up.svg'
              className={cx(!expand && 'hide')}
              alt='show/hide button'
            />
          </button>
        </div>
        {expand && !isLoading && (
          <>
            {graphMenu.value === 'all' ? (
              <MultipleTimeSeriesChart
                tagId='allchart'
                data={graphData.map((el) => {
                  const dateObject = new Date(el.timestamp);
                  return {
                    timestamp: dateObject,
                    cpu: el.cpu,
                    gpu: el.gpu,
                    ram: el.ram,
                  };
                })}
                axisSeriesArr={axisSeriesArr}
                customStyle={{
                  width: '100%',
                  height: '389px',
                }}
              />
            ) : (
              <>
                {(() => {
                  const chartOpt = {
                    data: graphData.map((el) => {
                      const dateObject = new Date(el.timestamp);
                      return {
                        timestamp: dateObject,
                        [graphMenu.value]: el[graphMenu.value],
                      };
                    }),
                    customStyle: {
                      width: '100%',
                      height: '395px',
                    },
                  };
                  if (graphMenu.value === 'gpu') {
                    chartOpt.tagId = 'gpuchart';
                    chartOpt.axisSeriesArr = [
                      {
                        dateX: 'timestamp',
                        valueY: 'gpu',
                        tooltipText: `GPU ${t('usage.label')}: {gpu}`,
                        opposite: false,
                        legendLabel: 'GPU',
                        color: '#00c775',
                      },
                    ];
                  } else if (graphMenu.value === 'cpu') {
                    chartOpt.tagId = 'cpuchart';
                    chartOpt.axisSeriesArr = [
                      {
                        dateX: 'timestamp',
                        valueY: 'cpu',
                        tooltipText: `CPU ${t('usage.label')}: {cpu}`,
                        opposite: false,
                        legendLabel: 'CPU',
                        color: '#ffab0e',
                      },
                    ];
                  } else if (graphMenu.value === 'ram') {
                    chartOpt.tagId = 'ramchart';
                    chartOpt.axisSeriesArr = [
                      {
                        dateX: 'timestamp',
                        valueY: 'ram',
                        tooltipText: `RAM ${t('usage.label')}: {ram}`,
                        opposite: false,
                        legendLabel: 'RAM',
                        color: '#2d76f8',
                      },
                    ];
                  }
                  return <MultipleTimeSeriesChart {...chartOpt} />;
                })()}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ResourceUsageGraph;
