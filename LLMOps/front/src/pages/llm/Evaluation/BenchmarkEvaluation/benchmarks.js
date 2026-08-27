// 벤치마크 정본 — id = llm_evaluation BE constants.BENCHMARK_IDS + evaluate-benchmark-mock 컨테이너와 일치.
// 메트릭 카탈로그는 benchmarkMetrics.js(점수 함수 — 벤치마크 이름과 분리).
// category id = 카테고리 사이드바 필터.
//
// evalType = **누가 채점하나**. 평가 유형(프로젝트 eval_type)과 같은 축이며, 이 값이
//   벤치마크가 어느 실행 화면에 서는지를 결정한다.
//     'reference' — 정답이 데이터에 있어 기계가 대조한다. 심판이 없고 재현 가능하다.
//     'judge'     — 정답이 없어 심판 LLM 이 1~10 점으로 매긴다. 심판 배포가 필수다.
//   BE 도 프로젝트 유형과 벤치마크 유형이 어긋나면 런 생성을 거부하므로, 두 목록을
//   섞어 한 화면에 세우면 화면에서만 고를 수 있고 서버에서 죽는 조합이 생긴다.

// ⚠️ 사용자에게 보이는 문구는 **전부 i18n 키**로 둔다(labelKey/descKey). 이 카탈로그는
// 데이터 모듈이라 t() 를 부를 수 없고, 문자열을 그대로 박아 두면 영어 로케일에서도 한국어가
// 그대로 나온다(키가 아니라 ko/en 대조로도 안 잡힌다). 렌더하는 쪽에서 t() 로 읽는다.
// 벤치마크 label(ARC·MMLU…)만은 고유명사라 번역하지 않고 문자열로 둔다.
export const BENCHMARK_CATEGORIES = [
  { id: 'all', labelKey: 'evaluation.bench.cat.all' },
  { id: 'knowledge', labelKey: 'evaluation.bench.cat.knowledge' },
  { id: 'reasoning', labelKey: 'evaluation.bench.cat.reasoning' },
  { id: 'commonsense', labelKey: 'evaluation.bench.cat.commonsense' },
  { id: 'math', labelKey: 'evaluation.bench.cat.math' },
  { id: 'safety', labelKey: 'evaluation.bench.cat.safety' },
  { id: 'code', labelKey: 'evaluation.bench.cat.code' },
];

// recommended = 생략 시 채택할 기본 메트릭(BE constants.BENCHMARK_RECOMMENDED_METRIC 와 일치).
// metrics = 이 벤치마크에서 고를 수 있는 메트릭 드롭다운 후보(benchmarkMetrics.js id).
export const BENCHMARKS = [
  {
    id: 'arc',
    label: 'ARC',
    descKey: 'evaluation.bench.benchDesc.arc',
    category: 'reasoning',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm', 'f1'],
  },
  {
    id: 'kobest',
    label: 'KoBEST',
    descKey: 'evaluation.bench.benchDesc.kobest',
    category: 'knowledge',
    evalType: 'reference',
    recommended: 'f1',
    metrics: ['f1', 'accuracy', 'acc_norm'],
  },
  {
    id: 'mmlu',
    label: 'MMLU',
    descKey: 'evaluation.bench.benchDesc.mmlu',
    category: 'knowledge',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm'],
  },
  {
    id: 'hellaswag',
    label: 'HellaSwag',
    descKey: 'evaluation.bench.benchDesc.hellaswag',
    category: 'commonsense',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
  },
  {
    id: 'winogrande',
    label: 'WinoGrande',
    descKey: 'evaluation.bench.benchDesc.winogrande',
    category: 'commonsense',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm'],
  },
  {
    id: 'gsm8k',
    label: 'GSM8K',
    descKey: 'evaluation.bench.benchDesc.gsm8k',
    category: 'math',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1'],
  },
  {
    id: 'truthfulqa',
    label: 'TruthfulQA',
    descKey: 'evaluation.bench.benchDesc.truthfulqa',
    category: 'safety',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1', 'bleu', 'rouge'],
  },
  {
    id: 'boolq',
    label: 'BoolQ',
    descKey: 'evaluation.bench.benchDesc.boolq',
    category: 'safety',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1'],
  },
  {
    id: 'humaneval',
    label: 'HumanEval',
    descKey: 'evaluation.bench.benchDesc.humaneval',
    category: 'code',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
  },
  // 실채점 벤치마크 — 위 9개(해시 mock)와 달리 실제 점수가 나온다.
  // 42문항 × 6영역 × 2턴을 심판 LLM 이 1~10 점으로 채점. 정답(reference)이 없어
  // accuracy/f1 계열은 계산 자체가 불가하고, 고를 수 있는 건 "어느 축을 대표값으로
  // 쓸지"(전체/1턴/2턴)뿐이다. 영역별 점수는 항상 함께 산출돼 결과 상세에 표시된다.
  {
    id: 'logickor',
    label: 'LogicKor',
    descKey: 'evaluation.bench.benchDesc.logickor',
    category: 'reasoning',
    evalType: 'judge',
    recommended: 'judge_overall',
    metrics: ['judge_overall', 'judge_single', 'judge_multi'],
    real: true,
  },
  // 발화의 의도(다중)와 슬롯(값+이름)을 동시에 맞히는 태스크. LogicKor 와 달리 정답이
  // 데이터에 있어(BIO 태그 + 의도 라벨) 심판 없이 결정론적으로 채점된다.
  // 네 지표는 재는 단위가 서로 다르다 — 발화 / 의도 항목 / 슬롯 쌍 / 발화(둘 다).
  {
    id: 'mixatis',
    label: 'MixATIS',
    descKey: 'evaluation.bench.benchDesc.mixatis',
    category: 'reasoning',
    evalType: 'reference',
    recommended: 'joint_acc',
    metrics: ['joint_acc', 'intent_acc', 'intent_f1', 'slot_f1'],
    real: true,
    // LogicKor 는 체크포인트 없이 데이터셋의 기존 생성물을 채점하는 경로가 있지만,
    // MixATIS 채점기는 평가할 가중치가 없으면 기동 직후 거부한다. BE 도
    // constants.CHECKPOINT_REQUIRED_MANIFEST_KEYS 로 파드를 띄우기 전에 막는다.
    requiresCheckpoint: true,
    // 출력이 UGEN 규약을 벗어나면 파싱이 빈 예측을 만들어 전 지표가 0 이 된다. 고르는
    // 자리에서 이 사실을 배지로 세워, 형식 학습이 안 된 가중치로 재고 나서 0 을 보는
    // 일이 없게 한다(실행 차단은 requiresCheckpoint 검증이 담당).
    requiresFormat: true,
  },
];

// 유형별 벤치마크 목록 — 실행 화면 하나가 세우는 후보 전체다. 정답 대조 화면은
// REFERENCE_BENCHMARKS 를(카테고리 필터·검색과 함께), LLM 심사 화면은 JUDGE_BENCHMARKS 를
// 그린다. 한 화면이 둘을 함께 세우지 않는 이유는 채점 주체가 다르면 물어야 할 것이
// 달라지기 때문이다 — 심사에는 심판 배포가 필수이고, 정답 대조에는 심판이 아예 없다.
export const REFERENCE_BENCHMARKS = BENCHMARKS.filter(
  (b) => b.evalType === 'reference',
);

export const JUDGE_BENCHMARKS = BENCHMARKS.filter(
  (b) => b.evalType === 'judge',
);

// 체크포인트 없이는 채점기가 기동 직후 거부하는 벤치마크. 실행 전에 화면에서 걸러
// 값비싼 GPU 파드가 떴다가 죽는 것을 막는다(BE 도 같은 경계를 강제한다).
export const CHECKPOINT_REQUIRED_BENCHMARK_IDS = BENCHMARKS.filter(
  (b) => b.requiresCheckpoint,
).map((b) => b.id);

export const BENCHMARK_MAP = Object.fromEntries(
  BENCHMARKS.map((b) => [b.id, b]),
);

export const BENCHMARK_LABEL = Object.fromEntries(
  BENCHMARKS.map((b) => [b.id, b.label]),
);

// 카테고리별 벤치마크 수(정답 대조 그리드의 필터 카운트). 'all' = 전체.
// 카테고리 필터는 **정답 대조 그리드에만** 걸리므로 세는 대상도 그 목록으로 좁힌다 —
// 전 벤치마크를 세면 그리드에 없는 심사 벤치마크(LogicKor)까지 잡혀 '전체 (11)' 인데
// 10개만 보이고, LogicKor 도 category:'reasoning' 이라 '추론 (3)' 인데 2개만 보이는
// 어긋남이 생긴다.
export const categoryCount = (categoryId) =>
  REFERENCE_BENCHMARKS.filter(
    (b) => categoryId === 'all' || b.category === categoryId,
  ).length;

// 벤치마크의 기본(권장) 메트릭. metrics 후보에 recommended 가 없으면 첫 후보로 폴백.
export const defaultMetricFor = (benchmarkId) => {
  const b = BENCHMARK_MAP[benchmarkId];
  if (!b) return null;
  return b.metrics.includes(b.recommended) ? b.recommended : b.metrics[0];
};

// 형식(출력 규약) 학습이 전제인 벤치마크 — 안 맞으면 점수가 0 으로 주저앉는다.
export const FORMAT_REQUIRED_BENCHMARK_IDS = BENCHMARKS.filter(
  (b) => b.requiresFormat,
).map((b) => b.id);

// 추론을 한 번 더 돌려야 나오는 "생성 지표". 나머지는 한 번의 채점에서 전부 나오므로
// 고를 것이 없지만, 이 둘만은 비용(추론 1회)이 붙어 옵트인으로 둔다.
// 키 = 벤치마크 id, 값 = 그 벤치마크의 metrics 중 생성 경로가 필요한 메트릭 id.
export const GENERATION_METRICS = {
  truthfulqa: ['bleu', 'rouge'],
};

// 이 런이 기록할 지표 목록. 채점기가 한 번에 계산해 내는 지표는 전부 기록되므로
// 사용자가 고를 것이 없다 — 화면은 "무엇이 기록되는지"만 통보한다.
// withGeneration=false 면 생성 지표는 빠진다(기본).
export const recordedMetricsFor = (benchmarkId, withGeneration = false) => {
  const benchmark = BENCHMARK_MAP[benchmarkId];
  if (!benchmark) return [];
  const generation = GENERATION_METRICS[benchmarkId] || [];
  return benchmark.metrics.filter(
    (m) => withGeneration || !generation.includes(m),
  );
};
