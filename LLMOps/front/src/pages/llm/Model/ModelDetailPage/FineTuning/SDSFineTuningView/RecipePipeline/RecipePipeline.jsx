// 다단계 학습 레시피(manifest.recipe, SP-10 / SDS) — MM 뷰 스타일 재구성(QA 7-10+6, 전면 재작성).
//
// 상단: 4-phase 단계 박스(번호 + 라벨 + 상태 + 학습대상, 클릭 선택). 실행 중 phase 자동 선택.
// 하단: 2컬럼(MM 뷰와 동일 레이아웃) —
//   좌(설정): 선택 phase 상태별 UI —
//     - idle: 학습 대상(freeze, params.phase 결정·읽기전용, 항목6) + 모델 구조/프로젝터
//             (MLP-2 고정·나머지 비활성, 항목8) + 하이퍼파라미터(params 에 있는 키만 슬라이더,
//             박스 선택 시 기본값 시드, 항목10·3) + 체크포인트 설정(항목9).
//     - done: 커밋명 + 학습 대상(readonly).
//     - running/pending: 학습 대상(readonly) + 실행 중 안내(진행 상황은 우측 모니터).
//   우(모니터링): MM 뷰 monitor-col 과 동일 — '학습 제어'(상태·통계·진행률·실행/중지·커밋불러오기·
//     시스템로그) + '학습 추이'(BasicLineChart). SSE 데이터/핸들러는 SDS external controller 에서 props.
//     실행 버튼이 모니터에 있으므로(MM 동형) 선택 phase 의 handleRun 을 여기서 호출.
//
// 계약: phase.params 는 파트너 /run 에 verbatim 전송되는 불투명 Dict(schema extra=forbid).
// 폼은 숫자 하이퍼파라미터/체크포인트 키만 오버레이하고 나머지(경로·phase·scenario·chain)는
// pass-through → onRunPhase(phase, merged) 시그니처·부모 체이닝 무변경.

import { Fragment, useCallback, useEffect, useState } from 'react';

import { getExternalCheckpoints } from '@src/apis/llm/model';
import { STATUS_SUCCESS } from '@src/network';

import BasicLineChart from '../../FineTuningGraph/BasicLineChart';
import MultimodalArchDiagram from './MultimodalArchDiagram';

import classNames from 'classnames/bind';
import style from './RecipePipeline.module.scss';
// MM(VLM) 학습 화면의 시각 언어 재사용 — section/freeze-banner/params-grid/slider/monitor-col 등.
import mmStyle from '../SDSFineTuningView.module.scss';

const cx = classNames.bind(style);
const mx = classNames.bind(mmStyle);

// SSE fine_tuning_status.status (running|pending|done|stop|error) + idle.
const STATUS_KEYS = {
  running: 'externalTraining.recipe.status.running',
  pending: 'externalTraining.recipe.status.pending',
  done: 'externalTraining.recipe.status.done',
  error: 'externalTraining.recipe.status.error',
  stop: 'externalTraining.recipe.status.stop',
  idle: 'externalTraining.recipe.status.idle',
};

// 모니터 상태 배지(MM STATUS_META 동형).
const MON_STATUS_META = {
  running: { label: '학습 중', cls: 'running' },
  pending: { label: '준비 중', cls: 'pending' },
  installing: { label: '준비 중', cls: 'pending' },
  done: { label: '완료', cls: 'done' },
  error: { label: '실패', cls: 'error' },
  stop: { label: '중지됨', cls: 'stop' },
};

// 차트 표시 순서(손실 우선) — MM 동형.
const MON_CHART_ORDER = [
  'train/loss',
  'eval/loss',
  'train/grad_norm',
  'train/learning_rate',
];

// params.phase(train_type) → 학습 대상. 개별 on/off 토글 없이 phase 가 결정(항목6).
const TRAIN_TARGET = {
  projector: { proj: 'train', llm: 'frozen', label: '프로젝터 정렬' },
  lora: { proj: 'train', llm: 'lora', label: '프로젝터 + 언어모델 LoRA' },
  lora_marine: { proj: 'frozen', llm: 'lora', label: '언어모델 LoRA' },
  lora_sds: { proj: 'train', llm: 'lora', label: '프로젝터 + 언어모델 LoRA' },
};

// 항목8: projector 구조(표시용) — 현재 MLP-2 고정. 실제 구조는 SDS 컨테이너(recipe/엔진)가
// 결정하며, 다른 구조/파라미터는 ETRI 가 컨테이너 고도화 시 추가 탑재. 백엔드로 전송하지 않음.
const PROJECTOR_TYPES = [
  { value: 'mlp2', label: 'MLP-2' },
  { value: 'linear', label: 'Linear' },
  { value: 'mlp3', label: 'MLP-3' },
  { value: 'xattn', label: 'Cross-Attention' },
  { value: 'qformer', label: 'Q-Former' },
];
const FIXED_PROJ = 'mlp2';

// 하이퍼파라미터 슬라이더 스펙 — params 에 실제 존재하는 키만 렌더(제너릭, 항목3).
const HP_SPECS = [
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
const HP_KEYS = HP_SPECS.map((s) => s.key);

// 항목9: 체크포인트 설정 — 이름(text) + step 제어(num). save/eval/logging step 은 현재 SDS
// /run 계약엔 없으나(파트너 무시) 전진 설계로 노출·전송 — 향후 컨테이너 탑재 시 자동 동작.
const CKPT_NUM_SPECS = [
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
const CKPT_DEFAULTS = {
  save_steps: 500,
  eval_steps: 500,
  logging_steps: 10,
  save_total_limit: 3,
};

const toNum = (v) =>
  v === '' || v === null || v === undefined || Number.isNaN(Number(v))
    ? undefined
    : Number(v);

// phase.params → 편집 폼(present HP 키 + 체크포인트 키[없으면 기본값]). 박스 선택 시 이 값이 시드(항목10).
const buildForm = (params = {}) => {
  const f = {};
  HP_KEYS.forEach((k) => {
    if (params[k] !== undefined && params[k] !== null) f[k] = Number(params[k]);
  });
  f.output_checkpoint_name =
    typeof params.output_checkpoint_name === 'string'
      ? params.output_checkpoint_name
      : '';
  CKPT_NUM_SPECS.forEach(({ key }) => {
    f[key] =
      params[key] !== undefined && params[key] !== null
        ? Number(params[key])
        : CKPT_DEFAULTS[key];
  });
  return f;
};

const phaseStatusOf = (phase, activePhaseId, activePhaseStatus, donePhases) => {
  if (phase.id === activePhaseId && activePhaseStatus) return activePhaseStatus;
  if (donePhases.has(phase.id)) return 'done';
  return 'idle';
};

const RecipePipeline = ({
  phases,
  modelId,
  activePhaseId,
  activePhaseStatus,
  donePhases,
  phaseCommitMap,
  onRunPhase,
  // 모니터(우측) — 부모 SSE 구독 데이터 + 컨트롤 핸들러(실행/중지 버튼줄 = 모니터 안, MM 동형).
  graphData,
  progressData,
  fineStatus,
  onStop,
  onSystemLog,
  t,
}) => {
  const done = donePhases || new Set();
  const commitMap = phaseCommitMap || {};

  // phase 별 편집 폼 — 각 phase params 로 시드(기본값). 선택 전환 시 이전 편집 보존.
  const [forms, setForms] = useState(() => {
    const m = {};
    phases.forEach((p) => {
      m[p.id] = buildForm(p.params || {});
    });
    return m;
  });

  // 선택 phase — 기본: 활성(실행 중) phase → 없으면 첫 미완료 → 없으면 첫 phase.
  const [selectedPhaseId, setSelectedPhaseId] = useState(() => {
    if (activePhaseId) return activePhaseId;
    const pending = phases.find((p) => !done.has(p.id));
    return (pending || phases[0] || {}).id;
  });

  // 모델 구조 · 프로젝터(항목8) — 시각화 전용 선택 상태(백엔드 미전송). 선택에 따라 도식만 갱신.
  const [projType, setProjType] = useState(FIXED_PROJ);
  const [mlpHidden, setMlpHidden] = useState(2048);
  const [xAttnHeads, setXAttnHeads] = useState(8);
  const [qTokens, setQTokens] = useState(32);
  const [diagramOpen, setDiagramOpen] = useState(false); // '크게 보기' 모달

  // 모달 열림 동안 Esc 닫기 + body 스크롤락(플랫폼 ModalFrame 관례 정합).
  useEffect(() => {
    if (!diagramOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setDiagramOpen(false);
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [diagramOpen]);

  // 실행 phase 가 바뀌면 그 phase 를 자동 선택(모니터링 따라가기).
  useEffect(() => {
    if (activePhaseId) setSelectedPhaseId(activePhaseId);
  }, [activePhaseId]);

  // 커밋이 비동기로 늦게 도착할 수 있다 — done 이 채워지고 활성 job 이 없을 때 현재 선택이
  // 이미 완료된 phase 면 첫 미완료로 보정(부분 완료 레시피 리로드 시 done 카드 선택 방지).
  useEffect(() => {
    if (activePhaseId) return;
    if (done.size === 0) return;
    setSelectedPhaseId((prev) => {
      if (phases.find((p) => p.id === prev && !done.has(p.id))) return prev;
      const pending = phases.find((p) => !done.has(p.id));
      return (pending || phases[phases.length - 1] || { id: prev }).id;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [donePhases, activePhaseId]);

  // 실행 중(running/pending)이면 모든 phase 의 실행 버튼 비활성(한 번에 한 job).
  const anyRunning =
    activePhaseStatus === 'running' || activePhaseStatus === 'pending';

  // 실행 가능: 활성 job 없음 + 체인 선행 phase 완료. (train 대상은 phase 고정 → 별도 토글 없음.)
  const canRun = useCallback(
    (phase) => {
      if (!phase) return false;
      if (anyRunning) return false;
      if (phase.chain_from && !done.has(phase.chain_from)) return false;
      return true;
    },
    [anyRunning, done],
  );

  const setField = (phaseId, key, value) =>
    setForms((s) => ({
      ...s,
      [phaseId]: { ...(s[phaseId] || {}), [key]: value },
    }));

  // 이어서 학습(가중치 warm-start) — 모델의 저장된 체크포인트 목록. 선택 시 그 가중치에서
  // 이어서 학습(옵티마이저/step 은 리셋). 목록 소스 = list_external_checkpoints(P1).
  const [resumeCkpts, setResumeCkpts] = useState([]);
  const [resumeSel, setResumeSel] = useState(''); // '' = 처음부터. 값 = "<commit>/checkpoint-<step>"
  useEffect(() => {
    // 모델 전환 시 이전 모델의 체크포인트 선택 잔존 방지(컴포넌트가 manifest@version 로만
    // keyed 라 같은 매니페스트의 다른 모델로 이동 시 미리마운트 → stale 선택으로 오모델
    // 체크포인트 주입 위험, codex MED).
    setResumeSel('');
    setResumeCkpts([]);
    if (!modelId) return;
    let alive = true;
    (async () => {
      const res = await getExternalCheckpoints(modelId);
      if (
        alive &&
        res?.status === STATUS_SUCCESS &&
        Array.isArray(res.result?.list)
      )
        setResumeCkpts(res.result.list.filter((c) => c && Number.isFinite(c.step)));
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 실행 — 편집한 숫자 하이퍼파라미터/step 과 체크포인트 이름만 phase.params 위에 오버레이,
  // 나머지 키(경로·phase·scenario·chain)는 pass-through(계약 보존). 체인 주입은 부모가 처리.
  const handleRun = useCallback(
    (phase) => {
      const f = forms[phase.id] || {};
      const merged = { ...(phase.params || {}) };
      [...HP_KEYS, ...CKPT_NUM_SPECS.map((s) => s.key)].forEach((k) => {
        const n = toNum(f[k]);
        if (n !== undefined) merged[k] = n;
      });
      const name = (f.output_checkpoint_name || '').trim();
      if (name) merged.output_checkpoint_name = name; // 빈값이 필수키를 덮지 않도록
      // 이어서 학습: FE-내부 마커. 부모 launchPhase 가 chain_inputs 뒤에 resume_lora_path/
      // projector_path 로 변환(사용자 선택이 자동 체인을 override) + commit_models 마운트 보장.
      if (resumeSel) merged._resume_checkpoint = resumeSel;
      onRunPhase(phase, merged);
    },
    [forms, onRunPhase, resumeSel],
  );

  const selectedPhase =
    phases.find((p) => p.id === selectedPhaseId) || phases[0] || null;
  const selectedStatus = selectedPhase
    ? phaseStatusOf(selectedPhase, activePhaseId, activePhaseStatus, done)
    : 'idle';

  // 편집(idle) 상태를 벗어나면 '크게 보기' 모달을 닫는다 — SSE 상태전이(running→done 등) 후
  // 도식 섹션이 사라졌다가 idle 로 돌아올 때 모달이 저절로 재출현하는 것을 방지.
  useEffect(() => {
    if (selectedStatus !== 'idle') setDiagramOpen(false);
  }, [selectedStatus]);
  const selForm = selectedPhase ? forms[selectedPhase.id] || {} : {};
  const target = selectedPhase
    ? TRAIN_TARGET[selectedPhase.params?.phase]
    : null;
  const selBlockedByChain =
    selectedPhase &&
    selectedPhase.chain_from &&
    !done.has(selectedPhase.chain_from);
  const presentHp = HP_SPECS.filter((s) => selForm[s.key] !== undefined);

  // ── 모니터 파생값(활성 job 의 SSE) — MM monitor-col 동형 ──
  const monStatus = fineStatus?.fine_tuning_status?.status;
  const monMeta = MON_STATUS_META[monStatus];
  const isMonRunning = monStatus === 'running' || monStatus === 'pending';
  const monLoss = graphData?.['train/loss']?.values?.slice(-1)?.[0];
  const monGrad = graphData?.['train/grad_norm']?.values?.slice(-1)?.[0];
  const monPct = Number.isFinite(progressData?.percent)
    ? Math.floor(progressData.percent)
    : 0;
  const monEpoch =
    Number.isFinite(progressData?.progress_epoch) && progressData?.total_epoch
      ? `${progressData.progress_epoch}/${progressData.total_epoch}`
      : '—';
  const monCharts = graphData
    ? Object.entries(graphData).sort(([a], [b]) => {
        const rank = (k) => {
          const i = MON_CHART_ORDER.indexOf(k);
          return i < 0 ? 99 : i;
        };
        return rank(a) - rank(b);
      })
    : [];

  // 학습 대상 freeze 배너(읽기전용) — 비전=항상 동결, projector/LLM 은 phase 가 결정.
  const freezeLayers = target
    ? [
        { icon: '🔒', name: 'Vision Encoder', note: '동결', cls: 'frozen' },
        target.proj === 'train'
          ? { icon: '⚙', name: 'Projector', note: '학습', cls: 'trainable' }
          : { icon: '🔒', name: 'Projector', note: '동결', cls: 'frozen' },
        target.llm === 'lora'
          ? {
              icon: '⚡',
              name: 'Language Model',
              note: 'LoRA 학습',
              cls: 'lora',
            }
          : { icon: '🔒', name: 'Language Model', note: '동결', cls: 'frozen' },
      ]
    : [];

  const FreezeBanner = () =>
    freezeLayers.length ? (
      <div className={mx('freeze-banner')}>
        {freezeLayers.map(({ icon, name, note, cls }) => (
          <div
            key={`${name}-${note}`}
            className={mx('freeze-item', `freeze-item--${cls}`)}
            aria-label={`${name}: ${note}`}
          >
            <span className={mx('freeze-icon')} aria-hidden='true'>
              {icon}
            </span>
            <div>
              <div className={mx('freeze-name')}>{name}</div>
              <div className={mx('freeze-note')}>{note}</div>
            </div>
          </div>
        ))}
      </div>
    ) : null;

  const renderSlider = (spec, phaseId) => {
    const val = selForm[spec.key];
    const disp = spec.exp ? Number(val).toExponential(1) : val;
    return (
      <div key={spec.key} className={mx('param-item')}>
        <div className={mx('param-header')}>
          <span className={mx('param-name')}>{spec.label}</span>
          <span className={mx('param-val')}>{disp}</span>
        </div>
        <input
          type='range'
          className={mx('slider')}
          min={spec.min}
          max={spec.max}
          step={spec.step}
          value={val}
          onChange={(e) => setField(phaseId, spec.key, Number(e.target.value))}
        />
      </div>
    );
  };

  // 좌측 설정 컬럼 — 선택 phase 의 상태별 UI(실행 버튼은 우측 모니터로 이동).
  const renderConfig = () => {
    if (!selectedPhase) return null;
    const isRun = selectedStatus === 'running' || selectedStatus === 'pending';
    const isDone = selectedStatus === 'done';

    return (
      <div className={cx('config-side')}>
        <div className={cx('detail-head')}>
          <span className={cx('detail-title')}>{selectedPhase.label}</span>
          <span className={cx('badge', `badge-${selectedStatus}`)}>
            {t(STATUS_KEYS[selectedStatus] || STATUS_KEYS.idle)}
          </span>
        </div>
        {selectedPhase.description ? (
          <div className={cx('phase-desc')}>{selectedPhase.description}</div>
        ) : null}

        {/* 학습 대상(읽기전용) — 모든 상태 공통 */}
        {freezeLayers.length ? (
          <section className={mx('section')}>
            <div className={mx('section-label')}>학습 대상</div>
            <FreezeBanner />
            {!isRun && !isDone ? (
              <div className={mx('train-hint')}>
                학습 대상은 단계에 따라 자동 결정됩니다. 개별 변경은 지원하지
                않습니다.
              </div>
            ) : null}
          </section>
        ) : null}

        {isDone ? (
          <section className={mx('section')}>
            <div className={mx('section-label')}>저장된 커밋</div>
            <div className={cx('commit-row')}>
              <span className={cx('commit-name')}>
                {commitMap[selectedPhase.id] || '-'}
              </span>
            </div>
          </section>
        ) : isRun ? (
          <div className={cx('running-note')}>
            학습이 진행 중입니다. 진행 상황은 오른쪽 모니터에서 확인하세요.
          </div>
        ) : (
          <>
            <section className={mx('section')}>
              <div className={mx('section-label')}>모델 구조 · 프로젝터</div>
              <div className={cx('proj-selector')}>
                {PROJECTOR_TYPES.map((p) => (
                  <button
                    key={p.value}
                    type='button'
                    className={cx('proj-btn', p.value === projType && 'active')}
                    onClick={() => setProjType(p.value)}
                    aria-pressed={p.value === projType}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {/* 프로젝터 타입별 파라미터(시각화 전용) — 도식 라벨에 반영 */}
              {(projType === 'mlp2' || projType === 'mlp3') && (
                <div className={cx('proj-param-row')}>
                  <span className={cx('proj-param-label')}>Hidden Dim</span>
                  <div className={cx('proj-selector')}>
                    {[1024, 2048, 4096].map((h) => (
                      <button
                        key={h}
                        type='button'
                        className={cx('proj-btn', mlpHidden === h && 'active')}
                        onClick={() => setMlpHidden(h)}
                        aria-pressed={mlpHidden === h}
                      >
                        {h}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {projType === 'xattn' && (
                <div className={cx('proj-param-row')}>
                  <span className={cx('proj-param-label')}>Attn Heads</span>
                  <div className={cx('proj-selector')}>
                    {[4, 8, 16].map((h) => (
                      <button
                        key={h}
                        type='button'
                        className={cx('proj-btn', xAttnHeads === h && 'active')}
                        onClick={() => setXAttnHeads(h)}
                        aria-pressed={xAttnHeads === h}
                      >
                        {`${h} heads`}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {projType === 'qformer' && (
                <div className={cx('proj-param-row')}>
                  <span className={cx('proj-param-label')}>Query Tokens</span>
                  <div className={cx('proj-selector')}>
                    {[16, 32, 64].map((q) => (
                      <button
                        key={q}
                        type='button'
                        className={cx('proj-btn', qTokens === q && 'active')}
                        onClick={() => setQTokens(q)}
                        aria-pressed={qTokens === q}
                      >
                        {`${q} tokens`}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className={cx('diagram-head')}>
                <button
                  type='button'
                  className={cx('diagram-open-btn')}
                  onClick={() => setDiagramOpen(true)}
                >
                  🔍 크게 보기
                </button>
              </div>

              <MultimodalArchDiagram
                projType={projType}
                mlpHidden={mlpHidden}
                xAttnHeads={xAttnHeads}
                qTokens={qTokens}
              />
            </section>

            {diagramOpen && (
              <div
                className={cx('diagram-modal-backdrop')}
                onClick={() => setDiagramOpen(false)}
              >
                <div
                  className={cx('diagram-modal')}
                  role='dialog'
                  aria-modal='true'
                  aria-label='모델 구조 · 프로젝터'
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className={cx('diagram-modal-head')}>
                    <span className={cx('diagram-modal-title')}>
                      모델 구조 · 프로젝터
                    </span>
                    <button
                      type='button'
                      className={cx('diagram-modal-close')}
                      onClick={() => setDiagramOpen(false)}
                      aria-label='닫기'
                    >
                      ✕
                    </button>
                  </div>
                  <div className={cx('diagram-modal-body')}>
                    <MultimodalArchDiagram
                      projType={projType}
                      mlpHidden={mlpHidden}
                      xAttnHeads={xAttnHeads}
                      qTokens={qTokens}
                    />
                  </div>
                </div>
              </div>
            )}

            {presentHp.length ? (
              <section className={mx('section')}>
                <div className={mx('section-label')}>하이퍼파라미터</div>
                <div className={mx('params-grid')}>
                  {presentHp.map((s) => renderSlider(s, selectedPhase.id))}
                </div>
              </section>
            ) : null}

            <section className={mx('section')}>
              <div className={mx('section-label')}>체크포인트 설정</div>
              <div className={cx('ckpt-name-row')}>
                <span className={cx('ckpt-name-label')}>체크포인트 이름</span>
                <input
                  type='text'
                  className={cx('ckpt-name-input')}
                  value={selForm.output_checkpoint_name || ''}
                  onChange={(e) =>
                    setField(
                      selectedPhase.id,
                      'output_checkpoint_name',
                      e.target.value,
                    )
                  }
                  placeholder='output_checkpoint_name'
                  spellCheck={false}
                />
              </div>
              <div className={mx('params-grid')}>
                {CKPT_NUM_SPECS.map((s) => renderSlider(s, selectedPhase.id))}
              </div>
            </section>

            <section className={mx('section')}>
              <div className={mx('section-label')}>이어서 학습 (선택)</div>
              <div className={cx('resume-row')}>
                <select
                  className={cx('resume-select')}
                  value={resumeSel}
                  onChange={(e) => setResumeSel(e.target.value)}
                >
                  <option value=''>처음부터 (이어받지 않음)</option>
                  {resumeCkpts.map((c) => (
                    <option
                      key={`${c.commit_id}:${c.step}`}
                      value={`${c.commit_name}/checkpoint-${c.step}`}
                    >
                      {`${c.stage_label ? `[${c.stage_label}] ` : ''}Step ${c.step.toLocaleString()}${
                        Number.isFinite(c.loss) ? ` · loss ${c.loss.toFixed(3)}` : ''
                      }`}
                    </option>
                  ))}
                </select>
              </div>
              <div className={mx('train-hint')}>
                선택한 체크포인트의 가중치에서 이어서 학습합니다(옵티마이저·step 은
                새로 시작). 저장된 체크포인트가 없으면 목록이 비어 있습니다.
              </div>
            </section>
          </>
        )}
      </div>
    );
  };

  // 우측 모니터 컬럼 — MM 뷰 monitor-col 과 동일(학습 제어 + 학습 추이). 실행/중지 = 버튼줄 안.
  const renderMonitor = () => (
    <div className={mx('monitor-col')}>
      <section className={mx('section')}>
        <div className={mx('control-head')}>
          <div className={mx('section-label')}>학습 제어</div>
          {monMeta ? (
            <span
              className={mx('status-badge', `status-badge--${monMeta.cls}`)}
            >
              {monMeta.label}
            </span>
          ) : null}
          <div className={mx('head-actions')}>
            <button
              type='button'
              className={mx('head-btn')}
              onClick={onSystemLog}
              disabled={!fineStatus}
              title={
                !fineStatus
                  ? '학습 기록이 아직 없습니다.'
                  : '학습 파드 로그를 확인합니다.'
              }
            >
              <span aria-hidden='true'>📄</span> 시스템 로그
            </button>
          </div>
        </div>
        {monStatus === 'error' && fineStatus?.fine_tuning_status?.reason ? (
          <div className={mx('train-warn')}>
            실패 사유: {fineStatus.fine_tuning_status.reason}
          </div>
        ) : null}
        <div className={mx('train-control')}>
          <div className={mx('train-stats')}>
            <div className={mx('stat-card')}>
              <span className={mx('stat-label')}>학습 Loss</span>
              <span className={mx('stat-val')}>
                {Number.isFinite(monLoss) ? monLoss.toFixed(4) : '—'}
              </span>
            </div>
            <div className={mx('stat-card')}>
              <span className={mx('stat-label')}>Grad Norm</span>
              <span className={mx('stat-val')}>
                {Number.isFinite(monGrad) ? monGrad.toFixed(3) : '—'}
              </span>
            </div>
            <div className={mx('stat-card')}>
              <span className={mx('stat-label')}>Epoch</span>
              <span className={mx('stat-val')}>{monEpoch}</span>
            </div>
            <div className={mx('stat-card')}>
              <span className={mx('stat-label')}>진행률</span>
              <span className={mx('stat-val')}>{monPct}%</span>
            </div>
          </div>
          <div className={mx('prog-track')}>
            <div className={mx('prog-fill')} style={{ width: `${monPct}%` }} />
          </div>
          <div className={mx('train-btn-row')}>
            {isMonRunning ? (
              <button
                type='button'
                className={mx('train-btn', 'train-btn--stop')}
                onClick={onStop}
              >
                ■ 학습 중지
              </button>
            ) : (
              <button
                type='button'
                className={mx('train-btn', 'train-btn--start')}
                onClick={() => selectedPhase && handleRun(selectedPhase)}
                disabled={!canRun(selectedPhase)}
                title={
                  selBlockedByChain
                    ? t('externalTraining.recipe.chainGate.label')
                    : undefined
                }
              >
                ▶ {t('externalTraining.recipe.run.label')}
              </button>
            )}
          </div>
          {selBlockedByChain && !isMonRunning ? (
            <div className={mx('train-hint')}>
              {t('externalTraining.recipe.chainGate.label')}
            </div>
          ) : null}
        </div>
      </section>

      <section className={mx('section')}>
        <div className={mx('section-label')}>학습 추이</div>
        {monCharts.length > 0 ? (
          <div className={mx('charts-grid')}>
            {monCharts.map(([key, value]) => (
              <div key={key} className={mx('chart-card')}>
                <BasicLineChart
                  title={key}
                  steps={value?.steps ?? []}
                  values={value?.values ?? []}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className={mx('chart-card')}>
            <div className={mx('chart-empty')}>
              {isMonRunning
                ? '학습 추이를 불러오는 중입니다…'
                : '학습 시작 후 표시됩니다'}
            </div>
          </div>
        )}
      </section>
    </div>
  );

  return (
    <div className={cx('recipe')}>
      {/* 상단 4-phase 단계 박스(full width) — 번호 + 라벨 + 상태 + 학습 대상. 클릭 선택. */}
      <div className={cx('pipeline')}>
        {phases.map((phase, idx) => {
          const st = phaseStatusOf(
            phase,
            activePhaseId,
            activePhaseStatus,
            done,
          );
          const selected = phase.id === selectedPhaseId;
          const ptarget = TRAIN_TARGET[phase.params?.phase];
          return (
            <Fragment key={phase.id}>
              {idx > 0 ? <div className={cx('connector')}>→</div> : null}
              <button
                type='button'
                className={cx('card', `st-${st}`, selected && 'selected')}
                onClick={() => setSelectedPhaseId(phase.id)}
              >
                <div className={cx('card-head')}>
                  <span className={cx('step-num')}>{idx + 1}</span>
                  <span className={cx('phase-label')}>{phase.label}</span>
                  <span className={cx('badge', `badge-${st}`)}>
                    {t(STATUS_KEYS[st] || STATUS_KEYS.idle)}
                  </span>
                </div>
                {ptarget ? (
                  <div className={cx('step-target')}>{ptarget.label}</div>
                ) : null}
              </button>
            </Fragment>
          );
        })}
      </div>

      {/* 하단 2컬럼 — 좌: 선택 phase 설정 / 우: 모니터링(MM monitor-col 동형, 실행/중지 포함) */}
      {selectedPhase ? (
        <div className={cx('sds-body')}>
          {renderConfig()}
          <div className={cx('monitor-side')}>{renderMonitor()}</div>
        </div>
      ) : null}
    </div>
  );
};

export default RecipePipeline;
