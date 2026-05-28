import classNames from 'classnames/bind';
import style from './OutputVideo.module.scss';
const cx = classNames.bind(style);

const OutputVideo = ({ output, objectKey }) => {
  return (
    <div className={cx('result-video')}>
      <label className={cx('title')}>{objectKey}</label>
      <video
        className={cx('video')}
        src={`data:video/mp4;base64,${output[objectKey]}`}
        controls
      >
        <source src={`data:video/mp4;base64,${output[objectKey]}`} type='video/mp4' />
        <source src={`data:video/ogg;base64,${output[objectKey]}`} type='video/ogg' />
      </video>
    </div>
  );
};

export default OutputVideo;
