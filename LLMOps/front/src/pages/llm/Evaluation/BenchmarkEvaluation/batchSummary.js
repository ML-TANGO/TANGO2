// 벤치마크 실행(묶음) 결과 — ETRI 결과 화면(Evaluation/lmeval 대시보드)을 이 플랫폼의 런으로
// 채우는 순수 계산부. 실행 카드(ProjectDetail)와 결과 요약 화면(BenchmarkBatchPage)은 여기서
// 나온 shape 만 그린다(렌더 밖에서도 그대로 쓰이도록 i18n 을 잡지 않는다).
//
// 단위는 **한 번의 실행 = 카드 1장**이다. 한 실행은 고른 GPU 수만큼의 런(eval_result)으로 나뉘고
// 런 하나가 벤치마크 여러 개를 차례로 채점한다(설계 §14). 함께 실행한 런과 런마다 담은 벤치마크는
// BE 의 실행 기록(project.batches: job_ids·job_benchmarks)이 묶는다. 기록이 없는 런(단건 실행·기록
// 이전 런)은 카드 한 장씩으로 선다. 화면의 진행·상태는 **벤치마크 단위**다 — 런 하나가 여러
// 벤치마크를 담으므로 런 상태만으로는 "무엇이 끝났나"를 말할 수 없다(채점기 progress.json).
//
// 요약 카드는 ETRI 의 4장(영어 core / 한국어 / 생성형 평균 + 종합)을 따른다. 다만 **종합**은
// 모델 비교 요약(compareMatrix.buildScorecards)과 같은 규칙으로 0~100 정답률 계열 대표 지표만
// 평균한다(사용자 결정 2026-09-29) — ETRI 의 종합은 정답률·F1·BLEU 를 한 평균에 섞는다.
// 생성형 카드는 ETRI 처럼 생성형 벤치마크의 대표 지표를 평균한다(BLEU 포함 — 카드 이름이 그 뜻이다).

import {
  BENCHMARK_CATEGORIES,
  BENCHMARK_GROUPS,
  BENCHMARK_LABEL,
  BENCHMARK_MAP,
  DATASET_FREE_BENCHMARK_IDS,
} from './benchmarks';
import { METRIC_MAP, scaleMaxFor } from './benchmarkMetrics';
import { AVERAGE_METRIC_IDS } from '../EvalCrossCompare/compareMatrix';

const RUNNING_STATUSES = new Set(['running', 'pending', 'created']);
const TERMINAL_RUN_STATUSES = new Set(['completed', 'failed', 'cancelled']);

// 카드 키 — 실행 기록은 id, 기록 없는 런은 job id 앞에 'r-'. 결과 화면 경로(/batch/:key)가 된다.
export const RUN_KEY_PREFIX = 'r-';

const mean = (values) =>
  values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

/**
 * 고른 벤치마크를 담는 데 필요한 **최소 런(GPU) 수** — BE plan_benchmark_runs 와 같은 규칙.
 * 코드 실행 벤치마크(HumanEval)는 격리 채점기라, 데이터셋을 읽는 벤치마크(custom)는 데이터셋을
 * 그 런에만 싣기 위해 각각 따로 런이 된다. 나머지는 몇 개든 런 하나에 담을 수 있다.
 */
export const minRunCount = (ids) => {
  const list = Array.isArray(ids) ? ids : [];
  const code = list.filter((id) => BENCHMARK_MAP[id]?.executesCode);
  const readsDataset = list.filter(
    (id) => !code.includes(id) && !DATASET_FREE_BENCHMARK_IDS.includes(id),
  );
  const plain = list.length - code.length - readsDataset.length;
  return (code.length ? 1 : 0) + (readsDataset.length ? 1 : 0) + (plain ? 1 : 0);
};

/**
 * 멤버 런 상태 → 카드 상태. 하나라도 도는 중이면 running, 전부 끝났는데 일부만 성공이면
 * partial(ETRI 는 벤치마크별 '실패' 를 목록에 남기고 나머지를 보여준다 — 같은 뜻이다).
 */
export const groupStatusOf = (members, launchFailed = 0) => {
  // launchFailed — 런치조차 못 한 벤치마크 수(런이 없다). 요청한 전부를 분모에 세운다.
  const counts = { completed: 0, running: 0, failed: launchFailed };
  members.forEach((run) => {
    const status = run.status || 'running';
    if (RUNNING_STATUSES.has(status)) counts.running += 1;
    else if (status === 'completed') counts.completed += 1;
    else counts.failed += 1;
  });
  const total = members.length + launchFailed;
  let status = 'failed';
  if (counts.running) status = 'running';
  else if (counts.completed === total) status = 'completed';
  else if (counts.completed) status = 'partial';
  return { status, counts, total };
};

/**
 * 벤치마크 항목 → 진행(벤치마크 단위). 카드·요약 화면이 쓴다 — 런 하나가 벤치마크 여러 개를 담으므로
 * 런 단위로 세면 "런 1/4 완료"가 몇 개의 점수를 뜻하는지 알 수 없다. 모양은 groupStatusOf 와 같다.
 */
export const entryProgressOf = (entries) => {
  // cancelled 는 사용자가 멈춘 것이라 실패와 따로 센다(화면 문구가 다르다). 상태 판정에서는 둘 다
  // "끝났는데 점수가 없다" 로 같다.
  const counts = { completed: 0, running: 0, failed: 0, cancelled: 0 };
  (Array.isArray(entries) ? entries : []).forEach((entry) => {
    if (entry.status === 'completed') counts.completed += 1;
    else if (RUNNING_STATUSES.has(entry.status)) counts.running += 1;
    else if (entry.status === 'cancelled') counts.cancelled += 1;
    else counts.failed += 1;
  });
  const total =
    counts.completed + counts.running + counts.failed + counts.cancelled;
  let status = 'failed';
  if (counts.running) status = 'running';
  else if (total && counts.completed === total) status = 'completed';
  else if (counts.completed) status = 'partial';
  return { status, counts, total };
};

/**
 * 런 목록 + 실행 기록 → 카드(실행) 목록(최신순).
 * groups[i] = { key, batchId, members, createDatetime, sampleLimit, checkpoint, modelName,
 *               status, counts, total }
 * 한 런은 한 카드에만 속한다(BE 가 job_str_id 를 멤버 테이블에서 유일하게 둔다).
 */
export const buildRunGroups = (runs, batches) => {
  const list = Array.isArray(runs) ? runs : [];
  const byJob = new Map(list.map((run) => [String(run.job_id), run]));
  const used = new Set();
  const groups = [];
  (Array.isArray(batches) ? batches : []).forEach((batch) => {
    // 런마다 담은 벤치마크 — 멤버 행에 붙여 둔다(metric_set 은 255자에서 잘려 정본이 못 된다).
    const jobBenchmarks = batch.job_benchmarks || {};
    const members = (batch.job_ids || [])
      .map((jobId) => {
        const run = byJob.get(String(jobId));
        const benchmarks = jobBenchmarks[jobId];
        return run && Array.isArray(benchmarks) && benchmarks.length
          ? { ...run, benchmarks }
          : run;
      })
      .filter(Boolean);
    if (!members.length) return;
    members.forEach((run) => used.add(String(run.job_id)));
    groups.push({
      key: String(batch.id),
      batchId: batch.id,
      members,
      launchFailures: Array.isArray(batch.launch_failures)
        ? batch.launch_failures
        : [],
      createDatetime: batch.create_datetime || members[0].create_datetime,
      sampleLimit: batch.sample_limit ?? null,
      checkpoint: batch.checkpoint || members[0].checkpoint || null,
    });
  });
  list.forEach((run) => {
    if (used.has(String(run.job_id))) return;
    groups.push({
      key: `${RUN_KEY_PREFIX}${run.job_id}`,
      batchId: null,
      members: [run],
      launchFailures: [],
      createDatetime: run.create_datetime,
      sampleLimit: run.sample_limit ?? null,
      checkpoint: run.checkpoint || null,
    });
  });
  return groups
    .map((group) => ({
      ...group,
      modelName:
        group.members[0].source_model || group.members[0].model_name || '-',
      ...groupStatusOf(group.members, group.launchFailures.length),
    }))
    .sort((a, b) =>
      String(b.createDatetime || '').localeCompare(
        String(a.createDatetime || ''),
      ),
    );
};

// metric_set("arc:accuracy,mmlu:accuracy") → [{benchmarkKey, metricId}] — **전 토큰**. API·기본 집합으로
// 만든 옛 런은 여러 벤치마크를 한 런에 담는다 — 첫 토큰만 읽으면 나머지가 요약에서 사라진다(codex 리뷰).
// 콜론 없는 옛 토큰은 지표 id 뿐이다. ⚠️ metric_set 은 255자에서 잘린다 — 실행 기록이 런마다 담은
// 벤치마크(run.benchmarks, buildRunGroups 가 붙인다)를 주면 그것이 우선이다.
const metricSetTokens = (run) => {
  if (Array.isArray(run?.benchmarks) && run.benchmarks.length) {
    return run.benchmarks.map((id) => ({
      benchmarkKey: id,
      metricId: BENCHMARK_MAP[id]?.recommended || null,
    }));
  }
  const tokens = String(run?.metric_set || '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
  if (!tokens.length) return [{ benchmarkKey: null, metricId: null }];
  return tokens.map((token) => {
    const [head, tail] = token.split(':');
    let metricId = null;
    if (tail && METRIC_MAP[tail]) metricId = tail;
    else if (METRIC_MAP[head]) metricId = head;
    return { benchmarkKey: head || null, metricId };
  });
};

const finite = (...values) => values.find((v) => Number.isFinite(v)) ?? null;

/**
 * 한 벤치마크의 상태 — 런 상태가 아니라 **그 벤치마크**가 어디까지 왔나.
 *   점수가 있으면 completed(런이 아직 돌거나 도중에 죽었어도 — 채점기가 끝난 점수를 남긴다),
 *   채점기가 실패로 적었으면 failed, 런이 끝났는데 점수가 없으면 런의 종료 상태(끝까지 돈 런이면
 *   failed), 아직이면 채점기 진행 기록의 pending(대기)/running(채점 중).
 */
const entryStatusOf = ({ value, failedRow, progRow, runStatus }) => {
  if (failedRow || progRow?.status === 'failed') return 'failed';
  if (value != null) return 'completed';
  if (TERMINAL_RUN_STATUSES.has(runStatus))
    return runStatus === 'completed' ? 'failed' : runStatus;
  return progRow?.status === 'pending' ? 'pending' : 'running';
};

/**
 * 멤버 런(+ 도착한 결과 JSON + 채점기 진행 기록) → 벤치마크 항목(런 × 담은 벤치마크).
 *   resultsByJob[jobId]  = 완료된 런의 metrics.json(BE get_eval_result ready).
 *   progressByJob[jobId] = 아직 metrics.json 이 없는 런의 진행({benchmarks:[…], partial_metrics}) —
 *     끝난 벤치마크의 점수(partial_metrics)는 런이 도중에 죽거나 취소돼도 남는다. 없으면 목록 행의
 *     run.progress(프로젝트 조회가 싣는 점수 요약)를 쓴다.
 * 값은 결과 JSON(또는 중간 결과)의 averages → 목록 행의 평탄화 점수 → 진행 기록의 점수 순. lm-eval
 * 상세(few-shot·태스크·문항 수·소요·원 지표)는 lmeval.benchmarks[<id>] 에만 있다(scoring.build_metrics).
 * key = `${jobId}:${benchmarkKey}` — 한 런이 여러 항목이 되어 jobId 만으로는 겹친다.
 */
export const benchmarkEntriesOf = (members, resultsByJob = {}, progressByJob = {}) =>
  members.flatMap((run, runOrder) =>
    metricSetTokens(run).map(({ benchmarkKey, metricId }, tokenOrder) => {
      const full = resultsByJob[run.job_id] || null;
      // 진행 기록 — 요약 화면은 폴링한 것을, 카드 목록은 프로젝트 조회가 끝나지 않은 런 행에 실어
      // 준 것(run.progress, 점수 요약만)을 쓴다. 둘이 같은 사실을 말해야 한다.
      const prog = full
        ? null
        : progressByJob[run.job_id] || run.progress || null;
      const source = full || prog?.partial_metrics || null;
      const bench = BENCHMARK_MAP[benchmarkKey] || null;
      const detail = source?.lmeval?.benchmarks?.[benchmarkKey] || null;
      const progRow =
        (prog?.benchmarks || []).find((b) => b?.benchmark === benchmarkKey) ||
        null;
      const failedRow =
        (source?.failed_benchmarks || []).find(
          (f) => f?.benchmark === benchmarkKey,
        ) || null;
      const value = finite(
        source?.averages?.[benchmarkKey],
        run.metrics?.[benchmarkKey],
        progRow?.score,
      );
      return {
        key: `${run.job_id}:${benchmarkKey ?? tokenOrder}`,
        jobId: run.job_id,
        run,
        order: runOrder,
        benchmarkKey,
        label: BENCHMARK_LABEL[benchmarkKey] || benchmarkKey || '-',
        group: bench?.group || 'custom',
        category: bench?.category || null,
        evalType: bench?.evalType || null,
        metricId,
        scaleMax: scaleMaxFor(metricId),
        value,
        status: entryStatusOf({
          value,
          failedRow,
          progRow,
          runStatus: run.status || 'running',
        }),
        mock: !!run.mock,
        sampleLimit: run.sample_limit ?? source?.lmeval?.limit ?? null,
        numFewshot: detail?.num_fewshot ?? null,
        tasks: Array.isArray(detail?.tasks) ? detail.tasks : [],
        n: detail?.n ?? null,
        elapsedSec: detail?.elapsed_sec ?? progRow?.elapsed_sec ?? null,
        lmMetrics: Array.isArray(detail?.metrics) ? detail.metrics : [],
        // 채점하다 실패한 사유(채점기 기록). 런치 실패(launchError)와는 다르다 — 런은 있다.
        error: failedRow?.error || progRow?.error || null,
        launchError: null,
      };
    }),
  );

/**
 * 결과 JSON 을 벤치마크 하나로 좁힌다 — 세부 화면(BenchmarkResultView)이 요약에서 누른 벤치마크만
 * 보이게. 런 하나가 여러 벤치마크를 담아도 세부 화면은 종전처럼 "벤치마크 하나"를 깊게 읽는다.
 * 그 벤치마크가 결과에 없으면(다른 런의 것·실패) 원본을 그대로 돌려준다.
 */
export const focusMetrics = (metrics, benchmarkKey) => {
  if (!metrics || !benchmarkKey) return metrics;
  const averages = metrics.averages || {};
  const details = metrics.lmeval?.benchmarks || {};
  if (!(benchmarkKey in averages) && !(benchmarkKey in details)) return metrics;
  const pick = (obj) =>
    obj && benchmarkKey in obj ? { [benchmarkKey]: obj[benchmarkKey] } : {};
  return {
    ...metrics,
    results: (Array.isArray(metrics.results) ? metrics.results : []).filter(
      (row) => row?.benchmark === benchmarkKey,
    ),
    averages: pick(averages),
    metric_map: pick(metrics.metric_map),
    benchmark_set: [benchmarkKey],
    ...(metrics.lmeval
      ? { lmeval: { ...metrics.lmeval, benchmarks: pick(details) } }
      : {}),
  };
};

/**
 * 런치조차 못 한 벤치마크 → 항목(런이 없어 누를 곳이 없다 — jobId null). 요청한 전부가 요약에
 * 보여야 "4개를 요청했는데 3개가 끝났다"가 읽힌다. 평균에는 값이 없어 들어가지 않는다.
 */
export const launchFailureEntriesOf = (failures) =>
  (Array.isArray(failures) ? failures : []).map((failure, i) => {
    const benchmarkKey = failure?.benchmark || null;
    const bench = BENCHMARK_MAP[benchmarkKey] || null;
    const metricId = bench?.recommended || null;
    return {
      key: `launch:${benchmarkKey ?? i}`,
      jobId: null,
      run: null,
      order: Number.MAX_SAFE_INTEGER,
      benchmarkKey,
      label: BENCHMARK_LABEL[benchmarkKey] || benchmarkKey || '-',
      group: bench?.group || 'custom',
      category: bench?.category || null,
      evalType: bench?.evalType || null,
      metricId,
      scaleMax: scaleMaxFor(metricId),
      value: null,
      status: 'failed',
      mock: false,
      sampleLimit: null,
      numFewshot: null,
      tasks: [],
      n: null,
      elapsedSec: null,
      lmMetrics: [],
      error: null,
      launchError: String(failure?.error || ''),
    };
  });

// 평균에 넣을 수 있는 값 — 점수가 있고, mock 이 아니고, 0~100 척도(MixATIS 0~1·심판 0~10 제외).
// 빠른 점검은 넣는다: 한 실행 안의 벤치마크는 문항 상한이 같아 서로의 분모가 같다(화면은 배지로 알린다).
const averageable = (entry) =>
  entry.value != null && !entry.mock && entry.scaleMax === 100;

// 종합·레이더에 넣는 값 — 정답률 계열 대표 지표만, 정답 대조 벤치마크만, 사용자 데이터셋 제외.
const accuracyLike = (entry) =>
  averageable(entry) &&
  AVERAGE_METRIC_IDS.has(entry.metricId) &&
  entry.evalType === 'reference' &&
  entry.category !== 'custom';

/**
 * 요약 카드 4장 + 레이더(카테고리 평균).
 * cards = [{ id: core_en|korean|generative|overall, value, count, total }]
 *   total — 그 묶음에 속한 벤치마크 수(아직 점수가 없는 것 포함), count — 평균에 들어간 수.
 * radar = [{ id: categoryId, value }] — 카탈로그 카테고리 순서.
 */
export const batchSummaryOf = (entries) => {
  const pick = (groups) => entries.filter((e) => groups.includes(e.group));
  const card = (id, groups) => {
    const members = pick(groups);
    const used = members.filter(averageable);
    return {
      id,
      value: mean(used.map((e) => e.value)),
      count: used.length,
      total: members.length,
    };
  };
  const overallSet = entries.filter(accuracyLike);
  const cards = [
    card('core_en', ['core_en']),
    card('korean', ['korean']),
    // ETRI 는 생성형 카드의 개수에 사용자 데이터셋 평가를 함께 센다 — 같은 묶음으로 둔다.
    card('generative', ['generative', 'custom']),
    {
      id: 'overall',
      value: mean(overallSet.map((e) => e.value)),
      count: overallSet.length,
      total: entries.length,
    },
  ];
  const radar = BENCHMARK_CATEGORIES.map((c) => c.id)
    .map((id) => ({
      id,
      value: mean(
        overallSet.filter((e) => e.category === id).map((e) => e.value),
      ),
    }))
    .filter((item) => item.value != null);
  return { cards, radar };
};

// 그룹 → 색 슬롯(막대·범례). BENCHMARK_GROUPS 의 순서가 곧 슬롯이다.
export const GROUP_COLOR = Object.fromEntries(
  BENCHMARK_GROUPS.map((g) => [g.id, g.color]),
);

// 생성형 지표 표의 열 — lm-eval 원 지표 이름 후보(앞이 우선). ETRI renderGenTable 과 같은 열.
//   SQuADv2: exact·f1 / TruthfulQA-gen: bleu_max·rouge*_max / DROP: em·f1 / custom: f1·em·bleu·rouge*
export const GENERATIVE_COLUMNS = [
  { id: 'f1', label: 'F1', names: ['f1', 'best_f1'] },
  { id: 'em', label: 'EM', names: ['em', 'exact', 'exact_match'] },
  { id: 'bleu', label: 'BLEU', names: ['bleu', 'bleu_max'] },
  { id: 'rouge1', label: 'ROUGE-1', names: ['rouge1', 'rouge1_max'] },
  { id: 'rouge2', label: 'ROUGE-2', names: ['rouge2', 'rouge2_max'] },
  { id: 'rougeL', label: 'ROUGE-L', names: ['rougeL', 'rougeL_max', 'rougel'] },
];

/**
 * 생성형 지표 표 — 생성형·사용자 묶음 중 그 지표가 하나라도 있는 벤치마크만(ETRI 와 같다).
 * rows[i] = { entry, cells: { f1, em, bleu, rouge1, rouge2, rougeL } } — 없으면 null.
 */
export const generativeRowsOf = (entries) =>
  entries
    .filter((e) => e.group === 'generative' || e.group === 'custom')
    .map((entry) => {
      const byName = {};
      entry.lmMetrics.forEach((m) => {
        if (!(m.metric in byName) && Number.isFinite(m.score))
          byName[m.metric] = m.score;
      });
      const cells = {};
      GENERATIVE_COLUMNS.forEach((col) => {
        const hit = col.names.find((name) => name in byName);
        cells[col.id] = hit === undefined ? null : byName[hit];
      });
      return { entry, cells };
    })
    .filter((row) => Object.values(row.cells).some((v) => v != null));

/**
 * 전체 지표 상세 — 벤치마크 × lm-eval 원 지표 한 줄씩(ETRI renderDetailTable). lm-eval 상세가
 * 없는 런(MixATIS·mock·완료 전)은 대표 점수 한 줄로 선다. first = 벤치마크의 첫 줄(병합 표시용).
 */
export const detailRowsOf = (entries) =>
  entries.flatMap((entry) => {
    if (!entry.lmMetrics.length) {
      return [
        {
          key: `${entry.key}:primary`,
          entry,
          first: true,
          metric: entry.metricId,
          filter: null,
          score: entry.value,
          stderr: null,
          lm: false,
        },
      ];
    }
    return entry.lmMetrics.map((m, i) => ({
      key: `${entry.key}:${m.metric}:${m.filter || ''}:${i}`,
      entry,
      first: i === 0,
      metric: m.metric,
      filter: m.filter && m.filter !== 'none' ? m.filter : null,
      score: Number.isFinite(m.score) ? m.score : null,
      stderr: Number.isFinite(m.stderr) ? m.stderr : null,
      lm: true,
    }));
  });
