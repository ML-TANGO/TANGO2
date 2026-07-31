import { memo } from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './NewStack.module.scss';

const cx = classNames.bind(style);

const NewStack = memo(({ rate }) => {
  return (
    <div className={cx('stack-wrap')}>
      <div className={cx('stack')}>
        <div
          className={cx(
            'fill',
            rate >= 0 && rate <= 25 && 'first',
            rate > 25 && rate <= 50 && 'second',
            rate > 50 && rate <= 75 && 'thrid',
            rate > 75 && 'fourth',
          )}
          style={{ width: `${rate}%` }}
        ></div>
      </div>
      <span className={cx('rate')}>
        {rate !== null ? (
          `${Math.floor(rate)}%`
        ) : (
          <span className={cx('error')}>error</span>
        )}
      </span>
    </div>
  );
});

export default NewStack;
