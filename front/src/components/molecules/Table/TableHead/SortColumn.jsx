// Images
import ArrowTopIcon from './ArrowTopIcon';
import ArrowBottomIcon from './ArrowBottomIcon';

// Style
import styles from './SortColumn.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(styles);

function SortColumn({ title, onClickHandler, idx, sortClickFlag }) {
  return (
    <div onClick={() => onClickHandler(idx)} className={cx('container')}>
      <div className={cx('title')}>{title}</div>
      <div className={cx('sort')}>
        <ArrowTopIcon
          className={cx(sortClickFlag && sortClickFlag[idx] && 'dark')}
        />
        <ArrowBottomIcon
          className={cx(
            sortClickFlag &&
              !sortClickFlag[idx] &&
              sortClickFlag[idx] !== undefined &&
              'dark',
          )}
        />
      </div>
    </div>
  );
}

export default SortColumn;
