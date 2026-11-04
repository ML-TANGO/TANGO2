// LogicKor 결과 화면 전용 파생값. 소스 모듈의 웹 콘솔(Evaluation/Logickor_web/web/index.html)
// 이 결과 패널에서 쓰는 계산을 그대로 옮긴 것이다 — 등급 임계값·차이 부호·소수 2자리 고정.
// 채점 자체는 컨테이너(scoring.py)가 하고, 여기서는 표시용 파생만 만든다.

// 영역 등급 임계값. 소스: verdict(avg) — avg = (single + multi) / 2.
// 값과 경계를 바꾸면 소스 콘솔과 화면 판정이 갈리므로 함께 움직여야 한다.
export const VERDICT_RULES = [
  { min: 7.5, key: 'good', badge: 'green' },
  { min: 6.5, key: 'ok', badge: 'blue' },
  { min: -Infinity, key: 'mid', badge: 'gray' },
];

// 영역 평균 → { key, badge }. key 는 i18n 키(evaluation.bench.verdict*)로 이어진다.
export const judgeVerdict = (avg) => {
  const n = Number(avg);
  if (!Number.isFinite(n)) return null;
  return VERDICT_RULES.find((r) => n >= r.min) || null;
};

// 심판 점수는 소수 2자리 고정. 공용 fmt 는 정수를 '8' 로 떨어뜨려(8.00 아님) 표에서
// 자릿수가 흔들리므로, 격자 표시에는 이쪽을 쓴다.
export const fmt2 = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : '-';
};

// 멀티턴 − 싱글턴. 부호를 보이게 찍는다(소스와 동일한 ±0.01 데드존).
const DIFF_DEADZONE = 0.001;

export const diffText = (multi, single) => {
  const d = Number(multi) - Number(single);
  if (!Number.isFinite(d)) return '-';
  return `${d > 0 ? '+' : ''}${d.toFixed(2)}`;
};

export const diffTone = (multi, single) => {
  const d = Number(multi) - Number(single);
  if (!Number.isFinite(d)) return 'zero';
  if (d > DIFF_DEADZONE) return 'pos';
  if (d < -DIFF_DEADZONE) return 'neg';
  return 'zero';
};

// SVG(레이더)는 scss 변수를 못 읽어 리터럴이 필요하다. 광 테마 팔레트와 짝을 맞춘 값이며,
// 짝이 되는 막대 색은 BenchmarkEvaluation.module.scss 의 .cat-fill-* 에 있다.
// 바꿀 때 두 곳을 같이 고쳐야 한다.
export const TURN_COLOR = {
  single: '#2d76f8', // $primary-color ($blue104)
  multi: '#439f6e', // $lime604
};

export const RADAR_INK = {
  grid: '#dbdbdb', // $mono203
  label: '#747474', // $mono205
};
