// i18n

// 커스텀 정의
import { PARTNER } from '@src/partner';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './LeftBoxContent.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
const SERVICE_LOGO = import.meta.env.VITE_REACT_APP_SERVICE_LOGO || 'TANGO';
const SERVICE_LOGO_IMG =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO_IMG ||
  '/images/logo/ETRI_TANGO_logo.svg';

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
        src='/images/logo/ETRI_TANGO_logo.svg'
        alt='ETRI TANGO'
      />
      <span className={cx('welcome-sub-title')}>
        <strong>T</strong>arget <strong>A</strong>ware <strong>N</strong>o-code neural network <strong>G</strong>eneration and <strong>O</strong>peration framework
      </span>
    </div>
  );
}

export default LeftBoxContent;
