// CSS Module
import classNames from 'classnames/bind';
import style from './SkeletonLine.module.scss';
const cx = classNames.bind(style);

function SkeletonLine({ length }) {
  const Skeleton = () => {
    const uiArray = [];
    for (let i = 0; i < length; i++) {
      uiArray.push(<div key={i} className={cx('skeleton-profile')} />);
    }
    return uiArray;
  };
  return (
    <div className={cx('skeleton-wrapper')}>
      <Skeleton />
    </div>
  );
}

export default SkeletonLine;
