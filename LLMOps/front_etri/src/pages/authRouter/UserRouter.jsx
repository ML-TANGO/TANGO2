import React, { lazy, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import {
  Redirect,
  Route,
  Switch,
  useHistory,
  useLocation,
  useRouteMatch,
} from 'react-router-dom';

import { loadModalComponent } from '@src/modal';

import IconPipeLineActive from '@src/static/images/icon/00-ic-basic-renew-blue.svg';
import IconPipeLine from '@src/static/images/icon/00-ic-basic-renew.svg';
import IconNavPlaygroundActive from '@src/static/images/nav/00-ic-nav-playground-active.svg';
import IconNavPlayground from '@src/static/images/nav/00-ic-nav-playground.svg';
import IconDataCollectActive from '@src/static/images/nav/data-collect-active-icon.svg';
import IconDataCollect from '@src/static/images/nav/data-collect-icon.svg';
import IconHpsActive from '@src/static/images/nav/hps-active-blue.svg';
import IconAnalysisActive from '@src/static/images/nav/ic-dataset-analysis-active.svg';
import IconAnalysis from '@src/static/images/nav/ic-dataset-analysis.svg';
import IconManagementActive from '@src/static/images/nav/ic-dataset-management-active.svg';
import IconManagement from '@src/static/images/nav/ic-dataset-management.svg';
import IconLnbDashboardBlue from '@src/static/images/nav/icon-lnb-dashboard-blue.svg';
import IconLnbDashboardGray from '@src/static/images/nav/icon-lnb-dashboard-gray.svg';
import IconLnbDatasetsBlue from '@src/static/images/nav/icon-lnb-dataset-blue.svg';
import IconLnbDatasetsGray from '@src/static/images/nav/icon-lnb-dataset-gray.svg';
import IconLnbDockerBlue from '@src/static/images/nav/icon-lnb-dockerimage-blue.svg';
import IconLnbDockerGray from '@src/static/images/nav/icon-lnb-dockerimage-gray.svg';
import IconLnbFederatedLearningBlue from '@src/static/images/nav/icon-lnb-federatedLearning-blue.svg';
import IconLnbFederatedLearningGray from '@src/static/images/nav/icon-lnb-federatedLearning-gray.svg';
import IconLnbHomeBlue from '@src/static/images/nav/icon-lnb-home-blue.svg';
import IconLnbHomeGray from '@src/static/images/nav/icon-lnb-home-gray.svg';
import IconLnbInformationBlue from '@src/static/images/nav/icon-lnb-information-blue.svg';
import IconLnbInformationGray from '@src/static/images/nav/icon-lnb-information-gray.svg';
import IconLnbNewHpsGray from '@src/static/images/nav/icon-lnb-new-hps-gray.svg';
import IconLnbNewJobBlue from '@src/static/images/nav/icon-lnb-new-job-blue.svg';
import IconLnbNewJobGray from '@src/static/images/nav/icon-lnb-new-job-gray.svg';
import IconRecordGray from '@src/static/images/nav/icon-lnb-record-gray.svg';
import IconLnbServingBlue from '@src/static/images/nav/icon-lnb-serving-blue.svg';
import IconLnbServingGray from '@src/static/images/nav/icon-lnb-serving-gray.svg';
import IconLnbTestBlue from '@src/static/images/nav/icon-lnb-test-blue.svg';
import IconLnbTestGray from '@src/static/images/nav/icon-lnb-test-gray.svg';
import IconLnbTrainingsBlue from '@src/static/images/nav/icon-lnb-training-blue.svg';
import IconLnbTrainingsGray from '@src/static/images/nav/icon-lnb-training-gray.svg';
import IconLnbWorkbenchBlue from '@src/static/images/nav/icon-lnb-workbench-blue.svg';
import IconLnbWorkbenchGray from '@src/static/images/nav/icon-lnb-workbench-gray.svg';
import IconLnbWorkerBlue from '@src/static/images/nav/icon-lnb-worker-blue.svg';
import IconLnbWorkerGray from '@src/static/images/nav/icon-lnb-worker-gray.svg';
import IconNavFlightbase from '@src/static/images/nav/Jonathan-fb.png';
import IconNavLLM from '@src/static/images/nav/Jonathan-llm.png';
import IconNavMarker from '@src/static/images/nav/Jonathan-marker.png';
import IconNavService from '@src/static/images/nav/Jonathan-service.png';
import IconMarkerLink from '@src/static/images/nav/marker-link.svg';
import IconModelActive from '@src/static/images/nav/model-active.svg';
import IconModel from '@src/static/images/nav/model.svg';
import IconPreProcessActive from '@src/static/images/nav/pre-process-active.svg';
import IconPreProcess from '@src/static/images/nav/pre-process.svg';
import IconPipelineProjectActive from '@src/static/images/nav/project-active.svg';
import IconPromptActive from '@src/static/images/nav/prompt-active.svg';
import IconPrompt from '@src/static/images/nav/prompt.svg';
import IconRagActive from '@src/static/images/nav/rag-active.svg';
import IconRag from '@src/static/images/nav/rag.svg';

import '@jonathan/ui-react/index.css';

import Alarm from '@src/components/Frame/Header/Alarm';
// Template
import PageTemplate from '@src/components/templates/PageTemplate';

import { closeAllModal } from '@src/store/modules/modal';
import usePrevScroll from '@src/hooks/usePrevScroll';
import TrackingHOC from '@src/hoc/TrackingHOC';

import useMoveToMarker from './useMoveToMarker';

import classNames from 'classnames/bind';
import style from './UserRouter.module.scss';

const Model = lazy(() => import('../llm/Model'));
const ModelDetailPage = lazy(() => import('../llm/Model/ModelDetailPage'));
const RagDetailPage = lazy(() => import('../llm/Rag/RagDetailPage'));

const Rag = lazy(() => import('../llm/Rag'));

const SelectedPage = lazy(() => import('../SelectedPage'));

const UserDatasetCollectDetailPage = lazy(() =>
  import('../UserDatasetCollectDetailPage'),
);

const Dashboard = lazy(() => import('@src/pages/llm/DashboardPage'));

const cx = classNames.bind(style);

const UserPipeLineInfo = lazy(() =>
  import(
    '@src/components/pageContents/user/UserPipeLineContent/UserPipeLineInfo'
  ),
);

const UserPipeLineSetting = lazy(() =>
  import(
    '@src/components/pageContents/user/UserPipeLineContent/UserPipeLineSetting'
  ),
);

const UserPipeLineContent = lazy(() =>
  import('@src/components/pageContents/user/UserPipeLineContent'),
);

const UserDatasetRedirectPage = lazy(() =>
  import('@src/pages/UserDatasetRedirectPage'),
);

const UserDataCollectMenuPage = lazy(() =>
  import('@src/pages/UserDataCollectMenuPage'),
);

const ModelCommitListItem = lazy(() =>
  import('@src/pages/llm/Model/ModelDetailPage/CommitList/ModelCommitListItem'),
);

const PromptCommitPage = lazy(() =>
  import('@src/pages/llm/Prompt/PromptCommitPage'),
);

const PromptDetail = lazy(() =>
  import('@src/pages/llm/Prompt/PromptDetailPage'),
);

const UserPipeLineMenu = lazy(() =>
  import(
    '@src/components/pageContents/user/UserPipeLineContent/UserPipeLineMenu'
  ),
);
const UserPipelineHistoryDetail = lazy(() =>
  import(
    '@src/components/pageContents/user/UserPipeLineContent/UserPipelineHistoryDetail'
  ),
);

const PromptMenuPage = lazy(() =>
  import('@src/pages/llm/Prompt/PromptMenuPage/PromptMenuPage'),
);

const PlaygroundMenu = lazy(() => import('../llm/Playground/PlaygroundMenu'));
const PlaygroundDetail = lazy(() =>
  import('../llm/Playground/PlaygroundDetail'),
);

const LLMDatasetPage = lazy(() => import('@src/pages/llm/LLMDatasetPage'));

// Pages
const UserDashboardPage = lazy(() => import('@src/pages/UserDashboardPage'));
const UserDockerImagePage = lazy(() =>
  import('@src/pages/UserDockerImagePage'),
);
const UserJobPage = lazy(() => import('@src/pages/UserJobPage'));
const UserDeploymentInfoPage = lazy(() =>
  import('@src/pages/UserDeploymentInfoPage'),
);
const UserTrainingInfoPage = lazy(() =>
  import('@src/pages/UserTrainingInfoPage'),
);
const DeployWorkerPage = lazy(() => import('@src/pages/DeployWorkerPage'));
const DeployWorkerDashboardPage = lazy(() =>
  import('@src/pages/DeployWorkerDashboardPage'),
);
const DeployDashboardPage = lazy(() =>
  import('@src/pages/DeployDashboardPage'),
);
const UserHomePage = lazy(() => import('@src/pages/UserHomePage'));
const UserDatasetPage = lazy(() => import('@src/pages/UserDatasetPage'));
const DatasetDetailPage = lazy(() => import('@src/pages/DatasetDetailPage'));
const UserTrainingPage = lazy(() => import('@src/pages/UserTrainingPage'));
const UserHpsPage = lazy(() => import('@src/pages/UserHpsPage'));
const UserCheckpointPage = lazy(() => import('@src/pages/UserCheckpointPage'));
const UserWorkbenchPage = lazy(() => import('@src/pages/UserWorkbenchPage'));
const UserFederatedLearningPage = lazy(() =>
  import('@src/pages/UserFederatedLearningPage'),
);
const UserDeploymentPage = lazy(() => import('@src/pages/UserDeploymentPage'));
const UserServicePage = lazy(() => import('@src/pages/UserServicePage'));
const UserTestPage = lazy(() => import('@src/pages/UserTestPage'));
const NotFoundPage = lazy(() => import('@src/pages/NotFoundPage'));
const UserDatasetPreprocessPage = lazy(() =>
  import('@src/pages/UserDatasetPreprocessPage'),
);
const UserDatasetPreprocessDetailPage = lazy(() =>
  import('@src/pages/UserDatasetPreprocessDetailPage'),
);

const UserDatasetAnalysisPage = lazy(() =>
  import('@src/pages/UserDatasetAnalysisPage'),
);
const UserDatasetAnalysisDetailPage = lazy(() =>
  import('@src/pages/UserDatasetAnalysisDetailPage'),
);

const IS_HIDE_TRAINING =
  import.meta.env.VITE_REACT_APP_IS_HIDE_TRAINING === 'true';
const IS_HIDE_JOB = import.meta.env.VITE_REACT_APP_IS_HIDE_JOB === 'true';
const IS_HIDE_HPS = import.meta.env.VITE_REACT_APP_IS_HIDE_HPS === 'true';
const IS_HIDE_DEPLOYMENT =
  import.meta.env.VITE_REACT_APP_IS_HIDE_DEPLOYMENT === 'true';
const IS_HIDE_TEST = import.meta.env.VITE_REACT_APP_IS_HIDE_TEST === 'true';
const IS_FL = import.meta.env.VITE_REACT_APP_IS_FEDERATED_LEARNING === 'true';

const trainingGroup = {
  backPath: '/user/workspace/:id/trainings',
  backPathBtnText: 'Training',
  target: 'TRAINING',
};

const pipeLineGroup = {
  backPath: '/user/workspace/:id/pipeline',
  backPathBtnText: 'Pipeline',
  target: 'PIPELINE',
};

const workbenchGroup = {
  backPath: '/user/workspace/:id/trainings/:tid/workbench',
  backPathBtnText: 'Workbench',
  target: 'WORKBENCH',
};

const deployGroup = {
  backPath: '/user/workspace/:id/deployments',
  backPathBtnText: 'Deployment',
  target: 'DEPLOY',
};

const datasetGroup = {
  backPath: '/user/workspace/:id/datasets',
  backPathBtnText: 'Dataset',
  target: 'DATASET',
};

const noneArr = [
  {
    name: 'Dashboard',
    path: '/user/dashboard',
    exact: true,
    disabled: true,
    platform: null,
    render: (props) => <UserDashboardPage {...props} />,
  },
  {
    name: 'Selected',
    path: '/user/workspace/:id/selected',
    exact: true,
    disabled: true,
    icon: IconLnbTestGray,
    activeIcon: IconLnbTestBlue,
    platform: null,
    render: () => <SelectedPage />,
  },
];

const llmRouteArr = [
  ...noneArr,
  // {
  //   name: 'Home',
  //   path: '/user/workspace/:id/llmhome',
  //   exact: true,
  //   disabled: false,
  //   icon: IconLnbHomeGray,
  //   activeIcon: IconLnbHomeBlue,
  //   platform: 'llm',
  //   render: (props) => <Dashboard {...props} />,
  // },

  {
    name: 'Dataset',
    path: '/user/workspace/:id/llm-datasets',
    exact: true,
    icon: IconLnbDatasetsGray,
    activeIcon: IconLnbDatasetsBlue,
    platform: 'llm',
    render: (props) => <LLMDatasetPage {...props} />,
  },
  {
    name: 'Dataset Detail',
    path: '/user/workspace/:id/llm-datasets/:did/files',
    exact: true,
    disabled: true,
    icon: IconLnbDatasetsGray,
    activeIcon: IconLnbDatasetsBlue,
    platform: 'llm',
    render: (props) => <DatasetDetailPage {...props} />,
  },
  {
    name: 'Training',
    path: '/user/workspace/:id/model',
    exact: true,
    disabled: false,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'llm',
    render: (props) => <Model {...props} />,
  },
  {
    name: 'Model Detail',
    path: '/user/workspace/:id/model/:mId',
    exact: false,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'llm',
    render: (props) => <ModelDetailPage {...props} />,
  },
  {
    name: 'Model CommitList Item',
    path: '/user/workspace/:id/model/:mId/commit-list/:cId',
    exact: false,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'llm',
    render: (props) => <ModelCommitListItem {...props} />,
  },
  {
    name: 'Playground',
    path: '/user/workspace/:id/llmplayground',
    exact: true,
    icon: IconNavPlayground,
    activeIcon: IconNavPlaygroundActive,
    platform: 'llm',
    render: (props) => <PlaygroundMenu {...props} />,
  },
  {
    name: 'PlaygroundDetail',
    path: '/user/workspace/:id/llmplayground/:did/llmplayground',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'llm',
    render: (props) => <PlaygroundDetail {...props} />,
  },
  {
    name: 'PlaygroundMonitoring',
    path: '/user/workspace/:id/llmplayground/:did/detail/:newId/playgroundmonitor',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'llm',
    render: (props) => <DeployDashboardPage {...props} />,
  },
];

const routeArr = [
  ...noneArr,
  // ...llmRouteArr,
  // {
  //   name: 'Home',
  //   path: '/user/workspace/:id/home',
  //   exact: true,
  //   icon: IconLnbHomeGray,
  //   activeIcon: IconLnbHomeBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserHomePage {...props} />,
  // },

  {
    name: 'Home',
    path: '/user/workspace/:id/home',
    exact: true,
    disabled: false,
    icon: IconLnbHomeGray,
    activeIcon: IconLnbHomeBlue,
    platform: 'flightbase',
    render: (props) => <Dashboard {...props} />,
  },

  // {
  //   name: 'Docker Image',
  //   path: '/user/workspace/:id/docker_images',
  //   exact: true,
  //   icon: IconLnbDockerGray,
  //   activeIcon: IconLnbDockerBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserDockerImagePage {...props} />,
  // },
  // {
  //   name: 'Dataset',
  //   path: '/user/workspace/:id/datasets',
  //   exact: true,
  //   isGroup: true,
  //   icon: IconLnbDatasetsGray,
  //   activeIcon: IconLnbDatasetsBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetRedirectPage {...props} />,
  // },
  // {
  //   name: 'collect.label',
  //   path: '/user/workspace/:id/datasets/collect/:did/detail',
  //   disabled: true,
  //   exact: false,
  //   group: datasetGroup,
  //   icon: IconDataCollect,
  //   activeIcon: IconDataCollectActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetCollectDetailPage {...props} />,
  // },
  // {
  //   name: 'collect.label',
  //   path: '/user/workspace/:id/datasets/collect',
  //   group: datasetGroup,
  //   isFirstGroup: true,
  //   icon: IconDataCollect,
  //   activeIcon: IconDataCollectActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDataCollectMenuPage {...props} />,
  // },
  // {
  //   name: 'preprocess.label',
  //   path: '/user/workspace/:id/datasets/process',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   icon: IconPreProcess,
  //   activeIcon: IconPreProcessActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetPreprocessPage {...props} />,
  // },
  // {
  //   name: '전처리 디테일',
  //   path: '/user/workspace/:id/datasets/process/:did/detail',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   disabled: true,
  //   icon: IconPreProcess,
  //   activeIcon: IconPreProcessActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetPreprocessDetailPage {...props} />,
  // },
  // {
  //   name: 'analyze.label',
  //   path: '/user/workspace/:id/datasets/analysis',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   icon: IconAnalysis,
  //   activeIcon: IconAnalysisActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetAnalysisPage {...props} />,
  // },
  // {
  //   name: 'Data Analysis Detail',
  //   path: '/user/workspace/:id/datasets/analysis/:did/detail',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   disabled: true,
  //   icon: IconAnalysis,
  //   activeIcon: IconAnalysisActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetAnalysisDetailPage {...props} />,
  // },
  // {
  //   name: 'management.label',
  //   path: '/user/workspace/:id/datasets/management',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   isLastGroup: true,
  //   icon: IconManagement,
  //   activeIcon: IconManagementActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserDatasetPage {...props} />,
  // },
  // {
  //   name: 'Dataset Detail',
  //   path: '/user/workspace/:id/datasets/management/:did/files',
  //   exact: true,
  //   isGroup: true,
  //   group: datasetGroup,
  //   disabled: true,
  //   icon: IconLnbDatasetsGray,
  //   activeIcon: IconLnbDatasetsBlue,
  //   platform: 'flightbase',
  //   render: (props) => <DatasetDetailPage {...props} />,
  // },
  {
    name: 'Dataset',
    path: '/user/workspace/:id/datasets/management',
    exact: true,
    icon: IconLnbDatasetsGray,
    activeIcon: IconLnbDatasetsBlue,
    platform: 'flightbase',
    render: (props) => <UserDatasetPage {...props} />,
  },
  {
    name: 'Dataset Detail',
    path: '/user/workspace/:id/datasets/management/:did/files',
    exact: true,
    disabled: true,
    icon: IconLnbDatasetsGray,
    activeIcon: IconLnbDatasetsBlue,
    platform: 'flightbase',
    render: (props) => <DatasetDetailPage {...props} />,
  },
  // {
  //   name: 'Training',
  //   path: '/user/workspace/:id/trainings',
  //   exact: true,
  //   isGroup: true,
  //   disabled: IS_HIDE_TRAINING,
  //   icon: IconLnbTrainingsGray,
  //   activeIcon: IconLnbTrainingsBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserTrainingPage {...props} />,
  // },
  // {
  //   name: 'Workbench',
  //   path: '/user/workspace/:id/trainings/:tid/workbench',
  //   exact: true,
  //   group: trainingGroup,
  //   isGroup: !IS_HIDE_JOB || !IS_HIDE_HPS,
  //   isFirstGroup: true,
  //   icon: IconLnbWorkbenchGray,
  //   activeIcon: IconLnbWorkbenchBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserWorkbenchPage {...props} />,
  // },
  // {
  //   name: 'JOB',
  //   path: '/user/workspace/:id/trainings/:tid/workbench/job',
  //   exact: true,
  //   disabled: IS_HIDE_JOB,
  //   group: trainingGroup,
  //   subGroup: workbenchGroup,
  //   icon: IconLnbNewJobGray,
  //   activeIcon: IconLnbNewJobBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserJobPage {...props} />,
  // },
  // {
  //   name: 'HPS',
  //   path: '/user/workspace/:id/trainings/:tid/workbench/hps',
  //   exact: true,
  //   disabled: IS_HIDE_HPS,
  //   group: trainingGroup,
  //   readOnly: true,
  //   subGroup: workbenchGroup,
  //   icon: IconLnbNewHpsGray,
  //   activeIcon: IconHpsActive,
  //   platform: 'flightbase',

  //   render: (props) => <UserHpsPage {...props} />,
  // },
  // {
  //   name: 'FL',
  //   path: '/user/workspace/:id/trainings/:tid/federated-learning',
  //   exact: true,
  //   disabled: !IS_FL,
  //   group: trainingGroup,
  //   // isFirstGroup: true,
  //   icon: IconLnbFederatedLearningGray,
  //   activeIcon: IconLnbFederatedLearningBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserFederatedLearningPage {...props} />,
  // },
  // {
  //   name: 'Training Info',
  //   path: '/user/workspace/:id/trainings/:tid/info',
  //   exact: true,
  //   group: trainingGroup,
  //   isLastGroup: true,
  //   icon: IconLnbInformationGray,
  //   activeIcon: IconLnbInformationBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserTrainingInfoPage {...props} />,
  // },
  // {
  //   name: 'Checkpoint',
  //   path: '/user/workspace/:id/checkpoints',
  //   exact: true,
  //   disabled: true,
  //   icon: IconLnbTrainingsGray,
  //   activeIcon: IconLnbTrainingsBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserCheckpointPage {...props} />,
  // },
  // {
  //   name: 'Deployment',
  //   path: '/user/workspace/:id/deployments',
  //   exact: true,
  //   isGroup: true,
  //   disabled: IS_HIDE_DEPLOYMENT,
  //   icon: IconLnbServingGray,
  //   activeIcon: IconLnbServingBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserDeploymentPage {...props} />,
  // },
  // {
  //   name: 'Monitoring',
  //   path: '/user/workspace/:id/deployments/:did/dashboard',
  //   group: deployGroup,
  //   isFirstGroup: true,
  //   icon: IconLnbDashboardGray,
  //   activeIcon: IconLnbDashboardBlue,
  //   platform: 'flightbase',
  //   render: (props) => <DeployDashboardPage {...props} />,
  // },
  // {
  //   name: 'Worker',
  //   path: '/user/workspace/:id/deployments/:did/workers',
  //   exact: true,
  //   group: deployGroup,
  //   icon: IconLnbWorkerGray,
  //   activeIcon: IconLnbWorkerBlue,
  //   platform: 'flightbase',
  //   render: (props) => <DeployWorkerPage {...props} />,
  // },
  // {
  //   name: 'Worker Detail',
  //   path: '/user/workspace/:id/deployments/:did/workers/:wkid/worker',
  //   exact: true,
  //   group: deployGroup,
  //   disabled: true,
  //   icon: IconLnbWorkerGray,
  //   activeIcon: IconLnbWorkerBlue,
  //   platform: 'flightbase',
  //   render: (props) => <DeployWorkerDashboardPage {...props} />,
  // },
  // {
  //   name: 'Deployment Info',
  //   path: '/user/workspace/:id/deployments/:did/info',
  //   exact: true,
  //   group: deployGroup,
  //   isLastGroup: true,
  //   icon: IconLnbInformationGray,
  //   activeIcon: IconLnbInformationBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserDeploymentInfoPage {...props} />,
  // },
  // {
  //   name: 'AIPipeline',
  //   path: '/user/workspace/:id/pipeline',
  //   exact: true,
  //   isGroup: true,
  //   icon: IconPipeLine,
  //   activeIcon: IconPipeLineActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserPipeLineMenu {...props} />,
  // },
  // {
  //   name: 'project.label',
  //   path: '/user/workspace/:id/pipeline/:tid',
  //   exact: true,
  //   disabled: true,
  //   icon: IconLnbTrainingsGray,
  //   activeIcon: IconPipelineProjectActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserPipeLineContent {...props} />,
  // },
  // {
  //   name: 'project.label',
  //   path: '/user/workspace/:id/pipeline/:tid/historydetail/:did',
  //   exact: true,
  //   disabled: true,
  //   icon: IconLnbTrainingsGray,
  //   activeIcon: IconPipelineProjectActive,
  //   platform: 'flightbase',
  //   render: (props) => <UserPipelineHistoryDetail {...props} />,
  // },
  // {
  //   name: 'history.label',
  //   path: '/user/workspace/:id/pipline/history',
  //   exact: true,
  //   group: pipeLineGroup,
  //   readOnly: true,
  //   isLastGroup: true,
  //   icon: IconRecordGray,
  //   activeIcon: IconLnbInformationBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserTrainingInfoPage {...props} />,
  // },
  // {
  //   name: 'Test',
  //   path: '/user/workspace/:id/services',
  //   exact: true,
  //   disabled: IS_HIDE_TEST,
  //   icon: IconLnbTestGray,
  //   activeIcon: IconLnbTestBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserServicePage {...props} />,
  // },
  // {
  //   name: 'Test',
  //   path: '/user/workspace/:id/services/:sid/test',
  //   exact: true,
  //   disabled: true,
  //   icon: IconLnbTestGray,
  //   activeIcon: IconLnbTestBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserTestPage {...props} />,
  // },
  {
    name: 'Training',
    path: '/user/workspace/:id/model',
    exact: true,
    // disabled: false,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <Model {...props} />,
  },
  {
    name: 'Model Detail',
    path: '/user/workspace/:id/model/:mId',
    exact: false,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <ModelDetailPage {...props} />,
  },
  {
    name: 'Model CommitList Item',
    path: '/user/workspace/:id/model/:mId/commit-list/:cId',
    exact: false,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <ModelCommitListItem {...props} />,
  },
  {
    name: 'Playground',
    path: '/user/workspace/:id/llmplayground',
    exact: true,
    icon: IconNavPlayground,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <PlaygroundMenu {...props} />,
  },
  {
    name: 'PlaygroundDetail',
    path: '/user/workspace/:id/llmplayground/:did/llmplayground',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <PlaygroundDetail {...props} />,
  },
  {
    name: 'PlaygroundMonitoring',
    path: '/user/workspace/:id/llmplayground/:did/detail/:newId/playgroundmonitor',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <DeployDashboardPage {...props} />,
  },
  {
    name: 'Evaluation',
    path: '/user/workspace/:id/services',
    exact: true,
    icon: IconLnbTestGray,
    activeIcon: IconLnbTestBlue,
    platform: 'flightbase',
    render: (props) => <UserServicePage {...props} />,
  },
  {
    name: 'Deployment',
    path: '/user/workspace/:id/deployments',
    exact: true,
    icon: IconLnbServingGray,
    activeIcon: IconLnbServingBlue,
    platform: 'flightbase',
    render: (props) => <UserDeploymentPage {...props} />,
  },
];

const calSideNavList = (selectedPlatform) => {
  if (!selectedPlatform) return routeArr.filter((route) => !route.platform);
  if (selectedPlatform === 1) {
    return routeArr.filter((route) => route.platform === 'flightbase');
  }
  return routeArr.filter((route) => route.platform === 'llm');
};

const RedirectRoute = ({ ...rest }) => (
  <Route
    {...rest}
    render={(props) => (
      <Redirect
        to={{ pathname: '/user/dashboard', state: { from: props.location } }}
      />
    )}
  />
);

const platFormList = [
  { label: 'flightbase', value: 1, icon: IconNavFlightbase, target: 'link' },
  // {
  //   label: 'marker',
  //   value: 0,
  //   icon: IconNavMarker,
  //   target: 'link',
  //   rightIcon: IconMarkerLink,
  // },
  // { label: 'LLM', value: 2, icon: IconNavLLM, target: 'link' },
  // { label: 'service', value: 3, icon: IconNavService, target: 'link' },
];
const PlatformNav = ({
  selectedPlatform,
  setSelectedPlatform,
  handleSelectPlatform,
  children,
  moveToMarker,
}) => {
  const match = useRouteMatch();
  const history = useHistory();

  const { path } = match;
  const { id: workspaceId } = match.params;

  if (!workspaceId) handleSelectPlatform(null);

  useEffect(() => {
    if (!path.includes('/home')) return;
    setSelectedPlatform(1);
  }, [path, setSelectedPlatform]);

  useEffect(() => {
    const curPlatform = routeArr.filter((v) => v.path === path)[0].platform;

    if (curPlatform === 'flightbase') {
      setSelectedPlatform(1);
    }
    if (curPlatform === 'llm') {
      setSelectedPlatform(2);
    }
  }, []);

  return (
    <nav className={cx('platform-nav')}>
      {platFormList.map((info) => (
        <React.Fragment key={info.value}>
          {info.target === 'blank' && <div className={cx('border')} />}
          <li
            className={cx(
              'item',
              selectedPlatform === info.value && 'selected',
              info.target === 'blank' && 'marker',
            )}
            onClick={() =>
              handleSelectPlatform(
                info.value,
                setSelectedPlatform,
                history,
                workspaceId,
                moveToMarker,
              )
            }
          >
            {/* <img src={info.icon} alt={info.label} /> */}
            {/* {info.rightIcon && <img src={info.rightIcon} alt={info.label} />} */}
            <div>GenAI Platform</div>
          </li>
          {selectedPlatform === info.value && <>{children}</>}
        </React.Fragment>
      ))}
    </nav>
  );
};

const handleSelectPlatform = (
  selectedPlatform,
  setSelectedPlatform,
  history,
  workspaceId,
  moveToMarker,
) => {
  if (selectedPlatform === 0) {
    // alert('marker로 이동');
    moveToMarker({ workspaceId });
    return;
  }
  // if (selectedPlatform === 3) {
  //   // 모델 베이스 이동
  //   window.open('https://servicebase.acryl.ai');
  //   return;
  // }
  history.push({
    pathname:
      selectedPlatform === 1
        ? `/user/workspace/${workspaceId}/home`
        : `/user/workspace/${workspaceId}/llmhome`,
  });
  setSelectedPlatform(selectedPlatform);
};

function UserRouter({ trackingEvent }) {
  const { path } = useRouteMatch();
  const location = useLocation();
  const dispatch = useDispatch();
  const { moveToMarker } = useMoveToMarker();

  // 이전 스크롤 위치 기억하기 위한 hook
  usePrevScroll();

  useEffect(() => {
    loadModalComponent('CHANGE_PASSWORD');
    return () => setSelectedPlatform(null);
  }, []);

  useEffect(() => {
    dispatch(closeAllModal());
  }, [dispatch, location]);

  const element = document.querySelector(
    '[data-testid="open-user-context-popup-btn"]',
  );
  const rightBoxWidth = element && element.getBoundingClientRect().width;

  const [selectedPlatform, setSelectedPlatform] = useState(null);
  const sideNavList = calSideNavList(selectedPlatform);

  return (
    <div>
      {element && (
        <>
          <div
            className={cx('strange-header-alarm')}
            style={{
              position: 'fixed',
              zIndex: '500',
              right: `${rightBoxWidth + 89}px`,
              top: '16px',
            }}
          >
            <Alarm />
          </div>
          <div
            className={cx('strange-header-data')}
            style={{
              position: 'fixed',
              zIndex: '500',
              right: `${rightBoxWidth + 139}px`,
              top: '16px',
            }}
          >
            {/* <DatasetUpload></DatasetUpload> */}
          </div>
        </>
      )}

      <Switch>
        <RedirectRoute exact path={path} />
        {routeArr.map(({ path, exact, render }, key) => {
          return (
            <Route exact={exact} path={path} key={key}>
              <PageTemplate
                navList={sideNavList}
                mainNavComponent={
                  <PlatformNav
                    selectedPlatform={selectedPlatform}
                    setSelectedPlatform={setSelectedPlatform}
                    handleSelectPlatform={handleSelectPlatform}
                    moveToMarker={moveToMarker}
                  />
                }
                handleResetPlatform={setSelectedPlatform}
              >
                {render({ trackingEvent })}
              </PageTemplate>
            </Route>
          );
        })}
        <NotFoundPage />
      </Switch>
    </div>
  );
}

export default TrackingHOC(UserRouter);
