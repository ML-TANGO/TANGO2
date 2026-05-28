// i18n

// Components
import { useTranslation } from 'react-i18next';

import { Tab } from '@jonathan/ui-react';

import DeployWorkerRunning from './DeployWorkerRunning';
import DeployWorkerStopped from './DeployWorkerStopped';

function DeployWorker({
  workerSettingInfo,
  selectedPage,
  workerList,
  overviewList,
  stopWorkerRequest,
  addWorker,
  tabHandler,
  workerStopPopup,
  workerStopConfirmPopupHandler,
  workerMemoModalHandler,
  onEdit,
  overviewHandler,
  moveToWorkerDetail,
  did,
  getStoppedData,
  workerDeleteClickHandler,
  checkedData,
  onSelect,
  toggledClear,
  workerDownHandler,
  inputValueHandler,
  keyword,
  stoppedInputValue,
  tableData,
  selectInputHandler,
  searchKey,
  getSystemLogData,
  systemLogLoading,
  workerIds,
  title,
  addLoading,
  workerStopList,
  cancelWorkerStopId,
  instanceType,
  workerSettingValue,
}) {
  const { t } = useTranslation();

  const category = [
    {
      label: t('worker.running.tab.label'),
      component: () => (
        <DeployWorkerRunning
          workerList={workerList}
          workerStopPopup={workerStopPopup}
          workerStopConfirmPopupHandler={workerStopConfirmPopupHandler}
          stopWorkerRequest={stopWorkerRequest}
          addWorker={addWorker}
          onEdit={onEdit}
          workerSettingInfo={workerSettingInfo}
          overviewList={overviewList}
          overviewHandler={overviewHandler}
          workerMemoModalHandler={workerMemoModalHandler}
          moveToWorkerDetail={moveToWorkerDetail}
          getSystemLogData={getSystemLogData}
          systemLogLoading={systemLogLoading}
          workerIds={workerIds}
          addLoading={addLoading}
          workerStopList={workerStopList}
          cancelWorkerStopId={cancelWorkerStopId}
          instanceType={instanceType}
          workerSettingValue={workerSettingValue}
        />
      ),
    },
    {
      label: t('worker.stopped.tab.label'),
      component: () => (
        <DeployWorkerStopped
          workerMemoModalHandler={workerMemoModalHandler}
          did={did}
          getStoppedData={getStoppedData}
          workerDeleteClickHandler={workerDeleteClickHandler}
          checkedData={checkedData}
          onSelect={onSelect}
          toggledClear={toggledClear}
          workerDownHandler={workerDownHandler}
          inputValueHandler={inputValueHandler}
          stoppedInputValue={stoppedInputValue}
          keyword={keyword}
          tableData={tableData}
          selectInputHandler={selectInputHandler}
          searchKey={searchKey}
          title={title}
        />
      ),
    },
  ];
  return (
    <Tab
      selectedItem={selectedPage}
      onClick={tabHandler}
      category={category}
      renderComponent={category[selectedPage].component}
      customStyle={{
        label: {
          width: 'max-content',
        },
        component: {
          paddingBottom: '10px',
        },
      }}
      t={t}
    />
  );
}

export default DeployWorker;
