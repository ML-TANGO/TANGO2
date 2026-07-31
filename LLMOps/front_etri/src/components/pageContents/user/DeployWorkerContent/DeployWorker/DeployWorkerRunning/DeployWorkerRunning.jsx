import { Fragment } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import Loading from '@src/components/atoms/loading/Loading';

// Component
import WorkerController from './WorkerController';
import WorkerList from './WorkerList';

// style
import classNames from 'classnames/bind';
import style from './DeployWorkerRunning.module.scss';

const cx = classNames.bind(style);

function DeployWorkerRunning({
  workerList,
  workerSettingInfo,
  overviewList,
  addWorker,
  stopWorkerRequest,
  onEdit,
  workerStopConfirmPopupHandler,
  overviewHandler,
  workerMemoModalHandler,
  workerStopPopup,
  moveToWorkerDetail,
  getSystemLogData,
  systemLogLoading,
  workerIds,
  addLoading,
  workerStopList,
  cancelWorkerStopId,
  instanceType,
  workerSettingValue,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('worker-running-wrap')}>
      <WorkerController
        workerSettingInfo={workerSettingInfo}
        onEdit={onEdit}
        addWorker={addWorker}
        addLoading={addLoading}
        workerSettingValue={workerSettingValue}
        t={t}
      />
      <div className={cx('info')}>
        <img
          src='/images/icon/00-ic-gray-info.svg'
          alt='info'
          width={16}
          height={16}
        />
        <div className={cx('text-desc')}>
          <div className={cx('desc')}>
            <span className={cx('title')}>{t('callCount.label')}</span>
            <span className={cx('content')}>
              {t('deploymentWorker.preview.callCountInfo')}
            </span>
          </div>
          <div className={cx('desc')}>
            <span className={cx('title')}>{t('abnormalProcessing.label')}</span>
            <span className={cx('content')}>
              {t('deploymentWorker.preview.abnormalProcessingInfo')}
            </span>
          </div>
        </div>
      </div>
      <ul className={cx('worker-list')}>
        {!workerList && (
          <div className={cx('loading-box')}>
            <Loading />
          </div>
        )}
        {workerList &&
          workerList.map((worker, idx) => {
            if (worker.worker_status.status !== 'stop') {
              let memGraphData = {};
              let cpuGraphData = {};
              let gpuGraphData = [];

              // 미리보기가 열려있을때만 연산 실행
              if (overviewList[worker.deployment_worker_id] === true) {
                const gpu = worker.running_info[3].gpus;
                const gpuHistoryInfo = Object.keys(gpu);
                const memHistory = worker.running_info[9].mem_history;
                const cpuHistory = worker.running_info[10].cpu_history;
                const gpuHistory = worker.running_info[11].gpu_history;

                // RAM 그래프 차트 data
                const memUsagePer = [];
                memHistory.forEach((mem, idx) => {
                  const { x, mem_usage_per } = mem;
                  memUsagePer[idx] = {
                    x,
                    y: mem_usage_per,
                  };
                });

                memGraphData = {
                  max: 100, // Number(worker.running_info[2].ram.split(' ')[0].replace('Gi', '')),
                  chartData: [
                    {
                      id: 'mem_usage_per',
                      color: 'rgba(255, 0, 0, 0.7)',
                      data: memUsagePer,
                    },
                  ],
                };

                const cpuData = [];
                cpuHistory.forEach((cpu, idx) => {
                  const { x, cpu_usage_on_pod } = cpu;
                  cpuData[idx] = {
                    x,
                    y: cpu_usage_on_pod,
                  };
                });

                cpuGraphData = {
                  max: 100, // Number(worker.running_info[1].cpu_coures.split(' ')[0]),
                  chartData: [
                    {
                      id: 'cpu_usage_on_pod',
                      data: cpuData,
                    },
                  ],
                };

                Object.keys(gpuHistory).forEach((gpus, i) => {
                  const gpuUtilData = [
                    {
                      id: 'util_gpu',
                      color: 'rgba(0, 0, 255, 0.7)',
                      data: [],
                    },
                    {
                      id: 'util_memory',
                      color: 'rgba(0, 255, 0, 0.7)',
                      data: [],
                    },
                  ];
                  const gpuMemData = [
                    {
                      id: 'memory_used',
                      color: 'rgba(0, 255, 0, 0.7)',
                      data: [],
                    },
                  ];
                  gpuHistory[gpus].forEach((gpu, idx) => {
                    const { x, memory_used, util_gpu, util_memory } = gpu;
                    gpuUtilData[0].data[idx] = {
                      x,
                      y: util_gpu,
                    };
                    gpuUtilData[1].data[idx] = {
                      x,
                      y: util_memory,
                    };
                    gpuMemData[0].data[idx] = {
                      x,
                      y: memory_used,
                    };
                  });
                  gpuGraphData[i] = {
                    gpuUtil: gpu[gpuHistoryInfo[i]].utils_gpu,
                    totalMemory: gpu[gpuHistoryInfo[i]].memory_total,
                    usedMemory: gpu[gpuHistoryInfo[i]].memory_used,
                    usedMemoryRatio: gpu[gpuHistoryInfo[i]].memory_used_ratio,
                    gpuChart: {
                      max: 100,
                      chartData: gpuUtilData,
                    },
                    memChart: {
                      max: gpu[gpuHistoryInfo[i]].memory_total,
                      chartData: gpuMemData,
                    },
                  };
                });
              }

              return (
                <li key={`${idx}-${worker.deployment_worker_id}`}>
                  <WorkerList
                    worker={worker}
                    workerStopPopup={workerStopPopup}
                    overview={overviewList[worker.deployment_worker_id]}
                    stopWorkerRequest={stopWorkerRequest}
                    memGraphData={memGraphData}
                    cpuGraphData={cpuGraphData}
                    gpuGraphData={gpuGraphData}
                    workerMemoModalHandler={workerMemoModalHandler}
                    workerStopConfirmPopupHandler={
                      workerStopConfirmPopupHandler
                    }
                    overviewHandler={overviewHandler}
                    moveToWorkerDetail={moveToWorkerDetail}
                    getSystemLogData={getSystemLogData}
                    systemLogLoading={systemLogLoading}
                    workerIds={workerIds}
                    t={t}
                    workerStopList={workerStopList}
                    cancelWorkerStopId={cancelWorkerStopId}
                    instanceType={instanceType}
                    workerSettingValue={workerSettingValue}
                  />
                </li>
              );
            }
            return (
              <Fragment
                key={`${idx}-${worker.deployment_worker_id}`}
              ></Fragment>
            );
          })}
      </ul>
    </div>
  );
}

export default DeployWorkerRunning;
