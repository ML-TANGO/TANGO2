import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './PipelineHeader.module.scss';

const cx = classNames.bind(style);

const PipelineHeader = React.memo(({ title, children }) => {
  return (
    <div className={cx('header')}>
      <h1 className={cx('title')}>{title}</h1>
      <div className={cx('right-cont')}>{children}</div>
    </div>
  );
});

export default PipelineHeader;
