// 메트릭 정본(점수 함수) — id = llm_evaluation BE constants.METRIC_IDS + 채점 컨테이너 일치
// (BE 테스트 test_benchmark_catalog.py 가 METRIC_IDS ⊆ 이 목록을 대조한다).
// 벤치마크(ARC·MMLU…) 와 분리된 "채점 방식"만 담는다. 벤치마크 카탈로그는 benchmarks.js.
//   descKey = 지표 정의 문구의 i18n 키 — 데이터 모듈이라 t() 를 부를 수 없으므로 키만 담고
//   렌더하는 쪽(결과 화면의 지표 정의 열·점수 카드)에서 읽는다. 문자열을 박아 두면 영어
//   로케일에서도 한국어가 그대로 나온다.
//   이름은 **둘 중 하나**를 갖는다 — Accuracy·F1·BLEU 처럼 번역할 것이 없는 고유명사/약어는
//   `label`(문자열, BENCHMARK_LABEL 과 같은 이유로 그대로 둔다), 번역이 필요한 것은
//   `labelKey`(i18n 키). 읽는 쪽은 반드시 metricLabel(t, id) 로 통일해서 읽는다 —
//   `.label` 을 직접 보면 labelKey 쪽 지표가 조용히 빈칸이 된다.
//   (수식 요약 formula·대표 벤치마크 태그 common 은 3단계 위저드와 함께 사라진 사문이라 뺐다.)
export const METRICS = [
  {
    id: 'accuracy',
    label: 'Accuracy',
    descKey: 'evaluation.bench.metricDef.accuracy',
  },
  {
    id: 'f1',
    label: 'F1 Score',
    descKey: 'evaluation.bench.metricDef.f1',
  },
  {
    id: 'acc_norm',
    label: 'ACC_NORM',
    descKey: 'evaluation.bench.metricDef.acc_norm',
  },
  {
    id: 'bleu',
    label: 'BLEU',
    descKey: 'evaluation.bench.metricDef.bleu',
  },
  {
    id: 'rouge',
    label: 'ROUGE-L',
    descKey: 'evaluation.bench.metricDef.rouge',
  },
  {
    id: 'meteor',
    label: 'METEOR',
    descKey: 'evaluation.bench.metricDef.meteor',
  },
  {
    id: 'cider',
    label: 'CIDEr',
    descKey: 'evaluation.bench.metricDef.cider',
  },
  {
    id: 'spice',
    label: 'SPICE',
    descKey: 'evaluation.bench.metricDef.spice',
  },
  // lm-eval 생성형 태스크의 정확 일치(KMMLU-Direct·SQuADv2·DROP)와 코드 통과율(HumanEval).
  // 채점기가 둘 다 0~100 으로 환산해 싣으므로 공용 기본 척도(100)를 그대로 쓴다.
  {
    id: 'exact_match',
    label: 'Exact Match',
    descKey: 'evaluation.bench.metricDef.exact_match',
  },
  {
    id: 'pass_at_1',
    label: 'pass@1',
    descKey: 'evaluation.bench.metricDef.pass_at_1',
  },
  // 심판 점수(1~10) — LogicKor 전용. 정답이 없는 생성형 벤치마크라 정답률 계열을 쓸 수
  // 없고 심판 LLM 의 점수가 유일한 채점 축이다. 셋의 차이는 "대표값을 어느 축으로 잡나"
  // 뿐이고(전체/1턴/2턴) 영역별·턴별 전체 점수는 어느 걸 골라도 함께 산출된다.
  // scaleMax=10 → 막대 폭 환산용(0~100 척도가 아니라, 8.1 이 8% 로 찌그러지는 것 방지).
  {
    id: 'judge_overall',
    labelKey: 'evaluation.bench.metricName.judge_overall',
    descKey: 'evaluation.bench.metricDef.judge_overall',
    scaleMax: 10,
  },
  {
    id: 'judge_single',
    labelKey: 'evaluation.bench.metricName.judge_single',
    descKey: 'evaluation.bench.metricDef.judge_single',
    scaleMax: 10,
  },
  {
    id: 'judge_multi',
    labelKey: 'evaluation.bench.metricName.judge_multi',
    descKey: 'evaluation.bench.metricDef.judge_multi',
    scaleMax: 10,
  },
  // MixATIS 4종. 넷 다 0~1 비율이라 scaleMax:1 이 필요하다 — 공용 기본값은 0~100
  // 척도여서, 안 주면 0.4855 를 0.49% 막대로 그린다(소스 콘솔은 x100 해 % 로 쓴다).
  // Joint 가 유독 낮은 건 결함이 아니라 정의다 — 의도집합과 슬롯집합을 **동시에**
  // 완전일치시켜야 1점이라, 슬롯이 5개면 5개 전부 값·이름이 맞아야 한다.
  {
    id: 'joint_acc',
    scaleMax: 1,
    labelKey: 'evaluation.bench.metricName.joint_acc',
    descKey: 'evaluation.bench.metricDef.joint_acc',
  },
  {
    id: 'intent_acc',
    scaleMax: 1,
    labelKey: 'evaluation.bench.metricName.intent_acc',
    descKey: 'evaluation.bench.metricDef.intent_acc',
  },
  {
    id: 'intent_f1',
    scaleMax: 1,
    labelKey: 'evaluation.bench.metricName.intent_f1',
    descKey: 'evaluation.bench.metricDef.intent_f1',
  },
  {
    id: 'slot_f1',
    scaleMax: 1,
    labelKey: 'evaluation.bench.metricName.slot_f1',
    descKey: 'evaluation.bench.metricDef.slot_f1',
  },
];

export const METRIC_MAP = Object.fromEntries(METRICS.map((m) => [m.id, m]));

// 지표 이름 — label(고유명사) | labelKey(번역) 중 있는 쪽을 읽는다.
// 모르는 지표(서버가 새 id 를 보냄)는 null 이라 호출부의 `|| id` 폴백이 그대로 산다.
// ⚠️ 종전의 METRIC_LABEL(id→문자열 맵)은 없앴다 — 일부만 문자열이 된 순간 그 맵은
//    labelKey 지표에서 조용히 undefined 를 내는 반쪽 맵이 되어 함정이 된다.
export const metricLabel = (t, metricId) => {
  const metric = METRIC_MAP[metricId];
  if (!metric) return null;
  return metric.labelKey ? t(metric.labelKey) : metric.label;
};

// 지표 정의 문구 — 카탈로그는 i18n 키만 담으므로 렌더하는 쪽이 t 를 넘겨 읽는다.
// 모르는 지표(서버가 새 id 를 보냄)는 빈 문자열 — 화면이 키 문자열을 그대로 보이지 않게.
export const metricDesc = (t, metricId) => {
  const key = METRIC_MAP[metricId]?.descKey;
  return key ? t(key) : '';
};

// 숫자 포맷 — 벤치마크 메트릭은 스케일 혼재(accuracy 0-100 vs perplexity 등)라 % 강제 X.
export const fmt = (v) => {
  if (v == null) return '-';
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
};

// 막대 폭은 0-100 클램프(비율 외 메트릭이 넘쳐 레이아웃 깨지는 것 방지 — 시각 근사).
// scaleMax 를 주면 그 척도를 100 기준으로 환산한다(심판 점수 1~10 → 8.1 을 81% 로).
// 인자를 안 주면 기존 동작(0-100 척도)과 동일하다.
export const barWidth = (v, scaleMax = 100) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  const max = Number(scaleMax) > 0 ? Number(scaleMax) : 100;
  return Math.max(0, Math.min(100, (n / max) * 100));
};

// 메트릭 id → 막대 환산에 쓸 척도 상한. 미등록 메트릭은 100(기존 동작).
export const scaleMaxFor = (metricId) => METRIC_MAP[metricId]?.scaleMax ?? 100;

// 지표 id → 표시 문자열. **척도를 통일하지 않는다** — 심판 점수는 `7.97 / 10`, 비율은
// `47.71%`, 0~100 계열은 `88.13` 으로 각자의 척도로 읽힌다. 한 단위로 환산해 버리면
// "8.19 점" 과 "81.9%" 가 같은 열에 섞여 무엇을 본 건지 알 수 없게 된다.
export const formatMetricValue = (metricId, value) => {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return '-';
  const max = scaleMaxFor(metricId);
  if (max === 1) return `${(n * 100).toFixed(2)}%`;
  if (max < 100) return `${n.toFixed(2)} / ${max}`;
  return n.toFixed(2);
};

// 정렬 전용 정규화 — 표시는 원 척도 그대로 두고, 비교만 만점 대비 비율로 한다.
// 안 맞추면 0~1 척도(joint_acc 0.4771)가 0~100 척도(88.13) 옆에서 늘 꼴찌로 가라앉아
// '점수' 정렬이 사실상 '척도' 정렬이 된다.
export const normalizedScore = (metricId, value) => {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return null;
  const max = scaleMaxFor(metricId);
  return max > 0 ? n / max : n;
};
