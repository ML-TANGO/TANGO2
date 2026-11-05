import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './TableEmptyBox.module.scss';

const cx = classNames.bind(style);

export default function TableEmptyBox({ message, ...rest }) {
  return (
    <article className={cx('empty-cont')}>
      <p className={cx('message')} {...rest}>
        {message}
      </p>
    </article>
  );
}
