// internal VLM(multimodal) 학습 요청 body — 순수 모듈.
//
// 수신처: `POST models/fine-tuning/run` → 내부 스케줄러 → 엔진
// (`llm_model_vlm_fine_tuning.py`). 하우스 텍스트 LLM 과 **같은** 엔드포인트라
// `fine_tuning_config` 봉투 형태를 유지해야 한다.
//
// ⚠️ 순수성 불변식: React / 네트워크 / `@src` alias / 어떤 import 도 금지
// (plain node 차분 검증의 전제).

/**
 * @param {object}   a
 * @param {number|string} a.modelId
 * @param {number}   a.modelDatasetId  바인딩된 model_datasets[0].id (없으면 0)
 * @param {*}        a.instanceId      FINETUNING_SETTING 모달 값(캐스팅 없음 — 원본 유지)
 * @param {*}        a.instanceCount
 * @param {*}        a.gpuCount
 * @param {object}   a.form            화면 로컬 state 묶음
 *   trainProj/trainLLM(boolean) · lr1/ep1(stage1) · lr2/ep2/bs2/wd2(stage2)
 *   loraR/loraA/loraD · loraTargets(Set|string[]) · maxSamples
 */
export const buildVlmRunBody = ({
  modelId,
  modelDatasetId,
  instanceId,
  instanceCount,
  gpuCount,
  form,
}) => {
  const {
    trainProj,
    trainLLM,
    lr1,
    ep1,
    lr2,
    ep2,
    bs2,
    wd2,
    loraR,
    loraA,
    loraD,
    loraTargets,
    maxSamples,
  } = form || {};
  // Set(화면 state) / Array 둘 다 수용 — 엔진은 콤마 구분 문자열을 받는다.
  const tgts = Array.from(loraTargets || []).join(',');
  return {
    model_id: parseInt(modelId, 10),
    model_dataset_id: modelDatasetId ?? 0,
    instance_id: instanceId,
    instance_count: instanceCount,
    gpu_count: gpuCount,
    fine_tuning_config: {
      fine_tuning_type: 'basic',
      vlm: 1,
      // 프로젝터 정렬(stage1) on/off → epoch 0 이면 스킵(엔진 지원). stage2(LM)는 항상 수행.
      vlm_stage1_epochs: trainProj ? Number(ep1) : 0,
      num_train_epochs: Number(ep2),
      used_lora: trainLLM ? 1 : 0,
      learning_rate: Number(lr2),
      vlm_stage1_lr: Number(lr1),
      vlm_weight_decay: Number(wd2),
      vlm_batch_size: Number(bs2),
      vlm_lora_r: Number(loraR),
      vlm_lora_alpha: Number(loraA),
      vlm_lora_dropout: Number(loraD),
      vlm_lora_target_modules: tgts,
      vlm_max_samples: Math.max(0, Number(maxSamples) || 0),
      cutoff_length: 512,
      gradient_accumulation_steps: 1,
      warmup_steps: 0,
    },
  };
};
