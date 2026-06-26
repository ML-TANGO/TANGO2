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

import usePreloadComponent from '@src/hooks/usePreloadComponent';

// Theme
import { theme } from '@src/utils';

import LeftBoxContent from './LeftBoxContent';
import LoginForm from './LoginForm';
import LoginHeader from './LoginHeader';

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();
// 브랜딩 전용 스위치 — MODE(통합 스위치)와 분리.
const BRAND = import.meta.env.VITE_REACT_APP_BRAND?.toLowerCase();
const UPDATE_DATE = import.meta.env.VITE_REACT_APP_UPDATE_DATE || today();

// Copyright 연도
const year = dayjs().year();

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
          logoIcon={
            // BRAND=tango 푸터는 로고 없음(ETRI 저작권만) — MODE 폴백 Jonathan 로고 방지
            BRAND === 'tango'
              ? () => null
              : PARTNER[MODE]?.logo.footer || PARTNER['jp'].logo.footer
          }
          copyrights={
            BRAND === 'tango'
              ? `© ${year} Electronics and Telecommunications Research Institute. All rights reserved.`
              : `© ${year} Acryl inc. All rights reserved.`
          }
          updated={UPDATE_DATE}
          language={<Language />}
        />
      }
    />
  );
}

export default LoginContent;
