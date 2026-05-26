// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';
import PageTitle from '@src/components/atoms/PageTitle';
import RoundList from './RoundList';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserFederatedLearningContent.module.scss';

const cx = classNames.bind(style);

function UserFederatedLearningContent({
  trainingName,
  isPermission,
  step,
  clientName,
  rounds,
  loading,
  onCreateContainer,
  onDeleteContainer,
  onJoinRequest,
  getContainerInfo,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('content')}>
      <div className={cx('title-box')}>
        <PageTitle>{trainingName}</PageTitle>
        <div className={cx('btn-box')}>
          <Button
            type='primary-light'
            size='medium'
            onClick={getContainerInfo}
            iconAlign='left'
            icon={
              loading[0]
                ? '/images/icon/spinner-1s-58.svg'
                : '/images/icon/ic-refresh-blue.svg'
            }
          >
            {t('refresh.label')}
          </Button>
        </div>
      </div>
      <div className={cx('content-box')}>
        <div className={cx('fl-box')}>
          <div className={cx('name-box')}>
            <div className={cx('icon')}>
              <img
                src='/images/logo/fl-logo-icon.svg'
                alt='FL icon'
              />
            </div>
            <label className={cx('label')}>Federated Learning</label>
          </div>
          <div className={cx('info-box')}>
            <ul className={cx('info-list')}>
              <li>
                <label className={cx('label')}>{t('clientName.label')}</label>
                <span className={cx('value')}>{clientName || '-'}</span>
              </li>
              <li>
                <label className={cx('label')}>{t('dataset.label')}</label>
                <span className={cx('value')}>federated-learning-dataset</span>
              </li>
              <li>
                <label className={cx('label')}>{t('latestRound.label')}</label>
                <span className={cx('value')}>
                  {step === 4 ? `#${rounds[0]?.round_info?.round_name}` : '-'}
                </span>
              </li>
            </ul>
            <div className={cx('btn-box')}>
              {step === 1 && (
                <div>
                  <Button
                    type='primary'
                    loading={loading[1]}
                    onClick={onCreateContainer}
                  >
                    {t('createContainer.label')}
                  </Button>
                </div>
              )}
              {(step === 2 || step === 3) && (
                <div>
                  <Button
                    type='primary'
                    loading={loading[2]}
                    disabled={step === 3}
                    onClick={onJoinRequest}
                  >
                    {step === 2
                      ? t('requestToJoin.label')
                      : t('waitingToJoin.label')}
                  </Button>
                </div>
              )}
              <Button
                type='red'
                loading={loading[3]}
                disabled={step === 1 || !isPermission}
                onClick={onDeleteContainer}
              >
                {t('deleteContainer.label')}
              </Button>
            </div>
          </div>
        </div>
        <div className={cx('round-box')}>
          <RoundList rounds={rounds} />
        </div>
      </div>
    </div>
  );
}

export default UserFederatedLearningContent;
