// 벤치마크 결과 폴링 정책 — 런 1건 결과 화면(BenchmarkResultView)과 실행 요약 화면
// (BenchmarkBatchPage)이 같은 값을 쓴다(둘이 따로 두면 한쪽만 끊기는 시점이 어긋난다).
//
// 폴링 예산은 "시도 횟수"가 아니라 "경과 시간"으로 잡는다. 벤치마크 런은 채점기에 따라
// 소요가 두 자릿수 배 차이 난다 — mock 은 10초(evaluate_benchmark_mock)인데 LogicKor
// 실채점은 기동에만 240초, 생성+심판까지 3600초다(evaluate_logickor_judge manifest
// capabilities). 40회×3초=120초 고정 예산은 LogicKor 런이 기동을 마치기도 전에 끊겨서
// 성공한 런조차 화면에서는 늘 '대기 시간 초과'로 보였다.
// 간격은 초반 촘촘 → 후반 성글게(backoff) 둔다. mock 의 응답성은 그대로 두면서 장시간
// 런의 요청 수만 줄인다(4시간 완주 시 약 500회).
// 가장 긴 채점기는 evaluate-lmeval 이다 — KMMLU 전체가 8B 에서 3시간 가까이 걸려 매니페스트
// timeout_seconds 가 36000(10h)이고 기동이 180초다. 그보다 먼저 끊기면 성공할 런도 화면에서는
// '대기 시간 초과'로 보인다(폴링이 멈춰도 런은 계속 돌고 이력에서 다시 열면 이어 받는다).
export const POLL_DEADLINE_MS = 11 * 60 * 60 * 1000; // 매니페스트 timeout(36000s) + 기동 + 여유

export const pollIntervalMs = (elapsedMs) => {
  if (elapsedMs < 60 * 1000) return 3000; // 첫 1분 — mock 완주·기동 실패를 즉시 반영
  if (elapsedMs < 5 * 60 * 1000) return 10 * 1000; // ~5분 — 실채점 컨테이너 기동 구간
  return 30 * 1000; // 이후 — 생성·심판 구간(수십 분)
};
