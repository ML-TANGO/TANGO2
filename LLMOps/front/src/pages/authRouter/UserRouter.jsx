import React, { lazy, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import {
  NavLink,
  Redirect,
  Route,
  Switch,
  useHistory,
  useLocation,
  useRouteMatch,
} from 'react-router-dom';

import { loadModalComponent } from '@src/modal';

import IconPipeLineActive from '@src/static/images/nav/ic-pipeline-blue.svg';
import IconPipeLine from '@src/static/images/nav/ic-pipeline-gray.svg';
import IconNavPlaygroundActive from '@src/static/images/nav/00-ic-nav-playground-active.svg';
import IconNavPlayground from '@src/static/images/nav/00-ic-nav-playground.svg';
import IconDataCollectActive from '@src/static/images/nav/data-collect-active-icon.svg';
import IconDataCollect from '@src/static/images/nav/data-collect-icon.svg';
import IconSynthesisActive from '@src/static/images/nav/synthesis-active-icon.svg';
import IconSynthesis from '@src/static/images/nav/synthesis-icon.svg';
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
const EdgeDeploymentDetail = lazy(() => import('../llm/Edge/EdgeDeploymentDetail'));
const StandaloneDeploymentDetail = lazy(() =>
  import('../llm/Standalone/StandaloneDeploymentDetail'),
);
const RagDetailPage = lazy(() => import('../llm/Rag/RagDetailPage'));

const Rag = lazy(() => import('../llm/Rag'));

const SelectedPage = lazy(() => import('../SelectedPage'));

const UserDatasetCollectDetailPage = lazy(
  () => import('../UserDatasetCollectDetailPage'),
);

const Dashboard = lazy(() => import('@src/pages/llm/DashboardPage'));

const cx = classNames.bind(style);

const UserPipeLineInfo = lazy(
  () =>
    import('@src/components/pageContents/user/UserPipeLineContent/UserPipeLineInfo'),
);

const UserPipeLineSetting = lazy(
  () =>
    import('@src/components/pageContents/user/UserPipeLineContent/UserPipeLineSetting'),
);

const UserPipeLineContent = lazy(
  () => import('@src/components/pageContents/user/UserPipeLineContent'),
);

const UserDatasetRedirectPage = lazy(
  () => import('@src/pages/UserDatasetRedirectPage'),
);

const UserDataCollectMenuPage = lazy(
  () => import('@src/pages/UserDataCollectMenuPage'),
);

const UserDatasetLabelingPage = lazy(
  () => import('@src/pages/UserDatasetLabelingPage'),
);

const ModelCommitListItem = lazy(
  () =>
    import('@src/pages/llm/Model/ModelDetailPage/CommitList/ModelCommitListItem'),
);

const PromptCommitPage = lazy(
  () => import('@src/pages/llm/Prompt/PromptCommitPage'),
);

const PromptDetail = lazy(
  () => import('@src/pages/llm/Prompt/PromptDetailPage'),
);

const UserPipeLineMenu = lazy(
  () =>
    import('@src/components/pageContents/user/UserPipeLineContent/UserPipeLineMenu'),
);
const UserPipelineHistoryDetail = lazy(
  () =>
    import('@src/components/pageContents/user/UserPipeLineContent/UserPipelineHistoryDetail'),
);

const PromptMenuPage = lazy(
  () => import('@src/pages/llm/Prompt/PromptMenuPage/PromptMenuPage'),
);

const PlaygroundMenu = lazy(() => import('../llm/Playground/PlaygroundMenu'));
const PlaygroundDetail = lazy(
  () => import('../llm/Playground/PlaygroundDetail'),
);

const LLMDatasetPage = lazy(() => import('@src/pages/llm/LLMDatasetPage'));

// Pages
const UserDashboardPage = lazy(() => import('@src/pages/UserDashboardPage'));
const UserDockerImagePage = lazy(
  () => import('@src/pages/UserDockerImagePage'),
);
const UserJobPage = lazy(() => import('@src/pages/UserJobPage'));
const UserDeploymentInfoPage = lazy(
  () => import('@src/pages/UserDeploymentInfoPage'),
);
const UserTrainingInfoPage = lazy(
  () => import('@src/pages/UserTrainingInfoPage'),
);
const DeployWorkerPage = lazy(() => import('@src/pages/DeployWorkerPage'));
const DeployWorkerDashboardPage = lazy(
  () => import('@src/pages/DeployWorkerDashboardPage'),
);
const DeployDashboardPage = lazy(
  () => import('@src/pages/DeployDashboardPage'),
);
const UserHomePage = lazy(() => import('@src/pages/UserHomePage'));
const UserDatasetPage = lazy(() => import('@src/pages/UserDatasetPage'));
const DatasetDetailPage = lazy(() => import('@src/pages/DatasetDetailPage'));
const UserTrainingPage = lazy(() => import('@src/pages/UserTrainingPage'));
const UserHpsPage = lazy(() => import('@src/pages/UserHpsPage'));
const UserCheckpointPage = lazy(() => import('@src/pages/UserCheckpointPage'));
const UserWorkbenchPage = lazy(() => import('@src/pages/UserWorkbenchPage'));
const UserFederatedLearningPage = lazy(
  () => import('@src/pages/UserFederatedLearningPage'),
);
const UserDeploymentPage = lazy(() => import('@src/pages/UserDeploymentPage'));
// SP-Deployment(D6) v3 §7.5 — 추론(Inference) 탭 (Playground test 소비 레이어)
const InferenceMenu = lazy(
  () => import('@src/pages/llm/Inference/InferenceMenu/InferenceMenu'),
);
// D6 v3 Tier-1 — 추론 상세 (배포 config 없는 lean 채팅/데이터셋, TestComponent 재사용)
const InferenceDetail = lazy(
  () => import('@src/pages/llm/Inference/InferenceDetail/InferenceDetail'),
);
// 평가(Evaluation, llm_evaluation) — 프로젝트 목록/허브
const EvaluationMenu = lazy(
  () => import('@src/pages/llm/Evaluation/EvaluationMenu/EvaluationMenu'),
);
// 벤치마크/judge/전문가 standalone 페이지는 프로젝트 상세(ProjectDetail)로 흡수 — 모델/데이터셋이
// 프로젝트에서 잠기므로 셋업 뷰가 무의미. 설정·결과·전문가 채점은 재사용 컴포넌트로 편입.
const ProjectDetail = lazy(
  () => import('@src/pages/llm/Evaluation/ProjectDetail/ProjectDetail'),
);
const EvalCrossCompare = lazy(
  () => import('@src/pages/llm/Evaluation/EvalCrossCompare/EvalCrossCompare'),
);
const UserServicePage = lazy(() => import('@src/pages/UserServicePage'));
const UserTestPage = lazy(() => import('@src/pages/UserTestPage'));
const NotFoundPage = lazy(() => import('@src/pages/NotFoundPage'));
const UserDatasetPreprocessPage = lazy(
  () => import('@src/pages/UserDatasetPreprocessPage'),
);
const UserDatasetPreprocessDetailPage = lazy(
  () => import('@src/pages/UserDatasetPreprocessDetailPage'),
);

const UserDatasetAnalysisPage = lazy(
  () => import('@src/pages/UserDatasetAnalysisPage'),
);
const UserSynthesisPage = lazy(() => import('@src/pages/UserSynthesisPage'));
const UserSynthesisDetailPage = lazy(
  () => import('@src/pages/UserSynthesisDetailPage'),
);
const UserSynthesisPromptOptimizePage = lazy(
  () => import('@src/pages/UserSynthesisPromptOptimizePage'),
);
const UserSynthesisPromptListPage = lazy(
  () => import('@src/pages/UserSynthesisPromptListPage'),
);
const UserSynthesisCanvasPage = lazy(
  () => import('@src/pages/UserSynthesisCanvasPage'),
);
const UserSynthesisWizardPage = lazy(
  () => import('@src/pages/UserSynthesisWizardPage'),
);
const UserDatasetAnalysisDetailPage = lazy(
  () => import('@src/pages/UserDatasetAnalysisDetailPage'),
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
    name: 'Model',
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
  {
    name: 'EdgeDeploymentDetail',
    path: '/user/workspace/:id/edge-deploy/:deployId',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'llm',
    render: (props) => <EdgeDeploymentDetail {...props} />,
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
    disabled: true,
    icon: IconLnbHomeGray,
    activeIcon: IconLnbHomeBlue,
    platform: 'flightbase',
    render: (props) => <Dashboard {...props} />,
  },

  // 2026-07-06 QA(11): 도커 이미지 메뉴 임시 숨김 (추후 재노출 예정 — 라우트/컴포넌트 보존 위해 주석 처리)
  // {
  //   name: 'Docker Image',
  //   path: '/user/workspace/:id/docker_images',
  //   exact: true,
  //   icon: IconLnbDockerGray,
  //   activeIcon: IconLnbDockerBlue,
  //   platform: 'flightbase',
  //   render: (props) => <UserDockerImagePage {...props} />,
  // },
  {
    name: 'Data',
    path: '/user/workspace/:id/datasets',
    exact: true,
    isGroup: true,
    // 그룹 헤드는 하위 페이지에서 점등 유지하되, 별개 목적지인 드라이브(/datasets/management)에선 제외.
    excludeChildren: ['management'],
    icon: IconLnbDatasetsGray,
    activeIcon: IconLnbDatasetsBlue,
    platform: 'flightbase',
    render: (props) => <UserDatasetRedirectPage {...props} />,
  },
  {
    name: 'collect.label',
    path: '/user/workspace/:id/datasets/collect/:did/detail',
    disabled: true,
    exact: false,
    group: datasetGroup,
    icon: IconDataCollect,
    activeIcon: IconDataCollectActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetCollectDetailPage {...props} />,
  },
  {
    name: 'collect.label',
    path: '/user/workspace/:id/datasets/collect',
    group: datasetGroup,
    isFirstGroup: true,
    icon: IconDataCollect,
    activeIcon: IconDataCollectActive,
    platform: 'flightbase',
    render: (props) => <UserDataCollectMenuPage {...props} />,
  },
  {
    name: 'labeling.label',
    path: '/user/workspace/:id/datasets/labeling',
    exact: true,
    group: datasetGroup,
    icon: IconManagement,
    activeIcon: IconManagementActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetLabelingPage {...props} />,
  },
  {
    name: 'preprocess.label',
    path: '/user/workspace/:id/datasets/process',
    exact: true,
    isGroup: true,
    group: datasetGroup,
    icon: IconPreProcess,
    activeIcon: IconPreProcessActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetPreprocessPage {...props} />,
  },
  {
    name: '전처리 디테일',
    path: '/user/workspace/:id/datasets/process/:did/detail',
    exact: true,
    isGroup: true,
    group: datasetGroup,
    disabled: true,
    icon: IconPreProcess,
    activeIcon: IconPreProcessActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetPreprocessDetailPage {...props} />,
  },
  {
    name: 'analyze.label',
    path: '/user/workspace/:id/datasets/analysis',
    exact: true,
    isGroup: true,
    group: datasetGroup,
    icon: IconAnalysis,
    activeIcon: IconAnalysisActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetAnalysisPage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis',
    exact: true,
    group: datasetGroup,
    isLastGroup: true,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisPage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis/:sid/overview',
    exact: true,
    disabled: true,
    group: datasetGroup,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisDetailPage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis/:sid/prompt-optimize',
    exact: true,
    disabled: true,
    group: datasetGroup,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisPromptOptimizePage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis/:sid/wizard',
    exact: true,
    disabled: true,
    group: datasetGroup,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisWizardPage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis/:sid/prompt-list',
    exact: true,
    disabled: true,
    group: datasetGroup,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisPromptListPage {...props} />,
  },
  {
    name: 'synthesis.label',
    path: '/user/workspace/:id/datasets/synthesis/:sid/canvas',
    exact: true,
    disabled: true,
    group: datasetGroup,
    icon: IconSynthesis,
    activeIcon: IconSynthesisActive,
    platform: 'flightbase',
    render: (props) => <UserSynthesisCanvasPage {...props} />,
  },
  {
    name: 'Data Analysis Detail',
    path: '/user/workspace/:id/datasets/analysis/:did/detail',
    exact: true,
    isGroup: true,
    group: datasetGroup,
    disabled: true,
    icon: IconAnalysis,
    activeIcon: IconAnalysisActive,
    platform: 'flightbase',
    render: (props) => <UserDatasetAnalysisDetailPage {...props} />,
  },
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
    name: 'Drive',
    path: '/user/workspace/:id/datasets/management',
    exact: true,
    disabled: true,
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
    name: 'Model',
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
    // SP-Deployment(D6) v3: Playground → "배포" 탭으로 repurpose.
    // 경로 /llmplayground 유지(딥링크·하위 라우트 보존), 라벨만 배포로.
    name: 'Deployment',
    path: '/user/workspace/:id/llmplayground',
    exact: true,
    icon: IconLnbServingGray,
    activeIcon: IconLnbServingBlue,
    platform: 'flightbase',
    render: (props) => <PlaygroundMenu {...props} />,
  },
  {
    // D6 v3 §7.5: 추론(consume) 탭 — 활성 배포 선택 → 추론 상세(채팅/데이터셋)
    name: 'Inference',
    path: '/user/workspace/:id/inference',
    exact: true,
    icon: IconNavPlayground,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <InferenceMenu {...props} />,
  },
  {
    // D6 v3 Tier-1: 추론 상세 — 배포 config 없는 lean 화면(TestComponent 인라인 재사용).
    // detail 전용이라 사이드nav 비노출(disabled). :did = playground(배포) id.
    name: 'InferenceDetail',
    path: '/user/workspace/:id/inference/:did',
    exact: true,
    disabled: true,
    icon: IconNavPlayground,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <InferenceDetail {...props} />,
  },
  {
    // 평가(Evaluation) 허브 — 벤치마크/judge/전문가 모드 picker (llm_evaluation)
    name: 'Evaluation',
    path: '/user/workspace/:id/evaluation',
    exact: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <EvaluationMenu {...props} />,
  },
  {
    // 평가 프로젝트 상세(목록에서 진입, run 실행·전문가 채점·비교). detail=사이드nav 비노출.
    name: 'ProjectDetail',
    path: '/user/workspace/:id/evaluation/project/:projectId',
    exact: true,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <ProjectDetail {...props} />,
  },
  {
    // ④ 교차모델 비교(읽기 전용 뷰). detail=사이드nav 비노출.
    name: 'EvalCrossCompare',
    path: '/user/workspace/:id/evaluation/compare',
    exact: true,
    disabled: true,
    icon: IconModel,
    activeIcon: IconModelActive,
    platform: 'flightbase',
    render: (props) => <EvalCrossCompare {...props} />,
  },
  // 2026-07-06 QA(11): AI 파이프라인 메뉴 임시 숨김 (추후 재노출 예정 — 라우트/컴포넌트 보존 위해 주석 처리)
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
  {
    name: 'project.label',
    path: '/user/workspace/:id/pipeline/:tid',
    exact: true,
    disabled: true,
    icon: IconLnbTrainingsGray,
    activeIcon: IconPipelineProjectActive,
    platform: 'flightbase',
    render: (props) => <UserPipeLineContent {...props} />,
  },
  {
    name: 'project.label',
    path: '/user/workspace/:id/pipeline/:tid/historydetail/:did',
    exact: true,
    disabled: true,
    icon: IconLnbTrainingsGray,
    activeIcon: IconPipelineProjectActive,
    platform: 'flightbase',
    render: (props) => <UserPipelineHistoryDetail {...props} />,
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
    name: 'EdgeDeploymentDetail',
    path: '/user/workspace/:id/edge-deploy/:deployId',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <EdgeDeploymentDetail {...props} />,
  },
  {
    name: 'StandaloneDeploymentDetail',
    path: '/user/workspace/:id/standalone-deploy/:deployId',
    exact: false,
    disabled: true,
    icon: IconNavPlaygroundActive,
    activeIcon: IconNavPlaygroundActive,
    platform: 'flightbase',
    render: (props) => <StandaloneDeploymentDetail {...props} />,
  },
];

const calSideNavList = (selectedPlatform) => {
  // 단일 플랫폼(flightbase): 미선택/null이면 flightbase 기본 → 첫 진입 빈 사이드바 방지
  if (selectedPlatform === 2) {
    return routeArr.filter((route) => route.platform === 'llm');
  }
  return routeArr.filter((route) => route.platform === 'flightbase');
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
// 목업 사이드바 상단 카드 버튼 (대시보드 / 드라이브)
const TOP_CARD_BASE = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#ffffff',
  border: '1px solid #e2e6ee',
  borderRadius: '10px',
  padding: '12px 6px',
  textAlign: 'center',
  fontSize: '12px',
  fontWeight: 500,
  color: '#3e3e3e',
  textDecoration: 'none',
  boxShadow: '0 3px 6px rgba(0,0,0,0.1)',
  transition: 'border-color 0.15s',
};
const TOP_CARD_ACTIVE = {
  borderColor: '#3d6df6',
  background: '#eef3ff',
  fontWeight: 700,
  color: '#3d6df6',
};

const TopCardNav = ({ workspaceId }) => {
  if (!workspaceId) return null;
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '8px',
        padding: '0 16px',
        margin: '8px 0 12px',
      }}
    >
      <NavLink
        to={`/user/workspace/${workspaceId}/home`}
        exact
        style={TOP_CARD_BASE}
        activeStyle={TOP_CARD_ACTIVE}
      >
        <svg
          viewBox='58 19 16 16'
          width='22'
          height='22'
          fill='currentColor'
          style={{ marginBottom: '6px' }}
          xmlns='http://www.w3.org/2000/svg'
        >
          <path d='M64.6658 31.6632V28.3299H67.3324V31.6632C67.3324 32.0299 67.6324 32.3299 67.9991 32.3299H69.9991C70.3658 32.3299 70.6658 32.0299 70.6658 31.6632V26.9966H71.7991C72.1058 26.9966 72.2524 26.6166 72.0191 26.4166L66.4458 21.3966C66.1924 21.1699 65.8058 21.1699 65.5524 21.3966L59.9791 26.4166C59.7524 26.6166 59.8924 26.9966 60.1991 26.9966H61.3324V31.6632C61.3324 32.0299 61.6324 32.3299 61.9991 32.3299H63.9991C64.3658 32.3299 64.6658 32.0299 64.6658 31.6632Z' />
        </svg>
        대시보드
      </NavLink>
      <NavLink
        to={`/user/workspace/${workspaceId}/datasets/management`}
        style={TOP_CARD_BASE}
        activeStyle={TOP_CARD_ACTIVE}
      >
        <svg
          viewBox='186 19 16 16'
          width='22'
          height='22'
          fill='currentColor'
          style={{ marginBottom: '6px' }}
          xmlns='http://www.w3.org/2000/svg'
        >
          <path d='M199.336 22.9974L194.003 22.9974L192.669 21.6641H188.669C187.936 21.6641 187.343 22.2641 187.343 22.9974L187.336 30.9974C187.336 31.7307 187.936 32.3307 188.669 32.3307H199.336C200.069 32.3307 200.669 31.7307 200.669 30.9974V24.3307C200.669 23.5974 200.069 22.9974 199.336 22.9974ZM199.336 30.9974L188.669 30.9974V29.2831L199.336 29.2831V30.9974Z' />
        </svg>
        데이터셋
      </NavLink>
    </div>
  );
};

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
    const curPlatform = routeArr.filter((v) => v.path === path)[0]?.platform;

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
          {/* 플랫폼 스위처 박스 제거: TANGO 단일 플랫폼이라 전환 대상이 없음
              (Jonathan > modelbase/agentbase 전환 슬롯의 잔재). 상단 다크바가 브랜드 담당.
              카드/네비/플랫폼 선택 로직은 유지. */}
          {(selectedPlatform ?? 1) === info.value && (
            <>
              <TopCardNav workspaceId={workspaceId} />
              {children}
            </>
          )}
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

  const [selectedPlatform, setSelectedPlatform] = useState(1);
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
