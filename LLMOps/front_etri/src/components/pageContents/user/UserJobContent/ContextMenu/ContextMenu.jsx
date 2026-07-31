// CSS module
import style from './ContextMenu.module.scss';
import classNames from 'classnames/bind';
import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
const cx = classNames.bind(style);

const ContextMenu = (props) => {
  const { t } = useTranslation();
  const menuRef = useRef(null);
  const {
    isMenuOpen,
    setIsMenuOpen,
    status,
    onCreate,
    onStop,
    openDeleteConfirmPopup,
    openCheckPointPopup,
  } = props;

  console.log('props ->', props);

  useEffect(() => {
    const clickOutside = (e) => {
      if (isMenuOpen && !menuRef.current.contains(e.target))
        e.stopPropagation();
      setTimeout(() => setIsMenuOpen(false), 0);
    };

    document.addEventListener('mouseup', clickOutside);

    return () => {
      document.removeEventListener('mouseup', clickOutside);
    };
  }, [isMenuOpen, setIsMenuOpen]);
  return (
    <ul ref={menuRef} id='ContextMenu' className={cx('menu_ul')}>
      {onCreate && (
        <li className={cx('menu_li')} onClick={() => onCreate()}>
          <img
            className={cx('icon')}
            src='/images/icon/00-ic-basic-plus.svg'
            alt='add'
          />
          {t('add.label')}
        </li>
      )}
      <li
        className={cx('menu_li')}
        onClick={() => {
          openDeleteConfirmPopup();
        }}
      >
        <img
          className={cx('icon')}
          src='/images/icon/00-ic-basic-delete.svg'
          alt='delete'
        />
        {t('delete.label')}
      </li>
      {status?.status === 'running' && (
        <li className={cx('menu_li')} onClick={() => onStop()}>
          <img
            className={cx('icon')}
            src='/images/icon/00-ic-basic-stop-o.svg'
            alt='stop'
          />
          {t('stop.label')}
        </li>
      )}
      {openCheckPointPopup && (
        <>
          <hr className={cx('border')} />
          <li className={cx('menu_li')} onClick={() => openCheckPointPopup()}>
            <img
              className={cx('icon')}
              src='/images/icon/00-ic-alert-success-o.svg'
              alt='checkpoint'
            />
            {t('checkpoint.label')}
          </li>
        </>
      )}
    </ul>
  );
};

export default ContextMenu;
