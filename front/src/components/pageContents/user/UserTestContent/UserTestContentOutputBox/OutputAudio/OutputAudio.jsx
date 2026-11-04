import classNames from 'classnames/bind';
import style from './OutputAudio.module.scss';
const cx = classNames.bind(style);

const OutputAudio = ({ output, objectKey }) => {
  return (
    <div className={cx('result-audio')}>
      <label className={cx('title')}>{objectKey}</label>
      <audio
        className={cx('audio')}
        src={`data:audio/mpeg;base64,${output[objectKey]}`}
        controls
      >
        <source
          src={`data:audio/mpeg;base64,${output[objectKey]}`}
          type='audio/mpeg'
        />
        <source src={`data:audio/wav;base64,${output[objectKey]}`} type='audio/wav' />
        <source src={`data:audio/ogg;base64,${output[objectKey]}`} type='audio/ogg' />
      </audio>
    </div>
  );
};

export default OutputAudio;
