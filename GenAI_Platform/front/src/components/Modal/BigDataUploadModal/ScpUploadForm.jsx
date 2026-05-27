import { InputPassword, InputText } from '@jonathan/ui-react';

import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './BigDataUploadModal.module.scss';

const cx = classNames.bind(style);

const ScpUploadForm = ({
  scpForm,
  handleScpForm,
  datasetName,
  scpFormError,
  scpErrorMessage,
  loc,
}) => {
  const { t } = useTranslation();

  return (
    <div>
      <div className={cx('row')}>
        <div className={cx('sub-title')}>{t('accessUser.label')}</div>

        <div className={cx('account')}>
          <InputText
            size='large'
            name='username'
            placeholder={'ID'}
            value={scpForm.username}
            onChange={(e) => handleScpForm(e.target.value, 'username')}
            status={scpFormError.username ? 'error' : 'default'}
          />

          <InputPassword
            size='large'
            name='password'
            placeholder={'Password'}
            value={scpForm.password}
            onChange={(e) => handleScpForm(e.target.value, 'password')}
            status={scpFormError.password ? 'error' : 'default'}
          />
        </div>
      </div>
      <div className={cx('row')}>
        <div className={cx('sub-title')}>{t('remoteIp.label')}</div>
        <InputText
          size='large'
          name='ip'
          placeholder={t('remoteIp.placeholder')}
          value={scpForm.ip}
          onChange={(e) => handleScpForm(e.target.value, 'ip')}
          status={scpFormError.ip ? 'error' : 'default'}
        />
      </div>
      <div className={cx('row')}>
        <div className={cx('sub-title')}>{t('remoteFilePath.label')}</div>

        <InputText
          size='large'
          name='filePath'
          placeholder={t('folderName.placeholder')}
          value={scpForm['file_path']}
          onChange={(e) => handleScpForm(e.target.value, 'file_path')}
          status={scpFormError.file_path ? 'error' : 'default'}
        />
      </div>
    </div>
  );
};

export default ScpUploadForm;
