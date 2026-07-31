import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { BENCHMARK_LABEL } from './benchmarks';
import { METRIC_LABEL, barWidth, fmt } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 40; // 약 2분(컨테이너 기동 여유)

// 결과 상태를 조나단 Badge type으로 매핑한다(프로젝트 상세와 동일 색상 체계).
const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};
const STATUS_LABEL_KEY = {
  created: 'evaluation.project.status.created',
  pending: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
  failed: 'evaluation.failed',
};

// 벤치마크 run 결과 뷰(프로젝트 상세 진입). getEvalResult(modelId, jobId)를 폴링해
// 벤치마크, 메트릭, 점수 구조의 랭킹/차트/표를 표시한다.
// 완료(ready) 시 onComplete로 상위 갱신을 트리거하며 기존 폴링 가드를 유지한다.
const BenchmarkResultView = ({ modelId, jobId, status, onComplete }) => {
  const { t } = useTranslation();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const pollRef = useRef({ alive: true, timer: null });
  const completedRef = useRef(false);

  useEffect(() => {
    const ref = pollRef.current;
    ref.alive = true;
    completedRef.current = false;
    setResults(null);
    setFailed(false);
    setLoading(true);

    const poll = (attempt) => {
      if (!ref.alive) return;
      getEvalResult(modelId, jobId).then((res) => {
        if (!ref.alive) return;
        if (res.status !== STATUS_SUCCESS) {
          setLoading(false);
          errorToastMessage(res.error, res.message);
          return;
        }
        const result = res.result || {};
        if (result.status === 'failed' || result.status === 'cancelled') {
          setLoading(false);
          setFailed(true);
          return;
        }
        if (result.ready) {
          setResults(result.metrics);
          setLoading(false);
          if (!completedRef.current) {
            completedRef.current = true;
            onComplete?.();
          }
          return;
        }
        if (attempt >= POLL_MAX) {
          setLoading(false);
          errorToastMessage(null, t('evaluation.poll.timeout'));
          return;
        }
        ref.timer = setTimeout(() => poll(attempt + 1), POLL_MS);
      });
    };
    poll(0);

    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
  }, [modelId, jobId, t, onComplete]);

  // 결과를 벤치마크별 행 {key, label, metric, score}으로 변환한다. 신 스키마 우선,
  // 없으면 averages의 key별 점수로 폴백해 구 실행 결과도 유지한다.
  const rows = useMemo(() => {
    if (!results) return [];
    if (Array.isArray(results.results) && results.results.length) {
      return results.results.map((result) => ({
        key: result.benchmark,
        label: BENCHMARK_LABEL[result.benchmark] || result.benchmark,
        metric: METRIC_LABEL[result.metric] || result.metric,
        score: result.score,
      }));
    }
    const averages = results.averages || {};
    const metricMap = results.metric_map || {};
    return Object.keys(averages).map((key) => ({
      key,
      label: BENCHMARK_LABEL[key] || METRIC_LABEL[key] || key,
      metric: metricMap[key]
        ? METRIC_LABEL[metricMap[key]] || metricMap[key]
        : null,
      score: averages[key],
    }));
  }, [results]);

  const ranking = useMemo(
    () =>
      rows
        .filter((row) => Number.isFinite(Number(row.score)))
        .sort((a, b) => Number(b.score) - Number(a.score)),
    [rows],
  );

  const columns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colBenchShort'),
        selector: 'label',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-label')}>{row.label}</span>
        ),
      },
      {
        name: t('evaluation.metric'),
        selector: 'metric',
        sortable: false,
        cell: (row) => row.metric || '-',
      },
      {
        name: t('evaluation.bench.score'),
        selector: 'score',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{fmt(row.score)}</span>
        ),
      },
    ],
    [t],
  );

  const resultStatus = failed
    ? 'failed'
    : results
      ? 'completed'
      : status || 'running';
  const statusLabel = t(STATUS_LABEL_KEY[resultStatus] || resultStatus);

  const statusBadge = (
    <div className={cx('result-status')}>
      <Badge
        label={statusLabel}
        type={STATUS_BADGE_TYPE[resultStatus] || 'gray'}
        size='sm'
      />
    </div>
  );

  if (failed) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.failed'
          isBox
          isRed
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }
  if (loading && !results) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.running')}</span>
        </div>
      </div>
    );
  }
  if (!results || rows.length === 0) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.poll.timeout'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  return (
    <div className={cx('benchmark-result')}>
      {statusBadge}

      {ranking.length > 0 && (
        <section className={cx('result-section')}>
          <div className={cx('result-section-head')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.bench.resultRanking')}
            </h3>
            {results.mock && <Badge label='mock' type='gray' size='sm' />}
          </div>
          <div className={cx('score-grid')}>
            {ranking.map((row, index) => (
              <div key={row.key} className={cx('score-card')}>
                <Badge label={`#${index + 1}`} type='blue' size='sm' />
                <div className={cx('score-metric')}>{row.label}</div>
                {row.metric && (
                  <div className={cx('score-sub')}>{row.metric}</div>
                )}
                <div className={cx('score-value')}>{fmt(row.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {ranking.length > 0 && (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.resultChart')}
          </h3>
          <div className={cx('chart-wrap')}>
            {ranking.map((row) => (
              <div key={row.key} className={cx('chart-row')}>
                <div className={cx('chart-label')}>{row.label}</div>
                <div className={cx('chart-bar-wrap')}>
                  <div
                    className={cx('chart-bar')}
                    style={{ width: `${barWidth(row.score)}%` }}
                  />
                </div>
                <div className={cx('chart-value')}>{fmt(row.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className={cx('result-section')}>
        <h3 className={cx('result-section-title')}>
          {t('evaluation.results')}
        </h3>
        <div className={cx('result-table')}>
          <BorderTable
            columns={columns}
            data={rows}
            loading={false}
            selectableRows={false}
            hideSearchBox
            hideButtons
            fixedHeader
            fixedHeaderScrollHeight='480px'
          />
        </div>
      </section>
    </div>
  );
};

export default BenchmarkResultView;
