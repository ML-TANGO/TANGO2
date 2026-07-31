import { useState } from 'react';
import classNames from 'classnames/bind';
import style from './NewInferenceWizard.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

const cx = classNames.bind(style);

const GPU_OPTIONS = [
  { id: 'a100-1',    label: '1× NVIDIA A100 80GB SXM4' },
  { id: 'a100-2',    label: '2× NVIDIA A100 80GB SXM4' },
  { id: 'v100-1',    label: '1× NVIDIA V100 32GB' },
  { id: 'rtx4090-1', label: '1× NVIDIA RTX 4090 24GB' },
];
const CPU_OPTIONS     = [4, 8, 16, 32];
const MEMORY_OPTIONS  = ['16GB', '32GB', '64GB', '128GB'];
const REPLICA_OPTIONS = [1, 2, 4];

const STEPS = ['모델 구성', '자원 할당', '확인 및 생성'];

export default function NewInferenceWizard({ wid, onClose, onCreate }) {
  const [step, setStep]                             = useState(1);
  const [inferenceModel, setInferenceModel]         = useState(null);
  const [inferenceModelData, setInferenceModelData] = useState(null);
  const [promptModel, setPromptModel]               = useState(null);
  const [promptModelData, setPromptModelData]       = useState(null);
  const [gpu, setGpu]         = useState('a100-1');
  const [cpu, setCpu]         = useState(8);
  const [memory, setMemory]   = useState('32GB');
  const [replicas, setReplicas] = useState(1);
  const [sessionName, setSessionName] = useState('');

  const canStep1  = !!inferenceModel && !!promptModel;
  const canCreate = canStep1 && sessionName.trim().length > 0;

  const handleCreate = () => {
    if (!canCreate) return;
    onCreate({
      id: `inf-${Date.now()}`,
      name: sessionName.trim(),
      mode: 'dual',
      models: [
        { role: 'prompt',    id: promptModel,    name: promptModelData?.name },
        { role: 'inference', id: inferenceModel, name: inferenceModelData?.name },
      ],
      resources: {
        gpu: GPU_OPTIONS.find((g) => g.id === gpu)?.label ?? gpu,
        cpu,
        memory,
        replicas,
      },
      status: 'ready',
      created_at: new Date().toISOString(),
    });
  };

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div className={cx('wizard')} onClick={(e) => e.stopPropagation()}>

        <div className={cx('header')}>
          <span className={cx('title')}>새 추론 생성</span>
          <button className={cx('close-btn')} onClick={onClose}>✕</button>
        </div>

        {/* Step indicator */}
        <div className={cx('step-bar')}>
          {STEPS.map((label, i) => (
            <div key={i} className={cx('step-item', step === i + 1 && 'active', step > i + 1 && 'done')}>
              <div className={cx('step-circle')}>{step > i + 1 ? '✓' : i + 1}</div>
              <span className={cx('step-label')}>{label}</span>
              {i < STEPS.length - 1 && <div className={cx('step-line', step > i + 1 && 'filled')} />}
            </div>
          ))}
        </div>

        {/* ── Step 1: 모델 구성 ── */}
        {step === 1 && (
          <div className={cx('body')}>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>추론 모델 (Inference Model)</h3>
              <ModelSelector
                wid={wid}
                selected={inferenceModel}
                onSelect={(id, data) => { setInferenceModel(id); setInferenceModelData(data); }}
              />
            </div>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>프롬프트 엔지니어링 모델</h3>
              <ModelSelector
                wid={wid}
                selected={promptModel}
                onSelect={(id, data) => { setPromptModel(id); setPromptModelData(data); }}
              />
            </div>
          </div>
        )}

        {/* ── Step 2: 자원 할당 ── */}
        {step === 2 && (
          <div className={cx('body')}>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>GPU</h3>
              <div className={cx('res-grid')}>
                {GPU_OPTIONS.map((g) => (
                  <div key={g.id} className={cx('res-card', gpu === g.id && 'selected')} onClick={() => setGpu(g.id)}>
                    {g.label}
                  </div>
                ))}
              </div>
            </div>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>CPU (코어)</h3>
              <div className={cx('chip-row')}>
                {CPU_OPTIONS.map((c) => (
                  <div key={c} className={cx('chip', cpu === c && 'selected')} onClick={() => setCpu(c)}>{c}코어</div>
                ))}
              </div>
            </div>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>메모리</h3>
              <div className={cx('chip-row')}>
                {MEMORY_OPTIONS.map((m) => (
                  <div key={m} className={cx('chip', memory === m && 'selected')} onClick={() => setMemory(m)}>{m}</div>
                ))}
              </div>
            </div>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>레플리카 수</h3>
              <div className={cx('chip-row')}>
                {REPLICA_OPTIONS.map((r) => (
                  <div key={r} className={cx('chip', replicas === r && 'selected')} onClick={() => setReplicas(r)}>{r}</div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: 확인 및 생성 ── */}
        {step === 3 && (
          <div className={cx('body')}>
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>세션 이름</h3>
              <input
                className={cx('name-input')}
                type="text"
                placeholder="추론 세션 이름을 입력하세요"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
              />
            </div>
            <div className={cx('summary')}>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>프롬프트 모델</span>
                <span className={cx('s-val')}>{promptModelData?.name ?? '-'}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>추론 모델</span>
                <span className={cx('s-val')}>{inferenceModelData?.name ?? '-'}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>GPU</span>
                <span className={cx('s-val')}>{GPU_OPTIONS.find((g) => g.id === gpu)?.label}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>CPU / 메모리</span>
                <span className={cx('s-val')}>{cpu}코어 / {memory}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>레플리카</span>
                <span className={cx('s-val')}>{replicas}</span>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className={cx('footer')}>
          {step > 1 && (
            <button className={cx('back-btn')} onClick={() => setStep((s) => s - 1)}>이전</button>
          )}
          <button className={cx('cancel-btn')} onClick={onClose}>취소</button>
          {step < 3 ? (
            <button
              className={cx('next-btn', step === 1 && !canStep1 && 'disabled')}
              disabled={step === 1 && !canStep1}
              onClick={() => setStep((s) => s + 1)}
            >
              다음
            </button>
          ) : (
            <button
              className={cx('create-btn', !canCreate && 'disabled')}
              disabled={!canCreate}
              onClick={handleCreate}
            >
              생성
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
