import { lazy } from 'react';

// Admin Page
export const AdminDashboardPage = lazy(() => import('./AdminDashboardPage'));

export const AdminWorkspacePage = lazy(() => import('./AdminWorkspacePage'));

export const AdminTrainingPage = lazy(() => import('./AdminTrainingPage'));

export const AdminDeploymentPage = lazy(() => import('./AdminDeploymentPage'));

export const AdminBuiltInModelPage = lazy(() =>
  import('./AdminBuiltInModelPage'),
);

export const AdminDatasetPage = lazy(() => import('./AdminDatasetPage'));

export const AdminDockerImagePage = lazy(() =>
  import('./AdminDockerImagePage'),
);

export const AdminNodePage = lazy(() => import('./AdminNodePage'));

export const AdminStoragePage = lazy(() => import('./AdminStoragePage'));

export const AdminRecordPage = lazy(() => import('./AdminRecordPage'));

export const AdminNetworkPage = lazy(() => import('./AdminNetworkPage'));

export const AdminBenchmarkingPage = lazy(() =>
  import('./AdminBenchmarkingPage'),
);

export const AdminUserPage = lazy(() => import('./AdminUserPage'));

// User Page
const _UserDashboardPage = import('./UserDashboardPage');
export const UserDashboardPage = lazy(() => _UserDashboardPage);

const _UserHomePage = import('./UserHomePage');
export const UserHomePage = lazy(() => _UserHomePage);

const _UserDockerImagePage = import('./UserDockerImagePage');
export const UserDockerImagePage = lazy(() => _UserDockerImagePage);

const _UserDatasetPage = import('./UserDatasetPage');
export const UserDatasetPage = lazy(() => _UserDatasetPage);

const _UserTrainingPage = import('./UserTrainingPage');
export const UserTrainingPage = lazy(() => _UserTrainingPage);

export const UserCheckpointPage = lazy(() => import('./UserCheckpointPage'));

const _UserTrainingInfoPage = import('./UserTrainingInfoPage');
export const UserTrainingInfoPage = lazy(() => _UserTrainingInfoPage);

const _UserWorkbenchPage = import('./UserWorkbenchPage');
export const UserWorkbenchPage = lazy(() => _UserWorkbenchPage);

const _UserFederatedLearningPage = import('./UserFederatedLearningPage');
export const UserFederatedLearningPage = lazy(() => _UserFederatedLearningPage);

const _UserJobPage = import('./UserJobPage');
export const UserJobPage = lazy(() => _UserJobPage);

const _UserHpsPage = import('./UserHpsPage');
export const UserHpsPage = lazy(() => _UserHpsPage);

const _UserDeploymentPage = import('./UserDeploymentPage');

export const UserDeploymentPage = lazy(() => _UserDeploymentPage);
export const UserDeploymentInfoPage = lazy(() =>
  import('./UserDeploymentInfoPage'),
);

const _DeployDashboardPage = import('./DeployDashboardPage');
export const DeployDashboardPage = lazy(() => _DeployDashboardPage);

const _DeployWorkerDashboardPage = import('./DeployWorkerDashboardPage');
export const DeployWorkerDashboardPage = lazy(() => _DeployWorkerDashboardPage);

export const DeployWorkerPage = lazy(() => import('./DeployWorkerPage'));
export const UserServicePage = lazy(() => import('./UserServicePage'));

const _UserTestPage = import('./UserTestPage');
export const UserTestPage = lazy(() => _UserTestPage);

const _DatasetDetailPage = import('./DatasetDetailPage');
export const DatasetDetailPage = lazy(() => _DatasetDetailPage);

// Common Page
export const NotFoundPage = lazy(() => import('./NotFoundPage'));
