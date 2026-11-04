// CSS Module
import classNames from 'classnames/bind';
import style from './CardLoading.module.scss';
const cx = classNames.bind(style);

/**
 * 학습 목록 카드 목록 로딩 컴포넌트
 * @component
 */
function CardLoading() {
  return (
    <div className={cx('card-skeleton')}>
      <div className={cx('skeleton-box', 'skeleton-1')}></div>
      <div className={cx('skeleton-box', 'skeleton-2')}></div>
      <div className={cx('skeleton-box', 'skeleton-3')}></div>
      <div className={cx('skeleton-box', 'skeleton-4')}></div>
      <div className={cx('skeleton-box', 'skeleton-5')}></div>
      <div className={cx('skeleton-box', 'skeleton-6')}></div>
    </div>
  );
}

export default CardLoading;
