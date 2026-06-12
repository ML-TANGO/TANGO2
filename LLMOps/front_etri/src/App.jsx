import { lazy, Suspense, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Prompt, Redirect, Route, Router, Switch } from 'react-router-dom';

import { PageTemplateProvider } from '@tango/ui-react';

import ConfirmPopup from '@src/containers/ConfirmContainer';
import DownloadProgressContainer from '@src/containers/DownloadProgressContainer';
// Error Handler
import ErrorBoundary from '@src/containers/ErrorBoundary';
import ModalContainer from '@src/containers/ModalContainer';
import ProgressStatusListContainer from '@src/containers/ProgressStatusListContainer';
import UploadListContainer from '@src/containers/UploadListContainer';
import customHistory from '@src/customHistory';
import dayjs from 'dayjs';

// Components
import { ToastContainer } from '@src/components/Toast';

// Store
import { activeTab, inActiveTab } from '@src/store/modules/tab';

import FBLoading from './components/organisms/FBLoading';
import PopupContainer from './containers/PopupContainer';
import DeferredComponent from './hooks/useDeferredComponent';
import useWorkerClose from './hooks/useWorkerClose';

const LoadingForIntegrationLogin = lazy(() =>
  import('@src/components/atoms/loading/LoadingForIntegrationLogin'),
);

// Pages
const LoginPage = lazy(() => import('@src/pages/LoginPage'));
const AdminRouter = lazy(() => import('@src/pages/authRouter/AdminRouter'));
const UserRouter = lazy(() => import('@src/pages/authRouter/UserRouter'));
const NotFoundPage = lazy(() => import('@src/pages/NotFoundPage'));
const UIPage = lazy(() => import('@src/pages/UiPage'));
const UploadTestPage = lazy(() => import('@src/pages/UploadTestPage'));
const IntegrationLoginFailPage = lazy(() =>
  import('@src/pages/IntegrationLoginFailPage'),
);

const MODE = import.meta.env.VITE_REACT_APP_MODE;
const UPDATED_DATE = import.meta.env.VITE_REACT_APP_UPDATE_DATE || 'Unknown';
const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

// 콘솔로그 Welcome to Tango!
const emoji = ['😊', '🥰', '😄', '😆', '🤩', '😘'];
function randomEmoji() {
  let random = Math.floor(Math.random() * emoji.length);
  return emoji[random];
}
console.log(
  `%c통합 AI 플랫폼, Tango %cWelcome to Tango!${randomEmoji()} %c\n${
    MODE === 'local' || MODE === 'dev'
      ? `API: ${API_HOST}`
      : `TANGO © ${dayjs().year()} Acryl inc. All rights reserved.`
  }  Updated: %c${UPDATED_DATE}\n`,
  `color: #121619; font-family: SpoqaB; font-size: 12px; margin-top: 16px;`,
  `color: #fff; font-family: SpoqaB; font-size: 30px; 
  text-shadow: 2px 2px #002f77; text-align: center;
  border: 4px solid #001338; border-radius: 8px;
  background: linear-gradient(45deg, #002f77, 40%, #2d76f8);
  padding: 16px 32px; margin: 8px 0 16px 0px`,
  `color: #3e3e3e; font-family: SpoqaR; font-size: 11px;`,
  `color: #121619; font-family: SpoqaM; font-size: 11px;`,
);

function AdminRoute({ isAuth, type, children, component, ...rest }) {
  if (type === 'USER') {
    return <NotFoundPage />;
  }

  return (
    <Route
      {...rest}
      render={({ location }) =>
        isAuth ? (
          component
        ) : (
          <Redirect
            to={{
              pathname: '/login',
              state: { from: location },
            }}
          />
        )
      }
    />
  );
}

function UserRoute({ isAuth, type, component, ...rest }) {
  if (type === 'ADMIN') {
    return <NotFoundPage />;
  }

  return (
    <Route
      {...rest}
      render={({ location }) =>
        isAuth ? (
          <LoadingForIntegrationLogin>{component}</LoadingForIntegrationLogin>
        ) : (
          <Redirect
            to={{
              pathname: '/login',
              state: { from: location },
            }}
          />
        )
      }
    />
  );
}

function PublicRoute({ isAuth, type, children, component, ...rest }) {
  return (
    <Route
      {...rest}
      render={({ location }) =>
        isAuth ? (
          <Redirect
            to={{
              pathname: type === 'ADMIN' ? '/admin' : '/user',
              state: { from: location },
            }}
          />
        ) : (
          <LoadingForIntegrationLogin>{component}</LoadingForIntegrationLogin>
        )
      }
    />
  );
}

function App() {
  const dispatch = useDispatch();
  const { auth, prompt } = useSelector(({ auth, prompt }) => ({
    auth,
    prompt,
  }));
  const { isAuth, type } = auth;

  const uploadLoading = useSelector((state) => state.uploadLoading.isUploading);
  const activeWorkers = useSelector(
    (state) => state.uploadLoading.activeWorkers,
  );

  useWorkerClose(uploadLoading, activeWorkers);

  useEffect(() => {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        dispatch(activeTab());
      } else {
        dispatch(inActiveTab());
      }
    });
  }, [dispatch]);

  return (
    <ErrorBoundary>
      <Router
        history={customHistory}
        basename={MODE === 'INTEGRATION' ? '/flightbase' : '/'}
      >
        <PageTemplateProvider>
          <ToastContainer
            position={'bottom-center'}
            autoClose={3000}
            progressStyle={{
              visibility: 'hidden',
            }}
          />
          <Suspense
            fallback={
              <DeferredComponent>
                <FBLoading />
              </DeferredComponent>
            }
          >
            <Switch>
              <PublicRoute
                exact
                path='/'
                isAuth={isAuth}
                type={type}
                component={<LoginPage />}
              />
              <PublicRoute
                exact
                path='/login'
                isAuth={isAuth}
                type={type}
                component={<LoginPage />}
              />
              <Route exact path='/unknownerror'>
                <IntegrationLoginFailPage />
              </Route>
              <AdminRoute
                path='/admin'
                isAuth={isAuth}
                type={type}
                component={<AdminRouter />}
              />
              <UserRoute
                path='/user'
                isAuth={isAuth}
                type={type}
                component={<UserRouter />}
              />
              <Route path='/ui'>
                <UIPage />
              </Route>
              <Route path='/upload'>
                <UploadTestPage />
              </Route>
              <NotFoundPage />
            </Switch>
          </Suspense>
          <ModalContainer />
          <ConfirmPopup />
          <PopupContainer />
          <UploadListContainer />
          <ProgressStatusListContainer />
          <DownloadProgressContainer />
          <Prompt when={prompt.isPrompt} message={() => prompt.message} />
        </PageTemplateProvider>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
