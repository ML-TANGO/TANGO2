import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { BENCHMARK_LABEL, BENCHMARK_MAP } from './benchmarks';
import {
  barWidth,
  fmt,
  formatMetricValue,
  metricDesc,
  metricLabel,
  scaleMaxFor,
} from './benchmarkMetrics';
import LogicKorRadar from './LogicKorRadar';
import { diffText, diffTone, fmt2, judgeVerdict } from './logickorResult';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// 폴링 예산은 "시도 횟수"가 아니라 "경과 시간"으로 잡는다. 벤치마크 런은 채점기에 따라
// 소요가 두 자릿수 배 차이 난다 — mock 은 10초(evaluate_benchmark_mock)인데 LogicKor
// 실채점은 기동에만 240초, 생성+심판까지 3600초다(evaluate_logickor_judge manifest
// capabilities). 40회×3초=120초 고정 예산은 LogicKor 런이 기동을 마치기도 전에 끊겨서
// 성공한 런조차 화면에서는 늘 '대기 시간 초과'로 보였다.
// 간격은 초반 촘촘 → 후반 성글게(backoff) 둔다. mock 의 응답성은 그대로 두면서 장시간
// 런의 요청 수만 줄인다(4시간 완주 시 약 500회).
const POLL_DEADLINE_MS = 4 * 60 * 60 * 1000; // 컨테이너 timeout_seconds(14400) 와 정렬

const pollIntervalMs = (elapsedMs) => {
  if (elapsedMs < 60 * 1000) return 3000; // 첫 1분 — mock 완주·기동 실패를 즉시 반영
  if (elapsedMs < 5 * 60 * 1000) return 10 * 1000; // ~5분 — 실채점 컨테이너 기동 구간
  return 30 * 1000; // 이후 — 생성·심판 구간(수십 분)
};

// MixATIS 막대 순서 = 느슨 → 엄격. 의도만 / 항목 단위 부분점수 / 슬롯 쌍 / 둘 다 완전일치.
// 이 순서로 놓아야 "어디서부터 무너지는지"가 한눈에 읽힌다.
const MIXATIS_ORDER = ['intent_acc', 'intent_f1', 'slot_f1', 'joint_acc'];

// 벤치마크 종류와 무관하게 결과는 같은 4단으로 쌓는다:
//   ① 지표 카드(전 지표, 대표만 강조) → ② 그래프 → ③ 표 → ④ 채점 구성(provenance).
// 채우는 내용만 벤치마크 성격에 따라 갈린다. 골격을 고정하는 이유는, 벤치마크마다 다른
// 화면을 주면 "이 숫자가 저 숫자와 같은 자리인가"를 매번 다시 배워야 하기 때문이다.
const BenchmarkResultView = ({ modelId, jobId, onComplete, onMeta }) => {
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

    const startedAt = Date.now();
    const poll = () => {
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
        const elapsed = Date.now() - startedAt;
        if (elapsed >= POLL_DEADLINE_MS) {
          setLoading(false);
          errorToastMessage(null, t('evaluation.poll.timeout'));
          return;
        }
        ref.timer = setTimeout(poll, pollIntervalMs(elapsed));
      });
    };
    poll();

    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
  }, [modelId, jobId, t, onComplete]);

  // LogicKor 상세 — 영역(6) × 턴(2) 격자. 벤치마크 계약(results[])은 대표 스칼라 1개만
  // 담으므로, 영역별 강약점은 채점기가 metrics JSON 의 'logickor' 키에 따로 실어 보낸다.
  const logickor = useMemo(() => {
    const detail = results?.logickor;
    if (
      !detail ||
      !Array.isArray(detail.categories) ||
      !detail.categories.length
    ) {
      return null;
    }
    return detail;
  }, [results]);

  const logickorScaleMax = logickor?.scale_max || 10;

  // MixATIS 상세 — 의도·슬롯이 서로 다른 단위(발화 / 항목 / 쌍)로 채점되므로 대표
  // 스칼라(joint_acc) 하나로는 "의도는 되는데 슬롯이 안 되는" 상태를 구분할 수 없다.
  const mixatis = useMemo(() => {
    const detail = results?.mixatis;
    if (!detail || typeof detail.joint_acc !== 'number') return null;
    return detail;
  }, [results]);

  // 이 런이 잰 벤치마크 **전부**. 실채점은 상세 키가 곧 신원이고, 표준은 결과 행이 들고
  // 있다 — 그 행이 여러 벤치마크일 수 있으므로(API·레거시 런) 첫 행만 보면 제목과 본문이
  // 어긋난다. 점수 카드·표가 results.results 를 전부 순회하는 것과 축을 맞춘다.
  const benchmarkIds = useMemo(() => {
    if (logickor) return ['logickor'];
    if (mixatis) return ['mixatis'];
    const rows = Array.isArray(results?.results) ? results.results : [];
    return [...new Set(rows.map((row) => row.benchmark).filter(Boolean))];
  }, [logickor, mixatis, results]);

  // 상위(페이지 헤더)가 제목·배지에 쓸 메타. 결과가 도착해야 알 수 있는 값이라 콜백으로 올린다.
  useEffect(() => {
    if (!results) return;
    onMeta?.({
      // 대표 하나(옛 계약 유지) + 제목용 전체 라벨.
      benchmarkId: benchmarkIds[0] ?? null,
      benchmarkLabel:
        benchmarkIds.map((id) => BENCHMARK_LABEL[id] || id).join(' · ') || null,
      // 섞인 런에 '실채점' 배지가 붙으면 mock 점수까지 실채점으로 읽힌다 — 전부일 때만.
      real:
        benchmarkIds.length > 0 &&
        benchmarkIds.every((id) => !!BENCHMARK_MAP[id]?.real),
      mock: !!results.mock,
      manifestName: results._meta?.name || null,
    });
  }, [results, benchmarkIds, onMeta]);

  // ① 지표 카드 — 이 런이 기록한 전 지표. 대표(권장)만 강조한다.
  //    실채점 두 종은 채점기가 상세 키에 전 지표를 실어 보내므로 거기서 뽑고,
  //    표준(mock)은 벤치마크→대표 스칼라 한 줄씩이라 결과 행이 그대로 카드가 된다.
  const metricCards = useMemo(() => {
    if (!results) return [];
    if (logickor) {
      return [
        {
          key: 'judge_single',
          id: 'judge_single',
          metric: 'judge_single',
          label: t('evaluation.bench.turnSingle'),
          value: logickor.single_turn,
          tone: 'turn-single',
        },
        {
          key: 'judge_multi',
          id: 'judge_multi',
          metric: 'judge_multi',
          label: t('evaluation.bench.turnMulti'),
          value: logickor.multi_turn,
          tone: 'turn-multi',
        },
        {
          key: 'judge_overall',
          id: 'judge_overall',
          metric: 'judge_overall',
          label: t('evaluation.bench.turnOverall'),
          value: logickor.overall,
          accent: true,
        },
      ];
    }
    if (mixatis) {
      const value = {
        intent_acc: mixatis.intent?.acc,
        intent_f1: mixatis.intent?.f1,
        slot_f1: mixatis.slot?.f1,
        joint_acc: mixatis.joint_acc,
      };
      return MIXATIS_ORDER.map((metric) => ({
        key: metric,
        id: metric,
        metric,
        label: metricLabel(t, metric) || metric,
        value: value[metric],
        accent: metric === 'joint_acc',
      }));
    }
    if (Array.isArray(results.results) && results.results.length) {
      const single = results.results.length === 1;
      return results.results.map((row) => ({
        key: `${row.benchmark}:${row.metric}`,
        id: `${row.benchmark}:${row.metric}`,
        metric: row.metric,
        label: BENCHMARK_LABEL[row.benchmark] || row.benchmark,
        sub: metricLabel(t, row.metric) || row.metric,
        value: row.score,
        accent: single,
      }));
    }
    // 구 실행 결과 — averages(키별 점수) + metric_map 폴백.
    const averages = results.averages || {};
    const metricMap = results.metric_map || {};
    return Object.keys(averages).map((key) => ({
      key,
      id: key,
      metric: metricMap[key] || key,
      label: BENCHMARK_LABEL[key] || metricLabel(t, key) || key,
      sub: metricMap[key] ? metricLabel(t, metricMap[key]) : null,
      value: averages[key],
    }));
  }, [results, logickor, mixatis, t]);

  // ③ 표 — LogicKor 영역 행 + 종합 행 1개. 소스 콘솔도 tbody 마지막에 종합을 덧붙여
  //    영역과 전체를 한 표에서 비교하게 한다. isTotal 로 셀 렌더러가 구분한다.
  const logickorRows = useMemo(() => {
    if (!logickor) return [];
    return [
      ...logickor.categories,
      {
        category: t('evaluation.bench.totalRow'),
        single: logickor.single_turn,
        multi: logickor.multi_turn,
        overall: logickor.overall,
        isTotal: true,
      },
    ];
  }, [logickor, t]);

  const logickorColumns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colCategory'),
        selector: 'category',
        sortable: false,
        cell: (row) => (
          <span className={cx(row.isTotal ? 'total-label' : 'table-label')}>
            {row.category}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.turnSingle'),
        selector: 'single',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score', 'turn-single')}>
            {fmt2(row.single)}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.turnMulti'),
        selector: 'multi',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score', 'turn-multi')}>
            {fmt2(row.multi)}
          </span>
        ),
      },
      {
        // 2턴 − 1턴. 후속 질문에서 무너지는지(음수) 버티는지(양수)가 이 벤치마크의 관전
        // 지점이라 소스도 별 열로 뽑아 부호째 보여준다.
        name: t('evaluation.bench.colDiff'),
        selector: 'diff',
        sortable: false,
        cell: (row) => (
          <span className={cx('diff-value', diffTone(row.multi, row.single))}>
            {diffText(row.multi, row.single)}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.colVerdict'),
        selector: 'verdict',
        sortable: false,
        cell: (row) => {
          // 종합 행은 등급이 아니라 대표 스칼라 그 자체 — 배지로 감싸면 영역 등급과
          // 같은 종류로 읽히므로 숫자만 놓는다.
          if (row.isTotal) {
            return (
              <span className={cx('table-score')}>{fmt2(row.overall)}</span>
            );
          }
          const verdict = judgeVerdict(
            (Number(row.single) + Number(row.multi)) / 2,
          );
          if (!verdict) return '-';
          return (
            <Badge
              label={t(`evaluation.bench.verdict.${verdict.key}`)}
              type={verdict.badge}
              size='sm'
            />
          );
        },
      },
    ],
    [t],
  );

  // MixATIS 표 — F1 만 보면 정밀도와 재현율 중 어느 쪽이 무너졌는지 알 수 없어 함께 둔다.
  const mixatisRows = useMemo(() => {
    if (!mixatis) return [];
    return [
      {
        key: 'intent',
        id: 'intent',
        axis: t('evaluation.bench.axisIntent'),
        ...(mixatis.intent || {}),
      },
      {
        key: 'slot',
        id: 'slot',
        axis: t('evaluation.bench.axisSlot'),
        ...(mixatis.slot || {}),
      },
    ];
  }, [mixatis, t]);

  const mixatisColumns = useMemo(() => {
    const ratio = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-';
    };
    return [
      {
        name: t('evaluation.bench.colAxis'),
        selector: 'axis',
        sortable: false,
        cell: (row) => <span className={cx('table-label')}>{row.axis}</span>,
      },
      {
        name: 'Precision',
        selector: 'precision',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{ratio(row.precision)}</span>
        ),
      },
      {
        name: 'Recall',
        selector: 'recall',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{ratio(row.recall)}</span>
        ),
      },
      {
        name: 'F1',
        selector: 'f1',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{ratio(row.f1)}</span>
        ),
      },
    ];
  }, [t]);

  // 표준 표 — 지표 · 값 · 척도 · 정의. 척도를 열로 세우는 이유는 값이 척도별로 다르게
  // 읽히기 때문이다(0~1 비율, 1~10 심판 점수, 0~100 정답률).
  const metricColumns = useMemo(
    () => [
      {
        name: t('evaluation.metric'),
        selector: 'label',
        sortable: false,
        // 표준 런은 한 행이 (벤치마크, 지표) 쌍이다 — 여러 벤치마크를 한 런에 돌린 옛
        // 결과에서 지표명만 세우면 어느 벤치마크의 값인지 사라진다.
        cell: (row) => (
          <span className={cx('metric-cell')}>
            <span className={cx(row.accent ? 'total-label' : 'table-label')}>
              {row.sub
                ? `${row.label} · ${row.sub}`
                : metricLabel(t, row.metric) || row.metric}
            </span>
            {row.accent && (
              <Badge
                label={t('evaluation.bench.representative')}
                type='blue'
                size='sm'
              />
            )}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.score'),
        selector: 'value',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>
            {formatMetricValue(row.metric, row.value)}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.colScale'),
        selector: 'scale',
        sortable: false,
        cell: (row) => `0 – ${scaleMaxFor(row.metric)}`,
      },
      {
        name: t('evaluation.bench.colDefinition'),
        selector: 'definition',
        sortable: false,
        cell: (row) => metricDesc(t, row.metric) || '-',
      },
    ],
    [t],
  );

  // ④ 채점 구성 — "이 점수가 어느 체크포인트·어느 심판·어느 컨테이너에서 나왔나".
  // 채점 컨테이너가 metrics 에 새겨 보내는 값을 그대로 읽는다. 대표 스칼라 하나만 놓고
  // 런끼리 비교하면 무엇을 비교한 건지 알 수 없어서, 점수 옆에 근거를 같이 세운다.
  // ⚠️ checkpoint.path 는 NFS 실경로라 화면에 올리지 않는다.
  // unscored/skipped/empty_rows/형식 이탈은 0 이 아니면 평균을 조용히 끌어내린 양이라
  // 경고 톤으로 세운다(컨테이너도 같은 이유로 이 값들을 metrics 에 남긴다).
  const provenance = useMemo(() => {
    if (!results) return [];
    const items = [];
    if (results.checkpoint?.name) {
      items.push({
        key: 'checkpoint',
        label: t('evaluation.bench.provCheckpoint'),
        value: results.checkpoint.name,
      });
    }
    const judge = results.judge || {};
    if (judge.model) {
      items.push({
        key: 'judge',
        label: t('evaluation.bench.provJudge'),
        value: judge.model,
      });
    }
    if (Number.isFinite(Number(judge.judged))) {
      items.push({
        key: 'judged',
        label: t('evaluation.bench.provJudged'),
        value: String(judge.judged),
      });
    }
    if (Number(judge.unscored) > 0) {
      items.push({
        key: 'unscored',
        label: t('evaluation.bench.provUnscored'),
        value: String(judge.unscored),
        warn: true,
      });
    }
    if (Number(judge.skipped) > 0) {
      items.push({
        key: 'skipped',
        label: t('evaluation.bench.provSkipped'),
        value: String(judge.skipped),
        warn: true,
      });
    }
    if (Number(results.generate?.empty_rows) > 0) {
      items.push({
        key: 'empty_rows',
        label: t('evaluation.bench.provEmptyRows'),
        value: String(results.generate.empty_rows),
        warn: true,
      });
    }
    if (mixatis) {
      // MixATIS 0.2.0 부터 채점기가 평가 전에 UGEN 형식을 학습한다 — 점수는 "체크포인트
      // 단독"이 아니라 "체크포인트 + 그 레시피"의 값이다.
      const train = results.train || {};
      items.push({
        key: 'train',
        label: t('evaluation.bench.mixTrainLabel'),
        value: train.trained
          ? t('evaluation.bench.mixTrainOn', {
              examples: train.examples,
              epochs: train.epochs,
            })
          : t('evaluation.bench.mixTrainOff'),
        warn: !train.trained,
      });
      const evaluate = results.evaluate || {};
      const empty =
        (evaluate.empty_slot_predictions || 0) +
        (evaluate.empty_intent_predictions || 0);
      if (empty > 0) {
        items.push({
          key: 'empty',
          label: t('evaluation.bench.mixEmptyLabel'),
          value: t('evaluation.bench.mixEmptyValue', { count: empty }),
          warn: true,
        });
      }
    }
    if (logickor?.count != null) {
      items.push({
        key: 'count',
        label: t('evaluation.bench.provItems'),
        value: t('evaluation.bench.logickorMeta', {
          count: logickor.count,
          max: fmt(logickorScaleMax),
        }),
      });
    }
    if (mixatis?.count != null) {
      items.push({
        key: 'mixcount',
        label: t('evaluation.bench.provItems'),
        value: t('evaluation.bench.mixatisMeta', { count: mixatis.count }),
      });
    }
    if (results._meta?.name) {
      items.push({
        key: 'container',
        label: t('evaluation.bench.provContainer'),
        value: results._meta.name,
      });
    }
    // mock 은 해시 기반 점수다 — 실채점과 같은 표에 실리므로 반드시 표식이 필요하다.
    if (results.mock) {
      items.push({
        key: 'mock',
        label: t('evaluation.bench.provScoring'),
        value: t('evaluation.bench.provMock'),
        warn: true,
      });
    }
    return items;
  }, [results, logickor, logickorScaleMax, mixatis, t]);

  if (failed) {
    return (
      <div className={cx('benchmark-result')}>
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
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.running')}</span>
        </div>
      </div>
    );
  }
  if (!results || metricCards.length === 0) {
    return (
      <div className={cx('benchmark-result')}>
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
      {/* ① 지표 카드 — 전 지표, 대표만 강조 */}
      <section className={cx('result-section')}>
        <div className={cx('result-section-head')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.metric')}
          </h3>
          <Badge
            label={t('evaluation.bench.recordedCount', {
              count: metricCards.length,
            })}
            type='gray'
            size='sm'
          />
        </div>
        <div className={cx('score-grid')}>
          {metricCards.map((card) => (
            <div
              key={card.key}
              className={cx('score-card', card.accent && 'accent')}
            >
              <div className={cx('score-metric')}>{card.label}</div>
              <div className={cx('score-value', card.tone)}>
                {formatMetricValue(card.metric, card.value)}
              </div>
              <div className={cx('score-unit')}>
                {card.accent
                  ? t('evaluation.bench.representative')
                  : card.sub || metricDesc(t, card.metric)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ② 그래프 */}
      {logickor ? (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.logickorTitle')}
          </h3>
          <div className={cx('logickor-charts')}>
            <div className={cx('chart-wrap')}>
              <h4 className={cx('chart-subtitle')}>
                {t('evaluation.bench.catChartTitle')}
              </h4>
              <div className={cx('cat-rows')}>
                {logickor.categories.map((row) => (
                  <div key={row.category} className={cx('cat-row')}>
                    <div className={cx('cat-name')}>{row.category}</div>
                    {[
                      ['single', row.single],
                      ['multi', row.multi],
                    ].map(([turn, score]) => (
                      <div key={turn} className={cx('cat-track')}>
                        <span className={cx('cat-tag')}>
                          {turn === 'single' ? 'S' : 'M'}
                        </span>
                        <div className={cx('cat-rail')}>
                          <div
                            className={cx('cat-fill', turn)}
                            style={{
                              width: `${barWidth(score, logickorScaleMax)}%`,
                            }}
                          />
                        </div>
                        <span className={cx('cat-value', `turn-${turn}`)}>
                          {fmt2(score)}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className={cx('chart-wrap')}>
              <h4 className={cx('chart-subtitle')}>
                {t('evaluation.bench.radarTitle')}
              </h4>
              <div className={cx('radar-wrap')}>
                <LogicKorRadar
                  categories={logickor.categories}
                  scaleMax={logickorScaleMax}
                />
                <div className={cx('radar-legend')}>
                  <span className={cx('radar-legend-item')}>
                    <i className={cx('radar-swatch', 'single')} />
                    {t('evaluation.bench.turnSingle')}
                  </span>
                  <span className={cx('radar-legend-item')}>
                    <i className={cx('radar-swatch', 'multi')} />
                    {t('evaluation.bench.turnMulti')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.resultChart')}
          </h3>
          <div className={cx('chart-wrap')}>
            {metricCards.map((card) => (
              <div key={card.key} className={cx('chart-row')}>
                <div className={cx('chart-label')}>{card.label}</div>
                <div className={cx('chart-bar-wrap')}>
                  <div
                    className={cx('chart-bar')}
                    style={{
                      width: `${barWidth(card.value, scaleMaxFor(card.metric))}%`,
                    }}
                  />
                </div>
                <div className={cx('chart-value')}>
                  {formatMetricValue(card.metric, card.value)}
                </div>
              </div>
            ))}
          </div>
          <p className={cx('note-line')}>
            {mixatis
              ? t('evaluation.bench.mixChartNote')
              : t('evaluation.bench.metricChartNote')}
          </p>
        </section>
      )}

      {/* ③ 표 */}
      <section className={cx('result-section')}>
        <h3 className={cx('result-section-title')}>
          {logickor
            ? t('evaluation.bench.catTableTitle')
            : mixatis
              ? t('evaluation.bench.mixTableTitle')
              : t('evaluation.bench.metricTableTitle')}
        </h3>
        <div className={cx('result-table')}>
          {/* 행 수가 고정(영역 6+종합 / 축 2 / 지표 몇 개)이라 페이지네이션이 의미가 없다.
              BorderTable 은 pagination={!fixedHeader} 이므로 fixedHeader 로 페이저를 끈다. */}
          <BorderTable
            columns={
              logickor
                ? logickorColumns
                : mixatis
                  ? mixatisColumns
                  : metricColumns
            }
            data={logickor ? logickorRows : mixatis ? mixatisRows : metricCards}
            loading={false}
            selectableRows={false}
            hideSearchBox
            hideButtons
            fixedHeader
            fixedHeaderScrollHeight='420px'
          />
        </div>
        {mixatis && (
          <p className={cx('note-line')}>
            {t('evaluation.bench.mixTableNote')}
          </p>
        )}
      </section>

      {/* ④ 채점 구성 */}
      {provenance.length > 0 && (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.provenanceTitle')}
          </h3>
          <ul className={cx('provenance')}>
            {provenance.map((item) => (
              <li
                key={item.key}
                className={cx('provenance-item', item.warn && 'warn')}
              >
                <span className={cx('provenance-label')}>{item.label}</span>
                <span className={cx('provenance-value')}>{item.value}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default BenchmarkResultView;
