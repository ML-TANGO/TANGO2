import React, { useMemo } from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import CompanyLogo from '@src/components/Frame/Header/CompanyLogo/CompanyLogo';

// Components
import Alarm from './Alarm/Alarm';
import LangSetting from './LangSetting';
import ServicePortal from './ServicePortal';
import UserSetting from './UserSetting';

// CSS Module
import classNames from 'classnames/bind';
import style from './Header.module.scss';

const cx = classNames.bind(style);

const SERVICE_LOGO =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO || 'Jonathan Flightbase';
/**
 * header 색이
 * 밝을 경우: VITE_REACT_APP_SERVICE_LOGO_IMG
 * 어두울 경우: VITE_REACT_APP_SERVICE_LOGO_IMG_WHITE
 */
const SERVICE_LOGO_IMG =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO_IMG_WHITE ||
  '/images/logo/BI_Jonathan_white.svg';
const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
const IS_INTEGRATION = MODE === 'integration';
// 아크릴 로고 (Powered by ACRYL)
const IS_POWERED_BY = import.meta.env.VITE_REACT_APP_IS_POWERED_BY === 'true';
const CUSTOM_COLOR = import.meta.env.VITE_REACT_APP_PRIMARY_COLOR;

function Header({ authType, navHandler, isDashboard }) {
  const { userName } = useSelector((state) => ({
    userName: state.auth.userName,
  }));

  const LogoItem = () => {
    return <div className={cx('logo-icon')}>GenAI Platform</div>;
  };
  return (
    <div
      className={cx('header')}
      style={CUSTOM_COLOR ? { background: CUSTOM_COLOR } : {}}
    >
      <div className={cx('left-box')}>
        {/* 햄버거 버튼 */}
        {!isDashboard && (
          <button
            id='side-menu-btn'
            data-testid='side-menu-btn'
            className={cx('menu-btn')}
            onClick={navHandler}
          >
            <div className={cx('line-wrapper')}>
              <div className={cx('line')}></div>
              <div className={cx('line')}></div>
              <div className={cx('line')}></div>
            </div>
          </button>
        )}
        <Link to={authType === 'USER' ? '/user/dashboard' : '/admin/dashboard'}>
          {/* <img
            className={cx('logo')}
            src={SERVICE_LOGO_IMG}
            alt={SERVICE_LOGO}
          /> */}
          <LogoItem />
        </Link>
      </div>
      <div className={cx('right-box')}>
        <Alarm userName={userName} />
        <UserSetting />
        <LangSetting />
        {IS_POWERED_BY && <CompanyLogo />}
        {IS_INTEGRATION && <ServicePortal />}
      </div>
    </div>
  );
}

export default Header;
