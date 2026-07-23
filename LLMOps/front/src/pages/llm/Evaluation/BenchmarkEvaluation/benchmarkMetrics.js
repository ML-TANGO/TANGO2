// 메트릭 정본(점수 함수) — id = llm_evaluation BE constants.METRIC_IDS + evaluate-benchmark-mock 일치.
// 벤치마크(ARC·MMLU…) 와 분리된 "채점 방식"만 담는다. 벤치마크 카탈로그는 benchmarks.js.
//   formula = 메트릭 설명 패널의 수식 요약, common = 주로 쓰이는 벤치마크 라벨(태그).
export const METRICS = [
  {
    id: 'accuracy',
    label: 'Accuracy',
    desc: '전체 정답률',
    formula: '정답으로 예측한 항목 수 / 전체 항목 수',
    common: ['MMLU', 'ARC', 'GSM8K', 'BoolQ'],
  },
  {
    id: 'f1',
    label: 'F1 Score',
    desc: 'Precision과 Recall의 조화평균',
    formula: '2 · (Precision · Recall) / (Precision + Recall)',
    common: ['KoBEST', 'BoolQ'],
  },
  {
    id: 'acc_norm',
    label: 'ACC_NORM',
    desc: '정규화된 정확도',
    formula: '길이 등으로 정규화한 정답률',
    common: ['HellaSwag', 'ARC'],
  },
  {
    id: 'bleu',
    label: 'BLEU',
    desc: 'N-gram 정밀도 기반 번역 품질',
    formula: 'BP · exp(Σ wₙ log pₙ)',
    common: ['TruthfulQA'],
  },
  {
    id: 'rouge',
    label: 'ROUGE-L',
    desc: '최장 공통 부분 수열 기반 요약 품질',
    formula: 'LCS 기반 F-measure',
    common: ['TruthfulQA'],
  },
  {
    id: 'meteor',
    label: 'METEOR',
    desc: '번역/생성 품질 — 단어 정렬 기반',
    formula: '단어 정렬 기반 정밀도·재현율 조화평균',
    common: [],
  },
  {
    id: 'cider',
    label: 'CIDEr',
    desc: '이미지 캡셔닝 품질 — TF-IDF 가중치',
    formula: 'TF-IDF 가중 n-gram 코사인 유사도',
    common: [],
  },
  {
    id: 'spice',
    label: 'SPICE',
    desc: '장면 그래프 기반 의미 유사도',
    formula: 'scene-graph 튜플 F-score',
    common: [],
  },
];

export const METRIC_MAP = Object.fromEntries(METRICS.map((m) => [m.id, m]));

export const METRIC_LABEL = Object.fromEntries(
  METRICS.map((m) => [m.id, m.label]),
);

// 숫자 포맷 — 벤치마크 메트릭은 스케일 혼재(accuracy 0-100 vs perplexity 등)라 % 강제 X.
export const fmt = (v) => {
  if (v == null) return '-';
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
};

// 막대 폭은 0-100 클램프(비율 외 메트릭이 넘쳐 레이아웃 깨지는 것 방지 — 시각 근사).
export const barWidth = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
};
