// Components
import { Button, ButtonV2 } from '@tango/ui-react';

import { Fragment, useRef } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

import { convertByte } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './File.module.scss';

const cx = classNames.bind(style);

const noop = () => {};

const File = ({
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
  fileList = true,
  single,
  disabled,
  t,
  uploadedDataName,
  uploadedDataIndex,
  labelStyle,
  flexStyle = 'col',
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
  const fileInput = useRef(null);
  const triggerInputFile = () => fileInput.current.click();
  return (
    <div
      className={`fb input file ${!status ? '' : status} ${cx(
        'input-wrap',
        !fileList && 'flex-wrap',
      )} `}
      style={{
        display: flexStyle === 'row' && 'flex',
        alignItems: flexStyle === 'row' && 'center',
        marginTop: flexStyle === 'row' && '16px',
      }}
    >
      {label && (
        <label className={cx('fb', 'label')} style={labelStyle}>
          {t(label)}
        </label>
      )}
      {uploadedDataIndex && uploadedDataIndex !== 1 && (
        <hr
          style={{ border: '0px', height: '1px', backgroundColor: '#dbdbdb' }}
        />
      )}
      {!uploadedDataName && (
        <div className={cx('input-wrap', 'file-input-wrap')}>
          <input
            style={{ display: 'none' }}
            ref={fileInput}
            type='file'
            onChange={(e) => {
              onChange([...e.target.files]);
              e.target.value = '';
            }}
            name={name}
            multiple={!single}
            disabled={disabled}
            {...directoryOption}
          />
          <ButtonV2
            type='outline'
            size='l'
            label={t(btnText)}
            disabled={disabled}
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
      <div className={cx('test')}>
        {fileList && value.length > 0 ? (
          <ul
            className={cx('file-list')}
            style={{
              marginTop: flexStyle === 'row' && 0,
            }}
          >
            {value &&
              value.map(({ name: fName, prev, size }, idx) => (
                <li
                  key={idx}
                  style={{
                    marginBottom: flexStyle === 'row' && '6px',
                  }}
                >
                  <span className={cx('file-name')}>{fName}</span>
                  <span
                    className={cx('file-name', 'file-size')}
                  >{`(${convertByte(size ?? 0)})`}</span>
                  {!disabled && (
                    <button
                      className={cx('remove-btn')}
                      onClick={() => {
                        onRemove(idx, prev);
                      }}
                    >
                      <img src='/images/icon/close.svg' alt='X' />
                    </button>
                  )}
                </li>
              ))}
          </ul>
        ) : (
          value && (
            <div>
              {value.map(({ name: fName }, idx) => (
                <div key={idx}>
                  {idx < 5 && (
                    <div className={cx('one-file-name')}>
                      <span className={cx('file-name')}>
                        {idx + 1}.&nbsp;
                        {fName}
                      </span>
                      <button
                        className={cx('remove-btn')}
                        onClick={() => {
                          onRemove(idx);
                        }}
                      >
                        <img src='/images/icon/close.svg' alt='X' />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {value.length > 5 && (
                <>
                  <span className={cx('file-more')}>
                    &amp; {value.length - 5} more
                  </span>
                </>
              )}
            </div>
          )
        )}
        {uploadedDataName != null && (
          <>
            <div className={cx('one-file-name')}>
              <span className={cx('file-name')}>{uploadedDataName}</span>
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

export default withTranslation()(File);
