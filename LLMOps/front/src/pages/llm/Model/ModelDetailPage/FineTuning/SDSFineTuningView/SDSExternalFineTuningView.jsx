// External-model variant of the FineTuning tab.
//
// 동일 SimpleNav + box{left, right} 레이아웃을 유지하되, 내용만 partner-
// container-specific:
//   left   — manifest meta + params JSON textarea (사용자가 사전 편집)
//   right  — FineTuningGraph 그대로 (SSE 는 model.external_job_id 기반)
//   top    — [System Log] + [실행] (internal 과 동일 위치/스타일)
//
// 실행 버튼 → 기존 `FINETUNING_SETTING` 모달 재사용 (instance/GPU 할당 UI 동일).
// 모달의 onSubmit({instanceId, instanceCount, gpuCount}) 콜백에서:
//   1. POST /api/external/jobs body{manifest, namespace, params,
//                                   instance_id, instance_count, gpu_count}
//   2. PATCH /api/models/{modelId}/external-job → job_id bind
//   3. fetchModel refresh → SSE 자동 시작
//
// 주의: instance/gpu 가 실제로 partner pod 의 helm resources 로 override
// 되려면 backend chain (BFF→fb_external_container→fb_scheduler→pod.yaml
// values) 5-layer 확장이 필요. v1.0.0 에서는 frontend UX 만 완성되어 있고
// backend 는 manifest 의 spec.resources default 를 사용한다.

import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { openModal } from '@src/store/modules/modal';
import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';
import { errorToastMessage, successToastMessage } from '@src/utils';

import FineTuningGraph from '../FineTuningGraph';
import FineTuningShell from '../FineTuningShell';
import SDSRawParamsPanel from './SDSRawParamsPanel';
import SDSRecipeFineTuningView from './SDSRecipeFineTuningView';
import SDSTopButtons from './SDSTopButtons';
import { toMonitorProps } from './monitorProps';
import {
  applyChaining,
  buildExternalJobBody,
  parseRawParams,
} from './payload/recipeParams';
import { derivePhaseCommitMap } from './payload/recipeState';
import useSSEStatus from '../useSSEStatus';
import useSSETime from '../useSSEFinetuningTime';
import useSSEGraph from '../useSSEGraph';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSExternalFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

const idleFineStatus = {
  fine_tuning_status: {
    status: 'stop',
    reason: null,
  },
  commit_status: {
    status: null,
    type: null,
    reason: null,
  },
};

// 하우스 `.name`(FineTuning.module.scss:59) 에는 break 규칙이 없다. manifest /
// job id 같은 긴 식별자가 402px 좌측 컬럼을 넘기지 않도록 값 쪽에만 적용한다
// (하우스 SCSS 무변경 — 하우스 화면 회귀 0).
const breakAllStyle = { wordBreak: 'break-all' };

// Defense in depth: the BFF already restricts wandb_url to http/https, but the
// value lands in an href so we re-check the scheme client-side and surface the
// destination host (anti-phishing — partner URL is untrusted). Returns
// { url, host } when safe, else null.
const parseSafeHttpUrl = (u) => {
  if (typeof u !== 'string' || !u) return null;
  try {
    const parsed = new URL(u);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return { url: u, host: parsed.host };
    }
  } catch (_) {
    /* invalid URL */
  }
  return null;
};

const SDSExternalFineTuningView = memo(function SDSExternalFineTuningView({
  navList,
  fineTuningData,
  workspaceId,
  modelId,
  refresh,
  filteredRest,
}) {
  const { t } = useTranslation();
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const dispatch = useDispatch();

  const manifestName = fineTuningData?.external_manifest_name || '';
  const manifestVersion = fineTuningData?.external_manifest_version || '';
  const externalJobId = fineTuningData?.external_job_id || '';
  const modelName = fineTuningData?.model_name || '';

  const [fineStatus, setFineStatus] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const [graphData, setGraphData] = useState(null);

  // 좌측 panel — 사용자가 사전에 편집하는 params JSON + namespace.
  // 실행 모달로 들어갈 때 closure 로 이 값을 캡쳐해서 BFF 호출에 같이 보낸다.
  // workspace_scope=per-workspace manifest 의 namespace 규칙 (platform
  // convention): jonathan-system-{workspace_id}. backend lifecycle.py 도
  // 같은 값으로 override 하지만, frontend default 를 일치시켜 UX 일관성.
  const defaultNamespace = workspaceId
    ? `jonathan-system-${workspaceId}`
    : 'jonathan-system';
  const [namespaceInput, setNamespaceInput] = useState(defaultNamespace);
  const [paramsInput, setParamsInput] = useState('{}');
  // 다단계 학습 레시피(manifest.recipe, SP-10) — 있으면 phase 카드 파이프라인 렌더.
  const [recipe, setRecipe] = useState(null);
  // activePhaseId = 현재 externalJobId 에 묶인(실행 중) phase. 완료 phase 는
  // 세션이 아니라 커밋(`{phase.id}-{ts}`)에서 derive → cross-reload 생존.
  const [activePhaseId, setActivePhaseId] = useState(null);
  const [commits, setCommits] = useState([]);
  // 커밋 API 가 돌려주는 model_name(=model_info["name"], commit dir 에 쓰는 그 값)
  // — _base_model.name 의 권위 source. client 추정(fineTuningData.model_name) 대체.
  const [commitModelName, setCommitModelName] = useState('');
  // 첫 마운트 시 manifest 의 default_params 로 textarea pre-fill + recipe 수신.
  useEffect(() => {
    if (!manifestName) return;
    let cancelled = false;
    const fetchDefaults = async () => {
      const response = await callApi({
        url: `external/manifests/${encodeURIComponent(manifestName)}`,
        method: 'get',
      });
      if (cancelled) return;
      const { status, result } = response;
      if (
        status === STATUS_SUCCESS &&
        result &&
        Array.isArray(result.versions)
      ) {
        const match = result.versions.find(
          (v) => v.manifest_version === manifestVersion,
        );
        // recipe 없는 버전으로 전환 시에도 stale recipe 가 남지 않도록 무조건 set.
        setRecipe(
          match && match.recipe && Array.isArray(match.recipe.phases)
            ? match.recipe
            : null,
        );
        if (
          match &&
          match.default_params &&
          typeof match.default_params === 'object'
        ) {
          try {
            setParamsInput(JSON.stringify(match.default_params, null, 2));
          } catch (_) {
            /* keep current */
          }
        }
      }
    };
    fetchDefaults();
    return () => {
      cancelled = true;
    };
  }, [manifestName, manifestVersion]);

  useEffect(() => {
    loadModalComponent('FINETUNING_SYSTEM_LOG');
    loadModalComponent('FINETUNING_SETTING');
  }, []);

  const fineTuningStatus = useMemo(
    () => fineStatus?.fine_tuning_status?.status,
    [fineStatus],
  );
  const isRunning =
    fineTuningStatus === 'running' || fineTuningStatus === 'pending';

  // W&B run 링크 — 컨테이너가 result.wandb_url 로 보고하면 sse-status payload 의
  // fine_tuning_status.wandb_url 로 흘러온다(학습 중/후 모두). 없으면 미표시.
  const wandb = useMemo(
    () => parseSafeHttpUrl(fineStatus?.fine_tuning_status?.wandb_url),
    [fineStatus],
  );

  // externalJobId 변경 시 이전 job 의 status/graph/progress 잔상 제거 — 새 SSE
  // 첫 메시지 도착 전 stale W&B 링크/그래프가 잠깐 보이는 것 방지.
  useEffect(() => {
    setFineStatus(externalJobId ? null : idleFineStatus);
    setProgressData(null);
    setGraphData(externalJobId ? null : {});
  }, [externalJobId]);

  // 모델/manifest 가 바뀌면 active/commits 초기화 — 이전 모델 상태 bleed 방지
  // (리뷰 C1/codex#4).
  useEffect(() => {
    setActivePhaseId(null);
    setCommits([]);
    setCommitModelName('');
  }, [modelId, manifestName, manifestVersion]);

  // 실행 중 phase 식별 복구 — activePhaseId 는 로컬 state 라 학습 중 reload 하면
  // 잃는다(codex HIGH). 모델에 바인딩된 job 의 output_subdir(=launch 시 phase.id
  // 규약)로 복구해, reload 후에도 모니터링 상세가 실행 중 phase 를 따라가게 한다.
  // job 이 cleanup(404)됐으면 그 phase 는 commit 으로 done 표시되므로 복구 불필요.
  useEffect(() => {
    if (
      !externalJobId ||
      activePhaseId ||
      !recipe ||
      !Array.isArray(recipe.phases)
    ) {
      return undefined;
    }
    let cancelled = false;
    (async () => {
      const res = await callApi({
        url: `external/jobs/${externalJobId}`,
        method: 'get',
      });
      if (cancelled) return;
      const sub = res?.result?.output_subdir;
      if (sub && recipe.phases.some((p) => p.id === sub)) {
        setActivePhaseId(sub);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [externalJobId, activePhaseId, recipe]);

  // recipe 모델의 커밋 목록 — phase 완료/체크포인트를 커밋 이름(`{phase.id}-{ts}`)
  // prefix 로 derive(영속 — cross-reload 생존). 마운트 + done 도달 시 재조회.
  const fetchRecipeCommits = useCallback(async () => {
    if (!modelId) return;
    const res = await callApi({
      url: `models/commit-models?model_id=${modelId}`,
      method: 'get',
    });
    if (res.status !== STATUS_SUCCESS) return;
    // 응답 result = { list: [...commits], model_name } (svc.get_commit_models).
    // 구버전(평면 배열)도 수용.
    const data = res.result;
    const list = Array.isArray(data)
      ? data
      : data && Array.isArray(data.list)
        ? data.list
        : null;
    if (list) setCommits(list);
    if (data && typeof data.model_name === 'string' && data.model_name) {
      setCommitModelName(data.model_name);
    }
  }, [modelId]);

  useEffect(() => {
    if (recipe) fetchRecipeCommits();
  }, [recipe, fetchRecipeCommits]);

  // 활성 phase done → 서버 auto-commit 은 terminal 직후 비동기(commit row 아직
  // 없을 수 있고 status 는 'done' 고정이라 1회 fetch 로는 놓친다). done 동안 제한
  // 재시도(0/2/5/10s)로 commit 이 보일 때까지 재조회(code F5/codex HIGH).
  useEffect(() => {
    if (!recipe || fineTuningStatus !== 'done') return undefined;
    let cancelled = false;
    const timers = [0, 2000, 5000, 10000].map((d) =>
      setTimeout(() => {
        if (!cancelled) fetchRecipeCommits();
      }, d),
    );
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, [recipe, fineTuningStatus, fetchRecipeCommits]);

  // phase.id → 최신 커밋 이름. 커밋명 = `{phase.id}-{YYYYMMDD-HHMMSS}`(service.py
  // :1495). phase.id 가 하이픈을 허용하므로 startsWith(`${id}-`) 는 `lora` 가
  // `lora-cc3m-...` 를 오매칭할 수 있다 → 타임스탬프까지 anchored 정규식으로 정확
  // 매칭(code F2/codex HIGH). ts 고정폭이라 lexicographic 정렬=시간순.
  const phaseCommitMap = useMemo(
    () => derivePhaseCommitMap(commits, recipe?.phases),
    [commits, recipe],
  );

  // 완료 phase = 커밋이 존재하는 phase (세션 아님 → reload 후에도 유지).
  const donePhases = useMemo(
    () => new Set(Object.keys(phaseCommitMap)),
    [phaseCommitMap],
  );

  useSSEStatus(externalJobId || null, userName, setFineStatus, 'external');
  useSSETime(
    externalJobId || null,
    userName,
    setProgressData,
    fineTuningStatus,
    'external',
  );
  useSSEGraph(
    externalJobId || null,
    userName,
    fineTuningStatus,
    setGraphData,
    'external',
  );

  // 실행 모달의 onSubmit — instance/gpu 정보 받음. BFF body 에 추가해 forward.
  // (backend 가 v1.0.0 에서 instance/gpu 를 helm resources override 로 쓰지
  // 않더라도 forward 자체는 안전 — fb_external_container 가 unknown 필드를
  // 무시한다. Phase 2 에서 chain 확장 시 자동으로 동작.)
  // 공유 launch — params + outputSubdir + instance/gpu 받아 POST /external/jobs
  // → PATCH external-job(활성 job 바인딩). 단일 launch 와 phase launch 가 모두 사용.
  const submitExternalJob = useCallback(
    async ({ params, outputSubdir, instanceId, instanceCount, gpuCount }) => {
      if (!namespaceInput.trim()) {
        errorToastMessage(null, t('externalTraining.start.failed.label'));
        return false;
      }
      const launch = await callApi({
        url: 'external/jobs',
        method: 'post',
        body: buildExternalJobBody({
          manifestName,
          manifestVersion,
          workspaceId,
          namespace: namespaceInput,
          params,
          instanceId,
          instanceCount,
          gpuCount,
          modelId,
          outputSubdir,
        }),
      });
      if (!(
        launch.status === STATUS_SUCCESS &&
        launch.result &&
        launch.result.job_id
      )) {
        errorToastMessage(
          launch.error,
          launch.message || t('externalTraining.start.failed.label'),
        );
        return false;
      }
      const bind = await callApi({
        url: `models/${modelId}/external-job`,
        method: 'patch',
        body: { external_job_id: launch.result.job_id },
      });
      if (bind.status !== STATUS_SUCCESS) {
        errorToastMessage(bind.error, bind.message);
        return false;
      }
      successToastMessage(null, t('finetuning.start.success.message'));
      if (typeof refresh === 'function') refresh();
      return true;
    },
    [
      namespaceInput,
      manifestName,
      manifestVersion,
      workspaceId,
      modelId,
      refresh,
      t,
    ],
  );

  // 단일 launch (recipe 없는 manifest) — 좌측 params textarea 사용.
  const launchTraining = useCallback(
    async ({ instanceId, instanceCount, gpuCount }) => {
      // 파싱/검증/outputSubdir 파생은 순수 함수. 토스트만 여기 남는다.
      const parsed = parseRawParams(paramsInput);
      if (!parsed.ok) {
        errorToastMessage(null, t('externalTraining.start.invalidJson.label'));
        return false;
      }
      return submitExternalJob({
        params: parsed.params,
        outputSubdir: parsed.outputSubdir,
        instanceId,
        instanceCount,
        gpuCount,
      });
    },
    [paramsInput, submitExternalJob, t],
  );

  // recipe phase launch — 해당 phase 의 (편집된) params 를 그대로 POST.
  // chain_from 있으면 직전 phase 의 커밋을 `_base_model`(commit_models mount) +
  // chain_inputs 치환으로 잇는다(output_subdir=phase.id 규약). 활성 phase 로 표시.
  const launchPhase = useCallback(
    (phase, editedParams) =>
      async ({ instanceId, instanceCount, gpuCount }) => {
        const base =
          editedParams && typeof editedParams === 'object'
            ? editedParams
            : phase.params;
        // 체이닝 + 이어서 학습 마커 번역 = 순수 applyChaining(payload/recipeParams.js).
        //   체이닝: chain_from phase 의 최신 커밋(`{phase.id}-{ts}`)을 직전 산출물로 잇는다.
        //     (1) chain_inputs 템플릿의 {checkpoint_name} 을 커밋명으로 치환해 partner
        //         param(projector_path/resume_lora_path 등)에 주입. 경로 규약은 recipe 소유.
        //     (2) `_base_model={name: <model>}` 로 그 모델의 commit_models 를
        //         /models/checkpoints 에 mount(pod.yaml).
        //   이어서 학습: RecipePipeline 이 심은 FE-내부 마커 `_resume_checkpoint` 를
        //     resume_lora_path/projector_path 로 번역하고 마커는 제거(파트너 미전송).
        //   ⚠️ (1)→(2)→마커 순서 불변식은 그 순수 함수가 고정한다 — recipe 가
        //     chain_inputs 로 예약키를 덮어써 mount 를 무력화하지 못하게(codex MED).
        const resolved = applyChaining({
          params: base,
          phase,
          phaseCommitMap,
          // _base_model.name = 모델 실제 dir 이름. commit API 의 model_name(=
          // model_info["name"], commit_external_artifacts 가 쓰는 그 값)을 권위
          // source 로 사용 — client 추정(fineTuningData.model_name) 대비 안전
          // (code F4/codex HIGH).
          baseModelName: commitModelName || modelName,
        });
        if (!resolved.ok) {
          if (resolved.code === 'CHAIN_MISSING') {
            errorToastMessage(
              null,
              t('externalTraining.recipe.chainMissing.label'),
            );
          }
          return false;
        }
        const ok = await submitExternalJob({
          params: resolved.params,
          outputSubdir: phase.id,
          instanceId,
          instanceCount,
          gpuCount,
        });
        if (ok) {
          // 직전 phase 의 stale done 상태가 새 phase 를 즉시 done 처리하는 레이스
          // 방지 — 활성 전환 전 status 초기화. 새 SSE 가 다시 채운다(codex#3).
          setFineStatus(null);
          setActivePhaseId(phase.id);
        }
        return ok;
      },
    [submitExternalJob, phaseCommitMap, commitModelName, modelName, t],
  );

  const onClickRun = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_SETTING',
        modalData: {
          workspaceId,
          modelId,
          onSubmit: launchTraining,
          refresh,
        },
      }),
    );
  }, [dispatch, workspaceId, modelId, launchTraining, refresh]);

  // phase 실행 버튼 → instance/GPU 모달 → 해당 phase params 로 launch.
  const onRunPhase = useCallback(
    (phase, editedParams) => {
      dispatch(
        openModal({
          modalType: 'FINETUNING_SETTING',
          modalData: {
            workspaceId,
            modelId,
            onSubmit: launchPhase(phase, editedParams),
            refresh,
          },
        }),
      );
    },
    [dispatch, workspaceId, modelId, launchPhase, refresh],
  );

  // 중지 — confirm 후 POST /api/external/jobs/{jobId}/cancel.
  // ETRI 의 /train/stop 이 호출되고 fb_external_container 가 helm uninstall 까지 처리.
  const doCancel = useCallback(async () => {
    if (!externalJobId) return;
    const response = await callApi({
      url: `external/jobs/${externalJobId}/cancel`,
      method: 'post',
    });
    if (response.status === STATUS_SUCCESS) {
      successToastMessage(null, t('finetuning.stop.requested.message'));
      if (typeof refresh === 'function') refresh();
    } else {
      errorToastMessage(response.error, response.message);
    }
  }, [externalJobId, refresh, t]);

  const onClickStop = useCallback(() => {
    if (!externalJobId) return;
    dispatch(
      openConfirm({
        title: 'externalTraining.stop.confirm.title',
        content: 'externalTraining.stop.confirm.message',
        submit: {
          text: 'externalTraining.stop.label',
          func: () => {
            doCancel();
          },
        },
        cancel: { text: 'cancel.label' },
      }),
    );
  }, [dispatch, externalJobId, doCancel]);

  const onClickSystemLog = useCallback(() => {
    if (!externalJobId) return;
    dispatch(
      openModal({
        modalType: 'FINETUNING_SYSTEM_LOG',
        modalData: {
          workspaceId,
          modelId,
          jobId: externalJobId,
          manifestName: `${manifestName}@${manifestVersion}`,
          mode: 'external',
        },
      }),
    );
  }, [
    dispatch,
    externalJobId,
    modelId,
    manifestName,
    manifestVersion,
    workspaceId,
  ]);

  // 좌측 1 — W&B run 링크. 하우스 모델 박스(FineTuning.jsx:519–546)와 같은 자리·같은
  // 클래스(`model-box` / `title` / `name`)를 쓴다.
  //
  // 읽기전용 메타 4행(모델명 / `manifest@version` / Workspace / Job ID)은 **유저 요청으로
  // 제거**했다 — 좌측 설정 컬럼을 잡아먹는 군더더기였고, 모델명과 manifest 는 이미
  // `SimpleNav` 의 `titleName`/`subTitle` 에 그대로 나온다. CSS 로 숨기지 않고 마크업을
  // 지운다(표시 전용이라 남길 이유가 없다).
  // W&B 는 메타 표시가 아니라 학습 run 으로 나가는 **기능성 외부 링크**라 유지한다.
  // 링크가 없으면 섹션 자체를 렌더하지 않는다(빈 박스 방지).
  //
  // recipe / 비-recipe **공용** — 두 갈래 모두 같은 자리에 이 노드를 놓는다.
  // `wordBreak` 인라인: W&B host 가 402px 좌측 컬럼을 넘길 수 있는데 하우스 `.name` 에는
  // break 규칙이 없다 → 하우스 SCSS 를 고치지 않고 값 쪽만 처리.
  const modelSection = wandb ? (
    <div className={cx('model-box')}>
      <div className={cx('title')}>{t('externalTraining.wandb.label')}</div>
      <div className={cx('name')} style={breakAllStyle}>
        <a
          className={lx('wandb-link')}
          href={wandb.url}
          target='_blank'
          rel='noopener noreferrer'
          title={t('externalTraining.wandb.viewRun.label')}
        >
          {wandb.host} ↗
        </a>
      </div>
    </div>
  ) : null;

  const recipeMode = !!(recipe && Array.isArray(recipe.phases));

  // ── recipe(SDS) 모드 — 하우스 골격(FineTuningShell)으로 렌더(설계 §8 Phase 4).
  //    과거 `RecipePipeline`(자체 2컬럼 + 모니터 안 실행 버튼)을 해체해
  //    `SDSRecipeFineTuningView`(RecipeStepNav + 하우스 좌측 섹션 + SDSMonitorSummary
  //    + FineTuningGraph, 실행/중지/로그는 상단 버튼줄)로 대체했다.
  //
  //    ⚠️ payload 2단 프로토콜(설계 §9 R2) — 이 컴포넌트 경계를 **없애지 않는다.**
  //       1단 `mergePhaseParams`(마커 `_resume_checkpoint` 심기) = 자식(recipe 뷰),
  //       2단 `applyChaining`(번역·제거) = 이 파일의 `launchPhase`.
  //       `onRunPhase(phase, editedParams)` 계약과 호출 순서 무변경.
  //    ⚠️ `key={manifest@version}` = phase 폼/선택/체크포인트 상태의 리셋 장치(무변경).
  if (recipeMode) {
    return (
      <SDSRecipeFineTuningView
        key={`${manifestName}@${manifestVersion}`}
        navList={navList}
        filteredRest={filteredRest}
        t={t}
        titleName={fineTuningData?.model_name}
        modelSection={modelSection}
        phases={recipe.phases}
        modelId={modelId}
        activePhaseId={activePhaseId}
        activePhaseStatus={fineTuningStatus}
        donePhases={donePhases}
        phaseCommitMap={phaseCommitMap}
        onRunPhase={onRunPhase}
        graphData={graphData}
        progressData={progressData}
        fineStatus={fineStatus}
        fineTuningData={fineTuningData}
        onStop={onClickStop}
        onSystemLog={onClickSystemLog}
      />
    );
  }

  // ── recipe 없는 external = 단일 launch. 하우스 골격(FineTuningShell)으로 렌더.
  //    (이 갈래는 이미 하우스 `box/left/right` 를 쓰고 있어 시각 델타가 가장 작다 — 설계 §8 Phase 2)

  // 상단 버튼줄 — 하우스와 같은 자리(`SimpleNav.topButtonList`) · 같은 위계(설계 §3-D):
  //   시스템 로그 = solid l skyblue / 실행 = solid l (기본 blue) / 중지 = solid l red.
  // 게이트는 여기서 계산해 descriptor 로 넘긴다(external sse-status 의 commit_status
  // 가 null 이라 하우스 TopButtonList 의 isCal* 게이트는 쓸 수 없다 — 설계 R12).
  const topButtons = (
    <SDSTopButtons
      buttons={[
        {
          key: 'systemLog',
          label: t('systemLog.label'),
          colorType: 'skyblue',
          onClick: onClickSystemLog,
          disabled: !externalJobId || !fineTuningStatus,
        },
        isRunning
          ? {
              key: 'stop',
              label: t('externalTraining.stop.label'),
              colorType: 'red',
              onClick: onClickStop,
            }
          : {
              key: 'run',
              label: externalJobId
                ? t('externalTraining.model.restart.label')
                : t('externalTraining.model.startTraining.label'),
              onClick: onClickRun,
              disabled: !manifestName,
            },
      ]}
    />
  );

  return (
    <FineTuningShell
      navList={navList}
      filteredRest={filteredRest}
      t={t}
      titleName={fineTuningData?.model_name}
      topButtons={topButtons}
      dimLeft={isRunning}
      leftSections={
        <>
          {modelSection}
          {/* 좌측 2 — 고급 옵션(namespace + raw params). 하우스 `Advanced` 는 config.json
              업로드에 하드바인딩돼 수용 불가 → 별도 패널(설계 §2-C). */}
          <SDSRawParamsPanel
            t={t}
            namespace={namespaceInput}
            onChangeNamespace={setNamespaceInput}
            params={paramsInput}
            onChangeParams={setParamsInput}
            disabled={isRunning}
          />
        </>
      }
      // 우측 — 뷰가 직접 구독한 external SSE 결과를 `toMonitorProps` 로 정규화해 주입.
      // 셸은 SSE 를 구독하지 않는다(설계 §5-B 불변식 S1·S3). internal VLM 도 같은
      // 함수로 정규화해 우측 파리티를 코드로 보장한다(Phase 3).
      right={
        <FineTuningGraph
          {...toMonitorProps({
            fineStatus,
            graphData,
            progressData,
            fineTuningData,
          })}
        />
      }
    />
  );
});

export default SDSExternalFineTuningView;
