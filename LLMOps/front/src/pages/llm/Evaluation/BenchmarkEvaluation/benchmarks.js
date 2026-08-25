// 벤치마크 정본 — id = llm_evaluation BE constants.BENCHMARK_IDS + evaluate-benchmark-mock 컨테이너와 일치.
// 벤치마크 평가는 "벤치마크 선택 → 벤치마크별 메트릭 지정" 2단계다. 이 카탈로그가
//   1단계(선택·카테고리 필터)와 2단계(권장/허용 메트릭)의 소스다. 메트릭 카탈로그는
//   benchmarkMetrics.js(점수 함수 — 벤치마크 이름과 분리). category id = 카테고리 사이드바 필터.

export const BENCHMARK_CATEGORIES = [
  { id: 'all', label: '전체' },
  { id: 'knowledge', label: '지식/이해' },
  { id: 'reasoning', label: '추론' },
  { id: 'commonsense', label: '상식/언어이해' },
  { id: 'math', label: '수학' },
  { id: 'safety', label: '사실성/안전성' },
  { id: 'code', label: '코드' },
];

// recommended = 생략 시 채택할 기본 메트릭(BE constants.BENCHMARK_RECOMMENDED_METRIC 와 일치).
// metrics = 이 벤치마크에서 고를 수 있는 메트릭 드롭다운 후보(benchmarkMetrics.js id).
export const BENCHMARKS = [
  {
    id: 'arc',
    label: 'ARC',
    desc: 'AI2 Reasoning Challenge',
    category: 'reasoning',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm', 'f1'],
  },
  {
    id: 'kobest',
    label: 'KoBEST',
    desc: '한국어 NLU 벤치마크',
    category: 'knowledge',
    recommended: 'f1',
    metrics: ['f1', 'accuracy', 'acc_norm'],
  },
  {
    id: 'mmlu',
    label: 'MMLU',
    desc: '다분야 언어 이해 (57개 과목)',
    category: 'knowledge',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm'],
  },
  {
    id: 'hellaswag',
    label: 'HellaSwag',
    desc: '상식 추론 — 문장 완성',
    category: 'commonsense',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
  },
  {
    id: 'winogrande',
    label: 'WinoGrande',
    desc: '상식 추론 — 대명사 해소',
    category: 'commonsense',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm'],
  },
  {
    id: 'gsm8k',
    label: 'GSM8K',
    desc: '초등 수학 문제 풀이',
    category: 'math',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1'],
  },
  {
    id: 'truthfulqa',
    label: 'TruthfulQA',
    desc: '사실 정확성 평가',
    category: 'safety',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1', 'bleu', 'rouge'],
  },
  {
    id: 'boolq',
    label: 'BoolQ',
    desc: '예/아니오 질의응답',
    category: 'safety',
    recommended: 'accuracy',
    metrics: ['accuracy', 'f1'],
  },
  {
    id: 'humaneval',
    label: 'HumanEval',
    desc: '코드 생성 능력 평가',
    category: 'code',
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
    desc: '한국어 추론·생성 — 6영역 × 2턴, 심판 LLM 1~10점',
    category: 'reasoning',
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
    desc: '다중의도·슬롯 — 828 발화, 정답 대조 채점(심판 없음)',
    category: 'reasoning',
    recommended: 'joint_acc',
    metrics: ['joint_acc', 'intent_acc', 'intent_f1', 'slot_f1'],
    real: true,
    // LogicKor 는 체크포인트 없이 데이터셋의 기존 생성물을 채점하는 경로가 있지만,
    // MixATIS 채점기는 평가할 가중치가 없으면 기동 직후 거부한다. BE 도
    // constants.CHECKPOINT_REQUIRED_MANIFEST_KEYS 로 파드를 띄우기 전에 막는다.
    requiresCheckpoint: true,
  },
];

// 실채점 벤치마크 id 집합 — mock(해시 점수)과 구분해 배지로 표시한다. BE
// constants.REAL_BENCHMARK_MANIFEST_KEY 와 대응한다(서로 다른 채점 컨테이너로 라우팅되며,
// 그래서 mock 벤치마크와 한 런에 섞어 실행할 수 없다).
export const REAL_BENCHMARK_IDS = BENCHMARKS.filter((b) => b.real).map((b) => b.id);

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

export const CATEGORY_LABEL = Object.fromEntries(
  BENCHMARK_CATEGORIES.map((c) => [c.id, c.label]),
);

// 카테고리별 벤치마크 수(사이드바 카운트). 'all' = 전체.
export const categoryCount = (categoryId) =>
  categoryId === 'all'
    ? BENCHMARKS.length
    : BENCHMARKS.filter((b) => b.category === categoryId).length;

// 벤치마크의 기본(권장) 메트릭. metrics 후보에 recommended 가 없으면 첫 후보로 폴백.
export const defaultMetricFor = (benchmarkId) => {
  const b = BENCHMARK_MAP[benchmarkId];
  if (!b) return null;
  return b.metrics.includes(b.recommended) ? b.recommended : b.metrics[0];
};
