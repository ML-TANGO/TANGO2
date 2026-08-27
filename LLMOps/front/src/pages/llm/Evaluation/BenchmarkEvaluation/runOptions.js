// LLM 심사(LogicKor) 실채점 컨테이너 실행 옵션.
//
// ⚠️ 이 옵션들은 **LLM 심사 전용**이다. 정답 대조 평가(BenchmarkRunConfig)는 심판이 없어
//    대응물 자체가 없고, 실어 보내도 BE 가 manifest_key == 'LOGICKOR' 밖에서는 조용히
//    버린다 — 화면에는 노브가 있는데 실행에는 영향이 없는 상태가 되므로 그 경로에서는
//    아예 만들지 않는다(BenchmarkRunConfig 는 이 모듈을 import 하지 않는다).
//
// ⚠️ 와이어 포맷은 **평면**이다 — BenchmarkRunBody 는 strategy / judge_max_output_tokens 를
//    최상위 필드로 받고, route.py 가 그것을 run_options 딕트로 묶어 서비스에 넘긴다.
//    여기서 만든 객체를 body 에 그대로 펼쳐야 하며(`...options`), run_options 로 감싸
//    보내면 Pydantic 이 조용히 버려 "설정했는데 컨테이너 기본값으로 돈" 런이 된다.
//
// 심판 자체(judge_model)는 여기 없다 — 심판은 **떠 있는 배포**로 일원화했다
//   (judge_playground_id). 내장 심판 폴백 API 는 BE 에 남아 있지만 화면에서는 감춘다:
//   컨테이너가 GPU 를 한 장 더 잡는 경로를 사용자가 모르는 채 고르게 두지 않는다.
// 컨텍스트 길이(generate_model_len / judge_model_len)도 노출하지 않는다 — 전부 optional 이라
//   안 보내면 컨테이너 기본값(생성 4096 / 심판 8192)이 그대로 쓰이고, 되살리려면 숫자 입력
//   두 칸을 더 세워야 한다.

// 이 옵션들을 소유한 벤치마크. BE 도 manifest_key == 'LOGICKOR' 로 같은 범위를 강제한다.
export const RUN_OPTIONS_BENCHMARK_ID = 'logickor';

// 프롬프트 전략 — BE constants.LOGICKOR_STRATEGIES 와 같은 집합이어야 한다.
// 목록에 없는 값은 422 로 거절된다(dto._validate_strategy).
export const JUDGE_STRATEGIES = ['default', '1-shot', 'cot-1-shot'];

// 심판 1회 출력 상한(토큰) — BE constants.LOGICKOR_JUDGE_MAX_OUTPUT_MIN/MAX 와 같은 범위.
export const JUDGE_MAX_OUTPUT_MIN = 64;
export const JUDGE_MAX_OUTPUT_MAX = 8192;

// 정수 범위 파서. 빈 값은 오류가 아니라 "미지정"이다 — 미지정이면 컨테이너 기본값이 쓰인다
// (기본값을 FE 가 복제해 두지 않는 이유: 컨테이너가 바꾸면 화면이 거짓말을 하게 된다).
const parseBounded = (raw, min, max) => {
  const text = String(raw ?? '').trim();
  if (text === '') return { ok: true, value: null };
  if (!/^\d+$/.test(text)) return { ok: false };
  const value = Number(text);
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    return { ok: false };
  }
  return { ok: true, value };
};

// 입력 상태 → { ok:true, options } 또는 { ok:false, errorKey }.
// errorKey 는 i18n 키 꼬리(evaluation.bench.optErr.<errorKey>)로 그대로 이어진다.
export const buildRunOptions = ({ strategy, judgeMaxOutputTokens }) => {
  const options = {};

  const picked = String(strategy ?? '').trim();
  if (picked !== '') {
    // 목록 밖 전략은 서버가 422 로 거절한다 — 여기서 먼저 잡아 어느 칸이 문제인지 보인다.
    if (!JUDGE_STRATEGIES.includes(picked)) {
      return { ok: false, errorKey: 'strategy' };
    }
    options.strategy = picked;
  }

  const maxOut = parseBounded(
    judgeMaxOutputTokens,
    JUDGE_MAX_OUTPUT_MIN,
    JUDGE_MAX_OUTPUT_MAX,
  );
  if (!maxOut.ok) return { ok: false, errorKey: 'judgeMaxOut' };
  if (maxOut.value != null) options.judge_max_output_tokens = maxOut.value;

  return { ok: true, options };
};
