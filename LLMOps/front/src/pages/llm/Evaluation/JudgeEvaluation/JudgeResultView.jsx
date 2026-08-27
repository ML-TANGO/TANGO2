import BenchmarkResultView from '../BenchmarkEvaluation/BenchmarkResultView';

// LLM 심사 런 결과 뷰(프로젝트 상세 진입).
//
// 심사 런은 벤치마크 런이다 — runBenchmark 로 나가고 eval_result 에 같은 스키마로 남는다.
// 그래서 결과도 벤치마크 결과 뷰가 그대로 읽는다: getEvalResult 폴링, metrics.logickor 의
// 6영역 × 2턴 격자(막대 + 레이더 + 영역 표), judge_single / judge_multi / judge_overall
// 지표 카드, 그리고 "어느 심판이 몇 문항을 채점했나"(채점 구성)까지 이미 있다.
//
// 여기서 다시 그리지 않는 이유는 **평행 구현이 곧 드리프트**이기 때문이다. 종전 이 파일은
// judge_accuracy 류 기준 4종을 표로 세웠는데, 그 기준은 mock 채점의 산물이라 실채점으로
// 갈아탄 지금 표시할 값 자체가 없다. 같은 숫자를 두 화면이 서로 다른 규칙으로 그리면
// (등급 임계값·소수 자릿수·척도) 어느 쪽이 맞는지 알 수 없게 된다.
//
// 얇은 어댑터로 남기는 이유: 라우팅은 유형별로 갈린다(정답 대조 런은 독립 페이지,
// 심사 런은 프로젝트 상세 안). 유형이 다시 갈라질 때 손댈 자리가 여기다.
const JudgeResultView = ({ modelId, jobId, onComplete }) => (
  <BenchmarkResultView
    modelId={modelId}
    jobId={jobId}
    onComplete={onComplete}
  />
);

export default JudgeResultView;
