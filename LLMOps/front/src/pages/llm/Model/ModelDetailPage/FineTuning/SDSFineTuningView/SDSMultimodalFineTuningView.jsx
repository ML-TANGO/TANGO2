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

import { Badge, ButtonV2 } from '@jonathan/ui-react';

import SimpleNav from '../../SimpleNav';
import BasicLineChart from '../FineTuningGraph/BasicLineChart';
import ModelRangeBar from '../ModelRangeBar/ModelRangeBar';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSFineTuningView.module.scss';

// 상태 → 조나단 Badge type 매핑(플랫폼 디자인시스템 재사용).
const BADGE_TYPE = {
  running: 'blue',
  pending: 'yellow',
  installing: 'yellow',
  done: 'green',
  error: 'red',
  stop: 'gray',
  idle: 'gray',
};

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

const LORA_TARGETS = [
  'q_proj',
  'k_proj',
  'v_proj',
  'o_proj',
  'gate_proj',
  'up_proj',
  'down_proj',
];

// 학습 추이 차트 표시 순서(중요도): 손실(train/eval) 먼저 → 진단(grad/lr). 2열 그리드와 합쳐
// 4개일 때 [loss|eval]/[grad|lr] 2×2 로 자연 정렬. 목록에 없는 태그는 뒤로.
const CHART_ORDER = [
  'train/loss',
  'eval/loss',
  'train/grad_norm',
  'train/learning_rate',
];

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
    if (node.type === 'file' && node.full_path)
      out.push({ name: node.name, full_path: node.full_path });
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
    <button
      type='button'
      className={lx('chip', selected && 'chip--on')}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

const SDSMultimodalFineTuningView = memo(function SDSMultimodalFineTuningView({
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
  const datasets = Array.isArray(fineTuningData?.model_datasets)
    ? fineTuningData.model_datasets
    : [];

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
  const toggleLoraTgt = (m) =>
    setLoraTgts((prev) => {
      const s = new Set(prev);
      if (s.has(m)) s.delete(m);
      else s.add(m);
      return s;
    });

  // 데모 샘플 수 제한(0=전체). CC3M 595K 같은 대용량셋은 1회 완주 데모를 위해 소량 캡 권장.
  const [maxSamples, setMaxSamples] = useState(0);
  const [dsFilesLoading, setDsFilesLoading] = useState(false); // 데이터 파일 조회 중(빈목록 깜빡임 방지)
  const [stopping, setStopping] = useState(false); // 중지 요청 in-flight(중복 클릭 방지)
  const [starting, setStarting] = useState(false); // 재학습 시작 optimistic 락(SSE running tick 전 gap 차단)
  // 체크포인트 레지스트리 UI 는 커밋(버전) 상세(ModelCommitListItem)로 이전(Phase 2-C) — 이 화면은
  // 학습/모니터링 전용. 체크포인트=버전에 귀속(커밋 시 commit_checkpoints 로 스냅샷).

  // 학습 모니터링 데이터(부모 SSE 구독에서 props 로 수신). 차트 소스=엔진 TensorBoard
  // (llm_model_vlm_fine_tuning.py 연속-step 콜백). 진행률=sse-time(TB latest_step + DB config).
  const fineTuningStatus = fineStatus?.fine_tuning_status?.status;
  const isRunning = fineTuningStatus === 'running';
  // pending/installing 도 "진행 중"으로 취급 — 설정 dim + 시작 버튼 숨김(중복 시작 방지, codex MED).
  const isActive = ['running', 'pending', 'installing'].includes(
    fineTuningStatus,
  );
  const isPreparing =
    fineTuningStatus === 'pending' || fineTuningStatus === 'installing';
  // 완료 시 sse-time(running 게이팅)이 끊겨 progressData 가 null/동결(<100%) → 정의상 완료=100%로 표시.
  const isDone = fineTuningStatus === 'done';
  const sMeta = STATUS_META[fineTuningStatus];
  // 커밋(저장) 상태 — sse-status(commit_status) 는 modality 무관(get_model 직접 읽음)이라 VLM 모델도
  // 그대로 수신. 학습 done 후 merged LLaVA(latest_checkpoint)를 버전드 commit_model 로 저장.
  const commitStatusVal = fineStatus?.commit_status?.status;
  const isCommitting = commitStatusVal === 'running'; // 커밋 잡(copy_commit_model) 실제 진행 중(라벨/스피너)
  // 커밋 버튼 비활성 게이트: SSE 첫 tick 전(null)·running 이면 차단 — 중복 커밋/상태 미확정 방지
  // (텍스트 FT 의 TopButtonList.isCalCommitLoad: !commitStatus||running → disabled 와 동형).
  const commitBlocked = !commitStatusVal || isCommitting;
  // 커밋 불러오기 / 시스템 로그 게이팅.
  // 시스템 로그: 상태 미확정 외엔 항상 노출 — 학습/커밋 에러 시에도 파드 로그로 진단해야 하므로
  // download-error 게이트는 두지 않음(텍스트 FT isCalSystemlog 와 의도적 차이, 리뷰 반영).
  const logBlocked = !commitStatusVal || !fineTuningStatus;
  // 커밋 불러오기: 학습 active(running/pending/installing)·커밋 in-flight·상태 미확정 시 비활성.
  const loadBlocked = logBlocked || isActive || isCommitting;
  // 초기 모델 로드(다운로드)·커밋(저장/불러오기/중지)을 상단 배너로 명시하고, 그 동안 설정 컬럼을 잠근다.
  // 상태/메시지 계약은 텍스트 FT 의 TopButtonList.isCalMessage 를 미러(동일 i18n 키 재사용). 학습 상태
  // (pending/installing/running/done)는 우측 '학습 제어' 배지·버튼이 이미 표시하므로 배너에서는 제외.
  const commitType = fineStatus?.commit_status?.type;
  const commitBanner = (() => {
    if (!commitStatusVal || commitStatusVal === 'done') return null;
    if (commitStatusVal === 'error') {
      // 다운로드 실패만 배너로(모델 재생성 유도). 그 외 커밋 에러는 토스트 처리 — 중복 방지.
      return commitType === 'download'
        ? { msg: 'finetuning.commit.error.message', tone: 'error' }
        : null;
    }
    const byType = {
      download: 'finetuning.commit.download.message', // 초기 모델 로드(생성)
      commit: 'finetuning.commit.save.message',
      load: 'finetuning.commit.load.message',
      stop: 'finetuning.commit.stop.message',
    };
    return {
      msg: byType[commitType] || 'finetuning.commit.download.message',
      tone: 'load',
    };
  })();
  // 설정 잠금 게이트: 학습 active(running/pending/installing) + 커밋/로드/다운로드 진행 중.
  const isBusy = isActive || isCommitting;
  const hasDataset = datasets.length > 0;
  const percent = progressData?.percent;
  const totalEpoch = progressData?.total_epoch; // VLM=stage1+stage2 합산(BE sse-time)
  const progressEpoch = progressData?.progress_epoch; // 완료 epoch 수
  const lossLatest = graphData?.['train/loss']?.values?.slice(-1)?.[0];
  const gradLatest = graphData?.['train/grad_norm']?.values?.slice(-1)?.[0];
  const stepsPerEpoch = fineTuningData?.steps_per_epoch; // BasicLineChart "1 Epoch = N steps"
  // 차트 정렬(손실 우선) — graphData 키 순서는 BE/tfevents 의존이라 명시 정렬.
  const orderedCharts = graphData
    ? Object.entries(graphData).sort(([a], [b]) => {
        const rank = (k) => {
          const i = CHART_ORDER.indexOf(k);
          return i < 0 ? 99 : i;
        };
        return rank(a) - rank(b);
      })
    : [];
  // 표시값: 완료면 100%/full epoch 로 고정(sse-time 끊김 보정), 그 외엔 progressData 기준.
  const pctShown = isDone
    ? 100
    : Number.isFinite(percent)
      ? Math.floor(percent)
      : 0;
  const epochShown = isDone
    ? totalEpoch
      ? `${totalEpoch}/${totalEpoch}`
      : '완료'
    : Number.isFinite(progressEpoch) && totalEpoch
      ? `${progressEpoch}/${totalEpoch}`
      : '—';

  // 재학습 optimistic 락 해제 — SSE 가 active(pending/installing/running) tick 을 전달하면 해제.
  // done→running gap(수 초) 동안 커밋/재학습 버튼 노출·재진입을 막는 로컬 가드(stopping 패턴 동형, 리뷰 HIGH).
  useEffect(() => {
    if (isActive) setStarting(false);
  }, [isActive]);

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
    const res = await callApi({
      url: 'models/fine-tuning/run',
      method: 'post',
      body,
    });
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
            if (ok) {
              setStarting(true); // SSE running tick 전까지 커밋/재학습 버튼 잠금(done→running 레이스 차단)
              if (refresh) refresh(); // 성공 후 모델 메타 재조회(상태/그래프는 SSE 가 별도 구독)
            }
            return ok;
          },
          refresh,
        },
      }),
    );
  };

  // 학습 중지 — 일반뷰(TopButtonList)와 동일 계약: body=modelId 직렬화(BE Body(...) 단일 int).
  const stopVlm = async () => {
    if (stopping) return; // 중복 클릭 → 중복 stop 요청 방지
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

  // 학습 완료 후 결과 저장(커밋) — merged LLaVA(latest_checkpoint)를 버전드 commit_model 로 복사.
  // 텍스트 FT 와 동일한 modality-agnostic 경로: FINETUNING_COMMIT 모달(부모 FineTuning 이 loadModalComponent
  // 등록) → POST models/commit-models → copy_commit_model 헬름(is_commit=0, shutil.copytree 로 LLaVA
  // config/processor/tokenizer 전부 복사). 저장본은 상위 '커밋 리스트' 탭에서 평가·양자화에 재사용.
  const handleCommit = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_COMMIT',
        // modelId 는 라우트 파라미터(문자열) → 다른 호출부(runVlm/stopVlm)와 동일하게 정수화(리뷰 HIGH).
        // stop:false 명시 — 모달은 stop truthy 면 stopURL 로 분기(falsy=commit). 암묵 undefined 제거.
        modalData: {
          workspaceId,
          modelId: parseInt(modelId, 10),
          refresh,
          stop: false,
        },
      }),
    );
  }, [dispatch, workspaceId, modelId, refresh]);

  // 커밋 불러오기 — 저장된 commit_model 을 활성 모델(latest_checkpoint)로 로드(텍스트 FT 와 동일 모달/엔드포인트).
  // 부모 FineTuning 이 FINETUNING_COMMIT_LOAD 등록. 모달이 commit 목록 조회→선택→POST models/commit-models/load.
  // VLM 은 항상 latest_checkpoint 에서 학습하므로 getCommitId(이어학습 commit_id 피드)는 불필요 → no-op.
  const handleCommitLoad = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_COMMIT_LOAD',
        modalData: {
          workspaceId,
          modelId: parseInt(modelId, 10),
          getCommitId: () => {},
          refresh,
        },
      }),
    );
  }, [dispatch, workspaceId, modelId, refresh]);

  // 시스템 로그 — 학습 파드 로그 조회(텍스트 FT 와 동일 모달). 내부 모델이라 models/fine-tuning/system-log 경로.
  const handleSystemLog = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_SYSTEM_LOG',
        modalData: {
          workspaceId,
          modelId: parseInt(modelId, 10),
          modelName: fineTuningData?.model_name,
        },
      }),
    );
  }, [dispatch, workspaceId, modelId, fineTuningData]);

  // 데이터셋 바인딩 — 모달 대신 인라인. 워크스페이스 전체 데이터셋을 마운트 시 조회.
  const fetchWsDatasets = useCallback(async () => {
    if (!workspaceId) return;
    const res = await callApi({
      url: `options/preprocessing/dataset?workspace_id=${workspaceId}`,
    });
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
    const res = await callApi({
      url: `options/preprocessing/data?dataset_id=${ds.id}`,
    });
    if (reqId !== selReqRef.current) return; // 더 최신 선택이 있음 → 이 응답 폐기
    setDsFilesLoading(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    // 학습 매니페스트 후보만(이미지 제외): jsonl/json/csv/txt. 1개면 자동 바인딩(데이터셋 선택만으로 끝).
    const files = flattenFiles(res.result).filter((f) =>
      /\.(jsonl|json|csv|txt)$/i.test(f.name || ''),
    );
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
      body: {
        dataset_id: datasetId,
        training_data_path: path,
        model_id: parseInt(modelId, 10),
      },
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
    {
      name: shortName(visionName),
      note: 'Vision Encoder (동결)',
      cls: 'frozen',
    },
    trainProj
      ? { name: 'Projector', note: 'MLP (학습)', cls: 'trainable' }
      : { name: 'Projector', note: '동결', cls: 'frozen' },
    trainLLM
      ? { name: shortName(llmName), note: 'LoRA 학습', cls: 'lora' }
      : {
          name: shortName(llmName),
          note: '전체 학습 (full)',
          cls: 'trainable',
        },
  ];

  const paramItem = ({ label, min, max, step, set, curr }) => (
    <ModelRangeBar
      key={label}
      label={label}
      value={curr}
      min={min}
      max={max}
      step={step}
      onChange={(e) => set(Number(e.target.value))}
    />
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

      {/* 초기 모델 로드(다운로드)·커밋 진행 상단 배너 — 진행 중 config-col 은 아래에서 잠금(클릭 방지). */}
      {commitBanner && (
        <div
          className={lx('top-banner', `top-banner--${commitBanner.tone}`)}
          role='status'
        >
          {commitBanner.tone !== 'error' && (
            <span className={lx('top-banner-spinner')} aria-hidden='true' />
          )}
          <span>{t(commitBanner.msg)}</span>
        </div>
      )}

      <div className={lx('panel')}>
        {/* 2-컬럼(텍스트 FT 화면과 동일 패턴): 왼쪽=설정(학습 중 dim·내부 스크롤), 오른쪽=모니터링(항상 보임).
            좁은 화면에선 SCSS 미디어쿼리로 1-컬럼 스택. */}
        <div className={lx('config-col', isBusy && 'config-col--dim')}>
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
                        <span className={lx('ds-name')}>
                          {ds.dataset_name ?? ds.name ?? `dataset-${ds.id}`}
                        </span>
                      </div>
                    </div>
                    <button
                      type='button'
                      className={lx('ds-del-btn')}
                      onClick={() => onDeleteDataset(ds.id)}
                      aria-label={`${ds.dataset_name ?? ds.name ?? `dataset-${ds.id}`} 데이터셋 제거`}
                    >
                      ✕
                    </button>
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
                    className={lx(
                      'dataset-item',
                      selDataset?.id === ds.id && 'dataset-item--on',
                    )}
                    role='button'
                    tabIndex={0}
                    onClick={() => onSelectDataset(ds)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelectDataset(ds);
                      }
                    }}
                  >
                    <div className={lx('ds-body')}>
                      <div className={lx('ds-name-row')}>
                        <span className={lx('ds-name')}>{ds.name}</span>
                      </div>
                    </div>
                    {ds.owner && (
                      <span className={lx('ds-owner')}>{ds.owner}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className={lx('empty')}>
                워크스페이스에 데이터셋이 없습니다.
              </div>
            )}

            {/* 데이터 파일 (선택된 데이터셋) — 클릭 시 바인딩 */}
            {selDataset && (
              <>
                <div className={lx('ds-sub-label')}>
                  데이터 파일 · {selDataset.name}
                </div>
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
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            bindDataset(selDataset.id, f.full_path);
                          }
                        }}
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
                  <Chip
                    label='프로젝터 정렬'
                    selected={trainProj}
                    onClick={() => setTrainProj((v) => !v)}
                  />
                  <Chip
                    label='언어모델 LoRA'
                    selected={trainLLM}
                    onClick={() => setTrainLLM((v) => !v)}
                  />
                </div>
              </div>
            </div>
            <div className={lx('train-hint')}>
              언어모델(2단계)은 항상 학습됩니다. &lsquo;프로젝터 정렬&rsquo;
              해제 시 1단계는 건너뜁니다. &lsquo;언어모델 LoRA&rsquo; 해제 시
              전체(full) 미세조정.
            </div>
            {!trainLLM && (
              <div className={lx('train-warn')}>
                ⚠️ &lsquo;언어모델 LoRA&rsquo; 해제 = 전체(full) 미세조정 —
                메모리 사용량이 크게 늘어 GPU 메모리 부족(OOM)이 날 수 있습니다.
              </div>
            )}
          </section>

          <div className={lx('freeze-banner')}>
            {freezeLayers.map(({ name, note, cls }) => (
              <div
                key={`${name}-${note}`}
                className={lx('freeze-item', `freeze-item--${cls}`)}
                aria-label={`${name}: ${note}`}
              >
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
                  {
                    label: 'Learning Rate',
                    min: 0.0001,
                    max: 0.01,
                    step: 0.0001,
                    set: setLr1,
                    curr: lr1,
                  },
                  {
                    label: '에포크 수',
                    min: 1,
                    max: 5,
                    step: 1,
                    set: setEp1,
                    curr: ep1,
                  },
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
                    {
                      label: 'LoRA Rank (r)',
                      min: 4,
                      max: 128,
                      step: 4,
                      set: setLoraR,
                      curr: loraR,
                    },
                    {
                      label: 'LoRA Alpha',
                      min: 8,
                      max: 256,
                      step: 8,
                      set: setLoraA,
                      curr: loraA,
                    },
                    {
                      label: 'LoRA Dropout',
                      min: 0,
                      max: 0.3,
                      step: 0.01,
                      set: setLoraD,
                      curr: loraD,
                    },
                  ].map(paramItem)}
                </div>
                <div className={lx('lora-targets-row')}>
                  <span className={lx('lora-targets-label')}>
                    Target Modules
                  </span>
                  <div className={lx('chip-row')}>
                    {LORA_TARGETS.map((m) => (
                      <Chip
                        key={m}
                        label={m}
                        selected={loraTgts.has(m)}
                        onClick={() => toggleLoraTgt(m)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </section>
          )}

          <section className={lx('section')}>
            <SectionLabel>하이퍼파라미터 — 언어모델 (2단계)</SectionLabel>
            <div className={lx('params-grid')}>
              {[
                {
                  label: 'Learning Rate',
                  min: 0.00001,
                  max: 0.001,
                  step: 0.00001,
                  set: setLr2,
                  curr: lr2,
                },
                {
                  label: '에포크 수',
                  min: 1,
                  max: 10,
                  step: 1,
                  set: setEp2,
                  curr: ep2,
                },
                {
                  label: '배치 크기',
                  min: 1,
                  max: 32,
                  step: 1,
                  set: setBs2,
                  curr: bs2,
                },
                {
                  label: 'Weight Decay',
                  min: 0,
                  max: 0.1,
                  step: 0.001,
                  set: setWd2,
                  curr: wd2,
                },
              ].map(paramItem)}
            </div>
          </section>

          <section className={lx('section')}>
            <SectionLabel>데이터 범위</SectionLabel>
            <div className={lx('chip-row')}>
              {[
                { label: '전체', v: 0 },
                { label: '50', v: 50 },
                { label: '200', v: 200 },
                { label: '1,000', v: 1000 },
                { label: '5,000', v: 5000 },
              ].map(({ label, v }) => (
                <Chip
                  key={v}
                  label={label}
                  selected={Number(maxSamples) === v}
                  onClick={() => setMaxSamples(v)}
                />
              ))}
            </div>
            <div className={lx('train-hint')}>
              대용량 데이터셋(예: CC3M 595K)은 1회 완주 데모를 위해 일부만
              사용할 수 있습니다. &lsquo;전체&rsquo;는 전부 학습합니다.
            </div>
          </section>
        </div>
        {/* /config-col */}

        {/* 오른쪽: 모니터링(상태·진행·그래프) — 학습 중에도 스크롤 없이 항상 보임. */}
        <div className={lx('monitor-col')}>
          <section className={lx('section')}>
            <div className={lx('control-head')}>
              <SectionLabel>학습 제어</SectionLabel>
              {sMeta && (
                <Badge
                  label={sMeta.label}
                  type={BADGE_TYPE[sMeta.cls] || 'gray'}
                  size='sm'
                />
              )}
              {/* 유틸 액션(텍스트 FT TopButtonList 미러): 커밋 불러오기 + 시스템 로그. 우측 정렬. */}
              <div className={lx('head-actions')}>
                <ButtonV2
                  type='solid'
                  colorType='skyblue'
                  size='l'
                  label='커밋 불러오기'
                  onClick={handleCommitLoad}
                  disabled={loadBlocked}
                />
                <ButtonV2
                  type='solid'
                  colorType='skyblue'
                  size='l'
                  label='시스템 로그'
                  onClick={handleSystemLog}
                  disabled={logBlocked}
                />
                {isRunning ? (
                  <ButtonV2
                    type='solid'
                    colorType='red'
                    size='l'
                    label='학습 중지'
                    onClick={stopVlm}
                    disabled={stopping}
                  />
                ) : isPreparing ? (
                  <ButtonV2
                    type='solid'
                    size='l'
                    label='준비 중…'
                    disabled
                    isLoading
                  />
                ) : (
                  <ButtonV2
                    type='solid'
                    size='l'
                    label={isDone ? '다시 학습' : '학습 시작'}
                    onClick={handleTrain}
                    disabled={!hasDataset || isCommitting || starting}
                  />
                )}
              </div>
            </div>
            {fineTuningStatus === 'error' &&
              fineStatus?.fine_tuning_status?.reason && (
                <div className={lx('train-warn')}>
                  실패 사유: {fineStatus.fine_tuning_status.reason}
                </div>
              )}
            <div className={lx('train-control')}>
              <div className={lx('train-stats')}>
                {/* 엔진은 단일 train/loss 만 기록(stage1/2 구분 태그 없음) → "학습 Loss" 로 통합 표기. */}
                <div className={lx('stat-card')}>
                  <span className={lx('stat-label')}>학습 Loss</span>
                  <span className={lx('stat-val')}>
                    {Number.isFinite(lossLatest) ? lossLatest.toFixed(4) : '—'}
                  </span>
                </div>
                <div className={lx('stat-card')}>
                  <span className={lx('stat-label')}>Grad Norm</span>
                  <span className={lx('stat-val')}>
                    {Number.isFinite(gradLatest) ? gradLatest.toFixed(3) : '—'}
                  </span>
                </div>
                <div className={lx('stat-card')}>
                  <span className={lx('stat-label')}>Epoch</span>
                  <span className={lx('stat-val')}>{epochShown}</span>
                </div>
                <div className={lx('stat-card')}>
                  <span className={lx('stat-label')}>진행률</span>
                  <span className={lx('stat-val')}>{pctShown}%</span>
                </div>
              </div>
              <div className={lx('prog-track')}>
                <div
                  className={lx('prog-fill')}
                  style={{ width: `${pctShown}%` }}
                />
              </div>
              <div className={lx('train-btn-row')}>
                {/* 학습 완료 시에만 저장(커밋) — merged LLaVA 는 stage2 정상 완료 후에만 latest_checkpoint 에
                  존재(중지/실패 시점엔 머지 산출물 없음) → done 게이트(텍스트 FT 의 done/stop/error 와 의도적
                  차이). 재학습 시작 직후(starting)엔 숨김 + 커밋 잡 in-flight/상태 미확정(commitBlocked)이면 비활성. */}
                {isDone && !starting && (
                  <ButtonV2
                    type='solid'
                    colorType='blue'
                    size='m'
                    label={isCommitting ? '저장 중…' : '학습 결과 저장'}
                    onClick={handleCommit}
                    disabled={commitBlocked}
                    isLoading={isCommitting}
                  />
                )}
              </div>
              {!hasDataset && !isActive && (
                <div className={lx('train-hint')}>
                  학습 데이터셋을 먼저 바인딩하면 시작할 수 있습니다.
                </div>
              )}
              {isDone && !starting && (
                <div className={lx('train-hint')}>
                  {isCommitting
                    ? '저장(커밋) 작업이 진행 중입니다. 완료 후 ‘커밋 리스트’ 탭에서 확인할 수 있습니다.'
                    : '학습 결과를 저장하면 ‘커밋 리스트’ 탭에서 평가·양자화에 사용할 수 있습니다.'}
                </div>
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
                  {isRunning
                    ? '학습 추이를 불러오는 중입니다…'
                    : '학습 시작 후 표시됩니다'}
                </div>
              </div>
            )}
          </section>
        </div>
        {/* /monitor-col */}
      </div>
    </div>
  );
});

export default SDSMultimodalFineTuningView;
