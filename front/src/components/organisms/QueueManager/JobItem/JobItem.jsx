// Components
import { Badge } from '@jonathan/ui-react';

// CSS Module
import style from './JobItem.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const JobItem = ({
  job_name: jobName,
  gpu_count: gpu,
  workspace_id: wId,
  training_id: tId,
  training_name: tName,
  executor,
  num_of_job: numOfJob,
  job_group_index: activeJob,
  moveToTarget,
  item_type: type,
  hideRemainingJob,
  t,
}) => {
  return (
    <li className={cx('job-item')}>
      <div className={cx('top')}>
        <div className={cx('title-wrap')}>
          <Badge
            label={'JOB'}
            type={'green'}
            customStyle={{ marginRight: '10px' }}
          />
          <span className={cx('title')}>{jobName}</span>
        </div>
        <button
          className={cx('move-to-job-btn')}
          onClick={() => {
            moveToTarget(wId, tId, tName, type);
          }}
        >
          {t ? t('moveToJob.label') : 'Move to Job'}
          <img src='/images/icon/ic-right.svg' alt='>'></img>
        </button>
      </div>
      <div className={cx('bottom')}>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('training.label') : 'Training'}</p>
          <span className={cx('value')}>{tName}</span>
        </div>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('gpus.label') : 'GPUs'}</p>
          <span className={cx('value')}>{gpu}</span>
        </div>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('creator.label') : 'Creator'}</p>
          <span className={cx('value')}>{executor}</span>
        </div>
      </div>
      <div className={cx('job-box')}>
        <div className={cx('info-group')}>
          <p className={cx('label')}>
            {t ? t('activeJob.label') : 'Active Job'}
          </p>
          <span className={cx('value')}>
            {activeJob > -1 ? activeJob + 1 : '-'}
          </span>
        </div>
        {!hideRemainingJob && (
          <div className={cx('info-group')}>
            <p className={cx('label')}>
              {t ? t('remainingJob.label') : 'Remaining Job'}
            </p>
            <span className={cx('value')}>{numOfJob}</span>
          </div>
        )}
      </div>
    </li>
  );
};

export default JobItem;
