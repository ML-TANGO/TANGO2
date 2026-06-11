import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import classNames from 'classnames/bind';
import style from './NewDeploymentWizard.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

const cx = classNames.bind(style);

const TARGET_CATEGORIES = [
  {
    id: 'edge-k8s',
    label: '엣지 장치 (클러스터 내)',
    icon: '⚡',
    desc: '쿠버네티스에 등록된 엣지 장치 — 자동 배포',
    method: 'auto',
    devices: [
      { id: 'orin-agx-64',  label: 'NVIDIA Jetson Orin AGX 64GB', arch: 'aarch64' },
      { id: 'orin-nx-16',   label: 'NVIDIA Jetson Orin NX 16GB',  arch: 'aarch64' },
      { id: 'orin-nano',    label: 'NVIDIA Jetson Orin Nano 8GB', arch: 'aarch64' },
    ],
  },
  {
    id: 'cloud',
    label: '클라우드 / 클러스터 서버',
    icon: '☁️',
    desc: '클러스터 내 GPU 서버 또는 클라우드 인스턴스 — 자동 배포',
    method: 'auto',
    devices: [
      { id: 'aws-g5',    label: 'AWS EC2 g5 (A10G)',    arch: 'x86_64' },
      { id: 'gcp-a100',  label: 'GCP A2 (A100)',         arch: 'x86_64' },
      { id: 'azure-nc',  label: 'Azure NC A100',          arch: 'x86_64' },
      { id: 'onprem-gpu', label: 'On-Premise GPU 서버',   arch: 'x86_64' },
    ],
  },
  {
    id: 'standalone',
    label: '독립 장치 (클러스터 외부)',
    icon: '🖥️',
    desc: '클러스터 미등록 PC·서버·외부 엣지 — 스크립트 수동 배포',
    method: 'manual',
    devices: [
      { id: 'standalone-pc',     label: '로컬 PC / 워크스테이션', arch: 'x86_64' },
      { id: 'standalone-server', label: '독립 GPU 서버',           arch: 'x86_64' },
      { id: 'standalone-edge',   label: '외부 엣지 장치',           arch: 'aarch64' },
      { id: 'raspi5',            label: 'Raspberry Pi 5',           arch: 'aarch64' },
    ],
  },
];

const SERVING_SYSTEMS = [
  { id: 'vllm',     label: 'vLLM',         badge: 'GPU',      arch: ['x86_64'],            desc: 'OpenAI API 호환, 고처리량 GPU 서빙' },
  { id: 'tensorrt', label: 'TensorRT-LLM', badge: 'NVIDIA',   arch: ['x86_64', 'aarch64'], desc: 'NVIDIA GPU 최적화, 최고 추론 성능' },
  { id: 'llamacpp', label: 'llama.cpp',    badge: 'CPU/GPU',  arch: ['x86_64', 'aarch64'], desc: '경량 추론, 양자화(GGUF) 지원' },
  { id: 'ollama',   label: 'Ollama',       badge: 'Universal',arch: ['x86_64', 'aarch64'], desc: '간편 설치·관리, REST API 제공' },
  { id: 'triton',   label: 'Triton IS',    badge: 'NVIDIA',   arch: ['x86_64'],            desc: 'NVIDIA Triton, 다중 모델 동시 서빙' },
];

const STEPS = ['모델 선택', '배포 대상', '서빙 시스템', '확인 및 생성'];

function NewDeploymentWizard({ isOpen, onClose, onSubmit, workspaceId }) {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);

  // Step 1
  const [modelId, setModelId]     = useState(null);
  const [modelData, setModelData] = useState(null);
  // Step 2
  const [catId, setCatId]       = useState(null);
  const [deviceId, setDeviceId] = useState(null);
  // Step 3
  const [servingId, setServingId] = useState(null);
  // Step 4
  const [depName, setDepName] = useState('');

  if (!isOpen) return null;

  const cat    = TARGET_CATEGORIES.find((c) => c.id === catId);
  const device = cat?.devices.find((d) => d.id === deviceId);
  const serving = SERVING_SYSTEMS.find((s) => s.id === servingId);

  const compatibleSystems = device
    ? SERVING_SYSTEMS.filter((s) => s.arch.includes(device.arch))
    : SERVING_SYSTEMS;

  const canNext = [
    !!modelId,
    !!catId && !!deviceId,
    !!servingId,
    depName.trim().length > 0,
  ];

  const handleClose = () => {
    setStep(1); setCatId(null); setDeviceId(null);
    setModelId(null); setModelData(null);
    setServingId(null); setDepName('');
    onClose();
  };

  const handleSubmit = () => {
    onSubmit({
      deployment_name: depName.trim(),
      model_name: modelData?.name ?? modelId,
      model_id: modelId,
      target_category: catId,
      target_device_id: deviceId,
      target_device: device?.label ?? deviceId,
      serving_system: serving?.label ?? servingId,
      deploy_method: cat?.method ?? 'manual',
    });
    handleClose();
  };

  return (
    <div className={cx('overlay')} onClick={handleClose}>
      <div className={cx('wizard')} onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className={cx('header')}>
          <span className={cx('title')}>{t('newDeployment.label', '새 배포 생성')}</span>
          <button className={cx('close-btn')} onClick={handleClose}>✕</button>
        </div>

        {/* Step bar */}
        <div className={cx('step-bar')}>
          {STEPS.map((label, i) => (
            <div key={i} className={cx('step-item', step === i + 1 && 'active', step > i + 1 && 'done')}>
              <div className={cx('step-circle')}>{step > i + 1 ? '✓' : i + 1}</div>
              <span className={cx('step-label')}>{label}</span>
              {i < STEPS.length - 1 && <div className={cx('step-line', step > i + 1 && 'filled')} />}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className={cx('body')}>

          {/* ── Step 1: 모델 선택 ── */}
          {step === 1 && (
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>배포할 학습 모델을 선택하세요</h3>
              <ModelSelector
                wid={workspaceId}
                selected={modelId}
                onSelect={(id, data) => { setModelId(id); setModelData(data); }}
              />
            </div>
          )}

          {/* ── Step 2: 배포 대상 ── */}
          {step === 2 && (
            <>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>배포 환경 유형</h3>
                <div className={cx('cat-grid')}>
                  {TARGET_CATEGORIES.map((c) => (
                    <div
                      key={c.id}
                      className={cx('cat-card', catId === c.id && 'selected')}
                      onClick={() => { setCatId(c.id); setDeviceId(null); setServingId(null); }}
                    >
                      <span className={cx('cat-icon')}>{c.icon}</span>
                      <span className={cx('cat-label')}>{c.label}</span>
                      <span className={cx('cat-desc')}>{c.desc}</span>
                      <span className={cx('method-badge', c.method)}>
                        {c.method === 'auto' ? '🔄 자동 배포' : '📋 수동 배포'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {cat && (
                <div className={cx('section')}>
                  <h3 className={cx('section-title')}>대상 장치 선택</h3>
                  <div className={cx('chip-row')}>
                    {cat.devices.map((d) => (
                      <div
                        key={d.id}
                        className={cx('device-chip', deviceId === d.id && 'selected')}
                        onClick={() => setDeviceId(d.id)}
                      >
                        <span className={cx('dev-label')}>{d.label}</span>
                        <span className={cx('dev-arch')}>{d.arch}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── Step 3: 서빙 시스템 ── */}
          {step === 3 && (
            <div className={cx('section')}>
              <h3 className={cx('section-title')}>
                서빙 시스템 선택
                {device && <span className={cx('arch-hint')}> · {device.label} ({device.arch})</span>}
              </h3>
              <div className={cx('serving-grid')}>
                {compatibleSystems.map((s) => (
                  <div
                    key={s.id}
                    className={cx('serving-card', servingId === s.id && 'selected')}
                    onClick={() => setServingId(s.id)}
                  >
                    <div className={cx('serving-top')}>
                      <span className={cx('serving-label')}>{s.label}</span>
                      <span className={cx('serving-badge')}>{s.badge}</span>
                    </div>
                    <span className={cx('serving-desc')}>{s.desc}</span>
                  </div>
                ))}
              </div>
              {SERVING_SYSTEMS.some((s) => !s.arch.includes(device?.arch) && servingId === s.id) && (
                <div className={cx('compat-warn')}>
                  ⚠ 선택한 서빙 시스템이 대상 장치 아키텍처와 호환되지 않을 수 있습니다.
                </div>
              )}
            </div>
          )}

          {/* ── Step 4: 확인 및 생성 ── */}
          {step === 4 && (
            <>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>배포 이름</h3>
                <input
                  className={cx('name-input')}
                  type='text'
                  placeholder='배포 이름을 입력하세요'
                  value={depName}
                  onChange={(e) => setDepName(e.target.value)}
                />
              </div>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>설정 요약</h3>
                <div className={cx('summary')}>
                  {[
                    ['모델',       modelData?.name ?? modelId],
                    ['배포 환경',  cat?.label],
                    ['대상 장치',  device?.label],
                    ['서빙 시스템', serving?.label],
                    ['배포 방식',  cat?.method === 'auto'
                      ? '🔄 자동 배포 (K8s)'
                      : '📋 수동 배포 (스크립트 제공)'],
                  ].map(([key, val]) => (
                    <div key={key} className={cx('s-row')}>
                      <span className={cx('s-key')}>{key}</span>
                      <span className={cx('s-val')}>{val}</span>
                    </div>
                  ))}
                </div>
                {cat?.method === 'manual' && (
                  <div className={cx('manual-notice')}>
                    📋 배포 완료 후 대상 장치에서 실행할 <strong>Docker 명령어·systemd 설정·API 엔드포인트</strong>를 상세 페이지에서 확인할 수 있습니다.
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className={cx('footer')}>
          {step > 1 && (
            <button className={cx('back-btn')} onClick={() => setStep((s) => s - 1)}>
              이전
            </button>
          )}
          <button className={cx('cancel-btn')} onClick={handleClose}>취소</button>
          {step < 4 ? (
            <button
              className={cx('next-btn', !canNext[step - 1] && 'disabled')}
              disabled={!canNext[step - 1]}
              onClick={() => setStep((s) => s + 1)}
            >
              다음
            </button>
          ) : (
            <button
              className={cx('create-btn', !canNext[3] && 'disabled')}
              disabled={!canNext[3]}
              onClick={handleSubmit}
            >
              배포 생성
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default NewDeploymentWizard;
