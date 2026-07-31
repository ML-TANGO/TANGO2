import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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

import { Badge, ButtonV2, Loading, Tooltip } from '@jonathan/ui-react';

import BenchmarkResultView from '../BenchmarkEvaluation/BenchmarkResultView';
import BenchmarkRunConfig from '../BenchmarkEvaluation/BenchmarkRunConfig';
import { BENCHMARK_LABEL } from '../BenchmarkEvaluation/benchmarks';
import { METRIC_LABEL } from '../BenchmarkEvaluation/benchmarkMetrics';
import EvalComparison from '../EvalComparison/EvalComparison';
import ExpertInferenceModal from '../ExpertEvaluation/ExpertInferenceModal';
import ExpertRunView from '../ExpertEvaluation/ExpertRunView';
import JudgeResultView from '../JudgeEvaluation/JudgeResultView';
import JudgeRunConfig from '../JudgeEvaluation/JudgeRunConfig';

import EvalGenerateModal from './EvalGenerateModal';

import ContentBox from '@src/components/molecules/ContentBox';
import EmptyBox from '@src/components/molecules/EmptyBox';

import {
  compareProjectRuns,
  deleteEvalRun,
  getEvalDatasets,
  getEvalProject,
  listEvalProjects,
  markEvalStatus,
  runBenchmark,
  runEvalInference,
  runJudge,
  startExpert,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { addNineHours, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ProjectDetail.module.scss';

const cx = classNames.bind(style);

const TYPE_KEYS = {
  benchmark: 'evaluation.project.type.benchmark',
  judge: 'evaluation.project.type.judge',
  expert: 'evaluation.project.type.expert',
};
const STATUS_KEYS = {
  created: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
};
const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};
const TYPE_BADGE_TYPE = {
  benchmark: 'blue',
  judge: 'yellow',
  expert: 'green',
};

const fmtDate = (v) => addNineHours(v) || '-';

// run 메트릭 프리뷰 포맷 — expert 스케일(/5·%) 구분, 그 외 기본. (EvalComparison 과 동형.)
const fmtRunMetric = (k, v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  if (k === 'expert_avg_score') return `${v.toFixed(2)}/5`;
  if (k === 'expert_pass_rate') return `${v.toFixed(2)}%`;
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

// SimpleNav 는 llmModel.info.name 을 titleName 보다 우선하므로 평가 프로젝트명이 모델명에
// 오염될 수 있다. 마크업·클래스 구조는 그대로 따르되 평가 데이터만 받는 전용 헤더로 분리한다.
const EvaluationNav = ({ navList, topButtonList, titleName, subTitle }) => {
  const { t } = useTranslation();

  return (
    <div className={cx('nav-box')}>
      <div className={cx('title')}>
        <div className={cx('name')}>
          <div>{titleName}</div>
          {subTitle && <div className={cx('sub-title')}>{subTitle}</div>}
        </div>
        {topButtonList && <div className={cx('btn')}>{topButtonList}</div>}
      </div>
      <ul className={cx('nav')}>
        {navList.map(({ label, path: navPath }) => (
          <li className={cx('nav-item')} key={navPath}>
            <NavLink exact to={navPath} activeClassName={cx('active')}>
              <span className={cx('link-name')}>{t(label)}</span>
              <span className={cx('stick')} />
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
};

// 네비게이션이라 button 을 유지한다 — div+onClick 은 Tab 으로 도달할 수 없어
// 키보드 사용자가 목록으로 돌아갈 방법이 사라진다. 아이콘 이름은 옆 라벨이 주므로 alt=''.
const DetailBack = ({ label, onClick }) => (
  <button type='button' className={cx('back-to-list')} onClick={onClick}>
    <img
      className={cx('back-btn-image')}
      src='/images/icon/00-ic-basic-arrow-02-left.svg'
      alt=''
    />
    <span className={cx('back-btn-label')}>{label}</span>
  </button>
);

// 평가 프로젝트 상세(P3+P4). 실행 목록·설정·결과·전문가 채점·비교를 URL로 승격해
// 딥링크와 새로고침을 보장한다. 모델/데이터셋은 프로젝트에서 상속하며 하위 뷰 계약은 유지한다.
const ProjectDetail = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const location = useLocation();
  const match = useRouteMatch();
  const { id: workspaceId, projectId } = match.params;
  const { path, url } = match;
  const runsPath = `${url}/runs`;
  const comparePath = `${url}/compare`;
  const normalizedPath = location.pathname.replace(/\/+$/, '');

  const [project, setProject] = useState(null); // null=로딩
  const [runsData, setRunsData] = useState(null); // { metric_keys, best, runs }
  const [notFound, setNotFound] = useState(false);
  const [modelMap, setModelMap] = useState({}); // model_id에서 name으로 매핑
  const [datasetMap, setDatasetMap] = useState({}); // dataset_id에서 name으로 매핑
  const [projectListUpdate, setProjectListUpdate] = useState(null);
  const [starting, setStarting] = useState(false);
  const [showInferModal, setShowInferModal] = useState(false);
  const [showGenModal, setShowGenModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [compareData, setCompareData] = useState(null);
  // 새 실행 직후 아직 목록 응답에 없는 run의 결과 뷰 props를 URL 전환 사이에 보존한다.
  const [activeRun, setActiveRun] = useState(null);

  const fetchProject = useCallback(async () => {
    const res = await getEvalProject(projectId);
    if (res.status === STATUS_SUCCESS && res.result?.project) {
      setProject(res.result.project);
      setRunsData(res.result.runs || { metric_keys: [], best: {}, runs: [] });
    } else {
      setNotFound(true);
      errorToastMessage(res.error, res.message);
    }
  }, [projectId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    fetchProject();
  }, [dispatch, fetchProject]);

  // 모델명·데이터셋명 매핑(상세 메타 표시용) — 1회 조회. 실패해도 #id 로 폴백.
  useEffect(() => {
    if (!workspaceId) return undefined;
    let cancelled = false;
    (async () => {
      const [modelRes, datasetRes, projectListRes] = await Promise.all([
        callApi({
          url: `models?workspace_id=${workspaceId}`,
          method: 'GET',
        }),
        getEvalDatasets(workspaceId),
        listEvalProjects(workspaceId),
      ]);
      if (cancelled) return;
      if (modelRes.status === STATUS_SUCCESS) {
        const list = Array.isArray(modelRes.result)
          ? modelRes.result
          : (modelRes.result?.list ?? []);
        const map = {};
        list.forEach((m) => {
          if (m?.id != null) map[m.id] = m.name;
        });
        setModelMap(map);
      }
      if (datasetRes.status === STATUS_SUCCESS) {
        const list = Array.isArray(datasetRes.result)
          ? datasetRes.result
          : (datasetRes.result?.list ?? []);
        const map = {};
        list.forEach((dataset) => {
          const id = dataset.id ?? dataset.dataset_id;
          if (id != null) map[id] = dataset.name ?? dataset.dataset_name;
        });
        setDatasetMap(map);
      }
      if (projectListRes.status === STATUS_SUCCESS) {
        const list = projectListRes.result?.projects ?? [];
        const current = list.find(
          (item) => String(item.id) === String(projectId),
        );
        setProjectListUpdate(current?.update_datetime ?? null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, workspaceId]);

  // 러너 generate 런이 running 인 동안 프로젝트를 폴링한다. 완료되어 runsData가 갱신되면 genRunning이
  // false 가 되어 폴링이 멈추고, 배너가 '생성 완료'로 전환 + 채점이 그 output 을 소비 가능.
  useEffect(() => {
    const running = (runsData?.runs ?? []).some(
      (r) => r.metric_set === 'inference' && r.status === 'running',
    );
    if (!running) return undefined;
    const timer = setInterval(() => {
      fetchProject();
    }, 4000);
    return () => clearInterval(timer);
  }, [runsData, fetchProject]);

  // 러너 inference 런(metric_set='inference')은 점수 런이 아니라 "생성" 서브스텝 — 점수 목록에서
  // 분리(클릭 시 dead-end 방지)하고, 최신 완료본은 배너/benchmark seam(inference_job_id)에 쓴다.
  const allRuns = runsData?.runs ?? [];
  const runs = allRuns.filter((r) => r.metric_set !== 'inference');
  const latestInference = allRuns.find(
    (r) => r.metric_set === 'inference' && r.status === 'completed',
  );
  const genRunning = allRuns.some(
    (r) => r.metric_set === 'inference' && r.status === 'running',
  );
  const metricKeys = runsData?.metric_keys ?? [];

  // 프로젝트 응답에는 데이터셋 ID만 있으므로 목록 API 이름을 우선하고, 실행 응답 이름으로 보강한다.
  const runDatasetMap = useMemo(() => {
    const map = {};
    runs.forEach((run) => {
      if (run.dataset_id != null && run.dataset_name) {
        map[run.dataset_id] = run.dataset_name;
      }
    });
    return map;
  }, [runs]);

  const backToList = () =>
    history.push(`/user/workspace/${workspaceId}/evaluation`);
  const backToRuns = () => {
    setActiveRun(null);
    history.push(runsPath);
    fetchProject();
  };

  // "새 평가 실행" — expert 는 즉시 세션 시작(startExpert), benchmark/judge 는 설정 폼으로.
  const handleNewRun = async () => {
    if (!project) return;
    if (project.eval_type === 'expert') {
      // 전문가 평가는 실추론(지연 단위 VLM)에 쓸 배포를 먼저 고른 뒤 startExpertRun으로 시작.
      setShowInferModal(true);
    } else {
      history.push(`${runsPath}/new`);
    }
  };

  // 배포 선택 확정 후 전문가 세션 시작. inferencePlaygroundId=null 이면 mock 출력(graceful).
  const startExpertRun = async (inferencePlaygroundId) => {
    setShowInferModal(false);
    if (starting) return;
    setStarting(true);
    const body = { project_id: Number(projectId) };
    if (inferencePlaygroundId)
      body.inference_playground_id = inferencePlaygroundId;
    // 생성 런이 있으면 그 샘플을 채점 대상으로(명시 opt-in). 없으면 배포/mock.
    if (latestInference?.job_id) body.inference_job_id = latestInference.job_id;
    const res = await startExpert(body);
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setActiveRun({ jobId: res.result.job_id });
    history.push(`${runsPath}/${res.result.job_id}`);
  };

  // 평가 추론 러너(generate) 실행 — 선택한 running 배포로 데이터셋 전량 batch 추론 후 _samples +
  // _gen_system_prompt 영속. 백그라운드 런이라 즉시 목록 갱신 후 genRunning 폴링이 완료까지 추적.
  const handleGenerate = async ({ inference_playground_id, system_prompt }) => {
    setShowGenModal(false);
    if (generating) return;
    setGenerating(true);
    try {
      const res = await runEvalInference({
        project_id: Number(projectId),
        inference_playground_id,
        system_prompt,
      });
      if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
        errorToastMessage(res.error, res.message);
        return;
      }
      // 러너 런(running)이 목록/배너에 반영되도록 갱신하고 genRunning 폴링이 완료까지 추적.
      await fetchProject();
    } finally {
      // busy 해제는 fetchProject 반영 후에야 — 그 전엔 genRunning 이 아직 false 라 버튼이
      //   재활성되어 이중 제출될 수 있음(리뷰 HIGH). finally 로 refetch 후 해제.
      setGenerating(false);
    }
  };

  // benchmarks = [{ benchmark, metric }] — 벤치마크별 메트릭 매핑(BenchmarkRunConfig 위저드).
  const handleBenchmarkRun = async (benchmarks) => {
    if (starting) return;
    setStarting(true);
    const res = await runBenchmark({
      project_id: Number(projectId),
      benchmarks,
      // 생성 런이 있으면 그 output 을 스코어러에 넘겨 채점(생성·채점 분리). 없으면 컨테이너 자체 생성.
      ...(latestInference?.job_id
        ? { inference_job_id: latestInference.job_id }
        : {}),
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setActiveRun({
      jobId: res.result.job_id,
      status: 'running',
    });
    history.push(`${runsPath}/${res.result.job_id}`);
  };

  const handleJudgeRun = async (body) => {
    if (starting) return;
    setStarting(true);
    const res = await runJudge({
      project_id: Number(projectId),
      ...body,
      // 생성 런이 있으면 그 output 을 채점(명시 opt-in, benchmark 와 통일). 없으면 배포/mock.
      ...(latestInference?.job_id
        ? { inference_job_id: latestInference.job_id }
        : {}),
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setActiveRun({
      jobId: res.result.job_id,
      status: 'running',
      criteria: body.criteria,
    });
    history.push(`${runsPath}/${res.result.job_id}`);
  };

  const openRun = (run) => {
    if (!run?.job_id) return;
    setActiveRun({
      jobId: run.job_id,
      status: run.status,
      // judge 의 metric_set 은 "judge:<provider>"(기준 아님) — JudgeResultView 가
      // judge_* 키에서 실제 기준을 파생하므로 빈 배열로 넘긴다. benchmark 결과 뷰는
      // metrics JSON 을 직접 폴링하므로 별도 metricSet prop 불필요(제거).
      criteria: [],
    });
    history.push(`${runsPath}/${run.job_id}`);
  };

  // 런 1건 삭제(진행중/완료 모두). 프로젝트 삭제와 동일하게 네이티브 확인 모달(openConfirm) 재사용.
  //   행 클릭(openRun) 과 겹치지 않게 stopPropagation. 삭제 후 목록 갱신.
  const handleDeleteRun = (run, e) => {
    e.stopPropagation();
    if (!run?.job_id) return;
    dispatch(
      openConfirm({
        title: 'evaluation.run.delete.title',
        content: 'evaluation.run.delete.message',
        testid: 'eval-run-delete-modal',
        submit: {
          text: 'delete.label',
          func: async () => {
            // 진행 중인 컨테이너 백엔드 런(benchmark/judge)은 삭제 전에 취소해 자원 회수
            //   (expert=컨테이너 없음). 취소는 best-effort — 실패해도 삭제는 진행.
            if (run.status === 'running' && project.eval_type !== 'expert') {
              await markEvalStatus(project.model_id, run.job_id, 'cancelled');
            }
            const res = await deleteEvalRun(project.model_id, run.job_id);
            if (res.status !== STATUS_SUCCESS) {
              errorToastMessage(res.error, res.message);
              return;
            }
            await fetchProject();
          },
        },
        cancel: { text: 'cancel.label' },
      }),
    );
  };

  const openCompare = () => {
    history.push(comparePath);
  };

  // 비교 탭은 NavLink·직접 URL·새로고침 어느 경로로 들어와도 데이터를 조회한다.
  // 비교 가능 여부는 navList 노출로만 제어하고 Route 자체는 항상 마운트한다.
  useEffect(() => {
    if (project?.id == null || normalizedPath !== comparePath) return undefined;
    let cancelled = false;
    setCompareData(null);
    (async () => {
      const res = await compareProjectRuns(projectId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        history.replace(runsPath);
        return;
      }
      setCompareData(res.result);
    })();
    return () => {
      cancelled = true;
    };
  }, [comparePath, history, normalizedPath, project?.id, projectId, runsPath]);

  // run.metric_set 은 DB 문자열 — benchmark 는 "bleu,rouge" CSV, judge 는 "judge:<provider>".
  const configSummary = (run) => {
    const raw = run.metric_set;
    if (raw == null || raw === '') return null;
    if (project.eval_type === 'benchmark') {
      // metric_set = "benchmark:metric" CSV(신 스키마)를 "벤치마크 · 메트릭"으로 함께 요약.
      //   구 런은 metric-id CSV("bleu,rouge", 콜론 없음)라 metric 라벨로 폴백
      //   (BenchmarkResultView와 동일한 3단계 폴백: BENCHMARK_LABEL, METRIC_LABEL, id).
      const parts = String(raw)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((tok) => {
          const [b, m] = tok.split(':');
          const benchLabel = BENCHMARK_LABEL[b] || METRIC_LABEL[b] || b;
          return m ? `${benchLabel} · ${METRIC_LABEL[m] || m}` : benchLabel;
        });
      return parts.length ? parts.join(', ') : null;
    }
    if (project.eval_type === 'judge') {
      const provider = String(raw)
        .replace(/^judge:/, '')
        .trim();
      return provider || null;
    }
    return null;
  };

  // ── 로딩 / 오류 ──
  if (project === null && !notFound) {
    return (
      <div className={cx('container')}>
        <div className={cx('loading-state')}>
          <Loading />
          <span>{t('evaluation.project.loading')}</span>
        </div>
      </div>
    );
  }
  if (notFound) {
    return (
      <div className={cx('container')}>
        <DetailBack
          label={t('evaluation.project.backToList')}
          onClick={backToList}
        />
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  const isRunsRoot =
    normalizedPath === url.replace(/\/+$/, '') || normalizedPath === runsPath;
  const backLabel = isRunsRoot
    ? t('evaluation.project.backToList')
    : t('evaluation.run.backToRuns');
  const goBack = isRunsRoot ? backToList : backToRuns;
  const typeLabel = t(TYPE_KEYS[project.eval_type] || project.eval_type);
  const modelName = modelMap[project.model_id] || `#${project.model_id}`;
  const datasetNames = (project.dataset_ids || []).map(
    (id) => datasetMap[id] || runDatasetMap[id] || `#${id}`,
  );
  const datasetLabel =
    datasetNames.join(', ') ||
    t('evaluation.project.datasetCount', {
      n: (project.dataset_ids || []).length,
    });
  // 상세 응답의 필드를 우선하되, 현행 목록 전용 additive 계약과 열린 화면의 최신 run으로 보강한다.
  const projectUpdateDatetime =
    project.update_datetime ||
    projectListUpdate ||
    allRuns[0]?.create_datetime ||
    project.create_datetime;
  const navList = [
    {
      label: 'evaluation.project.detail.runsTitle',
      path: runsPath,
    },
    // 비교 Route 는 항상 존재하며, 실행 2건 이상일 때만 탭을 노출한다.
    ...(runs.length >= 2
      ? [
          {
            label: 'evaluation.project.detail.compare',
            path: comparePath,
          },
        ]
      : []),
  ];
  const topButtonList = (
    <div className={cx('top-actions')}>
      <Badge
        label={typeLabel}
        type={TYPE_BADGE_TYPE[project.eval_type] || 'gray'}
        size='sm'
      />
      <Badge
        label={t(STATUS_KEYS[project.status] || project.status)}
        type={STATUS_BADGE_TYPE[project.status] || 'gray'}
        size='sm'
      />
      <ButtonV2
        type='outline'
        colorType='gray'
        size='s'
        label={
          genRunning
            ? t('evaluation.generate.running')
            : t('evaluation.generate.action')
        }
        disabled={generating || genRunning}
        isLoading={generating}
        onClick={() => setShowGenModal(true)}
      />
      {runs.length >= 2 && (
        <ButtonV2
          type='outline'
          size='s'
          label={t('evaluation.project.detail.compare')}
          onClick={openCompare}
        />
      )}
      <ButtonV2
        type='solid'
        size='s'
        label={
          starting
            ? t('evaluation.running')
            : t('evaluation.project.detail.newRun')
        }
        disabled={starting}
        isLoading={starting}
        onClick={handleNewRun}
      />
    </div>
  );

  return (
    <div id='ProjectDetail' className={cx('container')}>
      <DetailBack label={backLabel} onClick={goBack} />
      <div className={cx('content')}>
        <EvaluationNav
          navList={navList}
          topButtonList={topButtonList}
          titleName={project.name}
          subTitle={`${typeLabel} · ${modelName}`}
        />

        {/* 실행 결과를 해석하는 전제 메타는 별도 탭이 아니라 모든 하위 화면에서 계속 노출한다. */}
        <ContentBox title={t('evaluation.project.detail.infoTitle')}>
          <div className={cx('project-meta')}>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>
                {t('evaluation.project.dataset')}
              </span>
              <Tooltip
                contents={datasetLabel}
                contentsAlign={{ vertical: 'top', horizontal: 'left' }}
                globalCustomStyle={{ width: '100%' }}
                customStyle={{ width: '100%' }}
              >
                <span className={cx('meta-value', 'dataset-value')}>
                  {datasetLabel}
                </span>
              </Tooltip>
            </div>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>
                {t('evaluation.project.creator')}
              </span>
              <span className={cx('meta-value')}>{project.creator || '-'}</span>
            </div>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>{t('createdAt.label')}</span>
              <span className={cx('meta-value')}>
                {fmtDate(project.create_datetime)}
              </span>
            </div>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>
                {t('lastUpdatedTime.label')}
              </span>
              <span className={cx('meta-value')}>
                {fmtDate(projectUpdateDatetime)}
              </span>
            </div>
          </div>
        </ContentBox>

        <Switch>
          <Route exact path={path}>
            <Redirect to={runsPath} />
          </Route>

          {/* 라우트는 평가 유형·run 수와 무관하게 항상 마운트한다.
              유형과 비교 가능 여부는 각 Route 내부 분기와 navList 노출로만 제어한다. */}
          <Route exact path={`${path}/runs/new`}>
            {project.eval_type === 'benchmark' && (
              <BenchmarkRunConfig
                running={starting}
                onRun={handleBenchmarkRun}
              />
            )}
            {project.eval_type === 'judge' && (
              <JudgeRunConfig running={starting} onRun={handleJudgeRun} />
            )}
            {project.eval_type === 'expert' && <Redirect to={runsPath} />}
          </Route>

          <Route
            exact
            path={`${path}/runs/:jobId`}
            render={({ match: runMatch }) => {
              const jobId = runMatch.params.jobId;
              const savedRun = runs.find(
                (run) => String(run.job_id) === String(jobId),
              );
              const currentRun =
                String(activeRun?.jobId) === String(jobId)
                  ? activeRun
                  : savedRun;

              if (project.eval_type === 'benchmark') {
                return (
                  <BenchmarkResultView
                    modelId={project.model_id}
                    jobId={jobId}
                    status={currentRun?.status}
                    onComplete={fetchProject}
                  />
                );
              }
              if (project.eval_type === 'judge') {
                return (
                  <JudgeResultView
                    modelId={project.model_id}
                    jobId={jobId}
                    fallbackCriteria={currentRun?.criteria || []}
                    onComplete={fetchProject}
                  />
                );
              }
              if (project.eval_type === 'expert') {
                return (
                  <ExpertRunView
                    modelId={project.model_id}
                    jobId={jobId}
                    onExit={backToRuns}
                  />
                );
              }
              return <Redirect to={runsPath} />;
            }}
          />

          <Route exact path={`${path}/runs`}>
            <section className={cx('runs')}>
              <div className={cx('runs-head')}>
                <h3 className={cx('runs-title')}>
                  {t('evaluation.project.detail.runsTitle')}
                </h3>
                <Badge label={String(runs.length)} type='blue' size='sm' />
              </div>

              {(latestInference || genRunning) && (
                <div className={cx('gen-banner')}>
                  {genRunning
                    ? t('evaluation.generate.running')
                    : t('evaluation.generate.ready')}
                </div>
              )}

              {runs.length === 0 ? (
                <EmptyBox
                  text='evaluation.project.detail.noRuns'
                  isBox
                  customStyle={{ height: '120px' }}
                />
              ) : (
                <div className={cx('run-list')}>
                  {runs.map((run) => {
                    const summary = configSummary(run);
                    const preview = metricKeys
                      .filter((key) => run.metrics?.[key] != null)
                      .slice(0, 3);
                    return (
                      <div
                        key={run.id}
                        className={cx('run-row')}
                        onClick={() => openRun(run)}
                      >
                        <div className={cx('run-main')}>
                          <span className={cx('run-dataset')}>
                            {run.dataset_name || '-'}
                          </span>
                          {summary && (
                            <span className={cx('run-config')}>{summary}</span>
                          )}
                        </div>
                        <div className={cx('run-side')}>
                          {preview.length > 0 && (
                            <span className={cx('run-metrics')}>
                              {preview
                                .map((key) =>
                                  fmtRunMetric(key, run.metrics[key]),
                                )
                                .join(' · ')}
                            </span>
                          )}
                          <Badge
                            label={t(
                              STATUS_KEYS[run.status] ||
                                run.status ||
                                'running',
                            )}
                            type={STATUS_BADGE_TYPE[run.status] || 'gray'}
                            size='sm'
                          />
                          <span className={cx('run-date')}>
                            {fmtDate(run.create_datetime)}
                          </span>
                          <span className={cx('run-open')}>
                            {project.eval_type === 'expert'
                              ? t('evaluation.project.detail.resume')
                              : t('evaluation.project.detail.open')}
                          </span>
                          <ButtonV2
                            type='clear'
                            colorType='red'
                            size='s'
                            label={t('delete.label')}
                            onClick={(event) => handleDeleteRun(run, event)}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </Route>

          <Route exact path={`${path}/compare`}>
            <section className={cx('runs')}>
              <h3 className={cx('runs-title')}>
                {t('evaluation.project.detail.compareTitle')}
              </h3>
              {compareData === null ? (
                <div className={cx('loading-state')}>
                  <Loading />
                  <span>{t('evaluation.project.loading')}</span>
                </div>
              ) : (
                <EvalComparison comparison={compareData} />
              )}
            </section>
          </Route>

          <Redirect to={runsPath} />
        </Switch>

        {showInferModal && (
          <ExpertInferenceModal
            workspaceId={workspaceId}
            onConfirm={startExpertRun}
            onClose={() => setShowInferModal(false)}
          />
        )}
        {showGenModal && (
          <EvalGenerateModal
            workspaceId={workspaceId}
            running={generating}
            onConfirm={handleGenerate}
            onClose={() => setShowGenModal(false)}
          />
        )}
      </div>
    </div>
  );
};

export default ProjectDetail;
