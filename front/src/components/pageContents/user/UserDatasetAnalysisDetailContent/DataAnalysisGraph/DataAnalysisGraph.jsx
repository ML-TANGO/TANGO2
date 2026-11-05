import React from 'react';

import AnalysisGraph from './AnalysisGraph';
import AnalysisInfo from './AnalysisInfo';

// CSS Module
import classNames from 'classnames/bind';
import style from './DataAnalysisGraph.module.scss';

const cx = classNames.bind(style);

export default function DataAnalysisGraph({
  infoData,
  graphData,
  originGraphData,
  checkboxHandler,
  checkedId,
  showInfoHandler,
  showInfoId,
  isLoading,
}) {
  return (
    <div className={cx('info-cont')}>
      <AnalysisInfo infoData={infoData} originGraphData={originGraphData} />
      <AnalysisGraph
        originGraphData={originGraphData}
        graphData={graphData}
        checkboxHandler={checkboxHandler}
        checkedId={checkedId}
        showInfoHandler={showInfoHandler}
        showInfoId={showInfoId}
        isLoading={isLoading}
      />
    </div>
  );
}
