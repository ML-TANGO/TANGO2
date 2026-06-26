// 커스텀 정의
import { PARTNER } from '@src/partner';

// CSS Module
import classNames from 'classnames/bind';
import style from './LoginHeader.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
// 브랜딩 전용 스위치 — MODE(통합 스위치)와 분리.
const BRAND = import.meta.env.VITE_REACT_APP_BRAND?.toLowerCase();

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
  // TANGO 공동 프로젝트(ETRI) 공동브랜딩 — BRAND=tango 일 때만.
  // ETRI+Acryl 로고를 단일 flex wrapper(gap)로 묶어 쌍으로 표시.
  // (.header 의 row-reverse+space-between 가 두 로고를 양끝으로 벌리는 것 방지)
  if (BRAND === 'tango') {
    return (
      <div className={cx('header')}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <a href='https://www.etri.re.kr/' rel='noopener noreferrer' target='_blank'>
            <img
              className={cx('company-logo')}
              src='/images/logo/logo_etri.png'
              alt='ETRI'
            />
          </a>
          <a href='https://www.acryl.ai' rel='noopener noreferrer' target='_blank'>
            <img
              className={cx('company-logo')}
              src='/images/logo/ACRYL_CI.png'
              alt='Acryl Inc.'
            />
          </a>
        </div>
      </div>
    );
  }

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
