// 교차모델 비교 행렬 파생 — BE `/evaluations/compare` 의 `{ models, metric_keys, best, runs }`
// 를 "행=지표 · 열=모델" 로 뒤집는 순수 계산부. 화면(EvalCrossCompare)은 여기서 나온 shape 만
// 그린다.
//
// 행 제목·부제에 지표 이름이 들어가고 그 이름은 로케일을 타므로, 라벨을 만드는 함수는
// `t` 를 인자로 받는다(모듈이 i18n 인스턴스를 직접 잡지 않는다 — 그래야 이 파일이
// 렌더 밖에서도 그대로 쓰인다). 호출하는 memo 는 `t` 를 의존성에 넣어야 한다.
//
// ⚠️ BE 의 `best` 는 **모델 무관 전역 best**(지표별 run id 하나)다. 행렬이 필요로 하는
// "모델별 best" 는 BE 가 주지 않으므로 여기서 runs 를 model_id 로 그룹핑해 직접 뽑는다.

import { BENCHMARK_LABEL } from '../BenchmarkEvaluation/benchmarks';
import {
  METRIC_MAP,
  metricLabel,
  scaleMaxFor,
} from '../BenchmarkEvaluation/benchmarkMetrics';

// 모델 열 색상 슬롯 수 — scss 의 .sw-0 ~ .sw-5 와 개수를 맞춘다(MAX_MODELS 와 동수).
export const SWATCH_COUNT = 6;

// 낮을수록 좋은 지표. BE fb_utils/llm_db/db_model.py `_EVAL_METRIC_DIRECTION` 의 사본인데,
// 그 표에서 "min" 인 항목은 perplexity 하나뿐이고 나머지(bleu·rouge·f1·accuracy…)는 전부
// 기본값 "max" 와 같다. 미등록 키도 BE 와 동일하게 max 로 떨어진다.
const MIN_DIRECTION_KEYS = new Set(['perplexity']);

export const directionOf = (metricKey) =>
  MIN_DIRECTION_KEYS.has(String(metricKey).toLowerCase()) ? 'min' : 'max';

// 실행 상태 → 조나단 Badge type (EvalComparison 과 같은 매핑). 모델 축·런 축 두 화면이
// 같은 상태 표를 쓰므로 여기에 둔다(화면끼리 import 하면 순환 참조가 된다).
export const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};

// 전문가 평가 키는 카탈로그에 없어 i18n 라벨로 간다(EvalComparison 과 같은 매핑).
export const EXPERT_METRIC_LABEL_KEYS = {
  expert_avg_score: 'evaluate.metric.expertAvgScore',
  expert_pass_rate: 'evaluate.metric.expertPassRate',
};

/**
 * 런의 지표 id 를 되짚는다.
 * 벤치마크 런의 metric_key 는 벤치마크 id(`logickor`)로 와서 척도·라벨을 갖고 있지 않다.
 * 실제 채점 축은 `metric_set`("logickor:judge_overall")의 뒷부분에 있으므로 그걸 쓴다.
 * self-metric(`bleu`)처럼 키 자체가 지표 id 면 그대로 쓰고, 어느 쪽도 아니면 null.
 */
export const metricIdOf = (run, metricKey) => {
  const set = typeof run?.metric_set === 'string' ? run.metric_set : '';
  const suffix = set.includes(':') ? set.slice(set.indexOf(':') + 1) : set;
  if (suffix && METRIC_MAP[suffix]) return suffix;
  return METRIC_MAP[metricKey] ? metricKey : null;
};

// 행 척도 배지. 표시는 원 척도로 두므로(단위 통일 X) 이 배지가 "가로로만 비교하라"는 표식이다.
// 비율 지표(scaleMax 1)는 화면에 % 로 찍히니 배지도 % 로 읽어야 자기모순이 없다.
export const scaleLabelOf = (metricId) => {
  const max = scaleMaxFor(metricId);
  return max === 1 ? '0 – 100%' : `0 – ${max}`;
};

// 행 최고 대비 차이 — **표시 척도 그대로** 낸다(비율 지표는 %p). 부호를 붙여 최고보다
// 낮은지 높은지 그대로 읽히게 한다(perplexity 처럼 낮을수록 좋은 지표는 +가 열위).
export const deltaLabelOf = (metricId, value, rowBest) => {
  if (!Number.isFinite(value) || !Number.isFinite(rowBest)) return null;
  const raw = value - rowBest;
  const scaled = scaleMaxFor(metricId) === 1 ? raw * 100 : raw;
  if (scaled === 0) return null;
  return `${scaled > 0 ? '+' : ''}${scaled.toFixed(2)}`;
};

// 막대 길이는 **그 행의 최고점 기준**으로만 정규화한다(척도가 행마다 달라 세로 비교는 무의미).
export const barPercentOf = (value, rowBest, direction) => {
  if (!Number.isFinite(value) || !Number.isFinite(rowBest)) return 0;
  const ratio =
    direction === 'min'
      ? value > 0 && rowBest > 0
        ? rowBest / value
        : 0
      : rowBest > 0
        ? value / rowBest
        : 0;
  return Math.max(0, Math.min(100, ratio * 100));
};

const isScored = (run, metricKey) => {
  const v = run?.metrics?.[metricKey];
  return typeof v === 'number' && Number.isFinite(v);
};

const pickBetter = (a, b, direction) =>
  direction === 'min' ? Math.min(a, b) : Math.max(a, b);

/**
 * `{ models, metric_keys, runs }` → `{ models, rows }`.
 *
 * rows[i] = {
 *   key, metricId, title, subLabel, scaleLabel, direction, rowBest,
 *   cells: { [modelId]: { run, value, isBest, delta, barPercent } | null },
 *   runs: [...]            // 이 지표에 기여한 전 런(펼침용)
 * }
 *
 * 셀은 그 모델의 **최고 런**이며 후보는 completed 로 한정한다 — BE 가 전역 best 를 고르는
 * 기준과 같게 두어야 같은 데이터에서 두 화면이 다른 승자를 말하지 않는다.
 */
export const buildMatrix = (comparison, t) => {
  const models = Array.isArray(comparison?.models) ? comparison.models : [];
  const metricKeys = Array.isArray(comparison?.metric_keys)
    ? comparison.metric_keys
    : [];
  const allRuns = Array.isArray(comparison?.runs) ? comparison.runs : [];
  const modelOrder = new Map(models.map((m, i) => [m.id, i]));

  const rows = metricKeys.map((key) => {
    const direction = directionOf(key);
    const contributing = allRuns.filter((r) => isScored(r, key));

    // 모델별 최고 런(completed 한정). 동점이면 먼저 온 런을 유지한다 —
    // BE 가 runs 를 최신순으로 주므로 최신 런이 남는다.
    const bestByModel = new Map();
    contributing.forEach((run) => {
      if (run.status !== 'completed') return;
      const prev = bestByModel.get(run.model_id);
      if (!prev) {
        bestByModel.set(run.model_id, run);
        return;
      }
      const value = run.metrics[key];
      const prevValue = prev.metrics[key];
      const better =
        direction === 'min' ? value < prevValue : value > prevValue;
      if (better) bestByModel.set(run.model_id, run);
    });

    const metricId = metricIdOf(
      bestByModel.values().next().value || contributing[0],
      key,
    );

    const cellValues = [...bestByModel.values()].map((r) => r.metrics[key]);
    const rowBest = cellValues.length
      ? cellValues.reduce((acc, v) => pickBetter(acc, v, direction))
      : null;

    const cells = {};
    models.forEach((m) => {
      const run = bestByModel.get(m.id);
      if (!run) {
        cells[m.id] = null;
        return;
      }
      const value = run.metrics[key];
      cells[m.id] = {
        run,
        value,
        isBest: value === rowBest,
        delta:
          value === rowBest ? null : deltaLabelOf(metricId, value, rowBest),
        barPercent: barPercentOf(value, rowBest, direction),
      };
    });

    // 펼침 목록 — 모델 열 순서로 묶고, 같은 모델 안에서는 우수한 점수부터.
    const drawerRuns = [...contributing].sort((a, b) => {
      const oa = modelOrder.has(a.model_id)
        ? modelOrder.get(a.model_id)
        : Number.MAX_SAFE_INTEGER;
      const ob = modelOrder.has(b.model_id)
        ? modelOrder.get(b.model_id)
        : Number.MAX_SAFE_INTEGER;
      if (oa !== ob) return oa - ob;
      const va = a.metrics[key];
      const vb = b.metrics[key];
      return direction === 'min' ? va - vb : vb - va;
    });

    return {
      key,
      metricId,
      title: BENCHMARK_LABEL[key] || metricLabel(t, key) || key,
      // 벤치마크 행만 부제(채점 축)를 갖는다 — self-metric 은 제목이 곧 지표라 중복이 된다.
      subLabel: metricId && metricId !== key ? metricLabel(t, metricId) : null,
      scaleLabel: scaleLabelOf(metricId),
      direction,
      rowBest,
      cells,
      runs: drawerRuns,
    };
  });

  return { models, rows };
};

// ── 런 축(열=런) ─────────────────────────────────────────────────────────
// P1. 사용자가 **런을 지목**해 비교한다("모델 A 의 ckpt3 vs 모델 B 의 ckpt1"). 열 하나가
// 런 하나라 모델 축이 하던 "모델별 best 뽑기"가 여기선 필요 없다 — 그 런의 값을 그대로
// 쓴다. 행 best·delta·막대 정규화 규칙은 모델 축과 같다(가로로만 비교 가능).

/**
 * `metric_set`("logickor:judge_overall") 을 벤치마크 키와 채점 지표 id 로 쪼갠다.
 * 벤치마크 런의 `metrics` 는 벤치마크 키(`logickor`)로 값을 담고, 척도·라벨은 뒷부분
 * (`judge_overall`)이 갖는다. 콜론이 없으면 self-metric(`bleu`) 이라 양쪽이 같은 값이다.
 */
export const metricSetParts = (run) => {
  const set = typeof run?.metric_set === 'string' ? run.metric_set : '';
  const i = set.indexOf(':');
  const head = i < 0 ? set : set.slice(0, i);
  const tail = i < 0 ? set : set.slice(i + 1);
  return {
    benchmarkKey: head || null,
    metricId: tail && METRIC_MAP[tail] ? tail : null,
  };
};

/**
 * 후보 목록에 찍을 대표 점수 — 그 런이 실제로 잰 축 하나. `metric_set` 이 가리키는 키를
 * 우선 보고, 없으면 `metrics` 의 첫 유한값으로 떨어진다(계약 밖 런도 목록에선 읽혀야 한다).
 * 점수가 없으면 null → 화면은 `-`.
 */
export const primaryScoreOf = (run) => {
  const metrics =
    run?.metrics && typeof run.metrics === 'object' ? run.metrics : {};
  const { benchmarkKey, metricId } = metricSetParts(run);
  const direct = benchmarkKey == null ? undefined : metrics[benchmarkKey];
  if (Number.isFinite(direct)) {
    return {
      key: benchmarkKey,
      metricId: metricId || (METRIC_MAP[benchmarkKey] ? benchmarkKey : null),
      value: direct,
    };
  }
  const entry = Object.entries(metrics).find(([, v]) => Number.isFinite(v));
  if (!entry) return null;
  return {
    key: entry[0],
    metricId: METRIC_MAP[entry[0]] ? entry[0] : metricId,
    value: entry[1],
  };
};

// 후보 목록의 "무슨 벤치마크였나" 열. 날짜만으로는 런을 구분할 수 없어서 반드시 필요하다.
export const benchmarkLabelOf = (run, t) => {
  const { benchmarkKey } = metricSetParts(run);
  if (!benchmarkKey) return '-';
  return (
    BENCHMARK_LABEL[benchmarkKey] ||
    metricLabel(t, benchmarkKey) ||
    benchmarkKey
  );
};

/**
 * `{ runs, metric_keys }` → `{ runs, rows }`.
 *
 * rows[i] = {
 *   key, metricId, title, subLabel, scaleLabel, direction, rowBest,
 *   cells: { [runId]: { run, value, isBest, delta, barPercent } | null },
 * }
 *
 * 셀이 null 이면 "그 런이 그 지표를 안 쟀다" — 모델 축의 '미실행' 과 달리 런을 지목한
 * 결과라 화면은 `-` 로 둔다. `runs` 순서가 곧 열 순서다(BE 가 준 순서를 지킨다).
 */
export const buildRunMatrix = (comparison, t) => {
  const runs = Array.isArray(comparison?.runs) ? comparison.runs : [];
  const metricKeys = Array.isArray(comparison?.metric_keys)
    ? comparison.metric_keys
    : [];

  const rows = metricKeys.map((key) => {
    const direction = directionOf(key);
    const scored = runs.filter((r) => isScored(r, key));
    // 척도·라벨은 그 지표를 실제로 잰 런에서 되짚는다(안 잰 런엔 metric_set 이 없다).
    const metricId = metricIdOf(scored[0], key);

    const rowBest = scored.length
      ? scored
          .map((r) => r.metrics[key])
          .reduce((acc, v) => pickBetter(acc, v, direction))
      : null;

    const cells = {};
    runs.forEach((run) => {
      if (!isScored(run, key)) {
        cells[run.id] = null;
        return;
      }
      const value = run.metrics[key];
      cells[run.id] = {
        run,
        value,
        isBest: value === rowBest,
        delta:
          value === rowBest ? null : deltaLabelOf(metricId, value, rowBest),
        barPercent: barPercentOf(value, rowBest, direction),
      };
    });

    return {
      key,
      metricId,
      title: BENCHMARK_LABEL[key] || metricLabel(t, key) || key,
      subLabel: metricId && metricId !== key ? metricLabel(t, metricId) : null,
      scaleLabel: scaleLabelOf(metricId),
      direction,
      rowBest,
      cells,
    };
  });

  return { runs, rows };
};
