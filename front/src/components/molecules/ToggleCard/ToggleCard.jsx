import { useState } from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './ToggleCard.module.scss';

const cx = classNames.bind(style);

function ToggleCard({ defaultIsOpen = false, subject, title, children }) {
  const [isOpen, setIsOpen] = useState(defaultIsOpen);
  return (
    <div className={cx('card-container', isOpen && 'open')}>
      <div className={cx('header')} onClick={() => setIsOpen(!isOpen)}>
        <div className={cx('title-box')}>
          <div className={cx('subject')}>{subject}</div>
          <div className={cx('title')}>{title}</div>
        </div>
        <div className={cx('icon-box')}>
          <img
            className={cx('icon')}
            src='/images/icon/ic-arrow-up-white.svg'
            alt='^'
          />
        </div>
      </div>
      <div className={cx('contents')}>{children}</div>
    </div>
  );
}

export default ToggleCard;
