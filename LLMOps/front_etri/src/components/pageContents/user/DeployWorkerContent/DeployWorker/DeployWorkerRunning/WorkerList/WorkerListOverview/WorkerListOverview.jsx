// Components
import { Tooltip } from '@tango/ui-react';

import DeployLineChart from '@src/components/molecules/DeployChart/DeployLineChart';

import OverviewGPUChart from './OverviewGPUChart';

// Utils
import { numberWithCommas } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './WorkerListOverview.module.scss';

// Icons
import alert from '@src/static/images/icon/00-ic-alert-info-o.svg';

const cx = classNames.bind(style);

function WorkerListOverview({
  memGraphData,
  cpuGraphData,
  gpuGraphData,
  description,
  deploymentWorkerId,
  workerStatus: { restart_count: restartCount, status },
  runningInfo,
  workerMemoModalHandler,
  t,
  installing,
  isPending,
}) {
  return (
    <div
      className={cx(
        'overview',
        `${isPending ? 'pending' : ''}`,
        `${installing ? 'installing' : ''}`,
        `${status === 'error' ? 'error' : ''}`,
      )}
    >
      <div className={cx('left')}>
        <div className={cx('info')}>
          <div className={cx('overview-info')}>
            {runningInfo[0].configurations}
          </div>
          <div className={cx('restart')}>
            <span className={cx('restart-cnt-label')}>
              {t('restartCount.label')}
            </span>
            <div className={cx('overview-info')}>
              {numberWithCommas(restartCount)}
            </div>
          </div>
          <div className={cx('notice')}>
            <img
              src='/images/icon/00-ic-gray-info.svg'
              alt='notice'
              width={12}
              height={12}
            />
            <span>{t('deploymentWorker.overview.restartCountInfo')}</span>
          </div>
        </div>
        <div className={cx('memo')}>
          <div className={cx('memo-controler')}>
            <span>{t('memo.label')}</span>
            <img
              src='/images/icon/00-ic-gray-pencil.svg'
              alt='pencil'
              onClick={() => {
                workerMemoModalHandler(deploymentWorkerId, description);
              }}
              width={16}
              height={16}
              className={cx('pencil-icon')}
            />
          </div>
          <div className={cx('memo-output')}>{description}</div>
        </div>
      </div>
      <div className={cx('right')}>
        <div className={cx('chart-wrap')}>
          <div className={cx('overview-chart', 'ram')}>
            <div className={cx('chart-label')}>
              <label>
                RAM : <span className={cx('value')}>{runningInfo[2].ram}</span>
              </label>
              <label>{t('last5m.label')}</label>
            </div>
            <div className={cx('chart-area')}>
              <DeployLineChart
                data={memGraphData}
                height={208}
                width={460}
                enableGridX={false}
                enableGridY={false}
                filled={true}
              />
            </div>
          </div>
          <div className={cx('overview-chart', 'cpu')}>
            <div className={cx('chart-label')}>
              <label>
                CPU :{' '}
                <span className={cx('value')}>{runningInfo[1].cpu_cores}</span>
              </label>
              <label>{t('last5m.label')}</label>
            </div>
            <div className={cx('chart-area')}>
              <DeployLineChart
                data={cpuGraphData}
                width={460}
                height={208}
                enableGridX={false}
                enableGridY={false}
                filled={true}
              />
            </div>
          </div>
          {gpuGraphData && gpuGraphData.length > 0 && (
            <OverviewGPUChart gpuGraphData={gpuGraphData} t={t} />
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkerListOverview;
