// i18n
import { Tooltip } from '@jonathan/ui-react';

import { convertDuration, convertSeconds } from '@src/datetimeUtils';
// Icons
import error from '@src/static/images/icon/icon-error-c-red.svg';
import { useTranslation } from 'react-i18next';

// Components
import ResourceUsageChart from '@src/components/molecules/ResourceUsageChart';

// utils
import { convertBinaryByte, numberWithCommas } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeployStatusCard.module.scss';

const cx = classNames.bind(style);

/**
 * 배포 대시보드 상단 카드 형태 데이터
 * 
 * @param {object} totalInfoData 
 * ex) totalInfoData = {
    total_call_count: 4,
    total_success_rate: 1,
    total_log_size: 1235323,
    running_worker_count: 1,
    error_worker_count: 0,
    deployment_run_time: 146267,
    restart_count: 0,
  }
 * @param {object} resourceInfoData 
 * ex) resourceInfoData = {
 * 
    cpu_usage_rate: {
      min: 6.2,
      max: 6.2,
      average: 6.2,
    },
    ram_usage_rate: {
      min: 24.7,
      max: 24.7,
      average: 24.7,
    },
    gpu_mem_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    gpu_core_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    gpu_total_mem: 0,
    gpu_use_mem: 0,
    gpu_mem_unit: 'MiB',
  }
 * @returns 
 */

function DeploymentStatusCard({
  type,
  totalInfoData,
  resourceInfoData,
  visibleUsageChart = true,
  isWorker = false,
}) {
  const { t } = useTranslation();
  const {
    deployment_run_time: totalOperationTime,
    total_call_count: totalCall,
    total_log_size: totalLogSize,
    total_success_rate: successfulResponse,
    running_worker_count: runningWorkers,
    error_worker_count: errorWorkers,
    restart_count: restartCount,
  } = totalInfoData;
  const {
    cpu_usage_rate: cpuUsageRate,
    ram_usage_rate: ramUsageRate,
    gpu_core_usage_rate: gpuCoreUsage,
    gpu_mem_usage_rate: gpuMemUsage,
    gpu_total_mem: gpuTotalMem,
    gpu_use_mem: gpuUseMem,
    gpu_mem_unit: gpuMemUnit,
  } = resourceInfoData;

  return (
    <div className={cx('status-box')}>
      {totalInfoData && (
        <div className={cx('grid-container', 'total-info')}>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>
                {t(
                  `${
                    isWorker ? 'deploymentWorker.' : ''
                  }totalOperationTime.label`,
                )}
              </label>
              <Tooltip
                contents={t(
                  `${
                    isWorker ? 'deploymentWorker.' : ''
                  }totalOperationTime.tooltip.message`,
                )}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <div className={cx('value')}>
              {totalOperationTime > 0
                ? convertSeconds(totalOperationTime)
                : '0 days 00:00:00'}
            </div>
          </div>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('totalCall.label')}</label>
              <Tooltip
                contents={t('totalCall.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <div className={cx('value')}>
              {totalCall > 10000
                ? `${(totalCall / 1000).toFixed(1)}K`
                : totalCall}
              <span className={cx('size')}>
                {convertBinaryByte(totalLogSize)}
              </span>
            </div>
          </div>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('successfulResponse.label')}</label>
              <Tooltip
                contents={t('successfulResponse.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <div className={cx('value')}>{successfulResponse}%</div>
          </div>
          {isWorker ? (
            <div className={cx('card')}>
              <div className={cx('label')}>
                <label>{t('restartCount.label')}</label>
                <Tooltip
                  contents={t('restartCount.tooltip.message')}
                  contentsAlign={{ horizontal: 'right' }}
                  iconCustomStyle={{ width: '20px' }}
                />
              </div>
              <div className={cx('value')}>
                {numberWithCommas(restartCount)}
              </div>
            </div>
          ) : (
            <div className={cx('card')}>
              <div className={cx('label')}>
                <label>{t('runningWorkers.label')}</label>
              </div>
              <div className={cx('value')}>
                {runningWorkers}
                {errorWorkers > 0 && (
                  <span className={cx('error')}>
                    <img
                      src={error}
                      alt='error'
                      style={{
                        width: '14px',
                        height: '14px',
                      }}
                    />
                    {`${errorWorkers} worker${
                      errorWorkers > 1 ? 's are' : ' is'
                    } in error`}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      {resourceInfoData && visibleUsageChart && (
        <div className={cx('grid-container', 'usage-info')}>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('cpuUsageRate.label')}</label>
              <Tooltip
                contents={t('cpuUsageRate.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <ResourceUsageChart data={cpuUsageRate} tagId='cpu-usage' />
          </div>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('ramUsageRate.label')}</label>
              <Tooltip
                contents={t('ramUsageRate.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <ResourceUsageChart data={ramUsageRate} tagId='ram-usage' />
          </div>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('gpuCoreUsageRate.label')}</label>
              <Tooltip
                contents={t('gpuCoreUsageRate.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <ResourceUsageChart data={gpuCoreUsage} tagId='gpu-core-usage' />
          </div>
          <div className={cx('card')}>
            <div className={cx('label')}>
              <label>{t('gpuMemUsageRate.label')}</label>
              <Tooltip
                contents={t('gpuMemUsageRate.tooltip.message')}
                contentsAlign={{ horizontal: 'right' }}
                iconCustomStyle={{ width: '20px' }}
              />
            </div>
            <ResourceUsageChart
              data={gpuMemUsage}
              size={`${gpuUseMem}/${gpuTotalMem}${gpuMemUnit}`}
              tagId='gpu-mem-usage'
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default DeploymentStatusCard;
