import classNames from 'classnames/bind';
import style from './OutputText.module.scss';
const cx = classNames.bind(style);

const OutputText = ({ output, objectKey }) => {
  return (
    <div className={cx('result-text')}>
      <label className={cx('title')}>{objectKey}</label>
      {Array.isArray(output[objectKey]) ? (
        output[objectKey].map((v, j) => (
          <span key={`${v}_${j}`}>
            {v}
            <br />
          </span>
        ))
      ) : (
        <span>{output[objectKey]}</span>
      )}
    </div>
  );
};

export default OutputText;
