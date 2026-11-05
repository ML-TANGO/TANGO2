import { useRef } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Components

// CSS module
import classNames from 'classnames/bind';
import style from './File.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

const File = ({ status, name, accept, onChange = noop, t }) => {
  const fileInput = useRef(null);
  const triggerInputFile = () => fileInput.current.click();
  return (
    <div className={cx('fb', 'input', 'file', `${status || ''}`, 'input-wrap')}>
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
          multiple={false}
          accept={accept}
        />
        <button className={cx('btn')} onClick={triggerInputFile}>
          <img src='/images/icon/00-ic-data-upload.svg' alt='icon' />
          {t('dataUpload.label')}
        </button>
      </div>
    </div>
  );
};

export default withTranslation()(File);
