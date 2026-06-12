// CSS Module
import React from 'react';

import classNames from 'classnames/bind';
import style from './BackButton.module.scss';

const cx = classNames.bind(style);

const BackButton = React.memo(({ text, handleBackGo }) => {
  return (
    <div className={cx('back-btn')} onClick={handleBackGo}>
      <img
        src={'/src/static/images/icon/00-ic-basic-arrow-02-left.svg'}
        alt='back-icon'
      />
      <span>{text}</span>
    </div>
  );
});

export default BackButton;
