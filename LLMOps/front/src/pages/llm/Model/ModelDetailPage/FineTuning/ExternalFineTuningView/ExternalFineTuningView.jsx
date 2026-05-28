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

import { ButtonV2 } from '@jonathan/ui-react';

import { openModal } from '@src/store/modules/modal';
import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';
import { errorToastMessage, defaultSuccessToastMessage } from '@src/utils';

import SimpleNav from '../../SimpleNav';
import FineTuningGraph from '../FineTuningGraph';
import useSSEStatus from '../useSSEStatus';
import useSSETime from '../useSSEFinetuningTime';
import useSSEGraph from '../useSSEGraph';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './ExternalFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

const ExternalFineTuningView = memo(function ExternalFineTuningView({
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
  // 첫 마운트 시 manifest 의 default_params 로 textarea pre-fill.
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
  const isRunning = fineTuningStatus === 'running' || fineTuningStatus === 'pending';

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
  const launchTraining = useCallback(
    async ({ instanceId, instanceCount, gpuCount }) => {
      let parsedParams;
      try {
        parsedParams = JSON.parse(paramsInput);
        if (
          parsedParams === null ||
          typeof parsedParams !== 'object' ||
          Array.isArray(parsedParams)
        ) {
          throw new Error('not an object');
        }
      } catch (_) {
        errorToastMessage(null, t('externalTraining.start.invalidJson.label'));
        return false;
      }
      if (!namespaceInput.trim()) {
        errorToastMessage(null, t('externalTraining.start.failed.label'));
        return false;
      }
      // Auto commit hook 활성화 — 학습 종료(COMPLETED) 시 fb_external_container
      // 가 BFF /external-commit 자동 호출해서 commit_model row 생성.
      // output_checkpoint_name 은 ETRI eva-vlm-train 의 출력 폴더 이름 키
      // (partner-specific). 다른 manifest 면 manifest config 에서 매핑 필요.
      const outputSubdir =
        typeof parsedParams.output_checkpoint_name === 'string'
          ? parsedParams.output_checkpoint_name.trim()
          : null;

      const launch = await callApi({
        url: 'external/jobs',
        method: 'post',
        body: {
          manifest_name: manifestName,
          manifest_version: manifestVersion,
          workspace_id: Number(workspaceId),
          namespace: namespaceInput.trim(),
          params: parsedParams,
          instance_id: instanceId,
          instance_count: parseInt(instanceCount, 10),
          gpu_count: parseInt(gpuCount, 10),
          platform_model_id: Number(modelId),
          output_subdir: outputSubdir || null,
        },
      });
      if (
        !(launch.status === STATUS_SUCCESS && launch.result && launch.result.job_id)
      ) {
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
      defaultSuccessToastMessage(t('externalTraining.start.success.label'));
      if (typeof refresh === 'function') refresh();
      return true;
    },
    [
      paramsInput,
      namespaceInput,
      manifestName,
      manifestVersion,
      workspaceId,
      modelId,
      refresh,
      t,
    ],
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

  // 중지 — confirm 후 POST /api/external/jobs/{jobId}/cancel.
  // ETRI 의 /train/stop 이 호출되고 fb_external_container 가 helm uninstall 까지 처리.
  const doCancel = useCallback(async () => {
    if (!externalJobId) return;
    const response = await callApi({
      url: `external/jobs/${externalJobId}/cancel`,
      method: 'post',
    });
    if (response.status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('externalTraining.stop.success.label');
      if (typeof refresh === 'function') refresh();
    } else {
      errorToastMessage(response.error, response.message);
    }
  }, [externalJobId, refresh]);

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

  const topButtonList = (
    <div className={lx('top-buttons')}>
      <ButtonV2
        type='outline'
        size='l'
        label={t('systemLog.label')}
        onClick={onClickSystemLog}
        disabled={!externalJobId || !fineTuningStatus}
      />
      {isRunning ? (
        <ButtonV2
          type='solid'
          size='l'
          colorType='red'
          label={t('externalTraining.stop.label')}
          onClick={onClickStop}
        />
      ) : (
        <ButtonV2
          type='solid'
          size='l'
          colorType='skyblue'
          label={
            externalJobId
              ? t('externalTraining.model.restart.label')
              : t('externalTraining.model.startTraining.label')
          }
          onClick={onClickRun}
          disabled={!manifestName}
        />
      )}
    </div>
  );

  return (
    <div id='info-tab' className={cx('info-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        topButtonList={topButtonList}
        titleName={fineTuningData?.model_name}
        subTitle={`${manifestName}@${manifestVersion}`}
      />
      <div className={cx('box')}>
        <div className={cx('left', isRunning && 'disabled')}>
          <div className={lx('panel')}>
            <div className={lx('panel-title')}>
              {t('externalTraining.metadata.label')}
            </div>
            <ul className={lx('meta-list')}>
              <Row label='Model' value={fineTuningData?.model_name || '-'} />
              <Row label='Workspace' value={String(workspaceId ?? '')} />
              <Row
                label={t('externalTraining.model.manifest.label')}
                value={`${manifestName}@${manifestVersion}`}
              />
              <Row
                label='Job ID'
                value={externalJobId || '-'}
              />
            </ul>
          </div>

          <div className={lx('panel')}>
            <div className={lx('panel-title')}>
              {t('externalTraining.start.namespace.label')}
            </div>
            <input
              className={lx('text-input')}
              type='text'
              value={namespaceInput}
              onChange={(e) => setNamespaceInput(e.target.value)}
              disabled={isRunning}
            />
          </div>

          <div className={lx('panel')}>
            <div className={lx('panel-title')}>
              {t('externalTraining.start.params.label')}
            </div>
            <textarea
              className={lx('params-textarea')}
              value={paramsInput}
              onChange={(e) => setParamsInput(e.target.value)}
              disabled={isRunning}
              spellCheck={false}
            />
            <div className={lx('hint')}>
              {t('externalTraining.start.params.hint')}
            </div>
          </div>
        </div>
        <div className={cx('right')}>
          <FineTuningGraph
            fineTuningType={1}
            data={graphData}
            fineStatus={fineStatus}
            fineTuningData={fineTuningData}
            progressData={progressData}
          />
        </div>
      </div>
    </div>
  );
});

function Row({ label, value }) {
  return (
    <li className={lx('meta-row')}>
      <span className={lx('meta-label')}>{label}</span>
      <span className={lx('meta-value')}>{value}</span>
    </li>
  );
}

export default ExternalFineTuningView;
