// Utils

// Components
import { Footer } from '@jonathan/ui-react';

import { today } from '@src/datetimeUtils';
// 커스텀 정의
import { PARTNER } from '@src/partner';
import dayjs from 'dayjs';
import { useEffect } from 'react';

import Language from '@src/components/Frame/Footer/Language';
import LoginFrame from '@src/components/Frame/LoginFrame';
import ETRITANGOLogo from '@src/static/images/logo/ETRI_TANGO_logo.svg';

import usePreloadComponent from '@src/hooks/usePreloadComponent';

// Theme
import { theme } from '@src/utils';

import LeftBoxContent from './LeftBoxContent';
import LoginForm from './LoginForm';
import LoginHeader from './LoginHeader';

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
const UPDATE_DATE = import.meta.env.VITE_REACT_APP_UPDATE_DATE || today();

// Copyright 연도
const year = dayjs().year();

const partnerFooterLogo = PARTNER['jp'].logo.footer;
const PartnerFooterLogo = partnerFooterLogo;

function FooterLogos() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
      <img src='/images/logo/ACRYL_CI.png' alt='Acryl Inc.' style={{ height: '16px' }} />
      {typeof partnerFooterLogo === 'function' ? (
        <PartnerFooterLogo />
      ) : (
        <img src={partnerFooterLogo} alt='logo' style={{ height: '29px' }} />
      )}
      <img src={ETRITANGOLogo} alt='ETRI TANGO' style={{ height: '40px' }} />
    </div>
  );
}

function LoginContent() {
  const { lazyLoad } = usePreloadComponent();

  useEffect(
    function preloadPages() {
      const AdminRouter = lazyLoad(() => {
        import('@src/pages/authRouter/AdminRouter.jsx');
      });
      const AdminDashboardPage = lazyLoad(() => {
        import('@src/pages/AdminDashboardPage.jsx');
      });
      const UserDashboardPage = lazyLoad(() => {
        import('@src/pages/UserDashboardPage.jsx');
      });
      const UserRouter = lazyLoad(() => {
        import('@src/pages/authRouter/UserRouter.jsx');
      });

      AdminRouter.preload();
      AdminDashboardPage.preload();

      UserRouter.preload();
      UserDashboardPage.preload();
    },
    [lazyLoad],
  );

  return (
    <LoginFrame
      headerRender={<LoginHeader />}
      leftContentRender={<LeftBoxContent />}
      rightContentRender={<LoginForm />}
      footerRender={
        <Footer
          theme={theme.PRIMARY_THEME}
          logoIcon={() => null}
          copyrights={`© ${year} Electronics and Telecommunications Research Institute. All rights reserved.`}
          updated={UPDATE_DATE}
          language={<Language />}
        />
      }
    />
  );
}

export default LoginContent;
