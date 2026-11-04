import { Fragment } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { toast } from '@src/components/Toast';
import { CopyToClipboard } from 'react-copy-to-clipboard';

// CSS Module
import classNames from 'classnames/bind';
import style from './UsageStatus.module.scss';
const cx = classNames.bind(style);

function UsageStatus({ usageStatusInfo, permissionLevel, openEditApiModal }) {
  const { t } = useTranslation();
  const { api_address: apiAddress, worker_count: WorkerCount } =
    usageStatusInfo;

  const onCopy = () => {
    toast.success(t('copyToClipboard.success.message'));
  };

  return (
    <div className={cx('deployment-usage-status')}>
      <div className={cx('header')}>
        <span className={cx('title')}>{t('usageStatus.label')}</span>
      </div>
      <div className={cx('content')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('workerCount.label')}</div>
          <div className={cx('value')}>{WorkerCount || 0}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('apiAddress.label')}</div>
          <div className={cx('value-box')}>
            <span className={cx('value', 'api-address')}>
              {apiAddress || '-'}
            </span>
            {apiAddress && (
              <Fragment>
                <CopyToClipboard text={apiAddress} onCopy={onCopy}>
                  <button
                    className={cx('btn', 'copy-btn')}
                    title={t('copyToClipboard.message')}
                  ></button>
                </CopyToClipboard>
                {/* <button
                  className={cx('btn', 'edit-btn')}
                  onClick={openEditApiModal}
                  disabled={permissionLevel > 3}
                ></button> */}
              </Fragment>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default UsageStatus;
