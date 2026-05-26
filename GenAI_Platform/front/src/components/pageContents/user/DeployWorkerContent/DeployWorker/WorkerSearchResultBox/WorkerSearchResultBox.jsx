import { useState } from 'react';

// Components
import ChartSearchBox from '../ChartSearchBox';
import ChartControlBox from '../ChartControlBox';
import DeployDashboardHistoryChart from '@src/components/molecules/DeployChart/DeployDashboardHistoryChart';
import StatusCodeTable from '../StatusCodeTable';
import AbnormalProcessingRecordTable from '../AbnormalProcessingRecordTable';

// CSS Module
import classNames from 'classnames/bind';
import style from './WorkerSearchResultBox.module.scss';
const cx = classNames.bind(style);

function WorkerSearchResultBox({
  workerStatus,
  searchType,
  startDate,
  endDate,
  minDate,
  resolution,
  resolutionList,
  workers,
  workerList,
  infoData,
  historyGraphData,
  selectedGraph,
  statusCodeData,
  errorRecordData,
  onDownloadErrorRecord,
  logDownOptions,
  logDownOptionsHandler,
  selectedGraphPer,
  processTimeResponseTimeList,
  onSelectProcessTime,
  onSelectResponseType,
  onDownloadCallLogs,
  requestHistoryGraphData,
  onChangeDate,
  onChangeWorker,
  onChangeResolution,
  onChangeSearchType,
  onSelectGraph,
}) {
  const abnormalOptions = [
    { label: 'Calculate', isDisabled: true },
    { label: 'count.label', value: 'count', isDisabled: false },
    { label: 'rate.label', value: 'rate', isDisabled: false },
  ];
  const [selectedAbnormal, setSelectedAbnormal] = useState({
    label: 'count.label',
    value: 'count',
  });
  const [checkOptions, setCheckOptions] = useState({
    nginx: true,
    api: true,
  });

  /**
   * 체크박스 클릭 핸들러
   * @param {object} option
   */
  const optionClickHandler = (option) => {
    setCheckOptions({ ...checkOptions, [option]: !checkOptions[option] });
  };

  const selectInputHandler = (name, value) => {
    setSelectedAbnormal(value);
  };

  return (
    <div className={cx('worker-result-wrap')}>
      <ChartSearchBox
        workerStatus={workerStatus}
        searchType={searchType}
        startDate={startDate}
        endDate={endDate}
        minDate={minDate}
        onChangeDate={onChangeDate}
        resolution={resolution}
        resolutionList={resolutionList}
        workers={workers}
        workerList={workerList}
        infoData={infoData}
        onSubmit={requestHistoryGraphData}
        onChangeWorker={onChangeWorker}
        onChangeSearchType={onChangeSearchType}
        onChangeResolution={onChangeResolution}
      />
      <ChartControlBox
        selectedGraph={selectedGraph}
        workerList={workerList}
        infoData={infoData}
        onSelectGraph={onSelectGraph}
        logDownOptions={logDownOptions}
        logDownOptionsHandler={logDownOptionsHandler}
        onDownloadCallLogs={onDownloadCallLogs}
        abnormalOptions={abnormalOptions}
        selectedAbnormal={selectedAbnormal}
        checkOptions={checkOptions}
        selectedGraphPer={selectedGraphPer}
        processTimeResponseTimeList={processTimeResponseTimeList}
        onSelectProcessTime={onSelectProcessTime}
        onSelectResponseType={onSelectResponseType}
        optionClickHandler={optionClickHandler}
        selectInputHandler={selectInputHandler}
      />
      <DeployDashboardHistoryChart
        data={historyGraphData}
        selectedGraph={selectedGraph}
        selectedGraphPer={selectedGraphPer}
        selectedAbnormal={selectedAbnormal.value}
        abnormalCheckOption={checkOptions}
      />
      <StatusCodeTable data={statusCodeData} />
      <AbnormalProcessingRecordTable
        data={errorRecordData}
        onDownload={onDownloadErrorRecord}
      />
    </div>
  );
}

export default WorkerSearchResultBox;
