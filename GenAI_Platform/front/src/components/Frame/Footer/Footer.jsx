import { Fragment } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Utils
import { today } from '@src/datetimeUtils';
import dayjs from 'dayjs';

// 커스텀 정의
import { PARTNER } from '@src/partner';

// Components
import FamilySite from './FamilySite';
import Language from './Language';

// CSS module
import style from './Footer.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
const IS_INTEGRATION = MODE === 'integration';
const UPDATE_DATE = import.meta.env.VITE_REACT_APP_UPDATE_DATE || today();
const year = dayjs().year();

const Footer = ({ type, isExpand }) => {
  const { t } = useTranslation();
  return (
    <footer
      id='Footer'
      className={cx(
        'footer',
        `${type}`.toLowerCase(),
        isExpand && 'expand',
        IS_INTEGRATION && 'integration',
      )}
    >
      <Fragment>
        <div className={cx('footer-left')}>
          <a
            href={PARTNER[MODE]?.siteUrl || PARTNER['jp'].siteUrl}
            rel='noopener noreferrer'
            target='_blank'
          >
            <img
              className={cx('logo-img')}
              src={PARTNER[MODE]?.logo.footer || PARTNER['jp'].logo.footer}
              alt={MODE}
            />
          </a>
          <div className={cx('copyright-version')}>
            <span className={cx('acryl-inc')}>
              © {year} ACRYL inc. All rights reserved.
            </span>
            <span className={cx('border-item')}>|</span>
            <span className={cx('updated')}>Updated {UPDATE_DATE}</span>
          </div>
        </div>
        <div className={cx('footer-right')}>
          {IS_INTEGRATION && (
            <div className={cx('integration-footer')}>
              <div className={cx('info')}>
                <span className={cx('item')}>
                  <a
                    href={`${
                      import.meta.env.VITE_VITE_REACT_APP_INTEGRATION_API_HOST
                    }accounts/term/access`}
                  >
                    {t('terms.label')}
                  </a>
                </span>
                <span className={cx('bullet')}></span>
                <span className={cx('item')}>
                  <a
                    href={`${
                      import.meta.env.VITE_VITE_REACT_APP_INTEGRATION_API_HOST
                    }accounts/term/privacy`}
                  >
                    {t('privacy.label')}
                  </a>
                </span>
              </div>
              <FamilySite />
            </div>
          )}
          <Language />
        </div>
      </Fragment>
    </footer>
  );
};

export default Footer;
