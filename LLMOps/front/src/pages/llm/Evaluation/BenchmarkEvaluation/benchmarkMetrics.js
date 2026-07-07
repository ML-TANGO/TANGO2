// 벤치마크 17 메트릭 정본(id = llm_evaluation BE/컨테이너와 일치) + 포맷 헬퍼.
// 프로젝트 상세의 벤치마크 설정(BenchmarkRunConfig)·결과(BenchmarkResultView) 공용 —
// 구 standalone BenchmarkEvaluation 페이지에서 추출(중복 제거).
export const METRICS = [
  { id: 'accuracy', label: 'Accuracy', desc: '전체 정답률' },
  { id: 'f1', label: 'F1 Score', desc: 'Precision과 Recall의 조화평균' },
  { id: 'acc_norm', label: 'ACC_NORM', desc: '정규화된 정확도' },
  { id: 'arc', label: 'ARC', desc: 'AI2 Reasoning Challenge' },
  { id: 'kobest', label: 'KoBEST', desc: '한국어 NLU 벤치마크' },
  { id: 'mmlu', label: 'MMLU', desc: '다분야 언어 이해 (57개 과목)' },
  { id: 'hellaswag', label: 'HellaSwag', desc: '상식 추론 — 문장 완성' },
  { id: 'winogrande', label: 'WinoGrande', desc: '상식 추론 — 대명사 해소' },
  { id: 'gsm8k', label: 'GSM8K', desc: '초등 수학 문제 풀기' },
  { id: 'truthfulqa', label: 'TruthfulQA', desc: '사실 정확성 평가' },
  { id: 'boolq', label: 'BoolQ', desc: '예/아니오 질의응답' },
  { id: 'humaneval', label: 'HumanEval', desc: '코드 생성 능력 평가' },
  { id: 'meteor', label: 'METEOR', desc: '번역/생성 품질 — 단어 정렬 기반' },
  { id: 'cider', label: 'CIDEr', desc: '이미지 캡셔닝 품질 — TF-IDF 가중치' },
  { id: 'spice', label: 'SPICE', desc: '장면 그래프 기반 의미 유사도' },
  { id: 'bleu', label: 'BLEU', desc: 'N-gram 정밀도 기반 번역 품질' },
  { id: 'rouge', label: 'ROUGE-L', desc: '최장 공통 부분 수열 기반 요약 품질' },
];

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
