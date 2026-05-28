// i18n
import { withTranslation } from 'react-i18next';

// Components
import File from '../File';
import InputLabelBox from '../InputLabelBox';

// CSS module
import style from './InputVideo.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const InputVideo = ({
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
        type={t('video.label')}
      >
        <div className={cx('file-browse')} title={description}>
          <File
            name='video'
            accept='video/*'
            onChange={(e) => fileInputHandler(e, 'Video', idx)}
            value={selectedFileSrc}
          />
          <div className={cx('file-name')} title={selectedFile.name}>
            {selectedFile && selectedFile.name}
          </div>
        </div>
      </InputLabelBox>
      {selectedFile ? (
        <div className={cx('video-box')}>
          <video
            className={cx('selected-video')}
            src={selectedFileSrc}
            controls
          >
            <source src={selectedFileSrc} type='video/mp4' />
            <source src={selectedFileSrc} type='video/ogg' />
          </video>
        </div>
      ) : (
        <div className={cx('message-box')}>
          <div className={cx('message')}>{t('selectVideo.placeholder')}</div>
        </div>
      )}
    </div>
  );
};

export default withTranslation()(InputVideo);
