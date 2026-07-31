// CSS Module
import classNames from 'classnames/bind';
import style from './StorageStack.module.scss';
const cx = classNames.bind(style);

function StorageStack({ usage, allocation, share = false }) {
  return (
    <div className={cx('stack-wrap')} style={{ width: '100%', padding: '0' }}>
      <div className={cx('stack')}>
        <div
          className={cx(
            'fill',
            !share && usage >= 90 && 'danger',
            !share && usage >= 70 && usage <= 89 && 'warn',
          )}
          style={{ width: `${usage}%` }}
        ></div>
        <div
          className={cx('allocation')}
          style={{ width: `${allocation}%` }}
        ></div>
      </div>
      <div className={cx('rate')}>
        {usage !== null && `${Math.floor(usage)}%`}
        {allocation ? <span className={cx('bar')}>/</span> : ''}
        {allocation ? `${Math.floor(allocation)}%` : ''}
        {usage === null && !allocation && (
          <span className={cx('error')}>error</span>
        )}
      </div>
    </div>
  );
}

export default StorageStack;
