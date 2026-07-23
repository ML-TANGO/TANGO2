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
];

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
