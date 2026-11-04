import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { calInstanceTotalValue } from '../../util';

import { calAllocateInstanceValue } from '../InstanceDetail';
import ListDonutChart, { calInstanceName } from './ListDonutChart';
import classNames from 'classnames/bind';
import style from './GraphCont.module.scss';

const cx = classNames.bind(style);

const chartColorFourList = ['#2D76F8', '#93BAFF', '#C8DBFD', '#DEE9FF'];
const chartColorFiveList = ['#164ABE', ...chartColorFourList];
const chartColorSixList = ['#002F77', ...chartColorFiveList];
const chartColorSevenList = ['#042659', ...chartColorSixList];
const chartColorEightList = [...chartColorSevenList, '#C1C1C1'];

const chartColorObj = {
  4: chartColorFourList,
  5: chartColorFiveList,
  6: chartColorSixList,
  7: chartColorSevenList,
  8: chartColorEightList,
};

const calColorList = (length) => {
  if (length <= 4) return chartColorObj[4];
  if (length === 5) return chartColorObj[5];
  if (length === 6) return chartColorObj[6];
  if (length === 7) return chartColorObj[7];
  if (length >= 8) return chartColorObj[8];
};

const GraphCont = ({ instanceList, instanceTotalValue }) => {
  const { t } = useTranslation();

  const totalValue = calInstanceTotalValue(instanceList);

  const sortInstanceData = useMemo(() => {
    return instanceList.sort(
      (a, b) => b.instance_total_count - a.instance_total_count,
    );
  }, [instanceList]);

  const chartData = sortInstanceData.map((el, idx) => {
    const colorList = calColorList(instanceList.length);
    const allocateValue = calAllocateInstanceValue(el.allocate_workspace_list);
    const percentValue = ((allocateValue / totalValue) * 100).toFixed(0);
    const name = calInstanceName(el);
    return {
      value: percentValue,
      color: colorList[idx],
      name,
      ...el,
    };
  });
  const percentage = chartData.reduce((acc, cur) => {
    acc += +cur.value;
    return acc;
  }, 0);
  const graphDataList = useMemo(() => {
    const copyList = chartData.slice();
    copyList.push({
      value: 100 - percentage,
      color: '#F0F0F0',
      name: '',
    });
    return copyList;
  }, [chartData, percentage]);

  return (
    <div className={cx('node-pie-chart')}>
      <p className={cx('title')}>{t('node.instance.allocate.label')}</p>
      <div className={cx('content-cont')}>
        <div className={cx('chart-cont')}>
          <ListDonutChart
            data={graphDataList}
            width={160}
            percentage={percentage}
            instanceTotalValue={instanceTotalValue}
          />
        </div>
        <div className={cx('label-cont')}>
          {chartData.length === 0 && (
            <div className={cx('row')}>{t('noData.message')}</div>
          )}
          {chartData.map((el, idx) => {
            const allocateValue = calAllocateInstanceValue(
              el.allocate_workspace_list,
            );
            return (
              <div className={cx('row')} key={idx}>
                <div
                  className={cx('circle')}
                  style={{ backgroundColor: el.color }}
                />
                <span className={cx('name')}>
                  {el.gpu_name === 'No Resource Group'
                    ? `CPU.${el.cpu_count}.${el.ram_count}`
                    : el.gpu_name}
                </span>
                <span className={cx('count')}>
                  {el.instance_total_count} EA
                </span>
                <span className={cx('percent')}>
                  {((allocateValue / totalValue) * 100).toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default GraphCont;
