// i18n

// 커스텀 정의
import { PARTNER } from '@src/partner';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './LeftBoxContent.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
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
