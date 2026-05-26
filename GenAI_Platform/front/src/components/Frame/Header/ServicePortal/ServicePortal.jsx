import { useDispatch, useSelector } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import Popup from '../Popup';
import ContextPopupBtn from '../ContextPopupBtn';

import { servicePortalPopup } from '@src/store/modules/headerOptions';

// CSS Module
import classNames from 'classnames/bind';
import style from './ServicePortal.module.scss';

const cx = classNames.bind(style);

const serviceList = [
  {
    label: 'Flightbase',
    link: 'https://flightbase.acryl.ai',
    img: '/images/logo/BI_Flightbase_v.svg',
    selected: true,
  },
  {
    label: 'Datascope',
    link: 'http://datascope.acryl.ai',
    img: '/images/logo/BI_Datascope_v.svg',
    disabled: true,
  },
  {
    label: 'Nubot',
    link: 'https://nubot.acryl.ai',
    img: '/images/logo/BI_Nubot_v.svg',
    disabled: true,
  },
];

const familySiteList = [
  {
    label: 'Acryl',
    link: 'https://www.acryl.ai/',
    img: '/images/logo/acryl-logo.png',
    disabled: false,
  },
  {
    label: 'Jonathan',
    link: 'https://jonathan.acryl.ai/',
    img: '/images/logo/BI_Jonathan_only_text.svg',
    disabled: false,
  },
  {
    label: 'Hugbot',
    link: 'https://hugbot.acryl.ai/',
    img: '/images/logo/logo-hugbot-basic-v.png',
    disabled: false,
  },
];

function ServicePortal() {
  const dispatch = useDispatch();
  const {
    headerOptions: { servicePortalPopup: isOpen },
  } = useSelector((state) => ({
    headerOptions: state.headerOptions,
  }));

  const { t } = useTranslation();

  const popupHandler = () => {
    dispatch(servicePortalPopup());
  };

  return (
    <div className={cx('service-portal')}>
      {isOpen && (
        <Popup popupHandler={popupHandler} position='right'>
          <div className={cx('box', 'service')}>
            <p className={cx('title')}>{t('Services')}</p>
            <ul className={cx('list')}>
              {serviceList.map(
                ({ label, link, img, disabled, selected }, idx) => (
                  <li key={idx}>
                    <button
                      className={cx('service-btn', selected && 'selected')}
                      onClick={() => {
                        if (!selected) window.location.href = link;
                      }}
                      disabled={disabled}
                    >
                      <img
                        className={cx('logo', 'service')}
                        src={img}
                        alt={label}
                      />
                    </button>
                  </li>
                ),
              )}
            </ul>
          </div>
          <div className={cx('box', 'family')}>
            <p className={cx('title')}>{t('familySite.label')}</p>
            <ul className={cx('list')}>
              {familySiteList.map(
                ({ label, link, img, disabled, selected }, idx) => (
                  <li key={idx}>
                    <button
                      className={cx('service-btn', selected && 'selected')}
                      onClick={() => {
                        if (!selected) window.open(link, '_blank');
                      }}
                      disabled={disabled}
                    >
                      <img
                        className={cx('logo', 'site', label)}
                        src={img}
                        alt={label}
                      />
                    </button>
                  </li>
                ),
              )}
            </ul>
          </div>
        </Popup>
      )}
      <ContextPopupBtn
        isOpen={isOpen}
        customStyle={{ padding: '6px' }}
        popupHandler={popupHandler}
        disableArrow
      >
        <img src='/images/icon/btn-menu.svg' alt='menu icon' />
      </ContextPopupBtn>
    </div>
  );
}

export default ServicePortal;
