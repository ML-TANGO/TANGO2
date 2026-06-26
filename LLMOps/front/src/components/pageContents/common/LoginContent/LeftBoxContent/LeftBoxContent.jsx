// i18n

// 커스텀 정의
import { PARTNER } from '@src/partner';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './LeftBoxContent.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
// 브랜딩 전용 스위치 — MODE(통합 스위치)와 분리. INTEGRATION 배포에서도 브랜딩만 독립 제어.
const BRAND = import.meta.env.VITE_REACT_APP_BRAND?.toLowerCase();
const SERVICE_LOGO = import.meta.env.VITE_REACT_APP_SERVICE_LOGO || 'Jonathan';
const SERVICE_LOGO_IMG =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO_IMG ||
  '/images/logo/BI_Jonathan.svg';

/**
 * 로그인 페이지 로고 영역 컴포넌트
 * @component
 * @example
 *
 * return (
 *  <LeftBoxContent />
 * )
 */
function LeftBoxContent() {
  const { t } = useTranslation();

  // TANGO 공동 프로젝트(ETRI) 로그인 브랜딩 — BRAND=tango 일 때만. 그 외 배포는 기존 그대로.
  if (BRAND === 'tango') {
    return (
      <div className={cx('wrap')}>
        <img
          className={cx('service-logo')}
          src='/images/logo/ETRI_TANGO_logo.svg'
          alt='ETRI TANGO'
        />
        <span className={cx('welcome-sub-title')}>
          <strong>T</strong>arget <strong>A</strong>ware <strong>N</strong>o-code
          neural network <strong>G</strong>eneration and <strong>O</strong>peration
          framework
        </span>
      </div>
    );
  }

  return (
    <div className={cx('wrap')}>
      {PARTNER[MODE]?.logo?.loginContents && (
        <>
          <img
            className={cx('partner-service-logo', MODE)}
            src={PARTNER[MODE].logo.loginContents}
            alt={MODE.toUpperCase()}
          />
          <div className={cx('partner-title')}>
            {t('aiDevelopmentPlatform.label')}
          </div>
        </>
      )}
      <img
        className={cx('service-logo')}
        src={SERVICE_LOGO_IMG}
        alt={SERVICE_LOGO}
      />
      <span className={cx('welcome-title')}>MORE THAN READY TO FLY</span>
      <span className={cx('welcome-sub-title')}>
        - For your AIs’ development and operation
      </span>
    </div>
  );
}

export default LeftBoxContent;
