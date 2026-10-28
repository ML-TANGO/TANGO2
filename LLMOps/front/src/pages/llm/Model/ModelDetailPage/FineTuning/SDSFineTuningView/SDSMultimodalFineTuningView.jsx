// Multimodal (VLM) FineTuning 화면 — 상위 '파인튜닝' 탭 선택 시 학습 폼을 바로 표시.
//
// 골격 = 하우스 파인튜닝 화면과 **같은** `FineTuningShell`(설계 §3-A, Phase 3):
//   SimpleNav(topButtonList=SDSTopButtons) → [commitBanner] → box{ left{ left-top,
//   InstanceSetting } , right{ SDSMonitorSummary + FineTuningGraph } }.
// 자체 `panel`/`config-col`/`monitor-col` 2컬럼 그리드와 자체 어휘(`SectionLabel`·
// `Chip`)를 폐기하고 하우스 어휘로 치환했다 — `cx('title')` / `Radio` / `Checkbox`
// (설계 §3-D). 좌측 섹션은 하우스와 물리적으로 같은 클래스(`model-box` /
// `training-data-box` / `type-box` / `flex-16` / `border` / `range-checkbox`)를 쓴다.
//
// ⚠️ SSE (설계 §5-B 불변식 S1·S2): 이 화면은 부모 `FineTuning.jsx` 가 단일 구독한
//    internal SSE 결과를 **props 로 소비**한다(external 뷰와 반대). 여기서도, 셸에서도
//    SSE 훅을 구독하지 않는다 — 이중 구독 시 잘못된 상태로 화면이 덮인다.
// ⚠️ payload (설계 §4): `fine_tuning_config` 18키 조립은 순수 `buildVlmRunBody` 가
//    소유한다. 이 파일은 폼 값만 넘기고 키 이름·캐스팅에 절대 개입하지 않는다.
//
// 원칙([[feedback_mockup_drives_design]]): 화면/UI 는 목업에 충실하되, 플랫폼 정책/엔진
// 계약과 충돌하거나 변경 공수가 비대칭인 컨트롤은 플랫폼에 맞춘다.
//   - 자원 할당: 플랫폼은 인스턴스 단위 스케줄링 → 공용 인스턴스 모달(FINETUNING_SETTING),
//     실제 배정값은 좌측 하단 하우스 `InstanceSetting`(BE resource_info, 설계 §6-C).
//   - projector 구조 선택(7종)·Hidden Dim: HF Llava 표준 재로드가 커스텀 구조를 거부(실증) → 제거.
//   - 데이터셋: 하우스와 동일하게 바인딩 목록=`DataList`, 선택=`FINETUNING_DATA_UPLOAD`
//     모달(설계 D4 — 인라인 3단 피커 폐기).
//   - 하이퍼파라미터: 엔진이 받는 것만 노출·배선.

import { memo, useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import { ButtonV2, Checkbox, Radio } from '@jonathan/ui-react';

import DataList from '../DataList';
import FineTuningGraph from '../FineTuningGraph';
import FineTuningShell from '../FineTuningShell';
import InstanceSetting from '../InstanceSetting';
import ModelRangeBar from '../ModelRangeBar/ModelRangeBar';
import { toMonitorProps } from './monitorProps';
import { buildVlmRunBody } from './payload/vlmConfig';
import { formatPercentLabel, toPercentValue } from './progressFormat';
import SDSMonitorSummary from './SDSMonitorSummary';
import SDSTopButtons from './SDSTopButtons';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSFineTuningView.module.scss';

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

// 데모 샘플 수 제한(0=전체). 배타 선택이라 하우스 `Radio`(fineTuningTypeOptions 패턴)와
// 동형 — 자체 `Chip` 폐기(설계 §2-B #10).
const MAX_SAMPLES_OPTIONS = [
  { label: '전체', value: 0 },
  { label: '50', value: 50 },
  { label: '200', value: 200 },
  { label: '1,000', value: 1000 },
  { label: '5,000', value: 5000 },
];

// 학습 추이 차트 표시 순서(중요도): 손실(train/eval) 먼저 → 진단(grad/lr). 목록에 없는
// 태그는 뒤로. 하우스 `FineTuningGraph` 는 `Object.entries` 삽입 순서로 그리므로
// 넘기기 전에 키 순서를 정렬해 현재 표시 순서를 보존한다(컴포넌트 무수정).
const CHART_ORDER = [
  'train/loss',
  'eval/loss',
  'train/grad_norm',
  'train/learning_rate',
];

// HF id / 긴 경로가 402px 좌측 컬럼을 넘길 수 있는데 하우스 `.name` 에는 break 규칙이
// 없다 → 하우스 SCSS 를 고치지 않고 값 쪽만 처리(external 뷰와 동일 패턴).
const breakAllStyle = { wordBreak: 'break-all' };

// 학습/커밋 진행 중 설정 컬럼 잠금. 셸의 `dimLeft` 는 하우스와 동일하게 opacity 만
// 주므로(하우스 `.left.disabled`), MM 이 원래 갖고 있던 클릭 차단 가드
// (`config-col--dim` 의 pointer-events/user-select)를 여기서 유지한다.
const LOCKED_STYLE = { pointerEvents: 'none', userSelect: 'none' };

const shortName = (id) => {
  if (!id) return '-';
  const parts = String(id).split('/');
  return parts[parts.length - 1];
};

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

  // 모델 바인딩 데이터셋. 바인딩=FINETUNING_DATA_UPLOAD 모달, 해제=DataList 의 ✕.
  const datasets = Array.isArray(fineTuningData?.model_datasets)
    ? fineTuningData.model_datasets
    : [];

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
  // (pending/installing/running/done)는 우측 요약 카드의 배지·상단 버튼이 이미 표시하므로 배너에서는 제외.
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
  // 차트 정렬(손실 우선) — graphData 키 순서는 BE/tfevents 의존이라 명시 정렬 후 넘긴다.
  // null/undefined 는 그대로 통과(FineTuningGraph 의 no-data 분기 유지).
  const orderedGraphData = graphData
    ? Object.fromEntries(
        Object.entries(graphData).sort(([a], [b]) => {
          const rank = (k) => {
            const i = CHART_ORDER.indexOf(k);
            return i < 0 ? 99 : i;
          };
          return rank(a) - rank(b);
        }),
      )
    : graphData;
  // 표시값: 완료면 100%/full epoch 로 고정(sse-time 끊김 보정, 설계 §5-B S6), 그 외엔
  // progressData 기준. 바 width 는 숫자, 라벨은 1% 미만에서 소수 2자리(progressFormat 참조).
  const pctValue = isDone ? 100 : toPercentValue(percent);
  const pctShown = isDone ? '100' : formatPercentLabel(percent);
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
      toast.error(t('finetuning.dataset.required.message'));
      return false;
    }
    // body 조립은 순수 buildVlmRunBody(payload/vlmConfig.js) — 키 이름·캐스팅이
    // 엔진 계약이라 UI 와 분리해 legacy 대조 차분 검증 대상으로 둔다.
    const body = buildVlmRunBody({
      modelId,
      modelDatasetId: fineTuningData?.model_datasets?.[0]?.id,
      instanceId,
      instanceCount,
      gpuCount,
      form: {
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
        loraTargets: loraTgts,
        maxSamples,
      },
    });
    const res = await callApi({
      url: 'models/fine-tuning/run',
      method: 'post',
      body,
    });
    if (res.status === STATUS_SUCCESS) {
      toast.success(t('finetuning.start.success.message'));
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
        toast.success(t('finetuning.stop.requested.message'));
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

  // 데이터셋 선택/바인딩 — 하우스와 **같은** FINETUNING_DATA_UPLOAD 모달(설계 D4).
  // 모달의 바인딩 계약이 폐기된 인라인 피커와 동일함은 실측 확인됨
  // (FineTuningDataUploadModal.jsx:143–151 = POST models/option/add-dataset
  //  {dataset_id, training_data_path, model_id}). 모달 등록(loadModalComponent)은
  // 부모 FineTuning.jsx:450 이 이미 수행한다(분기 이전 useEffect).
  // modelId 는 다른 호출부와 동일하게 정수화해 넘긴다(인라인 bindDataset 과 같은 와이어 값).
  const onClickUpload = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_DATA_UPLOAD',
        modalData: {
          workspaceId,
          modelId: parseInt(modelId, 10),
          git: fineTuningData?.huggingface_git,
          refresh,
        },
      }),
    );
  }, [dispatch, workspaceId, modelId, fineTuningData, refresh]);

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

  // 하이퍼파라미터 슬라이더 — 하우스와 동일한 `ModelRangeBar`(무수정). 값은 반드시
  // 로컬 state(설계 R10: 부모가 SDS 분기에서 redux `range` 초기화를 건너뛴다).
  const paramItem = ({ label, min, max, step, set, curr }) => (
    <ModelRangeBar
      key={label}
      label={label}
      value={curr}
      min={min}
      max={max}
      step={step}
      disabled={isBusy}
      onChange={(e) => set(Number(e.target.value))}
    />
  );

  // 학습 대상/LoRA 타깃 체크박스 — 하우스 `range-checkbox` + `Checkbox` 어휘
  // (하우스 Load in 8bit / Use LoRA / VLM 2-stage 와 동형). 자체 `Chip` 폐기.
  const checkRow = ({ key, label, checked, onToggle }) => (
    <div
      key={key ?? label}
      className={cx('range-checkbox', isBusy && 'disabled')}
    >
      {label}
      <Checkbox
        checked={checked}
        onChange={() => {
          if (!isBusy) onToggle();
        }}
        disabled={isBusy}
      />
    </div>
  );

  // ── 상단 버튼줄 — 하우스와 같은 자리(`SimpleNav.topButtonList`)·같은 위계(설계 §3-D):
  //    시스템 로그 / 커밋 불러오기 / 학습 결과 저장 = solid l skyblue,
  //    실행(학습 시작·다시 학습) = solid l (기본 blue), 중지 = solid l red.
  //    게이트(logBlocked/loadBlocked/commitBlocked/starting/stopping)는 **값 그대로**
  //    이관한다 — 하우스 `TopButtonList` 는 재사용하지 않는다(설계 R11: MM 커밋은
  //    merged LLaVA 가 done 후에만 존재해 하우스보다 엄격한 isDone 게이트가 필요).
  const topButtons = (
    <SDSTopButtons
      buttons={[
        {
          key: 'systemLog',
          label: '시스템 로그',
          colorType: 'skyblue',
          onClick: handleSystemLog,
          disabled: logBlocked,
        },
        {
          key: 'commitLoad',
          label: '커밋 불러오기',
          colorType: 'skyblue',
          onClick: handleCommitLoad,
          disabled: loadBlocked,
        },
        isDone &&
          !starting && {
            key: 'commit',
            label: isCommitting ? '저장 중…' : '학습 결과 저장',
            colorType: 'skyblue',
            onClick: handleCommit,
            disabled: commitBlocked,
            isLoading: isCommitting,
          },
        isRunning
          ? {
              key: 'stop',
              label: '학습 중지',
              colorType: 'red',
              onClick: stopVlm,
              disabled: stopping,
            }
          : isPreparing
            ? {
                key: 'preparing',
                label: '준비 중…',
                disabled: true,
                isLoading: true,
              }
            : {
                key: 'run',
                label: isDone ? '다시 학습' : '학습 시작',
                onClick: handleTrain,
                disabled: !hasDataset || isCommitting || starting,
              },
      ]}
    />
  );

  // ── 좌측 — 하우스 `.left-top` 안에 하우스 클래스로 섹션을 쌓는다(설계 §3-B).
  //    1 모델 / 2 학습 데이터 / 3 학습 대상(freeze) / 4 하이퍼파라미터(1단계) /
  //    5 LoRA 설정 / 6 하이퍼파라미터(2단계) / 7 데이터 범위.
  //    섹션 사이 구분은 하우스 `border` 디바이더(자체 카드 중첩 폐기).
  const leftSections = (
    <div style={isBusy ? LOCKED_STYLE : undefined}>
      <div className={cx('model-box')}>
        <div className={cx('title')}>{t('model.label')}</div>
        <div className={cx('name')} style={breakAllStyle}>
          {fineTuningData?.model_name || '-'}
        </div>
        <div className={cx('title')}>Vision Encoder</div>
        <div className={cx('name')} style={breakAllStyle}>
          {visionName || '-'}
        </div>
        <div className={cx('title')}>Language Model</div>
        <div className={cx('name')} style={breakAllStyle}>
          {llmName || '-'}
        </div>
      </div>

      <div className={cx('training-data-box')}>
        <div className={cx('title')}>{t('trainingData.label')}</div>
        {hasDataset ? (
          <DataList
            list={datasets}
            disable={isBusy}
            onClickDelete={onDeleteDataset}
            t={t}
          />
        ) : (
          <ButtonV2
            type='outline'
            size='l'
            label={t('trainingDataSelect.label')}
            onClick={onClickUpload}
            disabled={isBusy}
            style={{ width: '100%' }}
          />
        )}
      </div>

      <div className={cx('type-box')}>
        <div className={cx('title')}>학습 대상</div>
        <div className={cx('flex-16')}>
          {[
            {
              key: 'trainProj',
              label: '프로젝터 정렬',
              checked: trainProj,
              onToggle: () => setTrainProj((v) => !v),
            },
            {
              key: 'trainLLM',
              label: '언어모델 LoRA',
              checked: trainLLM,
              onToggle: () => setTrainLLM((v) => !v),
            },
          ].map(checkRow)}
        </div>
        <div className={lx('train-hint')}>
          언어모델(2단계)은 항상 학습됩니다. &lsquo;프로젝터 정렬&rsquo; 해제 시
          1단계는 건너뜁니다. &lsquo;언어모델 LoRA&rsquo; 해제 시 전체(full)
          미세조정.
        </div>
        {!trainLLM && (
          <div className={lx('train-warn')}>
            ⚠️ &lsquo;언어모델 LoRA&rsquo; 해제 = 전체(full) 미세조정 — 메모리
            사용량이 크게 늘어 GPU 메모리 부족(OOM)이 날 수 있습니다.
          </div>
        )}
        {/* freeze 배너 — 입력이 아니라 위 토글의 파생 표시(읽기전용, 설계 §3-B 얹음 E) */}
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
          <>
            <div className={cx('border')}></div>
            <div className={cx('title')}>하이퍼파라미터 — 프로젝터 (1단계)</div>
            <div className={cx('flex-16')}>
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
          </>
        )}

        {trainLLM && (
          <>
            <div className={cx('border')}></div>
            <div className={cx('title')}>LoRA 설정</div>
            <div className={cx('flex-16')}>
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
            <div className={cx('title')} style={{ margin: '16px 0' }}>
              Target Modules
            </div>
            <div className={cx('flex-16')}>
              {LORA_TARGETS.map((m) =>
                checkRow({
                  key: m,
                  label: m,
                  checked: loraTgts.has(m),
                  onToggle: () => toggleLoraTgt(m),
                }),
              )}
            </div>
          </>
        )}

        <div className={cx('border')}></div>
        <div className={cx('title')}>하이퍼파라미터 — 언어모델 (2단계)</div>
        <div className={cx('flex-16')}>
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

        <div className={cx('border')}></div>
        <div className={cx('title')}>데이터 범위</div>
        <div className={lx('radio-wrap')}>
          <Radio
            options={MAX_SAMPLES_OPTIONS.map((option) => ({
              ...option,
              labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
            }))}
            name='vlmMaxSamples'
            selectedValue={maxSamples}
            isReadonly={isBusy}
            onChange={(e) => {
              if (!isBusy) setMaxSamples(Number(e.target.value));
            }}
          />
        </div>
        <div className={lx('train-hint')}>
          대용량 데이터셋(예: CC3M 595K)은 1회 완주 데모를 위해 일부만 사용할 수
          있습니다. &lsquo;전체&rsquo;는 전부 학습합니다.
        </div>
      </div>
    </div>
  );

  return (
    <FineTuningShell
      navList={navList}
      filteredRest={filteredRest}
      t={t}
      titleName={fineTuningData?.model_name}
      topButtons={topButtons}
      // 초기 모델 로드(다운로드)·커밋 진행 상단 배너 — 진행 중 좌측 컬럼은 dimLeft + LOCKED_STYLE 로 잠근다.
      banner={
        commitBanner ? (
          <div
            className={lx('top-banner', `top-banner--${commitBanner.tone}`)}
            role='status'
          >
            {commitBanner.tone !== 'error' && (
              <span className={lx('top-banner-spinner')} aria-hidden='true' />
            )}
            <span>{t(commitBanner.msg)}</span>
          </div>
        ) : null
      }
      dimLeft={isBusy}
      leftSections={leftSections}
      // 자원 정보 — 하우스 `InstanceSetting`(무수정). BE 가 MM 응답의 resource_info 를
      // 하우스와 동일한 3단계로 채운다(설계 §6-C, service.py:3159). instance_id 미배정
      // 모델은 `{}` 가 정상이며 그때는 값이 빈/대시로만 표시된다 → `? :` 가드 필수
      // (하우스 FineTuning.jsx:721–723 과 동일 패턴, BE 롤백 시에도 크래시 없음).
      leftFooter={
        isActive ? (
          <InstanceSetting
            infoData={
              fineTuningData?.resource_info ? fineTuningData.resource_info : {}
            }
          />
        ) : null
      }
      // 우측 — 부모 SSE props 를 `toMonitorProps` 로 정규화해 하우스 `FineTuningGraph`
      // 에 주입(external 뷰와 **같은** 함수 = 우측 파리티를 코드로 보장, 설계 §5-B S3).
      // `FineTuningGraph` 에 없는 상태배지/Loss/Grad/Epoch/진행바/실패사유는
      // `SDSMonitorSummary` 를 얹어 보존한다(설계 R7).
      right={
        <div className={lx('monitor-col')}>
          <SDSMonitorSummary
            t={t}
            label='학습 제어'
            status={fineTuningStatus}
            reason={
              fineTuningStatus === 'error'
                ? fineStatus?.fine_tuning_status?.reason
                : null
            }
            stats={[
              {
                // 엔진은 단일 train/loss 만 기록(stage1/2 구분 태그 없음) → "학습 Loss" 로 통합 표기.
                label: '학습 Loss',
                value: Number.isFinite(lossLatest)
                  ? lossLatest.toFixed(4)
                  : '—',
              },
              {
                label: 'Grad Norm',
                value: Number.isFinite(gradLatest)
                  ? gradLatest.toFixed(3)
                  : '—',
              },
              { label: 'Epoch', value: epochShown },
              { label: '진행률', value: `${pctShown}%` },
            ]}
            percent={pctValue}
            hints={[
              !hasDataset && !isActive
                ? '학습 데이터셋을 먼저 바인딩하면 시작할 수 있습니다.'
                : null,
              isDone && !starting
                ? isCommitting
                  ? '저장(커밋) 작업이 진행 중입니다. 완료 후 ‘커밋 리스트’ 탭에서 확인할 수 있습니다.'
                  : '학습 결과를 저장하면 ‘커밋 리스트’ 탭에서 평가·양자화에 사용할 수 있습니다.'
                : null,
            ]}
          />
          {/* 그래프 박스가 요약 카드 아래 남은 높이를 채워 컬럼 바닥까지 내려오도록
              하는 슬롯(`monitor-graph`). external 뷰와 **같은** 래퍼·같은 클래스 =
              우측 파리티 유지. 근거는 SCSS `.monitor-col` 주석 참고. */}
          <div className={lx('monitor-graph')}>
            <FineTuningGraph
              {...toMonitorProps({
                fineStatus,
                graphData: orderedGraphData,
                progressData,
                checkpoints,
                fineTuningData,
              })}
            />
          </div>
        </div>
      }
    />
  );
});

export default SDSMultimodalFineTuningView;
