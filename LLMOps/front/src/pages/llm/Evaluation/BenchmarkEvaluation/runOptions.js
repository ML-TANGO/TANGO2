// 실채점 컨테이너(LogicKor) 실행 옵션 카탈로그 — 경계·전략 목록은 BE
// llm_evaluation constants.py 의 LOGICKOR_* 와 **같은 값**이어야 한다. 어긋나면 FE 가
// 통과시킨 값이 서버에서 422 로 되돌아온다.
//
// ⚠️ seed 는 없다. 생성(generate.py temperature=0)·심판(judge.py temperature=0.0) 둘 다
//    greedy 디코딩이라 시드가 바꿀 난수가 존재하지 않는다 — 노브를 만들면 아무 것도
//    하지 않는 컨트롤이 된다. 런 간 변동을 보려면 컨테이너 샘플링부터 바꿔야 한다.
// ⚠️ hf_token 은 컨테이너가 받지만 시크릿이라 이 경로로 노출하지 않는다.

// 이 옵션들을 소유한 벤치마크. 실채점 벤치마크라고 다 해당하는 게 아니다 — MixATIS 는
// 심판 LLM 없이 정답 대조로 채점하므로 심판·전략 옵션에 대응물이 없다. 패널 노출과 전송을
// 이 id 로 좁힌다(BE 도 manifest_key == 'LOGICKOR' 로 같은 범위를 강제한다).
export const RUN_OPTIONS_BENCHMARK_ID = 'logickor';

// 프롬프트 전략 — ETRI 원본 templates.PROMPT_STRATEGY 키. 열거형이라 '미지정'을 두지 않고
// 정본 기본값(default)을 선택 상태로 두고 항상 보낸다.
export const STRATEGIES = [
  { value: 'default', label: '기본 (default)' },
  { value: '1-shot', label: '1-shot' },
  { value: 'cot-1-shot', label: 'cot-1-shot' },
];
export const DEFAULT_STRATEGY = 'default';

// 숫자·문자 옵션은 "비우면 컨테이너 기본값" 규약이다. 기본값을 FE 가 들고 있다가 컨테이너와
// 어긋나는 것을 막으려고, 값을 복제하지 않고 placeholder 로만 안내한다.
export const MODEL_LEN_MIN = 512;
export const MODEL_LEN_MAX = 32768;
export const JUDGE_MAX_OUTPUT_MIN = 64;
export const JUDGE_MAX_OUTPUT_MAX = 8192;

// 심판 모델은 서버 화이트리스트의 id 다(getBenchmarkJudgeModels). 자유 입력이 아니라
// 목록에서 고르는 값이라 FE 형식 검증이 필요 없다 — 유효성은 목록 자체가 보장하고,
// 서버도 같은 화이트리스트로 다시 막는다.

// 빈 문자열 → 미지정(요청에서 제외). 숫자 문자열 → 정수.
const asInt = (raw) => {
  const s = String(raw ?? '').trim();
  if (s === '') return null;
  return /^\d+$/.test(s) ? Number(s) : NaN;
};

// 입력 상태 → { ok, options } 또는 { ok:false, errorKey, min?, max? }.
// errorKey 는 i18n 키(어느 칸이 틀렸는지), min/max 는 그 문구에 끼울 실제 경계다 —
// 경계 숫자를 번역 문자열에 복제하지 않기 위해 값으로 넘긴다.
// 유효한 값만 options 에 담고 미지정은 빼서 컨테이너 기본값이 그대로 쓰이게 한다.
export const buildRunOptions = ({
  strategy,
  generateModelLen,
  judgeModel,
  judgeModelLen,
  judgeMaxOutputTokens,
  withGenerate,
}) => {
  const options = {};

  // 생성 옵션은 체크포인트를 골라 생성 모드로 갈 때만 의미가 있다.
  if (withGenerate) {
    options.strategy = strategy || DEFAULT_STRATEGY;
    const genLen = asInt(generateModelLen);
    const lenBounds = { min: MODEL_LEN_MIN, max: MODEL_LEN_MAX };
    if (Number.isNaN(genLen)) return { ok: false, errorKey: 'genLen', ...lenBounds };
    if (genLen !== null) {
      if (genLen < MODEL_LEN_MIN || genLen > MODEL_LEN_MAX) {
        return { ok: false, errorKey: 'genLen', ...lenBounds };
      }
      options.generate_model_len = genLen;
    }
  }

  const model = String(judgeModel ?? '').trim();
  if (model !== '') options.judge_model = model;

  const judgeLen = asInt(judgeModelLen);
  if (Number.isNaN(judgeLen)) {
    return { ok: false, errorKey: 'judgeLen', min: MODEL_LEN_MIN, max: MODEL_LEN_MAX };
  }
  if (judgeLen !== null) {
    if (judgeLen < MODEL_LEN_MIN || judgeLen > MODEL_LEN_MAX) {
      return { ok: false, errorKey: 'judgeLen', min: MODEL_LEN_MIN, max: MODEL_LEN_MAX };
    }
    options.judge_model_len = judgeLen;
  }

  const maxOut = asInt(judgeMaxOutputTokens);
  if (Number.isNaN(maxOut)) {
    return {
      ok: false, errorKey: 'judgeMaxOut',
      min: JUDGE_MAX_OUTPUT_MIN, max: JUDGE_MAX_OUTPUT_MAX,
    };
  }
  if (maxOut !== null) {
    if (maxOut < JUDGE_MAX_OUTPUT_MIN || maxOut > JUDGE_MAX_OUTPUT_MAX) {
      return {
        ok: false, errorKey: 'judgeMaxOut',
        min: JUDGE_MAX_OUTPUT_MIN, max: JUDGE_MAX_OUTPUT_MAX,
      };
    }
    options.judge_max_output_tokens = maxOut;
  }

  return { ok: true, options };
};
