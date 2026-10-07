import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { Redirect, useHistory, useRouteMatch } from 'react-router-dom';

import { Badge, ButtonV2, Loading } from '@jonathan/ui-react';

import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalProject, getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';
import { startPath } from '@src/store/modules/breadCrumb';

import { addNineHours } from '@src/utils';

import ScoreRadar from '../EvalCrossCompare/ScoreRadar';
import {
  BENCHMARK_CATEGORIES,
  BENCHMARK_GROUPS,
  BENCHMARK_RESULT_EVAL_TYPES,
} from './benchmarks';
import { formatMetricValue, metricLabel } from './benchmarkMetrics';
import {
  GENERATIVE_COLUMNS,
  GROUP_COLOR,
  batchSummaryOf,
  benchmarkEntriesOf,
  buildRunGroups,
  detailRowsOf,
  entryProgressOf,
  generativeRowsOf,
  launchFailureEntriesOf,
} from './batchSummary';
import { POLL_DEADLINE_MS, pollIntervalMs } from './resultPolling';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

// 이 화면의 숫자는 소수 둘째 자리로 맞춘다 — 원 지표 표에 70 과 26.40 이 섞이면 자릿수로 비교가 흐려진다.
const f2 = (value) => (Number.isFinite(value) ? value.toFixed(2) : '-');

// 카드(실행) 상태 → 배지. partial = 끝났는데 일부 벤치마크만 성공.
const GROUP_BADGE = {
  running: { type: 'blue', key: 'evaluation.project.status.running' },
  completed: { type: 'green', key: 'evaluation.project.status.completed' },
  partial: { type: 'yellow', key: 'evaluation.batch.statusPartial' },
  failed: { type: 'red', key: 'evaluation.failed' },
};

const CATEGORY_LABEL_KEY = Object.fromEntries(
  BENCHMARK_CATEGORIES.map((c) => [c.id, c.labelKey]),
);

// 벤치마크 실행(묶음) 결과 요약 — ETRI 결과 화면(Evaluation/lmeval 대시보드)의 구성을 따른다:
//   ① 실행 진행 상황 → ② 요약 카드 4장 → ③ 벤치마크별 점수 + 카테고리 레이더 → ④ 생성형 지표 →
//   ⑤ 전체 지표 상세. (ETRI 의 실행 로그는 벤치마크마다 잡이 따로라 각 런의 세부 화면에 둔다.)
// 벤치마크·지표 행을 누르면 그 런의 세부 결과(BenchmarkResultPage, /run/:jobId?benchmark=<id>)로
// 간다 — 종전 실행 목록에서 행을 눌렀을 때 열리던 바로 그 화면이고, 런 하나가 여러 벤치마크를
// 담으므로 누른 벤치마크만 보이게 좁힌다. 세부 화면의 뒤로가기는 이 요약으로 돌아온다.
// 한 실행은 GPU 수만큼의 런으로 나뉘고 런마다 벤치마크를 차례로 채점한다(설계 §14) — 진행은
// 벤치마크 단위로 센다(채점기 progress.json → BE get_eval_result.progress).
// 라우트: /user/workspace/:id/evaluation/project/:projectId/batch/:batchKey
//   batchKey = 실행 기록 id, 또는 기록 없는 런이면 'r-<jobId>'(batchSummary.RUN_KEY_PREFIX).
const BenchmarkBatchPage = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, projectId, batchKey } = match.params;

  const [project, setProject] = useState(null); // null=로딩
  const [runs, setRuns] = useState([]);
  const [batches, setBatches] = useState([]);
  const [notFound, setNotFound] = useState(false);
  // 멤버 런의 결과 JSON(도착한 것만) · 폴링이 알려 준 최신 상태(목록 행보다 빠르다) ·
  // 아직 결과 JSON 이 없는 런의 벤치마크별 진행(끝난 벤치마크 점수 포함).
  const [results, setResults] = useState({});
  const [liveStatus, setLiveStatus] = useState({});
  const [progressByJob, setProgressByJob] = useState({});

  const projectBase = `/user/workspace/${workspaceId}/evaluation/project/${projectId}`;
  const projectPath = `${projectBase}/runs`;
  const selfPath = `${projectBase}/batch/${batchKey}`;

  const fetchProject = useCallback(async () => {
    const res = await getEvalProject(projectId);
    if (res.status === STATUS_SUCCESS && res.result?.project) {
      setProject(res.result.project);
      setRuns(res.result.runs?.runs ?? []);
      setBatches(res.result.batches ?? []);
    } else {
      setNotFound(true);
    }
  }, [projectId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    fetchProject();
  }, [dispatch, fetchProject]);

  const group = useMemo(
    () => buildRunGroups(runs, batches).find((g) => g.key === batchKey) || null,
    [runs, batches, batchKey],
  );

  // 폴링은 결과 JSON 이 필요한 멤버만 — 진행 중인 런은 완료(또는 실패)까지, 완료 런은 한 번
  // (few-shot·태스크·원 지표 같은 상세가 결과 JSON 에만 있다). 목록 행의 상태는 결과 조회가
  // 런을 마감한 뒤에야 바뀌므로(BE lazy 마감), 이 폴링이 곧 멤버 런을 마감시키는 트리거다.
  const memberKey = group
    ? group.members.map((r) => `${r.job_id}:${r.model_id}`).join(',')
    : '';
  useEffect(() => {
    if (!group) return undefined;
    // effect 마다 제 상태를 둔다 — 공유 ref 를 쓰면 /batch/1 → /batch/2 로 바뀔 때 이전 요청이
    // 되살아난 alive 를 보고 다음 폴링을 또 건다(codex 리뷰). 이전 묶음의 결과도 비운다.
    const ref = { alive: true, timer: null };
    setResults({});
    setLiveStatus({});
    setProgressByJob({});
    const startedAt = Date.now();
    const pending = new Set(group.members.map((r) => String(r.job_id)));
    const modelOf = Object.fromEntries(
      group.members.map((r) => [String(r.job_id), r.model_id]),
    );
    let refreshed = false;

    const schedule = () => {
      const elapsed = Date.now() - startedAt;
      if (ref.alive && pending.size && elapsed < POLL_DEADLINE_MS) {
        ref.timer = setTimeout(tick, pollIntervalMs(elapsed));
      }
    };

    const tick = async () => {
      if (!ref.alive) return;
      const jobs = [...pending];
      let settled;
      try {
        settled = await Promise.all(
          jobs.map((jobId) =>
            getEvalResult(modelOf[jobId], jobId).then((res) => ({
              jobId,
              res,
            })),
          ),
        );
      } catch (err) {
        // 한 번의 실패가 폴링을 영구히 멈추지 않게 — 다음 차례에 다시 묻는다.
        console.error(err);
        schedule();
        return;
      }
      if (!ref.alive) return;
      let finishedNow = false;
      const nextResults = {};
      const nextStatus = {};
      const nextProgress = {};
      settled.forEach(({ jobId, res }) => {
        if (res.status !== STATUS_SUCCESS) return;
        const result = res.result || {};
        // 진행 기록은 결과 JSON 이 없을 때만 온다 — 도는 런은 벤치마크가 끝날 때마다, 도중에
        // 멈춘 런은 그때까지의 점수를 여기서 보여 준다.
        if (!result.ready && result.progress) nextProgress[jobId] = result.progress;
        if (result.ready) {
          nextResults[jobId] = result.metrics;
          nextStatus[jobId] = 'completed';
          pending.delete(jobId);
          finishedNow = true;
        } else if (TERMINAL.has(result.status)) {
          nextStatus[jobId] = result.status;
          pending.delete(jobId);
          finishedNow = true;
        } else if (result.status) {
          nextStatus[jobId] = result.status;
        }
      });
      setResults((prev) => ({ ...prev, ...nextResults }));
      setLiveStatus((prev) => ({ ...prev, ...nextStatus }));
      setProgressByJob((prev) => ({ ...prev, ...nextProgress }));
      // 이번에 마감된 런이 있으면 목록 행(평탄화 점수·상태)을 한 번 새로 받는다 — 카드 목록과
      // 이 화면이 같은 사실을 말해야 한다. 처음 한 바퀴의 완료 런은 이미 끝난 것이라 제외.
      if (finishedNow && refreshed) fetchProject();
      refreshed = true;
      schedule();
    };
    tick();
    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
    // 멤버 구성이 바뀔 때만 다시 건다(목록 새로 고침마다 폴링을 재시작하지 않는다).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberKey]);

  const members = useMemo(
    () =>
      (group?.members || []).map((run) => ({
        ...run,
        status: liveStatus[String(run.job_id)] || run.status,
      })),
    [group, liveStatus],
  );
  // 런치조차 못 한 벤치마크도 항목으로 — 요청한 전부가 보여야 "4개 중 3개" 가 읽힌다.
  const entries = useMemo(
    () => [
      ...benchmarkEntriesOf(members, results, progressByJob),
      ...launchFailureEntriesOf(group?.launchFailures),
    ],
    [members, results, progressByJob, group],
  );
  const summary = useMemo(() => batchSummaryOf(entries), [entries]);
  const generativeRows = useMemo(() => generativeRowsOf(entries), [entries]);
  const detailRows = useMemo(() => detailRowsOf(entries), [entries]);
  // 진행은 벤치마크 단위 — 런치 실패 항목도 entries 에 들어 있어 따로 세지 않는다.
  const progress = useMemo(() => entryProgressOf(entries), [entries]);

  // 런치 실패 항목은 런이 없어 열 곳이 없다(jobId null). 한 런이 여러 벤치마크를 담으므로 누른
  // 벤치마크를 쿼리로 넘겨 세부 화면이 그것만 보이게 한다.
  const openBenchmark = (entry) =>
    entry.jobId &&
    history.push({
      pathname: `${projectBase}/run/${entry.jobId}`,
      search: entry.benchmarkKey
        ? `?benchmark=${encodeURIComponent(entry.benchmarkKey)}`
        : '',
      state: { from: selfPath, fromLabel: t('evaluation.batch.backToSummary') },
    });
  const runAgain = () =>
    history.push({ pathname: projectPath, state: { openRunConfig: true } });
  const goBack = () => history.push(projectPath);

  if (notFound) {
    return (
      <div className={cx('result-page')}>
        <DeployDetailHeader
          title={t('evaluation.batch.title')}
          backLabel={t('evaluation.run.backToRuns')}
          onBack={goBack}
        />
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  if (project === null) {
    return (
      <div className={cx('result-page')}>
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.project.loading')}</span>
        </div>
      </div>
    );
  }

  // 이 화면은 정답 대조 프로젝트의 것이다(ProjectDetail 이 다른 유형에서는 이리로 보내지 않는다).
  if (!BENCHMARK_RESULT_EVAL_TYPES.includes(project.eval_type))
    return <Redirect to={projectPath} />;

  // 의도/슬롯 평가(MixATIS)는 한 실행이 벤치마크 하나라 요약 카드·그룹 범례·레이더·생성형 표·
  // lm-eval 지표 상세(묶음용)가 늘 비거나 점수 카드와 겹친다 — 그 영역을 걷고 제목도 유형 이름으로
  // 단다. 세부 결과는 점수 카드의 행을 눌러 연다. 정답 대조는 그대로다.
  const isIntent = project.eval_type === 'intent';
  const titleKey = isIntent
    ? 'evaluation.batch.titleIntent'
    : 'evaluation.batch.title';

  if (!group) {
    return (
      <div className={cx('result-page')}>
        <DeployDetailHeader
          title={t(titleKey)}
          backLabel={project.name || t('evaluation.run.backToRuns')}
          onBack={goBack}
        />
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  const badge = GROUP_BADGE[progress.status] || GROUP_BADGE.running;
  const quickLimit = group.sampleLimit ?? entries[0]?.sampleLimit ?? null;
  const donePercent = progress.total
    ? Math.round(
        ((progress.counts.completed +
          progress.counts.failed +
          progress.counts.cancelled) /
          progress.total) *
          100,
      )
    : 0;

  const statusText = (entry) => {
    if (entry.launchError != null) return t('evaluation.batch.launchFailed');
    if (entry.status === 'completed') return null;
    if (entry.status === 'cancelled') return t('evaluation.batch.cancelled');
    if (TERMINAL.has(entry.status)) return t('evaluation.batch.failed');
    // 대기 = 같은 런의 앞 벤치마크를 채점하는 중(런 하나가 벤치마크를 차례로 채점한다).
    if (entry.status === 'pending') return t('evaluation.batch.queued');
    return t('evaluation.batch.pending');
  };
  // 실패 사유 — 런치 실패(런이 없다)와 채점 실패(채점기 기록)를 같은 자리(툴팁)에 둔다.
  const reasonOf = (entry) => entry.launchError || entry.error || undefined;

  const cardLabel = (id) => t(`evaluation.batch.card.${id}`);

  return (
    <div id='BenchmarkBatchPage' className={cx('result-page')}>
      <DeployDetailHeader
        title={
          <span className={cx('result-title')}>
            {t(titleKey)}
            <Badge label={t(badge.key)} type={badge.type} size='lg' />
            {quickLimit != null && (
              <Badge
                label={t('evaluation.bench.quickCheckShort')}
                type='yellow'
                size='lg'
              />
            )}
          </span>
        }
        backLabel={project.name || t('evaluation.run.backToRuns')}
        onBack={goBack}
        right={
          <ButtonV2
            type='solid'
            size='l'
            label={t('evaluation.bench.runAgain')}
            onClick={runAgain}
          />
        }
      />

      <p className={cx('result-meta')}>
        <span>
          {t('evaluate.model.label')} <em>{group.modelName}</em>
        </span>
        <span>
          {t('checkpoint.label')} <em>{group.checkpoint || '-'}</em>
        </span>
        {/* 머리 줄은 모델·체크포인트·생성 일시만 — 벤치마크 수·진행은 아래 진행 상황, 빠른 점검은 배지,
            채점 엔진은 각 벤치마크 세부 화면(채점 구성)에 있다. */}
        <span>
          {t('createdAt.label')}{' '}
          <em>{addNineHours(group.createDatetime) || '-'}</em>
        </span>
      </p>

      <div className={cx('batch-body')}>
        {/* ① 실행 진행 상황 — 전체 진척 + 벤치마크별 상태. 벤치마크마다 잡이 따로라 "현재 태스크"
          진척 대신 각 벤치마크의 상태를 칩으로 세운다. */}
        <section className={cx('result-section', 'batch-card')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.batch.progressTitle')}
          </h3>
          <div className={cx('batch-progress')}>
            <span className={cx('batch-progress-label')}>
              {t('evaluation.batch.progressDone', {
                done: progress.counts.completed,
                total: progress.total,
              })}
              {progress.counts.failed > 0 &&
                ` · ${t('evaluation.batch.progressFailed', {
                  count: progress.counts.failed,
                })}`}
              {progress.counts.cancelled > 0 &&
                ` · ${t('evaluation.batch.progressCancelled', {
                  count: progress.counts.cancelled,
                })}`}
            </span>
            <div className={cx('batch-bar')}>
              <i style={{ width: `${donePercent}%` }} />
            </div>
            <span className={cx('batch-progress-pct')}>{donePercent}%</span>
          </div>
          <div className={cx('batch-stages')}>
            {entries.map((entry) => (
              <button
                type='button'
                key={entry.key}
                className={cx('batch-stage', `st-${entry.status}`)}
                onClick={() => openBenchmark(entry)}
                disabled={!entry.jobId}
                title={reasonOf(entry)}
              >
                <i className={cx('batch-stage-dot')} />
                {entry.label}
              </button>
            ))}
          </div>
        </section>

        {/* ② 요약 카드 4장 — ETRI 와 같은 구성. 종합만 정답률 계열 대표 지표로 좁힌다. */}
        {!isIntent && (
          <section className={cx('batch-cards4')}>
            {summary.cards.map((card) => (
              <div
                key={card.id}
                className={cx(
                  'batch-sum',
                  card.id === 'overall' ? 'overall' : `g-${GROUP_COLOR[card.id]}`,
                )}
              >
                <span className={cx('batch-sum-k')}>{cardLabel(card.id)}</span>
                <span className={cx('batch-sum-v')}>{f2(card.value)}</span>
                <span className={cx('batch-sum-s')}>
                  {card.id === 'overall'
                    ? t('evaluation.batch.cardOverallNote', { count: card.count })
                    : t('evaluation.batch.cardCount', {
                        count: card.count,
                        total: card.total,
                      })}
                </span>
              </div>
            ))}
          </section>
        )}

        {/* ③ 벤치마크별 점수 + 카테고리 레이더 */}
        <section className={cx('batch-two', isIntent && 'single')}>
          <div className={cx('result-section', 'batch-card')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.batch.scoresTitle')}
            </h3>
            {/* 그룹 색 범례 — 묶음(여러 그룹) 실행용. 의도/슬롯은 막대가 하나라 걷는다. */}
            {!isIntent && (
              <div className={cx('batch-legend')}>
                {BENCHMARK_GROUPS.map((g) => (
                  <span key={g.id}>
                    <i className={cx('batch-sw', `g-${g.color}`)} />
                    {t(g.labelKey)}
                  </span>
                ))}
              </div>
            )}
            <div className={cx('batch-benchlist')}>
              {entries.map((entry) => {
                const pending = statusText(entry);
                const width =
                  entry.value == null
                    ? 0
                    : Math.max(
                        0,
                        Math.min(100, (entry.value / entry.scaleMax) * 100),
                      );
                return (
                  <button
                    type='button'
                    key={entry.key}
                    className={cx(
                      'batch-brow',
                      pending && TERMINAL.has(entry.status) && 'error',
                    )}
                    onClick={() => openBenchmark(entry)}
                    disabled={!entry.jobId}
                    title={reasonOf(entry)}
                  >
                    <span className={cx('batch-bt')}>
                      <span className={cx('batch-bname')}>
                        {entry.label}
                        <span className={cx('batch-bmeta')}>
                          {metricLabel(t, entry.metricId) || entry.metricId}
                          {entry.numFewshot != null &&
                            ` · ${entry.numFewshot}-shot`}
                        </span>
                      </span>
                      <span className={cx('batch-bval')}>
                        {pending ||
                          formatMetricValue(entry.metricId, entry.value)}
                      </span>
                    </span>
                    <span className={cx('batch-bline')}>
                      <i
                        className={cx(`g-${GROUP_COLOR[entry.group] ?? 3}`)}
                        style={{ width: `${width}%` }}
                      />
                    </span>
                  </button>
                );
              })}
            </div>
            <p className={cx('run-note')}>{t('evaluation.batch.openHint')}</p>
          </div>

          {!isIntent && (
            <div className={cx('result-section', 'batch-card')}>
              <h3 className={cx('result-section-title')}>
                {t('evaluation.batch.radarTitle')}
              </h3>
              {summary.radar.length >= 3 ? (
                <ScoreRadar
                  title={t('evaluation.batch.radarTitle')}
                  axes={summary.radar.map((r) => ({
                    id: r.id,
                    label: CATEGORY_LABEL_KEY[r.id]
                      ? t(CATEGORY_LABEL_KEY[r.id])
                      : r.id,
                  }))}
                  series={[
                    {
                      key: 'batch',
                      label: group.checkpoint
                        ? `${group.modelName} · ${group.checkpoint}`
                        : group.modelName,
                      colorIndex: 0,
                      dashed: false,
                      values: Object.fromEntries(
                        summary.radar.map((r) => [r.id, r.value]),
                      ),
                    },
                  ]}
                />
              ) : (
                <p className={cx('batch-empty')}>
                  {t('evaluation.batch.radarNeedsThree')}
                </p>
              )}
            </div>
          )}
        </section>

        {/* ④ 생성형 지표 — 생성형·사용자 벤치마크의 F1/EM/BLEU/ROUGE(lm-eval 원 지표 이름으로 고른다). */}
        {!isIntent && (
          <section className={cx('result-section', 'batch-card')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.batch.generativeTitle')}
            </h3>
            {generativeRows.length === 0 ? (
              <p className={cx('batch-empty')}>
                {t('evaluation.batch.generativeEmpty')}
              </p>
            ) : (
              <div className={cx('batch-tablewrap')}>
                <table className={cx('batch-tbl')}>
                  <thead>
                    <tr>
                      <th scope='col'>{t('evaluation.batch.colBenchmark')}</th>
                      {GENERATIVE_COLUMNS.map((col) => (
                        <th key={col.id} scope='col' className={cx('num')}>
                          {col.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {generativeRows.map((row) => (
                      <tr
                        key={row.entry.key}
                        className={cx('clickable')}
                        onClick={() => openBenchmark(row.entry)}
                      >
                        {/* 행 클릭은 마우스용, 키보드는 이름 버튼으로 연다. */}
                        <td>
                          <button
                            type='button'
                            className={cx('batch-cell-link')}
                            onClick={(event) => {
                              event.stopPropagation();
                              openBenchmark(row.entry);
                            }}
                          >
                            {row.entry.label}
                          </button>
                        </td>
                        {GENERATIVE_COLUMNS.map((col) => (
                          <td key={col.id} className={cx('num')}>
                            {f2(row.cells[col.id])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* ⑤ 전체 지표 상세 — 벤치마크 × lm-eval 원 지표 한 줄씩. 행을 누르면 그 런의 세부 결과. */}
        {!isIntent && (
          <section className={cx('result-section', 'batch-card')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.batch.detailTitle')}
            </h3>
            <div className={cx('batch-tablewrap')}>
              <table className={cx('batch-tbl')}>
                <thead>
                  <tr>
                    <th scope='col'>{t('evaluation.batch.colBenchmark')}</th>
                    <th scope='col'>{t('evaluation.batch.colTask')}</th>
                    <th scope='col' className={cx('num')}>
                      {t('evaluation.batch.colFewshot')}
                    </th>
                    <th scope='col'>{t('evaluation.batch.colMetric')}</th>
                    <th scope='col' className={cx('num')}>
                      {t('evaluation.batch.colValue')}
                    </th>
                    <th scope='col' className={cx('num')}>
                      {t('evaluation.batch.colStderr')}
                    </th>
                    <th scope='col' className={cx('num')}>
                      {t('evaluation.batch.colN')}
                    </th>
                    <th scope='col' className={cx('num')}>
                      {t('evaluation.batch.colElapsed')}
                    </th>
                    <th scope='col'>{t('evaluation.batch.colStatus')}</th>
                  </tr>
                </thead>
                <tbody>
                  {detailRows.map((row) => {
                    const { entry } = row;
                    return (
                      <tr
                        key={row.key}
                        className={cx(
                          entry.jobId && 'clickable',
                          row.first && 'first',
                        )}
                        onClick={() => openBenchmark(entry)}
                        title={reasonOf(entry)}
                      >
                        <td>
                          {row.first &&
                            (entry.jobId ? (
                              <button
                                type='button'
                                className={cx('batch-cell-link')}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  openBenchmark(entry);
                                }}
                              >
                                {entry.label}
                              </button>
                            ) : (
                              entry.label
                            ))}
                        </td>
                        <td className={cx('mono', 'wrap')}>
                          {row.first ? entry.tasks.join(', ') || '-' : ''}
                        </td>
                        <td className={cx('num')}>
                          {row.first ? (entry.numFewshot ?? '-') : ''}
                        </td>
                        <td className={cx('mono')}>
                          {row.lm
                            ? `${row.metric}${row.filter ? ` · ${row.filter}` : ''}`
                            : metricLabel(t, row.metric) || row.metric || '-'}
                        </td>
                        <td className={cx('num')}>
                          {row.lm
                            ? f2(row.score)
                            : formatMetricValue(row.metric, row.score)}
                        </td>
                        <td className={cx('num')}>
                          {row.stderr == null ? '-' : `± ${f2(row.stderr)}`}
                        </td>
                        <td className={cx('num')}>
                          {row.first ? (entry.n ?? '-') : ''}
                        </td>
                        <td className={cx('num')}>
                          {row.first ? (entry.elapsedSec ?? '-') : ''}
                        </td>
                        <td>
                          {row.first && (
                            <span
                              className={cx('batch-pill', `st-${entry.status}`)}
                            >
                              {statusText(entry) ||
                                t('evaluation.project.status.completed')}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className={cx('run-note')}>{t('evaluation.batch.summaryNote')}</p>
          </section>
        )}
      </div>
    </div>
  );
};

export default BenchmarkBatchPage;
