import { useCallback, useEffect, useRef, useState } from 'react';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import { getInstancesList } from '@src/apis/llm/model';
import { postDualSession } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './NewInferenceWizard.module.scss';

const cx = classNames.bind(style);

// 이중모델 추론 세션 생성 마법사(WBS 추론 4.2 / 4.3).
//   Step1 모델 구성(추론 모델 + 프롬프트 생성 모델) → Step2 자원 할당(실 인스턴스)
//   → Step3 확인·생성 → POST /playgrounds/dual-session (co-provision).
// ETRI 목업(NewInferenceWizard) UI 를 우리 실 BE(인스턴스·커밋)로 재배선.
const STEPS = ['모델 구성', '자원 할당', '확인 및 생성'];
const GPU_OPTIONS = [1, 2, 4];

const NewInferenceWizard = ({ wid, onClose, onCreate }) => {
  const [step, setStep] = useState(1);

  // Step1 — 모델 구성
  const [inferenceModel, setInferenceModel] = useState(null);
  const [inferenceModelData, setInferenceModelData] = useState(null);
  const [inferenceCommit, setInferenceCommit] = useState(null);
  const [promptModel, setPromptModel] = useState(null);
  const [promptModelData, setPromptModelData] = useState(null);
  const [promptCommit, setPromptCommit] = useState(null);

  // Step2 — 자원 할당(실 인스턴스)
  const [instances, setInstances] = useState([]);
  const [instanceId, setInstanceId] = useState(null);
  // 모델별 GPU 수(회의결정: LLM1/LLM2 각각 독립). 레플리카는 미노출 → 인스턴스 1개 내부 고정.
  const [promptGpuCount, setPromptGpuCount] = useState(1);
  const [inferenceGpuCount, setInferenceGpuCount] = useState(1);

  // Step3 — 세션명 + 생성
  const [sessionName, setSessionName] = useState('');
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false); // 인플라이트 락(state 지연으로 인한 더블서브밋 방지)

  // 생성 중에는 닫기 차단(요청 중 unmount → 응답 후 stale 네비게이션 방지)
  const handleClose = useCallback(() => {
    if (creatingRef.current) return;
    onClose?.();
  }, [onClose]);

  // Escape 로 닫기(모달 접근성)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [handleClose]);

  const fetchInstances = useCallback(async () => {
    if (!wid) return;
    const res = await getInstancesList(wid);
    if (res.status === STATUS_SUCCESS) {
      setInstances(Array.isArray(res.result) ? res.result : []);
    } else {
      errorToastMessage(res.error, res.message);
    }
  }, [wid]);

  useEffect(() => {
    fetchInstances();
  }, [fetchInstances]);

  const sameModel =
    inferenceModel != null && String(inferenceModel) === String(promptModel);
  const canStep1 = !!inferenceModel && !!promptModel && !sameModel;
  const canStep2 = !!instanceId;
  const canCreate = canStep1 && canStep2 && sessionName.trim().length > 0;

  const handleCreate = async () => {
    if (!canCreate || creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    try {
      const res = await postDualSession({
        workspace_id: wid,
        name: sessionName.trim(),
        prompt_gen_model_id: promptModel,
        inference_model_id: inferenceModel,
        model_instance_id: instanceId,
        prompt_gen_commit_id: promptCommit,
        inference_commit_id: inferenceCommit,
        prompt_gen_gpu_count: promptGpuCount,
        inference_gpu_count: inferenceGpuCount,
      });
      if (res.status === STATUS_SUCCESS) {
        onCreate?.(res.result);
        return;
      }
      errorToastMessage(res.error, res.message);
    } catch (err) {
      errorToastMessage(null, '세션 생성 중 오류가 발생했습니다.');
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  };

  const selectedInstance = instances.find(
    (i) => String(i.instance_id) === String(instanceId),
  );

  return (
    <div className={cx('overlay')} onClick={handleClose}>
      <div
        className={cx('wizard')}
        role='dialog'
        aria-modal='true'
        aria-labelledby='dual-wizard-title'
        onClick={(e) => e.stopPropagation()}
      >
        <div className={cx('header')}>
          <span className={cx('title')} id='dual-wizard-title'>
            새 이중모델 추론 세션
          </span>
          <button
            type='button'
            className={cx('close-btn')}
            onClick={handleClose}
          >
            ✕
          </button>
        </div>

        {/* 단계 표시 */}
        <div className={cx('step-bar')}>
          {STEPS.map((label, i) => (
            <div
              key={label}
              className={cx(
                'step-item',
                step === i + 1 && 'active',
                step > i + 1 && 'done',
              )}
            >
              <div className={cx('step-circle')}>
                {step > i + 1 ? '✓' : i + 1}
              </div>
              <span className={cx('step-label')}>{label}</span>
              {i < STEPS.length - 1 && (
                <div className={cx('step-line', step > i + 1 && 'filled')} />
              )}
            </div>
          ))}
        </div>

        <div className={cx('body')}>
          {/* Step 1 — 모델 구성 */}
          {step === 1 && (
            <>
              {/* 실행 순서(LLM1→LLM2)와 일치: 프롬프트 생성 모델을 먼저 배치 */}
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>
                  프롬프트 생성 모델 (LLM1)
                </h3>
                <ModelSelector
                  wid={wid}
                  selected={promptModel}
                  onSelect={(id, data) => {
                    setPromptModel(id);
                    setPromptModelData(data);
                    setPromptCommit(null);
                  }}
                  onCheckpointSelect={(id) => setPromptCommit(id)}
                />
              </div>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>추론 모델 (LLM2)</h3>
                <ModelSelector
                  wid={wid}
                  selected={inferenceModel}
                  onSelect={(id, data) => {
                    setInferenceModel(id);
                    setInferenceModelData(data);
                    setInferenceCommit(null);
                  }}
                  onCheckpointSelect={(id) => setInferenceCommit(id)}
                />
              </div>
              {sameModel && (
                <p className={cx('warn')}>
                  프롬프트 생성 모델과 추론 모델은 서로 달라야 합니다.
                </p>
              )}
            </>
          )}

          {/* Step 2 — 자원 할당 */}
          {step === 2 && (
            <>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>
                  인스턴스 (두 모델에 각각 적용)
                </h3>
                {instances.length === 0 ? (
                  <p className={cx('empty')}>
                    사용 가능한 인스턴스가 없습니다.
                  </p>
                ) : (
                  <div className={cx('res-grid')}>
                    {instances.map((ins) => (
                      <div
                        key={ins.instance_id}
                        className={cx(
                          'res-card',
                          String(instanceId) === String(ins.instance_id) &&
                            'selected',
                        )}
                        onClick={() => setInstanceId(ins.instance_id)}
                      >
                        <span className={cx('res-name')}>
                          {ins.instance_name}
                        </span>
                        <span className={cx('res-meta')}>
                          GPU {ins.gpu_allocate ?? 0}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>
                  프롬프트 생성 모델 (LLM1) GPU 수
                </h3>
                <div className={cx('chip-row')}>
                  {GPU_OPTIONS.map((g) => (
                    <div
                      key={g}
                      className={cx('chip', promptGpuCount === g && 'selected')}
                      onClick={() => setPromptGpuCount(g)}
                    >
                      {g}
                    </div>
                  ))}
                </div>
              </div>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>추론 모델 (LLM2) GPU 수</h3>
                <div className={cx('chip-row')}>
                  {GPU_OPTIONS.map((g) => (
                    <div
                      key={g}
                      className={cx(
                        'chip',
                        inferenceGpuCount === g && 'selected',
                      )}
                      onClick={() => setInferenceGpuCount(g)}
                    >
                      {g}
                    </div>
                  ))}
                </div>
              </div>
              <p className={cx('note')}>
                * 세션은 두 모델을 각각 배포하므로 GPU{' '}
                {promptGpuCount + inferenceGpuCount}장을 점유합니다 (프롬프트
                생성 {promptGpuCount}장 + 추론 {inferenceGpuCount}장).
              </p>
            </>
          )}

          {/* Step 3 — 확인 및 생성 */}
          {step === 3 && (
            <>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>세션 이름</h3>
                <input
                  className={cx('name-input')}
                  type='text'
                  maxLength={64}
                  aria-label='세션 이름'
                  placeholder='추론 세션 이름을 입력하세요'
                  value={sessionName}
                  onChange={(e) => setSessionName(e.target.value)}
                />
              </div>
              <div className={cx('summary')}>
                <div className={cx('s-row')}>
                  <span className={cx('s-key')}>프롬프트 생성 모델</span>
                  <span className={cx('s-val')}>
                    {promptModelData?.name ?? '-'}
                  </span>
                </div>
                <div className={cx('s-row')}>
                  <span className={cx('s-key')}>추론 모델</span>
                  <span className={cx('s-val')}>
                    {inferenceModelData?.name ?? '-'}
                  </span>
                </div>
                <div className={cx('s-row')}>
                  <span className={cx('s-key')}>인스턴스</span>
                  <span className={cx('s-val')}>
                    {selectedInstance?.instance_name ?? '-'}
                  </span>
                </div>
                <div className={cx('s-row')}>
                  <span className={cx('s-key')}>
                    GPU (프롬프트 생성 / 추론)
                  </span>
                  <span className={cx('s-val')}>
                    {promptGpuCount} / {inferenceGpuCount}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        <div className={cx('footer')}>
          {step > 1 && (
            <button
              type='button'
              className={cx('back-btn')}
              onClick={() => setStep((s) => s - 1)}
            >
              이전
            </button>
          )}
          <button
            type='button'
            className={cx('cancel-btn')}
            onClick={handleClose}
          >
            취소
          </button>
          {step < 3 ? (
            <button
              type='button'
              className={cx(
                'next-btn',
                ((step === 1 && !canStep1) || (step === 2 && !canStep2)) &&
                  'disabled',
              )}
              disabled={(step === 1 && !canStep1) || (step === 2 && !canStep2)}
              onClick={() => setStep((s) => s + 1)}
            >
              다음
            </button>
          ) : (
            <button
              type='button'
              className={cx(
                'create-btn',
                (!canCreate || creating) && 'disabled',
              )}
              disabled={!canCreate || creating}
              onClick={handleCreate}
            >
              {creating ? '생성 중...' : '생성'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default NewInferenceWizard;
