// SDS external(recipe) 학습 payload 조립 — **순수 모듈**.
//
// 왜 분리했나: 조립이 컴포넌트 경계를 가로질러 2단으로 쪼개져 있었다.
//   자식(RecipePipeline.handleRun) 이 FE-내부 마커 `_resume_checkpoint` 를 심고
//   부모(SDSExternalFineTuningView.launchPhase) 가 그것을 파트너 키
//   (`resume_lora_path`/`projector_path`) 로 번역하는 **암묵 프로토콜**이었다.
//   이 모듈이 그 프로토콜을 명시적 함수 계약으로 고정한다:
//     mergePhaseParams()  = 마커를 **심는** 단(자식 책임)
//     applyChaining()     = 마커를 **번역하고 제거하는** 단(부모 책임)
//   마커 이름(`_resume_checkpoint`)과 번역 규칙은 계약이므로 바꾸면 안 된다.
//
// 계약 주의(파트너 422 표면): `phase.params` 는 플랫폼 매니페스트 스키마에서
// 검증되지 않고(Dict[str, Any]) 예약키 3종(`_dataset`/`_base_model`/
// `_built_in_checkpoint`)만 플랫폼이 소비·제거한 뒤 나머지 전부가 파트너
// `/train` 의 `TrainParams`(Pydantic) 로 직행한다. 즉 **키 집합이 곧 계약**이다.
// `save_steps`/`eval_steps`/`logging_steps`/`save_total_limit` 4키는 레시피에
// 없어도 `CKPT_DEFAULTS` 로 무조건 주입되는데, 이는 현재 동작을 **의도적으로
// 보존**한 것이다(결정 D1 — 조이기는 파트너 스키마 확인 후 별도 티켓).
//
// ⚠️ 순수성 불변식: React / 네트워크 / `@src` alias / 어떤 import 도 금지.
// plain `node` 로 그대로 import 해 legacy 스냅샷과 대조하는 차분 검증
// (게이트 1)의 전제 조건이다. alias 가 하나라도 섞이면 그 게이트가 무력화된다.

/** 하이퍼파라미터 슬라이더 스펙 — params 에 실제 존재하는 키만 렌더(제너릭). */
export const HP_SPECS = [
  {
    key: 'learning_rate',
    label: 'Learning Rate',
    min: 0.000001,
    max: 0.01,
    step: 0.000001,
    exp: true,
  },
  { key: 'num_epochs', label: '에포크 수', min: 1, max: 20, step: 1 },
  { key: 'batch_size', label: '배치 크기', min: 1, max: 32, step: 1 },
  { key: 'grad_accum', label: 'Grad Accum', min: 1, max: 32, step: 1 },
  { key: 'lora_r', label: 'LoRA Rank (r)', min: 4, max: 128, step: 4 },
  { key: 'lora_alpha', label: 'LoRA Alpha', min: 8, max: 256, step: 8 },
  { key: 'max_steps', label: 'Max Steps', min: 0, max: 20000, step: 100 },
];

export const HP_KEYS = HP_SPECS.map((s) => s.key);

/** 체크포인트 설정 — 이름(text) + step 제어(num). */
export const CKPT_NUM_SPECS = [
  { key: 'save_steps', label: 'Save Steps', min: 0, max: 5000, step: 50 },
  { key: 'eval_steps', label: 'Eval Steps', min: 0, max: 5000, step: 50 },
  { key: 'logging_steps', label: 'Logging Steps', min: 0, max: 1000, step: 10 },
  {
    key: 'save_total_limit',
    label: '최대 보관 개수',
    min: 1,
    max: 10,
    step: 1,
  },
];

/**
 * 레시피에 해당 키가 없을 때 시드되는 기본값.
 * ⚠️ 이 4키는 결과 params 에서 사라지면 안 된다(결정 D1). 차분 검증 스크립트에
 * 전용 케이스가 있어 무심코 "정리" 하면 실패로 잡힌다.
 */
export const CKPT_DEFAULTS = {
  save_steps: 500,
  eval_steps: 500,
  logging_steps: 10,
  save_total_limit: 3,
};

/** 빈 문자열/null/NaN 은 undefined(=오버레이 안 함) 로 접는다. */
const toNum = (v) =>
  v === '' || v === null || v === undefined || Number.isNaN(Number(v))
    ? undefined
    : Number(v);

/**
 * P1 — phase.params → 편집 폼 시드.
 * HP 키는 **존재할 때만** 넣는다(ModelRangeBar 의 `value=0` 기본값 스냅 회피).
 * 체크포인트 4키는 없으면 CKPT_DEFAULTS 로 채운다.
 */
export const buildPhaseForm = (params = {}) => {
  const form = {};
  HP_KEYS.forEach((key) => {
    if (params[key] !== undefined && params[key] !== null) {
      form[key] = Number(params[key]);
    }
  });
  form.output_checkpoint_name =
    typeof params.output_checkpoint_name === 'string'
      ? params.output_checkpoint_name
      : '';
  CKPT_NUM_SPECS.forEach(({ key }) => {
    form[key] =
      params[key] !== undefined && params[key] !== null
        ? Number(params[key])
        : CKPT_DEFAULTS[key];
  });
  return form;
};

/**
 * P2 — 편집 폼을 phase.params 위에 오버레이.
 * 숫자 HP/step 과 체크포인트 이름만 덮고 나머지(경로·phase·scenario·chain)는
 * pass-through. `resumeSelection` 이 있으면 FE-내부 마커를 **심는다** —
 * 번역은 applyChaining() 담당(2단 프로토콜의 1단).
 */
export const mergePhaseParams = ({ phaseParams, form, resumeSelection }) => {
  const f = form || {};
  const merged = { ...(phaseParams || {}) };
  [...HP_KEYS, ...CKPT_NUM_SPECS.map((s) => s.key)].forEach((key) => {
    const n = toNum(f[key]);
    if (n !== undefined) merged[key] = n;
  });
  const name = (f.output_checkpoint_name || '').trim();
  if (name) merged.output_checkpoint_name = name; // 빈값이 필수키를 덮지 않도록
  if (resumeSelection) merged._resume_checkpoint = resumeSelection;
  return merged;
};

/**
 * P3 + P4 — 체이닝 해소 + 마커 번역(2단 프로토콜의 2단).
 *
 * 순서 불변식(절대 역전 금지):
 *   1) chain_inputs 템플릿 치환({checkpoint_name} → 선행 커밋명)
 *   2) `_base_model` 주입 — 1) 뒤라서 레시피가 chain_inputs 로 예약키를
 *      덮어써 commit_models 마운트를 무력화할 수 없다.
 *   3) `_resume_checkpoint` 마커 번역 — 2) 뒤라서 사용자의 "이어서 학습"
 *      선택이 자동 체인을 override 한다. 마커는 파트너로 보내지 않는다(delete).
 *
 * 토스트/i18n 을 호출하지 않고 error code 만 돌려준다(순수성).
 * @returns {{ok: true, params: object} | {ok: false, code: 'CHAIN_MISSING'}}
 */
export const applyChaining = ({
  params,
  phase,
  phaseCommitMap,
  baseModelName,
}) => {
  const out = { ...(params || {}) };
  if (phase && phase.chain_from) {
    const priorCommit = (phaseCommitMap || {})[phase.chain_from];
    if (!priorCommit) return { ok: false, code: 'CHAIN_MISSING' };
    const chainInputs = phase.chain_inputs || {};
    Object.keys(chainInputs).forEach((key) => {
      out[key] = String(chainInputs[key]).replace(
        /\{checkpoint_name\}/g,
        priorCommit,
      );
    });
    if (baseModelName) out._base_model = { name: baseModelName };
  }
  if (out._resume_checkpoint) {
    const rel = String(out._resume_checkpoint);
    out.resume_lora_path = `/models/checkpoints/${rel}`;
    out.projector_path = `/models/checkpoints/${rel}/projector.bin`;
    delete out._resume_checkpoint;
    // 그 체크포인트가 있는 commit_models 를 /models/checkpoints 로 마운트하도록
    // _base_model 보장(chain_from 없는 phase 에서도).
    if (baseModelName && !out._base_model) {
      out._base_model = { name: baseModelName };
    }
  }
  return { ok: true, params: out };
};

/** P5 — BFF `POST external/jobs` 봉투. 키 이름·캐스팅 규칙 무변경. */
export const buildExternalJobBody = ({
  manifestName,
  manifestVersion,
  workspaceId,
  namespace,
  params,
  instanceId,
  instanceCount,
  gpuCount,
  modelId,
  outputSubdir,
}) => ({
  manifest_name: manifestName,
  manifest_version: manifestVersion,
  workspace_id: Number(workspaceId),
  namespace: String(namespace === null || namespace === undefined ? '' : namespace).trim(),
  params,
  instance_id: instanceId,
  instance_count: parseInt(instanceCount, 10),
  gpu_count: parseInt(gpuCount, 10),
  platform_model_id: Number(modelId),
  output_subdir: outputSubdir || null,
});

/**
 * P6 — 비-recipe(단일 launch) 경로의 raw params textarea 파싱.
 * 객체가 아니면(null/배열/깨진 JSON) 거부. `output_checkpoint_name` 에서
 * output_subdir 을 파생한다(partner-specific 출력 폴더 이름 키).
 * @returns {{ok: true, params: object, outputSubdir: string|null}
 *          | {ok: false, code: 'INVALID_JSON'}}
 */
export const parseRawParams = (text) => {
  let parsed;
  try {
    parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('not an object');
    }
  } catch (_) {
    return { ok: false, code: 'INVALID_JSON' };
  }
  const outputSubdir =
    typeof parsed.output_checkpoint_name === 'string'
      ? parsed.output_checkpoint_name.trim()
      : null;
  return { ok: true, params: parsed, outputSubdir };
};
