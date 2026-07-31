import React from 'react';

import PageTitle from '@src/components/atoms/PageTitle';

import classNames from 'classnames/bind';
import style from './AdminPageHeader.module.scss';

const cx = classNames.bind(style);

const AdminPageHeader = React.memo(
  ({ title, rightComponent, desc = '', sectionTitle, ...rest }) => {
    return (
      <div className={cx('page-header-cont')} {...rest}>
        <div className={cx('title')}>
          {sectionTitle && (
            <div className={cx('section-title')}>{sectionTitle}</div>
          )}
          <div className={cx('main-title')}>{title}</div>
        </div>
        <div className={cx('right-cont')}>{rightComponent}</div>
      </div>
    );
  },
);

export default AdminPageHeader;
