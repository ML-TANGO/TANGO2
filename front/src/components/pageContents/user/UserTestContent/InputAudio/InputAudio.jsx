// i18n
import { withTranslation } from 'react-i18next';

// Components
import File from '../File';
import InputLabelBox from '../InputLabelBox';

import classNames from 'classnames/bind';
// CSS module
import style from './InputAudio.module.scss';

const cx = classNames.bind(style);

const InputAudio = ({
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
        type={t('audio.label')}
      >
        <div className={cx('file-browse')} title={description}>
          <File
            name='audio'
            accept='audio/*'
            onChange={(e) => fileInputHandler(e, 'Audio', idx)}
            value={selectedFileSrc}
          />
          <div className={cx('file-name')} title={selectedFile.name}>
            {selectedFile && selectedFile.name}
          </div>
        </div>
      </InputLabelBox>
      {selectedFile ? (
        <div className={cx('audio-box')}>
          <audio
            className={cx('selected-audio')}
            src={selectedFileSrc}
            controls
          >
            <source src={selectedFileSrc} type='audio/mpeg' />
            <source src={selectedFileSrc} type='audio/wav' />
            <source src={selectedFileSrc} type='audio/ogg' />
          </audio>
        </div>
      ) : (
        <div className={cx('message-box')}>
          <div className={cx('message')}>{t('selectAudio.placeholder')}</div>
        </div>
      )}
    </div>
  );
};

export default withTranslation()(InputAudio);
