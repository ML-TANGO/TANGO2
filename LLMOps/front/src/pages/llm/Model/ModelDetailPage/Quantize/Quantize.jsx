import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';
import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  downloadQuantizeFile,
  downloadQuantizePackage,
  getQuantizeJob,
  getQuantizeLineage,
  getQuantizePackage,
  markQuantizeLineage,
  startQuantize,
} from '@src/apis/llm/model';

import SimpleNav from '../SimpleNav';
import QuantizeModal from './QuantizeModal';
import EdgeDeployModal from './EdgeDeployModal';

import classNames from 'classnames/bind';
import style from './Quantize.module.scss';

const cx = classNames.bind(style);

const TERMINAL = ['completed', 'failed', 'cancelled'];
const POLL_MS = 3000;
const MAX_POLL_FAILS = 5; // 연속 조회 실패 시 실패 처리(무한 폴링 방지)

const lsKey = (modelId) => `sp4_quantize_${modelId}`;

const formatBytes = (n) => {
  if (!n || n <= 0) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
};

// fb_external_container ExternalJobDetail 의 partner 상태는 nested result.status.
const readStatus = (detail) =>
  detail?.result?.status || detail?.status || 'pending';

const saveBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

/**
 * 양자화·포팅 탭 (SP-4 / v0.4 3.9).
 * 학습 완료 모델 → '양자화' 버튼 → Q4/Q5/Q6 모달 → convert job 폴링 →
 * 완료 시 포팅 패키지(GGUF + inference.py + run.sh + config.json) 다운로드.
 * job_id 는 localStorage 에 모델별 저장 — 새로고침 후에도 패키지 다운로드 유지.
 */
const Quantize = memo(function Quantize({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const { modelId } = data;

  const [titleName, setTitleName] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState(null); // { jobId, targetQuant, targetDevice, prune }
  const [status, setStatus] = useState(null);
  const [pkg, setPkg] = useState(null); // { files: [{name,bytes}], ready }
  const [lineage, setLineage] = useState([]); // 4.6 양자화 이력
  const [deployOpen, setDeployOpen] = useState(false); // 3.10 Edge 배포
  const pollRef = useRef(null);

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // 모델명 (SimpleNav 타이틀용)
  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      if (alive && res.status === STATUS_SUCCESS) setTitleName(res.result?.name ?? '');
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 진행 중이던 job 복원 (localStorage)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(lsKey(modelId));
      if (raw) setJob(JSON.parse(raw));
    } catch (e) {
      /* ignore malformed */
    }
  }, [modelId]);

  const fetchLineage = useCallback(async () => {
    const res = await getQuantizeLineage(modelId);
    if (res.status === STATUS_SUCCESS) setLineage(res.result?.lineage ?? []);
  }, [modelId]);

  // 양자화 이력 (마운트 시)
  useEffect(() => {
    fetchLineage();
  }, [fetchLineage]);

  const fetchPackage = useCallback(async () => {
    const res = await getQuantizePackage(modelId, job.jobId);
    if (res.status === STATUS_SUCCESS) setPkg(res.result);
    fetchLineage(); // 패키지 ready 시 BE 가 lineage 마감 → 이력 갱신
  }, [modelId, job, fetchLineage]);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // job 상태 폴링 → 완료 시 패키지 로드
  useEffect(() => {
    if (!job?.jobId) return undefined;
    let cancelled = false;
    let failCount = 0; // 연속 조회 실패(404/네트워크) 카운트

    const onTerminal = (st) => {
      stopPoll();
      if (cancelled) return;
      if (st === 'completed') {
        fetchPackage();
      } else {
        // 실패/취소 → lineage 에 반영(영구 'running' 방지) 후 이력 갱신
        markQuantizeLineage(modelId, job.jobId, st).finally(fetchLineage);
      }
    };

    const tick = async () => {
      const res = await getQuantizeJob(job.jobId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        // tracker 재시작/GC 등으로 job 조회 실패. 무한 'running' 방지:
        // 연속 실패가 임계치를 넘으면 실패 처리(리셋 가능 + 영구 폴링 종료).
        failCount += 1;
        if (failCount >= MAX_POLL_FAILS) onTerminal('failed');
        return;
      }
      failCount = 0;
      const st = readStatus(res.result);
      setStatus(st);
      if (TERMINAL.includes(st)) onTerminal(st);
    };

    tick();
    pollRef.current = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [job, modelId, fetchPackage, fetchLineage, stopPoll]);

  const handleLaunch = useCallback(
    async (body) => {
      setSubmitting(true);
      const res = await startQuantize(modelId, body);
      setSubmitting(false);
      if (res.status === STATUS_SUCCESS && res.result?.job_id) {
        const next = {
          jobId: res.result.job_id,
          targetQuant: body.target_quant,
          targetDevice: body.target_device || '',
          prune: !!body.prune,
        };
        try {
          window.localStorage.setItem(lsKey(modelId), JSON.stringify(next));
        } catch (e) {
          /* quota — 무시, 메모리 state 로 동작 */
        }
        setPkg(null);
        setStatus('pending');
        setJob(next);
        setModalOpen(false);
        toast.success(t('quantize.started'));
        fetchLineage(); // launch 시 이력 row 생성됨 → 갱신
      } else {
        toast.error(res.message || t('quantize.start.fail'));
      }
    },
    [modelId, t, fetchLineage],
  );

  const handleReset = useCallback(() => {
    stopPoll();
    try {
      window.localStorage.removeItem(lsKey(modelId));
    } catch (e) {
      /* ignore */
    }
    setJob(null);
    setStatus(null);
    setPkg(null);
  }, [modelId, stopPoll]);

  const handleDownloadAll = useCallback(async () => {
    if (!job?.jobId) return;
    try {
      const blob = await downloadQuantizePackage(modelId, job.jobId);
      saveBlob(blob, `${titleName || 'model'}-${job.jobId.slice(0, 8)}-package.zip`);
    } catch (e) {
      toast.error(t('quantize.download.fail'));
    }
  }, [modelId, job, titleName, t]);

  const handleDownloadFile = useCallback(
    async (name) => {
      if (!job?.jobId) return;
      try {
        const blob = await downloadQuantizeFile(modelId, job.jobId, name);
        saveBlob(blob, name);
      } catch (e) {
        toast.error(t('quantize.download.fail'));
      }
    },
    [modelId, job, t],
  );

  // 이력(lineage) 행에서 직접 포팅 패키지 다운로드. 현재 추적 job(localStorage)이 실패
  // 시도여도 완료된 과거 양자화를 받을 수 있게 한다(완료 패키지 UI 고립 방지).
  const handleDownloadLineage = useCallback(
    async (jobId) => {
      if (!jobId) return;
      try {
        const blob = await downloadQuantizePackage(modelId, jobId);
        saveBlob(blob, `${titleName || 'model'}-${jobId.slice(0, 8)}-package.zip`);
      } catch (e) {
        toast.error(t('quantize.download.fail'));
      }
    },
    [modelId, titleName, t],
  );

  const isRunning = job && !TERMINAL.includes(status);
  const isFailed = status === 'failed' || status === 'cancelled';
  const ggufFile = (pkg?.files || []).find((f) => f.name.endsWith('.gguf'))?.name;

  return (
    <div id='quantize-tab' className={cx('quantize-tab')}>
      <SimpleNav navList={navList} t={t} {...filteredRest} titleName={titleName} />

      <div className={cx('container')}>
        <div className={cx('intro')}>
          <div className={cx('intro-title')}>{t('quantize.label')}</div>
          <div className={cx('intro-desc')}>{t('quantize.intro.desc')}</div>
        </div>

        {!job && (
          <div className={cx('empty')}>
            <div className={cx('empty-text')}>{t('quantize.empty')}</div>
            <ButtonV2
              colorType='blue'
              label={t('quantize.start.label')}
              onClick={() => setModalOpen(true)}
            />
          </div>
        )}

        {job && (
          <div className={cx('job-card')}>
            <div className={cx('job-row')}>
              <span className={cx('job-label')}>{t('quantize.level.label')}</span>
              <span className={cx('job-value')}>
                {String(job.targetQuant || '').toUpperCase()}
              </span>
            </div>
            {job.targetDevice && (
              <div className={cx('job-row')}>
                <span className={cx('job-label')}>{t('quantize.device.label')}</span>
                <span className={cx('job-value')}>{job.targetDevice}</span>
              </div>
            )}
            <div className={cx('job-row')}>
              <span className={cx('job-label')}>{t('quantize.status.label')}</span>
              <span className={cx('status', isFailed ? 'fail' : status === 'completed' ? 'done' : 'run')}>
                {isRunning && <span className={cx('spinner')} />}
                {t(`quantize.status.${status || 'pending'}`)}
              </span>
            </div>

            {status === 'completed' && pkg?.ready && (
              <div className={cx('package')}>
                <div className={cx('package-head')}>
                  <span className={cx('package-title')}>{t('quantize.package.label')}</span>
                  <div className={cx('package-actions')}>
                    <ButtonV2
                      type='outline'
                      size='s'
                      label={t('edgeDeploy.title')}
                      onClick={() => setDeployOpen(true)}
                    />
                    <ButtonV2
                      colorType='blue'
                      size='s'
                      label={t('quantize.download.all')}
                      onClick={handleDownloadAll}
                    />
                  </div>
                </div>
                <ul className={cx('file-list')}>
                  {pkg.files.map((f) => (
                    <li key={f.name} className={cx('file-item')}>
                      <span className={cx('file-name')}>{f.name}</span>
                      <span className={cx('file-size')}>{formatBytes(f.bytes)}</span>
                      <button
                        type='button'
                        className={cx('file-dl')}
                        onClick={() => handleDownloadFile(f.name)}
                      >
                        {t('download.label')}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {isFailed && (
              <div className={cx('error-box')}>{t('quantize.status.failHint')}</div>
            )}

            <div className={cx('job-actions')}>
              <ButtonV2
                type='outline'
                label={t('quantize.restart.label')}
                onClick={handleReset}
                disabled={isRunning}
              />
            </div>
          </div>
        )}

        {lineage.length > 0 && (
          <div className={cx('lineage')}>
            <div className={cx('lineage-title')}>{t('quantize.lineage.label')}</div>
            <table className={cx('lineage-table')}>
              <thead>
                <tr>
                  <th>{t('quantize.level.label')}</th>
                  <th>{t('quantize.device.label')}</th>
                  <th>{t('quantize.prune.col')}</th>
                  <th>{t('quantize.status.label')}</th>
                  <th>{t('createdAt.label')}</th>
                  <th>{t('download.label')}</th>
                </tr>
              </thead>
              <tbody>
                {lineage.map((l) => (
                  <tr key={l.id}>
                    <td>{String(l.quantization_type || '').toUpperCase()}</td>
                    <td>{l.target_device || '-'}</td>
                    <td>{l.prune ? 'O' : '-'}</td>
                    <td className={cx('ln-status', l.status)}>
                      {t(`quantize.status.${l.status || 'pending'}`)}
                    </td>
                    <td>{l.create_datetime || '-'}</td>
                    <td>
                      {l.status === 'completed' ? (
                        <button
                          type='button'
                          className={cx('file-dl')}
                          onClick={() => handleDownloadLineage(l.job_id)}
                        >
                          {t('download.label')}
                        </button>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <QuantizeModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleLaunch}
        submitting={submitting}
      />

      <EdgeDeployModal
        open={deployOpen}
        onClose={() => setDeployOpen(false)}
        modelName={titleName}
        jobId={job?.jobId}
        ggufFile={ggufFile}
        targetQuant={job?.targetQuant}
      />
    </div>
  );
});

export default Quantize;
