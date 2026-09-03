// external SDS **recipe** 경로(다단계 학습 레시피, manifest.recipe / SP-10)의 학습 화면.
// 과거 `RecipePipeline`(720줄, 자체 2컬럼 그리드)을 해체해 하우스 골격으로 재조립한 것.
//
// 골격 = 하우스 파인튜닝 화면과 **같은** `FineTuningShell`(설계 §3-A, Phase 4):
//   SimpleNav(topButtonList=SDSTopButtons) → RecipeStepNav(fullWidthTop)
//   → box{ left{ left-top: 모델/학습데이터/학습대상/(상태별 편집 섹션) },
//          right{ SDSMonitorSummary + FineTuningGraph } }
// 폐기된 것: 자체 `recipe`/`sds-body`/`config-side`/`monitor-side` 그리드, 모니터 안의
//   `head-actions` 버튼줄, 자체 `charts-grid`(→ 하우스 `FineTuningGraph`),
//   `mx()` 로 MM SCSS 를 빌려 쓰던 22클래스 차용(설계 §1 "자체 어휘 부채").
//
// ⚠️ **왜 부모(SDSExternalFineTuningView)에 인라인 흡수하지 않고 컴포넌트를 유지하는가**
//    (설계 §4-B / §9 R2 — 이 위상의 최우선 리스크):
//    payload 조립이 컴포넌트 경계를 가로질러 2단으로 쪼개져 있다.
//      1단(여기) `mergePhaseParams` — FE-내부 마커 `_resume_checkpoint` 를 **심는다**
//      2단(부모) `applyChaining`    — 마커를 파트너 키로 **번역하고 제거한다**
//    경계를 없애면 두 호출이 한 함수로 합쳐질 유혹이 생기고 순서 불변식
//    (chain_inputs → `_base_model` → 마커)이 깨진다. → 경계와 호출 위치를 **그대로 둔다.**
//    부모의 `onRunPhase(phase, editedParams)` 계약도 무변경.
// ⚠️ 부모가 `key={`${manifestName}@${manifestVersion}`}` 로 이 컴포넌트를 리마운트하는
//    것이 phase 폼/선택/체크포인트 상태의 **유일한 리셋 장치**다. 컴포넌트를 없애면
//    그 리셋을 effect 로 재현해야 했다 → 유지가 곧 동작 보존.
// ⚠️ SSE 를 구독하지 않는다 — 부모 external 뷰가 `useSSE*(externalJobId, 'external')`
//    로 단일 구독한 결과를 props 로 받는다(설계 §5-B S1). 셸도 구독하지 않는다.
// ⚠️ 진행률/Epoch 의 `isDone → 100%` 보정은 **하지 않는다**(불변식 S6). MM 은 하고
//    external 은 안 하는 현재 차이를 그대로 보존한다 — 통일은 별도 결정(D5).

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import { getExternalCheckpoints } from '@src/apis/llm/model';
import { STATUS_SUCCESS } from '@src/network';

import FineTuningGraph from '../FineTuningGraph';
import FineTuningShell from '../FineTuningShell';
import { toMonitorProps } from './monitorProps';
import {
  CKPT_NUM_SPECS,
  HP_SPECS,
  buildPhaseForm,
  applyDatasetChoice,
  datasetNameOf,
  mergePhaseParams,
} from './payload/recipeParams';
import { canRunPhase, derivePhaseStatus } from './payload/recipeState';
import { formatPercentLabel, toPercentValue } from './progressFormat';
import RecipeStepNav from './RecipeStepNav';
import SDSMonitorSummary from './SDSMonitorSummary';
import SDSTopButtons from './SDSTopButtons';
import RecipeArchSection, { FIXED_PROJ } from './sections/RecipeArchSection';
import RecipeCheckpointSection from './sections/RecipeCheckpointSection';
import RecipeDatasetSection from './sections/RecipeDatasetSection';
import RecipeFreezeSection from './sections/RecipeFreezeSection';
import RecipeHyperParamsSection from './sections/RecipeHyperParamsSection';
import RecipeResumeSection from './sections/RecipeResumeSection';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

// params.phase(train_type) → 학습 대상. 개별 on/off 토글 없이 phase 가 결정(항목6).
// 실 매니페스트(eva-vlm-train 1.0.0-acryl-patched-v11) 4 phase 의 params.phase 값과 1:1.
const TRAIN_TARGET = {
  projector: { proj: 'train', llm: 'frozen', label: '프로젝터 정렬' },
  lora: { proj: 'train', llm: 'lora', label: '프로젝터 + 언어모델 LoRA' },
  lora_marine: { proj: 'frozen', llm: 'lora', label: '언어모델 LoRA' },
  lora_sds: { proj: 'train', llm: 'lora', label: '프로젝터 + 언어모델 LoRA' },
};

// 차트 정렬(손실 우선) — 하우스 `FineTuningGraph` 는 `Object.entries` 삽입 순서로
// 그리므로 넘기기 전에 키 순서를 정렬해 현재 표시 순서를 보존한다(컴포넌트 무수정).
// MM 뷰와 같은 목록 = 두 화면 차트 순서 일치.
const CHART_ORDER = [
  'train/loss',
  'eval/loss',
  'train/grad_norm',
  'train/learning_rate',
];

const RESUME_NONE_LABEL_KEY = 'externalTraining.recipe.resume.none.label';

// 학습 대상 freeze 배너의 note — 두 SDS 화면이 공유하는 시각언어라 `recipe.*` 가 아닌
// `externalTraining.freeze.*` 로 둔다(MM 뷰도 같은 어휘를 쓴다).
const FREEZE_NOTE_KEY = {
  frozen: 'externalTraining.freeze.frozen.label',
  trainable: 'externalTraining.freeze.trainable.label',
  lora: 'externalTraining.freeze.lora.label',
};

const SDSRecipeFineTuningView = ({
  // 셸 패스스루
  navList,
  filteredRest,
  t,
  titleName,
  subTitle,
  modelSection,
  // recipe / phase 상태(부모 소유 — 커밋 파생·job 바인딩은 부모 책임)
  phases,
  modelId,
  activePhaseId,
  activePhaseStatus,
  donePhases,
  phaseCommitMap,
  // 워크스페이스 데이터셋 [{label,value}] — 학습에 쓸 데이터셋 선택지(부모 조회).
  datasetOptions,
  onRunPhase,
  // 모니터(부모 SSE 구독 결과) + 컨트롤 핸들러
  graphData,
  progressData,
  fineStatus,
  fineTuningData,
  onStop,
  onSystemLog,
}) => {
  const done = donePhases || new Set();
  const commitMap = phaseCommitMap || {};

  // phase 별 편집 폼 — 각 phase params 로 시드(기본값). 선택 전환 시 이전 편집 보존.
  const [forms, setForms] = useState(() => {
    const m = {};
    phases.forEach((p) => {
      m[p.id] = buildPhaseForm(p.params || {});
    });
    return m;
  });

  // phase 별 학습 데이터셋 선택 — 기본값은 매니페스트의 `_dataset.name`.
  // 학습/평가 분할(sds_train ↔ sds_eval)이 생기면서 "무엇으로 학습했나" 가 결과 신뢰도를
  // 좌우해 화면에서 고를 수 있게 한다. 경로 파라미터 동반 재작성은 실행 시 순수 함수가 한다.
  const [datasetSel, setDatasetSel] = useState({});

  // 선택 phase — 기본: 활성(실행 중) phase → 없으면 첫 미완료 → 없으면 첫 phase.
  const [selectedPhaseId, setSelectedPhaseId] = useState(() => {
    if (activePhaseId) return activePhaseId;
    const pending = phases.find((p) => !done.has(p.id));
    return (pending || phases[0] || {}).id;
  });

  // 모델 구조 · 프로젝터(항목8) — 시각화 전용 선택 상태(백엔드 미전송).
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
    (phase) => canRunPhase(phase, { anyRunning, donePhases: done }),
    [anyRunning, done],
  );

  const setField = useCallback(
    (phaseId, key, value) =>
      setForms((s) => ({
        ...s,
        [phaseId]: { ...(s[phaseId] || {}), [key]: value },
      })),
    [],
  );

  // 이어서 학습(가중치 warm-start) — 모델의 저장된 체크포인트 목록. 선택 시 그 가중치에서
  // 이어서 학습(옵티마이저/step 은 리셋). 목록 소스 = list_external_checkpoints(P1).
  const [resumeCkpts, setResumeCkpts] = useState([]);
  const [resumeSel, setResumeSel] = useState(''); // '' = 처음부터. 값 = "<commit>/checkpoint-<step>"
  // 이어서 학습 체크포인트 → 조나단 Selectbox list(label/value) 형태로 변환.
  const resumeOptions = useMemo(
    () => [
      { label: t(RESUME_NONE_LABEL_KEY), value: '' },
      ...resumeCkpts.map((c) => ({
        label: `${c.stage_label ? `[${c.stage_label}] ` : ''}Step ${c.step.toLocaleString()}${
          Number.isFinite(c.loss) ? ` · loss ${c.loss.toFixed(3)}` : ''
        }`,
        value: `${c.commit_name}/checkpoint-${c.step}`,
      })),
    ],
    [resumeCkpts, t],
  );
  useEffect(() => {
    // 모델 전환 시 이전 모델의 체크포인트 선택 잔존 방지(컴포넌트가 manifest@version 로만
    // keyed 라 같은 매니페스트의 다른 모델로 이동 시 미리마운트 → stale 선택으로 오모델
    // 체크포인트 주입 위험, codex MED).
    setResumeSel('');
    setResumeCkpts([]);
    if (!modelId) return undefined;
    let alive = true;
    (async () => {
      const res = await getExternalCheckpoints(modelId);
      if (
        alive &&
        res?.status === STATUS_SUCCESS &&
        Array.isArray(res.result?.list)
      )
        setResumeCkpts(
          res.result.list.filter((c) => c && Number.isFinite(c.step)),
        );
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 실행 — 편집한 숫자 하이퍼파라미터/step 과 체크포인트 이름만 phase.params 위에 오버레이,
  // 나머지 키(경로·phase·scenario·chain)는 pass-through(계약 보존). 체인 주입은 부모가 처리.
  //
  // `resumeSel` 이 있으면 mergePhaseParams 가 FE-내부 마커 `_resume_checkpoint` 를 심는다.
  // 그 마커를 partner 키(resume_lora_path/projector_path)로 번역하고 제거하는 것은 부모
  // launchPhase → applyChaining 이다(2단 프로토콜, payload/recipeParams.js 주석 참조).
  const handleRun = useCallback(
    (phase) => {
      // 데이터셋 교체를 **먼저** 적용한다 — mergePhaseParams 가 얹는 값은 숫자/이름뿐이라
      // 순서에 영향받지 않지만, 경로 재작성은 원본 phase.params 기준이어야 안전하다.
      const chosen = datasetSel[phase.id];
      const base = chosen ? applyDatasetChoice(phase.params, chosen) : phase.params;
      onRunPhase(
        phase,
        mergePhaseParams({
          phaseParams: base,
          form: forms[phase.id],
          resumeSelection: resumeSel,
        }),
      );
    },
    [datasetSel, forms, onRunPhase, resumeSel],
  );

  const selectedPhase =
    phases.find((p) => p.id === selectedPhaseId) || phases[0] || null;
  const selectedStatus = selectedPhase
    ? derivePhaseStatus(selectedPhase, activePhaseId, activePhaseStatus, done)
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

  const isSelRunning =
    selectedStatus === 'running' || selectedStatus === 'pending';
  const isSelDone = selectedStatus === 'done';

  // ── 모니터 파생값(활성 job 의 SSE) ──
  const monStatus = fineStatus?.fine_tuning_status?.status;
  const isMonRunning = monStatus === 'running' || monStatus === 'pending';
  const monLoss = graphData?.['train/loss']?.values?.slice(-1)?.[0];
  const monGrad = graphData?.['train/grad_norm']?.values?.slice(-1)?.[0];
  // 바 width 는 숫자, 라벨은 1% 미만에서 소수 2자리(progressFormat 참조).
  const monPctValue = toPercentValue(progressData?.percent);
  const monPct = formatPercentLabel(progressData?.percent);
  const monEpoch =
    Number.isFinite(progressData?.progress_epoch) && progressData?.total_epoch
      ? `${progressData.progress_epoch}/${progressData.total_epoch}`
      : '—';
  // 키 순서만 정렬 — null/undefined 는 그대로 통과(FineTuningGraph 의 no-data 분기 유지).
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

  // 학습 대상 freeze 배너(읽기전용) — 비전=항상 동결, projector/LLM 은 phase 가 결정.
  const freezeLayer = (name, cls) => ({
    name,
    note: t(FREEZE_NOTE_KEY[cls]),
    cls,
  });
  const freezeLayers = target
    ? [
        freezeLayer('Vision Encoder', 'frozen'),
        freezeLayer(
          'Projector',
          target.proj === 'train' ? 'trainable' : 'frozen',
        ),
        freezeLayer(
          'Language Model',
          target.llm === 'lora' ? 'lora' : 'frozen',
        ),
      ]
    : [];

  // ── 상단 버튼줄 — 하우스와 같은 자리(`SimpleNav.topButtonList`)·같은 위계(설계 §3-D).
  //    **이 위상의 핵심 변경**: 실행/중지/시스템로그가 우측 모니터 `head-actions` 에서
  //    여기로 올라왔다. 게이트 값은 그대로 이관한다 — 시스템로그 `!fineStatus`,
  //    실행 `!canRun(selectedPhase)`(= 활성 job 없음 + chain_from 선행 완료).
  //    하우스 `TopButtonList` 는 쓸 수 없다(external sse-status 의 commit_status 가
  //    null 이라 `isCal*` 게이트가 전 버튼을 비활성화 — 설계 R12).
  const topButtons = (
    <SDSTopButtons
      buttons={[
        {
          key: 'systemLog',
          label: t('systemLog.label'),
          colorType: 'skyblue',
          onClick: onSystemLog,
          disabled: !fineStatus,
        },
        isMonRunning
          ? {
              key: 'stop',
              label: t('externalTraining.recipe.stopTraining.label'),
              colorType: 'red',
              onClick: onStop,
            }
          : {
              key: 'run',
              label: t('externalTraining.recipe.run.label'),
              onClick: () => selectedPhase && handleRun(selectedPhase),
              disabled: !canRun(selectedPhase),
            },
      ]}
    />
  );

  // ── 좌측 — 하우스 `.left-top` 안에 하우스 클래스로 섹션을 쌓는다(설계 §3-B).
  //    1 모델(부모 주입) / 2 학습 데이터 / 3 학습 대상(freeze) / 상태별:
  //      done      → 저장된 커밋
  //      running   → 실행 중 안내(진행 상황은 우측 모니터)
  //      idle      → 하이퍼파라미터 / 체크포인트 설정 / 이어서 학습 / 모델 구조
  //    섹션 사이 구분은 하우스 `border` 디바이더(MM 뷰와 동일 — 자체 카드 중첩 폐기).
  //    자원 정보 섹션은 **만들지 않는다**(설계 §6-B): external 은 `instance_id`/`count` 가
  //    스케줄링에 쓰이지 않아(lifecycle.py:389-392) 표시하면 파드 실제 자원과 다른 거짓이 된다.
  //
  //    구분선은 **섹션 사이에만** 넣는다 — 조건부 섹션(freeze / 하이퍼파라미터)이
  //    빠졌을 때 선행 `border` 만 남는 것을 구조적으로 막기 위해 노드 배열을 만들어
  //    인터리브한다(예: 매니페스트가 TRAIN_TARGET 에 없는 `params.phase` 를 쓰면
  //    freeze 섹션이 사라진다).
  const boxSections = [
    freezeLayers.length ? (
      <RecipeFreezeSection
        key='freeze'
        t={t}
        layers={freezeLayers}
        hint={
          !isSelRunning && !isSelDone
            ? t('externalTraining.recipe.trainTarget.hint')
            : null
        }
      />
    ) : null,
    ...(isSelDone
      ? [
          <Fragment key='commit'>
            <div className={cx('title')}>
              {t('externalTraining.recipe.savedCommit.label')}
            </div>
            <div className={cx('name')}>
              {commitMap[selectedPhase.id] || '-'}
            </div>
          </Fragment>,
        ]
      : isSelRunning
        ? [
            <div key='running' className={lx('train-hint')}>
              {t('externalTraining.recipe.running.hint')}
            </div>,
          ]
        : [
            presentHp.length ? (
              <RecipeHyperParamsSection
                key='hp'
                t={t}
                specs={presentHp}
                form={selForm}
                onChange={(key, value) =>
                  setField(selectedPhase.id, key, value)
                }
              />
            ) : null,
            datasetNameOf(selectedPhase.params) ? (
              <RecipeDatasetSection
                key='dataset'
                t={t}
                options={datasetOptions || []}
                value={
                  datasetSel[selectedPhase.id] ||
                  datasetNameOf(selectedPhase.params)
                }
                onChange={(name) =>
                  setDatasetSel((s) => ({ ...s, [selectedPhase.id]: name }))
                }
              />
            ) : null,
            <RecipeCheckpointSection
              key='ckpt'
              t={t}
              name={selForm.output_checkpoint_name || ''}
              onChangeName={(value) =>
                setField(selectedPhase.id, 'output_checkpoint_name', value)
              }
              specs={CKPT_NUM_SPECS}
              form={selForm}
              onChange={(key, value) => setField(selectedPhase.id, key, value)}
            />,
            <RecipeResumeSection
              key='resume'
              t={t}
              options={resumeOptions}
              value={resumeSel}
              onChange={setResumeSel}
            />,
            <RecipeArchSection
              key='arch'
              t={t}
              projType={projType}
              onProjType={setProjType}
              mlpHidden={mlpHidden}
              onMlpHidden={setMlpHidden}
              xAttnHeads={xAttnHeads}
              onXAttnHeads={setXAttnHeads}
              qTokens={qTokens}
              onQTokens={setQTokens}
              diagramOpen={diagramOpen}
              onOpenDiagram={() => setDiagramOpen(true)}
              onCloseDiagram={() => setDiagramOpen(false)}
            />,
          ]),
  ].filter(Boolean);

  // ⚠️ 구분선(`border`)은 `type-box` **안** `boxSections` 에만 `idx > 0` 로 인터리브된다.
  //    `modelSection` 은 그 바깥이므로 있으나 없으나 첫 섹션 앞에 선이 생기지 않는다.
  //    학습 데이터/데이터 경로 행(과거 `RecipeDataSection`)은 유저 요청으로 제거됐다.
  const leftSections = (
    <>
      {modelSection}
      <div className={cx('type-box')}>
        {boxSections.map((node, idx) => (
          <Fragment key={node.key}>
            {idx > 0 ? <div className={cx('border')}></div> : null}
            {node}
          </Fragment>
        ))}
      </div>
    </>
  );

  return (
    <FineTuningShell
      navList={navList}
      filteredRest={filteredRest}
      t={t}
      titleName={titleName}
      subTitle={subTitle}
      topButtons={topButtons}
      // box 위 full-width — phase 선택 네비(실행은 상단 버튼줄이 담당).
      fullWidthTop={
        <RecipeStepNav
          phases={phases}
          selectedPhaseId={selectedPhase?.id}
          onSelect={setSelectedPhaseId}
          activePhaseId={activePhaseId}
          activePhaseStatus={activePhaseStatus}
          donePhases={done}
        />
      }
      leftSections={leftSections}
      // 우측 — `FineTuningGraph` 에 없는 상태배지/Loss/Grad/Epoch/진행바/실패사유는
      // `SDSMonitorSummary` 를 얹어 보존한다(설계 R7). MM 뷰와 **같은** 두 컴포넌트·
      // 같은 `toMonitorProps` = 우측 파리티를 코드로 보장(§5-B S3).
      right={
        <div className={lx('monitor-col')}>
          <SDSMonitorSummary
            t={t}
            label={t('externalTraining.trainControl.label')}
            status={monStatus}
            reason={
              monStatus === 'error'
                ? fineStatus?.fine_tuning_status?.reason
                : null
            }
            stats={[
              {
                label: t('externalTraining.trainLoss.label'),
                value: Number.isFinite(monLoss) ? monLoss.toFixed(4) : '—',
              },
              {
                label: 'Grad Norm',
                value: Number.isFinite(monGrad) ? monGrad.toFixed(3) : '—',
              },
              { label: 'Epoch', value: monEpoch },
              {
                label: t('externalTraining.progress.label'),
                value: `${monPct}%`,
              },
            ]}
            percent={monPctValue}
            hints={[
              // chain_from 선행 미완료 힌트 — 상단 실행 버튼이 왜 비활성인지 설명.
              selBlockedByChain && !isMonRunning
                ? t('externalTraining.recipe.chainGate.label')
                : null,
            ]}
          />
          {/* 그래프 박스가 요약 카드 아래 남은 높이를 채워 컬럼 바닥까지 내려오도록
              하는 슬롯(`monitor-graph`). 하우스 `.right` 는 block 이라 flex 체인이
              여기서 끊긴다 — 자세한 이유는 SCSS `.monitor-col` 주석 참고. */}
          <div className={lx('monitor-graph')}>
            <FineTuningGraph
              {...toMonitorProps({
                fineStatus,
                graphData: orderedGraphData,
                progressData,
                fineTuningData,
              })}
            />
          </div>
        </div>
      }
    />
  );
};

export default SDSRecipeFineTuningView;
