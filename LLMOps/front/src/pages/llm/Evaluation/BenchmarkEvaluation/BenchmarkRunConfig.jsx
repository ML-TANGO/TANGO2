import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Badge,
  ButtonV2,
  Checkbox,
  InputText,
  Selectbox,
} from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import GuideBox from '@src/components/molecules/GuideBox';
import Tab from '@src/components/molecules/Tab';

import { errorToastMessage, successToastMessage } from '@src/utils';

import {
  BENCHMARKS,
  BENCHMARK_CATEGORIES,
  BENCHMARK_MAP,
  REAL_BENCHMARK_IDS,
  categoryCount,
  defaultMetricFor,
} from './benchmarks';
import { METRIC_MAP } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// 벤치마크 실행 설정(프로젝트 상속) — 모델·데이터셋은 프로젝트에서 잠금.
// 1) 벤치마크 선택, 2) 벤치마크별 메트릭 지정, 3) 확인 순서를 유지한다.
// onRun([{ benchmark, metric }]) 로 상위(ProjectDetail)가 runBenchmark를 호출한다.
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

  // 동기 클릭 핸들러라 selected 클로저를 그대로 분기한다. React updater 안에는
  // 부수효과를 넣지 않아 StrictMode 이중 호출에서도 선택/메트릭 상태를 분리해 유지한다.
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
    // 채점기 혼재 차단 — 실채점 벤치마크(LogicKor 등)는 전용 컨테이너로 가고 한 런은
    // 컨테이너 하나뿐이라, mock 벤치마크와 같은 런에 섞을 수 없다(BE service.run_benchmark
    // 가 거부한다). 선택 단계에서 막지 않으면 사용자가 3단계까지 진행한 뒤 실행 시점에
    // 영문 예외 메시지를 토스트로 보게 된다.
    const isReal = (bid) => REAL_BENCHMARK_IDS.includes(bid);
    const conflicting = selected.find((x) => isReal(x) !== isReal(id));
    if (conflicting) {
      const realOne = isReal(id) ? id : conflicting;
      errorToastMessage(
        null,
        t('evaluation.bench.mixScorerBlocked', {
          real: BENCHMARK_MAP[realOne]?.label || realOne,
        }),
      );
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
  const categoryOptions = BENCHMARK_CATEGORIES.map((item) => ({
    label: `${item.label} (${categoryCount(item.id)})`,
    value: item.id,
  }));
  const selectedCategory =
    categoryOptions.find((item) => item.value === category) ||
    categoryOptions[0];
  const stepOptions = STEPS.map((item) => ({
    label: item.key,
    value: item.n,
    disable: item.n > 1 && !canProceed,
  }));

  return (
    <div className={cx('wizard')}>
      <div className={cx('wizard-tabs')}>
        <Tab
          type='b'
          option={stepOptions}
          select={stepOptions[step - 1]}
          tabHandler={({ value }) => goStep(value)}
        />
      </div>

      <div className={cx('wizard-body')}>
        <div className={cx('wizard-main')}>
          {step === 1 && (
            <section className={cx('panel')}>
              <div className={cx('panel-head')}>
                <div>
                  <h3 className={cx('panel-title')}>
                    {t('evaluation.bench.selectBenchTitle')}
                  </h3>
                  <p className={cx('panel-desc')}>
                    {t('evaluation.bench.selectBenchDesc')}
                  </p>
                </div>
                <div className={cx('filters')}>
                  <Selectbox
                    list={categoryOptions}
                    selectedItem={selectedCategory}
                    onChange={(item) => setCategory(item.value)}
                    customStyle={{
                      selectboxForm: { width: '184px' },
                      listForm: { width: '184px' },
                    }}
                  />
                  <InputText
                    size='medium'
                    value={query}
                    placeholder={t('evaluation.bench.searchPlaceholder')}
                    leftIcon='/images/icon/ic-search.svg'
                    closeIcon='/images/icon/close-c.svg'
                    disableLeftIcon={false}
                    disableClearBtn={false}
                    onChange={(e) => setQuery(e.target.value)}
                    onClear={() => setQuery('')}
                    customStyle={{ width: '220px' }}
                  />
                </div>
              </div>

              <div className={cx('benchmark-grid')}>
                {filtered.map((benchmark) => {
                  const checked = selected.includes(benchmark.id);
                  const categoryLabel =
                    BENCHMARK_CATEGORIES.find(
                      (item) => item.id === benchmark.category,
                    )?.label || benchmark.category;
                  return (
                    <div
                      key={benchmark.id}
                      className={cx('benchmark-option', checked && 'selected')}
                    >
                      <Checkbox
                        checked={checked}
                        onChange={() => toggleBenchmark(benchmark.id)}
                        customLabelStyle={{ width: '100%' }}
                        label={
                          <div className={cx('benchmark-option-body')}>
                            <div className={cx('benchmark-option-name')}>
                              {benchmark.label}
                            </div>
                            <div className={cx('benchmark-option-desc')}>
                              {benchmark.desc}
                            </div>
                            <Badge
                              label={categoryLabel}
                              type='blue'
                              size='sm'
                            />
                          </div>
                        }
                      />
                    </div>
                  );
                })}
                {filtered.length === 0 && (
                  <div className={cx('grid-empty')}>
                    <EmptyBox
                      text='evaluation.noSearchResult'
                      isBox
                      customStyle={{ height: '120px' }}
                    />
                  </div>
                )}
              </div>

              <div className={cx('guide')}>
                <GuideBox
                  title={t('evaluation.bench.step1')}
                  isTitleIcon
                  textList={[t('evaluation.bench.minOne')]}
                />
              </div>
            </section>
          )}

          {step === 2 && (
            <section className={cx('panel')}>
              <div>
                <h3 className={cx('panel-title')}>
                  {t('evaluation.bench.metricTitle')}
                </h3>
                <p className={cx('panel-desc')}>
                  {t('evaluation.bench.metricDesc')}
                </p>
              </div>

              <div className={cx('metric-layout')}>
                <div className={cx('metric-list')}>
                  <div className={cx('metric-list-head')}>
                    <span>{t('evaluation.bench.colBench')}</span>
                    <span>{t('evaluation.bench.colRecommended')}</span>
                    <span>{t('evaluation.bench.colMetric')}</span>
                    <span />
                  </div>
                  {selected.map((id) => {
                    const benchmark = BENCHMARK_MAP[id];
                    const metricOptions = benchmark.metrics.map((metricId) => ({
                      label: METRIC_MAP[metricId]?.label || metricId,
                      value: metricId,
                    }));
                    const selectedMetric =
                      metricOptions.find(
                        (item) => item.value === metricMap[id],
                      ) || metricOptions[0];
                    return (
                      <div
                        key={id}
                        className={cx('metric-row')}
                        onClick={() => setFocusMetric(metricMap[id])}
                      >
                        <div className={cx('metric-benchmark')}>
                          <div className={cx('benchmark-option-name')}>
                            {benchmark.label}
                          </div>
                          <div className={cx('benchmark-option-desc')}>
                            {benchmark.desc}
                          </div>
                        </div>
                        <Badge
                          label={
                            METRIC_MAP[benchmark.recommended]?.label ||
                            benchmark.recommended
                          }
                          type='green'
                          size='sm'
                        />
                        <Selectbox
                          list={metricOptions}
                          selectedItem={selectedMetric}
                          onChange={(item) => setMetric(id, item.value)}
                          customStyle={{
                            selectboxForm: { width: '100%' },
                            listForm: { width: '100%' },
                          }}
                        />
                        <ButtonV2
                          type='clear'
                          colorType='red'
                          size='s'
                          label={t('delete.label')}
                          onClick={() => toggleBenchmark(id)}
                        />
                      </div>
                    );
                  })}
                  <div className={cx('custom-action')}>
                    {/* 섹션 단위 "추가" 액션 — 하우스(Advanced·RagSettingCenter·FineTuning)와 같은 outline+l. */}
                    <ButtonV2
                      type='outline'
                      colorType='blue'
                      size='l'
                      label={t('evaluation.bench.addCustom')}
                      onClick={() =>
                        successToastMessage(
                          null,
                          t('evaluation.bench.addCustomSoon'),
                        )
                      }
                    />
                  </div>
                </div>

                <aside className={cx('metric-description')}>
                  <h4 className={cx('metric-description-title')}>
                    {t('evaluation.bench.metricPanelTitle')}
                  </h4>
                  {focus && (
                    <>
                      <div className={cx('metric-description-name')}>
                        {focus.label}
                      </div>
                      <div className={cx('metric-description-sub')}>
                        {focus.desc}
                      </div>
                      {focus.formula && (
                        <div className={cx('metric-formula')}>
                          {focus.formula}
                        </div>
                      )}
                      {focus.common?.length > 0 && (
                        <>
                          <div className={cx('metric-common-title')}>
                            {t('evaluation.bench.commonBench')}
                          </div>
                          <div className={cx('badge-list')}>
                            {focus.common.map((item) => (
                              <Badge
                                key={item}
                                label={item}
                                type='gray'
                                size='sm'
                              />
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
            <section className={cx('panel')}>
              <div>
                <h3 className={cx('panel-title')}>
                  {t('evaluation.bench.confirmTitle')}
                </h3>
                <p className={cx('panel-desc')}>
                  {t('evaluation.bench.summaryInfo')}
                </p>
              </div>
              <div className={cx('confirm-list')}>
                {selected.map((id) => (
                  <div key={id} className={cx('confirm-row')}>
                    <span className={cx('confirm-name')}>
                      {BENCHMARK_MAP[id].label}
                    </span>
                    <Badge
                      label={METRIC_MAP[metricMap[id]]?.label || metricMap[id]}
                      type='blue'
                      size='sm'
                    />
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className={cx('summary')}>
          <div className={cx('summary-card')}>
            <div className={cx('summary-head')}>
              <h4 className={cx('summary-title')}>
                {t('evaluation.bench.selectedBench')} ({selected.length})
              </h4>
              {selected.length > 0 && (
                <ButtonV2
                  type='clear'
                  colorType='red'
                  size='s'
                  label={t('evaluation.bench.clearAll')}
                  onClick={clearAll}
                />
              )}
            </div>
            {selected.length === 0 ? (
              <EmptyBox
                text='evaluation.bench.empty'
                customStyle={{ height: '72px' }}
              />
            ) : (
              <ul className={cx('summary-list')}>
                {selected.map((id) => (
                  <li key={id} className={cx('summary-item')}>
                    <span>{BENCHMARK_MAP[id].label}</span>
                    <Badge
                      label={
                        BENCHMARK_CATEGORIES.find(
                          (item) => item.id === BENCHMARK_MAP[id].category,
                        )?.label
                      }
                      type='gray'
                      size='sm'
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {selected.length > 0 && (
            <div className={cx('summary-card')}>
              <h4 className={cx('summary-title')}>
                {t('evaluation.bench.metricMapping')}
              </h4>
              <ul className={cx('summary-list')}>
                {selected.map((id) => (
                  <li key={id} className={cx('summary-item')}>
                    <span>{BENCHMARK_MAP[id].label}</span>
                    <Badge
                      label={METRIC_MAP[metricMap[id]]?.label || metricMap[id]}
                      type='blue'
                      size='sm'
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className={cx('guide', 'summary-guide')}>
            <GuideBox
              title={t('evaluation.bench.setupTitle')}
              isTitleIcon
              textList={[
                t('evaluation.bench.summaryInfo'),
                `${t('evaluation.bench.totalBench')}: ${selected.length}`,
                `${t('evaluation.bench.totalMetric')}: ${metricCount}`,
              ]}
            />
          </div>

          <div className={cx('wizard-actions')}>
            {step > 1 && (
              <ButtonV2
                type='outline'
                colorType='blue'
                size='l'
                label={t('evaluation.bench.prev')}
                onClick={() => setStep(step - 1)}
              />
            )}
            {step < 3 ? (
              <ButtonV2
                type='solid'
                colorType='blue'
                size='l'
                label={
                  step === 1
                    ? t('evaluation.bench.nextToMetric')
                    : t('evaluation.bench.nextToConfirm')
                }
                disabled={!canProceed}
                onClick={() => goStep(step + 1)}
              />
            ) : (
              <ButtonV2
                type='solid'
                colorType='blue'
                size='l'
                label={
                  running
                    ? t('evaluation.running')
                    : t('evaluation.runBenchmark')
                }
                disabled={!canProceed || running}
                isLoading={running}
                onClick={handleRun}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default BenchmarkRunConfig;
