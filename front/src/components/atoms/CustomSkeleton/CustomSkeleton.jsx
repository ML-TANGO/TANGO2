import classNames from 'classnames/bind';
import style from './CustomSkeleton.module.scss';

const cx = classNames.bind(style);

const CustomSkeleton = ({ width, height, mb }) => {
  return (
    <div
      className={cx('skeleton-profile')}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        marginBottom: `${mb}px`,
      }}
    />
  );
};

export default CustomSkeleton;
