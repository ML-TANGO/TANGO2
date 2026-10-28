/**
 * SDS 학습 모니터의 진행률 표시 규칙 (외부 recipe / 내부 멀티모달 공용).
 *
 * BE sse-time 의 `percent` 를 그대로 `Math.floor` 하면, 스텝 수가 큰 런
 * (예: cc3m LoRA = 111,633 스텝 ≈ 6일)에서 첫 수 시간 동안 계속 `0%` 로 보여
 * 학습이 멈춘 것처럼 읽힌다. 1% 미만 구간만 소수 2자리로 열어 진행 중임을
 * 드러내고, 1% 이상은 기존처럼 정수로 유지한다(형제 화면 ExternalTraining 이
 * 쓰는 소수 2자리 정밀도와 동일한 자릿수).
 */

/** 0~100 으로 clamp 한 숫자 진행률. 값이 없으면 0. (프로그레스 바 width 용) */
export const toPercentValue = (percent) =>
  Number.isFinite(percent) ? Math.min(Math.max(percent, 0), 100) : 0;

/** 화면에 찍을 진행률 문자열 — `%` 기호는 호출부가 붙인다. */
export const formatPercentLabel = (percent) => {
  const value = toPercentValue(percent);
  return value > 0 && value < 1 ? value.toFixed(2) : String(Math.floor(value));
};
