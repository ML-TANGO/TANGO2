// Component
import { lazy, Suspense, useEffect } from 'react';
import { Redirect, Route, Switch, useLocation } from 'react-router-dom';

import AdminFrame from '@src/components/Frame/AdminFrame';
import FBLoading from '@src/components/organisms/FBLoading';

// Actions
import { closeAllModal } from '@src/store/modules/modal';
import DeferredComponent from '@src/hooks/useDeferredComponent';
import TrackingHOC from '@src/hoc/TrackingHOC';

const AdminDashboardPage = lazy(() => import('@src/pages/AdminDashboardPage'));
const AdminWorkspacePage = lazy(() => import('@src/pages/AdminWorkspacePage'));
const AdminTrainingPage = lazy(() => import('@src/pages/AdminTrainingPage'));
const AdminDeploymentPage = lazy(() =>
  import('@src/pages/AdminDeploymentPage'),
);

const AdminBuiltInModelPage = lazy(() =>
  import('@src/pages/AdminBuiltInModelPage'),
);
const AdminDockerImagePage = lazy(() =>
  import('@src/pages/AdminDockerImagePage'),
);
const AdminDatasetPage = lazy(() => import('@src/pages/AdminDatasetPage'));
const DatasetDetailPage = lazy(() => import('@src/pages/DatasetDetailPage'));
const AdminNodePage = lazy(() => import('@src/pages/AdminNodePage'));
const AdminStoragePage = lazy(() => import('@src/pages/AdminStoragePage'));
const AdminNetworkPage = lazy(() => import('@src/pages/AdminNetworkPage'));
const AdminBenchmarkingPage = lazy(() =>
  import('@src/pages/AdminBenchmarkingPage'),
);
const AdminRecordPage = lazy(() => import('@src/pages/AdminRecordPage'));
const AdminUserPage = lazy(() => import('@src/pages/AdminUserPage'));
const AdminBasicBillingPage = lazy(() =>
  import('@src/pages/AdminBasicBillingPage'),
);
const AdminInstanceBillingPage = lazy(() =>
  import('@src/pages/AdminInstanceBillingPage'),
);
const AdminStorageBillingPage = lazy(() =>
  import('@src/pages/AdminStorageBillingPage'),
);
const AdminBillingMonitoringPage = lazy(() =>
  import('@src/pages/AdminBillingMonitoringPage'),
);
const NotFoundPage = lazy(() => import('@src/pages/NotFoundPage'));

const path = '/admin';

function AdminRouter({ trackingEvent }) {
  const location = useLocation();

  const RedirectRoute = ({ ...rest }) => (
    <Route
      {...rest}
      render={(props) => (
        <Redirect
          to={{
            pathname: `${path}/dashboard`,
            state: { from: props.location },
          }}
        />
      )}
    />
  );

  useEffect(() => {
    closeAllModal();
  }, [location]);

  return (
    <AdminFrame type='ADMIN'>
      <Suspense
        fallback={
          <DeferredComponent>
            <div
              style={{
                position: 'fixed',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
              }}
            >
              <FBLoading />
            </div>
          </DeferredComponent>
        }
      >
        <Switch>
          <RedirectRoute exact path={path} />
          <Route
            path={`${path}/dashboard`}
            render={() => <AdminDashboardPage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/workspaces`}
            render={() => <AdminWorkspacePage trackingEvent={trackingEvent} />}
          />
          {/* <Route
            path={`${path}/trainings`}
            render={() => <AdminTrainingPage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/deployments`}
            render={() => <AdminDeploymentPage trackingEvent={trackingEvent} />}
          /> */}
          <Route
            path={`${path}/builtin_models`}
            render={() => (
              <AdminBuiltInModelPage trackingEvent={trackingEvent} />
            )}
          />
          {/* <Route
            path={`${path}/docker_images`}
            render={() => (
              <AdminDockerImagePage trackingEvent={trackingEvent} />
            )}
          /> */}
          <Route
            exact
            path={`${path}/datasets`}
            render={() => <AdminDatasetPage trackingEvent={trackingEvent} />}
          />
          <Route
            exact
            path={`${path}/datasets/:did/files`}
            render={() => <DatasetDetailPage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/nodes`}
            render={() => <AdminNodePage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/storages`}
            render={() => <AdminStoragePage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/networks`}
            render={() => <AdminNetworkPage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/benchmarking`}
            render={() => (
              <AdminBenchmarkingPage trackingEvent={trackingEvent} />
            )}
          />
          <Route
            path={`${path}/records`}
            render={() => <AdminRecordPage trackingEvent={trackingEvent} />}
          />
          <Route
            path={`${path}/users`}
            render={() => <AdminUserPage trackingEvent={trackingEvent} />}
          />
          {/* <Route
            path={`${path}/billing/basic`}
            render={() => (
              <AdminBasicBillingPage trackingEvent={trackingEvent} />
            )}
          /> */}
          {/* <Route
            path={`${path}/billing/instance`}
            render={() => (
              <AdminInstanceBillingPage trackingEvent={trackingEvent} />
            )}
          />
          <Route
            path={`${path}/billing/storage`}
            render={() => (
              <AdminStorageBillingPage trackingEvent={trackingEvent} />
            )}
          />
          <Route
            path={`${path}/billing/monitoring`}
            render={() => (
              <AdminBillingMonitoringPage trackingEvent={trackingEvent} />
            )}
          /> */}
          <NotFoundPage />
        </Switch>
      </Suspense>
    </AdminFrame>
  );
}

export default TrackingHOC(AdminRouter);
