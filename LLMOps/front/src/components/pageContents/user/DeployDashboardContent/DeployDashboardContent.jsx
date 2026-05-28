// Components
import { useHistory, useLocation, useRouteMatch } from 'react-router-dom';

import SelectBox from '@src/components/atoms/SelectBox';
import DeployStatusCard from '@src/components/molecules/DeployStatusCard';
import WorkerSearchResultBox from '@src/components/pageContents/user/DeployWorkerContent/DeployWorker/WorkerSearchResultBox';

import classNames from 'classnames/bind';
import style from './DeployDashboardContent.module.scss';

import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';

const cx = classNames.bind(style);

const calIsPlaygroundPath = (path) => {
  if (path.includes('playgroundmonitor')) return true;
  return false;
};

const calMonitoringId = (value, locationState) => {
  const { playground_id, embedding_id, reranker_id } = locationState;
  if (value === 0) return playground_id;
  if (value === 1) return embedding_id;
  return reranker_id;
};

const handleHistoryBack = (workspaceId, backPlaygroundId, history) => {
  history.push(
    `/user/workspace/${workspaceId}/llmplayground/${backPlaygroundId}/llmplayground`,
  );
};

const handleSelectbox = (
  { value },
  workspaceId,
  backPlaygroundId,
  locationState,
  history,
) => {
  const monitoringId = calMonitoringId(value, locationState);
  history.replace(
    `/user/workspace/${workspaceId}/llmplayground/${backPlaygroundId}/detail/${monitoringId}/playgroundmonitor`,
    { ...locationState, selectedValue: value },
  );
};

const PlaygroundHeader = ({ title }) => {
  const match = useRouteMatch();
  const location = useLocation();
  const history = useHistory();

  const { id: workspaceId } = match.params;

  const { state } = location;
  const { backPlaygroundId, playground_id, embedding_id, reranker_id } = state;

  const selectList = [
    {
      label: '플레이그라운드 모니터',
      value: 0,
      disabled: !playground_id,
    },
    {
      label: 'RAG 임베딩 모델 모니터',
      value: 1,
      disabled: !embedding_id,
    },
    {
      label: 'RAG 리랭커 모델 모니터',
      value: 2,
      disabled: !reranker_id,
    },
  ];

  return (
    <>
      <div
        className={cx('back-cont')}
        onClick={() =>
          handleHistoryBack(workspaceId, backPlaygroundId, history)
        }
      >
        <img src={BackIcon} alt='back-icon' />
        <span>돌아가기</span>
      </div>
      <div className={cx('title-cont')}>
        {title && (
          <>
            <div className={cx('title')}>{title}</div>
            {/* <SelectBox
              value={selectedValue}
              list={selectList}
              handleOptionClick={(value) =>
                handleSelectbox(
                  value,
                  workspaceId,
                  backPlaygroundId,
                  state,
                  history,
                )
              }
              style={{ width: '240px', height: '38px', padding: '0px 16px' }}
            /> */}
          </>
        )}
      </div>
    </>
  );
};

function DeployDashboardContent({
  title,
  totalInfoData,
  resourceInfoData,
  loading,
  searchType,
  startDate,
  endDate,
  minDate,
  resolution,
  resolutionList,
  workers,
  workerList,
  infoData,
  chartData,
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
  const match = useRouteMatch();
  const isPlayground = calIsPlaygroundPath(match.path);

  return (
    <div className={cx('dashboard')}>
      {isPlayground && <PlaygroundHeader title={title} />}
      {!isPlayground && title && <div className={cx('title')}>{title}</div>}
      <DeployStatusCard
        type='deployDashboard'
        totalInfoData={totalInfoData}
        resourceInfoData={resourceInfoData}
        visibleUsageChart={true}
        isWorker={false}
      />
      <WorkerSearchResultBox
        searchType={searchType}
        startDate={startDate}
        endDate={endDate}
        minDate={minDate}
        loading={loading}
        historyGraphData={historyGraphData}
        selectedGraphPer={selectedGraphPer}
        processTimeResponseTimeList={processTimeResponseTimeList}
        onSelectProcessTime={onSelectProcessTime}
        onSelectResponseType={onSelectResponseType}
        onSelectGraph={onSelectGraph}
        selectedGraph={selectedGraph}
        onChangeDate={onChangeDate}
        resolution={resolution}
        resolutionList={resolutionList}
        onChangeResolution={onChangeResolution}
        workers={workers}
        workerList={workerList}
        onChangeWorker={onChangeWorker}
        requestHistoryGraphData={requestHistoryGraphData}
        infoData={infoData}
        chartData={chartData}
        logDownOptions={logDownOptions}
        logDownOptionsHandler={logDownOptionsHandler}
        onDownloadCallLogs={onDownloadCallLogs}
        statusCodeData={statusCodeData}
        errorRecordData={errorRecordData}
        onChangeSearchType={onChangeSearchType}
        onDownloadErrorRecord={onDownloadErrorRecord}
      />
    </div>
  );
}

export default DeployDashboardContent;
