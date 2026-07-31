// i18n
import { withTranslation } from 'react-i18next';

// Components
import File from '../File';
import InputLabelBox from '../InputLabelBox';

import classNames from 'classnames/bind';
// CSS module
import style from './InputImage.module.scss';

const cx = classNames.bind(style);

const InputImage = ({
  idx,
  apiKey,
  description,
  fileInputHandler,
  selectedFile = [],
  selectedFileSrc = '',
  t,
}) => {
  return (
    <div className={cx('input-analysis')}>
      <InputLabelBox
        idx={idx}
        apiKey={apiKey}
        description={description}
        type={t('image.label')}
      >
        <div className={cx('file-browse')} title={description}>
          <File
            name='image'
            accept='image/*'
            onChange={(e) => fileInputHandler(e, 'Image', idx)}
            value={selectedFileSrc}
          />
          <div className={cx('file-name')} title={selectedFile.name}>
            {selectedFile && selectedFile.name}
          </div>
        </div>
      </InputLabelBox>
      {selectedFileSrc ? (
        <div className={cx('image-box')}>
          <img
            src={selectedFileSrc}
            alt='selected file'
            className={cx('selected-image')}
          />
        </div>
      ) : (
        <div className={cx('message-box')}>
          <div className={cx('message')}>{t('selectImage.placeholder')}</div>
        </div>
      )}
    </div>
  );
};

export default withTranslation()(InputImage);
