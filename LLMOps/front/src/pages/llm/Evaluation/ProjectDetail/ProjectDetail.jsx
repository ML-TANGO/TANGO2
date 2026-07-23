import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import BenchmarkResultView from '../BenchmarkEvaluation/BenchmarkResultView';
import BenchmarkRunConfig from '../BenchmarkEvaluation/BenchmarkRunConfig';
import { BENCHMARK_LABEL } from '../BenchmarkEvaluation/benchmarks';
import { METRIC_LABEL } from '../BenchmarkEvaluation/benchmarkMetrics';
import EvalComparison from '../EvalComparison/EvalComparison';
import ExpertInferenceModal from '../ExpertEvaluation/ExpertInferenceModal';
import ExpertRunView from '../ExpertEvaluation/ExpertRunView';
import JudgeResultView from '../JudgeEvaluation/JudgeResultView';
import JudgeRunConfig from '../JudgeEvaluation/JudgeRunConfig';

import {
  compareProjectRuns,
  deleteEvalRun,
  getEvalDatasets,
  getEvalProject,
  markEvalStatus,
  runBenchmark,
  runJudge,
  startExpert,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

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

const fmtDate = (v) => (v ? String(v).replace('T', ' ').slice(0, 16) : '-');

// run 메트릭 프리뷰 포맷 — expert 스케일(/5·%) 구분, 그 외 기본. (EvalComparison 과 동형.)
const fmtRunMetric = (k, v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  if (k === 'expert_avg_score') return `${v.toFixed(2)}/5`;
  if (k === 'expert_pass_rate') return `${v.toFixed(2)}%`;
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

// 평가 프로젝트 상세 (P3+P4). 고정 헤더(모델·데이터셋 read-only) + 실행(run) 목록 +
//   "새 평가 실행"(유형별 설정만 — 모델/데이터셋은 프로젝트 상속) + run 비교(EvalComparison 재사용).
//   run 열기: benchmark/judge → 결과 뷰(폴링), expert → ExpertRunView(재개). 설계 §6/§10(P3·P4).
const ProjectDetail = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, projectId } = match.params;

  const [project, setProject] = useState(null); // null=로딩
  const [runsData, setRunsData] = useState(null); // { metric_keys, best, runs }
  const [notFound, setNotFound] = useState(false);
  const [modelMap, setModelMap] = useState({}); // model_id → name
  const [dsMap, setDsMap] = useState({}); // dataset_id → name
  const [starting, setStarting] = useState(false);
  const [showInferModal, setShowInferModal] = useState(false);
  const [compareData, setCompareData] = useState(null);
  // view: { mode: 'list'|'newRun'|'result'|'expert'|'compare', jobId?, status?, metricSet?, criteria? }
  const [view, setView] = useState({ mode: 'list' });

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

  // 모델명 + 데이터셋명 매핑(헤더 표시용) — 1회 조회. 실패해도 #id 로 폴백.
  useEffect(() => {
    if (!workspaceId) return undefined;
    let cancelled = false;
    (async () => {
      const [mRes, dRes] = await Promise.all([
        callApi({ url: `models?workspace_id=${workspaceId}`, method: 'GET' }),
        getEvalDatasets(workspaceId),
      ]);
      if (cancelled) return;
      if (mRes.status === STATUS_SUCCESS) {
        const list = Array.isArray(mRes.result)
          ? mRes.result
          : (mRes.result?.list ?? []);
        const map = {};
        list.forEach((m) => {
          if (m?.id != null) map[m.id] = m.name;
        });
        setModelMap(map);
      }
      if (dRes.status === STATUS_SUCCESS) {
        const raw = Array.isArray(dRes.result)
          ? dRes.result
          : (dRes.result?.list ?? []);
        const map = {};
        raw.forEach((d) => {
          const id = d.id ?? d.dataset_id;
          if (id != null) map[id] = d.name ?? d.dataset_name;
        });
        setDsMap(map);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const runs = runsData?.runs ?? [];
  const metricKeys = runsData?.metric_keys ?? [];

  // run 행의 dataset_name 폴백(헤더 데이터셋명 보강용).
  const runDsName = useMemo(() => {
    const map = {};
    runs.forEach((r) => {
      if (r.dataset_id != null && r.dataset_name)
        map[r.dataset_id] = r.dataset_name;
    });
    return map;
  }, [runs]);

  const backToList = () =>
    history.push(`/user/workspace/${workspaceId}/evaluation`);
  const backToRuns = () => {
    setView({ mode: 'list' });
    fetchProject();
  };

  // "새 평가 실행" — expert 는 즉시 세션 시작(startExpert), benchmark/judge 는 설정 폼으로.
  const handleNewRun = async () => {
    if (!project) return;
    if (project.eval_type === 'expert') {
      // 전문가 평가는 실추론(지연 단위 VLM)에 쓸 배포를 먼저 고른다 → startExpertRun 으로 시작.
      setShowInferModal(true);
    } else {
      setView({ mode: 'newRun' });
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
    const res = await startExpert(body);
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setView({ mode: 'expert', jobId: res.result.job_id });
  };

  // benchmarks = [{ benchmark, metric }] — 벤치마크→메트릭 매핑(BenchmarkRunConfig 위저드).
  const handleBenchmarkRun = async (benchmarks) => {
    if (starting) return;
    setStarting(true);
    const res = await runBenchmark({
      project_id: Number(projectId),
      benchmarks,
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setView({
      mode: 'result',
      jobId: res.result.job_id,
      status: 'running',
    });
  };

  const handleJudgeRun = async (body) => {
    if (starting) return;
    setStarting(true);
    const res = await runJudge({ project_id: Number(projectId), ...body });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setView({
      mode: 'result',
      jobId: res.result.job_id,
      status: 'running',
      criteria: body.criteria,
    });
  };

  const openRun = (run) => {
    if (!run?.job_id) return;
    if (project.eval_type === 'expert') {
      setView({ mode: 'expert', jobId: run.job_id });
    } else {
      setView({
        mode: 'result',
        jobId: run.job_id,
        status: run.status,
        // judge 의 metric_set 은 "judge:<provider>"(기준 아님) — JudgeResultView 가
        // judge_* 키에서 실제 기준을 파생하므로 빈 배열로 넘긴다. benchmark 결과 뷰는
        // metrics JSON 을 직접 폴링하므로 별도 metricSet prop 불필요(제거).
        criteria: [],
      });
    }
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

  const openCompare = async () => {
    const res = await compareProjectRuns(projectId);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setCompareData(res.result);
    setView({ mode: 'compare' });
  };

  // run.metric_set 은 DB 문자열 — benchmark 는 "bleu,rouge" CSV, judge 는 "judge:<provider>".
  const configSummary = (run) => {
    const raw = run.metric_set;
    if (raw == null || raw === '') return null;
    if (project.eval_type === 'benchmark') {
      // metric_set = "benchmark:metric" CSV(신 스키마) → "벤치마크 · 메트릭" 함께 요약.
      //   구 런은 metric-id CSV("bleu,rouge", 콜론 없음)라 metric 라벨로 폴백
      //   (BenchmarkResultView 와 동일 3-way 체인: BENCHMARK_LABEL → METRIC_LABEL → id).
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
      <div className={cx('project-detail')}>
        <div className={cx('placeholder')}>
          {t('evaluation.project.loading')}
        </div>
      </div>
    );
  }
  if (notFound) {
    return (
      <div className={cx('project-detail')}>
        <div className={cx('header')}>
          <button type='button' className={cx('back-btn')} onClick={backToList}>
            ← {t('evaluation.project.backToList')}
          </button>
        </div>
        <div className={cx('placeholder')}>{t('evaluation.project.empty')}</div>
      </div>
    );
  }

  const datasetNames = (project.dataset_ids || [])
    .map((id) => dsMap[id] || runDsName[id] || `#${id}`)
    .join(', ');

  const isSub = view.mode !== 'list';

  return (
    <div className={cx('project-detail')}>
      <div className={cx('header')}>
        <button type='button' className={cx('back-btn')} onClick={backToList}>
          ← {t('evaluation.project.backToList')}
        </button>
      </div>

      {/* 고정 헤더 — 이름·유형·상태·모델·데이터셋·생성자·생성일 (전부 read-only). */}
      <div className={cx('fixed-header')}>
        <div className={cx('name-row')}>
          <h1 className={cx('name')}>{project.name}</h1>
          <span className={cx('type-badge', `type-${project.eval_type}`)}>
            {t(TYPE_KEYS[project.eval_type] || project.eval_type)}
          </span>
          <span className={cx('status-chip', `status-${project.status}`)}>
            {t(STATUS_KEYS[project.status] || project.status)}
          </span>
        </div>
        <div className={cx('meta-grid')}>
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>
              {t('evaluation.project.model')}
            </span>
            <span className={cx('meta-value')}>
              {modelMap[project.model_id] || `#${project.model_id}`}
            </span>
          </div>
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>
              {t('evaluation.project.dataset')}
            </span>
            <span className={cx('meta-value')} title={datasetNames}>
              {datasetNames ||
                t('evaluation.project.datasetCount', {
                  n: (project.dataset_ids || []).length,
                })}
            </span>
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
        </div>
      </div>

      {/* 하위 뷰 back(실행 목록으로) — list 모드 외에서만. */}
      {isSub && (
        <button type='button' className={cx('sub-back')} onClick={backToRuns}>
          ← {t('evaluation.run.backToRuns')}
        </button>
      )}

      {/* ── 실행 목록 + 액션 ── */}
      {view.mode === 'list' && (
        <section className={cx('runs')}>
          <div className={cx('runs-head')}>
            <h3 className={cx('runs-title')}>
              {t('evaluation.project.detail.runsTitle')}
            </h3>
            <span className={cx('runs-count')}>{runs.length}</span>
            <div className={cx('runs-spacer')} />
            {runs.length >= 2 && (
              <button
                type='button'
                className={cx('compare-btn')}
                onClick={openCompare}
              >
                {t('evaluation.project.detail.compare')}
              </button>
            )}
            <button
              type='button'
              className={cx('new-run-btn')}
              disabled={starting}
              onClick={handleNewRun}
            >
              {starting
                ? t('evaluation.running')
                : `+ ${t('evaluation.project.detail.newRun')}`}
            </button>
          </div>

          {runs.length === 0 ? (
            <div className={cx('runs-empty')}>
              {t('evaluation.project.detail.noRuns')}
            </div>
          ) : (
            <div className={cx('run-list')}>
              {runs.map((run) => {
                const summary = configSummary(run);
                const preview = metricKeys
                  .filter((k) => run.metrics?.[k] != null)
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
                            .map((k) => fmtRunMetric(k, run.metrics[k]))
                            .join(' · ')}
                        </span>
                      )}
                      <span
                        className={cx('status-chip', `status-${run.status}`)}
                      >
                        {t(STATUS_KEYS[run.status] || run.status || 'running')}
                      </span>
                      <span className={cx('run-date')}>
                        {fmtDate(run.create_datetime)}
                      </span>
                      <span className={cx('run-open')}>
                        {project.eval_type === 'expert'
                          ? t('evaluation.project.detail.resume')
                          : t('evaluation.project.detail.open')}
                      </span>
                      <button
                        type='button'
                        className={cx('run-delete')}
                        onClick={(e) => handleDeleteRun(run, e)}
                      >
                        {t('delete.label')}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* ── 새 실행 설정(benchmark/judge) ── */}
      {view.mode === 'newRun' && project.eval_type === 'benchmark' && (
        <BenchmarkRunConfig running={starting} onRun={handleBenchmarkRun} />
      )}
      {view.mode === 'newRun' && project.eval_type === 'judge' && (
        <JudgeRunConfig running={starting} onRun={handleJudgeRun} />
      )}

      {/* ── run 결과 뷰(benchmark/judge) ── */}
      {view.mode === 'result' && project.eval_type === 'benchmark' && (
        <BenchmarkResultView
          modelId={project.model_id}
          jobId={view.jobId}
          status={view.status}
          onComplete={fetchProject}
        />
      )}
      {view.mode === 'result' && project.eval_type === 'judge' && (
        <JudgeResultView
          modelId={project.model_id}
          jobId={view.jobId}
          fallbackCriteria={view.criteria}
          onComplete={fetchProject}
        />
      )}

      {/* ── 전문가 run 뷰(재개) ── */}
      {view.mode === 'expert' && (
        <ExpertRunView
          modelId={project.model_id}
          jobId={view.jobId}
          onExit={backToRuns}
        />
      )}

      {/* ── run 비교(EvalComparison 재사용) ── */}
      {view.mode === 'compare' && (
        <section className={cx('runs')}>
          <h3 className={cx('runs-title')}>
            {t('evaluation.project.detail.compareTitle')}
          </h3>
          <EvalComparison comparison={compareData} />
        </section>
      )}

      {showInferModal && (
        <ExpertInferenceModal
          workspaceId={workspaceId}
          onConfirm={startExpertRun}
          onClose={() => setShowInferModal(false)}
        />
      )}
    </div>
  );
};

export default ProjectDetail;
