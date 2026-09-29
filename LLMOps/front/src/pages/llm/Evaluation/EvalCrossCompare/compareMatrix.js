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

import {
  BENCHMARK_CATEGORIES,
  BENCHMARK_LABEL,
  BENCHMARK_MAP,
} from '../BenchmarkEvaluation/benchmarks';
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
 * 한 런이 여러 벤치마크를 담으면(묶음 실행이 GPU 수만큼 런을 나눈다, 설계 §14) metric_set 이
 * "arc:accuracy,piqa:acc_norm" 이다 — metricKey 와 같은 벤치마크의 토큰을 고른다. metric_set 은
 * 255자에서 잘려 토큰이 없을 수 있어, 그때는 카탈로그의 대표 지표로 되돌아간다.
 */
export const metricIdOf = (run, metricKey) => {
  const tokens = (typeof run?.metric_set === 'string' ? run.metric_set : '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
  const tailOf = (token) =>
    token && token.includes(':') ? token.slice(token.indexOf(':') + 1) : null;
  const own = tailOf(tokens.find((token) => token.split(':')[0] === metricKey));
  if (own && METRIC_MAP[own]) return own;
  // 옛 단일 토큰 런 — 키와 벤치마크 이름이 달라도 그 런의 축은 하나뿐이다(종전 규칙).
  const single = tokens.length === 1 ? tailOf(tokens[0]) || tokens[0] : null;
  if (single && METRIC_MAP[single]) return single;
  if (METRIC_MAP[metricKey]) return metricKey;
  const rec = BENCHMARK_MAP[metricKey]?.recommended;
  return rec && METRIC_MAP[rec] ? rec : null;
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

// 순위(Best·행 최고값)에 들지 않는 런 — 점수는 보이되 다른 런과 겨루지 않는다
// (BE build_eval_comparison 의 best 후보 규칙과 같다).
//   mock          — 해시 mock 채점기의 가짜 점수.
//   sample_limit  — 태스크당 앞 N문항만 잰 빠른 확인. 분모가 달라 전체 측정과 비교할 수 없다.
export const isUnranked = (run) => !!run?.mock || run?.sample_limit != null;

const pickBetter = (a, b, direction) =>
  direction === 'min' ? Math.min(a, b) : Math.max(a, b);

// ── 평가 대상(열) = 모델 × 출처 ─────────────────────────────────────────────
// 같은 모델이라도 체크포인트가 다르면 다른 가중치다 — 한 열로 합치면 ckpt3 의 MMLU 와 ckpt1 의
// ARC 가 한 모델의 성적표로 섞인다. 그래서 열은 "어떤 가중치가 이 점수를 냈나" 단위로 가른다:
//   ckpt:<이름>        — 채점기가 그 체크포인트를 직접 올린 런(lm-eval·포맷 학습)
//   dep:<배포>@<커밋>  — 배포에 생성을 맡긴 런. 커밋은 **완료 시점에 굳힌** 서빙 커밋
//                        (BE source_commit)이다 — 배포는 나중에 다른 커밋으로 다시 올라갈 수
//                        있어 배포 이름만으로 묶으면 한 열에 두 가중치가 섞인다. 굳히기 이전의
//                        옛 런은 커밋을 모르므로 dep:<배포> 로 따로 선다(추측해서 합치지 않는다).
//                        생성 경로(배포의 샘플링 설정)가 달라 체크포인트 열과도 합치지 않는다.
//   unknown           — 둘 다 없는 옛 런(mock 등).
export const sourceKeyOf = (run) => {
  if (run?.checkpoint) return `ckpt:${run.checkpoint}`;
  if (run?.source_mode === 'deployment' && run?.source_deployment)
    return run.source_commit
      ? `dep:${run.source_deployment}@${run.source_commit}`
      : `dep:${run.source_deployment}`;
  return 'unknown';
};

// 한 모델 안의 열 순서 — 기본 가중치(첫 커밋 source_model, evaluate_lmeval checkpoint.SOURCE_MODEL)
// 를 맨 앞에 세운다. 색 실선은 그 모델의 첫 열에 붙으므로 "기준 가중치 = 실선" 이 된다.
const SOURCE_ORDER = { ckpt: 0, dep: 1, unknown: 2 };
const sourceRank = (key) =>
  key === 'ckpt:source_model'
    ? -1
    : (SOURCE_ORDER[String(key).split(':')[0]] ?? 3);

export const subjectKeyOf = (run) => `${run?.model_id}|${sourceKeyOf(run)}`;

// 열 머리 라벨 — 키를 되쪼개지 않고 런의 필드에서 만든다(배포·커밋 이름에 구분자가 섞여도 안전).
const sourceLabelOfRun = (run, t) => {
  if (run?.checkpoint) return String(run.checkpoint);
  if (run?.source_mode === 'deployment' && run?.source_deployment) {
    const via = t('evaluation.compare.viaDeployment', {
      name: run.source_deployment,
    });
    return run.source_commit ? `${via} · ${run.source_commit}` : via;
  }
  return t('evaluation.compare.sourceUnknown');
};

/**
 * 고른 모델들의 런에서 평가 대상(열)을 뽑는다 — 모델 순서를 따르고, 한 모델 안에서는
 * 체크포인트 → 배포 → 출처 미상 순, 같은 종류는 이름순. 런이 하나도 없는 모델도 열 하나를
 * 세운다(전부 '실행 안 함' 으로 보이는 것이 그 모델의 사실이다).
 */
export const buildSubjects = (models, runs, t) =>
  models.flatMap((m, modelIndex) => {
    // id 는 문자열로 맞춰 비교한다 — 셀 키(subjectKeyOf)는 템플릿 문자열이라 타입이 섞여도
    // 같아지는데, 여기서만 엄격 비교하면 그 모델의 열이 자리표시(none)로 바뀌고 점수가 사라진다.
    const labels = new Map(); // 출처 키 → 라벨(그 키의 첫 런에서)
    runs
      .filter((r) => String(r.model_id) === String(m.id))
      .forEach((r) => {
        const key = sourceKeyOf(r);
        if (!labels.has(key)) labels.set(key, sourceLabelOfRun(r, t));
      });
    const keys = [...labels.keys()].sort(
      (a, b) => sourceRank(a) - sourceRank(b) || String(a).localeCompare(b),
    );
    if (!keys.length) {
      return [
        {
          key: `${m.id}|none`,
          modelId: m.id,
          modelName: m.name,
          modelIndex,
          sourceKey: null,
          sourceLabel: null,
          nthOfModel: 0,
        },
      ];
    }
    return keys.map((sourceKey, nthOfModel) => ({
      key: `${m.id}|${sourceKey}`,
      modelId: m.id,
      modelName: m.name,
      modelIndex,
      sourceKey,
      sourceLabel: labels.get(sourceKey),
      nthOfModel,
    }));
  });

/**
 * `{ models, metric_keys, runs }` → `{ models, subjects, rows }`.
 *
 * rows[i] = {
 *   key, metricId, title, subLabel, scaleLabel, direction, rowBest,
 *   cells: { [subjectKey]: { run, value, isBest, delta, barPercent } | null },
 *   runs: [...]            // 이 지표에 기여한 전 런(펼침용)
 * }
 *
 * 셀은 그 평가 대상(모델 × 출처)의 **최고 런**이며 후보는 completed 로 한정한다 — BE 가 전역
 * best 를 고르는 기준과 같게 두어야 같은 데이터에서 두 화면이 다른 승자를 말하지 않는다.
 */
export const buildMatrix = (comparison, t) => {
  const models = Array.isArray(comparison?.models) ? comparison.models : [];
  const metricKeys = Array.isArray(comparison?.metric_keys)
    ? comparison.metric_keys
    : [];
  const allRuns = Array.isArray(comparison?.runs) ? comparison.runs : [];
  const subjects = buildSubjects(models, allRuns, t);
  const subjectOrder = new Map(subjects.map((s, i) => [s.key, i]));

  const rows = metricKeys.map((key) => {
    const direction = directionOf(key);
    const contributing = allRuns.filter((r) => isScored(r, key));

    // 평가 대상별 최고 런(completed 한정). 동점이면 먼저 온 런을 유지한다 —
    // BE 가 runs 를 최신순으로 주므로 최신 런이 남는다.
    // 순위에 들지 않는 런(mock·빠른 확인)은 순위에 드는 런이 하나라도 있으면 그 대상의
    // 대표가 되지 못한다(BE build_eval_comparison 이 best 후보에서 빼는 것과 같은 규칙).
    const bestBySubject = new Map();
    contributing.forEach((run) => {
      if (run.status !== 'completed') return;
      const sk = subjectKeyOf(run);
      const prev = bestBySubject.get(sk);
      if (!prev || (isUnranked(prev) && !isUnranked(run))) {
        bestBySubject.set(sk, run);
        return;
      }
      if (isUnranked(run) && !isUnranked(prev)) return;
      const value = run.metrics[key];
      const prevValue = prev.metrics[key];
      const better =
        direction === 'min' ? value < prevValue : value > prevValue;
      if (better) bestBySubject.set(sk, run);
    });

    const metricId = metricIdOf(
      bestBySubject.values().next().value || contributing[0],
      key,
    );

    // 행 최고값은 순위에 드는 런에서만 뽑는다 — mock·빠른 확인뿐이면 최고값도 없다.
    const cellValues = [...bestBySubject.values()]
      .filter((r) => !isUnranked(r))
      .map((r) => r.metrics[key]);
    const rowBest = cellValues.length
      ? cellValues.reduce((acc, v) => pickBetter(acc, v, direction))
      : null;

    const cells = {};
    subjects.forEach((s) => {
      const run = bestBySubject.get(s.key);
      if (!run) {
        cells[s.key] = null;
        return;
      }
      const value = run.metrics[key];
      const unranked = isUnranked(run);
      cells[s.key] = {
        run,
        value,
        isBest: !unranked && value === rowBest,
        // 순위에 들지 않는 런은 최고값과 견주지 않는다 — 20문항 점수 옆에 "+55" 나 막대를
        // 그리면 분모가 다른 두 점수를 비교하는 셈이다(점수와 배지만 보인다).
        delta:
          unranked || value === rowBest
            ? null
            : deltaLabelOf(metricId, value, rowBest),
        barPercent: unranked ? 0 : barPercentOf(value, rowBest, direction),
      };
    });

    // 펼침 목록 — 평가 대상 열 순서로 묶고, 같은 대상 안에서는 우수한 점수부터.
    const drawerRuns = [...contributing].sort((a, b) => {
      const ka = subjectKeyOf(a);
      const kb = subjectKeyOf(b);
      const oa = subjectOrder.has(ka)
        ? subjectOrder.get(ka)
        : Number.MAX_SAFE_INTEGER;
      const ob = subjectOrder.has(kb)
        ? subjectOrder.get(kb)
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

  return { models, subjects, rows };
};

// ── 평가 대상 요약(스코어카드) ─────────────────────────────────────────────
// ETRI 대시보드의 "영어 core / 한국어 / 생성형 평균" 에 해당하는 요약이다. 다만 그 도구의
// "종합"(전체 대표지표 평균)은 따르지 않는다 — 정답률·F1·BLEU 를 한 평균에 섞는다.
//   · 평균에 넣는 것은 정답 대조 벤치마크의 **0~100 정답률 계열** 대표 지표뿐이다.
//     BLEU/ROUGE·perplexity·심판 점수(0~10)·MixATIS(0~1)·사용자 데이터셋(custom)은 뺀다.
//   · 순위에 들지 않는 런(mock·빠른 확인)도 뺀다 — 분모가 다르거나 점수가 가짜다.
//   · 평균은 **카드에 오른 모든 대상이 잰 벤치마크**로만 낸다. 대상마다 잰 벤치마크가 다르면
//     평균이 서로 다른 문항 집합을 재 비교가 거짓이 된다.
export const AVERAGE_METRIC_IDS = new Set([
  'accuracy',
  'acc_norm',
  'f1',
  'exact_match',
  'pass_at_1',
]);

const mean = (values) =>
  values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

/**
 * buildMatrix 결과 → `{ cards, sharedCount, totalCount, categoryIds }`.
 *
 * cards[i] = { subject, measured, overall, categories: { [categoryId]: number }, unrankedOnly }
 *   measured     — 이 대상이 전체 측정으로 잰 평균 가능 벤치마크 수(커버리지)
 *   overall      — 공통 벤치마크 평균(공통이 없으면 null)
 *   unrankedOnly — 순위 제외 점수(빠른 점검·mock)만 있는 대상(평균·공통 계산에서 빠진다)
 * sharedCount — 모든 카드가 잰 벤치마크 수, totalCount — 누구든 잰 평균 가능 벤치마크 수
 * categoryIds — 공통 벤치마크에 있는 카테고리(카탈로그 순서)
 */
export const buildScorecards = (matrix) => {
  const subjects = matrix?.subjects || [];
  const averageRows = (matrix?.rows || []).filter((row) => {
    const bench = BENCHMARK_MAP[row.key];
    return (
      bench &&
      bench.evalType === 'reference' &&
      bench.category !== 'custom' &&
      AVERAGE_METRIC_IDS.has(row.metricId) &&
      scaleMaxFor(row.metricId) === 100
    );
  });
  const ranked = (row, subject) => {
    const cell = row.cells[subject.key];
    return cell && !isUnranked(cell.run) ? cell : null;
  };
  const scoredSubjects = subjects.filter((s) =>
    averageRows.some((row) => ranked(row, s)),
  );
  const measuredRows = averageRows.filter((row) =>
    scoredSubjects.some((s) => ranked(row, s)),
  );
  const sharedRows = measuredRows.filter((row) =>
    scoredSubjects.every((s) => ranked(row, s)),
  );
  const categoryIds = BENCHMARK_CATEGORIES.map((c) => c.id).filter((id) =>
    sharedRows.some((row) => BENCHMARK_MAP[row.key].category === id),
  );

  const scoreCard = (subject) => {
    const categories = {};
    categoryIds.forEach((id) => {
      categories[id] = mean(
        sharedRows
          .filter((row) => BENCHMARK_MAP[row.key].category === id)
          .map((row) => ranked(row, subject).value),
      );
    });
    return {
      subject,
      measured: measuredRows.filter((row) => ranked(row, subject)).length,
      overall: mean(sharedRows.map((row) => ranked(row, subject).value)),
      categories,
      unrankedOnly: false,
    };
  };

  // 순위 제외 점수(빠른 점검·mock)만 있는 대상도 카드는 세운다 — 빼 버리면 "고른 모델에 비교할
  // 전체 측정이 없다"는 사실이 가려지고, 남은 한 대상의 평균이 비교 결과처럼 읽힌다(codex 리뷰).
  // 평균·공통 벤치마크 계산에는 넣지 않는다(넣으면 mock 만 있는 옛 이력이 요약을 늘 비운다).
  const cards = subjects
    .filter(
      (s) =>
        scoredSubjects.includes(s) ||
        averageRows.some((row) => row.cells[s.key]),
    )
    .map((subject) =>
      scoredSubjects.includes(subject)
        ? scoreCard(subject)
        : {
            subject,
            measured: 0,
            overall: null,
            categories: {},
            unrankedOnly: true,
          },
    );

  return {
    cards,
    sharedCount: sharedRows.length,
    totalCount: measuredRows.length,
    categoryIds,
  };
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

    // 행 최고값은 순위에 드는 런에서만 — mock·빠른 확인 점수가 Best 가 되면 전체 측정 런이 뒤처져 보인다.
    const realScored = scored.filter((r) => !isUnranked(r));
    const rowBest = realScored.length
      ? realScored
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
      const unranked = isUnranked(run);
      cells[run.id] = {
        run,
        value,
        isBest: !unranked && value === rowBest,
        // 순위에 들지 않는 런은 최고값과 견주지 않는다 — 20문항 점수 옆에 "+55" 나 막대를
        // 그리면 분모가 다른 두 점수를 비교하는 셈이다(점수와 배지만 보인다).
        delta:
          unranked || value === rowBest
            ? null
            : deltaLabelOf(metricId, value, rowBest),
        barPercent: unranked ? 0 : barPercentOf(value, rowBest, direction),
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
