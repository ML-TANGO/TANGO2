import React from 'react';

import PageTitle from '@src/components/atoms/PageTitle';

import classNames from 'classnames/bind';
import style from './PageHeader.module.scss';

const cx = classNames.bind(style);

const PageHeader = React.memo(
  ({ title, rightComponent, desc = '', ...rest }) => {
    return (
      <div className={cx('page-header-cont')} {...rest}>
        <PageTitle desc={desc}>{title}</PageTitle>
        <div className={cx('right-cont')}>{rightComponent}</div>
      </div>
    );
  },
);

export default PageHeader;
