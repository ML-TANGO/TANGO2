// CSS module
import classNames from 'classnames/bind';
import style from './StorageUsageBar.module.scss';
const cx = classNames.bind(style);

function StorageUsageBar({ barData, t }) {
  return (
    <>
      <div className={cx('container')}>
        <div className={cx('bar-box')}>
          {barData?.map((v, idx) => {
            return (
              <div
                className={cx('content', idx === 2 && 'curr-box')}
                key={idx}
                style={{
                  backgroundColor: v.color,
                  width: `${v.width}%`,
                  height: '16px',
                }}
              >
                {idx === 2 && <div className={cx('curr-value')}></div>}
              </div>
            );
          })}
        </div>
      </div>
      <div className={cx('legend-box')}>
        {barData?.map((list, idx) => {
          return (
            <div className={cx('legend')} key={idx}>
              <div
                className={cx('color-box')}
                style={{ backgroundColor: list.color }}
              ></div>
              <div className={cx('title-box')}>
                <span className={cx('title')}>{t(list.title)}</span>
                <span className={cx('usage')}>{list.usage}</span>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

export default StorageUsageBar;
