import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { METRIC_LABEL, barWidth, fmt } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 40; // ~2분 (컨테이너 기동 여유)

// 벤치마크 run 결과 뷰(프로젝트 상세 진입). getEvalResult(modelId, jobId) 폴링 → 데이터셋×메트릭
// 점수표 + 메트릭 평균 랭킹/차트. 완료(ready) 시 onComplete 로 상위(run 목록) 갱신 트리거.
// 폴링 가드(alive/timer/mounted + failed/timeout 토스트)는 구 standalone 페이지에서 보존.
const BenchmarkResultView = ({
  modelId,
  jobId,
  status,
  metricSet,
  onComplete,
}) => {
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

  if (failed) {
    return <div className={cx('empty')}>{t('evaluation.failed')}</div>;
  }
  if (loading && !results) {
    return <div className={cx('empty')}>{t('evaluation.running')}</div>;
  }
  if (!results) {
    return <div className={cx('empty')}>{t('evaluation.poll.timeout')}</div>;
  }

  const scores = results.scores || {};
  const averages = results.averages || {};
  const resultDatasets = Array.isArray(results.datasets)
    ? results.datasets
    : [];
  const resultMetrics = Array.isArray(results.metric_set)
    ? results.metric_set
    : Array.isArray(metricSet)
      ? metricSet
      : [];
  // 랭킹/차트용: 유한 평균만 내림차순. 표는 전체 메트릭 유지.
  const metricAverages = resultMetrics
    .map((m) => ({ id: m, label: METRIC_LABEL[m] || m, avg: averages[m] }))
    .filter((m) => Number.isFinite(Number(m.avg)))
    .sort((a, b) => Number(b.avg) - Number(a.avg));

  return (
    <div className={cx('benchmark')}>
      {metricAverages.length > 0 && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.metricRanking')}
            {results.mock && <span className={cx('mock-badge')}>mock</span>}
          </h3>
          <div className={cx('score-grid')}>
            {metricAverages.map((m, i) => (
              <div key={m.id} className={cx('score-card')}>
                <div className={cx('score-rank')}>#{i + 1}</div>
                <div className={cx('score-metric')}>{m.label}</div>
                <div className={cx('score-value')}>{fmt(m.avg)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {metricAverages.length > 0 && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>{t('evaluation.metricChart')}</h3>
          <div className={cx('chart-wrap')}>
            {metricAverages.map((m) => (
              <div key={m.id} className={cx('chart-row')}>
                <div className={cx('chart-label')}>{m.label}</div>
                <div className={cx('chart-bar-wrap')}>
                  <div
                    className={cx('chart-bar')}
                    style={{ width: `${barWidth(m.avg)}%` }}
                  />
                </div>
                <div className={cx('chart-value')}>{fmt(m.avg)}</div>
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
                <th>{t('evaluation.metric')}</th>
                {resultDatasets.map((ds) => (
                  <th key={ds}>{ds}</th>
                ))}
                <th>{t('evaluation.average')}</th>
              </tr>
            </thead>
            <tbody>
              {resultMetrics.map((m) => (
                <tr key={m}>
                  <td className={cx('metric-cell')}>{METRIC_LABEL[m] || m}</td>
                  {resultDatasets.map((ds) => (
                    <td key={ds} className={cx('score')}>
                      {fmt(scores[ds]?.[m])}
                    </td>
                  ))}
                  <td className={cx('score', 'avg')}>{fmt(averages[m])}</td>
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
