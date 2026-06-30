// Multimodal (VLM) FineTuning 화면 — 상위 '파인튜닝' 탭 선택 시 학습 폼을 바로 표시.
// (이전의 내부 3-탭(정보/학습/관리) 셸 제거: 정보의 모델구조→상위 '정보' 탭으로,
//  체크포인트(관리)→상위 커밋 리스트/커밋 상세로, 데이터셋→이 학습 화면 상단으로.)
//
// 원칙([[feedback_mockup_drives_design]]): 화면/UI 는 목업에 충실하되, 플랫폼 정책/엔진
// 계약과 충돌하거나 변경 공수가 비대칭인 컨트롤은 플랫폼에 맞춘다.
//   - 자원 할당: 플랫폼은 인스턴스 단위 스케줄링 → 공용 인스턴스 모달(FINETUNING_SETTING).
//   - projector 구조 선택(7종)·Hidden Dim: HF Llava 표준 재로드가 커스텀 구조를 거부(실증) → 제거.
//   - 데이터셋: 모델 바인딩(model_datasets) 표시(read-only).
//   - 하이퍼파라미터: 엔진이 받는 것만 노출·배선.

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import SimpleNav from '../../SimpleNav';
import BasicLineChart from '../FineTuningGraph/BasicLineChart';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './MultimodalFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

const LORA_TARGETS = ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'];

// 학습 추이 차트 표시 순서(중요도): 손실(train/eval) 먼저 → 진단(grad/lr). 2열 그리드와 합쳐
// 4개일 때 [loss|eval]/[grad|lr] 2×2 로 자연 정렬. 목록에 없는 태그는 뒤로.
const CHART_ORDER = ['train/loss', 'eval/loss', 'train/grad_norm', 'train/learning_rate'];

// 학습 상태 배지(sse-status). 버튼만으론 완료/실패/중지를 구분 못 해 사용자가 결과를 알 수 없던 문제.
const STATUS_META = {
  running: { label: '학습 중', cls: 'running' },
  done: { label: '완료', cls: 'done' },
  error: { label: '실패', cls: 'error' },
  stop: { label: '중지됨', cls: 'stop' },
  pending: { label: '준비 중', cls: 'pending' },
  installing: { label: '준비 중', cls: 'pending' },
};

const shortName = (id) => {
  if (!id) return '-';
  const parts = String(id).split('/');
  return parts[parts.length - 1];
};

// options/preprocessing/data 트리(노드 { name, full_path, type, sub_list })를 DFS 로
// 평탄화해 파일(type==='file')만 수집. (FinetuningDatasetSearch 의 dfsData 패턴 동형.)
const flattenFiles = (nodes) => {
  const out = [];
  const walk = (node) => {
    if (!node) return;
    if (node.type === 'file' && node.full_path) out.push({ name: node.name, full_path: node.full_path });
    if (Array.isArray(node.sub_list)) node.sub_list.forEach(walk);
  };
  (Array.isArray(nodes) ? nodes : []).forEach(walk);
  return out;
};

function SectionLabel({ children }) {
  return <div className={lx('section-label')}>{children}</div>;
}

function Chip({ label, selected, onClick }) {
  return (
    <button type='button' className={lx('chip', selected && 'chip--on')} onClick={onClick}>
      {label}
    </button>
  );
}

const MultimodalFineTuningView = memo(function MultimodalFineTuningView({
  navList,
  fineTuningData,
  workspaceId,
  modelId,
  refresh,
  filteredRest,
  // 학습 모니터링 SSE 는 부모(FineTuning)가 단일 구독해 내려줌(이중 구독 방지).
  fineStatus,
  graphData,
  progressData,
  checkpoints,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // huggingface_model_id = "{vision},{llm}" — 첫 콤마로 분리(BE 정규화 보장).
  const hfId = fineTuningData?.huggingface_model_id || '';
  const commaIdx = hfId.indexOf(',');
  const visionName = commaIdx >= 0 ? hfId.slice(0, commaIdx) : hfId;
  const llmName = commaIdx >= 0 ? hfId.slice(commaIdx + 1) : '';

  // 모델 바인딩 데이터셋(read-only). 바인딩은 아래 인라인 데이터셋 목록에서 직접.
  const datasets = Array.isArray(fineTuningData?.model_datasets) ? fineTuningData.model_datasets : [];

  // 인라인 데이터셋 선택(ETRI 목업 방식) — 워크스페이스 전체 데이터셋 + 선택 시 데이터 파일.
  const [wsDatasets, setWsDatasets] = useState([]);
  const [selDataset, setSelDataset] = useState(null);
  const [dsFiles, setDsFiles] = useState([]);

  // 학습 컴포넌트: 프로젝터 정렬(stage1 on/off) + 언어모델 LoRA(used_lora). stage2(LM)는 항상 수행.
  const [trainProj, setTrainProj] = useState(true);
  const [trainLLM, setTrainLLM] = useState(true);

  // stage1(projector 정렬)
  const [lr1, setLr1] = useState(0.001);
  const [ep1, setEp1] = useState(1);

  // stage2(LM)
  const [lr2, setLr2] = useState(0.0002);
  const [ep2, setEp2] = useState(3);
  const [bs2, setBs2] = useState(1);
  const [wd2, setWd2] = useState(0.01);
  const [loraR, setLoraR] = useState(16);
  const [loraA, setLoraA] = useState(32);
  const [loraD, setLoraD] = useState(0.05);
  const [loraTgts, setLoraTgts] = useState(new Set(['q_proj', 'v_proj']));
  const toggleLoraTgt = (m) => setLoraTgts((prev) => { const s = new Set(prev); if (s.has(m)) s.delete(m); else s.add(m); return s; });

  // 데모 샘플 수 제한(0=전체). CC3M 595K 같은 대용량셋은 1회 완주 데모를 위해 소량 캡 권장.
  const [maxSamples, setMaxSamples] = useState(0);
  const [dsFilesLoading, setDsFilesLoading] = useState(false); // 데이터 파일 조회 중(빈목록 깜빡임 방지)
  const [stopping, setStopping] = useState(false);             // 중지 요청 in-flight(중복 클릭 방지)

  // 학습 모니터링 데이터(부모 SSE 구독에서 props 로 수신). 차트 소스=엔진 TensorBoard
  // (llm_model_vlm_fine_tuning.py 연속-step 콜백). 진행률=sse-time(TB latest_step + DB config).
  const fineTuningStatus = fineStatus?.fine_tuning_status?.status;
  const isRunning = fineTuningStatus === 'running';
  // pending/installing 도 "진행 중"으로 취급 — 설정 dim + 시작 버튼 숨김(중복 시작 방지, codex MED).
  const isActive = ['running', 'pending', 'installing'].includes(fineTuningStatus);
  const isPreparing = fineTuningStatus === 'pending' || fineTuningStatus === 'installing';
  // 완료 시 sse-time(running 게이팅)이 끊겨 progressData 가 null/동결(<100%) → 정의상 완료=100%로 표시.
  const isDone = fineTuningStatus === 'done';
  const sMeta = STATUS_META[fineTuningStatus];
  const hasDataset = datasets.length > 0;
  const percent = progressData?.percent;
  const totalEpoch = progressData?.total_epoch;       // VLM=stage1+stage2 합산(BE sse-time)
  const progressEpoch = progressData?.progress_epoch; // 완료 epoch 수
  const lossLatest = graphData?.['train/loss']?.values?.slice(-1)?.[0];
  const gradLatest = graphData?.['train/grad_norm']?.values?.slice(-1)?.[0];
  const stepsPerEpoch = fineTuningData?.steps_per_epoch; // BasicLineChart "1 Epoch = N steps"
  // 차트 정렬(손실 우선) — graphData 키 순서는 BE/tfevents 의존이라 명시 정렬.
  const orderedCharts = graphData
    ? Object.entries(graphData).sort(([a], [b]) => {
        const rank = (k) => { const i = CHART_ORDER.indexOf(k); return i < 0 ? 99 : i; };
        return rank(a) - rank(b);
      })
    : [];
  // 표시값: 완료면 100%/full epoch 로 고정(sse-time 끊김 보정), 그 외엔 progressData 기준.
  const pctShown = isDone ? 100 : (Number.isFinite(percent) ? Math.floor(percent) : 0);
  const epochShown = isDone
    ? (totalEpoch ? `${totalEpoch}/${totalEpoch}` : '완료')
    : (Number.isFinite(progressEpoch) && totalEpoch ? `${progressEpoch}/${totalEpoch}` : '—');

  // 실 run — vlm_* 하이퍼파라미터를 fine_tuning_config 로 전송(엔진 llm_model_vlm_fine_tuning.py 수신).
  const runVlm = async ({ instanceId, instanceCount, gpuCount }) => {
    // 데이터셋 미바인딩(id=0)이면 스케줄러가 NoneType 으로 크래시 → FE 에서 차단(리뷰 CRITICAL).
    if (!fineTuningData?.model_datasets?.[0]?.id) {
      toast.error('데이터셋을 먼저 바인딩해 주세요.');
      return false;
    }
    const tgts = [...loraTgts].join(',');
    const body = {
      model_id: parseInt(modelId, 10),
      model_dataset_id: fineTuningData?.model_datasets?.[0]?.id ?? 0,
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
    const res = await callApi({ url: 'models/fine-tuning/run', method: 'post', body });
    if (res.status === STATUS_SUCCESS) {
      toast.success('VLM 학습을 시작했습니다.');
      return true;
    }
    errorToastMessage(res.error, res.message);
    return false; // 실패 시 모달 유지
  };

  // 학습 시작 — 플랫폼 공용 인스턴스 모달(자원 할당)을 띄우고 onSubmit 에서 실행.
  const handleTrain = () => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_SETTING',
        modalData: {
          workspaceId,
          modelId,
          onSubmit: async ({ instanceId, instanceCount, gpuCount }) => {
            const ok = await runVlm({ instanceId, instanceCount, gpuCount });
            if (ok && refresh) refresh();    // 성공 후 모델 메타 재조회(상태/그래프는 SSE 가 별도 구독)
            return ok;
          },
          refresh,
        },
      }),
    );
  };

  // 학습 중지 — 일반뷰(TopButtonList)와 동일 계약: body=modelId 직렬화(BE Body(...) 단일 int).
  const stopVlm = async () => {
    if (stopping) return;    // 중복 클릭 → 중복 stop 요청 방지
    setStopping(true);
    try {
      const res = await callApi({
        url: 'models/fine-tuning/stop',
        method: 'post',
        body: JSON.stringify(parseInt(modelId, 10)),
      });
      if (res.status === STATUS_SUCCESS) {
        toast.success('학습 중지를 요청했습니다.');
        if (refresh) refresh();
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      setStopping(false);
    }
  };

  // 데이터셋 바인딩 — 모달 대신 인라인. 워크스페이스 전체 데이터셋을 마운트 시 조회.
  const fetchWsDatasets = useCallback(async () => {
    if (!workspaceId) return;
    const res = await callApi({ url: `options/preprocessing/dataset?workspace_id=${workspaceId}` });
    if (res.status === STATUS_SUCCESS) {
      setWsDatasets(Array.isArray(res.result) ? res.result : []);
    } else {
      errorToastMessage(res.error, res.message);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchWsDatasets();
  }, [fetchWsDatasets]);

  // 데이터셋 클릭 → 선택 + 데이터 파일 조회/평탄화. 빠른 연속 클릭 시 늦게 온 응답이 현재 선택을
  // 덮어쓰지 않도록 요청 토큰(ref)으로 가드(race) + 조회 중 로딩 상태(빈목록 깜빡임 방지).
  const selReqRef = useRef(0);
  const onSelectDataset = async (ds) => {
    const reqId = (selReqRef.current += 1);
    setSelDataset(ds);
    setDsFiles([]);
    setDsFilesLoading(true);
    const res = await callApi({ url: `options/preprocessing/data?dataset_id=${ds.id}` });
    if (reqId !== selReqRef.current) return;    // 더 최신 선택이 있음 → 이 응답 폐기
    setDsFilesLoading(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    // 학습 매니페스트 후보만(이미지 제외): jsonl/json/csv/txt. 1개면 자동 바인딩(데이터셋 선택만으로 끝).
    const files = flattenFiles(res.result).filter((f) => /\.(jsonl|json|csv|txt)$/i.test(f.name || ''));
    setDsFiles(files);
    if (files.length === 1) {
      bindDataset(ds.id, files[0].full_path);
    }
  };

  // 파일 클릭 → 바인딩(add-dataset) → 성공 시 바인딩 목록 갱신 + 선택 접기.
  const bindDataset = async (datasetId, path) => {
    const res = await callApi({
      url: 'models/option/add-dataset',
      method: 'post',
      body: { dataset_id: datasetId, training_data_path: path, model_id: parseInt(modelId, 10) },
    });
    if (res.status === STATUS_SUCCESS) {
      toast.success('데이터셋을 바인딩했습니다.');
      setSelDataset(null);
      setDsFiles([]);
      if (refresh) refresh();
    } else {
      errorToastMessage(res.error, res.message);
    }
  };

  const onDeleteDataset = async (modelDatasetId) => {
    const res = await callApi({
      url: `models/option/model-dataset?model_dataset_id=${modelDatasetId}`,
      method: 'delete',
    });
    if (res.status === STATUS_SUCCESS) {
      if (refresh) refresh();
    } else {
      errorToastMessage(res.error, res.message);
    }
  };

  // freeze 배너 — 비전=항상 동결, projector=trainProj, LLM=LoRA/full(stage2 항상 수행).
  const freezeLayers = [
    { icon: '🔒', name: shortName(visionName), note: 'Vision Encoder (동결)', cls: 'frozen' },
    trainProj
      ? { icon: '⚙', name: 'Projector', note: 'MLP (학습)', cls: 'trainable' }
      : { icon: '🔒', name: 'Projector', note: '동결', cls: 'frozen' },
    trainLLM
      ? { icon: '⚡', name: shortName(llmName), note: 'LoRA 학습', cls: 'lora' }
      : { icon: '⚡', name: shortName(llmName), note: '전체 학습 (full)', cls: 'trainable' },
  ];

  const paramItem = ({ label, val, min, max, step, set, curr }) => (
    <div key={label} className={lx('param-item')}>
      <div className={lx('param-header')}>
        <span className={lx('param-name')}>{label}</span>
        <span className={lx('param-val')}>{val}</span>
      </div>
      <input type='range' className={lx('slider')} min={min} max={max} step={step} value={curr} onChange={(e) => set(Number(e.target.value))} />
    </div>
  );

  return (
    <div id='info-tab' className={cx('info-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        titleName={fineTuningData?.model_name}
        subTitle={`Multimodal · ${shortName(visionName)} + ${shortName(llmName)}`}
      />

      <div className={lx('panel')}>
        {/* 2-컬럼(텍스트 FT 화면과 동일 패턴): 왼쪽=설정(학습 중 dim·내부 스크롤), 오른쪽=모니터링(항상 보임).
            좁은 화면에선 SCSS 미디어쿼리로 1-컬럼 스택. */}
        <div className={lx('config-col', isActive && 'config-col--dim')}>
        <section className={lx('section')}>
          <SectionLabel>학습 데이터셋</SectionLabel>

          {/* 바인딩된 데이터셋 */}
          {datasets.length > 0 && (
            <div className={lx('dataset-list')}>
              {datasets.map((ds) => (
                <div key={ds.id} className={lx('dataset-item')}>
                  <div className={lx('ds-body')}>
                    <div className={lx('ds-name-row')}>
                      <span className={lx('ds-bound-tag')}>바인딩됨</span>
                      <span className={lx('ds-name')}>{ds.dataset_name ?? ds.name ?? `dataset-${ds.id}`}</span>
                    </div>
                  </div>
                  <button type='button' className={lx('ds-del-btn')} onClick={() => onDeleteDataset(ds.id)} aria-label={`${ds.dataset_name ?? ds.name ?? `dataset-${ds.id}`} 데이터셋 제거`}>✕</button>
                </div>
              ))}
            </div>
          )}

          {/* 데이터셋 선택 (워크스페이스 전체, 인라인) */}
          <div className={lx('ds-sub-label')}>데이터셋 선택</div>
          {wsDatasets.length ? (
            <div className={lx('dataset-list')}>
              {wsDatasets.map((ds) => (
                <div
                  key={ds.id}
                  className={lx('dataset-item', selDataset?.id === ds.id && 'dataset-item--on')}
                  role='button'
                  tabIndex={0}
                  onClick={() => onSelectDataset(ds)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectDataset(ds); } }}
                >
                  <div className={lx('ds-body')}>
                    <div className={lx('ds-name-row')}>
                      <span className={lx('ds-name')}>{ds.name}</span>
                    </div>
                  </div>
                  {ds.owner && <span className={lx('ds-owner')}>{ds.owner}</span>}
                </div>
              ))}
            </div>
          ) : (
            <div className={lx('empty')}>워크스페이스에 데이터셋이 없습니다.</div>
          )}

          {/* 데이터 파일 (선택된 데이터셋) — 클릭 시 바인딩 */}
          {selDataset && (
            <>
              <div className={lx('ds-sub-label')}>데이터 파일 · {selDataset.name}</div>
              {dsFilesLoading ? (
                <div className={lx('empty')}>데이터 파일을 불러오는 중…</div>
              ) : dsFiles.length ? (
                <div className={lx('file-list')}>
                  {dsFiles.map((f) => (
                    <div
                      key={f.full_path}
                      className={lx('file-row')}
                      role='button'
                      tabIndex={0}
                      onClick={() => bindDataset(selDataset.id, f.full_path)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); bindDataset(selDataset.id, f.full_path); } }}
                    >
                      <span className={lx('file-name')}>{f.name}</span>
                      <span className={lx('file-bind')}>선택 +</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={lx('empty')}>데이터 파일이 없습니다.</div>
              )}
            </>
          )}
        </section>

        <section className={lx('section')}>
          <SectionLabel>학습 컴포넌트</SectionLabel>
          <div className={lx('train-mode-block')}>
            <div className={lx('train-mode-row')}>
              <span className={lx('train-mode-label')}>학습 대상</span>
              <div className={lx('chip-row')}>
                <Chip label='프로젝터 정렬' selected={trainProj} onClick={() => setTrainProj((v) => !v)} />
                <Chip label='언어모델 LoRA' selected={trainLLM} onClick={() => setTrainLLM((v) => !v)} />
              </div>
            </div>
          </div>
          <div className={lx('train-hint')}>
            언어모델(2단계)은 항상 학습됩니다. &lsquo;프로젝터 정렬&rsquo; 해제 시 1단계는 건너뜁니다. &lsquo;언어모델 LoRA&rsquo; 해제 시 전체(full) 미세조정.
          </div>
          {!trainLLM && (
            <div className={lx('train-warn')}>
              ⚠️ &lsquo;언어모델 LoRA&rsquo; 해제 = 전체(full) 미세조정 — 메모리 사용량이 크게 늘어 GPU 메모리 부족(OOM)이 날 수 있습니다.
            </div>
          )}
        </section>

        <div className={lx('freeze-banner')}>
          {freezeLayers.map(({ icon, name, note, cls }) => (
            <div key={`${name}-${note}`} className={lx('freeze-item', `freeze-item--${cls}`)} aria-label={`${name}: ${note}`}>
              <span className={lx('freeze-icon')} aria-hidden='true'>{icon}</span>
              <div>
                <div className={lx('freeze-name')}>{name}</div>
                <div className={lx('freeze-note')}>{note}</div>
              </div>
            </div>
          ))}
        </div>

        {trainProj && (
          <section className={lx('section')}>
            <SectionLabel>하이퍼파라미터 — 프로젝터 (1단계)</SectionLabel>
            <div className={lx('params-grid')}>
              {[
                { label: 'Learning Rate', val: lr1.toExponential(1), min: 0.0001, max: 0.01, step: 0.0001, set: setLr1, curr: lr1 },
                { label: '에포크 수', val: ep1, min: 1, max: 5, step: 1, set: setEp1, curr: ep1 },
              ].map(paramItem)}
            </div>
          </section>
        )}

        {trainLLM && (
          <section className={lx('section')}>
            <SectionLabel>LoRA 설정</SectionLabel>
            <div className={lx('lora-block')}>
              <div className={lx('params-grid')}>
                {[
                  { label: 'LoRA Rank (r)', val: loraR, min: 4, max: 128, step: 4, set: setLoraR, curr: loraR },
                  { label: 'LoRA Alpha', val: loraA, min: 8, max: 256, step: 8, set: setLoraA, curr: loraA },
                  { label: 'LoRA Dropout', val: loraD.toFixed(2), min: 0, max: 0.3, step: 0.01, set: setLoraD, curr: loraD },
                ].map(paramItem)}
              </div>
              <div className={lx('lora-targets-row')}>
                <span className={lx('lora-targets-label')}>Target Modules</span>
                <div className={lx('chip-row')}>
                  {LORA_TARGETS.map((m) => <Chip key={m} label={m} selected={loraTgts.has(m)} onClick={() => toggleLoraTgt(m)} />)}
                </div>
              </div>
            </div>
          </section>
        )}

        <section className={lx('section')}>
          <SectionLabel>하이퍼파라미터 — 언어모델 (2단계)</SectionLabel>
          <div className={lx('params-grid')}>
            {[
              { label: 'Learning Rate', val: lr2.toExponential(1), min: 0.00001, max: 0.001, step: 0.00001, set: setLr2, curr: lr2 },
              { label: '에포크 수', val: ep2, min: 1, max: 10, step: 1, set: setEp2, curr: ep2 },
              { label: '배치 크기', val: bs2, min: 1, max: 32, step: 1, set: setBs2, curr: bs2 },
              { label: 'Weight Decay', val: wd2.toFixed(3), min: 0, max: 0.1, step: 0.001, set: setWd2, curr: wd2 },
            ].map(paramItem)}
          </div>
        </section>

        <section className={lx('section')}>
          <SectionLabel>데이터 범위</SectionLabel>
          <div className={lx('chip-row')}>
            {[{ label: '전체', v: 0 }, { label: '50', v: 50 }, { label: '200', v: 200 }, { label: '1,000', v: 1000 }, { label: '5,000', v: 5000 }].map(({ label, v }) => (
              <Chip key={v} label={label} selected={Number(maxSamples) === v} onClick={() => setMaxSamples(v)} />
            ))}
          </div>
          <div className={lx('train-hint')}>
            대용량 데이터셋(예: CC3M 595K)은 1회 완주 데모를 위해 일부만 사용할 수 있습니다. &lsquo;전체&rsquo;는 전부 학습합니다.
          </div>
        </section>
        </div>{/* /config-col */}

        {/* 오른쪽: 모니터링(상태·진행·그래프) — 학습 중에도 스크롤 없이 항상 보임. */}
        <div className={lx('monitor-col')}>
        <section className={lx('section')}>
          <div className={lx('control-head')}>
            <SectionLabel>학습 제어</SectionLabel>
            {sMeta && <span className={lx('status-badge', `status-badge--${sMeta.cls}`)}>{sMeta.label}</span>}
          </div>
          {fineTuningStatus === 'error' && fineStatus?.fine_tuning_status?.reason && (
            <div className={lx('train-warn')}>실패 사유: {fineStatus.fine_tuning_status.reason}</div>
          )}
          <div className={lx('train-control')}>
            <div className={lx('train-stats')}>
              {/* 엔진은 단일 train/loss 만 기록(stage1/2 구분 태그 없음) → "학습 Loss" 로 통합 표기. */}
              <div className={lx('stat-card')}><span className={lx('stat-label')}>학습 Loss</span><span className={lx('stat-val')}>{Number.isFinite(lossLatest) ? lossLatest.toFixed(4) : '—'}</span></div>
              <div className={lx('stat-card')}><span className={lx('stat-label')}>Grad Norm</span><span className={lx('stat-val')}>{Number.isFinite(gradLatest) ? gradLatest.toFixed(3) : '—'}</span></div>
              <div className={lx('stat-card')}><span className={lx('stat-label')}>Epoch</span><span className={lx('stat-val')}>{epochShown}</span></div>
              <div className={lx('stat-card')}><span className={lx('stat-label')}>진행률</span><span className={lx('stat-val')}>{pctShown}%</span></div>
            </div>
            <div className={lx('prog-track')}><div className={lx('prog-fill')} style={{ width: `${pctShown}%` }} /></div>
            <div className={lx('train-btn-row')}>
              {isRunning ? (
                <button type='button' className={lx('train-btn', 'train-btn--stop')} onClick={stopVlm} disabled={stopping}>■  학습 중지</button>
              ) : isPreparing ? (
                <button type='button' className={lx('train-btn', 'train-btn--start')} disabled>● 준비 중…</button>
              ) : (
                <button type='button' className={lx('train-btn', 'train-btn--start')} onClick={handleTrain} disabled={!hasDataset} title={!hasDataset ? '학습 데이터셋을 먼저 바인딩하세요.' : undefined}>▶  학습 시작</button>
              )}
            </div>
            {!hasDataset && !isActive && (
              <div className={lx('train-hint')}>학습 데이터셋을 먼저 바인딩하면 시작할 수 있습니다.</div>
            )}
          </div>
        </section>

        <section className={lx('section')}>
          <SectionLabel>학습 추이</SectionLabel>
          {orderedCharts.length > 0 ? (
            <div className={lx('charts-grid')}>
              {orderedCharts.map(([key, value]) => (
                <div key={key} className={lx('chart-card')}>
                  <BasicLineChart
                    title={key}
                    steps={value?.steps ?? []}
                    values={value?.values ?? []}
                    stepsPerEpoch={stepsPerEpoch}
                    checkpoints={checkpoints}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className={lx('chart-card')}>
              <div className={lx('chart-empty')}>
                {isRunning ? '학습 추이를 불러오는 중입니다…' : '학습 시작 후 표시됩니다'}
              </div>
            </div>
          )}
        </section>
        </div>{/* /monitor-col */}
      </div>
    </div>
  );
});

export default MultimodalFineTuningView;
