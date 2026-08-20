// External partner-container training tab — model-bound mode.
//
// Lives inside ModelDetailPage and is keyed off the LLM model row's
// training_type='external' + external_manifest_* + external_job_id columns.
//
//   - model.external_job_id is null   → render "학습 시작" form (manifest readonly,
//                                       params editable). On submit, the BFF
//                                       POST /api/external/jobs returns a
//                                       job_id which we then PATCH back onto
//                                       the model row so future visits jump
//                                       straight into monitoring.
//   - model.external_job_id is set    → render monitoring (SSE status / time /
//                                       graph + system log modal) using the
//                                       same hooks the internal LLM tab uses
//                                       with mode='external'.
//
// BFF endpoints consumed:
//   GET   /api/models?model_id={id}                  — fetch model (training_type, manifest, external_job_id)
//   GET   /api/external/jobs/{jobId}                 — job metadata (for the right-hand panel)
//   POST  /api/external/jobs                         — launch a new partner job
//   PATCH /api/models/{id}/external-job              — bind job_id onto the model row
//   GET   /api/external/jobs/{jobId}/sse-{status,time,graph}
//   GET   /api/external/jobs/{jobId}/system-log

import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { ButtonV2, Loading } from '@tango/ui-react';

import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  formatSecondsToDHMS,
} from '@src/utils';

import SimpleNav from '../SimpleNav';
import useSSEStatus from '../FineTuning/useSSEStatus';
import useSSETime from '../FineTuning/useSSEFinetuningTime';
import useSSEGraph from '../FineTuning/useSSEGraph';

import classNames from 'classnames/bind';
import style from './ExternalTraining.module.scss';

const cx = classNames.bind(style);

const STATUS_BADGE = {
  pending: { label: 'externalTraining.status.pending', color: 'gray' },
  running: { label: 'externalTraining.status.running', color: 'blue' },
  done: { label: 'externalTraining.status.done', color: 'green' },
  stop: { label: 'externalTraining.status.stop', color: 'yellow' },
  error: { label: 'externalTraining.status.error', color: 'red' },
};

const ExternalTraining = memo(function ExternalTraining({
  navList,
  data,
  ...rest
}) {
  const { t } = useTranslation();
  const { workspaceId, modelId } = data;
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const dispatch = useDispatch();

  // ── TrainingPage row (training_type / manifest / external_job_id) ──────────────
  const [model, setModel] = useState(null);
  const [modelLoading, setModelLoading] = useState(false);

  // ── Job-detail panel (only when external_job_id exists) ─────────────────
  const [jobDetail, setJobDetail] = useState(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);

  // ── SSE streams ─────────────────────────────────────────────────────────
  const [fineStatus, setFineStatus] = useState(null);
  const [progressData, setProgressData] = useState(null);
  // graphData 는 v1.0.0 에선 BFF 가 {graph:{}} 만 emit. v1.0.1+ 부터 의미 있음.
  const [_graphData, setGraphData] = useState(null);

  // ── Launch form state (only when external_job_id is null) ───────────────
  const [namespaceInput, setNamespaceInput] = useState('tango-system');
  const [paramsInput, setParamsInput] = useState('{}');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadModalComponent('FINETUNING_SYSTEM_LOG');
  }, []);

  const fetchModel = useCallback(async () => {
    if (!modelId) return;
    setModelLoading(true);
    const response = await callApi({
      url: `models?model_id=${modelId}`,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS && result) {
      setModel(result);
    } else {
      setModel(null);
      errorToastMessage(error, message);
    }
    setModelLoading(false);
  }, [modelId]);

  useEffect(() => {
    fetchModel();
  }, [fetchModel]);

  const externalJobId = model?.external_job_id || '';
  const manifestName = model?.external_manifest_name || '';
  const manifestVersion = model?.external_manifest_version || '';

  // Pull live job_detail for the metadata panel.
  useEffect(() => {
    if (!externalJobId) {
      setJobDetail(null);
      return;
    }
    let cancelled = false;
    const fetchDetail = async () => {
      setJobDetailLoading(true);
      const response = await callApi({
        url: `external/jobs/${externalJobId}`,
        method: 'get',
      });
      if (cancelled) return;
      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setJobDetail(result);
      } else {
        setJobDetail(null);
        errorToastMessage(error, message);
      }
      setJobDetailLoading(false);
    };
    fetchDetail();
    return () => {
      cancelled = true;
    };
  }, [externalJobId]);

  const fineTuningStatus = useMemo(
    () => fineStatus?.fine_tuning_status?.status,
    [fineStatus],
  );

  // SSE 는 external_job_id 가 채워진 경우에만 켠다. 첫 인자가 null/'' 이면
  // 내부 훅은 noop. (mode='external' 분기로 URL 만 외부용으로 빠짐.)
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

  // ── Pre-fill params dropdown from the manifest detail endpoint ─────────
  useEffect(() => {
    if (externalJobId) return; // already launched — form 안 보임
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
  }, [externalJobId, manifestName, manifestVersion]);

  const onStartTraining = useCallback(async () => {
    if (!manifestName || !manifestVersion) return;
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
      return;
    }
    if (!namespaceInput.trim()) {
      errorToastMessage(null, t('externalTraining.start.failed.label'));
      return;
    }
    setSubmitting(true);
    const launch = await callApi({
      url: 'external/jobs',
      method: 'post',
      body: {
        manifest_name: manifestName,
        manifest_version: manifestVersion,
        workspace_id: Number(workspaceId),
        namespace: namespaceInput.trim(),
        params: parsedParams,
      },
    });
    if (
      launch.status === STATUS_SUCCESS &&
      launch.result &&
      launch.result.job_id
    ) {
      // Bind job_id back onto the model row so future visits land in the
      // monitoring view (and so the model list page can show its status).
      const bind = await callApi({
        url: `models/${modelId}/external-job`,
        method: 'patch',
        body: { external_job_id: launch.result.job_id },
      });
      if (bind.status === STATUS_SUCCESS) {
        defaultSuccessToastMessage(
          t('externalTraining.start.success.label'),
        );
        await fetchModel(); // → external_job_id 채워짐 → 모니터링 화면 자동 전환
      } else {
        errorToastMessage(bind.error, bind.message);
      }
    } else {
      errorToastMessage(
        launch.error,
        launch.message || t('externalTraining.start.failed.label'),
      );
    }
    setSubmitting(false);
  }, [
    manifestName,
    manifestVersion,
    paramsInput,
    namespaceInput,
    workspaceId,
    modelId,
    fetchModel,
    t,
  ]);

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

  const filteredRest = useMemo(() => {
    const { tReady, dispatch: _d, trackingEvent, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  const statusBadge = STATUS_BADGE[fineTuningStatus] || null;
  const reason = fineStatus?.fine_tuning_status?.reason;

  const percent = progressData?.percent ?? 0;
  const remainingTime = progressData?.remaining_time;
  const totalEpoch = progressData?.total_epoch;
  const progressEpoch = progressData?.progress_epoch ?? 0;
  const startedAt = progressData?.start_datetime || jobDetail?.started_at || '-';

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div id='external-training-tab' className={cx('external-training')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        topButtonList={
          externalJobId ? (
            <ButtonV2
              type='outline'
              size='l'
              label={t('systemLog.label')}
              onClick={onClickSystemLog}
              disabled={!fineTuningStatus}
            />
          ) : null
        }
        titleName={
          manifestName
            ? `${manifestName}@${manifestVersion}`
            : t('externalTraining.title.label')
        }
        subTitle={model?.name || ''}
      />

      {modelLoading && (
        <div className={cx('panel-loading')}>
          <Loading />
        </div>
      )}

      {!modelLoading && !externalJobId && manifestName && (
        <div className={cx('start-form')}>
          <div className={cx('form-title')}>
            {t('externalTraining.start.title.label')}
          </div>
          <div className={cx('form-subtitle')}>
            {t('externalTraining.model.noJob.label')}
          </div>

          <div className={cx('form-row')}>
            <label className={cx('form-label')}>
              {t('externalTraining.model.manifest.label')}
            </label>
            <input
              className={cx('form-control')}
              type='text'
              value={`${manifestName}@${manifestVersion}`}
              disabled
              readOnly
            />
            <div className={cx('form-hint')}>
              {t('externalTraining.start.workspace.locked.hint')}
            </div>
          </div>

          <div className={cx('form-row')}>
            <label className={cx('form-label')}>
              {t('externalTraining.start.workspace.label')}
            </label>
            <input
              className={cx('form-control')}
              type='text'
              value={String(workspaceId ?? '')}
              disabled
              readOnly
            />
          </div>

          <div className={cx('form-row')}>
            <label className={cx('form-label')} htmlFor='ext-namespace'>
              {t('externalTraining.start.namespace.label')}
            </label>
            <input
              id='ext-namespace'
              className={cx('form-control')}
              type='text'
              value={namespaceInput}
              onChange={(e) => setNamespaceInput(e.target.value)}
            />
          </div>

          <div className={cx('form-row')}>
            <label className={cx('form-label')} htmlFor='ext-params'>
              {t('externalTraining.start.params.label')}
            </label>
            <textarea
              id='ext-params'
              className={cx('form-textarea')}
              value={paramsInput}
              onChange={(e) => setParamsInput(e.target.value)}
              spellCheck={false}
            />
            <div className={cx('form-hint')}>
              {t('externalTraining.start.params.hint')}
            </div>
          </div>

          <div className={cx('form-actions')}>
            <ButtonV2
              type='solid'
              size='l'
              colorType='skyblue'
              label={
                submitting
                  ? t('externalTraining.start.submitting.label')
                  : t('externalTraining.model.startTraining.label')
              }
              onClick={onStartTraining}
              disabled={submitting || !manifestName}
            />
          </div>
        </div>
      )}

      {!modelLoading && externalJobId && (
        <div className={cx('box')}>
          <div className={cx('left')}>
            <div className={cx('panel')}>
              <div className={cx('panel-title')}>
                {t('externalTraining.metadata.label')}
              </div>
              {jobDetailLoading && (
                <div className={cx('panel-loading')}>
                  <Loading />
                </div>
              )}
              {!jobDetailLoading && jobDetail && (
                <ul className={cx('meta-list')}>
                  <MetaRow label='Job ID' value={externalJobId} />
                  <MetaRow
                    label='Manifest'
                    value={`${jobDetail.manifest_name}@${jobDetail.manifest_version}`}
                  />
                  <MetaRow
                    label='Workspace'
                    value={String(jobDetail.workspace_id)}
                  />
                  <MetaRow label='Namespace' value={jobDetail.namespace} />
                  <MetaRow
                    label='Helm release'
                    value={jobDetail.helm_release}
                  />
                  <MetaRow label='Pod' value={jobDetail.pod_name} />
                  <MetaRow
                    label='Partner job'
                    value={jobDetail.partner_job_id || '-'}
                  />
                  <MetaRow
                    label='Started at'
                    value={String(jobDetail.started_at || '-')}
                  />
                  <MetaRow
                    label='Timeout (s)'
                    value={String(jobDetail.timeout_seconds || '-')}
                  />
                </ul>
              )}
              {!jobDetailLoading && !jobDetail && (
                <div className={cx('panel-error')}>
                  {t('externalTraining.detailFailed.label')}
                </div>
              )}
            </div>
          </div>

          <div className={cx('right')}>
            <div className={cx('status-card')}>
              <div className={cx('status-head')}>
                <div className={cx('status-label')}>
                  {t('fineTuningStatus.label')}
                </div>
                {statusBadge ? (
                  <div className={cx('badge', `badge-${statusBadge.color}`)}>
                    {t(statusBadge.label)}
                  </div>
                ) : (
                  <div className={cx('badge', 'badge-gray')}>-</div>
                )}
              </div>
              {reason && <div className={cx('reason')}>{reason}</div>}
            </div>

            <div className={cx('progress-card')}>
              <div className={cx('progress-row')}>
                <div className={cx('progress-label')}>
                  {t('externalTraining.progress.label')}
                </div>
                <div className={cx('progress-value')}>
                  {Number(percent || 0).toFixed(2)}%
                </div>
              </div>
              <div className={cx('progress-bar')}>
                <div
                  className={cx('progress-bar-fill')}
                  style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
                />
              </div>
              <div className={cx('progress-meta')}>
                <span>
                  {t('externalTraining.epoch.label')}: {progressEpoch}
                  {totalEpoch ? ` / ${totalEpoch}` : ''}
                </span>
                <span>
                  {t('externalTraining.startedAt.label')}: {startedAt}
                </span>
                <span>
                  {t('externalTraining.remaining.label')}:{' '}
                  {remainingTime != null
                    ? formatSecondsToDHMS(remainingTime)
                    : '-'}
                </span>
              </div>
            </div>

            <div className={cx('graph-card')}>
              <div className={cx('panel-title')}>
                {t('externalTraining.graph.label')}
              </div>
              <div className={cx('graph-placeholder')}>
                {t('externalTraining.graph.empty')}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

function MetaRow({ label, value }) {
  return (
    <li className={cx('meta-row')}>
      <span className={cx('meta-label')}>{label}</span>
      <span className={cx('meta-value')}>{value}</span>
    </li>
  );
}

export default ExternalTraining;
