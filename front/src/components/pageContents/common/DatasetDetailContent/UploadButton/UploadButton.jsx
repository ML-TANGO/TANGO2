import { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import Button from '@src/components/atoms/button/Button';

// CSS module
import classNames from 'classnames/bind';
import style from './UploadButton.module.scss';

const cx = classNames.bind(style);

const isGoogleUpload =
  import.meta.env.VITE_REACT_APP_GOOGLE_API_KEY &&
  import.meta.env.VITE_REACT_APP_GOOGLE_CLIENT_ID;

// 한림대 DB UPLOAD 버튼 추가용
const IS_HANLIM = import.meta.env.VITE_REACT_APP_MODE === 'hanlim';

function UploadButton({
  onFileUpload,
  onGoogleDrive,
  onGitHubClone,
  disabled,
  onDatabaseUpload,
}) {
  const { t } = useTranslation();
  const button = useRef(null);
  const [isOptionOpen, setIsOptionOpen] = useState(false);
  const handleClick = (e) => {
    if (
      button.current &&
      !ReactDOM.findDOMNode(button.current)?.contains(e.target)
    ) {
      setIsOptionOpen(false);
    }
  };
  useEffect(() => {
    document.addEventListener('click', handleClick, false);
    return () => {
      document.removeEventListener('click', handleClick, false);
    };
  });

  return (
    <div className={cx('upload')} ref={button}>
      <Button
        type='primary'
        onClick={() => {
          setIsOptionOpen(!isOptionOpen);
        }}
        disabled={disabled}
      >
        {t('uploadData.label')}
      </Button>
      {isOptionOpen && (
        <ul className={cx('options')}>
          <li className={cx('option_li')} onClick={onFileUpload}>
            <img
              className={cx('icon')}
              src='/images/icon/my_computer-icon.svg'
              alt='My Computer'
            />
            {t('myComputerUpload.label')}
          </li>
          {isGoogleUpload && (
            <li className={cx('option_li')} onClick={onGoogleDrive}>
              <img
                className={cx('icon')}
                src='/images/icon/google_drive-icon.svg'
                alt='Google Drive'
              />
              {t('googleDriveUpload.label')}
            </li>
          )}
          <li className={cx('option_li')} onClick={onGitHubClone}>
            <img
              className={cx('icon')}
              src='/images/icon/github-icon.svg'
              alt='GitHub'
            />
            {t('gitHubClone.label')}
          </li>
          {IS_HANLIM && (
            <li className={cx('option_li')} onClick={onDatabaseUpload}>
              <img
                className={cx('icon')}
                src='/images/icon/ic-database.svg'
                alt='DATABASE'
              />
              {t('databaseUpload.label')}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export default UploadButton;
