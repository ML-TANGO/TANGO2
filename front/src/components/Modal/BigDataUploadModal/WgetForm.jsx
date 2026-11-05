import { InputText } from '@jonathan/ui-react';

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
import style from './BigDataUploadModal.module.scss';

const cx = classNames.bind(style);

const WgetForm = ({
  wgetForm,
  handleWgetForm,
  datasetName,
  wgetFormError,
  loc,
}) => {
  const [spanWidth, setSpanWidth] = useState(datasetName.length * 10);
  const { t } = useTranslation();

  return (
    <div>
      {/* <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('folderCreate.label')}
          labelSize='large'
          errorMsg={wgetFormError.path}
        >
          <InputBoxWithLabel
            labelText={`/${datasetName}${loc}`}
            leftLabel={true}
            bgBox
          >
            <InputText
              size='large'
              name='wget_path'
              placeholder={t('folderName.placeholder')}
              value={wgetForm.path}
              onChange={(e) => handleWgetForm(e.target.value, 'path')}
              status={wgetFormError.path ? 'error' : 'default'}
            />
          </InputBoxWithLabel>
        </InputBoxWithLabel>
      </div> */}
      <div className={cx('row')}>
        <div className={cx('sub-title')}>{'URL'}</div>

        <InputText
          size='large'
          name='upload_url'
          placeholder={t('url.placeholder')}
          value={wgetForm.upload_url}
          onChange={(e) => handleWgetForm(e.target.value, 'upload_url')}
          status={wgetFormError.upload_url ? 'error' : 'default'}
        />
      </div>
    </div>
  );
};

export default WgetForm;
