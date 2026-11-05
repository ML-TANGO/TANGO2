// Components
import { ButtonV2 } from '@jonathan/ui-react';

import { Fragment, useRef } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './Folder.module.scss';

const cx = classNames.bind(style);

const noop = () => {};

const Folder = ({
  status,
  label,
  onChange = noop,
  onRemove = noop,
  name,
  btnText = 'browse.label',
  value,
  error,
  progressRef,
  progressRefs,
  index,
  directory,
  folderList = true,
  t,
  uploadedDataName,
  uploadedDataIndex,
  checkLoading,
}) => {
  let directoryOption = {};
  if (directory) {
    directoryOption = {
      webkitdirectory: 'true',
      mozdirectory: 'true',
      directory: 'true',
    };
  }
  const folderInput = useRef(null);
  const triggerInputFile = () => folderInput.current.click();
  return (
    <div
      className={`fb input folder ${!status ? '' : status} ${cx(
        'input-wrap',
        !folderList && 'flex-wrap',
      )} `}
    >
      {label && <label className='fb label'>{t(label)}</label>}
      {uploadedDataIndex && uploadedDataIndex !== 1 && (
        <hr
          style={{ border: '0px', height: '1px', backgroundColor: '#dbdbdb' }}
        />
      )}
      {!uploadedDataName && (
        <div className={cx('input-wrap', 'folder-input-wrap')}>
          <input
            style={{ display: 'none' }}
            ref={folderInput}
            type='file'
            onChange={(e) => {
              const theFiles = e.target.files;
              const relativePath = theFiles[0].webkitRelativePath;
              const folder = relativePath.split('/')[0];
              onChange([...e.target.files], folder);
              e.target.value = '';
            }}
            name={name}
            {...directoryOption}
          />
          {/* <Button
            type='primary-reverse'
            customStyle={{
              border: '1px solid #2d76f8',
              padding: '8px 16px',
              height: '28px',
              width: '118px',
              fontFamily: 'SpoqaB',
              fontSize: '14px',
            }}
            size='medium'
            onClick={triggerInputFile}
          >
            {t(btnText)}
          </Button> */}

          <ButtonV2
            type='outline'
            size='l'
            label={t(btnText)}
            onClick={triggerInputFile}
          />
          <div className={cx('info-box')}>
            <span className={cx('error')}>{error && t(error)}</span>
          </div>
          <div className={cx('check')}>
            {checkLoading && t('datasetFileCheck.message')}
          </div>
        </div>
      )}
      <div>
        {folderList && folderList.length > 0 ? (
          <ul className={cx('folder-list')}>
            {value &&
              value.map((folderName, idx) => (
                <li key={idx}>
                  <span className={cx('folder-name')}>{folderName}</span>
                  <button
                    className={cx('remove-btn')}
                    onClick={() => {
                      onRemove(folderName, idx);
                    }}
                  >
                    <img src='/images/icon/close.svg' alt='X' />
                  </button>
                </li>
              ))}
          </ul>
        ) : (
          value && (
            <div>
              {value.map((folderName, idx) => (
                <div key={idx}>
                  {idx < 5 && (
                    <div className={cx('one-folder-name')}>
                      <span className={cx('folder-name')}>
                        {idx + 1}.&nbsp; {folderName}
                      </span>
                      <button
                        className={cx('remove-btn')}
                        onClick={() => {
                          onRemove(folderName, idx);
                        }}
                      >
                        <img src='/images/icon/close.svg' alt='X' />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {value.length > 5 && (
                <span className={cx('folder-more')}>
                  &amp; {value.length - 5} more
                </span>
              )}
            </div>
          )
        )}
        {uploadedDataName != null && (
          <>
            <div className={cx('one-folder-name')}>
              <span className={cx('folder-name')}>{uploadedDataName}</span>
              <button
                className={cx('remove-btn')}
                onClick={() => {
                  onRemove(uploadedDataName);
                }}
              >
                <img src='/images/icon/close.svg' alt='X' />
              </button>
            </div>
          </>
        )}
        {progressRef && (
          <span className={cx('progress')} ref={progressRef}></span>
        )}
        {progressRefs && value.length !== 0 && (
          <span
            className={cx('progress')}
            ref={(ref) => {
              // eslint-disable-next-line no-param-reassign
              progressRefs[index] = ref;
            }}
          ></span>
        )}
      </div>
    </div>
  );
};

export default withTranslation()(Folder);
