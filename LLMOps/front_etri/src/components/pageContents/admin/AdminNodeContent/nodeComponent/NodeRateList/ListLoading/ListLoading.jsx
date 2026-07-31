// CSS Module
import classNames from 'classnames/bind';
import style from './ListLoading.module.scss';
const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용하는 할당률 및 사용률 리스트 컴포넌트의 로딩 컴포넌트
 * @component
 * @example
 *
 * return (
 *  <ListLoading />
 * );
 */
function ListLoading() {
  return (
    <div className={cx('list-skeleton')}>
      <div className={cx('skeleton-box')}></div>
      <div className={cx('skeleton-box')}></div>
      <div className={cx('skeleton-box')}></div>
      <div className={cx('skeleton-box')}></div>
    </div>
  );
}

export default ListLoading;
