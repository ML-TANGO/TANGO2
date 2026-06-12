// i18n
// import { Button } from '@tango/ui-react';

// Utils
import { useTranslation } from 'react-i18next';

import { calcDuration, convertLocalTime } from '@src/datetimeUtils';

// import Status from '../Status';

// Components

import classNames from 'classnames/bind';
// CSS module
import style from './JobListContent.module.scss';

import BuildIcon from '@src/static/images/icon/00-build-green.svg';
import HistoryIcon from '@src/static/images/icon/00-history-orange.svg';
import LoadingImage from '@src/static/images/icon/00-ic-red-spinner.svg';

const cx = classNames.bind(style);

const calRunningStatusMessage = (status, resourceType, isLoadingStopBtn, t) => {
  if (isLoadingStopBtn.current) {
    return t('joblist.exit.message');
  }

  if (status === 'installing') {
    return t('joblist.installing.message');
  }

  if (['shceduling', 'pending'].includes(status)) {
    if (resourceType === 'cpu') return t('joblist.cpu.pending.message');
    return t('joblist.gpu.pending.message');
  }
  return '';
};

const JobListContent = ({
  trainingId,
  trainingType,
  jobName,
  data,
  status,
  onViewLog,
  startTime,
  endTime,
  checked,
  logFile,
  onStopJob,
  isLoadingStopBtn,
  resourceType,
  toolData,
  checkpointIsOpen,
  onCreateDeployment,
  jobIdx,
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('group-contents', checked && 'selected')}>
      <div className={cx('list-item')}>
        <div className={cx('left-column')}>
          <div className={cx('flex-cont')}>
            <div className={cx('stop-btn-cont')}>
              {isLoadingStopBtn.current && (
                <img
                  className={cx('loading')}
                  src={LoadingImage}
                  alt='loading'
                />
              )}
              {!isLoadingStopBtn.current && status.status === 'running' && (
                <img
                  className={cx('job-stop-btn')}
                  src='/images/icon/00-ic-basic-stop-o.svg'
                  alt='stop'
                  onClick={() => {
                    if (status.status === 'running')
                      onStopJob(trainingId, isLoadingStopBtn);
                  }}
                />
              )}
              {!isLoadingStopBtn.current && status.status !== 'running' && (
                <img
                  className={cx('job-stop-btn', 'disabled')}
                  src='/images/icon/00-ic-basic-stop-o.svg'
                  alt='stop'
                />
              )}
            </div>
            <div className={cx('parameters')}>
              {['installing', 'pending', 'shceduling'].includes(
                status.status,
              ) ? (
                <div className={cx('status-message-cont')}>
                  <img
                    src={
                      status.status === 'installing' ? BuildIcon : HistoryIcon
                    }
                    alt='running-message-icon'
                  />
                  <p
                    className={cx(
                      'running-message-paragraph',
                      status.status === 'installing' ? 'green' : 'orange',
                    )}
                  >
                    {calRunningStatusMessage(
                      status.status,
                      resourceType,
                      isLoadingStopBtn,
                      t,
                    )}
                  </p>
                </div>
              ) : (
                <div className={cx('hyper-param')}>
                  <label className={cx('param-label')}>학습 시간</label>
                  <div className={cx('flex-cont')}>
                    <div className={cx('params')}>
                      <div className={cx('datetime')}>
                        <span>
                          {startTime
                            ? `${convertLocalTime(startTime)} ~ `
                            : '-'}
                        </span>
                        <span>{endTime && convertLocalTime(endTime)}</span>
                      </div>
                    </div>
                    <span className={cx('duration')}>
                      {startTime && endTime
                        ? calcDuration(startTime, endTime)
                        : '-'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className={cx('parameters')}>
            <div className={cx('hyper-param')}>
              <label className={cx('param-label')}>
                {t('jobRunningParameter.label')}
              </label>
              <div className={cx('params')}>
                {data.length > 0
                  ? data.map(({ key, value }, idx) => {
                      return (
                        <div key={idx} className={cx('item')}>
                          <label className={cx('param')}>{key}</label>
                          <span className={cx('value')}>{value}</span>
                        </div>
                      );
                    })
                  : '-'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default JobListContent;
