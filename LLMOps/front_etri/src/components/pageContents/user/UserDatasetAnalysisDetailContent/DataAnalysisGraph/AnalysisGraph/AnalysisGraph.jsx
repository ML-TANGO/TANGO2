import { useTranslation } from 'react-i18next';

import { ButtonV2, Loading } from '@jonathan/ui-react';

import ChartInfoCard from './ChartInfoCard';
import DynamicCharts from './DynamicCharts';

import classNames from 'classnames/bind';
import style from './AnalysisGraph.module.scss';

const cx = classNames.bind(style);

export default function AnalysisGraph({
  isFetching,
  columns = [],
  data = [],
  graphData,
  originGraphData,
  checkboxHandler,
  checkedId,
  showInfoHandler,
  showInfoId,
  isLoading,
}) {
  const { t } = useTranslation();

  return (
    <div
      className={cx(
        'frame',
        originGraphData.length === 0 ? 'height-746' : 'height-1140',
      )}
    >
      {isLoading && (
        <div className={cx('no-data')}>
          <Loading />
        </div>
      )}
      {/* <div className={cx('no-data')}>그래프를 추가해 주세요.</div> */}
      {!isLoading && originGraphData.length === 0 && (
        <div className={cx('no-data')}>{t('graphAdd.message')}</div>
      )}
      <div className={cx('chart-grid')}>
        {!isLoading &&
          originGraphData.length > 0 &&
          graphData?.map((item) => {
            const showGraph = showInfoId.includes(item?.id);
            console.log(item);
            if (showGraph) {
              return (
                <ChartInfoCard
                  key={item.id}
                  type={item.type}
                  data={item}
                  checkboxHandler={checkboxHandler}
                  checkedId={checkedId}
                  showInfoHandler={showInfoHandler}
                />
              );
            } else {
              return (
                <DynamicCharts
                  key={item.id}
                  id={item.id}
                  type={item.type}
                  data={item.graph}
                  title={item.name}
                  column={item.column}
                  checkboxHandler={checkboxHandler}
                  checkedId={checkedId}
                  showInfoHandler={showInfoHandler}
                />
              );
            }
          })}
      </div>
    </div>
  );
}
