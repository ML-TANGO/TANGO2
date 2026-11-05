import { useSelector } from 'react-redux';

// CSS module
import classNames from 'classnames/bind';
import style from './BackgroundLoading.module.scss';
const cx = classNames.bind(style);

/**
 * 노드 연결시 제공되는 전체 화면 로딩
 * @component
 * @example
 *
 * return (
 *  <BackgroundLoading />
 * )
 */
function BackgroundLoading() {
  const {
    bgLoading: { loading, text },
  } = useSelector((state) => state.loading);
  return (
    <>
      {loading && (
        <div className={cx('dim')}>
          <span className={cx('box')}>
            <span className={cx('loader')}>
              <img src='/images/icon/spinner.png' alt='loading icon' />
            </span>
            <p className={cx('text')}>{text}</p>
          </span>
        </div>
      )}
    </>
  );
}

export default BackgroundLoading;
