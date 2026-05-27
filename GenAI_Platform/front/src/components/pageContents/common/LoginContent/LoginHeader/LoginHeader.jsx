// 커스텀 정의
import { PARTNER } from '@src/partner';

// CSS Module
import classNames from 'classnames/bind';
import style from './LoginHeader.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

/**
 * 로그인 페이지 헤더
 * @component
 * @example
 *
 * return (
 *  <LoginHeader />
 * )
 */
function LoginHeader() {
  return (
    <div className={cx('header')}>
      <a href='https://www.acryl.ai' rel='noopener noreferrer' target='_blank'>
        <img
          className={cx('company-logo')}
          src='/images/logo/ACRYL_CI.png'
          alt='Acryl Inc.'
        />
      </a>
      {PARTNER[MODE]?.logo?.loginHeader && (
        <a
          href={PARTNER[MODE]?.siteUrl || '#'}
          rel='noopener noreferrer'
          target='_blank'
        >
          <img
            className={cx('partner-logo', MODE)}
            src={PARTNER[MODE].logo.loginHeader}
            alt={MODE.toUpperCase()}
          />
        </a>
      )}
    </div>
  );
}

export default LoginHeader;
