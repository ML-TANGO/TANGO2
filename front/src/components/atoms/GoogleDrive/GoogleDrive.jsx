import { useState, Fragment, useEffect } from 'react';

// Google api
import GooglePicker from 'react-google-picker';

// CSS Module
import classNames from 'classnames/bind';
import style from './GoogleDrive.module.scss';
const cx = classNames.bind(style);

/** Google API */
const API_KEY = import.meta.env.VITE_REACT_APP_GOOGLE_API_KEY;
const CLIENT_ID = import.meta.env.VITE_REACT_APP_GOOGLE_CLIENT_ID;
const SCOPES = 'https://www.googleapis.com/auth/drive';

function GoogleDrive({
  onChange,
  t,
  datasetName,
  text,
  type = 'files',
  builtInGoogleChange,
  uploadedDataIndex,
  googleAccessTokenHandler,
  googleDriveDelete,
}) {
  const [selectedData, setSelectedData] = useState(null);
  const [accessToken, setAccessToken] = useState(null);

  const createPicker = (google, oauthToken) => {
    const googleViewId = google.picker.ViewId.FOLDERS;
    const docsView = new google.picker.DocsView(googleViewId)
      .setIncludeFolders(true)
      .setMimeTypes(`application/vnd.google-apps/${type}`)
      .setSelectFolderEnabled(true);
    setAccessToken(oauthToken);

    const pickerCallback = (data) => {
      if (data.action === google.picker.Action.PICKED) {
        const pickedData = data.docs[0];
        setSelectedData(pickedData);
      }
    };

    const picker = new window.google.picker.PickerBuilder()
      .addView(docsView)
      .setOAuthToken(oauthToken)
      .setDeveloperKey(API_KEY)
      .setCallback(pickerCallback)
      .setTitle('Select a Folder');
    picker.build().setVisible(true);
  };

  useEffect(() => {
    if (selectedData !== null) {
      const { id, name, mimeType } = selectedData;
      const data = {
        id: id,
        name: name,
        mimetype: mimeType,
      };
      if (googleAccessTokenHandler == null) {
        Object.assign(data, { accessToken: `Bearer ${accessToken}` });
      }
      if (builtInGoogleChange) {
        builtInGoogleChange(data, uploadedDataIndex);
      } else onChange(data);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedData, onChange]);

  useEffect(() => {
    if (googleAccessTokenHandler) {
      googleAccessTokenHandler(accessToken);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  return (
    <div className={cx('wrapper')}>
      {text && (
        <>
          <p className={cx('form-type')}>
            {`/${datasetName || `{${t('datasetName.label')}}`}/`}
          </p>
          <p className={cx('form-desc')}>{t('topLevelPath.message')}</p>
        </>
      )}
      {uploadedDataIndex && uploadedDataIndex !== 1 && (
        <hr className={cx('border')} />
      )}
      {!selectedData && (
        <GooglePicker
          clientId={CLIENT_ID}
          developerKey={API_KEY}
          scope={[SCOPES]}
          onChange={(data) => console.log('on change:', data)}
          onAuthFailed={(data) => console.log('on auth failed:', data)}
          multiselect
          navHidden
          authImmediate={false}
          viewId={'FOLDERS'}
          createPicker={createPicker}
        >
          <div className='google'></div>
          <div className={cx('google-picker')}>
            <div className={cx('google-drive-btn')}>
              <img
                src='/images/icon/google-drive-logo.png'
                alt='Google Drive'
                className={cx('google-drive-logo')}
              />
            </div>
          </div>
        </GooglePicker>
      )}
      <div className={cx('selected-list')}>
        {selectedData && (
          <Fragment>
            <span className={cx('folder-name')}>{selectedData.name}</span>
            <button
              className={cx('remove-btn')}
              onClick={() => {
                googleDriveDelete && googleDriveDelete(uploadedDataIndex);
                setSelectedData(null);
              }}
            >
              <img src='/images/icon/close.svg' alt='X' />
            </button>
          </Fragment>
        )}
      </div>
    </div>
  );
}

export default GoogleDrive;
