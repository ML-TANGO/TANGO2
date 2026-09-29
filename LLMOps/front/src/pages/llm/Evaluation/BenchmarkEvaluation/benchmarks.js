// 벤치마크 정본 — id = llm_evaluation BE constants.BENCHMARK_IDS + 채점 컨테이너(evaluate_lmeval
// registry.py · LogicKor · MixATIS)와 일치. BE 테스트(llm_evaluation/tests/test_benchmark_catalog.py)가
// 이 파일의 id·recommended 를 읽어 대조한다 — 형식(4칸 들여쓴 `id: '...'`)을 바꾸면 그 테스트도 고친다.
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
  { id: 'reading', labelKey: 'evaluation.bench.cat.reading' },
  { id: 'custom', labelKey: 'evaluation.bench.cat.custom' },
];

// ETRI 결과 화면(Evaluation/lmeval 대시보드)의 벤치마크 묶음 — 요약 카드·막대 색의 축이다.
// category(레이더 역량 축)와는 다른 축이다: 이건 "어느 벤치마크 계열인가"(영어 표준·한국어·생성형·
// 사용자 데이터)이고, category 는 "무슨 능력을 재나"(지식·추론·상식…)다. ETRI 는 KoBEST·KMMLU·
// HAE-RAE 를 한국어로 묶고 SQuADv2·TruthfulQA-gen·DROP 을 생성형으로 묶는다 — 그대로 따른다.
// HumanEval(코드 생성)은 ETRI 목록에 없어 생성형에, MixATIS 는 도메인 과제라 사용자(커스텀)에 둔다.
export const BENCHMARK_GROUPS = [
  { id: 'core_en', labelKey: 'evaluation.batch.group.core_en', color: 0 },
  { id: 'korean', labelKey: 'evaluation.batch.group.korean', color: 1 },
  { id: 'generative', labelKey: 'evaluation.batch.group.generative', color: 2 },
  { id: 'custom', labelKey: 'evaluation.batch.group.custom', color: 3 },
];

// recommended = 생략 시 채택할 기본 메트릭(BE constants.BENCHMARK_RECOMMENDED_METRIC 와 일치).
// metrics = 이 벤치마크의 채점기가 실제로 내는 축(BE constants.BENCHMARK_ALLOWED_METRICS 와 일치).
// scorer: 'lmeval' = lm-evaluation-harness 채점기(evaluate-lmeval / -code)로 가는 벤치마크. 이
//   채점기는 배포에 생성을 위임하지 못해(객관식은 보기별 로그확률이 필요한데 배포 shim 이 주지
//   않는다) **고른 배포가 서빙 중인 커밋을 자기 GPU 한 장에 올려** 채점한다 — 실행 화면이 GPU
//   현황·체크포인트 필수·문항 상한(sample_limit)을 세우는 조건이다.
export const BENCHMARKS = [
  {
    id: 'arc',
    label: 'ARC',
    descKey: 'evaluation.bench.benchDesc.arc',
    category: 'reasoning',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy', 'acc_norm'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'kobest',
    label: 'KoBEST',
    descKey: 'evaluation.bench.benchDesc.kobest',
    category: 'knowledge',
    group: 'korean',
    evalType: 'reference',
    recommended: 'f1',
    metrics: ['f1', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'mmlu',
    label: 'MMLU',
    descKey: 'evaluation.bench.benchDesc.mmlu',
    category: 'knowledge',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'hellaswag',
    label: 'HellaSwag',
    descKey: 'evaluation.bench.benchDesc.hellaswag',
    category: 'commonsense',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'winogrande',
    label: 'WinoGrande',
    descKey: 'evaluation.bench.benchDesc.winogrande',
    category: 'commonsense',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'gsm8k',
    label: 'GSM8K',
    descKey: 'evaluation.bench.benchDesc.gsm8k',
    category: 'math',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'truthfulqa',
    label: 'TruthfulQA',
    descKey: 'evaluation.bench.benchDesc.truthfulqa',
    category: 'safety',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'boolq',
    label: 'BoolQ',
    descKey: 'evaluation.bench.benchDesc.boolq',
    category: 'safety',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'humaneval',
    label: 'HumanEval',
    descKey: 'evaluation.bench.benchDesc.humaneval',
    category: 'code',
    group: 'generative',
    evalType: 'reference',
    // 코드 통과율(pass@1). 모델이 생성한 코드를 실제로 실행해 채점하므로 BE 가 격리된 전용
    // 채점기(evaluate-lmeval-code)로 보내고, 다른 벤치마크와 한 런에 섞지 않는다.
    recommended: 'pass_at_1',
    metrics: ['pass_at_1'],
    scorer: 'lmeval',
    real: true,
    executesCode: true,
  },
  // ── lm-eval 로 추가된 표준 벤치마크(2026-09-28) ──
  {
    id: 'arc_easy',
    label: 'ARC-Easy',
    descKey: 'evaluation.bench.benchDesc.arc_easy',
    category: 'reasoning',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'piqa',
    label: 'PIQA',
    descKey: 'evaluation.bench.benchDesc.piqa',
    category: 'commonsense',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'openbookqa',
    label: 'OpenBookQA',
    descKey: 'evaluation.bench.benchDesc.openbookqa',
    category: 'knowledge',
    group: 'core_en',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'kmmlu',
    label: 'KMMLU',
    descKey: 'evaluation.bench.benchDesc.kmmlu',
    category: 'knowledge',
    group: 'korean',
    evalType: 'reference',
    recommended: 'accuracy',
    metrics: ['accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'kmmlu_direct',
    label: 'KMMLU (Direct)',
    descKey: 'evaluation.bench.benchDesc.kmmlu_direct',
    category: 'knowledge',
    group: 'korean',
    evalType: 'reference',
    recommended: 'exact_match',
    metrics: ['exact_match'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'haerae',
    label: 'HAE-RAE Bench',
    descKey: 'evaluation.bench.benchDesc.haerae',
    category: 'knowledge',
    group: 'korean',
    evalType: 'reference',
    recommended: 'acc_norm',
    metrics: ['acc_norm', 'accuracy'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'squadv2',
    label: 'SQuAD v2',
    descKey: 'evaluation.bench.benchDesc.squadv2',
    category: 'reading',
    group: 'generative',
    evalType: 'reference',
    recommended: 'f1',
    metrics: ['f1', 'exact_match'],
    scorer: 'lmeval',
    real: true,
  },
  {
    id: 'truthfulqa_gen',
    label: 'TruthfulQA (gen)',
    descKey: 'evaluation.bench.benchDesc.truthfulqa_gen',
    category: 'safety',
    group: 'generative',
    evalType: 'reference',
    recommended: 'bleu',
    metrics: ['bleu', 'rouge'],
    scorer: 'lmeval',
    real: true,
  },
  {
    // upstream lm-eval drop 의 정답 템플릿 버그를 고친 수정본(drop_tango)으로 채점한다 —
    // 공개된 lm-eval DROP 수치와 직접 비교할 수 없다(설명 문구에 밝힌다).
    id: 'drop',
    label: 'DROP',
    descKey: 'evaluation.bench.benchDesc.drop',
    category: 'reading',
    group: 'generative',
    evalType: 'reference',
    recommended: 'f1',
    metrics: ['f1', 'exact_match'],
    scorer: 'lmeval',
    real: true,
  },
  {
    // 표준 문항이 아니라 **런에서 고른 데이터셋**(입력-정답 쌍)으로 생성한 뒤 채점한다.
    // 다른 벤치마크는 데이터셋 선택을 읽지 않는다(문항이 채점기 이미지에 있다) — 이것만 읽는다.
    id: 'custom',
    label: 'Custom Dataset',
    descKey: 'evaluation.bench.benchDesc.custom',
    category: 'custom',
    group: 'custom',
    evalType: 'reference',
    recommended: 'f1',
    metrics: ['f1', 'exact_match', 'bleu', 'rouge'],
    scorer: 'lmeval',
    real: true,
    usesDataset: true,
  },
  // 전용 채점기 벤치마크 — 위(lm-eval)와 채점 컨테이너가 다르다(배포에 생성을 위임한다).
  // 42문항 × 6영역 × 2턴을 심판 LLM 이 1~10 점으로 채점. 정답(reference)이 없어
  // accuracy/f1 계열은 계산 자체가 불가하고, 고를 수 있는 건 "어느 축을 대표값으로
  // 쓸지"(전체/1턴/2턴)뿐이다. 영역별 점수는 항상 함께 산출돼 결과 상세에 표시된다.
  {
    id: 'logickor',
    label: 'LogicKor',
    descKey: 'evaluation.bench.benchDesc.logickor',
    category: 'reasoning',
    group: 'korean',
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
    group: 'custom',
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
    // 그 형식을 **평가 직전에 같은 잡에서** 학습할 수 있다(채점기 evaluate-intent 0.2.0+
    // 의 train 단계). 켜면 배포 위임을 걷고 그 배포의 체크포인트를 마운트해 LoRA 를 짧게
    // 태운 뒤 로컬에서 생성·채점한다 — 학습 LoRA 를 원격 배포에 얹을 통로가 없어 두 경로는
    // 배타다(BE constants.FORMAT_TRAIN_MANIFEST_KEYS 와 같은 집합이어야 한다).
    supportsFormatTrain: true,
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

// lm-eval 채점기로 가는 벤치마크 — 로컬 가중치(GPU 1장)·체크포인트 필수·문항 상한 옵션.
// BE constants.LOCAL_WEIGHTS_MANIFEST_KEYS 로 라우팅되는 집합과 같아야 한다(sample_limit 을
// 그 밖의 채점기에 보내면 BE 가 거절한다).
export const LMEVAL_BENCHMARK_IDS = BENCHMARKS.filter(
  (b) => b.scorer === 'lmeval',
).map((b) => b.id);

// 런 데이터셋을 **읽지 않는** 벤치마크 — 문항이 채점 이미지에 구워져 있다. 이것만 고른 런은
// 데이터셋을 싣지 않는다(결과 머리에 채점에 안 쓴 데이터셋이 찍히지 않게). custom 은
// 데이터셋이 곧 평가 문항이라 빠진다. BE constants.DATASET_FREE_BENCHMARK_IDS 와 같은 집합이어야
// 한다(tests/test_benchmark_catalog.py 가 scorer·usesDataset 플래그로 대조한다).
export const DATASET_FREE_BENCHMARK_IDS = BENCHMARKS.filter(
  (b) => b.scorer === 'lmeval' && !b.usesDataset,
).map((b) => b.id);

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

// 그 형식 학습을 평가 런 안에서 돌릴 수 있는 벤치마크. 실행 화면이 '포맷 학습' 스위치를
// 세우는 조건이고, BE 도 같은 경계를 강제한다(FORMAT_TRAIN_MANIFEST_KEYS) — 지원하지 않는
// 벤치마크에 켜서 보내면 조용히 무시되는 대신 사유와 함께 거절된다.
export const FORMAT_TRAIN_BENCHMARK_IDS = BENCHMARKS.filter(
  (b) => b.supportsFormatTrain,
).map((b) => b.id);

// 추론을 한 번 더 돌려야 나오는 "생성 지표"(옵트인). 키 = 벤치마크 id, 값 = 그 벤치마크의
// metrics 중 생성 경로가 필요한 메트릭 id.
// 2026-09-28 부터 비어 있다 — TruthfulQA 의 BLEU/ROUGE 는 별도 벤치마크(truthfulqa_gen)가
// 되어 한 런이 한 채점 경로만 돈다. 옵트인 체크박스는 BE 에 전달된 적이 없었다(요청에 없음).
export const GENERATION_METRICS = {};

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
