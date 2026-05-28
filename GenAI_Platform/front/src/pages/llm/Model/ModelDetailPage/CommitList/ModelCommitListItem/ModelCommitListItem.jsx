import { getModelsCommitModels } from '@src/apis/llm/model';
import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import * as echarts from 'echarts';
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ModelCommitListItem.module.scss';

const cx = classNames.bind(style);

function DynamicLineCharts({ resultLog, epoch }) {
  const chartRefs = useRef([]);

  console.log(resultLog);
  useLayoutEffect(() => {
    // 그래프 초기화
    if (resultLog && Object.keys(resultLog).length > 0) {
      Object.entries(resultLog).forEach(([key, value], index) => {
        const chartContainer = chartRefs.current[index];
        if (chartContainer && value.steps && value.values) {
          const minValue =
            Math.trunc(Math.min(...value.values) * 0.95 * 100) / 100;
          // const rawMinValue = Math.min(...value.values);
          // const minValue =
          //   rawMinValue < 0 ? 0 : parseFloat(rawMinValue.toFixed(2));
          const chart = echarts.init(chartContainer);
          const option = {
            tooltip: { trigger: 'axis' },
            grid: {
              top: 24,
              right: 24,
              bottom: 24,
              left: 24,
              containLabel: true,
            },
            xAxis: { type: 'category', data: value.steps, boundaryGap: false },
            yAxis: { type: 'value', min: minValue },
            series: [
              {
                type: 'line',
                data: value.values,
                smooth: true,
                lineStyle: { width: 2 },
                itemStyle: { color: '#002f77' },
              },
            ],
          };
          chart.setOption(option);

          const resizeObserver = new ResizeObserver(() => {
            chart.resize();
          });
          resizeObserver.observe(chartContainer);

          // Cleanup
          return () => {
            resizeObserver.disconnect();
          };
        }
      });
    }
  }, [resultLog]);

  return (
    <div className={cx('chart-grid')}>
      {resultLog &&
        Object.entries(resultLog).map(([key], index) => (
          <div key={key} className={cx('chart-item')}>
            <div className={cx('chart-title')}>{key}</div>
            <div
              ref={(el) => (chartRefs.current[index] = el)}
              className={cx('chart-container')}
            />
            <div className={cx('epoch')}>
              <img src={InfoIcon} alt='icon' />1 Epoch = {epoch} steps
            </div>
          </div>
        ))}
    </div>
  );
}

function ModelCommitListItem({ data }) {
  const { cId, t } = data;

  const [info, setInfo] = useState(null);

  const getInfo = useCallback(async () => {
    const res = await getModelsCommitModels(cId);

    const { result, status, error, message } = res;
    if (status === STATUS_SUCCESS) {
      setInfo(result);
    } else {
      errorToastMessage(error, message);
    }
  }, [cId]);

  useEffect(() => {
    getInfo();
  }, [getInfo]);
  return (
    <div className={cx('container')}>
      <div className={cx('title')}>
        {info?.name ?? '-'}
        <span>{info?.model_name ?? '-'}</span>
      </div>
      <div className={cx('top')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitName.label')}</div>
          <div className={cx('value')}>{info?.name ?? '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitMessage.label')}</div>
          <div className={cx('value')}>
            {!info?.commit_message ? '-' : info.commit_message}
          </div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('writer.label')}</div>
          <div className={cx('value')}>{info?.create_user_name ?? '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitDate.label')}</div>
          <div className={cx('value')}>{info?.commit_datetime ?? '-'}</div>
        </div>
      </div>
      <div className={cx('graph')}>
        {info?.result_log && (
          <DynamicLineCharts
            resultLog={info.result_log}
            epoch={info.steps_per_epoch}
          />
        )}
      </div>
    </div>
  );
}

export default ModelCommitListItem;
