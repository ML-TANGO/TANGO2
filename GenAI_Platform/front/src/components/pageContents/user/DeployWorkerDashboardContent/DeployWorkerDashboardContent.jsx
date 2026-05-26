// Container
import WorkerDetail from './WorkerDetail';

// Components
import Loading from '@src/components/atoms/loading/CircleLoading';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeployWorkerDetailContent.module.scss';
const cx = classNames.bind(style);

function DeployWorkerDashboardContent({
  loading,
  workerId,
  totalInfoData,
  resourceInfoData,
  detailInfoData,
  detailInfoOverview,
  resourceGraphData,
  searchType,
  startDate,
  endDate,
  minDate,
  resolution,
  resolutionList,
  historyGraphData,
  searchResultInfoData,
  statusCodeData,
  errorRecordData,
  processTimeResponseTimeList,
  workerMemoModalHandler,
  selectedGraph,
  onSelectGraph,
  openStopModal,
  gotoList,
  logDownOptions,
  selectedGraphPer,
  logDownOptionsHandler,
  onDownloadCallLogs,
  workerStopHandler,
  requestHistoryGraphData,
  stopWorkerRequest,
  onChangeDate,
  onChangeSearchType,
  onChangeResolution,
  detailInfoOverviewHandler,
  onDownloadErrorRecord,
  onSelectProcessTime,
  onSelectResponseType,
  workerStatus,
  openDeleteWorkerModal,
  getSystemLogData,
  systemLogLoading,
  title,
}) {
  return (
    <div className={cx('worker-detail')}>
      {loading && (
        <div className={cx('loading-box')}>
          <Loading
            customStyle={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          />
        </div>
      )}
      {!loading && (
        <WorkerDetail
          workerId={workerId}
          endDate={endDate}
          minDate={minDate}
          startDate={startDate}
          searchType={searchType}
          resolution={resolution}
          workerStatus={workerStatus}
          openStopModal={openStopModal}
          selectedGraph={selectedGraph}
          totalInfoData={totalInfoData}
          detailInfoData={detailInfoData}
          resolutionList={resolutionList}
          statusCodeData={statusCodeData}
          logDownOptions={logDownOptions}
          errorRecordData={errorRecordData}
          historyGraphData={historyGraphData}
          resourceInfoData={resourceInfoData}
          selectedGraphPer={selectedGraphPer}
          resourceGraphData={resourceGraphData}
          detailInfoOverview={detailInfoOverview}
          searchResultInfoData={searchResultInfoData}
          processTimeResponseTimeList={processTimeResponseTimeList}
          gotoList={gotoList}
          onChangeDate={onChangeDate}
          onSelectGraph={onSelectGraph}
          workerStopHandler={workerStopHandler}
          stopWorkerRequest={stopWorkerRequest}
          onChangeSearchType={onChangeSearchType}
          onChangeResolution={onChangeResolution}
          onDownloadCallLogs={onDownloadCallLogs}
          onSelectProcessTime={onSelectProcessTime}
          onSelectResponseType={onSelectResponseType}
          logDownOptionsHandler={logDownOptionsHandler}
          onDownloadErrorRecord={onDownloadErrorRecord}
          workerMemoModalHandler={workerMemoModalHandler}
          requestHistoryGraphData={requestHistoryGraphData}
          detailInfoOverviewHandler={detailInfoOverviewHandler}
          openDeleteWorkerModal={openDeleteWorkerModal}
          getSystemLogData={getSystemLogData}
          systemLogLoading={systemLogLoading}
          title={title}
        />
      )}
    </div>
  );
}

export default DeployWorkerDashboardContent;
