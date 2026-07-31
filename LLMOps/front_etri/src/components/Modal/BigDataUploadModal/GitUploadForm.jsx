import { InputText } from '@tango/ui-react';

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
import style from './BigDataUploadModal.module.scss';

const cx = classNames.bind(style);

const GitUploadForm = ({
  gitForm,
  handleGitForm,
  datasetName,
  handleGitCommand,
  gitCommend,
}) => {
  const [spanWidth, setSpanWidth] = useState(datasetName.length * 9);
  const { t } = useTranslation();

  return (
    <div>
      <div className={cx('row')}>
        <div className={cx('sub-title')}>{t('gitCommand.label')}</div>
        <Radio
          name='git'
          options={[
            { label: 'clone', value: 'clone' },
            { label: 'pull', value: 'pull' },
          ]}
          value={gitCommend}
          onChange={(e) => handleGitCommand(e.target.value)}
          isTranLabel={false}
        />
      </div>
      {/* {gitCommend === 'clone' && (
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('uploadSavePath.label')}
            labelSize='large'
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ width: `${spanWidth}px` }}>/{datasetName}</span>
              <InputText
                size='large'
                customStyle={{
                  width: `${692 - spanWidth}px`,
                }}
                name='name'
                placeholder={t('folderName.placeholder')}
                value={gitForm.uploadPath}
                onChange={(e) => handleGitForm(e.target.value, 'uploadPath')}
              />
            </div>
          </InputBoxWithLabel>
        </div>
      )} */}

      {/* {gitCommend === 'pull' && (
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('gitPullPath.label')}
            labelSize='large'
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ width: `${spanWidth}px` }}>/{datasetName}</span>
              <InputText
                size='large'
                customStyle={{
                  width: `${692 - spanWidth}px`,
                }}
                name='name'
                placeholder={t('folderName.placeholder')}
                value={gitForm.pullPath}
                onChange={(e) => handleGitForm(e.target.value, 'pullPath')}
              />
            </div>
          </InputBoxWithLabel>
        </div>
      )} */}

      {gitCommend === 'clone' && (
        <div className={cx('row')}>
          <div className={cx('sub-title')}>{t('gitRepositoryUrl.label')}</div>
          <InputText
            size='large'
            name='filePath'
            placeholder={t('gitRepositoryUrl.placeholder')}
            value={gitForm.url}
            onChange={(e) => handleGitForm(e.target.value, 'url')}
          />
        </div>
      )}

      <div className={cx('row')}>
        <div className={cx('sub-title')}>{t('gitReleaseType.label')}</div>
        <Radio
          name='disclosure'
          options={[
            { label: 'public', value: 'public' },
            { label: 'private', value: 'private' },
          ]}
          value={gitForm.disclosure}
          onChange={(e) => handleGitForm(e.target.value, 'disclosure')}
          isTranLabel={false}
        />
      </div>
      {gitForm.disclosure === 'private' && (
        <div className={cx('row')}>
          <div className={cx('sub-title')}>{t('accessInfo.label')}</div>
          <div className={cx('account')}>
            <InputText
              size='large'
              name='id'
              placeholder={'ID'}
              value={gitForm.id}
              onChange={(e) => handleGitForm(e.target.value, 'id')}
            />
            {/* <div style={{ marginTop: '10px' }}></div> */}
            <InputText
              size='large'
              name='password'
              placeholder={'Password (or Access Token)'}
              value={gitForm.password}
              onChange={(e) => handleGitForm(e.target.value, 'password')}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default GitUploadForm;
