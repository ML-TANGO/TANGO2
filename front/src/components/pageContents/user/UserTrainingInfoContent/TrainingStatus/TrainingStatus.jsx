// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingStatus.module.scss';
const cx = classNames.bind(style);

function TrainingStatus({ trainingStatusList, allStop }) {
  const { t } = useTranslation();
  return (
    <div className={cx('training-status')}>
      <div className={cx('header')}>
        <span className={cx('title')}>
          {`${t('training.label')} ${t('status.label')}`}
        </span>
        <div className={cx('btn-wrap')}>
          <Button type='secondary' onClick={allStop}>
            {`${t('all.label')} ${t('stop.label')}`}
          </Button>
        </div>
      </div>
      <div className={cx('content')}>
        <ul className={cx('training-list')}>
          {trainingStatusList.map(
            (
              {
                type,
                docker_image: dockerImage,
                cpu_cores: cpuCores,
                network,
                memory,
                configurations,
                status,
              },
              key,
            ) => (
              <li className={cx('training-item')} key={key}>
                <span className={cx('status-icon', status.status)}></span>
                <div className={cx('item')}>
                  <div className={cx('label')}>{t('status.label')}</div>
                  <div className={cx('value')}>
                    {type} {status.status}
                  </div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('label')}>{t('dockerImage.label')}</div>
                  <div className={cx('value')}>{dockerImage || '-'}</div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('label')}>{t('network.label')}</div>
                  <div className={cx('value')}>{network || '-'}</div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('label')}>CPU Core</div>
                  <div className={cx('value')}>{cpuCores || '-'}</div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('label')}>RAM</div>
                  <div className={cx('value')}>{memory || '-'}</div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('label')}>GPU/CPU</div>
                  <div className={cx('value')}>{configurations || '-'}</div>
                </div>
              </li>
            ),
          )}
        </ul>
      </div>
    </div>
  );
}

export default TrainingStatus;
