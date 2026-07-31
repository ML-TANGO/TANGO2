import { useRef } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './ThumbnailForm.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

function ThumbnailForm({
  thumbnailImage,
  thumbnailPath,
  onChange = noop,
  onRemove = noop,
}) {
  const { t } = useTranslation();
  const fileInput = useRef(null);
  const triggerInputFile = () => fileInput.current.click();
  return (
    <div className={cx('thumbnail-form')}>
      {thumbnailImage ? (
        <div className={cx('image-box')}>
          <img
            src={thumbnailImage}
            alt='thumbnail'
            className={cx('thumbnail-image')}
          />
        </div>
      ) : (
        <div className={cx('message-box')}>
          <div className={cx('message')}>{t('thumbnail.placeholder')}</div>
        </div>
      )}
      <div className={cx('input-wrap', 'file-input-wrap')}>
        <input
          style={{ display: 'none' }}
          ref={fileInput}
          type='file'
          onChange={(e) => {
            onChange([...e.target.files]);
            e.target.value = '';
          }}
          name='thumbnail'
          multiple={false}
          accept='image/*'
        />
        <button className={cx('btn')} onClick={triggerInputFile}>
          <img src='/images/icon/00-ic-data-upload.svg' alt='icon' />
          {t('imageUpload.label')}
        </button>
        <div className={cx('file-name')} title={thumbnailPath}>
          {thumbnailPath}
        </div>
        {thumbnailPath !== '' && (
          <button
            className={cx('remove-btn')}
            onClick={() => {
              onRemove();
            }}
          >
            <img src='/images/icon/close.svg' alt='X' />
          </button>
        )}
      </div>
    </div>
  );
}

export default ThumbnailForm;
