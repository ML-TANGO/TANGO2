import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { BENCHMARK_LABEL } from './benchmarks';
import { METRIC_LABEL, barWidth, fmt } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 40; // ~2분 (컨테이너 기동 여유)

// 벤치마크 run 결과 뷰(프로젝트 상세 진입). getEvalResult(modelId, jobId) 폴링 → 벤치마크별
// (benchmark → metric → score) 랭킹/차트/표. 완료(ready) 시 onComplete 로 상위 갱신 트리거.
// 폴링 가드(alive/timer/mounted + failed/timeout 토스트)는 구 standalone 페이지에서 보존.
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
        const r = res.result || {};
        if (r.status === 'failed' || r.status === 'cancelled') {
          setLoading(false);
          setFailed(true);
          return;
        }
        if (r.ready) {
          setResults(r.metrics);
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

  // 결과 → 벤치마크별 행 {key, label, metric, score}. 신 스키마(results 배열) 우선,
  // 없으면 averages(key→score) 폴백(구 런/메트릭키 런도 안 깨지게).
  const rows = useMemo(() => {
    if (!results) return [];
    if (Array.isArray(results.results) && results.results.length) {
      return results.results.map((r) => ({
        key: r.benchmark,
        label: BENCHMARK_LABEL[r.benchmark] || r.benchmark,
        metric: METRIC_LABEL[r.metric] || r.metric,
        score: r.score,
      }));
    }
    const avg = results.averages || {};
    const mmap = results.metric_map || {};
    return Object.keys(avg).map((k) => ({
      key: k,
      label: BENCHMARK_LABEL[k] || METRIC_LABEL[k] || k,
      metric: mmap[k] ? METRIC_LABEL[mmap[k]] || mmap[k] : null,
      score: avg[k],
    }));
  }, [results]);

  const ranking = useMemo(
    () =>
      rows
        .filter((r) => Number.isFinite(Number(r.score)))
        .sort((a, b) => Number(b.score) - Number(a.score)),
    [rows],
  );

  if (failed) {
    return <div className={cx('empty')}>{t('evaluation.failed')}</div>;
  }
  if (loading && !results) {
    return <div className={cx('empty')}>{t('evaluation.running')}</div>;
  }
  if (!results || rows.length === 0) {
    return <div className={cx('empty')}>{t('evaluation.poll.timeout')}</div>;
  }

  return (
    <div className={cx('benchmark')}>
      {ranking.length > 0 && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.bench.resultRanking')}
            {results.mock && <span className={cx('mock-badge')}>mock</span>}
          </h3>
          <div className={cx('score-grid')}>
            {ranking.map((r, i) => (
              <div key={r.key} className={cx('score-card')}>
                <div className={cx('score-rank')}>#{i + 1}</div>
                <div className={cx('score-metric')}>{r.label}</div>
                {r.metric && <div className={cx('score-sub')}>{r.metric}</div>}
                <div className={cx('score-value')}>{fmt(r.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {ranking.length > 0 && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.bench.resultChart')}
          </h3>
          <div className={cx('chart-wrap')}>
            {ranking.map((r) => (
              <div key={r.key} className={cx('chart-row')}>
                <div className={cx('chart-label')}>{r.label}</div>
                <div className={cx('chart-bar-wrap')}>
                  <div
                    className={cx('chart-bar')}
                    style={{ width: `${barWidth(r.score)}%` }}
                  />
                </div>
                <div className={cx('chart-value')}>{fmt(r.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.results')}</h3>
        <div className={cx('table-wrap')}>
          <table className={cx('result-table')}>
            <thead>
              <tr>
                <th>{t('evaluation.bench.colBenchShort')}</th>
                <th>{t('evaluation.metric')}</th>
                <th>{t('evaluation.bench.score')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td className={cx('metric-cell')}>{r.label}</td>
                  <td>{r.metric || '-'}</td>
                  <td className={cx('score', 'avg')}>{fmt(r.score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default BenchmarkResultView;
