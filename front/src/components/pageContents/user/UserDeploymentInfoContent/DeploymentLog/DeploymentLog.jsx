// i18n

// Components
import { Button } from '@jonathan/ui-react';

import { useTranslation } from 'react-i18next';

// Util
import { convertBinaryByte } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentLog.module.scss';

const cx = classNames.bind(style);

function DeploymentLog({
  logInfo,
  permissionLevel,
  openDownloadLogModal,
  openDeleteLogModal,
}) {
  const { t } = useTranslation();
  const { total_log_size: size } = logInfo;

  return (
    <div className={cx('deployment-log')}>
      <div className={cx('content')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('logSize.label')}</div>
          <div className={cx('value-box')}>
            <span className={cx('value')}>
              {size ? convertBinaryByte(size) : '-'}
            </span>
            {size > 0 && (
              <div className={cx('btn-box')}>
                <Button type='gray' onClick={openDownloadLogModal}>
                  {t('logDownload.label')}
                </Button>
                <Button
                  type='red-light'
                  onClick={openDeleteLogModal}
                  disabled={permissionLevel > 3}
                >
                  {t('logDelete.label')}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DeploymentLog;
