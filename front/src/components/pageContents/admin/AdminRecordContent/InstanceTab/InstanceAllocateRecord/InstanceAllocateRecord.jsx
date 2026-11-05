import { convertDuration } from '@src/datetimeUtils';
import StorageIcon from '@src/static/images/icon/00-ic-filled-storage.svg';
import TimeIcon from '@src/static/images/icon/00-ic-record-time.svg';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { convertMBtoGB } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InstanceAllocateRecord.module.scss';

const cx = classNames.bind(style);

const InstanceAllocateRecord = ({
  workspaceId,
  summary,
  isLoading,
  instance_allocation_histories,
}) => {
  const { t } = useTranslation();

  const { activation_time, instance_usage, storage_usage } = summary;

  return (
    <div className={cx('summary')}>
      <div className={cx('card')}>
        <div className={cx('rows', 'headers')}>
          <div className={cx('cell1', 'workspace')}>{t('workspace')}</div>
          <div className={cx('cell2', 'usage-time')}>{t('usageTime')}</div>
          <div className={cx('cell3', 'instance')}>{t('Instance')}</div>
        </div>
        <div
          className={cx(
            'gpu-allocation-list',
            instance_allocation_histories.length === 0 && 'center',
          )}
        >
          {/* {isLoading && <Spinner color='primary' size='lg' />} */}
          {!isLoading && instance_allocation_histories.length === 0 && (
            <>{t('noData.message')}</>
          )}
          {instance_allocation_histories.length !== 0 &&
            instance_allocation_histories.map(
              (
                { start_datetime, end_datetime, instances, workspace_name },
                idx,
              ) => (
                <div className={cx('rows', 'gpu-allocation-item')} key={idx}>
                  <div className={cx('cell1', 'workspace-content')}>
                    {workspace_name}
                  </div>
                  <div className={cx('cell2', 'usage-content')}>
                    <p>
                      <span className={cx('gray')}>{t('start.label')}</span>
                      <span className={cx('date')}>{start_datetime}</span>
                    </p>
                    <p>
                      <span className={cx('gray')}>{t('end.label')}</span>
                      <span className={cx('date')}>{end_datetime}</span>
                    </p>
                  </div>
                  <div className={cx('cell3', 'instance-content')}>
                    {instances.map(({ instance_info: iInfo }, idx) => (
                      <p key={idx}>
                        {iInfo.instance_name} x {iInfo.instance_count}EA
                      </p>
                    ))}
                  </div>
                </div>
              ),
            )}
        </div>
      </div>
      <div className={cx('avg-time-cont')}>
        <div className={cx('back-card')}>
          <div className={cx('usage-time-header-cont')}>
            <img src={TimeIcon} alt='usage-time-icon' />
            <span>{t('recordTime.label')}</span>
          </div>
          <div className={cx('storage-cont')}>
            <div className={cx('storage-header-cont')}>
              <img src={StorageIcon} alt='storageIcon' />
              <h3 className={cx('avg-time-txt')}>
                {t('average.storage.usage')}
              </h3>
            </div>
            <div
              className={cx(
                'storage-instance-cont',
                'borderBottom',
                (isLoading || storage_usage.length === 0) && 'center',
              )}
            >
              {storage_usage.length === 0 && <>{t('noData.message')}</>}
              {storage_usage &&
                storage_usage.map((info, idx) => (
                  <div className={cx('storage-instance')} key={idx}>
                    <p className={cx('instance-name-txt')}>
                      {info.storage_name}
                    </p>
                    <span className={cx('instance-memory-txt')}>
                      {convertMBtoGB(info.storage_utilization).toFixed(2)}GB
                    </span>
                  </div>
                ))}
            </div>
          </div>
          <div className={cx('record-instance-time-cont')}>
            <div className={cx('record-time-header-cont')}>
              <img src={TimeIcon} alt='record-time-icon' />
              <h3 className={cx('record-time-txt')}>
                {t('recordInstanceTime.label')}
              </h3>
            </div>
            <div
              className={cx(
                'record-instance-cont',
                'height-78',
                instance_usage.length === 0 && 'center',
              )}
            >
              {instance_usage.length === 0 && <>{t('noData.message')}</>}
              {instance_usage &&
                instance_usage.map((info, idx) => (
                  <div className={cx('record-instance')} key={idx}>
                    <p className={cx('record-name-txt')}>
                      {info.instance_name}
                    </p>
                    <span className={cx('record-memory-txt')}>
                      {convertDuration(Number(info.instance_time))}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InstanceAllocateRecord;
