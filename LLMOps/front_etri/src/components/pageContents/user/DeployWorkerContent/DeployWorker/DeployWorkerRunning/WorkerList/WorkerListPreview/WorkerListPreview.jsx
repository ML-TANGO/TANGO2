// Atom
import { BarChart, BarLineChart, Button, Tooltip } from '@tango/ui-react';

import { getKoreaTime } from '@src/datetimeUtils';

// CSS module
import classNames from 'classnames/bind';
import style from './WorkerListPreview.module.scss';

import downIcon from '@src/static/images/icon/00-ic-basic-arrow-02-down-blue.svg';
import upIcon from '@src/static/images/icon/00-ic-basic-arrow-02-up-blue.svg';
import warning from '@src/static/images/icon/00-ic-deploy-warning.svg';

const cx = classNames.bind(style);

function WorkerListPreview({
  deploymentWorkerId,
  workerStatus: { status, reason, resolution },
  changed,
  changedItems,
  overview,
  installing,
  isPending,
  runningInfo,
  workerStopConfirmPopupHandler,
  overviewHandler,
  mouseOver,
  mouseOut,
  getSystemLogData,
  systemLogLoading,
  workerIds,
  t,
  startDateTime,
  instance,
  workerStopPopup,
  openStopPopup,
  workerStopList,
  instanceType,
}) {
  const previewChart = [
    {
      label: 'callCount.label',
      tootipLabel: 'deploymentWorker.preview.callCountInfo',
    },
    {
      label: 'abnormalProcessing.label',
      tootipLabel: 'deploymentWorker.preview.abnormalProcessingInfo',
    },
  ];

  const makeLeftChartData = () => {
    const callCntChart = runningInfo[5].call_count_chart;
    const medianChart = runningInfo[6].median_chart;
    const arr = [];
    callCntChart.forEach((data, idx) => {
      arr[idx] = {
        callCnt: data,
        xAxisData: idx,
      };
    });
    medianChart.forEach((data, idx) => {
      arr[idx] = {
        ...arr[idx],
        median: data,
      };
    });
    const makeData = {
      lineDataSelector: 'median',
      barDataSelector: 'callCnt',
      xAxisSelector: 'xAxisData',
      data: arr,
    };
    return makeData;
  };

  const makeRightChartData = () => {
    const nginx = runningInfo[7].nginx_abnormal_count_chart;
    const abnormalCnt = runningInfo[8].api_monitor_abnormal_count_chart;
    const arr = [];
    nginx.forEach((data, idx) => {
      arr[idx] = {
        ...arr[idx],
        barData: [
          {
            value: data,
            color: '#CCFCC',
          },
        ],
      };
    });
    abnormalCnt.forEach((data, idx) => {
      arr[idx] = {
        ...arr[idx],
        barData: [
          ...arr[idx].barData,
          {
            value: data,
            color: '#9999FF',
          },
        ],
      };
    });
    const makeData = {
      xAxisSelector: 'xAxisData',
      dataSelector: 'barData',
      data: arr,
    };

    return makeData;
  };

  const renderWorkerMessage = () => {
    if (instanceType === 'NPU') {
      return t('worker.npuResource.desc');
    } else if (instance?.gpu_name) {
      return t('worker.gpuresource.desc');
    } else {
      return t('worker.cpuramresource.desc');
    }
  };

  return (
    <div
      className={cx(
        'preview',
        `${
          isPending || workerStopList.includes(deploymentWorkerId)
            ? 'pending'
            : ''
        }`,
        `${overview ? 'overview' : ''}`,
        `${installing ? 'installing' : ''}`,
        `${status === 'error' ? 'error' : ''}`,
      )}
    >
      <div className={cx('left')}>
        <div className={cx('worker-status')}>
          {/* {changed === true && (
            <Tooltip
              icon={error}
              iconCustomStyle={{
                width: '20px',
                height: '20px',
              }}
              contentsAlign={{ vertical: 'top' }}
              contents={changedItems.map(
                (
                  { item, current_version: current, latest_version: latest },
                  idx,
                ) => (
                  <div key={idx} className={cx('tooltip-contents-box')}>
                    <label>[{t(`${_.camelCase(item)}.label`)}]</label>
                    <div>
                      <b>{t('currentVersion.label')}:</b>{' '}
                      {current && typeof current === 'object'
                        ? Object.keys(current).join(', ')
                        : Array.isArray(current)
                        ? current.join(', ')
                        : current || '-'}
                    </div>
                    <div>
                      <b>{t('latestVersion.label')}:</b>{' '}
                      {latest && typeof latest === 'object'
                        ? Object.keys(latest).join(', ')
                        : Array.isArray(latest)
                        ? latest.join(', ')
                        : latest || '-'}
                    </div>
                  </div>
                ),
              )}
            />
          )} */}
        </div>
        <div className={cx('overview-append-btn')}>
          {!installing && !isPending && (
            <img
              src={overview ? upIcon : downIcon}
              alt=''
              onClick={() => {
                overviewHandler(deploymentWorkerId);
              }}
              onMouseOver={() => {
                mouseOver('preview');
              }}
              onMouseOut={() => {
                mouseOut('preview');
              }}
            />
          )}
          {(installing || isPending) && <div className={cx('empty-box')}></div>}
        </div>
        <div className={cx('btn-box')}>
          <div className={cx('system-log-btn')}>
            <Button
              type='primary-reverse'
              onClick={() => getSystemLogData(deploymentWorkerId)}
              onMouseOver={() => {
                mouseOver('stop');
              }}
              onMouseOut={() => {
                mouseOut('stop');
              }}
              loading={
                systemLogLoading && workerIds.includes(deploymentWorkerId)
              }
              customStyle={{ fontFamily: 'SpoqaB' }}
            >
              {t('systemLog.label')}
            </Button>
          </div>
          <div className={cx('worker-stop-btn')}>
            {workerStopList.includes(deploymentWorkerId) && (
              <img
                className={cx('spinner')}
                src='/images/icon/00-ic-worker-spinner.svg'
                alt=''
              />
            )}
            {!workerStopList.includes(deploymentWorkerId) && (
              <button
                className={cx('btn')}
                disabled={status === 'stop'}
                onClick={() => {
                  if (overview) {
                    overviewHandler(deploymentWorkerId);
                  }
                  workerStopConfirmPopupHandler(deploymentWorkerId);
                  openStopPopup();
                }}
                onMouseOver={() => {
                  mouseOver('stop');
                }}
                onMouseOut={() => {
                  mouseOut('stop');
                }}
              >
                <span>{t('stop.label')}</span>
              </button>
            )}
          </div>
        </div>
      </div>
      <div className={cx('instance-info')}>
        <div className={cx('first-row')}>
          <div className={cx('circle', status)}></div>
          <div className={cx('worker-id', status)}>
            <span>
              {t('worker.label')} {deploymentWorkerId}
            </span>

            {status === 'error' && (
              <Tooltip
                icon={warning}
                iconCustomStyle={{
                  width: '20px',
                  height: '20px',
                  transform: 'translateY(-2px)',
                }}
                // contentsAlign={{ vertical: 'top' }}
                title={reason}
                contents={resolution}
              />
            )}
          </div>
        </div>
        <div className={cx('second-row')}>
          <span className={cx('start-time')}>
            {getKoreaTime(startDateTime)}
          </span>
          <div className={cx('info')}>
            <span className={cx('resource')}>
              {instanceType === 'NPU' ? 'vNPU' : 'vGPU'}
            </span>
            <span>{`${
              instance?.gpu_name
                ? `${instance?.gpu_name} x ${instance?.gpu_allocate}EA`
                : '-'
            }`}</span>
          </div>
          <div className={cx('info')}>
            <span className={cx('resource')}>vCPU</span>
            <span>
              {instance?.cpu_allocate ? `${instance?.cpu_allocate} Cores` : '-'}
            </span>
          </div>
          <div className={cx('info')}>
            <span className={cx('ram')}>RAM</span>
            <span>
              {instance?.ram_allocate ? `${instance?.ram_allocate} GB` : '-'}
            </span>
          </div>
        </div>
      </div>

      <div className={cx('right')}>
        {isPending && !workerStopList.includes(deploymentWorkerId) && (
          <div className={cx('status')}>
            <img
              src='/images/icon/00-ic-orange-history.svg'
              alt='history'
              width={24}
              height={24}
            />
            <span className={cx('text', 'pending')}>
              {renderWorkerMessage()}
            </span>
          </div>
        )}
        {workerStopList.includes(deploymentWorkerId) && (
          <div className={cx('status')}>
            <img
              src='/images/icon/00-ic-orange-history.svg'
              alt='history'
              width={24}
              height={24}
            />
            <span className={cx('text', 'pending')}>
              {t('worker.resource.clear.desc')}
            </span>
          </div>
        )}
        {installing && (
          <div className={cx('status')}>
            <img
              src='/images/icon/00-ic-green-installing.svg'
              alt='history'
              width={20}
              height={20}
            />
            <span className={cx('text', 'installing')}>
              {t('worker.installing.desc')}
            </span>
          </div>
        )}
        <div className={cx('chart')}>
          {!installing &&
            !isPending &&
            !workerStopList.includes(deploymentWorkerId) &&
            previewChart.map((chartInfo, idx) => (
              <div className={cx('chart-wrap')} key={idx}>
                <div className={cx('preview-chart')}>
                  <label>
                    {t(chartInfo.label)}
                    {/* <Tooltip
                      icon={alert}
                      iconCustomStyle={{
                        width: '20px',
                        height: '20px',
                      }}
                      contents={t(chartInfo.tootipLabel)}
                    /> */}
                  </label>
                  <label>{t('last24h.label')}</label>
                </div>
                <div className={cx('chart-area')}>
                  {idx === 0 && (
                    <BarLineChart
                      data={makeLeftChartData()}
                      width={460}
                      height={100}
                      barWidth={8}
                      barChartColor='rgba(100, 255, 100, 0.5)'
                      lineChartColor='rgba(0, 0, 255, 0.3)'
                      point={0}
                      isAxisDraw={false}
                      background='rgba(100, 150, 255, 0.1)'
                    />
                  )}
                  {idx === 1 && (
                    <BarChart
                      data={makeRightChartData()}
                      width={460}
                      height={100}
                      barWidth={8}
                      isAxisDraw={false}
                      background='rgba(100, 150, 255, 0.1)'
                    />
                  )}
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

export default WorkerListPreview;
