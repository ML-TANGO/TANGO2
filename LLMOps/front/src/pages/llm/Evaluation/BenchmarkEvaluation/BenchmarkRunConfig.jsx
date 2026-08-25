import { useEffect, useMemo, useState } from 'react';
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

import { getBenchmarkJudgeModels } from '@src/apis/llm/evaluation';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage, successToastMessage } from '@src/utils';

import {
  BENCHMARKS,
  BENCHMARK_CATEGORIES,
  BENCHMARK_LABEL,
  BENCHMARK_MAP,
  CHECKPOINT_REQUIRED_BENCHMARK_IDS,
  REAL_BENCHMARK_IDS,
  categoryCount,
  defaultMetricFor,
} from './benchmarks';
import { METRIC_MAP } from './benchmarkMetrics';
import {
  DEFAULT_STRATEGY,
  RUN_OPTIONS_BENCHMARK_ID,
  JUDGE_MAX_OUTPUT_MAX,
  JUDGE_MAX_OUTPUT_MIN,
  MODEL_LEN_MAX,
  MODEL_LEN_MIN,
  STRATEGIES,
  buildRunOptions,
} from './runOptions';

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

// 체크포인트 "미지정" 센티넬 — Selectbox 는 value 로 항목을 찾으므로 null 대신 빈 문자열을
// 쓴다(커밋 id 는 숫자라 충돌하지 않는다).
const CHECKPOINT_NONE = '';

const BenchmarkRunConfig = ({ running, modelId, onRun }) => {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState([]); // 벤치마크 id(선택 순서)
  const [metricMap, setMetricMap] = useState({}); // { benchmarkId: metricId }
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [focusMetric, setFocusMetric] = useState('accuracy'); // 설명 패널 대상
  const [commits, setCommits] = useState([]); // 실채점 벤치마크용 커밋 체크포인트 후보
  const [commitId, setCommitId] = useState(CHECKPOINT_NONE);
  // 실행 옵션 — 숫자·문자 칸은 빈 문자열이 "미지정"이고, 그때 컨테이너 기본값이 쓰인다.
  // 기본값을 FE 가 들고 있으면 컨테이너와 어긋날 수 있어 placeholder 로만 안내한다.
  const [strategy, setStrategy] = useState(DEFAULT_STRATEGY);
  const [generateModelLen, setGenerateModelLen] = useState('');
  const [judgeModel, setJudgeModel] = useState('');
  const [judgeModels, setJudgeModels] = useState([]); // 서버 화이트리스트
  const [judgeModelLen, setJudgeModelLen] = useState('');
  const [judgeMaxOutputTokens, setJudgeMaxOutputTokens] = useState('');

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
    setCommitId(CHECKPOINT_NONE);
    setStrategy(DEFAULT_STRATEGY);
    setGenerateModelLen('');
    setJudgeModel(judgeModels.find((m) => m.isDefault)?.id ?? '');
    setJudgeModelLen('');
    setJudgeMaxOutputTokens('');
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

  // 실채점 벤치마크(LogicKor)만 체크포인트를 쓴다. 선택 단계에서 mock 과 섞이는 것을
  // 이미 막고 있으므로 selected 는 전부 실채점이거나 전부 mock 이다.
  const hasRealBenchmark = useMemo(
    () => selected.some((id) => REAL_BENCHMARK_IDS.includes(id)),
    [selected],
  );

  // 실행 옵션(전략·심판)은 LogicKor 채점기의 계약이라 실채점 전체가 아니라 그 벤치마크에만
  // 붙인다 — MixATIS 는 심판 LLM 이 없어 띄워 봐야 아무 데도 닿지 않는 칸이 된다.
  const hasRunOptions = useMemo(
    () => selected.includes(RUN_OPTIONS_BENCHMARK_ID),
    [selected],
  );

  // 심판 후보 — 서버 화이트리스트만 렌더한다. 자유 입력을 두면 캐시에 없는 모델이
  // 통과해 컨테이너가 GPU 를 잡은 뒤에야 죽는다(HF_HUB_OFFLINE=1, /hf-cache RO).
  useEffect(() => {
    if (!hasRunOptions) return undefined;
    let cancelled = false;
    (async () => {
      const res = await getBenchmarkJudgeModels();
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      const list = res.result?.models ?? [];
      const fallback = res.result?.default ?? null;
      setJudgeModels(
        list.map((m) => ({ ...m, isDefault: m.id === fallback })),
      );
      // 초기 선택 = 서버가 알려준 기본 심판. 사용자가 이미 고른 게 있으면 건드리지 않는다.
      setJudgeModel((prev) => prev || fallback || list[0]?.id || '');
    })();
    return () => {
      cancelled = true;
    };
  }, [hasRunOptions]);

  // 커밋 체크포인트 목록 — 모델 상세(CommitList)·SDS 학습 뷰와 같은 엔드포인트/응답 규약을
  // 그대로 쓴다(전용 API 헬퍼가 없는 자리라 callApi 직접 호출도 그 선례를 따른다).
  // mock 전용 런은 체크포인트를 쓰지 않으므로 조회 자체를 하지 않는다.
  useEffect(() => {
    if (!hasRealBenchmark || !modelId) return undefined;
    let cancelled = false;
    (async () => {
      const res = await callApi({
        url: `models/commit-models?model_id=${modelId}`,
        method: 'get',
      });
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      // 응답 result = { list: [...commits], model_name } (svc.get_commit_models).
      // 구버전(평면 배열)도 수용 — SDSExternalFineTuningView 와 같은 방어.
      const data = res.result;
      const list = Array.isArray(data) ? data : (data?.list ?? []);
      // 최신 커밋이 위로(모델 상세 CommitList 와 같은 정렬).
      setCommits(
        [...list].sort((a, b) =>
          String(b?.commit_datetime ?? '').localeCompare(
            String(a?.commit_datetime ?? ''),
          ),
        ),
      );
    })();
    return () => {
      cancelled = true;
    };
  }, [hasRealBenchmark, modelId]);

  const checkpointOptions = useMemo(
    () => [
      { label: t('evaluation.bench.checkpointNone'), value: CHECKPOINT_NONE },
      ...commits
        .filter((c) => c?.id != null && c?.name)
        .map((c) => ({ label: c.name, value: c.id })),
    ],
    [commits, t],
  );
  const selectedCheckpoint =
    checkpointOptions.find((item) => item.value === commitId) ||
    checkpointOptions[0];

  // 라벨에 크기를 병기한다 — 심판이 커질수록 런이 길어지므로 고르는 자리에서 보이게.
  const judgeModelOptions = useMemo(
    () =>
      judgeModels.map((m) => ({
        label: m.size_gb ? `${m.label} (${m.size_gb}GB)` : m.label,
        value: m.id,
      })),
    [judgeModels],
  );
  const selectedJudgeModel =
    judgeModelOptions.find((item) => item.value === judgeModel) ||
    judgeModelOptions[0];

  const strategyOptions = STRATEGIES.map((item) => ({
    label: item.label,
    value: item.value,
  }));
  const selectedStrategy =
    strategyOptions.find((item) => item.value === strategy) ||
    strategyOptions[0];

  const canProceed = selected.length > 0;
  const goStep = (n) => {
    if (n > 1 && !canProceed) return;
    setStep(n);
  };

  const handleRun = () => {
    if (!canProceed || running) return;
    // 체크포인트는 실채점 벤치마크에서만 의미가 있다. mock 런에 실어 보내면 BE 가
    // 무시하지만, 애초에 보내지 않아 요청이 무엇을 뜻하는지 흐리지 않는다.
    const withCheckpoint = hasRealBenchmark && commitId !== CHECKPOINT_NONE;

    // 체크포인트가 필수인 벤치마크를 빈 채로 보내면 BE 가 거부하지만, 거기까지 가지 않고
    // 무엇을 골라야 하는지 여기서 짚어 준다(위 실행옵션 검증과 같은 취지).
    const missingCheckpoint = selected.filter((id) =>
      CHECKPOINT_REQUIRED_BENCHMARK_IDS.includes(id),
    );
    if (missingCheckpoint.length > 0 && commitId === CHECKPOINT_NONE) {
      errorToastMessage(
        null,
        t('evaluation.bench.checkpointRequired', {
          benchmarks: missingCheckpoint
            .map((id) => BENCHMARK_LABEL[id] || id)
            .join(', '),
        }),
      );
      return;
    }
    let runOptions = null;
    if (hasRunOptions) {
      // BE 도 같은 경계를 강제하지만, 여기서 먼저 걸러 어느 칸이 틀렸는지 짚어 준다
      // (서버까지 갔다 오면 어느 필드인지 모르는 422 문구만 남는다).
      const built = buildRunOptions({
        strategy,
        generateModelLen,
        judgeModel,
        judgeModelLen,
        judgeMaxOutputTokens,
        withGenerate: withCheckpoint,
      });
      if (!built.ok) {
        errorToastMessage(
          null,
          t(`evaluation.bench.optErr.${built.errorKey}`, {
            min: built.min,
            max: built.max,
          }),
        );
        return;
      }
      runOptions = built.options;
    }
    onRun(
      selected.map((id) => ({ benchmark: id, metric: metricMap[id] })),
      withCheckpoint ? Number(commitId) : null,
      runOptions,
    );
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

              {/* 체크포인트 선택 — 실채점 벤치마크에서만 뜬다. 고르면 채점 컨테이너가 그
                  커밋 가중치를 올려 답변 생성부터 수행하고(생성 모드), 미지정이면 종전대로
                  데이터셋에 담긴 미채점 생성물을 채점한다. 두 모드는 소요가 크게 달라
                  설명 문구로 어느 쪽인지 항상 보이게 둔다. 벤치마크·메트릭과 달리 런 전체에
                  하나라서 벤치마크별 표(2단계)가 아니라 확인 단계에 놓는다. */}
              {hasRealBenchmark && (
                <div className={cx('checkpoint-box')}>
                  <div className={cx('checkpoint-head')}>
                    <span className={cx('checkpoint-title')}>
                      {t('evaluation.bench.checkpointTitle')}
                    </span>
                    <Selectbox
                      list={checkpointOptions}
                      selectedItem={selectedCheckpoint}
                      onChange={(item) => setCommitId(item.value)}
                      customStyle={{
                        selectboxForm: { width: '260px' },
                        listForm: { width: '260px' },
                      }}
                    />
                  </div>
                  <p className={cx('panel-desc')}>
                    {commitId === CHECKPOINT_NONE
                      ? t('evaluation.bench.checkpointNoneDesc')
                      : t('evaluation.bench.checkpointPickedDesc')}
                  </p>
                </div>
              )}

              {/* 실행 옵션 — 채점 컨테이너가 실제로 읽는 파라미터만 둔다
                  (evaluate_logickor_judge app.py 의 params.get). 숫자·문자 칸은 비우면
                  컨테이너 기본값이라, 기본값을 FE 가 복제하지 않고 placeholder 로만 알린다.
                  생성 옵션은 체크포인트를 골라 생성 모드로 갈 때만 효력이 있어 그때만 뜬다 —
                  채점 전용 런에 띄우면 눌러도 아무 일이 없는 칸이 된다. */}
              {hasRunOptions && (
                <div className={cx('checkpoint-box')}>
                  <div className={cx('checkpoint-head')}>
                    <span className={cx('checkpoint-title')}>
                      {t('evaluation.bench.runOptionsTitle')}
                    </span>
                  </div>
                  <p className={cx('panel-desc')}>
                    {t('evaluation.bench.runOptionsDesc')}
                  </p>

                  {commitId !== CHECKPOINT_NONE && (
                    <div className={cx('opt-grid')}>
                      <div className={cx('opt-field')}>
                        <span className={cx('opt-label')}>
                          {t('evaluation.bench.optStrategy')}
                        </span>
                        <Selectbox
                          list={strategyOptions}
                          selectedItem={selectedStrategy}
                          onChange={(item) => setStrategy(item.value)}
                          customStyle={{
                            selectboxForm: { width: '100%' },
                            listForm: { width: '100%' },
                          }}
                        />
                      </div>
                      <div className={cx('opt-field')}>
                        <span className={cx('opt-label')}>
                          {t('evaluation.bench.optGenModelLen')}
                        </span>
                        <InputText
                          size='medium'
                          value={generateModelLen}
                          placeholder={t('evaluation.bench.optGenModelLenPh', {
                            min: MODEL_LEN_MIN,
                            max: MODEL_LEN_MAX,
                          })}
                          onChange={(e) => setGenerateModelLen(e.target.value)}
                          customStyle={{ width: '100%' }}
                        />
                      </div>
                    </div>
                  )}

                  <div className={cx('opt-grid')}>
                    <div className={cx('opt-field')}>
                      <span className={cx('opt-label')}>
                        {t('evaluation.bench.optJudgeModel')}
                      </span>
                      <Selectbox
                        list={judgeModelOptions}
                        selectedItem={selectedJudgeModel}
                        onChange={(item) => setJudgeModel(item.value)}
                        customStyle={{
                          selectboxForm: { width: '100%' },
                          listForm: { width: '100%' },
                        }}
                      />
                    </div>
                    <div className={cx('opt-field')}>
                      <span className={cx('opt-label')}>
                        {t('evaluation.bench.optJudgeModelLen')}
                      </span>
                      <InputText
                        size='medium'
                        value={judgeModelLen}
                        placeholder={t('evaluation.bench.optJudgeModelLenPh', {
                          min: MODEL_LEN_MIN,
                          max: MODEL_LEN_MAX,
                        })}
                        onChange={(e) => setJudgeModelLen(e.target.value)}
                        customStyle={{ width: '100%' }}
                      />
                    </div>
                    <div className={cx('opt-field')}>
                      <span className={cx('opt-label')}>
                        {t('evaluation.bench.optJudgeMaxOut')}
                      </span>
                      <InputText
                        size='medium'
                        value={judgeMaxOutputTokens}
                        placeholder={t('evaluation.bench.optJudgeMaxOutPh', {
                          min: JUDGE_MAX_OUTPUT_MIN,
                          max: JUDGE_MAX_OUTPUT_MAX,
                        })}
                        onChange={(e) =>
                          setJudgeMaxOutputTokens(e.target.value)
                        }
                        customStyle={{ width: '100%' }}
                      />
                    </div>
                  </div>
                </div>
              )}

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
