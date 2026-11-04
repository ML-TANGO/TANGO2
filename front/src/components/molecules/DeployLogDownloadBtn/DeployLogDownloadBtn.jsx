// Atoms
import { Button, Checkbox, Tooltip } from '@jonathan/ui-react';

import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Molecules
import DropMenu from '@src/components/molecules/DropMenu/DropMenu2';

// CSS Module
import classnames from 'classnames/bind';
import style from './DeployLogDownloadBtn.module.scss';

const cx = classnames.bind(style);

function DeployLogDownloadBtn({
  btnRender,
  logDownOptions,
  logDownOptionsHandler,
  logDownClickHandler,
  tooltipAlign = { vertical: 'top', horizontal: 'left' },
}) {
  const { t } = useTranslation();

  const [isOpenPopup, setIsOpenPopup] = useState(false);

  const popupHandler = (e) => {
    if (e) e.stopPropagation();
    if (isOpenPopup) {
      setIsOpenPopup(false);
    } else {
      setIsOpenPopup(true);
    }
  };

  return (
    <DropMenu
      btnRender={btnRender}
      popupHandler={popupHandler}
      isOpen={isOpenPopup}
      menuRender={() => (
        <>
          <div className={cx('log-download-wrapper')}>
            <div className={cx('check-box')}>
              <Checkbox
                label={t('logNginx.label')}
                checked={logDownOptions?.nginx}
                onChange={() => logDownOptionsHandler('nginx')}
              />
              <Tooltip
                contents={t('logNginx.tooltip.message')}
                contentsAlign={tooltipAlign}
              />
            </div>
            <div className={cx('check-box')}>
              <Checkbox
                label={t('logApi.label')}
                checked={logDownOptions?.api}
                onChange={() => logDownOptionsHandler('api')}
              />
              <Tooltip
                contents={t('logApi.tooltip.message')}
                contentsAlign={tooltipAlign}
              />
            </div>
            <div className={cx('button-box')}>
              <Button
                type='primary'
                customStyle={{
                  backgroundColor: '#DEE9FF',
                  border: 'none',
                  color: '#2D76F8',
                  fontWeight: 700,
                  width: '100%',
                }}
                disabled={(() => {
                  if (logDownOptions === undefined) {
                    return true;
                  }
                  if (
                    logDownOptions.nginx === false &&
                    logDownOptions.api === false
                  ) {
                    return true;
                  }
                  return false;
                })()}
                onClick={logDownClickHandler}
              >
                {t('download.label')}
              </Button>
            </div>
          </div>
        </>
      )}
      align='LEFT'
      customStyle={{ paddingBottom: '90px' }}
    />
  );
}

export default DeployLogDownloadBtn;
