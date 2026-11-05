// 우측 모니터(FineTuningGraph) props 정규화 — 순수 모듈.
//
// SDS 두 화면은 모니터 데이터를 **서로 다른 소스**에서 얻는다:
//   external SDS — 뷰가 직접 `useSSEStatus/Time/Graph(externalJobId, 'external')` 구독
//   internal VLM — 부모 FineTuning.jsx 가 `(modelId, 'internal')` 로 구독해 props 로 내려줌
// 정규화 지점을 이 한 곳으로 만들어 두 화면의 우측 파리티를 코드로 보장한다.
// (골격 컴포넌트는 SSE 를 절대 구독하지 않는다 — 이중 구독 시 external 모델에서
//  internal SSE 가 동시에 열려 잘못된 상태로 화면이 덮인다.)
//
// ⚠️ `checkpoints` 는 하우스 `FineTuningGraph` 가 이미 받는 prop 이다. external 은
// 소스가 없어 항상 undefined 이며, prop 부재와 undefined 는 destructuring 상
// 동일하므로 표시 결과가 달라지지 않는다(현재 동작 보존).
//
// ⚠️ 순수성 불변식: React / 네트워크 / `@src` alias / 어떤 import 도 금지.

/** @returns FineTuningGraph 에 그대로 spread 할 수 있는 props 객체. */
export const toMonitorProps = ({
  fineStatus,
  graphData,
  progressData,
  checkpoints,
  fineTuningData,
}) => ({
  fineStatus,
  data: graphData,
  progressData,
  checkpoints,
  fineTuningData,
  fineTuningType: 1,
});
