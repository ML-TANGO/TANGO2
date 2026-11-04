// i18n
import { useTranslation } from 'react-i18next';

// Components
import Status from '@src/components/atoms/Status';

import { convertLocalTime } from '@src/datetimeUtils';

// CSS Module
import classNames from 'classnames/bind';
import style from './RoundList.module.scss';

const cx = classNames.bind(style);

function RoundList({ rounds = [] }) {
  const { t } = useTranslation();

  return (
    <div className={cx('list-wrapper')}>
      {rounds.map(
        ({
          round_info: roundInfo,
          round_global_model_meta: globalModelMeta,
        }) => {
          const {
            round_name: round,
            info: { training, broadcasting },
            stage,
          } = roundInfo;
          const {
            training: trainingStatus,
            aggregation: aggregationStatus,
            broadcasting: broadcastingStatus,
          } = stage;
          let activeStatus = 'flActive';
          if (trainingStatus === 1) {
            activeStatus = 'clientTraining';
          } else if (aggregationStatus === 1) {
            activeStatus = 'aggregation';
          } else if (broadcastingStatus === 1) {
            activeStatus = 'broadcasting';
          }
          return (
            <div key={round} className={cx('list-item')}>
              <div className={cx('status-box')}>
                <div className={cx('status-round')}>
                  <Status
                    status={
                      roundInfo.status === 'active'
                        ? activeStatus
                        : roundInfo.status
                    }
                    type='dark'
                    size='medium-long'
                  />
                  <div className={cx('round')}>
                    {t('round.label')} #{round}
                  </div>
                </div>
                <div className={cx('datetime')}>
                  {`${convertLocalTime(training.stage_start_datetime)} ~ 
                ${
                  broadcasting.completed_datetime
                    ? convertLocalTime(broadcasting.completed_datetime)
                    : ''
                }`}
                </div>
              </div>
              <div className={cx('info-box')}>
                <div className={cx('item')}>
                  <label className={cx('label')}>{t('seedModel.label')}</label>
                  <div className={cx('value')}>
                    {training.seed_model_round_name
                      ? `${t('round.label')} #${training.seed_model_round_name}`
                      : '-'}
                  </div>
                </div>
                <div className={cx('item')}>
                  <label className={cx('label')}>
                    {t('hpsParameters.label')}
                  </label>
                  <div className={cx('value', 'params')}>
                    {Object.keys(training?.hyperparameter).length > 0
                      ? Object.entries(training.hyperparameter)?.map(
                          ([key, value], idx) => {
                            return (
                              <div key={idx} className={cx('param')}>
                                <label className={cx('key')}>{key}</label>
                                <span className={cx('value')}>{value}</span>
                              </div>
                            );
                          },
                        )
                      : '-'}
                  </div>
                </div>
                <div className={cx('item')}>
                  <label className={cx('label')}>
                    {t('globalModel.label')}
                  </label>
                  <div className={cx('value', 'params')}>
                    {Object.keys(globalModelMeta?.metrics).length > 0
                      ? Object.entries(globalModelMeta.metrics)?.map(
                          ([key, value], idx) => {
                            return (
                              <div key={idx} className={cx('param')}>
                                <label className={cx('key')}>{key}</label>
                                <span className={cx('value')}>{value}</span>
                              </div>
                            );
                          },
                        )
                      : '-'}
                  </div>
                </div>
              </div>
            </div>
          );
        },
      )}
    </div>
  );
}

export default RoundList;
