import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { successToastMessage } from '@src/utils';

import {
  BENCHMARKS,
  BENCHMARK_CATEGORIES,
  BENCHMARK_MAP,
  categoryCount,
  defaultMetricFor,
} from './benchmarks';
import { METRIC_MAP } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// 벤치마크 실행 설정(프로젝트 상속) — 모델·데이터셋은 프로젝트에서 잠금. image.png 대로
//   1) 벤치마크 선택 → 2) 벤치마크별 메트릭 지정 → 3) 확인 3단계 위저드.
//   onRun([{ benchmark, metric }]) 로 상위(ProjectDetail)가 runBenchmark 호출.
const STEPS = [
  { n: 1, key: 'evaluation.bench.step1' },
  { n: 2, key: 'evaluation.bench.step2' },
  { n: 3, key: 'evaluation.bench.step3' },
];

const BenchmarkRunConfig = ({ running, onRun }) => {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState([]); // 벤치마크 id(선택 순서)
  const [metricMap, setMetricMap] = useState({}); // { benchmarkId: metricId }
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [focusMetric, setFocusMetric] = useState('accuracy'); // 설명 패널 대상

  // 동기 클릭 핸들러라 selected 클로저를 그대로 분기(부수효과를 updater 안에 중첩 안 함 —
  // React updater 는 순수해야 하며 StrictMode 이중호출/향후 prev 의존 시 오작동 방지).
  const toggleBenchmark = (id) => {
    if (selected.includes(id)) {
      setSelected((prev) => prev.filter((x) => x !== id));
      setMetricMap((m) => {
        const next = { ...m };
        delete next[id];
        return next;
      });
      return;
    }
    const metric = defaultMetricFor(id);
    setSelected((prev) => [...prev, id]);
    setMetricMap((m) => ({ ...m, [id]: metric }));
    setFocusMetric(metric);
  };

  const setMetric = (benchmarkId, metricId) => {
    setMetricMap((m) => ({ ...m, [benchmarkId]: metricId }));
    setFocusMetric(metricId);
  };

  const clearAll = () => {
    setSelected([]);
    setMetricMap({});
    setStep(1);
  };

  const filtered = useMemo(
    () =>
      BENCHMARKS.filter(
        (b) =>
          (category === 'all' || b.category === category) &&
          (query.trim() === '' ||
            b.label.toLowerCase().includes(query.trim().toLowerCase()) ||
            b.desc.toLowerCase().includes(query.trim().toLowerCase())),
      ),
    [category, query],
  );

  const metricCount = useMemo(
    () => new Set(selected.map((id) => metricMap[id]).filter(Boolean)).size,
    [selected, metricMap],
  );

  const canProceed = selected.length > 0;
  const goStep = (n) => {
    if (n > 1 && !canProceed) return;
    setStep(n);
  };

  const handleRun = () => {
    if (!canProceed || running) return;
    onRun(selected.map((id) => ({ benchmark: id, metric: metricMap[id] })));
  };

  const focus = METRIC_MAP[focusMetric];

  return (
    <div className={cx('wz')}>
      {/* ── 헤더 + 스텝 인디케이터 ── */}
      <div className={cx('wz-head')}>
        <div className={cx('wz-head-text')}>
          <h2 className={cx('wz-title')}>{t('evaluation.bench.setupTitle')}</h2>
          <p className={cx('wz-subtitle')}>
            {t('evaluation.bench.setupSubtitle')}
          </p>
        </div>
        <ol className={cx('wz-steps')}>
          {STEPS.map((s) => (
            <li
              key={s.n}
              className={cx(
                'wz-step',
                step === s.n && 'on',
                step > s.n && 'done',
              )}
              onClick={() => goStep(s.n)}
            >
              <span className={cx('wz-step-num')}>{s.n}</span>
              <span className={cx('wz-step-label')}>{t(s.key)}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className={cx('wz-body')}>
        {/* ── 좌: 단계별 본문 ── */}
        <div className={cx('wz-main')}>
          {step === 1 && (
            <section className={cx('wz-panel')}>
              <div className={cx('wz-panel-head')}>
                <div>
                  <h3 className={cx('wz-panel-title')}>
                    1. {t('evaluation.bench.selectBenchTitle')}
                  </h3>
                  <p className={cx('wz-panel-desc')}>
                    {t('evaluation.bench.selectBenchDesc')}
                  </p>
                </div>
                <input
                  className={cx('wz-search')}
                  type='text'
                  value={query}
                  placeholder={t('evaluation.bench.searchPlaceholder')}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>

              <div className={cx('wz-select-body')}>
                <ul className={cx('wz-cats')}>
                  <li className={cx('wz-cats-label')}>
                    {t('evaluation.bench.category')}
                  </li>
                  {BENCHMARK_CATEGORIES.map((c) => (
                    <li
                      key={c.id}
                      className={cx('wz-cat', category === c.id && 'on')}
                      onClick={() => setCategory(c.id)}
                    >
                      <span>{c.label}</span>
                      <span className={cx('wz-cat-count')}>
                        {categoryCount(c.id)}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className={cx('wz-cards')}>
                  {filtered.map((b) => {
                    const on = selected.includes(b.id);
                    return (
                      <div
                        key={b.id}
                        className={cx('wz-card', on && 'on')}
                        onClick={() => toggleBenchmark(b.id)}
                      >
                        <span className={cx('wz-check', on && 'on')}>
                          {on ? '✓' : ''}
                        </span>
                        <div className={cx('wz-card-body')}>
                          <div className={cx('wz-card-name')}>{b.label}</div>
                          <div className={cx('wz-card-desc')}>{b.desc}</div>
                          <span className={cx('wz-tag')}>
                            {BENCHMARK_CATEGORIES.find(
                              (c) => c.id === b.category,
                            )?.label || b.category}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  {filtered.length === 0 && (
                    <div className={cx('wz-cards-empty')}>
                      {t('evaluation.noSearchResult')}
                    </div>
                  )}
                </div>
              </div>

              <p className={cx('wz-hint')}>{t('evaluation.bench.minOne')}</p>
            </section>
          )}

          {step === 2 && (
            <section className={cx('wz-panel')}>
              <h3 className={cx('wz-panel-title')}>
                2. {t('evaluation.bench.metricTitle')}
              </h3>
              <p className={cx('wz-panel-desc')}>
                {t('evaluation.bench.metricDesc')}
              </p>

              <div className={cx('wz-metric-body')}>
                <div className={cx('wz-metric-table')}>
                  <div className={cx('wz-mt-head')}>
                    <span>{t('evaluation.bench.colBench')}</span>
                    <span>{t('evaluation.bench.colRecommended')}</span>
                    <span>{t('evaluation.bench.colMetric')}</span>
                    <span />
                  </div>
                  {selected.map((id) => {
                    const b = BENCHMARK_MAP[id];
                    return (
                      <div key={id} className={cx('wz-mt-row')}>
                        <div className={cx('wz-mt-bench')}>
                          <div className={cx('wz-card-name')}>{b.label}</div>
                          <div className={cx('wz-card-desc')}>{b.desc}</div>
                        </div>
                        <div className={cx('wz-mt-rec')}>
                          {METRIC_MAP[b.recommended]?.label || b.recommended}
                        </div>
                        <select
                          className={cx('wz-metric-select')}
                          value={metricMap[id] || ''}
                          onChange={(e) => setMetric(id, e.target.value)}
                          onFocus={() => setFocusMetric(metricMap[id])}
                        >
                          {b.metrics.map((mid) => (
                            <option key={mid} value={mid}>
                              {METRIC_MAP[mid]?.label || mid}
                            </option>
                          ))}
                        </select>
                        <button
                          type='button'
                          className={cx('wz-mt-remove')}
                          onClick={() => toggleBenchmark(id)}
                          aria-label='remove'
                        >
                          ✕
                        </button>
                      </div>
                    );
                  })}

                  <button
                    type='button'
                    className={cx('wz-add-custom')}
                    onClick={() =>
                      successToastMessage(
                        null,
                        t('evaluation.bench.addCustomSoon'),
                      )
                    }
                  >
                    + {t('evaluation.bench.addCustom')}
                  </button>
                </div>

                {/* 메트릭 설명 패널 */}
                <aside className={cx('wz-metric-desc')}>
                  <h4 className={cx('wz-md-title')}>
                    {t('evaluation.bench.metricPanelTitle')}
                  </h4>
                  {focus && (
                    <>
                      <div className={cx('wz-md-metric')}>{focus.label}</div>
                      <div className={cx('wz-md-sub')}>{focus.desc}</div>
                      {focus.formula && (
                        <div className={cx('wz-md-formula')}>
                          {focus.formula}
                        </div>
                      )}
                      {focus.common?.length > 0 && (
                        <>
                          <div className={cx('wz-md-label')}>
                            {t('evaluation.bench.commonBench')}
                          </div>
                          <div className={cx('wz-md-tags')}>
                            {focus.common.map((c) => (
                              <span key={c} className={cx('wz-md-tag')}>
                                {c}
                              </span>
                            ))}
                          </div>
                        </>
                      )}
                    </>
                  )}
                </aside>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className={cx('wz-panel')}>
              <h3 className={cx('wz-panel-title')}>
                3. {t('evaluation.bench.confirmTitle')}
              </h3>
              <p className={cx('wz-panel-desc')}>
                {t('evaluation.bench.summaryInfo')}
              </p>
              <div className={cx('wz-confirm-list')}>
                {selected.map((id) => (
                  <div key={id} className={cx('wz-confirm-row')}>
                    <span className={cx('wz-card-name')}>
                      {BENCHMARK_MAP[id].label}
                    </span>
                    <span className={cx('wz-confirm-metric')}>
                      {METRIC_MAP[metricMap[id]]?.label || metricMap[id]}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* ── 우: 평가 설정 요약(상시) ── */}
        <aside className={cx('wz-summary')}>
          <div className={cx('wz-sum-block')}>
            <div className={cx('wz-sum-head')}>
              <h4 className={cx('wz-sum-title')}>
                {t('evaluation.bench.selectedBench')} ({selected.length})
              </h4>
              {selected.length > 0 && (
                <button
                  type='button'
                  className={cx('wz-sum-clear')}
                  onClick={clearAll}
                >
                  {t('evaluation.bench.clearAll')}
                </button>
              )}
            </div>
            {selected.length === 0 ? (
              <div className={cx('wz-sum-empty')}>
                {t('evaluation.bench.empty')}
              </div>
            ) : (
              <ul className={cx('wz-sum-list')}>
                {selected.map((id) => (
                  <li key={id} className={cx('wz-sum-item')}>
                    <span className={cx('wz-sum-name')}>
                      {BENCHMARK_MAP[id].label}
                    </span>
                    <span className={cx('wz-sum-tag')}>
                      {
                        BENCHMARK_CATEGORIES.find(
                          (c) => c.id === BENCHMARK_MAP[id].category,
                        )?.label
                      }
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {selected.length > 0 && (
            <div className={cx('wz-sum-block')}>
              <h4 className={cx('wz-sum-title')}>
                {t('evaluation.bench.metricMapping')}
              </h4>
              <ul className={cx('wz-map-list')}>
                {selected.map((id) => (
                  <li key={id} className={cx('wz-map-item')}>
                    <span className={cx('wz-map-bench')}>
                      {BENCHMARK_MAP[id].label}
                    </span>
                    <span className={cx('wz-map-metric')}>
                      {METRIC_MAP[metricMap[id]]?.label || metricMap[id]}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className={cx('wz-sum-info')}>
            {t('evaluation.bench.summaryInfo')}
            <ul>
              <li>
                {t('evaluation.bench.totalBench')}: {selected.length}
              </li>
              <li>
                {t('evaluation.bench.totalMetric')}: {metricCount}
              </li>
            </ul>
          </div>

          <div className={cx('wz-sum-actions')}>
            {step > 1 && (
              <button
                type='button'
                className={cx('wz-btn', 'ghost')}
                onClick={() => setStep(step - 1)}
              >
                {t('evaluation.bench.prev')}
              </button>
            )}
            {step < 3 ? (
              <button
                type='button'
                className={cx('wz-btn', 'primary', !canProceed && 'disabled')}
                disabled={!canProceed}
                onClick={() => goStep(step + 1)}
              >
                {step === 1
                  ? t('evaluation.bench.nextToMetric')
                  : t('evaluation.bench.nextToConfirm')}
              </button>
            ) : (
              <button
                type='button'
                className={cx(
                  'wz-btn',
                  'primary',
                  (!canProceed || running) && 'disabled',
                )}
                disabled={!canProceed || running}
                onClick={handleRun}
              >
                {running
                  ? t('evaluation.running')
                  : t('evaluation.runBenchmark')}
              </button>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default BenchmarkRunConfig;
