import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import ContentBox from '@src/components/molecules/ContentBox';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { focusMetrics } from './batchSummary';
import { BENCHMARK_LABEL } from './benchmarks';
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
import { POLL_DEADLINE_MS, pollIntervalMs } from './resultPolling';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// 폴링 예산(경과 시간 기준)·간격(backoff)은 실행 요약 화면과 공용이다 — resultPolling.js.

// MixATIS 막대 순서 = 느슨 → 엄격. 의도만 / 항목 단위 부분점수 / 슬롯 쌍 / 둘 다 완전일치.
// 이 순서로 놓아야 "어디서부터 무너지는지"가 한눈에 읽힌다.
const MIXATIS_ORDER = ['intent_acc', 'intent_f1', 'slot_f1', 'joint_acc'];

// 벤치마크 종류와 무관하게 결과는 같은 4단으로 쌓는다:
//   ① 지표 카드(전 지표, 대표만 강조) → ② 그래프 → ③ 표 → ④ 채점 구성(provenance).
// 채우는 내용만 벤치마크 성격에 따라 갈린다. 골격을 고정하는 이유는, 벤치마크마다 다른
// 화면을 주면 "이 숫자가 저 숫자와 같은 자리인가"를 매번 다시 배워야 하기 때문이다.
// focusBenchmark — 한 런이 여러 벤치마크를 담을 때(묶음 실행이 GPU 수만큼 런을 나눈다, 설계 §14)
//   실행 요약에서 누른 벤치마크 하나만 보이게 좁힌다(batchSummary.focusMetrics). onShowAll 이 있으면
//   "런 전체 보기" 로 풀 수 있다. 결과 JSON 이 아직 없어도 채점기가 끝난 벤치마크의 점수를 중간
//   결과(progress.partial_metrics)로 남기므로, 도는 런·도중에 멈춘 런에서도 끝난 것은 보여 준다.
const BenchmarkResultView = ({
  modelId,
  jobId,
  onComplete,
  onMeta,
  focusBenchmark = null,
  onShowAll,
}) => {
  const { t } = useTranslation();
  // 런 전체의 결과 JSON(완료) 또는 중간 결과. 화면은 아래 results(좁힌 것)를 그린다.
  const [fullResults, setFullResults] = useState(null);
  // 중간 결과를 보이는 중인가 — 'running'(다른 벤치마크 채점 중) | 'stopped'(런이 도중에 멈춤).
  const [partialMode, setPartialMode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const completedRef = useRef(false);

  useEffect(() => {
    // effect 마다 제 상태를 둔다 — 공유 ref 를 쓰면 런 A → B 로 바뀔 때 A 의 늦은 응답이 되살아난
    // alive 를 보고 B 화면에 A 의 결과를 그린다(codex 리뷰, 실행 요약 화면과 같은 처방).
    const ref = { alive: true, timer: null };
    completedRef.current = false;
    setFullResults(null);
    setPartialMode(null);
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
        const partial = result.progress?.partial_metrics;
        const hasPartial =
          !!partial && Object.keys(partial.averages || {}).length > 0;
        if (result.status === 'failed' || result.status === 'cancelled') {
          setLoading(false);
          // 도중에 멈춘 런이라도 끝난 벤치마크 점수는 남아 있다 — 있으면 그것을 보인다.
          if (hasPartial) {
            setFullResults(partial);
            setPartialMode('stopped');
          } else {
            setFailed(true);
          }
          return;
        }
        if (result.ready) {
          setFullResults(result.metrics);
          setPartialMode(null);
          setLoading(false);
          if (!completedRef.current) {
            completedRef.current = true;
            onComplete?.();
          }
          return;
        }
        // 아직 도는 런 — 끝난 벤치마크가 있으면 먼저 보이고 폴링은 계속한다.
        if (hasPartial) {
          setFullResults(partial);
          setPartialMode('running');
          setLoading(false);
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

  // 화면이 그리는 결과 — 누른 벤치마크 하나로 좁힌다(그 벤치마크가 결과에 없으면 런 전체).
  const results = useMemo(
    () => focusMetrics(fullResults, focusBenchmark),
    [fullResults, focusBenchmark],
  );
  // 누른 벤치마크를 채점기가 실패로 기록했나(런의 나머지 벤치마크는 점수가 있다).
  const focusFailure = useMemo(
    () =>
      focusBenchmark
        ? (fullResults?.failed_benchmarks || []).find(
            (f) => f?.benchmark === focusBenchmark,
          ) || null
        : null,
    [fullResults, focusBenchmark],
  );
  // 누른 벤치마크의 점수가 결과에 있나. 없으면 좁힐 수 없다 — 같은 런의 다른 벤치마크 결과로
  // 채우면 "MMLU" 링크 아래 ARC 점수가 뜬다(codex 리뷰).
  const focusPresent = useMemo(
    () =>
      !!(
        focusBenchmark &&
        fullResults &&
        (focusBenchmark in (fullResults.averages || {}) ||
          focusBenchmark in (fullResults.lmeval?.benchmarks || {}))
      ),
    [fullResults, focusBenchmark],
  );
  // 이 런이 담은 벤치마크 수(채점된 것 + 실패한 것) — 좁혀 보는 중인지 알리는 줄에 쓴다.
  const runBenchmarkCount = useMemo(
    () =>
      new Set([
        ...Object.keys(fullResults?.averages || {}),
        ...(fullResults?.failed_benchmarks || []).map((f) => f?.benchmark),
      ]).size,
    [fullResults],
  );

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

  // lm-eval 상세 — 채점기(evaluate-lmeval)가 벤치마크마다 설정·전 지표·서브태스크를
  // metrics.lmeval.benchmarks[<id>] 에 실어 보낸다. 서브태스크를 results[] 에 넣지 않는 이유는
  // 결과 행 키가 `${benchmark}:${metric}` 라 겹치기 때문이다(채점기 scoring.py 주석).
  const lmeval = useMemo(() => {
    const detail = results?.lmeval;
    if (!detail || typeof detail.benchmarks !== 'object' || !detail.benchmarks)
      return null;
    const benchmarks = Object.entries(detail.benchmarks).map(([id, d]) => ({
      ...d,
      id,
      metrics: Array.isArray(d?.metrics) ? d.metrics : [],
      subtasks: Array.isArray(d?.subtasks) ? d.subtasks : [],
      warnings: Array.isArray(d?.warnings) ? d.warnings : [],
    }));
    return benchmarks.length ? { ...detail, benchmarks } : null;
  }, [results]);

  // lm-eval 원 지표명(acc·acc_norm·exact_match…) 표. 값은 채점기가 이미 0~100 으로 환산해
  // 싣는다(스케일 명시표) — 여기서는 다시 환산하지 않는다.
  const lmevalMetricColumns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colLmMetric'),
        selector: 'metric',
        sortable: false,
        cell: (row) =>
          row.filter && row.filter !== 'none'
            ? `${row.metric} · ${row.filter}`
            : row.metric,
      },
      {
        name: t('evaluation.bench.score'),
        selector: 'score',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{fmt2(row.score)}</span>
        ),
      },
      {
        name: t('evaluation.bench.colStderr'),
        selector: 'stderr',
        sortable: false,
        cell: (row) => (row.stderr == null ? '-' : `± ${fmt2(row.stderr)}`),
      },
    ],
    [t],
  );

  const lmevalSubtaskColumns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colTask'),
        selector: 'task',
        sortable: false,
        cell: (row) => row.task,
      },
      ...lmevalMetricColumns.slice(1),
    ],
    [t, lmevalMetricColumns],
  );

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
      // 문항 상한을 준 빠른 점검 — 분모가 달라 전체 측정과 나란히 비교하면 안 된다.
      quickLimit: results.lmeval?.limit ?? null,
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
    // LoRA 커밋은 채점기가 서빙 파드와 같은 방식으로 기반 가중치 위에 병합해 올린다 —
    // 점수가 "어댑터 단독"이 아니라 "기반 + 어댑터"의 값임을 밝힌다.
    if (results.checkpoint?.format === 'lora') {
      items.push({
        key: 'weights',
        label: t('evaluation.bench.provWeights'),
        value: t('evaluation.bench.provLoraMerged', {
          base: results.checkpoint.base || '-',
        }),
      });
    }
    if (lmeval) {
      items.push({
        key: 'engine',
        label: t('evaluation.bench.provEngine'),
        value: t('evaluation.bench.provEngineValue', {
          vllm: lmeval.vllm_version || '-',
          lmeval: lmeval.lm_eval_version || '-',
        }),
      });
      if (lmeval.limit != null) {
        items.push({
          key: 'limit',
          label: t('evaluation.bench.provSampleLimit'),
          value: t('evaluation.bench.quickCheck', { limit: lmeval.limit }),
          warn: true,
        });
      }
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
  }, [results, logickor, logickorScaleMax, mixatis, lmeval, t]);

  // 좁혀 보는 중 · 중간 결과 — 무엇을 보고 있는지 머리에 한 줄로 알린다.
  const focusBar =
    (focusPresent && runBenchmarkCount > 1) || partialMode ? (
      <div className={cx('focus-bar')}>
        {focusPresent && runBenchmarkCount > 1 && (
          <span>
            {t('evaluation.bench.focusNote', {
              count: runBenchmarkCount,
              benchmark: BENCHMARK_LABEL[focusBenchmark] || focusBenchmark,
            })}
            {onShowAll && (
              <button
                type='button'
                className={cx('batch-cell-link')}
                onClick={onShowAll}
              >
                {t('evaluation.bench.focusShowAll')}
              </button>
            )}
          </span>
        )}
        {partialMode && (
          <span className={cx(partialMode === 'stopped' && 'warn')}>
            {t(
              partialMode === 'stopped'
                ? 'evaluation.bench.partialStopped'
                : 'evaluation.bench.partialRunning',
            )}
          </span>
        )}
      </div>
    ) : null;

  // 누른 벤치마크가 아직(또는 끝내) 점수가 없다 — 중간 결과만 있는 런에서 다른 벤치마크 결과로
  // 채우지 않고 그 벤치마크의 처지를 말한다. 완료된 런에서 결과에 없는 id 면(잘못된 링크) 좁히지
  // 않고 런 전체를 보인다(focusMetrics 가 원본을 돌려준다).
  if (focusBenchmark && partialMode && !focusPresent && !focusFailure) {
    return (
      <div className={cx('benchmark-result')}>
        {focusBar}
        <section className={cx('result-section')}>
          <p className={cx('run-hint')}>
            {t(
              partialMode === 'stopped'
                ? 'evaluation.bench.focusStopped'
                : 'evaluation.bench.focusPending',
              {
                benchmark: BENCHMARK_LABEL[focusBenchmark] || focusBenchmark,
              },
            )}
          </p>
          {onShowAll && (
            <button
              type='button'
              className={cx('batch-cell-link')}
              onClick={onShowAll}
            >
              {t('evaluation.bench.focusShowAll')}
            </button>
          )}
        </section>
      </div>
    );
  }
  // 누른 벤치마크를 채점기가 실패로 기록 — 런의 다른 벤치마크 점수로 대신 채우지 않는다.
  if (focusFailure) {
    return (
      <div className={cx('benchmark-result')}>
        {focusBar}
        <section className={cx('result-section')}>
          <p className={cx('run-hint', 'err')}>
            {t('evaluation.bench.benchmarkFailed', {
              benchmark: BENCHMARK_LABEL[focusBenchmark] || focusBenchmark,
            })}
          </p>
          <p className={cx('focus-error')}>{focusFailure.error}</p>
        </section>
      </div>
    );
  }
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
      {focusBar}
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
            <ContentBox title={t('evaluation.bench.catChartTitle')}>
              <div className={cx('chart-body')}>
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
            </ContentBox>

            <ContentBox title={t('evaluation.bench.radarTitle')}>
              <div className={cx('chart-body')}>
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
            </ContentBox>
          </div>
        </section>
      ) : (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.resultChart')}
          </h3>
          <ContentBox>
            <div className={cx('chart-body', 'untitled')}>
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
          </ContentBox>
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

      {/* ③-b lm-eval 채점 상세 — 벤치마크마다 설정 요약 · 전 지표(원 지표명·표준오차) ·
          서브태스크(MMLU 57 · KMMLU 45 … 는 접어 둔다) · 경고. */}
      {lmeval && (
        <section className={cx('result-section')}>
          <div className={cx('result-section-head')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.bench.lmevalDetailTitle')}
            </h3>
            {lmeval.limit != null && (
              <Badge
                label={t('evaluation.bench.quickCheck', {
                  limit: lmeval.limit,
                })}
                type='yellow'
                size='sm'
              />
            )}
          </div>
          {lmeval.benchmarks.map((detail) => {
            const summary = [
              detail.tasks?.length > 0 && {
                key: 'tasks',
                label: t('evaluation.bench.lmevalTasks'),
                value: detail.tasks.join(', '),
              },
              detail.tasks?.length > 0 && {
                key: 'fewshot',
                label: t('evaluation.bench.lmevalFewshot'),
                value: String(detail.num_fewshot ?? 0),
              },
              detail.n != null && {
                key: 'n',
                label: t('evaluation.bench.lmevalItems'),
                value: String(detail.n),
              },
              detail.elapsed_sec != null && {
                key: 'elapsed',
                label: t('evaluation.bench.lmevalElapsed'),
                value: t('evaluation.bench.lmevalElapsedValue', {
                  minutes: (Number(detail.elapsed_sec) / 60).toFixed(1),
                }),
              },
              // custom — 런 데이터셋으로 생성·채점한 경우의 근거.
              detail.dataset && {
                key: 'dataset',
                label: t('evaluation.bench.customDataset'),
                value: detail.dataset,
              },
              detail.korean != null && {
                key: 'tokenize',
                label: t('evaluation.bench.customTokenize'),
                value: t(
                  detail.korean
                    ? 'evaluation.bench.customTokenizeKo'
                    : 'evaluation.bench.customTokenizeWs',
                ),
              },
              detail.id === 'custom' && {
                key: 'chat',
                label: t('evaluation.bench.customChatTemplate'),
                value: t(
                  detail.chat_template
                    ? 'evaluation.bench.customChatOn'
                    : 'evaluation.bench.customChatOff',
                ),
              },
              // 0 이 아니면 평균을 조용히 끌어내린 양이다 — 경고 톤으로 세운다.
              Number(detail.skipped_rows) > 0 && {
                key: 'skipped',
                label: t('evaluation.bench.customSkipped'),
                value: String(detail.skipped_rows),
                warn: true,
              },
              Number(detail.truncated_prompts) > 0 && {
                key: 'truncated',
                label: t('evaluation.bench.customTruncated'),
                value: String(detail.truncated_prompts),
                warn: true,
              },
              Number(detail.empty_predictions) > 0 && {
                key: 'empty',
                label: t('evaluation.bench.customEmpty'),
                value: String(detail.empty_predictions),
                warn: true,
              },
            ].filter(Boolean);
            return (
              <div key={detail.id} className={cx('lmeval-detail')}>
                <p className={cx('lmeval-detail-title')}>
                  {BENCHMARK_LABEL[detail.id] || detail.id}
                </p>
                <ul className={cx('provenance')}>
                  {summary.map((item) => (
                    <li
                      key={item.key}
                      className={cx('provenance-item', item.warn && 'warn')}
                    >
                      <span className={cx('provenance-label')}>
                        {item.label}
                      </span>
                      <span className={cx('provenance-value')}>
                        {item.value}
                      </span>
                    </li>
                  ))}
                </ul>
                {detail.metrics.length > 0 && (
                  <>
                    <p className={cx('lmeval-sub-title')}>
                      {t('evaluation.bench.lmevalMetricsTitle')}
                    </p>
                    <div className={cx('result-table')}>
                      <BorderTable
                        columns={lmevalMetricColumns}
                        data={detail.metrics.map((m) => ({
                          ...m,
                          id: `${m.metric}:${m.filter}`,
                        }))}
                        loading={false}
                        selectableRows={false}
                        hideSearchBox
                        hideButtons
                        fixedHeader
                        fixedHeaderScrollHeight='320px'
                      />
                    </div>
                  </>
                )}
                {detail.subtasks.length > 0 && (
                  <details className={cx('lmeval-subtasks')}>
                    <summary className={cx('lmeval-sub-title')}>
                      {t('evaluation.bench.lmevalSubtasksTitle', {
                        count: detail.subtasks.length,
                      })}
                    </summary>
                    <div className={cx('result-table')}>
                      <BorderTable
                        columns={lmevalSubtaskColumns}
                        data={detail.subtasks.map((s) => ({
                          ...s,
                          id: `${s.task}:${s.metric}:${s.filter}`,
                        }))}
                        loading={false}
                        selectableRows={false}
                        hideSearchBox
                        hideButtons
                        fixedHeader
                        fixedHeaderScrollHeight='360px'
                      />
                    </div>
                  </details>
                )}
                {detail.warnings.length > 0 && (
                  <ul className={cx('provenance')}>
                    {detail.warnings.map((w) => (
                      <li key={w} className={cx('provenance-item', 'warn')}>
                        <span className={cx('provenance-label')}>
                          {t('evaluation.bench.lmevalWarnings')}
                        </span>
                        <span className={cx('provenance-value')}>{w}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </section>
      )}

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
