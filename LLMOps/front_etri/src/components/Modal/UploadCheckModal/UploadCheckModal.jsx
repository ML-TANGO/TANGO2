// Components
import { Button, Checkbox, Switch } from '@tango/ui-react';

import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './UploadCheckModal.module.scss';

const cx = classNames.bind(style);

function UploadCheckModal({
  show,
  onClose,
  checked,
  checkHandler,
  fileName,
  uploadType,
}) {
  const { t } = useTranslation();

  const handleCancel = () => {
    onClose(true, fileName); // 취소 버튼 클릭 시 true 값을 전달
  };

  if (!show) {
    return null;
  }

  const messageKey =
    uploadType === 0
      ? 'datasetFileExist.message'
      : 'datasetFolderExist.message';
  return (
    <div className={cx('modal-overlay')}>
      <div className={cx('modal-content', uploadType === 0 && 'folder')}>
        <div className={cx('header')}>
          <span>
            {/* {fileName}과 동일한 {uploadType === 0 ? '파일이' : '폴더가'}{' '}
            존재합니다. */}
            {t(messageKey, { fileName })}
          </span>
          <span>{t('datasetUploadType.message')}</span>
          <div className={cx('check')}>
            <Checkbox
              label={
                uploadType === 0
                  ? t('applyToAllFiles.label')
                  : t('applyToAllFolders.label')
              }
              checked={uploadType === 1 ? true : checked}
              onChange={() => {
                checkHandler(!checked);
              }}
              disabled={uploadType === 1}
            />
          </div>
        </div>

        <div className={cx('btn-box')}>
          <Button
            type='primary'
            customStyle={{ fontFamily: 'SpoqaR' }}
            onClick={() => {
              onClose('copy', fileName, checked);
            }}
          >
            {t('createCopy.label')}
          </Button>
          <Button
            type='primary-reverse'
            customStyle={{ border: '1px solid #2d76f8', fontFamily: 'SpoqaR' }}
            onClick={() => {
              onClose('overwrite', fileName, checked);
            }}
            // disabled={isDisabledBtn || isTempPath}
          >
            {t('overwrite.label')}
          </Button>

          <Button
            type='none-border'
            customStyle={{ fontFamily: 'SpoqaR' }}
            onClick={() => {
              onClose('cancel', fileName, checked);
            }}
            // disabled={isDisabledBtn || isTempPath}
          >
            {t('cancel.label')}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default UploadCheckModal;
