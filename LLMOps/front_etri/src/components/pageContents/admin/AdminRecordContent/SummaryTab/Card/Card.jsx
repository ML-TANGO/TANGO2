// i18n

// Utils
import { Badge } from '@jonathan/ui-react';

import { convertDuration, convertLocalTime } from '@src/datetimeUtils';
import StorageIcon from '@src/static/images/icon/00-ic-filled-storage.svg';
import TimeIcon from '@src/static/images/icon/00-ic-record-time.svg';
import { useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { convertMBtoGB } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './Card.module.scss';

const cx = classNames.bind(style);

const handleFlip = (cardRef) => {
  cardRef.current = !cardRef.current;
};

const Card = ({ data }) => {
  const { t } = useTranslation();
  const {
    workspace_name: workspaceName,
    start_datetime: start,
    end_datetime: end,
    instance_usage,
    storage_usage,
    activation_time: activationTime,
    status,
  } = data;

  const cardRef = useRef(false);

  return (
    <li
      className={cx('card', cardRef.current && 'flip')}
      onClick={() => handleFlip(cardRef)}
    >
      <div className={cx('front-card')}>
        <div className={cx('status-box')}>
          <Badge
            label={t(status)}
            size='xl'
            type={status === 'active' ? 'green' : 'gray'}
            customStyle={{ marginBottom: '24px' }}
          />
          <p className={cx('name')}>{workspaceName}</p>
          <span className={cx('range')}>
            {convertLocalTime(start, 'YYYY-MM-DD HH:mm')} ~{' '}
            {convertLocalTime(end, 'YYYY-MM-DD HH:mm')}
          </span>
        </div>
        <div className={cx('content-info-box')}>
          <h3 className={cx('content-title')}>{t('record.lastmonth.usage')}</h3>
          <div className={cx('right-box')}>
            <div className={cx('info-item')}>
              <p className={cx('label')}>
                <img src={TimeIcon} alt='usage-time-icon' />
                <label>{t('recordTime.label')}</label>
              </p>
              <span className={cx('val')}>
                {convertDuration(Number(activationTime), 'h')}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div className={cx('scroll-cont')}>
        <div className={cx('back-card')}>
          <div className={cx('storage-cont')}>
            <div className={cx('storage-header-cont', 'pt-0')}>
              <img src={StorageIcon} alt='storageIcon' />
              <h3 className={cx('avg-time-txt')}>
                {t('average.storage.usage')}
              </h3>
            </div>
            <div className={cx('storage-instance-cont')}>
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
            <div className={cx('record-instance-cont')}>
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
    </li>
  );
};

export default Card;
