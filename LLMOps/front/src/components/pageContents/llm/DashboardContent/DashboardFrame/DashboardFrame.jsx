import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardFrame.module.scss';

const cx = classNames.bind(style);

export default function DashboardFrame({
  children,
  title,
  contentStyle,
  ...rest
}) {
  return (
    <div className={cx('dashboard-frame')} style={{ ...rest.style }}>
      {title && <div className={cx('title-cont')}>{title}</div>}
      {title && (
        <div className={cx('outer-cont')}>
          <div className={cx('title-content-cont')} style={{ ...contentStyle }}>
            {children}
          </div>
        </div>
      )}
      {!title && <div className={cx('content-cont')}>{children}</div>}
    </div>
  );
}
