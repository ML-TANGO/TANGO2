// CSS Module
import classNames from 'classnames/bind';
import style from './SkeletonBox.module.scss';
const cx = classNames.bind(style);

function SkeletonBox({ items }) {
  return (
    <div className={cx('card-skeleton')}>
      {items.map(({ width, height, bgColor }, key) => (
        <div
          key={key}
          style={{ width, height, backgroundColor: bgColor }}
          className={cx('skeleton-box')}
        ></div>
      ))}
    </div>
  );
}

export default SkeletonBox;
